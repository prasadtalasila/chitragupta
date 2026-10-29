"""chitragupta/figure/_look_draft.py: every figure of a draft just
rendered to pdf, its look and its page (#1052), and `draft render`'s
`[figure-look]` notes."""

import dataclasses
import subprocess
from pathlib import Path

import pytest

from chitragupta import config, render_output
from chitragupta.figure import _look_draft
from chitragupta.figure._look import Look, lines
from chitragupta.render_output import _cli
from chitragupta.render_output._errors import MissingBinary
from tests.conftest import content_draft, lualatex_available, pandoc_available, tikz_available
from tests.test_figure_look import needs_poppler, png_bytes

DESTS = (
    "Page  Destination                 Name\n"
    '   3 [ XYZ  103  609 null      ] "cgfig:figures/flow"\n'
)


@pytest.fixture
def draft(isolated_config):
    path = content_draft(isolated_config, "drafts/rag/survey.md")
    (path.parent / "figures").mkdir()
    for name in ("flow", "stack"):
        (path.parent / "figures" / f"{name}.tex").write_text("\\begin{tikzpicture}\\end{tikzpicture}")
    path.write_text(
        "Text.\n\n<!-- figure: figures/flow -->\n\n<!-- figure: figures/stack -->\n\n"
        "<!-- figure: figures/absent -->\n",
        encoding="utf-8",
    )
    return path


def rendered(*parts: str) -> Path:
    return config.RENDERED_DIR.joinpath(*parts)


def fake_look(figure: Path) -> Look:
    out = rendered("rag", "figures")
    return Look(out / f"{figure.stem}.look.pdf", out / f"{figure.stem}.look.png",
                out / f"{figure.stem}.look.json", "wrote", 431.0, 180.0, 452.97, (1804, 758))


class Poppler:
    """`_look_draft._run` without poppler: `pdfinfo -dests` answers
    `dests`, `pdftoppm` writes an A4 page at 300 dpi."""

    def __init__(self, dests=DESTS, info_code=0, raster_code=0):
        self.dests, self.info_code, self.raster_code = dests, info_code, raster_code
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **_kwargs):
        self.calls.append(cmd)
        if cmd[0] == "pdfinfo":
            return subprocess.CompletedProcess(cmd, self.info_code, stdout=self.dests, stderr="")
        if self.raster_code:
            return subprocess.CompletedProcess(cmd, self.raster_code, stdout="", stderr="bad page\n")
        Path(f"{cmd[-1]}.png").write_bytes(png_bytes(2480, 3508))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


@pytest.fixture
def tools(monkeypatch):
    """Every tool present, and `look` itself faked."""
    present = {"pdftoppm", "pdfinfo"}
    monkeypatch.setattr(_look_draft.programs, "resolve_program", lambda n: n if n in present else None)
    monkeypatch.setattr(_look_draft.programs, "require_program", lambda n: n)
    monkeypatch.setattr(_look_draft, "look", fake_look)
    poppler = Poppler()
    monkeypatch.setattr(_look_draft, "_run", poppler)
    return present, poppler


class TestDraftFigures:
    def test_only_markers_that_resolve_to_a_file(self, draft):
        assert _look_draft.draft_figures(draft) == {
            "figures/flow": draft.parent / "figures" / "flow.tex",
            "figures/stack": draft.parent / "figures" / "stack.tex",
        }

    def test_a_tex_draft_names_its_figures_by_input(self, draft):
        tex = draft.with_suffix(".tex")
        tex.write_text("\\input{figures/flow}\n% figure: figures/flow\n", encoding="utf-8")
        assert list(_look_draft.draft_figures(tex)) == ["figures/flow"]


