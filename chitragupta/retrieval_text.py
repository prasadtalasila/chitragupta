"""Where a document's own bibliography starts, so BM25 stops indexing it.

`chitragupta/retrieval.py`'s `_full_text` used to hand the whole of
`content/parsed/<citekey>.txt` to the tokenizer, reference list included.
So every paper carried dozens of *other* papers' titles as its own body
text, and a short query naming a subject matched the bibliography of
every paper that merely cites work on that subject -- the same
"mentions it in passing" failure a title weight addresses, from a
different cause.

Measured on this corpus (497 parsed items, all with a corpus-layer
passage sidecar), with the locator below:

| | |
| --- | --- |
| Items with a locatable reference-section header | 459 of 497 |
| Median share of a document's BM25 tokens after it | 16.0% |
| Maximum share | 80.4% |
| Corpus-wide | 669,795 of 4,246,711 indexed tokens = **15.8%** |

It costs twice. Spurious term frequencies, and an inflated `length`, so
a paper with a long reference list is penalised by BM25's own length
normalization for text that is not its own.

**A structural cut, not a semantic one, and the distinction is the whole
mechanism.** Docling has no `reference` label -- the same caveat
`chitragupta/_abstract.py` records about there being no `abstract` label.
What identifies the span is a `section_header` passage whose text reads
`references` / `bibliography` / `works cited`, and everything from the
last such header onward. Nothing here reads a reference *entry*; the
header's position is the entire signal.

**Two-step, and deliberately so.** The sidecar decides *whether* there is
a bibliography; a line-anchored search decides *where* it starts in the
flattened text. Regexing the `.txt` alone to decide was rejected --
`pdftotext -layout` splices two-column pages, so a header can land
mid-line -- and that rejection still holds, because this module never
reaches the deciding step without a sidecar, which only a
reading-order backend writes. The locating step is safe for the same
reason: a sidecar means the text beside it is Docling's markdown export,
which has real line structure to anchor on.

Backend-dependent in exactly the way `chitragupta/retrieval.py`'s
docstring already licenses: a `pdftotext` parse leaves no sidecar, so
those items keep today's behaviour, indexed whole.

Measured against the alternative locator, a plain `rfind` of the header
text: both located the header in all 459 items, and they agreed on every
one to within the three characters of the `## ` markdown heading mark.
The line-anchored form is kept because it cannot match an occurrence
mid-sentence, which `rfind` can and which would truncate a document at
its own prose.
"""

import json
import re
import sqlite3
from pathlib import Path

from chitragupta import passages

__all__ = ["body_before_references"]

# What a reference section calls itself. Anchored at both ends against
# the *header's own text*, never against a line of body prose, so the
# leading number a numbered heading carries ("5. References") is allowed
# and a sentence containing the word is not. `\W*` rather than `\s*` so a
# trailing colon or a leading bullet does not defeat the match.
_REFERENCE_HEADING = re.compile(
    r"\W*\d*\.?\s*(?:references?|bibliography|works\s+cited)\W*\Z", re.I
)


def _reference_header(citekey: str) -> str | None:
    """The text of the last reference-section header in `citekey`'s
    corpus-layer sidecar, or None if there is no sidecar or no such
    header.

    Reads the sidecar file directly rather than through
    `passages.structural_passages`, because that function climbs the
    ladder into the enrichment layer's own sidecar (rung 1) and
    `chitragupta/retrieval.py` promises that running the enrichment layer
    does not change what BM25 ranks. Rung 2 only, so the promise holds.

    A damaged or hand-edited file reads as "no header" rather than
    raising: falling back to indexing the document whole is the same
    outcome as the 38 items that have no header at all, and is what this
    module's failure should cost.
    """
    try:
        records = json.loads(passages.sidecar_path(citekey).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(records, list):
        return None
    found = None
    for record in records:
        if not isinstance(record, dict) or record.get("label") != "section_header":
            continue
        text = record.get("text")
        if isinstance(text, str) and _REFERENCE_HEADING.fullmatch(text.strip()):
            found = text.strip()
    return found


def _cut_offset(body: str, header: str) -> int | None:
    """Offset of the last line of `body` that *is* `header`, or None.

    Compared line by line rather than by a substring search: a heading
    mark (`## References`) has to be tolerated, and an occurrence inside a
    sentence has to be refused. Those two requirements are the same
    requirement, and a whole-line comparison is what satisfies both.
    """
    want = header.lower()
    offset = 0
    cut = None
    for line in body.splitlines(keepends=True):
        if line.lstrip("#").strip().lower() == want:
            cut = offset
        offset += len(line)
    return cut


def body_before_references(body: str, citekey: str) -> str:
    """`body` truncated at `citekey`'s reference-section header.

    Returned unchanged when there is no sidecar, no reference header in
    it, or no line in `body` that matches the header -- three different
    reasons that all mean the same thing to a caller, which is why they
    are not distinguished in the return.
    """
    header = _reference_header(citekey)
    if header is None:
        return body
    cut = _cut_offset(body, header)
    return body if cut is None else body[:cut]


def _full_text(item: sqlite3.Row) -> str:
    """The text BM25 indexes for `item`: its title, then its parsed body
    up to that document's own bibliography.

    Lives here rather than in `chitragupta/retrieval.py`, where it was
    written, because the truncation above gave it a second input -- the
    corpus layer's passage sidecar -- and a function that reads the
    sidecar belongs beside the code that interprets it. `retrieval.py`
    and `chitragupta/retrieval_cli.py` both import it from here.

    Every caller gets the truncation, which is deliberate and is two of
    the three things it buys. `_tokenize_item` gets it, so a document's
    `length` stops counting other people's reference lists against it.
    `search`'s snippet gets it, so a returned window can no longer be
    drawn from a bibliography. And `chitragupta/retrieval_cli.py`'s
    `evidence` gets it, so a window transcribed into a dossier cannot be
    one either -- not asked for by the issue this implements, and the
    same defect, so it would have been strange to leave.
    """
    text_parts = [item["title"] or ""]
    # A non-'parsed' status means parsed_path may point at a superseded
    # version's text (or none at all) -- mark_parse_failed and a
    # hash-changed re-sync both leave the column set without updating what
    # it names (#490). overlap_index_ledger.py already gates on status;
    # this was BM25 retrieval and evidence's own read serving the stale
    # text as current.
    if item["status"] == "parsed" and item["parsed_path"]:
        try:
            body = Path(item["parsed_path"]).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
        else:
            text_parts.append(body_before_references(body, item["citekey"]))
    return "\n".join(text_parts)
