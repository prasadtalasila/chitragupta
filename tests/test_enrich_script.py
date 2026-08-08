"""scripts/enrich.py: the orchestrator -- Docling -> embed ->
BERTopic -> Pandoc/LaTeX. Each stage_* wrapper's ok/partial/
skipped/missing-binary shaping is tested directly against mocked
underlying module calls; main()'s stage-selection and per-stage
exception isolation are tested against a fully mocked STAGE_FUNCS/corpus."""

import logging
import re
import sys
import types

import pytest

import scripts.enrich as enrich_script
from src import config, render_output
from src.enrich import docling_parse, embed_index, topic_model
from src.enrich.corpus import CorpusDoc


def make_args(**overrides):
    ns = types.SimpleNamespace(
        target="host", stages=",".join(enrich_script.STAGE_ORDER),
        input=None, output_format="pdf", documentclass="article",
    )
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


class TestStageDocling:
    def test_ok_when_no_errors(self, monkeypatch):
        monkeypatch.setattr(docling_parse, "parse_corpus", lambda docs: {"a": "ok: /x"})
        result = enrich_script.stage_docling([], make_args())
        assert result["status"] == "ok"

    def test_partial_when_any_error(self, monkeypatch):
        monkeypatch.setattr(docling_parse, "parse_corpus", lambda docs: {"a": "ok: /x", "b": "error: boom"})
        result = enrich_script.stage_docling([], make_args())
        assert result["status"] == "partial"


class TestStageEmbed:
    def test_ok(self, monkeypatch):
        monkeypatch.setattr(embed_index, "build_index", lambda docs: {"a": 3})
        result = enrich_script.stage_embed([], make_args())
        assert result == {"status": "ok", "detail": {"a": 3}}


class TestStageBertopic:
    def test_ok_shapes_detail(self, monkeypatch):
        monkeypatch.setattr(
            topic_model, "run_topic_model",
            lambda docs: {"n_docs": 2, "assignments": {"a": -1, "b": -1}, "topic_info": [1, 2, 3]},
        )
        result = enrich_script.stage_bertopic([], make_args())
        assert result["status"] == "ok"
        assert result["detail"] == {"n_docs": 2, "assignments": {"a": -1, "b": -1}}
        assert "topic_info" not in result["detail"]


class TestStageProvenance:
    def test_skipped_without_input(self):
        result = enrich_script.stage_provenance([], make_args(input=None))
        assert result == {"status": "skipped", "detail": "no --input given"}

    def test_ok_when_all_formats_written(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            enrich_script.citation_provenance, "write_report",
            lambda path, formats: {"md": tmp_path / "r.md", "tex": tmp_path / "r.tex",
                                   "pdf": tmp_path / "r.pdf"})
        result = enrich_script.stage_provenance([], make_args(input="draft.md"))
        assert result["status"] == "ok"
        assert set(result["detail"]) == {"md", "tex", "pdf"}

    def test_partial_when_a_render_was_skipped(self, monkeypatch, tmp_path):
        """pandoc/pdflatex absent is a normal host condition here, so the
        stage reports partial rather than failing the run."""
        monkeypatch.setattr(
            enrich_script.citation_provenance, "write_report",
            lambda path, formats: {"md": tmp_path / "r.md"})
        result = enrich_script.stage_provenance([], make_args(input="draft.md"))
        assert result["status"] == "partial"
        assert set(result["detail"]) == {"md"}


class TestStageRender:
    def test_skipped_without_input(self):
        result = enrich_script.stage_render([], make_args(input=None))
        assert result == {"status": "skipped", "detail": "no --input given"}

    def test_missing_binary(self, monkeypatch):
        def raise_missing(*a, **k):
            raise render_output.MissingBinary("pandoc missing")
        monkeypatch.setattr(render_output, "render", raise_missing)
        result = enrich_script.stage_render([], make_args(input="draft.md"))
        assert result["status"] == "missing-binary"
        assert "pandoc missing" in result["detail"]

    def test_ok(self, monkeypatch, tmp_path):
        out = tmp_path / "draft.pdf"
        monkeypatch.setattr(render_output, "render", lambda *a, **k: out)
        result = enrich_script.stage_render([], make_args(input="draft.md"))
        assert result == {"status": "ok", "detail": str(out)}


