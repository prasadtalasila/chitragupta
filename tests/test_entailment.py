"""chitragupta/entailment.py: the one seam that reaches the optional
NLI cross-encoder. sentence_transformers is mocked via sys.modules,
the same way tests/test_overlap_embed.py does it for the embedding
stack -- imported lazily inside functions, so patching sys.modules
before the call shadows the real package without needing it
uninstalled."""

import sys
import types

import pytest

from chitragupta import config, entailment


def test_optional_stack_is_none_without_sentence_transformers(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    assert entailment.optional_stack() is None


def test_optional_stack_returns_cross_encoder_when_installed(monkeypatch):
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = object
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    assert entailment.optional_stack() is object


class FakeCrossEncoderModel:
    """Stands in for the underlying transformers model CrossEncoder
    wraps -- only `.config.id2label` is read off it."""

    def __init__(self, id2label):
        self.config = types.SimpleNamespace(id2label=id2label)


class FakeCrossEncoder:
    """Stands in for sentence_transformers.CrossEncoder itself.

    `logits` is keyed by the exact (premise, hypothesis) pair handed
    to `.predict()`, so a test can say "this pair scores these raw
    logits" without a real model anywhere.
    """

    def __init__(self, logits, id2label):
        self.logits = logits
        self.model = FakeCrossEncoderModel(id2label)
        self.calls = []

    def predict(self, pairs):
        self.calls.append(list(pairs))
        return [self.logits[pair] for pair in pairs]


def test_score_picks_the_entailment_column_by_label_not_position():
    """The label order is a model property, not a convention this
    module may assume -- entailment sits at index 1 here and would
    break silently if the code hard-coded index 0. Same raw logits as
    the contradiction test below; only the label mapping differs, and
    that alone must flip which score comes out."""
    fake = FakeCrossEncoder(
        logits={("premise a", "claim a"): [-10.0, 10.0, -10.0]},
        id2label={0: "contradiction", 1: "entailment", 2: "neutral"},
    )
    entailer = entailment.Entailer(model=fake)
    scores = entailer.score([("premise a", "claim a")])
    assert len(scores) == 1
    assert scores[0] == pytest.approx(1.0, abs=1e-3)


def test_score_is_low_for_a_contradiction_logit():
    fake = FakeCrossEncoder(
        logits={("premise b", "claim b"): [-10.0, 10.0, -10.0]},
        id2label={0: "entailment", 1: "contradiction", 2: "neutral"},
    )
    entailer = entailment.Entailer(model=fake)
    scores = entailer.score([("premise b", "claim b")])
    assert scores[0] == pytest.approx(0.0, abs=1e-3)


def test_score_handles_several_pairs_in_one_call():
    fake = FakeCrossEncoder(
        logits={
            ("p1", "c1"): [0.0, 0.0, 0.0],
            ("p2", "c2"): [-10.0, 10.0, -10.0],
        },
        id2label={0: "contradiction", 1: "entailment", 2: "neutral"},
    )
    entailer = entailment.Entailer(model=fake)
    scores = entailer.score([("p1", "c1"), ("p2", "c2")])
    assert scores[0] == pytest.approx(1 / 3, abs=1e-3)
    assert scores[1] == pytest.approx(1.0, abs=1e-3)


def test_score_of_no_pairs_is_no_scores_and_touches_no_model():
    """An empty batch must not even reach `.model` -- the property
    would otherwise try to load the real model for zero work."""

    class ExplodingModel:
        @property
        def model(self):
            raise AssertionError("model should not be loaded for an empty batch")

    entailer = entailment.Entailer(model=ExplodingModel())
    assert entailer.score([]) == []


def test_model_property_lazily_constructs_a_cross_encoder(monkeypatch):
    """No model handed to the constructor: first access to `.model`
    must import sentence_transformers and build a CrossEncoder from
    config.ENTAILMENT_MODEL, then cache it -- the same lazy-load shape
    as chitragupta/overlap_chroma.py's Embedder.model."""
    built = []

    class RecordingCrossEncoder:
        def __init__(self, model_name):
            self.model_name = model_name
            built.append(model_name)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = RecordingCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    entailer = entailment.Entailer()
    model = entailer.model
    assert isinstance(model, RecordingCrossEncoder)
    assert model.model_name == config.ENTAILMENT_MODEL
    assert built == [config.ENTAILMENT_MODEL]

    # Second access must not build a second one.
    assert entailer.model is model
    assert built == [config.ENTAILMENT_MODEL]


def test_unavailable_reason_names_the_missing_group(monkeypatch):
    monkeypatch.setattr(entailment, "optional_stack", lambda: None)
    reason = entailment.unavailable_reason()
    assert reason is not None
    assert "enrich" in reason


def test_unavailable_reason_is_none_when_the_stack_is_present(monkeypatch):
    monkeypatch.setattr(entailment, "optional_stack", object)
    assert entailment.unavailable_reason() is None


def test_open_entailer_returns_reason_when_unavailable(monkeypatch):
    monkeypatch.setattr(entailment, "optional_stack", lambda: None)
    entailer, reason = entailment.open_entailer()
    assert entailer is None
    assert reason is not None


def test_open_entailer_returns_an_entailer_when_available(monkeypatch):
    monkeypatch.setattr(entailment, "optional_stack", object)
    entailer, reason = entailment.open_entailer()
    assert isinstance(entailer, entailment.Entailer)
    assert reason is None
