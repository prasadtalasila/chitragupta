"""chitragupta/enrich/__main__.py: the orchestrator -- Docling -> embed -> BERTopic.
Each stage_* wrapper's ok/partial/skipped/missing-binary shaping is
tested directly against mocked underlying module calls; main()'s
stage-selection and per-stage exception isolation are tested against a
fully mocked STAGE_FUNCS/corpus.

4.0.0 removed the `provenance` and `render` stages -- both were
three-line wrappers around a tier-1 command, and hosting them here made
the enrichment layer import the review and drafting layers and made two
per-draft commands wait on sync's write lock. Their tests went with
them; the commands themselves are covered by
tests/test_citation_provenance.py and tests/test_render_output.py."""

import logging
import re
import sys
import types
from pathlib import Path

import pytest

from chitragupta.enrich import __main__ as enrich_script
from chitragupta import config
from chitragupta.enrich import docling_parse, embed_index, topic_model
from chitragupta.enrich.corpus import CorpusDoc


def make_args(**overrides):
    ns = types.SimpleNamespace(
        target="host", stages=",".join(enrich_script.STAGE_ORDER), for_draft=None,
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


class TestParseArgs:
    def test_defaults(self, monkeypatch):
        """`--stages` parses as None rather than the joined list, so
        main() can tell "every stage, because you said so" apart from
        "every stage, because you said nothing" -- --for-draft narrows
        the second and is refused against the first."""
        monkeypatch.setattr(sys, "argv", ["enrich.py"])
        args = enrich_script.parse_args()
        assert args.target == "host"
        assert args.stages is None
        assert args.for_draft is None

    def test_custom_stages(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "embed,bertopic", "--target", "docker"])
        args = enrich_script.parse_args()
        assert args.stages == "embed,bertopic"
        assert args.target == "docker"

    def test_help_states_both_halves_of_the_stages_default(self, monkeypatch, capsys):
        """argparse prints no "(default: ...)" of its own for --stages,
        so this help string is the only place the default is written
        down -- and it now depends on whether --for-draft was given."""
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--help"])
        with pytest.raises(SystemExit):
            enrich_script.parse_args()
        # Whitespace-collapsed: argparse rewraps help text to the
        # terminal width, so the sentence is split across lines at a
        # column this test has no business predicting.
        out = re.sub(r"\s+", " ", capsys.readouterr().out)
        assert "default: all three, or docling alone with --for-" in out


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
        assert "docling" in out
        assert "ok" in out
        assert "=== Summary ===" in out
        assert "WARNING: unknown stage" not in out  # every selected name is real

    def test_no_stages_argument_runs_every_stage(self, monkeypatch):
        """The documented default, and the one an unattended run gets.
        Worth pinning separately from `--stages docling,embed` because
        the default is no longer the literal argparse default -- main()
        resolves it, and --for-draft resolves it differently."""
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py"])

        called = []
        for name in enrich_script.STAGE_ORDER:
            monkeypatch.setitem(
                enrich_script.STAGE_FUNCS, name,
                lambda d, a, _n=name: called.append(_n) or {"status": "ok", "detail": _n},
            )

        assert enrich_script.main() == 0
        assert called == enrich_script.STAGE_ORDER

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


