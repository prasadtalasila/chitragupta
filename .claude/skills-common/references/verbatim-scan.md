# The verbatim scan: what it is and how to report it

Read this at the verbatim-scan step, once you have run the two commands
that step names: the section-map rebuild, then the scan. Paths here are
from the project root.

**A review aid, not a gate: it exits 0 either way, it cannot block the
draft, and it is never a condition of presenting.** It reports wording
the draft shares with **any** parsed source, cited or not -- including a
source the citing paragraph never names, and reuse in prose that cites
nothing, which no per-citekey check can see. It skips fenced code, so
commands and file contents in a draft do not light it up.

**Say what it did not check.** If `tiers_not_run` is not empty, quote
each reason as the scan wrote it, and where the reason names a fix
(`poetry install --with enrich`, `python -m chitragupta.enrich`) pass
that on once. It sees verbatim and near-verbatim reuse only, and
**genuine restatement is only detected where the embedding tier can
run**, so a clean scan is not a clean bill of health
(`docs/PLAGIARISM.md`).

**Show what it found** rather than summarising it away, and lead with
the `long` and `short` buckets. A `quoted` run that also cites its
source is a legitimate attributed quotation, so give those a count
rather than a list.

**Why the section map is rebuilt first.** The embedding tier compares
each section against the citekeys that section's `sections.md` row
records, so a table written earlier describes a draft that has since
been edited. If the rebuild exits 1 for a missing dossier, say so and
scan anyway.

**Keeping the report.** If the user wants the finding kept, add
`--write` to the scan: the report goes to `content/review/`, mirroring
the draft's path, beside any provenance and coverage reports for the
same draft.
