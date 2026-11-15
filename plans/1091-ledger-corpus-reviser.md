# Move ledger: corpus-reviser (#1204, SK-7)

Status: **built on `feat-1091-corpus-reviser`, which branches from
`feat-1091-draft-reviser` (SK-4, not yet merged); above the 8,000
target, with a reason in its cap row.** Written 2026-11-15 against
`cc8856ac` (6.173.8), for [plans/1091-skill-shrink.md](1091-skill-shrink.md),
the PR 7 row of "PRs 3-8, in outline".

**Written for** the reviewer of PR 7. **Assumed:** the plan's
"Decisions" and "Review focus";
[plans/1091-ledger-survey-writer.md](1091-ledger-survey-writer.md), whose
shape this follows; and
[plans/1091-ledger-draft-reviser.md](1091-ledger-draft-reviser.md), "For
SK-5 and SK-7", which lists what of draft-reviser this skill may rely on.

Every paragraph removed from corpus-reviser's `SKILL.md` has one row
below: its first words, then where it went (file and section) or "cut"
with the reason. A row with no destination is a defect. Line references
are to the old `.claude` copy at `cc8856ac`; the `.agents` and
`.opencode` copies held the same paragraphs, differing only where
`tests/fixtures/skill_harness_phrases.toml` says, and changed the same
way.

## What it relies on in draft-reviser