class TestForDraftScope:
    """`--for-draft content/drafts/<slug>.md` (issue #52).

    The enrichment layer's unit of work is the corpus, which is right
    for `embed` and `bertopic` and expensive for nothing in particular
    when what you want is quotable passages for the eleven papers a
    chapter cites. The flag narrows the document list to those papers.

    Two properties are what make it safe to offer, and both are pinned
    here: the narrowing never reaches the two stages whose artefact has
    no partial form (`embed`'s Chroma collection records no completeness
    marker; `bertopic` overwrites content/topics.json outright), and a
    scope that selects nothing says so rather than running a stage over
    an empty corpus.
    """

    @pytest.fixture
    def corpus_of_three(self, monkeypatch):
        docs = [
            CorpusDoc(citekey="a2024", title="A", pdf_path="/tmp/a.pdf"),
            CorpusDoc(citekey="b2025", title="B", pdf_path="/tmp/b.pdf"),
            CorpusDoc(citekey="c2026", title="C", pdf_path="/tmp/c.pdf"),
        ]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        return docs

    @pytest.fixture
    def recorded_stages(self, monkeypatch):
        """Every stage replaced by a recorder of the corpus it was
        handed, so a test can assert both which stages ran and what
        reached them without any of the real work happening."""
        calls = {}

        def recorder(name):
            def stage(docs, args):
                calls[name] = [doc.citekey for doc in docs]
                return {"status": "ok", "detail": name}
            return stage

        for name in enrich_script.STAGE_ORDER:
            monkeypatch.setitem(enrich_script.STAGE_FUNCS, name, recorder(name))
        return calls

    @pytest.fixture
    def draft(self, tmp_path):
        path = tmp_path / "chapter.md"
        path.write_text("A claim [@a2024] and another [@c2026], and @a2024 again.\n")
        return path

    def test_only_the_cited_papers_reach_docling(
        self, corpus_of_three, recorded_stages, draft, monkeypatch
    ):
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        assert enrich_script.main() == 0
        assert recorded_stages["docling"] == ["a2024", "c2026"]  # b2025 is uncited

    def test_the_count_says_what_was_left_out_not_only_what_was_kept(
        self, corpus_of_three, recorded_stages, draft, monkeypatch, capsys
    ):
        """"Corpus: 2 doc(s)" would read as a two-paper corpus. The
        denominator is what tells a reader the run was narrowed, and the
        draft path is what tells them by what."""
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        enrich_script.main()
        out = capsys.readouterr().out

        assert "Corpus: 2 of 3 doc(s)" in out
        assert f"scoped to {draft}" in out

    def test_a_bare_for_draft_runs_docling_alone(
        self, corpus_of_three, recorded_stages, draft, monkeypatch
    ):
        """Passages for the cited papers are what the flag is for, and
        embed/bertopic must not run at all -- a scoped invocation that
        quietly rebuilt the whole corpus would be an hour of work nobody
        asked for."""
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        assert enrich_script.main() == 0
        assert set(recorded_stages) == {"docling"}

    @pytest.mark.parametrize("stage", ["embed", "bertopic"])
    def test_scoping_a_whole_corpus_stage_is_refused(
        self, recorded_stages, draft, monkeypatch, capsys, stage
    ):
        """A tier, not a ladder: it stops and names what it cannot give
        you. Running the stage corpus-wide instead would be an hour of
        work the flag exists to avoid, and running it scoped would leave
        an artefact that answers as though it covered the corpus."""
        def never(*_a, **_k):
            raise AssertionError("the corpus must not be built for a refused run")

        monkeypatch.setattr(enrich_script.corpus, "build_corpus", never)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft), "--stages", stage])

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == enrich_script.EXIT_BAD_SCOPE
        assert f"--for-draft cannot scope {stage}" in out
        assert f"--stages {stage}" in out  # the corpus-wide command to run instead
        assert recorded_stages == {}

    def test_refusing_names_every_offending_stage_at_once(
        self, draft, monkeypatch, capsys
    ):
        """Reporting one at a time would make the user re-run to
        discover the second."""
        monkeypatch.setattr(
            sys, "argv",
            ["enrich.py", "--for-draft", str(draft), "--stages", "docling,embed,bertopic"],
        )

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == enrich_script.EXIT_BAD_SCOPE
        assert "cannot scope bertopic or embed" in out

    def test_a_cited_citekey_the_ledger_lacks_is_named(
        self, corpus_of_three, recorded_stages, monkeypatch, tmp_path, capsys
    ):
        """The hard gate normally keeps these out of a passing draft,
        but a draft written before a re-export has them. Enriching the
        remainder silently would report a smaller number with nothing to
        explain it."""
        draft = tmp_path / "stale.md"
        draft.write_text("Cited [@a2024] and [@gone2019].\n")
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        assert enrich_script.main() == 0
        out = capsys.readouterr().out

        assert "1 cited citekey(s) are not in the ledger" in out
        assert "gone2019" in out
        assert recorded_stages["docling"] == ["a2024"]  # the rest still ran

    def test_a_scope_matching_nothing_stops_before_the_stage(
        self, corpus_of_three, recorded_stages, monkeypatch, tmp_path, capsys
    ):
        """parse_corpus([]) would report `ok` over zero documents, which
        reads like a successful run."""
        draft = tmp_path / "stale.md"
        draft.write_text("Nothing here is in the ledger [@gone2019].\n")
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == enrich_script.EXIT_BAD_SCOPE
        assert "nothing to enrich" in out
        assert "python -m chitragupta.corpus sync" in out
        assert recorded_stages == {}

    def test_every_stage_now_reads_the_corpus_so_an_empty_scope_always_stops(
        self, corpus_of_three, recorded_stages, monkeypatch, tmp_path, capsys
    ):
        """CORPUS_STAGES == STAGE_ORDER since 4.0.0 removed the two
        per-draft passthroughs, so there is no longer a selection that an
        empty scope could leave work for. The carve-out that used to
        exist for `render`/`provenance` went with them."""
        assert set(enrich_script.CORPUS_STAGES) == set(enrich_script.STAGE_ORDER)

        draft = tmp_path / "stale.md"
        draft.write_text("Nothing here is in the ledger [@gone2019].\n")
        monkeypatch.setattr(
            sys, "argv", ["enrich.py", "--for-draft", str(draft), "--stages", "docling"],
        )

        assert enrich_script.main() == enrich_script.EXIT_BAD_SCOPE
        assert "nothing to enrich" in capsys.readouterr().out
        assert recorded_stages == {}

    def test_an_unreadable_draft_stops_before_the_lock(
        self, recorded_stages, monkeypatch, tmp_path, capsys
    ):
        def never(*_a, **_k):
            raise AssertionError("the corpus must not be built for an unreadable draft")

        monkeypatch.setattr(enrich_script.corpus, "build_corpus", never)
        missing = tmp_path / "does-not-exist.md"
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(missing)])

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == enrich_script.EXIT_BAD_SCOPE
        assert f"cannot read --for-draft {missing}" in out

    def test_a_draft_that_is_not_utf8_stops_instead_of_raising(
        self, recorded_stages, monkeypatch, tmp_path, capsys
    ):
        """UnicodeDecodeError is a ValueError, not an OSError, so it
        slips past the unreadable-file branch and would reach the user
        as a traceback -- from a script whose whole argument-validation
        style is a one-line message and an exit code.

        Read strictly rather than with errors="replace" on purpose: a
        replacement character lands inside whatever citekey the bad byte
        belonged to, so the tolerant read would scope the run to a
        quietly wrong set of papers instead of stopping.
        """
        def never(*_a, **_k):
            raise AssertionError("the corpus must not be built for an undecodable draft")

        monkeypatch.setattr(enrich_script.corpus, "build_corpus", never)
        draft = tmp_path / "latin1.md"
        draft.write_bytes("Caf\xe9 in latin-1, then [@a2024].\n".encode("latin-1"))
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == enrich_script.EXIT_BAD_SCOPE
        assert f"cannot read --for-draft {draft} as UTF-8" in out
        assert "re-save it in that encoding" in out

    def test_a_draft_with_no_citations_stops_and_says_how_to_proceed(
        self, recorded_stages, monkeypatch, tmp_path, capsys
    ):
        """An empty scope from an uncited draft is not "enrich nothing"
        and not "enrich everything" -- neither is obviously what was
        meant, so the run stops and names the flag to drop."""
        def never(*_a, **_k):
            raise AssertionError("the corpus must not be built for an uncited draft")

        monkeypatch.setattr(enrich_script.corpus, "build_corpus", never)
        draft = tmp_path / "uncited.md"
        draft.write_text("# A chapter that cites nothing at all.\n")
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == enrich_script.EXIT_BAD_SCOPE
        assert "no citations found" in out
        assert "Drop --for-draft" in out


