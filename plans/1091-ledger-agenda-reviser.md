# Move ledger: agenda-reviser (#1202, SK-5)

Status: **built on `feat-1091-agenda-reviser`, above the 8,000 target,
with a reason in its cap row.** Written 2026-11-15 on top of
`feat-1091-draft-reviser` (SK-4, not yet merged), for
[plans/1091-skill-shrink.md](1091-skill-shrink.md), the PR 5 row of
"PRs 3-8, in outline".

**Written for** the reviewer of PR 5. **Assumed:** the plan's
"Decisions" and "Review focus", and
[plans/1091-ledger-draft-reviser.md](1091-ledger-draft-reviser.md),
whose section "For SK-5 and SK-7" lists what of draft-reviser this skill
may rely on, and whose shape this follows.

Every paragraph removed from agenda-reviser's `SKILL.md` has one row
below: its first words, then where it went (file and section) or "cut"
with the reason. A row with no destination is a defect. Line references
are to the old `.claude` copy at `cc8856ac` (the SK-4 branch head); the
`.agents` and `.opencode` copies held the same paragraphs, differing only
where `tests/fixtures/skill_harness_phrases.toml` says, and changed the
same way.

## What this skill relies on in draft-reviser

Only what the SK-4 ledger guarantees: the path
`<harness>/skills/draft-reviser/SKILL.md` (`skill_path_draft_reviser`),
the heading `## The loop`, its steps 1, 3, 4, 5, 6 and 7 by number and
by what they hold, the unnumbered "prose check", "verbatim scan" and
"Show what changed" steps, `## When there is no dossier`, and
`references/draft-diff.md`. The old file named four parts of the loop
and then restated each of them with its own edits layered on; the new
one names the same four parts once (the `agenda_loop_edit` sentence,
unchanged) and adds a table mapping each draft-reviser step onto this
loop, saying how it differs:

| draft-reviser step | Here |
| --- | --- |
| 1 (`scope.md`, `steering.md`, `mark-revision`) | step 1, after `dossier export`; label `agenda remediation` |
| 3 (map onto sections) | step 4, the owning section only |
| 4 (search) | never |
| 5 (edit in place) | step 4, the exact span |
| 6 (write the dossier back) | step 6, `revisions.md` only (R1) |
| 7 (gate, references, render, stamp) | step 5's gate after every repair; no `references`, no `render`, never `dossier stamp` |
| the three unnumbered steps | the prose check is refreshed by every `--baseline` cycle (step 5); the scan and the diff are step 7 |

No draft-reviser text was copied into a reference: the pointer is a
routing sentence between skills and stays in `SKILL.md`, one path per
harness.

## Who cites this skill's text

Grepped over all three harness folders, `docs/`, `bench/`,
`chitragupta/`, `tests/` and `scripts/`. Every site still resolves.

| Site | What it cites |
| --- | --- |
| `tests/test_skill_references.py:112-114` | `### 4. Repair one item`, naming the three repair references before the next heading |
| `tests/test_review_agenda.py:1690-1695` | "stale_spans", "refused as stale", "R12" in `SKILL.md` |
| `tests/test_skill_style_check_step.py:95`, `:154` | agenda-reviser exempt from the prose-check pointer and "fix none of them"; "§9 marks decidable" still within 1,400 characters of `-m chitragupta.draft style` |
| `tests/test_skill_verbatim_scan_step.py` | the regeneration-then-scan fence, the `verbatim-scan.md` pointer, the caveat, `tiers_not_run`, "never a condition of presenting" |
| `tests/test_skill_pregate_feedback_step.py:80`, `:132` | agenda-reviser excluded; a comment names "agenda-reviser's own step 6" (logging), still step 6 |
| `bench/skill_bench_tasks.py:405-419` | the task: "the closing full-format agenda run and the draft diff as a pdf", both still in step 7 |
| `docs/GENRE.md:357-400`, `docs/AGENDA.md`, `docs/AUTO-IMPROVEMENT.md` §3 | the skill's behaviour, not its text; every claim there still holds |

