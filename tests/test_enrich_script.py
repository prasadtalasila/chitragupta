import logging
import re
import sys
import types

import pytest

from chitragupta.enrich import __main__ as enrich_script
from chitragupta import config
from chitragupta.enrich import (
    docling_parse,
    embed_index,
    keyword_extract,
    topic_converge,
    topic_graph,
    topic_model,
    topic_seeding,
)
from chitragupta.enrich.corpus import CorpusDoc


def make_args(**overrides):
    ns = types.SimpleNamespace(
        target="host",
        stages=",".join(enrich_script.STAGE_ORDER),
        for_draft=None,
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
        monkeypatch.setattr(
            docling_parse, "parse_corpus", lambda docs: {"a": "ok: /x", "b": "error: boom"}
        )
        result = enrich_script.stage_docling([], make_args())
        assert result["status"] == "partial"


class TestStageEmbed:
    def test_ok(self, monkeypatch):
        monkeypatch.setattr(embed_index, "build_index", lambda docs: {"a": 3})
        result = enrich_script.stage_embed([], make_args())
        assert result == {"status": "ok", "detail": {"a": 3}}


class TestStageBertopic:
    def test_ok_shapes_detail(self, isolated_config, monkeypatch):
        monkeypatch.setattr(
            topic_model,
            "run_topic_model",
            lambda docs: {"n_docs": 2, "assignments": {"a": -1, "b": -1}, "topic_info": [1, 2, 3]},
        )
        result = enrich_script.stage_bertopic([], make_args())
        assert result["status"] == "ok"
        assert result["detail"] == {"n_docs": 2, "assignments": {"a": -1, "b": -1}}
        assert "topic_info" not in result["detail"]

    def test_the_seed_list_never_reaches_the_clustering(self, isolated_config, monkeypatch):
        isolated_config.SEED_TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.SEED_TOPICS_PATH.write_text('topics = ["digital twin"]', encoding="utf-8")
        seen = {}
        monkeypatch.setattr(
            topic_model,
            "run_topic_model",
            lambda docs, **kw: (
                seen.update(kw=kw) or {"n_docs": 0, "assignments": {}, "topic_info": []}
            ),
        )
        enrich_script.stage_bertopic([], make_args())
        assert seen["kw"] == {}


class TestStageExtractKeywords:
    def test_delegates_to_keyword_extract(self, monkeypatch):
        monkeypatch.setattr(
            keyword_extract, "run_stage", lambda docs: {"status": "ok", "detail": {"phrases": 3}}
        )
        result = enrich_script.stage_extract_keywords([], make_args())
        assert result == {"status": "ok", "detail": {"phrases": 3}}

    def test_runs_after_bertopic_and_before_seed_topics(self):
        order = enrich_script.STAGE_ORDER
        assert order.index("bertopic") < order.index("extract-keywords")
        assert order.index("extract-keywords") < order.index("seed-topics")

    def test_refused_with_a_draft_scope(self):
        assert "extract-keywords" in enrich_script.SCOPE_REFUSED


class TestStageSeedTopics:
    def test_skipped_when_the_author_wrote_no_seed_file(self, isolated_config):
        result = enrich_script.stage_seed_topics([], make_args())
        assert result["status"] == "skipped"
        assert "no seed topics" in result["detail"]["reason"]

    def test_ok_shapes_detail_as_counts(self, isolated_config, monkeypatch):
        isolated_config.SEED_TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.SEED_TOPICS_PATH.write_text('topics = ["digital twin"]', encoding="utf-8")
        monkeypatch.setattr(
            topic_seeding,
            "run_topic_seeding",
            lambda docs, phrases: {
                "n_docs": 3,
                "topics": [
                    {
                        "phrase": "digital twin",
                        "matches": [{"citekey": "a", "score": 0.9}, {"citekey": "b", "score": 0.7}],
                    }
                ],
                "unmatched": ["c"],
            },
        )
        result = enrich_script.stage_seed_topics([], make_args())
        assert result["status"] == "ok"
        assert result["detail"] == {"n_docs": 3, "matched": {"digital twin": 2}, "unmatched": 1}


class TestSeedPhraseUnion:
    def _capture(self, monkeypatch, module, func_name):
        seen = {}
        monkeypatch.setattr(
            module,
            func_name,
            lambda docs, phrases: (
                seen.update(phrases=phrases) or {"n_docs": 0, "topics": [], "unmatched": []}
            ),
        )
        return seen

    def test_seed_topics_reads_both_files(self, isolated_config, monkeypatch):
        isolated_config.SEED_TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.SEED_TOPICS_PATH.write_text(
            'topics = ["Digital Twin", "IoT"]', encoding="utf-8"
        )
        isolated_config.KEYWORDS_PATH.write_text(
            'topics = ["digital twin", "edge computing"]', encoding="utf-8"
        )
        seen = self._capture(monkeypatch, topic_seeding, "run_topic_seeding")
        result = enrich_script.stage_seed_topics([], make_args())
        assert result["status"] == "ok"
        assert seen["phrases"] == ("Digital Twin", "IoT", "edge computing")

    def test_extracted_keywords_alone_run_the_stage(self, isolated_config, monkeypatch):
        isolated_config.KEYWORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.KEYWORDS_PATH.write_text(
            'topics = ["federated learning"]', encoding="utf-8"
        )
        seen = self._capture(monkeypatch, topic_seeding, "run_topic_seeding")
        result = enrich_script.stage_seed_topics([], make_args())
        assert result["status"] == "ok"
        assert seen["phrases"] == ("federated learning",)

    def test_converge_reads_the_same_union(self, isolated_config, monkeypatch):
        isolated_config.SEED_TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.SEED_TOPICS_PATH.write_text('topics = ["Digital Twin"]', encoding="utf-8")
        isolated_config.KEYWORDS_PATH.write_text('topics = ["edge computing"]', encoding="utf-8")
        seen = {}
        monkeypatch.setattr(
            topic_converge,
            "run_stage",
            lambda docs, phrases: seen.update(phrases=phrases) or {"status": "ok", "detail": {}},
        )
        enrich_script.stage_converge([], make_args())
        assert seen["phrases"] == ("Digital Twin", "edge computing")

    def test_skip_message_names_both_sources(self, isolated_config):
        result = enrich_script.stage_seed_topics([], make_args())
        assert result["status"] == "skipped"
        reason = result["detail"]["reason"]
        assert str(isolated_config.SEED_TOPICS_PATH) in reason
        assert str(isolated_config.KEYWORDS_PATH) in reason


class TestParseArgs:
    def test_defaults(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["enrich.py"])
        args = enrich_script.parse_args()
        assert args.target == "host"
        assert args.stages is None
        assert args.for_draft is None

    def test_custom_stages(self, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["enrich.py", "--stages", "embed,bertopic", "--target", "docker"]
        )
        args = enrich_script.parse_args()
        assert args.stages == "embed,bertopic"
        assert args.target == "docker"

    def test_help_states_both_halves_of_the_stages_default(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--help"])
        with pytest.raises(SystemExit):
            enrich_script.parse_args()
        out = re.sub(r"\s+", " ", capsys.readouterr().out)
        assert "default: all seven, or docling alone with --for-" in out


class TestMain:
    @pytest.fixture(autouse=True)
    def _isolated(self, isolated_config):
        pass

    def test_runs_only_selected_stages_and_prints_summary(self, monkeypatch, capsys):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling,embed"])

        called = []
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS,
            "docling",
            lambda d, a: called.append("docling") or {"status": "ok", "detail": "d"},
        )
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS,
            "embed",
            lambda d, a: called.append("embed") or {"status": "ok", "detail": "e"},
        )
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS,
            "bertopic",
            lambda d, a: called.append("bertopic") or {"status": "ok", "detail": "b"},
        )

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 0
        assert called == ["docling", "embed"]  # bertopic not selected, never called
        assert "docling" in out
        assert "ok" in out
        assert "=== Summary ===" in out
        assert "WARNING: unknown stage" not in out  # every selected name is real

    def test_no_stages_argument_runs_every_stage(self, monkeypatch):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py"])

        called = []
        for name in enrich_script.STAGE_ORDER:
            monkeypatch.setitem(
                enrich_script.STAGE_FUNCS,
                name,
                lambda d, a, _n=name: called.append(_n) or {"status": "ok", "detail": _n},
            )

        assert enrich_script.main() == 0
        assert called == enrich_script.STAGE_ORDER

    def test_reports_the_corpus_size_before_any_stage_runs(self, monkeypatch, capsys):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "embed"])
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS,
            "embed",
            lambda d, a: {"status": "ok", "detail": "e"},
        )

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 0
        assert "Corpus: 1 doc(s)" in out
        assert out.index("Corpus: 1 doc(s)") < out.index("=== embed ===")

    def test_warns_on_unknown_stage(self, monkeypatch, capsys):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "retired-stage,embed"])
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS, "embed", lambda d, a: {"status": "ok", "detail": "e"}
        )

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 0  # a bad stage name warns, it doesn't fail the run
        assert "WARNING: unknown stage(s) retired-stage" in out
        assert "embed" in out  # the valid stage alongside it still ran

    def test_whitespace_and_empty_stage_segments_are_tolerated(self, monkeypatch, capsys):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling, embed,"])

        called = []
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS,
            "docling",
            lambda d, a: called.append("docling") or {"status": "ok", "detail": "d"},
        )
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS,
            "embed",
            lambda d, a: called.append("embed") or {"status": "ok", "detail": "e"},
        )

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
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS, "embed", lambda d, a: {"status": "ok", "detail": "e"}
        )

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == 1
        assert "error" in out
        assert "stage exploded" in out
        assert "embed" in out  # second stage still ran despite the first raising
        assert "1 stage(s) errored: docling" in out

    def test_a_run_with_no_errored_stage_still_exits_zero(self, monkeypatch, capsys):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling,embed"])
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS, "docling", lambda d, a: {"status": "skipped", "detail": "d"}
        )
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS, "embed", lambda d, a: {"status": "ok", "detail": "e"}
        )
        assert enrich_script.main() == 0
        assert "stage(s) errored" not in capsys.readouterr().out


