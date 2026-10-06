# 🖍 One shared figure-drawing skill: implementation plan (#1027)

> **For agentic workers:** REQUIRED SUB-SKILL: use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to carry out this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **planned, not built.** Written 2026-10-06 against `main` at
`10ac21f` (#1026), version 6.135.0.

**Written for** whoever builds #1027: a session that changes
`.claude/skills/`, `.agents/skills/`, `.opencode/`, `tests/` and `docs/`,
and so is governed by `DEVELOPER-AGENTS.md` and `docs/CODE-STANDARDS.md`.

**Assumed:** you have read #1027 itself (the duplication count, the
per-genre table, Options A and B), `docs/TIKZ-STYLE.md`,
`docs/WRITING-STANDARDS.md` §10, and `docs/HARNESS.md` on why each skill
exists three times.

**Not covered here:** Option B's bundled check script (rejected in the
issue for v1; its value lands through F2 #1013 and F4 #1016 in
`chitragupta/`), the house `pic`s (F3 #1014), and moving any asset out of
`assets/tikz/` (rejected on #1026).

**Goal:** Figure drawing becomes one skill, `figure-drawer`, that the
four figure-drawing genre skills and `draft-reviser` hand off to. The
generic figure rules then live in one place per harness instead of
twelve.

**Architecture:** Option A from the issue: `SKILL.md` (the procedure)
plus `reference.md` (worked examples, read only when the procedure
points at a section), in all three harness copies. Each genre skill keeps
a short stub: its when-to-draw threshold, its output shape, the
no-citekey rule, and the handoff. The stub is what still holds if a
harness skips the handoff. The skill draws and checks figures and never
presents a draft. Control always returns to the caller (a genre skill,
or `draft-reviser` on direct use), and the caller runs the gate, render,
prose check, verbatim scan and fingerprint stamp as it does today.

**Tech stack:** Markdown skill files, pytest text scans in the shape of
`tests/test_skill_table_step.py`, `.opencode/opencode.json`. No
`chitragupta/` code changes, so the coverage bar is untouched by
construction.

**Spec:** issue #1027. This plan argues from it; read both.

## Global constraints

- Skill name `figure-drawer`; OpenCode copy `figure-drawer-opencode` in
  `.opencode/skills/figure-drawer-opencode/`, its `name:` field matching.
- Assets stay in `assets/tikz/`. The skill points at them and never copies
  one into its own folder.
- No new code under `chitragupta/`, no new script, no new check promoted
  into a gate (SOUL.md). `python -m chitragupta.draft gate` stays the
  only gate.
- No citekey anywhere in the new files, the test fixtures or the docs
  examples (CLAUDE.md's one rule). Examples use `figures/<name>` and
  `content/drafts/rag/figures/flow.tex`, never a key.
- Harness-neutral wording in `figure-drawer`: say "write the file", never
  a backticked tool name (`Edit`, `Write`, `apply_patch`, `edit`). The
  three copies are then identical apart from the `-opencode` suffix, and
  `tests/fixtures/skill_harness_phrases.toml` needs no new entry. Add one
  only if a harness-specific sentence turns out to be unavoidable.
- Frontmatter `description:` at most 1,024 characters
  (`tests/test_skill_frontmatter.py`).
- Line and branch coverage stays at 100%.
- Version bump: **MINOR**, 6.135.0 → 6.136.0 (a new skill is new
  backward-compatible functionality, `DEVELOPER-AGENTS.md` "Versioning and
  releases"). If `main` has moved, bump from whatever it holds then.
- Branch off the latest `origin/main`:
  `git fetch origin main && git checkout -B 1027-figure-drawer-skill origin/main`.

## Decisions this plan makes

The issue leaves these open. Each is recorded so a reviewer can tell a
decision from an accident.

1. **The skill never presents a draft.** It draws, checks and returns.
   Every "every skill does X" test that exists because a skill presents a
   draft (verbatim scan, prose check, pre-gate critique) gets
   `figure-drawer` as an exemption **by name**, with the reason in a
   comment. A wildcard would let a future drafting skill slip through. The
   docs say the same in `docs/GENRE.md`'s shared-rules section, alongside
   the paragraph that already exempts `book-assembler` from writing rules.
2. **Direct use is a revision.** "Draw a figure for section 3 of
   rag/survey.md" changes an existing draft, so after drawing,
   `figure-drawer` sends the session to `draft-reviser`'s loop from
   "6. Write the dossier back" (log in `revisions.md`) through
   "7. Gate, reference, render" and the steps after it. That way the
   fingerprint is re-stamped and the gate runs. On direct use the
   per-genre threshold does not apply: the person asked for the figure.
3. **The placement shapes appear twice on purpose:** in each genre stub,
   which is the safety copy, and in one table in `figure-drawer`, which
   direct use needs because it has no genre skill loaded. A test pins
   both: each genre stub carries its shape, and `figure-drawer` carries
   both shapes.
4. **The fallback for a missing TikZ install stays in the stub.** The
   probe (`kpsewhich tikz.sty`) moves to `figure-drawer`. The fallback is
   output shape: an ASCII fence in Markdown genres, `verbatim` in the
   thesis genre. So `figure-drawer` says "if `kpsewhich` finds nothing,
   stop and return. The caller writes the ASCII inline in its own fallback
   form", and each stub names that form.
5. **What moves and what stays.** Signature phrases are in quotes; the
   tests pin them.

   | Rider (today, in each genre skill) | Goes to |
   | --- | --- |
   | "Commit to a layout metaphor", scaffolds, "pre-flight defect list", type floor, no `\resizebox` | `figure-drawer` |
   | "lettered sub-captions" in both forms | `figure-drawer` (+ `reference.md` §2 example) |
   | Compile probe, `\usetikzlibrary` line, "write nothing else about loading", `tikz@node@reset@hook` | `figure-drawer` |
   | "as original as the ASCII" | `figure-drawer` |
   | Look first: `python -m chitragupta.draft figures <citekey>` | `figure-drawer` |
   | "No citekey inside either figure file" | **stays** in every stub, and is also stated in `figure-drawer` |
   | Marker / `\input` + `%figure:` shape, the caption rule | **stays** (output shape) |
   | "A topic directory is required" | **stays** (refers to the genre's own step 0/1) |
   | Thesis-only: marker is a comment, float with `\caption`/`\label`, preamble `[tikz-libraries]` and `[unicode]` lines | **stays** in `thesis-chapter-writer` |
   | Quantity/math paragraphs (§12) | **stays**; not a figure rule |

6. **`deep-research` is untouched.** It uses no figures and must not name
   `figure-drawer`. A test pins that it does not.

## Review focus

The failures most likely to reach a user that no task's main test
exercises, most likely first. Each has its test in the owning task.

1. **The handoff is skipped** (Codex or OpenCode never loads the second
   skill). Expected: the figure still carries no citekey, sits in the
   genre's shape and compiles or falls back. Pinned by Task 2's stub
   tests, plus Task 4's run in each harness.
2. **The OpenCode genre copy names bare `figure-drawer`**, which
   `opencode.json` denies, so the handoff is refused. Expected: the
   OpenCode copies say `figure-drawer-opencode`. Pinned by the existing
   `test_the_opencode_copy_refers_to_opencode_skills` once the skill
   exists. Task 2 step 6 runs it explicitly.
3. **A rider reappears in a genre skill later** (someone edits one copy
   back to the old text, and the four drift again). Expected: the moved
   riders exist only in `figure-drawer`. Pinned by Task 2's absence test.
4. **A direct "draw a figure" request leaves the draft unstamped or
   ungated.** Expected: `figure-drawer` names `draft-reviser`'s write-back
   and gate steps. Pinned by Task 1's handback test.
5. **A thesis figure gets the Markdown marker, or a Markdown draft gets
   `\input`.** Expected: the placement table maps `.md` to the marker and
   `.tex` to `\input` + `%figure:`. Pinned by Task 1's shape test, and by
   Task 2's per-genre shape test.

---

### Task 1: The `figure-drawer` skill lands, suite green

**Files:**

- Create: `.claude/skills/figure-drawer/SKILL.md`,
  `.claude/skills/figure-drawer/reference.md`
- Create: `.agents/skills/figure-drawer/SKILL.md`,
  `.agents/skills/figure-drawer/reference.md`
- Create: `.opencode/skills/figure-drawer-opencode/SKILL.md`,
  `.opencode/skills/figure-drawer-opencode/reference.md`
- Modify: `.opencode/opencode.json` (add `"figure-drawer": "deny"`,
  alphabetical)
- Create: `tests/test_skill_figure_step.py`
- Modify: `tests/test_skill_frontmatter.py:41` (27 → 30, comment "ten skills")
- Modify: `tests/test_skill_verbatim_scan_step.py` (helper exemption; count 9 →
  10; "What all ten have in common")
- Modify: `tests/test_skill_style_check_step.py` (helper exemption in
  `test_every_drafting_skill_runs_the_prose_check`)
- Modify: `tests/test_skill_pregate_feedback_step.py:60` (add to
  `_EXCLUDED_SKILLS`, fix "four"/"nine" in comments)
- Modify: `docs/GENRE.md` (new section, heading "What all ten have in common",
  TOC link, at-a-glance row)
- Modify: `docs/FEATURES.md:101,214` ("10 skills", "### 🤖 Ten skills", a bullet
  naming `` `figure-drawer` ``)
- Modify: `README.md:161,372`, `DEVELOPER.md:223,377`,
  `docs/HARNESS.md:176,263` ("nine" → "ten" where it counts today's skills.
  Leave dated measurements such as `HARNESS.md:409-410` as they are: they record
  a run.)
- Modify: `pyproject.toml` version → 6.136.0

**Interfaces:**

- Produces: a skill folder named `figure-drawer` whose `SKILL.md` contains
  these literal strings, which Tasks 2 and 3 and the tests rely on:
  `Commit to a layout metaphor`, `pre-flight defect list`,
  `lettered sub-captions`, `tikz@node@reset@hook`,
  `as original as the ASCII`, `No citekey inside either figure file`,
  `kpsewhich tikz.sty`, `python -m chitragupta.draft figures`,
  `<!-- figure: figures/<name> -->`, `%figure: figures/<name>`,
  `python -m chitragupta.review figure`, `draft-reviser`,
  `never presents a draft`.
- Produces: `reference.md` with headings `## 1. Choosing a metaphor`,
  `## 2. Panels`, `## 3. Fit without scaling`, `## 4. An annotated exemplar`.

- [ ] **Step 1: Write the failing tests**

`tests/test_skill_figure_step.py` (Task 2 and Task 3 extend this file):

```python
"""Figure drawing is one skill the genre skills hand off to (#1027).

Before #1027 each of the four figure-drawing genre skills carried the
same ~70 lines of figure riders, in three harness copies each, and
#1012 had to change one sentence in twelve files. Those riders now live
once, in `figure-drawer`. This text scan keeps it that way. It pins
that the shared skill carries every rider, that each genre skill keeps
only the stub whose loss would be unsafe if a harness skipped the
handoff, and that no rider drifts back into a genre skill.

It exercises no behaviour: `tests/test_tikz_scaffolds.py`,
`tests/test_figure_layout.py` and `tests/test_tikz_subcaptions.py` own
that. `tests/test_skill_harness_copies.py` makes a check against
`.claude/skills/` hold for the other two copies.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
DRAWER = "figure-drawer"

# The riders that moved, by a phrase each one cannot be stated without.
_RIDERS = (
    "Commit to a layout metaphor",
    "pre-flight defect list",
    "lettered sub-captions",
    "tikz@node@reset@hook",
    "as original as the ASCII",
)
_NO_CITEKEY = "No citekey inside either figure file"
_MARKDOWN_SHAPE = "<!-- figure: figures/<name> -->"
_THESIS_SHAPE = "%figure: figures/<name>"


def _text(name: str) -> str:
    return re.sub(r"\s+", " ", (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8"))


def test_the_drawer_carries_every_rider():
    text = _text(DRAWER)
    missing = [r for r in _RIDERS + (_NO_CITEKEY,) if r not in text]
    assert not missing, f"figure-drawer lost: {missing}"


def test_the_drawer_knows_both_placement_shapes():
    # Direct use has no genre skill loaded, so the drawer is the only
    # thing telling it a .tex draft takes \input and a .md one the marker.
    text = _text(DRAWER)
    assert _MARKDOWN_SHAPE in text and _THESIS_SHAPE in text


def test_the_drawer_hands_back_and_never_presents():
    # Decision 1 and 2: the gate, render, scan and stamp stay with the
    # caller. On direct use that is draft-reviser's write-back and gate.
    text = _text(DRAWER)
    assert "never presents a draft" in text
    assert "`draft-reviser`" in text
    assert "6. Write the dossier back" in text and "7. Gate, reference, render" in text


def test_the_drawer_runs_the_existing_checks_in_order():
    text = _text(DRAWER)
    order = ["kpsewhich tikz.sty", "pdflatex", "python -m chitragupta.review figure"]
    at = [text.find(s) for s in order]
    assert -1 not in at and at == sorted(at), dict(zip(order, at))


def test_the_reference_file_has_the_sections_the_procedure_points_at():
    ref = (SKILLS_DIR / DRAWER / "reference.md").read_text(encoding="utf-8")
    for heading in ("## 1. Choosing a metaphor", "## 2. Panels",
                    "## 3. Fit without scaling", "## 4. An annotated exemplar"):
        assert heading in ref, heading
    for section in ("§1", "§2", "§3", "§4"):
        assert f"reference.md {section}" in _text(DRAWER), section
```

The handback test pins `draft-reviser`'s step headings by their exact
text (`### 6. Write the dossier back`, `### 7. Gate, reference, render`
on `10ac21f`). If either heading is renamed, update the skill and this
test together.

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest tests/test_skill_figure_step.py -v`
Expected: FAIL, `FileNotFoundError` on `.claude/skills/figure-drawer/SKILL.md`.

- [ ] **Step 3: Write `.claude/skills/figure-drawer/SKILL.md`**

Frontmatter (check the description is ≤ 1,024 characters with
`python -c "..."` or the frontmatter test):

```markdown
---
name: figure-drawer
description: Draws one figure for a draft in content/drafts/ -- a TikZ picture in figures/<name>.tex and its ASCII twin in figures/<name>.txt -- from the house scaffolds in assets/tikz/, then compiles and reviews it. Handed off to by survey-writer, tutorial-writer, textbook-chapter-writer and thesis-chapter-writer once they have decided a figure is warranted, and by draft-reviser to redraw or fix one. Also triggers directly when the user asks to draw, add, redraw or fix a figure or diagram in an existing draft. Owns how a figure is drawn, never whether a genre wants one. Never presents a draft: it returns to the skill that called it, which gates and renders. Never puts a citekey in a figure file.
tags: [figure, tikz, drafting]
---
```

Body, in this order. Text in **bold quotes** is the wording to use. The
riders are **moved, not rewritten**: take `survey-writer/SKILL.md`'s
rider list (lines 436-517 on `10ac21f`) as the source text, strip the
genre-specific clauses named below, and keep everything else
word for word, so #1012's wording survives.

````markdown
# figure-drawer

This skill owns *how* a figure is drawn. Whether a draft wants one, and
what shape it takes in that draft, belongs to the genre skill that
called you; its figure step has already decided both. This skill
**never presents a draft**: when the figure is drawn and checked, return
to the step that sent you here.

## Who called you

- **A genre skill** (`survey-writer`, `tutorial-writer`,
  `textbook-chapter-writer`, `thesis-chapter-writer`): it has decided a
  figure is warranted and named its shape. Draw, check, return to its
  next step.
- **`draft-reviser`**: it is redrawing or fixing one figure. Same, and
  it logs the change.
- **The user, directly** ("draw a figure for section 3"): this is a
  change to an existing draft, so it is a revision. Read the draft's
  `scope.md` for its genre and the draft's extension for its shape
  (table below). Draw and check. Then continue in
  `draft-reviser`'s loop at "6. Write the dossier back" and its
  "7. Gate, reference, render" onward, which log the change, run
  `python -m chitragupta.draft gate` and re-stamp the fingerprint. The
  genre's when-to-draw threshold does not apply: the person asked.
  A `deep-research` draft takes no figure (its skill says why); say so
  and stop.

## Where it goes

| Draft | In the draft | Files |
| --- | --- | --- |
| `.md` (survey, tutorial, textbook chapter) | a line of its own: `<!-- figure: figures/<name> -->`, caption line directly below, `<!-- figureref: <name> -->` where prose points at it | `figures/<name>.tex` + `figures/<name>.txt` |
| `.tex` (thesis chapter) | `\input{figures/<name>.tex}` then `%figure: figures/<name>`, inside a `figure` float with `\caption`/`\label{fig:<id>}` | same pair |

Both files sit under the draft's topic directory
(`content/drafts/<topic>/figures/`). A flat draft has none; the caller's
figure step says what to do about that.

## The procedure

1. **Look before you draw.** <moved: the "look at how the literature
   draws it first" paragraph, `python -m chitragupta.draft figures
   <citekey>`, genre wording removed; it ends "AGENTS.md states the
   boundary in full.">
2. **Commit to a layout metaphor before drawing, and start from the
   scaffold for it.** <moved rider 1 verbatim, including "pre-flight
   defect list", the type floor and the `\resizebox` ban>. **For which
   metaphor fits, see reference.md §1; for a figure that does not fit,
   reference.md §3.**
   ```bash
   cp assets/tikz/zoned-spine.tex content/drafts/rag/figures/flow.tex
   ```
3. **Panels get lettered sub-captions, in both forms.** <moved rider 2
   verbatim>. **The worked three-panel example is reference.md §2.**
4. **Write the ASCII twin** in `figures/<name>.txt`, in
   `docs/WRITING-STANDARDS.md` §10's 7-bit alphabet, depicting the same
   thing as the TikZ: same boxes, same arrows, same panel letters.
   "A Unicode box character hard-fails `pdflatex`" (from the thesis
   rider).
5. **No citekey inside either figure file.** The gate reads the draft
   and does not follow `\input`, so a citekey in a node label evades the
   one check this pipeline exists for. Attribute in the prose beside the
   figure, where the gate can see the key.
6. **The TikZ must be as original as the ASCII.** <moved rider verbatim>
7. **Verify it compiles.** Run `kpsewhich tikz.sty` first. **If it
   finds nothing, write no pair: return to the caller, whose figure
   step names its ASCII fallback, and say so in chat.** Otherwise
   <moved probe rider verbatim: minimal article + `\usepackage{tikz}`,
   `pdflatex`, the `\usetikzlibrary` line, "write nothing else about
   loading", `tikz@node@reset@hook`, #781>.
   ```bash
   kpsewhich tikz.sty
   pdflatex probe.tex          # \documentclass{article}\usepackage{tikz} + \input{figures/flow}
   ```
8. **Read what the geometry says.**
   `python -m chitragupta.review figure <draft>` reports what the
   figure's own geometry shows. It is a review aid and never a gate:
   read each finding, fix what is a real defect against the pre-flight
   list, and leave the rest.
9. **Return.** Tell the caller the two paths and whether the probe
   passed. The caller places the marker and caption in its own shape,
   and later runs `python -m chitragupta.draft gate` and renders. None
   of that is this skill's.
````

Strip from the moved text: "Step 11's gate" / "Step 13's gate" (say
"the gate"); "This is the genre most likely to want one -- a taxonomy
figure..." (survey-only, stays in the survey stub); the
"-- the same 'actually run it' discipline step 8 applies" clause
(tutorial-only); and any "if step 0 settled on a flat draft".

- [ ] **Step 4: Write `.claude/skills/figure-drawer/reference.md`**

```markdown
# figure-drawer: reference

Read a section only when the procedure in SKILL.md points at it.

## 1. Choosing a metaphor
<The table from assets/tikz/README.md ("File | Metaphor | Reach for it
when"), quoted with a line saying assets/tikz/README.md is the source and
wins if the two ever disagree. Then one paragraph per common confusion,
taken from docs/TIKZ-STYLE.md "Commit to a layout metaphor":
pipeline vs control loop (does the cycle close?), tree vs hub-and-spoke,
zoned spine vs layered stack.>

## 2. Panels
<docs/TIKZ-STYLE.md "Panels in one figure"'s three-panel worked example,
both the TikZ and the .txt, plus the row-wrapping rule, and why not
`subcaption`, each in two or three sentences with a pointer back to the
section.>

## 3. Fit without scaling
<#1012's before/after: the `\resizebox`-ed figure whose labels fell
below the body size, and the same figure re-laid out (fewer columns,
wrapped labels, a second row). Take the pair from PR #1026's description
or docs/TIKZ-STYLE.md "Draw for the width it will be printed at".>

## 4. An annotated exemplar
<assets/tikz/exemplars/architecture.tex, excerpted (not copied whole),
with a note per feature: why the zone cards, why the step badges, why
the legend swatch, why the house block is left byte-identical. It ends
by saying the exemplars are set at acmart's 506pt and a draft starts from
a scaffold, not an exemplar.>
```

Each `<...>` is text you compose from the named source, not a slot to
leave: the step is done when no angle bracket is left. Quote
`docs/TIKZ-STYLE.md` rather than paraphrase where it is already
precise. Keep `reference.md` under ~250 lines.

- [ ] **Step 5: Make the other two copies**

```bash
mkdir -p .agents/skills/figure-drawer .opencode/skills/figure-drawer-opencode
cp .claude/skills/figure-drawer/{SKILL.md,reference.md} .agents/skills/figure-drawer/
cp .claude/skills/figure-drawer/{SKILL.md,reference.md} .opencode/skills/figure-drawer-opencode/
```

In the OpenCode copy, change `name: figure-drawer` to
`name: figure-drawer-opencode`, and change every backticked skill name
(`` `draft-reviser` ``, `` `survey-writer` `` and so on) to its
`-opencode` form, as the other OpenCode copies do. Add
`"figure-drawer": "deny"` to `.opencode/opencode.json` between
`"draft-reviser"` and `"survey-writer"`.

- [ ] **Step 6: Exempt the helper by name in the every-skill tests**

In `tests/test_skill_verbatim_scan_step.py`, after `_OLD_OFFER`:

```python
# Skills that never present a draft, so have nothing to scan. Named, not
# inferred, so a new drafting skill cannot slip in here by accident.
# `figure-drawer` draws and returns to its caller, which runs the scan
# (#1027).
_HELPERS = {"figure-drawer"}
```

and in `test_every_drafting_skill_runs_the_verbatim_scan` filter
`files = [p for p in _skill_files() if p.parent.name not in _HELPERS]`.
In `test_genre_doc_still_speaks_for_every_skill_that_exists` change
`9` → `10` and `"all nine"` → `"all ten"` (message and assertion).

In `tests/test_skill_style_check_step.py`, add the same `_HELPERS`
constant with the same comment, and filter it out of
`test_every_drafting_skill_runs_the_prose_check` only. The qualifier
test iterates over mentions, so it needs no change.

In `tests/test_skill_pregate_feedback_step.py`, add `"figure-drawer"`
to `_EXCLUDED_SKILLS`, and update the comment above it ("The five
skills that must never carry this step") plus the "five-of-nine"
wording in the docstring and messages to "five-of-ten".

`tests/test_skill_frontmatter.py:41`:
`assert len(SKILL_FILES) == 30  # ten skills, three harnesses`.

- [ ] **Step 7: Docs**

- `docs/GENRE.md`: add a section after "📕 Assembling a book":
  ``## 🖍 Drawing a figure: `figure-drawer` ``. It covers what the skill
  owns, the handoff from four genre skills and `draft-reviser`, direct
  use as a revision, and why each genre keeps a stub (the handoff can be
  skipped; the stub holds the no-citekey rule). Rename
  "What all nine have in common" → "What all ten have in common" (heading,
  TOC link and anchor, "nine `SKILL.md` files" → "ten"). Add, next to the
  `book-assembler` paragraph: "`figure-drawer` presents no draft at all.
  It draws one figure and returns to the skill that called it, so the
  gate, the prose check, the verbatim scan and the stamp below are that
  skill's, not its own." Add an at-a-glance row.
- `docs/FEATURES.md`: line 101 "9 skills" → "10 skills"; heading
  "### 🤖 Nine skills" → "### 🤖 Ten skills"; a bullet naming
  `` `figure-drawer` `` (`tests/test_features_doc.py` requires both).
- `README.md:161` "Nine skills" → "Ten skills", and a line for the new
  skill if that list names each; `README.md:372`, `DEVELOPER.md:223,377`,
  `docs/HARNESS.md:176,263`: nine → ten.
- Find any others:
  `grep -rn -i -E "\bnine\b" README.md DEVELOPER.md AGENTS.md docs/ | grep -i skill`.
  Leave `plans/` alone (allowed to go stale) and dated measurements.
- `pyproject.toml`: `version = "6.136.0"`.

- [ ] **Step 8: Run the touched tests**

Run:

```bash
poetry run pytest tests/test_skill_figure_step.py tests/test_skill_harness_copies.py tests/test_skill_frontmatter.py tests/test_skill_verbatim_scan_step.py tests/test_skill_style_check_step.py tests/test_skill_pregate_feedback_step.py tests/test_skill_retrieval_logging.py tests/test_features_doc.py tests/test_init.py -v
```

Expected: all PASS. If `test_the_copies_differ_only_where_the_phrase_map_says`
fails for `figure-drawer`, a sentence differs between copies. Fix the
copy; do not add a phrase-map entry for drift.

- [ ] **Step 9: Commit**

```bash
git add .claude/skills/figure-drawer .agents/skills/figure-drawer .opencode/skills/figure-drawer-opencode \
  .opencode/opencode.json tests/test_skill_figure_step.py tests/test_skill_frontmatter.py \
  tests/test_skill_verbatim_scan_step.py tests/test_skill_style_check_step.py \
  tests/test_skill_pregate_feedback_step.py docs/GENRE.md docs/FEATURES.md README.md \
  DEVELOPER.md docs/HARNESS.md pyproject.toml
git commit -m "Add the figure-drawer skill the genre skills will hand figures to"
```

---

### Task 2: The four genre skills keep a stub and hand off

**Files:**

- Modify (×3 copies each, 12 files):
  `{.claude,.agents}/skills/survey-writer/SKILL.md` +
  `.opencode/skills/survey-writer-opencode/SKILL.md` (step 9, lines 401-497 on
  `10ac21f`),
  `tutorial-writer` (step 9, 373-476),
  `textbook-chapter-writer` (step 7, 331-~434),
  `thesis-chapter-writer` (step 9, 320-~460)
- Modify: `tests/test_skill_figure_step.py`

**Interfaces:**

- Consumes: Task 1's skill name `figure-drawer` / `figure-drawer-opencode`, and
  its literal rider phrases (now asserted *absent* here).

- [ ] **Step 1: Add the failing stub tests** (append to
      `tests/test_skill_figure_step.py`)

```python
_GENRES = {
    "survey-writer": _MARKDOWN_SHAPE,
    "tutorial-writer": _MARKDOWN_SHAPE,
    "textbook-chapter-writer": _MARKDOWN_SHAPE,
    "thesis-chapter-writer": _THESIS_SHAPE,
}


def test_every_figure_genre_keeps_the_no_citekey_rule():
    # The one rule whose loss is unsafe if a harness skips the handoff:
    # the gate does not follow \input (SOUL.md). It must not be trimmed
    # out of a stub on the grounds that figure-drawer also says it.
    missing = [g for g in _GENRES if _NO_CITEKEY not in _text(g)]
    assert not missing, f"no-citekey rule missing from: {missing}"


def test_every_figure_genre_keeps_its_own_shape():
    wrong = [g for g, shape in _GENRES.items() if shape not in _text(g)]
    assert not wrong, wrong
    assert _MARKDOWN_SHAPE not in _text("thesis-chapter-writer")


def test_every_figure_genre_hands_off():
    missing = [g for g in _GENRES if f"`{DRAWER}`" not in _text(g)]
    assert not missing, f"no handoff to figure-drawer in: {missing}"


def test_no_rider_has_drifted_back_into_a_genre_skill():
    # #1012 edited twelve files for one sentence. A rider that reappears
    # here is that duplication coming back one copy at a time.
    found = {g: [r for r in _RIDERS if r in _text(g)] for g in _GENRES}
    found = {g: rs for g, rs in found.items() if rs}
    assert not found, f"riders belong only in figure-drawer: {found}"


def test_deep_research_draws_no_figure_and_names_no_drawer():
    assert f"`{DRAWER}`" not in _text("deep-research")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest tests/test_skill_figure_step.py -v`
Expected: `test_every_figure_genre_hands_off` and
`test_no_rider_has_drifted_back_into_a_genre_skill` FAIL; the no-citekey,
shape and deep-research tests already PASS. That is expected: they guard
against Step 3 trimming too much.

- [ ] **Step 3: Rewrite `survey-writer`'s step 9 (Claude copy) as a stub**

Keep the opening "Add a figure only for what the table can't express"
paragraph unchanged, since it is the threshold. Replace everything from
"**On that rare occasion, look at how the surveyed papers draw it
first.**" through the caption rider with:

````markdown
   **On the rare occasion one is warranted, hand the drawing to
   `figure-drawer`** and return here when it does. It owns the
   scaffolds, the panels, the ASCII twin, the compile probe and the
   geometry review. Three things stay with this step, because they
   must hold even if that skill is never loaded:

   - **The shape.** A pair of files,
     `content/drafts/<topic>/figures/<name>.tex` and `.txt`, named in
     the draft by a marker line of its own, with nothing beside it:

     ```html
     <!-- figure: figures/<name> -->
     ```

     with a caption line directly below (no blank line) and an inline
     `<!-- figureref: <name> -->` wherever prose points at it. Never
     write "Figure" or a number. An uncaptioned marker is
     `chitragupta.FigureNoCaption` in step 16. If TikZ is not installed,
     `figure-drawer` writes no pair; write the ASCII inline in a fence
     instead, no marker, and say so in chat.
   - **A topic directory is required.** If step 0 settled on a flat
     `content/drafts/<slug>.md`, move the draft and its dossier first, or
     drop the figure. In this genre, dropping it is usually right.
   - **No citekey inside either figure file.** Step 11's gate reads the
     draft and does not follow `\input`. This is the genre most likely to
     want one, since a taxonomy naturally attributes each branch, and the
     figure is exactly the wrong place for it: attribute in the prose or
     the comparison table.
````

The quantity and numbered-math paragraphs after it are unchanged.

- [ ] **Step 4: The same for `tutorial-writer` and `textbook-chapter-writer`**

Same stub, with each genre's own wording kept where it differs today:

- `tutorial-writer` step 9: keep the "Go back to wherever it belongs ...
  Draw every one that passes, and none that doesn't" threshold
  paragraph. Gate is "Step 13's"; render step is 15; flat-draft line
  refers to "step 1" and says "skip the figure". Caption sentence: "Most
  of this genre's rare figures need no caption at all, and that is the
  accepted case, not a gap." No-citekey closer: "This genre's citations
  belong in 'Where to go next' anyway."
- `textbook-chapter-writer` step 7: keep the threshold paragraph
  including "A figure you considered and dropped is a `rejected.md` row".
  Gate is step 12's (its "Never write a citekey" step), render step 14,
  flat-draft line refers to "step 0". Caption: "Every figure needs a
  caption -- an uncaptioned marker is reported as
  `chitragupta.FigureNoCaption` (#421)."

Before trimming, diff each genre's rider block against survey-writer's
(for example, `diff` the two `sed -n` ranges).
Any genre-specific sentence the diff shows, other than those listed
above, either stays in that genre's stub or gets a line in the PR saying
why it went.

- [ ] **Step 5: `thesis-chapter-writer` step 9**

Keep the threshold paragraph ("Default to no figure."). Replace the look
paragraph and the generic riders (metaphor, panels, compile probe, "as
original") with the handoff sentence. Keep these, all thesis-only output
shape: the `\input{figures/<name>.tex}` + `%figure: figures/<name>`
block; "The marker is a comment, never a second `\input`"; "A topic
directory is required"; the ASCII fallback in a `verbatim` environment
if TikZ is absent; "No citekey inside either figure file" ("Cite in the
prose that introduces the figure."); the `figure` float with
`\caption`/`\label{fig:<id>}`, never `\renewcommand{\thefigure}`; and
the `[tikz-libraries]` and `[unicode]` preamble riders, word for word.
The equation paragraph is unchanged.

- [ ] **Step 6: Propagate to `.agents/` and `.opencode/` copies**

Apply each edit to the other two copies. In the OpenCode copies, the
handoff names `` `figure-drawer-opencode` ``. Then:

Run:

```bash
poetry run pytest tests/test_skill_harness_copies.py tests/test_skill_figure_step.py -v
```

Expected: all PASS, including
`test_the_opencode_copy_refers_to_opencode_skills[survey-writer]` and
the three other genres.

- [ ] **Step 7: Measure what was saved, for the PR**

```bash
git diff --stat origin/main -- .claude/skills .agents/skills .opencode/skills
```

Record each genre's figure-step line count before and after (the issue
says 122-162). The issue expects roughly 70 lines saved per copy,
about 840 in all.

- [ ] **Step 8: Run the skill scans and commit**

Run:

```bash
poetry run pytest tests/test_skill_*.py tests/test_features_doc.py -v
```

Expected: all PASS.

```bash
git add .claude/skills .agents/skills .opencode/skills tests/test_skill_figure_step.py
git commit -m "Hand figure drawing from the four genre skills to figure-drawer"
```

---

### Task 3: `draft-reviser` hands redrawing to `figure-drawer`

**Files:**

- Modify: `.claude/skills/draft-reviser/SKILL.md:50-100` (+ the `.agents/` and
  `.opencode/` copies)
- Modify: `tests/test_skill_figure_step.py`

**Interfaces:**

- Consumes: `figure-drawer`'s "Who called you" section from Task 1, which says
  `draft-reviser` logs the change.

- [ ] **Step 1: Failing test** (append)

```python
def test_draft_reviser_hands_redrawing_to_the_drawer():
    text = _text("draft-reviser")
    assert f"`{DRAWER}`" in text
    # The revision-only rule stays here: both forms change together, and
    # the change is logged. That is not a drawing rule.
    assert "Touch a figure, touch both forms" in text
    assert not [r for r in _RIDERS if r in text]
```

- [ ] **Step 2: Run it to verify it fails**

Run:

```bash
poetry run pytest tests/test_skill_figure_step.py::test_draft_reviser_hands_redrawing_to_the_drawer -v
```

Expected: FAIL on the `figure-drawer` assertion.

- [ ] **Step 3: Edit the Claude copy**

In the "Touch a figure, touch both forms" bullet, keep everything about
finding the pair from the marker, both forms changing together,
re-lettering panels, the thesis inline `\input`, and "Nothing checks
any of this". Replace "If you edit the TikZ, re-verify it compiles before
you keep it (§10's standalone `pdflatex` check) -- a figure that no
longer compiles fails the whole pdf render, not just the figure." with:

```markdown
  **To redraw or fix the picture, hand it to `figure-drawer`** and
  come back to step 6 to log it: that skill owns the scaffolds, the
  compile probe and the geometry review, and it re-verifies the TikZ
  compiles before you keep it.
```

Keep the "drifted too far to reconcile, say so and drop the figure"
sentence. Leave the "consult a source figure" bullet as it is: in a
revision it also serves sentences about a paper's figure, not only
drawing.

- [ ] **Step 4: Propagate, run, commit**

Apply the edit to the `.agents/` and `.opencode/` copies (the latter
says `` `figure-drawer-opencode` ``).

Run:

```bash
poetry run pytest tests/test_skill_figure_step.py tests/test_skill_harness_copies.py -v
```

Expected: PASS.

```bash
git add .claude/skills/draft-reviser .agents/skills/draft-reviser .opencode/skills/draft-reviser-opencode tests/test_skill_figure_step.py
git commit -m "Send draft-reviser's figure redraws through figure-drawer"
```

---

### Task 4: Full suite, and the handoff checked in each harness

**Files:**

- Modify: this plan (outcome line at the top) and the PR description only.

- [ ] **Step 1: Full suite under CI's interpreter**

Set up the worktree's environment as memory "Worktree test env setup"
describes (clean in-project venv, `config.toml`). Then:

Run: `poetry run pytest -q` then `poetry run pylint chitragupta tests` under
Python 3.13, and the repository's coverage command from `DEVELOPER-AGENTS.md`.
Expected: all pass, 100% line and branch coverage (no code changed, so
any drop means a test edit broke something).

- [ ] **Step 2: Claude Code handoff run**

In a scratch `chitragupta init` project with a synced test corpus, ask
the tutorial genre for a short lesson that needs one diagram. Record
whether `figure-drawer` was loaded (the session's skill-load line), the
`figures/<name>.tex`/`.txt` pair, and that `draft gate` passed.

- [ ] **Step 3: Codex and OpenCode handoff runs**

Drive each with the stand-in model as memory "Harness testing with a
stand-in model" describes (Codex: no API key; OpenCode: local Qwen at
:18080; watch for the zombie-git stall). Same request. Record for each:
did it load `figure-drawer` (OpenCode: `figure-drawer-opencode`)? If it
skipped the handoff, did the stub alone keep the figure citekey-free and
in shape? A skipped handoff is a finding to record in the PR and in
`docs/HARNESS.md`'s measured section, not a reason to block. The stub
exists for exactly that case.

- [ ] **Step 4: Review**

`ocr review` cannot run in the container (memory "OCR has no LLM endpoint
in container"). Use the `pr-review-toolkit:code-reviewer` agent on the
branch diff instead, and say so in the PR's test plan.

- [ ] **Step 5: Record the outcome and open the PR**

Add the outcome line under `Status:` here. Write the PR with the
`## Commit message` fence `scripts/merge_pr.py --check` expects (memory
"merge_pr.py commit message fence"). Include the before/after line
counts from Task 2 Step 7 and the three harness results from Steps 2-3,
and tick the issue's checklist item by item.

---

## Self-review against #1027's success criteria

| Criterion | Where |
| --- | --- |
| Skill in all three copies; harness test, deny list and doc counts agree | Task 1 steps 3-7 |
| Genre figure steps keep only threshold, shape, no-citekey, handoff; riders once | Task 2; `test_no_rider_has_drifted_back_into_a_genre_skill` |
| A test pins the no-citekey rule in each genre skill | `test_every_figure_genre_keeps_the_no_citekey_rule` |
| A drafting run in each harness loads `figure-drawer`, recorded in the PR | Task 4 steps 2-3 |
| 100% coverage | Task 4 step 1 (no `chitragupta/` change) |
| No citekey generated; no check promoted to a gate | Global constraints; `test_the_drawer_hands_back_and_never_presents`; `review figure` described as an aid |
| `draft-reviser` can use it to fix one | Task 3 |
| Direct use ("draw a figure for this section") | Task 1 "Who called you" (Decision 2) |
