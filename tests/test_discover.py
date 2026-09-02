"""chitragupta/discover/: the reader over the topic artefacts.

The property under test throughout: **the reader computes no topic and
no edge** -- it resolves a phrase to topics that already exist, displays
relations a stage already derived, and says which rung of the ladder
answered (`resolved_via`), degrading honestly when the enrich extra is
absent rather than pretending semantic resolution ran.
"""

import json

import pytest

from chitragupta import config
from chitragupta import discover
from chitragupta.discover import _data, _resolve


def write_artefacts(cfg, graph=None, topic_set=None, topics=None):
    cfg.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    if graph is not None:
        cfg.TOPIC_GRAPH_PATH.write_text(json.dumps(graph), encoding="utf-8")
    if topic_set is not None:
        cfg.TOPIC_SET_PATH.write_text(json.dumps(topic_set), encoding="utf-8")
    if topics is not None:
        cfg.TOPICS_PATH.write_text(json.dumps(topics), encoding="utf-8")


def make_ledger(cfg, citekeys):
    from chitragupta import ledger

    con = ledger.connect()
    for i, citekey in enumerate(citekeys):
        path = cfg.CONTENT_DIR / "parsed" / f"{citekey}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"The opening sentence of {citekey} runs long enough to quote. "
            f"A second, longer sentence about the topic of {citekey} and its methods.",
            encoding="utf-8",
        )
        con.execute(
            "INSERT INTO items (citekey, item_type, title, year, status, parsed_path,"
            " last_synced, bib_fields) VALUES (?, 'article', ?, ?, 'parsed', ?, 't', ?)",
            (
                citekey,
                f"Title of {citekey}",
                str(2020 + i),
                str(path),
                json.dumps({"author": "Doe, Jane", "journal": "Journal of Tests"}),
            ),
        )
    con.commit()
    con.close()


GRAPH = {
    "model": "the-model",
    "n_docs": 4,
    "n_topics": 2,
    "corpus_mean": [0.5, 0.5],
    "topics": [
        {"label": "digital twin", "provenance": "seed", "size": 2, "centroid": [0.5, -0.5]},
        {"label": "machine learning", "provenance": "emergent", "size": 3, "centroid": [-0.5, 0.5]},
    ],
    "edges_overlap": [
        {
            "a": "digital twin",
            "b": "machine learning",
            "jaccard": 0.25,
            "overlap_coeff": 0.5,
            "p_value": 0.004,
            "shared": ["p2"],
        }
    ],
    "edges_semantic": [
        {"a": "digital twin", "b": "machine learning", "similarity": 0.61, "bridge": ["p2", "p3"]}
    ],
    "hierarchy": [],
}

TOPIC_SET = {
    "model": "the-model",
    "n_docs": 4,
    "topics": [
        {
            "label": "digital twin",
            "provenance": "seed",
            "topic_id": 0,
            "members": [{"citekey": "p1", "score": 0.9}, {"citekey": "p2", "score": 0.8}],
        },
        {
            "label": "machine learning",
            "provenance": "emergent",
            "topic_id": 1,
            "members": [
                {"citekey": "p2", "score": 0.7},
                {"citekey": "p3", "score": 0.6},
                {"citekey": "p4", "score": 0.5},
            ],
        },
    ],
    "uncovered": [],
}

TOPICS_JSON = {
    "topic_info": [
        {"Topic": 0, "Representation": ["twin", "simulation"]},
        {"Topic": 1, "Representation": ["learning", "models"]},
    ]
}


def prepare(cfg):
    write_artefacts(cfg, graph=GRAPH, topic_set=TOPIC_SET, topics=TOPICS_JSON)
    make_ledger(cfg, ["p1", "p2", "p3", "p4"])


class FakeModel:
    """Encodes any text to the vector VECTORS names for it, so a test
    can steer the semantic rung without sentence-transformers."""

    VECTORS: dict = {}

    def encode(self, texts, show_progress_bar=False):
        if isinstance(texts, str):
            return self.VECTORS[texts]
        return [self.VECTORS[t] for t in texts]


