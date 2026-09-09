"""The author's own abstract, lifted out of the structural passage
sidecar -- extraction, never summarisation.

This is what `chitragupta/tldr.py` falls back to when nobody has written a
TL;DR by hand. The words are the authors' own, so there is no
hallucination surface and no LLM call: issue #401 proposed a two-path
design where a paper *without* a detectable abstract had its whole text
sent to a model, and that half is declined. A document with no abstract
reports that it has none.

**Why the sidecar and not `content/parsed/<citekey>.txt`.** The obvious
implementation is a regex over the flattened text, and it is the one that
issue and `docs/TLDR.md` originally described. The flattened file has lost
the one thing the job needs: Docling resolves reading order and labels
each item, and `content/docling/<citekey>.passages.json` already carries
both. Recall is the same either way -- 342 of 498 real documents against
the regex's 337 -- so the sidecar buys nothing in coverage and everything
in *precision*, because "stop at the next `section_header`" is a
structural fact where "stop after N words" is a guess.

Note what Docling does *not* provide, since it is the first thing a reader
assumes: there is no `abstract` label. `DocItemLabel` runs
caption/chart/code/.../section_header/table/text/title, and none of them
marks an abstract semantically. Structure here means reading order and
heading boundaries, nothing more, which is why the two openers below are
matched on their text.

**The guards withhold rather than trim, and the asymmetry is the reason.**
A false negative reports "no abstract available" for a paper that has one,
and costs a reader one `less content/parsed/<citekey>.txt`. A false
positive publishes something that is not an abstract as though the authors
wrote it. The three guards are therefore set where measurement put them,
against this project's own 498-document corpus, and each is a real
failure that was read rather than imagined:

- `MAX_LEAD_ITEMS` -- a genuine opener sits at median item #5 (inline) or
  #7 (heading), p90 #21. `slavic_python_2025` matched an inline `Abstract`
  at item #155 and `akiki_resources_2025` at #93, both capturing
  class-diagram text. The cost is stated rather than hidden: a real
  chapter abstract deep inside a whole-book PDF is withheld too --
  `fitzgerald_engineering_2024-1`, at item #407.
- `MAX_BODY_ITEMS` -- five documents opened with a correct abstract and
  then ran on, because no `section_header` and no `Keywords` line arrived
  to stop them; `humlum_large_2025` swallowed 1442 words that way. The cap
  counts *items* rather than words on purpose: a word cap discards a
  correct abstract whose real text sits in its first 200 words.
- `MIN_BODY_WORDS`/`MAX_BODY_WORDS` -- a length sanity check on the
  result, not a content check. The longest genuine abstract measured here
  is 321 words and the p90 is 243, so anything past the ceiling means the
  stop rule failed. The floor is 40 rather than the 60 issue #401
  proposed because `lin_utwin_2023`'s genuine abstract is 58 words;
  `deslauriers_everyday_2022`'s title-and-affiliations false positive
  falls under it at 35.

Together those yield 318 of 498 (63.9%), slightly under the flat-text
regex's 68% and deliberately so -- the difference is the withheld set.

Stdlib only, and that is load-bearing rather than incidental:
`chitragupta/tldr.py` is a tier-1 `chitragupta.draft` command that must
run under bare `python3` with no venv (docs/ARCHITECTURE.md), so this may
import nothing heavier than `chitragupta.passages`, itself stdlib. The
`sentence_transformers` centroid design issue #401 rejected on
dependency-boundary grounds would have broken exactly that.
"""

import re

from chitragupta import passages

# A sentinel distinct from None, because "this paper has no abstract" and
# "there is no sidecar, so nothing here can tell" are different answers
# and only one of them is a statement about the paper. Collapsing them
# would report "no abstract available" for a `pdftotext`-parsed document
# whose abstract is sitting in the PDF unread.
#
# **Compare it with `is`, never `==`.** It is a `str` so that `extract`'s
# return stays `str | None` rather than widening to `object` for one
# case, which costs every caller an annotation to carry a value none of
# them wants to read. The identity check is what keeps that safe: a real
# body is always built by the `" ".join` below, so it is a fresh object
# and can never *be* this one -- where `==` would mistake a paper whose
# extracted text happened to be this word for a paper nobody could read.
UNKNOWN = "unknown"

