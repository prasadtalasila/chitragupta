"""Every optional model tier degrades, under every way it can be absent
(#977).

Three ways a tier is absent, and each has to leave the command working
with the tier below it:

- **flag off:** the user turned it off, so it is never loaded;
- **`ImportError`:** the enrich extra is not installed;
- **load failure:** the extra is there but the model is not, the usual
  case being a host with no cached checkpoint and no network.
  `reranker.load_reranker` wraps every such failure in `RuntimeError`;
  `SentenceTransformer` raises `OSError` itself.

Before #977 the cross-encoder was loaded whatever `[enrich].rerank`
said, and only `ImportError` was caught, so a plain `corpus discover` on
such a host died with a traceback blaming a setting that was off.
"""

import sys
import types

import pytest

from chitragupta import config, discover, entailment
from chitragupta.discover import _overview, _resolve
from chitragupta.review import claim_support
from tests.test_discover import FakeModel, IndifferentReranker, prepare

PHRASE = "simulation twin"
ABSENT = {
    "ImportError": ImportError("No module named 'sentence_transformers'"),
    "RuntimeError": RuntimeError("[enrich].rerank_model could not be loaded"),
    "OSError": OSError("We couldn't connect to 'https://huggingface.co'"),
}


def _raising(failure):
    def load():
        raise failure

    return load


def _place(monkeypatch) -> None:
    """A semantic rung that works, near the digital-twin centroid."""
    FakeModel.VECTORS = {PHRASE: [1.0, 0.0]}
    monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())


@pytest.fixture
def topics(isolated_config):
    prepare(isolated_config)
    return isolated_config


class TestTheSemanticRung:
    @pytest.mark.parametrize("failure", ABSENT.values(), ids=ABSENT)
    def test_a_model_that_will_not_load_falls_back_to_vocabulary(
        self, topics, monkeypatch, capsys, failure
    ):
        monkeypatch.setattr(_resolve, "_load_model", _raising(failure))
        monkeypatch.setattr(_resolve, "_load_reranker", lambda: IndifferentReranker())
        monkeypatch.setattr(config, "RERANK", True)
        assert discover.main([PHRASE]) == 0
        out = capsys.readouterr().out
        assert "digital twin" in out
        assert "note: semantic resolution unavailable" in out


class TestTheRerankRung:
    def test_it_is_never_loaded_with_the_flag_off(self, topics, monkeypatch, capsys):
        """The reported bug: `_rescored` loaded the cross-encoder
        unconditionally, contradicting docs/CONFIG.md's "read only when
        `rerank` is on"."""
        _place(monkeypatch)

        def refuse():
            raise AssertionError("loaded the cross-encoder with [enrich].rerank = false")

        monkeypatch.setattr(_resolve, "_load_reranker", refuse)
        monkeypatch.setattr(config, "RERANK", False)
        assert discover.main([PHRASE]) == 0
        assert "rerank" not in capsys.readouterr().out

    @pytest.mark.parametrize("failure", ABSENT.values(), ids=ABSENT)
    def test_a_reranker_that_will_not_load_keeps_the_fused_order(
        self, topics, monkeypatch, capsys, failure
    ):
        _place(monkeypatch)
        monkeypatch.setattr(_resolve, "_load_reranker", _raising(failure))
        monkeypatch.setattr(config, "RERANK", True)
        assert discover.main([PHRASE]) == 0
        out = capsys.readouterr().out
        assert "digital twin" in out
        assert "note: reranking unavailable" in out

    def test_both_degraded_rungs_are_named(self, topics, monkeypatch, capsys):
        monkeypatch.setattr(_resolve, "_load_model", _raising(ABSENT["OSError"]))
        monkeypatch.setattr(_resolve, "_load_reranker", _raising(ABSENT["RuntimeError"]))
        monkeypatch.setattr(config, "RERANK", True)
        assert discover.main([PHRASE]) == 0
        out = capsys.readouterr().out
        assert "semantic resolution unavailable" in out
        assert "reranking unavailable" in out


class TestTheOverviewSnippets:
    @pytest.mark.parametrize("failure", ABSENT.values(), ids=ABSENT)
    def test_a_model_that_will_not_load_writes_the_overview_without_them(
        self, topics, monkeypatch, tmp_path, failure
    ):
        monkeypatch.setattr(_overview, "_load_model", _raising(failure))
        out = tmp_path / "overview.md"
        assert discover.main(["digital twin", "--out", str(out)]) == 0
        text = out.read_text(encoding="utf-8")
        assert "# digital twin" in text
        assert "snippet" in text.lower()


class TestTheEntailmentAid:
    """The review layer's optional tier, under the same three cases. It
    has no flag of its own: `review support` is run by hand, so asking
    for it is the switch. The model still loads at the first claim
    scored, so a draft with nothing to score pays nothing."""

    def _cross_encoder(self, monkeypatch, failure):
        def construct(_model_id):
            raise failure

        module = types.ModuleType("sentence_transformers")
        module.CrossEncoder = construct
        monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    @pytest.mark.parametrize(
        "failure", [ABSENT["RuntimeError"], ABSENT["OSError"]], ids=["RuntimeError", "OSError"]
    )
    def test_a_model_that_will_not_load_is_a_reason_not_a_traceback(self, monkeypatch, failure):
        self._cross_encoder(monkeypatch, failure)
        with pytest.raises(entailment.EntailmentUnavailable) as raised:
            entailment.Entailer().model  # pylint: disable=expression-not-assigned
        assert config.ENTAILMENT_MODEL in str(raised.value)
        assert str(failure) in str(raised.value)

    def test_the_aid_reports_not_run_and_exits_zero(self, isolated_config, monkeypatch, capsys):
        draft = isolated_config.DRAFTS_DIR / "t" / "d.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("A claim [@p1].\n", encoding="utf-8")
        monkeypatch.setattr(entailment, "open_entailer", lambda: (entailment.Entailer(), None))

        def unavailable(*_args):
            raise entailment.EntailmentUnavailable("the entailment model 'm' could not be loaded")

        monkeypatch.setattr(claim_support, "build_report", unavailable)
        assert claim_support.main([str(draft)]) == 0
        assert "support: not run -- the entailment model 'm'" in capsys.readouterr().err

    def test_without_the_extra_it_is_still_the_install_hint(self, monkeypatch):
        monkeypatch.setattr(entailment, "optional_stack", lambda: None)
        entailer, reason = entailment.open_entailer()
        assert entailer is None
        assert "enrich" in reason


class TestTheNoteIsOneLine:
    """huggingface's load errors run to several lines; a degradation
    note is one line of a printed view."""

    def test_only_the_first_line_of_the_failure_is_kept(self):
        _model, note = _resolve.optional_model(
            _raising(OSError("We couldn't connect.\nCheck your internet connection.")), "tier"
        )
        assert note == "tier unavailable (the model would not load: We couldn't connect.)"

    def test_a_failure_with_no_message_is_named_by_its_type(self):
        _model, note = _resolve.optional_model(_raising(OSError()), "tier")
        assert note == "tier unavailable (the model would not load: OSError)"

    def test_the_entailment_reason_is_trimmed_the_same_way(self, monkeypatch):
        for failure, shown in ((OSError("first\nsecond"), "(first)"), (OSError(), "(OSError)")):
            TestTheEntailmentAid()._cross_encoder(monkeypatch, failure)
            with pytest.raises(entailment.EntailmentUnavailable) as raised:
                entailment.Entailer().model  # pylint: disable=expression-not-assigned
            assert shown in str(raised.value)
            assert "second" not in str(raised.value)
