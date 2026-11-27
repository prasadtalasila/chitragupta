import ctypes
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from chitragupta.figure._advisory import slack
from chitragupta.figure._check import check
from chitragupta.page import ARTICLE
from chitragupta.figure._layout import LAYOUT_DIR, RangeRow, declared_layout, range_rows
from chitragupta.figure._twin import agree
from chitragupta.review import figure_layout
from tests.conftest import needs_tikz

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_DIR = REPO_ROOT / "assets" / "tikz"
EXEMPLAR_DIR = SCAFFOLD_DIR / "exemplars"
STYLE_DOC = REPO_ROOT / "docs" / "TIKZ-STYLE.md"

BLOCK = SCAFFOLD_DIR / "cg-figstyle.tex"
_REGION_START = "% >>> chitragupta figure style v"
_REGION_END = "% >>> end chitragupta figure style <<<\n"

_TABLE_HEADER = "| Metaphor | TikZ idiom |"
_ROW_RE = re.compile(r"^\|\s*(?P<metaphor>[^|]+?)\s*\|\s*(?P<idiom>[^|]+?)\s*\|$")


def _metaphors() -> list[str]:
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
    return re.sub(r"[^a-z0-9]+", "-", metaphor.lower()).strip("-")


def _scaffolds() -> list[Path]:
    return sorted(path for path in SCAFFOLD_DIR.glob("*.tex") if path != BLOCK)


def _carriers() -> list[Path]:
    return _scaffolds() + sorted(EXEMPLAR_DIR.glob("*.tex"))


def _region(text: str) -> str | None:
    start = text.find(_REGION_START)
    end = text.find(_REGION_END, start)
    if start < 0 or end < 0:
        return None
    return text[start : end + len(_REGION_END)]


_WELL_RE = re.compile(
    r"cgwell/\.style=\{[^}]*minimum width=(?P<w>[\d.]+)mm, minimum height=(?P<h>[\d.]+)mm"
)
_PIC_RE = re.compile(r"pics/(?P<name>\w+)/\.style=")
_PT_PER_MM = 72.27 / 25.4
_CGPIC_RE = re.compile(r"CGPIC (\S+) (-?[\d.]+)pt (-?[\d.]+)pt (-?[\d.]+)pt (-?[\d.]+)pt")
_LIBRARIES = "arrows.meta,positioning,fit,backgrounds,calc,shadows.blur"


def _pics() -> list[str]:
    return _PIC_RE.findall(BLOCK.read_text(encoding="utf-8"))


def _pics_overriding_the_join(source: str) -> list[str]:
    starts = list(_PIC_RE.finditer(source))
    ends = [m.start() for m in starts[1:]] + [len(source)]
    return [m["name"] for m, end in zip(starts, ends) if "line join" in source[m.start() : end]]


_PIC_TABLE_HEADER = "| `pic` | Stands for | Twin says |"
_PIC_ROW_RE = re.compile(r"^\|\s*`(?P<name>\w+)`\s*\|")


def _documented_pics() -> list[str]:
    lines = STYLE_DOC.read_text(encoding="utf-8").splitlines()
    start = lines.index(_PIC_TABLE_HEADER) + 2
    found = []
    for line in lines[start:]:
        match = _PIC_ROW_RE.match(line)
        if match is None:
            break
        found.append(match.group("name"))
    return found


by_scaffold = pytest.mark.parametrize("scaffold", _scaffolds(), ids=lambda p: p.stem)
by_carrier = pytest.mark.parametrize("scaffold", _carriers(), ids=lambda p: p.stem)


class TestMetaphorCoverage:
    def test_the_table_was_actually_read_past_its_first_row(self):
        assert len(_metaphors()) > 1

    def test_every_metaphor_has_a_scaffold(self):
        missing = [m for m in _metaphors() if not (SCAFFOLD_DIR / f"{_slug(m)}.tex").exists()]

        assert missing == []

    def test_no_scaffold_names_a_metaphor_the_doc_dropped(self):
        expected = {_slug(m) for m in _metaphors()}

        assert {path.stem for path in _scaffolds()} == expected


REFERENCES = REPO_ROOT / ".claude" / "skills" / "figure-drawer" / "references"
PATTERNS = REFERENCES / "patterns.md"
SKILL_COPIES = [
    REPO_ROOT / ".claude" / "skills" / "figure-drawer" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "figure-drawer" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "figure-drawer-opencode" / "SKILL.md",
]

