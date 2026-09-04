"""Figure crops rendered one at a time, instead of held to the end (#600).

pypdfium2 is faked through `sys.modules` for the same reason docling is
in `test_enrich_docling_parse.py`: it is imported lazily inside the
function that uses it, so the enrich extra stays optional. The fake
records every call, because *when things are released* is the whole
point of this module -- a version that rendered all the crops correctly
and freed none of them would pass a naive output-only test while
reproducing the bug it exists to fix.

`test_enrich_real_libraries.py` checks the same surface against the
pypdfium2 CI actually installs, so fake and library cannot drift apart
silently.
"""

import types

import conftest
import pytest

from chitragupta.enrich import _docling_crops


class FakeBBox:
    """A docling BoundingBox, including the `to_bottom_left_origin`
    conversion `crop_insets` delegates to.

    The conversion mirrors docling's own -- `t` and `b` are reflected
    about the page height and the origin flips -- verified against the
    real `BoundingBox` in test_enrich_real_libraries.py, so this double
    cannot quietly disagree with the library.
    """

    def __init__(self, left, top, right, bottom, origin="BOTTOMLEFT"):
        self.l = left
        self.t = top
        self.r = right
        self.b = bottom
        self.coord_origin = f"CoordOrigin.{origin}"

    def to_bottom_left_origin(self, page_height):
        if self.coord_origin.endswith("BOTTOMLEFT"):
            return self
        return FakeBBox(self.l, page_height - self.t, self.r, page_height - self.b)


def bbox(left, top, right, bottom, origin="BOTTOMLEFT"):
    return FakeBBox(left, top, right, bottom, origin=origin)


class FakePicture:
    def __init__(self, page=1, box=None):
        self.prov = [types.SimpleNamespace(page_no=page, bbox=box or bbox(10, 90, 60, 40))]

    @staticmethod
    def without_provenance():
        pic = FakePicture()
        pic.prov = []
        return pic


class TestCropInsets:
    """docling reports a bbox; pdfium wants insets from each page edge.

    Getting this wrong yields a crop that is plausibly sized and shows
    the wrong part of the page -- a failure invisible in any count or
    byte-size assertion, which is why both origins are pinned by
    arithmetic rather than by round-tripping.
    """

    def test_bottomleft_origin(self):
        # l=10 t=90 r=60 b=40 on a 100x100 page: the box is 10 from the
        # left, 40 up from the bottom, 40 from the right, 10 down from
        # the top.
        assert _docling_crops.crop_insets(bbox(10, 90, 60, 40), 100.0, 100.0) == (
            10.0,
            40.0,
            40.0,
            10.0,
        )

    def test_topleft_origin(self):
        """The same *region*, described from the top instead.

        t=10 is 10 below the top and b=40 is 40 below the top, so this is
        a box near the top of the page -- and the insets must come out as
        10 from the top and 60 from the bottom. Read as BOTTOMLEFT by
        mistake it would crop 10 from the *bottom*: same size, wrong
        third of the page.
        """
        assert _docling_crops.crop_insets(bbox(10, 10, 60, 40, origin="TOPLEFT"), 100.0, 100.0) == (
            10.0,
            60.0,
            40.0,
            10.0,
        )

    def test_bbox_without_the_conversion_is_treated_as_bottomleft(self):
        """docling's own default, and what every real bbox in this corpus
        carries -- checked because the delegation is behind a hasattr."""
        plain = types.SimpleNamespace(l=10, t=90, r=60, b=40)
        assert _docling_crops.crop_insets(plain, 100.0, 100.0) == (10.0, 40.0, 40.0, 10.0)


