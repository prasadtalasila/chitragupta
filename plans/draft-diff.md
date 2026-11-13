# Draft versions and a redline diff of a revision

Status: **plan.** Written 2026-11-13. Issue to be filed; rename this
file `<issue>-draft-diff.md` when it is.

**Written for** whoever builds draft snapshots and `draft diff`, and
whoever later changes a reviser skill's closing step. **Assumed:**
[docs/DOSSIER.md](../docs/DOSSIER.md),
[docs/RENDERING-FLOW.md](../docs/RENDERING-FLOW.md) and the three
reviser skills as they stood at v6.170.2. **Not covered here:** accepting
or rejecting a hunk (track changes), and diffing an assembled book; both
are deferred, see the last section.

## What is missing

A revision is reviewed by reading the whole draft again. The revisers
edit `content/drafts/<path>` in place and keep no earlier copy:
`dossier stamp` records a fingerprint, which says *that* the text moved
and not *what* moved, and `dossier export` is a backup only
agenda-reviser takes. `content/` is outside git on purpose
([docs/MIGRATION.md](../docs/MIGRATION.md)), so git cannot supply the
earlier text either. agenda-reviser already ends with "Show the diff",
and nothing produces one.

## Decisions (user, 2026-11-12 and 2026-11-13)

1. **Readers.** The author, checking what a reviser just did, first; a
   supervisor or co-author, sent a PDF, second. One diff serves both.
2. **Baseline.** By default, the version taken just before the latest
   revision pass. `--against` picks a named milestone, a version
   number, or any file.
3. **Content.** Word-level prose changes; citekeys added and dropped,
   listed explicitly; figures added, removed or redrawn; sections added,
   removed or moved as a summary.
4. **Why.** Each changed section links to its `revisions.md` entry,
   through a new machine-readable `Sections:` line in each entry.
   Entries without one appear only in a list at the top.
5. **Read-only.** No accept/reject.
6. **Scope.** Every draft genre. Books later.
7. **Snapshots** live in the dossier, are taken by `mark-revision`
   automatically and by `dossier snapshot --label` on request, skip a
   draft whose fingerprint matches the latest one, and are all kept.
   Each holds the draft source and both forms (`.tex` and `.txt`) of
   every figure the draft names.
8. **Labels.** An automatic snapshot is numbered only; the label the
   reviser passes to `mark-revision` is stored as its description.
   Named milestones come from the author alone; a reviser runs
   `dossier snapshot` only with a name the author gave.
9. **Engine.** latexdiff for the PDF; our own Python for the change
   report. latexdiff is optional: without it the report still works
   and `--format pdf` fails with an install hint.
10. **Redline approach A.** Render both versions with citations
    deferred to bibtex, latexdiff them, compile once.
11. **Withdrawn citations, option (a).** On the old side only, a
    citation whose key is no longer citable becomes the plain words
    `(citation withdrawn)` before rendering. The gate runs unchanged
    on both sides.
12. **Figures** are shown as they are now, with a margin flag; never
    redlined inside.
13. **No filter** for spelling-only changes.
14. **Status of the output.** Never gated, never a deliverable, never a
    source. Its header says "Changes since <ref> — review copy".
15. **Revisers** end by running `draft diff` and showing the report.
16. **Install scripts** gain latexdiff.
17. **Delivery.** One issue, one PR carrying this plan, snapshots,
    `draft diff`, the install changes and the reviser changes
    (revised 2026-11-13 from two PRs).

## Spike findings (2026-11-13)

A throwaway run on a copy of `docs/examples/sample-project`, synced,
with an old and a new survey differing by a reworded phrase, a new
citation, a multi-citation change, an equation, a table cell, a moved
section, a dropped sentence and a redrawn figure; latexdiff 1.4.0 from
CTAN; `latexmk -lualatex`. Nothing was kept.

| Finding | Consequence for the design |
| --- | --- |
| A standalone render resolves citations to text (`\citeproc{ref-key}{[1]}`); one new citation renumbers every later one. latexdiff marked 25 changes; with `\citep{key}` on both sides, 8 | Both sides render with deferred citations (§3) |
| A thesis `.tex` fragment's standalone render also goes through citeproc | It takes the same deferred mode; no special case |
| latexdiff's default `UNDERLINE` markup needs `ulem.sty`, which is not installed: the diff does not compile | Markup is redefined with `lua-ul`, already installed with `texlive-luatex` |
| `CFONT` compiles but sets deletions in a tiny font | Not used |
| `--preamble` needs the Perl module `Encode::Locale`, absent with the bare script | The DIF preamble is patched in post-processing instead |
| A redrawn figure behind `\input` shows no mark; `--flatten` shows none either and needs a `.bbl` per side | The margin flag from the change report is the only figure signal; no `--flatten` |
| `--math-markup=coarse` strikes and replaces a changed fraction whole; a table cell is marked alone | Kept as the default |
| A moved section is one whole insertion plus one whole deletion | The report calls it moved; margin notes say so in the PDF |
| `[citation withdrawn]` lost its brackets: latexdiff reads pandoc's `{[}` as a command | The token is `(citation withdrawn)` |
| Margin notes at a 1 in margin wrap a word per line | The diff renders with a wider outer margin |

