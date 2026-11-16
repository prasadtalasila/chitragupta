# Move ledger: tutorial-writer (#1199, SK-2)

Status: **built on `feat-1091-tutorial-writer`, above the 12,000 target
(Decision 1 as answered on 2026-11-14: the cap is a guideline).**
Written 2026-11-15 against `b86f27f2` (6.173.5, the tip of
`feat-1091-critique-pointer`), for
[plans/1091-skill-shrink.md](1091-skill-shrink.md) PR 2, Task 1 Step 2
and Task 4.

**Written for** the reviewer of PR 2, and for whoever joins the three
SK-2 branches. **Assumed:** the plan's "Decisions" and "Review focus",
and [plans/1091-ledger-survey-writer.md](1091-ledger-survey-writer.md),
whose shape this follows.

Every paragraph removed from tutorial-writer's `SKILL.md` has one row
below: its first words, then where it went (file and section) or "cut"
with the reason. Line references are to the old `.claude` copy at
`b86f27f2`. The `.agents` and `.opencode` copies held the same
paragraphs, differing only where
`tests/fixtures/skill_harness_phrases.toml` says (`critique_edit_tool`)
and in OpenCode's `-opencode` suffixes, and changed the same way.

## What cites tutorial-writer's steps

Grepped over the whole repository before any edit
(`grep -rn -i "tutorial" | grep -i "step [0-9]"`, then by heading:
"What this genre is not", "Verified environment", "Rejected paths",
"Self-check", "Where to go next"). **No step was renumbered or
renamed**: tutorial merges nothing (plan, Task 5), so every citation
below still lands.

| Site | Cites | Changed |
| --- | --- | --- |
| `plans/1091-skill-shrink.md:1133`, `:1140`, `:1195` | step 9 (figure); `:361` "step 15" | no: the plan is not edited on this branch; both still hold |
| `plans/1027-figure-drawer-skill.md:548`, `:653` | step 9 | no: a merged plan, and step 9 is still the figure step |
| `plans/b2-multi-source-synthesis.md:319` | step 6, the document unit | no: still step 6 |
| `plans/951-reference-heading-grammar.md:157`, `:341` | step 14, the References heading | no: still step 14 |
| `plans/b5-pregate-self-feedback.md:249`, `:467` | step 12 as it was before the critique step existed | no: history |
| `docs/WRITING-STANDARDS.md:160` | the "What this genre is not" routing table | no: the table stays in `SKILL.md` under that heading |
| `docs/GENRE.md:627` | the table naming how-to and reference | no: unchanged |
| `docs/GENRE.md:195` | "the governing analogy in the skill" | **yes**: the analogy moved to `genres/tutorial.md`, which the sentence now links |
| `.claude/skills/draft-reviser/SKILL.md:302`, `:363` (and copies) | `scope.md`'s `## Verified environment` block | no: step 8 still writes it |
| `docs/WRITE-A-TUTORIAL.md:185-189` | `rejected.md`'s `## Rejected paths` section | no: step 2 still writes it |
| internal: steps 2, 5, 9, 12, 18, 19 | steps 3, 4, 6, 8, 11, 13, 15 | no: all still valid |

`docs/PROMPTS.md` cites no tutorial step: its only mention is a skill
name (`:107`), and `:76`'s "19-step" is textbook-chapter-writer's. The
plan's Task 5 list (`docs/WRITING-STANDARDS.md:561`,
`chitragupta/review/synthesis.py:48`, `chitragupta/review/_units.py:22`)
names textbook's step 4 only. Nothing there for this skill.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/tutorial-writer/SKILL.md` | 33,562 | 16,426 |
| `.agents/skills/tutorial-writer/SKILL.md` | 33,577 | 16,441 |
| `.opencode/skills/tutorial-writer-opencode/SKILL.md` | 33,724 | 16,561 |

New files: `.claude/skills/tutorial-writer/references/tutorial.md`
(seven sections) and `docs/writing-standards/genres/tutorial.md`.

The cap in `tests/test_skill_size.py` falls from 34,000 to 17,000, with
its reason. **It stays above the 12,000 target**, and nothing was
compressed to fit. What the 16 KB holds, on the `.claude` copy:

- about 1,100 bytes of frontmatter and title (Decision 7);
- the "What this genre is not" routing table, about 750 bytes, which
  names four skills and so cannot move into a reference, and which
  `docs/WRITING-STANDARDS.md` §5 cites by heading;
- about 1,900 bytes of fenced commands and the marker examples
  (Decision 2), across 19 steps;
