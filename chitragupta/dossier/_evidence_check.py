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
from chitragupta.dossier._citekeys import evidence_blocks
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


def _fields(block: str) -> dict[str, str]:
    """`block`'s `field: value` lines, keyed by field name -- the same
    match-then-slice-to-the-next-match reading `_citekeys._GLOSSARY_TERM`
    uses, over this module's own field set instead of glossary bullets.
    """
    matches = list(_FIELD.finditer(block))
    fields: dict[str, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        value = block[match.end():end].strip()
        if value:
            fields.setdefault(match.group("field"), value)
    return fields


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


def reworded_claims(dossier: Path) -> dict[str, float]:
    """citekey -> overlap score, for every kept-evidence block whose
    `claim:` scores at or above `_OVERLAP_THRESHOLD` against its own
    `quote:`. Empty for a dossier with no evidence.md, no block with
    both fields, or nothing that crosses the threshold.
    """
    found: dict[str, float] = {}
    for citekey, block in evidence_blocks(dossier).items():
        fields = _fields(block)
        claim, quote = fields.get("claim"), fields.get("quote")
        if not claim or not quote:
            continue
        score = overlap_score(claim, quote)
        if score is not None and score >= _OVERLAP_THRESHOLD:
            found[citekey] = score
    return found


def _cmd_check_evidence(args: argparse.Namespace) -> int:
    """`dossier check-evidence <draft>`: print, never block. The score
    is hidden behind `--score` on purpose -- printing it by default
    would hand a drafting run a number to reword against until it drops,
    which is exactly the optimisation the plan's R3 constraint forbids.
    """
    target = _resolve_dossier(Path(args.draft))
    if not target.is_dir():
        print(f"No dossier at {draft_relpath(target)}. Create one with "
              f"`python -m chitragupta.draft dossier init {args.draft} --genre <genre>`.")
        return 1

    findings = reworded_claims(target)
    if not findings:
        print("No claim: reads like its quote: reworded.")
        return 0
    for citekey, score in findings.items():
        print(f"[warn] {citekey}: claim: reads like quote: with its words moved -- "
              "re-read whether this is your own reading of the source, not a cue "
              "to reword until this warning goes away.")
        if args.score:
            print(f"    ({score:.0%} content-word bigram overlap with quote:)")
    return 0
