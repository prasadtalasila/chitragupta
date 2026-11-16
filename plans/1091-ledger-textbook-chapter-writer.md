# Move ledger: textbook-chapter-writer (#1199, SK-2)

Status: **built on `feat-1091-textbook-writer`, above the 12,000 target,
which the owner's 2026-11-14 answer allows.** Written 2026-11-15 against
`feat-1091-critique-pointer` (`40c8e507`, 6.173.5), for
[plans/1091-skill-shrink.md](1091-skill-shrink.md) PR 2, Task 2, in the
shape of [the survey-writer ledger](1091-ledger-survey-writer.md).

**Written for** the reviewer of PR 2, and whoever joins the three SK-2
branches. **Assumed:** the plan's "Decisions" and "Review focus", and
[docs/HARNESS.md](../docs/HARNESS.md) on the three `SKILL.md` copies.

Every paragraph removed from textbook-chapter-writer's `SKILL.md` has
one row below: its first words, then where it went (file and section)
or "cut" with the reason. A row with no destination is a defect. Line
references are to the old `.claude` copy at `40c8e507`; the `.agents`
and `.opencode` copies held the same paragraphs, differing only where
`tests/fixtures/skill_harness_phrases.toml` says, and changed the same
way.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/textbook-chapter-writer/SKILL.md` | 32,215 | 15,062 |
| `.agents/skills/textbook-chapter-writer/SKILL.md` | 32,230 | 15,077 |
| `.opencode/skills/textbook-chapter-writer-opencode/SKILL.md` | 32,386 | 15,197 |

The cap in `tests/test_skill_size.py` falls from 33,000 to 16,000, with
its reason. **It stays above the 12,000 target**, which the owner
answered on 2026-11-14 is a guideline: nothing is compressed to fit.
What the 15 KB holds that survey-writer's 13 KB does not, measured on
the `.claude` copy:

- 1,170 bytes of frontmatter and title, which Decision 7 leaves alone
  (survey's is 1,075);
- one more step (19, 0 to 18: textbook merges nothing, plan Task 5),
  each with its `Done when`;
- the steps an optional-citation genre adds: the empty-ledger question
  in place of a refusal, and "skip if the chapter cites nothing" on
  steps 11 to 13, each with its alternative `Done when`;
- the genre's own markers and judgement: the exercise label, step 4's
  section-unit floor with the single-source marker, the
  "reading or doing?" routing question, and the
  `mathematical-prose.md` pointer `tests/test_skill_references.py`
  pins;
- two retrieval fences in step 3 (declared and free), which survey also
  carries, and the figure stub `tests/test_skill_figure_step.py`
  requires (about 1,500 bytes).

## Pinned phrases: what the tests read

Built before the rewrite. "Raw" means the test reads `SKILL.md` as
written (whitespace collapsed at most), so the phrase cannot move into a
reference. "Expanded" means it reads `tests/skill_text.py`'s
`expanded()`. Every phrase below is present after the rewrite; the suite
is green on it.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_references.py` | "from the project root" no later than 250 characters after the first `.claude/skills…` path, all three copies | raw |
| `test_skill_references.py` | a `## Collection scoping` section naming `` `.claude/skills-common/references/collection-scoping.md` `` and "ledger --collections" | raw |
| `test_skill_references.py` | "Read `.claude/skills-common/references/mathematical-prose.md` now", all three copies (`_MATH_PROSE_GENRES`) | raw |
| `test_skill_references.py` | every named path exists; the three copies cite the same `` `path` §N `` set; every cited section exists; every `## N.` of a reference is cited; no reference left unnamed | raw |
| `test_skill_references.py` | no backticked skill name and no tool word in any reference, `textbook.md` included | the references |
| `test_skill_harness_copies.py` | `critique_edit_tool`: "each edit with `Edit`" and its two forms; the OpenCode copy suffixes every backticked skill name | raw, all copies |
| `test_skill_figure_step.py` | "No citekey inside either figure file", `<!-- figure: figures/<name> -->`, `` `figure-drawer` ``, "kpsewhich tikz.sty", "compiles", "redrawn from a source" | raw |
| `test_skill_figure_step.py` | absent: the six `_RIDERS` | raw |
| `test_skill_table_step.py` | `<!-- table:`, `<!-- tableref:`, "§13" | raw |
| `test_skill_acronym_step.py` | "acronyms.toml" or "acronym vocabulary" | raw |
| `test_skill_pregate_feedback_step.py` | now in `_POINTER_FORM`: the step names `critique.md` within 2,000 characters of "Critique against the evidence packet", says "not done until the loop the reference describes has run", ends on a `Done when`, and names no `-m chitragupta` command | raw |
| `test_skill_pregate_feedback_step.py` | every rider ("evidence.md", "claim:", "at most three items", "no second critique pass", the command order, "objective_delta", "90% of its own", "revisions.md", "Never write any of this to `rejected.md`", "`no evidence`", "cut the sentence", "never to re-point it", "declared queries are exhausted", "dossier status", "there is no declared list", "never a condition of presenting") in the step plus the whole reference | raw step plus reference |
| `test_skill_style_check_step.py` | the `prose-check.md` pointer within 1,400 characters after some `draft style`; "§9 marks decidable" and "fix none of them" within 1,400 after every one | raw; expanded |
| `test_skill_verbatim_scan_step.py` | the `verbatim-scan.md` pointer within 1,200 after some scan; the caveat within 2,000 after every scan; the section-map regeneration within 200 before the scan; "tiers_not_run"; "never a condition of presenting"; absent "Offer the verbatim scan" | raw; expanded |
| `test_skill_retrieval_logging.py` | `--log` within 220 characters of every `retrieve search` | raw, references too |
| `test_skill_size.py` | each copy at or under the cap; cap within 1,000 of the largest copy; a reason when above 12,000 | raw |
| `test_init.py` | `python -m chitragupta.draft` in the scaffolded copy | raw |
| `bench/skill_commands.py` `expected_commands` | the 21 commands below | raw, named files too |

