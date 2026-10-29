"""What `chitragupta figure check` finds in one figure file (#1053).

One compile, through `review figure`'s own probe in its boxed form
(`review/figure_layout/_probe.py` has why the box and the preload go
together), then every rule in `_rules.RULES`: the three this command
adds, and `review figure`'s seven findings under the ids its JSON
already ships. Then the figure's own `% cg-allow:` lines are applied.

**It measures; it never places**, for the reason
`review/figure_layout/__init__.py` gives: every number here is read
back from what TikZ decided, and the fix for a finding is to change
what the figure asks TikZ for.

The thresholds are this module's: TeX's own `\\hfuzz` for width, and
half a point for stray space, which is rounding rather than a space
(an interword space at 12pt is about 4pt).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta._tex_comments import strip_comments
from chitragupta.figure._advisory import advise
from chitragupta.figure._allow import Allow, Malformed, parse_allows

from chitragupta.figure._connector_check import CONNECTOR, connector_rules
from chitragupta.figure._connectors import connectors
from chitragupta.figure._contrast import CONTRAST, contrast_check
from chitragupta.figure._focal import cgkey_nodes
from chitragupta.figure._layout import declared_layout, reference
from chitragupta.figure._overlap import drawn_overlaps
from chitragupta.figure._rules import RULES, Finding
from chitragupta.figure._wording import wording_rules
from chitragupta.review.figure_layout import (
    BBOX_NAME,
    MAX_NODE_WORDS,
    FigureResult,
    check_figure,
)

# The render's text width: A4 (8.27in) less two 1in margins, at
# 72.27pt/in, for `render_output.render`'s `a4` and `1in` defaults. A
# test pins it to those defaults. Part X (output targets) replaces it.
DEFAULT_WIDTH_PT = 453.0

# A figure-scope finding's target: the rule is about the whole picture.
FIGURE = "figure"

_HFUZZ_PT = 0.1
_STRAY_PT = 0.5

# The rules that need the compiled geometry, listed as not measured
# whenever it is missing, so their silence is never read as a pass.
GEOMETRY = (
    "nothing-measurable",
    "size-width",
    "size-stray",
    "content-protrusion",
    "node-overlap",
    *CONNECTOR,
    *CONTRAST,
)

# Why the geometry is missing. The probe sits inside the figure's last
# `tikzpicture` environment, so a file with none (a bare `\tikz`, say)
# has nowhere to put it and is not compiled at all, rather than reported
# as a compile failure that is the probe's, not the figure's. A picture
# whose only `\end{tikzpicture}` sits in a macro body that never runs
# compiles and prints no extent.
NO_PICTURE = "the file has no tikzpicture environment to measure"
NO_EXTENT = "the picture's extent was not printed (is its last tikzpicture inside a macro?)"
_NOT_COMPILED = "the figure does not compile"

_PICTURE_RE = re.compile(r"\\begin\s*\{tikzpicture\}")


@dataclass
class CheckResult:
    """One file's report. `allowed` pairs each honoured allow with the
    measurement it suppressed, or `None` where its rule did not fire;
    `not_measured` pairs a rule with why it could not run. `figure` is
    kept for the diagnostics the report prints beside the findings.
    `advisory` is #1057's size reports, kept out of `findings` because
    nothing is to be resolved or allowed about them, and `layout` the
    name they were read against (`""` for none)."""

    path: Path
    width_pt: float
    figure: FigureResult
    # Stroked lines the connector rules did not check, because they do
    # not run between two nodes; `None` where nothing was drawn.
    loose_lines: int | None = None
    findings: list[Finding] = field(default_factory=list)
    allowed: list[tuple[Allow, str | None]] = field(default_factory=list)
    deferred: list[Allow] = field(default_factory=list)
    malformed: list[Malformed] = field(default_factory=list)
    not_measured: list[tuple[str, str]] = field(default_factory=list)
    advisory: list[Finding] = field(default_factory=list)
    layout: str = ""


def check(path: Path, width_pt: float, layout: str = "") -> CheckResult:
    """Compile `path` once, unless it has no picture to measure, and
    report every rule. The caller has already established that this
    host has `lualatex` and `tikz.sty`, and that `path` reads as UTF-8."""
    source = path.read_text(encoding="utf-8")  # pragma: no cover-windows
    skipped = "" if _pictures(source) else NO_PICTURE  # pragma: no cover-windows
    figure = check_figure(path, skipped, boxed=True)  # pragma: no cover-windows
    return apply(path, width_pt, figure, source, layout)  # pragma: no cover-windows


def apply(
    path: Path, width_pt: float, figure: FigureResult, source: str, layout: str = ""
) -> CheckResult:
    """Every rule over an already-checked figure, with its allows applied.

    Each allow is matched against everything that fired, so two allows
    for one rule both report what they set aside. `layout` overrides the
    figure's own `% cg-layout:` line."""
    layout = layout or declared_layout(source)
    fired, not_measured = evaluate(source, figure, width_pt, layout)
    advisory, unmeasured = advise(
        figure, source, layout, reference(layout), _unmeasurable(source, figure)
    )
    advisory += wording_rules(source)[1]
    allows = parse_allows(source)
    allowed = [
        (allow, "; ".join(f.measurement for f in fired if f.rule == allow.rule) or None)
        for allow in allows.honoured
    ]
    excused = {allow.rule for allow in allows.honoured}
    findings = [finding for finding in fired if finding.rule not in excused]
    loose = len(connectors(figure.drawn)[1]) if figure.drawn else None
    return CheckResult(
        path,
        width_pt,
        figure,
        loose,
        findings,
        allowed,
        allows.deferred,
        allows.malformed,
        not_measured + unmeasured,
        advisory,
        layout,
    )


