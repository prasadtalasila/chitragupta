"""The words a query is ranked on beyond those typed, and how they are shown.

Two sources add words to a query: acronym expansion (#789,
`retrieval_expansion.py`), `DT` adding "digital twin", and spelling
correction (#1232, `retrieval_spelling.py`), `strucutral` adding
"structural". `retrieval.query_terms` calls `added_terms` once, and every
path that ranks or windows a query reads the result (#953). The CLI note
and the `--log` record read the same entries, so neither can describe an
addition that was not ranked.

Each entry carries its source, because the two read differently to a
person: an acronym's terms are what it stands for, a correction is a
guess at what was meant. Both read the *typed* terms only -- a correction
is never acronym-expanded, an expansion is never corrected -- and a word
both would add is added once, by the acronym.
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


def added_terms(typed: list[str], tokenize, tokenize_item, excluded) -> list[Added]:
    """What to rank `typed` with beyond itself: acronym expansions in
    `expand`'s order, then spelling corrections in query order.

    The tokenizers and `excluded` (`retrieval._INTERROGATIVES`) are passed
    in because `chitragupta.retrieval` imports this module. A query with
    no terms reads no vocabulary.
    """
    if not typed:
        return []
    added = [Added(a, t, ACRONYM) for a, t in retrieval_expansion.expand(typed, tokenize)]
    expanded = {entry.term for entry in added}
    for word, correction in retrieval_spelling.correct(typed, tokenize_item, excluded):
        if correction not in expanded:
            added.append(Added(word, correction, SPELLING))
    return added


def describe(added: list[Added]) -> str:
    """`added` as one line: `retrieval.md`'s `expanded` column and the
    CLI's acronym note both use it, so the two cannot drift.

    An acronym and the terms it contributed (`dt -> digital twin`), as
    every log written before #1232 already reads; a correction as
    `strucutral ~> structural`; semicolons between entries. Empty string
    for an empty list.
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

    On stderr, beside the CLI's "too short to search on" note: a genre
    skill parses `retrieve`'s stdout as a documented contract, and a note
    about the query is not a result. One acronym note for all expansions,
    as before #1232, and one line per correction. Prints nothing and
    returns `""` when nothing was added.

    `added` is what `retrieval.query_terms` returned, never a second
    computation (#953). `search()` never calls this: what a library adds
    to a query is the caller's to read, not the ranker's to print.
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
