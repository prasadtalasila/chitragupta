"""What one checked figure amounts to.

Its own module so the dependency runs one way: `_report.py` serialises
these and `__init__.py` builds them, and neither has to import the other.

The derived checks are properties rather than stored fields so a
`FigureResult` cannot be constructed holding boxes that disagree with its
own findings -- there is one source of truth (`boxes`) and everything
else is computed from it.
"""

from dataclasses import dataclass, field
from pathlib import Path

from chitragupta.review.figure_layout._geometry import (
    Box,
    emptiness,
    overlaps,
    protrudes,
)


@dataclass
class FigureResult:
    """Everything checked about one figure.

    `boxes` is `None` where geometry could not be obtained at all, and
    the two reasons are kept apart because they mean opposite things to a
    reader: `skipped` is *the host* cannot compile any figure, `failed`
    is *this figure* is broken while others may be fine.
    """

    path: Path
    overlong: list[tuple[str, int]] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    stranded: list[str] = field(default_factory=list)
    declared: list[str] = field(default_factory=list)
    boxes: dict[str, Box] | None = None
    skipped: str = ""
    failed: str | None = None

    @property
    def overlapping(self) -> list[tuple[str, str]]:
        return overlaps(self.boxes) if self.boxes else []

    @property
    def unmeasured(self) -> list[str]:
        """Declared names the geometry did not come back with.

        #404's failure mode, kept visible after the fix rather than
        assumed gone: a name the probe could not resolve leaves that node
        unmeasured, and `protrudes()` then reads the band it occupies as
        a tall empty one. A reader seeing a protrusion finding beside
        this list knows to distrust it.

        Empty where `boxes is None`, because nothing was attempted --
        that is `skipped` or `failed`, and reporting names as unmeasured
        there would be a second wrong answer on top of the one already
        reported.
        """
        if self.boxes is None:
            return []
        return [name for name in self.declared if name not in self.boxes]

    @property
    def nothing_measurable(self) -> bool:
        """Whether this figure compiled and yielded no node geometry at
        all -- #405.

        The distinction the report exists to make. Every geometry check
        here needs a named node to measure, so a figure that names none
        reports no overlap and no protrusion *because nothing ran*, which
        used to be indistinguishable from a figure where everything ran
        and found nothing. Exactly 1 of the 43 figures in this
        repository's own drafted book names a node (#393), so this is the
        normal case rather than a corner.

        Binary, and therefore safe as a finding under
        docs/AUTO-IMPROVEMENT.md's R3 -- unlike the proportion of names
        measured, which is a score and stays a labelled diagnostic.

        `current bounding box` is excluded by construction: it is never a
        declared name, and counting it would make "something was
        measured" true of every figure that compiles.
        """
        if self.boxes is None:
            return False
        return not any(name in self.boxes for name in self.declared)

    @property
    def protruding(self) -> bool:
        return protrudes(self.boxes) if self.boxes else False

    @property
    def empty_fraction(self) -> float | None:
        return emptiness(self.boxes) if self.boxes else None

    @property
    def has_findings(self) -> bool:
        """Whether anything binary fired. Deliberately excludes
        `empty_fraction` *and* `unmeasured`: neither is a finding, and
        counting either as one is the first step towards something
        optimising it. `nothing_measurable` is in because it is binary --
        the figure named a node or it did not."""
        return bool(
            self.overlong
            or self.overlapping
            or self.protruding
            or self.stranded
            or self.nothing_measurable
            or self.failed
        )