class TestDraftCitekeys:
    def test_repeats_collapse_and_both_syntaxes_are_read(self, tmp_path):
        draft = tmp_path / "d.md"
        draft.write_text("[@a2024] again [@a2024], and \\citep{b2025} too.\n")
        assert enrich_script.draft_citekeys(draft) == {"a2024", "b2025"}

    def test_a_citation_wrapped_across_lines_contributes_every_key(self, tmp_path):
        """The reason this calls extract_citekeys() and not the
        per-line wrapper: a `\\citep{...}` argument spanning two lines is
        common once a claim rests on more than a couple of papers, and a
        per-line scan matches neither line, so both papers would be left
        out of the scope with nothing said."""
        draft = tmp_path / "d.md"
        draft.write_text("A well-supported claim \\citep{a2024,\n    b2025}.\n")
        assert enrich_script.draft_citekeys(draft) == {"a2024", "b2025"}

    def test_a_citation_inside_a_code_fence_is_not_one(self, tmp_path):
        """Inherited from the gate rather than re-decided here: a
        teaching draft's `@dataclass` is not a paper, and scoping a run
        to it would look for a citekey no ledger has."""
        draft = tmp_path / "d.md"
        draft.write_text("Real [@a2024].\n\n```python\n@dataclass\nclass X: ...\n```\n")
        assert enrich_script.draft_citekeys(draft) == {"a2024"}


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
        logging.getLogger("chitragupta").setLevel(logging.NOTSET)

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
        """What `python -m chitragupta.enrich` actually does: the stage table
        it prints also lands in logs/pipeline.log, tagged with this
        script's logger name so it can be told apart from sync's lines in
        the shared file."""
        assert self._run_one_stage(monkeypatch, configure_logging=True) == 0

        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "chitragupta.enrich" in log_text
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
        from chitragupta import runlock

        def refuse():
            raise runlock.AlreadyRunning("another sync or pipeline run is already running")

        monkeypatch.setattr(runlock, "pipeline_lock", lambda *a, **k: refuse())
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling"])

        assert enrich_script.main() == runlock.EXIT_ALREADY_RUNNING
        assert "already running" in capsys.readouterr().out
