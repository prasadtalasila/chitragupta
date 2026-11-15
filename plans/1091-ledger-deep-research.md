# Move ledger: deep-research (#1205, SK-8)

Status: **built on `feat-1091-deep-research`, branched from
`feat-1091-critique-pointer` (`40c8e507`, 6.173.5), 2026-11-15; above
the 8,000 target with a reason.** Written for
[plans/1091-skill-shrink.md](1091-skill-shrink.md) PR 8, in the shape of
[the survey-writer ledger](1091-ledger-survey-writer.md).

**Written for** the reviewer of PR 8. **Assumed:** the plan's
"Decisions" and "Review focus", the survey-writer ledger's "Step 10
behind its pointer", and [docs/HARNESS.md](../docs/HARNESS.md) on the
three `SKILL.md` copies.

Every paragraph removed from deep-research's `SKILL.md` has one row
below: its first words, then where it went (file and section) or "cut"
with the reason. A row with no destination is a defect. Line references
are to the old `.claude` copy at `40c8e507`; the `.agents` and
`.opencode` copies held the same paragraphs, differing only where
`tests/fixtures/skill_harness_phrases.toml` says, and changed the same
way.

## Where phase names and numbers are cited

Grepped across the repository (`.claude/`, `.agents/`, `.opencode/`,
`docs/`, `bench/`, `tests/`, `chitragupta/`, `plans/`) before the
rewrite. Every phase number, every Phase 7 letter (a, a2, b to h) and
every phase title is unchanged, so none of these moved:

| Site | Cites |
| --- | --- |
| `.claude/agents/deep-research-interviewer.md` | "Phase 2" (description), "Phase 3's contradiction map", "Phase 6" |
| `.claude/agents/deep-research-writer.md` | "Phase 5" (description), "Phase 2" |
| `.claude/agents/peer-reviewer.md` | "Phase 7" (description) |
| `.claude/skills/deep-research/references/report.md` | Phase 1, 2, 7a, 7b, 7(d), 4, 6 |
| `docs/PROMPTS.md:149,250-252,265` | Phase 2, 5, 7a, 7; `report.md` §1 |
| `docs/TOKENS.md:105,132,144,153,212,232,268,271,295,328,334,409,413,583-606,648,688,707,796,921` | Phases 2, 3, 5, 7, 7f; `report.md` §1 |
| `docs/DRAFT-ITERATION.md:8,99,118-128,160,177` | Phases 1-7, 2, 4, 5 |
| `docs/DOSSIER.md:597-600` | Phase 4, 5, 7(e) |
| `docs/REJECTION.md:333` | Phases 2, 3-7 |
| `docs/WRITE-A-DEEP-RESEARCH-REPORT.md:192-194,238-239` | Phase 4; phase titles 6 and 7 |
| `docs/examples/dossiers/deep-research/outline.md:8` | Phase 4 |
| `docs/INSPIRATION.md:113` | `report.md` §7 |
| `chitragupta/dossier/_brief.py:6` | Phase 5 |
| `bench/bench_prompt_economics.py:20,55` | Phase 5 |
| `tests/test_dossier.py:3086,3269` | Phase 4, 5 |
| `tests/test_skill_pregate_feedback_step.py:123` | Phase 7 |
| `tests/test_init.py:594` | `report.md` (path only) |

