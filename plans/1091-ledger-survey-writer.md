# Move ledger: survey-writer (#1198, SK-1)

Status: **built on `feat-1091-survey-writer`, above the 12,000 target,
which the owner accepted on 2026-11-14; step 10 cut to a pointer on
`feat-1091-critique-pointer`, 2026-11-15.** Written 2026-11-14 against `9cbaf678`
(6.173.0), for [plans/1091-skill-shrink.md](1091-skill-shrink.md) PR 1,
Task 3; the critique step's rows are in
["Step 10 behind its pointer"](#step-10-behind-its-pointer-2026-11-15) below.

**Written for** the reviewer of PR 1, and for whoever builds PRs 2–8,
which keep a ledger in this shape. **Assumed:** the plan's "Decisions"
and "Review focus", and [docs/HARNESS.md](../docs/HARNESS.md) on the
three `SKILL.md` copies.

Every paragraph removed from survey-writer's `SKILL.md` has one row
below: its first words, then where it went (file and section) or "cut"
with the reason. A row with no destination is a defect. Line references
are to the old `.claude` copy at `9cbaf678`; the `.agents` and
`.opencode` copies held the same paragraphs, differing only where
`tests/fixtures/skill_harness_phrases.toml` says, and changed the same
way.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/survey-writer/SKILL.md` | 31,779 | 14,087 |
| `.agents/skills/survey-writer/SKILL.md` | 31,783 | 14,091 |
| `.opencode/skills/survey-writer-opencode/SKILL.md` | 31,909 | 14,208 |

The cap in `tests/test_skill_size.py` falls from 32,000 to 15,000, with
its reason. **It stays above the 12,000 target.** Decision 1 sent that back to the
owner, who answered on 2026-11-14 that the cap is a guideline: the goal
is less duplication and better compliance, so nothing is compressed to
fit. What the 14 KB
holds, measured on the `.claude` copy:

- 1,075 bytes of frontmatter and title, which Decision 7 leaves alone;
- about 2,300 bytes of fenced commands and the table and marker
  examples, which Decision 2 keeps;
- 2,200 bytes for step 10 (the critique), whose commands were then
  inline by measurement (`docs/HARNESS.md`, "A pointer alone is not
  enough") and whose two qualifiers sat inside the windows
  `tests/test_skill_style_check_step.py` and
  `tests/test_skill_verbatim_scan_step.py` measure from each command
  (since cut to a pointer step of about 1,250 bytes: see
  ["Step 10 behind its pointer"](#step-10-behind-its-pointer-2026-11-15));
- 1,500 bytes for step 9 (the figure stub), which
  `tests/test_skill_figure_step.py` requires to hold without the drawer;
- about 1,200 bytes of project-root paths in pointers (each citation of
  `.claude/skills-common/references/genre-steps.md` is 50 bytes), and a
  one-line `Done when` on each of 19 steps.

## Pinned phrases: what the tests read

Built before the rewrite. "Raw" means the test reads `SKILL.md` as
written (whitespace collapsed at most), so the phrase cannot move into a
reference. "Expanded" means it reads `tests/skill_text.py`'s
`expanded()`, which splices each named reference in after its path, so
the phrase may live in the reference, provided it stays inside the
window measured from its anchor. Every phrase below is still present
after the rewrite; the suite is green on it.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_references.py` | "from the project root" no later than 250 characters after the first `.claude/skills…` path, all three copies | raw |
| `test_skill_references.py` | a `## Collection scoping` section naming `` `.claude/skills-common/references/collection-scoping.md` `` and "ledger --collections" | raw |
| `test_skill_references.py` | every named `.claude/skills…` path exists; the three copies cite the same `` `path` §N `` set; every cited section exists; every `## N.` of a reference is cited by some skill | raw |
| `test_skill_references.py` | no backticked skill name and no tool word (`` `Edit` ``, `` `Write` ``, `` `Read` ``, `` `apply_patch` ``, `` `task` `` …) in any reference | the references |
| `test_skill_harness_copies.py` | `survey_subagents`: "Dispatch one `general-purpose` subagent per sub-theme, all in one message, each told to" (Codex and OpenCode forms in the phrase map) | raw, all copies |
| `test_skill_harness_copies.py` | `critique_edit_tool`: "each edit with `Edit`" (and its two forms); every phrase-map entry used by every harness (`:140-144`) | raw, all copies |
| `test_skill_harness_copies.py` | "never a fabricated one" in the Codex copy (the description) | raw |
| `test_skill_harness_copies.py` | OpenCode copy: every backticked skill name suffixed `-opencode` | raw |
| `test_skill_figure_step.py` | "No citekey inside either figure file", `<!-- figure: figures/<name> -->`, `` `figure-drawer` ``, "kpsewhich tikz.sty", "compiles", "redrawn from a source" | raw |
| `test_skill_figure_step.py` | absent: the six `_RIDERS` ("Commit to a layout metaphor", "pre-flight defect list", "lettered sub-captions", "tikz@node@reset@hook", "as original as the ASCII", "chitragupta.figure sync") | raw |
| `test_skill_table_step.py` | `<!-- table:`, `<!-- tableref:`, "§13" | raw |
| `test_skill_acronym_step.py` | "acronyms.toml" or "acronym vocabulary" | raw |
| `test_skill_pregate_feedback_step.py` | the pointer `` `.claude/skills-common/references/critique.md` `` within 2,000 characters of "Critique against the evidence packet" | raw |
| `test_skill_pregate_feedback_step.py` | `verbatim scan`, `draft gate` and `verbatim recheck` commands within 5,900 characters of that anchor (since 2026-11-15 survey-writer is in `_POINTER_FORM`, and this applies only to the inline-form skills; see below) | raw |
| `test_skill_pregate_feedback_step.py` | within 5,900 of every anchor (since 2026-11-15: 6,800 for an inline-form skill; for survey-writer, in the step plus the whole reference): "evidence.md", "claim:", "at most three items", "no second critique pass", scan before gate before recheck, a `draft style`, "objective_delta", "90% of its own", "revisions.md", "Never write any of this to `rejected.md`", "`no evidence`", "cut the sentence", "never to re-point it", "declared queries are exhausted", "dossier status", "there is no declared list", "never a condition of presenting" | expanded |
| `test_skill_pregate_feedback_step.py` | the anchor phrase appears only in the five genre writers | expanded |
| `test_skill_style_check_step.py` | the pointer `` `.claude/skills-common/references/prose-check.md` `` within 1,400 characters after some `-m chitragupta.draft style` | raw |
| `test_skill_style_check_step.py` | "§9 marks decidable" and "fix none of them" within 1,400 characters after **every** `-m chitragupta.draft style` (frontmatter stripped) | expanded |
| `test_skill_verbatim_scan_step.py` | the pointer `` `.claude/skills-common/references/verbatim-scan.md` `` within 1,200 characters after some `-m chitragupta.review verbatim scan` | raw |
| `test_skill_verbatim_scan_step.py` | "genuine restatement is only detected where the embedding tier can run" within 2,000 characters after **every** scan command | expanded |
| `test_skill_verbatim_scan_step.py` | `dossier sections … --citekeys --write` followed within 200 characters by the scan, and "tiers_not_run" within 2,000 of it; "never a condition of presenting"; absent: "Offer the verbatim scan" | expanded |
| `test_skill_retrieval_logging.py` | `--log` within 220 characters of every `python -m chitragupta.draft retrieve search\|evidence`, in every `.md` under `.claude/` | raw, references too |
| `test_skill_size.py` | each copy at or under the cap; cap within 1,000 of the largest copy; a reason when above 12,000 | raw |
| `test_init.py` | `python -m chitragupta.draft` in the scaffolded `.claude` copy | raw |
| `test_install_remedies.py`, `test_pdf_requirement_wording.py` | no `scripts/install_full_pipeline.sh`, no "pandoc … pdflatex" requirement; now also over `.claude/skills-common/` (Task 1) | raw |
| `bench/skill_commands.py` `expected_commands` | the 19 commands below, from `SKILL.md` and the references it names | raw, references too |

What that left free to move, and the review-focus rule that bound where
citations go: **no citation sits inside steps 10, 15 or 16** (the
critique, the prose check and the verbatim scan), so no spliced
reference pushes a rider out of its window.

**Expected commands, before and after** (`bench/skill_commands.py`,
each harness's copy plus the references it names). The set is
unchanged on all three harnesses, 19 commands each; only the order of
first appearance moved, because the read-only rule now comes first and
the retrieval commands are no longer named in the corpus-layer bullets:

```text
draft gate, corpus ledger, draft dossier init, draft dossier outline,
review uncited, draft retrieve search, draft retrieve evidence,
draft dossier check-evidence, review synthesis, draft dossier sections,
draft dossier status, review verbatim scan, draft style,
review verbatim recheck, draft dossier stamp, draft dossier export,
draft references, draft render, draft evidence
```

## Where each removed paragraph went

`genre-steps.md` is `.claude/skills-common/references/genre-steps.md`;
`survey.md` is `.claude/skills/survey-writer/references/survey.md`;
`genres/survey.md` is `docs/writing-standards/genres/survey.md`.

### Header, corpus layer, collection scoping, dossier

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "Genre-specific drafting agent for survey-style output" | cut: restates the layer split `docs/ARCHITECTURE.md` "Layer 1" and "Layer 2" state; a one-sentence summary of what the skill drafts replaces it |
| 15 | "Shared corpus layer (read, don't regenerate)" (heading) | cut: the heading of the four bullets below |
| 17 | "`content/ledger.sqlite` -- per-citekey status" | `genre-steps.md` §1 |
| 18 | "`papers/bibliography.bib` (gitignored, per-host)" | `genre-steps.md` §1 |
| 20 | "`content/parsed/<citekey>.txt`" | `genre-steps.md` §1 |
| 21 | "`chitragupta/retrieval.py` -- `python -m chitragupta.draft retrieve search`" | `genre-steps.md` §1 (what each call returns); both commands stay in steps 1 and 2 |
| 27 | "Collection scoping (#195): draft from the shelf" (heading) | stays as "Collection scoping"; "(#195)" cut as history (Decision 4); the subtitle is `collection-scoping.md`'s own title |
| 36 | "Paths in this skill are from the project root" | stays, moved to the opening paragraph, before the first path |
| 49 | "The draft is only half of what this run produces" | `genre-steps.md` §2 |
| 55 | "`chitragupta/dossier/` owns that state" | `genre-steps.md` §2 |
| 61 | "**Read-only means read-only: never run `python -m chitragupta.corpus sync`" | the rule and both commands stay ("Before you start"); the write lock, the run time and "do not build an index" go to `genre-steps.md` §1 |
| 71 | "**If the ledger is empty, stop.**" | stays, with its command |
| 77 | "If it reports no items, or none with status `parsed`" | stays in one sentence with the remedy command; "Do not draft around it, do not sync, do not cite" goes to `genre-steps.md` §1 |

### When to invoke, prose standards, what a survey owes

| Old line | First words | Went to |
| --- | --- | --- |
| 86 | table row "User asks for a survey / lit review" | cut: the frontmatter description routes it (plan, Task 3) |
| 87–90 | table rows naming `thesis-chapter-writer`, `textbook-chapter-writer`, `tutorial-writer`, `draft-reviser` | stays, as one line under "When to invoke" naming the four (plan, Task 3); the heading stays because `docs/WRITING-STANDARDS.md` §5 names it |
| 91 | table row "Ledger is empty, or nothing is `parsed`" | cut: duplicate of "If the ledger is empty, stop" |
| 95 | "Follow `docs/WRITING-STANDARDS.md` for the cross-genre rules" | stays as one sentence; the list of rules it summarised is cut as a restatement of `docs/WRITING-STANDARDS.md` §1–§6; its attribution sentence becomes the link in "Prose standards" |
| 101 | "The genre-specific additions below layer on top of it" | cut: the index in `docs/WRITING-STANDARDS.md` (PR 0b) states the layering |
| 105 | "A survey's job is to **organize a field and locate the gaps**" | `genres/survey.md`, "What a survey owes its reader" |
| 108 | "**Drifting into a textbook chapter.**" | `genres/survey.md`, "What a survey owes its reader"; the skill name becomes "the textbook-chapter writer", since the routing line in `SKILL.md` names the skill |
| 112 | "**Drifting into an argument.**" | `genres/survey.md`, "What a survey owes its reader" |
| 117 | "Unlike the tutorial genre, **alternatives and options are the point**" | `genres/survey.md`, "What a survey owes its reader" |

### Steps 0–5

| Old line | First words | Went to |
| --- | --- | --- |
| 122 | "0. **Name the reader and the scope, and open the dossier.** Before searching, settle who" | title and command stay; the three example readers go to `genres/survey.md`; the scope statement and its exclusions go to `genre-steps.md` §3 |
| 134 | "**Settle `<slug>` with the user before running that.**" | `genre-steps.md` §3, with the generic `<topic>/<genre>.<ext>` example; "Settle `<slug>` with the user" stays |
| 144 | "Fill in `scope.md`'s **Reader**, **Covers**" | `genre-steps.md` §3; `Done when` names the three fields |
| 145 | "Settle the **dialect** with the reader in the same breath" | `genre-steps.md` §3 |
| 150 | "Read the acronym vocabulary too" | `genre-steps.md` §3; "the acronym vocabulary" stays in step 0's pointer |
| 154 | "`init` also stamps the corpus fingerprint" | `genre-steps.md` §3 |
| 159 | "**First, check whether the dossier has an `outline.md`** -- a human writes this file" | command stays; what the file holds goes to `genre-steps.md` §4 |
| 168 | "**If it exists and passes**, run each section's declared queries **verbatim**" | stays in one sentence, with its command; detail to `genre-steps.md` §4 |
| 176 | "Score and record evidence exactly as steps 2-3 describe" | `genre-steps.md` §4; `--origin extended` stays in step 1 |
| 183 | "**A `claim:` section is content to ground, not steer from.**" | `genre-steps.md` §4; `python -m chitragupta.review uncited` stays in step 1 |
| 193 | "**No `outline.md`, or it fails `--check`:** break the requested topic into 2-4 sub-themes" | stays, with its command |
| 200 | "Pull more candidates than you expect to use. This is a keyword-overlap ranker" | first sentence stays; the ranker caveat goes to `genre-steps.md` §1 |
| 205 | "`--log` records the call's size in the dossier's `retrieval.md`" | `genre-steps.md` §1; step 1's `Done when` keeps "each with `--log`" |
| 208 | "2. **Score every candidate yourself before it counts as evidence.** Read the full snippet" | title and the judgement in one sentence stay; the snippet size and PaperQA2 go to `genre-steps.md` §5 |
| 216 | "Where a snippet is not enough to decide on a source you are minded to keep" | stays, with its command |
| 223 | "Use it to be **more careful about something you are about to cite**" | `genre-steps.md` §5 |
| 229 | "**Record both outcomes in the dossier before you start drafting prose**" | stays in one sentence; the formats go to `genre-steps.md` §5 |
| 231 | "what survives, into `evidence.md` -- one `## \`citekey\`` block" | `genre-steps.md` §5 |
| 240 | "what doesn't, into `rejected.md` -- one table row per candidate" | `genre-steps.md` §5 |
| 245 | "The rejected list is the more valuable of the two" | `genre-steps.md` §5 |
| 250 | "Then run the advisory self-check, which flags a `claim:`" | command stays; what it flags goes to `genre-steps.md` §5 |
| 257 | "Two kinds of warning. `N blocks under one citekey`" | `genre-steps.md` §5 |
| 262 | "2a. **On a broad topic, put steps 1-2 behind a subagent.**" | stays: the dispatch sentence is the `survey_subagents` harness phrase |
| 267 | "**The packet itself is `claim:`/`quote:` shaped**" | `survey.md` §1 |
| 278 | "The reason is not parallelism" | `survey.md` §1 |
| 286 | "Skip this for a narrow topic with one sub-theme" | `survey.md` §1 |
| 288 | "3. **Reformulate and re-search if a sub-theme comes up thin.** A single query wording" | title stays; body to `genre-steps.md` §6 |
| 295 | "4. **Cluster by judgment.** With a small corpus there's no BERTopic step" | stays |
| 298 | "5. **Check for disagreement across sources before writing.** If two kept pieces" | title stays; body to `genre-steps.md` §6 |

### Steps 6–9

| Old line | First words | Went to |
| --- | --- | --- |
| 303 | "6. **Draft**, in Markdown, using Pandoc-style citations" | stays |
| 305 | "Framing paragraph for the overall topic" | stays, in step 6's list sentence |
| 306 | "One subsection per theme, citing the papers that actually support each claim" | stays, in step 6's list sentence ("citing only from `evidence.md`") |
| 307 | "A comparison table: columns for approach/paper, citekey, core idea, stated limitations. **It carries a caption and an id**" | the caption-and-id sentence and §13 stay; the columns are the fence's header and `survey.md` §2; "the one it was written for" goes to `survey.md` §2 |
| 312 | the table fence | stays |
| 321 | "Refer to it with an inline `<!-- tableref: start-here -->`" | the marker stays; "never write the number yourself, and never write the word Table" is cut, duplicate of `docs/writing-standards/tables.md` §13 ("you write neither the word "Table" nor a number") |
| 325 | "Introduce the table before it appears" | cut: duplicate of `tables.md` §13, "The sentence that reads the table", which `survey.md` §2 points at |
| 327 | "A comparison nobody reads aloud is a table the reader has to interpret unaided" | cut: duplicate of `tables.md` §13 ("a table dropped into a section with neither a lead-in nor a reading is work handed to the reader") |
| 329 | "A gap-analysis paragraph: what the retrieved corpus does *not* cover" | "a gap-analysis paragraph" stays; what it holds goes to `survey.md` §2 |
| 332 | "**Every body paragraph closes on two or more citekeys wherever the evidence allows.**" | the rule, the `<!-- single-source: -->` marker, §11 and the `review synthesis` command stay |
| 333 | "A paragraph fusing three papers cannot be a transcription" | cut: duplicate of `docs/WRITING-STANDARDS.md` §11's opening paragraph |
| 335 | "Organise a paragraph around what its sources agree and disagree about" | `survey.md` §2 |
| 342 | "7. **Never write a citekey you didn't get from a retrieval result.**" | stays |
| 347 | "8. **Map sections to citekeys.** Save the draft" | stays, with its command |
| 355 | "It joins each heading's line range to the citekeys cited inside it" | what `sections.md` is for goes to `genre-steps.md` §2; "Drop `--write` to see the table first" is cut as a restatement of `dossier sections --help`; the stderr rule stays |
| 362 | "9. **Add a figure only for what the table can't express.** Place it beside" | title and "absence is the default" stay; placement and rarity go to `genres/survey.md`, "Figures are the rarest of any genre" |
| 369 | "On the rare occasion one is warranted, it is a **pair of files**" | stays, citing `docs/writing-standards/figures.md` §10 |
| 374 | the `<!-- figure: figures/<name> -->` fence | stays |
| 378 | "Write both `content/drafts/<topic>/figures/<name>.tex`" | the pair stays; how the renderer swaps the marker per format, and why that suits a paper, is cut as a duplicate of `figures.md` §10, "Every figure has two forms" |
| 386 | "Hand the drawing itself to `figure-drawer`" | stays; the list of what the drawer owns is cut as a duplicate of `figure-drawer`'s own `SKILL.md` |
| 392 | "**A topic directory is required.**" | stays; where flat-draft figures land goes to `genre-steps.md` §3 |
| 397 | "**Check for TikZ, and that the figure compiles.**" | stays |
| 404 | "**No citekey inside either figure file.**" | the guardrail stays; why, and "this genre is most likely to want one", go to `genres/survey.md`, "Figures are the rarest of any genre" |
| 411 | "**Nothing redrawn from a source.**" | the guardrail stays; the taxonomy example goes to `genres/survey.md` |
| 414 | "**A caption, if this figure warrants one, goes in the draft**" | the caption line and `figureref` marker stay; no number, no word "Figure" and `FigureNoCaption` (with "since #421") are cut as a duplicate of `figures.md` §10, "A caption, and no number you write yourself" |
| 422 | "**Any quantity in the prose follows `docs/WRITING-STANDARDS.md` §12**" | the pointer stays, now to `docs/writing-standards/mathematics.md` §12; the code-span and `math.md` rule is cut as a duplicate of §12; "a survey rarely has much" goes to `genres/survey.md`, "Mathematics: rare, and mostly unnumbered" |
| 429 | "**Most of that math stays unnumbered.**" | the two markers stay; when to number goes to `genres/survey.md`; "never number it yourself" and `EquationUnreferenced` are cut as a duplicate of `mathematics.md` §12, "A number for a chosen few" |

### Steps 10–18 (now 10–17), and Sources

| Old line | First words | Went to |
| --- | --- | --- |
| 443 | "10. **Critique against the evidence packet, before gating.**" | stays |
| 449 | "This is one inline judgement call" | stays; "nothing in this pipeline scores this automatically" is cut as a duplicate of `critique.md`'s opening ("What decides whether an edit is kept is the external count below") |
| 453 | "**Run this step: it is never a condition of presenting**" | stays |
| 459 | "1. Where the dossier has an `outline.md`" | stays |
| 466 | "2. Take the baseline" | stays, with the `tiers_not_run` caveat; its `style` qualifier ("its count is a proxy for a new defect, not a work list") is cut as a duplicate of `critique.md` "The baseline" and of item 3's qualifier, which the window test still finds within 1,400 characters |
| 480 | "3. Repair at most three items" | stays |
| 494 | "4. Log every attempt" | stays |
| 496 | "If nothing on the list clears the bar, or the list was empty" | cut: duplicate of `critique.md`'s closing paragraph; the step's `Done when` keeps it |
| 498 | "11. **Gate before presenting.**" | stays |
| 508 | "12. **Build the References section.**" | stays |
| 512 | "13. **Render tex, pdf and md, then the evidence sidecar.**" | stays |
| 515 | "**A survey emits one.** This genre is the natural fit" | `survey.md` §3 |
| 518 | "14. **Read it once as the reader**" | merged into step 14, "Read it once as the reader, and record any steering"; the checklist goes to `genres/survey.md`, "The reread" |
| 523 | "15. **Record any steering.**" | merged into step 14; the examples and why go to `genre-steps.md` §2 |
| 528 | "16. **Run the prose check.**" | now step 15, otherwise stays; "what the check can and cannot see, and how to report what it finds" is cut as a description of `prose-check.md`, which the pointer reaches |
| 539 | "17. **Run the verbatim scan.**" | now step 16; "a section map written ten steps ago" is cut as a duplicate of `verbatim-scan.md`, "Why the section map is rebuilt first"; "what to show, what the scan could not check" is cut as a description of that file |
| 556 | "18. **Stamp the draft fingerprint, then present.** Nothing edits the draft's text after this point" | now step 17; why goes to `genre-steps.md` §7; "(#454)" cut as history |
| 564 | "Then present the draft plus a one-paragraph summary" | `genre-steps.md` §7; the `draft-reviser` handoff and the `dossier export` command stay |
| 574 | "## Sources" (heading) | cut: the link moves to "Prose standards" |
| 576 | "The prose standards this skill inherits are not original" | `survey.md` §4 |
| 578 | "Full citations, licences and a per-principle attribution table" | the link stays, in "Prose standards"; the licence sentence goes to `survey.md` §4 |
| 582 | "What bears on *this* genre specifically" | `survey.md` §4 |
| 584 | "**Last, *Technical Writing Essentials***" | `survey.md` §4 |
| 588 | "**Google, *Technical Writing Courses***" | `survey.md` §4 |
| 592 | "**Procida, *Diátaxis***" | `survey.md` §4 |

### Totals

- **103 rows**, one per paragraph, list item, table row or fence of the
  old file.
- **Stay whole: 25** (a title, a command, a guardrail or a marker the
  tests read), some reworded into the step's one judgement sentence.
- **Moved: 59 rows** send text to `genre-steps.md` (35), `survey.md` (14)
  or `genres/survey.md` (11); a row may name two files.
- **Cut: 24 rows** cut some or all of their text, each with its reason:
  a duplicate of a named file and section, a restatement of `--help`, a
  description of a reference the pointer reaches, or history (an issue
  number). 19 of them move nothing elsewhere.
- **Without a destination: none.**

### What was added, not moved

Each step gained a one-line `Done when` (Decision 4), and each pointer a
condition for reading it. `genre-steps.md` §1 states that every retrieval
call is logged and why, which the old text said only in step 1, and §2
holds the old step 8's purpose sentence. Nothing else in the three new
files is new text: each sentence there is one of the rows above,
generalised where it is shared (`<topic>/<genre>.<ext>` for the slug
example; "the revision skill the step names" for `draft-reviser`).

## If SK-0c chooses handoffs

**It did not.** SK-0c measured a skill handoff against an `.md` pointer
and kept the pointers (plans/1091-skill-shrink.md, PR 0c, decided
2026-11-15), so nothing below is planned. It is kept as the record of
what a handoff would have moved. Had it chosen handoffs, these pointers
in the new survey-writer would have become handoffs, and this is what
would have moved with each. Every one of these sections and files was
written to be lifted out whole: each opens with its own condition and
names no step number.

| Step | Pointer today | What would move into the skill | What would have to stay, and why |
| --- | --- | --- | --- |
| 0 | `genre-steps.md` §3 (opening the dossier) | §3 whole, plus `python -m chitragupta.draft dossier init <draft> --genre <genre>` and settling the slug with the user | §2 (why a dossier) stays a reference; `--genre survey` becomes an argument; `tests/test_skill_acronym_step.py` reads "acronym vocabulary" from each genre's raw `SKILL.md`, so it would need to read the handed-off skill instead |
| 10 | `critique.md` | the whole repair loop, and the inline outline of its commands | the step's anchor "Critique against the evidence packet", its opening judgement and "never a condition of presenting"; `tests/test_skill_pregate_feedback_step.py` then required `scan`, `gate` and `recheck` in the raw step text, which was measured (`docs/HARNESS.md`), so the handoff would need its own measurement first. SK-0c measured it, and the step is now a pointer (below) |
| 12, 13 | `render-and-references.md` §1–§3 | the references, render and sidecar commands, which already live only there | the formats a survey renders (tex, pdf, md; sidecar pdf and md) as arguments; `survey.md` §3 stays |
| 15 | `prose-check.md` | the `python -m chitragupta.draft style` command and the report rules | the `draft-reviser` routing sentence (a reference names no skill); the window `tests/test_skill_style_check_step.py` measures from the command |
| 16 | `verbatim-scan.md` | the section-map rebuild, the scan, and the report rules | the `agenda-reviser` routing sentence; the regeneration-then-scan pair `tests/test_skill_verbatim_scan_step.py` anchors on |
| 17 | `genre-steps.md` §7 (stamping and handing over) | §7 whole, plus `dossier stamp` and `dossier export` | the `draft-reviser` handoff named in the presenting sentence, which differs per harness (`-opencode`) |

Steps 1, 2, 3, 5 and 6 point at `genre-steps.md` §1, §4, §5 and §6 and at
`survey.md` §1 and §2: judgement, not procedure, so they stay pointers
either way.

## Step 10 behind its pointer (2026-11-15)

Built from `cc65f47a` (6.173.3). SK-0c measured a pointer step that says
the step is not done until the loop has run, and it held as well as the
inline step, in 12 of 12 Claude Code runs (plans/1091-skill-shrink.md,
PR 0c, "Result"). The owner then decided that the critique loop's
commands may move behind its pointer in the four genre writers and
deep-research, one PR each, benched. This is survey-writer's.

| File | Before | After |
| --- | ---: | ---: |
| `.claude/skills/survey-writer/SKILL.md` | 14,087 | 13,129 |
| `.agents/skills/survey-writer/SKILL.md` | 14,091 | 13,133 |
| `.opencode/skills/survey-writer-opencode/SKILL.md` | 14,208 | 13,250 |
| `.claude/skills-common/references/critique.md` | 5,090 | 6,955 |

The cap falls from 15,000 to 14,000, still above the 12,000 target, with
its reason. `critique.md` grew because it is now the loop itself, read by
all five callers: numbered steps, a `Done when` on each, and a closing
step that returns to the caller. The other four callers keep their
inline outline until their own PRs, and the reference reads correctly
for them too. It names no skill, no tool and no caller's step number,
says "the tool the step that sent you names" for the edit, and opens
"before listing anything", which is what all five steps already said.

### Pinned phrases that changed

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_pregate_feedback_step.py` | `_POINTER_FORM = {"survey-writer"}`: the step, from its anchor to the end of its `Done when` sentence, names `` `.claude/skills-common/references/critique.md` ``, carries "not done until the loop the reference describes has run", and holds no `-m chitragupta` command | raw |
| `test_skill_pregate_feedback_step.py` | the reference holds `dossier status`, `dossier sections <draft> --citekeys --write`, `verbatim scan`, `draft style`, `draft gate` and `verbatim recheck`, in that order | the reference |
| `test_skill_pregate_feedback_step.py` | for a pointer-form skill, every rider of the table above is found in the step plus the whole reference; for an inline-form skill, within 6,800 characters (was 5,900) of every anchor, because the reference's "Never write any of this to `rejected.md`" now sits 6,398 characters from deep-research's anchor | raw step plus reference; expanded |
| `test_skill_harness_copies.py` | `critique_edit_tool` stays, inside "make each edit with `Edit`" and its two other forms | raw, all copies |
| `test_skill_style_check_step.py`, `test_skill_verbatim_scan_step.py` | unchanged: every `draft style` and `verbatim scan` in the reference still has its qualifiers within 1,400 and 2,000 characters, and step 10 names no command of its own | expanded |

### Where step 10's text went

Old lines are the `.claude` copy at `cc65f47a`.

| Old line | First words | Went to |
| --- | --- | --- |
| 201 | "10. **Critique against the evidence packet, before gating.** Read the dossier's `evidence.md`" | stays: the title and the survey's listing paragraph. "This step runs on every survey, once the draft is written and before step 11's gate" is added, saying when it runs |
| 206 | "One inline judgement call: not a subagent dispatch" | stays; also in `critique.md` step 2, with "nothing in this pipeline scores this automatically" |
| 209 | "**Run this step: it is never a condition of presenting, but it is not done until you have run its commands.**" | "never a condition of presenting" stays; "not done until you have run its commands" becomes "not done until the loop the reference describes has run", the sentence SK-0c measured |
| 210 | "Read `.claude/skills-common/references/critique.md` now, before listing anything, and work it through with" | stays, as "follow it with `content/drafts/<slug>.md` as `<draft>`"; "In outline:" is cut, since the step no longer outlines the loop |
| 215 | "1. Where the dossier has an `outline.md`, read what the corpus could not answer" and its `dossier status` fence | `critique.md` step 1, which already held both |
| 222 | "2. Take the baseline" and its three-command fence | `critique.md` step 3, which already held them |
| 230 | "If the scan's `tiers_not_run` is not empty, quote the reason" | `critique.md` step 3, which already held it; the step asks for the reason back ("the scan's `tiers_not_run` reason if it gave one"), and `critique.md` step 6 returns it |
| 233 | "3. Repair at most three items, each edit with `Edit`, inside that section only" | `critique.md` step 4, substeps 1, 2 and 4; "each edit with `Edit`" stays in the step as "make each edit with `Edit`", the `critique_edit_tool` phrase; "at most three repairs" stays in the not-done-until sentence |
| 237 | the `gate`, `verbatim recheck` and `style` fence | `critique.md` step 4, substep 3, which already held it |
| 244 | "Read `style`'s count only as a number" | `critique.md` step 4, substep 3, which already held it |
| 247 | "4. Log every attempt, kept or reverted, in the dossier's `revisions.md`" | `critique.md` step 4, substep 5; the step keeps "each checked and logged in the dossier's `revisions.md`" |
| 249 | "Done when every attempt is logged, or you have said that nothing cleared the bar." | stays, as "Done when the loop has returned and every attempt is logged, or you have said that nothing cleared the bar"; the step adds what to come back with, which `critique.md` step 6 returns |

**Totals for step 10:** 12 rows. Stay: 5 (the title and listing, the
judgement call, the presenting clause, the pointer and the `Done when`),
four of them reworded or extended. Moved to `critique.md`: 7, each a duplicate of
text the reference already held. Cut with nothing moved: "In outline:"
alone. Without a destination: none.

### What `critique.md` gained, and from where

Its four `##` sections became numbered steps: "A sub-theme the corpus
could not answer" is step 1, "The baseline" step 3, "The repairs" step
4, and "Then report exhaustion, and carry on" steps 5 and 6. Nothing in
them was cut. Added, each from a caller's step:

- in the opening, "before listing anything" (all five steps say it; the
  old text said "once you have the prioritised list"), "which prose to
  read against the evidence", and "this loop is never a condition of
  presenting";
- step 2, the listing: the three kinds of gap every genre's listing
  paragraph names, the judgement-call sentence, and adding each sentence
  step 1 found resting on a `no evidence` sub-theme to the list, which
  step 1's "cut inside the same accept-or-revert cycle" already implied.
  Which prose to read stays with each genre;
- a `Done when` on each step, "If the list is empty there is nothing to
  repair", and a note in step 1 that step 5 reads the same block;
- step 6, what to return with (the list, each repair, the
  `tiers_not_run` reason, the exhaustion sentence), from the "Come back
  with" sentence of survey-writer's step in the SK-0c pointer arm.

### The bench

Claude Code only, skill-only, 6 runs an arm, 6 at a time, each capped
at 3600 seconds, `PYTHONPATH` unset. Rows in
`bench/results/2026-11-15-survey-writer-critique-pointer/`: `inline.json`
is 6 runs of `main`'s survey-writer (`cc65f47a`) on the same host the
same day, `pointer.json` this branch, and `pointer-outline.json` this
branch with `--outline`, compared against SK-0c's
`2026-11-14-skill-handoff-experiment/inline-outline.json`. Counted by
hand from each run's transcript and project:

| | Inline | Pointer | Inline, outline (SK-0c) | Pointer, outline |
| --- | ---: | ---: | ---: | ---: |
| Usable runs, none timed out, gate passed | 6 | 6 | 6 | 6 |
| Opened `critique.md` | 6 | 6 | 6 | 6 |
| `revisions.md` has a critique entry | 6 | 6 | 6 | 6 |
| `review verbatim recheck` ran | 6 | 6 | 6 | 6 |
| Baseline scan (`--write`) before the first recheck | 6 | 6 | 6 | 6 |
| `draft dossier status` at or before the baseline scan | 4 | 1 | 6 | 6 |
| Median run | 319 s | 340 s | 334 s | 332 s |

**Without an outline `--compare` exits 1**, on `draft dossier status`
alone (5 of 6 runs to 1 of 6). That command is conditional: the loop
runs it only "where the dossier has an `outline.md`", and none of these
dossiers had one. The pointer runs skipped it as the loop says to, and
three of them wrote "no outline.md, so no declared queries to exhaust"
in `revisions.md`; the inline step's outline put the command in front of
the model whether or not it applied. SK-0c's pointer arm showed the same
drop (4 of 6). **With `--outline`, which makes the command required,
`--compare` exits 0** and every run ran it before the baseline scan.
So the command was not put back inline: the drop is a skipped step that
did not apply, not a lost one.

### For the plan

`plans/1091-skill-shrink.md` is not edited on this branch. What it
should say:

**Decision 2, replacement text:**

```markdown
2. **Commands stay in `SKILL.md`** (#1091 item 3): every
   `python -m chitragupta...` line, every marker a draft must carry, and
   every phrase a test reads from the raw file. Output samples (the
   `text` fences in thesis step 9) may move. **Two steps are measured
   exceptions**, whose commands live in a shared reference behind a
   pointer: the render step (`render-and-references.md`, measured
   2026-10-30 to 11-02), and the critique loop (`critique.md`), decided
   2026-11-15 on PR 0c's result for the four genre writers and
   deep-research. A critique step moves in its own skill's PR, benched
   for that skill. Its pointer says the step is not done until the loop
   the reference describes has run, and
   `tests/test_skill_pregate_feedback_step.py`'s `_POINTER_FORM` lists
   the skills that have moved. survey-writer moved first.
```

**Global constraint "A shared reference names no step number and
contains no command", replacement text:**

```markdown
- A shared reference names no skill, no harness tool and no step
  number of a step that points at it. A reference that holds a
  procedure numbers its own steps, ends each on a `Done when`, and
  returns to the step that sent the reader. A command a step requires
  stays in that step's `SKILL.md`, except in the steps Decision 2
  names; a reference may also repeat a command its caller carries.
```

The old sentence was already untrue on `main` before this branch:
`render-and-references.md` holds six commands, and `prose-check.md`,
`verbatim-scan.md`, `collection-scoping.md`, `digest-copying.md` and
`figures-tables-equations.md` one or two each, besides `critique.md`'s
seven.

**Review focus 1** should read 6,800 where it says 5,900, and add that
a pointer-form critique step is read whole, the step and then the
reference, so a spliced reference cannot push its riders out of a
window.

**PR 2 and PR 8** each convert their skills' critique steps the same
way: move the skill into `_POINTER_FORM`, replace the inline outline
with the pointer step, record the rows in that skill's own ledger, and
bench that skill against a fresh before arm, with `--outline` too where
its task takes one.
