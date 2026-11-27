"""A2's self-check (#306, plans/a2-claim-quote-split.md): does a
`claim:` in evidence.md merely restate its own `quote:` with the words
moved? Advisory only, and the similarity number is *reported, never
optimised*: it must not become an acceptance criterion.

Reuses `overlap_skipgram.stem_filter` (stemming survives rewording) but
not its family split or `DEFAULT_N=5`: a claim/quote pair is a sentence,
and at n=5 a short pair never forms a gram. Legacy `support:`-only
blocks have no `claim:` and are skipped.
"""

import argparse
import re
from pathlib import Path

from chitragupta.dossier import _resolve_dossier, draft_relpath
from chitragupta.dossier._citekeys import duplicate_evidence_keys, evidence_blocks
from chitragupta.overlap_index import _norm, gram_hashes
from chitragupta.overlap_skipgram import stem_filter

# A bigram (tests/test_dossier.py TestOverlapScore): reworded quotes score
# 0.5-0.75 at n=2, genuine restatements ~0.08; n=3 collapses a short
# reworded fixture to 0.33, so n=2 is the width that separates every one.
_NGRAM = 2

# Inside the 0.08-0.5 gap, nearer the reworded side, so a restatement
# drifting toward its source's wording still passes.
_OVERLAP_THRESHOLD = 0.5

# `[ \t]*`, not `\s*`: a swallowed newline let an empty `quote:` read the
# next note as the quote.
_FIELD = re.compile(r"^-?\s*(?P<field>claim|quote|relevance|support):[ \t]*", re.MULTILINE)

# Stripped from a `quote:` value (#1174): a trailing page locator, which
# leaves `p24` behind that no source contains, and one pair of double
# quotation marks. A hand-written page is dropped, not compared. A dot or
# space must follow `p`/`pp`, so a study label like `(P1)` stays.
_LOCATOR = re.compile(
    r"\s*[(\[]\s*(?:pages?\s+|pp?\.\s*|pp?\s+)\d+(?:\s*[-\u2013]\s*\d+)?\s*[)\]]\s*\.?\s*$",
    re.IGNORECASE,
)
_DOUBLE_MARKS = '"\u201c\u201d'

# A margin line shaped like another field (lowercase, up to three words,
# colon) ends the value above, or a note under a `quote:` was checked as
# the quotation. Indented continuations and capitalised wraps continue.
# Cost: a margin wrap like "as follows: ..." reads as a field; quotes are
# one line, and on the owner's 122 quotes this cut none.
_OTHER_FIELD = re.compile(r"^(?:- )?[a-z][a-z0-9_-]*(?: [a-z0-9_-]+){0,2}:(?:\s|$)", re.MULTILINE)


def _values(block: str) -> list[tuple[str, str]]:
    """Every non-empty `field: value` in `block`, in file order; the one
    reading `fields`, `quotes` and `repeated_fields` share."""
    matches = list(_FIELD.finditer(block))
    found = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        value = block[match.end() : end]
        other = _OTHER_FIELD.search(value, value.find("\n") + 1) if "\n" in value else None
        value = (value[: other.start()] if other else value).strip()
        if value:
            found.append((match.group("field"), value))
    return found


def fields(block: str) -> dict[str, str]:
    """`block`'s fields, keyed by name, the first value of each.

    The one `evidence.md` field parser. `quote:` may repeat (#1174), so
    callers read `quotes()`; repeats of the other fields are what
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
    appear in `claim`, order-blind so a pure rewording still scores near 1.0.

    `None` if `quote` forms no bigram: a zero would claim the pair was
    checked and found clean. Normalised by the quote, so it catches "the
    quote with its words moved", not paste-then-summarize.
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
    `_OVERLAP_THRESHOLD` against it.
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
    is behind `--score` so a drafting run is not handed a number to
    reword against (R3).
    """
    target = _resolve_dossier(Path(args.draft))
    if not target.is_dir():
        print(
            f"No dossier at {draft_relpath(target)}. Create one with "
            f"`python -m chitragupta.draft dossier init {args.draft} --genre <genre>`."
        )
        return 1

    # Printed first and independently: a duplicated heading means findings
    # below may be about text not in play (#506/m-65).
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
