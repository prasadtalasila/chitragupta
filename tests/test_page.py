"""The two pages a draft prints on (#1140, X-1 and X-5 reduced): what
each records, that LuaLaTeX agrees with it, that the render defaults and
the book skeleton say the same, and which page a figure is checked on.
"""

import inspect
import re
import subprocess
from pathlib import Path

import pytest

from chitragupta import page, spec, tex_engine
from chitragupta.render_output import _cli, render
from tests.conftest import needs_tikz, run_python

REPO_ROOT = Path(__file__).resolve().parent.parent
SKELETON = REPO_ROOT / ".claude" / "skills" / "book-assembler" / "assets" / "book-skeleton.tex"


@pytest.mark.slow
@needs_tikz
@pytest.mark.parametrize("measured", page.PAGES.values(), ids=list(page.PAGES))
def test_each_recorded_text_block_is_what_lualatex_sets(measured, tmp_path):
    """The values are recorded, not computed, so this compile is what
    keeps them true: a class or geometry change moves `\\textwidth` and
    turns this red, which arithmetic over papersize and margin did not."""
    (tmp_path / "page.tex").write_text(
        measured.preamble + "\\begin{document}\n"
        "\\typeout{CGPAGE \\the\\textwidth\\space\\the\\textheight}\nx\n\\end{document}\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["lualatex", *tex_engine.engine_opts(), "-interaction=nonstopmode", "page.tex"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    width, height = re.search(r"CGPAGE ([\d.]+)pt ([\d.]+)pt", result.stdout).groups()

    assert measured.text_width_pt == pytest.approx(float(width), abs=0.01)
    assert measured.text_height_pt == pytest.approx(float(height), abs=0.01)


def test_the_render_defaults_are_the_article_page():
    defaults = inspect.signature(render).parameters
    parsed = _cli._build_parser().parse_args(["draft.md"])
    for field in ("documentclass", "fontsize", "papersize", "margin"):
        assert defaults[field].default == getattr(page.ARTICLE, field)
        assert getattr(parsed, field) == getattr(page.ARTICLE, field)


def test_the_article_preamble_is_the_one_its_fields_describe():
    assert page.ARTICLE.preamble == (
        "\\documentclass[12pt,a4paper]{article}\n\\usepackage[margin=1in]{geometry}\n"
    )


def test_the_book_skeleton_sets_the_book_page():
    skeleton = SKELETON.read_text(encoding="utf-8").splitlines()
    for line in page.BOOK.preamble.splitlines():
        assert any(row.rstrip() == line or row.startswith(line + " ") for row in skeleton), line


def test_the_spec_file_name_is_the_spec_modules():
    assert page.SPEC_MD == spec.SPEC_MD


def test_render_output_imports_in_a_fresh_interpreter():
    """`page` must not import `spec`: `spec` reaches `render_output`
    through the dossier, and `render_output` imports `page`."""
    result = run_python("-c", "import chitragupta.render_output", check=False)

    assert result.returncode == 0, result.stderr


class TestPageFor:
    def test_a_figure_outside_the_drafts_is_on_the_article(self, isolated_config, tmp_path):
        found, why = page.page_for(tmp_path / "fig.tex")

        assert found is page.ARTICLE
        assert why == f"not under {isolated_config.DRAFTS_DIR}"

    def test_a_drafts_figure_with_no_spec_above_it_is_on_the_article(self, isolated_config):
        found, why = page.page_for(isolated_config.DRAFTS_DIR / "rag" / "figures" / "f.tex")

        assert (found, why) == (page.ARTICLE, "no book spec above it")

    def test_a_book_units_figure_is_on_the_book(self, isolated_config):
        spec_md = _spec(isolated_config, "twins")

        found, why = page.page_for(isolated_config.DRAFTS_DIR / "twins" / "figures" / "f.tex")

        assert (found, why) == (page.BOOK, f"from {spec_md}")

    def test_a_book_further_up_still_counts(self, isolated_config):
        spec_md = _spec(isolated_config, "books/twins")
        figure = isolated_config.DRAFTS_DIR / "books" / "twins" / "figures" / "f.tex"

        assert page.page_for(figure) == (page.BOOK, f"from {spec_md}")

    def test_a_spec_directory_symlinked_out_of_the_specs_does_not_make_a_book(
        self, isolated_config, tmp_path
    ):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "spec.md").write_text("# A book\n", encoding="utf-8")
        isolated_config.SPECS_DIR.mkdir(parents=True)
        (isolated_config.SPECS_DIR / "twins").symlink_to(outside)

        found, _ = page.page_for(isolated_config.DRAFTS_DIR / "twins" / "figures" / "f.tex")

        assert found is page.ARTICLE


def _spec(config, book: str) -> Path:
    spec_md = config.SPECS_DIR / book / "spec.md"
    spec_md.parent.mkdir(parents=True)
    spec_md.write_text("# A book\n", encoding="utf-8")
    return spec_md