_PATTERN_LINK_RE = re.compile(r"\]\(layouts/(?P<slug>[\w-]+)\.md\)")

_TEXT_WIDTH_PT = ARTICLE.text_width_pt
_TEXT_HEIGHT_PT = ARTICLE.text_height_pt
_FRACTION_TOLERANCE = 0.02


def _layout_file(slug: str) -> Path:
    return LAYOUT_DIR / f"{slug}.md"


def _all_range_rows() -> list[RangeRow]:
    return [
        row
        for path in sorted(LAYOUT_DIR.glob("*.md"))
        for row in range_rows(path.read_text(encoding="utf-8"))
    ]


def _counted(source: Path) -> tuple[int, int]:
    text = source.read_text(encoding="utf-8")
    return len(figure_layout.node_names(text)), len(figure_layout.edge_list(text))


def _measured(source: Path) -> tuple[float, float, float]:
    boxes = figure_layout.node_boxes(source)
    bx1, by1, bx2, by2 = boxes[figure_layout.BBOX_NAME]
    return (bx2 - bx1) / _TEXT_WIDTH_PT, (by2 - by1) / _TEXT_HEIGHT_PT, slack(boxes)


def _count_mismatch(row: RangeRow) -> str | None:
    nodes, edges = _counted(REPO_ROOT / row.source)
    if (nodes, edges) == (row.nodes, row.edges):
        return None
    return f"{row.source}: written {row.nodes} nodes, {row.edges} edges; measured {nodes}, {edges}"


def _extent_mismatch(row: RangeRow) -> str | None:
    measured = _measured(REPO_ROOT / row.source)
    written = (row.width, row.height, row.slack)
    if all(abs(a - b) <= _FRACTION_TOLERANCE for a, b in zip(written, measured)):
        return None
    shown = " | ".join(f"{value:.2f}" for value in measured)
    return f"{row.source}: written {written}; measured | {shown} |"


class TestEveryLayoutHasAReferenceFile:
    def test_every_metaphor_has_a_reference_file(self):
        missing = [m for m in _metaphors() if not _layout_file(_slug(m)).exists()]

        assert missing == []

    def test_no_reference_file_for_a_layout_the_doc_dropped(self):
        assert {path.stem for path in LAYOUT_DIR.glob("*.md")} == {_slug(m) for m in _metaphors()}

    @pytest.mark.parametrize("metaphor", _metaphors(), ids=_slug)
    def test_each_file_states_its_anti_patterns(self, metaphor):
        text = _layout_file(_slug(metaphor)).read_text(encoding="utf-8")

        assert "\n## Anti-patterns\n\n- " in text

    @pytest.mark.parametrize("metaphor", _metaphors(), ids=_slug)
    def test_each_file_measures_its_own_scaffold(self, metaphor):
        rows = range_rows(_layout_file(_slug(metaphor)).read_text(encoding="utf-8"))

        assert f"assets/tikz/{_slug(metaphor)}.tex" in [row.source for row in rows]

    def test_every_exemplar_is_measured_under_exactly_one_layout(self):
        sources = [row.source for row in _all_range_rows()]
        exemplars = [path.relative_to(REPO_ROOT).as_posix() for path in EXEMPLAR_DIR.glob("*.tex")]

        assert exemplars
        assert sorted(s for s in sources if s in exemplars) == sorted(exemplars)

    def test_patterns_route_to_every_layout_and_only_to_layouts(self):
        routed = set(_PATTERN_LINK_RE.findall(PATTERNS.read_text(encoding="utf-8")))

        assert routed == {_slug(m) for m in _metaphors()}

    def test_the_style_doc_points_at_the_routing(self):
        text = STYLE_DOC.read_text(encoding="utf-8")

        assert ".claude/skills/figure-drawer/references/patterns.md" in text
        assert ".claude/skills/figure-drawer/references/layouts/" in text

    @pytest.mark.parametrize("skill", SKILL_COPIES, ids=lambda p: p.parent.parent.parent.name)
    def test_every_harness_copy_points_at_the_routing(self, skill):
        text = skill.read_text(encoding="utf-8")

        assert ".claude/skills/figure-drawer/references/patterns.md" in text


