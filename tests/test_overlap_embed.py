import json
import random
import sqlite3
import sys
import types

import pytest

from chitragupta import (
    chroma_paging,
    config,
    install,
    ledger,
    overlap_chroma,
    overlap_embed,
    overlap_segments,
)
from tests.conftest import add_citable


SQLITE_VARIABLE_LIMIT = 32766


class FakeEmbedder:
    def __init__(self, scores=None):
        self.scores = scores or {}
        self.encoded = []

    def encode(self, texts):
        self.encoded.append(list(texts))
        return list(texts)

    def encode_lists(self, texts):
        return [[float(len(t))] for t in texts]

    def similarity(self, left, right):
        return [[self.scores.get((a, b), 0.0) for b in right] for a in left]


class FakeCollection:
    def __init__(self, count=1, get_response=None):
        self.get_response = get_response
        self.gets = []
        self._count = count

    def get(self, where, include=None, limit=None, offset=None):
        self.gets.append({"where": where, "include": include, "limit": limit, "offset": offset})
        metadatas = (self.get_response or {}).get("metadatas", [])
        metadatas = metadatas[offset or 0 :]
        if limit is not None:
            metadatas = metadatas[:limit]
        if len(metadatas) > SQLITE_VARIABLE_LIMIT:
            raise RuntimeError(
                "Error executing plan: Internal error: error returned from "
                "database: (code: 1) too many SQL variables"
            )
        return {"ids": [f"row{i}" for i in range(len(metadatas))], "metadatas": metadatas}

    def count(self):
        return self._count


class FakeClient:
    def __init__(self, collections):
        self.collections = collections

    def list_collections(self):
        return list(self.collections)

    def get_collection(self, name):
        return self.collections[name]


@pytest.fixture
def fake_chromadb(monkeypatch):
    def install(collections):
        client = FakeClient(collections)
        chromadb = types.SimpleNamespace(PersistentClient=lambda path: client)
        transformers = types.ModuleType("sentence_transformers")
        transformers.SentenceTransformer = object
        monkeypatch.setitem(sys.modules, "chromadb", chromadb)
        monkeypatch.setitem(sys.modules, "sentence_transformers", transformers)
        return client

    return install


def write_draft(cfg, text, *, dossier_rows=None):
    draft = cfg.DRAFTS_DIR / "topic" / "draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(text, encoding="utf-8")
    if dossier_rows is not None:
        sections = cfg.DOSSIERS_DIR / "topic" / "draft"
        sections.mkdir(parents=True, exist_ok=True)
        rows = "".join(f"| {title} | {keys} |\n" for title, keys in dossier_rows)
        (sections / "sections.md").write_text(
            "| section | citekeys |\n|---|---|\n" + rows, encoding="utf-8"
        )
    return draft


class TestOptionalStack:
    def test_it_reports_the_stack_when_both_import(self, fake_chromadb):
        fake_chromadb({})
        assert overlap_chroma.optional_stack() is not None

    def test_a_missing_package_is_not_installed_rather_than_an_exception(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "chromadb", None)
        assert overlap_chroma.optional_stack() is None


class TestBuiltCollection:
    def test_no_chroma_directory_is_no_collection(self, isolated_config):
        assert not config.CHROMA_DIR.exists()
        chromadb = types.SimpleNamespace(PersistentClient=lambda path: FakeClient({}))
        assert overlap_chroma.built_collection(chromadb) is None

    def test_a_directory_with_no_matching_collection_is_none(self, isolated_config, fake_chromadb):
        config.CHROMA_DIR.mkdir(parents=True)
        client = fake_chromadb({"corpus-someone-elses-model": FakeCollection()})
        chromadb = types.SimpleNamespace(PersistentClient=lambda path: client)
        assert overlap_chroma.built_collection(chromadb) is None

    def test_an_empty_collection_is_none_rather_than_a_tier_that_finds_nothing(
        self, isolated_config, fake_chromadb
    ):
        from chitragupta.enrich import embed_index

        config.CHROMA_DIR.mkdir(parents=True)
        client = fake_chromadb({embed_index.collection_name(): FakeCollection(count=0)})
        chromadb = types.SimpleNamespace(PersistentClient=lambda path: client)
        assert overlap_chroma.built_collection(chromadb) is None

    def test_a_built_collection_comes_back(self, isolated_config, fake_chromadb):
        from chitragupta.enrich import embed_index

        config.CHROMA_DIR.mkdir(parents=True)
        collection = FakeCollection(count=17)
        client = fake_chromadb({embed_index.collection_name(): collection})
        chromadb = types.SimpleNamespace(PersistentClient=lambda path: client)
        assert overlap_chroma.built_collection(chromadb) is collection

    def test_a_client_listing_bare_names_is_handled_too(self, isolated_config, fake_chromadb):
        from chitragupta.enrich import embed_index

        config.CHROMA_DIR.mkdir(parents=True)
        collection = FakeCollection(count=3)
        name = embed_index.collection_name()

        class NameListingClient(FakeClient):
            def list_collections(self):
                return [name]

        client = NameListingClient({name: collection})
        chromadb = types.SimpleNamespace(PersistentClient=lambda path: client)
        assert overlap_chroma.built_collection(chromadb) is collection


