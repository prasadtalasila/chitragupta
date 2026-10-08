# Repairing a `missing-citekey` item

Read this when the item in hand is of class `missing-citekey`. The step that sent
you here says which edit tool to use. Paths here are from the project
root.

**Repair a `missing-citekey` item.** The only unattended repair available
is a deletion: this skill may not run `corpus sync` (the user's write
lock) and may not fabricate a citekey. Remove the `[@citekey]` marker,
leaving the sentence standing -- never delete the sentence itself.
**Also drop the citekey from `evidence.md`** (and from `sections.md`'s row
for the section, on the next `dossier sections --citekeys --write`) --
`missing-citekey` is detected off the dossier's own record of what it
cites, not off the draft's live markers, so a repair that only edits the
draft leaves the item unresolved on the next agenda. This is the "writing
the dossier back" half of the revising skill's loop, made
explicit here because it is easy to miss for this one class. The now-
uncited claim becomes an `uncited-claim` item on the next agenda, a
**surfaced** class, so it is reported rather than silently dropped. Where
the sentence carries another surviving citation, only the marker for the
missing one goes, and `evidence.md` keeps that citekey's entry.

If the `evidence.md` entry is left in place -- because dropping it is a
judgement about evidence rather than a mechanical edit -- the next
agenda reports it as a `recorded-but-uncited` item, which is the state
the repair manufactures by construction. That is the intended outcome
and not a failure of the repair: it is now visible, surfaced for a
person, and removable with `dossier prune`. Before #701 it was
reported on no surface at all unless the dossier happened to carry a
`dossier stamp` baseline.
