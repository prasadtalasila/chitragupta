import importlib.util
import inspect
import sys
import types

import numpy
import pytest

from chitragupta import chroma_paging, config, overlap_chroma
from chitragupta.enrich import embed_index
from chitragupta.enrich.corpus import CorpusDoc

chromadb_available = importlib.util.find_spec("chromadb") is not None
sentence_transformers_available = importlib.util.find_spec("sentence_transformers") is not None
bertopic_available = importlib.util.find_spec("bertopic") is not None


class CountingModel:
    def __init__(self, model_name):
        self.model_name = model_name
        self.calls = []

    def encode(self, texts, show_progress_bar=False):
        self.calls.append(list(texts))
        return numpy.array([[float(len(text)), float(sum(map(ord, text[:8])))] for text in texts])


@pytest.fixture
def real_chromadb(monkeypatch, isolated_config):
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
        kept = doc_with_text(tmp_path, "a2024", " ".join(["twin"] * 40))
        departing = doc_with_text(tmp_path, "b2024", " ".join(["shadow"] * 40))
        embed_index.build_index([kept, departing])

        embed_index.build_index([kept])

        client, _model = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        assert collection.get(where={"citekey": "b2024"})["ids"] == []

    def test_the_prune_reads_a_collection_that_spans_several_pages(
        self, real_chromadb, isolated_config, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(chroma_paging, "PAGE_SIZE", 1)
        kept = doc_with_text(tmp_path, "a2024", " ".join(["twin"] * 40))
        first = doc_with_text(tmp_path, "b2024", " ".join(["shadow"] * 40))
        second = doc_with_text(tmp_path, "c2024", " ".join(["ember"] * 40))
        embed_index.build_index([kept, first, second])

        embed_index.build_index([kept])

        client, _model = embed_index.get_client_and_model()
        collection = client.get_or_create_collection(embed_index.collection_name())
        assert collection.get(where={"citekey": "b2024"})["ids"] == []
        assert collection.get(where={"citekey": "c2024"})["ids"] == []
        assert collection.get(where={"citekey": "a2024"})["ids"] == ["a2024::0"]


@pytest.mark.skipif(not chromadb_available, reason="chromadb not installed")
class TestShortlistAgainstRealChromadb:
    class PointEmbedder:
        def encode_lists(self, texts):
            return [[0.0, 0.0] for _ in texts]

    def test_a_dominant_source_does_not_crowd_the_others_out(self, tmp_path):
        import chromadb

        collection = chromadb.PersistentClient(path=str(tmp_path)).create_collection("shortlist")
        placed = [("a2024", 0.10 + i / 100) for i in range(6)] + [("b2024", 0.2), ("c2024", 0.3)]
        collection.add(
            ids=[f"{key}::{i}" for i, (key, _) in enumerate(placed)],
            embeddings=[[x, 0.0] for _, x in placed],
            metadatas=[{"citekey": key} for key, _ in placed],
        )
        found = overlap_chroma.shortlist(
            collection,
            self.PointEmbedder(),
            ["d2024", "c2024", "b2024", "a2024"],
            "One sentence of section prose.",
            3,
        )
        assert found == ["a2024", "b2024", "c2024"]


@pytest.mark.skipif(
    not (chromadb_available and sentence_transformers_available and bertopic_available),
    reason="the enrich extra is not installed",
)
class TestTheFakesStillMatchTheRealApi:
    @staticmethod
    def _accepts(func, keyword: str) -> bool:
        return keyword in inspect.signature(func).parameters

    def test_persistent_client_still_takes_path(self):
        import chromadb

        assert self._accepts(chromadb.PersistentClient, "path")

    @pytest.mark.parametrize(
        "method,keywords",
        [
            ("upsert", ("ids", "documents", "embeddings", "metadatas")),
            ("get", ("where", "include", "limit", "offset")),
            ("update", ("ids", "metadatas")),
            ("delete", ("ids",)),
            ("query", ("query_embeddings", "n_results", "where", "include")),
        ],
    )
    def test_the_collection_methods_the_fake_models_still_exist(self, method, keywords):
        from chromadb.api.models.Collection import Collection

        real = getattr(Collection, method, None)
        assert real is not None, f"chromadb's Collection no longer has {method}()"
        for keyword in keywords:
            assert self._accepts(real, keyword), (
                f"chromadb's Collection.{method}() no longer accepts {keyword!r}, "
                "which chitragupta/enrich/embed_index.py or "
                "chitragupta/overlap_chroma.py passes and the fakes in "
                "tests/test_enrich_embed_index.py or tests/test_overlap_embed.py model."
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
        from bertopic import BERTopic

        assert self._accepts(BERTopic.__init__, keyword)

    def test_bertopic_still_fits_from_texts_and_precomputed_embeddings(self):
        from bertopic import BERTopic

        parameters = list(inspect.signature(BERTopic.fit_transform).parameters)
        assert parameters[:3] == ["self", "documents", "embeddings"]
        assert hasattr(BERTopic, "get_topic_info")


class TestCropsAgainstTheRealRenderer:
    @staticmethod
    def _blank_pdf(path, width=200, height=100, pages=2):
        pdfium = pytest.importorskip("pypdfium2")
        pdf = pdfium.PdfDocument.new()
        for _ in range(pages):
            pdf.new_page(width, height)
        pdf.save(str(path))
        return path

    def test_real_crop_arithmetic_matches_what_the_fake_models(self, tmp_path):
        pdfium = pytest.importorskip("pypdfium2")
        pdf = pdfium.PdfDocument(str(self._blank_pdf(tmp_path / "blank.pdf")))
        page = pdf[0]

        bitmap = page.render(scale=2.0, crop=(10, 20, 30, 40))

        assert bitmap.to_pil().size == (round((200 - 10 - 30) * 2), round((100 - 20 - 40) * 2))

    @pytest.mark.parametrize(
        "origin,top,bottom",
        [
            ("BOTTOMLEFT", 90, 40),
            ("TOPLEFT", 10, 60),
        ],
    )
    def test_crop_insets_against_a_real_bounding_box(self, origin, top, bottom):
        doc_types = pytest.importorskip("docling_core.types.doc")
        from chitragupta.enrich import _docling_crops

        box = doc_types.BoundingBox(
            l=10, t=top, r=60, b=bottom, coord_origin=getattr(doc_types.CoordOrigin, origin)
        )

        assert _docling_crops.crop_insets(box, 200.0, 100.0) == (10.0, 40.0, 140.0, 10.0)

    def test_write_picture_crops_end_to_end(self, tmp_path):
        pytest.importorskip("pypdfium2")
        doc_types = pytest.importorskip("docling_core.types.doc")
        from PIL import Image

        from chitragupta.enrich import _docling_crops

        pdf_path = self._blank_pdf(tmp_path / "paper.pdf")
        box = doc_types.BoundingBox(
            l=10, t=90, r=60, b=40, coord_origin=doc_types.CoordOrigin.BOTTOMLEFT
        )
        dl_doc = types.SimpleNamespace(
            pictures=[types.SimpleNamespace(prov=[types.SimpleNamespace(page_no=1, bbox=box)])]
        )
        art = tmp_path / "paper_artifacts"

        names = _docling_crops.write_picture_crops(pdf_path, dl_doc, art, 2.0)

        assert names == ["paper_artifacts/picture_000000.png"]
        written = art / "picture_000000.png"
        assert written.exists()
        assert Image.open(written).size == (100, 100)
