"""The enrich stack against the libraries themselves, not against fakes.

`tests/test_enrich_embed_index.py` and `tests/test_enrich_topic_model.py`
put `sys.modules` fakes in front of `chromadb`, `sentence_transformers`
and `bertopic` on both CI legs, where `poetry install --with enrich` has
already installed the real ones. Those fakes
are unusually faithful -- `FakeChromaClient`'s docstring models
`PersistentClient`'s cross-instance persistence deliberately, because
`build_index()` and `search()` each call `get_client_and_model()`
independently -- and that faithfulness is exactly what makes the day they
quietly stop matching expensive (#514, m-88). Until now the only thing
standing between a fake and the real library was the manual smoke test
DEVELOPER-AGENTS.md mandates, which nothing automates.

**What this module does and does not exercise, and why.** It drives the
real `chromadb` end to end: `PersistentClient`, `get_or_create_collection`,
and the `upsert`/`get`/`update`/`delete`/`query` surface the fake models,
through `build_index()` and `search()` themselves. It does **not**
download a real embedding model. `config.EMBEDDING_MODEL` is
`sentence-transformers/all-mpnet-base-v2`, ~420 MB from HuggingFace, and
this host has no cached copy -- so a test that constructed it would make
every CI run depend on a network fetch and turn an unrelated HuggingFace
outage into a red build. The model half is checked a different way, by
`TestTheFakesStillMatchTheRealApi` below, which asks the real classes
whether they still accept what the fakes accept without instantiating
anything.

That split is the honest one rather than a convenient one: the chromadb
half is where the subtle semantics live (persistence across client
instances, `where=` filtering, metadata update without re-embedding), and
it costs nothing to run for real. The sentence-transformers and bertopic
halves are a constructor and a method call each, and their risk is a
rename or a dropped keyword -- which a signature check catches and a
download would only catch more expensively.

`FakeBERTopic` is the sharpest case for that check: it takes `**kwargs`
and records them, so it accepts *anything*, and its own suite therefore
cannot notice a keyword BERTopic has dropped. `BERTopic.__init__` has no
`**kwargs`, so asking it directly is a real question.
"""

import importlib.util
import inspect
import sys
import types

import numpy
import pytest

from chitragupta import config
from chitragupta.enrich import embed_index
from chitragupta.enrich.corpus import CorpusDoc

chromadb_available = importlib.util.find_spec("chromadb") is not None
sentence_transformers_available = importlib.util.find_spec("sentence_transformers") is not None
bertopic_available = importlib.util.find_spec("bertopic") is not None


class CountingModel:
    """A deterministic stand-in for the *model* only, so the chromadb
    half runs for real.

    Not a fake of `sentence_transformers` in the sense this module exists
    to distrust: nothing here asserts anything about what a real model
    returns. It exists to make `build_index`'s embeddings cheap and its
    re-embed decisions countable, which is what the chromadb-side
    invariants below are actually about.
    """

    def __init__(self, model_name):
        self.model_name = model_name
        self.calls = []

    def encode(self, texts, show_progress_bar=False):
        self.calls.append(list(texts))
        # A numpy array, because that is what a real `SentenceTransformer`
        # returns and `embed_index` calls `.tolist()` on the result -- a
        # plain list would make this stand-in *less* faithful than the
        # fake it is meant to be less than, and hide a real contract.
        # Two dimensions varying with content, so two different chunks are
        # not the same point: a query against identical vectors says
        # nothing about ordering.
        return numpy.array([[float(len(text)), float(sum(map(ord, text[:8])))] for text in texts])


@pytest.fixture
def real_chromadb(monkeypatch, isolated_config):
    """The real `chromadb`, with only the model stubbed out.

    Patched at `sys.modules["sentence_transformers"]` rather than by
    replacing `get_client_and_model`, so the `import chromadb` and
    `chromadb.PersistentClient(path=...)` inside that function are the
    real ones and the code path under test is the shipped one.
    """
    model = CountingModel(config.EMBEDDING_MODEL)
    fake_st = types.ModuleType("sentence_transformers")
    fake_st.SentenceTransformer = lambda name: model
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    return model


def doc_with_text(tmp_path, citekey, text, title="A Paper"):
    parsed = tmp_path / f"{citekey}.txt"
    parsed.write_text(text, encoding="utf-8")
    return CorpusDoc(citekey=citekey, title=title, pdf_path=None, text_path=str(parsed))


