"""The verbatim digest's findings as data (#991, #1172).

What `_digest_match.check_run` writes and `_digest_render` reads, split
from the matcher so this says what a result is and that decides it.
"""

from dataclasses import dataclass, field

# Worst first: the report's order, and a repair pass's.
CLASSES = (
    "unsupported-text",
    "copy-mismatch",
    "dangling-reference",
    "repeated-text",
    "unquoted-text",
)

FRACTION_CLASSES = ("unsupported-text", "copy-mismatch", "unquoted-text")


@dataclass(frozen=True)
class Span:
    """Verified copied text: a whole run, or one sentence of a broken one.
    `note` names a page disagreement with the `cited` hint, an assembled
    run, or both.
    """

    line: int
    citekeys: tuple[str, ...]
    text: str
    tier: str
    pages: tuple[int, ...]
    cited: tuple[int, int] | None
    note: str | None


@dataclass(frozen=True)
class Finding:
    """One sentence in one class of `CLASSES`, anchored to its own line.

    `detail` is the class's evidence. `seq` numbers the sentence within the
    digest, so two findings on one sentence share it and a sentence written
    twice on one line does not (#1172).
    """

    cls: str
    line: int
    text: str
    citekeys: tuple[str, ...]
    detail: dict = field(default_factory=dict)
    seq: int = 0

    def __post_init__(self) -> None:
        if self.cls not in CLASSES:
            raise ValueError(f"unknown digest class {self.cls!r}; expected one of {CLASSES}")


@dataclass(frozen=True)
class Own:
    """A sentence in the drafter's own words that raised nothing."""

    line: int
    citekeys: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Unverifiable:
    """A run the aid could not check: one reason per citekey with no
    reading-ordered passages."""

    line: int
    citekeys: tuple[str, ...]
    words: int
    reason: str


def _fraction(part: int, whole: int) -> float:
    # 0.0 for an empty digest; the report says "0 of 0 words" beside it.
    return round(part / whole, 3) if whole else 0.0


@dataclass
class Checked:
    """The accumulator `check_run` fills, one run at a time; mutable by
    design, as `quotation.py`'s."""

    spans: list[Span] = field(default_factory=list)
    own: list[Own] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    unverifiable: list[Unverifiable] = field(default_factory=list)
    words_total: int = 0
    sentences: int = 0

    @property
    def words_copied(self) -> int:
        return sum(len(span.text.split()) for span in self.spans)

    @property
    def words_flagged(self) -> int:
        """Words of every distinct flagged sentence, keyed by line, text and
        `seq`: a sentence written twice counts twice, one with two classes
        once."""
        flagged = {
            (finding.line, finding.text, finding.seq)
            for finding in self.findings
            if finding.cls in FRACTION_CLASSES
        }
        return sum(len(text.split()) for _, text, _ in flagged)

    @property
    def words_own(self) -> int:
        return sum(len(own.text.split()) for own in self.own)

    @property
    def words_unverifiable(self) -> int:
        return sum(run.words for run in self.unverifiable)

    @property
    def unsupported_fraction(self) -> float:
        return _fraction(self.words_flagged, self.words_total)

    @property
    def copied_fraction(self) -> float:
        return _fraction(self.words_copied, self.words_total)

    @property
    def own_fraction(self) -> float:
        return _fraction(self.words_own, self.words_total)

    @property
    def unverifiable_fraction(self) -> float:
        return _fraction(self.words_unverifiable, self.words_total)
