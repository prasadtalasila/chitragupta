# Move ledger: book-assembler (#1203, SK-6)

Status: **built on `feat-1091-book-assembler`, above the 8,000 target,
which Decision 1 allows with a reason.** Written 2026-11-15 against
`cc65f47a` (6.173.3), for
[plans/1091-skill-shrink.md](1091-skill-shrink.md), "PRs 3-8, in
outline", PR 6.

**Written for** the reviewer of PR 6, and for whoever builds the
edited-volume skill (#1157). **Assumed:** the plan's "Decisions" and
"Review focus", [the survey-writer ledger](1091-ledger-survey-writer.md)
whose shape this follows, and [docs/HARNESS.md](../docs/HARNESS.md) on
the three `SKILL.md` copies.

Every paragraph removed from book-assembler's `SKILL.md` has one row
below: its first words, then where it went (file and section) or "cut"
with the reason. A row with no destination is a defect. Line references
are to the old `.claude` copy at `cc65f47a`; the `.agents` copy was
identical and the `.opencode` copy differed only in the `-opencode`
suffix on skill names, and both changed the same way.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/book-assembler/SKILL.md` | 19,704 | 13,806 |
| `.agents/skills/book-assembler/SKILL.md` | 19,704 | 13,806 |
| `.opencode/skills/book-assembler-opencode/SKILL.md` | 19,821 | 13,923 |

The cap in `tests/test_skill_size.py` falls from 20,000 to 14,000, with
its reason. **It stays above the 8,000 target.** What the 13.8 KB holds,
measured on the `.claude` copy:

- 963 bytes of frontmatter and title, which Decision 7 leaves alone;
- about 2,000 bytes of fenced commands: every step but step 10 has at
  least one, plus the three cross-unit collision checks and the two
  `book.log` checks, all of which Decision 2 keeps;
- about 1,000 bytes for the guardrail paragraph the brief requires (no
  prose, no fabricated citekey, no edit to a unit, stop on a missing or
  unaccepted unit, stop at the second sign-off) and the five-row
  routing table, whose skill names are harness phrases;
- about 1,000 bytes of project-root paths: 16 citations of the two book
  references (each of `latex-conventions.md` is 62 bytes, each of
  `book-steps.md` 49) and the two review-aid pointers;
- a one-line `Done when` on each of the ten steps.

## Pinned phrases: what the tests read

Built before the rewrite. "Raw" means the test reads `SKILL.md` as
written; "expanded" means `tests/skill_text.py`'s `expanded()`, which
splices each named reference in after its path, and
`tests/test_skill_book_assembly.py`'s `_body()` also appends
`assets/book-skeleton.tex`. Every phrase is still present after the
rewrite; the suite is green on it.

| Test | Phrase, window or absence | Reads | Where it lives now |
| --- | --- | --- | --- |
| `test_skill_book_assembly.py` | "The author is the outline's `- author:` line", "ask the user only if it has none, never invent one" | expanded | `SKILL.md` step 5 |
| `test_skill_book_assembly.py` | `{#front}`, `{#appendices}`, `{#back}`, `{#glossary}`, `{#symbols}`, `{#figures}`, `{#tables}`; "**An outline with none of the three reserved parts** is one"; "Never edit it: its wording, licence and year are the author's."; "only if it has something to show" | expanded | `latex-conventions.md` §3, §4 |
| `test_skill_book_assembly.py` | "-m chitragupta.draft registry check"; "print every finding to the user, in full, before composing"; "exits 0 whatever it finds" | expanded | `SKILL.md` step 3 (the command, "exits 0 whatever it finds"); `book-steps.md` §3 (the print-in-full sentence verbatim) |
| `test_skill_book_assembly.py` | "-m chitragupta.draft spec status", "-m chitragupta.draft unit status", "Do not say the book is finished" | expanded | `SKILL.md` steps 1, 2, 10 |
| `test_skill_book_assembly.py` | "-m chitragupta.draft gate content/rendered/<book>/book.tex" | expanded | `SKILL.md` step 6 |
| `test_skill_book_assembly.py` | "It writes no prose."; "draft-reviser" | expanded | `SKILL.md` opening |
| `test_skill_book_assembly.py` | "--format tex --fragment"; absent "--fragment --output-dir" | expanded | `SKILL.md` step 4 |
| `test_skill_book_assembly.py` | `\bibliographystyle{IEEEtran}`, the natbib line, `\addcontentsline{toc}{chapter}{Bibliography}`, `\input{preamble}`, `\input{chitragupta-floats}`, the `\setcounter` lines | expanded (skeleton) | `assets/book-skeleton.tex`, unchanged |
| `test_skill_book_assembly.py` | "lualatex -interaction=nonstopmode book.tex", "bibtexu book", "Four passes"; absent "pdflatex -interaction" | expanded | `SKILL.md` step 9 |
| `test_skill_book_assembly.py` | "write `book.md`", "hyperlinking the chapter files" | expanded | `latex-conventions.md` §1, "Two files, not one" |
| `test_skill_book_assembly.py` | "Read `book.log` before believing the PDF"; "chitragupta float page:"; "not a failure of the build" | expanded | `SKILL.md` step 9 |
| `test_skill_book_assembly.py` | "No `citeproc-defs.def`", "drop both the line and the file" | expanded | `latex-conventions.md` §5 |
| `test_skill_book_assembly.py` | "content/rendered/<book>/book.tex", "content/rendered/<book>/book.md", "cd content/rendered/<book>" | expanded | `SKILL.md` steps 5, 6, 9 |
| `test_skill_book_assembly.py` | `\setcounter{secnumdepth}{-2}` | expanded | `latex-conventions.md` §2, §4 |
| `test_skill_book_assembly.py` | "content/specs/<book>/preamble.tex"; "last line of the preamble"; "write no `\input` and say nothing about it" | expanded | `SKILL.md` step 5; `latex-conventions.md` §4 |
| `test_skill_book_assembly.py` | the three index command fragments | expanded | `SKILL.md` steps 3, 4, 9 |
| `test_skill_book_assembly.py` | conventions: the skeleton path, no `\documentclass`, "**The index** (#1168", "Front and back matter" | the reference | `latex-conventions.md` §1, §9 |
| `test_skill_references.py` | `## Conventions as data` names `` `.claude/skills/book-assembler/references/latex-conventions.md` `` | raw | `SKILL.md`, heading kept |
| `test_skill_references.py` | "from the project root" within 250 characters of the first named path; every named path exists; the three copies cite the same `§N` set; every `## N.` is cited; no skill or tool name in a reference | raw | the opening paragraph; 16 citations, identical in all three copies; `latex-conventions.md` §1–§9 and `book-steps.md` §1–§5 all cited |
| `test_skill_harness_copies.py` | OpenCode copy: every backticked skill name suffixed `-opencode` | raw | all copies |
| `test_skill_table_step.py` | `<!-- table:` and `§13` | raw | `SKILL.md` step 5 (the collision check, citing `docs/writing-standards/tables.md` §13) |
| `test_skill_style_check_step.py` | the `prose-check.md` pointer within 1,400 characters after `-m chitragupta.draft style`; its riders within 1,400 | raw; expanded | `SKILL.md` step 7, with no citation added inside it |
| `test_skill_verbatim_scan_step.py` | the regeneration within 200 of the scan; the `verbatim-scan.md` pointer within 1,200 of it; the caveat and "tiers_not_run" within 2,000; "never a condition of presenting" | raw; expanded | `SKILL.md` step 8, with no citation added inside it |
| `test_skill_pregate_feedback_step.py` | book-assembler does **not** carry "Critique against the evidence packet" | expanded | absent, as before |
| `test_skill_size.py` | each copy at or under the cap; cap within 1,000 of the largest copy; a reason above 8,000 | raw | 14,000, with its reason |

**Expected commands, before and after** (`bench/skill_commands.py`,
each harness's copy plus the files it names). The set is unchanged on
all three harnesses, 15 commands each; only the order of first
appearance moved:

```text
draft spec, draft unit, draft registry check, draft gate,
draft unit accept, draft spec status, draft spec sign, draft unit status,
draft registry build, draft render, draft style, draft dossier sections,
review verbatim scan, draft registry index, review figure
```

## The four "the conventions say" pointers

Each now states when to read `latex-conventions.md` and which section,
which the old file could not: the reference had no numbered sections.
It now has nine, each opening with its own condition, and every one is
cited by `SKILL.md`.

| Old line | Old text | Now |
| --- | --- | --- |
| 149 (the plan's `:150`) | "The front matter, appendices and back matter go where the outline puts them, as the conventions say" | **The whole-step one.** Placing the reserved parts and the generated pages has no command, so step 5 says it is not done until every outline entry and generated page sits where `latex-conventions.md` §3 puts it, and to come back with the list of what was placed and which generated pages printed. §3 is also one of the four sections "Conventions as data" has read before step 5 on every run |
| 157 (`:158`) | "Copy it, never `\input` it across directories (the conventions say why)" | step 5: "When either exists, read `latex-conventions.md` §4 before copying it" |
| 229 (`:230`) | "**LuaLaTeX and `bibtexu`, the engine the pdf render uses** (#1037; the conventions say why, and what it costs)" | step 9: "If a pass fails, or the user asks why LuaLaTeX and `bibtexu`, read `latex-conventions.md` §7"; the "(#1037)" history is cut from the skill (Decision 4) |
| 353 (`:354`) | "A self-numbered *chapter title* is a different case (#804), and the conventions say why" | step 9: "If a unit's own headings carry numbers, or the PDF numbers a heading twice, read `latex-conventions.md` §2 before changing anything" |

The fifth pointer, "Read `latex-conventions.md` before composing, and
follow it exactly" in "Conventions as data", named no section and sent a
model to the whole 25 KB file on every run. It now names the four
sections every composition needs (§1, §3, §4, §6) and leaves the rest
to the step that needs each one.

## What #1170 trimmed, and where each passage is now

`plans/1168-book-index.md` ("Assembly") records only that #1170 put its
three index command lines in `SKILL.md` "with existing wording trimmed
to fit". The trims, read from `e19021ee`'s diff of `SKILL.md`, are four.
Each passage is still stated where a model reads it; none was lost, so
nothing is restored.

| #1170 trimmed from `SKILL.md` | Where it is now |
| --- | --- |
| step 5: why `preamble.tex` is copied rather than `\input` across directories ("the `\input` paths in `book.tex` are all relative to the book's own directory, and one that reached out of it would break the moment the book was built anywhere else") | `latex-conventions.md` §4, "An authored preamble", added by #1170 itself; step 5 now cites §4 for it |
| step 8: "rather than a wall: the book has fifteen chapters" | `book-steps.md` §5, "Report the per-unit results as one table" (the fifteen-reports reason); step 8 keeps the instruction |
| step 9: the LuaLaTeX measurements (86 s against 26 s on 287 pages, `bibtex` abbreviating `Ö.` by byte, `bibtexu` by character) | `latex-conventions.md` §7, "Build the book with LuaLaTeX", added by #1170 itself; step 9 now cites §7 |
| step 9: "This check became load-bearing when the bibliography moved to the end of the book" | `latex-conventions.md` §7, "Why `book.log` is read before the PDF is believed" (#1170 put it in the LuaLaTeX paragraph; it now sits with the other log-check reason) |

The other move the plan names was #1158's (`17b282f4`): the #804
self-numbered chapter-title passage left step 9 for the conventions. It
is whole in `latex-conventions.md` §2.

## Where each removed paragraph went

`book-steps.md` is `.claude/skills-common/references/book-steps.md`;
`latex-conventions.md` is
`.claude/skills/book-assembler/references/latex-conventions.md`.

### Opening, routing, conventions

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "The last step of the book-scale track (`docs/WRITE-A-BOOK.md`), and deliberately the smallest" | stays as the opening sentence; "deliberately the smallest" cut as a description of the file's size, not a rule |
| 14 | "Read `docs/WRITE-A-BOOK.md` before the first run. This file is the procedure" | the opening names the doc; `book-steps.md` preamble says it is the track the procedure belongs to, with `docs/book/` |
| 17 | "## What this skill is not" and its five-row table | stays whole (routing with harness-suffixed skill names) |
| 27 | "**It writes no prose.** The only file it authors is the book document" | stays, now the opening guardrail paragraph with the brief's three guardrails beside it; "If you find yourself writing a sentence that will be read by the book's reader, you are in the wrong skill" goes to `book-steps.md` §4, "Composing writes no prose" |
| 34 | "Paths in this skill are from the project root" | stays, moved to the opening paragraph, before the first path |
| 37 | "The whole of the composition is one table: the outline" | the sentence stays in "Conventions as data", with a citation of §1, §3, §4 and §6; the list of what the reference holds is cut as a table of contents of a file whose sections now open with their own conditions; "A character the Unicode package does not map is fixed by the author" stays |

### Steps 1–5

| Old line | First words | Went to |
| --- | --- | --- |
| 51 | "1. **Confirm the outline is signed off.**" and its command | stays |
| 58 | "Non-zero means nobody approved this outline" | stays; what the outline sign-off covers is added in `book-steps.md` §2 (from `docs/book/SIGN-OFF.md`) |
| 63 | "2. **Confirm every unit is accepted and current.**" and its command | stays |
| 69 | "Report the table as it stands. A unit reading `unwritten`, `drafted` or `stale: ...` is not assemblable" | stays, now with "stop, and say which unit and why", which the routing table already required; why `stale: inputs changed` is the user's decision goes to `book-steps.md` §1 with the status table |
| 75 | "3. **Rebuild the registries and report every finding.**" and its commands | stays |
| 86 | "If `build` exits 1 on `[glossary]` bullets or `[notation]` symbol rows, **stop**" | stays; the same rule, neutral, in `book-steps.md` §3 |
| 91 | "`check` exits 0 whatever it finds -- it is a machine's reading of prose" | "exits 0 whatever it finds", printing every finding in full and the coverage line stay in one sentence; the Layer 4 reasoning, "what is guaranteed", the examples of findings and the coverage reason go to `book-steps.md` §3 |
| 101 | "4. **Convert each accepted unit to a fragment.** The default output directory is already the right one" | the command and "no `--output-dir`" stay; why the default directory is right goes to `latex-conventions.md` §1 |
| 113 | "With `{#index}`, add `--index-terms`" | stays |
| 116 | "**A unit's mathematics resolves per unit, and that is why this works.**" | "Never move or rename a unit's `.md`" stays in step 4; the per-unit `math.md`, the typewriter-text failure and the loud half go to `book-steps.md` §4, "A unit is found by its path", now citing `docs/writing-standards/mathematics.md` §12 |
| 126 | "`--fragment` is what makes it assemblable: no preamble" | `latex-conventions.md` §1, "What `--fragment` changes"; "A unit already drafted as `.tex` by `thesis-chapter-writer` needs no conversion" stays in step 4 |
| 136 | "Then add the outline's ids as labels" | the action (`\label{<unit-id>}` plus `\label{ch-NN}` right after the `\chapter`) stays; why pandoc's derived labels make it necessary goes to `latex-conventions.md` §1 |
| 141 | "5. **Compose the book.** Write `content/rendered/<book>/book.tex` and `content/rendered/<book>/book.md`" | stays; "That directory is assembly output, not authored material" goes to `book-steps.md` §4 |
| 149 | "The front matter, appendices and back matter go where the outline puts them, as the conventions say" | rewritten as above ("The four ... pointers") |
| 153 | "**Copy `content/specs/<book>/preamble.tex` beside `book.tex` if it exists**" | stays, with the §4 citation; "reporting its absence would read as a finding" is cut as a duplicate of §4 ("its absence is the ordinary case, not a finding"); the author sentence stays verbatim |

### Steps 6–10

| Old line | First words | Went to |
| --- | --- | --- |
| 162 | "6. **Run the gate on what you composed.** Every unit passed it already" | the title and command stay; why the composed document is gated goes to `book-steps.md` §5 |
| 170 | "A `FAIL` here is a failing test, not a warning." | stays |
| 174 | "7. **Run the prose check over the units, not the skeleton.**" | stays; "so scanning it would report nothing and mean nothing" goes to `book-steps.md` §5 |
| 182 | "Read `.claude/skills-common/references/prose-check.md` now and follow it: what the check can and cannot see" | the pointer stays; "what the check can and cannot see, and how to report what it finds" is cut as a description of `prose-check.md` (as in survey-writer) |
| 187 | "8. **Run the verbatim scan, per unit.** Assembly is the last moment" | stays |
| 196 | "The first command is not optional. The embedding tier compares each section" | "not optional" stays, with "a unit accepted weeks ago may have been revised since"; the embedding-tier reason is cut as a duplicate of `verbatim-scan.md`, "Why the section map is rebuilt first" |
| 200 | "**A review aid, not a gate: it is never a condition of presenting** -- a unit with findings is still an assembled unit" | the bold sentence and the pointer stay; "a unit with findings is still an assembled unit, and this step reports rather than withholds" goes to `book-steps.md` §5 |
| 208 | "Report the per-unit results as one table" | the instruction stays, now covering step 7 as well; the reason goes to `book-steps.md` §5 |
| 211 | "9. **Build the PDF, if the toolchain is there.**" and its commands | stays |
| 226 | "Tell the user the line `registry index` prints" | stays, with a citation of `latex-conventions.md` §9 |
| 229 | "**LuaLaTeX and `bibtexu`, the engine the pdf render uses**" | rewritten as above; the `book.blg` sentence stays |
| 234 | "**Four passes, and the `bibtexu` one is not optional.** The first `lualatex` records" | the title and the `[?]` consequence stay; what each pass does goes to `latex-conventions.md` §7 |
| 241 | "**Read `book.log` before believing the PDF.**" and its command | stays |
| 250 | "Anything but `[]` means a citekey did not reach the bibliography" | stays, with a citation of `latex-conventions.md` §5 |
| 253 | "**Then report any figure that landed on a float-only page.**" and its command | stays; "(#1065)" cut as history |
| 261 | "Tell the user every line it prints, as a finding about the figure" | stays; the 0.85-of-text-height reason and "`[]` means ... only if the skeleton loads that file" go to `latex-conventions.md` §6, "Figure placement" |
| 269 | "**A citekey containing `--` is the case worth knowing about.**" | `latex-conventions.md` §5, beside the paragraph on the copied `.bib` |
| 274 | "**Never run `draft gate` on a fragment.**" | "Never run `draft gate` on a fragment" stays in step 6, beside the gate it qualifies; why goes to `book-steps.md` §5; the "Python rather than `grep -c`" sentences, which belonged to the log check, go to `latex-conventions.md` §7 |
| 283 | "**Table numbers are the book's, not a unit's, and one thing can break them.**" | the measured numbering shapes go to `latex-conventions.md` §2; the collision and its routing go to `book-steps.md` §4; the `§13` citation stays in step 5 |
| 302 | the table-id `grep` | stays, moved into step 5, since it is a check "before composing" and step 5 is where composing starts |
| 306 | "Anything printed is a collision. The per-unit prose check reports the same defect" | "Anything printed is a collision" and the `draft-reviser` routing stay in step 5; the per-unit vs cross-unit reason goes to `book-steps.md` §4 |
| 310 | "**A captioned figure's number is the book's for the same reason**" | `latex-conventions.md` §2 (issue 411's `\label{fig:}`) and `book-steps.md` §4 (the collision) |
| 316 | the figure-id `grep` | stays, moved into step 5 |
| 320 | "Anything printed is a collision, whether or not every copy is captioned" | `book-steps.md` §4 (an uncaptioned marker counts, and `FigureNoCaption`); "since #421" cut as history |
| 328 | "**A numbered equation's number is the book's for the same reason**" | `latex-conventions.md` §2 (#457's `\label{eq:}`) and `book-steps.md` §4; "most equations across a book carry no id ... rarer than the table or figure one" is cut as a duplicate of `docs/writing-standards/mathematics.md` §12, "A number for a chosen few" |
| 337 | the equation-id `grep` | stays, moved into step 5 |
| 341 | "Anything printed is a collision. The per-unit prose check (`EquationDuplicateId`)" | as row 306 |
| 345 | "**If the units number their own *sections*, turn LaTeX's numbering off**" | `latex-conventions.md` §2, whole; step 9 keeps the condition, the citation and "renumbering the author's headings is `draft-reviser`'s call" |
| 357 | "Without TeX Live, say so plainly and stop there" | stays |
| 360 | "10. **Stop at the sign-off.**" | stays, now reading `book-steps.md` §2 again before presenting |
| 365 | "**Do not say the book is finished.** Nothing here has read the argument. Every check in this pipeline verifies" | the bold sentence and "nothing here has read the argument; that judgement is the user's, deliberately" stay; "Every check ... grounded, consistent and complete -- none of them verifies that it is any good" goes to `book-steps.md` §2 |

### What this skill does not write, and Sources

| Old line | First words | Went to |
| --- | --- | --- |
| 370 | "## What this skill does not write" (heading) | cut: the heading of the two paragraphs below |
| 372 | "**No dossier.** Every drafting skill writes one because it makes judgement calls" | `book-steps.md` §1, "The record of a book is these files" |
| 381 | "**No acronym vocabulary step**, for the same reason" | `book-steps.md` §1, same paragraph |
| 385 | "## Sources" and its paragraph | stays whole |

### Totals

- **56 rows**, one per paragraph, fence, table or heading of the old
  file. Two of them (149, 229) are pointer rewrites, detailed in "The
  four pointers" above, with the other two pointers inside rows 153
  and 345.
- **Stay, whole or in part: 30 rows** (a title, a command fence, a
  guardrail, the routing table, Sources, or the one sentence of a
  paragraph whose reasoning moved).
- **Moved: 32 rows** send text to `book-steps.md` (23) or
  `latex-conventions.md` (13); a row may name both.
- **Cut: 9 rows** cut some of their text, each with its reason: a
  duplicate of a named file and section, a description of a reference
  the pointer reaches, a heading, or history (an issue number). Four of
  them (37, 182, 196, 370) move nothing elsewhere, and none of those
  four was the only statement of a rule.
- **Without a destination: none.**

### What was added, not moved

Each step gained a one-line `Done when` (Decision 4) and each pointer a
condition. `latex-conventions.md` gained numbered sections, each opening
with when to read it; its text is otherwise the old file's, plus the
rows above, and its `WideCodeLine` link now points at
`docs/writing-standards/page.md` §14 directly. `book-steps.md` §1's
status table restates `docs/book/CHAPTERS.md`'s (the meanings) with a
"Composable" column, and §2's first sign-off restates what
`docs/book/SIGN-OFF.md` says the digest covers; neither is new behaviour.

## The shared reference, `book-steps.md`

Five sections, each cited with its condition, in the shape of
`genre-steps.md`: no skill name, no harness tool, no step number of any
caller and no command. book-assembler's commands stay in its `SKILL.md`.

| § | Title | Cited by book-assembler at |
| --- | --- | --- |
| 1 | The spec and the acceptance records | the opening (before step 1), and step 2 |
| 2 | The two human sign-offs | the opening (before step 1), and step 10 |
| 3 | Checking the registries before composing | step 3 |
| 4 | Composing from accepted units | step 5 |
| 5 | Gating what was composed | step 6 |

**What stayed with book-assembler**, because only a monograph composed
into LaTeX needs it: the composition table, the skeleton and its
macros, the reserved parts' LaTeX modes, the copyright page and an
authored preamble, the one bibliography, the preamble lines a fragment
leaves to the book, LuaLaTeX and `bibtexu`, the Glossary and List of
Symbols layout, and the index, all in `latex-conventions.md` §1–§9; and
every command, the routing table and the guardrails, in `SKILL.md`.

No citation sits inside steps 7 or 8 (the prose check and the verbatim
scan), so no spliced reference pushes their riders out of the windows
`tests/test_skill_style_check_step.py` and
`tests/test_skill_verbatim_scan_step.py` measure (Review focus 1).

## What book-assembler does not cite, and why

book-assembler writes no prose and drafts no unit. Its text says so in
the opening ("**It writes no prose.** The only files it authors are the
book document itself ... and its Markdown twin") and in the routing
table ("This skill composes what exists; it does not write"); every
wording change routes to `draft-reviser` and every missing unit to a
genre skill. So it cites no writing-standards genre file (there is no
`docs/writing-standards/genres/book.md` to write: a genre file holds
what a genre owes its reader and its reread checklist, and this skill
has no reader-facing text to reread), and it does not cite
`.claude/skills-common/references/mathematical-prose.md`, which is for a
skill that can write or edit mathematics. The only mathematics it
touches is a unit's `math.md` mapping, which it must never move
(`book-steps.md` §4); it names `docs/writing-standards/mathematics.md`
§12 there only for what that mapping is. Neither the old nor the new
`SKILL.md` names `docs/writing-standards/genres/` or
`mathematical-prose.md`.

## For #1157

The edited-volume skill #1157 plans (chapter authors, per-chapter
references, a List of Contributors) could cite `book-steps.md` as it
stands for:

- **§2, the two human sign-offs**: the outline before composing, the
  book after; neither is a monograph's alone.
- **§3, checking the registries**: the build-refuses rule and the
  print-every-finding guarantee hold for any book whose units have
  dossiers.
- **§5, gating what was composed**, with one exception below.

It would need to extend:

- **§1, the spec and the acceptance records**: an edited volume's
  outline carries a chapter author per chapter, and probably an editor
  in place of the book's single `- author:` line; who may accept a unit
  (the chapter's author, the editor, or both) is a question §1 answers
  only for one author. The status table itself carries over.
- **§4, composing from accepted units**: "The book's author comes from
  the outline" assumes one author; a volume adds per-chapter author
  lines and the List of Contributors, a generated page built from them.
  The id-collision and the never-rename rules carry over unchanged.
- **§5**: "the bibliography" is not mentioned in §5, so §5 carries over,
  but a volume with per-chapter references changes what its gate run on
  the composed document is checking; whether the composed document is
  gated once or per chapter is that skill's decision to add.

Nothing in `latex-conventions.md` is shared: a volume's LaTeX (per-chapter
bibliographies with `chapterbib` or `biblatex` `refsection`, an author
line under each `\chapter`) differs from a monograph's in exactly the
places that file covers, so it would keep its own.

## For the plan

What would have gone into `plans/1091-skill-shrink.md`, PR 6's row:

- PR 6 built on `feat-1091-book-assembler` at 6.173.10: 19,821 to
  13,923 bytes (largest copy), cap 20,000 to 14,000 with a reason;
  `book-steps.md` added; `latex-conventions.md` numbered §1–§9.
- **The plan's line numbers are right** for `cc65f47a`: `SKILL.md`
  at `9aa75085` and `cc65f47a` are the same file, so `:150`, `:158`,
  `:230` and `:354` still land one line from the text.
- **`:150` is a paragraph, not a step.** The plan calls it "a whole
  step"; it is a whole *paragraph* of step 5 holding only the pointer.
  It is the one with no command, so it was given the "not done until"
  and "come back with" treatment.
- **The plan's Task 5 lists for `genre-steps.md` do not name the file**:
  `docs/GENRE.md` ("What all eleven have in common") and `DEVELOPER.md`
  (the `.claude/skills-common/` row) list the shared references by what
  they hold, so `book-steps.md` was added as "the steps composing a book
  from accepted units takes" and "a book skill's shared steps".
- **The skeleton's comments name `latex-conventions.md` sections by
  title**, and one ("Numbering") named no heading before this PR; §2 is
  now titled "Numbering", so every comment lands.

## Bench

Claude Code only, skill-only prompt, 3 runs, `--jobs 3`, against the
"before" rows in `bench/results/2026-11-14-skill-bench-skill-only/`
(same host). The after rows are
`bench/results/2026-11-15-book-assembler-shrink/tier2.json`.
`--compare` exits 0, **pass**: every command row and the gate are equal,
3/3 to 3/3 or 0/3 to 0/3, and no run timed out or ran a forbidden
command.

| | Before | After |
| --- | ---: | ---: |
| Gate passed | 3/3 | 3/3 |
| `draft spec status`, `unit status`, `registry build`, `registry check`, `render`, `gate`, `style`, `dossier sections`, `review verbatim scan` | 3/3 each | 3/3 each |
| `draft registry index`, `review figure` (the outline has no `{#index}`; no figure to check) | 0/3 | 0/3 |
| Median run | 52 s | 48 s |

Every after run opened `book-steps.md`, `latex-conventions.md`,
`prose-check.md` and `verbatim-scan.md` (before: the last three), and
every one wrote `book.tex`, `book.md` and a built `book.pdf`. Two of the
three also ran `draft spec show`, which step 5 names for the author line
and the bench does not count as expected.