class TestEveryReferenceFigureDeclaresItsLayout:
    @pytest.mark.parametrize("metaphor", _metaphors(), ids=_slug)
    def test_each_scaffold_declares_its_own_layout(self, metaphor):
        source = (SCAFFOLD_DIR / f"{_slug(metaphor)}.tex").read_text(encoding="utf-8")

        assert declared_layout(source) == _slug(metaphor)

    def test_each_measured_source_declares_the_layout_that_measures_it(self):
        wrong = [
            f"{row.source}: measured under {path.stem}, declares "
            f"{declared_layout((REPO_ROOT / row.source).read_text(encoding='utf-8'))!r}"
            for path in sorted(LAYOUT_DIR.glob("*.md"))
            for row in range_rows(path.read_text(encoding="utf-8"))
            if declared_layout((REPO_ROOT / row.source).read_text(encoding="utf-8")) != path.stem
        ]

        assert wrong == []

    def test_the_layout_directory_is_the_one_the_skill_reads(self):
        assert LAYOUT_DIR.resolve() == (REFERENCES / "layouts").resolve()


class TestTheReferenceRangesAreMeasured:
    def test_the_tables_were_read(self):
        assert len(_all_range_rows()) > len(_metaphors())

    def test_a_doctored_count_is_caught(self):
        row = _all_range_rows()[0]

        assert _count_mismatch(row._replace(nodes=row.nodes + 1)) is not None

    def test_counts_match_the_source(self):
        assert [m for m in map(_count_mismatch, _all_range_rows()) if m] == []

    @pytest.mark.slow
    @needs_tikz
    def test_a_doctored_extent_is_caught(self):
        row = _all_range_rows()[0]

        assert _extent_mismatch(row._replace(slack=row.slack + 0.1)) is not None

    @pytest.mark.slow
    @needs_tikz
    def test_extents_match_the_probe(self):
        assert [m for m in map(_extent_mismatch, _all_range_rows()) if m] == []


class TestTheWellSizeIsStatedOnce:
    def test_the_prose_names_the_well_the_block_draws(self):
        match = _WELL_RE.search(BLOCK.read_text(encoding="utf-8"))
        stated = re.findall(r"(\d+)mm `cgwell`", BLOCK.read_text(encoding="utf-8"))
        stated += re.findall(
            r"fixed-size \((\d+)mm\)", STYLE_DOC.read_text(encoding="utf-8").replace("\n", " ")
        )

        assert len(stated) == 2
        assert set(stated) == {match["w"], match["h"]}


class TestTheShapesAreTheDocumentedOnes:
    def test_the_table_was_read(self):
        assert len(_documented_pics()) > 1

    def test_the_block_and_the_table_name_the_same_pics(self):
        assert _documented_pics() == _pics()

    def test_a_scaffold_draws_one_into_a_well(self):
        drawn = re.compile(
            r"\\node\[cgwell\b[^]]*\]\s*\((?P<well>[\w-]+)\)"
            r"[^\n]*\n\s*\\pic\b[^\n]*at \((?P=well)\)"
        )

        assert [s.stem for s in _scaffolds() if drawn.search(s.read_text(encoding="utf-8"))]


class TestEverySourceProperty:
    @by_carrier
    def test_carries_its_own_usetikzlibrary_line(self, scaffold):
        assert "\\usetikzlibrary{" in scaffold.read_text(encoding="utf-8")

    @by_carrier
    def test_names_the_nodes_it_draws(self, scaffold):
        assert figure_layout.node_names(scaffold.read_text(encoding="utf-8"))

    @by_carrier
    def test_no_node_text_past_the_conciseness_line(self, scaffold):
        source = scaffold.read_text(encoding="utf-8")

        assert figure_layout.overlong_nodes(source) == []

    @by_carrier
    def test_its_ascii_twin_agrees_with_it(self, scaffold):
        twin = scaffold.with_suffix(".txt")
        text = twin.read_bytes().decode("ascii") if twin.is_file() else None

        assert agree(scaffold.read_text(encoding="utf-8"), text, twin.name) == ([], [])
        assert max(len(line) for line in text.splitlines()) <= 72


@pytest.mark.slow
@needs_tikz
class TestEveryGeometryProperty:
    @by_carrier
    def test_compiles_and_measures_every_name_it_declares(self, scaffold):
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


