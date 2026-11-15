# Move ledger: thesis-chapter-writer (#1199, SK-2)

Status: **built on `feat-1091-thesis-writer`, from
`feat-1091-critique-pointer`, 2026-11-15.** Written for
[plans/1091-skill-shrink.md](1091-skill-shrink.md) PR 2, Task 3, the
first half of Task 1 (`placement.md` §4) and thesis's part of Task 5,
in the shape of [the survey-writer ledger](1091-ledger-survey-writer.md).

**Written for** the reviewer of PR 2 and whoever joins its three
branches. **Assumed:** the plan's "Decisions" and "Review focus", and
[docs/HARNESS.md](../docs/HARNESS.md) on the three `SKILL.md` copies.

Every paragraph removed from thesis-chapter-writer's `SKILL.md` has one
row below: its first words, then where it went (file and section) or
"cut" with the reason. A row with no destination is a defect. Line
references are to the old `.claude` copy at `40c8e507`; the `.agents`
and `.opencode` copies held the same paragraphs, differing only where
`tests/fixtures/skill_harness_phrases.toml` says and in OpenCode's
`-opencode` suffixes, and changed the same way.

## What cites this skill's steps

Grepped before renumbering, over the whole repository
(`grep -rnE 'thesis(-chapter-writer)?.{0,80}[Ss]teps? [0-9]+|[Ss]teps? [0-9]+.{0,60}thesis'`,
then a second pass for the step titles):

| Site | Cites | After this branch |
| --- | --- | --- |
| `docs/RENDERING-FLOW.md` ("both run by `thesis-chapter-writer` step 12") | step 12 renders md and pdf | still true: step 12 keeps its number and its two formats |
| `docs/RENDERING-FLOW.md`, "Open gaps" ("`thesis-chapter-writer`'s step 9 says `--format tex` and `--format pdf` get it") | a sentence of step 9 | that sentence is cut (a duplicate of `figures.md` §10, and untrue while that gap is open); the gap now cites step 12's figure-file exception, which relies on the TikZ reaching the pdf |
| the skill's own "step 0", "step 2", "step 7", "step 8", "step 11", "step 12" | internal | steps 0–12 keep their numbers; the ones that survive the rewrite still name the right step |
| `plans/1027-*`, `plans/781-*`, `plans/948-*`, `plans/b5-*`, `plans/b2-*`, `plans/1091-skill-shrink.md` | old step numbers | historical plans, not updated; `1091-skill-shrink.md` is "For the plan" below |