def evaluate(
    source: str, figure: FigureResult, width_pt: float, layout: str = ""
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """`(findings, not_measured)`, the findings in `RULES` order. `layout`
    is the one the connector rules' exemptions read; `""` reads the
    figure's own `% cg-layout:` line."""
    findings: list[Finding] = []
    if figure.failed:
        findings.append(Finding("does-not-compile", FIGURE, figure.failed))
    missing = _missing(figure)
    not_measured = [(rule, missing) for rule in GEOMETRY] if missing else []
    if not missing:
        findings, not_measured = _size(source, figure, width_pt)
        findings += _geometry(figure)
        connected, unmeasured = connector_rules(
            source, figure, layout or declared_layout(source), _pictures(source)
        )
        findings += connected
        not_measured += unmeasured
        contrasted, unmeasured = contrast_check(source, figure, _pictures(source))
        findings += contrasted
        not_measured += unmeasured
    findings += _focal(source) + _static(figure) + wording_rules(source)[0]
    order = list(RULES)
    return sorted(findings, key=lambda finding: order.index(finding.rule)), not_measured


def _missing(figure: FigureResult) -> str:
    """Why the compiled geometry cannot be read, or `""` where it can."""
    if figure.failed:
        return _NOT_COMPILED
    if figure.boxes is None:
        return figure.skipped
    if BBOX_NAME not in figure.boxes or figure.input_width is None:
        return NO_EXTENT
    return ""


def _unmeasurable(source: str, figure: FigureResult) -> str:
    """Why #1057's size reports cannot read the boxes, or `""`. The probe
    reads the last picture's extent, and an earlier picture's nodes sit
    in another picture's frame, so several pictures are not measured."""
    pictures = _pictures(source)
    if pictures > 1 and not _missing(figure):
        return f"{pictures} tikzpictures; only the last one's extent is read"
    return _missing(figure)


def _pictures(source: str) -> int:
    return len(_PICTURE_RE.findall(strip_comments(source)))


def _size(
    source: str, figure: FigureResult, width_pt: float
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """`size-width` and `size-stray`.

    One picture is measured by its own bounding box. Several are what a
    reader sees side by side, so their width is the whole box, and the
    box's extra width is their spacing rather than stray space.
    """
    pictures = _pictures(source)
    x1, _, x2, _ = figure.boxes[BBOX_NAME]
    picture = x2 - x1
    found, not_measured = [], []
    width, whole = (
        (figure.input_width, f" (whole input, {pictures} pictures)")
        if pictures > 1
        else (picture, "")
    )
    if width > width_pt + _HFUZZ_PT:
        found.append(
            Finding("size-width", FIGURE, f"{width:.1f}pt wide{whole}, target {width_pt:.1f}pt")
        )
    if pictures > 1:
        not_measured.append(
            ("size-stray", f"{pictures} tikzpictures; panels and their spacing are not stray")
        )
    elif figure.input_width - picture > _STRAY_PT:
        stray = figure.input_width - picture
        found.append(
            Finding(
                "size-stray",
                FIGURE,
                f"{stray:.1f}pt stray (input {figure.input_width:.1f}pt, picture {picture:.1f}pt)",
            )
        )
    return found, not_measured


def _focal(source: str) -> list[Finding]:
    """`focal-count`: at most one `cgkey` node (`_focal.py`)."""
    keyed = cgkey_nodes(source)
    if len(keyed) < 2:
        return []
    return [Finding("focal-count", FIGURE, f"{len(keyed)} cgkey nodes: {', '.join(keyed)}")]


def _geometry(figure: FigureResult) -> list[Finding]:
    """`review figure`'s findings that need the compiled boxes."""
    found = []
    if figure.nothing_measurable:
        found.append(
            Finding("nothing-measurable", FIGURE, "names no node, so nothing was measured")
        )
    if figure.protruding:
        found.append(Finding("content-protrusion", FIGURE, "content protrudes past the main block"))
    # Every drawn node where the probe logged them (#1054), so unnamed
    # text such as a zone title is measured; the named ones otherwise.
    pairs = drawn_overlaps(figure.drawn) if figure.drawn else figure.overlapping
    found += [Finding("node-overlap", f"{one}+{other}", "boxes intersect") for one, other in pairs]
    return found


def _static(figure: FigureResult) -> list[Finding]:
    """`review figure`'s findings read from source, under the ids its
    JSON ships; they hold whether or not the figure compiled."""
    found = []
    if figure.by_hand:
        found.append(Finding("loads-library-by-hand", FIGURE, ", ".join(figure.by_hand)))
    found += [
        Finding("node-text-overload", name, f"{count} words (over {MAX_NODE_WORDS})")
        for name, count in figure.overlong
    ]
    found += [
        Finding("stranded-arrowhead", f"({point})", "arrowhead lands mid-line")
        for point in figure.stranded
    ]
    return found
