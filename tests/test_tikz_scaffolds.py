"""assets/tikz/: the known-good layout scaffolds, one per metaphor.

docs/FEATURE-ROADMAP.md's D3 (#382). docs/TIKZ-STYLE.md tells an author
to commit to a layout metaphor before placing a node; these are what
that choice hands them, so a figure starts from a file rather than from
an empty `tikzpicture`.

**The point of this file is that "known-good" is a check and not a
claim.** #382's acceptance criterion is that every scaffold reports zero
binary findings from `python -m chitragupta.review figure`, and the aid
shipped in #314, so the criterion is testable and is tested here rather
than asserted in a README.

Two things it guards that are easy to miss:

- **The metaphor list is read out of docs/TIKZ-STYLE.md**, not restated.
  Adding a row to that table without adding a file here fails, which is
  the coverage half of the criterion.
- **Zero findings has to be earned, not vacuous.** The aid measures a
  node's geometry only where the source spells an explicit `(name)`, so
  a picture that names nothing reports no overlap and no protrusion
  because nothing was measurable at all. Exactly 1 of the 43 figures in
  this repository's own drafted book names a node (#393), so this is the
  normal case rather than a corner. Every scaffold is therefore also
  asserted to have every name it declares come back measured. That
  assertion used to be this file's own workaround for the aid reporting
  the two cases identically; #405 moved the distinction into the aid, so
  it is now a second opinion on a thing `has_findings` already covers
  rather than the only thing covering it.

#1012 added the house figure-style block, `assets/tikz/cg-figstyle.tex`,
which every scaffold and exemplar carries verbatim. Two more guards
follow from that:

- **The copies cannot fork.** Duplication on purpose fails one way,
  silently: a copy edited in one file. Every carrier's marked region is
  compared byte for byte with the block.
- **The type floor is read back out of the PDF**, not out of the
  source. A `\\scriptsize` in the source is the easy case; the one that
  matters is a size arriving from somewhere the figure file cannot see,
  such as a `\\resizebox` in the draft that inputs it.
"""

import ctypes
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from chitragupta.review import figure_layout
from tests.conftest import needs_tikz

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_DIR = REPO_ROOT / "assets" / "tikz"
EXEMPLAR_DIR = SCAFFOLD_DIR / "exemplars"
STYLE_DOC = REPO_ROOT / "docs" / "TIKZ-STYLE.md"

# The house block, and the two comment lines that bound its copy inside a
# figure. The markers are the shape #1013's `figure sync` will rewrite
# between; matching the start by prefix leaves its version free to move.
BLOCK = SCAFFOLD_DIR / "cg-figstyle.tex"
_REGION_START = "% >>> chitragupta figure style v"
_REGION_END = "% >>> end chitragupta figure style <<<\n"

# The metaphor table in docs/TIKZ-STYLE.md, found by its header rather
# than by position: the rows after `| Metaphor | TikZ idiom |` and its
# `| --- |` separator, up to the first line that is not a table row.
_TABLE_HEADER = "| Metaphor | TikZ idiom |"
_ROW_RE = re.compile(r"^\|\s*(?P<metaphor>[^|]+?)\s*\|\s*(?P<idiom>[^|]+?)\s*\|$")


def _metaphors() -> list[str]:
    """Every metaphor docs/TIKZ-STYLE.md's table names, in its order."""
    lines = STYLE_DOC.read_text(encoding="utf-8").splitlines()
    start = lines.index(_TABLE_HEADER) + 2  # header, then the `| --- |`
    found = []
    for line in lines[start:]:
        match = _ROW_RE.match(line)
        if match is None:
            break
        found.append(match.group("metaphor"))
    return found


def _slug(metaphor: str) -> str:
    """The file name a metaphor maps to: `Layered stack` ->
    `layered-stack`. Mechanical on purpose -- the mapping is a rule a
    reader can apply, not a lookup table that has to be maintained
    alongside the doc it mirrors."""
    return re.sub(r"[^a-z0-9]+", "-", metaphor.lower()).strip("-")


def _scaffolds() -> list[Path]:
    """One file per metaphor: everything here except the block itself."""
    return sorted(path for path in SCAFFOLD_DIR.glob("*.tex") if path != BLOCK)


def _carriers() -> list[Path]:
    """Every figure this directory ships, scaffolds and exemplars alike.
    Each carries the block, and each is held to the same checks."""
    return _scaffolds() + sorted(EXEMPLAR_DIR.glob("*.tex"))