class TestCorpusKey:
    def test_it_matches_the_collection_name_with_no_chroma_installed(self, monkeypatch):
        from chitragupta.enrich import embed_index

        monkeypatch.setitem(sys.modules, "chromadb", None)
        assert overlap_chroma.corpus_key() == embed_index.collection_name()


class TestEmbedder:
    class FakeVectors(list):
        @property
        def T(self):
            return self

        def __matmul__(self, other):
            return TestEmbedder.FakeVectors([[a * b for b in other] for a in self])

        def tolist(self):
            return list(self)

    class FakeModel:
        def __init__(self):
            self.calls = []

        def encode(self, texts, show_progress_bar=False, normalize_embeddings=False):
            self.calls.append({"texts": list(texts), "normalized": normalize_embeddings})
            return TestEmbedder.FakeVectors(float(len(t)) for t in texts)

    def test_it_encodes_normalized_so_a_dot_product_is_the_cosine(self):
        model = self.FakeModel()
        overlap_chroma.Embedder(model).encode(["one", "two"])
        assert model.calls[0]["normalized"] is True

    def test_encode_lists_hands_chroma_plain_lists(self):
        embedder = overlap_chroma.Embedder(self.FakeModel())
        assert embedder.encode_lists(["abc"]) == [3.0]

    def test_similarity_multiplies_two_already_encoded_batches(self):
        embedder = overlap_chroma.Embedder(self.FakeModel())
        left = embedder.encode(["ab"])
        right = embedder.encode(["abc"])
        assert embedder.similarity(left, right) == [[6.0]]

    def test_the_model_is_loaded_once_and_only_on_first_use(self, monkeypatch):
        loads = []

        def fake_get_client_and_model():
            loads.append(True)
            return None, TestEmbedder.FakeModel()

        from chitragupta.enrich import embed_index

        monkeypatch.setattr(embed_index, "get_client_and_model", fake_get_client_and_model)
        embedder = overlap_chroma.Embedder()
        assert loads == []
        embedder.encode(["one"])
        embedder.encode(["two"])
        assert loads == [True]


class ChunkCollection:
    def __init__(self, chunks):
        self.chunks = chunks
        self.queries = []

    def query(self, query_embeddings, n_results, where, include=None):
        self.queries.append(
            {
                "n": len(query_embeddings),
                "n_results": n_results,
                "where": where,
                "include": include,
            }
        )
        wanted = where["citekey"]
        admitted = set(wanted["$in"]) if isinstance(wanted, dict) else {wanted}
        hits = sorted(
            (distance, citekey)
            for citekey, distances in self.chunks.items()
            if citekey in admitted
            for distance in distances
        )[:n_results]
        return {
            "metadatas": [[{"citekey": c} for _, c in hits] for _ in query_embeddings],
            "distances": [[d for d, _ in hits] for _ in query_embeddings],
        }


