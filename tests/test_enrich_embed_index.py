"""chitragupta/enrich/embed_index.py: sentence-transformers + Chroma, the
embeddings-based retrieval upgrade path for chitragupta/retrieval.py.

chromadb/sentence_transformers are mocked via sys.modules for fast,
deterministic unit tests -- they're imported lazily inside functions
(not at module top), so patching sys.modules before calling those
functions shadows the real packages for the duration of the test
without needing them uninstalled.
"""

import io
import re
import subprocess
import sys
import types

import pytest

from chitragupta import chroma_paging, config
from chitragupta.enrich import _rerank, embed_index
from chitragupta.enrich.corpus import CorpusDoc


# SQLite's SQLITE_MAX_VARIABLE_NUMBER on 3.32+, and so the ceiling on
# how many rows one Chroma `get` may return -- see FakeCollection.get.
SQLITE_VARIABLE_LIMIT = 32766


class FakeArray(list):
    def tolist(self):
        return list(self)


class FakeSentenceTransformer:
    instances = []

    def __init__(self, model_name):
        self.model_name = model_name
        FakeSentenceTransformer.instances.append(self)

    def encode(self, texts, show_progress_bar=False):
        # Deterministic "embedding": length of each text as a 1-d vector.
        return FakeArray([FakeArray([float(len(t))]) for t in texts])


class FakeCollection:
    """Models enough of a real chromadb.Collection's get/upsert/delete
    persistence semantics for build_index()'s incremental skip logic to
    exercise for real, not just record calls.

    Including the one limit that only shows up on a real corpus (#581):
    Chroma's SQLite backend resolves a `get` by re-fetching the matching
    rows with an `IN (?, ?, ...)` list, one bound variable per *returned*
    row, so a `get` whose result set passes SQLITE_VARIABLE_LIMIT is
    rejected by SQLite rather than truncated. Measured against the real
    chromadb 1.5.9 / SQLite 3.46.1 before being modelled here: 32766 rows
    come back, 32767 raise `chromadb.errors.InternalError: ... too many
    SQL variables`. The message is reproduced; the exception type is not,
    because importing chromadb's real error class here would defeat the
    point of a fake, and nothing in the shipped code catches it.
    """

    def __init__(self):
        self.upserted = []
        self.query_response = None
        self.last_n_results = None
        self._store = {}  # id -> {"document":..., "embedding":..., "metadata":...}

    def upsert(self, ids, documents, embeddings, metadatas):
        self.upserted.append(
            {
                "ids": ids,
                "documents": documents,
                "embeddings": embeddings,
                "metadatas": metadatas,
            }
        )
        for i, doc, emb, meta in zip(ids, documents, embeddings, metadatas):
            self._store[i] = {"document": doc, "embedding": emb, "metadata": meta}

    def get(self, where=None, include=None, limit=None, offset=None):
        items = list(self._store.items())
        if where:
            key, value = next(iter(where.items()))
            items = [(i, v) for i, v in items if v["metadata"].get(key) == value]
        items = items[offset or 0 :]
        if limit is not None:
            items = items[:limit]
        if len(items) > SQLITE_VARIABLE_LIMIT:
            raise RuntimeError(
                "Error executing plan: Internal error: error returned from "
                "database: (code: 1) too many SQL variables"
            )
        return {
            "ids": [i for i, _ in items],
            "documents": [v["document"] for _, v in items],
            "metadatas": [v["metadata"] for _, v in items],
        }

    def delete(self, ids):
        for i in ids:
            self._store.pop(i, None)

    def update(self, ids, metadatas):
        for i, meta in zip(ids, metadatas):
            if i in self._store:
                self._store[i]["metadata"] = meta

    def query(self, query_embeddings, n_results):
        self.last_n_results = n_results
        return self.query_response


class FakeChromaClient:
    """Models chromadb.PersistentClient's actual persistence semantics:
    two client instances constructed with the same `path` see the same
    collections (backed by files on disk, in the real thing) -- which
    matters here because build_index()/search() each call
    get_client_and_model() independently, so a test that pre-seeds a
    collection via one client instance needs a later instance (same
    path) to see it too."""

    instances = []
    _stores_by_path = {}

    def __init__(self, path):
        self.path = path
        self.collections = FakeChromaClient._stores_by_path.setdefault(path, {})
        FakeChromaClient.instances.append(self)

    def get_or_create_collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


@pytest.fixture
def fake_enrich_deps(monkeypatch):
    FakeSentenceTransformer.instances.clear()
    FakeChromaClient.instances.clear()
    FakeChromaClient._stores_by_path.clear()

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    fake_chromadb_module = types.ModuleType("chromadb")
    fake_chromadb_module.PersistentClient = FakeChromaClient
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb_module)

    return types.SimpleNamespace(client_cls=FakeChromaClient, model_cls=FakeSentenceTransformer)


