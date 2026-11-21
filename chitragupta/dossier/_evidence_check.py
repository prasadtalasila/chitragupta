"""A2's self-check (#306, plans/a2-claim-quote-split.md): does a
`claim:` in evidence.md merely restate its own `quote:` with the words
moved, rather than reflecting the drafter's own reading of the source?
Advisory only -- see `_cmd_check_evidence` -- and per the plan's own
constraint, the similarity number is *reported, never optimised*: it
must not become an acceptance criterion for an unattended edit.

Reuses `chitragupta.overlap_skipgram`'s stemmed, stopword-filtered word
stream (`stem_filter`) rather than `overlap_index`'s exact tier -- a
reworded quote survives stemming and reordering, which an exact n-gram
match is blind to by construction. It does *not* reuse that module's
even/odd family split or its `DEFAULT_N=5`: that split buys robustness
against a single substituted word when aligning a whole document against
a large corpus, which is not this problem, and a claim/quote pair is a
sentence, not a document -- at n=5 a short pair never reaches one gram
at all. `overlap_score`'s docstring below records the fixture scores
that picked n=2 over n=3.

Only ever runs on a block a genre skill wrote under the new contract:
a legacy `support:`-only block has no separate `claim:` to compare
against, and nothing here goes looking for one.
"""

import argparse
import re
from pathlib import Path

from chitragupta.dossier import _resolve_dossier, draft_relpath
from chitragupta.dossier._citekeys import duplicate_evidence_keys, evidence_blocks
from chitragupta.overlap_index import _norm, gram_hashes
from chitragupta.overlap_skipgram import stem_filter

# A bigram, not overlap_skipgram.DEFAULT_N's 5 -- see module docstring.
# Measured on this module's own test fixtures (tests/test_dossier.py,
# TestOverlapScore): a reworded quote (clauses swapped, no new words)
# scores 0.5-0.75 at n=2, a genuine restatement (same topic, different
# structure and words) scores ~0.08. n=3 still separates that pair but
# collapses a short reworded fixture to 0.33 -- under a threshold that
# still needs to catch the long-fixture case -- so n=2 is the width that
# separates every fixture tried, not merely the first one that worked.
_NGRAM = 2

# Set inside the gap the n=2 fixtures above leave open (0.08 to 0.5),
# closer to the reworded side than the midpoint so a restatement that
# drifts a little toward its source's wording still passes.
_OVERLAP_THRESHOLD = 0.5

_FIELD = re.compile(r"^-?\s*(?P<field>claim|quote|relevance|support):\s*", re.MULTILINE)

# What `quotes()` takes off a `quote:` value before anything reads it
# (#1174): a page locator at the very end -- `(p. 24)`, `(pp. 12-13)`,
# `[page 24]`, with a full stop after it if one follows -- and one pair of
# double quotation marks around the whole value. The matcher flattens
# punctuation away, so marks never caused a miss, but a locator leaves
# `p24` behind, which no source contains. The page is derived by
# locating the quote; a page written by hand is not compared, only
# dropped, which is the cost the owner accepted for not warning.
_LOCATOR = re.compile(
    r"\s*[(\[]\s*(?:pages?|pp?\.?)\s*\d+(?:\s*[-\u2013]\s*\d+)?\s*[)\]]\s*\.?\s*$",
    re.IGNORECASE,
)
_DOUBLE_MARKS = '"\u201c\u201d'


def _values(block: str) -> list[tuple[str, str]]:
    """Every non-empty `field: value` in `block`, in file order -- a
    match-then-slice-to-the-next-match reading over this module's own
    field set. The one reading `fields`, `quotes` and `repeated_fields`
    all share."""
    matches = list(_FIELD.finditer(block))
    found = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        value = block[match.end() : end].strip()
        if value:
            found.append((match.group("field"), value))
    return found


def fields(block: str) -> dict[str, str]:
    """`block`'s fields, keyed by name, the first value of each.

    Public because `chitragupta/evidence_appendix.py` reads the same file.
    `evidence.md` has one field parser and this module is it: a second one
    would be a second place for the field set to drift. A `quote:` may
    repeat (#1174), so a caller after quotes reads `quotes()`, not this;
    the other three fields are single-valued, and a repeat of one is what
    `repeated_fields` warns about.
    """
    found: dict[str, str] = {}
    for name, value in _values(block):
        found.setdefault(name, value)
    return found


def normalise_quote(value: str) -> str:
    """`value` without a trailing page locator or one surrounding pair of
    double quotation marks, repeated until neither is left.

    The pair comes off only when no other double mark is inside it, so
    `\u201cTwin\u201d is used loosely, as is \u201cshadow\u201d` -- which
    opens and closes with a mark that belongs to a quoted word -- keeps
    every mark it has.
    """
    text = value.strip()
    while True:
        before = text
        text = _LOCATOR.sub("", text).strip()
        inner = text[1:-1]
        if (
            len(text) >= 2
            and text[0] in '"\u201c'
            and text[-1] in '"\u201d'
            and not any(mark in inner for mark in _DOUBLE_MARKS)
        ):
            text = inner.strip()
        if text == before:
            return text