class TestForDraftScope:
    @pytest.fixture(autouse=True)
    def _isolated(self, isolated_config):
        pass

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
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        enrich_script.main()
        out = capsys.readouterr().out

        assert "Corpus: 2 of 3 doc(s)" in out
        assert f"scoped to {draft}" in out

    def test_a_bare_for_draft_runs_docling_alone(
        self, corpus_of_three, recorded_stages, draft, monkeypatch
    ):
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--for-draft", str(draft)])

        assert enrich_script.main() == 0
        assert set(recorded_stages) == {"docling"}

    @pytest.mark.parametrize("stage", ["embed", "bertopic"])
    def test_scoping_a_whole_corpus_stage_is_refused(
        self, recorded_stages, draft, monkeypatch, capsys, stage
    ):
        def never(*_a, **_k):
            raise AssertionError("the corpus must not be built for a refused run")

        monkeypatch.setattr(enrich_script.corpus, "build_corpus", never)
        monkeypatch.setattr(
            sys, "argv", ["enrich.py", "--for-draft", str(draft), "--stages", stage]
        )

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == enrich_script.EXIT_BAD_SCOPE
        assert f"--for-draft cannot scope {stage}" in out
        assert f"--stages {stage}" in out  # the corpus-wide command to run instead
        assert recorded_stages == {}

    def test_refusing_names_every_offending_stage_at_once(self, draft, monkeypatch, capsys):
        monkeypatch.setattr(
            sys,
            "argv",
            ["enrich.py", "--for-draft", str(draft), "--stages", "docling,embed,bertopic"],
        )

        rc = enrich_script.main()
        out = capsys.readouterr().out

        assert rc == enrich_script.EXIT_BAD_SCOPE
        assert "cannot scope bertopic or embed" in out

    def test_a_cited_citekey_the_ledger_lacks_is_named(
        self, corpus_of_three, recorded_stages, monkeypatch, tmp_path, capsys
    ):
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
        assert set(enrich_script.CORPUS_STAGES) == set(enrich_script.STAGE_ORDER)

        draft = tmp_path / "stale.md"
        draft.write_text("Nothing here is in the ledger [@gone2019].\n")
        monkeypatch.setattr(
            sys,
            "argv",
            ["enrich.py", "--for-draft", str(draft), "--stages", "docling"],
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
        draft = tmp_path / "d.md"
        draft.write_text("A well-supported claim \\citep{a2024,\n    b2025}.\n")
        assert enrich_script.draft_citekeys(draft) == {"a2024", "b2025"}

    def test_a_citation_inside_a_code_fence_is_not_one(self, tmp_path):
        draft = tmp_path / "d.md"
        draft.write_text("Real [@a2024].\n\n```python\n@dataclass\nclass X: ...\n```\n")
        assert enrich_script.draft_citekeys(draft) == {"a2024"}


class TestLogging:
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
            enrich_script.STAGE_FUNCS,
            "embed",
            lambda d, a: {"status": "ok", "detail": "e"},
        )
        return enrich_script.main(**kwargs)

    def test_the_run_is_logged_when_the_entrypoint_asks_for_it(
        self, isolated_config, monkeypatch, _cleanup_root_handlers
    ):
        assert self._run_one_stage(monkeypatch, configure_logging=True) == 0

        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "chitragupta.enrich" in log_text
        assert "=== embed ===" in log_text
        assert "Corpus: 1 doc(s)" in log_text

    def test_a_dict_stage_detail_is_one_record_not_one_per_json_line(
        self, isolated_config, monkeypatch, _cleanup_root_handlers
    ):
        docs = [CorpusDoc(citekey="a", title="t", pdf_path=None)]
        monkeypatch.setattr(enrich_script.corpus, "build_corpus", lambda: docs)
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "embed"])
        monkeypatch.setitem(
            enrich_script.STAGE_FUNCS,
            "embed",
            lambda d, a: {"status": "ok", "detail": {"a": 3, "b": {"c": 1}}},
        )

        assert enrich_script.main(configure_logging=True) == 0

        for line in (config.LOGS_DIR / "pipeline.log").read_text().splitlines():
            assert re.match(r"^\d{4}-\d{2}-\d{2} ", line), (
                f"every record must start its own timestamped line: {line!r}"
            )
        assert '[ok] {"a": 3, "b": {"c": 1}}' in (config.LOGS_DIR / "pipeline.log").read_text()

    def test_calling_main_directly_leaves_no_handler_or_logs_directory(
        self, isolated_config, monkeypatch, _cleanup_root_handlers
    ):
        handlers_before = list(logging.getLogger().handlers)
        assert self._run_one_stage(monkeypatch) == 0

        assert logging.getLogger().handlers == handlers_before
        assert not config.LOGS_DIR.exists()