class TestChunkText:
    def test_empty_text_returns_no_chunks(self):
        assert embed_index.chunk_text("") == []

    def test_short_text_single_chunk(self):
        assert embed_index.chunk_text("one two three", chunk_words=200, overlap_words=40) == [
            "one two three"
        ]

    def test_overlap_arithmetic(self):
        text = " ".join(str(i) for i in range(10))  # "0 1 2 ... 9"
        chunks = embed_index.chunk_text(text, chunk_words=4, overlap_words=1)
        assert chunks == ["0 1 2 3", "3 4 5 6", "6 7 8 9", "9"]


class TestStripImageRefs:
    def test_drops_referenced_images_but_keeps_captions(self):
        markdown = (
            "## Results\n\n"
            "![Image](paper_artifacts/image_000003_"
            "f668750d27034c34410db49e47fdf48b467fade315f521d8a7697c87e25fec82.png)\n\n"
            "Figure 3. Sensor placement on the test article.\n\n"
            "The sensors were placed as shown.\n"
        )
        out = embed_index.strip_image_refs(markdown)

        assert "![Image]" not in out
        assert ".png" not in out
        # The caption is a separate docling text item, not the image's alt
        # text -- it's real prose about the figure and must survive.
        assert "Figure 3. Sensor placement on the test article." in out
        assert "The sensors were placed as shown." in out

    def test_drops_bare_image_placeholders(self):
        out = embed_index.strip_image_refs("intro\n\n<!-- image -->\n\nbody\n")
        assert "<!-- image -->" not in out
        assert "intro" in out
        assert "body" in out

    def test_collapses_the_gap_left_behind(self):
        out = embed_index.strip_image_refs("a\n\n<!-- image -->\n\nb\n")
        assert "\n\n\n" not in out

    def test_leaves_inline_bang_bracket_text_alone(self):
        """Only whole-line image references are markers; a bracket
        sequence mid-sentence is prose and must not be eaten."""
        prose = "The result was surprising![1] and worth noting.\n"
        assert embed_index.strip_image_refs(prose) == prose


class TestGetText:
    def test_strips_image_refs_from_docling_output(self, isolated_config):
        isolated_config.DOCLING_DIR.mkdir(parents=True)
        (isolated_config.DOCLING_DIR / "a2024.md").write_text(
            "real text\n\n![Image](a2024_artifacts/image_000000_abc.png)\n\nmore text\n"
        )
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=None)

        out = embed_index.get_text(doc)

        assert "image_000000_abc.png" not in out
        assert "real text" in out
        assert "more text" in out

    def test_prefers_docling_output(self, isolated_config):
        isolated_config.DOCLING_DIR.mkdir(parents=True)
        (isolated_config.DOCLING_DIR / "a2024.md").write_text("docling content")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=None, text_path="ignored.txt")
        assert embed_index.get_text(doc) == "docling content"

    def test_falls_back_to_text_path(self, isolated_config, tmp_path):
        parsed = tmp_path / "parsed.txt"
        parsed.write_text("parsed text content")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=None, text_path=str(parsed))
        assert embed_index.get_text(doc) == "parsed text content"

    def test_falls_back_to_pdftotext_subprocess(self, isolated_config, monkeypatch, tmp_path):
        def fake_run(cmd, **kwargs):
            out_path = cmd[-1]
            with open(out_path, "w") as f:
                f.write("pdftotext output")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(tmp_path / "a.pdf"))
        assert embed_index.get_text(doc) == "pdftotext output"

    def test_returns_none_when_nothing_available(self, isolated_config):
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=None)
        assert embed_index.get_text(doc) is None


class TestGetClientAndModel:
    def test_creates_persistent_client_and_model(self, isolated_config, fake_enrich_deps):
        client, model = embed_index.get_client_and_model()
        assert isinstance(client, FakeChromaClient)
        assert client.path == str(isolated_config.CHROMA_DIR)
        assert isolated_config.CHROMA_DIR.exists()
        assert model.model_name == isolated_config.EMBEDDING_MODEL


