# Splitting each skill into `SKILL.md`, `references/`, `scripts/` and `assets/`

Status: **designed, unbuilt.** Written 2026-10-06, for
[issue 997](https://github.com/prasadtalasila/chitragupta/issues/997).

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Written for** whoever builds #997, one PR at a time. **It assumes**
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the shipping cycle each
PR below runs (version bump, changelog, local checks, the
`## Commit message` fence), [docs/HARNESS.md](../docs/HARNESS.md) for why
there are three skill trees, and [docs/PACKAGING.md](../docs/PACKAGING.md)
for the two command forms.

**Not covered here:** rewriting any skill's *judgement*. This plan moves
text and wraps commands. A paragraph that changes meaning on the way is
out of scope and goes through its own issue.

**Goal:** each skill's `SKILL.md` keeps the workflow and the decisions only
the model can make. Reference detail loads only at the step that needs it,
fixed command tails run as one tested script, and the reference material
and scripts exist **once** instead of three times.

**Architecture:** harness-neutral material lives only under `.claude/`
(`.claude/skills/<name>/{references,assets}/` for one skill,
`.claude/skills-common/{references,scripts}/` for material several skills
share). All three harness copies of `SKILL.md` point at those files by
project-root path. Only `SKILL.md` stays triplicated, which is where the
wording actually differs.

**Tech stack:** Markdown, stdlib Python 3.11+ scripts that shell out to
`sys.executable -P -m chitragupta.<layer> <verb>`, and pytest.

## 🔬 What was measured, and what it settles

Everything below was established on 2026-10-06 against `8517f70`.

### Every open question in the issue has an answer

| Issue's open question | Answer | Evidence |
| --- | --- | --- |
| Do Codex and OpenCode load `references/` on demand? | **Yes, all three harnesses.** Up front they load only the name and description, the body loads on use, and subfolder files are read or run by path, never inlined. OpenCode's `skill` tool lists up to 10 file *paths* but not their contents | Claude Code docs; `openai/codex` `ext/skills/src/catalog_prompt.rs`; `sst/opencode` `packages/opencode/src/tool/skill.ts` |
| Can a skill point outside its own folder? | **Yes.** Reads go through the model's ordinary file tools, and no harness confines them to the skill folder. Codex's prompt resolves a relative path against the skill directory *first*, so write a project-root path and say that it is one | same sources. Not stated in any harness's docs: inferred from the tool design |
| Does `code_standards_hook.py`'s issue-890 rule catch `.claude/skills/*/scripts/`? | **No.** `WATCHED_ROOTS = ("chitragupta", "scripts")` is matched with `is_relative_to(REPO_ROOT / root)` (`.claude/hooks/code_standards_hook.py:77,113`). The "planted `scripts/`" reading is in `docs/HOOKS.md:426-431`, not a path match, and an installed project starts no scanner at all (`:128`) | read |
| Interpreter resolution | A script run by path gets its *own* directory as `sys.path[0]`, not the project root, so it avoids the shadowing #928 fixed with `-P`. Its children are launched as `sys.executable -P -m …`. It checks `importlib.util.find_spec("chitragupta")` first and exits 2 with a pointer to `docs/CLI.md` "Which interpreter" | design, Task 16 |
| Does `chitragupta init` carry subfolders? | **Yes, unchanged.** `_write_tree` copies with `rglob("*")` (`chitragupta/init.py:272-294`). `.claude` is in `COPY_VERBATIM` for **every** `--agent` (`:73-92`), so a Codex or OpenCode project always has the shared files. The `python -P` rewrite applies to every `.md` under it, `references/` included | read |
| Does `scripts/release.py` carry them? | **Yes.** It filters on the first path component only (`:149`) | read |

### Why one physical copy under `.claude/` rather than a synced copy per tree

The issue's step 4 leaves this open. There are three options:

- **Copy into all three trees and keep them synced with a script.** This
  keeps every skill self-contained, but every reference file then sits on
  disk three times. `test_skill_harness_copies.py` would have to compare
  subtrees, and a fix made in the wrong copy is overwritten silently.
- **Symlinks.** No harness documents symlinks *inside* a skill. OpenCode's
  file listing uses `follow: false`, and the wheel, the sdist and the
  release zip were never tested with symlinks.
- **One copy under `.claude/`, pointed at by path (chosen).** `.claude/`
  is already scaffolded for every harness, and the harnesses read files by
  path anyway. Nothing needs syncing, and the triplication drops to
  `SKILL.md` alone.

The cost of the chosen option is a rule: **a harness-neutral file names
no harness tool and no skill.** OpenCode's copy must route to
`<name>-opencode`, so a reference that said `agenda-reviser` would send it
to a skill `.opencode/opencode.json` denies. A routing sentence therefore
stays in `SKILL.md`, and Task 1 makes this a test.

### Where the context saving actually comes from

The inventory below puts roughly 30% of the 6,738 lines in each tree in
reference (R) or template (A) passages, with another ~20% in fixed
command sequences (S). **Only some of that is a context saving.** A
passage the model reaches on every run, such as the verbatim-scan rider,
costs the same tokens whether it sits in `SKILL.md` or in a reference
file. Moving it saves duplication, not context. The real context saving
comes from passages that apply only sometimes:

| Conditional passage | Skill(s) | Lines (approx.) |
| --- | --- | --- |
| Copy-edit mode, acronym realignment, re-grounding R1–R5, whole-corpus / no-dossier | draft-reviser | 310 |
| LaTeX conventions and skeleton | book-assembler | 240 |
| Per-class repair recipes and the class table | agenda-reviser | 170 |
| Figure stub (only when a figure is warranted) | 4 genre writers | 80 each |
| Collection scoping (only when the ledger has collections) | 4 genre writers | 59 each |

There are two PRs. PR 1 is all of what the issue calls *"a reasonable
first phase"*: shared references and per-skill references. PR 2,
which adds scripts, can be declined without stranding anything.

### Inventory (issue step 1)

These classifications come from a full read of all ten skills. Line
numbers are in `.claude/skills/<name>/SKILL.md` at `8517f70`.

| Skill | W | R | S | A | Main R/A blocks to move |
| --- | ---: | ---: | ---: | ---: | --- |
| survey-writer | 360 | 230 | 160 | 10 | corpus layer 15–26, collection 27–85, dossier 86–120, figure stub 401–480, finish riders 585–745 |
| thesis-chapter-writer | 330 | 240 | 150 | 10 | as survey; figure stub 320–439 |
| textbook-chapter-writer | 320 | 230 | 150 | — | as survey; figure stub 331–415 |
| tutorial-writer | 350 | 220 | 150 | — | as survey; figure stub 373–453 |
| deep-research | 430 | 230 | 200 | (reference.md §5) | depth presets 235–244, Phase 7 d–h 504–834 |
| draft-reviser | 560 | 150 | 110 | — | modes 493–802, prose/verbatim riders 426–492 |
| corpus-reviser | 90 | 110 | 60 | — | copied rules 121–240 |
| agenda-reviser | 230 | 170 | 60 | — | class table 66–109, recipes 165–290 |
| book-assembler | 110 | 250 | 130 | 40 | conventions 32–275 (skeleton 53–90) |
| figure-drawer | most | 35 | some | — | already has `reference.md` |

Passages that are shared across skills and identical, or nearly so:

- **collection scoping:** byte-identical in 4 genres
- **corpus read-only paragraph:** 5 genres
- **critique against the evidence packet:** ~100 lines, 5 genres
- **prose-check rider:** 8 skills
- **verbatim-scan rider:** 9 skills
- **render, references and evidence paragraphs:** 4 genres
- **figure stub:** 4 genres

## Global constraints

- **SOUL.md's one invariant.** No file this plan creates holds a
  citekey, whether in an example, a fixture or a reference. No new check
  is promoted into a gate.
- **Coverage stays at 100%**, line and branch, on both the Linux and the
  Windows config (`pyproject.toml`, `coveragerc-windows.toml`,
  `tests/test_coverage_configs_agree.py`).
- **A script never reimplements a verb.** Each script is an ordered list
  of `python -m chitragupta.<layer> <verb>` calls, every one of them named
  in `docs/CLI.md`. A test enforces this (Task 17).
- **The model keeps its decisions.** A script never decides anything a
  `SKILL.md` step asks the model to judge: whether to proceed uncited,
  what to fix after a gate failure, whether to present. The gate stays a
  separate command in `SKILL.md`, because acting on its failure is
  judgement.
- **No behaviour change.** Today's command orders are kept exactly, even
  where they differ: draft-reviser and corpus-reviser stamp *before*
  style and scan, the genres stamp last, and agenda-reviser never stamps.
  Making them consistent is a separate issue.
- **Every SKILL.md edit lands in all three trees in the same commit.**
  `tests/test_skill_harness_copies.py` and the phrase map keep doing
  their job for `SKILL.md`.
- **Paths in `SKILL.md` are project-root paths**, written in backticks
  and introduced once per skill with "(paths from the project root)".
- **Markdown lint:** run the `markdownlint-cli2` glob from
  DEVELOPER-AGENTS.md. It already covers `.claude/**/*.md`.

## Review focus

The five failures most likely to reach a user that no task's main tests
would otherwise catch. Each line names the task that pins it.

1. **A reference link that does not resolve**, after a typo or a rename,
   in any of the three trees. The model then reads nothing and carries on.
   Expected: CI fails, naming the `SKILL.md` and the path (Task 1,
   `test_every_named_path_exists`).
2. **A shared reference that names a skill or a harness tool.** OpenCode
   would be routed to a denied skill, or Codex told to use `Edit`.
   Expected: CI fails (Task 1, `test_neutral_files_name_no_skill_or_tool`).
3. **`finish.py` run by an interpreter without `chitragupta`**, such as
   the system `python` in a project whose venv is not active. Expected:
   exit 2 with one line naming `docs/CLI.md` "Which interpreter", and no
   traceback (Task 16).
4. **A draft path with spaces, or a Windows path.** Expected: the script
   passes it through untouched as one argv element. It never uses a shell
   (Task 16, `test_a_path_with_spaces_is_one_argument`).
5. **A step in the tail exits non-zero for an expected reason**, such as
   `dossier sections` exiting 1 on a draft with no dossier, which every
   genre says to "say so and scan anyway". Expected: the scan still runs
   and the script exits 0. An *unexpected* exit continues the sequence,
   so every report is shown, but makes the script exit 1 (Task 16,
   `test_a_missing_dossier_still_scans`).

---

## PR 1: the layout, the shared references and the per-skill references

One PR in four parts. The user merged what were three PRs into it on
2026-10-06 and asked for every skill to be checked on every harness on
this machine before it merges.

- **Part A** sets up the layout using the two files that already exist
  (Tasks 1–3).
- **Part B** moves the passages several skills share (Tasks 4–9).
- **Part C** moves each skill's own conditional material (Tasks 10–14).
- **Part D** runs every skill on Claude Code, Codex and OpenCode locally
  (Task 15).

Each part lands as its own run of commits, in that order, so a reviewer
can read them apart and a bisect lands inside one part.

### Part A: the layout, proved with the two existing reference files

Closes nothing. It is titled *"Give skills a `references/` folder, kept
once under `.claude/`"*.

#### Task 1: teach the harness-copy test the new layout

**Files:**

- Modify: `tests/test_skill_harness_copies.py`
- Create: `tests/test_skill_references.py`

**Interfaces:**

- Produces: `NEUTRAL_ROOTS` (list of `Path` globs below), plus the rule
  that `.agents/skills/<name>/` and `.opencode/skills/<name>-opencode/`
  hold exactly `SKILL.md`.

- [ ] **Step 1: write the failing tests** in
  `tests/test_skill_references.py`:

```python
"""Harness-neutral skill files exist once, under .claude/ (#997).

`SKILL.md` is the only file kept per harness. Every other file a skill
uses lives in `.claude/skills/<name>/{references,assets,scripts}/` or in
`.claude/skills-common/`, which `chitragupta init` scaffolds for every
`--agent`, and all three copies of `SKILL.md` name it by project-root
path. A file read by all three harnesses therefore names no harness's
tools and no skill: OpenCode routes to `<name>-opencode`, so a bare
skill name here would send it to a skill its config denies.
"""

import re
from pathlib import Path

import pytest

from tests.test_skill_harness_copies import FOREIGN, ROOTS, SKILLS, folder

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE = REPO_ROOT / ".claude"
NEUTRAL_DIRS = ("references", "assets", "scripts")
NAMED_PATH = re.compile(r"`(\.claude/skills(?:-common)?/[^`\s]+)`")
TOOLS = sorted({word for words in FOREIGN.values() for word in words} | {"`Edit`", "`Write`", "`Read`"})


def neutral_files() -> list:
    roots = [CLAUDE / "skills-common", *(CLAUDE / "skills" / s / d for s in SKILLS for d in NEUTRAL_DIRS)]
    return sorted(p for root in roots if root.is_dir() for p in root.rglob("*") if p.is_file())


def every_skill_md() -> list:
    return [folder(h, name) / "SKILL.md" for h in ROOTS for name in SKILLS]


@pytest.mark.parametrize("skill_md", every_skill_md(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_every_named_path_exists(skill_md):
    text = skill_md.read_text(encoding="utf-8")
    missing = [m for m in NAMED_PATH.findall(text) if not (REPO_ROOT / m.split("#")[0]).exists()]
    assert not missing, missing


def test_every_neutral_file_is_named_by_some_skill():
    text = "".join(p.read_text(encoding="utf-8") for p in every_skill_md())
    named = {REPO_ROOT / m.split("#")[0] for m in NAMED_PATH.findall(text)}
    orphans = [p for p in neutral_files() if p not in named and p.suffix == ".md"]
    assert not orphans, orphans


@pytest.mark.parametrize("path", neutral_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_neutral_files_name_no_skill_or_tool(path):
    text = path.read_text(encoding="utf-8")
    hits = [w for w in TOOLS if w in text] + [s for s in SKILLS if f"`{s}`" in text]
    assert not hits, hits


@pytest.mark.parametrize("harness", ["codex", "opencode"])
@pytest.mark.parametrize("name", SKILLS)
def test_only_skill_md_is_kept_per_harness(name, harness):
    assert sorted(p.name for p in folder(harness, name).iterdir()) == ["SKILL.md"]
```

`test_every_neutral_file_is_named_by_some_skill` applies to `.md` files
only. A script is named by its caller, which Task 18 pins, and an
asset by the reference that uses it (Task 12).

- [ ] **Step 2: run it and see it fail.** Run `pytest
  tests/test_skill_references.py -v`. Expect
  `test_only_skill_md_is_kept_per_harness` to FAIL for `deep-research` and
  `figure-drawer`, because both still carry `reference.md` in every tree.

- [ ] **Step 3: make the harness-copy test layout-aware.** In
  `tests/test_skill_harness_copies.py`, compare only the per-harness
  `SKILL.md`. Do this by replacing `iterdir()` with `glob("*.md")` in
  `test_each_copy_holds_the_same_files` and
  `test_the_copies_differ_only_where_the_phrase_map_says`. Today the
  `iterdir()` there raises `IsADirectoryError` on any subfolder. Then add
  one paragraph to the module docstring saying that the neutral files are
  pinned in `tests/test_skill_references.py`.

#### Task 2: move the two existing `reference.md` files

**Files:**

- Move: `.claude/skills/deep-research/reference.md` →
  `.claude/skills/deep-research/references/report.md`
- Move: `.claude/skills/figure-drawer/reference.md` →
  `.claude/skills/figure-drawer/references/figures.md`
- Delete: the `reference.md` in `.agents/skills/{deep-research,figure-drawer}/`
  and `.opencode/skills/{deep-research,figure-drawer}-opencode/`
- Modify: all six `SKILL.md` copies of the two skills, plus
  `tests/test_skill_figure_step.py`, wherever it asserts
  `reference.md §N`

- [ ] **Step 1: `git mv` the two `.claude` copies, then `git rm` the
  other four.** Keep every `§N` heading, because the tests and `SKILL.md`
  cite them by number.
- [ ] **Step 2: rewrite every mention.** For example,
  `reference.md §1` becomes
  `` `.claude/skills/figure-drawer/references/figures.md` §1 ``.
  On first mention in each skill, add "(paths from the project root)".
  Apply the same edit in all three trees.
- [ ] **Step 3: make the figures file harness-neutral.** Its line 115
  names `thesis-chapter-writer`, and the OpenCode copy suffixed it. Move
  that sentence into `figure-drawer`'s `SKILL.md`, which is per-harness,
  and leave the reference saying "the thesis genre".
- [ ] **Step 4: retarget the tests.** In `tests/test_skill_figure_step.py`,
  read the reference from its new path, and assert the new
  `references/figures.md §1`–`§4` form.
- [ ] **Step 5: run `pytest tests/test_skill_references.py
  tests/test_skill_harness_copies.py tests/test_skill_figure_step.py
  tests/test_skill_frontmatter.py -v`.** Expect every test to PASS.
- [ ] **Step 6: commit both tasks as one commit.**
  `git add -A .claude .agents .opencode tests && git commit`

#### Task 3: pin the scaffold, then write the layout down

**Files:**

- Modify: `tests/test_init.py`
- Modify: `docs/HARNESS.md` ("Skills: one copy per harness",
  `:137-208`), `docs/PACKAGING.md`, `docs/HOOKS.md` (`:404-479`)

- [ ] **Step 1: write the failing init test.** For each `--agent` in
  `("claude", "codex", "opencode")`, run the scaffold and assert three
  things:
  - `.claude/skills/figure-drawer/references/figures.md` exists;
  - every `python -m chitragupta` in it was rewritten to `python -P -m`;
  - no `reference.md` exists anywhere under the target.

  Follow the existing `scaffold(...)` fixtures in `tests/test_init.py`.
  The test passes once Task 2 is in, which confirms that init needs no
  code change. If it fails, the copy filter has changed since this plan
  was written, so fix that rather than the test.

- [ ] **Step 2: update `docs/HARNESS.md`.**
  - Replace the tree at `:150-163` with the new one: `SKILL.md` per
    harness, `references/`, `assets/` and `scripts/` only under `.claude/`,
    and `.claude/skills-common/`.
  - State the neutral-file rule and why it exists (OpenCode routing).
  - Add the per-harness answers from the table above: on-demand loading,
    how each harness learns the base directory, and that Codex resolves
    against the skill folder first.
  - Drop the stale "(deep-research also has reference.md)".

- [ ] **Step 3: update `docs/PACKAGING.md`.** Add one paragraph: `.claude/`
  is scaffolded for every agent, and the reason is now twofold. It
  registers the hooks, and it holds the only copy of every skill's
  reference files.

- [ ] **Step 4: add the upgrade path to `docs/HOOKS.md`.** Under
  "updating an older scaffold" (`:453-464`), document it as these
  commands:

```bash
chitragupta init /tmp/fresh --agent <yours>
cp -r /tmp/fresh/.claude/skills /tmp/fresh/.claude/skills-common .claude/   # skills-common from part B on
cp /tmp/fresh/.agents/skills/*/SKILL.md ...   # each per-harness SKILL.md
find .claude/skills .agents/skills .opencode/skills -name reference.md -delete
```

  `init --force` overwrites but never deletes, which is why the final
  `find … -delete` is spelled out. Also note in one sentence that the
  issue-890 rule concerns a *root-level* `scripts/` and does not cover
  `.claude/skills*/scripts/`.

- [ ] **Step 5: lint, run the tests and commit.**
  - Run `markdownlint-cli2` with DEVELOPER-AGENTS.md's glob.
  - Run `pytest tests/test_init.py tests/test_skill_references.py -v`.
  - Commit.

**Part A is done when** the full local-check list in DEVELOPER-AGENTS.md
passes. List the before and after line counts for the two moved files in
the PR's test plan.

---

### Part B: shared references (de-duplication, plus the conditional saving)

Each task moves **one** passage. In each task:

1. Create `.claude/skills-common/references/<topic>.md`. Its opening line
   says which step points at it, and that it is read only from there.
2. In every skill that carries the passage, in all three trees, replace
   the passage with a pointer sentence. The pointer names the file and
   keeps every per-genre or per-harness sentence (routing, a genre's own
   exception) in `SKILL.md`.
3. Retarget the step test, so that it asserts **the pointer** in
   `SKILL.md` and **the riders** in the reference file. The test still
   fails if either goes missing.

Pointer sentence shape (the same in all three trees):

```markdown
Read `.claude/skills-common/references/verbatim-scan.md` now and follow it.
Repairing a finding is `agenda-reviser`'s job, and only if the user asks.
```

Only the second sentence differs by harness, and only by the OpenCode
suffix, which the existing `SUFFIXED` normalisation absorbs.

#### Task 4: `verbatim-scan.md` (9 skills)

**Files:**

- Create: `.claude/skills-common/references/verbatim-scan.md`
- Modify: 9 skills × 3 trees, and `tests/test_skill_verbatim_scan_step.py`

- [ ] **Step 1: retarget the test before moving anything.**
  - For each of the 9 skills, `SKILL.md` keeps the `dossier sections …
    --write` followed by `review verbatim scan` (200 chars) until PR 2.
  - It names `.claude/skills-common/references/verbatim-scan.md` within
    400 chars after the scan command.
  - The reference contains "genuine restatement is only detected where
    the embedding tier can run", `tiers_not_run` and "never a condition of
    presenting".
  - Keep the existing "Offer the verbatim scan must be absent" check, and
    the `docs/GENRE.md` count.
- [ ] **Step 2: run it and see it fail.** The reference file does not
  exist yet.
- [ ] **Step 3: write the reference from survey-writer's step 17**
  (`.claude/skills/survey-writer/SKILL.md:707-731`), minus the
  `agenda-reviser` sentence. Diff it against the other 8 copies, and
  where they differ, keep the union and record the choice in the commit
  body.
- [ ] **Step 4: swap the passage for the pointer** in 27 files.
- [ ] **Step 5: run the tests.** Run `pytest
  tests/test_skill_verbatim_scan_step.py tests/test_skill_references.py
  tests/test_skill_harness_copies.py -v`. Expect them to PASS.
- [ ] **Step 6: commit.**

#### Task 5: `prose-check.md` (8 skills)

The same five steps as Task 4.

- The anchor is `-m chitragupta.draft style`.
- The riders, "§9 marks decidable" and "fix none of them", move to the
  reference.
- The test is `tests/test_skill_style_check_step.py`. Retarget it to the
  pointer within 400 chars of the command, plus the riders in the
  reference.
- The `draft-reviser` copy-edit sentence stays in `SKILL.md`, because it
  names a skill.

#### Task 6: `critique.md` (5 genres)

The same steps, with one difference: this passage varies by genre. The
reference holds the shared core:

- the baseline commands;
- the per-edit cycle;
- `objective_delta`;
- "90% of its own";
- "at most three items";
- "no second critique pass";
- the `revisions.md` and "Never write any of this to `rejected.md`" rules;
- the `no evidence` / "cut the sentence" / "never to re-point it" /
  `dossier status` block;
- the exhausted-queries rule;
- "never a condition of presenting".

`SKILL.md` keeps the heading "Critique against the evidence packet" and
the genre's own deltas: draft or fragment, textbook and tutorial's "skip
if no citations", and deep-research's peer-review distinction.

In `tests/test_skill_pregate_feedback_step.py`:

- Keep "only the 5 genres contain the heading".
- Move the 5900-char window assertions onto the reference file.
- Assert that each genre's step names the reference.

#### Task 7: `collection-scoping.md` and `corpus-read-only.md`

- **Collection scoping** is byte-identical in survey, thesis, textbook
  and tutorial, so it moves whole. deep-research's deliberate
  anti-version and the revisers' "inherit" variants stay where they are.
- **Corpus read-only** covers the five genres. The revisers' short forms
  stay.

No step test reads either passage today. Add one assertion to
`tests/test_skill_references.py`: each of the four genres names
`collection-scoping.md` within its collection step.

#### Task 8: `figure-handoff.md` (4 figure genres)

The figure stub is the largest conditional passage per genre, at about
80 lines.

- **The reference holds the shared part:**
  - topic directory required;
  - `kpsewhich tikz.sty`;
  - "No citekey inside either figure file";
  - "compiles";
  - "redrawn from a source";
  - the caption and `figureref` rule;
  - §12 math numbering.
- **`SKILL.md` keeps three things:**
  - the decision whether a figure is warranted;
  - the genre's own marker shape, LaTeX for thesis and Markdown for the
    others;
  - the `figure-drawer` handoff sentence, which names a skill.

In `tests/test_skill_figure_step.py`, the per-genre assertions split two
ways: marker shape and handoff stay on `SKILL.md`, and the rest move to
the reference. Keep the "no riders in the genre" check, now applied to
`SKILL.md` *and* to the reference.

#### Task 9: `render-and-references.md` (4 genres plus deep-research)

This task covers the shared paragraphs on render, references and the
evidence sidecar:

- the "All three land beside the draft" / `[missing-binary]` warning;
- the "Stdlib-only… IEEE… leave `[@citekey]`" paragraph.

It contains no literal citekey. `[@citekey]` is a placeholder in
backticks, and it is already in today's text.

The per-genre format matrix stays in `SKILL.md`, because it is a genre
decision:

- thesis renders md and pdf only;
- tutorial has no evidence sidecar;
- textbook writes the evidence sidecar as pdf only.

Then add `.claude/skills-common/references/` to the Task 3 init test for
all three agents, and commit.

**Part B is done when** the local checks pass. The PR's test plan lists
the per-skill `SKILL.md` line counts before and after, for all three
trees.
Expected `SKILL.md` lengths per tree, estimated on 2026-10-06 from the
measured passage spans. Each moved passage leaves a pointer of 3–25
lines that keeps the genre's own sentences:

| Skill | Now | After part B | Passages moved |
| --- | ---: | ---: | --- |
| survey-writer | 769 | ~475 | corpus, collection, figure, critique, render, prose, verbatim |
| tutorial-writer | 771 | ~455 | same |
| textbook-chapter-writer | 720 | ~405 | same |
| thesis-chapter-writer | 732 | ~400 | same; its LaTeX figure marker keeps more |
| deep-research | 867 | ~735 | corpus, Phase 7 render, prose, verbatim, critique core |
| draft-reviser | 841 | ~780 | prose, verbatim, render rider |
| agenda-reviser | 543 | ~515 | verbatim; its prose section is its own and mostly stays |
| corpus-reviser | 263 | ~225 | prose, verbatim |
| book-assembler | 611 | 611 | none |
| figure-drawer | 200 | ~202 | none; gains the thesis sentence from Task 2 step 3 |
| **all ten** | **6,317** | **~4,800** | |

New files, each held once:

| File | Lines (approx.) |
| --- | ---: |
| `skills-common/references/critique.md` | 100 |
| `skills-common/references/figure-handoff.md` | 70 |
| `skills-common/references/collection-scoping.md` | 60 |
| `skills-common/references/render-and-references.md` | 45 |
| `skills-common/references/verbatim-scan.md` | 35 |
| `skills-common/references/prose-check.md` | 30 |
| `skills-common/references/corpus-read-only.md` | 15 |
| `skills/deep-research/references/report.md` (moved) | 218 |
| `skills/figure-drawer/references/figures.md` (moved) | ~201 |

Across the three trees the skill text goes from ~20,200 lines to
~15,200, about 25% less. **The per-run context saving is small, by
design.** A survey run reads the five always-used references, ~225
lines, so it loads ~700 lines rather than 769. A run that also uses
collections and a figure loads ~830, slightly *more* than today because
of the pointers. Part C is where the context saving is.

### Part C: per-skill references and assets (the main context saving)

Each skill below is one task, and each follows Task 4's five steps.
Within a skill, a reference's file name is the mode or topic it covers.

| Task | Skill | Moves to | Test retargeted |
| --- | --- | --- | --- |
| 10 | draft-reviser | `references/copy-edit.md` (493–567), `references/acronyms.md` (568–610), `references/re-grounding.md` (611–760), `references/whole-corpus.md` (761–802) | `tests/test_skill_figure_step.py`'s three draft-reviser headings stay in `SKILL.md`, so it is unchanged. `tests/test_skill_acronym_step.py` is unchanged too, because it covers the genres only |
| 11 | agenda-reviser | `references/classes.md` (66–109), `references/repairs.md` (165–290) | `tests/test_review_agenda.py:1644`: find `stale_spans` / "refused as stale" / "R12" wherever they land, `SKILL.md` or reference |
| 12 | book-assembler | `references/latex-conventions.md` (32–275 minus the skeleton), `assets/book-skeleton.tex` (53–90, as a real `.tex` file) | `tests/test_skill_book_assembly.py`: the skeleton strings are asserted on the asset, the conventions phrases on the reference, and the commands and "Do not say the book is finished" on `SKILL.md` |
| 13 | deep-research | `references/depth-presets.md` (235–244). Split `references/report.md` by section if it reads better; optional | none |
| 14 | corpus-reviser | delete the rules copied from draft-reviser (121–240) and point at the part B references and at draft-reviser's new references | none (check with `grep -l corpus-reviser tests/`) |

Each mode reference opens with the condition that sends the model to it.
For example: "Read this only when the request is a copy-edit that touches
no evidence." `SKILL.md`'s "When to invoke" table names the file in the
row for that mode, so the routing decision never leaves `SKILL.md`.

**Part C is done when** the local checks pass. Expected lengths after
part C, from the same simulation as part B's table:

| Skill | After part B | After part C |
| --- | ---: | ---: |
| draft-reviser | ~780 | ~470 |
| book-assembler | 611 | ~370 |
| agenda-reviser | ~515 | ~345 |
| corpus-reviser | ~225 | ~155 |
| deep-research | ~735 | ~725 |
| **all ten** | **~4,800** | **~4,000** |

Text shared between skills ends at about 17% of words, down from 32%.
The extra lines held in the second and third harness copies end at
about 7,960, down from about 13,480.

### Part D: every skill on every harness, on this machine

#### Task 15: check that each harness loads and follows the new layout

The unit tests prove the files exist and the paths resolve. They cannot
prove that a harness *loads* the right `SKILL.md`, lets its model read a
`.claude/...` path from a Codex or OpenCode skill, or that a model
actually follows a pointer at the step that names it. This task checks
both, on this machine, against projects scaffolded from this branch. It
runs in addition to DEVELOPER-AGENTS.md's local-check list, not instead
of it.

**Files:**

- Create: `bench/bench_skill_harnesses.py`. `bench/` sits outside every
  check by design, as a measurement harness; see DEVELOPER-AGENTS.md.
- Modify: `docs/HARNESS.md`, to record what was measured and when.

**Setup:**

1. Scaffold one project per harness from this checkout:
   `chitragupta init $WORK/<harness> --agent <claude|codex|opencode>`.
   Then copy in the fixture corpus that `docs/examples/{codex,opencode}/run.sh`
   uses, so `content/ledger.sqlite` is not empty.
2. Run `chitragupta doctor` in each project. It must report the OpenCode
   deny list as correct, and nothing new.

**Tier 1: loading. All 10 skills × 3 harnesses = 30 runs, with a
scripted stand-in model.** These runs need no API key and take minutes.
The bench script serves a fake model on `127.0.0.1` that answers with
scripted tool calls and logs what the harness hands back. Its setup is
the recipe already used for #903:

- **Codex:** `-c model_provider=fake` with `wire_api="responses"`, a
  real model name, and `--dangerously-bypass-approvals-and-sandbox` in
  the scratch directory. The user approved that flag for scratch-dir
  harness runs on 2026-10-02.
- **OpenCode:** an `@ai-sdk/openai-compatible` provider in
  `opencode.json`, run with `git` off `PATH` (the zombie-`git` stall).
- **Claude Code:** a real model, not the fake: `claude -p --model
  sonnet` (the user's choice, 2026-10-06). The prompt asks for the three
  turns below and nothing else: load the skill, read every file it
  names, print each file's first line. The assertions are taken from
  `--output-format stream-json`. Record the token cost in the test plan.

For each skill, the script drives three turns:

1. Load the skill the way that harness loads one:
   - Claude Code: `Skill` with the skill's name;
   - OpenCode: `skill` with `<name>-opencode`;
   - Codex: a `$<name>` mention, which injects the body.
2. Read every `.claude/skills…` path the loaded body names, with that
   harness's own read tool:
   - Claude Code: `Read`;
   - OpenCode: `read`;
   - Codex: `exec_command` with `cat`.
3. Finish with a text answer.

It then asserts, from the server's log:

- the body handed back is that harness's own `SKILL.md`. OpenCode's
  carries the suffix, and loading the unsuffixed name is denied by
  `.opencode/opencode.json`;
- every read returned the file's first line, never an error, a
  permission prompt or a "file not found";
- the set of paths read equals the set `tests/test_skill_references.py`
  extracts. A mismatch means the regex and the harness disagree about
  what a path is.

**Tier 2: following. Real models, two skills per harness.** Tier 1
proves the files can be read. Tier 2 checks that a model reads them at
the right step:

- **The skills:** `survey-writer` end to end on the fixture corpus, then
  `draft-reviser` in copy-edit mode on the draft that run produced. The
  copy-edit run exercises a part C mode reference.
- **The models:** Claude Code runs via `claude -p --model sonnet`.
  Codex and OpenCode run on the local Qwen at `127.0.0.1:18080`.
  - That server has one slot, so run the harnesses one at a time.
  - A survey takes about 40 minutes there.
  - If the server is down, restart it with
    `~/host-open-llm/project/scripts/server-ctl.sh start`.
- **What to check in each transcript:**
  - which reference files were read, and at which step;
  - whether the gate passed;
  - whether `finish`-tail reports were shown.
- **What to expect:**
  - every always-used reference is read at its step;
  - `collection-scoping.md` and `figure-handoff.md` are read only if
    the run used collections or drew a figure;
  - `copy-edit.md` is read by the reviser run;
  - no read of a path that does not exist.
- **Known limit, recorded rather than fixed:** behind llama.cpp, Codex is
  never offered `apply_patch`, so its gate hook does not fire. The gate
  is run as a command in the skill all the same.
- **The baseline** is the recorded run in `docs/examples/codex/` and
  `docs/examples/opencode/` from before this change. Compare the gate
  outcome and the dossier, not the prose, which differs run to run.

- [ ] **Step 1: write the bench script.** Use one entry per harness that
  holds the three things that differ: how to launch the harness, its
  load call and its read call. The 10 skills and their named paths come
  from `tests/test_skill_references.py`'s helpers, so the bench and the
  unit test cannot disagree about which files exist.
- [ ] **Step 2: run Tier 1 on `main`'s scaffold first.** The two
  existing `reference.md` files make this a non-empty baseline, and a
  failure here is the harness or the script, not this PR.
- [ ] **Step 3: run Tier 1 on this branch's scaffold.** Expect 30 of 30
  to pass. Fix the cause of any failure, not the bench, and rerun.
- [ ] **Step 4: run Tier 2, one harness at a time.**
- [ ] **Step 5: record the results.** Put a 30-row Tier 1 table and a
  6-row Tier 2 table (harness × skill: references read, gate outcome,
  wall time, token cost where known) in the PR's test plan. In
  `docs/HARNESS.md`, add the dated measured facts: each harness loads
  references on demand, and Codex and OpenCode read `.claude/` paths
  without a prompt.
- [ ] **Step 6: commit** the bench script and the docs change.

**PR 1 is done when** DEVELOPER-AGENTS.md's full local-check list passes
(the full suite with coverage, pylint under Python 3.13, ruff, both
markdown lints) and Task 15's two tiers pass on this machine. The test
plan carries both line-count tables and both harness tables.

---

## PR 2: scripts for the fixed tails (optional; can be declined)

PR 2 wraps exactly two sequences: the review tail and the critique
cycle. Nothing else qualifies:

- **The gate stays a `SKILL.md` command**, because acting on its failure
  is judgement.
- **book-assembler's `pdflatex`/`bibtex` passes are not chitragupta
  verbs**, so they fall outside the "documented CLI calls" rule.
- **Preflight is not wrapped**, because the empty-ledger branch is a
  decision that differs by genre.

### Task 16: `finish.py`, the review tail

**Files:**

- Create: `.claude/skills-common/scripts/finish.py`
- Create: `tests/test_skill_scripts.py`

**Interfaces:**

- Produces: `finish.steps(draft: str, stamp: str) -> list`, a list of
  `(module_args: tuple[str, ...], allowed_exits: frozenset[int])` pairs,
  `finish.main(argv: list[str] | None = None) -> int`
- CLI: `python .claude/skills-common/scripts/finish.py <draft> [--stamp {last,first,never}]`
  - genres: `last`
  - draft-reviser and corpus-reviser: `first`
  - agenda-reviser: `never`

- [ ] **Step 0: confirm the exit codes before encoding them.** Check each
  one in `docs/CLI.md`:
  - `draft style` "exits 0 whatever it finds";
  - `dossier sections` exits 1 on a missing dossier, and the genres say
    "scan anyway";
  - `verbatim scan` "exits 0 either way";
  - `dossier stamp` (`:1156`).

  If any of these differs from the `allowed` sets below, the docs win.
  Correct the set and say so in the commit.

- [ ] **Step 1: write the failing tests:**

```python
"""The skill scripts run documented commands in a fixed order (#997).

Loaded from their path, as a harness runs them: they live under
`.claude/skills-common/scripts/`, outside every package.
"""

import importlib.util
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".claude" / "skills-common" / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ran(monkeypatch):
    calls = []

    def fake(argv, check):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1 if "sections" in argv else 0)

    monkeypatch.setattr(subprocess, "run", fake)
    return calls


def modules(calls):
    return [tuple(argv[3:5]) for argv in calls]


@pytest.mark.parametrize(
    "stamp, order",
    [
        ("last", ["style", "sections", "scan", "stamp"]),
        ("first", ["stamp", "style", "sections", "scan"]),
        ("never", ["style", "sections", "scan"]),
    ],
)
def test_finish_runs_the_tail_in_order(ran, stamp, order):
    finish = load("finish")
    assert finish.main(["content/drafts/x.md", "--stamp", stamp]) == 0
    assert [next(w for w in argv[4:] if w in order) for argv in ran] == order
    assert all(argv[:3] == [sys.executable, "-P", "-m"] for argv in ran)


def test_a_missing_dossier_still_scans(ran):
    load("finish").main(["content/drafts/x.md"])
    assert any("scan" in argv for argv in ran)


def test_an_unexpected_exit_is_reported_but_the_rest_still_runs(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda argv, check: calls.append(argv) or subprocess.CompletedProcess(argv, 3))
    assert load("finish").main(["d.md"]) == 1
    assert len(calls) == 4


def test_a_path_with_spaces_is_one_argument(ran):
    load("finish").main(["content/drafts/my draft.md"])
    assert all("content/drafts/my draft.md" in argv for argv in ran)


def test_a_missing_install_exits_2_and_names_the_doc(monkeypatch, capsys):
    finish = load("finish")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert finish.main(["d.md"]) == 2
    assert "Which interpreter" in capsys.readouterr().err


def test_run_as_a_script(ran, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["finish.py", "d.md"])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPTS / "finish.py"), run_name="__main__")
    assert exited.value.code == 0
```

- [ ] **Step 2: run `pytest tests/test_skill_scripts.py -v`.** Expect a
  FAIL, because the file does not exist yet.

- [ ] **Step 3: write the script:**

```python
"""Run a draft's closing review tail: prose check, section map, verbatim scan, stamp.

Each step is a `python -m chitragupta.<layer>` command documented in
docs/CLI.md, and this file only fixes their order. Every command is
echoed before it runs and its exit status after, so the transcript shows
exactly what ran and the model reads every report as it would have.
None of these steps is a gate: an expected non-zero exit (a draft with
no dossier yet) is reported and the tail carries on; any other exit is
reported, the tail still carries on so no report is lost, and the script
exits 1.
"""

import argparse
import importlib.util
import subprocess
import sys

NO_INSTALL = (
    "chitragupta is not importable by {exe}. Run this script with the interpreter "
    "chitragupta is installed in; docs/CLI.md, 'Which interpreter', says which."
)


def steps(draft: str, stamp: str) -> list:
    """`[(module_args, allowed_exits), ...]` in the order they run."""
    tail = [
        (("chitragupta.draft", "style", draft), frozenset({0})),
        (("chitragupta.draft", "dossier", "sections", draft, "--citekeys", "--write"), frozenset({0, 1})),
        (("chitragupta.review", "verbatim", "scan", draft), frozenset({0})),
    ]
    stamped = (("chitragupta.draft", "dossier", "stamp", draft), frozenset({0}))
    return {"first": [stamped, *tail], "last": [*tail, stamped], "never": tail}[stamp]


def run(module_args: tuple, allowed: frozenset) -> bool:
    print("$ python -P -m " + " ".join(module_args), flush=True)
    code = subprocess.run([sys.executable, "-P", "-m", *module_args], check=False).returncode
    print(f"[exit {code}]", flush=True)
    return code in allowed


def main(argv: "list | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("draft")
    parser.add_argument("--stamp", choices=("last", "first", "never"), default="last")
    args = parser.parse_args(argv)
    if importlib.util.find_spec("chitragupta") is None:
        print(NO_INSTALL.format(exe=sys.executable), file=sys.stderr)
        return 2
    results = [run(module_args, allowed) for module_args, allowed in steps(args.draft, args.stamp)]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: run `pytest tests/test_skill_scripts.py -v`.** Expect a
  PASS.

- [ ] **Step 5: bring the scripts directory under every code check.** The
  directory is the same everywhere: `.claude/skills-common/scripts`.

| Check | File and line | Change |
| --- | --- | --- |
| coverage `source` | `pyproject.toml:341` and `coveragerc-windows.toml:18` | add it to both; `test_coverage_configs_agree.py` pins them together |
| pylint and `ruff check` | `.github/workflows/ci.yml:483,493` and DEVELOPER-AGENTS.md's local command | add it as a root |
| `ruff format --check` | `ci.yml:505` | add it as a root |
| C1 and C2 | `STATEMENT_ROOTS` and `CODE_LINE_ROOTS` in `scripts/code_standards.py:57-58` | add it; regenerate `code-standards-register.toml` if the tool asks |
| code-standards hook | `WATCHED_ROOTS` in `.claude/hooks/code_standards_hook.py:77` | add it |
| bare-launch scan | `_scanned()` in `tests/test_bare_launch_scan.py:184` | add it. `sys.executable` passes this scan as written |
| bare no-cover pragma scan | `tests/test_coverage_configs_agree.py:108` | add it |

  Then run the full suite with coverage, and pylint under Python 3.13
  as CI does.

- [ ] **Step 6: commit.**

### Task 17: `critique.py`, and the rule against a third interface

**Files:**

- Create: `.claude/skills-common/scripts/critique.py`
- Modify: `tests/test_skill_scripts.py`, `docs/CLI.md` ("Which
  interpreter" and a new short "Skill scripts" subsection)

**Interfaces:**

- `python .claude/skills-common/scripts/critique.py baseline <draft>` runs:
  1. `dossier status`
  2. `dossier sections --citekeys --write` (exit 1 allowed)
  3. `review verbatim scan --write --json`
  4. `draft style --json`
- `python .claude/skills-common/scripts/critique.py recheck <draft> --baseline <path>`
  runs:
  1. `draft gate`
  2. `review verbatim recheck --baseline <path> --json`
  3. `draft style --json`

  The script exits with the **gate's** exit code, so a failing gate
  still reads as a failure. The other two always run.
- Produces: `critique.steps(mode: str, draft: str, baseline: str | None)`,
  which has the same shape as `finish.steps`, and the same `run()` and
  `main()` contract.

Copy `finish.py`'s `run()` into this script. Do not import it, because
the scripts must stay runnable by path with no package. That makes two
copies of a three-line function, and C1 and C2 both allow it.

- [ ] **Step 1: write the failing tests.** Follow Task 16's pattern:
  - assert the baseline order;
  - assert the recheck order;
  - assert that a gate exit of 1 makes `main` return 1 while recheck and
    style still run.

  Then add the guard test that stops scripts becoming a third interface:

```python
def test_every_script_command_is_documented():
    cli = (REPO_ROOT / "docs" / "CLI.md").read_text(encoding="utf-8")
    sequences = [*load("finish").steps("d.md", "last"), *load("critique").steps("baseline", "d.md", None),
                 *load("critique").steps("recheck", "d.md", "b.json")]
    for module_args, _ in sequences:
        words = [w for w in module_args[1:] if not w.startswith("-") and w not in {"d.md", "b.json"}]
        assert " ".join(words) in cli or f"{module_args[0]} {words[0]}" in cli, module_args
```

- [ ] **Step 2: run them and see them fail. Step 3: write the script.
  Step 4: run them and see them pass.**
- [ ] **Step 5: update `docs/CLI.md`.** Add a subsection, "Skill scripts
  are not a third interface", that says:
  - each script under `.claude/skills-common/scripts/` is an ordered list
    of the commands above;
  - each script echoes every command before running it;
  - a person never needs to run one;
  - `tests/test_skill_scripts.py` keeps every command a script runs
    named in this file.

  In "Which interpreter", add one sentence on the `find_spec` check and
  exit 2.
- [ ] **Step 6: commit.**

### Task 18: point the skills at the scripts

**Files:** every skill that carries the tail or the critique cycle,
across the three trees, plus `tests/test_skill_verbatim_scan_step.py`,
`tests/test_skill_style_check_step.py` and
`tests/test_skill_pregate_feedback_step.py`.

- [ ] **Step 1: retarget the step tests.** The ordering assertions
  (`sections` then `scan`, and `verbatim scan` < `gate` < `verbatim
  recheck`) are now owned by `tests/test_skill_scripts.py`. Delete them
  from the text scans. The text scans instead assert three things in
  each skill's `SKILL.md`:
  - it names `finish.py` with the right `--stamp`;
  - the 5 genres name `critique.py baseline` and `critique.py recheck`;
  - the part B reference pointers are still present.
- [ ] **Step 2: replace the literal blocks in `SKILL.md`** with one
  command each. For a genre, that is:

```bash
python .claude/skills-common/scripts/finish.py content/drafts/<slug>.md
```

  Keep the instruction around it: "Show what it found… lead with the
  `long` and `short` buckets" is now in the reference, and "then present"
  stays in `SKILL.md`.

- [ ] **Step 3: run the full suite, with coverage and both markdown
  lints.** Then commit.

**PR 2 is done when** the local checks pass and Task 15's bench passes
again on this branch. Add one Tier 1 turn per harness that runs
`finish.py` through that harness's own shell tool, and rerun Tier 2's
`survey-writer` on all three harnesses. This proves that each harness
runs the `.claude` script with an interpreter that can import
`chitragupta`.

---

## Self-review against the issue

| Issue success criterion | Where |
| --- | --- |
| Every genre skill follows the four-part layout, and `SKILL.md` holds only workflow and judgement | PR 1 (layout, shared references, per-skill references and assets), PR 2 (scripts). A skill with no scripts or assets has no empty folders: YAGNI, and the spec makes them optional |
| Each script is a sequence of documented CLI calls, with a test that runs it | Tasks 16–17, plus `test_every_script_command_is_documented` |
| Harness copies share whatever is harness-independent, and the test covers the rest | Task 1: one physical copy, `test_only_skill_md_is_kept_per_harness`, and the neutral-file test |
| `chitragupta init` scaffolds the new layout, with a documented upgrade path | Task 3 (init test for all three agents, HOOKS.md upgrade commands) |
| Coverage stays at 100% | Task 16 step 5 |
| No citekey generated, no new gate | Global constraints. Scripts never stop on a review aid, and the gate stays in `SKILL.md` |

| Issue open question | Where answered |
| --- | --- |
| A second interface | Task 17 (`docs/CLI.md` subsection plus the guard test) |
| Trust, and hook issue 890 | Measured table, and Task 3 step 4 |
| Interpreter resolution | Task 16 (`find_spec`, exit 2, `-P` children) |
| Tests that read skill text | Tasks 4–9, 10–14 (each retargets its own test), and Task 18 (ordering moves to the script tests) |
| Harness support | Measured table: all three load on demand. Task 15 re-measures it on this machine, for every skill |
