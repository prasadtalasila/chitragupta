"""One IEEE-style bibliography entry, from a ledger row's fields (#441).

Takes only a citekey, title, year and `bib_fields`; nothing here touches
the ledger or imports back from `references.py`.
"""

import re

from chitragupta import bib_names


def _initials(first: str) -> str:
    """A given-name field as IEEE initials: `Jane Mary` -> `J. M.`,
    `J.-P.` -> `J.-P.`, `` -> ``."""
    out = []
    for part in first.replace(".", " ").split():
        # A hyphenated given name initializes on both halves, IEEE's rule.
        out.append("-".join(f"{seg[0]}." for seg in part.split("-") if seg))
    return " ".join(out)


def _format_name(name: str) -> str:
    """One BibTeX author name in IEEE order: "Doe, Jane" -> "J. Doe".
    The given/family grammar is `bib_names`', shared with `bib_reader`.
    """
    name = name.strip()
    # Braced corporate authors are one unit. Kept here, not in the shared
    # helper, which would change what the ledger records.
    if name.startswith("{") and name.endswith("}"):
        return name[1:-1].strip()
    first, last = bib_names.split_name(name)
    initials = _initials(first)
    return f"{initials} {last}".strip()


def _format_authors(field: str) -> str:
    """A BibTeX author/editor field as an IEEE author list.

    "et al." past six names. BibTeX's "and others" renders as "et al.",
    never as an author named "others". Split on a zero-width "and",
    because bibtexparser keeps line wraps inside the field (as in
    `bib_reader._parse_authors`).
    """
    names = [n.strip() for n in re.split(r"(?<=\s)and(?=\s)", field) if n.strip()]
    truncated = bool(names) and names[-1].lower() == "others"
    if truncated:
        names = names[:-1]
    if not names:
        return ""
    formatted = [_format_name(n) for n in names]
    if truncated or len(formatted) > 6:
        return f"{formatted[0]} et al."
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"


# The container's name field, in preference order: an @inbook can carry
# both, and there "booktitle" is the right one.
_VENUE_FIELDS = ("booktitle", "journaltitle", "journal")


def _md_escape(text: str) -> str:
    """Neutralizes Markdown emphasis in a value pasted into an entry, so
    "The C_str_ Problem" cannot silently italicize the reference list.
    """
    return re.sub(r"([*_`\[\]])", r"\\\1", text)


def format_entry(citekey: str, title: str, year: str, fields: dict[str, str]) -> str:
    """One IEEE-style bibliography entry, without its "[n] " number.

    `fields` may be empty (an old row, or a title-only entry); the entry
    then degrades to title and year: thinner but true, and `sync` fixes it.
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
    # "n.d." already ends the sentence; avoid "n.d..".
    return entry if entry.endswith(".") else f"{entry}."


def _authors_part(fields: dict[str, str]) -> str:
    """Authors, or the editors marked as such when there are none."""
    authors = _format_authors(fields.get("author", ""))
    if not authors and fields.get("editor"):
        authors = f"{_format_authors(fields['editor'])}, Eds."
    return _md_escape(authors) if authors else ""


def _strip_trailing_period(title: str) -> str:
    """Drops one trailing sentence-ending period, but not an abbreviation's
    ("U.S." would become "U.S," after the appended comma)."""
    if not title.endswith(".") or re.search(r"(?:^|\.)[A-Za-z]\.$", title):
        return title
    return title[:-1]


def _title_part(title: str, fields: dict[str, str]) -> str:
    """The title, quoted or italicised by IEEE's container rule.

    Quoted when the work sits inside a container, italicised when it is
    the publication. Decided by a container field, not the entry type:
    this corpus's exports use @misc for preprints and books alike.
    """
    title = _md_escape(_strip_trailing_period((title or "").strip()))
    if not title:
        return ""
    has_container = any(fields.get(f) for f in _VENUE_FIELDS)
    return f'"{title},"' if has_container else f"*{title}*"


def _venue_part(fields: dict[str, str]) -> str:
    field_name = next((f for f in _VENUE_FIELDS if fields.get(f)), "")
    if not field_name:
        return ""
    venue = _md_escape(fields[field_name].strip())
    # "in" only for a paper in a proceedings or edited volume (booktitle).
    prefix = "in " if field_name == "booktitle" else ""
    return f"{prefix}*{venue}*"


def _locator_parts(fields: dict[str, str]) -> list[str]:
    """Volume, number and pages, each only when present."""
    parts = []
    if fields.get("volume"):
        parts.append(f"vol. {_md_escape(fields['volume'])}")
    if fields.get("number"):
        parts.append(f"no. {_md_escape(fields['number'])}")
    if fields.get("pages"):
        # IEEE prints an en dash for "1--10" and "1-10" alike.
        pages = re.sub(r"(?<=\d)-+(?=\d)", "–", fields["pages"].strip())
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
    """Comma-joins entry parts without doubling punctuation: a quoted
    title carries its comma inside (`"Title,"`), so a space follows.
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
