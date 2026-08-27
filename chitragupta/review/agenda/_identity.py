"""Stable identity for an agenda item, and the section it anchors to.

Every item's id and section anchor go through the two functions here so
the per-class extractors in `_items.py` cannot each invent their own
convention. `item_id` keeps the same position-free discipline the seven
review aids' own `finding_id` functions already document --
`chitragupta/review/citation_provenance.py`'s reason applies verbatim: an
identity built on `line` would rename every remaining item the moment an
edit above it shifted line numbers, and nothing could then decide
whether a given item had survived a revision (R2).
"""

import hashlib

from chitragupta.dossier._sections import Section


def item_id(aid: str, cls: str, section: str | None, citekey: str | None, span: str) -> str:
    """A stable, position-free identity for one agenda item.

    `span` is a piece of matched text -- a claim, a sentence, a matched
    run -- never a line number. Two items with identical
    `(aid, cls, section, citekey, span)` are the same item across runs,
    the same convention the seven aids' own `finding_id` functions use.
    """
    digest = hashlib.sha256(
        f"{aid}\x00{cls}\x00{section or ''}\x00{citekey or ''}\x00{span}".encode()
    )
    return digest.hexdigest()[:12]


def section_anchor(sections: list[Section], line: int | None) -> str | None:
    """The title of the section containing `line`, or None.

    None covers two different states the same way: `line` itself is
    `None` (no position applies, e.g. a `candidate` item), or the draft
    has no heading covering it (a citation before the first heading, the
    same "unattributed" case `dossier.attribute_citekeys` names). Both
    mean "no section to anchor this item to" and neither is an error.
    """
    if line is None:
        return None
    for section in sections:
        if section.start <= line <= section.end:
            return section.title
    return None