`report.md`'s numbered sections keep their numbers: §3 (the interview
protocol, a duplicate of the interviewer's own file) is replaced by the
collection-scoping reasoning, so §4 to §7 and their citations
(`report.md` §4 in the interviewer file, §7 in `peer-reviewer.md` and
`docs/INSPIRATION.md`) still land. The interviewer file cited §3, and
now says it is the whole interview. §8 and §9 are new.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/deep-research/SKILL.md` | 40,760 | 19,141 |
| `.agents/skills/deep-research/SKILL.md` | 40,779 | 19,156 |
| `.opencode/skills/deep-research-opencode/SKILL.md` | 40,927 | 19,278 |
| `.claude/skills/deep-research/references/report.md` | 10,312 | 13,834 |
| `.claude/agents/deep-research-interviewer.md` | 6,279 | 6,258 |
| `docs/writing-standards/genres/deep-research.md` | new | 4,474 |

The cap in `tests/test_skill_size.py` falls from 41,000 to 20,000, with
its reason. **It stays above the 8,000 target and the 10-12 KB the plan
expected.** Decision 1 as answered on 2026-11-14 makes the target a
guideline, so nothing is compressed to fit. What the 19 KB holds,
measured on the `.claude` copy:

- 990 bytes of frontmatter, which Decision 7 leaves alone;
- about 2,300 bytes of fenced commands (eleven commands, two of them
  wrapped, and the depth table);
- 1,600 bytes for the critique step and its gate, the pointer form the
  critique-pointer branch measured;
- the three dispatch sites (Phases 2, 5 and 7(a)), each naming its
  packet, its harness phrase and the agent file a run without that
  subagent reads instead: about 2,000 bytes;
- the three transcription paragraphs (Phases 2 and 5, and Phase 3's
  record), which only the main run can do, and the rule that it does:
  about 2,000 bytes;
- about 1,700 bytes of project-root paths in pointers, and a one-line
  `Done when` on each of 7 phases and 10 lettered steps.

The plan's estimate assumed a 6.4 KB floor; it did not count the
dispatch and transcription text, which is the coordinator's and cannot
move to an agent file: an agent never transcribes, and the main run
never reads an agent file on Claude Code.

## The structural question: phase detail beside the agent that runs it

The owner agreed that each phase's detail may live with the agent that
runs it, if every harness still reaches it. What each harness does at
each dispatch, read from `chitragupta/init.py` (`COPY_VERBATIM` copies
`.claude/` whole for every `--agent`), `docs/HARNESS.md` and the copies:

| Phase | Claude Code | Codex | OpenCode | `quick` depth |
| --- | --- | --- | --- | --- |
| 2, interviews | `deep-research-interviewer` subagent, its file loaded as its whole instruction | no subagent tool: runs each interview itself, "following the protocol from `.claude/agents/deep-research-interviewer.md`" | `general` subagent through `task`, "give it the protocol from" that file | as the run's harness (the depth table changes rounds, not dispatch) |
| 5, section writing | `deep-research-writer` subagent | writes each section itself "with `.claude/agents/deep-research-writer.md`'s instructions" | `general` subagent with that file's instructions | inline: "follow that file's 'Writing standards', 'Citation protocol' and 'If a subpoint is thin' yourself" (new; the paragraph rule used to reach a quick run only from `SKILL.md`) |
| 7(a), review panel | `peer-reviewer` subagents | reviews in turn itself with `.claude/agents/peer-reviewer.md` | `general` subagents with that file | no panel: `report.md` §7's inline self-critique |

So the move holds on all three harnesses: each run is told, at the step
that needs it, to read the agent file by its path from the project root.
It was made as deduplication rather than as a transfer: the skill and
`report.md` said in other words what the three agent files already say,
so those passages were cut and the dispatch sites name the file. The
agent files gained nothing but the interviewer's header sentence ("This
file is the whole interview"), because `report.md` §3, its duplicate,
is gone. Nothing coordinator-only went into an agent file.

Two limits of what the tests see, recorded rather than changed:

- `tests/test_skill_references.py`'s `NAMED_PATH` matches only
  `.claude/skills…` paths, so a `.claude/agents/` path a `SKILL.md`
  names is not checked to exist; all three exist.
- `bench/bench_skill_harnesses.py`'s `SKILL_FILE` reads commands from
  `.claude/skills…` files only, so a command only an agent file names
  (`draft retrieve search`, `draft retrieve evidence`) is never
  expected; it is counted as `ran_unnamed` when it runs. The expected
  set did not change (below).

The quick depth: every instruction a phase needs is still reachable
inline: Phase 5 names the writer file's sections, and `report.md` §7
holds the self-critique that used to sit in Phase 7(a).

## `mathematical-prose.md`: not cited

A deep-research report writes no mathematics of its own. Every
sentence is grounded in a source; a quantity is one "carried over from
a source -- a threshold, an effect size, a bound" (old line 220), set
in a code span with a `math.md` row; numbering fires only when two
writers state the same bound. `mathematical-prose.md` governs the
sentences around symbols a writer introduces and derivations it
develops, which this genre never does, so it is not cited, as
survey-writer does not cite it for the same reason. The old text's
"two writers independently derived the same bound" now reads
"reported" in the genre file.

## Pinned phrases: what the tests read

"Raw" means the test reads `SKILL.md` as written (whitespace collapsed
at most); "expanded" means `tests/skill_text.py`'s `expanded()`, which
splices each named `.claude/skills…/references` file in after its path.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_references.py` | "from the project root" within 250 characters of the first `.claude/skills…` path; every named path exists; the copies cite the same `` `path` §N `` set; every `## N.` of `report.md` (§1 to §9) is cited | raw |
| `test_skill_references.py` | no backticked skill name and no tool word in `report.md` | the reference |
| `test_skill_harness_copies.py` | `checklist`, `interview_dispatch`, `writer_fallback`, `reviewer_fallback`, `critique_edit_tool` in all three copies; every OpenCode skill name suffixed | raw |
| `test_skill_pregate_feedback_step.py` | `_POINTER_FORM` now `{"survey-writer", "deep-research"}`: the step from "critique against the evidence packet" to its `Done when` names `critique.md` within 2,000 characters, says "not done until the loop the reference describes has run", holds no command, and with the whole reference holds every rider | raw step plus reference |
| `test_skill_style_check_step.py` | the `prose-check.md` pointer within 1,400 characters after `draft style`; its riders within 1,400 after every `draft style` | raw; expanded |
| `test_skill_verbatim_scan_step.py` | `dossier sections … --citekeys --write` within 200 characters of the scan; the `verbatim-scan.md` pointer within 1,200; its caveat within 2,000; "never a condition of presenting" | raw; expanded |
| `test_skill_table_step.py` | `<!-- table:`, `<!-- tableref:`, "§13" | raw |
| `test_skill_acronym_step.py` | "acronym vocabulary" | raw |
| `test_skill_figure_step.py` | absent: `` `figure-drawer` `` | raw |
| `test_skill_retrieval_logging.py` | `--log` beside every `retrieve search\|evidence` under `.claude/` (the skill names none; the agent files do, unchanged) | raw |
| `test_skill_size.py` | each copy at or under 20,000, within 1,000 of the largest, with a reason | raw |
| `test_writing_standards_layers.py` | the new genre file is an index row and opens "Assumes the core, §1–9" | the docs |