The plan's other Task 5 sites (`docs/WRITING-STANDARDS.md` near line
561, `chitragupta/review/synthesis.py:48`, `chitragupta/review/_units.py:22`,
`docs/PROMPTS.md`'s "19-step") all name textbook-chapter-writer, not
this skill. Nothing outside the skill cites steps 13–17, so the merge of
13 and 14 and the renumbering after it move no other file.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/thesis-chapter-writer/SKILL.md` | 33,773 | 14,666 |
| `.agents/skills/thesis-chapter-writer/SKILL.md` | 33,788 | 14,681 |
| `.opencode/skills/thesis-chapter-writer-opencode/SKILL.md` | 33,890 | 14,783 |

The cap in `tests/test_skill_size.py` falls from 34,000 to 15,000 with
its reason, above the 12,000 target, which the owner's 2026-11-14 answer
makes a guideline. What the 14.7 KB holds, measured on the `.claude`
copy: about 1,000 bytes of frontmatter and title (Decision 7); about
2,600 bytes of fenced commands, ten of them; about 2,700 bytes for step
9, the figure stub `tests/test_skill_figure_step.py` requires to hold
without the drawer, plus the equation form; about 1,300 for step 10,
the critique pointer; and a `Done when` on each of 17 steps.

## Pinned phrases: what the tests read

"Raw" means the test reads `SKILL.md` as written (whitespace collapsed
at most), so the phrase cannot move into a reference. "Expanded" means
it reads `tests/skill_text.py`'s `expanded()`. Every phrase below is
present after the rewrite; the suite is green on it.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_references.py` | "from the project root" within 250 characters after the first `.claude/skills…` path, all three copies | raw |
| `test_skill_references.py` | a `## Collection scoping` section naming `` `.claude/skills-common/references/collection-scoping.md` `` and "ledger --collections" | raw |
| `test_skill_references.py` | "Read `` `.claude/skills-common/references/mathematical-prose.md` `` now", all three copies | raw |
| `test_skill_references.py` | every named path exists; the three copies cite the same `` `path` §N `` set; every cited section exists; every `## N.` of a reference is cited by some skill; no backticked skill name or tool word in a reference | raw; the references |
| `test_skill_harness_copies.py` | `critique_edit_tool`: "each edit with `Edit`" and its two forms; the copies identical after the phrase map; OpenCode names suffixed | raw, all copies |
| `test_skill_figure_step.py` | `%figure: figures/<name>`; absent: `<!-- figure: figures/<name> -->`; "No citekey inside either figure file", `` `figure-drawer` ``, "kpsewhich tikz.sty", "compiles", "redrawn from a source"; absent: the six `_RIDERS` | raw |
| `test_skill_figure_step.py` | figure-drawer and its references still hold "a `verbatim` environment", "## 3. A flat draft", "[tikz-libraries]", "[unicode]", `\renewcommand{\thefigure}` | figure-drawer, references too |
| `test_skill_table_step.py` | `\label{tab:` and `Table~\ref{tab:`, "§13"; absent: `<!-- table:` | raw |
| `test_skill_acronym_step.py` | "acronym vocabulary" | raw |
| `test_skill_pregate_feedback_step.py` | now in `_POINTER_FORM`: the step, from "Critique against the evidence packet" to its `Done when` sentence, names `` `.claude/skills-common/references/critique.md` `` (within 2,000 characters), says "not done until the loop the reference describes has run", and names no `-m chitragupta` command; every rider in the step plus the whole reference | raw step plus reference |
| `test_skill_style_check_step.py` | the `prose-check.md` pointer within 1,400 characters after `-m chitragupta.draft style`; "§9 marks decidable" and "fix none of them" after every such command | raw; expanded |
| `test_skill_verbatim_scan_step.py` | the `verbatim-scan.md` pointer within 1,200 after the scan; `dossier sections … --citekeys --write` within 200 before it; "tiers_not_run", "genuine restatement is only detected where the embedding tier can run" and "never a condition of presenting" | raw; expanded |
| `test_skill_retrieval_logging.py` | `--log` within 220 characters of every `retrieve search` and `retrieve evidence` | raw, references too |
| `test_skill_size.py` | each copy at or under 15,000; the cap within 1,000 of the largest copy; a reason, since it is above 12,000 | raw |
| `bench/skill_commands.py` | the expected commands, below | raw, references and the handed-off skill too |

No citation sits inside steps 10, 14 or 15 other than each step's own
pointer, so no spliced reference pushes a rider out of its window.

