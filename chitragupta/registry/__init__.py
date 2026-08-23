"""The three consistency registries a book is checked against.

`python -m chitragupta.draft registry build|check|excerpt` over a book whose
outline `chitragupta/spec/` holds and whose units `chitragupta/unit/` has accepted.
Three registries, all derived by a deterministic post-pass over
**accepted units only** (#138):

- **terminology and notation** -- a term is defined once, and the
  definition is where it was defined;
- **the claim register** -- what has been asserted, in which unit, with
  which citation;
- **the cross-reference graph** -- which unit points at what, and whether
  it resolves.

**Nothing here is written by an LLM**, which is the constraint that makes
them trustworthy at all: they are a reading of accepted prose, the way
`chitragupta/ledger.py` is a reading of a real bib file. Extraction reuses the
conventions the repository already has rather than inventing a second
set -- the `- **Term** -- definition` bullet the dossier glossary uses,
the sentence splitter the provenance aid uses, and the `## References`
cut-off `chitragupta/acronyms.py` measured against the real 15-chapter book.

**A cross-reference is never spelled `@id`.** That is a citekey position,
and a section id reaching it would put something the ledger has never
seen where only a real bibliography entry may go. Markdown cross-
references are `[text](#id)` and LaTeX ones `\\ref{id}`/`\\cref{id}`;
`tests/test_registry.py` pins that the citation gate reads neither.

**What these checks cannot see**, stated rather than left implied:
*contradiction*. Two chapters asserting opposite things is what #138 asks
for and is not deterministically decidable -- a duplicate is, and that is
what the claim register flags. The second human sign-off is what covers
the rest. docs/BOOKS.md carries this and the reason `check` exits 0
whatever it finds.
"""

import re
from pathlib import Path

from chitragupta import spec, unit

# Three conventions borrowed rather than re-derived. Each is private to
# the module that owns it; a second regex for the same shape is the
# "second way of doing something the codebase already does" that
# docs/CODE-STANDARDS.md calls the highest-value review finding here, and
# is worse than reaching across for the name. Promoting any of them to a
# public name belongs in its own PR, not this one.
from chitragupta.acronyms import _REFERENCES_HEADING
from chitragupta.dossier._citekeys import _GLOSSARY_TERM
from chitragupta.citation_gate import extract_citekeys
from chitragupta.sentences import split as split_sentences

# `[text](#some-id)` -- the Markdown cross-reference. Anchored on the
# closing bracket so a bare `(#id)` in prose is not read as one.
_MD_REFERENCE = re.compile(r"\]\(#([A-Za-z0-9][A-Za-z0-9._:-]*)\)")

# `\ref{id}`, `\cref{id}`, `\Cref{id}`, `\autoref{id}` -- the LaTeX ones.
_TEX_REFERENCE = re.compile(r"\\(?:auto|[cC])?ref\{([^}]+)\}")

# What a unit offers others to point at: a Pandoc `{#id}` attribute, or a
# LaTeX `\label{id}`. The outline's own unit ids are anchors too, and are
# added by `build` rather than matched here.
_MD_LABEL = re.compile(r"\{#([A-Za-z0-9][A-Za-z0-9._:-]*)\}")


_TEX_LABEL = re.compile(r"\\label\{([^}]+)\}")

# Everything a claim's identity ignores: case, punctuation and how the
# prose happened to be wrapped. Two units asserting the same thing with
# different spacing are one claim made twice, which is the finding.
_NOT_WORD = re.compile(r"[^a-z0-9]+")


def registry_dir(book) -> Path:
    """Where a book's three registries are written."""
    return spec.spec_dir(book) / "registries"


def definitions(text: str) -> list[tuple[str, str, str]]:
    """`(term, kind, definition)` for every definition bullet in `text`.

    `notation` rather than `term` when the term is written as code or
    maths -- `` `x_t` `` or `$x_t$` -- which is the only distinction
    between the two registries #138 asks for that a machine can draw
    without being told.
    """
    found = []
    for match in _GLOSSARY_TERM.finditer(text):
        term = match.group("term").strip()
        line_end = text.find("\n", match.end())
        definition = text[match.end() : line_end if line_end != -1 else len(text)].strip()
        kind = "notation" if term[:1] in "`$" and term[-1:] in "`$" else "term"
        found.append((term, kind, definition))
    return found


def _prose(text: str) -> str:
    """`text` with the parts no claim is made in removed.

    Two exclusions. A reference list is nothing but citation-bearing
    lines, so reading it as claims would fill the register with
    bibliography -- the same cut `chitragupta/acronyms.py` makes, measured
    there against the real book. And a definition bullet is a
    definition, already registered as one.
    """
    cut = _REFERENCES_HEADING.search(text)
    body = text[: cut.start()] if cut else text
    return "\n".join(line for line in body.splitlines() if not _GLOSSARY_TERM.match(line))


