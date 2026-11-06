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

**A run of the drafter's own words is checked for support, not for
copying (#1172).** `Run.own` marks one: closed by `[see @key]`, under an
`<!-- own: why -->` line, or a table row. Each sentence is scored with
`score_claim` against its cited sources' passages, page-level ones
included; a weak one is `unsupported-text` and any other is own text,
raising nothing. An uncited sentence in a declared-own block is own
text too: the drafter said so. Own text never raises `unquoted-text`,
which is for words the drafter did not declare.

**The headline is the unsupported fraction**: the words of every
sentence carrying a finding of the three source classes
(`FRACTION_CLASSES`), a sentence counted once however many it carries,
over all words. It is the number a repair pass drives down. The copied
fraction, the own-words share and the not-checkable share are kept
beside it so the four partition the digest: `words_copied + words_own +
words_flagged + words_unverifiable == words_total`, because `check_run`,
the one writer, routes every sentence to exactly one of the four lists.
`dangling-reference` (`_digest_dangling.py`) is listed beside them and
counted in none: it faults where a copied run stops, not whether a
source says it.

`MISMATCH_SHARE` is the one number here and it is not tuned: it is the
share `near_miss` already reports, read as "most of the sentence is on
that page". docs/CODE-STANDARDS.md's R3 bars optimising it, and the
honest statement is that no corpus has been measured against it yet.

A source with no reading-ordered passages cannot be checked. A run
citing one -- any one, where the bracket names several -- is
`unverifiable`, counted in the total and the not-checkable share and
nowhere else: never `absent` after a failed comparison, the same
refusal `quotation.py` makes, and never matched against the other
sources alone, which would report text copied from the unreadable one
as the drafter's own.

The records it writes live in `_digest_model.py` and are re-exported
here, where every caller has always found them.

Stdlib only, interpreter tier 1.
"""

from collections.abc import Callable

from chitragupta import config
from chitragupta.passages import Passage, distinctive
from chitragupta.review import _quotation_match
from chitragupta.review._digest_dangling import dangling
from chitragupta.review._digest_model import (
    CLASSES,
    FRACTION_CLASSES,
    Checked,
    Finding,
    Own,
    Span,
    Unverifiable,
)
from chitragupta.review._digest_runs import Run
from chitragupta.review.citation_provenance import score_claim

# A sentence `locate` cannot find, at least this share of whose
# distinctive words sit on one page, is a copy that drifted rather than
# the drafter's own words.
MISMATCH_SHARE = 0.8

_NO_READING_ORDER = (
    "no reading-ordered passages -- run `chitragupta enrich --stages docling` "
    "so the source has a Docling sidecar to match against"
)

__all__ = [
    "CLASSES",
    "FRACTION_CLASSES",
    "MISMATCH_SHARE",
    "Checked",
    "Finding",
    "Own",
    "Span",
    "Unverifiable",
    "check_run",
    "page_note",
]

Lookup = Callable[[str], tuple[list[Passage], str | None]]


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


def _span(run: Run, line: int, text: str, tier: str, pages, extra: str | None = None) -> Span:
    """The one `Span` builder, so every copied span carries the page note."""
    notes = [note for note in (page_note(run.cited, pages), extra) if note]
    return Span(line, run.citekeys, text, tier, tuple(pages), run.cited, "; ".join(notes) or None)


def _own(run: Run, line: int, sentence: str, passages: list[Passage]) -> list[Finding]:
    """`unquoted-text`, plus `unsupported-text` when nothing cites the
    sentence or its cited sources do not lexically support it."""
    found = [Finding("unquoted-text", line, sentence, run.citekeys)]
    score, passage = score_claim(sentence, passages) if run.citekeys else (0.0, None)
    if score < config.PROVENANCE_WEAK_SCORE:
        detail = {"support_score": round(score, 3), "page": passage.page if passage else None}
        found.append(Finding("unsupported-text", line, sentence, run.citekeys, detail))
    return found


def _mismatch(run: Run, line: int, sentence: str, quotable: list[Passage]) -> Finding | None:
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
    return Finding("copy-mismatch", line, sentence, run.citekeys, detail)


def _assembled(run: Run, spans: list[Span]) -> Span:
    """Every sentence found, just not contiguously: one copied span, with
    where it came from. Information, not a finding."""
    pages = sorted({page for span in spans for page in span.pages})
    places = len({span.pages for span in spans})
    where = ", ".join(str(page) for page in pages) or "?"
    note = f"assembled from {places} places" if places > 1 else f"assembled within p. {where}"
    return _span(run, run.line, run.text, "assembled", pages, note)


def _sentence_level(
    run: Run, quotable: list[Passage], passages: list[Passage], checked: Checked
) -> None:
    """The diagnosis for a run not found whole."""
    spans, findings = [], []
    for line, sentence in zip(run.lines, run.sentences, strict=True):
        located = _quotation_match.locate(sentence, quotable)
        if located is not None:
            spans.append(_span(run, line, sentence, *located))
            continue
        mismatch = _mismatch(run, line, sentence, quotable)
        findings.extend([mismatch] if mismatch else _own(run, line, sentence, passages))
    if not findings and len(spans) > 1:
        spans = [_assembled(run, spans)]
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


def _check_own(run: Run, lookup: Lookup, checked: Checked) -> None:
    """A run in the drafter's own words: supported, or `unsupported-text`."""
    if not run.citekeys:
        checked.own += [Own(line, (), s) for line, s in zip(run.lines, run.sentences, strict=True)]
        return
    passages, reasons = [], []
    for citekey in run.citekeys:
        found, reason = lookup(citekey)
        passages += found
        if not found:
            reasons.append(f"{citekey}: {reason or 'no passages'}")
    if reasons:
        checked.unverifiable.append(
            Unverifiable(run.line, run.citekeys, run.words, "; ".join(reasons))
        )
        return
    for line, sentence in zip(run.lines, run.sentences, strict=True):
        score, passage = score_claim(sentence, passages)
        if score < config.PROVENANCE_WEAK_SCORE:
            detail = {"support_score": round(score, 3), "page": passage.page if passage else None}
            checked.findings.append(
                Finding("unsupported-text", line, sentence, run.citekeys, detail)
            )
        else:
            checked.own.append(Own(line, run.citekeys, sentence))


def check_run(
    run: Run, lookup: Lookup, checked: Checked, shown: frozenset[tuple[str, str]] = frozenset()
) -> None:
    """Verify one run and record the outcome on `checked`. `shown` is
    `_digest_runs.shown_figures` of the whole digest."""
    checked.words_total += run.words
    checked.findings += [
        Finding("dangling-reference", line, sentence, run.citekeys, detail)
        for line, sentence, detail in dangling(run, shown)
    ]
    if run.own:
        _check_own(run, lookup, checked)
        return
    if not run.citekeys:
        for line, sentence in zip(run.lines, run.sentences, strict=True):
            checked.findings.extend(_own(run, line, sentence, []))
        return
    passages, quotable, reasons = _sources(run, lookup)
    if reasons:
        checked.unverifiable.append(
            Unverifiable(run.line, run.citekeys, run.words, "; ".join(reasons))
        )
        return
    located = _quotation_match.locate(run.text, quotable)
    if located is not None:
        checked.spans.append(_span(run, run.line, run.text, *located))
        return
    _sentence_level(run, quotable, passages, checked)
