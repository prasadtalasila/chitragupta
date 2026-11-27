import types

import conftest
import pytest

from chitragupta.enrich import _docling_crops


class FakeBBox:
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
    def test_bottomleft_origin(self):
        assert _docling_crops.crop_insets(bbox(10, 90, 60, 40), 100.0, 100.0) == (
            10.0,
            40.0,
            40.0,
            10.0,
        )

    def test_topleft_origin(self):
        assert _docling_crops.crop_insets(bbox(10, 10, 60, 40, origin="TOPLEFT"), 100.0, 100.0) == (
            10.0,
            60.0,
            40.0,
            10.0,
        )

    def test_bbox_without_the_conversion_is_treated_as_bottomleft(self):
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
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=4) for _ in range(3)])

        _docling_crops.write_picture_crops("p.pdf", dl_doc, tmp_path / "art", 2.0)

        assert fake_pdfium.count("page.open page=3") == 1
        assert len([line for line in fake_pdfium if line.startswith("render")]) == 3

    def test_picture_without_provenance_gets_no_name(self, fake_pdfium, tmp_path):
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
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1)])

        _docling_crops.write_picture_crops("p.pdf", dl_doc, tmp_path / "art", 6.0)

        assert any("scale=6.0" in line for line in fake_pdfium)

    def test_no_pictures_writes_nothing_and_opens_no_pdf(self, fake_pdfium, tmp_path):
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
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1), FakePicture(page=2)])
        real_getitem = conftest.FakePdfiumDocument.__getitem__

        def explode(self, index):
            if index == 0:
                raise ValueError("Decoded image exceeds size limit of 20971520 bytes.")
            return real_getitem(self, index)

        monkeypatch.setattr(conftest.FakePdfiumDocument, "__getitem__", explode)
        names = _docling_crops.write_picture_crops("p.pdf", dl_doc, tmp_path / "art", 2.0)

        assert names == [None, "art/picture_000001.png"]
        assert "could not open page 1" in caplog.text

    def test_clears_a_stale_crop_from_a_previous_run(self, fake_pdfium, tmp_path):
        art = tmp_path / "art"
        art.mkdir()
        (art / "picture_000005.png").write_bytes(b"stale")
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1)])

        names = _docling_crops.write_picture_crops("p.pdf", dl_doc, art, 2.0)

        assert names == ["art/picture_000000.png"]
        assert sorted(p.name for p in art.iterdir()) == ["picture_000000.png"]

    def test_clearing_is_scoped_to_this_documents_own_directory(self, fake_pdfium, tmp_path):
        art = tmp_path / "a2024_artifacts"
        art.mkdir()
        other = tmp_path / "b2024_artifacts"
        other.mkdir()
        (other / "picture_000000.png").write_bytes(b"someone else's figure")
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1)])

        _docling_crops.write_picture_crops("p.pdf", dl_doc, art, 2.0)

        assert (other / "picture_000000.png").read_bytes() == b"someone else's figure"

    def test_a_clear_failure_other_than_missing_is_not_swallowed(self, monkeypatch, tmp_path):
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
        art = tmp_path / "art"
        art.mkdir()
        (art / "picture_000000.png").write_bytes(b"stale")
        dl_doc = types.SimpleNamespace(pictures=[FakePicture.without_provenance()])

        names = _docling_crops.write_picture_crops("p.pdf", dl_doc, art, 2.0)

        assert names == [None]
        assert not art.exists()

    def test_a_pdf_pdfium_cannot_open_keeps_the_text_parse(self, tmp_path, caplog):
        pytest.importorskip("pypdfium2")
        stub = tmp_path / "paper.pdf"
        stub.write_bytes(b"%PDF-1.4")
        dl_doc = types.SimpleNamespace(pictures=[FakePicture(page=1)])
        art = tmp_path / "art"

        names = _docling_crops.write_picture_crops(stub, dl_doc, art, 2.0)

        assert names == [None]
        assert "could not open" in caplog.text
        assert not art.exists(), "no artifacts directory for a document with no crops"
