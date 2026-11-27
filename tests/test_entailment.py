import sys
import types

import pytest

from chitragupta import config, entailment, install


def test_optional_stack_is_none_without_sentence_transformers(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    assert entailment.optional_stack() is None


def test_optional_stack_returns_cross_encoder_when_installed(monkeypatch):
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = object
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    assert entailment.optional_stack() is object


class FakeCrossEncoderModel:
    def __init__(self, id2label):
        self.config = types.SimpleNamespace(id2label=id2label)


class FakeCrossEncoder:
    def __init__(self, logits, id2label):
        self.logits = logits
        self.model = FakeCrossEncoderModel(id2label)
        self.calls = []

    def predict(self, pairs):
        self.calls.append(list(pairs))
        return [self.logits[pair] for pair in pairs]


def test_score_picks_the_entailment_column_by_label_not_position():
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


@pytest.mark.parametrize("spelling", ["ENTAILMENT", "Entailment", "entailment"])
def test_score_matches_the_entailment_label_whatever_its_case(spelling):
    fake = FakeCrossEncoder(
        logits={("premise", "claim"): [-10.0, 10.0, -10.0]},
        id2label={0: "CONTRADICTION", 1: spelling, 2: "NEUTRAL"},
    )
    scores = entailment.Entailer(model=fake).score([("premise", "claim")])
    assert scores[0] == pytest.approx(1.0, abs=1e-3)


def test_score_raises_a_named_error_when_no_label_is_an_entailment_label(monkeypatch):
    monkeypatch.setattr(config, "ENTAILMENT_MODEL", "some-org/not-an-nli-model")
    fake = FakeCrossEncoder(
        logits={("premise", "claim"): [-10.0, 10.0, -10.0]},
        id2label={0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"},
    )
    with pytest.raises(entailment.EntailmentLabelError) as excinfo:
        entailment.Entailer(model=fake).score([("premise", "claim")])
    message = str(excinfo.value)
    assert "some-org/not-an-nli-model" in message  # the model it resolved to
    assert "entailment_model" in message  # and the setting that named it
    for reported in ("LABEL_0", "LABEL_1", "LABEL_2"):
        assert reported in message  # and what the checkpoint actually reports


def test_score_of_no_pairs_is_no_scores_and_touches_no_model():
    class ExplodingModel:
        @property
        def model(self):
            raise AssertionError("model should not be loaded for an empty batch")

    entailer = entailment.Entailer(model=ExplodingModel())
    assert entailer.score([]) == []


def test_model_property_lazily_constructs_a_cross_encoder(monkeypatch):
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

    assert entailer.model is model
    assert built == [config.ENTAILMENT_MODEL]


def test_unavailable_reason_names_the_missing_group(monkeypatch):
    monkeypatch.setattr(entailment, "optional_stack", lambda: None)
    reason = entailment.unavailable_reason()
    assert reason is not None
    assert install.enrich_remedy() in reason


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
