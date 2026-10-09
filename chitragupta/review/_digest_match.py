"""Is each run of a verbatim digest really in the source it cites, and
what is every sentence that is not? (#991)

**The run is the unit; the sentence is the diagnosis.** A run that
`_quotation_match.locate` finds whole is one copied span and raises
nothing. Only a run that is not found whole is split into sentences,
and only to show where it breaks: a sentence found on its own is still
copied; one whose distinctive words are mostly on one page is a
`copy-mismatch` naming the words that are not; anything else is the
drafter's own, `unquoted-text`, and additionally `unsupported-text`
when no citation covers it or the cited source does not support it
lexically -- the provenance aid's own `score_claim` under the same
`PROVENANCE_WEAK_SCORE` it bands on.

**The headline is the unsupported fraction**: the words of every
sentence carrying at least one finding, a sentence counted once however
many classes it carries, over all words. It is the number a repair pass
drives down. The copied fraction and the not-checkable share are kept
beside it so the three account for the whole digest.

`MISMATCH_SHARE` is the one number here and it is not tuned: it is the
share `near_miss` already reports, read as "most of the sentence is on
that page". docs/CODE-STANDARDS.md's R3 bars optimising it, and the
honest statement is that no corpus has been measured against it yet.

A source with no reading-ordered passages cannot be checked. Its run is
`unverifiable`, counted in the total and the not-checkable share and
nowhere else -- never `absent` after a failed comparison, the same
refusal `quotation.py` makes.

Stdlib only, interpreter tier 1.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from chitragupta import config
from chitragupta.passages import Passage, distinctive
from chitragupta.review import _quotation_match
from chitragupta.review._digest_runs import Run
from chitragupta.review.citation_provenance import score_claim

# Worst first: the order the report lists classes in, and the order a
# repair pass works them.
CLASSES = ("unsupported-text", "copy-mismatch", "unquoted-text")

# A sentence `locate` cannot find, at least this share of whose
# distinctive words sit on one page, is a copy that drifted rather than
# the drafter's own words.
MISMATCH_SHARE = 0.8

_NO_READING_ORDER = (
    "no reading-ordered passages -- run `chitragupta enrich --stages docling` "
    "so the source has a Docling sidecar to match against"
)

Lookup = Callable[[str], tuple[list[Passage], str | None]]


@dataclass(frozen=True)
class Span:
    """Verified copied text: a whole run, or one sentence of a broken one."""

    line: int
    citekeys: tuple[str, ...]
    text: str
    tier: str
    pages: tuple[int, ...]
    cited: tuple[int, int] | None
    note: str | None


@dataclass(frozen=True)
class Finding:
    cls: str
    line: int
    text: str
    citekeys: tuple[str, ...]
    detail: dict = field(default_factory=dict)


def _fraction(part: int, whole: int) -> float:
    # 0.0 for an empty digest: a number rather than a crash, and it
    # reads as what it is.
    return round(part / whole, 3) if whole else 0.0


@dataclass
class Checked:
    spans: list[Span] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    unverifiable: list[dict] = field(default_factory=list)
    words_total: int = 0

    @property
    def words_copied(self) -> int:
        return sum(len(span.text.split()) for span in self.spans)

    @property
    def words_flagged(self) -> int:
        """Words of every distinct flagged sentence. Keyed by line and
        text so the same sentence written twice is two sentences and one
        sentence with two classes is one."""
        flagged = {(finding.line, finding.text) for finding in self.findings}
        return sum(len(text.split()) for _, text in flagged)

    @property
    def words_unverifiable(self) -> int:
        return sum(run["words"] for run in self.unverifiable)

    @property
    def unsupported_fraction(self) -> float:
        return _fraction(self.words_flagged, self.words_total)

    @property
    def copied_fraction(self) -> float:
        return _fraction(self.words_copied, self.words_total)

    @property
    def unverifiable_fraction(self) -> float:
        return _fraction(self.words_unverifiable, self.words_total)


def page_note(cited: tuple[int, int] | None, pages: list[int] | tuple[int, ...]) -> str | None:
    """`cited p. A-B, found on p. X` when no found page is in the hint's
    range; None when there is no hint, no page, or agreement."""
    if cited is None or not pages:
        return None
    first, last = cited
    if any(first <= page <= last for page in pages):
        return None
    hint = f"p. {first}" if first == last else f"p. {first}-{last}"
    return f"cited {hint}, found on p. {', '.join(str(page) for page in pages)}"


def _span(run: Run, text: str, tier: str, pages: list[int]) -> Span:
    return Span(
        run.line, run.citekeys, text, tier, tuple(pages), run.pages, page_note(run.pages, pages)
    )


def _own(run: Run, sentence: str, passages: list[Passage]) -> list[Finding]:
    """`unquoted-text`, plus `unsupported-text` when nothing cites the
    sentence or its cited sources do not lexically support it."""
    found = [Finding("unquoted-text", run.line, sentence, run.citekeys)]
    score, passage = score_claim(sentence, passages) if run.citekeys else (0.0, None)
    if score < config.PROVENANCE_WEAK_SCORE:
        detail = {"support_score": round(score, 3), "page": passage.page if passage else None}
        found.append(Finding("unsupported-text", run.line, sentence, run.citekeys, detail))
    return found


def _mismatch(run: Run, sentence: str, quotable: list[Passage]) -> Finding | None:
    """A `copy-mismatch` finding, or None when the sentence is not mostly
    on any one page."""
    share, page = _quotation_match.near_miss(sentence, quotable)
    if share < MISMATCH_SHARE:
        return None
    on_page: set[str] = set().union(*(p.words for p in quotable if p.page == page))
    detail = {
        "page": page,
        "share": round(share, 3),
        "missing": sorted(distinctive(sentence) - on_page),
    }
    return Finding("copy-mismatch", run.line, sentence, run.citekeys, detail)


def _sentence_level(
    run: Run, quotable: list[Passage], passages: list[Passage], checked: Checked
) -> None:
    """The diagnosis for a run not found whole."""
    spans, findings = [], []
    for sentence in run.sentences:
        located = _quotation_match.locate(sentence, quotable)
        if located is not None:
            spans.append(_span(run, sentence, *located))
            continue
        mismatch = _mismatch(run, sentence, quotable)
        findings.extend([mismatch] if mismatch else _own(run, sentence, passages))
    if not findings and len(spans) > 1:
        # Every sentence is in the source, just not contiguously: one
        # copied span, with where it came from. Information, not a finding.
        pages = sorted({page for span in spans for page in span.pages})
        places = len({span.pages for span in spans})
        note = f"assembled from {places} places"
        spans = [Span(run.line, run.citekeys, run.text, "assembled", tuple(pages), run.pages, note)]
    checked.spans.extend(spans)
    checked.findings.extend(findings)


def _sources(run: Run, lookup: Lookup) -> tuple[list[Passage], list[Passage], list[str]]:
    """Every passage the run's citekeys reach, the quotable ones, and one
    reason per citekey that has none."""
    passages, quotable, reasons = [], [], []
    for citekey in run.citekeys:
        found, reason = lookup(citekey)
        readable = [p for p in found if p.quotable]
        passages.extend(found)
        quotable.extend(readable)
        if not readable:
            reasons.append(f"{citekey}: {reason or _NO_READING_ORDER}")
    return passages, quotable, reasons


def check_run(run: Run, lookup: Lookup, checked: Checked) -> None:
    """Verify one run and record the outcome on `checked`."""
    checked.words_total += run.words
    if not run.citekeys:
        for sentence in run.sentences:
            checked.findings.extend(_own(run, sentence, []))
        return
    passages, quotable, reasons = _sources(run, lookup)
    if not quotable:
        checked.unverifiable.append(
            {
                "line": run.line,
                "citekeys": list(run.citekeys),
                "words": run.words,
                "reason": "; ".join(reasons),
            }
        )
        return
    located = _quotation_match.locate(run.text, quotable)
    if located is not None:
        checked.spans.append(_span(run, run.text, *located))
        return
    _sentence_level(run, quotable, passages, checked)
