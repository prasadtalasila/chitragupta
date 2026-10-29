"""`chitragupta figure look`: one figure, set as the render sets it,
cropped to itself and rasterized (#1052)."""

import json
import math
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from chitragupta import config, pdf_fonts
from chitragupta.figure import _look
from chitragupta.figure import __main__ as cli
from chitragupta.figure._check import DEFAULT_WIDTH_PT
from chitragupta.render_output._errors import MissingBinary
from tests.conftest import needs_tikz

FIXTURES = Path(__file__).parent / "fixtures" / "figure" / "check"
NARROW = (FIXTURES / "narrow.tex").read_text(encoding="utf-8")
WIDE = (FIXTURES / "wide.tex").read_text(encoding="utf-8")

needs_poppler = pytest.mark.skipif(
    shutil.which("pdftoppm") is None or shutil.which("pdfinfo") is None,
    reason="needs poppler-utils (pdftoppm, pdfinfo)",
)


def png_bytes(width: int, height: int) -> bytes:
    """Just enough of a PNG for its size to be read back: the signature
    and the IHDR chunk's width and height."""
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", width, height)


class FakeTeX:
    """`_look._run` without a toolchain: lualatex prints the measurement
    line and writes a PDF, pdftoppm writes a PNG of the matching size."""

    def __init__(self, width=431.0, height=150.0, depth=30.0, failure=None):
        self.width, self.height, self.depth, self.failure = width, height, depth, failure
        self.calls: list[list[str]] = []

    def __call__(self, cmd, cwd=None, **_kwargs):
        self.calls.append(cmd)
        if Path(cmd[0]).name.startswith("lualatex"):
            if self.failure:
                return subprocess.CompletedProcess(cmd, 1, stdout=self.failure, stderr="")
            (Path(cwd) / "look.pdf").write_bytes(b"%PDF-fake")
            line = f"CGLOOK {self.width}pt {self.height}pt {self.depth}pt 452.9679pt\n"
            return subprocess.CompletedProcess(cmd, 0, stdout=line, stderr="")
        (Path(cwd) / f"{cmd[-1]}.png").write_bytes(png_bytes(1804, 758))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    @property
    def compiles(self) -> int:
        return sum(Path(cmd[0]).name.startswith("lualatex") for cmd in self.calls)


@pytest.fixture
def fake(monkeypatch):
    tex = FakeTeX()
    monkeypatch.setattr(_look, "_run", tex)
    monkeypatch.setattr(_look.programs, "require_program", lambda name: name)
    return tex


@pytest.fixture
def flow(isolated_config):
    path = config.DRAFTS_DIR / "rag" / "figures" / "flow.tex"
    path.parent.mkdir(parents=True)
    path.write_text(NARROW, encoding="utf-8")
    return path


def rendered(*parts: str) -> Path:
    return config.RENDERED_DIR.joinpath(*parts)


class TestDocument:
    def test_it_sets_the_figure_as_the_pdf_render_does(self):
        doc = _look.document(NARROW)
        assert doc.startswith("\\documentclass[12pt,a4paper]{article}\n")
        assert "\\usepackage[margin=1in]{geometry}" in doc
        assert pdf_fonts.latex_fonts() in doc
        assert "\\usetikzlibrary{positioning}" in doc.split("\\begin{document}")[0]

    def test_the_figure_is_set_in_a_box_whose_size_is_printed(self):
        doc = _look.document(NARROW)
        body = doc.split("\\begin{document}")[1]
        assert "\\setbox\\cgfigbox=\\hbox{%\n" + NARROW in body
        assert "\\typeout{CGLOOK" in body and "\\pagewidth=" in body

    def test_the_hairline_is_drawn_only_past_the_text_width(self):
        assert "\\ifdim\\wd\\cgfigbox>\\textwidth" in _look.document(NARROW)