No citation sits inside the critique, prose-check or verbatim-scan
steps. `report.md` is spliced wherever it is named, so its §5 and §8
pointer sits in (d), before (f)'s `draft style`.

**Expected commands** (`bench/skill_commands.py`), each harness's copy
plus the references it names: the same 18 commands before and after, on
all three harnesses; only the order of first appearance moved, since
the critique loop's commands now come from `critique.md`:

```text
draft gate, corpus ledger, draft dossier init, draft dossier outline,
review uncited, draft dossier check-evidence, draft dossier brief,
review synthesis, draft dossier sections, draft style,
review verbatim scan, draft dossier stamp, draft dossier export,
draft references, draft dossier status, review verbatim recheck,
draft render, draft evidence
```

## Where each removed paragraph went

`genre-steps.md` is `.claude/skills-common/references/genre-steps.md`;
`report.md` is `.claude/skills/deep-research/references/report.md`;
`genres/deep-research.md` is `docs/writing-standards/genres/deep-research.md`;
the agent files are `.claude/agents/<name>.md`.

### Header, corpus layer, collection scoping

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "Every claim must resolve to one of:" and its two bullets | stays, as the opening sentence; the `embed_index.search()` alternative is `genre-steps.md` §1 ("unless `chitragupta/enrich/embed_index.py` has been built") and each agent file's search step |
| 17 | "This is a heavier, slower alternative to `survey-writer`" | "When to invoke" ("faster, single-pass"; "a heavy, multi-phase run"); the description says it too |
| 22 | "Adapted from hadufer/claude-storm (MIT)" | one sentence stays; the attribution in full was already `report.md`'s header |
| 29 | "Shared corpus layer (read, don't regenerate)" (heading) | cut: the heading of the bullets below |
| 31 | "`content/ledger.sqlite` -- per-citekey status" | `genre-steps.md` §1 |
| 32 | "`papers/bibliography.bib` (gitignored, per-host)" | `genre-steps.md` §1 |
| 33 | "`chitragupta/retrieval.py` -- `search(query, k, snippet_chars)`" | `genre-steps.md` §1 |
| 34 | "`chitragupta/enrich/embed_index.py` … check `content/chroma/` first" | `genre-steps.md` §1; "check `content/chroma/` first" is in all three agent files, which are the ones that search |
| 36 | "`chitragupta/enrich/corpus.py` -- builds the enrichment corpus from the ledger" | cut: a duplicate of `DEVELOPER-AGENTS.md`'s enrichment-layer section ("every document it yields is citable"); no step acts on it |
| 40 | "Collection scoping (#195): deliberately not used here" (heading) | stays; "(#195)" cut as history |
| 42 | "Every other genre skill offers to scope retrieval" | `report.md` §3; "no `--collection`, here or in any agent" stays |
| 48 | "The reason is what this skill is for" | `report.md` §3; one sentence of it stays |
| 58 | "There is measured reason to expect that" | `report.md` §3 |
| 66 | "So: **search the whole corpus, always.**" | stays |