def _region(text: str) -> str | None:
    """The block's copy inside `text`, markers included, or None."""
    start = text.find(_REGION_START)
    end = text.find(_REGION_END, start)
    if start < 0 or end < 0:
        return None
    return text[start : end + len(_REGION_END)]


# The well a `pic` is drawn into, and the `pic`s themselves, both read
# out of the block rather than restated, so the test follows an edit.
_WELL_RE = re.compile(
    r"cgwell/\.style=\{[^}]*minimum width=(?P<w>[\d.]+)mm, minimum height=(?P<h>[\d.]+)mm"
)
_PIC_RE = re.compile(r"pics/(?P<name>\w+)/\.style=")
_PT_PER_MM = 72.27 / 25.4
_CGPIC_RE = re.compile(r"CGPIC (\S+) (-?[\d.]+)pt (-?[\d.]+)pt (-?[\d.]+)pt (-?[\d.]+)pt")
_LIBRARIES = "arrows.meta,positioning,fit,backgrounds,calc,shadows.blur"


def _pics() -> list[str]:
    """Every `pic` the block defines, in the order it defines them."""
    return _PIC_RE.findall(BLOCK.read_text(encoding="utf-8"))


# Parametrised by file rather than by metaphor so a failure names the
# scaffold a reader would go and open.
by_scaffold = pytest.mark.parametrize("scaffold", _scaffolds(), ids=lambda p: p.stem)
by_carrier = pytest.mark.parametrize("scaffold", _carriers(), ids=lambda p: p.stem)


class TestMetaphorCoverage:
    """The set covers docs/TIKZ-STYLE.md's table, in both directions."""

    def test_the_table_was_actually_read_past_its_first_row(self):
        """The non-vacuous-scan guard every repo-walking test here owes.

        A doc reformat that renamed a column or reflowed the table makes
        `_metaphors()` return nothing, and an empty list satisfies
        `test_every_metaphor_has_a_scaffold` for the wrong reason. More
        than one row also catches the row loop breaking early.

        Deliberately not `>= 6`: the number of metaphors is the style
        doc's to change, and pinning today's count here would turn
        dropping one into a test failure in the wrong file. The set
        equality below is what actually holds the two in step.
        """
        assert len(_metaphors()) > 1

    def test_every_metaphor_has_a_scaffold(self):
        missing = [m for m in _metaphors() if not (SCAFFOLD_DIR / f"{_slug(m)}.tex").exists()]

        assert missing == []

    def test_no_scaffold_names_a_metaphor_the_doc_dropped(self):
        """The other direction: a row deleted from the table leaves a
        file here claiming to implement guidance that no longer
        exists."""
        expected = {_slug(m) for m in _metaphors()}

        assert {path.stem for path in _scaffolds()} == expected


class TestEverySourceProperty:
    """What can be checked without a toolchain, so it runs everywhere."""

    @by_carrier
    def test_carries_its_own_usetikzlibrary_line(self, scaffold):
        """The renderer's preamble loads `tikz` and no library, so a
        scaffold that relies on `positioning`/`matrix`/`fit` and does
        not load it fails the whole render rather than just itself."""
        assert "\\usetikzlibrary{" in scaffold.read_text(encoding="utf-8")

    @by_carrier
    def test_names_the_nodes_it_draws(self, scaffold):
        """The measurability precondition, checked from source so it
        also holds on a host with no TeX."""
        assert figure_layout.node_names(scaffold.read_text(encoding="utf-8"))

    @by_carrier
    def test_no_node_text_past_the_conciseness_line(self, scaffold):
        source = scaffold.read_text(encoding="utf-8")

        assert figure_layout.overlong_nodes(source) == []


@needs_tikz
class TestEveryGeometryProperty:
    """The half that needs a real `pdflatex`."""

    @by_carrier
    def test_compiles_and_measures_every_name_it_declares(self, scaffold):
        """Zero findings, earned rather than vacuous -- see this
        module's docstring."""
        source = scaffold.read_text(encoding="utf-8")
        boxes = figure_layout.node_boxes(scaffold)
        measured = set(boxes) - {figure_layout.BBOX_NAME}

        assert measured == set(figure_layout.node_names(source))

    @by_carrier
    def test_no_two_nodes_collide(self, scaffold):
        assert figure_layout.overlaps(figure_layout.node_boxes(scaffold)) == []

    @by_carrier
    def test_nothing_protrudes(self, scaffold):
        assert figure_layout.protrudes(figure_layout.node_boxes(scaffold)) is False