No citation sits inside steps 11, 16 or 17 (the critique, the prose
check and the verbatim scan), so no spliced reference pushes a rider out
of its window (review focus 1).

**Expected commands, before and after** (`bench/skill_commands.py`, each
harness's copy, the files it names, and `figure-drawer` by handoff).
The set is unchanged on all three harnesses, 21 each: `dossier status`
and `verbatim recheck` now come from `critique.md`, which the step names.

```text
corpus ledger, draft dossier export, draft dossier init,
draft dossier outline, draft dossier sections, draft dossier stamp,
draft dossier status, draft evidence, draft figures, draft gate,
draft references, draft render, draft retrieve search, draft style,
figure check, figure look, figure new, figure sync, review synthesis,
review verbatim recheck, review verbatim scan
```

## Where each removed paragraph went

`genre-steps.md` is `.claude/skills-common/references/genre-steps.md`;
`textbook.md` is
`.claude/skills/textbook-chapter-writer/references/textbook.md`;
`genres/textbook-chapter.md` is
`docs/writing-standards/genres/textbook-chapter.md`.

### Header, corpus layer, collection scoping, dossier

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "Genre-specific drafting agent for undergraduate textbook-chapter output" | cut: restates the layer split `docs/ARCHITECTURE.md` states; a one-sentence summary of what the skill drafts replaces it |
| 12 | "Its register is teaching, not persuading a reviewer" | `genres/textbook-chapter.md`, "What a textbook chapter owes its reader"; the routing it implies stays in "When to invoke" |
| 20 | "Shared corpus layer (read, don't regenerate)" (heading) | cut: the heading of the three bullets below |
| 22 | "`content/ledger.sqlite` -- per-citekey status" | `genre-steps.md` §1 |
| 23 | "`content/parsed/<citekey>.txt` -- extracted PDF text, useful for pulling a real worked example" | `genre-steps.md` §1; "useful for a worked example" cut, since step 5 says to construct examples for the course level rather than lift them |
| 25 | "`chitragupta/retrieval.py` -- `search(query, k, snippet_chars)`" | `genre-steps.md` §1; "citing the result is still optional" stays in step 3 |
| 29 | "**Read-only means read-only: never run `python -m chitragupta.corpus sync`" | the rule and both commands stay ("Before you start"); the write lock, the run time and "do not build an index" go to `genre-steps.md` §1 |
| 39 | "If `python -m chitragupta.corpus ledger` reports an empty ledger, say so before you start" | stays, with its command, under "Before you start"; the step says `genre-steps.md` §1's empty-ledger paragraph does not apply here (see "For the integrator") |
| 46 | "Citations here are optional, not the point. Don't force them in." | cut: duplicate of step 3's "cite only if attributing it helps the student" and `textbook.md` §1, "Finding a good example does not oblige a citation" |
| 48 | "Collection scoping (#195): draft from the shelf, not the library" (heading) | stays as "Collection scoping"; "(#195)" cut as history (Decision 4) |
| 50 | "At step 0, before any retrieval, check whether the library is sorted" and its fence | stays |
| 57 | "Paths in this skill are from the project root" | stays, moved to the opening paragraph, before the first path |
| 60 | "If it reports none, say nothing, ask nothing" | stays |
| 68 | "The dossier: write down what produced the draft" (heading) | cut: the heading of the paragraphs below |
| 70 | "The chapter is only half of what this run produces" | `genre-steps.md` §2 (the shared half); the teaching judgement it lists (prior knowledge, worked example chosen) goes to `textbook.md` §4 |
| 77 | "`chitragupta/dossier/` owns that state" | `genre-steps.md` §2 |
| 83 | "What the dossier is worth here is not what it is worth in the citation-dense genres" | `textbook.md` §4, "The weight sits in `scope.md` and `rejected.md`" and "A source worth recording gets the full block" |
| 93 | "and in `rejected.md`, which in this genre records **pedagogical** rejects" | `textbook.md` §4 |
| 100 | "None of this depends on citing anything. **A chapter that carries no citations at all still gets a dossier**" | the rule stays in step 0 ("A chapter that will carry no citations still gets a dossier"); the reasoning goes to `textbook.md` §4 |

### When to invoke, prose standards, audience

| Old line | First words | Went to |
| --- | --- | --- |
| 108 | table row "User asks for a textbook chapter / course reader" | cut: the frontmatter description routes it (plan, PR 1 Task 3) |
| 111–114 | table rows naming `tutorial-writer`, `survey-writer`, `thesis-chapter-writer`, `draft-reviser` | stays, as one sentence under "When to invoke" naming the four |
| 116 | "If the request is genuinely ambiguous ... ask one question" | stays: it routes to another skill, so it cannot move to a reference |
| 118 | "Don't guess -- the two genres have opposite rules about explanation" | "Don't guess" stays; the reason goes to `genres/textbook-chapter.md`, "What a textbook chapter owes its reader" |
| 124 | "`docs/WRITING-STANDARDS.md` holds the cross-genre rules" | stays as one sentence, now naming `genres/textbook-chapter.md` beside it |
| 125 | "Read `.claude/skills-common/references/mathematical-prose.md` now and follow it" | stays verbatim (`tests/test_skill_references.py`) |
| 129 | "Where this genre departs from `tutorial-writer`: explanation is welcome" | `genres/textbook-chapter.md`, "What a textbook chapter owes its reader" |
| 133 | "## Audience first" (heading) and "Before drafting anything, write down" | `genres/textbook-chapter.md`, "Audience first"; step 0's `Done when` names the reader and what they already know |
| 140 | "Then check yourself against the **curse of knowledge**" | `genres/textbook-chapter.md`, "Audience first"; the four defect words are cut as a duplicate of `docs/WRITING-STANDARDS.md` §2, which lists them, and the genre file points there |

### Steps 0–4

| Old line | First words | Went to |
| --- | --- | --- |
| 150 | "0. **Name the reader and the scope, and open the dossier.** Before drafting and before any retrieval" | title and command stay; "settle who ... and what they already know" stays in the `Done when`; the rest goes to `genre-steps.md` §3 |
| 159 | "**Settle `<slug>` with the user before running that.**" | `genre-steps.md` §3, with the generic `<topic>/<genre>.<ext>` example; "Settle `<slug>` with the user" stays |
| 169 | "Fill in `scope.md`'s **Reader**, **Covers**, **Does not cover** and **Glossary**" | `genre-steps.md` §3; the glossary's value for this genre goes to `textbook.md` §4 |
| 173 | "Settle the **dialect** with the reader in the same breath" | `genre-steps.md` §3; "the course's own institution decides it" cut, the general rule there covers it |
| 176 | "Read the acronym vocabulary too" | `genre-steps.md` §3; "the acronym vocabulary" stays in step 0's pointer |
| 180 | "Where a ledger is present, `init` also stamps the corpus fingerprint" | `genre-steps.md` §3; "Do this even if the chapter will carry no citations" stays in step 0 |
| 184 | "1. **Establish the learning objectives** first -- 3-5 concrete" | title, the count, "observable verb" and "drop anything that serves none" stay; the verbs and why go to `textbook.md` §1 |
| 189 | "2. **State scope and prerequisites** near the top" | title and the three things stay; why goes to `textbook.md` §1 |
| 194 | "3. **Motivation: establish the need before the mechanism.** A short section on why" | title stays; the paragraph goes to `textbook.md` §1 |
| 200 | "If the dossier has an `outline.md` ... with declared `queries:`" | the `--check` command, "declared queries verbatim", `--origin extended` and "a `claim:` block is a steer" stay; the rest is `genre-steps.md` §4, whose last sentence already says it for a genre where citing is optional. A fence for the declared search, with `--origin declared`, is added in the shape of survey-writer's step 1: the old text named the flag only in prose |
| 211 | "Otherwise, if you search the synced corpus for a motivating example" and its fence | stays |
| 218 | "`--log` records the query in the dossier's `retrieval.md`. **Pass it on every call**" | "Pass `--log` on every call" stays; why goes to `textbook.md` §1 and `genre-steps.md` §1 |
| 221 | "Then read each 500-character snippet yourself rather than trusting the score, and reformulate" | `textbook.md` §1; the step points at `genre-steps.md` §6 for a thin search |
| 225 | "**Whether to cite at all stays optional here, unlike the other skills.**" | "Cite a result ... only if attributing it helps the student" stays; the rest goes to `textbook.md` §1 |
| 231 | "Anything you do cite still must be a real citekey from a `search()` result" | `textbook.md` §1; step 12's title says it too |
| 234 | "4. **Diversify sources within a section -- the unit here is the section**" | stays: title, "don't write a multi-source paragraph", the floor, the single-source marker, §11 and `review synthesis` |
| 239 | "Spread alone is not enough -- three paragraphs on one paper" | cut: duplicate of `docs/WRITING-STANDARDS.md` §11, "For the section unit, spread is not enough" |
| 248 | "The rest of this step is how you get there." | `textbook.md` §2; "before reusing the same citekey a third time within one section, do one more search pass" stays as the step's judgement sentence, which `chitragupta/review/synthesis.py` quotes |

### Steps 5–9

| Old line | First words | Went to |
| --- | --- | --- |
| 263 | "5. **Worked example(s), then faded ones.** Concrete, step-by-step" | title and the three judgements (show the reasoning, construct for the course level, fade) stay in one sentence; the detail goes to `textbook.md` §3 |
| 268 | "Prefer originally-constructed examples suited to the target course level" | `textbook.md` §3 |
| 270 | "Where the chapter has room for more than one, **fade the support**" | `textbook.md` §3 |
| 275 | "6. **Exercises.** Include a mix of difficulty, label each one" | the label, "those three grades only", solutions or hints, the objective mapping and the `rejected.md` row stay; "the grade is not a defect marker" goes to `textbook.md` §3 (also `docs/WRITING-STANDARDS.md` §2); "exercise the objectives, not recall" to `textbook.md` §3 |
| 282 | "Note each cut in the dossier's `rejected.md`" | stays, with the abandoned worked example; why goes to `textbook.md` §4 |
| 287 | "Wherever a step above puts a table in the chapter" | the three markers and §13 stay, citing `docs/writing-standards/tables.md` §13; "Never write the number" cut as a duplicate of `tables.md` §13; "a student meeting a table with no lead-in" goes to `textbook.md` §3 |
| 297 | "7. **Add a figure, if a worked example or concept earns one.**" | title stays; placement and rarity go to `genres/textbook-chapter.md`, "Figures: common, and earned one at a time" |
| 302 | "A figure you considered and dropped is a `rejected.md` row" | stays |
| 306 | "A figure that stays is a **pair of files**, and §10 is the contract" | stays, citing `docs/writing-standards/figures.md` §10, with its fence |
| 314 | "Write both `content/drafts/<topic>/figures/<name>.tex`" | the pair stays; how the renderer swaps the marker per format is cut as a duplicate of `figures.md` §10, "Every figure has two forms" |
| 322 | "Hand the drawing itself to `figure-drawer`" | stays; the list of what the drawer owns is cut as a duplicate of `figure-drawer`'s own `SKILL.md` |
| 328 | "**A topic directory is required.**" | stays; where flat-draft figures land goes to `genre-steps.md` §3 |
| 333 | "**Check for TikZ, and that the figure compiles.**" | stays |
| 340 | "**No citekey inside either figure file.** Step 12's gate reads the draft" | the guardrail stays; why goes to `genres/textbook-chapter.md`, "Figures" |
| 344 | "**Nothing redrawn from a source.** ... the textbook diagram everyone in the field already knows" | the guardrail stays; the textbook-diagram temptation goes to `genres/textbook-chapter.md`, "Figures" |
| 349 | "**A caption, if the figure earns one, goes in the draft**" | the caption line and `figureref` marker stay; no number, no word "Figure" and `FigureNoCaption` (#421) are cut as a duplicate of `figures.md` §10 |
| 357 | "**Equations follow `docs/WRITING-STANDARDS.md` §12 ... more of them than any other here.**" | the pointer stays, now to `docs/writing-standards/mathematics.md` §12, with the `math.md` row and the `<!-- math -->` marker; "more than any other", the bare-code-span warning and why go to `genres/textbook-chapter.md`, "Mathematics"; the code-span, untagged-fence and matrix rules are cut as a duplicate of §12 |
| 369 | "**This genre also has more of §12's numbered equations than any other**" | the two markers stay; when to number goes to `genres/textbook-chapter.md`, "Mathematics"; "Never write 'Equation 3'" and `EquationUnreferenced` are cut as a duplicate of `mathematics.md` §12, "A number for a chosen few" |
| 385 | "8. **Close the loop.**" | stays |
| 389 | "9. **Read it once as the student.**" | title stays; the checklist and "catches more real problems than any other single step" go to `genres/textbook-chapter.md`, "The reread" |

### Steps 10–18, house style and Sources

| Old line | First words | Went to |
| --- | --- | --- |
| 394 | "10. **Map the chapter's sections.**" and its fence | stays |
| 401 | "so a later revision can find the section that owns a change" | `genre-steps.md` §2 ("The section map is derived"); "skips fenced code" cut as a restatement of `dossier sections --help`; "A chapter with no citations still gets this map" stays |
| 407 | "11. **Critique against the evidence packet, before gating.** Skip this entirely if the chapter has no citations" | stays: the title, the skip condition and the listing paragraph |
| 415 | "This is one inline judgement call, not a subagent dispatch" | stays; "nothing in this pipeline scores this automatically" is in `critique.md` step 2 |
| 418 | "**Run this step: it is never a condition of presenting, but it is not done until you have run its commands.**" | "never a condition of presenting" stays; the rest becomes "not done until the loop the reference describes has run" |
| 419 | "Read `.claude/skills-common/references/critique.md` now, before listing anything, and work it through" | stays, as "follow it with `content/drafts/<slug>.md` as `<draft>`"; "In outline:" cut, since the step no longer outlines the loop |
| 424 | "1. Where the dossier has an `outline.md`" and its `dossier status` fence | `critique.md` step 1, which already held both |
| 431 | "2. Take the baseline" and its three-command fence | `critique.md` step 3, which already held them |
| 439 | "If the scan's `tiers_not_run` is not empty, quote the reason" | `critique.md` step 3; the step asks for the reason back |
| 445 | "3. Repair at most three items, each edit with `Edit`" | `critique.md` step 4; "each edit with `Edit`" stays as "make each edit with `Edit`" (`critique_edit_tool`); "at most three repairs" stays |
| 449 | the `gate`, `verbatim recheck` and `style` fence | `critique.md` step 4, substep 3 |
| 456 | "Read `style`'s count only as a number" | `critique.md` step 4, substep 3 |
| 459 | "4. Log every attempt, kept or reverted, in the dossier's `revisions.md`" | `critique.md` step 4, substep 5; the step keeps "each checked and logged in the dossier's `revisions.md`" |
| 461 | "If nothing on the list clears the bar, or the list was empty, say so" | `critique.md` step 6; the step's `Done when` keeps it |
| 463 | "12. **Never write a citekey you didn't get from `search()`.**" and the gate fence | stays |
| 470 | "Fix and re-run until `OK` before presenting. If there are no citations" | stays |
| 473 | "13. **Build the References section.**" | stays, with its `--heading` clause and skip condition |
| 478 | "14. **Render tex, pdf and md, then the evidence sidecar** -- and expect" | stays: the formats, "pdf only", and "expect it to be thin or absent" |
| 484 | "**This chapter emits one when it has anything to show, which is often not.**" | `textbook.md` §5 |
| 493 | "**That is the right outcome, not a gap to fill.** Do not go back and add a `quote:`" | "the right outcome" and the deliberate-quotation case go to `textbook.md` §5; "Do not go back and add a `quote:`" is cut as a duplicate of `render-and-references.md` §3 ("Never add a `quote:` after the fact to populate it"), which the step points at |
| 497 | "15. **Record any steering.**" | stays, with two of its four examples; the other two and why pedagogical steering undoes quietly go to `textbook.md` §4; why steering is recorded at all is `genre-steps.md` §2 |
| 505 | "16. **Run the prose check.**" | stays; "what the check can and cannot see, and how to report" cut as a description of `prose-check.md`, which the pointer reaches |
| 517 | "Read the acronym findings rather than skipping them" | stays |
| 519 | "17. **Run the verbatim scan.**" and its fence | stays |
| 527 | "The first command is not optional: a section map written earlier" | "not optional" stays, as "not a repeat of step 10"; the reason is cut as a duplicate of `verbatim-scan.md`, "Why the section map is rebuilt first" |
| 530 | "It matters most in the connective prose between worked examples" | stays, with "never a condition of presenting" |
| 534 | "Read `.claude/skills-common/references/verbatim-scan.md` now and follow it" | stays; "what to show, what the scan could not check" cut as a description of that file |
| 538 | "18. **Stamp the draft fingerprint, then present.** Nothing edits the chapter's text" | stays, now pointing at `genre-steps.md` §7 first; why goes there; "(#454)" cut as history |
| 546 | "Then **present the draft** plus a short note on what it assumes" | the textbook note stays ("prior knowledge, what it leaves out, where a student goes next"); the render outcome, the dossier's location and gitignore go to `genre-steps.md` §7; the `draft-reviser` handoff and `dossier export` stay |
| 555 | "## House style for this genre" and "Beyond `docs/WRITING-STANDARDS.md` §4" | `genres/textbook-chapter.md`, "House style for this genre" |
| 559 | "Prefer a concrete instance over an abstract statement" | `genres/textbook-chapter.md`, "House style for this genre" |
| 562 | "Notation follows the mathematical-prose reference" | `genres/textbook-chapter.md`, "House style for this genre"; the pointer itself stays in "Prose standards" |
| 565 | "## Sources" and "The principles in this file are not original" | the link stays, in "Prose standards"; the per-work summary is cut as a duplicate of `docs/WRITING-STANDARDS.md`, "Sources and attribution", whose "Supplies" lines name what each of the four works (Wilson, the Carpentries, BCcampus, Wilkes) gives this skill |

### Totals

- **99 rows**, one per paragraph, list item, table row group or fence
  of the old file.
- **Stay: 33 rows** keep their text in `SKILL.md`, whole or as the
  step's one judgement sentence (a title, a command, a guardrail, a
  marker the tests read, or a routing sentence); some of them also move
  their detail out.
- **Moved: 63 rows** send text to `genre-steps.md` (21), `textbook.md`
  (23), `genres/textbook-chapter.md` (15) or `critique.md` (8); a row
  may name two files.
- **Cut: 24 rows** cut some or all of their text, each with its reason:
  a duplicate of a named file and section, a restatement of `--help`, a
  description of a reference the pointer reaches, or history (an issue
  number). 6 of them move nothing elsewhere.
- **Without a destination: none.**

### What was added, not moved

Each step gained a one-line `Done when` (Decision 4), and each pointer
a condition for reading it. Step 3 gained a fence for the declared
search, which the old step named only in prose. Step 11 gained "it runs
once the draft is written and before step 12's gate" and "Come back
with", from survey-writer's pointer step. `textbook.md`'s and
`genres/textbook-chapter.md`'s opening paragraphs are new, in the shape
of their survey counterparts. Nothing else in the two new files is new
text: each sentence there is one of the rows above.

## The critique step, in pointer form

Done as `feat-1091-critique-pointer` did for survey-writer: the step
keeps its number (11), title and listing paragraph; says when it runs,
including the textbook-only skip when the chapter cites nothing; points
at `critique.md`; names the edit tool; carries "not done until the loop
the reference describes has run"; says what to come back with; and ends
on a `Done when`. `tests/test_skill_pregate_feedback_step.py`'s
`_POINTER_FORM` gains `textbook-chapter-writer`. `critique.md` is not
edited.

## The bench

Claude Code only, skill-only, `PYTHONPATH` unset, each run capped at
3600 seconds. Rows in
`bench/results/2026-11-15-textbook-chapter-writer-shrink/`. `before.json`
holds the 3 textbook rows of
`bench/results/2026-11-14-skill-bench-skill-only/tier2.json` (runs 1-3)
and 3 new runs scaffolded from `origin/main` at `18adc5e9`, whose
textbook skill and shared references are byte-identical to this
branch's base (runs 4-6). `after.json` holds 6 runs of this branch.

The first 3-against-3 `--compare` exited 3 (inconclusive), on one-run
drops in `draft dossier status` and `figure sync`. As the rule says, 3
more runs of each arm were made, before arm first, then after. **At 6
against 6, `--compare` exits 0 (pass).** No run reported an HTTP 429
error, and none timed out.

| Command or row | Before | After |
| --- | ---: | ---: |
| Gate passed | 6 | 6 |
| `draft dossier outline` | 0 | 4 |
| `review synthesis` | 4 | 5 |
| `draft dossier status` | 6 | 4 |
| `review verbatim recheck` (as the scorer counts it) | 6 | 4 |
| `figure sync` | 1 | 0 |
| Median run | 605 s | 519 s |

Every other command row is equal (6 against 6, or 0 against 0 for
`draft dossier export` and `draft figures`).

**Counted by hand, after arm, out of 6:**

- the dossier's `revisions.md` has a critique entry: 6;
- the baseline `review verbatim scan --write` ran before the first
  `review verbatim recheck`: 5, in every run that rechecked. The scorer
  counts 4, because one run called the recheck from a script it had
  written with a heredoc, which the scorer does not read as a command.
  The sixth run listed three gaps, found that they were omissions in
  `evidence.md` rather than overclaims in the prose, made no prose edit,
  and so had nothing to recheck; its `revisions.md` says so;
- opened `critique.md`, `genre-steps.md` and `textbook.md`: 6, 6 and 6.
  Every run also opened `mathematical-prose.md`, `render-and-references.md`,
  `verbatim-scan.md` and `prose-check.md`.

**`draft dossier status`, 6 to 4, is the expected conditional row.**
The task gives the dossier no `outline.md`, so the loop runs the command
only to read an outline that is not there. Where it ran, it ran at the
baseline (2 runs) or at the end (2 runs). Of the 2 runs that skipped it,
one wrote "no outline" in its critique entry and one wrote nothing about
the outline; 4 of the 6 entries record that there was no outline. Per
the brief, the commands were not put back inline.

## Docs whose claims this moved

- `chitragupta/review/synthesis.py`: its comment quotes step 4's
  "before reusing the same citekey a third time within one section, do
  one more search() pass"; the step now says "search pass", and the
  quote follows it.
- `chitragupta/review/_units.py` (step 4 "says not to let one citekey
  carry a whole section") and `docs/WRITING-STANDARDS.md` §11 (step 4's
  interleaving instruction): still true, since step 4 keeps the floor;
  unchanged.
- `docs/PROMPTS.md` and `docs/diagrams/prompts-single-context.mmd` ("the
  full 19-step process (0-18)"): still true, since textbook merges no
  step; unchanged.
- `docs/WRITING-STANDARDS.md`'s Wilkes paragraph says the skill reads
  `mathematical-prose.md` "for a maths-heavy chapter", while the skill
  has read it on every run since before this branch (#1135). Not made
  false here, so unchanged; noted for the plan.

## For the integrator

Procedure this skill repeats that `genre-steps.md` does not yet hold,
and that tutorial-writer repeats too. Kept inline here; join it into the
shared file when the three branches meet.

1. **An empty ledger in a genre where citing is optional** (the
   tutorial branch found the same thing).
   `genre-steps.md` §1's last paragraph says an empty ledger stops the
   run; textbook-chapter-writer and tutorial-writer ask instead, so this
   skill's "Before you start" says that paragraph does not apply. A
   sentence for §1, in the shape of §4's last one:

   ```markdown
   In a genre where citing is optional, an empty ledger does not stop
   the run: say so before you start, since the draft will carry no
   citations, and ask whether to proceed uncited or to sync first. Wait
   for the answer.
   ```

2. **A draft with no citations.** Both skills skip the critique, the
   gate and the References section when the draft cites nothing, and
   both say such a draft still gets a dossier and a section map. A
   sentence for §2:

   ```markdown
   A draft that cites nothing still gets a dossier and a section map:
   the reader, the scope, the glossary and the rejected candidates are
   what a revision needs, whether or not a single citation exists.
   ```

## For the plan

`plans/1091-skill-shrink.md` is not edited on this branch. What it
should say:

- **PR 2, Task 2:** the genre file is
  `docs/writing-standards/genres/textbook-chapter.md`, named by
  `dossier init --genre textbook-chapter`, not `genres/textbook.md`.
  The coordination bullet with #1128 can go: the epic is unstarted, so
  there was nothing to rebase onto, and no `exercise-types.md` exists.
- **PR 2, Task 5, Step 1:** textbook-chapter-writer is above 12,000
  (15,197 in its largest copy) with its cap at 16,000 and a reason, as
  the owner's 2026-11-14 answer allows.
- **PR 2, Task 5, Step 2:** of the four sites it names for this skill,
  only `chitragupta/review/synthesis.py` changed; see "Docs whose
  claims this moved" above.
