# A size budget for every skill, and the rest of #997

Status: **built in PR #1106 (6.156.0)**, rebased onto #1107 on the way.
Written 2026-11-02 against
`104b9eb` (6.155.0), for issues
[997](https://github.com/prasadtalasila/chitragupta/issues/997),
[1091](https://github.com/prasadtalasila/chitragupta/issues/1091),
[1067](https://github.com/prasadtalasila/chitragupta/issues/1067) and
[1068](https://github.com/prasadtalasila/chitragupta/issues/1068).
[1069](https://github.com/prasadtalasila/chitragupta/issues/1069) (PR 2's
scripts) was declined and closed on 2026-10-30; the reasons are on the
issue.

**Written for** whoever reviews or extends this PR. **Assumed:**
[plans/997-skill-directory-layout.md](997-skill-directory-layout.md) for
the layout (`SKILL.md` per harness, everything else once under
`.claude/`), and [docs/HARNESS.md](../docs/HARNESS.md) for why there are
three copies.

**Not covered here:** shrinking any skill to its #1091 target. That is
one later PR per skill, each lowering its own cap. This PR builds the
budget and finishes #997; it moves only the passages named below.

## What was measured first

PR #1039 recorded that a step reduced to "read `critique.md` and follow it"
was skipped once by Claude Code, and #1068 made that the gate on moving
any step's commands into a reference. It was re-measured on 2026-10-30
to 11-02, for the render step only.

- **The probe.** survey-writer's steps 12 and 13 (`draft references`,
  `draft render`, `draft evidence`) were cut to a pointer at a new
  `render-and-references.md`, with no command left in `SKILL.md`. The
  task prompt was the bench's Tier 2 survey with its "then render" clause
  removed, so only the skill could make the model run those commands.
- **Models.** Claude Code ran Sonnet; Codex 0.159.3 and OpenCode
  1.18.34 ran Qwen3.6-35B-A3B `UD-Q4_K_M` on llama-server b11321 (CPU,
  one slot, 131,072-token context).

| Harness | Runs per arm | Commands inline (baseline) | Pointer only |
| --- | ---: | --- | --- |
| Claude Code | 3 | all three steps, 3 of 3 | reference opened and all three steps run, 3 of 3 |
| Codex | 1 | **skipped `draft references`**; rendered md only | reference opened; references, tex, pdf, md and the sidecar |
| OpenCode | 1 | all three steps | reference opened; all three steps |

Every final draft passed the gate. No pointer-only step was skipped; the
one partial skip was a baseline with its commands inline. That is one
step and small samples, so it supports moving *this* step, not a general
rule; the critique loop keeps its inline commands until it is measured
the same way.

## What this PR builds

### 1. The budget test (#1091 item 1)

`tests/test_skill_size.py` holds one table:

```python
BUDGET = {  # skill: (cap in bytes, why the cap is above its target, or None)
    "figure-drawer": (7_000, None),
    "survey-writer": (<largest copy, rounded up>, "#1091: shrinks in its own PR"),
    ...
}
```

- It checks **all three copies** of each `SKILL.md` against the cap.
- **Targets:** 12,000 bytes for the four genre writers, 8,000 for every
  other skill. A cap above its target must carry a non-empty reason;
  that is #1091's "or its cap carries a recorded reason".
- **Slack:** a cap more than 1,000 bytes above the largest of its three
  copies fails, so a shrink must lower the cap in the same commit.
- **Coverage:** every skill in `tests/test_skill_harness_copies.SKILLS`
  has a row, and no row names a skill that does not exist.
- Each cap starts at the largest copy after this PR, rounded up to the
  next 1,000. figure-drawer's 8,000 moves here from
  `tests/test_skill_figure_router.py` and becomes 7,000, since its
  largest copy is 6,940 bytes (the OpenCode one).

Raising a cap cannot be detected statically; the reason column makes a
raise visible in review, and that is the whole enforcement.

### 2. The section-link test (#1091 item 4)

`tests/test_skill_figure_router.py`'s two link tests are generalised in
`tests/test_skill_references.py`, from figure-drawer to every reference
under `.claude/skills/*/references/` and
`.claude/skills-common/references/`, with the citation regex shared
between the two files rather than copied:

- every `## N.` section of a reference is cited (`` `path` §N``, or
  `§1, §3 and §4`) by at least one skill, so no section is orphaned;
- the three copies of one skill cite exactly the same sections, so a
  harness copy cannot silently lose one;
- every cited section exists.

Not "every skill that names the file cites every section": the thesis
writer names `render-and-references.md` but deliberately skips §1.
figure-drawer cites every section of its own references, so it keeps
its stricter test.

**This is red on today's tree, and the fix is part of the PR.**
deep-research's `references/report.md` has `## 1.` to `## 7.`, and its
`SKILL.md` cites §1, §3, §4, §5 and §7 but never §2 (the personas) or
§6 (the honesty rules). All three copies gain `§2` at Phase 1 and `§6`
under Guardrails.

A reference with no numbered sections is untouched by the test, so the
existing references need no renumbering. figure-drawer's router-shape
tests (taste gate, return, figure check) stay where they are.

### 3. `render-and-references.md` (#1068 Task 9)

`.claude/skills-common/references/render-and-references.md`, three
numbered sections:

1. **Build the References section**: the command, IEEE numbering, keep
   `[@citekey]`, `--heading "N. References"` for a manually numbered
   draft, and the heading names `render_output` recognises.
2. **Render**: the command per format, where the files land, the
   numbered md copy, and the `[missing-binary]`/`[error]` rule.
3. **The evidence sidecar**: the command per format, what it lists,
   `no quoted evidence recorded` as an expected answer, never adding a
   `quote:` after the fact.

Commands are written with `<draft>` for the draft's path. Each genre
keeps, in its own `SKILL.md` step, only what differs:

| Genre | Keeps in `SKILL.md` |
| --- | --- |
| survey-writer | §1-§3; formats tex, pdf, md; sidecar in pdf and md; why a survey emits one |
| textbook-chapter-writer | skip §1 when nothing is cited; sidecar pdf only, expected thin |
| tutorial-writer | skip §1 when nothing is cited; **no sidecar**, and why (kept whole) |
| thesis-chapter-writer | **not §1** (natbib fragment) and why; md and pdf previews from the `.tex`; the figure-error rule; sidecar pdf, and why it is safe |
| deep-research | `report.md` §5's template; formats tex, pdf, md; sidecar pdf and md; why it has the strongest claim |

The step numbers do not change, so no cross-reference ("not a repeat of
step 8") moves.

Two more skills carry render commands inline and are **not** pointed at
the reference in this PR: review-digest (a private digest, rendered
differently) and draft-reviser's step 7 (a re-render rider, not the
first build). The reference is shared by the five drafting genres only.

### 4. #1068's other two references: declined

- **Task 7, `corpus-read-only.md`.** The four genre copies differ, and
  the rule is "never run `sync`", which belongs in front of the model on
  every run. Declined; the passage stays inline.
- **Task 8, `figure-handoff.md`.** #1027 and #1048 already cut the genre
  stub to the decision and the handoff sentence, which names a skill and
  so must stay in `SKILL.md`. `tests/test_skill_figure_step.py`'s
  `test_every_stub_probes_for_tikz_and_guards_originality_itself`
  requires `kpsewhich tikz.sty`, "compiles" and "redrawn from a source"
  in each genre's own `SKILL.md`, on purpose: the stub must hold if the
  drawer is never loaded. A reference could hold only the caption rule.
  Declined.

### 5. #1067

- **Task 10, draft-reviser.** "When there is no dossier" moves to
  `.claude/skills/draft-reviser/references/no-dossier.md`, named in that
  section. "When a whole-corpus pass is what's wanted" **stays**: it is a
  routing decision that names `corpus-reviser`, and a reference may name
  no skill (`test_neutral_files_name_no_skill_or_tool`).
- **Task 12, book-assembler.** The skeleton becomes
  `.claude/skills/book-assembler/assets/book-skeleton.tex`, the first
  `assets/` in any skill. It is a **template, not a compilable file**:
  it opens with a `%` comment saying so, keeps the two placeholders as
  written today (`<the outline's own title>`, `<ask the user; never
  invent one>`), and marks `\input{preamble}` "only if the book has
  one" as today. `latex-conventions.md` names it where the skeleton was
  and says to copy it into `book.tex`, replacing each `<...>` and
  dropping the preamble line when there is no `preamble.tex`. Its
  `% see "X" below` comments become `see latex-conventions.md, "X"`.
  `tests/skill_text.py` splices only `references/*.md`, so the
  skeleton assertions in `tests/test_skill_book_assembly.py`
  (`secnumdepth`/`tocdepth`, `\input{preamble}`,
  `\input{chitragupta-floats}`) read the asset instead.
- **Task 14, corpus-reviser.** A new shared reference,
  `.claude/skills-common/references/figures-tables-equations.md`, holds
  the skill-free detail both revisers repeat: consulting a source
  figure, touching both forms of a figure, table, captioned-figure and
  equation ids, and `math.md` rows. Each section opens with its
  condition. What stays in **draft-reviser**'s `SKILL.md`, because a
  test or the no-skill-name rule needs it there: the genre bullet (it
  names five skills), "Touch a figure, touch both forms" and the
  `figure-drawer` handoff (`test_draft_reviser_hands_redrawing_to_the_drawer`),
  the `<!-- table: -->`/`<!-- tableref: -->` markers and §13
  (`tests/test_skill_table_step.py`), and the §12 equation markers. Each
  bullet keeps its rule in one or two sentences and cites the section
  for the rest. **corpus-reviser** replaces its four copied bullets with
  one that keeps its skill-naming lines (the "same rule as
  `draft-reviser`" pointer and "a `deep-research` draft gets none") and
  cites the reference; the rest of "What does not relax" (rejected.md,
  `--log`, Edit-not-Write, the citekey rule, dossier write-back, gate,
  stamp, the prose check and the verbatim scan's inline commands) stays.

Every new reference opens with the condition that sends a model to it,
uses project-root paths, and names no skill and no harness tool.

### 6. Docs and the bench

- `docs/HARNESS.md`: a new paragraph beside #1039's, in the same shape:
  date, models (Claude Code on Sonnet, 3 runs per arm; Codex and
  OpenCode on the local Qwen, 1 run per arm), the table, and what it
  does and does not show. The rule stays "move rationale and detail,
  keep the commands a step requires", with the render step as the one
  measured exception. The tree at the top of the Skills section and the
  "`references/` for one skill" sentence gain `assets/`.
- `docs/HOOKS.md`'s upgrade recipe and `docs/PACKAGING.md`: `assets/`
  now exists under a skill.
- `plans/997-skill-directory-layout.md`: status becomes "closed by this
  PR", task by task: 7 and 8 declined; 9 built; 10 partial
  (`no-dossier.md` built, `whole-corpus.md` declined as routing); 11's
  `classes.md` and 13's `depth-presets.md` not taken, with reasons; 12
  and 14 built. Its caution after Task 6 is updated, not deleted.
- `bench/bench_skill_harnesses.py`: Tier 2 also records which of the
  render-step commands a tool call ran, and gains `--skill-only` to drop
  the prompt's render clause, so the measurement above re-runs as
  written. (bench is outside coverage, per bench/README.md.)

## Order and checks

Each step is test-first: the new test fails, then the move makes it pass.

1. `test_skill_size.py` with today's caps; green.
2. The link test generalised; red on deep-research's §2 and §6, then
   green once they are cited.
3. `render-and-references.md` and the five genre steps; lower caps.
4. #1067's three moves; lower caps.
5. Docs, bench, version, changelog.

Then the full suite with coverage, `scripts/check_local.sh`
(markdownlint included), `ocr delegate`, and a Fable-model review.

**Version: MINOR (6.156.0).** No pipeline behaviour, CLI or output
format changes, which on its own would be a PATCH like PR #1093
(`4857f1a`, 6.148.1 to 6.148.2). The maintainer asked for a minor
release, so it also publishes to PyPI. 6.155.1 was taken by #1107 while
this PR was open.

## Done when

- [x] Every skill has a cap, every cap above target has a reason, and
      no cap has more than 1,000 bytes of slack.
- [x] Every numbered reference section is cited by some skill, the
      three copies of each skill cite the same sections, and every
      citation resolves.
- [x] The five render steps point at `render-and-references.md`, and
      each genre's own differences stay in its `SKILL.md`.
- [x] #1067: the skeleton asset (the first `assets/`) and
      corpus-reviser's shared rules are built; draft-reviser gets
      `no-dossier.md`, and `whole-corpus.md` is **declined** as routing.
      The close comment on #1067 says so.
- [x] docs/HARNESS.md records the measurement.
- [x] Coverage stays at 100%. No citekey is generated, guessed or
      rewritten, and no new check becomes a gate.