## Design

### 1. Snapshots

```text
content/dossiers/<path>/versions/
  001/
    <stem>.<md|tex>          # the draft, byte for byte
    figures/<name>.tex       # each figure the draft's `figure:` markers name
    figures/<name>.txt
    snapshot.json
  002-sent-to-supervisor/
```

- `NNN` is a running number and the identifier; a manual label adds a
  slug suffix. Labels are unique within a draft and may not be all
  digits, so `--against 3` is never ambiguous. The directory mirrors
  a draft's own layout, so the render path reads a snapshot unchanged.
- `snapshot.json`: `number`, `label`, `taken_at`, `trigger`
  (`mark-revision` | `manual`), `revision_label`, `fingerprint`
  (`spec.digest`, as `dossier stamp` uses), `draft_name`.
- `chitragupta/dossier/_versions.py`: `take(draft, label="",
  trigger=..., revision_label="") -> Snapshot | None` (None when the
  fingerprint matches the latest), `list_versions(draft)`,
  `resolve(draft, ref)` (number, label, or None for latest),
  `latest(draft)`.
- `mark_revision()` calls `take(trigger="mark-revision",
  revision_label=label)` before its boundary row.
- `dossier snapshot <draft> --label` and `dossier versions <draft>
  [--json]` take the draft path, like `mark-revision`.
- `dossier status` adds one line: versions held and the latest.
- `dossier export`/`restore` already carry `dossiers/`; a test pins
  that `versions/` survives the round trip.
- No backfill. The first `mark-revision` after upgrading takes 001.
- [docs/DOSSIER.md](../docs/DOSSIER.md) gains the `versions/` row.

### 2. The change report

`chitragupta/draft_diff/`. The core is pure:
`compare(old: VersionView, new: VersionView, citable) -> ChangeReport`,
where a `VersionView` is a source text plus its figure files, so a
snapshot, the live draft and an `--against` file look alike.

1. **Summary**: words changed, sections changed of total, citekeys
   added and dropped, figures changed, the baseline (number, label or
   path, date, revision label).
2. **Sections**, matched by heading title (the rule
   `_draft_fingerprint.py` uses): added, removed, moved, changed with a
   words-changed count, or unchanged (collapsed to a count). A rename
   is a removal and an addition; renames are not guessed.
3. **Citekeys**, extracted with the existing `_pandoc_cites` helpers
   for Markdown and `\cite*` for `.tex`: added (with the section),
   dropped (with the ledger's status now: still citable, or no longer
   parsed or in the corpus). Only keys present in one of the two texts
   are ever named.
4. **Figures**: added, removed, redrawn, comparing the TikZ and ASCII
   forms separately; a change to one form only is flagged.
5. **Revision log**: `revisions.md` entries dated after the baseline
   are listed at the top. An entry's `Sections:` line (comma-separated
   headings or numbers) attaches it to each changed section it names;
   a name matching no heading is reported. A changed section no entry
   names is flagged "changed, no log entry".
6. **Hand edits**: if the live draft's fingerprint differs from the
   one `dossier stamp` last recorded, the report says it includes
   edits made outside any revision pass.

Outputs: `content/review/<topic>/<stem>.diff.md` (also printed) and
`<stem>.diff.json` for the revisers, with no timestamp in the body so
reports diff cleanly ([docs/REVIEW.md](../docs/REVIEW.md)). The
`Sections:` line joins the `revisions.md` template comment in
`chitragupta/dossier/_create.py`.

### 3. The redline PDF

1. **Prepare.** Write both versions, each with its `figures/`, into
   `content/review/<topic>/<stem>.diff/{old,new}/`. On the old side
   only, replace each citation whose key is not citable now with
   `(citation withdrawn)`.
2. **Render** both through `render()` to standalone `.tex` with a new
   deferred-citation mode: `--standalone` with `--natbib`, keeping the
   article layout (the book fragment's chapter division is not
   wanted), and a wider outer margin through `render()`'s existing
   `margin`. Gate, figure injection and LuaLaTeX header run as for
   any render, so both sides share one preamble.
