"""chitragupta/overlap_embed.py and chitragupta/overlap_chroma.py: tier 3's policy, and
the one seam that reaches the optional embedding stack.

chromadb/sentence_transformers are mocked via sys.modules, the same way
tests/test_enrich_embed_index.py does it and for the same reason: both
are imported lazily inside functions, so patching sys.modules before the
call shadows the real packages without needing them uninstalled. The
alignment itself is exercised with a fake embedder that returns a
hand-written matrix -- no model, no vectors, no numpy."""

import json
import sys
import types

import pytest

from chitragupta import config, ledger, overlap_chroma, overlap_embed, overlap_segments
from tests.conftest import make_reference


class FakeEmbedder:
    """Encodes to the texts themselves and compares by table lookup.

    `similarity` is handed whatever `encode` returned, which is the real
    class's contract too -- so a test can say "this draft segment against
    that source segment scores 0.8" without a vector anywhere."""

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
    def __init__(self, response=None, count=1, get_response=None):
        self.response = response
        self.get_response = get_response
        self.queries = []
        self.gets = []
        self._count = count

    def query(self, query_embeddings, n_results, where):
        self.queries.append({"n": len(query_embeddings), "n_results": n_results, "where": where})
        return self.response

    def get(self, where, include=None):
        self.gets.append({"where": where, "include": include})
        return self.get_response

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
    """Install a chromadb/sentence_transformers pair in sys.modules, and
    hand back the client the module under test will build."""

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
    """A draft under content/drafts/ with a dossier beside it, which is
    what tier 3 needs before it will run at all."""
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
        # `embed_index.get_client_and_model()` imports these bare and
        # raises ModuleNotFoundError uncaught, which would take the whole
        # scan down; this is the probe that exists so it does not.
        monkeypatch.setitem(sys.modules, "chromadb", None)
        assert overlap_chroma.optional_stack() is None


class TestBuiltCollection:
    def test_no_chroma_directory_is_no_collection(self, isolated_config):
        assert not config.CHROMA_DIR.exists()
        chromadb = types.SimpleNamespace(PersistentClient=lambda path: FakeClient({}))
        assert overlap_chroma.built_collection(chromadb) is None

    def test_a_directory_with_no_matching_collection_is_none(self, isolated_config, fake_chromadb):
        # The corpus was embedded under a different `embedding_model`:
        # the collection is namespaced per model, so this one is simply
        # not there and the tier has nothing to read.
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
        # chromadb 0.5 lists collection objects and 1.0 lists names.
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


class TestEmbedder:
    """The lazy model handle. Every method here is one line over the
    model, so what is worth pinning is the laziness and the shapes."""

    class FakeVectors(list):
        """Stands in for the numpy array `model.encode` returns: `@`,
        `.T` and `.tolist()` are the whole of what this module asks of
        it, which is why it never imports numpy."""

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
        # A scan whose draft has no dossier -- the ordinary case on a
        # host that never ran the drafting pipeline -- must not pay a
        # multi-hundred-megabyte load to find out it has nothing to do.
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


class TestShortlist:
    def test_a_single_citekey_is_returned_without_a_query(self):
        collection = FakeCollection()
        assert overlap_chroma.shortlist(collection, FakeEmbedder(), ["only_2024"], "prose", 5) == [
            "only_2024"
        ]
        assert collection.queries == []

    def test_citekeys_come_back_nearest_first(self):
        collection = FakeCollection(
            {
                "metadatas": [[{"citekey": "far_2024"}, {"citekey": "near_2024"}]],
                "distances": [[0.9, 0.1]],
            }
        )
        assert overlap_chroma.shortlist(
            collection, FakeEmbedder(), ["far_2024", "near_2024"], "prose", 5
        ) == ["near_2024", "far_2024"]

    def test_a_citekey_takes_its_best_distance_across_every_chunk(self):
        collection = FakeCollection(
            {
                "metadatas": [
                    [{"citekey": "a_2024"}],
                    [{"citekey": "a_2024"}, {"citekey": "b_2024"}],
                ],
                "distances": [[0.9], [0.05, 0.5]],
            }
        )
        assert overlap_chroma.shortlist(
            collection, FakeEmbedder(), ["a_2024", "b_2024"], "prose", 5
        ) == ["a_2024", "b_2024"]

    def test_a_citekey_the_collection_never_embedded_ranks_last_not_nowhere(self):
        # A source whose PDF never parsed has no chunk; dropping it would
        # shrink the shortlist below its cap for no stated reason.
        collection = FakeCollection(
            {
                "metadatas": [[{"citekey": "indexed_2024"}]],
                "distances": [[0.2]],
            }
        )
        assert overlap_chroma.shortlist(
            collection, FakeEmbedder(), ["indexed_2024", "missing_2024"], "prose", 5
        ) == ["indexed_2024", "missing_2024"]

    def test_a_hit_with_no_citekey_in_its_metadata_is_skipped(self):
        collection = FakeCollection(
            {
                "metadatas": [[{"title": "no citekey here"}, {"citekey": "real_2024"}]],
                "distances": [[0.1, 0.4]],
            }
        )
        assert overlap_chroma.shortlist(
            collection, FakeEmbedder(), ["real_2024", "other_2024"], "prose", 5
        ) == ["real_2024", "other_2024"]

    def test_the_cap_is_applied(self):
        collection = FakeCollection(
            {
                "metadatas": [[{"citekey": f"k{i}_2024"} for i in range(4)]],
                "distances": [[0.1, 0.2, 0.3, 0.4]],
            }
        )
        found = overlap_chroma.shortlist(
            collection, FakeEmbedder(), [f"k{i}_2024" for i in range(4)], "prose", 2
        )
        assert found == ["k0_2024", "k1_2024"]

    def test_the_whole_section_is_one_query_not_one_per_citekey(self):
        collection = FakeCollection({"metadatas": [[]], "distances": [[]]})
        overlap_chroma.shortlist(
            collection, FakeEmbedder(), ["a_2024", "b_2024", "c_2024"], "prose", 5
        )
        assert len(collection.queries) == 1
        assert collection.queries[0]["where"] == {
            "citekey": {"$in": ["a_2024", "b_2024", "c_2024"]}
        }