@pytest.mark.skipif(not chromadb_available, reason="chromadb not installed")
class TestBuildIndexAgainstRealChromadb:
    """Each of these has a counterpart in `test_enrich_embed_index.py`
    that runs against `FakeChromaClient`. That is the point: if the fake
    and the library ever disagree, one of the pair goes red."""

    def test_a_document_is_indexed_and_readable_back_through_search(
        self, real_chromadb, isolated_config, tmp_path
    ):
        counts = embed_index.build_index(
            [doc_with_text(tmp_path, "a2024", " ".join(["twin"] * 40))]
        )
        assert counts["a2024"] == 1

        found = embed_index.search("twin", k=1)
        assert [hit["citekey"] for hit in found] == ["a2024"]

    def test_a_second_client_instance_sees_the_first_ones_writes(
        self, real_chromadb, isolated_config, tmp_path
    ):
        """`FakeChromaClient`'s docstring calls this out as the semantics
        it models, because `build_index()` and `search()` each call
        `get_client_and_model()` independently. Here it is against the
        real `PersistentClient`."""
        embed_index.build_index([doc_with_text(tmp_path, "a2024", " ".join(["twin"] * 40))])
        client, _model = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        assert collection.get(where={"citekey": "a2024"})["ids"] == ["a2024::0"]

    def test_unchanged_text_is_not_re_embedded(self, real_chromadb, isolated_config, tmp_path):
        doc = doc_with_text(tmp_path, "a2024", " ".join(["twin"] * 40))
        embed_index.build_index([doc])
        before = len(real_chromadb.calls)
        embed_index.build_index([doc])
        assert len(real_chromadb.calls) == before

    def test_a_corrected_title_updates_metadata_without_re_embedding(
        self, real_chromadb, isolated_config, tmp_path
    ):
        """#503/m-48's invariant, against the real `collection.update`:
        the staleness check compares `text_hash`, so a title-only bib
        correction must reach `search()`'s output without paying
        `model.encode()` again."""
        text = " ".join(["twin"] * 40)
        embed_index.build_index([doc_with_text(tmp_path, "a2024", text, title="Old Title")])
        before = len(real_chromadb.calls)

        embed_index.build_index([doc_with_text(tmp_path, "a2024", text, title="New Title")])

        assert len(real_chromadb.calls) == before
        client, _model = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        titles = {m["title"] for m in collection.get(where={"citekey": "a2024"})["metadatas"]}
        assert titles == {"New Title"}

    def test_a_departed_citekey_stops_being_searchable(
        self, real_chromadb, isolated_config, tmp_path
    ):
        """#503/M-23, against the real `collection.delete`: `search()`
        promises a returned citekey always resolves against the ledger,
        so a citekey dropped from the corpus must lose its chunks."""
        kept = doc_with_text(tmp_path, "a2024", " ".join(["twin"] * 40))
        departing = doc_with_text(tmp_path, "b2024", " ".join(["shadow"] * 40))
        embed_index.build_index([kept, departing])

        embed_index.build_index([kept])

        client, _model = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        assert collection.get(where={"citekey": "b2024"})["ids"] == []


@pytest.mark.skipif(
    not (chromadb_available and sentence_transformers_available and bertopic_available),
    reason="the enrich extra is not installed",
)
class TestTheFakesStillMatchTheRealApi:
    """The drift check the fakes have never had.

    Every call the shipped code makes into these two libraries, asked of
    the real class: does the method still exist, and does it still accept
    the keyword arguments the fakes accept? A rename or a dropped keyword
    is how a faithful fake stops being faithful, and it is silent -- the
    fake-backed suite stays green while the pipeline breaks on a host
    that has the real thing.

    Signatures, not calls: nothing here instantiates a model (see the
    module docstring) or a client, so this costs nothing and cannot flake.
    """

    @staticmethod
    def _accepts(func, keyword: str) -> bool:
        """A *named* parameter, and deliberately not satisfied by a
        `**kwargs` in the signature.

        `SentenceTransformer.encode` has both `show_progress_bar` and a
        `kwargs`, so a lenient check would pass whether or not the
        keyword still existed -- and a renamed keyword swallowed by
        `**kwargs` is precisely the silent drift this class exists to
        catch. If a library legitimately moves one of these into
        `**kwargs`, this goes red and a human re-reads the call site,
        which is the right outcome rather than a false alarm.
        """
        return keyword in inspect.signature(func).parameters

    def test_persistent_client_still_takes_path(self):
        import chromadb

        assert self._accepts(chromadb.PersistentClient, "path")

    @pytest.mark.parametrize(
        "method,keywords",
        [
            ("upsert", ("ids", "documents", "embeddings", "metadatas")),
            ("get", ("where", "include")),
            ("update", ("ids", "metadatas")),
            ("delete", ("ids",)),
            ("query", ("query_embeddings", "n_results")),
        ],
    )
    def test_the_collection_methods_the_fake_models_still_exist(self, method, keywords):
        from chromadb.api.models.Collection import Collection

        real = getattr(Collection, method, None)
        assert real is not None, f"chromadb's Collection no longer has {method}()"
        for keyword in keywords:
            assert self._accepts(real, keyword), (
                f"chromadb's Collection.{method}() no longer accepts {keyword!r}, "
                "which chitragupta/enrich/embed_index.py passes and "
                "tests/test_enrich_embed_index.py's FakeCollection models."
            )

    def test_sentence_transformer_still_takes_a_model_name_and_encodes_quietly(self):
        from sentence_transformers import SentenceTransformer

        assert self._accepts(SentenceTransformer.__init__, "model_name_or_path")
        assert self._accepts(SentenceTransformer.encode, "show_progress_bar")

    @pytest.mark.parametrize(
        "keyword",
        [
            "embedding_model",
            "umap_model",
            "hdbscan_model",
            "vectorizer_model",
            "calculate_probabilities",
            "verbose",
        ],
    )
    def test_bertopic_still_takes_every_keyword_topic_model_passes(self, keyword):
        """`FakeBERTopic` in `tests/test_enrich_topic_model.py` takes
        `**kwargs` and records them, so it accepts anything -- which means
        that suite cannot notice a keyword BERTopic has dropped. This can.
        `BERTopic.__init__` has no `**kwargs` of its own, so each of these
        is a real named parameter or a real failure."""
        from bertopic import BERTopic

        assert self._accepts(BERTopic.__init__, keyword)

    def test_bertopic_still_fits_from_texts_and_precomputed_embeddings(self):
        """`topic_model._fit` calls `fit_transform(texts, embeddings)`
        positionally, and reads `hdbscan_model` back off the fitted model
        for soft memberships -- both of which the fake models."""
        from bertopic import BERTopic

        parameters = list(inspect.signature(BERTopic.fit_transform).parameters)
        assert parameters[:3] == ["self", "documents", "embeddings"]
        assert hasattr(BERTopic, "get_topic_info")