def claims(text: str) -> list[tuple[str, list[str]]]:
    """`(sentence, citekeys)` for every sentence in `text` that cites.

    Split per paragraph rather than over the whole unit, so a sentence
    cannot run across a blank line and swallow the heading or bullet
    above it -- which would make the same claim in two units look
    different for a reason that is about layout, not content.
    """
    found = []
    for paragraph in re.split(r"\n\s*\n", _prose(text)):
        for sentence in split_sentences(paragraph):
            citekeys = [key for _, key in extract_citekeys(sentence)]
            if citekeys:
                found.append((" ".join(sentence.split()), citekeys))
    return found


def claim_key(claim: str) -> str:
    """What makes two claims the same claim: the words, lowercased."""
    return _NOT_WORD.sub(" ", claim.lower()).strip()


def _unique(values: list[str]) -> list[str]:
    """`values` in first-seen order, without repeats -- a unit pointing
    at the same target twice is one edge, not two findings."""
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


def references(text: str) -> list[str]:
    """Every cross-reference target `text` points at, in order."""
    return _unique(_MD_REFERENCE.findall(text) + _TEX_REFERENCE.findall(text))


def labels(text: str) -> set[str]:
    """Every anchor `text` offers other units to point at."""
    return set(_MD_LABEL.findall(text)) | set(_TEX_LABEL.findall(text))


def _read_unit(book, unit_id: str, built: dict, anchors: set[str]) -> None:
    """Fold one accepted unit into the registries being built."""
    text = unit.draft_path(book, unit_id).read_text(encoding="utf-8")
    for term, kind, definition in definitions(text):
        built["terms"].append(
            {"term": term, "kind": kind, "unit": unit_id, "definition": definition}
        )
    for claim, citekeys in claims(text):
        built["claims"].append({"claim": claim, "unit": unit_id, "citekeys": citekeys})
    for target in references(text):
        built["xrefs"].append({"from": unit_id, "target": target})
    anchors |= labels(text)


def build(book) -> dict:
    """The three registries, plus the full anchor set, over the units a
    human has accepted.

    Units that are not accepted are named in `skipped` rather than
    silently left out: a registry built over half a book is not the same
    claim as one built over all of it, and a reader has to be able to
    tell which they are holding.
    """
    outline = unit.outline(book)
    built = {"accepted": [], "skipped": [], "terms": [], "claims": [], "xrefs": []}
    # Every id in the outline, not only the sections: "see Chapter 1" is
    # an ordinary cross-reference, and reporting it unresolved because a
    # chapter generates no prose of its own would be a finding about this
    # module rather than about the book.
    anchors = {entry["id"] for entry in outline}
    for section in [entry for entry in outline if entry["kind"] == "section"]:
        state = unit.state(book, section["id"])
        built["accepted" if state == "accepted" else "skipped"].append(section["id"])
    for unit_id in built["accepted"]:
        _read_unit(book, unit_id, built, anchors)
    for edge in built["xrefs"]:
        edge["resolves"] = edge["target"] in anchors
    built["anchors"] = sorted(anchors)
    return built


def _repeats(rows: list[dict], key: str) -> dict[str, list[dict]]:
    """Rows grouped by `key`, keeping only the keys more than one unit
    contributed to."""
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[key], []).append(row)
    return {
        value: found for value, found in grouped.items() if len({row["unit"] for row in found}) > 1
    }


def findings(built: dict) -> list[tuple[str, str]]:
    """`(kind, message)` for everything the three registries disagree on.

    Evidence for a human judgement, never a verdict -- which is why the
    caller prints these and exits 0 regardless. See docs/BOOKS.md.
    """
    found = []
    for term, rows in _repeats(built["terms"], "term").items():
        found.append(
            (
                "term",
                f"`{term}` is defined in more than one unit: "
                + ", ".join(sorted(row["unit"] for row in rows)),
            )
        )
    for rows in _repeats(
        [{**row, "key": claim_key(row["claim"])} for row in built["claims"]], "key"
    ).values():
        units = ", ".join(sorted({row["unit"] for row in rows}))
        found.append(("claim", f'the same claim is made in {units}: "{rows[0]["claim"]}"'))
    for edge in built["xrefs"]:
        if not edge["resolves"]:
            found.append(
                (
                    "xref",
                    f"{edge['from']} points at `{edge['target']}`, "
                    "which no unit or outline entry defines",
                )
            )
    return found


def excerpt(book, unit_id: str) -> dict:
    """What a unit's generation should be told about the rest of the book.

    The terminology the *other* accepted units already settled, and the
    ids available to point at. A unit is not told to conform to itself.

    Deliberately **not** part of `unit.contract`'s input digest: a
    registry grows with every acceptance, so hashing it in would mark
    every later unit stale each time one earlier is accepted -- which is
    exactly the cheap-regeneration property #137 exists for. docs/BOOKS.md
    has the argument.
    """
    built = build(book)
    return {
        "terms": [row for row in built["terms"] if row["unit"] != unit_id],
        "anchors": built["anchors"],
    }


# Re-exported so `from chitragupta import registry` reaches the entry point
# `chitragupta/draft.py` dispatches to, as `chitragupta/spec/` and `chitragupta/unit/` do. The
# position is load-bearing: `_cli` imports the names above from here.
# pylint: disable=wrong-import-position
from chitragupta.registry._cli import main
