# 🧭 Model compliance: which skill steps a local model runs, and why

Status: **measured** on 2026-11-21, one model on two harnesses.

This page records what the 2026-11-21 skill bench showed about how
closely an agent follows a skill's steps when the model behind it is a
small local one, which steps it runs every time, which it never runs,
and the reasons the transcripts give. It is kept in git and left out of
the documentation site.

**Written for** anyone choosing a model or a harness to draft with, and
anyone changing a skill's wording. It assumes
[HARNESS.md](HARNESS.md), "Measuring a skill change", for how a run is
scored.

## 📏 What was measured

Every user skill's Tier 2 task, skill-only prompt, 3 runs each, on:

| Harness | Model |
| --- | --- |
| Claude Code | Claude Sonnet (`--model sonnet`) |
| Codex 0.159.3 | Qwen3.6-35B-A3B, 4-bit (Q4_K_M), on llama.cpp `b11321` |
| OpenCode 1.18.34 | the same local model |

The rows are in `bench/results/2026-11-21-local-harness-rebaseline/`
(Codex and OpenCode) and each skill's newest skill-only rows from the
`#1091` series (Claude Code). The local runs used two versions of the
skills, differing only in the wording of the style step; the results
folder's README says which run had which. A **step** here is one command a skill
names, in one skill: `draft gate` in survey-writer and `draft gate` in
tutorial-writer are two steps. There are 201. Timed-out runs are left
out. Counts are runs that ran the step, out of usable runs.

## 🔍 Why a local harness runs fewer of a skill's steps

Four causes, cheapest to fix first.

1. **Some steps are never meant to run in a given task.** A skill names
   commands on branches a task does not reach: a book's sign-off, a
   restore, a figure a draft does not need. 42 of the 201 steps were run
   by no harness at all, Claude Code included. That is why Claude Code
   runs 74% of named commands and not 100%.
2. **The setup ended runs early.** Until 2026-11-21 a figure image sent
   to a server without a vision projector, a read outside the project
   under OpenCode, and Codex's context overflowing each ended a run,
   and every step after went unrun. All three are fixed in the bench
   (HARNESS.md).
3. **The model finishes the draft and treats what follows as optional,
   or does it by hand.** This is most of what is left, and it points at
   the model, not the harness: Codex and OpenCode run the same model,
   and most steps one of them never runs the other never runs either
   (68 steps skipped by both, 27 by Codex alone, 17 by OpenCode alone).
   The commonest shape is that the model **writes the file a command
   would have written**, then moves on, so the command that writes or
   checks that file never runs.
4. **The model's own limits.** Now and then it writes a tool call whose
   arguments are not JSON; `llama-server` answers 500 and Codex gives up
   after five identical retries. The two longest skills (deep-research,
   agenda-reviser) sometimes run past the 1,500-second limit.

The model is small for this work. "35B-A3B" means 35 billion parameters
of which about 3 billion are used for each token, and Q4 stores each
weight in about 4 bits. That is fast, and weaker at holding a 15- to
25-step procedure, spread over a 15 KB skill and its references, in
mind to the end.

### What the vision projector is for

Qwen3.6-35B-A3B reads images, but only when the server is given two
files: the model, and a small **vision projector** (`mmproj-F16.gguf`)
that turns an image into tokens the model can read. The figure steps
(`figure look`) render a figure to PNG so the model can check its own
drawing, as Claude Code does. Without the projector the server answered
`500 image input is not supported` and Codex ended the run; with it the
model sees the figure, and the run goes on. A model chosen for the bench
needs a projector of its own, or every Codex run that draws a figure
ends there again.

## 🗂 Three kinds of step

Per harness, over the 201 steps:

| Harness | Run in every run | Run in no run | Run in some runs |
| --- | ---: | ---: | ---: |
| Claude Code | 130 | 52 | 19 |
| Codex (Qwen3.6) | 89 | 76 | 36 |
| OpenCode (Qwen3.6) | 92 | 62 | 47 |

### Always followed

65 steps ran in every usable run on **both** local harnesses. They are
the steps the task cannot be finished without, or whose output the
model reads next:

| Step | Command | Skills it is always run in |
| --- | --- | ---: |
| Check every citekey | `draft gate` | 10 |
| Scan for copied source wording | `review verbatim scan` | 7 |
| Check the prose against the house style | `draft style` | 7 |
| See what the corpus holds | `corpus ledger` | 6 |
| Render the draft | `draft render` | 5 |
| Search the corpus | `draft retrieve search` | 4 |
| Open the dossier | `draft dossier init` | 4 |
| Rebuild the section map | `draft dossier sections` | 4 |
| Build the reference list | `draft references` | 3 |

The rest are one skill's own required step: the book's `registry`,
`spec` and `unit` checks in book-assembler, `review digest` and
`review synthesis` in review-digest, `review agenda` in agenda-reviser,
`draft diff` in draft-reviser, and `figure check` and `figure look` when
figure-drawer is the skill asked for.

### Never followed while Claude Code follows it

These steps ran in **no** run on a local harness while Claude Code ran
them in at least two runs of three. The table lists each step once, with
the skills and harnesses where it never ran. A reason marked **seen**
was read in that harness's transcripts; **likely** is the shape seen in
a neighbouring step; **not examined** means no transcript was read for
it.

