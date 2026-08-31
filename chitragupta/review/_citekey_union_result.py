"""The shape the citekey union invariant is computed into, and the
arithmetic over it.

Split from `chitragupta/review/citekey_union.py` (C2, the 250-code-line
ratchet), along the boundary that was already there: that module reads
the book off disk, serialises and wires up the CLI, and
`_citekey_union_includes` resolves what the assembly pulls in. This holds
what those produce -- and, because both directions are properties rather
than stored fields, the subtraction itself. Nothing here touches the
filesystem, which is what makes the invariant testable without a book.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UnitInput:
    """One acceptance unit as an input to the assembly: what it stands on,
    whether that record can be believed, and whether the assembly includes
    it. `citekeys` is empty for anything but an `accepted` unit -- see the
    module docstring."""

    unit: str
    state: str
    included: bool = False
    citekeys: list[str] = field(default_factory=list)


@dataclass
class UnionResult:
    assembled: Path
    checked: list[UnitInput] = field(default_factory=list)
    unchecked: list[UnitInput] = field(default_factory=list)
    # Citekeys the assembly states itself: its own text plus every file it
    # includes that is not a unit. Never the units' own -- see the module
    # docstring on why a book's skeleton carries none of those.
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
        the assembly does not carry.

        A citekey an omitted unit stands on is *not* dropped if the
        assembly states it elsewhere -- another included unit, or its own
        front matter. The reader still meets the source; what they lost is
        that unit's prose, which is a different finding and not this one.

        In outline order, so a reader walks the book's own structure
        rather than an alphabet.
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
        unassessed unit means the question cannot be answered.

        `None` has one cause and one only: a unit whose record cannot be
        believed might record this very citekey, so attributing it to the
        assembly would be a guess. Nothing else withholds it -- an empty
        set here is a real answer, because the non-unit includes were
        opened and read rather than assumed empty.
        """
        if self.unchecked:
            return None
        return self.own - {key for entry in self.checked for key in entry.citekeys}