- step 8, "Run it", about 1,700 bytes, kept whole by the brief: its
  instructions are the genre;
- step 9, the figure stub `tests/test_skill_figure_step.py` requires to
  hold without the drawer, about 2,300 bytes, plus the quantity and
  equation pointers;
- step 6, about 2,000 bytes: the only citing section, with its outline
  check, two retrieval paths, the `check-evidence` command and three
  conditional pointers;
- the critique step in pointer form, about 1,500 bytes, with this
  genre's skip condition and its "Where to go next" limit;
- project-root paths in 17 pointers, and a `Done when` on every step.

## Pinned phrases: what the tests read

"Raw" means the test reads `SKILL.md` as written (whitespace collapsed
at most); "expanded" means it reads `tests/skill_text.py`'s `expanded()`,
with each named reference spliced in. Every phrase is present after the
rewrite; the suite is green on it.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_references.py` | "from the project root" no later than 250 characters after the first `.claude/skills…` path, all three copies | raw |
| `test_skill_references.py` | a `## Collection scoping` section naming `` `.claude/skills-common/references/collection-scoping.md` `` and "ledger --collections" | raw |
| `test_skill_references.py` | every named `.claude/skills…` path exists; the three copies cite the same `` `path` §N `` set; every `## N.` of `tutorial.md` is cited | raw |
| `test_skill_references.py` | no backticked skill name and no tool word in `tutorial.md` (so §6 says "a textbook chapter", not the skill) | the reference |
| `test_skill_harness_copies.py` | `critique_edit_tool`: "each edit with `Edit`" and its two forms; OpenCode copy suffixes every backticked skill name | raw, all copies |
| `test_skill_figure_step.py` | "No citekey inside either figure file", `<!-- figure: figures/<name> -->`, `` `figure-drawer` ``, "kpsewhich tikz.sty", "compiles", "redrawn from a source"; the six `_RIDERS` absent | raw |
| `test_skill_figure_step.py` (**new**) | absent: "need(s) no caption", "if this/the figure warrants", "warrants one/a caption", in the Markdown figure genres' `SKILL.md`, the drawer and its references, and `docs/FIGURE-DRAWER.md` | raw |
| `test_skill_table_step.py` | `<!-- table:`, `<!-- tableref:`, "§13" | raw |
| `test_skill_acronym_step.py` | "acronym vocabulary" | raw |
| `test_skill_pregate_feedback_step.py` | `_POINTER_FORM` now holds `tutorial-writer`: the step, from "Critique against the evidence packet" to the end of its `Done when` sentence, names `` `.claude/skills-common/references/critique.md` ``, says "not done until the loop the reference describes has run", and names no `-m chitragupta` command; every rider found in the step plus the whole reference | raw step plus reference |
| `test_skill_style_check_step.py` | the `prose-check.md` pointer within 1,400 characters after a `draft style`; "§9 marks decidable" and "fix none of them" within 1,400 after every one | raw; expanded |
| `test_skill_verbatim_scan_step.py` | the `verbatim-scan.md` pointer within 1,200 after the scan; the rebuild within 200 before it; the restatement caveat and "tiers_not_run" within 2,000; "never a condition of presenting" | raw; expanded |
| `test_skill_retrieval_logging.py` | `--log` within 220 characters of every `retrieve search` | raw, references too |
| `test_skill_size.py` | each copy under 17,000; the cap within 1,000 of the largest copy; a reason | raw |
| `bench/skill_commands.py` `expected_commands` | the 22 commands below | raw, references too |

No citation sits inside steps 12, 17 or 18 (the critique, prose check
and verbatim scan: Review focus 1). The new `mathematical-prose.md`
citation is in step 9, before them.

**Expected commands, before and after** (each harness's copy, the files
it names, and `figure-drawer` by handoff). The same 22 on all three
harnesses; only the order of first appearance moved:

```text
draft gate, corpus ledger, draft dossier init, draft dossier outline,
draft retrieve search, review synthesis, draft dossier check-evidence,
draft dossier sections, draft dossier status, review verbatim scan,
draft style, review verbatim recheck, draft evidence,
draft dossier stamp, draft dossier export, draft references,
draft render, draft figures, figure new, figure sync, figure check,
figure look
```

## The caption inconsistency (PR 2, Task 1, Step 2)

