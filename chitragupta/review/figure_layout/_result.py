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
    Box, emptiness, overlaps, protrudes,
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
    boxes: dict[str, Box] | None = None
    skipped: str = ""
    failed: str | None = None

    @property
    def overlapping(self) -> list[tuple[str, str]]:
        return overlaps(self.boxes) if self.boxes else []

    @property
    def protruding(self) -> bool:
        return protrudes(self.boxes) if self.boxes else False

    @property
    def empty_fraction(self) -> float | None:
        return emptiness(self.boxes) if self.boxes else None

    @property
    def has_findings(self) -> bool:
        """Whether anything binary fired. Deliberately excludes
        `empty_fraction`: a proportion is not a finding, and counting it
        as one is the first step towards something optimising it."""
        return bool(
            self.overlong or self.overlapping or self.protruding or self.failed
        )
