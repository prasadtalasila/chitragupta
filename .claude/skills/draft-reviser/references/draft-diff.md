# Showing what changed: `draft diff`

Read this at the end of a revision pass. Paths here are from the project
root.

## When

Last, once the gate has passed, the draft is stamped (where the skill
stamps; an agenda pass never does) and this pass's `revisions.md` entry
is written, `Sections:` line included. The default baseline is the
snapshot `mark-revision` took at the start of the pass, so the diff
shows this pass and nothing older.

```bash
python -m chitragupta.draft diff content/drafts/<path> --format pdf
```

The report is written to `content/review/<topic>/<stem>.diff.md` (and
`.json`) before any PDF work starts, and printed; the redline's path is
printed after it. `No changes.`: say so; there is no PDF. If the command
ends in an `[error]` saying a tool is not on PATH, show the report
already printed and tell the user the PDF needs the tool the error
names, and that `python -m chitragupta doctor` shows what is missing.
Any other `[error]` after the report: show the report and quote the
error. The diff is a review copy, never a deliverable, and a failed
redline never blocks presenting.

## The `Sections:` line

The report ties each changed section to the entries whose `Sections:`
line names it. An entry is read only if its first line starts with the
date, `YYYY-MM-DD`. End it with a `Sections:` line naming every section
the pass changed, comma-separated, each by its heading's full text as
the report lists it (`2. Background`, not `Background`) or by its
number:

```text
Sections: 2. Background, 4.1 Synchronisation, Conclusions
```

A `.tex` draft's headings carry no number (LaTeX numbers them), so name
its sections by title. A copy-edit entry still states the convention;
its `Sections:` line names every section the pass changed, or the diff
flags each one.

## What to show the user

From the report, in this order:

1. The `# Changes since …` header, which names the baseline.
2. The summary under it: words changed, sections changed of the total,
   citekeys added and dropped, figures. It spans several lines; show
   all of them.
3. "Includes edits made outside any revision pass.", if present: the
   draft changed since its last stamp. After an agenda pass, which never
   stamps, that is the pass's own repairs; say so.
4. Every section under `## Sections` that is not unchanged, with the
   entries under it; the unchanged count is enough for the rest.
5. Every line under `## Citekeys`. A dropped key's status says whether
   it is still citable or has left the corpus.
6. The PDF path, when there is one.

## `## Needs a log entry`

Each section listed there changed, and no entry since the baseline
names it. Add every one to this pass's `Sections:` line and run `draft
diff` again. If a section stays listed after its name was added (a
comma in its title splits the name), tell the user so and present.

## Milestones

`python -m chitragupta.draft dossier snapshot content/drafts/<path>
--label "<name>"` keeps the draft as a named version a later diff can
take `--against`. Run it only with a name the user gave, such as "the
version I sent my supervisor"; never invent a milestone.
`python -m chitragupta.draft dossier versions content/drafts/<path>`
lists what exists.