@pytest.mark.slow
@needs_tikz
class TestThroughTheDocumentedCommand:
    def test_a_draft_that_starts_from_a_scaffold_reports_no_finding(self, tmp_path):
        figures = tmp_path / "figures"
        figures.mkdir()
        shutil.copy(SCAFFOLD_DIR / "pipeline.tex", figures / "flow.tex")
        draft = tmp_path / "survey.md"
        draft.write_text("Prose.\n\n<!-- figure: figures/flow -->\n", encoding="utf-8")

        results = figure_layout.check_draft(draft)

        assert len(results) == 1
        assert results[0].skipped == ""
        assert results[0].has_findings is False
        assert results[0].unmeasured == []


@pytest.mark.slow
@needs_tikz
@pytest.mark.parametrize("figure", _carriers(), ids=lambda p: p.stem)
def test_every_asset_passes_every_rule(figure):
    result = check(figure, ARTICLE.text_width_pt)

    assert [(f.rule, f.target) for f in result.findings] == []
    assert result.malformed == []
    assert result.stale == []
    assert [
        (rule, why)
        for rule, why in result.not_measured
        if rule.startswith("c") and not why.startswith("round nodes")
    ] == []


class TestTheBlockTravelsUnforked:
    def test_there_is_more_than_one_carrier(self):
        assert len(_scaffolds()) > 1 and len(_carriers()) > len(_scaffolds())

    def test_the_block_file_is_exactly_its_own_region(self):
        text = BLOCK.read_text(encoding="utf-8")

        assert _region(text) == text

    @by_carrier
    def test_carries_the_block_once_and_verbatim(self, scaffold):
        text = scaffold.read_text(encoding="utf-8")

        assert text.count(_REGION_START) == 1
        assert _region(text) == BLOCK.read_text(encoding="utf-8")

    def test_a_one_value_edit_is_caught(self):
        text = (SCAFFOLD_DIR / "pipeline.tex").read_text(encoding="utf-8")
        forked = text.replace("rounded corners=3pt", "rounded corners=2pt", 1)

        assert forked != text
        assert _region(forked) != BLOCK.read_text(encoding="utf-8")


_MATH_RGB = (1, 2, 3)