def quotes(block: str) -> list[str]:
    """Every `quote:` in `block`, normalised (`normalise_quote`), in file
    order, an identical repeat counted once."""
    found: list[str] = []
    for name, value in _values(block):
        quote = normalise_quote(value) if name == "quote" else ""
        if quote and quote not in found:
            found.append(quote)
    return found


def repeated_fields(block: str) -> dict[str, int]:
    """field -> count, for each single-valued field written more than
    once in `block`. Only the first is ever read, so the rest would
    otherwise be dropped without a word."""
    counts: dict[str, int] = {}
    for name, _ in _values(block):
        counts[name] = counts.get(name, 0) + 1
    return {name: n for name, n in counts.items() if n > 1 and name != "quote"}


def overlap_score(claim: str, quote: str) -> "float | None":
    """The share of `quote`'s stemmed content-word bigrams that also
    appear in `claim`, order-blind so a pure rewording (same words,
    different order) still scores near 1.0.

    `None` if `quote` is too short to form even one bigram after
    stopwords are dropped -- nothing to compare, not a zero score, since
    a zero would claim the pair was checked and found clean. A quote
    that short is common (a one-clause quotation), not a degenerate
    input to reject.

    Normalised by `quote`'s own bigram count, so sensitivity runs one
    direction only: a short, deliberate quotation restated in the same
    clause scores high (fires), while a long pasted window condensed
    into a short claim scores low (silent) -- most of the window's
    bigrams simply have nowhere to land in a claim a fraction its
    length. This catches "the quote with its words moved", which is
    what it is named for; it does not catch paste-then-summarize.
    """
    quote_stems, _ = stem_filter(_norm(quote))
    if len(quote_stems) < _NGRAM:
        return None
    claim_stems, _ = stem_filter(_norm(claim))
    quote_grams = set(gram_hashes(quote_stems, _NGRAM))
    claim_grams = set(gram_hashes(claim_stems, _NGRAM)) if len(claim_stems) >= _NGRAM else set()
    return len(quote_grams & claim_grams) / len(quote_grams)


def reworded_claims(dossier: Path) -> dict[str, list[tuple[int, int, float]]]:
    """citekey -> (quote's position, quotes in its block, overlap score),
    for every `quote:` whose block's `claim:` scores at or above
    `_OVERLAP_THRESHOLD` against it. Empty for a dossier with no
    evidence.md, no block with both fields, or nothing that crosses the
    threshold.
    """
    found: dict[str, list[tuple[int, int, float]]] = {}
    for citekey, block in evidence_blocks(dossier).items():
        claim = fields(block).get("claim")
        if not claim:
            continue
        block_quotes = quotes(block)
        for index, quote in enumerate(block_quotes, start=1):
            score = overlap_score(claim, quote)
            if score is not None and score >= _OVERLAP_THRESHOLD:
                found.setdefault(citekey, []).append((index, len(block_quotes), score))
    return found


def _cmd_check_evidence(args: argparse.Namespace) -> int:
    """`dossier check-evidence <draft>`: print, never block. The score
    is hidden behind `--score` on purpose -- printing it by default
    would hand a drafting run a number to reword against until it drops,
    which is exactly the optimisation the plan's R3 constraint forbids.
    """
    target = _resolve_dossier(Path(args.draft))
    if not target.is_dir():
        print(
            f"No dossier at {draft_relpath(target)}. Create one with "
            f"`python -m chitragupta.draft dossier init {args.draft} --genre <genre>`."
        )
        return 1

    # Printed before the claim/quote findings and independently of them:
    # a duplicated heading means the block a run was handed is not the
    # block the file's author last wrote, which makes every finding below
    # it about text that may not be the one in play (#506/m-65).
    for citekey, count in duplicate_evidence_keys(target).items():
        print(
            f"[warn] {citekey}: {count} blocks under one citekey -- the first is "
            "the one every reader gets. Merge them, or the later ones are text "
            "nothing will ever read."
        )

    repeated = _print_repeated_fields(target)
    findings = reworded_claims(target)
    if not findings:
        if not repeated:
            print("No claim: reads like its quote: reworded.")
        return 0
    for citekey, hits in findings.items():
        for index, of, score in hits:
            which = f"quote {index} of {of}" if of > 1 else "quote:"
            print(
                f"[warn] {citekey}: claim: reads like {which} with its words moved -- "
                "re-read whether this is your own reading of the source, not a cue "
                "to reword until this warning goes away."
            )
            if args.score:
                print(f"    ({score:.0%} content-word bigram overlap with {which})")
    return 0


def _print_repeated_fields(target: Path) -> bool:
    """Warn on each block that repeats a single-valued field; True if any
    did. A repeated `claim:` means the reword check above only compared
    the first, so its clean line would claim more than was checked."""
    warned = False
    for citekey, block in evidence_blocks(target).items():
        for name, count in repeated_fields(block).items():
            warned = True
            print(f"[warn] {citekey}: {count} {name}: lines -- only the first is read. Merge them.")
    return warned
