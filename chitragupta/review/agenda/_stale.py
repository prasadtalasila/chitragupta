"""R12: an item whose draft span is gone is dropped and reported, never
relocated.

It closes the one loop failure that destroys a person's work: the author
revises a passage after an aid filed its `.json`, and `agenda-reviser`
would apply a repair aimed at text that no longer exists, overwriting the
human's edit. The item is dropped, reported, and re-derived next run.
Rejected: merging edits (the human's must win, which refusal gives free);
relocating by similarity (an edit on a similarity score, refused as for
the embedding tier; `TestNoFuzzyRelocation` guards it); locking the draft.

The check is that the exact draft text the finding came from is no longer
present. `Item.span` carries it only where it is an exact substring:
`verbatim`'s `draft_text` and `style_check`'s Vale `Match`. Only
`verbatim-run` can actually be refused (#839): `prose` is re-derived from
the live draft each build, which `TestStalePartition` pins. Every other
class has `span=None` and is never refused; `recorded-but-uncited` names
a citekey the draft does not cite, so a containment check would always
fire. Older reports without `draft_text` degrade to "not span-checked".

Dropping an item lowers a bare run's `objective_class_count`, so an
author's edit can read as progress; `--baseline`, the R4 cycle's mode,
re-runs the aids and is unaffected.
"""

# The one sentence a refused item carries, stated as the check that ran.
REFUSAL = "the draft text this finding was derived from is no longer present"


def partition(draft_text: str, items: list) -> tuple[list, list]:
    """`(live, refused)` for one item list against the current draft, order
    preserved, so the worklist is `_order.sort`'s minus the refusals.
    """
    live, refused = [], []
    for item in items:
        stale = item.span is not None and item.span not in draft_text
        (refused if stale else live).append(item)
    return live, refused


def stale_dicts(refused: list) -> list[dict]:
    """The refusals as the payload publishes them, narrower than
    `_render._item_dict` so they never read as worklist entries: `section`
    so a person can locate it, no `detail` since there is no repair.
    """
    return [
        {
            "id": item.id,
            "class": item.cls,
            "section": item.section,
            "summary": item.summary,
            "refused": REFUSAL,
        }
        for item in refused
    ]


def stale_lines(refused: list) -> list[str]:
    """The refusals as Markdown, or nothing when there are none: an empty
    section would read as an assurance, and every aid states absences in
    its Sources header instead.
    """
    if not refused:
        return []
    lines = [
        "## Refused as stale",
        "",
        f"Dropped from the worklist, not repaired -- {REFUSAL}. Each is",
        "re-derived on the next run against the current text.",
        "",
    ]
    for item in refused:
        section = f" ({item.section})" if item.section else ""
        lines.append(f"- `{item.id}` [{item.cls}]{section}: {item.summary}")
    lines.append("")
    return lines