### The dossier

| Old line | First words | Went to |
| --- | --- | --- |
| 71 | "The dossier: write down what produced the draft" (heading) | stays as "The dossier" |
| 73 | "The report is only half of what this run produces" | `genre-steps.md` §2, which says it for every genre; "running seven phases and a dozen subagents again" is cut, a duplicate of `genre-steps.md` §7's hand-over |
| 80 | "`chitragupta/dossier/` owns that state" | `genre-steps.md` §2 |
| 86 | "**The main run owns the dossier. A subagent never writes it.**" | stays, rule and reasons |
| 94 | "**After Phase 2**, each interviewer packet's kept claims" | Phase 2's transcription paragraph, which already said it; the `evidence.md` and `rejected.md` formats are `genre-steps.md` §5 |
| 105 | "**After Phase 3**, record the contradictions themselves" | Phase 3, which already said it |
| 109 | "**After Phase 5**, every writer's `### Sources added` block" | Phase 5, which already said it, now with "at `quick` depth, record what you found the same way" |
| 116 | "The `peer-reviewer` packets are the one exception" | stays, in two sentences |
| 123 | "Do not ask a subagent to write into `content/dossiers/`" | stays |
| 127 | "**Then dispatch from the file rather than from your context.**" and its `brief` fence | the sentence stays; the fence is cut, a duplicate of Phase 5's |
| 134 | "Pasting the same claims into four dispatch prompts" | one clause stays with `docs/TOKENS.md`, which holds the arithmetic; "a context is append-only between compactions" is cut, a duplicate of `docs/TOKENS.md` and `docs/DRAFT-ITERATION.md` |
| 142 | "Which is the other reason to prefer it: `brief` exits non-zero" | stays |
| 146 | "**The dossier is not the provenance JSON**" | Phase 7(c), beside the provenance write |
| 154 | "**Read-only means read-only**" | the rule and both commands stay ("Before you start"); the write lock, the run time and "do not build one" are `genre-steps.md` §1 |
| 164 | "**If the ledger is empty, stop.**" | stays, with its command |
| 170 | "If it reports no items, or none with status `parsed`" | stays in one sentence with the remedy; "Do not draft around it, do not sync, do not cite" is `genre-steps.md` §1 |

### When to invoke, prose standards, depth