# `Abstract` alone on its own line, optionally numbered -- the heading
# form. Anchored at both ends so a section called "Abstract syntax tree"
# is not a match.
_HEADING = re.compile(r"^(\d+\s*[.)]?\s*)?abstract\s*[:.—-]?$", re.I)

# The same word opening a paragraph that then continues into the abstract
# itself, which is how Docling emits it for 210 of the 342 documents where
# it is found at all -- `Abstract At the heart of a digital twin is...`.
# The captured group is the first character of the real body, so the
# marker word can be dropped without also dropping the sentence.
_INLINE = re.compile(r"^abstract\s*[:.—-]?\s+(\S)", re.I)

# What ends an abstract when no `section_header` does. These arrive as
# ordinary text as often as as a heading, so the stop cannot rely on the
# label alone.
#
# `chitragupta/enrich/keyword_extract.py`'s `_MARKER` matches two of the
# same words and is deliberately not shared with this. It is looking for
# the keyword declaration in order to *read* it; this is looking past the
# abstract's end in order to stop. Same vocabulary, opposite purpose --
# and reaching into `chitragupta/enrich/` from a tier-1 drafting module
# would breach the boundary that kept this module stdlib-only in the
# first place, to share one alternation.
_STOP = re.compile(r"^(keywords?|key words|index terms|\d*\s*\.?\s*introduction)\b", re.I)

# Docling's labels for running prose. `list_item` is deliberately absent:
# an abstract is paragraphs, and admitting list items pulls in the table
# of contents that follows one in a report.
_PROSE = ("text", "paragraph")

MAX_LEAD_ITEMS = 40
MAX_BODY_ITEMS = 3
MIN_BODY_WORDS = 40
MAX_BODY_WORDS = 400


def _opener(found: list) -> tuple[int, list[str]] | None:
    """Where the abstract starts, as (index after the marker, body so
    far), or None if no marker sits within the lead window."""
    for i, passage in enumerate(found[:MAX_LEAD_ITEMS]):
        text = (passage.text or "").strip()
        if passage.label == "section_header" and _HEADING.match(text):
            return i + 1, []
        if _INLINE.match(text) and passage.label in (*_PROSE, "section_header"):
            return i + 1, [_INLINE.sub(r"\1", text, count=1)]
    return None


def _body(found: list, start: int, body: list[str]) -> str:
    """The paragraphs from `start` that belong to the abstract."""
    for passage in found[start:]:
        if len(body) >= MAX_BODY_ITEMS:
            break
        text = (passage.text or "").strip()
        if passage.label == "section_header" or _STOP.match(text):
            break
        # A caption or a formula between two paragraphs is skipped rather
        # than treated as the end: Docling interleaves them by page
        # position, so one sitting inside an abstract's span does not mean
        # the abstract stopped there.
        if passage.label in _PROSE and text:
            body.append(text)
    return " ".join(body)


def extract(citekey: str) -> str | None:
    """`citekey`'s abstract, None if the paper has none, or `UNKNOWN` if
    there is no structural sidecar to look in.

    Derived on every call and never cached. That is not an oversight: an
    abstract is free to re-derive, so a stored copy could only ever go
    stale against a re-parse that this cannot. `chitragupta/tldr.py`'s
    fingerprint machinery exists for the summaries a person writes, which
    genuinely cannot be recovered.
    """
    found = passages.structural_passages(citekey)
    if found is None:
        return UNKNOWN
    opener = _opener(found)
    if opener is None:
        return None
    text = _body(found, *opener)
    if not MIN_BODY_WORDS <= len(text.split()) <= MAX_BODY_WORDS:
        return None
    return text
