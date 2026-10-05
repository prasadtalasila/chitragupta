"""Every artefact the enrichment layer adopts or caches is read by its own
reader before it is trusted (#967, #979).

The class is one bug in three places: a file taken on trust because it
exists, and then either stamped with a fingerprint that watches something
else, or subscripted by a caller that assumed the loader had checked its
shape. Each artefact here is damaged the same four ways a real one gets
damaged -- a write killed mid-character, a write killed between
characters, a file of the wrong shape, an entry missing a field -- and
each must be declined rather than adopted, and repaired by the next run
rather than served from then on.

The intact case runs beside the four for every artefact. Without it, a
"declined" assertion would also pass for code that declines everything.
"""

import json

import pytest

from chitragupta import config, passages
from chitragupta.enrich import _docling_cache, doc_vectors, docling_parse
from chitragupta.enrich.corpus import CorpusDoc
from tests.test_enrich_docling_parse import FakeDocumentConverter, fake_docling  # noqa: F401

# Both "truncated" cases cut at the first non-ASCII character, which every
# good payload below carries, so the two differ by exactly one byte: at a
# byte boundary the cut splits that character and the file no longer
# decodes; at a character boundary it decodes and is not JSON.
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
    """`_reuse_corpus_parse` copied the corpus layer's sidecar byte for
    byte, and `parse_doc` then stamped it with the PDF's fingerprint, which
    a later `sync` repairing the corpus copy does not move (#967)."""

    GOOD = '[{"text": "Un café, s\'il vous plaît.", "label": "text", "page": 1}]'
    WRONG_SHAPE = '{"text": "not a list of records"}'
    # No "missing key" row: the sidecar's reader requires no key of a
    # record, and a record without "text" is one its caller skips
    # (`passages._from_sidecar`), so it is readable rather than damaged.
    DAMAGE = [kind for kind in CORRUPTIONS if kind != "missing key"]

    def _corpus_parsed(self, tmp_path, sidecar: bytes) -> CorpusDoc:
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        text_path = config.PARSED_DIR / "a2024.txt"
        text_path.write_text("corpus text", encoding="utf-8")
        doc = _pdf_doc(tmp_path, text_path=str(text_path))
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
        """What a version before this fix left behind: the damaged copy
        under `content/docling/`, and a cache entry saying it is current.
        The fingerprint has not moved, so only reading the copy finds it."""
        doc = _pdf_doc(tmp_path)
        docling_parse.parse_doc(doc)
        stamped = config.DOCLING_DIR / "a2024.passages.json"
        stamped.write_bytes(_corrupted(kind, self.GOOD, self.WRONG_SHAPE, ""))

        docling_parse.parse_doc(doc)

        assert FakeDocumentConverter.call_count == 2
        assert passages.sidecar_state(stamped) == "ok"

    def test_a_sidecar_gone_between_the_check_and_the_read_is_declined(self, tmp_path, monkeypatch):
        """`_corpus_parse_available` stats the sidecar and `read_records`
        opens it, and a concurrent `sync` clears sidecars before every
        re-parse; no sidecar at that point means nothing to adopt."""
        doc = self._corpus_parsed(tmp_path, self.GOOD.encode("utf-8"))
        monkeypatch.setattr(passages, "read_records", lambda path: None)
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1


class _OneDimensionModel:
    """Each chunk's vector is its length, like the topic suite's FakeModel,
    and every call is counted so a cache hit can be told from a miss."""

    calls = 0

    def encode(self, chunks, show_progress_bar=False):
        _OneDimensionModel.calls += 1
        return [[float(len(chunk))] for chunk in chunks]


@pytest.mark.usefixtures("isolated_config")
class TestTheEmbedCacheIsReadBeforeItIsUsed:
    """`_load_embed_cache` checked only that the file held a dict, and
    `document_embeddings` subscripted every entry's `["hash"]`, so one
    malformed entry failed every topic stage (#979). A file cut inside a
    character raised past the loader too, which caught only JSON errors."""

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
        """One bad entry costs one re-embed, not the whole cache."""
        good = json.loads(self._good())
        self._write(json.dumps({**good, "other2024": entry}).encode("utf-8"))
        assert doc_vectors._load_embed_cache() == good


@pytest.mark.usefixtures("isolated_config", "fake_docling")
class TestTheDoclingCacheIsReadBeforeItIsTrusted:
    """The fingerprint cache that stamps both of the above. Its loader
    already declined every damaged shape but one: a file cut inside a
    character raised `UnicodeDecodeError` out of every `parse_corpus`."""

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