class TestBuildIndex:
    def test_indexes_docs_with_text_and_counts_chunks(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        parsed = tmp_path / "a.txt"
        parsed.write_text(" ".join(["word"] * 10))
        doc_with_text = CorpusDoc(citekey="a2024", title="A", pdf_path=None, text_path=str(parsed))
        doc_without_text = CorpusDoc(citekey="b2024", title="B", pdf_path=None)

        counts = embed_index.build_index([doc_with_text, doc_without_text])

        assert counts["a2024"] == 1
        assert counts["b2024"] == 0

        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]
        assert len(collection.upserted) == 1
        upsert_call = collection.upserted[0]
        assert upsert_call["ids"] == ["a2024::0"]
        assert upsert_call["metadatas"][0] == {
            "citekey": "a2024",
            "title": "A",
            "text_hash": embed_index.hash_text(" ".join(["word"] * 10)),
        }

    def test_empty_chunks_from_whitespace_only_text(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        parsed = tmp_path / "empty.txt"
        parsed.write_text("   ")
        doc = CorpusDoc(citekey="a2024", title="A", pdf_path=None, text_path=str(parsed))
        counts = embed_index.build_index([doc])
        assert counts["a2024"] == 0


class TestBuildIndexIncremental:
    def make_doc(self, tmp_path, text, citekey="a2024"):
        parsed = tmp_path / f"{citekey}.txt"
        parsed.write_text(text)
        return CorpusDoc(citekey=citekey, title="A", pdf_path=None, text_path=str(parsed))

    def test_a_pre_57_collection_is_not_re_embedded(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        """Collections written before #57 carry a `doc_id` metadata key
        that build_index no longer writes or queries. They must still hit
        the unchanged-text skip: re-embedding an existing corpus because
        of a field rename would cost a full encode pass for nothing.

        This works because `citekey` was always written alongside `doc_id`
        with the same value, which is what makes the query switch safe --
        the claim is load-bearing, so it is tested rather than asserted.
        """
        doc = self.make_doc(tmp_path, "word " * 10)
        text = embed_index.get_text(doc)

        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.upsert(
            ids=["a2024::0"],
            documents=[" ".join(text.split())],
            embeddings=[[1.0]],
            metadatas=[
                {
                    "doc_id": "a2024",  # the retired key, as v3.3.0 wrote it
                    "citekey": "a2024",
                    "source": "bib",  # retired even earlier, in #56
                    "title": "A",
                    "text_hash": embed_index.hash_text(text),
                }
            ],
        )
        upserts_before = len(collection.upserted)

        counts = embed_index.build_index([doc])

        assert counts["a2024"] == 1
        assert len(collection.upserted) == upserts_before  # no re-encode

    def test_second_call_with_unchanged_text_skips_encode(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        doc = self.make_doc(tmp_path, "word " * 10)
        embed_index.build_index([doc])

        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]
        upserts_before = len(collection.upserted)

        counts = embed_index.build_index([doc])

        assert counts["a2024"] == 1
        assert len(collection.upserted) == upserts_before  # no new upsert -- encode was skipped

    def test_changed_text_re_embeds_and_replaces_chunks(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        doc = self.make_doc(tmp_path, "word " * 10)
        embed_index.build_index([doc])

        # Same citekey, different (longer) text -> different hash, different chunk count.
        doc2 = self.make_doc(tmp_path, "different word " * 300, citekey="a2024")
        counts = embed_index.build_index([doc2])

        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]
        remaining = collection.get(where={"citekey": "a2024"})

        assert counts["a2024"] == len(remaining["ids"]) > 1
        # No stale chunks left over from the first, shorter version.
        assert all(
            m["text_hash"] == embed_index.hash_text("different word " * 300)
            for m in remaining["metadatas"]
        )

    def test_shrinking_chunk_count_leaves_no_orphaned_chunks(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        doc_long = self.make_doc(tmp_path, "word " * 300)
        embed_index.build_index([doc_long])
        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]
        long_chunk_count = len(collection.get(where={"citekey": "a2024"})["ids"])
        assert long_chunk_count > 1

        doc_short = self.make_doc(tmp_path, "word " * 10, citekey="a2024")
        counts = embed_index.build_index([doc_short])

        remaining = collection.get(where={"citekey": "a2024"})
        assert len(remaining["ids"]) == counts["a2024"] == 1


class TestBuildIndexPrunesDepartedCitekeys:
    """#503, M-23: build_index only ever upserts, so a citekey dropped
    from the bib (and, after re-export + sync, the ledger) kept its
    chunks in Chroma forever -- contradicting search()'s own documented
    invariant that a returned citekey always resolves against the
    ledger."""

    def make_doc(self, tmp_path, text, citekey="a2024"):
        parsed = tmp_path / f"{citekey}.txt"
        parsed.write_text(text)
        return CorpusDoc(citekey=citekey, title="A", pdf_path=None, text_path=str(parsed))

    def test_a_citekey_absent_from_the_next_corpus_is_deleted(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        departed = self.make_doc(tmp_path, "word " * 10, citekey="departed_2024")
        staying = self.make_doc(tmp_path, "other word " * 10, citekey="staying_2024")
        embed_index.build_index([departed, staying])

        embed_index.build_index([staying])  # departed_2024 no longer in the corpus

        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]
        assert collection.get(where={"citekey": "departed_2024"})["ids"] == []
        assert len(collection.get(where={"citekey": "staying_2024"})["ids"]) == 1

    def test_an_interrupted_run_prunes_nothing(
        self, isolated_config, fake_enrich_deps, tmp_path, monkeypatch
    ):
        departed = self.make_doc(tmp_path, "word " * 10, citekey="departed_2024")
        staying = self.make_doc(tmp_path, "other word " * 10, citekey="staying_2024")
        embed_index.build_index([departed, staying])

        def raise_interrupt(*a, **kw):
            raise KeyboardInterrupt

        monkeypatch.setattr(embed_index, "_embed_doc", raise_interrupt)
        with pytest.raises(KeyboardInterrupt):
            embed_index.build_index([staying])

        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]
        # A partial pass says nothing about who departed -- must not prune.
        assert len(collection.get(where={"citekey": "departed_2024"})["ids"]) == 1

    def test_nothing_departed_leaves_the_collection_untouched(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        doc = self.make_doc(tmp_path, "word " * 10)
        embed_index.build_index([doc])
        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]

        embed_index.build_index([doc])

        assert len(collection.get(where={"citekey": "a2024"})["ids"]) == 1

    def test_an_empty_corpus_prunes_nothing(self, isolated_config, fake_enrich_deps, tmp_path):
        # An empty `docs` is the maximal partial pass, not proof every
        # document departed -- build_corpus() returns [] for an empty or
        # freshly-recreated ledger, and the far more likely cause is a
        # wrong-project CHITRAGUPTA_PROJECT/cwd than a corpus that
        # actually went to zero. Emptying a real index over that would
        # cost a full re-embed to recover.
        doc = self.make_doc(tmp_path, "word " * 10)
        embed_index.build_index([doc])
        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]

        embed_index.build_index([])

        assert len(collection.get(where={"citekey": "a2024"})["ids"]) == 1