class TestRefresh:
    def test_each_figure_gets_its_look_and_a_marked_one_its_page(self, draft, tools):
        _present, poppler = tools
        result = _look_draft.refresh(draft, Path("survey.pdf"))
        flow, stack = result.figures
        assert flow.page.png == rendered("rag", "figures", "flow.page.png")
        assert (flow.page.number, flow.page.pixels) == (3, (2480, 3508))
        assert flow.page.png.read_bytes() == png_bytes(2480, 3508)
        assert stack.page is None and stack.note == _look_draft.NO_MARK
        [raster] = [cmd for cmd in poppler.calls if cmd[0] == "pdftoppm"]
        assert raster[1:9] == ["-f", "3", "-l", "3", "-r", "300", "-png", "-singlefile"]

    def test_an_old_page_picture_of_a_figure_that_no_longer_prints_is_deleted(self, draft, tools):
        stale = rendered("rag", "figures", "stack.page.png")
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"old")
        _look_draft.refresh(draft, Path("survey.pdf"))
        assert not stale.exists()

    def test_a_draft_with_no_figures_or_no_file_says_nothing(self, draft, tools):
        draft.write_text("No figures.\n", encoding="utf-8")
        assert _look_draft.notes(_look_draft.refresh(draft, Path("x.pdf"))) == []
        missing = _look_draft.refresh(draft.with_name("absent.md"), Path("x.pdf"))
        assert _look_draft.notes(missing) == []

    def test_no_pdftoppm_skips_everything_with_one_note(self, draft, tools):
        tools[0].clear()
        assert _look_draft.notes(_look_draft.refresh(draft, Path("x.pdf"))) == [
            "[figure-look] skipped: pdftoppm not found on PATH (chitragupta install os-deps)"
        ]

    def test_no_pdfinfo_keeps_the_looks_and_skips_the_pages(self, draft, tools):
        tools[0].discard("pdfinfo")
        result = _look_draft.refresh(draft, Path("x.pdf"))
        assert [item.page for item in result.figures] == [None, None]
        assert _look_draft.notes(result) == [
            "[figure-look] 2 wrote; 0 page PNGs",
            "[figure-look] skipped page PNGs: pdfinfo not found on PATH "
            "(chitragupta install os-deps)",
        ]

    def test_pdfinfo_failing_is_no_marks(self, draft, tools, monkeypatch):
        monkeypatch.setattr(_look_draft, "_run", Poppler(info_code=1))
        notes = [item.note for item in _look_draft.refresh(draft, Path("x.pdf")).figures]
        assert notes == [_look_draft.NO_MARK, _look_draft.NO_MARK]

    def test_pdftoppm_failing_is_a_note(self, draft, tools, monkeypatch):
        monkeypatch.setattr(_look_draft, "_run", Poppler(raster_code=1))
        flow = _look_draft.refresh(draft, Path("x.pdf")).figures[0]
        assert flow.page is None and flow.note == "no page PNG: pdftoppm: bad page"

    def test_a_look_that_cannot_read_its_figure_is_a_note(self, draft, tools, monkeypatch):
        def unreadable(figure):
            raise OSError(f"{figure.name}: gone")

        monkeypatch.setattr(_look_draft, "look", unreadable)
        flow = _look_draft.refresh(draft, Path("x.pdf")).figures[0]
        assert flow.look is None and flow.note == "no look: flow.tex: gone"

    def test_the_notes_count_and_name_failures(self, draft, tools, monkeypatch):
        def failing(figure):
            detail = "! Undefined control sequence."
            return dataclasses.replace(fake_look(figure), action="failed", detail=detail)

        monkeypatch.setattr(_look_draft, "look", failing)
        notes = _look_draft.notes(_look_draft.refresh(draft, Path("x.pdf")))
        stack = draft.parent / "figures" / "stack.tex"
        assert notes[0] == "[figure-look] 2 failed; 1 page PNGs"
        assert f"[figure-look] failed {stack}: ! Undefined control sequence." in notes
        assert f"[figure-look] {stack}: {_look_draft.NO_MARK}" in notes

    def test_a_figure_with_no_look_at_all_still_counts_its_page(self, draft, tools, monkeypatch):
        monkeypatch.setattr(_look_draft, "look", lambda f: (_ for _ in ()).throw(OSError("x")))
        assert _look_draft.notes(_look_draft.refresh(draft, Path("x.pdf")))[0] == (
            "[figure-look] no looks; 1 page PNGs"
        )

    def test_the_page_line(self):
        page = _look_draft.Page(Path("out/flow.page.png"), 4, (2480, 3508))
        assert _look_draft.page_line(page, Path("out/survey.pdf")) == (
            f"wrote    {Path('out/flow.page.png')}   (page 4 of survey.pdf; 2480 x 3508 px)"
        )