class TestResolveLadder:
    LABELS = ("digital twin", "machine learning")

    def test_exact_is_case_insensitive(self):
        assert _resolve.exact_match("Digital TWIN", self.LABELS) == "digital twin"

    def test_fuzzy_catches_a_typo(self):
        assert _resolve.fuzzy_match("digital twni", self.LABELS) == "digital twin"

    def test_fuzzy_refuses_a_distant_phrase(self):
        assert _resolve.fuzzy_match("quantum sensing", self.LABELS) is None

    def test_bm25_ranks_by_topic_vocabulary(self):
        vocab = {
            "digital twin": "digital twin twin simulation",
            "machine learning": "machine learning learning models",
        }
        ranked = _resolve.bm25_ranking("simulation of twins", vocab)
        assert ranked and ranked[0][0] == "digital twin"

    def test_rrf_rewards_agreement_between_rankings(self):
        fused = _resolve.rrf_fuse([["a", "b", "c"], ["b", "a", "c"]])
        labels = [label for label, _ in fused]
        assert set(labels[:2]) == {"a", "b"}
        assert labels[2] == "c"

    def test_resolution_records_the_rung_that_fired(self, isolated_config, monkeypatch):
        prepare(isolated_config)
        resolution = _resolve.resolve("digital twin", GRAPH, TOPIC_SET, {})
        assert resolution.via == "exact"
        assert resolution.label == "digital twin"

    def test_a_typo_resolves_through_the_fuzzy_rung(self, isolated_config):
        resolution = _resolve.resolve("digital twni", GRAPH, TOPIC_SET, {})
        assert resolution.via == "fuzzy"
        assert resolution.label == "digital twin"

    def test_a_topic_without_a_centroid_never_ranks_semantically(
        self, isolated_config, monkeypatch
    ):
        """A topic whose members all failed to parse has no centroid; it
        can still win the lexical rungs, but geometry has nothing to say
        about it."""
        FakeModel.VECTORS = {"anything": [1.0, 0.0]}
        monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())
        graph = dict(GRAPH)
        graph["topics"] = [
            {"label": "digital twin", "provenance": "seed", "size": 2, "centroid": [0.5, -0.5]},
            {"label": "unparsed", "provenance": "seed", "size": 1, "centroid": []},
        ]
        ranked = _resolve.semantic_ranking("anything", graph)
        assert [label for label, _ in ranked] == ["digital twin"]

    def test_hybrid_fires_when_lexical_rungs_miss(self, isolated_config, monkeypatch):
        """'cyber replica' shares no token with any label, so only the
        semantic ranking places it -- next to the digital-twin centroid."""
        FakeModel.VECTORS = {"cyber replica": [1.0, 0.0]}
        monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())
        resolution = _resolve.resolve("cyber replica", GRAPH, TOPIC_SET, {}, min_similarity=0.2)
        assert resolution.via == "hybrid"
        assert resolution.label == "digital twin"

    def test_below_the_floor_falls_through_to_search(self, isolated_config, monkeypatch):
        FakeModel.VECTORS = {"unrelated phrase": [0.5, 0.5]}
        monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())
        resolution = _resolve.resolve("unrelated phrase", GRAPH, TOPIC_SET, {}, min_similarity=0.9)
        assert resolution.label is None
        assert resolution.via == "search"

    def test_without_the_enrich_extra_it_degrades_and_says_so(self, isolated_config, monkeypatch):
        def refuse():
            raise ImportError("no sentence_transformers")

        monkeypatch.setattr(_resolve, "_load_model", refuse)
        resolution = _resolve.resolve(
            "simulation twin", GRAPH, TOPIC_SET, {"digital twin": ["twin", "simulation"]}
        )
        assert resolution.via == "hybrid"
        assert resolution.label == "digital twin"
        assert "semantic" in (resolution.note or "")


class TestModelLoading:
    def test_both_lazy_loaders_construct_the_configured_model(self, monkeypatch):
        """Patched at sys.modules so the `from sentence_transformers
        import ...` lines under test are the shipped ones."""
        import sys
        import types

        from chitragupta.discover import _overview

        seen = []
        fake_st = types.ModuleType("sentence_transformers")
        fake_st.SentenceTransformer = lambda name: seen.append(name) or "model"
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
        assert _resolve._load_model() == "model"
        assert _overview._load_model() == "model"
        assert seen == [config.EMBEDDING_MODEL] * 2


