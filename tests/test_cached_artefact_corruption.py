import json

import pytest

from chitragupta import config, passages
from chitragupta.enrich import _docling_cache, doc_vectors, docling_parse
from chitragupta.enrich.corpus import CorpusDoc
from tests.test_enrich_docling_parse import FakeDocumentConverter, fake_docling  # noqa: F401

CORRUPTIONS = [
    "truncated at a byte boundary",
    "truncated at a character boundary",
    "wrong top-level shape",
    "missing key",
]


def _corrupted(kind: str, good: str, wrong_shape: str, missing_key: str) -> bytes:
    cut = next(i for i, ch in enumerate(good) if ord(ch) > 127)
    damaged = {
        "truncated at a byte boundary": good[: cut + 1].encode("utf-8")[:-1],
        "truncated at a character boundary": good[: cut + 1].encode("utf-8"),
        "wrong top-level shape": wrong_shape.encode("utf-8"),
        "missing key": missing_key.encode("utf-8"),
    }
    return damaged[kind]


def _pdf_doc(tmp_path, citekey="a2024", text_path=None) -> CorpusDoc:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    return CorpusDoc(citekey=citekey, title="t", pdf_path=str(pdf), text_path=text_path)


@pytest.mark.usefixtures("isolated_config", "fake_docling")
class TestTheCorpusPassageSidecarIsReadBeforeItIsAdopted:
    GOOD = '[{"text": "Un café, s\'il vous plaît.", "label": "text", "page": 1}]'
    WRONG_SHAPE = '{"text": "not a list of records"}'
    DAMAGE = [kind for kind in CORRUPTIONS if kind != "missing key"]

    def _corpus_parsed(self, tmp_path, sidecar: bytes) -> CorpusDoc:
        text_path = config.PARSED_DIR / "a2024.txt"
        doc = _pdf_doc(tmp_path, text_path=str(text_path))
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        text_path.write_text("corpus text", encoding="utf-8")
        passages.sidecar_path(doc.citekey).write_bytes(sidecar)
        return doc

    def test_an_intact_sidecar_is_adopted(self, tmp_path):
        doc = self._corpus_parsed(tmp_path, self.GOOD.encode("utf-8"))
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 0
        adopted = passages.read_records(config.DOCLING_DIR / "a2024.passages.json")
        assert adopted == json.loads(self.GOOD)

    @pytest.mark.parametrize("kind", DAMAGE)
    def test_a_damaged_sidecar_is_declined(self, tmp_path, kind):
        doc = self._corpus_parsed(tmp_path, _corrupted(kind, self.GOOD, self.WRONG_SHAPE, ""))
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1
        assert passages.sidecar_state(config.DOCLING_DIR / "a2024.passages.json") == "ok"

    @pytest.mark.parametrize("kind", DAMAGE)
    def test_a_damaged_sidecar_already_stamped_is_repaired(self, tmp_path, kind):
        doc = _pdf_doc(tmp_path)
        docling_parse.parse_doc(doc)
        stamped = config.DOCLING_DIR / "a2024.passages.json"
        stamped.write_bytes(_corrupted(kind, self.GOOD, self.WRONG_SHAPE, ""))

        docling_parse.parse_doc(doc)

        assert FakeDocumentConverter.call_count == 2
        assert passages.sidecar_state(stamped) == "ok"

    def test_a_sidecar_gone_between_the_check_and_the_read_is_declined(self, tmp_path, monkeypatch):
        doc = self._corpus_parsed(tmp_path, self.GOOD.encode("utf-8"))
        monkeypatch.setattr(passages, "read_records", lambda path: None)
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1


class _OneDimensionModel:
    calls = 0

    def encode(self, chunks, show_progress_bar=False):
        _OneDimensionModel.calls += 1
        return [[float(len(chunk))] for chunk in chunks]


