"""Does each run of a verbatim digest stand on its own? (#1172)

A digest is read without its sources open, so a copied run that points
at something the digest does not contain leaves the reader holding a
pointer to nothing. Three shapes, each a `dangling-reference`:

- **cross-reference**: "Fig. 5.13", "Eq. (5.1)", "Sect. 6.4.3",
  "Chapter 7" -- a numbered item of the source, or of a book the digest
  is not. A figure the digest shows, captioned `Figure N of [@key]`, is
  the one exception, for a run citing that key.
- **reference-marker**: a bracketed `[2]` or `[ 24]` left in the text.
  The matcher drops these from the source, so removing them costs
  nothing; leaving them points at a bibliography the digest does not
  have.
- **opener**: a copied run whose first word refers back -- "where",
  "thus", "this" -- with nothing before it from the same source: it
  opens its paragraph, or follows a run that cites none of its sources.
  A drafter's own `[see @a; @b]` sentence is a fine antecedent for a run
  from `@b`. A paragraph
  right after a displayed equation may open on "where"; that is what
  the equation is for.

Cross-references are read in copied runs only: a sentence of the
drafter's own saying "Section 2 compares them" points into the digest,
and nothing here can tell that from a pointer out of it (#1172 review).
A reference marker is read everywhere. The opener rule reads copied
runs only. A sentence of the drafter's own
opening on "This" usually refers to the drafter's previous sentence, and
nothing here can see which. The word list is the anaphors the sample
digest of #1172 actually opened runs on, plus their obvious siblings; it
is advisory like every finding of this aid and never gates.

Stdlib only, interpreter tier 1.
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
    """`(line, sentence, detail)` per dangling reference in `run`."""
    return _opener(run) + _references(run, shown)