class TestDraftRender:
    def test_a_pdf_render_prints_the_notes_and_then_its_path(self, draft, tools, monkeypatch, capsys):
        pdf = rendered("rag", "survey.pdf")
        monkeypatch.setattr(render_output, "render", lambda *a, **k: pdf)
        assert _cli.main([str(draft), "--format", "pdf"]) == 0
        captured = capsys.readouterr()
        assert captured.out == f"{pdf}\n"
        assert captured.err.startswith("[figure-look] 2 wrote; 1 page PNGs\n")

    def test_another_format_refreshes_nothing(self, draft, tools, monkeypatch, capsys):
        monkeypatch.setattr(render_output, "render", lambda *a, **k: Path("out.tex"))
        assert _cli.main([str(draft), "--format", "tex"]) == 0
        assert "[figure-look]" not in capsys.readouterr().err

    def test_a_refused_render_refreshes_nothing(self, draft, tools, monkeypatch, capsys):
        def refused(*_args, **_kwargs):
            raise render_output.MissingBinary("pandoc not found.")

        monkeypatch.setattr(render_output, "render", refused)
        assert _cli.main([str(draft), "--format", "pdf"]) == 1
        captured = capsys.readouterr()
        assert "[missing-binary] pandoc not found." in captured.out
        assert "[figure-look]" not in captured.err


@needs_poppler
@pytest.mark.skipif(
    not (pandoc_available and lualatex_available and tikz_available),
    reason="needs pandoc and lualatex with tikz.sty",
)
def test_a_real_pdf_render_leaves_every_figure_looked_at(isolated_config, capsys):
    isolated_config.BIB_FILE_PATH.write_text("")
    draft = content_draft(isolated_config, "drafts/rag/survey.md")
    (draft.parent / "figures").mkdir()
    picture = "\\begin{tikzpicture}\\node[draw] {Parse};\\end{tikzpicture}%\n"
    (draft.parent / "figures" / "flow.tex").write_text(picture, encoding="utf-8")
    (draft.parent / "figures" / "flow.txt").write_text("[ Parse ]\n", encoding="utf-8")
    draft.write_text("Text.\n\n<!-- figure: figures/flow -->\n\nMore.\n", encoding="utf-8")
    assert _cli.main([str(draft), "--format", "pdf"]) == 0
    assert "[figure-look] 1 wrote; 1 page PNGs" in capsys.readouterr().err
    out = rendered("rag", "figures")
    # flow.tex is the render's own copy of the source, as it always was.
    assert {p.name for p in out.iterdir()} == {
        "flow.tex", "flow.look.pdf", "flow.look.png", "flow.look.json", "flow.page.png"
    }
    # A4 at 300 dpi, rounded up as pdftoppm rounds: 595.28pt is 2480.3 px.
    assert _look_draft._png_size(out / "flow.page.png") == (2481, 3508)