Step numbers 1-7 and the headings of steps 1-6 are unchanged. Step 7's
heading changed from `### 7. Present` to `### 7. Close the pass and
present`, and the three unnumbered sections after it (`### Prose is now
this skill's work, not merely surfaced`, `### Run the verbatim scan`,
`### Close the pass with one full-format run`) are gone, folded into
steps 4, 5 and 7. No file outside `plans/` cited any of them
(`plans/f3-agenda-reviser.md:627` names "Close the pass with one
full-format run" as a design item, not a heading).
`## What may be repaired unattended, and what may not` is now
`## What may be repaired unattended`, and `## Sources` is gone; nothing
cited either.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/agenda-reviser/SKILL.md` | 28,097 | 18,121 |
| `.agents/skills/agenda-reviser/SKILL.md` | 28,172 | 18,196 |
| `.opencode/skills/agenda-reviser-opencode/SKILL.md` | 28,205 | 18,193 |

The cap in `tests/test_skill_size.py` falls from 29,000 to 18,500, with
its reason. **It stays well above the 8,000 target.** What this file
must hold, per the brief, is every guardrail of an unattended repair
loop beside its command, and that is most of the file:

- 1,000 bytes of frontmatter (Decision 7);
- about 900 bytes of fenced commands: export, mark-revision, the bare
  agenda (three uses: baseline, stale-span read, re-file), `--baseline`,
  `draft style`, the section rebuild and scan, the closing agenda run,
  the diff;
- step 5, about 3,700 bytes: the R4 cycle, the sync refusal, the
  `not_refreshed` and `refresh_errors` handling, the five acceptance
  conditions, the re-file before a retry, two attempts, the
  strictly-falls terminator and `pass_bound`. Every sentence there is a
  guardrail a skipped step would break silently, and no run reaches only
  part of it, so nothing went behind a pointer;
- the stale-span refusal (R12) and its two consequences, in step 4;
- the eleven guardrails, each with its positive target (about 2,000
  bytes);
- the class table and the surfaced classes, which every run's triage
  reads;
- the tested phrases below.

What did move was duplication: of draft-reviser's loop (now a mapping
table), of `verbatim-scan.md`, of `docs/AGENDA.md`, of the repair
references themselves, and history (decision and issue numbers).

## `mathematical-prose.md`: not cited

**Decision: do not cite it.** That reference governs the sentences that
introduce a symbol, a condition or a derivation. This skill never writes
one: every repair is a rewording of a short shared run, an attribution,
a marker removal, a caption or reference marker, or (for
`EquationUnreferenced`) one sentence naming an equation by its id, and
"never add a claim" binds all of them. Its one contact with mathematics
is a check, not writing: a repaired quantity must still match `math.md`
(`docs/writing-standards/mathematics.md` §12), which stays inline in step
5's acceptance list and reverts a repair that breaks the mapping. If a
short run ever spans a symbol's defining sentence, that check is what
catches it. A person who wants mathematics rewritten is sent to
draft-reviser, which cites the reference behind a condition.

## Pinned phrases: what the tests read

"Raw" means the test reads `SKILL.md` as written (whitespace collapsed
at most); "expanded" means `tests/skill_text.py`'s `expanded()`. Every
phrase is still present; the suite is green on it.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_harness_copies.py` | `skill_path_draft_reviser`, `agenda_edit_payload`, `agenda_loop_edit`, `agenda_remove_marker`, `agenda_edit_span`, `agenda_old_string`, `never_rewrite_draft`, in all three copies | raw |
| `test_skill_harness_copies.py` | OpenCode copy: every backticked skill name suffixed `-opencode`; no foreign tool word | raw |
| `test_skill_references.py` | "from the project root" no later than 250 characters after the first `.claude/skills…` path | raw |
| `test_skill_references.py` | `### 4. Repair one item` names `repair-missing-citekey.md`, `repair-prose.md`, `repair-verbatim-run.md` before the next heading | raw |
| `test_skill_references.py` | every named path exists; no backticked skill name or tool word in a reference | raw, references |
| `test_review_agenda.py` | "stale_spans", "refused as stale" (step 6 and the guardrail), "R12" | raw |
| `test_skill_style_check_step.py` | `-m chitragupta.draft style` present; "§9 marks decidable" within 1,400 after it | expanded |
| `test_skill_verbatim_scan_step.py` | the scan present; `dossier sections … --citekeys --write` then the scan within 200; the `verbatim-scan.md` pointer within 1,200; "genuine restatement is only detected where the embedding tier can run" within 2,000 of the scan and "tiers_not_run" within 2,000 of the rebuild (both from the spliced `verbatim-scan.md`); "never a condition of presenting"; absent: "Offer the verbatim scan" | raw / expanded |
| `test_skill_pregate_feedback_step.py` | absent: "Critique against the evidence packet" | expanded |
| `test_skill_size.py` | each copy under the cap; cap within 1,000 of the largest copy; a reason above 8,000 | raw |
| `bench/skill_commands.py` `expected_commands` | the 19 commands below, from `SKILL.md`, draft-reviser's `SKILL.md`, and the references they name | raw, references too |

**Expected commands, before and after**, all three harnesses, 19 each,
the same set (only the order of `draft style`, `review verbatim scan`
and `draft diff` changed, as step 7 now runs the diff last):

```text
review agenda, draft gate, draft dossier export, draft dossier
mark-revision, draft dossier list, draft dossier sections, draft style,
review verbatim scan, draft diff, draft figures, draft dossier status,
draft dossier prune, draft retrieve search, draft retrieve evidence,
draft references, draft render, draft dossier stamp, draft dossier
snapshot, draft dossier versions
```

## Where each removed paragraph went

`SKILL.md` below means the new agenda-reviser `SKILL.md`; the three
repair references are `references/repair-*.md` in this skill's folder.

### Header and When to invoke

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "`python -m chitragupta.review agenda <draft>` merges every review aid's own report" | stays, shortened, as the opening paragraph; the list of eight aids cut as a duplicate of `docs/AGENDA.md` ("Section by section", `## Sources`); the per-class unattended list cut as a duplicate of the class table below it; "That is the tedious half, and the half that gets skipped" cut as rationale (`docs/AUTO-IMPROVEMENT-RATIONALE.md`, "The gap") |
| 24 | "That scan runs two deterministic tiers" | cut: a duplicate of `verbatim-scan.md` ("Say what it did not check"), which step 7 points at and the tests splice in; "say so when you present, every time" stays in step 7 ("matters most here", a clean recheck is no clean bill of health) |
| 36 | "This skill does the half that was left over." | stays, as the opening paragraph's last two sentences; "It is not a better agenda" cut as restating "decides nothing the agenda left undecided" |
| 42 | "**A finding is not a verdict.**" | stays; "A run of shared wording is a place to look" cut as restating the sentence after it |
| 52-53 | the first two When-to-invoke rows | merged into one row: "clean up what an agenda run found" covers "what do I do about these" |
| 54-55 | run-only row; user-disagrees row | stay |
| 56 | "Any other change to an existing draft" | stays, gaining old line 430 (wording no agenda item names is draft-reviser's copy-edit mode) |
| 57-60 | corpus-reviser, new draft, no dossier, empty ledger rows | stay |
| 62 | "**Read-only over the corpus layer.**" | merged into the `## Guardrails` corpus bullet, with the reason (write lock, the user's to run) and the positive target "if one is needed, say so and stop" |

### What may be repaired

| Old line | First words | Went to |
| --- | --- | --- |
| 66 | "## What may be repaired unattended, and what may not" | heading shortened; the second half is the paragraph on surfaced classes |
| 68 | "Every agenda item carries its own `unattended` field." | stays, shortened, with the never-re-derive rule in bold |
| 75-79 | the five `verbatim-run` rows | one row: unattended when `short`, `exact`/`skip-gram`, not `names`; the `long` (stop and ask), `names` (`content/style_exceptions.toml`), `embedding` (surfaced, advisory) and `quoted` (do not touch) cases in its third column. The embedding tier's rationale ("its findings move with tier availability … do not infer it from the length") cut as a duplicate of `docs/AGENDA.md` ("Unattended versus surfaced") and `docs/PLAGIARISM.md`; the skill reads the field, not the length |
| 80 | the `prose` row | stays as a row; the list of `repair: "review"` rules (`WideCodeLine`, `AcronymCase`, the two dialect cases) moved to `repair-prose.md`, whose item it describes |
| 81 | the `missing-citekey` row | stays as a row; "by removing the marker" is step 4's pointer and the guardrail "Remove a missing key's marker instead"; the persistence until `dossier prune` / `dossier sections --citekeys --write` cut as a duplicate of `repair-missing-citekey.md` |
| 82 | the `recorded-but-uncited` row | the paragraph after the table: surfaced, the person's to clear with the two commands; "pruning it here would delete evidence that may instead be an uncited candidate" cut as a duplicate of `repair-missing-citekey.md` |
| 83 | "Every other class (…)" | the paragraph after the table, with the reason (about meaning, which no re-run settles, from `docs/AGENDA.md`) |
| 85 | "**Never run `review agenda --accept`.**" | `## Guardrails`, with its positive target (report, tell them `--accept <id>`); the three acceptable classes and "an item already accepted never reaches this skill" cut as duplicates of `docs/AGENDA.md` ("Accepted items") |
| 94 | "**The agenda's own `detail` field is thin by design**" | step 4, with the `agenda_edit_payload` harness phrase |
| 99-103 | the lookup table | the `verbatim-run` row to `repair-verbatim-run.md` ("matched on `id`", "`draft_text`, `min_run`, the `citekey` and the page range"); the `prose` row to `repair-prose.md` (`summary`, `detail.message`) and step 4 (`python -m chitragupta.draft style`); the `missing-citekey` row to `repair-missing-citekey.md` ("the whole repair payload") |
| 105 | "A long `verbatim-run` is still where the choice actually matters" | the paragraph after the class table, shortened; "same reason it always did" and "asked rather than taken" cut as history and as restating the table's "stop and ask" |

### The loop and steps 1-3

| Old line | First words | Went to |
| --- | --- | --- |
| 113 | "Paths in this skill are from the project root" | stays |
| 116 | "Follow `.claude/skills/draft-reviser/SKILL.md`'s `## The loop`" | stays, with `agenda_loop_edit` unchanged; "for the parts this skill does not restate" becomes "for four of its parts", followed by the new step-mapping table (above) |
| 124-129 | "Before the first edit:" + fence | stays |
| 131 | "`<name>` is the draft's path under `content/drafts/`" | stays, shortened |
| 135 | "The export is the way back" | stays; "The marker is what lets `dossier status` attribute this session's cost" cut as a duplicate of draft-reviser step 1 ("The marker lets `dossier status` total retrieval cost per revision") |
| 139 | "Then read `scope.md` and `steering.md`." | stays |
| 145 | baseline fence | stays |
| 148 | "Unlike `verbatim scan`, `agenda` has no `--write` flag" | one clause stays ("files its report on every run … `--json` only decides what prints"); the comparison cut as a restatement of `review agenda --help` and `docs/AGENDA.md` |
| 153 | "Read `pass_bound` and `objective_class_count` off it now" | stays, with "never hardcode either"; why both are carried as data cut as a duplicate of `docs/AGENDA.md` ("The JSON sibling"); "the closing report is stated against it" stays, tagged R9 |
| 160 | "If the agenda reports no unattended items" | stays; "same as ever" cut |
| 164 | "Take a fresh one at the start of every pass." | stays; the eight-aids mtime mechanism cut as a duplicate of `docs/AGENDA.md` (`stale` in `## Sources`) |
| 408 | "Take the step-2 baseline the same way" | moved up into step 2, where it acts: rebuild the section map before the baseline, naming step 7's command |
| 171 | "Read the baseline agenda's `items`." | stays; "both are single-field lookups with no external payload to fetch" cut as the reason for an order the step states |

### Step 4

| Old line | First words | Went to |
| --- | --- | --- |
| 182 | "**First, refuse a stale span.**" + fence | stays, shortened; "that window is real" cut |
| 193 | "An item whose exact draft text has changed is **dropped**" | stays, with R12 and `stale_spans`; the positive target leads ("Repair only an item that is in the fresh `items`") |
| 203 | "Two consequences to hold." | stays, shortened to one sentence each; "Step 5's `--baseline` cycle re-runs the eight aids in front of the rebuild and is the number that counts" cut: step 5's first paragraph says the cycle refreshes the aids |
| 211 | "Then read only the section that owns the item" | stays (draft-reviser step 3 in the mapping table) |
| 216-221 | "**Then repair by class**" + the three pointers | stays; each pointer now names its class as the condition, and the sentence says "now" |
| 223 | "Remove a marker with `Edit`, leaving the sentence standing." | stays, with `agenda_remove_marker`, `agenda_edit_span` and `agenda_old_string` |
| 227 | "A `long` verbatim-run is surfaced, not unattended" | the long-run half cut as a duplicate of the class table and the guardrail "Never decide paraphrase-or-quote on a long run"; "**Never add a claim**" and the four repair kinds stay |
| 368-370 | the `draft style` fence (old prose section) | step 4, as the way to reproduce a `prose` finding |
| 372 | "Already run as part of the baseline agenda in step 2" | "the one skill where the prose check's list is a work list" stays in step 4; "Your own repairs are new prose … re-run the check as part of every `--baseline` cycle" goes to step 5's first paragraph (the cycle refreshes the prose check); "Under Decision 1 of `plans/f3-agenda-reviser.md`", "(issue 836)" and "the one skill of the nine" cut as history; "unless its rule built it with `repair: \"review\"`" is the class table's `prose` row |
| 387 | "**It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable**" | stays in step 4, after the command (`test_skill_style_check_step.py`); "(since #435)" cut as history |
| -- | (new) "Done when the edit is made … not repaired until step 5 accepts it" | added (Decision 4 and the brief) |

### Step 5

| Old line | First words | Went to |
| --- | --- | --- |
| 235 | "After every repair, one command does the whole R4 cycle" + fence | stays, gaining "the prose check included" from old 372 |
| 245 | "**If the command exits 1 with the sync instruction, stop the pass.**" | stays; "The ledger went missing, or needs a sync … refused before re-running anything" cut as a duplicate of `docs/AGENDA.md` ("Acting on an agenda"); "Never run it yourself" is the `## Guardrails` corpus bullet |
| 251 | "**Read `not_refreshed` first.**" | stays, shortened |
| 261 | "**An aid in `refresh_errors` comes first**" | stays, shortened; "So decide what to *do*, and do not claim to know the cause" folded into "one retry cannot tell that from a host fault" |
| 268-277 | the two outcome bullets | stay; "Keeping an edit that no aid could check is the risk this avoids, and losing a sound repair is the cheaper mistake" cut as rationale for an instruction that stands; "In step 7, report …" kept as "Report the aid, its reason …" |
| 279-285 | "Then, for every aid still in `not_refreshed`:" + two bullets | stay, joined into one paragraph |
| 287-309 | "Accept the repair only if **all** of:" + five bullets | stay; "this now couples classes that used to be independent" cut as history; the explanation of how `objective_new` is computed ("counts the items in `new` that carry `unattended: true`, matched by id as R4 requires") cut as a duplicate of `docs/AGENDA.md` ("Read `objective_new` as well as the delta"); the `math.md` bullet stays, its §12 now `docs/writing-standards/mathematics.md` §12 (PR 0b's split), and "this skill is the likeliest of all of them to break that mapping" cut as rationale |
| 311-316 | "Otherwise revert the item … re-file the baseline" + fence | stays |
| 318 | "`--baseline`'s target is also what every `agenda` call refiles on exit" | stays, shortened; "**Two attempts per item.**" stays |
| 326 | "**The pass loop.**" | stays; `objective_after` and the strictly-falls terminator stay; "read from the payload rather than carried as a literal" cut as a duplicate of step 2's "never hardcode either"; the backstop wording stays, and it gains "one pass works every unattended item" and "`pass_bound` counts passes, never repairs" after a bench run misread the bound (see "The bench") |
| 335 | "**One pass per invocation.**" | stays |
| -- | (new) "Done when each item is accepted, reverted, escalated or refused, and the pass has stopped." | added |

### Step 6

| Old line | First words | Went to |
| --- | --- | --- |
| 341 | "Append to the dossier's `revisions.md`" | stays; the outcomes gain "refused as stale", which old step 4 required logging ("Log the refusal in step 6") |
| 348 | "**Never write any of this to `rejected.md`.**" | stays |

### Step 7, the scan, the full-format run

| Old line | First words | Went to |
| --- | --- | --- |
| 353 | "Run `python -m chitragupta.draft diff …`" | step 7, last, as its own fence (it now runs after the scan and the full-format agenda, as `draft-diff.md` "When" asks: last) |
| 356 | "State the outcome against the baseline agenda" | step 7, gaining "refused as stale or left surfaced" from old 199 and the surfaced-item report |
| 364 | "The human accepts." | stays |
| 366 | "### Prose is now this skill's work, not merely surfaced" | heading cut; content to steps 4 and 5 (rows 368-387 above) |
| 395 | "### Run the verbatim scan" | heading cut; content to step 7 |
| 397 | "The baseline in step 2 is that scan, so it has already run." | cut: inaccurate (step 2 reads the scan's filed report, it does not run it); the reason for the rebuild ("rewording … moves wording between citekeys") stays as "which rewording has just invalidated" |
| 403-406 | rebuild + scan fence | stays |
| 411 | "Read `.claude/skills-common/references/verbatim-scan.md` now" | stays; "these drafts are LLM-written, literal paraphrase is an LLM's normal failure mode" cut as a duplicate of `verbatim-scan.md` and `docs/PLAGIARISM.md`; the "most misleading sentence" and clean-`recheck` points and the bold not-a-gate clause stay |
| 420 | "### Close the pass with one full-format run" | heading cut; content to step 7 |
| 422 | "Every `--baseline` refresh in step 5 ran at `--formats md`" | step 7, with its fence; "(Decision 6 -- only three of the eight aids render … about 2.5 seconds a cycle)" cut as history and rationale (`docs/AGENDA.md`, "Acting on an agenda", states the `--formats md` fact) |
| 430 | "`agenda-reviser` repairs a style finding **that appears as an agenda item**" | the When-to-invoke "Any other change" row |
| -- | (new) "Done when the user has the diff and the report." | added |

### Guardrails and Sources

| Old line | First words | Went to |
| --- | --- | --- |
| 436 | "- **Never start this on your own initiative.**" | stays |
| 439 | "- **Never edit anything but the draft and `revisions.md`.**" | stays; "(prose became work under Decision 1, which puts the Vale rule definitions within reach …)" cut as history, the Vale path kept in the list |
| 447 | "- **Never repair an item the fresh agenda refused as stale**" | stays; "No merge, no similarity-based relocation, no best-effort application" cut as a duplicate of step 4 |
| 451, 452, 457, 458 | paraphrase-or-quote; `Write`; corpus; gate | stay (452 is `never_rewrite_draft`) |
| 453 | "- **Never add a claim, and never fabricate a citekey.**" | stays; "the one failure this whole pipeline exists to prevent" cut as a duplicate of draft-reviser step 5, which the loop pointer reaches; positive target added ("Remove a missing key's marker instead") |
| 460 | "- **Never report a repair you did not verify.** If `recheck` was not run" | stays; "`recheck`" becomes "its `--baseline` recheck": no `recheck` command is run by this skill |
| 462 | "- **Never run `dossier stamp`.**" | stays, shortened; "(#454)" cut as history; "Leaving the draft fingerprint stale after a repair is correct, not a gap" folded into "the honest signal" |
| 472 | "## Sources" | heading cut |
| 474 | "The prose standards this skill inherits are documented" | cut: the attribution is `docs/WRITING-STANDARDS.md`'s own Sources section, reached from step 4's §9 citation; this skill writes no prose beyond its repairs |
| 477 | "What the verbatim tiers catch … `docs/PLAGIARISM.md`" | cut as a duplicate of the opening's "Read `docs/PLAGIARISM.md`" |
| 479 | "The requirements this loop is built to satisfy … R1-R12" | `## Guardrails`, its opening sentence, with both links |

### The repair references

| File | Change |
| --- | --- |
| `repair-missing-citekey.md` | gains "the item's own `citekey` and `section` are the whole repair payload" (old line 103); "Before #701 the residue was reported on no surface" cut as history; ends on "Not done at the edit" |
| `repair-prose.md` | gains the item's `summary`/`detail.message` (old line 102) and the `repair: "review"` rules (old line 80); ends on "Not done at the edit" |
| `repair-verbatim-run.md` | gains "matched on `id`" and what the finding gives (old line 101); ends on "Not done at the edit" |

Each still opens on its condition ("Read this when the item in hand is
of class …"), names no skill and no tool, and leaves the edit tool to
the step that sent the reader there.

### Totals

- **78 rows** for the old file, one per paragraph, list item, table row
  group or fence (a row may cover adjacent items that went the same
  way), plus 3 rows marked "(new)".
- **Stay, whole or shortened in place, with nothing cut or moved: 24.**
- **Moved, with nothing cut: 17 rows** send text to another part of
  `SKILL.md` (a step, the When-to-invoke table, `## Guardrails`) or to a
  repair reference.
- **Cut: 37 rows** cut some of their text, each with its reason:
  history (a decision or issue number), a restatement of `--help`, a
  duplicate of `docs/AGENDA.md`, `verbatim-scan.md`, a repair reference
  or draft-reviser's loop, rationale for an instruction that stands, or
  (old 397) a sentence that was wrong. Several of these also move the
  rest of their text.
- **Without a destination: none.**

## The bench

Skill `agenda-reviser`, Claude Code, skill-only. The task runs
survey-writer first, seeds two short unquoted source runs and five prose
findings, and asks for one pass. It reaches steps 1-7, both repair
references for `prose` and `verbatim-run`, the swap revert and the
retry re-file. **It cannot reach a `missing-citekey`, a stale span, an
aid in `refresh_errors`, the sync refusal or a long run** (the seed
makes none); for those only history and duplicated rationale moved, and
no command left `SKILL.md`.

Files in `bench/results/2026-11-15-agenda-reviser-shrink/`:
`tier2.json` (after runs 1-6, the text before the `pass_bound` fix
below), `before-rerun.json` (before runs 4-6, from a clean `origin/main`
checkout), `after-confirm.json` (3 runs on the final text). A first
after batch hit the account's usage limit (HTTP 429 in 2-3 seconds a
run) and was discarded.

**Verdict: pass** at 6 against 6 (`--compare` exit 0; 3 against 3 was
inconclusive). Every gated command is unchanged except two that are
not steps of this skill:

- `draft style` 3/6 -> 0/6, and 0/3 in the confirmation runs. Step 4
  now offers the command only to reproduce a finding, and step 5's
  `--baseline` cycle runs the prose check itself on every repair, so no
  run went without the prose findings: every after run repaired the
  seeded `prose` items it reached (all five, except run 6, below). The
  old file gave the command its own section and fence, which half the
  before runs ran.
- `draft dossier status` 2/6 -> 1/6: draft-reviser's step 1, which this
  skill never named; the drift it reports is an agenda source.
- The forbidden `enrich` fell 1/6 -> 0/6.

All 9 after runs passed their gate and their prerequisite survey's gate.
Seven of them opened `repair-prose.md` and `repair-verbatim-run.md`
(the before arm's first 3 runs opened neither, its runs 4-6 one of
three); every after run opened `verbatim-scan.md` and `draft-diff.md`.

**Compliance, read from each after run's project** (`revisions.md` and
the transcript), runs 1-6 then the 3 confirmation runs:

| Question | Runs 1-6 | Confirmation |
| --- | --- | --- |
| Logged every repair attempt in `revisions.md`, reverts included | 6/6 | 3/3 |
| Ran the gate and the `--baseline` recheck after every edit, before keeping it | 6/6 | 3/3 |
| Stopped correctly: worked the list while the count strictly fell, no second pass | 5/6 | 3/3 |

The count never stopped falling in any run (each accepted repair
lowered it; the two `objective_new` 1 swaps were reverted and retried,
which is the per-item rule), so the stop on a non-falling count was not
exercised. **Run 6 stopped after three accepted repairs**, reading
`pass_bound` (3) as a repair budget, and left 12 objective items open.
The old text was as ambiguous ("Continue to the next item only while …
Stop at `pass_bound`") and no before run misread it, but this text had
done it once, so step 5 now says that one pass works every unattended
item and that `pass_bound` counts passes, never repairs. The 3
confirmation runs on that text each worked the list to 0.

Two observations outside the skill: most runs in both arms ran
`review agenda --accept` on the uncited-claim items because the task
prompt asks for it, against the guardrail (one run in each arm refused,
citing it); and concurrent runs wrote helper scripts to the same `/tmp`
path, so one run's recheck once ran against another run's project.

## For the plan

- PR 5's row: the 8,000 target is not reachable without moving
  guardrails of an unattended loop behind a pointer, which the brief
  forbids. The cap is 18,500 with a reason.
- PR 5 decided `mathematical-prose.md`: not cited (above).
- `docs/AGENDA.md` and `docs/GENRE.md:270` say agenda-reviser must never
  be run on a verbatim digest; the skill itself has never said so. Not
  added here (a new rule, not a move); worth a guardrail in its own
  change.
- Parallel agents in this series share one scratchpad. A bench `--out`
  under a generic name (`bench/after`) collides between agents: two
  benches wrote the same `tier2.json`. Give each agent's brief a
  per-skill output folder.