**Expected commands** (each harness's copy, the files it names, and
`figure-drawer`'s): 23 before, 24 after, on all three harnesses. None
dropped. `draft retrieve evidence` is added: the old skill named it only
as `... evidence "<q>"` in a bullet, which the bench does not read as a
command, and step 2 now carries it as a fence, as survey-writer's does.

## Where each removed paragraph went

`genre-steps.md` is `.claude/skills-common/references/genre-steps.md`;
`thesis.md` is `.claude/skills/thesis-chapter-writer/references/thesis.md`;
`genres/thesis-chapter.md` is `docs/writing-standards/genres/thesis-chapter.md`;
`placement.md` is `.claude/skills/figure-drawer/references/placement.md`.

### Header, corpus layer, collection scoping, dossier

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "Genre-specific drafting agent for thesis-chapter output" | cut: restates the layer split `docs/ARCHITECTURE.md` states; a one-sentence summary of what the skill drafts replaces it |
| 13 | "Shared corpus layer (read, don't regenerate)" (heading) | cut: heading of the bullets below |
| 15 | "`content/ledger.sqlite` -- per-citekey status" | `genre-steps.md` §1 |
| 16 | "`papers/bibliography.bib` (gitignored, per-host)" | `genre-steps.md` §1; "point the thesis document's `\addbibresource` … at this file directly" goes to `thesis.md` §4 |
| 19 | "`content/parsed/<citekey>.txt`" | `genre-steps.md` §1 |
| 20 | "`chitragupta/retrieval.py` -- `python -m chitragupta.draft retrieve search`" | `genre-steps.md` §1 (what each call returns); both commands stay, now as fences in step 2 |
| 26 | "Collection scoping (#195): draft from the shelf" (heading) | stays as "Collection scoping"; "(#195)" cut as history (Decision 4) |
| 35 | "Paths in this skill are from the project root" | stays, moved to the opening paragraph |
| 38 | "If it reports none, say nothing, ask nothing" | stays |
| 46 | "The dossier: write down what produced the draft" (heading) | cut: the section's paragraphs moved below |
| 48 | "The chapter is only half of what this run produces" | `genre-steps.md` §2; "the terminology the chapter settled on" goes to `genres/thesis-chapter.md`, "What a thesis chapter owes its reader" |
| 55 | "`chitragupta/dossier/` owns that state" | `genre-steps.md` §2 |
| 61 | "This skill writes both the dossier's Markdown files and … `provenance.json`" | `thesis.md` §2 |
| 67 | "**Read-only means read-only: never run `python -m chitragupta.corpus sync`" | the rule and both commands stay ("Before you start"); the write lock, run time and "do not build an index" go to `genre-steps.md` §1 |
| 77 | "**If the ledger is empty, stop.**" | stays, with its command |
| 83 | "If it reports no items, or none with status `parsed`" | stays in one sentence with the remedy; "Do not draft around it, do not sync, do not cite" goes to `genre-steps.md` §1 |

### When to invoke, prose standards, what a thesis chapter owes

| Old line | First words | Went to |
| --- | --- | --- |
| 92 | table row "User asks for a thesis chapter" | cut: the frontmatter description routes it |
| 93–96 | table rows naming `survey-writer`, `textbook-chapter-writer`, `tutorial-writer`, `draft-reviser` | stays, as one line under "When to invoke"; the heading stays because `docs/WRITING-STANDARDS.md` §5 and `docs/GENRE.md` name it |
| 97 | table row "Ledger is empty, or nothing is `parsed`" | cut: duplicate of "If the ledger is empty, stop" |
| 101 | "Follow `docs/WRITING-STANDARDS.md` for the cross-genre rules" | stays as one sentence; its list of rules is cut as a restatement of `docs/WRITING-STANDARDS.md` §1–§6; its attribution becomes the link in "Prose standards" |
| 107 | "The genre-specific additions below layer on top of it. Read `…mathematical-prose.md` now" | the first sentence is cut (the index in `docs/WRITING-STANDARDS.md` states the layering); the pointer stays verbatim, now with its condition: every run, since a single formula brings it in |
| 113 | "Its reader is an examiner" | `genres/thesis-chapter.md`, "What a thesis chapter owes its reader" |
| 119 | "The genre boundary that matters most here" | `genres/thesis-chapter.md`, "What a thesis chapter owes its reader" |

### Steps 0–8

| Old line | First words | Went to |
| --- | --- | --- |
| 126 | "0. **Name the reader's starting point, and open the dossier.** Before searching, settle what an examiner" | title, the examiner's prior knowledge (one clause) and the command stay; why (recap where needed, not condescending) goes to `genres/thesis-chapter.md`; scope and slug go to `genre-steps.md` §3 |
| 137 | "**Settle `<slug>` with the user before running that.**" | "settle `<slug>` with the user" stays; the paths and why go to `genre-steps.md` §3, whose `<topic>/<genre>.<ext>` example covers "the methods chapter of `thesis/`" |
| 147 | "Fill in `scope.md`'s **Reader**, **Covers**" | `genre-steps.md` §3; "the glossary pins the chapter's terminology" stays as a clause; the `Done when` names the fields |
| 150 | "Settle the **dialect** with the reader in the same breath" | `genre-steps.md` §3; "the examiner's institution decides it (an Indian university is `en-IN` or `en-GB`)" stays in step 0 |
| 154 | "Read the acronym vocabulary too" | `genre-steps.md` §3; "the acronym vocabulary" stays in step 0's pointer |
| 158 | "`init` also stamps the corpus fingerprint" | `genre-steps.md` §3 |
| 161 | "1. **Clarify the research question**" | title stays; "argue toward/around this RQ, not just summarize" goes to `genres/thesis-chapter.md` |
| 164 | "2. **Retrieve broadly, then filter.**" | stays |
| 166 | "**First, check whether the dossier has an `outline.md`**" | command stays; what the file holds goes to `genre-steps.md` §4 |
| 175 | "**If it exists and passes**, run each section's declared queries" | stays in one sentence, now with a `--origin declared` fence; why the origins differ goes to `genre-steps.md` §4 |
| 184 | "**A `claim:` section is content to ground, not steer from.**" | `genre-steps.md` §4; `python -m chitragupta.review uncited` stays |
| 194 | "**No `outline.md`, or it fails `--check`:** search against the RQ" | stays, with its command |
| 202 | "`--log` records the query and the call's size" | `genre-steps.md` §1; the `Done when` keeps "with `--log`"; "the list a later `dossier status` re-asks" is cut as a duplicate of `docs/DRAFT-ITERATION.md` |
| 207 | "This is keyword overlap, not embeddings" | `genre-steps.md` §1 and §5; "keep only what supports part of the argument" stays |
| 210 | "Record the judgment in the dossier while the snippets are still in front of you" | stays in one sentence; the `evidence.md` and `rejected.md` formats go to `genre-steps.md` §5 |
| 219 | "Then run `python -m chitragupta.draft dossier check-evidence`" | command stays, now as a fence; what it flags goes to `genre-steps.md` §5 |
| 224 | "3. **Reformulate and re-search if a concept comes up thin.**" | title stays; body to `genre-steps.md` §6 |
| 228 | "4. **Check for disagreement across kept sources.**" | title stays; body to `genre-steps.md` §6 |
| 231 | "5. **Draft** as a LaTeX fragment" | stays |
| 234 | "Section/subsection structure that builds an argument toward the RQ" | stays, in step 5's sentence |
| 235 | "Citations via `\citep{key}` / `\citet{key}`" | stays |
| 236 | "**Two or more citekeys per body paragraph wherever the evidence allows.**" | the rule, `% single-source: why`, its placement, §11 and `review synthesis` stay; "matters most in … related work" goes to `genres/thesis-chapter.md` |
| 244 | "6. **Never write a citekey you didn't get from `search()`.**" | stays; "see AGENTS.md's citekey invariant (fabricated placeholder references …)" is cut as a duplicate of `CLAUDE.md` and `AGENTS.md` |
| 249 | "7. **Log provenance.**" | path and shape stay; why it is in the dossier goes to `thesis.md` §2 |
| 256 | "8. **Map sections to citekeys in the dossier.**" | stays, with its command |
| 264 | "It reads `\citep`/`\citet` as readily as `[@key]`" | `thesis.md` §2; "Drop `--write` to see the table first" is cut as a restatement of `dossier sections --help`; the stderr rule stays |
| 271 | "A table in this genre is **written as real LaTeX**" | the form, `\label{tab:` and `Table~\ref{tab:` and §13 stay, moved into step 5 where tables are drafted; why goes to `thesis.md` §1; "introduce … and read a pattern off it" is cut as a duplicate of `tables.md` §13, "The sentence that reads the table" |

### Step 9

| Old line | First words | Went to |
| --- | --- | --- |
| 283 | "9. **Add a figure only if the argument needs one.** Place it beside the framework" | title and "default to no figure" stay; placement and rarity go to `genres/thesis-chapter.md`, "Figures are occasional" |
| 289 | "When one is earned, it is a **pair of files**" | the pair and the citation of `figures.md` §10 stay; "vector art that sets at the thesis's own font" goes to `genres/thesis-chapter.md` |
| 295 | the `\input` / `%figure:` fence | stays |
| 300 | "with both `…/figures/<name>.tex` and `.txt` written -- the `.txt` in §10's 7-bit alphabet" | cut: duplicate of `figures.md` §10 (the 7-bit alphabet and why a Unicode box character fails pdflatex; the md-preview substitution). "`--format tex` and `--format pdf` get the TikZ" is untrue while `docs/RENDERING-FLOW.md`'s first open gap stands, and that file now cites step 12 instead |
| 308 | "Hand the drawing itself to `figure-drawer`" | stays (the bench's handoff sentence); the list of what the drawer owns is cut as a duplicate of `figure-drawer`'s `SKILL.md` |
| 314 | "**The marker is a comment, never a second `\input`.**" | the guardrail stays; the `Missing $ inserted` reason is cut as a duplicate of `figures.md` §10 |
| 319 | "**Check for TikZ, and that the figure compiles.**" | stays |
| 326 | "**A topic directory is required.**" | stays; where flat-draft figures land goes to `genre-steps.md` §3 |
| 331 | "**No citekey inside either figure file.**" | stays |
| 335 | "**Nothing redrawn from a source.**" | stays; the second sentence is cut as a duplicate of `figures.md` §10 and `figure-drawer` |
| 338 | "**A captioned figure is written as real LaTeX too**" | the float, `\label{fig:`, `Figure~\ref{fig:` and "Never write `\renewcommand{\thefigure}`" stay; why goes to `thesis.md` §1; "issue 411" cut as history |
| 347 | "**Tell the user what their thesis preamble must load.**" | the title stays, as a pointer to `placement.md` §4 (Task 1); the float-is-a-group reason, the flag-clearing hazard and the `\resizebox` note go to `placement.md` §4; "#781" and "#1046" cut as history |
| 356 | the `[tikz-libraries]` `text` fence | `thesis.md` §3 (Decision 2: output samples may move) |
| 371 | "**The same goes for Unicode characters**" | `placement.md` §4 (engine, both files, never edit their thesis); "never rewrite the characters" and the example characters go to `thesis.md` §3; "#948", "#1037", "#996" cut as history |
| 375 | the `[unicode]` `text` fence | `thesis.md` §3 |
| 391 | "**Float placement is theirs to opt into** (#1065)" | `placement.md` §4, which already held it; "never add it yourself" added there from this bullet; "#1065" cut |
| 400 | "**An equation gets the same carve-out, without the pair-of-files ceremony.**" | the `equation` form, `\label{eq:`, `Equation~\ref{eq:` and `\[...\]` stay in step 9; the rest goes to `thesis.md` §1, and "most often the closing line of a derivation" to `genres/thesis-chapter.md`, "Mathematics" |

### Steps 10–17 (now 10–16), and Sources

| Old line | First words | Went to |
| --- | --- | --- |
| 420 | "10. **Critique against the evidence packet, before gating.** Read the dossier's `evidence.md`" | stays: the title and the listing paragraph; "This step runs on every chapter, once the fragment is written and before step 11's gate" added |
| 426 | "This is one inline judgement call" | stays; "nothing in this pipeline scores this automatically" is in `critique.md` step 2 |
| 430 | "**Run this step: it is never a condition of presenting, but it is not done until you have run its commands.**" | "never a condition of presenting" stays; the rest becomes "not done until the loop the reference describes has run" |
| 431 | "Read `.claude/skills-common/references/critique.md` now, before listing anything, and work it through" | stays, as "follow it with `content/drafts/<slug>.tex` as `<draft>`"; "In outline:" cut |
| 436 | "1. Where the dossier has an `outline.md`" and its `dossier status` fence | `critique.md` step 1, which already held both |
| 443 | "2. Take the baseline" and its fence | `critique.md` step 3, which already held them |
| 451 | "If the scan's `tiers_not_run` is not empty, quote the reason" | `critique.md` step 3; the step asks for the reason back |
| 457 | "3. Repair at most three items, each edit with `Edit`" | `critique.md` step 4; "each edit with `Edit`" stays as "make each edit with `Edit`" (`critique_edit_tool`); "at most three repairs" stays |
| 461 | the `gate`, `verbatim recheck` and `style` fence | `critique.md` step 4, substep 3 |
| 468 | "Read `style`'s count only as a number" | `critique.md` step 4, substep 3 |
| 471 | "4. Log every attempt, kept or reverted" | `critique.md` step 4, substep 5; the step keeps "logged in the dossier's `revisions.md`" |
| 473 | "If nothing on the list clears the bar, or the list was empty" | `critique.md` step 6; the `Done when` keeps it |
| 475 | "11. **Gate before presenting.**" | stays; "Fix and re-run until `OK`" becomes survey's wording |
| 484 | "12. **Render md and pdf previews.**" | stays, title extended with the sidecar; "pandoc's LaTeX reader handles a preamble-less fragment" and where the previews land go to `thesis.md` §4 and `render-and-references.md` §2, which already says it; the figure-file exception stays |
| 497 | "**Then render the evidence sidecar**, per … §3, in **pdf only**" | stays, in step 12's sentence |
| 501 | "**This chapter emits one, and the reason it is safe to …**" | `thesis.md` §4 |
| 510 | "It is also the genre that most wants one" | `thesis.md` §4 |
| 517 | "`\citep{...}`/`\citet{...}` markers are read the same as `[@key]` here" | `thesis.md` §4 |
| 521 | "**Skip the reference's §1.**" | "Skip its §1" stays; why goes to `thesis.md` §4; "same as before this feature existed" cut as history |
| 531 | "Note the preview renders that bibliography in IEEE style" | `thesis.md` §4 |
| 537 | "13. **Read it once as the examiner**" | merged into step 13, "Read it once as the examiner, and record any steering"; the checklist and "weaken the claim" go to `genres/thesis-chapter.md`, "The reread", and "weakening any claim that outruns its evidence" stays as a clause |
| 544 | "14. **Record any steering.**" | merged into step 13; the examples and why go to `genre-steps.md` §2 |
| 549 | "15. **Run the prose check.**" | now step 14; "what the check can and cannot see, and how to report" cut as a description of `prose-check.md` |
| 560 | "16. **Run the verbatim scan.**" | now step 15; "a section map written earlier in this run describes a draft you have since edited" cut as a duplicate of `verbatim-scan.md`; "It matters most in the connective prose an examiner reads as your own" stays; "it cannot block the fragment" folded into "not a gate"; "what to show, …" cut as a description of `verbatim-scan.md` |
| 579 | "17. **Stamp the draft fingerprint, then present.**" | now step 16; why goes to `genre-steps.md` §7; "(#454)" cut |
| 587 | "Then present the `.tex` fragment … plus, if rendering succeeded, the preview paths" | stays in one sentence; the hand-over and why the dossier is gitignored go to `genre-steps.md` §7; the `draft-reviser` handoff and `dossier export` stay |
| 596 | "## Sources" (heading) | cut: the link moves to "Prose standards" |
| 598 | "The prose standards this skill inherits are not original" | `thesis.md` §5 |
| 600 | "Full citations, licences and a per-principle attribution table" | the link stays; the licence sentence goes to `thesis.md` §5 |
| 604 | "What bears on *this* genre specifically" | `thesis.md` §5 |
| 606 | "**Google, *Technical Writing Courses***" | `thesis.md` §5 |
| 610 | "**Last, *Technical Writing Essentials***" | `thesis.md` §5 |
| 612 | "**Procida, *Diátaxis***" | `thesis.md` §5 |

### Totals

- **100 rows**, one per paragraph, list item, table row (or run of
  rows) or fence.
- **Keep some of their text: 60** (a title, a command, a guardrail, a
  marker or form a test reads), many reduced to the step's one judgement
  sentence.
- **Moved: 66 rows** send text to `genre-steps.md` (27), `thesis.md`
  (22), `genres/thesis-chapter.md` (10), `placement.md` (3) or
  `critique.md` (9, each already holding the text); a row may name
  several files.
- **Cut: 26 rows** cut some or all of their text, each with its reason:
  a duplicate of a named file and section, a restatement of `--help`, a
  description of a reference the pointer reaches, or history (an issue
  number). 7 of them move nothing elsewhere.
- **Without a destination: none.**

### What was added, not moved

A `Done when` on each step (Decision 4), a condition on each pointer,
step 10's "This step runs on every chapter …" and "Come back with …"
(as survey-writer's step 10 has them), and in step 2 a fence for the
`--origin declared` search and for `retrieve evidence`, which the old
step named in prose. `thesis.md` §3's "the library names … vary with the
fragment; the rest of each line is fixed" is new, so a model quotes the
line as printed rather than the sample. `genres/thesis-chapter.md`'s
pointer to the glossary as the place terms are pinned is step 0's old
clause, generalised.

## `placement.md` §4 (plan PR 2, Task 1, first half)

Each claim was checked against the code before it was written:

| Claim | Where it holds |
| --- | --- |
| the pdf render runs LuaLaTeX with `chitragupta-lualatex.tex`'s fonts | `chitragupta/render_output/_unicode.py` (`FONT_HEADER`, "A pdf is compiled here, by LuaLaTeX"); `assets/latex/chitragupta-lualatex.tex`'s header; `docs/CLI.md` |
| a `[unicode]` line copies both files beside the fragment; LuaLaTeX is recommended, after `fontspec` and `unicode-math` | `_unicode.preamble_files`, the printed line itself |
| `chitragupta-unicode.sty` is for pdflatex only, never overrides an existing glyph, does nothing under LuaLaTeX | the `.sty`'s `\ifPDFTeX\else\endinput` and `\ifcsname u8:…` guard |
| the float-is-a-group reason, the flag-clearing hazard | `docs/RENDERING-FLOW.md` (#781), `docs/TIKZ-STYLE.md` |
| the `\resizebox` note, 135pt to 147pt | `docs/TIKZ-STYLE.md`, "A load while TeX is setting a line prints as blank width"; `tests/test_figure_stray_width.py` |
| `[floats]` is optional | `chitragupta/render_output/_floats.py` |
| **only a `--fragment` render prints any of the three lines** | `fragment` is set only by `render --fragment` (`_cli.py`); `_tikz_libraries.preamble_libraries`, `_unicode.preamble_files` and `_floats.preamble_args` print only when it is true |

The last row is new to §4, and it exposes a disagreement this branch
does not resolve; see "For the plan" below.

## For the integrator

Procedure this skill repeats that a second genre writer also repeats,
and that `genre-steps.md` does not hold: **none found.** Everything
the old skill shared with survey-writer is already a citation of
`genre-steps.md` §1–§7. The LaTeX-fragment rules are this skill's alone
until a research-paper writer exists (the plan's Task 2 note on
`genre-steps.md`), so they went to `thesis.md` §1, not to a shared file.

## For the plan

`plans/1091-skill-shrink.md` is not edited on this branch. What it
should say:

- **PR 2, Task 3:** done as written, with the critique step converted
  to the pointer form (`_POINTER_FORM` gains `thesis-chapter-writer`).
  The cap is 15,000, not at or under 12,000; Task 5 Step 1's "goes back
  to the user" is superseded by the 2026-11-14 answer.
- **PR 2, Task 1, Step 1:** done. **Disagreement found:** step 9 used
  to say "Render the fragment and quote the line it prints", and
  `placement.md` §4 says when each line is printed, but the thesis skill
  never renders with `--fragment`. Step 12 renders md and pdf previews,
  each with its own preamble, so `[tikz-libraries]`, `[unicode]` and
  `[floats]` never print in a thesis run, and the user is never told
  what their preamble needs unless they ask. Either step 12 adds a
  `--format tex --fragment` render (a new output in
  `content/rendered/`, and a bench-visible behaviour change), or §4
  tells the drafter to read the libraries from the figure files. Neither
  is done here, because both change behaviour; the owner decides.
- **`docs/FIGURE-DRAWER.md`, "Thesis fragments"** still tells the user
  to copy `chitragupta-unicode.sty` for a `[unicode]` line, the pre-#1037
  advice `placement.md` §4 has now dropped. It was stale before this
  branch (the same inconsistency Task 1 names) and is left for the
  owner, by the surgical-changes rule.
- **Task 5, Step 2:** none of the four sites it names cites a thesis
  step; `docs/RENDERING-FLOW.md`'s two do, and one is updated.
