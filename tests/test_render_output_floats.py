"""chitragupta/render_output/_floats.py and assets/latex/chitragupta-floats.tex:
where a rendered figure may float, and the report of one that still
lands on a float-only page (#1065)."""

import re
import shutil
import subprocess

import pytest

from chitragupta import render_output
from chitragupta.render_output import _floats
from tests.conftest import (
    content_draft,
    lualatex_available,
    pandoc_available,
    pdftotext_available,
)

# Six paragraphs of body text, so a figure has a page of text to sit in.
_TEXT = ("word " * 120 + "\n\n") * 6


def _figure(height: str, caption: str) -> str:
    """A figure `height` of the text height tall, plus its caption."""
    rule = f"\\rule{{1pt}}{{{height}\\textheight}}"
    return f"\\begin{{figure}}{rule}\\caption{{{caption}}}\\end{{figure}}\n"


class TestPreambleArgs:
    @pytest.mark.parametrize("fmt", ["pdf", "tex"])
    def test_a_standalone_latex_render_includes_the_file(self, tmp_path, fmt):
        args = _floats.preamble_args(fmt, False, [], tmp_path)
        assert args == ["--include-in-header", str(_floats.path())]

    @pytest.mark.parametrize("fmt", ["html", "docx", "md"])
    def test_a_format_that_is_not_latex_gets_nothing(self, tmp_path, fmt):
        assert _floats.preamble_args(fmt, False, ["figures/a.tex"], tmp_path) == []

    def test_a_fragment_with_a_figure_gets_the_file_beside_it_and_a_notice(self, tmp_path, capsys):
        out = tmp_path / "out"
        # A fragment has no preamble: pandoc's -H would make it standalone.
        assert _floats.preamble_args("tex", True, ["figures/a.tex"], out) == []
        assert (out / "chitragupta-floats.tex").read_bytes() == _floats.path().read_bytes()
        err = capsys.readouterr().err
        assert err.startswith("[floats] ")
        assert "\\input{chitragupta-floats}" in err

    def test_a_fragment_without_a_figure_is_silent(self, tmp_path, capsys):
        assert _floats.preamble_args("tex", True, [], tmp_path) == []
        assert capsys.readouterr().err == ""
        assert not (tmp_path / "chitragupta-floats.tex").exists()


class TestThePandocCommand:
    def _cmd(self, tmp_path, output_format, fragment=False):
        names = ("in.md", "bib.bib", "ieee.csl", f"out.{output_format}", "in.md")
        cmd, _ = render_output._pandoc_command(
            *(tmp_path / name for name in names),
            output_format, "article", "12pt", "a4", "1in", ["figures/a.tex"], fragment, False, [],
        )  # fmt: skip
        return [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--include-in-header"]

    @pytest.mark.parametrize("fmt", ["pdf", "tex"])
    def test_a_standalone_render_includes_the_file(self, tmp_path, fmt):
        assert str(_floats.path()) in self._cmd(tmp_path, fmt)

    def test_a_fragment_includes_nothing_and_takes_the_file_beside_it(self, tmp_path):
        assert self._cmd(tmp_path, "tex", fragment=True) == []
        assert (tmp_path / "chitragupta-floats.tex").is_file()


def _info(lines: str) -> bytes:
    """A pdf's Info dictionary as LuaTeX writes the key, around `lines`."""
    return (
        b"<< /Title (T) /ChitraguptaFloatPages <" + lines.encode().hex().upper().encode() + b"> >>"
    )


class TestPrintReport:
    def test_one_line_per_page_naming_its_figures(self, tmp_path, capsys):
        pdf = tmp_path / "out.pdf"
        pdf.write_bytes(_info("36\t2.5\n40\t3.1\n40\t3.2\n41\tA.1\n41\tA.2\n41\tA.3\n"))
        _floats.print_report(pdf)
        lines = capsys.readouterr().err.splitlines()
        assert [line.split(" and no text")[0] for line in lines] == [
            "[float-page] p. 36 holds Figure 2.5",
            "[float-page] p. 40 holds Figures 3.1 and 3.2",
            "[float-page] p. 41 holds Figures A.1, A.2 and A.3",
        ]
        assert all("0.85" in line for line in lines), "says what may share a page"

    def test_an_uncaptioned_figure_is_not_given_another_figure_s_number(self, tmp_path, capsys):
        """No `\\caption` steps no counter, so the number field is empty."""
        pdf = tmp_path / "out.pdf"
        pdf.write_bytes(_info("6\t\n7\t3\n7\t\n7\t\n"))
        _floats.print_report(pdf)
        lines = capsys.readouterr().err.splitlines()
        assert [line.split(" and no text")[0] for line in lines] == [
            "[float-page] p. 6 holds an uncaptioned figure",
            "[float-page] p. 7 holds Figure 3 and 2 uncaptioned figures",
        ]

    def test_a_pdf_without_the_key_is_silent(self, tmp_path, capsys):
        # LuaLaTeX writes the key only when a figure lands on a float page.
        pdf = tmp_path / "out.pdf"
        pdf.write_bytes(b"<< /Title (T) >>")
        _floats.print_report(pdf)
        assert capsys.readouterr().err == ""


@pytest.mark.usefixtures("programs_on_path")
def test_a_pdf_render_prints_the_report_once_pandoc_returns(monkeypatch, tmp_path, capsys):
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(_info("2\t1\n"))
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", "")
    )
    render_output._run_pandoc(["pandoc", "in.md", "--pdf-engine", "lualatex", "-o", str(pdf)], {})
    assert capsys.readouterr().err.startswith("[float-page] p. 2 holds Figure 1 and no text.")


