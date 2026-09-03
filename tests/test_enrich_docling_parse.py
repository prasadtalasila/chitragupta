"""chitragupta/enrich/docling_parse.py: layout-aware PDF parsing via Docling.

Docling is mocked via sys.modules (imported lazily inside parse_doc, not
at module top), so these stay fast and don't need real model weights.
"""

import contextlib
import importlib.machinery
import json
import multiprocessing
import os
import re
import sys
import threading
import types
from concurrent.futures import Future
from pathlib import Path

import pytest

from chitragupta import config, passages, pdf_text
from chitragupta.enrich import (
    _docling_cache,
    _docling_figures,
    _docling_pool,
    _docling_reuse,
    docling_parse,
)
from chitragupta.enrich.corpus import CorpusDoc


# What `_docling_crops` writes: the picture's index in
# `dl_doc.pictures`, zero-padded. Not docling's
# `image_<index>_<sha256>.png` -- that digest was of bitmap bytes docling
# held all at once and this pipeline no longer has (#600).
FAKE_IMAGE_NAME = "picture_{i:06d}.png"


class FakePicture:
    """Enough of a docling PictureItem for _figure_records: a caption and
    a page provenance.

    `image.uri.path` deliberately carries a base64 `data:` payload, which
    is what real Docling holds -- `save_as_markdown` does NOT rewrite it
    to the written filename. An earlier fake returned a tidy path here,
    which let a bug through: the records inlined ~17MB of base64 across
    one real corpus instead of naming the files.
    """

    def __init__(self, caption="", page=1):
        self._caption = caption
        bbox = types.SimpleNamespace(l=10.0, t=90.0, r=60.0, b=40.0)
        self.prov = [types.SimpleNamespace(page_no=page, bbox=bbox)] if page is not None else []
        self.image = types.SimpleNamespace(
            uri=types.SimpleNamespace(path="image/png;base64,iVBORw0KGgoAAAANSUhEUg" + "A" * 200)
        )

    def caption_text(self, _doc):
        return self._caption


class FakeTextItem:
    """A docling TextItem: label, text, and prov[0] with page + bbox."""

    def __init__(self, text, label="text", page=1):
        self.text = text
        self.label = f"DocItemLabel.{label.upper()}"
        if page is None:
            self.prov = []
        else:
            bbox = types.SimpleNamespace(l=1.0, t=2.0, r=3.0, b=4.0)
            self.prov = [types.SimpleNamespace(page_no=page, bbox=bbox)]


class FakeDocument:
    last_image_mode = None

    def __init__(self, markdown, pictures=None, texts=None):
        self._markdown = markdown
        self.pictures = pictures if pictures is not None else []
        self.texts = texts if texts is not None else []

    def export_to_markdown(self):
        """One `<!-- image -->` per picture, as real docling emits when it
        was never asked to generate the bitmaps (#600).

        Those placeholders are what `_inject_image_refs` rewrites into
        references to the files `_docling_crops` wrote, so a fake without
        them would leave that whole step unexercised.
        """
        body = self._markdown
        for _ in self.pictures:
            body += "\n\n<!-- image -->"
        return body

    def save_as_markdown(self, path, image_mode=None):
        """Kept only to catch its return: nothing in `chitragupta/` may call
        this any more.

        It is what makes docling materialise every bitmap it holds, which
        is the bug in #600 -- and it re-reads and re-decodes any file an
        ImageRef points at, so it cannot be used even to write references
        to crops already on disk.
        """
        FakeDocument.last_image_mode = image_mode
        raise AssertionError(
            "save_as_markdown must not be called -- it materialises every "
            "held bitmap (#600); export_to_markdown + _inject_image_refs "
            "is the path."
        )


class FakeConversionResult:
    """What a real docling `convert()` returns on a clean parse.

    `status` is not decoration: real docling always sets it, and
    `check_docling_status` now *fails closed* on its absence (#509/m-36),
    since without it a PARTIAL_SUCCESS -- a document that stops at page k
    of n -- cannot be told from a clean parse.
    """

    def __init__(self, markdown, pictures=None, texts=None):
        self.document = FakeDocument(markdown, pictures, texts)
        self.status = types.SimpleNamespace(name="SUCCESS")


class FakeDocumentConverter:
    last_convert_path = None
    last_format_options = None
    call_count = 0
    # Constructions, as distinct from call_count's conversions: every
    # construction re-initialises Docling's real layout/table/OCR models,
    # which is the cost parse_corpus's hoisted converter exists to pay once.
    build_count = 0
    pictures = []
    texts = []

    def __init__(self, format_options=None):
        FakeDocumentConverter.last_format_options = format_options
        FakeDocumentConverter.build_count += 1

    def convert(self, pdf_path):
        FakeDocumentConverter.last_convert_path = pdf_path
        FakeDocumentConverter.call_count += 1
        if "explode" in str(pdf_path):
            raise RuntimeError("simulated docling failure")
        return FakeConversionResult(
            f"# Parsed content of {pdf_path}",
            FakeDocumentConverter.pictures,
            FakeDocumentConverter.texts,
        )


@pytest.fixture
def fake_docling(monkeypatch):
    FakeDocumentConverter.last_convert_path = None
    FakeDocumentConverter.last_format_options = None
    FakeDocumentConverter.call_count = 0
    FakeDocumentConverter.build_count = 0
    _docling_pool._reset_worker_converter()
    FakeDocumentConverter.pictures = []
    FakeDocumentConverter.texts = []
    FakeDocument.last_image_mode = None

    converter_mod = types.ModuleType("docling.document_converter")
    converter_mod.DocumentConverter = FakeDocumentConverter
    converter_mod.PdfFormatOption = lambda pipeline_options=None: types.SimpleNamespace(
        pipeline_options=pipeline_options
    )
    base_models = types.ModuleType("docling.datamodel.base_models")
    base_models.InputFormat = types.SimpleNamespace(PDF="pdf")
    pipeline_options = types.ModuleType("docling.datamodel.pipeline_options")
    pipeline_options.PdfPipelineOptions = lambda: types.SimpleNamespace(
        generate_picture_images=False,
        images_scale=1.0,
        do_ocr=True,
        accelerator_options=None,
        document_timeout=None,
    )
    accelerator = types.ModuleType("docling.datamodel.accelerator_options")
    accelerator.AcceleratorOptions = lambda num_threads=None, device=None: types.SimpleNamespace(
        num_threads=num_threads, device=device
    )
    core_doc = types.ModuleType("docling_core.types.doc")
    core_doc.ImageRefMode = types.SimpleNamespace(REFERENCED="referenced")

    for name, mod in [
        ("docling", types.ModuleType("docling")),
        ("docling.document_converter", converter_mod),
        ("docling.datamodel", types.ModuleType("docling.datamodel")),
        ("docling.datamodel.base_models", base_models),
        ("docling.datamodel.pipeline_options", pipeline_options),
        ("docling.datamodel.accelerator_options", accelerator),
        ("docling_core", types.ModuleType("docling_core")),
        ("docling_core.types", types.ModuleType("docling_core.types")),
        ("docling_core.types.doc", core_doc),
    ]:
        # Every fake gets a `__spec__`, which a normally-imported module
        # always has and a bare `types.ModuleType` never does.
        # `importlib.util.find_spec` -- which `parse_corpus`'s
        # not-installed probe calls (#509/m-40) -- raises `ValueError` on
        # a name already in `sys.modules` with no spec, so a fake without
        # one stands in for something that cannot exist.
        if mod.__spec__ is None:
            mod.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
        monkeypatch.setitem(sys.modules, name, mod)
    return FakeDocumentConverter