class TestLook:
    def test_it_writes_three_files_beside_the_mirrored_figure(self, fake, flow):
        result = _look.look(flow)
        assert result.action == "wrote"
        assert result.pdf == rendered("rag", "figures", "flow.look.pdf")
        assert result.png == rendered("rag", "figures", "flow.look.png")
        assert result.pdf.read_bytes() == b"%PDF-fake"
        assert result.png.is_file() and result.record.is_file()
        assert (result.width, result.height, result.text_width) == (431.0, 180.0, 452.9679)
        assert result.pixels == (1804, 758) and not result.past_text_width

    def test_pdftoppm_is_asked_for_300_dpi_and_one_page(self, fake, flow):
        _look.look(flow)
        [pdftoppm] = [cmd for cmd in fake.calls if cmd[0] == "pdftoppm"]
        assert pdftoppm == ["pdftoppm", "-r", "300", "-png", "-singlefile", "look.pdf", "look"]

    def test_a_figure_outside_the_drafts_lands_flat_in_rendered(self, fake, isolated_config):
        loose = config.CONTENT_DIR / "loose.tex"
        loose.parent.mkdir(parents=True)
        loose.write_text(NARROW, encoding="utf-8")
        assert _look.look(loose).png == rendered("loose.look.png")

    def test_an_unchanged_figure_is_not_compiled_again(self, fake, flow):
        _look.look(flow)
        again = _look.look(flow)
        assert again.action == "current" and fake.compiles == 1
        assert (again.width, again.pixels) == (431.0, (1804, 758))

    @pytest.mark.parametrize("change", ["figure", "fonts", "dpi", "png"])
    def test_any_changed_input_or_missing_output_rebuilds(self, fake, flow, monkeypatch, change):
        first = _look.look(flow)
        if change == "figure":
            flow.write_text(NARROW.replace("Left", "Leftmost"), encoding="utf-8")
        elif change == "fonts":
            monkeypatch.setattr(_look.pdf_fonts, "latex_fonts", lambda: "\\setmainfont{X}\n")
        elif change == "dpi":
            monkeypatch.setattr(_look, "DPI", 150)
        else:
            first.png.unlink()
        assert _look.look(flow).action == "wrote" and fake.compiles == 2

    def test_an_unreadable_record_rebuilds(self, fake, flow):
        _look.look(flow).record.write_text("{not json", encoding="utf-8")
        assert _look.look(flow).action == "wrote"

    @pytest.mark.parametrize("record", ["[]", "{}", "missing-fields"])
    def test_a_record_of_the_wrong_shape_rebuilds(self, fake, flow, record):
        built = _look.look(flow)
        text = (
            json.dumps({"digest": _look.digest(NARROW)}) if record == "missing-fields" else record
        )
        built.record.write_text(text, encoding="utf-8")
        assert _look.look(flow).action == "wrote"

    def test_a_figure_past_the_text_width_says_so(self, monkeypatch, flow):
        monkeypatch.setattr(_look, "_run", FakeTeX(width=470.0))
        monkeypatch.setattr(_look.programs, "require_program", lambda name: name)
        result = _look.look(flow)
        assert result.past_text_width and result.width == 470.0

    def test_a_failed_compile_reports_and_removes_the_old_look(self, fake, flow, monkeypatch):
        old = _look.look(flow)
        flow.write_text(NARROW + "\\broken", encoding="utf-8")
        log = "This is LuaHBTeX\n! Undefined control sequence.\nl.12 \\broken\n"
        monkeypatch.setattr(_look, "_run", FakeTeX(failure=log))
        result = _look.look(flow)
        assert result.action == "failed" and result.detail == "! Undefined control sequence."
        assert not any(p.exists() for p in (old.pdf, old.png, old.record))

    def test_a_failed_rasterize_reports(self, fake, flow, monkeypatch):
        def no_png(cmd, cwd=None, **kwargs):
            if cmd[0] == "pdftoppm":
                return subprocess.CompletedProcess(cmd, 99, stdout="", stderr="Syntax Error\n")
            return fake(cmd, cwd=cwd, **kwargs)

        monkeypatch.setattr(_look, "_run", no_png)
        result = _look.look(flow)
        assert result.action == "failed" and result.detail == "pdftoppm: Syntax Error"

    def test_the_record_says_what_was_built_from(self, fake, flow):
        record = json.loads(_look.look(flow).record.read_text(encoding="utf-8"))
        assert record["digest"] == _look.digest(NARROW)
        assert record["pixels"] == [1804, 758]