| Old line | First words | Went to |
| --- | --- | --- |
| 179 | table row "User asks for 'deep research'" | cut: the description routes it |
| 180-184 | table rows naming `survey-writer`, `thesis-chapter-writer`, `textbook-chapter-writer`, `tutorial-writer`, `draft-reviser` | stays, as one sentence naming the five |
| 185 | table row "Ledger is empty" | cut: a duplicate of "If the ledger is empty, stop" |
| 187 | "Tell the user up front that this is a heavy, multi-phase run" | stays, with the `checklist` phrase |
| 194 | "Follow `docs/WRITING-STANDARDS.md` for the cross-genre rules" | stays; "Two apply with particular force" goes to `genres/deep-research.md` |
| 199 | "**Terminology is fixed at outline time**" | the rule to `genres/deep-research.md`, "What a deep-research report owes its reader"; handing writers the glossary stays in Phase 4 |
| 203 | "**Scope is stated in the report**" | `genres/deep-research.md`; the lead's scope statement stays in Phase 6(a) |
| 206 | "**This genre does not use … §10's figures.**" | "This genre uses no figures (§10)" stays; the rest to `genres/deep-research.md`, "No figures, by design" |
| 210 | "**§13's tables do apply**" | the caption, the two markers and §13 stay; the genre's natural shape and the collision example go to `genres/deep-research.md`, "Tables carry this genre's shape"; checking ids is Phase 6(a2) |
| 219 | "**§12's mathematics does apply**" | §12 and the `math.md` row stay; the rest to `genres/deep-research.md`, "Mathematics: carried over, reconciled once"; collecting rows is Phase 6(a2) |
| 227 | "**Number sparingly, and only at synthesis.**" | `genres/deep-research.md`; the two markers and "only here" are Phase 6(a2) |
| 239 | the depth table and "+ basic" | stays |

### Phases 1-4

| Old line | First words | Went to |
| --- | --- | --- |
| 249 | "**Before any retrieval, name the reader and the scope**" | the title and the init command stay; the three example readers are cut, a duplicate of `genre-steps.md` §3 and WRITING-STANDARDS §1 on naming a reader |
| 258 | "Give it the same path Phase 7(d) will save to" | stays |
| 262 | "**Settle that path with the user first.** It may contain directories" | `genre-steps.md` §3 (directories, the topic layout, what mirrors the path); "use it verbatim everywhere below", with its four sites, stays |
| 277 | "Fill in `scope.md`'s **Reader**, **Covers**" | `genre-steps.md` §3; Phase 4 keeps writing over Phase 1's versions; "this genre writes more prose than any other here" is cut, `genre-steps.md` §3 giving the reason for every genre |
| 284 | "Read the acronym vocabulary too" | `genre-steps.md` §3; "the acronym vocabulary" stays in Phase 1's pointer |
| 287 | "`init` also stamps the corpus fingerprint" | `genre-steps.md` §3; "It only creates files that are missing" is cut, a property of `dossier init` documented in `docs/DRAFT-ITERATION.md`, which no step acts on |
| 292 | "**If the dossier has an `outline.md`**" and its fence | stays |
| 299 | "If it exists and passes, its sections are the report's declared structure" | stays in two sentences; the `declared`/`extended` reasoning is `genre-steps.md` §4 |
| 307 | "Derive the interview personas below from the outline's own section headings" | stays ("its headings name the personas") |
| 309 | "A section declaring `claim:` is content to ground" | `genre-steps.md` §4; `review uncited` stays |
| 314 | "**No `outline.md`, or it fails `--check`:** run 1-2 broad retrieval calls" | the pointer stays; the calls and the corpus-specific personas go to `report.md` §2 |
| 321-330 | the five lenses | `report.md` §2 |
| 332 | "Always add the **Basic fact writer**. State your final persona list" | stays; "§2 has how STORM discovers personas" becomes the pointer |
| 338 | "Dispatch one `deep-research-interviewer` subagent per persona" | stays, with `interview_dispatch`; the fallback's "report.md §3 plus the packet schema from" the agent file becomes the agent file alone, since `report.md` §3 was a duplicate of it |
| 346 | "Give each subagent: `TOPIC`, its `PERSPECTIVE`" | stays; "Without that path … concurrency-safe" is cut, a duplicate of the interviewer file's step 3 and `genre-steps.md` §1 |
| 353 | "Each returns: core position, grounded key claims" | cut: a duplicate of the interviewer file's "Required output"; what the main run transcribes from it stays |
| 359 | "**Transcribe every packet into the dossier before starting Phase 3**" | stays, with `check-evidence`; the warnings it prints are `genre-steps.md` §5 |
| 370 | "No web fallback: if a perspective's searches turn up nothing" | one sentence stays, citing `genre-steps.md` §6; the interviewer file states the agent's side |
| 374 | "Citekeys need no de-duplication/global-renumbering step" | one sentence in Phase 7(b), citing `report.md` §4 |
| 381-388 | Phase 3's five items | stays, shortened |
| 390 | "Record the contradictions in `evidence.md`" | stays |
| 397 | "Sketch a draft outline from general topic knowledge" | stays |
| 401 | "Also fix, at this point, two things Phase 5 will otherwise get wrong" | stays |
| 407 | "Update `scope.md`'s **Reader** and **Glossary**" | stays; "One glossary, in one place" goes to `genres/deep-research.md` |
| 412 | "**Then write the plan into `sections.md`**" | stays, shortened |