class TestDataLoading:
    def test_a_missing_graph_names_the_stage_to_run(self, isolated_config):
        with pytest.raises(_data.MissingArtefact, match="topic-graph"):
            _data.load_graph()

    def test_a_missing_topic_set_names_converge(self, isolated_config):
        write_artefacts(isolated_config, graph=GRAPH)
        with pytest.raises(_data.MissingArtefact, match="converge"):
            _data.load_topic_set()

    def test_top_terms_key_on_labels_not_ids(self, isolated_config):
        write_artefacts(isolated_config, topics=TOPICS_JSON)
        terms = _data.top_terms(TOPIC_SET)
        assert terms["digital twin"] == ["twin", "simulation"]

    def test_missing_topics_json_means_no_terms_not_an_error(self, isolated_config):
        assert _data.top_terms(TOPIC_SET) == {}

    def test_no_citekeys_means_no_ledger_visit(self, isolated_config):
        assert _data.entries_for([]) == {}

    def test_a_missing_ledger_names_sync(self, isolated_config):
        with pytest.raises(_data.MissingArtefact, match="corpus sync"):
            _data.entries_for(["p1"])

    def test_a_stale_artefact_citekey_refuses_instead_of_crashing(self, isolated_config):
        """A sync that removed a paper leaves the topic artefacts naming
        a citekey the ledger no longer holds; the reader must refuse with
        the re-run instruction, not hand the user a KeyError traceback."""
        make_ledger(isolated_config, ["p1"])
        with pytest.raises(_data.MissingArtefact, match="no longer"):
            _data.entries_for(["p1", "vanished2020"])

    def test_the_missing_ledger_refusal_reaches_the_cli(self, isolated_config, capsys):
        write_artefacts(isolated_config, graph=GRAPH, topic_set=TOPIC_SET)
        assert discover.main(["digital twin"]) == 1
        assert "corpus sync" in capsys.readouterr().out

    def test_topics_of_inverts_the_membership(self, isolated_config):
        assert [t["label"] for t in _data.topics_of(TOPIC_SET)["p2"]] == [
            "digital twin",
            "machine learning",
        ]