Only what "For SK-5 and SK-7" lists, all of it still true on this
branch: the path `<harness>/skills/draft-reviser/SKILL.md`, the heading
`## The loop`, steps 1 to 7 by number (step 3's `dossier sections`, step
4's search decision, step 5's `Edit` rule, step 6's `revisions.md`
`Sections:` line and `math.md`, step 7's gate and stamp), the mode name
"re-grounding mode" and "copy-edit mode", and
`.claude/skills/draft-reviser/references/draft-diff.md`. It does **not**
rely on draft-reviser's `## Prose standards` or `## Collection scoping`,
which that list does not name, so the figure, table, equation and
collection rules a wide pass needs stay in this file.

## Who cites this skill's text

Grepped over all three harness folders, `docs/`, `bench/`,
`chitragupta/`, `tests/` and `plans/`.

| Site | What it cites | After |
| --- | --- | --- |
| `plans/1091-ledger-draft-reviser.md:30-34` | the path, `## The loop`, "steps 1 through 7", "Step 3 becomes a whole-draft read", "Step 4 stops being a decision", "re-grounding mode", "copy-edit mode", `draft-diff.md` | all kept |
| `plans/1091-ledger-draft-reviser.md:32`, `:77` | "`draft-reviser`'s numbered steps 1-7 do not reach its unnumbered riders" | reworded: the loop now says "Then run this skill's own three closing steps". The fact it relied on (draft-reviser's three unnumbered steps sit outside 1-7) is unchanged; that ledger is SK-4's record and is not edited here |
| `bench/skill_bench_tasks.py:390` | the task's prompt only | unaffected |
| `tests/test_skill_style_check_step.py:57-61` | a comment: the furthest prose-check rider, 1,273 characters, in this skill | the window now holds with more room (the pointer follows the command directly) |
| `tests/test_skill_size.py:44` | the cap | lowered, with a reason |
| `docs/GENRE.md`, `docs/DRAFT-ITERATION.md`, `docs/ARCHITECTURE.md`, `docs/ZOTERO.md:69`, `docs/WRITING-PROCESS.md:98` | what the skill does, not its words | still true |

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/corpus-reviser/SKILL.md` | 12,762 | 10,088 |
| `.agents/skills/corpus-reviser/SKILL.md` | 12,789 | 10,117 |
| `.opencode/skills/corpus-reviser-opencode/SKILL.md` | 12,917 | 10,216 |

The cap in `tests/test_skill_size.py` falls from 13,000 to 11,000, with
its reason. **It stays above the 8,000 target**, and no further real
duplicate is left to take out. What the 10 KB holds, `.claude` copy:

- 1,050 bytes of frontmatter and title (Decision 7);
- about 1,200 bytes of fenced commands (Decision 2): the search fence
  and the three closing steps' commands, which the prose-check and
  verbatim-scan tests read from this file;
- the routing table (about 1,000 bytes), which the brief keeps;
- the guardrails, each paired with its positive target (about 1,800);
- the cost statement, the collection widening and the two step
  differences, which are what this skill *is*;
- about 700 bytes of project-root paths in the nine citations.

## No `references/` folder

Nothing left in `SKILL.md` is reached by only some runs and lacks a
shared home: the figure, table and equation rules already point at
`figures-tables-equations.md`, scoring at `genre-steps.md` §5, the
closing steps at their own references, and the rationale at
`docs/DRAFT-ITERATION.md`. The skill stays without a `references/`
folder.

## `mathematical-prose.md`: cited, with a condition

**Decision: cite it.** A wide pass edits the draft in its own genre, and
the old text already said it touches mathematics: "a wide rewrite
rewords more quantities than a scoped one" (old `:151-153`), pointing at
`figures-tables-equations.md` §6 for `math.md`. In a textbook or thesis
chapter the sentences around a reworded symbol are governed by the same
reference the chapter writers read. draft-reviser cites it from its
Prose standards, which this skill does not follow (above), so it is
cited here, on the same condition as there: "when the pass adds or
rewords a symbol, a condition or a derivation, read ... before writing
it" (in the step 6 bullet). `tests/test_skill_references.py` pins
"Read ... now" for the chapter genres only, and the reference holds no
command, so nothing else changed.

## The stale step reference

Old `:118`, "Score what you keep the way `survey-writer` step 2
describes", has been false since PR 1 (#1215): that procedure is
`.claude/skills-common/references/genre-steps.md` §5 ("Judging a
candidate and recording it"). It now reads "Before recording what you
kept and what you turned down, read
`.claude/skills-common/references/genre-steps.md` §5", draft-reviser's
step 4 wording. No other reference to another skill's step number was
in the file: the rest cite draft-reviser's steps 1-7, 3, 4 and its
modes, all still true (above).

## Pinned phrases: what the tests read

"Raw" means the test reads `SKILL.md` as written (whitespace collapsed
at most); "expanded" means `tests/skill_text.py`'s `expanded()`. Every
phrase is still present; the suite is green on it.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_references.py` | "from the project root" no later than 250 characters after the first `.claude/skills…` path (now before it, in the opening) | raw |
| `test_skill_references.py` | every named path exists; the three copies cite the same `` `path` §N `` set (`genre-steps.md` §5, `figures-tables-equations.md` §1-§6) | raw |
| `test_skill_references.py` | `test_only_skill_md_is_kept_per_harness`: no `references/` folder needed | files |
| `test_skill_harness_copies.py` | `skill_path_draft_reviser`, `edit_never_write_bold` ("- **`Edit`, never `Write`.**", used by no other skill, so the bullet keeps it) | raw, all copies |
| `test_skill_harness_copies.py` | OpenCode copy: every backticked skill name suffixed `-opencode` | raw |
| `test_skill_style_check_step.py` | the `prose-check.md` pointer within 1,400 characters after `-m chitragupta.draft style`; "§9 marks decidable" and "fix none of them" within 1,400 | raw / expanded |
| `test_skill_verbatim_scan_step.py` | the `verbatim-scan.md` pointer within 1,200 after the scan; `dossier sections … --citekeys --write` then the scan within 200; "tiers_not_run" and "genuine restatement is only detected where the embedding tier can run" within 2,000; "never a condition of presenting" | raw / expanded |
| `test_skill_retrieval_logging.py` | `--log` within 220 characters of every `retrieve search\|evidence` | raw |
| `test_skill_pregate_feedback_step.py` | listed as a skill without the critique step | expanded |
| `test_skill_size.py` | each copy under the cap; cap within 1,000 of the largest copy; a reason above 8,000 | raw |
| `bench/skill_commands.py` `expected_commands` | the 16 commands below | raw, references too |

**Expected commands, before and after**, all three harnesses, 16 each,
the same set (only `draft dossier stamp`'s position moved, as it now
comes from draft-reviser's step 7 rather than this file):

```text
draft gate, draft dossier sections, draft retrieve search,
draft retrieve evidence, draft style, review verbatim scan, draft diff,
draft figures, draft dossier status, draft dossier prune,
draft dossier mark-revision, draft references, draft render,
draft dossier stamp, draft dossier snapshot, draft dossier versions
```

The two new citations (`genre-steps.md`, `mathematical-prose.md`) hold
no command, so the set did not grow. No citation was placed inside the
prose-check or verbatim-scan steps but their own pointers (review focus
1).

## Where each removed paragraph went

`fte.md` is `.claude/skills-common/references/figures-tables-equations.md`.

### Opening and When to invoke

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "`draft-reviser` reads the dossier instead of the corpus" | one sentence stays, as the opening ("`draft-reviser`'s loop, with a search of every sub-theme…"); "an economy rather than a rule… This skill is the way out of it" cut as a duplicate of `docs/DRAFT-ITERATION.md` ("The scoped default, and the way out of it"), now cited with its condition (when the user asks why) |
| 14 | "It exists as a separate skill so the choice is yours" | cut: a duplicate of `docs/DRAFT-ITERATION.md` ("Why a separate skill and not a mode") and `docs/GENRE.md` ("Revising widely"), reached by the same citation |
| 21 | "**What this is not is a re-run of the genre skill.**" | "keeps all of that and spends tokens only on what is genuinely unknown" and the list of what the dossier holds stay in the opening; the rule and its reason go to `## Guardrails` ("Never re-run the genre skill"), which already said it |
| — | (new) "Paths in this skill are from the project root" | moved up from old `:87` to the opening, before the first path |
| 30 | the When-to-invoke table | stays, unchanged (routing) |
| 40 | "That last row is not modesty." | moved to `## Guardrails`, first bullet, as its positive target ("When unsure, use `draft-reviser` and say so…") |
| 44 | "**Read-only over the corpus layer**, exactly as everywhere else." | the rule and both commands stay in `## Guardrails`, with the reason (write lock, tens of minutes, the user's to run); the separate paragraph was a duplicate of that guardrail and of `genre-steps.md` §1 |

### Collection scoping

| Old line | First words | Went to |
| --- | --- | --- |
| 51 | "## Collection scoping (#195): inherit it, do not re-ask" | renamed `## Collection scoping: say you are widening it`: "(#195)" cut as history; "inherit it, do not re-ask" was draft-reviser's rule, which this skill's own section then overrode. No file cited the heading; the fence comment cites "Collection scoping", which still matches |
| 53 | "`scope.md` may carry a `collection:` line" | the first clause stays; "every retrieval call in this pass carries the same `--collection`" cut: it is draft-reviser's rule, and this skill's searches carry none (old `:66`, `:112`) |
| 57 | "This matters more here than it does at drafting time." | one sentence stays (the shelf-to-library change nothing in the diff shows); "(#254)" and "nothing in `retrieval.md` records that the scope moved" cut as history |
| 63 | "A missing line, or `- collection: (whole corpus)`" | stays, as a clause; "exactly as this skill behaved before this section existed" cut as history |
| 66 | "**This skill is the one exception.**" | stays: no `--collection`, name the collection in the cost sentence (which now says so too), record the widening in `revisions.md` (also in the step 6 bullet), leave the `collection:` line |

### Cost

| Old line | First words | Went to |
| --- | --- | --- |
| 74 | "One sentence, before the first search, and let them stop you." | stays; gains the collection clause from old `:66` |
| 81 | "If the ledger is empty or absent, stop and say so" | stays |
| — | (new) "Done when the user has the cost sentence" | added (Decision 4) |

### The loop

| Old line | First words | Went to |
| --- | --- | --- |
| 87 | "Paths in this skill are from the project root" | moved to the opening |
| 90 | "Follow `.claude/skills/draft-reviser/SKILL.md`'s `## The loop`, steps 1 through 7" | stays (the routing sentence, `skill_path_draft_reviser`); "It is the same scope check, the same edit discipline, the same dossier write-back and the same exit" cut as restating draft-reviser's step titles; "Then run this skill's own three closing steps" added, replacing old `:173`'s aside |
| 95 | "**Step 3 becomes a whole-draft read.**" | stays, with a `Done when` |
| 100 | "**Step 4 stops being a decision.**" | stays |
| 104 | "Take the sub-themes from `retrieval.md`'s recorded queries" | stays; "which is the case for any draft written before `--log` was passed" cut as history ("where it records none" says the same) |
| 110 | the search fence | stays, unchanged |
| 116 | "`evidence` stays optional and stays for deepening an acceptance" | one sentence stays; "Score what you keep the way `survey-writer` step 2 describes, and record both outcomes: kept into `evidence.md`, turned down into `rejected.md`" becomes a citation of `genre-steps.md` §5 (see "The stale step reference"); the `support:` sentence stays, shortened ("the conservative reading" cut as a duplicate of draft-reviser step 4) |
| — | (new) "Done when every sub-theme has had its search" | added |

### What does not relax

| Old line | First words | Went to |
| --- | --- | --- |
| 124 | "## What does not relax" + "The cost is the only thing this skill changes." | heading and intro cut: the loop's "unchanged except for the two steps below" says it; the bullets that were differences now sit under "Steps 5 to 7 hold as written, and three of their rules bind harder here" |
| 130 | "**`rejected.md` is still consulted first, and still honoured.**" | moved into step 4's difference, whole (step 4 is replaced, so its `rejected.md` check must be stated here); the guardrail bullet gains "re-open a rejection only by saying which and why" |
| 136 | "**Every call carries `--log`.**" | cut: a duplicate of `genre-steps.md` §1 ("Every retrieval call logs to the draft"), and the fence carries `--log` on both lines; step 4's `Done when` says "each with `--log`" |
| 139 | "**`Edit`, never `Write`.**" | stays (harness phrase `edit_never_write_bold`), first sentence and "most sections survive a re-check untouched"; "costs thousands of output tokens to produce a diff nobody can review" cut as a duplicate of draft-reviser step 5 |
| 143 | "**Never write a citekey** that isn't already in the draft" | moved to `## Guardrails`; "A fabricated citekey is the one failure this whole pipeline exists to prevent" cut as a duplicate of draft-reviser step 5 and CLAUDE.md; "a long run is exactly where the temptation shows up" stays |
| 147 | "**The dossier is written back**" | the file list cut as a duplicate of draft-reviser step 6; what differs stays: the `revisions.md` entry says the pass was wide and why (and, from old `:70`, names any collection searched past), `Sections:` names every section touched, `math.md` with `fte.md` §6. Gains the conditional `mathematical-prose.md` citation |
| 154 | "**Figures, tables and equations follow the same rules as in `draft-reviser`.**" | stays, as "When the pass touches a figure, a table or an equation", with `fte.md` §1-§5; "Tables, captioned figures and numbered equations renumber themselves" shortened to "Only ids matter", which is `fte.md` §3-§5's rule |
| 164 | "**The gate is the exit.**" | moved to `## Guardrails` (a guardrail the brief keeps); the gate itself is draft-reviser step 7 |
| 166 | "**Re-stamp the draft fingerprint once the gate passes**" + command | cut: a duplicate of draft-reviser step 7 ("Once the gate passes, and not before, re-stamp"), which this skill follows unchanged; the why is `genre-steps.md` §7. The prose check now opens "After step 7, and the stamp it ends on". `draft dossier stamp` stays expected through draft-reviser's `SKILL.md` |
| 171 | "**Run the prose check**" + command + pointer | stays, as `### Run the prose check` with a `Done when`; "`draft-reviser`'s numbered steps 1-7 do not reach its unnumbered riders, so this is written out here for the same reason the scan offer is" cut: replaced by the loop's "Then run this skill's own three closing steps", and "the scan offer" is history (#312). "**Fix none of the findings:**" cut as a duplicate of `prose-check.md` ("Report every finding and fix none of them"); the wide-pass reason and the copy-edit routing stay |
| 181 | "**Run the verbatim scan.**" + fence | stays, as `### Run the verbatim scan` with a `Done when` |
| 189 | "The first command is not optional." | the first sentence and the wide-pass reason stay; "the embedding tier compares each section against the citekeys that section's `sections.md` row records" cut as a duplicate of `verbatim-scan.md` ("Why the section map is rebuilt first") |
| 195 | "It earns its place after a wide pass in particular" | merged into the sentence above (its reason was the same "rewrites against sources the draft may never have cited"); the bold not-a-gate clause stays |
| 201 | "Read `.claude/skills-common/references/verbatim-scan.md` now" | stays; "what to show, what the scan could not check, and how to keep the report" cut as a description of the file |
| 205 | "**Show what changed, last** -- an unnumbered rider too" | stays, as `### Show what changed` with its command, pointer and a `Done when` |

### Guardrails and Sources

| Old line | First words | Went to |
| --- | --- | --- |
| 212 | "**Never invoke this skill on your own initiative.**" | stays; gains old `:40` as its positive target |
| 215 | "**Never re-run the genre skill.**" | stays; gains old `:21`'s reason |
| 217 | "**Never run `python -m chitragupta.corpus sync`…**" | stays; gains old `:44`'s reason |
| 218 | "**Never treat a wide search as permission to re-judge `rejected.md`.**" | stays; gains "Honour it, and re-open a rejection only by saying which and why" |
| 219 | "**Never silently change scope, reader or terminology.**" | stays; gains its positive target (only as agreed in step 2, recorded in `scope.md`) |
| 220 | "**Report what the pass actually changed**" | stays, unchanged |
| 225 | "## Sources" | cut as a heading |
| 227 | "The prose standards this skill inherits are documented" | cut: draft-reviser's Prose standards carries the same attribution link, and this skill states no prose rule of its own |
| 230 | "The reasoning for why the scoped default exists" | the `docs/DRAFT-ITERATION.md` pointer moved to the opening, with its condition |

### Totals

- **44 rows** for the old file, one per paragraph, list item, table or
  fence (a row may cover adjacent items that went the same way), plus 3
  rows marked "(new)" for text added.
- **Stay, whole or shortened in place, with nothing cut or moved: 15.**
- **Moved: 11 rows** send text to another part of `SKILL.md` (the
  opening, step 4, `## Guardrails`) or behind a citation
  (`genre-steps.md` §5, `docs/DRAFT-ITERATION.md`).
- **Cut: 23 rows** cut some of their text, each with its reason: a
  duplicate of draft-reviser steps 5-7, of `genre-steps.md` §1 or §7, of
  `prose-check.md` or `verbatim-scan.md`, of `docs/DRAFT-ITERATION.md`,
  or history (an issue number, "before `--log` was passed", "before this
  section existed"). Five rows are both moved and cut.
- **Without a destination: none.**

### What was added, not moved

A `Done when` line on the cost statement, steps 3 and 4 and the three
closing steps (Decision 4); a conditional citation of
`mathematical-prose.md` and of `genre-steps.md` §5; a condition on the
`docs/DRAFT-ITERATION.md` pointer; and a positive target on the
guardrails that lacked one. No reference file changed, and none was
created.

## The bench

See the commit that records it, and the section below once filled.

## For the plan

- PR 7's row: the 8,000 target is not reached without compressing
  prose; real deduplication stops at about 10.1 KB (the cap is 11,000,
  with a reason). The rest is the routing table, the guardrails, the
  closing steps' commands and the two step differences.
- corpus-reviser keeps no `references/` folder (above).
- `mathematical-prose.md`: decided, cited behind a condition (above).
- `docs/GENRE.md` ("Revising widely") and `docs/DRAFT-ITERATION.md` say
  the wide pass re-searches "every sub-theme in `sections.md`"; the skill
  takes `retrieval.md`'s recorded queries first and falls back to
  `sections.md`'s headings. That predates this PR and is left as is.