3. **latexdiff** `--math-markup=coarse`, no `--flatten`, no
   `--preamble`.
4. **Post-process** `<stem>.diff.tex`: redefine `\DIFadd`/`\DIFdel`
   (and the `FL` variants) with `lua-ul`'s `\underLine` in blue and
   `\strikeThrough` in red; add the header line and a legend; add a
   `\marginnote` beside each changed figure (anchored on its
   `\input{figures/<name>.tex}`), each moved section, and each section
   the log links (anchored on its heading).
5. **Compile** with `latexmk -lualatex` and bibtex against the
   project's `.bib` (IEEEtran), so numbers are consistent within the
   diff. Output `content/review/<topic>/<stem>.diff.pdf`.
6. **On failure**, retry once with `--math-markup=whole`; then keep
   `.diff.tex` and the log, print where, exit non-zero. The report is
   written before any of this.

### 4. Commands, revisers, errors, tests

```bash
python -m chitragupta.draft dossier snapshot <draft> --label "sent to supervisor"
python -m chitragupta.draft dossier versions <draft> [--json]
python -m chitragupta.draft diff <draft> [--against N|label|path] [--format md|pdf] [--json]
```

`--format md` (default) writes and prints the report; `pdf` adds
`.diff.tex` and `.diff.pdf`. No changes: says so, exits 0, no PDF.

**Revisers.** draft-reviser's closing step: write the `revisions.md`
entry with its `Sections:` line, run `draft diff --format pdf` (or
`md` when latexdiff is missing), show the summary, changed sections
and citekey changes, and the PDF path; on "changed, no log entry",
complete the entry and re-run before presenting. corpus-reviser
inherits it through draft-reviser's loop, adding only that its entry
names every section touched. agenda-reviser's "Show the diff" becomes
the same command, against the snapshot its one `mark-revision` took.
Each `SKILL.md` gets about five lines; the detail goes in
`.claude/skills/draft-reviser/references/draft-diff.md`, mirrored to
the `.agents/` and `.opencode/` copies. A cap in
`tests/test_skill_size.py` rises only with this issue as its reason.

**Errors.**

| Situation | Behaviour |
| --- | --- |
| No snapshot yet | Exit 1, naming `mark-revision` and `--against <file>` |
| Unknown `--against` | Exit 1, listing numbers and labels |
| `--against <path>` without `figures/` beside it | Report says baseline figures are unknown; figures not compared |
| `.md` against `.tex` | Refused |
| Old side cites a key not citable now | `(citation withdrawn)` on the old side; the report names the key |
| latexdiff missing, `--format pdf` | Report written; `MissingBinary` with the install hint |
| Compile fails | One retry, then artefacts kept, exit non-zero |

**Install.** `scripts/install_full_pipeline.sh` `os-deps` adds
`texlive-extra-utils` (latexdiff and its Perl modules), with a comment
recording the ulem and lua-ul findings; `docker/Dockerfile` inherits it;
`chitragupta/doctor.py` checks `latexdiff`;
[docs/WINDOWS.md](../docs/WINDOWS.md) gets a row once MiKTeX's latexdiff
and its Perl requirement are verified on Windows, not before;
`docs/DEV-ENV.md` and `docs/RENDERING-FLOW.md` mention it.

**Tests.**

- Not slow: `_versions` (numbering, skip-unchanged, label uniqueness,
  resolution, both figure forms, export round trip); `compare()`
  (section kinds, citekeys with status seeded by `add_citable`,
  `Sections:` parsing, no-log-entry flag, hand-edit flag, withdrawn
  replacement); the `.tex` post-processing on stored latexdiff output;
  subprocesses mocked, keeping not-slow coverage at 100%.
- Fixtures cite only keys in the sample project's `.bib`.
- Slow, skipped without latexdiff or lualatex: the spike scenario end
  to end, asserting a PDF, the new citation as one
  `\DIFadd{\citep{...}}`, **no `\DIF` markup on any unchanged
  citation**, and the figure's margin note.

## Delivery

One PR: this plan, §1–§4, the install scripts, the three skills, and
the docs ([docs/DOSSIER.md](../docs/DOSSIER.md),
[docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md),
[docs/CLI.md](../docs/CLI.md)). Snapshots land first within it, so the
commits that follow can build on them.

## Deferred

- Accept/reject of individual changes.
- Diffing an assembled book.
- Pruning automatic snapshots.
- A filter for cosmetic changes.
