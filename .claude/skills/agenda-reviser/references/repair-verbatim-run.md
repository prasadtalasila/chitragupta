# Repairing a `verbatim-run` item

Read this when the item in hand is of class `verbatim-run`. The step that sent
you here says which edit tool to use. Paths here are from the project
root.

**Repair a `verbatim-run` item at severity `short`.** Look up
`detail.verbatim_id` in `content/review/<topic>/<stem>.verbatim.json`'s
`findings`, matched on `id`. It gives `draft_text`, `min_run`, the
`citekey` and the page range. `draft_text` is the exact passage,
including casing, punctuation and any mid-run citation marker -- it is
the exact text your edit replaces. If it does not match, the draft
almost certainly has CRLF line endings and the run spans a line break:
the payload carries the `\n` the file was read with, not the `\r\n` on
disk. Re-read the line and edit it by hand rather than widening the
search.

**Paraphrase** -- the default, and the only option for a `short` run:

- Preserve the claim. This is a rewording, not a retraction.
- Preserve the citation.
- Leave no run of `min_run` consecutive source words (the looked-up
  finding's own field).
- Prefer the smaller diff.

**Not done at the edit.** The repair is done only once the recheck
the step that sent you here names has run and accepted it, or it has
been reverted and logged.