@pytest.mark.usefixtures("isolated_config")
class TestTheEmbedCacheIsReadBeforeItIsUsed:
    TEXTS = {"müller2024": "a paper about digital twins " * 5}

    def _good(self) -> str:
        text = self.TEXTS["müller2024"]
        entry = {
            "hash": doc_vectors.embed_index.hash_text(text),
            "model": config.EMBEDDING_MODEL,
            "method": doc_vectors.EMBED_METHOD,
            "embedding": [42.0],
        }
        return json.dumps({"müller2024": entry}, ensure_ascii=False)

    def _write(self, raw: bytes) -> None:
        config.TOPIC_EMBED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.TOPIC_EMBED_CACHE_PATH.write_bytes(raw)
        _OneDimensionModel.calls = 0

    def test_an_intact_cache_is_used(self):
        self._write(self._good().encode("utf-8"))
        vectors = doc_vectors.document_embeddings(self.TEXTS, _OneDimensionModel())
        assert vectors == {"müller2024": [42.0]}
        assert _OneDimensionModel.calls == 0

    @pytest.mark.parametrize("kind", CORRUPTIONS)
    def test_a_damaged_cache_is_re_embedded_and_repaired(self, kind):
        good = json.loads(self._good())
        missing_key = {"müller2024": {k: v for k, v in good["müller2024"].items() if k != "hash"}}
        self._write(_corrupted(kind, self._good(), '[["müller2024"]]', json.dumps(missing_key)))

        vectors = doc_vectors.document_embeddings(self.TEXTS, _OneDimensionModel())

        assert _OneDimensionModel.calls == 1
        assert vectors["müller2024"] != [42.0]
        assert doc_vectors._load_embed_cache()["müller2024"]["embedding"] == vectors["müller2024"]

    @pytest.mark.parametrize(
        "entry",
        [
            ["not", "a", "dict"],
            {"hash": "h", "model": "m", "method": "v"},
            {"hash": 7, "embedding": [1.0]},
            {"hash": "h", "embedding": "not a vector"},
        ],
        ids=["not a dict", "no embedding", "hash not a string", "embedding not a list"],
    )
    def test_a_malformed_entry_is_a_miss_and_its_neighbours_survive(self, entry):
        good = json.loads(self._good())
        self._write(json.dumps({**good, "other2024": entry}).encode("utf-8"))
        assert doc_vectors._load_embed_cache() == good


@pytest.mark.usefixtures("isolated_config", "fake_docling")
class TestTheDoclingCacheIsReadBeforeItIsTrusted:
    def _good(self, doc: CorpusDoc) -> str:
        payload = {
            "version": _docling_cache._CACHE_VERSION,
            "images": config.DOCLING_IMAGES,
            "ocr": config.PARSER_OCR,
            "image_scale": config.DOCLING_IMAGE_SCALE,
            "formulas": config.DOCLING_FORMULAS,
            "items": {doc.citekey: docling_parse._fingerprint(doc)},
        }
        return json.dumps(payload, ensure_ascii=False)

    def _parsed_once(self, tmp_path) -> CorpusDoc:
        doc = _pdf_doc(tmp_path, citekey="müller2024")
        docling_parse.parse_doc(doc)
        return doc

    def test_an_intact_cache_skips_the_parse(self, tmp_path):
        doc = self._parsed_once(tmp_path)
        config.DOCLING_CACHE_PATH.write_text(self._good(doc), encoding="utf-8")
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1

    @pytest.mark.parametrize("kind", CORRUPTIONS)
    def test_a_damaged_cache_re_parses_and_is_repaired(self, tmp_path, kind):
        doc = self._parsed_once(tmp_path)
        good = json.loads(self._good(doc))
        missing_key = json.dumps({k: v for k, v in good.items() if k != "items"})
        config.DOCLING_CACHE_PATH.write_bytes(
            _corrupted(kind, self._good(doc), json.dumps(good["items"]), missing_key)
        )

        docling_parse.parse_doc(doc)

        assert FakeDocumentConverter.call_count == 2
        assert _docling_cache._load_cache() == good["items"]