### Phases 5 and 6

| Old line | First words | Went to |
| --- | --- | --- |
| 426 | "Phase 4 already chose each section's citekeys" and the `--check` fence | stays |
| 435 | "`--check` prints how many of the row's citekeys have a block" | stays as "without reading the evidence back into your own context"; what it prints is `dossier brief --help` |
| 438 | "Fix a gap now" | stays |
| 441 | "For `standard`/`deep`, dispatch `deep-research-writer` subagents" and its fence | stays |
| 450 | "**Do not paste the kept claims into the prompt.**" | stays; "That is the whole of this phase's cost saving" is cut, a duplicate of "The dossier" and `docs/TOKENS.md` |
| 456 | "If `deep-research-writer` is unavailable" | stays, with `writer_fallback`; "the command line goes in the prompt either way" becomes "and the `brief` line for its section" |
| 458 | "For `quick`, write inline: you are the writer" | stays, and now names the writer file's sections a quick run follows |
| 461 | "Cap concurrency per `report.md` §1" | stays |
| 463 | "Inline `[@citekey]` citations, neutral tone, every sentence grounded" | cut: a duplicate of `deep-research-writer.md`'s "Writing standards", "Citation protocol" and "If a subpoint is thin" |
| 467 | "Tell every writer the paragraph rule explicitly" | the rule is cut from Phase 5 as a duplicate of `deep-research-writer.md`'s "Close each body paragraph on two or more citekeys" (its system prompt on Claude Code, its named instructions elsewhere); the rule, the `single-source` marker, §11 and `review synthesis` stay in Phase 6(a2), where the main run checks the assembled report |
| 478 | "When the writers return, copy each `### Sources added` block" | stays |
| 487 | "**(a) Lead:**" | stays |
| 491 | "**(a2) Reconcile across sections.**" and its five seams | the seams go to `genres/deep-research.md`, "The reread"; the step and its pointer stay |
| 500 | "Then read the assembled draft once as the Phase 4 reader" | stays; "which no individual section writer was in a position to do" goes to `genres/deep-research.md` |
| 504 | "**(b) Synthesis briefing:**" | stays, now pointing at `report.md` §5's template, which already held its shape |

### Phase 7