class TestBuildIndexPrunesPastTheSqliteVariableLimit:
    """#581: the prune above read the whole collection in one `get`, and
    Chroma's SQLite backend cannot return more than
    `SQLITE_VARIABLE_LIMIT` rows from one call -- so every `corpus
    enrich` run on a corpus past that size died at the prune, after all
    the embedding work was already done.

    Note where the failure sat: on the *read*, before a single orphan had
    been identified, which is why the run that reported it failed
    identically with zero departed citekeys to remove. The delete is not
    the problem -- the real chromadb 1.5.9 takes 41050 ids in one
    `delete` call without complaint -- so a test that only counted
    deletions would have gone green on the unfixed code.
    """

    def make_doc(self, tmp_path, text, citekey="a2024"):
        parsed = tmp_path / f"{citekey}.txt"
        parsed.write_text(text)
        return CorpusDoc(citekey=citekey, title="A", pdf_path=None, text_path=str(parsed))

    def seed_departed_chunks(self, collection, count):
        """`count` chunks of a citekey no corpus will claim, written
        straight into the collection rather than embedded: this test
        needs a collection larger than the variable limit, and reaching
        that through build_index() would mean chunking 32767 chunks of
        real text for a size check."""
        collection.upsert(
            ids=[f"departed_2024::{i}" for i in range(count)],
            documents=["word" for _ in range(count)],
            embeddings=[[1.0] for _ in range(count)],
            metadatas=[{"citekey": "departed_2024", "title": "D"} for _ in range(count)],
        )

    def test_a_collection_past_the_limit_is_still_read_and_pruned(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        staying = self.make_doc(tmp_path, "word " * 10, citekey="staying_2024")
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        self.seed_departed_chunks(collection, SQLITE_VARIABLE_LIMIT + 1)

        embed_index.build_index([staying])

        assert collection.get(where={"citekey": "departed_2024"}, limit=1)["ids"] == []
        assert len(collection.get(where={"citekey": "staying_2024"})["ids"]) == 1

    def test_a_chunk_past_the_first_page_is_not_missed(
        self, isolated_config, fake_enrich_deps, tmp_path, monkeypatch
    ):
        """The page size is what decides which orphans are seen, so it is
        tested at a size the test controls rather than only at the real
        one -- a paging loop that stopped after its first page would pass
        the test above only because 32767 happens to exceed one page."""
        monkeypatch.setattr(chroma_paging, "PAGE_SIZE", 2)
        staying = self.make_doc(tmp_path, "word " * 10, citekey="staying_2024")
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        self.seed_departed_chunks(collection, 5)

        embed_index.build_index([staying])

        assert collection.get(where={"citekey": "departed_2024"})["ids"] == []


class TestBuildIndexRefreshesStaleTitle:
    """#503, m-48: the unchanged-text skip compared only text_hash, so a
    bib correction to a document's title never reached the stored
    metadata -- search() would serve the old title indefinitely."""

    def make_doc(self, tmp_path, text, title, citekey="a2024"):
        parsed = tmp_path / f"{citekey}.txt"
        parsed.write_text(text)
        return CorpusDoc(citekey=citekey, title=title, pdf_path=None, text_path=str(parsed))

    def test_a_corrected_title_is_written_without_re_encoding(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        doc = self.make_doc(tmp_path, "word " * 10, title="Old Title")
        embed_index.build_index([doc])
        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]
        upserts_before = len(collection.upserted)

        corrected = self.make_doc(tmp_path, "word " * 10, title="Corrected Title")
        counts = embed_index.build_index([corrected])

        assert counts["a2024"] == 1
        assert len(collection.upserted) == upserts_before  # no re-encode -- text is unchanged
        remaining = collection.get(where={"citekey": "a2024"})
        assert remaining["metadatas"][0]["title"] == "Corrected Title"

    def test_an_unchanged_title_triggers_no_update(
        self, isolated_config, fake_enrich_deps, tmp_path
    ):
        doc = self.make_doc(tmp_path, "word " * 10, title="Same Title")
        embed_index.build_index([doc])
        client = FakeChromaClient.instances[-1]
        collection = client.collections[embed_index.collection_name()]
        monkeypatch_calls = []
        collection.update = lambda *a, **kw: monkeypatch_calls.append((a, kw))

        embed_index.build_index([doc])

        assert monkeypatch_calls == []


class TestBuildIndexReporting:
    """Issue #50: the stage printed nothing between its header and its
    return, so a run over a real corpus was indistinguishable from a hung
    one, and the one that prompted the issue was Ctrl-C'd partway."""

    def make_doc(self, tmp_path, text, citekey="a2024"):
        parsed = tmp_path / f"{citekey}.txt"
        parsed.write_text(text)
        return CorpusDoc(citekey=citekey, title="A", pdf_path=None, text_path=str(parsed))

    def test_names_each_document_with_its_position_and_outcome(
        self, isolated_config, fake_enrich_deps, tmp_path, capsys
    ):
        docs = [
            self.make_doc(tmp_path, "word " * 10, citekey="a2024"),
            self.make_doc(tmp_path, "word " * 10, citekey="b2024"),
        ]

        embed_index.build_index(docs)

        out = capsys.readouterr().out
        assert "  [1/2] a2024 -- embedded, 1 chunk(s)" in out
        assert "  [2/2] b2024 -- embedded, 1 chunk(s)" in out

    def test_names_the_document_before_embedding_it(
        self, isolated_config, fake_enrich_deps, tmp_path, monkeypatch
    ):
        """The name has to be on the terminal *before* model.encode(), not
        after it returns: a line printed on completion still leaves the
        slowest document in the corpus looking like a hang for as long as
        it takes, which is the whole complaint in issue #50."""
        stream = io.StringIO()
        monkeypatch.setattr(sys, "stdout", stream)
        printed_when_encode_ran = []

        def encode(self, texts, show_progress_bar=False):
            printed_when_encode_ran.append(stream.getvalue())
            return FakeArray([FakeArray([float(len(t))]) for t in texts])

        monkeypatch.setattr(FakeSentenceTransformer, "encode", encode)

        embed_index.build_index([self.make_doc(tmp_path, "word " * 10)])

        assert "a2024" in printed_when_encode_ran[0]

    def test_reports_an_unchanged_document_as_such(
        self, isolated_config, fake_enrich_deps, tmp_path, capsys
    ):
        doc = self.make_doc(tmp_path, "word " * 10)
        embed_index.build_index([doc])
        capsys.readouterr()

        embed_index.build_index([doc])

        assert "  [1/1] a2024 -- unchanged, 1 chunk(s)" in capsys.readouterr().out

    def test_reports_a_document_with_no_text(self, isolated_config, fake_enrich_deps, capsys):
        doc = CorpusDoc(citekey="a2024", title="A", pdf_path=None)

        embed_index.build_index([doc])

        assert "  [1/1] a2024 -- no text to embed" in capsys.readouterr().out

    def test_reports_whitespace_only_text_as_no_text(
        self, isolated_config, fake_enrich_deps, tmp_path, capsys
    ):
        embed_index.build_index([self.make_doc(tmp_path, "   ")])

        assert "  [1/1] a2024 -- no text to embed" in capsys.readouterr().out

    def test_closing_line_tallies_every_disposition(
        self, isolated_config, fake_enrich_deps, tmp_path, capsys
    ):
        unchanged = self.make_doc(tmp_path, "word " * 10, citekey="a2024")
        embed_index.build_index([unchanged])
        capsys.readouterr()

        embed_index.build_index(
            [
                unchanged,
                self.make_doc(tmp_path, "word " * 300, citekey="b2024"),
                CorpusDoc(citekey="c2024", title="C", pdf_path=None),
            ]
        )

        out = capsys.readouterr().out
        assert (
            "  3 document(s): 1 embedded, 1 unchanged, 1 with no text -- 3 chunk(s) in the index"
        ) in out

    def test_interrupt_says_how_far_it_got_and_that_the_work_is_kept(
        self, isolated_config, fake_enrich_deps, tmp_path, monkeypatch, capsys
    ):
        docs = [
            self.make_doc(tmp_path, "word " * 10, citekey="a2024"),
            self.make_doc(tmp_path, "word " * 10, citekey="b2024"),
        ]

        calls = []

        def encode(self, texts, show_progress_bar=False):
            calls.append(texts)
            if len(calls) == 2:  # Ctrl+C while the second document is under the embedder
                raise KeyboardInterrupt
            return FakeArray([FakeArray([float(len(t))]) for t in texts])

        monkeypatch.setattr(FakeSentenceTransformer, "encode", encode)

        with pytest.raises(KeyboardInterrupt):
            embed_index.build_index(docs)

        out = capsys.readouterr().out
        assert "interrupted after 1/2 document(s)" in out
        assert "re-run to continue" in out
        # The first document's chunks are already in Chroma, and the next
        # run's text-hash check will skip them -- so the run is worth
        # something and the message has to say so.
        collection = FakeChromaClient.instances[-1].collections[embed_index.collection_name()]
        assert collection.get(where={"citekey": "a2024"})["ids"]


class TestCollectionName:
    def test_sanitizes_model_name_into_a_valid_chroma_collection_name(
        self, isolated_config, monkeypatch
    ):
        monkeypatch.setattr(config, "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        name = embed_index.collection_name()
        assert name == "corpus-sentence-transformers-all-MiniLM-L6-v2"
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]", name)

    def test_different_models_get_different_collection_names(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        name_a = embed_index.collection_name()
        monkeypatch.setattr(config, "EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
        name_b = embed_index.collection_name()
        assert name_a != name_b


class TestBuildIndexModelChange:
    def make_doc(self, tmp_path, text, citekey="a2024"):
        parsed = tmp_path / f"{citekey}.txt"
        parsed.write_text(text)
        return CorpusDoc(citekey=citekey, title="A", pdf_path=None, text_path=str(parsed))

    def test_model_swap_re_embeds_into_a_separate_collection_despite_unchanged_text(
        self, isolated_config, fake_enrich_deps, tmp_path, monkeypatch
    ):
        # Regression test: build_index()'s incremental skip previously keyed
        # only off the doc's text hash, so swapping config.toml's
        # embedding_model (e.g. MiniLM-L6-v2 -> mpnet-base-v2, a real change
        # made in this repo) on a doc whose *text* hadn't changed would skip
        # re-embedding and keep serving the old model's now-wrong-dimension
        # vectors under the new model.
        monkeypatch.setattr(config, "EMBEDDING_MODEL", "model-a")
        doc = self.make_doc(tmp_path, "word " * 10)
        embed_index.build_index([doc])

        client = FakeChromaClient.instances[-1]
        collection_a = client.collections[embed_index.collection_name()]
        assert len(collection_a.upserted) == 1

        monkeypatch.setattr(config, "EMBEDDING_MODEL", "model-b")
        counts = embed_index.build_index([doc])

        client2 = FakeChromaClient.instances[-1]
        collection_b = client2.collections[embed_index.collection_name()]

        assert collection_b is not collection_a
        assert len(collection_b.upserted) == 1  # freshly re-embedded, not skipped
        assert counts["a2024"] == 1
        assert len(collection_a.upserted) == 1  # model-a's collection untouched


class TestSearch:
    def test_combines_metadata_snippet_and_distance(self, isolated_config, fake_enrich_deps):
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = {
            "documents": [["some long document text " * 5]],
            "metadatas": [[{"citekey": "a2024", "title": "A"}]],
            "distances": [[0.123]],
        }

        results = embed_index.search("query", k=3, snippet_chars=10)
        assert len(results) == 1
        assert results[0]["citekey"] == "a2024"
        assert results[0]["distance"] == 0.123
        assert len(results[0]["snippet"]) == 10


class TestSearchCapsPerSource:
    """Issue #305: one paper's chunks must not own every slot in the top k."""

    def make_response(self, hits):
        """`hits`: `[(citekey, title, snippet_text, distance), ...]`, in the
        distance-ranked order Chroma would return them."""
        return {
            "documents": [[text for _, _, text, _ in hits]],
            "metadatas": [[{"citekey": citekey, "title": title} for citekey, title, _, _ in hits]],
            "distances": [[distance for _, _, _, distance in hits]],
        }

    def test_capping_promotes_a_second_documents_chunk_into_top_k(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 2)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response(
            [
                ("a2024", "A", "chunk a1", 0.1),
                ("a2024", "A", "chunk a2", 0.2),
                ("a2024", "A", "chunk a3", 0.3),
                ("a2024", "A", "chunk a4", 0.4),
                ("b2024", "B", "chunk b1", 0.5),
            ]
        )

        results = embed_index.search("query", k=3)

        # Truncate-then-cap would have returned three a2024 chunks and
        # never reached b2024 at all; cap-then-truncate promotes it in.
        assert [r["citekey"] for r in results] == ["a2024", "a2024", "b2024"]

    def test_cap_of_three_admits_exactly_three_not_four(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 3)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response(
            [
                ("a2024", "A", "chunk a1", 0.1),
                ("a2024", "A", "chunk a2", 0.2),
                ("a2024", "A", "chunk a3", 0.3),
                ("a2024", "A", "chunk a4", 0.4),
            ]
        )

        # k is deliberately not the binding constraint here -- only the
        # cap is -- so a 0-based-counter-with-`>` bug (admits 4) is
        # distinguishable from the fix (admits 3).
        results = embed_index.search("query", k=10)

        assert [r["citekey"] for r in results] == ["a2024", "a2024", "a2024"]

    def test_untitled_duplicate_title_documents_are_capped_apart(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 1)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response(
            [
                ("a2024", "", "chunk a1", 0.1),
                ("b2024", "", "chunk b1", 0.2),
            ]
        )

        results = embed_index.search("query", k=10)

        # A title-keyed cap (OpenScholar's bug) would bucket both under
        # "" and drop the second even though they're different papers.
        assert [r["citekey"] for r in results] == ["a2024", "b2024"]

    def test_over_fetch_is_bounded_by_a_multiple_of_k_not_by_collection_size(
        self, isolated_config, fake_enrich_deps
    ):
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response([("a2024", "A", "chunk", 0.1)])

        embed_index.search("query", k=5)

        assert collection.last_n_results > 5
        assert collection.last_n_results == 5 * config.EMBED_OVERFETCH_MULTIPLIER


class TestSearchIsSizedByConfig:
    """#380 moved all three of search()'s sizes into `config.toml`.
    Each test here fails if one of them is read from a literal again."""

    def make_response(self, hits):
        return TestSearchCapsPerSource.make_response(self, hits)

    def test_k_defaults_to_the_configured_top_k(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        monkeypatch.setattr(config, "EMBED_TOP_K", 2)
        monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 9)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response(
            [("a2024", "A", f"chunk {i}", 0.1 * i) for i in range(5)]
        )

        assert len(embed_index.search("query")) == 2

    def test_an_explicit_k_still_wins_over_the_configured_default(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        """The setting is a default, not a ceiling -- the CLI's --k and
        every skill that names a k must still be honoured."""
        monkeypatch.setattr(config, "EMBED_TOP_K", 2)
        monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 9)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response(
            [("a2024", "A", f"chunk {i}", 0.1 * i) for i in range(5)]
        )

        assert len(embed_index.search("query", k=4)) == 4

    def test_the_over_fetch_multiplier_is_configured_not_hardcoded(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        monkeypatch.setattr(config, "EMBED_OVERFETCH_MULTIPLIER", 7)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response([("a2024", "A", "chunk", 0.1)])

        embed_index.search("query", k=3)

        assert collection.last_n_results == 3 * 7


class TestSearchReranks:
    """Issue #380: a cross-encoder reorders the over-fetched passages
    **before** the per-citekey cap, never after.

    Every test here drives a **stub scorer** rather than a model. That is
    the point, not a shortcut: what is under test is the position of the
    rerank relative to the cap, and a real cross-encoder's judgement
    would make the assertions depend on a downloaded model's opinion
    instead of on the ordering this module controls.
    """

    def make_response(self, hits):
        return TestSearchCapsPerSource.make_response(self, hits)

    def stub_scorer(self, monkeypatch, by_snippet):
        """Substitute a scorer whose ranking is known: `by_snippet` maps a
        passage's text to the score the cross-encoder is to return."""
        scorer = types.SimpleNamespace(
            predict=lambda pairs: [by_snippet[snippet] for _query, snippet in pairs]
        )
        monkeypatch.setattr(_rerank, "_load_reranker", lambda _model_id: scorer)
        return scorer

    # The pool below is the one bench/bench_rerank_position.py's own
    # self_check() plants, so the shipped behaviour and the benchmark
    # that measured it are pinned against the same fixture.
    POOL = [
        ("a2024", "A", "chunk a1", 0.1),
        ("a2024", "A", "chunk a2", 0.2),
        ("a2024", "A", "chunk a3", 0.3),
        ("b2024", "B", "chunk b1", 0.4),
        ("c2024", "C", "chunk c1", 0.5),
    ]
    PROMOTES_C = {
        "chunk c1": 9.0,
        "chunk a3": 8.0,
        "chunk a1": 3.0,
        "chunk a2": 2.0,
        "chunk b1": 1.0,
    }

    def test_a_promotion_changes_which_document_survives_the_cap(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        """The whole reason the rerank sits before the cap. Reranking
        after it could only ever permute {A, A, B}; reranking before it
        puts C in and pushes B out."""
        monkeypatch.setattr(config, "RERANK", True)
        monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 2)
        self.stub_scorer(monkeypatch, self.PROMOTES_C)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response(self.POOL)

        results = embed_index.search("query", k=3)

        assert [r["citekey"] for r in results] == ["c2024", "a2024", "a2024"]

    def test_the_rejected_order_is_not_what_ships(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        """Cap-then-rerank is the plausible mistake, and it is
        distinguishable from the shipped order by the *set* of papers it
        returns, not merely by their order -- which is why this asserts
        on membership rather than on a permutation."""
        monkeypatch.setattr(config, "RERANK", True)
        monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 2)
        self.stub_scorer(monkeypatch, self.PROMOTES_C)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response(self.POOL)

        returned = {r["citekey"] for r in embed_index.search("query", k=3)}

        assert returned == {"a2024", "c2024"}
        assert returned != {"a2024", "b2024"}, (
            "the reranker ran after the cap -- it can only have permuted the "
            "chunks the bi-encoder already chose"
        )

    def test_reranking_off_is_the_default_and_leaves_the_order_alone(
        self, isolated_config, fake_enrich_deps, monkeypatch
    ):
        assert config.RERANK is False, "reranking must ship off"

        def explode(_model_id):
            raise AssertionError("a cross-encoder was constructed while rerank was off")

        monkeypatch.setattr(_rerank, "_load_reranker", explode)
        monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 2)
        client, _ = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        collection.query_response = self.make_response(self.POOL)

        results = embed_index.search("query", k=3)

        # Asserts the loader was never *called*, not merely that the
        # output looks unchanged: keeping the suite free of a model
        # download is the property, and it survives only if this fails
        # loudly when someone makes the load eager.
        assert [r["citekey"] for r in results] == ["a2024", "a2024", "b2024"]

    def test_an_empty_pool_is_returned_untouched(self, isolated_config, monkeypatch):
        def explode(_model_id):
            raise AssertionError("scored an empty pool")

        monkeypatch.setattr(_rerank, "_load_reranker", explode)
        assert _rerank.rerank("query", []) == []


class TestLoadReranker:
    """The loader itself, which every test above substitutes."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """`_load_reranker` is `lru_cache`d, so a model loaded (or a
        failure raised) in one test would otherwise be served to the
        next."""
        _rerank._load_reranker.cache_clear()
        yield
        _rerank._load_reranker.cache_clear()

    def test_a_model_that_will_not_load_raises_naming_the_key_and_the_model(self, monkeypatch):
        def exploding_cross_encoder(model_id):
            raise OSError(f"no such model: {model_id}")

        fake_st = types.ModuleType("sentence_transformers")
        fake_st.CrossEncoder = exploding_cross_encoder
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)

        with pytest.raises(RuntimeError) as excinfo:
            _rerank._load_reranker("nonexistent/model")

        # Naming both is the whole point: silently falling back to
        # un-reranked results would be invisible, since they look
        # entirely normal.
        assert "nonexistent/model" in str(excinfo.value)
        assert "[enrich].rerank_model" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, OSError)

    def test_the_model_is_constructed_once_and_cached(self, monkeypatch):
        calls = []

        def counting_cross_encoder(model_id):
            calls.append(model_id)
            return types.SimpleNamespace(predict=lambda pairs: [0.0] * len(pairs))

        fake_st = types.ModuleType("sentence_transformers")
        fake_st.CrossEncoder = counting_cross_encoder
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)

        _rerank._load_reranker("some/model")
        _rerank._load_reranker("some/model")

        # A reranked drafting session makes many search() calls; paying
        # the ~2s construction on each one would dwarf the rerank itself.
        assert calls == ["some/model"]
