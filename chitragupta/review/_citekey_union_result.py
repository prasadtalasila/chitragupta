"""The shape the citekey union invariant is computed into, and the
arithmetic over it. Touches no filesystem, so the invariant is testable
without a book.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UnitInput:
    """One acceptance unit as an input to the assembly. `citekeys` is empty
    for anything but an `accepted` unit."""

    unit: str
    state: str
    included: bool = False
    citekeys: list[str] = field(default_factory=list)


@dataclass
class UnionResult:
    assembled: Path
    checked: list[UnitInput] = field(default_factory=list)
    unchecked: list[UnitInput] = field(default_factory=list)
    # Citekeys the assembly states itself (own text plus non-unit includes),
    # never the units' own.
    own: set[str] = field(default_factory=set)
    outside_units: list[str] = field(default_factory=list)  # the non-unit files read
    unresolved: list[str] = field(default_factory=list)  # includes with no file on disk

    @property
    def omitted(self) -> list[UnitInput]:
        """Accepted units the assembly never includes, in outline order."""
        return [entry for entry in self.checked if not entry.included]

    @property
    def dropped(self) -> dict[str, list[str]]:
        """`citekey -> the accepted units that stand on it`, for every one
        the assembly does not carry, in outline order. A citekey stated
        elsewhere in the assembly is not dropped: losing a unit's prose is
        another finding.
        """
        carried = self.own | {
            key for entry in self.checked if entry.included for key in entry.citekeys
        }
        found: dict[str, list[str]] = {}
        for entry in self.omitted:
            for key in entry.citekeys:
                if key not in carried:
                    found.setdefault(key, []).append(entry.unit)
        return found

    @property
    def appeared(self) -> set[str] | None:
        """Citekeys the assembly states outside any unit, or `None` when an
        unassessed unit might record this very citekey. An empty set is a
        real answer: the non-unit includes were read, not assumed empty.
        """
        if self.unchecked:
            return None
        return self.own - {key for entry in self.checked for key in entry.citekeys}
