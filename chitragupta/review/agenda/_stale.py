"""R12: an item whose draft span is gone is dropped and reported, never
relocated.

The window this closes is a real one and it is the only failure mode in
the loop that destroys a person's own work. An aid runs and files its
`.json`. The author reads the worklist and revises the very passage it
found. `agenda-reviser` then runs, reads that same `.json`, and holds a
repair computed against text that no longer exists -- a `draft_text` to
use as an `Edit`'s `old_string`, aimed at a position the author has just
rewritten. Applying it overwrites the human's edit with a machine's
answer to a question nobody is asking any more.

**The answer is refusal, not reconciliation.** The item is dropped from
the worklist, named in a report of its own, and nothing is applied. The
finding is re-derived on the next agenda run against the current text,
where it will either still stand or have been fixed by the author's own
edit. Three alternatives were considered and each is refused for a
reason that is recorded rather than merely implied:

- **Merging the two edits**, as `llm_wiki` does for a regenerated page.
  A merge has to decide which of two edits wins, and this project's
  posture is that the human's wins by default. Refusal gets that for
  free and needs no policy.
- **Re-locating the span by similarity.** This authorises an edit on the
  evidence of a similarity score, which `docs/AUTO-IMPROVEMENT.md`
  already refuses for the verbatim scan's embedding tier, for the same
  reason. `tests/test_review_agenda.py::TestNoFuzzyRelocation` scans
  this package for a fuzzy matcher so the refusal cannot erode into a
  threshold later.
- **Locking the draft between runs.** A person editing their own draft
  is the point of the tool.

**What is actually checked, and what is not claimed.** An item's identity
(`_identity.item_id`) already hashes the span it was derived from, which
is what makes staleness detectable at all -- but that hash is over a
tuple including the class and the section, and for two classes the
hashed string is not the draft's own text (`prose` hashes
`rule\\x00match`; `verbatim-run` hashes the whitespace-collapsed
`fragment` where one is filed). So the check here is stated as what it
is: **the exact draft text the finding was derived from is no longer
present in the draft.** `Item.span` carries that text, and only where an
aid guarantees it is an exact substring of the draft -- `verbatim`'s
`draft_text` (`draft[char_start:char_end]` by construction, which is
what makes it usable as an `Edit` `old_string`) and `style_check`'s Vale
`Match`. Those two are exactly the classes that carry `unattended: true`
*and* a position in the draft, so the hazard is covered end to end.

`span` is `None` on every other class, and a `None` span is never
refused. That is not caution, it is correctness: `missing-citekey` and
`recorded-but-uncited` are derived from the dossier's record rather than
the draft's live markers, and the second by construction names a citekey
the draft does *not* cite -- a containment check would refuse it on
every run, on every draft. `misquoted`'s span lives in `evidence.md`.
An older report filed before `draft_text` existed also lands here, and
degrades to "not span-checked" rather than to a refusal.

Nothing is serialised beyond the refusal itself. The span never leaves
the process: `build_agenda` already holds both the aid's `.json` and the
current draft, so the check needs no new payload field and the agenda's
own `detail` stays thin by the decision that made it thin.

One consequence worth stating rather than engineering around: dropping
an item lowers a bare run's `objective_class_count`, so an author's edit
between two passes can make `agenda-reviser`'s strictly-falling
terminator read as progress no repair made. `--baseline` re-runs the
eight aids in front of the rebuild and is unaffected, and that is the
mode the R4 cycle uses.
"""

# The one sentence a refused item carries, so a reader of the payload is
# told why rather than left to infer it from the key's name. Stated as
# the check that actually ran -- see this module's docstring on why it is
# not called a span-hash comparison.
REFUSAL = "the draft text this finding was derived from is no longer present"


def partition(draft_text: str, items: list) -> tuple[list, list]:
    """`(live, refused)` for one item list against the draft as it now
    stands.

    Order is preserved in both halves, so the worklist a caller renders
    is the ordered one `_order.sort` produced minus the refusals, never a
    re-sorted list.
    """
    live, refused = [], []
    for item in items:
        stale = item.span is not None and item.span not in draft_text
        (refused if stale else live).append(item)
    return live, refused


def stale_dicts(refused: list) -> list[dict]:
    """The refusals as the payload publishes them.

    Deliberately narrower than `_render._item_dict`: a refused item is
    not a worklist entry and must not read like one. `section` is
    carried because the issue asks for it by name -- a refusal a person
    cannot locate in their own draft is barely a report -- and `detail`
    is not, because `detail` is the repair payload's key and there is no
    repair here.
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
    """The refusals as Markdown, or nothing at all when there are none.

    An empty section would be read as an assurance that staleness was
    checked and none found, which is true only of the run that wrote it;
    every other review aid in this layer states an absence in its
    Sources header rather than as an empty findings heading.
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
