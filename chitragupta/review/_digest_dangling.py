"""Does each run of a verbatim digest stand on its own? (#1172)

A digest is read without its sources open, so a copied run pointing at
something the digest lacks is a pointer to nothing. Three
`dangling-reference` shapes:

- **cross-reference** ("Fig. 5.13", "Eq. (5.1)", "Chapter 7"), except a
  figure the digest shows as `Figure N of [@key]`, for a run citing it.
- **reference-marker**: a bracketed `[2]` left in the text; the matcher
  drops these from the source, so removing them costs nothing.
- **opener**: a run whose first word refers back ("where", "this") with
  nothing before it from the same source. A drafter's `[see @a; @b]`
  sentence is a fine antecedent, and "where" after a displayed equation
  is fine.

Cross-references and openers are read in copied runs only: the drafter's
own "Section 2" or "This" usually points within the digest, which nothing
here can tell apart. Markers are read everywhere. The word list is the
anaphors #1172's sample opened on; advisory, never a gate.
"""

import re

from chitragupta.review._digest_runs import Run

_XREF = re.compile(
    r"\b(?P<kind>Fig(?:ure)?s?\.?|Eqs?\.|Equations?|Sects?\.|Sections?|Chap(?:ter)?s?\.?"
    r"|Ch\.|Tables?|Algorithms?|Listings?|Appendix)"
    r"\s*(?P<paren>\()?(?P<number>[A-Z]?\d+(?:\.\d+)*)(?(paren)\))"
)
_MARKER = re.compile(r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")
_ANAPHORS = frozenset(
    {
        "accordingly",
        "also",
        "consequently",
        "finally",
        "furthermore",
        "hence",
        "here",
        "however",
        "it",
        "moreover",
        "such",
        "then",
        "therefore",
        "these",
        "they",
        "this",
        "those",
        "thus",
        "where",
        "which",
    }
)
_FIRST_WORD = re.compile(r"[A-Za-z]+")


def _shown(kind: str, number: str, run: Run, shown: frozenset[tuple[str, str]]) -> bool:
    return kind.startswith("Fig") and any((key, number) in shown for key in run.citekeys)


def _references(run: Run, shown: frozenset[tuple[str, str]]) -> list[tuple[int, str, dict]]:
    found = []
    for line, sentence in zip(run.lines, run.sentences, strict=True):
        for match in _XREF.finditer(sentence):
            if not run.own and not _shown(match["kind"], match["number"], run, shown):
                found.append((line, sentence, {"kind": "cross-reference", "match": match[0]}))
        found += [
            (line, sentence, {"kind": "reference-marker", "match": match[0]})
            for match in _MARKER.finditer(sentence)
        ]
    return found


def _opener(run: Run) -> list[tuple[int, str, dict]]:
    if run.own or not run.citekeys or set(run.citekeys) <= set(run.follows or ()):
        return []
    if run.follows is None and run.after_math:
        return []
    word = _FIRST_WORD.match(run.sentences[0].lstrip(" ([\"'"))
    if word is None or word[0].lower() not in _ANAPHORS:
        return []
    return [(run.lines[0], run.sentences[0], {"kind": "opener", "match": word[0]})]


def dangling(run: Run, shown: frozenset[tuple[str, str]]) -> list[tuple[int, str, dict]]:
    return _opener(run) + _references(run, shown)
