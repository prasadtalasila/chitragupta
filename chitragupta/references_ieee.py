"""One IEEE-style bibliography entry, from a ledger row's fields.

Split from `chitragupta/references.py` (#441): `format_entry` and
everything it composes from -- author/title/venue/locator/publisher
formatting -- take only a citekey, title, year and a `bib_fields` dict
and return a string. None of it touches the ledger, a draft's text, or
`citation_gate`, which is what makes it a clean seam: `references.py`
imports `format_entry` from here, and nothing here imports back.
"""

import re

from chitragupta import bib_names


def _initials(first: str) -> str:
    """A given-name field as IEEE initials.

    `Jane Mary` -> `J. M.`, `J.-P.` -> `J.-P.`, `` -> ``.
    """
    out = []
    for part in first.replace(".", " ").split():
        # A hyphenated given name initializes on both halves ("Jean-Paul"
        # -> "J.-P."), which is IEEE's own rule and not what a naive
        # part[0] would give.
        out.append("-".join(f"{seg[0]}." for seg in part.split("-") if seg))
    return " ".join(out)


def _format_name(name: str) -> str:
    """One BibTeX author name in IEEE order: "Doe, Jane" -> "J. Doe".

    The given/family split itself lives in `bib_names`, shared with
    `bib_reader` -- this module reads the ledger's `bib_fields` column and
    never `bibliography.bib`, but the *grammar* for reading a name out of
    that column is the same grammar, and it used to exist here in a second
    copy. See that module for what the duplication actually risked.
    """
    name = name.strip()
    # Braced corporate authors ("{IEEE Standards Association}") are a
    # single unit, never split into given/family or initialized. Stays
    # here rather than moving into the shared helper: `_parse_authors`
    # does not do it, and hoisting it would change what the ledger
    # records rather than where the split lives.
    if name.startswith("{") and name.endswith("}"):
        return name[1:-1].strip()
    first, last = bib_names.split_name(name)
    initials = _initials(first)
    return f"{initials} {last}".strip()


def _format_authors(field: str) -> str:
    """A BibTeX author/editor field as an IEEE author list.

    IEEE abbreviates to "first author et al." past six names; below that
    it lists all of them, with "and" before the last.
    """
    names = [n.strip() for n in field.split(" and ") if n.strip()]
    if not names:
        return ""
    formatted = [_format_name(n) for n in names]
    if len(formatted) > 6:
        return f"{formatted[0]} et al."
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"


# Where the containing work's name lives, in the order BibTeX/biblatex
# variants prefer it. "booktitle" is checked last because an @inbook entry
# can carry both, and there the journal-shaped field is the wrong one.
_VENUE_FIELDS = ("journal", "journaltitle", "booktitle")


def _md_escape(text: str) -> str:
    """Neutralizes Markdown emphasis in a value pasted into an entry.

    A title like "The C_str_ Problem" or "A*B benchmarks" would otherwise
    silently italicize part of the reference list, and a citekey-labelled
    bibliography that renders differently from the bib file it came from
    is exactly the sort of quiet drift this project's citation rules
    exist to prevent.
    """
    return re.sub(r"([*_`\[\]])", r"\\\1", text)


def format_entry(citekey: str, title: str, year: str, fields: dict[str, str]) -> str:
    """One IEEE-style bibliography entry, without its "[n] " number.

    `fields` is the ledger's `bib_fields` for this citekey (see
    ledger_upsert._BIB_FIELDS_KEPT), and may be empty -- a row synced before that
    column existed, or an entry that genuinely carries nothing but a
    title. The entry then degrades to title and year rather than failing:
    a thinner reference is still a true one, and `sync` is what fixes it.
    """
    fields = {k.lower(): v for k, v in fields.items()}
    parts = [
        _authors_part(fields),
        _title_part(title, fields),
        _venue_part(fields),
        *_locator_parts(fields),
        _publisher_part(fields),
    ]
    if year:
        parts.append(_md_escape(str(year).strip()))

    entry = _join(parts)
    if not entry:
        return f"{citekey}."
    # A value can already end the sentence itself -- an undated entry's
    # year is the literal "n.d.", which would otherwise close as "n.d..".
    return entry if entry.endswith(".") else f"{entry}."


def _authors_part(fields: dict[str, str]) -> str:
    """Authors, or the editors marked as such when there are none."""
    authors = _format_authors(fields.get("author", ""))
    if not authors and fields.get("editor"):
        authors = f"{_format_authors(fields['editor'])}, Eds."
    return _md_escape(authors) if authors else ""


def _title_part(title: str, fields: dict[str, str]) -> str:
    """The title, quoted or italicised by IEEE's container rule.

    IEEE quotes the title of a work published *inside* something
    else (an article in a journal, a paper in proceedings) and
    italicizes the title of a work that is itself the publication (a
    book, a thesis, a standalone report). The presence of a
    container field is what distinguishes the two, and is more
    reliable here than the entry type: this corpus's exports use
    @misc for both preprints and books.
    """
    title = _md_escape((title or "").strip().rstrip("."))
    if not title:
        return ""
    has_container = any(fields.get(f) for f in _VENUE_FIELDS)
    return f'"{title},"' if has_container else f"*{title}*"


def _venue_part(fields: dict[str, str]) -> str:
    venue = next((fields[f] for f in _VENUE_FIELDS if fields.get(f)), "")
    if not venue:
        return ""
    venue = _md_escape(venue.strip())
    # "in" only for a paper inside a proceedings/edited volume, which
    # is what a booktitle (rather than a journal) means.
    prefix = "in " if fields.get("booktitle") and not fields.get("journal") else ""
    return f"{prefix}*{venue}*"


def _locator_parts(fields: dict[str, str]) -> list[str]:
    """Volume, number and pages, each only when present."""
    parts = []
    if fields.get("volume"):
        parts.append(f"vol. {_md_escape(fields['volume'])}")
    if fields.get("number"):
        parts.append(f"no. {_md_escape(fields['number'])}")
    if fields.get("pages"):
        # BibTeX page ranges are "1--10"; IEEE prints an en dash, and the
        # doubled hyphen is a TeX-ism that shouldn't reach a Markdown reader.
        pages = re.sub(r"-{2,}", "–", fields["pages"].strip())
        label = "pp." if re.search(r"[–,]", pages) else "p."
        parts.append(f"{label} {_md_escape(pages)}")
    return parts


def _publisher_part(fields: dict[str, str]) -> str:
    """The most specific issuing body the entry names, and only one."""
    for field_name in ("school", "institution", "publisher", "organization"):
        if fields.get(field_name):
            return _md_escape(fields[field_name].strip())
    return ""


def _join(parts: list[str]) -> str:
    """Comma-joins entry parts without doubling punctuation.

    A quoted title already carries IEEE's comma *inside* the quotes
    (`"Title,"`), so the separator before the next part is a space, not
    another comma -- otherwise every article entry reads `"Title,",
    *Journal*`.
    """
    out = ""
    for part in (p for p in parts if p):
        if not out:
            out = part
        elif out.endswith(',"'):
            out += f" {part}"
        else:
            out += f", {part}"
    return out