class TestCli:
    def test_it_prints_both_files_and_their_sizes(self, fake, flow, capsys):
        assert cli.main(["look", str(flow)]) == 0
        out = capsys.readouterr().out.splitlines()
        assert out == [
            f"wrote    {rendered('rag', 'figures', 'flow.look.pdf')}"
            "   (431 x 180pt; text width 453pt)",
            f"wrote    {rendered('rag', 'figures', 'flow.look.png')}   (1804 x 758 px at 300 dpi)",
        ]

    def test_a_wide_figure_says_how_far_past(self, monkeypatch, flow, capsys):
        monkeypatch.setattr(_look, "_run", FakeTeX(width=470.0))
        monkeypatch.setattr(_look.programs, "require_program", lambda name: name)
        cli.main(["look", str(flow)])
        assert "(470 x 180pt; 17pt past the text width, line drawn)" in capsys.readouterr().out

    def test_a_failed_compile_exits_zero_with_the_error(self, monkeypatch, flow, capsys):
        monkeypatch.setattr(_look, "_run", FakeTeX(failure="! Missing $ inserted.\n"))
        monkeypatch.setattr(_look.programs, "require_program", lambda name: name)
        assert cli.main(["look", str(flow)]) == 0
        assert f"failed   {flow}: ! Missing $ inserted." in capsys.readouterr().out

    def test_an_unreadable_figure_exits_two(self, tmp_path, capsys):
        assert cli.main(["look", str(tmp_path / "absent.tex")]) == 2
        assert "not a readable UTF-8 file" in capsys.readouterr().err

    @pytest.mark.parametrize("tool", ["lualatex", "pdftoppm"])
    def test_a_missing_tool_exits_two_and_writes_nothing(self, flow, monkeypatch, capsys, tool):
        def missing(binary):
            if binary == tool:
                raise MissingBinary(f"{binary} not found on PATH.")

        monkeypatch.setattr(cli, "_require", missing)
        monkeypatch.setattr(cli, "_require_tikz", lambda: None)
        assert cli.main(["look", str(flow)]) == 2
        assert f"{tool} not found" in capsys.readouterr().err
        assert not config.RENDERED_DIR.exists()

    def test_an_unwritable_rendered_directory_exits_two(self, fake, flow, monkeypatch, capsys):
        def read_only(path, data):
            raise PermissionError(f"[Errno 13] Permission denied: '{path}'")

        monkeypatch.setattr(_look, "write_atomically", read_only)
        assert cli.main(["look", str(flow)]) == 2
        assert "Permission denied" in capsys.readouterr().err

    def test_an_output_directory_outside_content_exits_two(self, fake, flow, monkeypatch, capsys):
        def outside(_path):
            raise cli.OutsideContentDir("content/rendered resolves outside content")

        monkeypatch.setattr(_look, "_output_dir", outside)
        assert cli.main(["look", str(flow)]) == 2
        assert "resolves outside content" in capsys.readouterr().err


@needs_tikz
@needs_poppler
class TestRealCompile:
    """The crop and the pixel size, measured on what LuaLaTeX and
    pdftoppm actually wrote."""

    def page_size(self, pdf: Path) -> tuple[float, float]:
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True)
        [line] = [ln for ln in out.stdout.splitlines() if ln.startswith("Page size:")]
        width, _x, height = line.split()[2:5]
        return float(width), float(height)

    @pytest.mark.parametrize("source", [NARROW, WIDE], ids=["narrow", "wide"])
    def test_the_page_is_the_figure_plus_a_one_point_border(self, flow, source):
        flow.write_text(source, encoding="utf-8")
        result = _look.look(flow)
        assert result.action == "wrote", result.detail
        width_bp, height_bp = self.page_size(result.pdf)
        # pdfinfo reports PostScript points (1/72in); TeX's pt is 1/72.27in.
        assert width_bp * 72.27 / 72 == pytest.approx(result.width + 2, abs=0.05)
        assert height_bp * 72.27 / 72 == pytest.approx(result.height + 2, abs=0.05)
        assert result.past_text_width == (source is WIDE)

    def test_the_png_is_the_page_at_300_dpi(self, flow):
        result = _look.look(flow)
        width_bp, height_bp = self.page_size(result.pdf)
        # pdftoppm rounds a page's pixel size up, never to nearest.
        assert result.pixels == (math.ceil(width_bp / 72 * 300), math.ceil(height_bp / 72 * 300))

    def test_the_text_width_is_the_renders(self, flow):
        assert _look.look(flow).text_width == pytest.approx(DEFAULT_WIDTH_PT, abs=0.05)