| Old line | First words | Went to |
| --- | --- | --- |
| 511 | "**(a) Peer review.** STORM's documented weakness is skipping self-critique" | cut: a duplicate of `report.md` §7, "Why a panel instead of one self-critique pass"; the Imbad0202 credit was already in `report.md` §7 and `peer-reviewer.md` |
| 522 | "Dispatch four `peer-reviewer` subagents **in parallel**" | stays, with `reviewer_fallback` |
| 530 | "**Reconcile under the concession threshold**" | stays in one sentence; in full in `report.md` §7, which already held it |
| 538 | "Act as the reconciling editor yourself" | stays in one clause; `report.md` §7 "Reconciliation" already held it |
| 543 | "For `quick` depth, do a single inline self-critique instead" | `report.md` §7, "At `quick` depth there is no panel"; the step points there |
| 548 | "**(b) Assemble** per `report.md` §5's template" | stays |
| 553 | "**(c) Save, log provenance, critique, and gate.**" | stays; "every other skill in this repo saves before gating" is cut, the gate-reads-a-file reason staying |
| 562 | "**Then critique against the evidence packet, before gating.**" | stays: the anchor and the listing paragraph, naming Phases 2 and 5 as what recorded the blocks; "nothing in this pipeline scores this automatically" is in `critique.md` step 2 |
| 577 | "**Run this step: it is never a condition of presenting**" | "never a condition of presenting" stays; "not done until you have run its commands" becomes the measured "not done until the loop the reference describes has run" |
| 579 | "Read `critique.md` now, before listing anything, and work it through" | stays, as "follow it with … as `<draft>`; make each edit with `Edit`"; "In outline:" is cut |
| 583 | "1. Where the dossier has an `outline.md`" and its fence | `critique.md` step 1, which already held both |
| 590 | "2. Take the baseline" and its fence | `critique.md` step 3, which already held them |
| 598 | "If the scan's `tiers_not_run` is not empty, quote the reason" | `critique.md` step 3; the step asks for the reason back and `critique.md` step 6 returns it |
| 604 | "3. Repair at most three items, each edit with `Edit`" and its fence | `critique.md` step 4; "each edit with `Edit`" stays as the `critique_edit_tool` phrase |
| 615 | "Read `style`'s count only as a number" | `critique.md` step 4, substep 3 |
| 618 | "4. Log every attempt, kept or reverted, in the dossier's `revisions.md`" | `critique.md` step 4, substep 5; the step keeps "logged in the dossier's `revisions.md`" |
| 620 | "If nothing on the list clears the bar" | `critique.md` step 6; the `Done when` keeps it |
| 623 | "**Then gate:**" and its fence | stays |
| 631 | "**(d) Save and render.**" | stays, title included |
| 640 | "**Deep research emits one, and has the strongest claim to it**" | `report.md` §5, its last paragraph; the step points there when the user asks |
| 646 | "**(e) Close the dossier.**" and "**The section map.**" | stays, shortened; "It overwrites the file with the heading -> citekey relation …" is cut, a duplicate of `genre-steps.md` §2, "The section map is derived" |
| 662 | "**Do this only here, never before Phase 5.**" | stays |
| 669 | "**The steering.**" | one sentence stays; the examples and why go to `genre-steps.md` §2, which already held them |
| 675 | "**(f) Run the prose check.**" | stays; "what the check can and cannot see, and how to report what it finds" is cut as a description of `prose-check.md` |
| 686 | "This is the first time anything reads the whole report at once" | `report.md` §8 |
| 690 | "**(g) Run the verbatim scan.**" | stays; "not a repeat of step (c)" now names (e) as well, which also rebuilds the map |
| 703 | "This genre earns the check more than most" | `report.md` §8; "A review aid, not a gate" stays |
| 709 | "Read `verbatim-scan.md` now and follow it: what to show" | the pointer stays; the description of the file is cut |
| 714 | "**(h) Stamp the draft fingerprint, then present.** Nothing edits the report's text after this point" | stays; why goes to `genre-steps.md` §7; "(#454)" cut as history |
| 722 | "Then present. Give the user: headline finding" | the list stays; where the dossier is and that it is gitignored are `genre-steps.md` §7; "seven phases and a dozen subagents is the wrong price for an edit" is cut, a duplicate of `genre-steps.md` §7's reason; the `draft-reviser` handoff and the export command stay |

### Guardrails and Sources