def test_a_float_page_must_be_fuller_than_a_text_page_may_be():
    """A figure taller than \\floatpagefraction but shorter than
    \\topfraction can go either way; the other order strands one that
    fits neither until the next \\clearpage."""
    text = _floats.path().read_text(encoding="utf-8")
    values = dict(re.findall(r"\\renewcommand\{\\(\w+)\}\{([\d.]+)\}", text))
    assert float(values["floatpagefraction"]) < float(values["topfraction"])
    assert float(values["textfraction"]) + float(values["topfraction"]) <= 1


# The class defaults this file replaces, put back after it.
_CLASS_DEFAULTS = (
    "\\renewcommand{\\floatpagefraction}{0.5}\\renewcommand{\\topfraction}{0.7}"
    "\\makeatletter\\def\\fps@figure{tbp}\\makeatother"
)
_FLOAT_PAGE_RE = r"chitragupta float page: (\d+) holds Figure 1\b"


@pytest.mark.skipif(not lualatex_available, reason="lualatex not installed")
class TestUnderLuaLaTeX:
    def _compile(self, tmp_path, body, after=""):
        doc = tmp_path / "doc.tex"
        doc.write_text(
            "\\documentclass{article}\n"
            f"\\input{{{_floats.path().as_posix()}}}\n{after}\n"
            f"\\begin{{document}}\n{body}\\end{{document}}\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [shutil.which("lualatex"), "-interaction=nonstopmode", "-halt-on-error", doc.name],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout[-2000:]
        return (tmp_path / "doc.log").read_text(encoding="utf-8", errors="replace")

    def test_a_figure_the_class_defaults_would_float_stays_in_the_text(self, tmp_path, capsys):
        body = _TEXT + _figure("0.7", "Fits") + _TEXT
        assert "chitragupta float page:" not in self._compile(tmp_path, body)
        _floats.print_report(tmp_path / "doc.pdf")
        assert capsys.readouterr().err == ""

    def test_the_class_defaults_are_what_put_it_on_a_page_of_its_own(self, tmp_path):
        """The same figure with the defaults put back: the guard has to
        see the shape it exists for."""
        body = _TEXT + _figure("0.7", "Fits") + _TEXT
        assert re.search(_FLOAT_PAGE_RE, self._compile(tmp_path, body, after=_CLASS_DEFAULTS))

    def test_a_figure_too_tall_for_the_text_is_reported_in_the_log_and_the_pdf(
        self, tmp_path, capsys
    ):
        body = _TEXT + _figure("0.9", "Tall") + _TEXT
        page = re.search(_FLOAT_PAGE_RE, self._compile(tmp_path, body)).group(1)
        _floats.print_report(tmp_path / "doc.pdf")
        assert capsys.readouterr().err.startswith(f"[float-page] p. {page} holds Figure 1 ")

    def test_an_uncaptioned_figure_is_reported_as_one(self, tmp_path):
        """Reproduced in review: it was logged under the last captioned
        figure's number, which sat in the text pages earlier."""
        bare = "\\begin{figure}\\rule{1pt}{0.9\\textheight}\\end{figure}\n"
        body = _figure("0.2", "Small") + _TEXT + bare + _TEXT
        log = self._compile(tmp_path, body)
        assert re.search(r"chitragupta float page: \d+ holds an uncaptioned figure", log)
        assert "holds Figure 1" not in log


@pytest.mark.skipif(
    not (pandoc_available and lualatex_available and pdftotext_available),
    reason="pandoc/lualatex/poppler not installed",
)
def test_a_pdf_render_reports_a_figure_alone_on_a_float_page(isolated_config, capsys):
    isolated_config.BIB_FILE_PATH.write_text("")
    draft = content_draft(isolated_config, "draft.md")
    tall = "```{=latex}\n" + _figure("0.9", "Tall") + "```\n\n"
    draft.write_text("---\ntitle: Kept\n---\n\n" + _TEXT + tall + _TEXT, encoding="utf-8")
    out = render_output.render(str(draft), output_format="pdf")
    err = capsys.readouterr().err
    assert re.search(r"^\[float-page\] p\. \d+ holds Figure 1 and no text", err, re.MULTILINE)
    # The template's own Info entries survive the one this adds.
    info = subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True, check=True)
    assert re.search(r"^Title:\s+Kept$", info.stdout, re.MULTILINE)
