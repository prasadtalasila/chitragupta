"""What one checked figure amounts to.

Derived checks are properties so a `FigureResult` cannot hold boxes that
disagree with its findings: `boxes` is the one source of truth.
"""

from dataclasses import dataclass, field
from pathlib import Path

from chitragupta.review.figure_layout._drawn import Drawn
from chitragupta.review.figure_layout._geometry import (
    Box,
    emptiness,
    overlaps,
    protrudes,
)


@dataclass
class FigureResult:
    """Everything checked about one figure.

    `boxes` is `None` where no geometry was obtained: `skipped` means the
    host cannot compile any figure, `failed` that this one is broken.
    """

    path: Path
    overlong: list[tuple[str, int]] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    stranded: list[str] = field(default_factory=list)
    by_hand: list[str] = field(default_factory=list)
    declared: list[str] = field(default_factory=list)
    boxes: dict[str, Box] | None = None
    skipped: str = ""
    failed: str | None = None
    # `figure check`'s boxed probe only (#1053, #1054).
    input_width: float | None = None
    drawn: Drawn | None = None

    @property
    def overlapping(self) -> list[tuple[str, str]]:
        return overlaps(self.boxes) if self.boxes else []

    @property
    def unmeasured(self) -> list[str]:
        """Declared names the geometry did not come back with (#404), so a
        protrusion beside them is not to be trusted. Empty when nothing
        was attempted (`boxes is None`)."""
        if self.boxes is None:
            return []
        return [name for name in self.declared if name not in self.boxes]

    @property
    def nothing_measurable(self) -> bool:
        """Whether this figure compiled and yielded no node geometry (#405).

        Every check needs a named node, so a figure naming none used to
        look clean because nothing ran; most drafted figures name none
        (#393). Binary, so a finding under R3. `current bounding box` is
        never declared, so it cannot count as measured.
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
        """Whether anything binary fired. Excludes `empty_fraction` and
        `unmeasured`: counting either is the first step to optimising it."""
        return bool(
            self.overlong
            or self.overlapping
            or self.protruding
            or self.stranded
            or self.by_hand
            or self.nothing_measurable
            or self.failed
        )
