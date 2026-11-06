"""The verbatim digest's findings as data (#991, #1172).

What `_digest_match.check_run` writes and `_digest_render` reads: the
classes, one record per copied span, finding, own-words sentence and
uncheckable run, and the `Checked` accumulator whose properties are the
report's fractions. Split from the matcher so each stays one thing: this
file says what a result is, that one decides it.

Stdlib only, interpreter tier 1.
"""

from dataclasses import dataclass, field

# Worst first: the order the report lists classes in, and the order a
# repair pass works them.
CLASSES = ("unsupported-text", "copy-mismatch", "dangling-reference", "unquoted-text")

# The classes whose words the unsupported fraction counts.
FRACTION_CLASSES = ("unsupported-text", "copy-mismatch", "unquoted-text")


@dataclass(frozen=True)
class Span:
    """Verified copied text: a whole run, or one sentence of a broken one.

    `pages` is where the text was found; `cited` is the citation's hint;
    `note` names a disagreement between the two, an assembled run, or
    both, and is None when there is nothing to say.
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

    `detail` is the class's evidence: `copy-mismatch` carries `page`,
    `share` and `missing`; `unsupported-text` carries `support_score` and
    `page`; `dangling-reference` carries `kind` and `match`;
    `unquoted-text` carries nothing. `seq` numbers the sentence within
    the digest, so two findings on one sentence share it and the same
    sentence written twice on one line does not (#1172): the fraction
    counts each distinct `(line, text, seq)` once.
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
    """A run the aid could not check, and why -- one reason per citekey
    the ladder had no reading-ordered passages for."""

    line: int
    citekeys: tuple[str, ...]
    words: int
    reason: str


def _fraction(part: int, whole: int) -> float:
    # 0.0 for an empty digest: a number rather than a crash, and the
    # report says "0 of 0 words" beside it.
    return round(part / whole, 3) if whole else 0.0


@dataclass
class Checked:
    """The accumulator `check_run` fills, one run at a time.

    Mutable by design, the same shape as `quotation.py`'s: it is passed
    by reference through the run loop and read whole afterwards.
    """

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
        """Words of every distinct flagged sentence. Keyed by line, text
        and `seq` so the same sentence written twice is two sentences and
        one sentence with two classes is one."""
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