class TestPipelineLock:
    def test_a_concurrent_run_is_refused_with_its_own_exit_code(self, monkeypatch, capsys):
        from chitragupta import runlock

        def refuse():
            raise runlock.AlreadyRunning("another sync or pipeline run is already running")

        monkeypatch.setattr(runlock, "pipeline_lock", lambda *a, **k: refuse())
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling"])

        assert enrich_script.main() == runlock.EXIT_ALREADY_RUNNING
        assert "already running" in capsys.readouterr().out


class TestStageConverge:
    def test_it_passes_the_seed_list_through(self, isolated_config, monkeypatch):
        isolated_config.SEED_TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.SEED_TOPICS_PATH.write_text('topics = ["digital twin"]', encoding="utf-8")
        seen = {}
        monkeypatch.setattr(
            topic_converge,
            "run_stage",
            lambda docs, phrases: seen.update(phrases=phrases) or {"status": "ok"},
        )
        assert enrich_script.stage_converge([], make_args()) == {"status": "ok"}
        assert seen["phrases"] == ("digital twin",)


class TestStageTopicGraph:
    def test_it_passes_the_docs_through(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            topic_graph,
            "run_stage",
            lambda docs: seen.update(docs=docs) or {"status": "ok"},
        )
        assert enrich_script.stage_topic_graph(["doc"], make_args()) == {"status": "ok"}
        assert seen["docs"] == ["doc"]