class TestShortlist:
    def test_a_single_citekey_is_returned_without_a_query(self):
        collection = ChunkCollection({})
        assert overlap_chroma.shortlist(collection, FakeEmbedder(), ["only_2024"], "prose", 5) == [
            "only_2024"
        ]
        assert collection.queries == []

    def test_citekeys_come_back_nearest_first(self):
        collection = ChunkCollection({"far_2024": [0.9], "near_2024": [0.1]})
        assert overlap_chroma.shortlist(
            collection, FakeEmbedder(), ["far_2024", "near_2024"], "prose", 5
        ) == ["near_2024", "far_2024"]

    def test_a_citekey_takes_its_best_distance_across_every_chunk(self):
        collection = ChunkCollection({"a_2024": [0.9, 0.05], "b_2024": [0.5]})
        assert overlap_chroma.shortlist(
            collection, FakeEmbedder(), ["b_2024", "a_2024"], "prose", 5
        ) == ["a_2024", "b_2024"]

    def test_a_citekey_the_collection_never_embedded_ranks_last_not_nowhere(self):
        collection = ChunkCollection({"indexed_2024": [0.2]})
        assert overlap_chroma.shortlist(
            collection, FakeEmbedder(), ["missing_2024", "indexed_2024"], "prose", 5
        ) == ["indexed_2024", "missing_2024"]

    def test_the_cap_is_applied(self):
        collection = ChunkCollection({f"k{i}_2024": [0.1 * (i + 1)] for i in range(4)})
        found = overlap_chroma.shortlist(
            collection, FakeEmbedder(), [f"k{i}_2024" for i in range(4)], "prose", 2
        )
        assert found == ["k0_2024", "k1_2024"]

    def test_a_dominant_source_does_not_crowd_the_others_out_of_the_ranking(self):
        collection = ChunkCollection(
            {
                "a_2024": [0.10, 0.11, 0.12, 0.13, 0.14],
                "b_2024": [0.2],
                "c_2024": [0.3],
                "d_2024": [0.4],
                "e_2024": [0.5],
                "f_2024": [0.6],
            }
        )
        cited = ["e_2024", "d_2024", "c_2024", "g_2024", "f_2024", "b_2024", "a_2024"]
        assert overlap_chroma.shortlist(collection, FakeEmbedder(), cited, "prose", 5) == [
            "a_2024",
            "b_2024",
            "c_2024",
            "d_2024",
            "e_2024",
        ]

    def test_every_embedded_source_is_ranked_ahead_of_every_unembedded_one(self):
        rng = random.Random(954)
        for _ in range(300):
            cited = [f"k{i}_2024" for i in range(rng.randint(2, 8))]
            rng.shuffle(cited)
            chunks = {
                key: [rng.random() for _ in range(rng.choice([0, 1, 2, 12]))] for key in cited
            }
            limit = rng.randint(1, len(cited))
            embedded = sorted((k for k in cited if chunks[k]), key=lambda k: min(chunks[k]))
            expected = (embedded + [k for k in cited if not chunks[k]])[:limit]
            found = overlap_chroma.shortlist(
                ChunkCollection(chunks), FakeEmbedder(), cited, "prose", limit
            )
            assert found == expected, (chunks, cited, limit)

    def test_the_section_is_encoded_once_however_many_sources_it_cites(self):
        collection = ChunkCollection({})
        embedder = FakeEmbedder()
        calls = []
        embedder.encode_lists = lambda texts: calls.append(texts) or [[1.0] for _ in texts]
        overlap_chroma.shortlist(collection, embedder, ["a_2024", "b_2024", "c_2024"], "prose", 5)
        assert len(calls) == 1
        assert [q["where"] for q in collection.queries] == [
            {"citekey": "a_2024"},
            {"citekey": "b_2024"},
            {"citekey": "c_2024"},
        ]
        assert {q["n_results"] for q in collection.queries} == {1}


class TestAbsentCitekeys:
    def test_every_cited_key_present_is_empty(self):
        collection = FakeCollection(
            get_response={"metadatas": [{"citekey": "a_2024"}, {"citekey": "b_2024"}]}
        )
        assert overlap_chroma.absent_citekeys(collection, ["a_2024", "b_2024"]) == set()

    def test_a_citekey_with_no_chunk_anywhere_is_reported(self):
        collection = FakeCollection(get_response={"metadatas": [{"citekey": "a_2024"}]})
        assert overlap_chroma.absent_citekeys(collection, ["a_2024", "b_2024"]) == {"b_2024"}

    def test_no_citekeys_is_no_query(self):
        collection = FakeCollection()
        assert overlap_chroma.absent_citekeys(collection, []) == set()
        assert collection.gets == []

    def test_it_queries_by_citekey_not_by_similarity(self):
        collection = FakeCollection(get_response={"metadatas": []})
        overlap_chroma.absent_citekeys(collection, ["a_2024", "b_2024"])
        assert collection.gets == [
            {
                "where": {"citekey": {"$in": ["a_2024", "b_2024"]}},
                "include": ["metadatas"],
                "limit": chroma_paging.PAGE_SIZE,
                "offset": 0,
            }
        ]

    def test_cited_sources_owning_more_chunks_than_sqlite_allows_are_still_read(self):
        present = [{"citekey": "a_2024"} for _ in range(SQLITE_VARIABLE_LIMIT + 1)]
        collection = FakeCollection(get_response={"metadatas": present})

        assert overlap_chroma.absent_citekeys(collection, ["a_2024", "b_2024"]) == {"b_2024"}