class TestParseArgs:
    def test_defaults(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["enrich.py"])
        args = enrich_script.parse_args()
        assert args.target == "host"
        assert args.stages == ",".join(enrich_script.STAGE_ORDER)
        assert args.input is None

    def test_custom_stages(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "embed,bertopic", "--target", "docker"])
        args = enrich_script.parse_args()
        assert args.stages == "embed,bertopic"
        assert args.target == "docker"


class TestMain:
    def test_runs_only_selected_stages_and_prints_summary(self, monkeypatch, capsys):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling,embed"])

        called = []
        monkeypatch.setitem(enrich_script.STAGE_FUNCS, "docling", lambda d, a: called.append("docling") or {"status": "ok", "detail": "d"})
        monkeypatch.setitem(enrich_script.STAGE_FUNCS, "embed", lambda d, a: called.append("embed") or {"status": "ok", "detail": "e"})
        monkeypatch.setitem(enrich_script.STAGE_FUNCS, "bertopic", lambda d, a: called.append("bertopic") or {"status": "ok", "detail": "b"})

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 0
        assert called == ["docling", "embed"]  # bertopic not selected, never called
        assert "docling" in out and "ok" in out
        assert "=== Summary ===" in out
        assert "WARNING: unknown stage" not in out  # every selected name is real

    def test_reports_the_corpus_size_before_any_stage_runs(self, monkeypatch, capsys):
        """What went into the corpus decides what every stage indexes, so
        the count has to be visible while the run is still cheap to stop."""
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "embed"])
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS, "embed",
            lambda d, a: {"status": "ok", "detail": "e"},
        )

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 0
        assert "Corpus: 1 doc(s)" in out
        assert out.index("Corpus: 1 doc(s)") < out.index("=== embed ===")

    def test_warns_on_unknown_stage(self, monkeypatch, capsys):
        """Naming a stage this pipeline no longer has would otherwise be
        a silent no-op -- main() iterates STAGE_ORDER and skips anything
        unselected, so an unused name never surfaces."""
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "retired-stage,embed"])
        monkeypatch.setitem(enrich_script.STAGE_FUNCS, "embed", lambda d, a: {"status": "ok", "detail": "e"})

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 0  # a bad stage name warns, it doesn't fail the run
        assert "WARNING: unknown stage(s) retired-stage" in out
        assert "embed" in out  # the valid stage alongside it still ran

    def test_whitespace_and_empty_stage_segments_are_tolerated(self, monkeypatch, capsys):
        """`--stages "docling, embed,"` is natural to type. Without
        normalisation the space makes a real stage look unknown and the
        trailing comma puts a blank name in the warning."""
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling, embed,"])

        called = []
        monkeypatch.setitem(enrich_script.STAGE_FUNCS, "docling", lambda d, a: called.append("docling") or {"status": "ok", "detail": "d"})
        monkeypatch.setitem(enrich_script.STAGE_FUNCS, "embed", lambda d, a: called.append("embed") or {"status": "ok", "detail": "e"})

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 0
        assert called == ["docling", "embed"]
        assert "WARNING: unknown stage" not in out

    def test_stage_exception_does_not_abort_other_stages(self, monkeypatch, capsys):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling,embed"])

        def raise_boom(d, a):
            raise RuntimeError("stage exploded")

        monkeypatch.setitem(enrich_script.STAGE_FUNCS, "docling", raise_boom)
        monkeypatch.setitem(enrich_script.STAGE_FUNCS, "embed", lambda d, a: {"status": "ok", "detail": "e"})

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 0
        assert "error" in out
        assert "stage exploded" in out
        assert "embed" in out  # second stage still ran despite the first raising