| Step, in plain terms | Command | Skills | Never run on | Reason |
| --- | --- | --- | --- | --- |
| Check the evidence file just written | `draft dossier check-evidence` | survey-writer, thesis-chapter-writer, tutorial-writer | Codex (all three); OpenCode (tutorial) | **Seen:** Codex writes `evidence.md` and `rejected.md` with a heredoc and goes on; the check is the last line of a long step, after "Then:" |
| Open the dossier | `draft dossier init` | review-digest | Codex | **Seen** in all 6 runs over two arms: `mkdir` the dossier directory, then `scope.md`, `evidence.md`, `rejected.md`, `steering.md` written by hand, following `genre-steps.md` §3's "Fill in `scope.md`". Follow-up: issue 1247 |
| Rebuild the section map | `draft dossier sections` | draft-reviser, agenda-reviser, review-digest | Codex | **Seen** (draft-reviser): "Now update `sections.md` to remove the anomaly section from the map", by hand, though the map is derived and never hand-written |
| Mark the start of a revision | `draft dossier mark-revision` | draft-reviser, agenda-reviser | Codex | **Seen** (draft-reviser): "Now add a `revisions.md` entry", by hand |
| Stamp the draft's fingerprint | `draft dossier stamp` | draft-reviser, corpus-reviser | Codex | **Seen** (draft-reviser): the run closes on gate, render, style and a summary; the stamp, a closing bookkeeping line, is left out. Likely the same in corpus-reviser |
| Rebuild the reference list after a revision | `draft references` | draft-reviser, corpus-reviser | Codex | **Seen** (draft-reviser): not run after the edit; the reference list is treated as unchanged |
| Render the revised draft | `draft render` | corpus-reviser | Codex | Not examined |
| Show what changed | `draft diff` | agenda-reviser | Codex | Not examined (2 usable runs). In draft-reviser Codex snapshots only at the end, so a diff there has no baseline |
| Back up and list dossiers | `draft dossier export`, `draft dossier list` | agenda-reviser | Codex | Not examined (2 usable runs) |
| Read the dossier's state first | `draft dossier status` | corpus-reviser | Codex | Likely: it is step 1 of the reviser loop, and Codex opens the dossier's files directly instead (seen in a draft-reviser run: "find the correct dossier path and read the key files") |
| Read what the corpus could not answer | `draft dossier status` | textbook-chapter-writer | Codex | Likely: the critique loop runs it only where the dossier has an `outline.md`, and Codex does not check for one (next row) |
| Check for an outline first | `draft dossier outline` | review-digest, tutorial-writer | Codex | **Seen** (review-digest): the step opens "First check for an `outline.md`"; Codex searches without checking |
| Check how many sources each section rests on | `review synthesis` | textbook-chapter-writer (both), deep-research (Codex) | Codex, OpenCode | **Seen** in the skill text: the command is named in parentheses ("reports the spread"), never given as a line to run; Claude Code runs it anyway |
| Re-check after a critique edit | `review verbatim recheck` | tutorial-writer | Codex, OpenCode | **Seen:** it sits inside the critique loop's repair sub-step, behind a pointer to `critique.md`, and OpenCode never opened that file. Codex opened it in 2 of 3 runs; likely it made no critique edit, the only case the recheck is for |
| Extract a paper's figures | `draft figures` | review-digest | Codex | Likely: part of the hand-written dossier path above |
| Look at the rendered figure | `figure look` | survey-writer, textbook-chapter-writer | OpenCode | **Seen:** in 6 of 12 genre-writer runs OpenCode never handed the figure to `figure-drawer` and drew it itself, so the look step never came up; when it did hand over, it often looked |
| Snapshot the draft, list its versions | `draft dossier snapshot`, `draft dossier versions` | draft-reviser | OpenCode | Not examined |
| Render the evidence sidecar | `draft evidence` | thesis-chapter-writer | OpenCode | Not examined |

Two never-run steps are **right** to skip, and the score counts them
only because the skill names the command: tutorial-writer's
`draft evidence`, which the skill says not to run (Claude Code ran it
once in six, wrongly), and its `draft dossier status`, which the loop
runs only with an `outline.md` the task did not give.

### Followed unpredictably

89 steps ran in some runs and not others, pooled over the two local
harnesses. Two kinds hide in that number:

- **Steps that depend on the harness, not on chance.** 21 ran in every
  run on one harness and in none on the other: Codex's reviser
  bookkeeping above (OpenCode runs it every time), OpenCode's single
  usable deep-research run against Codex's three, and review-digest's
  `dossier init` (OpenCode always, Codex never). On a given harness
  these are steady; it is the pooled count that varies.
- **Steps that come and go run by run.** The rest, most often:
  - the figure steps (`figure new`, `figure check`, `figure sync`,
    `figure look`), which depend on whether the run decided to draw a
    figure and whether it handed it to `figure-drawer`;
  - `draft dossier status` and `draft dossier outline`, which depend on
    a condition the model sometimes checks;
  - the closing steps of a revision (`draft references`,
    `draft render`, `draft evidence`, `draft dossier stamp`), which
    depend on whether the run reached the end of the loop before
    summarising;
  - `review verbatim recheck`, which runs only when the critique loop
    made an edit.

This is the noise that keeps a local harness's `--compare` advisory:
over all three harnesses an unchanged skill still fails 0% to 15% or 0%
to 20% of the time, depending on how the runs are drawn (HARNESS.md).

## 🧩 What the patterns suggest

None of these is applied; each is a wording a skill change would have to
bench first.

- **A command that writes a file is skipped when the model can write the
  file itself.** Saying so in the step ("`init` writes these files; do
  not write them by hand") is the change proposed for review-digest in
  issue 1247.
- **A check at the end of a long step is the first thing dropped.**
  `check-evidence` after "Then:" is the clearest case.
- **A command named in parentheses is read as information.** Claude Code
  runs `review synthesis` from a parenthesis; the local model does not.
- **A step behind a pointer runs only if the pointer is followed.**
  OpenCode often does not open `critique.md` or load `figure-drawer`.

Whether a stronger model closes most of the gap without any of these is
the open question; benching a stronger local model on the same tasks is
the next measurement.