@needs_tikz
class TestThroughTheDocumentedCommand:
    """One scaffold checked the way an author actually reaches it.

    Everything above calls the library's own functions. This goes
    through `check_draft()`, which is what
    `python -m chitragupta.review figure <draft>` runs -- and which
    resolves a figure only *beside the draft that marks it*, so a
    scaffold is reached by being copied into a draft's `figures/`
    directory, exactly as assets/tikz/README.md tells an author to.
    """

    def test_a_draft_that_starts_from_a_scaffold_reports_no_finding(self, tmp_path):
        figures = tmp_path / "figures"
        figures.mkdir()
        shutil.copy(SCAFFOLD_DIR / "pipeline.tex", figures / "flow.tex")
        draft = tmp_path / "survey.md"
        draft.write_text("Prose.\n\n<!-- figure: figures/flow -->\n", encoding="utf-8")

        results = figure_layout.check_draft(draft)

        assert len(results) == 1
        assert results[0].skipped == ""
        # `has_findings` now carries the whole criterion, because #405
        # put "nothing was measurable" inside it. Before that this had to
        # additionally assert that every declared name came back measured
        # -- the aid could not tell a clean figure from an unmeasured
        # one, so every caller had to make the distinction for itself.
        assert results[0].has_findings is False
        assert results[0].unmeasured == []


class TestTheBlockTravelsUnforked:
    """#1012's acceptance: the block is byte-identical in every file
    carrying it, because the first edit to one copy is otherwise
    invisible until two figures in one book disagree."""

    def test_there_is_more_than_one_carrier(self):
        """The non-vacuous guard: an empty glob passes every check below."""
        assert len(_scaffolds()) > 1 and len(_carriers()) > len(_scaffolds())

    def test_the_block_file_is_exactly_its_own_region(self):
        """Nothing outside the markers, so a copy of the region is a copy
        of the whole file and `figure sync` (#1013) has one thing to stamp."""
        text = BLOCK.read_text(encoding="utf-8")

        assert _region(text) == text

    @by_carrier
    def test_carries_the_block_once_and_verbatim(self, scaffold):
        text = scaffold.read_text(encoding="utf-8")

        assert text.count(_REGION_START) == 1
        assert _region(text) == BLOCK.read_text(encoding="utf-8")

    def test_a_one_value_edit_is_caught(self):
        """The shape this guard exists for, fed to it: one corner radius
        changed inside a copy, everything else intact."""
        text = (SCAFFOLD_DIR / "pipeline.tex").read_text(encoding="utf-8")
        forked = text.replace("rounded corners=3pt", "rounded corners=2pt", 1)

        assert forked != text
        assert _region(forked) != BLOCK.read_text(encoding="utf-8")


# A colour no figure uses, given to everything set in math mode, so the
# PDF reader can tell TeX's script style -- the one size the type floor
# exempts -- from text that was shrunk.
_MATH_RGB = (1, 2, 3)


