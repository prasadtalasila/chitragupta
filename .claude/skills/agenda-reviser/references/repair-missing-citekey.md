# Repairing a `missing-citekey` item

Read this when the item in hand is of class `missing-citekey`: a key the
dossier declares that has left the ledger, or whose PDF no longer parses
(it is then still in the `.bib` but not citable). The step that sent
you here says which edit tool to use. Paths here are from the project
root.

**Repair a `missing-citekey` item.** The only unattended repair available
is a deletion: this skill may not run `corpus sync` (the user's write
lock) and may not fabricate a citekey. Remove the `[@citekey]` marker,
leaving the sentence standing -- never delete the sentence itself.
Do not touch `evidence.md` or `sections.md`: this skill's write-set is
the draft and `revisions.md`, and dropping a recorded key is the
author's call about their evidence. The now-uncited claim becomes an
`uncited-claim` item on the next agenda, a **surfaced** class, so it is
reported rather than silently dropped. Where the sentence carries another
surviving citation, only the marker for the missing one goes.

Removing the marker does not clear the item. Two things persist on the
next agenda while `evidence.md` or `sections.md` still hold the key. The
`missing-citekey` item itself, because it is detected off the dossier's
record and not off the draft's live markers. And a `recorded-but-uncited`
item, which is the state the repair manufactures by construction: the
draft no longer cites a key the dossier still records. Neither is a
failure of the repair, and neither is the intended end state. Both clear
only when the author runs `dossier prune`, which a person confirms
because a recorded key may instead be an uncited candidate. The reviser
does not run it. **Its report says so, naming the command**: "N
`missing-citekey` items remain until you run `dossier prune`", not a
statement that the residue is intended. Before #701 the residue was
reported on no surface at all unless the dossier carried a `dossier
stamp` baseline.
