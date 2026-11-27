"""The three consistency registries a book is checked against.

Derived by a deterministic post-pass over **accepted units only**
(#138): terminology and notation (each unit's glossary since #1138 and
`math.md` `## Symbols` since #1143), the claim register, and the
cross-reference graph. **Nothing here is written by an LLM**, which is
what makes them trustworthy; extraction reuses the repository's
existing parsers.

**A cross-reference is never spelled `@id`**: that is a citekey
position. They are `[text](#id)` and `\\ref{id}`/`\\cref{id}`, and
`tests/test_registry.py` pins that the gate reads neither. Contradiction
is not deterministically decidable; the second human sign-off covers
it, and `check` exits 0 (docs/WRITE-A-BOOK.md).
"""

import re
from pathlib import Path

from chitragupta import spec, unit

# Borrowed private conventions rather than a second regex for the same
# shape (docs/CODE-STANDARDS.md's highest-value review finding).
from chitragupta.acronyms import _REFERENCES_HEADING
from chitragupta.dossier._glossary import _GLOSSARY_TERM
from chitragupta.citation_gate import extract_citekeys_from_line, is_latex
from chitragupta.registry import _symbols, _terms
from chitragupta.sentences import split as split_sentences

# Anchored on the closing bracket so a bare `(#id)` in prose is not one.
_MD_REFERENCE = re.compile(r"\]\(#([A-Za-z0-9][A-Za-z0-9._:-]*)\)")

_TEX_REFERENCE = re.compile(r"\\(?:auto|[cC])?ref\{([^}]+)\}")

# A Pandoc `{#id}` or LaTeX `\label{id}`; outline unit ids are added by
# `build`.
_MD_LABEL = re.compile(r"\{#([A-Za-z0-9][A-Za-z0-9._:-]*)\}")


_TEX_LABEL = re.compile(r"\\label\{([^}]+)\}")

# Case, punctuation and wrapping are ignored, so the same claim with
# different spacing is the duplicate finding.
_NOT_WORD = re.compile(r"[^a-z0-9]+")


def registry_dir(book) -> Path:
    return spec.spec_dir(book) / "registries"


def _prose(text: str) -> str:
    """`text` with the parts no claim is made in removed.

    Drops the reference list (as `chitragupta/acronyms.py` does) and
    definition-shaped bullets, whose home is the glossary.
    """
    cut = _REFERENCES_HEADING.search(text)
    body = text[: cut.start()] if cut else text
    return "\n".join(line for line in body.splitlines() if not _GLOSSARY_TERM.match(line))


def claims(text: str, *, latex: bool = False) -> list[tuple[str, list[str]]]:
    """`(sentence, citekeys)` for every sentence in `text` that cites.

    `latex` keeps a `.tex` citation between quotes from dropping out
    (#957). Split per paragraph, so a sentence cannot swallow the
    heading above it and make one claim look like two.
    """
    found = []
    for paragraph in re.split(r"\n\s*\n", _prose(text)):
        for sentence in split_sentences(paragraph):
            citekeys = extract_citekeys_from_line(sentence, latex=latex)
            if citekeys:
                found.append((" ".join(sentence.split()), citekeys))
    return found


def claim_key(claim: str) -> str:
    """What makes two claims the same claim: the words, lowercased."""
    return _NOT_WORD.sub(" ", claim.lower()).strip()


def _unique(values: list[str]) -> list[str]:
    """`values` in first-seen order, without repeats: one edge, not two
    findings."""
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


def references(text: str) -> list[str]:
    return _unique(_MD_REFERENCE.findall(text) + _TEX_REFERENCE.findall(text))


def labels(text: str) -> set[str]:
    return set(_MD_LABEL.findall(text)) | set(_TEX_LABEL.findall(text))


def _read_unit(book, unit_id: str, built: dict, anchors: set[str]) -> None:
    path = unit.draft_path(book, unit_id)
    text = path.read_text(encoding="utf-8")
    _terms.read_unit(unit_id, path, built)
    _symbols.read_unit(unit_id, path, built)
    for claim, citekeys in claims(text, latex=is_latex(path)):
        built["claims"].append({"claim": claim, "unit": unit_id, "citekeys": citekeys})
    for target in references(text):
        built["xrefs"].append({"from": unit_id, "target": target})
    anchors |= labels(text)


def build(book) -> dict:
    """The three registries, plus the full anchor set, over the units a
    human has accepted.

    Unaccepted units are named in `skipped`, so a reader can tell a
    half-book registry from a whole one.
    """
    outline = unit.outline(book)
    built = {
        "accepted": [],
        "skipped": [],
        "terms": [],
        "claims": [],
        "xrefs": [],
        "glossary": [],
        "no_glossary": [],
        "symbols": [],
        "math": [],
        "glossary_maths": [],
        "unnumbered": [],
    }
    # Every outline id, so "see Chapter 1" resolves, less the generated
    # pages (#1137), which have no label.
    anchors = {entry["id"] for entry in outline if entry["id"] not in spec.GENERATED}
    # Only *accepted* units: since #472 a section may be a heading inside
    # a chapter file, and only files are accepted.
    for entry in unit.acceptance_units(book):
        # A front- or back-matter chapter prints no number (#1137), which
        # the glossary's `\Cref` to its defining unit depends on.
        if spec.matter(entry) in (spec.FRONT, spec.BACK):
            built["unnumbered"].append(entry["id"])
        state = unit.state(book, entry["id"])
        built["accepted" if state == "accepted" else "skipped"].append(entry["id"])
    for unit_id in built["accepted"]:
        _read_unit(book, unit_id, built, anchors)
    for edge in built["xrefs"]:
        edge["resolves"] = edge["target"] in anchors
    built["anchors"] = sorted(anchors)
    # After every unit, since a link may name a term a later unit defines.
    built["unresolved_symbols"] = _symbols.resolve(built)
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

    Evidence for a human, never a verdict, so the caller exits 0.
    """
    found = _terms.findings(built) + _symbols.findings(built)
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

    What the *other* accepted units settled, and the ids to point at.
    Deliberately **not** in `unit.contract`'s digest: it grows with every
    acceptance and would mark later units stale (#137).
    """
    built = build(book)
    return {
        "terms": [row for row in built["terms"] if row["unit"] != unit_id],
        "symbols": [row for row in built["symbols"] if row["unit"] != unit_id and "key" in row],
        "anchors": built["anchors"],
    }


# Re-exported for `chitragupta/draft.py`; placed last because `_cli`
# imports the names above from here.
# pylint: disable=wrong-import-position
from chitragupta.registry._cli import main