| Old line | First words | Went to |
| --- | --- | --- |
| 735 | "## Guardrails" (heading) | cut, with its three bullets |
| 737 | "**Grounded by default, closed-corpus.**" | the opening sentence, which now cites `report.md` §6 |
| 741 | "**Parallelize, with a cap.**" | cut: a duplicate of "in parallel" at Phases 2, 5 and 7(a) and of Phase 5's cap pointer; the `parallel_cap` phrase-map entry goes with it |
| 744 | "**Be honest about cost.**" | cut: a duplicate of "When to invoke" ("faster, single-pass"; "a heavy, multi-phase run") |
| 747 | "## Sources" (heading) | cut: the link moves to "Prose standards" |
| 749 | "The prose standards this skill inherits are not original" | `report.md` §9 |
| 751 | "Full citations, licences and a per-principle attribution table" | the link stays in "Prose standards"; the licence sentence goes to `report.md` §9 |
| 755-769 | "What bears on *this* genre specifically" and its three bullets | `report.md` §9 |

### What `report.md` lost

| Section | Went to |
| --- | --- |
| §3 "Interview protocol (Phase 2) -- what each `deep-research-interviewer` does" | cut: every item is in `deep-research-interviewer.md`'s "Interview process" and "Mandatory grounding discipline" (one question a round, never repeated; up to three reformulations; 500-character snippets judged before use; an honest "no appropriate answer"; real citekeys only). The section number now holds the collection-scoping reasoning |
| §7's role-mandate table | cut: a duplicate of `peer-reviewer.md`'s `ROLE` list; the four role names stay, pointing at that file |

### Totals

- **122 rows**: 120 for the old `SKILL.md`, one per paragraph, list
  item, table row or fence, and 2 for `report.md`.
- **Stay, moving nothing: 47** (a title, a command, a dispatch site, a
  transcription rule or a marker the tests read), most shortened.
- **Send text to a file: 62**, to `genre-steps.md` (24 rows),
  `report.md` (20), `genres/deep-research.md` (10) or `critique.md`
  (8); a row may name two files.
- **Cut: 30 rows** cut some or all of their text, 13 of them wholly,
  each with its reason: a duplicate of a named file and section (an
  agent file's, for several of them), a description of a reference the
  pointer reaches, a property of a command, or history.
- **Without a destination: none.**

### What was added, not moved

Each phase and each Phase 7 step gained a one-line `Done when`
(Decision 4), and each pointer a condition. Phase 5 names the writer
file's sections for a `quick` run. The genre file's opening paragraph,
and `report.md`'s §2, §3, §8 and §9 openers saying when to read them,
are new; everything else in them is one of the rows above.

## The critique step and the rider window

Phase 7(c)'s critique is now in the pointer form, as survey-writer's
step 10 is: the step keeps its place, its anchor and its own listing
paragraph (deep-research reads the `relevance:`/`claim:`/`quote:`
blocks Phases 2 and 5 recorded, against the assembled report), names
`critique.md` and `Edit`, says it is not done until the loop has run,
says what to come back with, and ends on its `Done when`. `critique.md`
is unchanged.

**The 6,800 window is no longer needed for deep-research**, which
`_STEP_TAIL_CHARS` was raised for. Measured after this change, the
furthest rider from an anchor in the three inline-form skills, to the
end of the rider: thesis-chapter-writer 6,070, textbook-chapter-writer
6,183, tutorial-writer 6,286. The window still has to exceed 5,900 for
them, so it is left at 6,800 for the PR 2 skills to settle when they
convert; once all four are pointers, the constant and its inline branch
can go.

## The bench

Pending: filled in from the after runs.

## For the plan

`plans/1091-skill-shrink.md` is not edited on this branch. What it
should say:

- **PRs 3-8 table, row 8:** the target is 8,000 and the result 19.1 KB;
  the cap is 20,000 with a reason. The 6.4 KB floor left out the three
  dispatch sites and the transcription paragraphs.
- **"consider splitting phases across its subagent boundary":** done as
  deduplication. What the skill said that its agents need was already in
  their files, so it was cut and each dispatch site names the file, which
  Codex and OpenCode read by path. Nothing moved into an agent file.
- **"decide whether it cites `mathematical-prose.md`":** it does not;
  the reason is above.
- **`Closes #1091`, then the MINOR release:** for the PR, which this
  branch does not open.
- **Review focus 1:** once PR 2's skills join `_POINTER_FORM`,
  `_STEP_TAIL_CHARS` has no user; until then 6,800 still covers the
  furthest rider, 6,286 characters in tutorial-writer.