class TestParseDoc:
    def test_no_pdf_path_raises(self, isolated_config):
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=None)
        with pytest.raises(ValueError, match="no PDF to parse"):
            docling_parse.parse_doc(doc)

    def test_writes_markdown_output(self, isolated_config, fake_docling, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        out_path = docling_parse.parse_doc(doc)

        assert out_path == isolated_config.DOCLING_DIR / "a2024.md"
        assert "Parsed content" in out_path.read_text()
        assert FakeDocumentConverter.last_convert_path == str(pdf)


class TestImageExtraction:
    @pytest.fixture
    def images_on(self, isolated_config, monkeypatch, fake_pdfium):
        """Figures on, with the pypdfium2 that now renders them faked.

        `fake_pdfium` is a fixture dependency rather than a per-test
        argument because since #600 *every* images-on parse goes through
        pdfium: docling is no longer asked for the bitmaps, so a test on
        this path without the fake would fail on the import rather than
        on anything it meant to assert.
        """
        monkeypatch.setattr(isolated_config, "DOCLING_IMAGES", True)
        return isolated_config

    def _doc(self, tmp_path, citekey="richstein_characterizing_2024"):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        return CorpusDoc(citekey=citekey, title="t", pdf_path=str(pdf))

    def test_images_off_uses_export_and_writes_no_figure_index(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            FakeDocumentConverter, "pictures", [FakePicture("Figure 1. A plot", page=3)]
        )
        docling_parse.parse_doc(self._doc(tmp_path))

        assert FakeDocument.last_image_mode is None  # save_as_markdown never called
        # Pipeline options are always passed now (they carry do_ocr), so
        # "images off" is asserted on the option itself rather than on the
        # converter having been built bare.
        assert (
            FakeDocumentConverter.last_format_options[
                "pdf"
            ].pipeline_options.generate_picture_images
            is False
        )
        assert not (
            isolated_config.DOCLING_DIR / "richstein_characterizing_2024.figures.json"
        ).exists()

    def test_ocr_is_off_by_default(self, isolated_config, fake_docling, tmp_path):
        docling_parse.parse_doc(self._doc(tmp_path))
        assert FakeDocumentConverter.last_format_options["pdf"].pipeline_options.do_ocr is False

    def test_ocr_can_be_turned_back_on(self, isolated_config, fake_docling, monkeypatch, tmp_path):
        monkeypatch.setattr(isolated_config, "PARSER_OCR", True)
        docling_parse.parse_doc(self._doc(tmp_path))
        assert FakeDocumentConverter.last_format_options["pdf"].pipeline_options.do_ocr is True

    def test_formula_enrichment_is_off_by_default(self, isolated_config, fake_docling, tmp_path):
        """Off unless asked for: the formula model is an extra download
        and an extra pass per page, the same economics as OCR."""
        docling_parse.parse_doc(self._doc(tmp_path))
        opts = FakeDocumentConverter.last_format_options["pdf"].pipeline_options
        assert opts.do_formula_enrichment is False

    def test_formula_enrichment_can_be_turned_on(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(isolated_config, "DOCLING_FORMULAS", True)
        docling_parse.parse_doc(self._doc(tmp_path))
        opts = FakeDocumentConverter.last_format_options["pdf"].pipeline_options
        assert opts.do_formula_enrichment is True

    def test_images_on_never_asks_docling_for_the_bitmaps(
        self, images_on, fake_docling, tmp_path, monkeypatch
    ):
        """The fix for #600, at the point where it is decided.

        Docling retains every crop it generates until save_as_markdown --
        +8.95 GiB on one 99-page deck, and a 74.31 GiB failure at
        docling_image_scale = 6.0. So the pipeline stopped asking: the
        boxes come from docling, the bitmaps from pdfium, one at a time.
        `generate_picture_images` must stay unset even with figures
        *enabled*, which is the case that used to set it.
        """
        monkeypatch.setattr(
            FakeDocumentConverter, "pictures", [FakePicture("Figure 1. A plot", page=3)]
        )
        docling_parse.parse_doc(self._doc(tmp_path))

        opts = FakeDocumentConverter.last_format_options["pdf"].pipeline_options
        assert opts.generate_picture_images is False
        # ...and the figures still arrive, from the other renderer.
        assert (images_on.DOCLING_DIR / "richstein_characterizing_2024.figures.json").exists()
        # save_as_markdown is what materialises the held bitmaps, so it
        # must never run -- the fake raises if it does, and this pins the
        # absence directly rather than trusting that.
        assert FakeDocument.last_image_mode is None

    def test_figure_index_cites_by_the_papers_own_number(
        self, images_on, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            FakeDocumentConverter,
            "pictures",
            [
                FakePicture("Figure 3. Sensor placement", page=7),
            ],
        )
        docling_parse.parse_doc(self._doc(tmp_path))

        records = json.loads(
            (images_on.DOCLING_DIR / "richstein_characterizing_2024.figures.json").read_text()
        )
        assert records[0]["cite"] == "Figure 3 of [@richstein_characterizing_2024], p.7"
        assert records[0]["page"] == 7
        assert records[0]["caption"] == "Figure 3. Sensor placement"

    @pytest.mark.parametrize(
        "caption,expected",
        [
            # Chapter-scoped numbering. Real captions from
            # larsen_engineering_2024, which first exposed this: matching only
            # the leading integer collapsed all four onto "Fig 1".
            ("Fig. 1.1: A CPS composed of Physical and Computational parts", "Figure 1.1"),
            ("Fig. 1.2: Overview of a DT-Enabled System concept.", "Figure 1.2"),
            ("Fig. 1.4: Fields related to Digital Twins.", "Figure 1.4"),
            # Plain, sub-figure, deeper nesting, and the other label words.
            ("Figure 3. Sensor placement", "Figure 3"),
            ("Figure 2a. Detail view", "Figure 2a"),
            ("Fig 10.2.3 Something nested", "Figure 10.2.3"),
            ("Table 2: Comparison of approaches", "Table 2"),
            ("Scheme 4 - reaction pathway", "Scheme 4"),
        ],
    )
    def test_caption_number_is_captured_whole(
        self, images_on, fake_docling, tmp_path, caption, expected, monkeypatch
    ):
        monkeypatch.setattr(FakeDocumentConverter, "pictures", [FakePicture(caption, page=3)])
        docling_parse.parse_doc(self._doc(tmp_path))

        records = json.loads(
            (images_on.DOCLING_DIR / "richstein_characterizing_2024.figures.json").read_text()
        )
        assert records[0]["cite"] == f"{expected} of [@richstein_characterizing_2024], p.3"

    def test_a_numberless_pageless_figure_is_cited_as_unplaced(
        self, images_on, fake_docling, tmp_path, monkeypatch
    ):
        """No caption number and no page provenance -- a publisher logo is
        the usual culprit. The citation names it unplaced rather than
        inventing a number or a page for it."""
        monkeypatch.setattr(
            FakeDocumentConverter, "pictures", [FakePicture("just a logo", page=None)]
        )
        docling_parse.parse_doc(self._doc(tmp_path))

        records = json.loads(
            (images_on.DOCLING_DIR / "richstein_characterizing_2024.figures.json").read_text()
        )
        assert records[0]["cite"] == "an unplaced figure in [@richstein_characterizing_2024]"
        assert records[0]["page"] is None

    def test_distinct_subfigures_do_not_collapse_onto_one_number(
        self, images_on, fake_docling, tmp_path, monkeypatch
    ):
        """The actual regression: four figures, four distinct citations."""
        monkeypatch.setattr(
            FakeDocumentConverter,
            "pictures",
            [FakePicture(f"Fig. 1.{n}: caption {n}", page=n + 2) for n in (1, 2, 3, 4)],
        )
        docling_parse.parse_doc(self._doc(tmp_path))

        records = json.loads(
            (images_on.DOCLING_DIR / "richstein_characterizing_2024.figures.json").read_text()
        )
        cites = [r["cite"] for r in records]
        assert len(set(cites)) == 4, cites
        assert "Figure 1.3 of [@richstein_characterizing_2024], p.5" in cites

    def test_image_field_names_the_file_and_never_inlines_base64(
        self, images_on, fake_docling, tmp_path, monkeypatch
    ):
        """The regression: pic.image.uri is a base64 data: URI that
        save_as_markdown does not rewrite, so reading it put the whole
        PNG in the JSON (~17MB across one real corpus)."""
        monkeypatch.setattr(
            FakeDocumentConverter, "pictures", [FakePicture("Figure 1. A plot", page=2)]
        )
        docling_parse.parse_doc(self._doc(tmp_path))

        raw = (images_on.DOCLING_DIR / "richstein_characterizing_2024.figures.json").read_text()
        assert "base64" not in raw
        records = json.loads(raw)
        assert (
            records[0]["image"]
            == f"richstein_characterizing_2024_artifacts/{FAKE_IMAGE_NAME.format(i=0)}"
        )

    def test_markdown_image_refs_are_relative_to_the_md(
        self, images_on, fake_docling, tmp_path, monkeypatch
    ):
        """Docling writes absolute paths, which bake this host's layout
        into content/docling/ and break if the folder moves."""
        monkeypatch.setattr(
            FakeDocumentConverter,
            "pictures",
            [FakePicture("Figure 1", page=1), FakePicture("Figure 2", page=2)],
        )
        out_path = docling_parse.parse_doc(self._doc(tmp_path))

        refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", out_path.read_text())
        assert len(refs) == 2
        assert all(not r.startswith("/") for r in refs), refs
        assert all(r.startswith("richstein_characterizing_2024_artifacts/") for r in refs), refs

    def test_placeholders_are_pointed_at_the_written_crops(self, images_on, tmp_path):
        """`export_to_markdown` leaves a marker per picture; this is what
        turns each one into a reference to the file rendered for it."""
        md = tmp_path / "doc.md"
        md.write_text("text\n\n<!-- image -->\n\nmore\n\n<!-- image -->\n")

        names = _docling_figures._inject_image_refs(
            md, ["doc_artifacts/picture_000000.png", "doc_artifacts/picture_000001.png"]
        )

        assert names == ["doc_artifacts/picture_000000.png", "doc_artifacts/picture_000001.png"]
        body = md.read_text()
        assert "![Image](doc_artifacts/picture_000000.png)" in body
        assert "![Image](doc_artifacts/picture_000001.png)" in body
        assert "<!-- image -->" not in body
        assert "text" in body and "more" in body

    def test_refs_are_relative_and_use_forward_slashes(self, images_on, tmp_path):
        """A Markdown image reference is URL-ish, and `content/docling/`
        has to stay movable as a unit -- generated in a container and read
        elsewhere, say. Absolute paths would bake this host's layout into
        every .md, and backslashes would make it readable only on the box
        that wrote it (this repo has a windows-latest CI leg).

        Now a property of `write_picture_crops`, which builds the names
        with an explicit "/" rather than a Path join, instead of something
        a relativiser had to repair after docling wrote absolute paths.
        """
        md = tmp_path / "doc.md"
        md.write_text("<!-- image -->\n")

        names = _docling_figures._inject_image_refs(md, ["doc_artifacts/sub/picture_000000.png"])

        assert names == ["doc_artifacts/sub/picture_000000.png"]
        assert "\\" not in md.read_text()
        assert not md.read_text().startswith("![Image](/")

    def test_a_picture_with_no_crop_keeps_its_placeholder(self, images_on, tmp_path):
        """`None` means no file was written -- a picture docling gave no
        provenance for, or one whose render failed. The marker stays, and
        `embed_text.strip_image_refs` removes either form on the way to
        the embedder."""
        md = tmp_path / "doc.md"
        md.write_text("<!-- image -->\n\n<!-- image -->\n")

        names = _docling_figures._inject_image_refs(md, [None, "art/picture_000001.png"])

        assert names == [None, "art/picture_000001.png"]
        body = md.read_text()
        assert body.count("<!-- image -->") == 1
        assert "![Image](art/picture_000001.png)" in body

    def test_a_placeholder_count_mismatch_drops_every_name(self, images_on, tmp_path, caplog):
        """Rather than shift every reference onto its neighbour's image.

        The two counts come from different docling surfaces --
        `len(dl_doc.pictures)` and the markers `export_to_markdown()`
        emitted -- so their agreeing is an assumption about the library,
        not an invariant of this code. Same trade `_figure_records` makes
        on the same suspicion.
        """
        md = tmp_path / "doc.md"
        md.write_text("<!-- image -->\n")

        names = _docling_figures._inject_image_refs(md, ["a.png", "b.png"])

        assert names == [None, None]
        assert "<!-- image -->" in md.read_text(), "markdown left alone"
        assert "1 image placeholder(s) for 2 picture(s)" in caplog.text

    def test_image_is_dropped_when_ref_count_disagrees_with_picture_count(
        self, images_on, fake_docling, tmp_path
    ):
        """Rather than pair a figure with someone else's image."""
        names = ["only_one.png"]
        pics = [FakePicture("Figure 1", page=1), FakePicture("Figure 2", page=2)]
        doc = self._doc(tmp_path)
        records = _docling_figures._figure_records(doc, types.SimpleNamespace(pictures=pics), names)
        assert [r["image"] for r in records] == [None, None]
        assert records[0]["cite"].startswith("Figure 1 of")  # citation still works

    def test_uncaptioned_picture_is_cited_by_page_not_an_invented_number(
        self, images_on, fake_docling, tmp_path, monkeypatch
    ):
        """Publisher logos and licence badges are pictures too, so the Nth
        picture is routinely not the paper's Figure N -- never guess."""
        monkeypatch.setattr(FakeDocumentConverter, "pictures", [FakePicture("", page=1)])
        docling_parse.parse_doc(self._doc(tmp_path))

        records = json.loads(
            (images_on.DOCLING_DIR / "richstein_characterizing_2024.figures.json").read_text()
        )
        assert records[0]["cite"] == "the figure on p.1 of [@richstein_characterizing_2024]"
        assert records[0]["caption"] is None


class TestReusingTheCorpusLayersParse:
    """The dependency this repository allows: the enrichment layer reads
    the corpus layer's artefacts, never the reverse.

    Nothing in these cases reaches into `chitragupta/` to make it work -- the
    corpus layer writes what it writes for its own reasons, and this
    stage either finds it or parses the PDF itself.
    """

    def _doc(self, tmp_path, citekey="a2024", parsed_text=None):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        text_path = None
        if parsed_text is not None:
            config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
            text_path = config.PARSED_DIR / f"{citekey}.txt"
            text_path.write_text(parsed_text, encoding="utf-8")
            text_path = str(text_path)
        return CorpusDoc(citekey=citekey, title="t", pdf_path=str(pdf), text_path=text_path)

    def _corpus_parsed(self, tmp_path, citekey="a2024", pages=("page one", "page two")):
        """A citekey the corpus layer has already parsed with docling.

        Pages are joined the way real Docling writes them -- the
        placeholder sits inside the blank line between two blocks, not
        flush against the text (checked against docling_core 2.89.0).
        """
        doc = self._doc(tmp_path, citekey, parsed_text="\n\n\f\n\n".join(pages))
        passages.write_sidecar(
            citekey,
            [
                {"text": "A reading-ordered paragraph.", "label": "text", "page": 1},
            ],
        )
        return doc

    def test_no_second_parse_happens(self, isolated_config, fake_docling, tmp_path):
        doc = self._corpus_parsed(tmp_path)
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 0

    def test_the_markdown_drops_the_form_feeds(self, isolated_config, fake_docling, tmp_path):
        """The corpus layer asks Docling for page breaks; this layer does
        not. Removing them, and the blank run each leaves behind, gives
        back what a plain export would have produced."""
        doc = self._corpus_parsed(tmp_path, pages=("page one", "page two"))
        out = docling_parse.parse_doc(doc)
        assert out.read_text() == "page one\n\npage two"

    def test_a_form_feed_flush_against_the_text_does_not_fuse_words(
        self, isolated_config, fake_docling, tmp_path
    ):
        """Deleting the form feed outright would run the last word of one
        page into the first word of the next, inventing a token that is
        in neither."""
        doc = self._doc(tmp_path, parsed_text="ends here\fbegins there")
        passages.write_sidecar("a2024", [{"text": "p", "label": "text", "page": 1}])
        out = docling_parse.parse_doc(doc)
        assert "herebegins" not in out.read_text()
        assert out.read_text() == "ends here\n\nbegins there"

    def test_the_passage_sidecar_is_carried_over(self, isolated_config, fake_docling, tmp_path):
        doc = self._corpus_parsed(tmp_path)
        docling_parse.parse_doc(doc)
        records = json.loads((isolated_config.DOCLING_DIR / "a2024.passages.json").read_text())
        assert [r["text"] for r in records] == ["A reading-ordered paragraph."]

    def test_the_result_is_cached_like_a_real_parse(self, isolated_config, fake_docling, tmp_path):
        doc = self._corpus_parsed(tmp_path)
        docling_parse.parse_doc(doc)
        cache = json.loads(config.DOCLING_CACHE_PATH.read_text())
        assert doc.citekey in cache["items"]

    def test_a_pdftotext_corpus_parse_is_not_reused(self, isolated_config, fake_docling, tmp_path):
        """No sidecar means the corpus text is column-spliced flat text,
        not Docling Markdown -- adopting it would quietly replace this
        stage's output with something it must never quote from."""
        doc = self._doc(tmp_path, parsed_text="page one\fpage two")
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1

    def test_a_doc_with_no_corpus_text_is_never_reused(
        self, isolated_config, fake_docling, tmp_path
    ):
        """A bib entry the corpus layer hasn't parsed -- no attachment, or
        a parse that failed -- has no artefact to adopt."""
        doc = self._doc(tmp_path, parsed_text=None)
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1

    def test_images_on_forces_a_real_parse(
        self, isolated_config, monkeypatch, fake_docling, tmp_path
    ):
        """The corpus layer writes no figure bitmaps, so adopting its
        parse would leave this stage's own output incomplete."""
        monkeypatch.setattr(config, "DOCLING_IMAGES", True)
        doc = self._corpus_parsed(tmp_path)
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1

    def test_a_pdf_newer_than_the_corpus_text_forces_a_real_parse(
        self, isolated_config, fake_docling, tmp_path
    ):
        doc = self._corpus_parsed(tmp_path)
        pdf_mtime = os.stat(doc.pdf_path).st_mtime_ns
        for path in (Path(doc.text_path), passages.sidecar_path(doc.citekey)):
            os.utime(path, ns=(pdf_mtime - 10**9, pdf_mtime - 10**9))

        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1

    def test_a_torn_sidecar_falls_back_to_a_real_parse(
        self, isolated_config, fake_docling, tmp_path
    ):
        """A sidecar truncated mid-write by a killed process can split a
        multi-byte character. Declining the reuse costs one parse; raising
        would report a hard error for a document whose PDF is fine."""
        doc = self._corpus_parsed(tmp_path)
        # Cut inside the two bytes of "é", leaving a lone continuation
        # byte -- the write is truncated, not merely invalid JSON.
        torn = '[{"text": "café'.encode("utf-8")[:-1]
        assert torn.endswith(b"\xc3")
        passages.sidecar_path(doc.citekey).write_bytes(torn)

        out = docling_parse.parse_doc(doc)

        assert FakeDocumentConverter.call_count == 1
        assert "Parsed content" in out.read_text()

    def test_an_unreadable_sidecar_leaves_no_half_written_markdown(
        self, isolated_config, fake_docling, tmp_path
    ):
        """Both reads happen before either write, so a reuse that
        declines has written nothing for the real parse to clean up."""
        doc = self._corpus_parsed(tmp_path)
        passages.sidecar_path(doc.citekey).unlink()
        Path(doc.text_path).write_text("corpus text that must not be adopted")
        # No sidecar at all is the ordinary "not a docling parse" case,
        # so force the read to fail on a sidecar that does exist.
        passages.sidecar_path(doc.citekey).mkdir()

        assert (
            _docling_reuse._reuse_corpus_parse(doc, config.DOCLING_DIR / "a2024.md", "a2024")
            is False
        )
        assert not (config.DOCLING_DIR / "a2024.md").exists()

    def test_reused_docs_never_reach_a_worker(
        self, isolated_config, monkeypatch, fake_docling, tmp_path
    ):
        """parse_corpus must not dispatch them: a worker costs a process
        and a model load to discover there was nothing to parse.

        Deliberately run with enough un-reusable documents alongside to
        put the pool on the parallel path -- with only the reusable one,
        `pending` would be empty, parse_corpus would take the serial
        branch, and this would pass even with the exclusion removed.
        """
        dispatched = []

        def fake_submit(_fn, job):
            doc, _threads = job
            dispatched.append(doc.citekey)
            future = Future()
            future.set_result((doc.citekey, "ok: parsed", {doc.citekey: [1, 2]}))
            return future

        monkeypatch.setattr(
            _docling_pool,
            "_executor_for",
            lambda workers: types.SimpleNamespace(submit=fake_submit, shutdown=lambda **kw: None),
        )
        monkeypatch.setattr(pdf_text, "resolve_workers", lambda n, docling: (4, None))

        reusable = self._corpus_parsed(tmp_path)
        others = []
        for i in range(3):
            pdf = tmp_path / f"other{i}.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            others.append(CorpusDoc(citekey=f"other{i}", title="t", pdf_path=str(pdf)))

        status = docling_parse.parse_corpus([reusable, *others])

        assert reusable.citekey not in dispatched
        assert sorted(dispatched) == ["other0", "other1", "other2"]
        assert status[reusable.citekey].startswith("ok:")


class TestPassageSidecar:
    def _doc(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        return CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

    def test_written_for_every_doc_with_page_and_bbox(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            FakeDocumentConverter,
            "texts",
            [
                FakeTextItem("Body paragraph one.", label="text", page=2),
                FakeTextItem("2 Related Work", label="section_header", page=3),
            ],
        )
        docling_parse.parse_doc(self._doc(tmp_path))

        records = json.loads((isolated_config.DOCLING_DIR / "a2024.passages.json").read_text())
        assert [r["text"] for r in records] == ["Body paragraph one.", "2 Related Work"]
        assert records[0]["page"] == 2
        assert records[0]["bbox"] == [1.0, 2.0, 3.0, 4.0]

    def test_excludes_running_heads_and_captions(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        """A journal name repeated on every page would otherwise let a
        claim 'match' seventeen times over."""
        monkeypatch.setattr(
            FakeDocumentConverter,
            "texts",
            [
                FakeTextItem("Designs 2024, 8, 8", label="page_header", page=1),
                FakeTextItem("Figure 1. A plot", label="caption", page=1),
                FakeTextItem("17", label="page_footer", page=1),
                FakeTextItem("Real prose.", label="text", page=1),
            ],
        )
        docling_parse.parse_doc(self._doc(tmp_path))

        records = json.loads((isolated_config.DOCLING_DIR / "a2024.passages.json").read_text())
        assert [r["text"] for r in records] == ["Real prose."]

    def test_written_even_with_images_off(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        assert isolated_config.DOCLING_IMAGES is False
        monkeypatch.setattr(
            FakeDocumentConverter, "texts", [FakeTextItem("Prose.", label="text", page=1)]
        )
        docling_parse.parse_doc(self._doc(tmp_path))
        assert (isolated_config.DOCLING_DIR / "a2024.passages.json").exists()

    def test_item_without_provenance_still_recorded(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            FakeDocumentConverter, "texts", [FakeTextItem("Prose.", label="text", page=None)]
        )
        docling_parse.parse_doc(self._doc(tmp_path))
        records = json.loads((isolated_config.DOCLING_DIR / "a2024.passages.json").read_text())
        assert records[0]["page"] is None
        assert "bbox" not in records[0]


class TestIncrementalSkip:
    def test_second_call_with_unchanged_pdf_skips_docling(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 v1")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        first = docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1

        second = docling_parse.parse_doc(doc)
        assert second == first
        assert FakeDocumentConverter.call_count == 1  # not called again

    def test_changed_pdf_content_triggers_reparse(self, isolated_config, fake_docling, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 v1")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1

        # A different size (and, on filesystems with coarse mtime
        # resolution, possibly the same mtime) must still be detected.
        pdf.write_bytes(b"%PDF-1.4 v1 -- now with more bytes")
        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 2

    def test_deleted_output_forces_reparse_even_if_cache_matches(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 v1")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        out_path = docling_parse.parse_doc(doc)
        out_path.unlink()

        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 2
        assert out_path.exists()

    def test_deleted_passages_sidecar_forces_reparse(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        """The .md alone isn't proof the run's outputs are intact -- a
        deleted sidecar would otherwise stay missing forever, since the
        fingerprint only says the input PDF is unchanged."""
        monkeypatch.setattr(
            FakeDocumentConverter, "texts", [FakeTextItem("Prose.", label="text", page=1)]
        )
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1
        sidecar = isolated_config.DOCLING_DIR / "a2024.passages.json"
        sidecar.unlink()

        docling_parse.parse_doc(doc)

        assert FakeDocumentConverter.call_count == 2
        assert sidecar.exists()

    def test_deleted_figures_sidecar_forces_reparse_when_images_on(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(isolated_config, "DOCLING_IMAGES", True)
        monkeypatch.setattr(FakeDocumentConverter, "pictures", [FakePicture("Figure 1", page=1)])
        monkeypatch.setattr(
            FakeDocumentConverter, "texts", [FakeTextItem("Prose.", label="text", page=1)]
        )
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1
        (isolated_config.DOCLING_DIR / "a2024.figures.json").unlink()

        docling_parse.parse_doc(doc)

        assert FakeDocumentConverter.call_count == 2

    def test_figures_sidecar_not_required_when_images_off(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        """Images off never writes figures.json, so requiring it would
        re-parse the whole corpus on every run."""
        monkeypatch.setattr(
            FakeDocumentConverter, "texts", [FakeTextItem("Prose.", label="text", page=1)]
        )
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        docling_parse.parse_doc(doc)
        docling_parse.parse_doc(doc)

        assert FakeDocumentConverter.call_count == 1

    def test_failed_parse_does_not_poison_the_cache(self, isolated_config, fake_docling, tmp_path):
        pdf = tmp_path / "explode.pdf"
        pdf.write_bytes(b"%PDF-1.4 broken")
        doc = CorpusDoc(citekey="b2024", title="t", pdf_path=str(pdf))

        with pytest.raises(RuntimeError, match="simulated docling failure"):
            docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 1

        with pytest.raises(RuntimeError, match="simulated docling failure"):
            docling_parse.parse_doc(doc)
        assert FakeDocumentConverter.call_count == 2  # retried, not skipped

    def test_parse_corpus_shares_one_cache_load_and_save_across_docs(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        pdf_a = tmp_path / "a.pdf"
        pdf_a.write_bytes(b"%PDF a")
        pdf_b = tmp_path / "b.pdf"
        pdf_b.write_bytes(b"%PDF b")
        docs = [
            CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf_a)),
            CorpusDoc(citekey="b2024", title="t", pdf_path=str(pdf_b)),
        ]

        docling_parse.parse_corpus(docs)
        assert FakeDocumentConverter.call_count == 2
        # One converter for the whole corpus, not one per document: each
        # construction re-initialises the layout/table/OCR models, 16.5s
        # of measured cold start that a 501-PDF corpus would otherwise
        # pay 501 times.
        assert FakeDocumentConverter.build_count == 1
        assert isolated_config.DOCLING_CACHE_PATH.exists()

        # A fresh parse_corpus call (simulating the next `enrich.py`
        # run) must read that persisted cache and skip both docs.
        monkeypatch.setattr(FakeDocumentConverter, "build_count", 0)
        docling_parse.parse_corpus(docs)
        assert FakeDocumentConverter.call_count == 2
        # ...and must not stand the models up at all to discover that.
        # The converter is built on first *use*, not on entry, so the
        # common case -- re-running a corpus that hasn't changed -- costs
        # no model load whatsoever.
        assert FakeDocumentConverter.build_count == 0

    def test_a_narrowed_corpus_does_not_evict_the_rest_of_the_cache(
        self, isolated_config, fake_docling, tmp_path
    ):
        """The property that makes `--for-draft` (issue #52) safe to
        offer: a scoped run and a full run do no duplicate work in
        either order.

        Stated as the regression rather than the principle, because
        there is exactly one way to break it -- rewriting the cache as
        the scoped run's own view of it, so that every document the
        narrow run didn't look at loses its fingerprint and re-parses on
        the next full one. `_save_cache` persists the merged dict today,
        so this passes as written; it is here to keep that true.
        """
        pdfs = {}
        for citekey in ("a2024", "b2024"):
            pdf = tmp_path / f"{citekey}.pdf"
            pdf.write_bytes(f"%PDF {citekey}".encode())
            pdfs[citekey] = CorpusDoc(citekey=citekey, title="t", pdf_path=str(pdf))

        docling_parse.parse_corpus(list(pdfs.values()))
        assert FakeDocumentConverter.call_count == 2

        # The scoped run: one document of the two, as `--for-draft`
        # would hand it over.
        docling_parse.parse_corpus([pdfs["a2024"]])

        cache = json.loads(isolated_config.DOCLING_CACHE_PATH.read_text())
        assert set(cache["items"]) == {"a2024", "b2024"}

        # ...and the full run that follows still parses nothing.
        docling_parse.parse_corpus(list(pdfs.values()))
        assert FakeDocumentConverter.call_count == 2


class TestCacheLoading:
    def test_missing_cache_file_is_empty(self, isolated_config):
        assert _docling_cache._load_cache() == {}

    def test_corrupt_json_is_treated_as_empty(self, isolated_config):
        isolated_config.CONTENT_DIR.mkdir(parents=True)
        isolated_config.DOCLING_CACHE_PATH.write_text("{not valid json")
        assert _docling_cache._load_cache() == {}

    def test_non_dict_top_level_is_treated_as_empty(self, isolated_config):
        isolated_config.CONTENT_DIR.mkdir(parents=True)
        isolated_config.DOCLING_CACHE_PATH.write_text("[1, 2, 3]")
        assert _docling_cache._load_cache() == {}

    def _write_cache(self, isolated_config, items, **overrides):
        payload = {
            "version": _docling_cache._CACHE_VERSION,
            "images": isolated_config.DOCLING_IMAGES,
            "ocr": isolated_config.PARSER_OCR,
            "image_scale": isolated_config.DOCLING_IMAGE_SCALE,
            "formulas": isolated_config.DOCLING_FORMULAS,
            "items": items,
        }
        payload.update(overrides)
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        isolated_config.DOCLING_CACHE_PATH.write_text(json.dumps(payload))

    def test_malformed_entries_are_dropped_not_raised(self, isolated_config):
        self._write_cache(
            isolated_config,
            {
                "good2024": [123, 456],
                "bad_not_a_list": "oops",
                "bad_wrong_length": [1, 2, 3],
                "bad_non_int": [1, "two"],
            },
        )
        assert _docling_cache._load_cache() == {"good2024": [123, 456]}

    def test_stale_schema_version_invalidates_whole_cache(self, isolated_config):
        self._write_cache(
            isolated_config,
            {"good2024": [123, 456]},
            version=_docling_cache._CACHE_VERSION + 1,
        )
        assert _docling_cache._load_cache() == {}

    def test_non_dict_items_is_treated_as_empty(self, isolated_config):
        self._write_cache(isolated_config, ["not", "a", "dict"])
        assert _docling_cache._load_cache() == {}

    def test_unversioned_legacy_cache_is_invalidated(self, isolated_config):
        """Pre-versioning caches were a bare {citekey: fingerprint} dict."""
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        isolated_config.DOCLING_CACHE_PATH.write_text(json.dumps({"good2024": [123, 456]}))
        assert _docling_cache._load_cache() == {}

    def test_toggling_images_invalidates_whole_cache(self, isolated_config, monkeypatch):
        """The trap this guards: DOCLING_IMAGES changes what every .md
        should contain, but the (size, mtime_ns) fingerprint only sees
        the PDF -- so without this the old image-less output is served
        forever."""
        self._write_cache(isolated_config, {"good2024": [123, 456]})
        assert _docling_cache._load_cache() == {"good2024": [123, 456]}

        monkeypatch.setattr(isolated_config, "DOCLING_IMAGES", not isolated_config.DOCLING_IMAGES)
        assert _docling_cache._load_cache() == {}

    def test_toggling_ocr_invalidates_whole_cache(self, isolated_config, monkeypatch):
        """Same trap as DOCLING_IMAGES above, on a second axis: OCR
        changes what every .md should contain (it is the difference
        between reading a scan and not), while the (size, mtime_ns)
        fingerprint still only sees the PDF."""
        self._write_cache(isolated_config, {"good2024": [123, 456]})
        assert _docling_cache._load_cache() == {"good2024": [123, 456]}

        monkeypatch.setattr(isolated_config, "PARSER_OCR", not isolated_config.PARSER_OCR)
        assert _docling_cache._load_cache() == {}

    def test_toggling_formulas_invalidates_whole_cache(self, isolated_config, monkeypatch):
        """Same trap as DOCLING_IMAGES, on a fourth axis (#627): formula
        enrichment changes what every .md and passage sidecar should
        contain -- decoded LaTeX against `formula-not-decoded` markers --
        while the (size, mtime_ns) fingerprint still only sees the PDF."""
        self._write_cache(isolated_config, {"good2024": [123, 456]})
        assert _docling_cache._load_cache() == {"good2024": [123, 456]}

        monkeypatch.setattr(
            isolated_config, "DOCLING_FORMULAS", not isolated_config.DOCLING_FORMULAS
        )
        assert _docling_cache._load_cache() == {}

    def test_toggling_image_scale_invalidates_whole_cache(self, isolated_config, monkeypatch):
        """#504, m-46: the worker converter key at _docling_pool.py:87
        already includes DOCLING_IMAGE_SCALE, so a scale change produces
        differently-sized bitmaps for every fingerprint-unchanged PDF --
        but the cache's own invalidation check ignored it until now,
        serving the old bitmaps forever."""
        self._write_cache(isolated_config, {"good2024": [123, 456]})
        assert _docling_cache._load_cache() == {"good2024": [123, 456]}

        monkeypatch.setattr(
            isolated_config, "DOCLING_IMAGE_SCALE", isolated_config.DOCLING_IMAGE_SCALE + 1.0
        )
        assert _docling_cache._load_cache() == {}

    def test_a_pre_m46_cache_with_no_recorded_scale_is_invalidated(self, isolated_config):
        """A cache written before this fix has no "image_scale" key at
        all -- must not compare equal to today's float by accident."""
        payload = {
            "version": _docling_cache._CACHE_VERSION,
            "images": isolated_config.DOCLING_IMAGES,
            "ocr": isolated_config.PARSER_OCR,
            "items": {"good2024": [123, 456]},
        }
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        isolated_config.DOCLING_CACHE_PATH.write_text(json.dumps(payload))
        assert _docling_cache._load_cache() == {}

    def test_save_then_load_round_trips(self, isolated_config):
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        _docling_cache._save_cache({"a2024": [1, 2]})
        assert _docling_cache._load_cache() == {"a2024": [1, 2]}

    def test_corrupt_cache_does_not_abort_the_batch(self, isolated_config, fake_docling, tmp_path):
        isolated_config.CONTENT_DIR.mkdir(parents=True)
        isolated_config.DOCLING_CACHE_PATH.write_text("{not valid json")
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        status = docling_parse.parse_corpus([doc])

        assert status["a2024"].startswith("ok:")


class TestSaveCacheFailureIsNonFatal:
    def test_save_cache_warns_and_does_not_raise(self, isolated_config, monkeypatch, capsys):
        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(_docling_cache.os, "replace", boom)

        _docling_cache._save_cache({"a2024": [1, 2]})

        assert "WARNING" in capsys.readouterr().out

    def test_parse_doc_still_returns_output_when_cache_save_fails(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(_docling_cache.os, "replace", boom)

        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(pdf))

        out_path = docling_parse.parse_doc(doc)

        assert out_path.exists()
        assert "Parsed content" in out_path.read_text()


class TestParseCorpus:
    def test_reports_per_doc_status_without_aborting_batch(
        self, isolated_config, fake_docling, tmp_path
    ):
        (tmp_path / "a.pdf").write_bytes(b"%PDF a")
        (tmp_path / "explode.pdf").write_bytes(b"%PDF explode")
        good = CorpusDoc(citekey="a2024", title="t", pdf_path=str(tmp_path / "a.pdf"))
        bad = CorpusDoc(citekey="b2024", title="t", pdf_path=str(tmp_path / "explode.pdf"))
        no_pdf = CorpusDoc(citekey="c2024", title="t", pdf_path=None)

        status = docling_parse.parse_corpus([good, bad, no_pdf])

        assert status["a2024"].startswith("ok:")
        assert status["b2024"].startswith("error:")
        assert "simulated docling failure" in status["b2024"]
        # Not an `error:` -- there was never a PDF to parse, and that
        # verdict is what pinned the stage at `partial` forever (#586,
        # TestUrlOnlyEntryIsSkippedNotAnError below).
        assert status["c2024"] == docling_parse.NO_PDF_SKIP

    def test_serial_path_reports_progress_per_document(
        self, isolated_config, fake_docling, tmp_path, capsys
    ):
        """The single-worker branch used to print nothing at all -- a run
        over a real corpus was indistinguishable from a hang for the
        length of every parse (#501, the same convention chitragupta/sync.py
        and the parallel leg both already follow)."""
        docs = [
            CorpusDoc(citekey=f"d{i}", title="t", pdf_path=str(tmp_path / f"p{i}.pdf"))
            for i in range(2)
        ]
        for doc in docs:
            Path(doc.pdf_path).write_bytes(b"%PDF")

        docling_parse.parse_corpus(docs)
        out = capsys.readouterr().out
        assert "[1/2] d0" in out
        assert "[2/2] d1" in out


def _thread_executor(workers):
    """A real ProcessPoolExecutor would run parse_one in a child
    interpreter, where this process's sys.modules fakes don't exist -- the
    fake docling would silently not be used. Swapping the executor keeps
    the concurrency real while leaving the fakes visible."""
    from concurrent.futures import ThreadPoolExecutor

    return ThreadPoolExecutor(max_workers=workers)


class TestParseCorpusParallel:
    @pytest.fixture(autouse=True)
    def _four_workers(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        monkeypatch.setattr(_docling_pool, "_executor_for", _thread_executor)

    def _docs(self, tmp_path, n=5):
        docs = []
        for i in range(n):
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * (50 * i))
            docs.append(CorpusDoc(citekey=f"d{i}", title="t", pdf_path=str(pdf)))
        return docs

    def test_every_document_is_parsed(self, isolated_config, fake_docling, tmp_path):
        status = docling_parse.parse_corpus(self._docs(tmp_path))
        assert len(status) == 5
        assert all(v.startswith("ok:") for v in status.values())
        assert FakeDocumentConverter.call_count == 5

    def test_the_parent_owns_every_cache_write(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        """Workers can't share the parent's cache dict, so they hand back
        a fingerprint and the parent records it -- the same shape as
        chitragupta/sync.py keeping every ledger write on the main process."""
        docs = self._docs(tmp_path)
        docling_parse.parse_corpus(docs)

        cache = json.loads(isolated_config.DOCLING_CACHE_PATH.read_text())
        assert set(cache["items"]) == {d.citekey for d in docs}

        # ...and a second run therefore skips all of them.
        monkeypatch.setattr(FakeDocumentConverter, "call_count", 0)
        docling_parse.parse_corpus(docs)
        assert FakeDocumentConverter.call_count == 0

    def test_a_cached_document_is_never_sent_to_a_worker(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        """Dispatching a cached doc would cost a process and a model load
        to discover there was nothing to do."""
        docs = self._docs(tmp_path)
        docling_parse.parse_corpus(docs)

        submitted = []
        real_parse_one = _docling_pool.parse_one
        monkeypatch.setattr(
            _docling_pool,
            "parse_one",
            lambda job: submitted.append(job[0].citekey) or real_parse_one(job),
        )
        status = docling_parse.parse_corpus(docs)
        assert submitted == []
        assert all(v.startswith("ok:") for v in status.values())

    def test_one_failure_does_not_abort_the_batch(self, isolated_config, fake_docling, tmp_path):
        docs = self._docs(tmp_path)
        bad = tmp_path / "explode.pdf"
        bad.write_bytes(b"%PDF")
        docs.append(CorpusDoc(citekey="bad", title="t", pdf_path=str(bad)))

        status = docling_parse.parse_corpus(docs)
        assert status["bad"].startswith("error:")
        assert all(status[f"d{i}"].startswith("ok:") for i in range(5))

        # A failed doc must not be cached, or it would never be retried.
        cache = json.loads(isolated_config.DOCLING_CACHE_PATH.read_text())
        assert "bad" not in cache["items"]

    def test_workers_get_a_thread_budget(self, isolated_config, fake_docling, tmp_path):
        docling_parse.parse_corpus(self._docs(tmp_path, n=2))
        opts = FakeDocumentConverter.last_format_options["pdf"].pipeline_options
        assert opts.accelerator_options.num_threads == pdf_text.docling_threads(4)

    def test_biggest_document_is_submitted_first(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        submitted = []
        real_parse_one = _docling_pool.parse_one
        monkeypatch.setattr(
            _docling_pool,
            "parse_one",
            lambda job: submitted.append(job[0].citekey) or real_parse_one(job),
        )
        docling_parse.parse_corpus(self._docs(tmp_path))
        assert submitted == ["d4", "d3", "d2", "d1", "d0"]

    def test_progress_follows_completion_not_submission_order(
        self, isolated_config, fake_docling, monkeypatch, tmp_path, capsys
    ):
        """executor.map() blocks on *submitted* order, so with LPT
        scheduling nothing prints until the biggest document -- submitted
        first -- finishes, even if smaller ones land sooner. That is the
        killed-at-399-of-501 convention (issue #50) verbatim (#501). d4 is
        the biggest here and is gated to finish last; the fix must still
        report the smaller ones as they land, not block behind it.

        Gated on `_save_cache` rather than on `parse_one`'s own
        invocation: that call happens on the *main* thread inside
        `_drain`'s `as_completed` loop, so by the time it has landed
        twice, those two futures are guaranteed already fully processed
        there -- gating on a flag set from inside a *worker* thread's
        callable races the main thread's bookkeeping for the same
        future and is not reliably ordered.
        """
        real_parse_one = _docling_pool.parse_one
        real_save_cache = _docling_pool._save_cache
        two_saved = threading.Event()

        def counting_save(cache):
            real_save_cache(cache)
            if len(cache) >= 2:
                two_saved.set()

        def gated(job):
            doc, _threads = job
            if doc.citekey == "d4":
                assert two_saved.wait(5), "the smaller docs' cache saves never landed"
            return real_parse_one(job)

        monkeypatch.setattr(_docling_pool, "parse_one", gated)
        monkeypatch.setattr(_docling_pool, "_save_cache", counting_save)
        docling_parse.parse_corpus(self._docs(tmp_path))
        lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("  [")]
        assert "d4" not in lines[0]
        assert "d4" in lines[-1]


class TestParseCorpusParallelBrokenPool:
    """The hazards `sync_pool` already closed, reintroduced in the
    docling leg (#501): `executor.map()` had no per-future exception
    handling and no cache save in a `finally`, so one OOM-killed worker
    lost every fingerprint from the run, completed documents included."""

    @pytest.fixture(autouse=True)
    def _pool(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        monkeypatch.setattr(_docling_pool, "_executor_for", _thread_executor)

    def _docs(self, tmp_path, n=4):
        docs = []
        for i in range(n):
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * (50 * i))
            docs.append(CorpusDoc(citekey=f"d{i}", title="t", pdf_path=str(pdf)))
        return docs

    def test_work_finished_before_the_pool_died_is_not_thrown_away(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        from concurrent.futures.process import BrokenProcessPool

        real_parse_one = _docling_pool.parse_one

        def die_on_d0(job):
            doc, _threads = job
            if doc.citekey == "d0":
                raise BrokenProcessPool("a worker died")
            return real_parse_one(job)

        monkeypatch.setattr(_docling_pool, "parse_one", die_on_d0)
        status = docling_parse.parse_corpus(self._docs(tmp_path))

        assert status["d0"].startswith("error:")
        assert all(status[f"d{i}"].startswith("ok:") for i in range(1, 4))
        cache = json.loads(isolated_config.DOCLING_CACHE_PATH.read_text())
        assert set(cache["items"]) == {"d1", "d2", "d3"}

    def test_a_pool_already_broken_at_submit_time_is_handled_too(
        self, isolated_config, fake_docling, monkeypatch, tmp_path, capsys
    ):
        """submit() itself raises once the pool is already known-broken --
        a second path to the same outcome, one `as_completed` never sees."""
        from concurrent.futures.process import BrokenProcessPool

        class DeadExecutor:
            def submit(self, *args, **kwargs):
                raise BrokenProcessPool("pool was already dead")

            def shutdown(self, *args, **kwargs):
                pass

        monkeypatch.setattr(_docling_pool, "_executor_for", lambda workers: DeadExecutor())
        status = docling_parse.parse_corpus(self._docs(tmp_path))

        assert all(status[f"d{i}"].startswith("error:") for i in range(4))
        assert "worker" in capsys.readouterr().out.lower()

    def test_a_break_mid_submission_keeps_the_futures_already_submitted(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """Building `futures` via a single list comprehension would let a
        BrokenProcessPool raised partway through the submit loop discard
        every future already handed to the executor -- real, in-flight
        work thrown away for the same reason this whole PR exists.
        Submitting biggest-first, d3 and d2 must be submitted (and
        therefore still collected) before d1's submit() blows up.

        d0 was the other half of this: it sat *behind* d1 in the submit
        loop, so the break meant it was never handed to a worker at all
        -- and it used to be reported a parse failure regardless. Since
        #584 the pool is rebuilt and d0 is parsed, which is the whole
        point of that issue; the stub therefore builds a fresh
        ThreadPoolExecutor per pool, as `_executor_for` does, rather than
        sharing one that the first shutdown would close."""
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures.process import BrokenProcessPool

        class PartiallyDeadExecutor:
            def __init__(self):
                self.real_executor = ThreadPoolExecutor(max_workers=4)

            def submit(self, fn, job):
                doc, _threads = job
                if doc.citekey == "d1":
                    raise BrokenProcessPool("died mid-submission")
                return self.real_executor.submit(fn, job)

            def shutdown(self, *args, **kwargs):
                self.real_executor.shutdown(*args, **kwargs)

        monkeypatch.setattr(_docling_pool, "_executor_for", lambda workers: PartiallyDeadExecutor())
        status = docling_parse.parse_corpus(self._docs(tmp_path))

        assert status["d3"].startswith("ok:")
        assert status["d2"].startswith("ok:")
        assert status["d1"].startswith("error:")
        assert status["d0"].startswith("ok:")


class TestABrokenPoolIsRebuiltRatherThanAbandoned:
    """#584. `_parse_with_pool` drained one executor and then wrote
    `error: parse worker died before this document was parsed` for every
    job without a result -- including the jobs still queued, and the ones
    never submitted at all because `_submit_jobs` broke out of its loop.
    One OOM-killed worker therefore cost the rest of the corpus: 460 of
    642 documents on the run that surfaced this, the great majority of
    them never given to a worker.

    #501 is what keeps those documents *recoverable* -- the cache is
    saved per landed document, so a re-run picks them up -- but it did
    not make them attempted in the run that dropped them. That is this
    class.
    """

    @pytest.fixture(autouse=True)
    def _pool(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)

    def _docs(self, tmp_path, n=6):
        """One poison document, deliberately the largest so the
        biggest-file-first schedule submits it first, plus n ordinary
        ones. That order is the whole difficulty: the document that kills
        the pool is also the one every rebuild reaches first."""
        poison = tmp_path / "poison.pdf"
        poison.write_bytes(b"%PDF" + b"x" * 10_000)
        docs = [CorpusDoc(citekey="poison", title="t", pdf_path=str(poison))]
        for i in range(n):
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * (10 * i))
            docs.append(CorpusDoc(citekey=f"d{i}", title="t", pdf_path=str(pdf)))
        return docs

    @staticmethod
    def _dying_pool(deaths, builds=None):
        """An executor factory whose pools die like a real one, rather
        than like a single failing future.

        A `BrokenProcessPool` is not one document's failure: the pool is
        gone, so every outstanding future raises it and every later
        `submit()` raises too. That is what leaves a batch unparsed, and
        a ThreadPoolExecutor cannot express it -- its other futures
        happily keep succeeding, which would make this whole class pass
        against the unfixed code.

        Jobs run synchronously inside `submit`, so the schedule is
        deterministic: no thread timing decides how much of the batch
        lands before the death. `deaths` is how many times the poison
        document kills its pool before parsing normally; pass a large
        number for a document that always does. `builds`, when given,
        collects the worker count each pool was built with.
        """
        from concurrent.futures.process import BrokenProcessPool

        real_parse_one = _docling_pool.parse_one
        died = []

        class _DyingPool:
            def __init__(self):
                self.dead = False

            def submit(self, fn, job):
                if self.dead:
                    raise BrokenProcessPool("pool was already dead")
                doc, _threads = job
                future = Future()
                if doc.citekey == "poison" and len(died) < deaths:
                    died.append(doc.citekey)
                    self.dead = True
                    future.set_exception(BrokenProcessPool("a worker died"))
                    return future
                future.set_result(real_parse_one(job))
                return future

            def shutdown(self, *args, **kwargs):
                pass

        def factory(workers):
            if builds is not None:
                builds.append(workers)
            return _DyingPool()

        return factory

    def test_documents_the_dead_pool_never_reached_are_parsed_on_a_rebuild(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """The defect itself: the pool dies on the first document, and
        under a single drain every other document in the batch was
        reported a failure without ever having been opened."""
        monkeypatch.setattr(_docling_pool, "_executor_for", self._dying_pool(deaths=1))

        status = docling_parse.parse_corpus(self._docs(tmp_path))

        assert all(status[f"d{i}"].startswith("ok:") for i in range(6))
        assert status["poison"].startswith("ok:")

    def test_a_document_that_kills_every_pool_still_costs_only_itself(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """Which document killed the worker is not knowable from a
        `BrokenProcessPool`, so a poison one reaches every rebuilt pool
        and dies again -- *first* every time, under the biggest-first
        schedule, which is why a rebuild alone rescues nothing and the
        retry has to reverse the order it hands over. The batch must
        survive it, and the run must still end."""
        monkeypatch.setattr(_docling_pool, "_executor_for", self._dying_pool(deaths=99))

        status = docling_parse.parse_corpus(self._docs(tmp_path))

        assert all(status[f"d{i}"].startswith("ok:") for i in range(6))
        assert status["poison"] == "error: parse worker died before this document was parsed"

    def test_the_rebuilds_are_bounded_and_narrow_the_pool_each_time(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """A `while` here never terminates on a poison PDF, so the count
        is bounded. Each rebuild also halves the width: memory pressure
        is the realistic cause of a worker death, and retrying at the
        same width reproduces it -- the same fix the module's own warning
        already asks a human to make by hand.

        The last width is 1, where there is nothing left to halve. That
        is not a gap: at one worker the recovery is the fresh process and
        the reversed order, and `parse_corpus` only takes this path when
        the resolved count is above 1, so 1 is reachable only as the
        floor of the halving."""
        builds = []
        monkeypatch.setattr(
            _docling_pool, "_executor_for", self._dying_pool(deaths=99, builds=builds)
        )

        docling_parse.parse_corpus(self._docs(tmp_path))

        assert len(builds) == _docling_pool._MAX_POOL_REBUILDS + 1
        assert builds == [4, 2, 1]

    def test_a_rebuild_that_lands_nothing_is_not_tried_again(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """The case the bound alone does not cover: a pool that lands
        nothing at all will land nothing next time either, so the second
        such round ends the run rather than spending a third pool build
        -- and its model loads per worker -- to learn the same thing.

        Deliberately not checked on the *first* round, which can
        legitimately land nothing: the biggest document is submitted
        first, so a pool that dies on it lands nothing at all, and that
        is exactly the run this whole class exists to rescue."""
        from concurrent.futures.process import BrokenProcessPool

        builds = []

        class DeadPool:
            def submit(self, *args, **kwargs):
                raise BrokenProcessPool("pool was already dead")

            def shutdown(self, *args, **kwargs):
                pass

        def factory(workers):
            builds.append(workers)
            return DeadPool()

        monkeypatch.setattr(_docling_pool, "_executor_for", factory)
        status = docling_parse.parse_corpus(self._docs(tmp_path))

        assert builds == [4, 2]
        assert all(v.startswith("error:") for v in status.values())

    def test_a_healthy_run_builds_exactly_one_pool(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """The loop must not cost a second executor when nothing broke --
        each pool build reloads docling's models in every worker."""
        builds = []
        monkeypatch.setattr(
            _docling_pool, "_executor_for", self._dying_pool(deaths=0, builds=builds)
        )

        status = docling_parse.parse_corpus(self._docs(tmp_path))

        assert builds == [4]
        assert all(v.startswith("ok:") for v in status.values())

    def test_the_stage_errors_when_a_document_was_abandoned_so_cron_hears_about_it(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """The other half of #584, from the issue's own measurement: the
        run exited 0. `_summarise` returns nonzero only for a stage whose
        status is `error`, and a dead pool's failures folded into
        `partial` -- so an unattended run that abandoned 460 of 642
        documents reported itself to cron exactly as a clean run does.

        A pool that kept dying is the one case the rebuilds above cannot
        rescue, which is precisely when the caller needs to be told."""
        from chitragupta.enrich import stages

        monkeypatch.setattr(_docling_pool, "_executor_for", self._dying_pool(deaths=99))

        result = stages.stage_docling(self._docs(tmp_path), None)

        assert result["status"] == "error"
        assert result["detail"]["poison"] == docling_parse.POOL_DEATH_ERROR

    def test_an_ordinary_parse_failure_is_still_only_partial(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """The escalation must be to abandoned work, not to any failure.
        A PDF the backend read and could not parse is a deterministic,
        per-document result: reported, batch continues, stage `partial`,
        exit 0. Widening that to `error` would fail a nightly run over
        one bad file."""
        from chitragupta.enrich import stages

        monkeypatch.setattr(_docling_pool, "_executor_for", _thread_executor)
        (tmp_path / "explode.pdf").write_bytes(b"%PDF explode")
        docs = self._docs(tmp_path)
        docs.append(CorpusDoc(citekey="bad", title="t", pdf_path=str(tmp_path / "explode.pdf")))

        result = stages.stage_docling(docs, None)

        assert result["status"] == "partial"
        assert result["detail"]["bad"].startswith("error:")

    def test_with_the_bound_at_zero_the_behaviour_is_the_old_one(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """_MAX_POOL_REBUILDS is the only knob, and at 0 it turns the
        loop back into the single drain this issue is about: one pool,
        and everything it did not reach reported failed. Worth pinning
        because it is also the path where the loop ends by running out of
        attempts rather than by deciding to stop."""
        builds = []
        monkeypatch.setattr(_docling_pool, "_MAX_POOL_REBUILDS", 0)
        monkeypatch.setattr(
            _docling_pool, "_executor_for", self._dying_pool(deaths=99, builds=builds)
        )

        status = docling_parse.parse_corpus(self._docs(tmp_path))

        assert builds == [4]
        assert all(v == docling_parse.POOL_DEATH_ERROR for v in status.values())


class TestParseOneFingerprint:
    def test_fingerprint_is_captured_before_conversion_not_after(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """A PDF replaced while the parse is running must be recorded
        against the fingerprint it had when the parse *started*, matching
        the serial path's stat-before-parse order -- not the one it ends
        with, which would be served forever against text read from the
        old bytes (#501)."""
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = CorpusDoc(citekey="p2024", title="t", pdf_path=str(pdf))
        pre_stat = os.stat(pdf)
        pre_fingerprint = [pre_stat.st_size, pre_stat.st_mtime_ns]

        real_convert = FakeDocumentConverter.convert

        def convert_then_replace(self, pdf_path):
            result = real_convert(self, pdf_path)
            pdf.write_bytes(b"%PDF-1.4" + b"x" * 500)
            return result

        monkeypatch.setattr(FakeDocumentConverter, "convert", convert_then_replace)
        _citekey, status, cache = _docling_pool.parse_one((doc, None))
        assert status.startswith("ok:")
        assert cache[doc.citekey] == pre_fingerprint


class TestParallelHelpers:
    def test_is_cached_is_false_for_an_unreadable_pdf(self, isolated_config, tmp_path):
        """A PDF that vanished can't be fingerprinted. Treat it as
        not-cached so the parse runs and reports the real error, rather
        than crashing the dispatch loop."""
        doc = CorpusDoc(citekey="gone", title="t", pdf_path=str(tmp_path / "gone.pdf"))
        assert docling_parse._is_cached(doc, {"gone": [1, 2]}) is False

    def test_pdf_size_of_a_missing_file_sorts_last(self, tmp_path):
        assert _docling_pool._pdf_size(str(tmp_path / "gone.pdf")) == 0

    def test_pdf_size_of_none_sorts_last(self):
        """corpus docs without a PDF never reach the pool, but the sort
        key must not raise if one does."""
        assert _docling_pool._pdf_size(None) == 0

    def test_executor_claims_a_gpu_per_worker(self, monkeypatch):
        """Asserted through a recording stub rather than the executor's
        private _initializer/_initargs/_mp_context, which are CPython
        implementation details that could be renamed."""
        captured = {}

        def record(**kwargs):
            captured.update(kwargs)
            return contextlib.nullcontext()

        monkeypatch.setattr(pdf_text._pool, "usable_devices", lambda docling: ([0, 1, 2, 3], None))
        monkeypatch.setattr(pdf_text._pool, "ProcessPoolExecutor", record)
        with _docling_pool._executor_for(2):
            pass

        assert captured["max_workers"] == 2
        assert captured["initializer"] is pdf_text.init_worker
        assert captured["initargs"][2] == [0, 1, 2, 3]
        # Whichever start method pdf_text picked -- asserted against that
        # rather than a literal, so this stays one source of truth with
        # chitragupta/sync.py's pool rather than two that can drift apart.
        assert captured["mp_context"].get_start_method() == pdf_text.start_method()[0]

    def test_a_full_card_is_kept_out_of_this_pool_too(self, monkeypatch):
        """Two pool builders, one contract. This one skipped the check
        until PR #40 review caught it."""
        captured = {}
        monkeypatch.setattr(pdf_text._pool, "usable_devices", lambda docling: ([1, 2], "  WARNING"))
        monkeypatch.setattr(
            pdf_text._pool,
            "ProcessPoolExecutor",
            lambda **kwargs: captured.update(kwargs) or contextlib.nullcontext(),
        )
        with _docling_pool._executor_for(2):
            pass

        assert captured["initargs"][2] == [1, 2]

    def test_the_initargs_actually_work_as_init_worker_arguments(self, monkeypatch):
        """The regression this pool actually had: it passed
        pdf_text.gpu_count() -- an int -- where init_worker wants a list
        of cards, so every worker would have died with "'int' object is
        not iterable" at startup. Invisible to a test that only compares
        initargs to a literal, because the initializer is never run."""
        captured = {}
        monkeypatch.setattr(pdf_text._pool, "usable_devices", lambda docling: ([2, 3], None))
        monkeypatch.setattr(
            pdf_text._pool,
            "ProcessPoolExecutor",
            lambda **kwargs: captured.update(kwargs) or contextlib.nullcontext(),
        )
        with _docling_pool._executor_for(2):
            pass

        pdf_text._reset_worker_device()
        try:
            pdf_text.init_worker(*captured["initargs"])
            assert pdf_text.worker_device() == "cuda:2"
        finally:
            pdf_text._reset_worker_device()

    def test_a_skipped_card_is_reported_not_swallowed(self, monkeypatch, capsys):
        monkeypatch.setattr(
            pdf_text._pool, "usable_devices", lambda docling: ([1], "  WARNING skipping cuda:0")
        )
        monkeypatch.setattr(
            pdf_text._pool, "ProcessPoolExecutor", lambda **kwargs: contextlib.nullcontext()
        )
        with _docling_pool._executor_for(2):
            pass

        assert "WARNING skipping cuda:0" in capsys.readouterr().out

    def test_a_start_method_complaint_is_printed_not_swallowed(self, monkeypatch, capsys):
        """A pool that quietly falls back to spawn looks identical to one
        that got what was configured, and is ~1.5s slower to start."""
        monkeypatch.setattr(pdf_text._pool, "usable_devices", lambda docling: ([], None))
        monkeypatch.setattr(
            pdf_text._pool,
            "process_pool_context",
            lambda: (multiprocessing.get_context("spawn"), "  NOTE fell back"),
        )
        monkeypatch.setattr(
            pdf_text._pool, "ProcessPoolExecutor", lambda **kwargs: contextlib.nullcontext()
        )
        with _docling_pool._executor_for(2):
            pass

        assert "NOTE fell back" in capsys.readouterr().out

    def test_accelerator_options_are_left_alone_without_a_budget(
        self, isolated_config, fake_docling, tmp_path
    ):
        """A single-worker run must reach Docling with its own defaults."""
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        docling_parse.parse_doc(CorpusDoc(citekey="a", title="t", pdf_path=str(pdf)))
        opts = FakeDocumentConverter.last_format_options["pdf"].pipeline_options
        assert opts.accelerator_options is None

    def test_worker_device_reaches_the_pipeline(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(pdf_text._worker, "_WORKER_DEVICE", "cuda:3")
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        docling_parse.parse_doc(CorpusDoc(citekey="a", title="t", pdf_path=str(pdf)))
        opts = FakeDocumentConverter.last_format_options["pdf"].pipeline_options
        assert opts.accelerator_options.device == "cuda:3"


class TestParseCorpusParallelEdges:
    @pytest.fixture(autouse=True)
    def _pool(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(_docling_pool, "_executor_for", _thread_executor)

    def test_already_cached_docs_are_still_reported_in_a_parallel_run(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """A mixed run -- some cached, some not -- must report every
        document, not just the ones that went through the pool."""
        monkeypatch.setattr(config, "PARSER_WORKERS", 1)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        docs = []
        for i in range(5):
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * i)
            docs.append(CorpusDoc(citekey=f"d{i}", title="t", pdf_path=str(pdf)))
        docling_parse.parse_corpus(docs[:2])  # warm the cache for d0, d1

        # Three still to parse, so the resolved worker count stays above
        # 1 and the parallel branch is genuinely exercised -- with two
        # cached documents alongside it.
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(FakeDocumentConverter, "call_count", 0)
        status = docling_parse.parse_corpus(docs)

        assert set(status) == {f"d{i}" for i in range(5)}
        assert all(v.startswith("ok:") for v in status.values())
        assert FakeDocumentConverter.call_count == 3  # only d2, d3, d4 re-parsed

    def test_an_oversized_worker_request_is_reported(
        self, isolated_config, fake_docling, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.setattr(config, "PARSER_WORKERS", 64)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 8)
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        docling_parse.parse_corpus(
            [
                CorpusDoc(citekey="a", title="t", pdf_path=str(pdf)),
                CorpusDoc(citekey="b", title="t", pdf_path=str(pdf)),
            ]
        )
        assert "[parser].workers=64" in capsys.readouterr().out

    def test_a_doc_with_no_pdf_is_reported_not_raised_in_a_parallel_run(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """A doc with no PDF never reaches the pool -- it has nothing to
        parse -- so it falls into the same branch as the cached ones and
        must be reported there rather than taking down the batch."""
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        docs = [CorpusDoc(citekey="nopdf", title="t", pdf_path=None)]
        for i in range(3):
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * i)
            docs.append(CorpusDoc(citekey=f"d{i}", title="t", pdf_path=str(pdf)))

        status = docling_parse.parse_corpus(docs)
        assert status["nopdf"] == docling_parse.NO_PDF_SKIP
        assert "no PDF to parse" in status["nopdf"]
        assert all(status[f"d{i}"].startswith("ok:") for i in range(3))


class TestWorkerConverterReuse:
    """A pool worker handles many documents over its life, and
    DocumentConverter keeps its initialized_pipelines cache on the
    *instance* -- so a converter per document reloads every model per
    document, which is exactly the cost the serial path stopped paying in
    v0.12.0. This is the parallel path's version of that guarantee."""

    @pytest.fixture(autouse=True)
    def _reset(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        _docling_pool._reset_worker_converter()
        yield
        _docling_pool._reset_worker_converter()

    def _doc(self, tmp_path, name):
        pdf = tmp_path / f"{name}.pdf"
        pdf.write_bytes(b"%PDF")
        return CorpusDoc(citekey=name, title="t", pdf_path=str(pdf))

    def test_one_converter_serves_every_document_a_worker_handles(
        self, isolated_config, fake_docling, tmp_path
    ):
        for i in range(5):
            _docling_pool.parse_one((self._doc(tmp_path, f"d{i}"), 4))
        assert FakeDocumentConverter.build_count == 1
        assert FakeDocumentConverter.call_count == 5

    def test_a_changed_thread_budget_rebuilds_it(self, isolated_config, fake_docling, tmp_path):
        _docling_pool.parse_one((self._doc(tmp_path, "a"), 4))
        _docling_pool.parse_one((self._doc(tmp_path, "b"), 2))
        assert FakeDocumentConverter.build_count == 2

    def test_a_changed_device_rebuilds_it(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """Caching on "was one built already" alone would leave a worker
        using a converter pinned to another worker's GPU."""
        monkeypatch.setattr(pdf_text._worker, "_WORKER_DEVICE", "cuda:0")
        _docling_pool.parse_one((self._doc(tmp_path, "a"), 4))
        monkeypatch.setattr(pdf_text._worker, "_WORKER_DEVICE", "cuda:1")
        _docling_pool.parse_one((self._doc(tmp_path, "b"), 4))
        assert FakeDocumentConverter.build_count == 2

    def test_a_changed_image_setting_no_longer_rebuilds_it(
        self, isolated_config, fake_docling, monkeypatch, tmp_path, fake_pdfium
    ):
        """The inverse of what this asserted before #600, and for a
        reason rather than as a concession.

        The image settings used to change what `_build_converter` built,
        so they belonged in the reuse key. They no longer reach it at all
        -- the converter never generates bitmaps, and the scale is
        applied per crop by `_docling_crops`, long after the converter
        has finished. Keeping them in the key would pay a full reload of
        docling's layout, table and OCR models per worker for a setting
        the converter cannot see.
        """
        _docling_pool.parse_one((self._doc(tmp_path, "a"), 4))
        monkeypatch.setattr(isolated_config, "DOCLING_IMAGES", True)
        _docling_pool.parse_one((self._doc(tmp_path, "b"), 4))
        assert FakeDocumentConverter.build_count == 1

    def test_a_changed_ocr_setting_still_rebuilds_it(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """The control for the test above: a setting that *does* reach the
        converter must still invalidate the key, or that test would pass
        just as well against a key that had stopped working."""
        _docling_pool.parse_one((self._doc(tmp_path, "a"), 4))
        monkeypatch.setattr(isolated_config, "PARSER_OCR", True)
        _docling_pool.parse_one((self._doc(tmp_path, "b"), 4))
        assert FakeDocumentConverter.build_count == 2


class TestParseCorpusInterrupt:
    """Same fix as chitragupta/sync.py's: `with executor` waits for every queued
    job, so Ctrl+C over a real corpus drained the whole backlog first."""

    @pytest.fixture(autouse=True)
    def _pool(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        monkeypatch.setattr(_docling_pool, "_executor_for", _thread_executor)

    def _docs(self, tmp_path, n=6):
        docs = []
        for i in range(n):
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * (50 * i))
            docs.append(CorpusDoc(citekey=f"d{i}", title="t", pdf_path=str(pdf)))
        return docs

    def test_interrupt_keeps_finished_work_and_says_so(
        self, isolated_config, fake_docling, monkeypatch, tmp_path, capsys
    ):
        """Now that results land in *completion* order (as_completed), not
        submission order (map), the interrupt has to be gated on a real
        completion count rather than on invocation count -- otherwise
        which job "wins" the race to raise first is a coin flip. d0 is
        the smallest file, so LPT scheduling submits it last; it blocks
        until two other jobs' fingerprints have actually been persisted,
        then blows up the pool deterministically.

        Gated on `_save_cache`, not on `parse_one`'s own invocation: that
        call happens on the *main* thread inside `_drain`'s
        `as_completed` loop, so two landed saves guarantee those two
        futures are already fully processed there. A flag set from
        inside a *worker* thread's callable instead races the main
        thread's own bookkeeping for that same future.
        """
        real = _docling_pool.parse_one
        real_save_cache = _docling_pool._save_cache
        two_saved = threading.Event()

        def counting_save(cache):
            real_save_cache(cache)
            if len(cache) >= 2:
                two_saved.set()

        def interrupt_after_two(job):
            doc, _threads = job
            if doc.citekey == "d0":
                assert two_saved.wait(5), "the other jobs' cache saves never landed"
                raise KeyboardInterrupt
            return real(job)

        monkeypatch.setattr(_docling_pool, "parse_one", interrupt_after_two)
        monkeypatch.setattr(_docling_pool, "_save_cache", counting_save)
        docs = self._docs(tmp_path)
        with pytest.raises(KeyboardInterrupt):
            docling_parse.parse_corpus(docs)

        out = capsys.readouterr().out
        assert "interrupted after" in out
        # The cache is persisted on the way out, so the documents that did
        # finish are not re-parsed on the next run.
        cache = json.loads(isolated_config.DOCLING_CACHE_PATH.read_text())
        assert len(cache["items"]) >= 2

    def test_progress_is_reported_as_documents_land(
        self, isolated_config, fake_docling, tmp_path, capsys
    ):
        docling_parse.parse_corpus(self._docs(tmp_path))
        out = capsys.readouterr().out
        assert "[1/6]" in out
        assert "[6/6]" in out


class TestEnrichPartialSuccess:
    """The enrichment stage had the same silent-truncation hole chitragupta/pdf_text.py
    closed in v1.2.0: convert(raises_on_error=True) raises only on
    FAILURE, so a PARTIAL_SUCCESS returned a document that stops early
    and parse_doc wrote it to content/docling/<doc>.md as if complete.

    That output feeds embeddings, topic modelling and citation
    provenance, so a truncated .md is a source a claim can be checked
    against and silently pass.
    """

    def _doc(self, tmp_path):
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        return CorpusDoc(citekey="a", title="t", pdf_path=str(pdf))

    def test_partial_success_is_rejected(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(
            FakeDocumentConverter,
            "convert",
            lambda self, p: _PartialResult("PARTIAL_SUCCESS", ["timeout after 10s"]),
        )
        doc = self._doc(tmp_path)
        with pytest.raises(RuntimeError, match="PARTIAL_SUCCESS"):
            docling_parse.parse_doc(doc)

    def test_no_markdown_is_written_for_a_partial_parse(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(
            FakeDocumentConverter,
            "convert",
            lambda self, p: _PartialResult("PARTIAL_SUCCESS", []),
        )
        doc = self._doc(tmp_path)
        with pytest.raises(RuntimeError):
            docling_parse.parse_doc(doc)
        assert not (isolated_config.DOCLING_DIR / "a.md").exists()

    def test_a_partial_parse_is_reported_and_not_cached_by_parse_corpus(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """It must come back for retry on the next run, not be recorded
        as done."""
        monkeypatch.setattr(
            FakeDocumentConverter,
            "convert",
            lambda self, p: _PartialResult("PARTIAL_SUCCESS", ["bad page 3"]),
        )
        status = docling_parse.parse_corpus([self._doc(tmp_path)])
        assert status["a"].startswith("error:")
        cache = json.loads(isolated_config.DOCLING_CACHE_PATH.read_text())
        assert "a" not in cache["items"]

    def test_success_still_parses(self, isolated_config, fake_docling, tmp_path):
        out = docling_parse.parse_doc(self._doc(tmp_path))
        assert out.exists()


class _PartialResult:
    def __init__(self, status_name, messages):
        self.status = types.SimpleNamespace(name=status_name)
        self.errors = [types.SimpleNamespace(error_message=m) for m in messages]
        self.document = FakeDocument("# partial")


class TestDoclingNotInstalledIsSkippedNotPartial:
    """m-40 (#509). `_build_converter` imports docling lazily, so on a
    host without the enrich extra every document failed with its own
    `error: No module named 'docling'` and the stage reported `partial` --
    which says "some documents did not parse", when what happened is that
    the stage could not run at all and nobody has been told to install
    anything."""

    def test_every_document_gets_one_shared_skipped_reason(
        self, isolated_config, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            docling_parse.importlib.util,
            "find_spec",
            lambda name: None if name == "docling" else object(),
        )
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        docs = [
            CorpusDoc(citekey="a2024", title="A", pdf_path=str(pdf)),
            CorpusDoc(citekey="b2024", title="B", pdf_path=str(pdf)),
        ]
        status = docling_parse.parse_corpus(docs)
        assert set(status) == {"a2024", "b2024"}
        assert len(set(status.values())) == 1
        reason = status["a2024"]
        assert reason.startswith("skipped:")
        assert "pip install 'chitragupta-cli[enrich]'" in reason

    def test_the_stage_reports_skipped_and_surfaces_the_install_step(
        self, isolated_config, tmp_path, monkeypatch
    ):
        from chitragupta.enrich import stages

        monkeypatch.setattr(
            docling_parse.importlib.util,
            "find_spec",
            lambda name: None if name == "docling" else object(),
        )
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        result = stages.stage_docling(
            [CorpusDoc(citekey="a2024", title="A", pdf_path=str(pdf))], None
        )
        assert result["status"] == "skipped"
        assert "pip install 'chitragupta-cli[enrich]'" in result["detail"]


class TestUrlOnlyEntryIsSkippedNotAnError:
    """#586. A bibliography entry with no PDF at all -- a standards page,
    a software link, a website -- was reported `error: <citekey>: no PDF
    to parse`, and `stages.stage_docling` reads any `error` prefix as
    `partial`. On the 642-document corpus that surfaced this, 145 entries
    are URL-only, so the stage could never report `ok` again whatever the
    corpus did -- and 460 documents that failed for a real reason (a dead
    parse worker) sat in the same bucket, indistinguishable.

    The same correction #509 made for a missing docling install, one
    level down: a document the stage correctly did not parse is
    `skipped`, not a failure.
    """

    @staticmethod
    def _docs(tmp_path, n_pdfs):
        docs = [CorpusDoc(citekey="urlonly", title="A standards page", pdf_path=None)]
        for i in range(n_pdfs):
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * i)
            docs.append(CorpusDoc(citekey=f"d{i}", title="t", pdf_path=str(pdf)))
        return docs

    def test_the_serial_path_reports_a_skip(self, isolated_config, fake_docling, tmp_path):
        status = docling_parse.parse_corpus(self._docs(tmp_path, 1))

        assert status["urlonly"].startswith("skipped:")
        assert status["d0"].startswith("ok:")

    def test_the_pool_path_reports_a_skip(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        """The two paths report failures at two different call sites --
        the serial loop in parse_corpus and _adopt_cached in the pool leg
        -- so a fix at one of them leaves the other reporting an error."""
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        # Threads rather than processes, as TestParseCorpusParallelEdges
        # does: the fake docling lives in this process's sys.modules and
        # a spawned worker would import the real one.
        monkeypatch.setattr(_docling_pool, "_executor_for", _thread_executor)

        status = docling_parse.parse_corpus(self._docs(tmp_path, 3))

        assert status["urlonly"].startswith("skipped:")
        assert all(status[f"d{i}"].startswith("ok:") for i in range(3))

    def test_the_stage_reports_ok_when_the_only_unparsed_entry_has_no_pdf(
        self, isolated_config, fake_docling, tmp_path
    ):
        """The symptom the issue is about: `partial` on a run where
        nothing went wrong."""
        from chitragupta.enrich import stages

        result = stages.stage_docling(self._docs(tmp_path, 1), None)

        assert result["status"] == "ok"
        assert result["detail"]["urlonly"].startswith("skipped:")

    def test_a_real_parse_failure_is_still_partial(self, isolated_config, fake_docling, tmp_path):
        """The skip must not swallow the case it was hiding. A PDF that
        is declared and fails to parse stays an error, and one alongside
        a URL-only entry still reports the stage `partial`."""
        from chitragupta.enrich import stages

        (tmp_path / "explode.pdf").write_bytes(b"%PDF explode")
        docs = self._docs(tmp_path, 1)
        docs.append(CorpusDoc(citekey="bad", title="t", pdf_path=str(tmp_path / "explode.pdf")))

        result = stages.stage_docling(docs, None)

        assert result["status"] == "partial"
        assert result["detail"]["bad"].startswith("error:")
        assert result["detail"]["urlonly"].startswith("skipped:")