Old step 9 (`:390-396`) said "A caption, **if this figure warrants
one**, goes in the draft" and "Most of this genre's rare figures need no
caption at all, and that is the accepted case, not a gap".
`docs/writing-standards/figures.md` §10 gives every figure a caption and
`draft style` reports a bare marker as `FigureNoCaption` (#421), so the
sentence asked for a draft the checker then flags. Written test first:
`test_nothing_a_markdown_figure_genre_reads_makes_its_caption_optional`
failed on three files before the fix:

| File | Wording | Now |
| --- | --- | --- |
| `.claude/skills/tutorial-writer/SKILL.md` step 9 (three copies) | "if this figure warrants", "need no caption" | "**A caption line directly below the marker** ... Every figure has one." |
| `.claude/skills/figure-drawer/references/placement.md` §1, the `.md` row (survey, tutorial, textbook) | "if the figure warrants a caption, a caption line directly below it" | "its caption line directly below it" |
| `docs/FIGURE-DRAWER.md`, "What you get", the `.md` row | "a caption line directly below it if the figure warrants one" | "its caption line directly below it" |

The last two are read on every tutorial figure (the drawer's placement
table) or describe tutorials (the `.md` row names them), so each
contradicted the same rule. Also found, **not changed**, because it
concerns the thesis genre, not tutorials: the `.tex` rows of both tables
("a captioned figure goes inside a hand-written `figure` float", "when
captioned") imply a thesis figure may go uncaptioned. That is the thesis
branch's to settle. "Most of this genre's rare figures" also
contradicted the same step's own "this is the genre most free to use
them"; `genres/tutorial.md` keeps only the latter.

## Does a tutorial write mathematics?

**Yes, so it now cites `mathematical-prose.md`.** Old step 9 (`:398-414`)
tells it to treat a value the lesson reasons about as a quantity with a
row in `math.md`, and to number a formula reused across steps. The bench
task asks for exactly that ("treat the threshold as a quantity in the
prose"). A skill that can write a quantity and number an equation can
write mathematics, so step 9 now says: when the lesson reasons about a
quantity, read `.claude/skills-common/references/mathematical-prose.md`
now and follow it. The citation is conditional, unlike the two chapter
genres', because most lessons stay at the keyboard; that reference opens
"Read this on every run of a chapter skill", which this skill's
condition narrows, and it is not edited here (it is a shared file).

## Where each removed paragraph went

`genre-steps.md` is `.claude/skills-common/references/genre-steps.md`;
`tutorial.md` is `.claude/skills/tutorial-writer/references/tutorial.md`;
`genres/tutorial.md` is `docs/writing-standards/genres/tutorial.md`.

### Header, what this genre is not, prose standards

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "Genre-specific drafting agent for tutorial output, in the Diataxis sense" | the definition stays, reworded into the opening paragraph; "The drafting layer (generative, on-demand, user-reviewed)" cut: restates `docs/ARCHITECTURE.md`'s layer split |
| 14 | "The governing analogy is a driving lesson" | `genres/tutorial.md`, "What a tutorial owes its learner" |
| 20 | "That responsibility is the whole discipline of this genre" | `genres/tutorial.md`, same section; the bold "A tutorial that doesn't work is worse than no tutorial" also stays in the opening paragraph |
| 25 | "## What this genre is not" (heading) | stays: `docs/WRITING-STANDARDS.md` §5 names it |
| 27–33 | the routing table | stays whole: it names skills |
| 35 | "Changing a tutorial that **already exists**" | stays, as one sentence with its reason |
| 40 | "The two failure directions, both common" | `genres/tutorial.md`, "What a tutorial owes its learner" |
| 42 | "**Drifting into explanation.**" | `genres/tutorial.md`, same section |
| 45 | "**Drifting into a how-to.**" | `genres/tutorial.md`, same section |
| 50 | "If the user actually wants either of those, tell them so" | stays; "Writing a tutorial when a how-to was wanted wastes everyone's time" cut: restates the sentence before it |
| 53 | "## Prose standards" | stays |
| 55 | "`docs/WRITING-STANDARDS.md` holds the cross-genre rules" | stays as one sentence plus the pointer to `genres/tutorial.md`; the list of rules it summarised is cut as a restatement of the core's §1–§6 |
| 59 | "Where this genre departs from it: §5's 'don't let a document do two jobs' is strictest" | `genres/tutorial.md`, "What a tutorial owes its learner" |

### Corpus layer, collection scoping, dossier

| Old line | First words | Went to |
| --- | --- | --- |
| 64 | "## Shared corpus layer (read, don't regenerate)" (heading) | becomes "## Before you start", as in survey-writer |
| 66 | "`content/ledger.sqlite` -- per-citekey status" | `genre-steps.md` §1 |
| 67 | "`content/parsed/<citekey>.txt`" | `genre-steps.md` §1 |
| 68 | "`chitragupta/retrieval.py` -- `search(query, k, snippet_chars)`" | `genre-steps.md` §1 |
| 70 | "**Read-only means read-only: never run `python -m chitragupta.corpus sync`" | the rule and both commands stay; the write lock, the run time and "do not build an index" go to `genre-steps.md` §1 |
| 80 | "If `python -m chitragupta.corpus ledger` reports an empty ledger, say so" | stays, with the command in a fence; the step says `genre-steps.md` §1's empty-ledger rule does not apply here |
| 87 | "**Citations are rare in this genre and belong only in the closing 'Where to go next'**" | `genres/tutorial.md`, "Citations: only in 'Where to go next'"; the rule itself stays in step 6 ("the only section that may cite") and in the critique step |
| 93 | "## Collection scoping (#195): draft from the shelf, not the library" | stays as "Collection scoping"; "(#195)" cut as history (Decision 4); the subtitle is `collection-scoping.md`'s own title |
| 95 | "At step 0, before any retrieval" | stays as "Before the first retrieval": this skill has no step 0 |
| 98 | the `ledger --collections` fence | stays; its comment "what exists, with counts" cut: restates the command's output |
| 102 | "Paths in this skill are from the project root" | stays, moved to the opening paragraph |
| 105 | "If it reports none, say nothing, ask nothing" | stays |
| 113 | "## The dossier: write down what produced the draft" (heading) | cut: the section's content moved (rows below) |
| 115 | "The lesson is only half of what this run produces" | `tutorial.md` §1, "The dossier holds the lesson's design" |
| 124 | "`chitragupta/dossier/` owns that state" | cut: duplicate of `genre-steps.md` §2, which step 1 cites |
| 130 | "None of this depends on the draft citing anything" | `tutorial.md` §1 |

### Steps 1–8

| Old line | First words | Went to |
| --- | --- | --- |
| 136 | "1. **Establish the destination artifact, and open the dossier.** Decide the one concrete thing" | title, "in a sentence" and "ask the user" stay; "small, real and visibly functioning", "'A working X that does Y'" and "isn't scoped yet" go to `tutorial.md` §1 |
| 142 | "Then, once the artifact and the draft's path are settled ... create the dossier" | the command stays |
| 149 | "**Settle `<slug>` with the user before running that.**" | `genre-steps.md` §3, with the generic example; "Settle `<slug>` with the user" stays |
| 159 | "Fill in `scope.md` now, while you are deciding these things" | `genre-steps.md` §3; `Done when` names the fields |
| 161 | "**Reader** -- the learner in one concrete sentence" | `tutorial.md` §1 |
| 163 | "**Covers** -- the destination artifact" | `tutorial.md` §1 |
| 165 | "**Does not cover** -- the variations, edge cases" | `tutorial.md` §1 |
| 168 | "**Glossary** -- each recurring term ... Check the acronym vocabulary first" | the glossary to `tutorial.md` §1; the vocabulary to `genre-steps.md` §3; "the acronym vocabulary" stays in step 1's pointer |
| 173 | "**`language:`** -- the dialect, a BCP-47 tag" | the dialect to `genre-steps.md` §3; "command output and file contents keep the tool's spelling" to `tutorial.md` §1 |
| 179 | "`init` also stamps the corpus fingerprint" | `genre-steps.md` §3 |
| 182 | "2. **Do a task analysis.** Walk the entire path yourself first" | stays; "The steps you perform automatically are exactly the ones your draft will omit" goes to `tutorial.md` §2 |
| 188 | "Record the outcome in the dossier while you have it ... `## Rejected paths`" | the instruction and the heading stay; the table format, the two examples and "the most valuable entry" go to `tutorial.md` §2 |
| 198 | "3. **Write the front matter the learner needs before starting:**" | title and the four item names stay |
| 199 | "**What you'll build**" | `tutorial.md` §2 |
| 202 | "**What you'll learn**" | `tutorial.md` §2 |
| 203 | "**What you need**" | `tutorial.md` §2; "exact versions" stays |
| 206 | "**How long it takes**" | `tutorial.md` §2 |
| 208 | "4. **Write the steps.** Rules, in priority order" | title and a one-sentence summary stay; the rules go to `tutorial.md` §3 |
| 209 | "**Every step is an action the learner takes.**" | `tutorial.md` §3 |
| 211 | "**Start each step with an imperative verb.**" | `tutorial.md` §3 |
| 212 | "**Be concrete, never abstract.**" | `tutorial.md` §3 |
| 216 | "**Show the expected result after every step that produces one.**" | `tutorial.md` §3 |
| 220 | "**Guarantee results.**" | `tutorial.md` §3 |
| 223 | "**No options, no alternatives**" | `tutorial.md` §3 |
| 225 | "**Minimal explanation inline.**" | `tutorial.md` §3 |
| 228 | "**Repetition is fine.**" | `tutorial.md` §3 |
| 230 | "**Warnings go before the step they concern**" | `tutorial.md` §3 |
| 232 | "**Never say 'simply', 'just', 'obviously', or 'easy'.**" | `genres/tutorial.md`, "What a tutorial owes its learner": a writing rule, the core's §2 defect markers with this genre's reason |
| 235 | "5. **Land the ending.**" | stays; "A tutorial that stops at the last command leaves the learner unsure" goes to `tutorial.md` §3 |
| 240 | "6. **'Where to go next'.** This is where deferred explanation" | title and judgement stay; the detail goes to `tutorial.md` §4 |
| 245 | "If the dossier has an `outline.md` ... run those verbatim" | the `--check` command, "declared" and "extended" stay; the outline's detail is `genre-steps.md` §4; "a `claim:` block is a steer" is in `genre-steps.md` §4 and `tutorial.md` §4 |
| 256 | "Otherwise, same retrieval discipline as the other skills if you do search: over-fetch" | stays, with its command |
| 263 | "`--log` records the query in the dossier's `retrieval.md`. **Pass it on every call**" | `--log` stays in the fence; why goes to `genre-steps.md` §1 and `tutorial.md` §4; reading snippets to `genre-steps.md` §5; reformulation to `genre-steps.md` §6 (cited); "a real citekey from a search result" stays |
| 273 | "**The multi-source floor here is the whole document, not the paragraph.**" | the rule in one sentence, the marker, §11 and the `review synthesis` command stay; the rationale goes to `tutorial.md` §4 and `genres/tutorial.md` "Citations" |
| 287 | "If you did search, record both outcomes in the dossier" | the command stays; the formats and the two warnings are `genre-steps.md` §5 (cited) |
| 301 | "7. **Budget the length.**" | stays |
| 306 | "8. **Run it. This step is not optional.**" | stays, every instruction and the not-optional title; "an untested tutorial is the exact artifact this genre exists to avoid" goes to `tutorial.md` §5 |
| 317 | "Then write what you actually ran against into `scope.md`, under a `## Verified environment` heading" | stays, with the unverified steps; the dated example and "the front matter states what it supports; the dossier states what was executed" go to `tutorial.md` §5 |
| 326 | "A tutorial rarely needs a table" | stays, with its three markers and §13 (now `docs/writing-standards/tables.md` §13); "weighing alternatives is a different genre's job" goes to `genres/tutorial.md`; "Never write the number yourself" cut: duplicate of `tables.md` §13 |

### Steps 9–11

| Old line | First words | Went to |
| --- | --- | --- |
| 334 | "9. **Add a figure, if the path needs one.** Go back to wherever it belongs" | title, placement and the per-figure test stay; "the genre most free to use them", "a heavily illustrated tutorial is a good tutorial" go to `genres/tutorial.md`, "Figures" |
| 348 | "A figure that does earn its place is a **pair of files**" | stays, citing `docs/writing-standards/figures.md` §10 |
| 353 | the marker fence | stays |
| 357 | "Write both `content/drafts/<topic>/figures/<name>.tex`" | the pair and "(step 15) get the TikZ" stay; how the renderer swaps the marker per format is cut: duplicate of `figures.md` §10, "Every figure has two forms" |
| 365 | "Hand the drawing itself to `figure-drawer`" | stays; the list of what the drawer owns is cut: duplicate of `figure-drawer`'s `SKILL.md` |
| 371 | "**A topic directory is required.**" | stays; where flat-draft figures land is `genre-steps.md` §3 |
| 376 | "**Check for TikZ, and that the figure compiles.**" | stays |
| 383 | "**No citekey inside either figure file.**" | stays, with "Step 13's gate does not follow `\input`"; "This genre's citations belong in 'Where to go next' anyway" cut: duplicate of step 6 |
| 387 | "**Nothing redrawn from a source.**" | stays; "the same violation in different pixels" cut: duplicate of `figures.md` §10, "Originality binds the TikZ identically" |
| 390 | "**A caption, if this figure warrants one, goes in the draft**" | the caption line and `figureref` stay, now unconditional; "never write 'Figure' or a number" cut: duplicate of `figures.md` §10; "Most of this genre's rare figures need no caption at all" **removed as wrong** (see "The caption inconsistency") |
| 398 | "**A quantity in the prose follows `docs/WRITING-STANDARDS.md` §12.**" | the pointer stays (now `mathematics.md` §12) with "a value the learner types stays code", plus the new `mathematical-prose.md` pointer; the typed-versus-reasoned rule, its example and "prefer code" go to `genres/tutorial.md`, "Mathematics" |
| 407 | "**Numbering one is rarer still.**" | the two markers stay; when to number goes to `genres/tutorial.md` |
| 416 | "10. **Reread as the beginner.**" | title stays; the four flags go to `genres/tutorial.md`, "The beginner reread, and the self-check" |
| 421 | "11. **Map the lesson's outline into the dossier.** Save the draft" | title, "save the draft" and the command stay; "reports `No such draft`" cut: the command's own error |
| 430 | "It writes one row per heading, and it skips fenced code" | fenced code cut: duplicate of `docs/DRAFT-ITERATION.md` ("It skips code first, and has to", which names the tutorial case); "an empty cell is the honest result" stays in one sentence and in `tutorial.md` §4; "the outline is the real payload ... repair one step at its recorded line range" is `genre-steps.md` §2 (what `sections.md` is for) |

### Step 12, the critique, in pointer form

| Old line | First words | Went to |
| --- | --- | --- |
| 441 | "12. **Critique against the evidence packet, before gating.** Skip this entirely if the lesson has no citations" | title and skip condition stay ("runs only if the lesson cites anything"); "zero citations is the normal case, not a gap" goes to `tutorial.md` §4 |
| 444 | "Otherwise, since this genre cites only in 'Where to go next,' read the dossier's `evidence.md`" | stays: this genre's listing paragraph, limited to "Where to go next" |
| 450 | "This is one inline judgement call" | stays; "nothing in this pipeline scores this automatically" cut: duplicate of `critique.md` step 2 |
| 454 | "**Run this step: it is never a condition of presenting, but it is not done until you have run its commands.**" | "never a condition of presenting" stays; the rest becomes "not done until the loop the reference describes has run", the sentence SK-0c measured |
| 456 | "Read `.claude/skills-common/references/critique.md` now, before listing anything, and work it through" | stays, as "follow it with `content/drafts/<slug>.md` as `<draft>`"; "In outline:" cut |
| 460 | "1. Where the dossier has an `outline.md`" and its `dossier status` fence | `critique.md` step 1, which already held both |
| 467 | "2. Take the baseline" and its three-command fence | `critique.md` step 3, which already held them |
| 475 | "If the scan's `tiers_not_run` is not empty, quote the reason" and the `style` qualifier | `critique.md` step 3; the step asks for the reason back |
| 481 | "3. Repair at most three items, each edit with `Edit`, inside 'Where to go next' only" | "each edit with `Edit`" (`critique_edit_tool`) and "inside 'Where to go next' only" stay; "at most three repairs" stays in the not-done-until sentence; the accept rule goes to `critique.md` step 4 |
| 485 | the `gate`, `verbatim recheck` and `style` fence | `critique.md` step 4, substep 3 |
| 492 | "Read `style`'s count only as a number" | `critique.md` step 4, substep 3 |
| 495 | "4. Log every attempt, kept or reverted, in the dossier's `revisions.md`" | `critique.md` step 4, substep 5; the step keeps "logged in the dossier's `revisions.md`" |
| 497 | "If nothing on the list clears the bar, or the list was empty" | `critique.md` step 6; the step's `Done when` keeps it, and the step adds what to come back with |

### Steps 13–19, self-check and sources

| Old line | First words | Went to |
| --- | --- | --- |
| 499 | "13. **Gate any citations.**" | stays, with its command and the no-citations case |
| 508 | "Note: the gate blanks what pandoc does not render as prose" | stays, every clause, in two sentences |
| 516 | "14. **Build the References section**, only if the draft cites anything" | stays; "keep the default `## References` heading" stays; "the same contract as `textbook-chapter-writer` (#699)" cut: a cross-skill aside with an issue number (Decision 4); why another heading lists references twice is `render-and-references.md` §1 |
| 524 | "15. **Render tex, pdf, and numbered md.**" | stays |
| 528 | "**Do not render an evidence sidecar, and this is a recorded answer rather than an omission.**" | stays, with the command it does not run |
| 533 | "The reason is what a tutorial *is*" | `tutorial.md` §6 |
| 542 | "If you find yourself wanting one, that is a signal you have written a textbook chapter" | `tutorial.md` §6, without the skill name (a reference names none); the routing is the "What this genre is not" table |
| 546 | "16. **Record any steering.**" | stays, with its four examples; "it is usually what fixed the single path ... a revision that doesn't know about it will undo it" is `genre-steps.md` §2, "Steering belongs there too", cited |
| 553 | "17. **Run the prose check.**" | stays; "what the check can and cannot see, and how to report what it finds" cut: a description of `prose-check.md`, which the pointer reaches |
| 564 | "18. **Run the verbatim scan.**" | stays |
| 572 | "The first command is not optional: a section map written earlier" | "not optional" stays, as "not a repeat of step 11"; why is `verbatim-scan.md`, "Why the section map is rebuilt first" |
| 575 | "It matters here even though this genre barely cites" | cut: duplicate of `verbatim-scan.md` ("reuse in prose that cites nothing, which no per-citekey check can see"); "A review aid, not a gate" stays |
| 580 | "Read `.claude/skills-common/references/verbatim-scan.md` now and follow it: what to show" | the pointer and the `agenda-reviser` routing stay; "what to show, what the scan could not check" cut: a description of that file |
| 585 | "19. **Stamp the draft fingerprint, then present.** Nothing edits the lesson's text after this point ... (#454)" | the command stays; why goes to `genre-steps.md` §7; "(#454)" cut as history |
| 593 | "Then **present**, reporting: the draft path, the render outcome" | the draft and render outcome are `genre-steps.md` §7; "whether step 8 verification passed in full, in part, or not at all" stays; the dossier, gitignore and hand-over are `genre-steps.md` §7; the `draft-reviser` routing and the `dossier export` command stay |
| 602 | "## Self-check before presenting" and its nine items | `genres/tutorial.md`, "The beginner reread, and the self-check", all nine; step 10 now reads it and is done when each is "yes" |
| 616 | "## Sources" and its paragraph | the link stays in "Prose standards"; the summary goes to `tutorial.md` §7 |

### Totals

- **113 rows**, one per paragraph, list item, table or fence of the old
  file (the critique step's numbered items count one row each).
- **Stay, with nothing moved or cut: 18** (a title, a command, a
  guardrail, a marker or a routing sentence, some reworded into the
  step's one judgement sentence).
- **Moved: rows naming `tutorial.md` 36, `genres/tutorial.md` 16,
  `genre-steps.md` 19 and `critique.md` 9**; a row may name more than
  one file, and most keep their title or command inline as well.
- **Cut: 23 rows** cut some or all of their text, each as a duplicate of
  a named file and section, a description of a reference the pointer
  reaches, history, or the command's own output. One sentence was
  **removed as wrong**: "need no caption at all".
- **Without a destination: none.**

### What was added, not moved

Each step gained a one-line `Done when` and each pointer its condition.
Step 9 gained the conditional `mathematical-prose.md` pointer. Step 12
gained "with no citations there is no evidence packet, so skip to step
13", "Come back with ..." and its `Done when`, the survey's pointer-form
sentences. Step 10's `Done when` makes the old self-check a condition of
the reread. Nothing else in the three new files is new text.

## For the integrator

Procedure this skill repeats that at least one other genre writer also
repeats and `genre-steps.md` does not hold. Each stays inline here,
quoted as it now stands, for joining when the three SK-2 branches meet:

1. **The empty ledger in a genre where citing is optional.**
   `genre-steps.md` §1 says "An empty ledger stops the run", which is
   wrong for this skill and textbook-chapter-writer (`AGENTS.md:198`).
   This skill's text: "If it reports nothing `parsed`, say so before you
   start. Citations are optional in this genre, so the lesson is still
   possible, but it will carry none: ask whether to proceed uncited or
   to sync first, and wait for the answer." §1 could gain one sentence
   for both: "In a genre where citing is optional, say so and ask
   whether to proceed uncited or to sync first, and wait."
2. **A draft with no citations still gets a dossier.** `tutorial.md` §1:
   "None of this depends on the draft citing anything ... an empty
   `evidence.md` is honest." textbook-chapter-writer's dossier section
   says the same. A fit for `genre-steps.md` §2.
3. **The steps that run only if the draft cites anything**: the critique
   ("runs only if the lesson cites anything; with no citations there is
   no evidence packet"), the gate ("If it contains any `[@citekey]`
   ... with no citations at all, just save the file") and the
   References section ("only if the draft cites anything"). Textbook
   has all three (its `:408`, `:470`, `:477`). Each stays in its step,
   because the critique step's text is pinned and the gate is the gate;
   a shared sentence would sit in `genre-steps.md` as the rule the steps
   apply.

## For the plan

`plans/1091-skill-shrink.md` is not edited on this branch. What it
should say:

- **PR 2, Task 1, Step 2**: done, and wider than written: the drawer's
  `placement.md` §1 and `docs/FIGURE-DRAWER.md` carried the same
  "if the figure warrants" wording for every `.md` genre, and are fixed
  with it; a new test pins all three. The `.tex` rows of both tables
  still imply an optional thesis caption, for the thesis task.
- **PR 2, Task 4**: done. The reference has seven sections, not five:
  §1 (the destination and the lesson's `scope.md`, from step 1 and the
  old dossier section) and §7 (sources) were added to the list.
  `tutorial-writer` cites `mathematical-prose.md`, conditionally (above).
- **PR 2, Task 5, Step 1**: tutorial-writer ends at 16,561 bytes, cap
  17,000 with a reason, under Decision 1's 2026-11-14 answer.
- **PR 2, Task 5, Step 2**: no file cites a tutorial step that changed;
  only `docs/GENRE.md:195` named moved text.

## The bench

Claude Code only, skill-only, `PYTHONPATH` unset, each run capped at
3600 seconds. Rows in `bench/results/2026-11-15-tutorial-writer-shrink/`:
`before.json` is the 3 recorded rows of
`2026-11-14-skill-bench-skill-only` plus 3 fresh runs of `origin/main`
at `b392448a` (whose tutorial-writer, shared references and drawer are
byte-identical to this branch's base), renumbered 4-6; `after.json` is 6
runs of this branch, in two batches of 3. The task gives the dossier no
`outline.md`: no run in either arm had one.

**3 against 3: inconclusive** (exit 3), on `draft dossier status` alone
(3 to 2). **6 against 6: fail** (exit 1), on that row alone:

| | Before | After |
| --- | ---: | ---: |
| Usable runs, none timed out, gate passed | 6 | 6 |
| `draft dossier status` | 6 | 2 |
| `review verbatim recheck` | 5 | 6 |
| `draft dossier outline` (the step 6 check) | 0 | 5 |
| every other command row | equal | equal, but `draft evidence` 0 to 1 and `figure sync` 0 to 1 |

Per the brief, `draft dossier status` alone is the expected row: the
loop runs it only where the dossier has an `outline.md`, and none did.
What each after run wrote about the outline in `revisions.md`:

| Run | Ran `dossier status` | `revisions.md` on the outline |
| --- | --- | --- |
| 1 | no | "No `outline.md`, so no declared queries to read." |
| 2 | yes, with the baseline | "No outline.md, so no declared queries to read." |
| 3 | yes, with the baseline | "No outline.md ..."; "Declared queries: none declared (no outline.md)." |
| 4 | no | "No `outline.md`, so no declared-query report." |
| 5 | no | nothing about the outline (the critique entry lists its gaps and three accepted repairs) |
| 6 | no | "Declared queries: no `outline.md`, so no declared list to exhaust." |

So the commands were not put back. The one `draft evidence` in run 6 was
a mistyped `--citekey` lookup (meant as `draft retrieve evidence`), not a
sidecar: no `.evidence.*` file was rendered in any run.

**Counted by hand** from each after run's project and transcript:

| | Runs 1-3 | Runs 4-6 |
| --- | ---: | ---: |
| `revisions.md` has a critique entry | 3 | 3 |
| Baseline `verbatim scan --write` before the first recheck | 3 | 3 |
| Opened `critique.md`, `genre-steps.md` and `references/tutorial.md` | 3 | 3 |
| Opened `mathematical-prose.md` | 3 | 3 |
| Executed the lesson's own commands (extracted from the draft, in a fresh directory) before the stamp | 3 | 3 |
| `scope.md` has `## Verified environment` | 3 | 3 |

The 3 fresh before runs also logged a critique entry and ran the lesson,
and opened `critique.md`; none opened the new reference, which `main`'s
skill does not name. Median run: 436 s for the three fresh before runs,
416 s for the six after runs.