def _lualatex(directory: Path, body: str) -> subprocess.CompletedProcess:
    (directory / "probe.tex").write_text(
        "\\documentclass{article}\n\\usepackage{tikz}\n\\pagestyle{empty}\n"
        "\\everymath\\expandafter{\\the\\everymath\\color[RGB]{%d,%d,%d}}\n"
        % _MATH_RGB
        + f"\\begin{{document}}\n{body}\n\\end{{document}}\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [shutil.which("lualatex"), "-interaction=nonstopmode", "-halt-on-error", "probe.tex"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )


class TestALoopKeepsTheHouseArrow:
    def test_the_picture_style_empties_every_loop(self):
        text = BLOCK.read_text(encoding="utf-8")
        start = text.index("  cg/.style={")
        cg = text[start : text.index("\n  },", start)]

        assert "every loop/.style={}" in cg


@pytest.mark.slow
@needs_tikz
class TestTheBlockTypesetsNothing:
    @staticmethod
    def _width(directory: Path, source: Path) -> str:
        result = _lualatex(
            directory, f"\\setbox0\\hbox{{\\input{{{source}}}}}\\typeout{{CGWIDTH=\\the\\wd0}}"
        )
        assert result.returncode == 0, result.stdout[-2000:]
        return re.search(r"CGWIDTH=(\S+)", result.stdout).group(1)

    def test_the_block_is_zero_width(self, tmp_path):
        assert self._width(tmp_path, BLOCK) == "0.0pt"

    @by_carrier
    def test_a_whole_figure_sets_only_its_picture(self, scaffold, tmp_path):
        source = scaffold.read_text(encoding="utf-8")
        start = source.index("\\begin{tikzpicture}", source.index(_REGION_END))
        end = source.rindex("\\end{tikzpicture}") + len("\\end{tikzpicture}")
        bare = tmp_path / "bare.tex"
        bare.write_text(source[start:end] + "%", encoding="utf-8")
        libraries = f"{_LIBRARIES},matrix,trees"
        result = _lualatex(
            tmp_path,
            f"\\usetikzlibrary{{{libraries}}}\\input{{{BLOCK}}}%\n"
            f"\\setbox0\\hbox{{\\input{{{scaffold}}}}}\\typeout{{CGFULL=\\the\\wd0}}%\n"
            f"\\setbox2\\hbox{{\\input{{{bare}}}}}\\typeout{{CGBARE=\\the\\wd2}}%\n"
            "\\box0\\box2",
        )
        assert result.returncode == 0, result.stdout[-2000:]

        full = re.search(r"CGFULL=(\S+)", result.stdout).group(1)
        assert full == re.search(r"CGBARE=(\S+)", result.stdout).group(1)

    def test_the_probe_sees_a_stray_space(self, tmp_path):
        stray = tmp_path / "stray.tex"
        stray.write_text("\\definecolor{cgInk}{HTML}{1A1A1A}     % ink\n", encoding="utf-8")

        assert self._width(tmp_path, stray) != "0.0pt"


class _Glyph(NamedTuple):
    size: float  # printed size, in points
    in_math: bool
    x: float  # the glyph's origin on the page, in points
    y: float


def _effective_sizes(pdf_path: Path, page: int) -> list[_Glyph]:
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


_SIZE_TOLERANCE = 0.01

_SCRIPT_RATIO = 0.7


def _floor_ratios(floor: float, glyphs: list[_Glyph]) -> list[float]:
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


@pytest.mark.slow
@needs_tikz
class TestTheTypeFloor:
    @staticmethod
    def _floor_and_figure(directory: Path, figure: str) -> tuple[float, list[float]]:
        result = _lualatex(directory, f"Body text.\n\\clearpage\n{figure}")
        assert result.returncode == 0, result.stdout[-2000:]
        pdf = directory / "probe.pdf"
        floor = min(glyph.size for glyph in _effective_sizes(pdf, 0))
        return floor, _floor_ratios(floor, _effective_sizes(pdf, 1))

    @staticmethod
    def _largest(directory: Path, figure: str) -> float:
        result = _lualatex(directory, f"Body text.\n\\clearpage\n{figure}")
        assert result.returncode == 0, result.stdout[-2000:]
        pdf = directory / "probe.pdf"
        floor = min(glyph.size for glyph in _effective_sizes(pdf, 0))
        return max(glyph.size for glyph in _effective_sizes(pdf, 1)) / floor

    @by_carrier
    def test_no_glyph_is_set_below_the_body_size(self, scaffold, tmp_path):
        _, sizes = self._floor_and_figure(
            tmp_path, f"\\begin{{center}}\\input{{{scaffold}}}\\end{{center}}"
        )

        assert sizes, "the figure printed no text, so the floor was never tested"
        assert min(sizes) >= 1 - _SIZE_TOLERANCE

    @by_carrier
    def test_no_glyph_is_set_above_the_body_size(self, scaffold, tmp_path):
        largest = self._largest(tmp_path, f"\\begin{{center}}\\input{{{scaffold}}}\\end{{center}}")

        assert largest <= 1 + _SIZE_TOLERANCE

    def test_a_larger_name_is_caught(self, tmp_path):
        largest = self._largest(tmp_path, "\\tikz\\node[font=\\large\\bfseries]{Intake};")

        assert largest > 1 + _SIZE_TOLERANCE

    def test_the_floor_holds_inside_a_smaller_group(self, tmp_path):
        figure = SCAFFOLD_DIR / "pipeline.tex"
        _, sizes = self._floor_and_figure(tmp_path, f"{{\\small\\input{{{figure}}}}}")

        assert min(sizes) >= 1 - _SIZE_TOLERANCE

    def test_a_resizebox_in_the_draft_is_caught(self, tmp_path):
        figure = SCAFFOLD_DIR / "pipeline.tex"
        _, sizes = self._floor_and_figure(
            tmp_path, f"\\resizebox{{0.6\\textwidth}}{{!}}{{\\input{{{figure}}}}}"
        )

        assert min(sizes) < 1 - _SIZE_TOLERANCE

    def test_a_subscript_is_exempt_and_shrunk_math_is_not(self, tmp_path):
        _, subscript = self._floor_and_figure(tmp_path, "\\tikz\\node{$k_1$};")
        _, shrunk = self._floor_and_figure(tmp_path, "\\tikz\\node{\\scriptsize $k$};")
        _, shrunk_sub = self._floor_and_figure(tmp_path, "\\tikz\\node{\\scriptsize $k_1$};")

        assert min(subscript) >= 1 - _SIZE_TOLERANCE
        assert min(shrunk) < 1 - _SIZE_TOLERANCE
        assert min(shrunk_sub) < 1 - _SIZE_TOLERANCE

    def test_a_shrunk_label_in_the_figure_is_caught(self, tmp_path):
        shrunk = tmp_path / "shrunk.tex"
        source = (SCAFFOLD_DIR / "pipeline.tex").read_text(encoding="utf-8")
        shrunk.write_text(
            source.replace("{\\cglab{Serve}{answers}}", "{\\scriptsize serve}"), encoding="utf-8"
        )
        _, sizes = self._floor_and_figure(tmp_path, f"\\input{{{shrunk}}}")

        assert min(sizes) < 1 - _SIZE_TOLERANCE


@needs_tikz
class TestEveryPicFitsItsWell:
    @staticmethod
    def _extents(directory: Path, names: list[str], extra: str = "") -> dict:
        body = "".join(
            f"\\begin{{tikzpicture}}[cg]\\pic{{{name}}};"
            "\\pgfpointanchor{current bounding box}{south west}\\pgfgetlastxy\\cgxa\\cgya"
            "\\pgfpointanchor{current bounding box}{north east}\\pgfgetlastxy\\cgxb\\cgyb"
            f"\\typeout{{CGPIC {name} \\cgxa\\space\\cgya\\space\\cgxb\\space\\cgyb}}"
            "\\end{tikzpicture}\n"
            for name in names
        )
        result = _lualatex(
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
        assert len(_pics()) > 1 and _WELL_RE.search(BLOCK.read_text(encoding="utf-8"))

    def test_every_pic_is_measured_and_fits(self, tmp_path):
        extents = self._extents(tmp_path, _pics())

        assert set(extents) == set(_pics())
        assert [n for n, box in extents.items() if not self._inside_the_well(box)] == []

    def test_the_probe_sees_an_oversize_pic(self, tmp_path):
        oversize = (
            "\\tikzset{pics/cgoversize/.style={code={"
            "\\path[draw] (-6mm,-6mm) rectangle (6mm,6mm);}}}"
        )
        extents = self._extents(tmp_path, ["cgoversize"], oversize)

        assert not self._inside_the_well(extents["cgoversize"])

    def test_no_pic_overrides_the_round_join(self):
        assert _pics_overriding_the_join(BLOCK.read_text(encoding="utf-8")) == []

    def test_the_join_check_sees_a_mitred_pic(self):
        spike = (
            "\\tikzset{pics/cgspike/.style={code={\\path[draw, line join=miter]"
            " (-1mm,0) -- (0,4mm) -- (1mm,0);}}}%\n"
        )

        assert _pics_overriding_the_join(spike) == ["cgspike"]

    def test_a_pic_colour_does_not_leak_to_the_next_pic(self, tmp_path):
        result = _lualatex(
            tmp_path,
            f"\\usetikzlibrary{{{_LIBRARIES}}}\\input{{{BLOCK}}}\n"
            "\\begin{tikzpicture}[cg]\\pic[cg pic colour=cgAlt]{cgstore};"
            "\\typeout{CGCOL=\\cgPicColour}\\end{tikzpicture}",
        )

        assert result.returncode == 0, result.stdout[-2000:]
        assert "CGCOL=cgFlow" in result.stdout


@pytest.mark.slow
@needs_tikz
class TestDrawnAtFinalWidth:
    @by_scaffold
    def test_fits_the_text_width_unscaled(self, scaffold, tmp_path):
        result = _lualatex(tmp_path, f"\\begin{{center}}\\input{{{scaffold}}}\\end{{center}}")

        assert result.returncode == 0, result.stdout[-2000:]
        assert "Overfull \\hbox" not in (tmp_path / "probe.log").read_text(
            encoding="utf-8", errors="replace"
        )

    @pytest.mark.parametrize("exemplar", sorted(EXEMPLAR_DIR.glob("*.tex")), ids=lambda p: p.stem)
    def test_each_exemplar_fits_the_render_width(self, exemplar):
        result = check(exemplar, ARTICLE.text_width_pt)

        assert [f.measurement for f in result.findings if f.rule == "size-width"] == []
        assert "size-width" not in dict(result.not_measured)