class TestOpenScope:
    def test_a_draft_outside_content_drafts_has_no_dossier(self, isolated_config, tmp_path):
        stray = tmp_path / "elsewhere.md"
        stray.write_text("# T\n\nprose\n", encoding="utf-8")
        scope, reason = overlap_embed.open_scope(stray)
        assert scope is None
        assert "no dossier" in reason

    def test_a_dossier_recording_no_citekeys_is_unavailable(self, isolated_config):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[])
        scope, reason = overlap_embed.open_scope(draft)
        assert scope is None
        assert "records no citekeys" in reason
        assert "whole corpus" in reason

    def test_a_missing_enrichment_layer_says_how_to_install_it(self, isolated_config, monkeypatch):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: None)
        scope, reason = overlap_embed.open_scope(draft)
        assert scope is None
        assert install.enrich_remedy() in reason

    def test_an_unbuilt_collection_says_how_to_build_it(self, isolated_config, monkeypatch):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: ("chromadb", None))
        monkeypatch.setattr(overlap_chroma, "built_collection", lambda module: None)
        scope, reason = overlap_embed.open_scope(draft)
        assert scope is None
        assert "python -m chitragupta.enrich" in reason

    def test_everything_present_opens_a_scope(self, isolated_config, ledger_con, monkeypatch):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        collection = FakeCollection()
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: ("chromadb", None))
        monkeypatch.setattr(overlap_chroma, "built_collection", lambda module: collection)
        scope, reason = overlap_embed.open_scope(draft)
        assert reason is None
        assert scope.citekeys_by_section == {"T": ["smith_2024"]}
        assert scope.collection is collection
        scope.close()

    def test_an_absent_ledger_is_a_reason_not_a_ledger_this_tier_creates(
        self, isolated_config, monkeypatch
    ):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: ("chromadb", None))
        monkeypatch.setattr(overlap_chroma, "built_collection", lambda module: FakeCollection())
        assert not config.LEDGER_PATH.exists()

        scope, reason = overlap_embed.open_scope(draft)

        assert scope is None
        assert "corpus sync" in reason
        assert not config.LEDGER_PATH.exists()

    def test_the_connection_this_tier_opens_cannot_write(
        self, isolated_config, ledger_con, monkeypatch
    ):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: ("chromadb", None))
        monkeypatch.setattr(overlap_chroma, "built_collection", lambda module: FakeCollection())
        scope, _reason = overlap_embed.open_scope(draft)
        try:
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                scope.connection.execute("DELETE FROM items")
        finally:
            scope.close()

    def test_unavailable_reason_does_not_leak_the_scope_it_opened(
        self, isolated_config, ledger_con, monkeypatch
    ):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: ("chromadb", None))
        monkeypatch.setattr(overlap_chroma, "built_collection", lambda module: FakeCollection())
        opened = []
        real = ledger.read_connection

        def tracked():
            con = real()
            opened.append(con)
            return con

        monkeypatch.setattr(ledger, "read_connection", tracked)
        assert overlap_embed.unavailable_reason(draft) is None
        assert len(opened) == 1
        with pytest.raises(sqlite3.ProgrammingError):
            opened[0].execute("SELECT 1")

    def test_unavailable_reason_is_the_same_answer_without_the_scope(
        self, isolated_config, tmp_path
    ):
        stray = tmp_path / "elsewhere.md"
        stray.write_text("# T\n\nprose\n", encoding="utf-8")
        assert overlap_embed.unavailable_reason(stray) == (overlap_embed.open_scope(stray)[1])

    def test_the_dossier_check_comes_before_anything_imports_torch(
        self, isolated_config, tmp_path, monkeypatch
    ):
        called = []
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: called.append(True))
        stray = tmp_path / "elsewhere.md"
        stray.write_text("# T\n\nprose\n", encoding="utf-8")
        overlap_embed.open_scope(stray)
        assert called == []