class TestWritePictureCrops:
    def test_writes_one_png_per_picture(self, fake_pdfium, tmp_path):
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1), FakePicture(page=2)])
        art = tmp_path / "a2024_artifacts"

        names = _docling_crops.write_picture_crops("p.pdf", dl_doc, art, 2.0)

        assert names == [
            "a2024_artifacts/picture_000000.png",
            "a2024_artifacts/picture_000001.png",
        ]
        assert sorted(p.name for p in art.iterdir()) == [
            "picture_000000.png",
            "picture_000001.png",
        ]

    def test_releases_each_crop_before_rendering_the_next(self, fake_pdfium, tmp_path):
        """The bug this module fixes, asserted directly.

        Both crops must be closed, and the first must be closed *before*
        the second is rendered -- holding two at once is the beginning of
        holding all 280.
        """
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1), FakePicture(page=1)])

        _docling_crops.write_picture_crops("p.pdf", dl_doc, tmp_path / "art", 2.0)

        renders = [i for i, line in enumerate(fake_pdfium) if line.startswith("render")]
        closes = [i for i, line in enumerate(fake_pdfium) if line == "bitmap.close"]
        assert len(renders) == len(closes) == 2
        assert closes[0] < renders[1], f"crop held across a render: {fake_pdfium}"

    def test_closes_every_page_it_opens(self, fake_pdfium, tmp_path):
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1), FakePicture(page=3)])

        _docling_crops.write_picture_crops("p.pdf", dl_doc, tmp_path / "art", 2.0)

        assert fake_pdfium.count("page.open page=0") == 1
        assert fake_pdfium.count("page.close page=0") == 1
        assert fake_pdfium.count("page.open page=2") == 1
        assert fake_pdfium.count("page.close page=2") == 1
        assert "pdf.close" in fake_pdfium

    def test_opens_a_shared_page_once(self, fake_pdfium, tmp_path):
        """Three pictures on one page is one page open, not three.

        A slide deck routinely has tens of pictures per page, and
        reopening the page per picture is the cost this grouping avoids.
        """
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=4) for _ in range(3)])

        _docling_crops.write_picture_crops("p.pdf", dl_doc, tmp_path / "art", 2.0)

        assert fake_pdfium.count("page.open page=3") == 1
        assert len([line for line in fake_pdfium if line.startswith("render")]) == 3

    def test_picture_without_provenance_gets_no_name(self, fake_pdfium, tmp_path):
        """No bbox, no crop -- and the *positions* must still line up.

        `_figure_records` pairs these names against `dl_doc.pictures` by
        index, so a skipped picture has to leave a hole rather than
        shorten the list, or every later figure points at its
        neighbour's image.
        """
        dl_doc = types.SimpleNamespace(
            pictures=[FakePicture(page=1), FakePicture.without_provenance(), FakePicture(page=2)]
        )
        art = tmp_path / "art"

        names = _docling_crops.write_picture_crops("p.pdf", dl_doc, art, 2.0)

        assert names == ["art/picture_000000.png", None, "art/picture_000002.png"]
        assert sorted(p.name for p in art.iterdir()) == [
            "picture_000000.png",
            "picture_000002.png",
        ]

    def test_scale_reaches_the_renderer(self, fake_pdfium, tmp_path):
        """docling_image_scale is the setting that made this expensive; it
        must reach pdfium rather than silently defaulting to 1.0."""
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1)])

        _docling_crops.write_picture_crops("p.pdf", dl_doc, tmp_path / "art", 6.0)

        assert any("scale=6.0" in line for line in fake_pdfium)

    def test_no_pictures_writes_nothing_and_opens_no_pdf(self, fake_pdfium, tmp_path):
        """A text-only document must not pay for a PDF handle it never reads."""
        art = tmp_path / "art"

        names = _docling_crops.write_picture_crops(
            "p.pdf", types.SimpleNamespace(pictures=[]), art, 2.0
        )

        assert names == []
        assert fake_pdfium == []
        assert not art.exists()

    def test_a_failed_crop_does_not_lose_the_other_figures(
        self, fake_pdfium, tmp_path, caplog, monkeypatch
    ):
        """One unrenderable picture costs that picture, not the parse.

        The document's text and every other figure are already correct by
        this point; raising here would discard them and mark a document
        that parsed fine as failed.
        """
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1), FakePicture(page=2)])
        real_getitem = conftest.FakePdfiumDocument.__getitem__

        def explode(self, index):
            if index == 0:
                # The verbatim failure docling_core raised at
                # docling_image_scale = 6.0, after 74 GiB and 17 minutes.
                raise ValueError("Decoded image exceeds size limit of 20971520 bytes.")
            return real_getitem(self, index)

        monkeypatch.setattr(conftest.FakePdfiumDocument, "__getitem__", explode)
        names = _docling_crops.write_picture_crops("p.pdf", dl_doc, tmp_path / "art", 2.0)

        assert names == [None, "art/picture_000001.png"]
        assert "could not open page 1" in caplog.text

    def test_clears_a_stale_crop_from_a_previous_run(self, fake_pdfium, tmp_path):
        """#661: an index this run does not reuse must not survive it.

        `picture_000005.png` stands for a picture a previous parse
        reported at index 5 -- one #653's junk filter or a
        `[parser].formulas` change means this run never reaches, so
        nothing this run writes would ever overwrite it.
        """
        art = tmp_path / "art"
        art.mkdir()
        (art / "picture_000005.png").write_bytes(b"stale")
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1)])

        names = _docling_crops.write_picture_crops("p.pdf", dl_doc, art, 2.0)

        assert names == ["art/picture_000000.png"]
        assert sorted(p.name for p in art.iterdir()) == ["picture_000000.png"]

    def test_clearing_is_scoped_to_this_documents_own_directory(self, fake_pdfium, tmp_path):
        """A sibling document's `_artifacts/` must survive this call.

        Each document gets its own per-stem directory; nothing here
        should reach past the one it was given, so a run that stops
        partway through the corpus does not strip documents it never
        got to.
        """
        art = tmp_path / "a2024_artifacts"
        art.mkdir()
        other = tmp_path / "b2024_artifacts"
        other.mkdir()
        (other / "picture_000000.png").write_bytes(b"someone else's figure")
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1)])

        _docling_crops.write_picture_crops("p.pdf", dl_doc, art, 2.0)

        assert (other / "picture_000000.png").read_bytes() == b"someone else's figure"

    def test_a_clear_failure_other_than_missing_is_not_swallowed(self, monkeypatch, tmp_path):
        """Only "nothing to clear" is unremarkable, per `clear_sidecar`'s
        own `missing_ok=True` precedent -- a permission or IO error
        clearing a directory that does exist must surface rather than be
        swallowed into silently keeping the stale crops it failed to
        remove."""

        def explode(_path):
            raise PermissionError("no")

        monkeypatch.setattr(_docling_crops.shutil, "rmtree", explode)
        art = tmp_path / "art"
        art.mkdir()

        with pytest.raises(PermissionError):
            _docling_crops.write_picture_crops(
                "p.pdf", types.SimpleNamespace(pictures=[]), art, 2.0
            )

    def test_a_run_that_keeps_zero_pictures_still_clears_the_directory(self, fake_pdfium, tmp_path):
        """Every picture now junk (or none reporting provenance) must not
        leave last run's figures behind forever -- the early return for
        an empty `grouped` sits after the clear, not before it."""
        art = tmp_path / "art"
        art.mkdir()
        (art / "picture_000000.png").write_bytes(b"stale")
        dl_doc = types.SimpleNamespace(pictures=[FakePicture.without_provenance()])

        names = _docling_crops.write_picture_crops("p.pdf", dl_doc, art, 2.0)

        assert names == [None]
        assert not art.exists()

    def test_a_pdf_pdfium_cannot_open_keeps_the_text_parse(self, tmp_path, caplog):
        """docling and pdfium are different parsers, and only here does
        that matter.

        Deliberately run against the *real* pypdfium2 with a file docling
        would have had to accept to get this far. Before this was
        handled, `PdfiumError` escaped `write_picture_crops` and failed a
        document whose text had already been written correctly -- found
        by an unrelated test in test_enrich_docling_parse.py that feeds a
        `b"%PDF-1.4"` stub through the images-on path.
        """
        pytest.importorskip("pypdfium2")
        stub = tmp_path / "paper.pdf"
        stub.write_bytes(b"%PDF-1.4")
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1)])
        art = tmp_path / "art"

        names = _docling_crops.write_picture_crops(stub, dl_doc, art, 2.0)

        assert names == [None]
        assert "could not open" in caplog.text
        assert not art.exists(), "no artifacts directory for a document with no crops"