class TestAbsentCitekeys:
    """#499 (M-16): a metadata-only presence check, distinct from
    `shortlist`'s similarity ranking -- see `absent_citekeys`'s
    docstring for why the two cannot share one signal."""

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
            {"where": {"citekey": {"$in": ["a_2024", "b_2024"]}}, "include": ["metadatas"]}
        ]


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
        # And it names the rule rather than just failing: never the whole
        # corpus.
        assert "whole corpus" in reason

    def test_a_missing_enrichment_layer_says_how_to_install_it(self, isolated_config, monkeypatch):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: None)
        scope, reason = overlap_embed.open_scope(draft)
        assert scope is None
        assert "poetry install --with enrich" in reason

    def test_an_unbuilt_collection_says_how_to_build_it(self, isolated_config, monkeypatch):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: ("chromadb", None))
        monkeypatch.setattr(overlap_chroma, "built_collection", lambda module: None)
        scope, reason = overlap_embed.open_scope(draft)
        assert scope is None
        assert "python -m chitragupta.enrich" in reason

    def test_everything_present_opens_a_scope(self, isolated_config, monkeypatch):
        draft = write_draft(config, "# T\n\nprose\n", dossier_rows=[("T", "`smith_2024`")])
        collection = FakeCollection()
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: ("chromadb", None))
        monkeypatch.setattr(overlap_chroma, "built_collection", lambda module: collection)
        scope, reason = overlap_embed.open_scope(draft)
        assert reason is None
        assert scope.citekeys_by_section == {"T": ["smith_2024"]}
        assert scope.collection is collection
        scope.connection.close()

    def test_unavailable_reason_is_the_same_answer_without_the_scope(
        self, isolated_config, tmp_path
    ):
        stray = tmp_path / "elsewhere.md"
        stray.write_text("# T\n\nprose\n", encoding="utf-8")
        assert overlap_embed.unavailable_reason(stray) == (overlap_embed.open_scope(stray)[1])

    def test_the_dossier_check_comes_before_anything_imports_torch(
        self, isolated_config, tmp_path, monkeypatch
    ):
        # Ordering, not a nicety: on a host that never ran the drafting
        # pipeline every draft lands here, and loading the embedding
        # stack to discover that would cost seconds per scan.
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
            ledger.upsert_reference(ledger_con, make_reference(citekey=citekey))
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
        # No lexical-overlap ceiling: `scan_findings` drops an alignment
        # a real exact or skip-gram finding overlaps, which is the check
        # a ceiling could only guess at. Measured on the graded fixture,
        # a ceiling threw away the strongest alignment in it -- which
        # neither deterministic tier caught, because substituting words
        # also moved them.
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
        # Encoding is essentially the whole cost of this tier, and a
        # book chapter's sections routinely cite the same paper.
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
        # A section's passage aligning against four of its five cited
        # sources is one place to look, not four.
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
        # The whole point of ranking per section rather than per draft:
        # scores are not comparable across sections, and a draft-wide
        # top-N drops the one hand-verified organic paraphrase in
        # chapter 1 of the real book.
        found = overlap_embed.report(
            [
                self.alignment(section=f"S{i}", score=1.0 - i / 100, start=i * 20, end=i * 20 + 10)
                for i in range(30)
            ]
        )
        assert len(found) == 30

    def test_a_later_span_overlapping_a_kept_one_is_dropped_across_sections(self):
        # Sections do not overlap in the draft, but two alignments can
        # still share draft words when a section limit of more than one
        # is in force -- the overlap check is what keeps the reported
        # spans disjoint regardless.
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
