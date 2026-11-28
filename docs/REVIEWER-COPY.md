# 🔀 Reviewer copy: snapshot a draft, then diff it

Status: **reference.**

**Written for** an author who wants to keep earlier versions of a draft
and see what changed between them, for example before sending a draft
to a supervisor and again when it comes back. **Assumed:** you have a
draft under `content/drafts/` and its dossier under `content/dossiers/`
([WRITING-PROCESS.md](WRITING-PROCESS.md#-phase-2-write-a-first-draft)
if you don't yet). **Not covered here:** every flag and exit code
([CLI.md](CLI.md#-chitragupta-draft-diff)), or how a reviser uses the
diff at the end of a pass
([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-reviewing-a-revision)).

## 🎯 Why keep snapshots at all

`content/` is outside git on purpose, so nothing else keeps a draft's
earlier text. If you hand-edit a draft
([USER-EDITS.md](USER-EDITS.md)) or ask a skill to revise it, the old
wording is gone unless a snapshot holds it. A snapshot is that copy,
and `draft diff` is what reads it back.

## 📸 Take a snapshot

```bash
python -m chitragupta.draft dossier snapshot content/drafts/dt-overview/survey.md --label "sent to supervisor"
```

This prints
`Snapshot 001-sent-to-supervisor of content/drafts/dt-overview/survey.md`
and writes the draft and both forms of each figure it uses
(`figures/<name>.tex` and `figures/<name>.txt`) to
`content/dossiers/dt-overview/survey/versions/001-sent-to-supervisor/`.

- **Snapshots are numbered** `001`, `002`, and so on, in the order they
  are taken. A named snapshot is always taken, even when the draft has
  not changed since the last one.
- **The label is required** and names a milestone. It must contain a
  letter or digit, must not be all digits (so `--against 3` always
  means version 3), and must not repeat an earlier label.
- **Skills take snapshots too.** Every `dossier mark-revision` takes an
  unlabelled one when the draft changed since the latest snapshot, so a
  revised draft always has a version to compare against.

List what you have:

```bash
python -m chitragupta.draft dossier versions content/drafts/dt-overview/survey.md
```

```text
001  2026-11-14  manual         sent to supervisor
002  2026-11-20  mark-revision  "shortened the background"
```

Add `--json` for a machine-readable list.

Snapshots live in the dossier, so `chitragupta draft dossier export`
carries them with everything else
([MIGRATION.md](MIGRATION.md)). They do not back up the rest of
`content/`.

## 🔍 Compare two versions

```bash
python -m chitragupta.draft diff content/drafts/dt-overview/survey.md
python -m chitragupta.draft diff content/drafts/dt-overview/survey.md --against "sent to supervisor" --format pdf
python -m chitragupta.draft diff content/drafts/dt-overview/survey.md --against 1 --format pdf
python -m chitragupta.draft diff content/drafts/dt-overview/survey.md --against old/survey.md
```

`diff` compares the draft as it is now with a baseline:

| `--against` | Baseline |
| --- | --- |
| omitted | the latest snapshot |
| a number (`1`, `001`) | that snapshot |
| a label (`"sent to supervisor"`) | the snapshot with that label |
| a path to a file | that file; a file wins over a label with the same text |

Everything is written to `content/review/<topic>/`:

- `<stem>.diff.md` and `<stem>.diff.json`: the change report. It is
  also printed, as Markdown or, with `--json`, as JSON.
- `<stem>.diff.pdf`: the redline, with `--format pdf` only. It needs
  latexdiff, LuaLaTeX and bibtexu; `python -m chitragupta doctor`
  checks them. Without them the report is still written and the
  command exits 1.

When nothing changed, the report says `No changes.` and no PDF is made.

## 🖍 Read the redline

The redline is the draft rendered once, with deleted text struck through
in red and added text underlined in blue. Section moves and redrawn
figures are noted in the right margin.

The example below is a real redline. A short note was snapshotted, then
edited five ways: a figure deleted, a phrase replaced, a section
renamed, a sentence deleted, and a section deleted.

![A redline PDF page. Struck-through red text marks a deleted figure caption, the old phrase "at a fixed rate", the old heading "Staleness", a deleted sentence and the whole "Historical background" section. Underlined blue text marks the new phrase "every few seconds" and the new heading "When a twin goes stale". Numbered labels 1 to 5 in the margin name each change.](images/reviewer-copy/redline-example.png)

| # | Change | In the redline | In the report |
| --- | --- | --- | --- |
| 1 | Deleted figure | The caption is struck through. The drawing is not shown, and a sentence that pointed at it reads `Figure ??` | `Figures: figures/twin-loop: removed` |
| 2 | Replaced phrase | Old words struck, new words underlined, side by side | The section is listed as `changed` with a word count |
| 3 | Renamed section | Old heading struck, new heading underlined | Listed as one section `removed` and one `added`: the report does not detect a rename |
| 4 | Deleted sentence | The sentence is struck through in place | Part of that section's `changed` or `removed` entry |
| 5 | Deleted section | Heading and body struck through | `removed: Historical background` |

The report for the same edits:

```text
# Changes since 001 · sent to supervisor · 2026-11-28 — review copy

133 words changed in 2 of 5 sections, 2 removed ·
citekeys +0 −0 ·
figures 0 redrawn, 1 removed

## Revision log

No entries since the baseline.

## Sections

- changed: The twin loop (29 words)
- added: When a twin goes stale (31 words)
- removed: Staleness (39 words)
- removed: Historical background (34 words)

3 unchanged

## Citekeys

No citekeys added or dropped.

## Figures

- `figures/twin-loop`: removed

## Needs a log entry

- changed: The twin loop
- added: When a twin goes stale
```

Read the report alongside the redline for two things the PDF cannot
show:

- **Citations.** The report lists citekeys added and dropped. A
  baseline citation that is no longer citable prints as
  `(citation withdrawn)` in the redline.
- **Unexplained changes.** `## Needs a log entry` names every changed
  section that no `revisions.md` entry since the baseline explains.
  [DRAFT-ITERATION.md](DRAFT-ITERATION.md#-reviewing-a-revision) shows
  the entry format.

## 🚫 What a reviewer copy is not

The report and the redline are for reading. They are never gated, never
submitted, and never used as a source for another draft. Send the
rendered draft, not the redline, as the deliverable.
