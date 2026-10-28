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
from chitragupta.figure._allow import Allow, Malformed, parse_allows
from chitragupta.figure._rules import RULES
from chitragupta.review.figure_layout import (
    BBOX_NAME,
    MAX_NODE_WORDS,
    FigureResult,
    check_figure,
)
from chitragupta.review.figure_layout._source import _NODE_KEYWORD

# The render's text width: A4 (8.27in) less two 1in margins, at
# 72.27pt/in, for `render_output.render`'s `a4` and `1in` defaults. A
# test pins it to those defaults. Part X (output targets) replaces it.
DEFAULT_WIDTH_PT = 453.0

# A figure-scope finding's target: the rule is about the whole picture.
FIGURE = "figure"

_HFUZZ_PT = 0.1
_STRAY_PT = 0.5

# The rules a figure that does not compile has no geometry for.
_GEOMETRY = ("nothing-measurable", "size-width", "size-stray", "content-protrusion", "node-overlap")

_PICTURE_RE = re.compile(r"\\begin\s*\{tikzpicture\}")

# A node declaration's options, before or after its name -- TikZ takes
# both `\node[opts] (a)` and `\node (a) [opts]` -- and the name if it
# has one. The declaration's own spelling is `_source.py`'s, so the two
# cannot drift; only what this rule needs from it differs.
_KEYED_NODE_RE = re.compile(
    _NODE_KEYWORD + r"\s*(?:\[(?P<before>[^\]]*)\])?\s*(?:\((?P<name>[^)]+)\))?"
    r"\s*(?:\[(?P<after>[^\]]*)\])?"
)
# `cgkey` as a whole style name: not `cgkeyish`, not `my-cgkey`.
_CGKEY_RE = re.compile(r"(?<![\w-])cgkey(?![\w-])")


@dataclass(frozen=True)
class Finding:
    rule: str
    target: str
    measurement: str


@dataclass
class CheckResult:
    """One file's report. `allowed` pairs each honoured allow with the
    measurement it suppressed, or `None` where its rule did not fire;
    `not_measured` pairs a rule with why it could not run. `figure` is
    kept for the diagnostics the report prints beside the findings."""

    path: Path
    width_pt: float
    figure: FigureResult
    findings: list[Finding] = field(default_factory=list)
    allowed: list[tuple[Allow, str | None]] = field(default_factory=list)
    deferred: list[Allow] = field(default_factory=list)
    malformed: list[Malformed] = field(default_factory=list)
    not_measured: list[tuple[str, str]] = field(default_factory=list)


def check(path: Path, width_pt: float) -> CheckResult:
    """Compile `path` once and report every rule. The caller has already
    established that this host has `lualatex` and `tikz.sty`."""
    figure = check_figure(path, "", boxed=True)  # pragma: no cover-windows
    return apply(
        path, width_pt, figure, path.read_text(encoding="utf-8")
    )  # pragma: no cover-windows


def apply(path: Path, width_pt: float, figure: FigureResult, source: str) -> CheckResult:
    """Every rule over an already-checked figure, with its allows applied."""
    findings, not_measured = evaluate(source, figure, width_pt)
    allows = parse_allows(source)
    allowed = []
    for allow in allows.honoured:
        matched = [finding.measurement for finding in findings if finding.rule == allow.rule]
        findings = [finding for finding in findings if finding.rule != allow.rule]
        allowed.append((allow, "; ".join(matched) or None))
    return CheckResult(
        path, width_pt, figure, findings, allowed, allows.deferred, allows.malformed, not_measured
    )


def evaluate(
    source: str, figure: FigureResult, width_pt: float
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """`(findings, not_measured)`, the findings in `RULES` order."""
    findings: list[Finding] = []
    not_measured: list[tuple[str, str]] = []
    if figure.failed:
        findings.append(Finding("does-not-compile", FIGURE, figure.failed))
        not_measured += [(rule, "the figure does not compile") for rule in _GEOMETRY]
    else:
        findings, not_measured = _size(source, figure, width_pt)
    findings += _focal(source) + _existing(figure)
    order = list(RULES)
    return sorted(findings, key=lambda finding: order.index(finding.rule)), not_measured


def _size(
    source: str, figure: FigureResult, width_pt: float
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """`size-width` and `size-stray`.

    One picture is measured by its own bounding box. Several are what a
    reader sees side by side, so their width is the whole box, and the
    box's extra width is their spacing rather than stray space.
    """
    pictures = len(_PICTURE_RE.findall(strip_comments(source)))
    if not pictures:
        why = "the file draws no tikzpicture"
        return [], [("size-width", why), ("size-stray", why)]
    x1, _, x2, _ = figure.boxes[BBOX_NAME]
    picture = x2 - x1
    found, not_measured = [], []
    width, whole = (
        (picture, "")
        if pictures == 1
        else (figure.input_width, f" (whole input, {pictures} pictures)")
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
    """`focal-count`: at most one `cgkey` node. TIKZ-STYLE.md: "if two
    things are accented, neither is".

    Read from source, so a `cgkey` reached only through a style the
    figure defines itself is not seen. That is a limit stated in the
    rule's documentation rather than a guess made here.
    """
    keyed = []
    for match in _KEYED_NODE_RE.finditer(strip_comments(source)):
        options = f"{match.group('before') or ''},{match.group('after') or ''}"
        if _CGKEY_RE.search(options):
            keyed.append((match.group("name") or "(unnamed)").strip())
    if len(keyed) < 2:
        return []
    return [Finding("focal-count", FIGURE, f"{len(keyed)} cgkey nodes: {', '.join(keyed)}")]


def _existing(figure: FigureResult) -> list[Finding]:
    """`review figure`'s findings, under the ids its JSON ships."""
    found = []
    if figure.nothing_measurable:
        found.append(
            Finding("nothing-measurable", FIGURE, "names no node, so nothing was measured")
        )
    if figure.protruding:
        found.append(Finding("content-protrusion", FIGURE, "content protrudes past the main block"))
    if figure.by_hand:
        found.append(Finding("loads-library-by-hand", FIGURE, ", ".join(figure.by_hand)))
    found += [
        Finding("node-overlap", f"{one}+{other}", "boxes intersect")
        for one, other in figure.overlapping
    ]
    found += [
        Finding("node-text-overload", name, f"{count} words (over {MAX_NODE_WORDS})")
        for name, count in figure.overlong
    ]
    found += [
        Finding("stranded-arrowhead", f"({point})", "arrowhead lands mid-line")
        for point in figure.stranded
    ]
    return found