class TestLookDraftCli:
    """`figure look <figure> --draft <draft>`, with the render and the
    refresh faked at the CLI's own names."""

    @pytest.fixture
    def figure_cli(self, draft, monkeypatch):
        from chitragupta.figure import __main__ as cli

        monkeypatch.setattr(cli, "_require", lambda binary: None)
        monkeypatch.setattr(cli, "_require_tikz", lambda: None)
        monkeypatch.setattr(cli, "look", fake_look)
        return cli

    def run(self, cli, figure, draft) -> int:
        return cli.main(["look", str(figure), "--draft", str(draft)])

    def test_it_prints_the_render_the_look_and_the_page(
        self, figure_cli, draft, monkeypatch, capsys
    ):
        flow = draft.parent / "figures" / "flow.tex"
        pdf = rendered("rag", "survey.pdf")
        page = _look_draft.Page(rendered("rag", "figures", "flow.page.png"), 4, (2481, 3508))
        refreshed = _look_draft.Refresh([_look_draft.DraftFigure(flow, fake_look(flow), page)])
        monkeypatch.setattr(figure_cli, "_rendered", lambda args: pdf)
        monkeypatch.setattr(figure_cli, "refresh", lambda d, p: refreshed)
        assert self.run(figure_cli, flow, draft) == 0
        captured = capsys.readouterr()
        assert captured.out.splitlines() == [
            f"wrote    {pdf}",
            *lines(fake_look(flow), flow),
            _look_draft.page_line(page, pdf),
        ]
        assert captured.err == "[figure-look] 1 wrote; 1 page PNGs\n"

    def test_the_render_s_own_arguments_are_a_pdf_of_the_draft(
        self, figure_cli, draft, monkeypatch
    ):
        seen = []
        monkeypatch.setattr(figure_cli, "_rendered", lambda args: seen.append(args))
        self.run(figure_cli, draft.parent / "figures" / "flow.tex", draft)
        assert (seen[0].input, seen[0].output_format) == (str(draft), "pdf")

    def test_a_draft_that_does_not_render_still_writes_the_look(
        self, figure_cli, draft, monkeypatch, capsys
    ):
        flow = draft.parent / "figures" / "flow.tex"
        monkeypatch.setattr(figure_cli, "_rendered", lambda args: None)
        assert self.run(figure_cli, flow, draft) == 0
        assert capsys.readouterr().out.splitlines() == lines(fake_look(flow), flow)

    def test_a_figure_the_draft_does_not_name_gets_its_look_and_a_note(
        self, figure_cli, draft, monkeypatch, capsys
    ):
        loose = draft.parent / "figures" / "loose.tex"
        loose.write_text("\\begin{tikzpicture}\\end{tikzpicture}", encoding="utf-8")
        monkeypatch.setattr(figure_cli, "_rendered", lambda args: Path("survey.pdf"))
        monkeypatch.setattr(figure_cli, "refresh", lambda d, p: _look_draft.Refresh())
        assert self.run(figure_cli, loose, draft) == 0
        assert capsys.readouterr().out.splitlines()[-1] == (
            f"note     {loose}: no figure marker in {draft} names it, so no page PNG"
        )

    @pytest.mark.parametrize(
        ("item", "skipped", "note"),
        [
            ({"note": _look_draft.NO_MARK}, "", _look_draft.NO_MARK),
            ({}, "page PNGs: pdfinfo not found", "page PNGs: pdfinfo not found"),
            ({"look": None, "note": "no look: gone"}, "", "no look: gone"),
        ],
        ids=["no-mark", "no-pdfinfo", "no-look"],
    )
    def test_whatever_is_missing_is_one_note(
        self, figure_cli, draft, monkeypatch, capsys, item, skipped, note
    ):
        flow = draft.parent / "figures" / "flow.tex"
        fields = {"look": fake_look(flow), **item}
        refreshed = _look_draft.Refresh([_look_draft.DraftFigure(flow, **fields)], skipped)
        monkeypatch.setattr(figure_cli, "_rendered", lambda args: Path("survey.pdf"))
        monkeypatch.setattr(figure_cli, "refresh", lambda d, p: refreshed)
        self.run(figure_cli, flow, draft)
        out = capsys.readouterr().out.splitlines()
        assert out[-1] == f"note     {flow}: {note}"
        assert (len(out) == 2) == (fields["look"] is None)

    def test_no_pandoc_exits_two(self, draft, monkeypatch, capsys):
        from chitragupta.figure import __main__ as cli

        def missing(binary):
            if binary == "pandoc":
                raise MissingBinary("pandoc not found on PATH.")

        monkeypatch.setattr(cli, "_require", missing)
        monkeypatch.setattr(cli, "_require_tikz", lambda: None)
        flow = draft.parent / "figures" / "flow.tex"
        assert cli.main(["look", str(flow), "--draft", str(draft)]) == 2
        assert "pandoc not found" in capsys.readouterr().err