class TestAlignDraft:
    @pytest.fixture
    def source(self, ledger_con):
        def write(citekey, records):
            add_citable(ledger_con, citekey)
            path = config.DOCLING_DIR / f"{citekey}.passages.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(records), encoding="utf-8")

        return write

    def section(self, title="T", citekeys=("smith_2024",), texts=("a claim",)):
        return overlap_segments.DraftSection(
            title,
            list(citekeys),
            [
                overlap_segments.DraftSentence(text, i * 5, i * 5 + 5)
                for i, text in enumerate(texts)
            ],
        )

    def test_an_aligned_pair_carries_the_sources_page_and_the_drafts_words(
        self, isolated_config, ledger_con, source
    ):
        source("smith_2024", [{"text": "the source claim.", "label": "text", "page": 7}])
        embedder = FakeEmbedder({("a claim", "the source claim."): 0.9})
        scope = overlap_embed.Scope({}, FakeCollection(), ledger_con, embedder)
        [found] = overlap_embed.align_draft(scope, [self.section()])
        assert found.citekey == "smith_2024"
        assert (found.page, found.end_page) == (7, 7)
        assert (found.word_start, found.word_end) == (0, 5)
        assert found.source_text == "the source claim."

    def test_an_unrelated_pair_produces_nothing(self, isolated_config, ledger_con, source):
        source("smith_2024", [{"text": "something else.", "label": "text", "page": 1}])
        scope = overlap_embed.Scope({}, FakeCollection(), ledger_con, FakeEmbedder())
        assert overlap_embed.align_draft(scope, [self.section()]) == []

    def test_a_near_verbatim_pair_is_aligned_here_and_deduplicated_upstream(
        self, isolated_config, ledger_con, source
    ):
        source("smith_2024", [{"text": "a claim", "label": "text", "page": 1}])
        embedder = FakeEmbedder({("a claim", "a claim"): 0.99})
        scope = overlap_embed.Scope({}, FakeCollection(), ledger_con, embedder)
        assert len(overlap_embed.align_draft(scope, [self.section()])) == 1

    def test_a_source_with_no_usable_passages_is_skipped(self, isolated_config, ledger_con):
        scope = overlap_embed.Scope({}, FakeCollection(), ledger_con, FakeEmbedder())
        assert overlap_embed.align_draft(scope, [self.section()]) == []

    def test_each_source_is_encoded_once_for_the_whole_draft(
        self, isolated_config, ledger_con, source
    ):
        source("smith_2024", [{"text": "the source claim.", "label": "text", "page": 1}])
        embedder = FakeEmbedder()
        scope = overlap_embed.Scope({}, FakeCollection(), ledger_con, embedder)
        overlap_embed.align_draft(
            scope,
            [
                self.section(title="one"),
                self.section(title="two"),
            ],
        )
        source_batches = [batch for batch in embedder.encoded if batch == ["the source claim."]]
        assert len(source_batches) == 1


class TestReport:
    def alignment(self, section="A", citekey="k_2024", score=1.0, start=0, end=10):
        return overlap_embed.SectionAlignment(
            section=section,
            citekey=citekey,
            page=1,
            end_page=1,
            score=score,
            word_start=start,
            word_end=end,
            matched_words=end - start,
            source_text="src",
        )

    def test_the_same_span_matching_several_sources_reports_once(self):
        found = overlap_embed.report(
            [
                self.alignment(citekey="a_2024", score=0.9),
                self.alignment(citekey="b_2024", score=0.8),
                self.alignment(citekey="c_2024", score=0.7),
            ]
        )
        assert [a.citekey for a in found] == ["a_2024"]

    def test_it_keeps_at_most_one_alignment_per_section(self):
        found = overlap_embed.report(
            [
                self.alignment(section="A", score=0.9, start=0, end=10),
                self.alignment(section="A", score=0.8, start=20, end=30),
                self.alignment(section="B", score=0.1, start=40, end=50),
            ]
        )
        assert [(a.section, a.score) for a in found] == [("A", 0.9), ("B", 0.1)]

    def test_a_weak_alignment_in_its_own_section_still_reports(self):
        found = overlap_embed.report(
            [
                self.alignment(section=f"S{i}", score=1.0 - i / 100, start=i * 20, end=i * 20 + 10)
                for i in range(30)
            ]
        )
        assert len(found) == 30

    def test_a_later_span_overlapping_a_kept_one_is_dropped_across_sections(self):
        found = overlap_embed.report(
            [
                self.alignment(section="A", score=0.9, start=0, end=10),
                self.alignment(section="B", score=0.5, start=5, end=15),
                self.alignment(section="B", score=0.4, start=30, end=40),
            ]
        )
        assert [(a.section, a.word_start) for a in found] == [("A", 0), ("B", 30)]

    def test_nothing_in_gives_nothing_out(self):
        assert overlap_embed.report([]) == []
