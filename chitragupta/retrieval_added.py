"""The words a query is ranked on beyond those typed, and how they are shown.

Acronym expansion (#789) and spelling correction (#1232) both add words.
`retrieval.query_terms` calls `added_terms` once and every ranking path,
the CLI note and the `--log` record read that result, so none can
describe an addition that was not ranked (#953). Each reads the typed
terms only, and a word both would add is added once, by the acronym.
"""

import sys
from typing import NamedTuple

from chitragupta import retrieval_expansion, retrieval_spelling

ACRONYM = "acronym"
SPELLING = "spelling"


class Added(NamedTuple):
    """One word a query is ranked on beyond those typed."""

    typed: str  # the typed term that caused it
    term: str  # the word added
    source: str  # ACRONYM or SPELLING


def added_terms(
    typed: list[str], context: list[str], tokenize, tokenize_item, excluded
) -> list[Added]:
    """What to rank `typed` and `context` with beyond themselves: acronym
    expansions of both, then spelling corrections of `typed` alone.

    `context` (`--y-prev`'s prose) is never corrected: that would guess at
    a word nobody searched for. The tokenizers and `excluded` are passed in
    because `chitragupta.retrieval` imports this module.
    """
    words = typed + context
    if not words:
        return []
    added = [Added(a, t, ACRONYM) for a, t in retrieval_expansion.expand(words, tokenize)]
    taken = set(words) | {entry.term for entry in added}
    for word, correction in retrieval_spelling.correct(typed, tokenize_item, excluded):
        if correction not in taken:
            added.append(Added(word, correction, SPELLING))
    return added


def describe(added: list[Added]) -> str:
    """`added` as one line, shared by `retrieval.md`'s `expanded` column
    and the CLI note so they cannot drift: `dt -> digital twin` (as pre-
    #1232 logs read), `strucutral ~> structural`, `;` between entries.
    """
    grouped: dict[tuple[str, str], list[str]] = {}
    for entry in added:
        grouped.setdefault((entry.source, entry.typed), []).append(entry.term)
    arrow = {ACRONYM: "->", SPELLING: "~>"}
    return "; ".join(
        f"{typed} {arrow[source]} {' '.join(terms)}" for (source, typed), terms in grouped.items()
    )


def announce(added: list[Added]) -> str:
    """Print the CLI's notes for `added`, and return `describe(added)`.

    On stderr: a genre skill parses `retrieve`'s stdout as a contract.
    `added` is what `retrieval.query_terms` returned, never recomputed
    (#953); `search()` never calls this, since printing is the caller's.
    """
    acronyms = [entry for entry in added if entry.source == ACRONYM]
    if acronyms:
        print(f"  [note] acronym expansion added: {describe(acronyms)}", file=sys.stderr)
    for entry in added:
        if entry.source == SPELLING:
            print(
                f"  [note] spelling: searched '{entry.term}' for '{entry.typed}'", file=sys.stderr
            )
    return describe(added)