def _pdflatex(directory: Path, body: str) -> subprocess.CompletedProcess:
    """Compile `body` inside the minimal document WRITING-STANDARDS.md
    §10 tells an author to probe a figure with, plus the math marker."""
    (directory / "probe.tex").write_text(
        "\\documentclass{article}\n\\usepackage{tikz}\n\\pagestyle{empty}\n"
        "\\everymath\\expandafter{\\the\\everymath\\color[RGB]{%d,%d,%d}}\n"
        % _MATH_RGB
        + f"\\begin{{document}}\n{body}\n\\end{{document}}\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [shutil.which("pdflatex"), "-interaction=nonstopmode", "-halt-on-error", "probe.tex"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )


@needs_tikz
class TestTheBlockTypesetsNothing:
    """`\\input` of the block adds no material to the page, and `\\input`
    of a figure adds nothing beyond its picture.

    A line ending after `}` is a space token, and in horizontal mode a
    space has width. The block as first drafted set fifteen of them, 50pt
    of blank to the left of any picture `\\input` beside text. A figure
    float starts in vertical mode and drops them, which is why nothing
    showed; a `standalone` preview or an inline `\\input` does not.
    """

    @staticmethod
    def _width(directory: Path, source: Path) -> str:
        result = _pdflatex(
            directory, f"\\setbox0\\hbox{{\\input{{{source}}}}}\\typeout{{CGWIDTH=\\the\\wd0}}"
        )
        assert result.returncode == 0, result.stdout[-2000:]
        return re.search(r"CGWIDTH=(\S+)", result.stdout).group(1)

    def test_the_block_is_zero_width(self, tmp_path):
        assert self._width(tmp_path, BLOCK) == "0.0pt"

    @by_carrier
    def test_a_whole_figure_sets_only_its_picture(self, scaffold, tmp_path):
        """The same property for everything around the block: the
        `\\usetikzlibrary` line and the picture's own last line end in
        `%`, so `\\input` of the file is exactly as wide as the picture
        alone. Libraries and block are loaded first, outside the boxes,
        so the bare picture can compile on its own."""
        source = scaffold.read_text(encoding="utf-8")
        # After the block, whose comments mention `\\begin{tikzpicture}[cg]`.
        start = source.index("\\begin{tikzpicture}", source.index(_REGION_END))
        end = source.rindex("\\end{tikzpicture}") + len("\\end{tikzpicture}")
        bare = tmp_path / "bare.tex"
        # The `%` stops the bare file's own last line setting a space.
        bare.write_text(source[start:end] + "%", encoding="utf-8")
        libraries = "arrows.meta,positioning,fit,backgrounds,calc,shadows.blur,matrix,trees"
        result = _pdflatex(
            tmp_path,
            f"\\usetikzlibrary{{{libraries}}}\\input{{{BLOCK}}}%\n"
            f"\\setbox0\\hbox{{\\input{{{scaffold}}}}}\\typeout{{CGFULL=\\the\\wd0}}%\n"
            f"\\setbox0\\hbox{{\\input{{{bare}}}}}\\typeout{{CGBARE=\\the\\wd0}}%",
        )
        assert result.returncode == 0, result.stdout[-2000:]

        full = re.search(r"CGFULL=(\S+)", result.stdout).group(1)
        assert full == re.search(r"CGBARE=(\S+)", result.stdout).group(1)

    def test_the_probe_sees_a_stray_space(self, tmp_path):
        """The probe against the exact shape it was written for: one
        colour line with its comment set off by spaces, as drafted."""
        stray = tmp_path / "stray.tex"
        stray.write_text("\\definecolor{cgInk}{HTML}{1A1A1A}     % ink\n", encoding="utf-8")

        assert self._width(tmp_path, stray) != "0.0pt"


class _Glyph(NamedTuple):
    size: float  # printed size, in points
    in_math: bool
    x: float  # the glyph's origin on the page, in points
    y: float


def _effective_sizes(pdf_path: Path, page: int) -> list[_Glyph]:
    """Every glyph on `page`, with its printed size and where it sits.

    pdfium's own font size is the size the font was *selected* at, which
    is blind to a `\\resizebox`: that arrives as a transformation matrix,
    not as a font change. Each glyph's matrix carries it, so the printed
    size is the font size times the matrix's linear scale.
    """
    pdfium = pytest.importorskip("pypdfium2")
    raw = pytest.importorskip("pypdfium2.raw")
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        text = document[page].get_textpage()
        sizes = []
        for index in range(text.count_chars()):
            if (
                raw.FPDFText_IsGenerated(text.raw, index)
                or chr(raw.FPDFText_GetUnicode(text.raw, index)).isspace()
            ):
                continue
            matrix = raw.FS_MATRIX()
            raw.FPDFText_GetMatrix(text.raw, index, ctypes.byref(matrix))
            scale = math.sqrt(abs(matrix.a * matrix.d - matrix.b * matrix.c))
            rgba = [ctypes.c_uint() for _ in range(4)]
            raw.FPDFText_GetFillColor(text.raw, index, *(ctypes.byref(part) for part in rgba))
            in_math = tuple(part.value for part in rgba[:3]) == _MATH_RGB
            size = raw.FPDFText_GetFontSize(text.raw, index) * scale
            sizes.append(_Glyph(size, in_math, matrix.e, matrix.f))
        return sizes
    finally:
        document.close()


# Rounding slack only. pdfium reports sizes in big points and a matrix
# that has been through pdfTeX's decimal output, so equal sizes can
# differ in the fourth figure; a real step down the ramp is 1pt or more.
_SIZE_TOLERANCE = 0.01

# TeX's script style at a 10pt body is 7pt: the exemption, as a ratio.
_SCRIPT_RATIO = 0.7


def _floor_ratios(floor: float, glyphs: list[_Glyph]) -> list[float]:
    """Each glyph's size as a fraction of the floor it answers to.

    A math glyph answers to the script floor only when it hangs off a
    full-size math glyph, within one body size across and up or down,
    which is what a subscript or an exponent does. Math that is small
    throughout -- `\\scriptsize $k$` -- has nothing to hang off, so it
    answers to the body size like any other text.
    """

    def attached(glyph: _Glyph) -> bool:
        return any(
            other.in_math
            and other.size >= floor - _SIZE_TOLERANCE
            and abs(other.x - glyph.x) <= floor
            and abs(other.y - glyph.y) <= floor
            for other in glyphs
        )

    return [
        glyph.size / (floor * (_SCRIPT_RATIO if glyph.in_math and attached(glyph) else 1))
        for glyph in glyphs
    ]


@needs_tikz
class TestTheTypeFloor:
    """Nothing in a figure prints smaller than the paragraph beside it.

    Body text on page 1 is the reference, measured from the same PDF so
    no number here depends on a class or a unit; the figure alone is on
    page 2. A subscript or exponent may drop to TeX's own script size,
    the exemption #1012 names, and no further; every other glyph, math
    included, is held to the body size itself.
    """

    @staticmethod
    def _floor_and_figure(directory: Path, figure: str) -> tuple[float, list[float]]:
        """The body size, and each figure glyph's size as a fraction of
        the floor it answers to (1.0 is exactly on it)."""
        result = _pdflatex(directory, f"Body text.\n\\clearpage\n{figure}")
        assert result.returncode == 0, result.stdout[-2000:]
        pdf = directory / "probe.pdf"
        floor = min(glyph.size for glyph in _effective_sizes(pdf, 0))
        return floor, _floor_ratios(floor, _effective_sizes(pdf, 1))

    @by_carrier
    def test_no_glyph_is_set_below_the_body_size(self, scaffold, tmp_path):
        _, sizes = self._floor_and_figure(
            tmp_path, f"\\begin{{center}}\\input{{{scaffold}}}\\end{{center}}"
        )

        assert sizes, "the figure printed no text, so the floor was never tested"
        assert min(sizes) >= 1 - _SIZE_TOLERANCE

    def test_the_floor_holds_inside_a_smaller_group(self, tmp_path):
        """`[cg]` sets `\\normalsize` as a picture option rather than
        inheriting it, so a figure input inside `\\small` keeps its size."""
        figure = SCAFFOLD_DIR / "pipeline.tex"
        _, sizes = self._floor_and_figure(tmp_path, f"{{\\small\\input{{{figure}}}}}")

        assert min(sizes) >= 1 - _SIZE_TOLERANCE

    def test_a_resizebox_in_the_draft_is_caught(self, tmp_path):
        """The case reading the source cannot see: the figure file is
        clean and the scaling lives in the document that inputs it."""
        figure = SCAFFOLD_DIR / "pipeline.tex"
        _, sizes = self._floor_and_figure(
            tmp_path, f"\\resizebox{{0.6\\textwidth}}{{!}}{{\\input{{{figure}}}}}"
        )

        assert min(sizes) < 1 - _SIZE_TOLERANCE

    def test_a_subscript_is_exempt_and_shrunk_math_is_not(self, tmp_path):
        """The exemption is TeX's script style, not math as such: a
        subscript passes, and math set inside `\\scriptsize` does not --
        with a subscript or without one, so the small base glyph is what
        fails rather than an even smaller subscript beside it."""
        _, subscript = self._floor_and_figure(tmp_path, "\\tikz\\node{$k_1$};")
        _, shrunk = self._floor_and_figure(tmp_path, "\\tikz\\node{\\scriptsize $k$};")
        _, shrunk_sub = self._floor_and_figure(tmp_path, "\\tikz\\node{\\scriptsize $k_1$};")

        assert min(subscript) >= 1 - _SIZE_TOLERANCE
        assert min(shrunk) < 1 - _SIZE_TOLERANCE
        assert min(shrunk_sub) < 1 - _SIZE_TOLERANCE

    def test_a_shrunk_label_in_the_figure_is_caught(self, tmp_path):
        """The common case, through the same reader."""
        shrunk = tmp_path / "shrunk.tex"
        source = (SCAFFOLD_DIR / "pipeline.tex").read_text(encoding="utf-8")
        shrunk.write_text(
            source.replace("{\\cglab{Serve}{answers}}", "{\\scriptsize serve}"), encoding="utf-8"
        )
        _, sizes = self._floor_and_figure(tmp_path, f"\\input{{{shrunk}}}")

        assert min(sizes) < 1 - _SIZE_TOLERANCE


@needs_tikz
class TestEveryPicFitsItsWell:
    """#1014: a `pic` is drawn into a `cgwell`, and a zone card `fit`s
    the well, not the `pic`. A `pic` that outgrows its well therefore
    pokes through its own zone card and nothing measures it, because a
    path has no name. `cgdocs` as #1026 shipped it did exactly that,
    0.92mm through the top."""

    @staticmethod
    def _extents(directory: Path, names: list[str], extra: str = "") -> dict:
        """Each `pic`'s ink box in mm, origin at the well's centre.
        `current bounding box` includes half the stroke width."""
        body = "".join(
            f"\\begin{{tikzpicture}}[cg]\\pic{{{name}}};"
            "\\pgfpointanchor{current bounding box}{south west}\\pgfgetlastxy\\cgxa\\cgya"
            "\\pgfpointanchor{current bounding box}{north east}\\pgfgetlastxy\\cgxb\\cgyb"
            f"\\typeout{{CGPIC {name} \\cgxa\\space\\cgya\\space\\cgxb\\space\\cgyb}}"
            "\\end{tikzpicture}\n"
            for name in names
        )
        result = _pdflatex(
            directory, f"\\usetikzlibrary{{{_LIBRARIES}}}\\input{{{BLOCK}}}{extra}\n{body}"
        )
        assert result.returncode == 0, result.stdout[-2000:]
        return {
            m.group(1): tuple(float(v) / _PT_PER_MM for v in m.groups()[1:])
            for m in _CGPIC_RE.finditer(result.stdout)
        }

    @staticmethod
    def _inside_the_well(box: tuple) -> bool:
        match = _WELL_RE.search(BLOCK.read_text(encoding="utf-8"))
        half_w, half_h = float(match["w"]) / 2, float(match["h"]) / 2
        x0, y0, x1, y1 = box
        return -half_w <= x0 and x1 <= half_w and -half_h <= y0 and y1 <= half_h

    def test_there_are_pics_to_measure(self):
        """The non-vacuous guard: a regex that stops matching makes every
        check below pass on an empty list."""
        assert len(_pics()) > 1 and _WELL_RE.search(BLOCK.read_text(encoding="utf-8"))

    def test_every_pic_is_measured_and_fits(self, tmp_path):
        extents = self._extents(tmp_path, _pics())

        assert set(extents) == set(_pics())
        assert [n for n, box in extents.items() if not self._inside_the_well(box)] == []

    def test_the_probe_sees_an_oversize_pic(self, tmp_path):
        """The probe against the shape it exists to catch."""
        oversize = (
            "\\tikzset{pics/cgoversize/.style={code={"
            "\\path[draw] (-6mm,-6mm) rectangle (6mm,6mm);}}}"
        )
        extents = self._extents(tmp_path, ["cgoversize"], oversize)

        assert not self._inside_the_well(extents["cgoversize"])

    def test_a_pic_colour_does_not_leak_to_the_next_pic(self, tmp_path):
        """`cg pic colour` is set per `\\pic`, so the next un-keyed one in
        the same picture is the default again, not the last zone's hue."""
        result = _pdflatex(
            tmp_path,
            f"\\usetikzlibrary{{{_LIBRARIES}}}\\input{{{BLOCK}}}\n"
            "\\begin{tikzpicture}[cg]\\pic[cg pic colour=cgAlt]{cgstore};"
            "\\typeout{CGCOL=\\cgPicColour}\\end{tikzpicture}",
        )

        assert result.returncode == 0, result.stdout[-2000:]
        assert "CGCOL=cgFlow" in result.stdout


@needs_tikz
class TestDrawnAtFinalWidth:
    """Every scaffold fits the article class's text width as drawn, so it
    is `\\input` bare and never scaled. The exemplars are laid out to a
    wider page (acmart's 506pt, stated in each one's header) and are not
    held to this one."""

    @by_scaffold
    def test_fits_the_text_width_unscaled(self, scaffold, tmp_path):
        result = _pdflatex(tmp_path, f"\\begin{{center}}\\input{{{scaffold}}}\\end{{center}}")

        assert result.returncode == 0, result.stdout[-2000:]
        assert "Overfull \\hbox" not in (tmp_path / "probe.log").read_text(
            encoding="utf-8", errors="replace"
        )
