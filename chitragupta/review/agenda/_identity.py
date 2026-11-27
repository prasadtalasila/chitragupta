"""Stable identity for an agenda item, and the section it anchors to.

All extractors go through these two functions. `item_id` is position-free
like the aids' `finding_id`: a line-based id would rename every later item
after an edit, and survival across revisions could not be decided (R2).
"""

import hashlib

from chitragupta.dossier._sections import Section


def item_id(aid: str, cls: str, section: str | None, citekey: str | None, span: str) -> str:
    """A stable, position-free identity for one agenda item; `span` is
    matched text, never a line number.
    """
    digest = hashlib.sha256(
        f"{aid}\x00{cls}\x00{section or ''}\x00{citekey or ''}\x00{span}".encode()
    )
    return digest.hexdigest()[:12]


def section_anchor(sections: list[Section], line: int | None) -> str | None:
    """The title of the section containing `line`, or None when there is no
    line (e.g. `candidate`) or no heading covers it; neither is an error.
    """
    if line is None:
        return None
    for section in sections:
        if section.start <= line <= section.end:
            return section.title
    return None
