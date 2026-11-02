# Building the References section and rendering a draft

Read this once the draft has passed the citation gate, at the step that
sends you here. That step says which sections apply and which formats to
render; `<draft>` below is the draft's path, as the step gives it (for
example `content/drafts/<slug>.md`).

## 1. Build the References section

Generate it from exactly the gated citekeys, never by hand:

```bash
python -m chitragupta.draft references <draft>
```

Stdlib-only, like the citation gate: bare `python`, no venv. It writes
numbered IEEE-style entries from `content/ledger.sqlite`, ordered by
first appearance so the numbers match the rendered PDF's. Each entry
keeps its citekey in a trailing code span, so a reader can trace every
`[@citekey]` marker in the body back to an entry by that same key.

Leave the body's inline citations as `[@citekey]`. Do **not**
hand-number them to `[1]`: the literal key is what the gate and the hook
verify, and pandoc assigns the numbers at render time.

If the draft's other section headings are numbered by hand (for example
`## 6. Challenges and Open Issues`), pass `--heading "N. References"`
with the next number, so the new section matches the draft's own
numbering instead of the bare `## References` default. Keep the heading
text `References`, `Bibliography` or `Works cited`, bare or
number-prefixed: the renderer recognises the section only by one of
those, and swaps its entries for citeproc's own bibliography. Any other
heading leaves the manual list in the rendered `.tex` and `.pdf` *and*
citeproc's list below it, so every reference appears twice.

## 2. Render

Run one command per format the step names:

```bash
python -m chitragupta.draft render <draft> --format tex
python -m chitragupta.draft render <draft> --format pdf
python -m chitragupta.draft render <draft> --format md
```

Every render lands beside the draft: a draft at
`content/drafts/<topic>/<name>.md` renders to
`content/rendered/<topic>/<name>.{tex,pdf,md}`, so one topic directory
holds the draft, its dossier and its renders. The `md` output is a
numbered copy, with the same IEEE numbers as the PDF, for a reader who
won't open one. The draft itself keeps its `[@citekey]` markers.

This needs only bare `python` plus `pandoc` (and, for pdf, LuaLaTeX) on
PATH, no enrich group. Don't assume either is present or absent from a
run on another host: try the command and read the result. If a command
reports `[missing-binary]` or `[error]`, print a one-line warning in
chat with that message and continue: a rendering failure never blocks
presenting the draft.

## 3. Render the evidence sidecar

Run one command per format the step names:

```bash
python -m chitragupta.draft evidence <draft> --format pdf
python -m chitragupta.draft evidence <draft> --format md
```

The sidecar lands as `content/rendered/<topic>/<name>.evidence.{pdf,md}`,
beside the render. It lists each cited source with the verbatim spans
the evidence blocks' `quote:` fields recorded, grouped by the section
that leans on them.

You do not write it and you cannot add to it: it is built from
`evidence.md`, and it can only name citekeys the draft already cites.
A draft whose blocks carry no `quote:` produces no sidecar and prints
`no quoted evidence recorded`. That is the expected answer, not a
failure: it means no quotation was captured. Never add a `quote:` after
the fact to populate it; a quote is captured when the evidence is judged
or not at all.