class TestLogging:
    """The `configure_logging` flag exists because this script takes its
    lock *inside* main() rather than at the entrypoint, so
    logging_setup.configure() -- which must run inside the lock -- can't
    simply sit beside the SystemExit in `__main__`. Both sides of the
    flag are load-bearing: on, or a scheduled run leaves no transcript;
    off by default, or every test calling main() directly attaches
    handlers and makes a logs/ directory appear."""

    @pytest.fixture
    def _cleanup_root_handlers(self):
        root = logging.getLogger()
        before = list(root.handlers)
        yield
        for handler in root.handlers[:]:
            if handler not in before:
                root.removeHandler(handler)
                handler.close()
        logging.getLogger("scripts").setLevel(logging.NOTSET)

    def _run_one_stage(self, monkeypatch, **kwargs):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "embed"])
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS, "embed",
            lambda d, a: {"status": "ok", "detail": "e"},
        )
        return enrich_script.main(**kwargs)

    def test_the_run_is_logged_when_the_entrypoint_asks_for_it(
        self, isolated_config, monkeypatch, _cleanup_root_handlers
    ):
        """What `python scripts/enrich.py` actually does: the stage table
        it prints also lands in logs/pipeline.log, tagged with this
        script's logger name so it can be told apart from sync's lines in
        the shared file."""
        assert self._run_one_stage(monkeypatch, configure_logging=True) == 0

        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "scripts.enrich" in log_text
        assert "=== embed ===" in log_text
        assert "Corpus: 1 doc(s)" in log_text

    def test_a_dict_stage_detail_is_one_record_not_one_per_json_line(
        self, isolated_config, monkeypatch, _cleanup_root_handlers
    ):
        """Every stage but `render` returns a dict here, and the terminal
        renders it with json.dumps(indent=2). Mirrored verbatim that
        wrote a log record per JSON line, only the first timestamped --
        one event reading as six, with `grep '\\[ok\\]'` finding a header
        and none of its content. The terminal keeps the indented form;
        the file gets the same object on one line."""
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "embed"])
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS, "embed",
            lambda d, a: {"status": "ok", "detail": {"a": 3, "b": {"c": 1}}},
        )

        assert enrich_script.main(configure_logging=True) == 0

        for line in (config.LOGS_DIR / "pipeline.log").read_text().splitlines():
            assert re.match(r"^\d{4}-\d{2}-\d{2} ", line), (
                f"every record must start its own timestamped line: {line!r}"
            )
        assert '[ok] {"a": 3, "b": {"c": 1}}' in (
            config.LOGS_DIR / "pipeline.log"
        ).read_text()

    def test_calling_main_directly_leaves_no_handler_or_logs_directory(
        self, isolated_config, monkeypatch, _cleanup_root_handlers
    ):
        """The default, and why it is the default: every other test in
        this file calls main() directly. If that configured logging, they
        would each attach a handler to the root logger and create a
        logs/ directory as a side effect of asserting on stdout."""
        handlers_before = list(logging.getLogger().handlers)
        assert self._run_one_stage(monkeypatch) == 0

        assert logging.getLogger().handlers == handlers_before
        assert not config.LOGS_DIR.exists()


class TestPipelineLock:
    def test_a_concurrent_run_is_refused_with_its_own_exit_code(self, monkeypatch, capsys):
        """The enrichment stage writes content/ too, and sync's parsed-text
        writes are not atomic -- so an enrichment run overlapping a sync can
        read a half-written .txt. Exit code 2, distinct from 1, so an
        unattended caller can tell "skipped" from "failed"."""
        from src import runlock

        def refuse():
            raise runlock.AlreadyRunning("another sync or pipeline run is already running")

        monkeypatch.setattr(runlock, "pipeline_lock", lambda *a, **k: refuse())
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling"])

        assert enrich_script.main() == runlock.EXIT_ALREADY_RUNNING
        assert "already running" in capsys.readouterr().out