class TestListView:
    def test_lists_every_topic_with_provenance_and_size(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main([]) == 0
        out = capsys.readouterr().out
        assert "digital twin" in out and "seed" in out
        assert "machine learning" in out and "emergent" in out

    def test_json_lists_the_same_topics(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert [t["label"] for t in data["topics"]] == ["digital twin", "machine learning"]

    def test_a_missing_artefact_exits_one_and_names_the_fix(self, isolated_config, capsys):
        assert discover.main([]) == 1
        assert "topic-graph" in capsys.readouterr().out


class TestTopicView:
    def test_members_carry_ledger_detail_and_their_other_topics(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["digital twin"]) == 0
        out = capsys.readouterr().out
        assert "Title of p1" in out
        # p2 belongs to both topics; the digital-twin view must say so.
        assert "machine learning" in out

    def test_linked_topics_show_both_edge_families_with_evidence(self, isolated_config, capsys):
        prepare(isolated_config)
        discover.main(["digital twin"])
        out = capsys.readouterr().out
        assert "via: p2" in out
        assert "bridge: p2 <-> p3" in out

    def test_json_records_the_resolution_rung(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["digital", "twin", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["resolved_via"] == "exact"
        assert data["topic"]["label"] == "digital twin"
        assert [m["citekey"] for m in data["members"]] == ["p1", "p2"]

    def test_search_fallback_is_labelled_and_annotated(self, isolated_config, capsys, monkeypatch):
        from chitragupta import retrieval

        prepare(isolated_config)

        def refuse():
            raise ImportError("no sentence_transformers")

        monkeypatch.setattr(_resolve, "_load_model", refuse)
        monkeypatch.setattr(
            retrieval,
            "search",
            lambda query, k=5: [
                retrieval.SearchResult(citekey="p3", title="Title of p3", score=1.2, snippet="...")
            ],
        )
        assert discover.main(["entirely unrelated question", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["resolved_via"] == "search"
        assert data["results"][0]["citekey"] == "p3"
        assert [t["label"] for t in data["results"][0]["topics"]] == ["machine learning"]

    def test_a_phrase_nothing_answers_exits_one_with_near_misses(
        self, isolated_config, capsys, monkeypatch
    ):
        from chitragupta import retrieval

        prepare(isolated_config)

        def refuse():
            raise ImportError("no")

        monkeypatch.setattr(_resolve, "_load_model", refuse)
        monkeypatch.setattr(retrieval, "search", lambda query, k=5: [])
        assert discover.main(["zzz qqq"]) == 1
        assert "digital twin" in capsys.readouterr().out


class TestRenderEdgeCases:
    def test_the_list_view_names_uncovered_papers(self, isolated_config, capsys):
        topic_set = dict(TOPIC_SET)
        topic_set["uncovered"] = ["orphan2019"]
        write_artefacts(isolated_config, graph=GRAPH, topic_set=topic_set, topics=TOPICS_JSON)
        make_ledger(isolated_config, ["p1", "p2", "p3", "p4"])
        discover.main([])
        assert "orphan2019" in capsys.readouterr().out

    def test_a_topic_with_no_edges_says_so(self, isolated_config, capsys):
        graph = dict(GRAPH)
        graph["edges_overlap"] = []
        graph["edges_semantic"] = []
        write_artefacts(isolated_config, graph=graph, topic_set=TOPIC_SET, topics=TOPICS_JSON)
        make_ledger(isolated_config, ["p1", "p2", "p3", "p4"])
        discover.main(["digital twin"])
        assert "none above the graph's floors" in capsys.readouterr().out

    def test_a_topic_with_no_terms_renders_without_a_terms_line(self, isolated_config, capsys):
        write_artefacts(isolated_config, graph=GRAPH, topic_set=TOPIC_SET)
        make_ledger(isolated_config, ["p1", "p2", "p3", "p4"])
        discover.main(["digital twin"])
        assert "terms:" not in capsys.readouterr().out

    def test_a_search_hit_outside_every_topic_gets_no_topics_line(
        self, isolated_config, capsys, monkeypatch
    ):
        from chitragupta import retrieval

        prepare(isolated_config)

        def refuse():
            raise ImportError("no")

        monkeypatch.setattr(_resolve, "_load_model", refuse)
        monkeypatch.setattr(
            retrieval,
            "search",
            lambda query, k=5: [
                retrieval.SearchResult(citekey="stray2018", title="Stray", score=0.5, snippet="...")
            ],
        )
        assert discover.main(["entirely unrelated question"]) == 0
        assert "topics:" not in capsys.readouterr().out.split("stray2018")[-1]

    def test_search_without_a_note_carries_none(self, isolated_config, capsys, monkeypatch):
        """The semantic rung ran and answered 'too far' -- no degradation
        happened, so the fallback output carries no note."""
        from chitragupta import retrieval

        prepare(isolated_config)
        FakeModel.VECTORS = {"far away phrase": [0.5, 0.5]}
        monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())
        monkeypatch.setattr(
            retrieval,
            "search",
            lambda query, k=5: [
                retrieval.SearchResult(citekey="p4", title="Title of p4", score=0.9, snippet="...")
            ],
        )
        assert discover.main(["far away phrase", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["resolved_via"] == "search"
        assert "note" not in data


class TestPaperView:
    def test_shows_the_papers_topics(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--paper", "p2"]) == 0
        out = capsys.readouterr().out
        assert "digital twin" in out and "machine learning" in out

    def test_an_unknown_citekey_exits_one(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--paper", "nope2020"]) == 1
        assert "nope2020" in capsys.readouterr().out

    def test_json_shape(self, isolated_config, capsys):
        prepare(isolated_config)
        discover.main(["--paper", "p1", "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["citekey"] == "p1"
        assert [t["label"] for t in data["topics"]] == ["digital twin"]


class TestOverviewFile:
    def test_out_writes_markdown_with_verbatim_snippets(
        self, isolated_config, tmp_path, monkeypatch
    ):
        from chitragupta.discover import _overview

        prepare(isolated_config)
        FakeModel.VECTORS = {}

        def fake_model():
            raise ImportError("snippets should degrade, not fail")

        monkeypatch.setattr(_overview, "_load_model", fake_model)
        out = tmp_path / "overview.md"
        assert discover.main(["digital twin", "--out", str(out)]) == 0
        text = out.read_text(encoding="utf-8")
        assert "# digital twin" in text
        assert "Title of p1" in text
        assert "machine learning" in text  # linked topic
        assert "snippet" in text.lower()  # the degradation note names what is absent

    def test_snippets_quote_member_sentences_verbatim(self, isolated_config, tmp_path, monkeypatch):
        from chitragupta.discover import _overview

        prepare(isolated_config)

        class SnippetModel:
            def encode(self, texts, show_progress_bar=False):
                # Sentences naming p1 rank highest against the centroid.
                return [
                    [1.0, 0.0] if "p1" in t else [0.0, 1.0]
                    for t in (texts if isinstance(texts, list) else [texts])
                ]

        monkeypatch.setattr(_overview, "_load_model", lambda: SnippetModel())
        out = tmp_path / "overview.md"
        assert discover.main(["digital twin", "--out", str(out)]) == 0
        text = out.read_text(encoding="utf-8")
        assert "The opening sentence of p1 runs long enough to quote." in text
        assert "`p1`" in text

    def test_a_topic_with_no_parsed_text_says_so(self, isolated_config, tmp_path, monkeypatch):
        """Members whose parse never happened leave nothing quotable; the
        overview names that instead of quietly omitting the section."""

        prepare(isolated_config)
        for member in ("p1", "p2"):
            (isolated_config.CONTENT_DIR / "parsed" / f"{member}.txt").unlink()
        out = tmp_path / "overview.md"
        assert discover.main(["digital twin", "--out", str(out)]) == 0
        assert "No member paper has parsed text" in out.read_text(encoding="utf-8")

    def test_a_topic_without_a_centroid_gets_no_snippets(self, isolated_config, monkeypatch):
        from chitragupta.discover import _overview

        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["topics"][0]["centroid"] = []
        assert _overview.snippets(TOPIC_SET["topics"][0]["members"], graph, "digital twin") == []

    def test_markdown_without_terms_or_edges_still_renders(self, isolated_config):
        from chitragupta.discover import _overview

        data = {
            "topic": {"label": "bare", "provenance": "seed", "size": 1, "terms": []},
            "members": [{"citekey": "p1", "score": 1.0, "entry": "entry", "topics": []}],
            "linked": {"overlap": [], "semantic": []},
        }
        text = _overview.build_markdown(data, quoted=[])
        assert "# bare" in text
        assert "none above the graph's floors" in text

    def test_an_unwritable_out_path_exits_one_naming_it(
        self, isolated_config, tmp_path, capsys, monkeypatch
    ):
        from chitragupta.discover import _overview

        prepare(isolated_config)

        def refuse():
            raise ImportError("no")

        monkeypatch.setattr(_overview, "_load_model", refuse)
        target = tmp_path / "no-such-dir" / "overview.md"
        assert discover.main(["digital twin", "--out", str(target)]) == 1
        streams = capsys.readouterr()
        # The stream is pinned, not just the text: the failure line is
        # diagnostics on stderr, and stdout stays whatever the view emitted.
        assert str(target) in streams.err
        assert str(target) not in streams.out

    def test_an_unwritable_out_path_leaves_json_stdout_parseable(
        self, isolated_config, tmp_path, capsys, monkeypatch
    ):
        """`--json --out` has already written the payload to stdout by the
        time the write fails, so a failure line on that stream would leave
        the caller parsing JSON followed by prose."""
        from chitragupta.discover import _overview

        prepare(isolated_config)

        def refuse():
            raise ImportError("no")

        monkeypatch.setattr(_overview, "_load_model", refuse)
        target = tmp_path / "no-such-dir" / "overview.md"
        assert discover.main(["digital twin", "--json", "--out", str(target)]) == 1
        streams = capsys.readouterr()
        assert json.loads(streams.out)["topic"]["label"] == "digital twin"
        assert str(target) in streams.err

    def test_a_graph_stale_against_the_topic_set_refuses(self, isolated_config, capsys):
        """One stage re-run without the other leaves a label only
        topic_set.json knows; that is a refusal naming topic-graph, not
        a StopIteration traceback."""
        graph = json.loads(json.dumps(GRAPH))
        graph["topics"] = [t for t in graph["topics"] if t["label"] != "digital twin"]
        write_artefacts(isolated_config, graph=graph, topic_set=TOPIC_SET, topics=TOPICS_JSON)
        make_ledger(isolated_config, ["p1", "p2", "p3", "p4"])
        assert discover.main(["digital twin"]) == 1
        assert "topic-graph" in capsys.readouterr().out

    def test_snippets_with_no_members_touch_no_sql(self, isolated_config):
        from chitragupta.discover import _overview

        assert _overview._parsed_texts([]) == {}

    def test_nothing_is_written_without_the_flag(self, isolated_config, tmp_path, capsys):
        prepare(isolated_config)
        discover.main(["digital twin"])
        # tmp_path holds the fixture's content/ tree; what must be absent
        # is any overview file, which only --out may create.
        assert not list(tmp_path.glob("*.md"))
        assert not list((tmp_path / "content").glob("*.md"))


class TestCorpusWiring:
    def test_the_corpus_layer_dispatches_discover(self, isolated_config, capsys):
        from chitragupta import corpus

        prepare(isolated_config)
        assert corpus.main(["discover"]) == 0
        assert "digital twin" in capsys.readouterr().out
