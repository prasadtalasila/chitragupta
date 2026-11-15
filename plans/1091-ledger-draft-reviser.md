# Move ledger: draft-reviser (#1201, SK-4)

Status: **built on `feat-1091-draft-reviser`, above the 8,000 target,
with a reason in its cap row.** Written 2026-11-15 against `cc65f47a`
(6.173.3), for [plans/1091-skill-shrink.md](1091-skill-shrink.md), the
PR 4 row of "PRs 3-8, in outline".

**Written for** the reviewer of PR 4, and for whoever builds SK-5
(agenda-reviser) and SK-7 (corpus-reviser) on top of this branch.
**Assumed:** the plan's "Decisions" and "Review focus", and
[plans/1091-ledger-survey-writer.md](1091-ledger-survey-writer.md), whose
shape this follows.

Every paragraph removed from draft-reviser's `SKILL.md` has one row
below: its first words, then where it went (file and section) or "cut"
with the reason. A row with no destination is a defect. Line references
are to the old `.claude` copy at `cc65f47a`; the `.agents` and
`.opencode` copies held the same paragraphs, differing only where
`tests/fixtures/skill_harness_phrases.toml` says, and changed the same
way.

## Who cites this skill's text

Grepped before anything moved, over all three harness folders, `docs/`,
`bench/`, `chitragupta/`, `tests/` and `plans/`. Every one still
resolves after the rewrite; none needed an edit.

| Site | What it cites |
| --- | --- |
| `corpus-reviser/SKILL.md:90` (3 copies) | the path `<harness>/skills/draft-reviser/SKILL.md`, heading `## The loop`, "steps 1 through 7" |
| `corpus-reviser/SKILL.md:96`, `:100` | "Step 3 becomes a whole-draft read", "Step 4 stops being a decision" |
| `corpus-reviser/SKILL.md:173` | "`draft-reviser`'s numbered steps 1-7 do not reach its unnumbered riders" |
| `corpus-reviser/SKILL.md:36`, `:179` | "re-grounding mode", "copy-edit mode" |
| `corpus-reviser/SKILL.md:207`, `agenda-reviser/SKILL.md:355` | `.claude/skills/draft-reviser/references/draft-diff.md` |
| `agenda-reviser/SKILL.md:116` (3 copies) | the path, `## The loop`, and four of its parts: reading `scope.md` and `steering.md` first (step 1), mapping onto sections (3), `Edit` not `Write` (5), writing the dossier back (6) |
| `agenda-reviser/SKILL.md:59` | "Bootstrap one as `draft-reviser` describes" (`## When there is no dossier`) |
| `agenda-reviser/SKILL.md:432` | "copy-edit mode" |
| `figure-drawer/SKILL.md:24-25` (3 copies) | "6. Write the dossier back" and "7. Gate, reference, render" |
| `survey-`, `thesis-chapter-`, `textbook-chapter-`, `tutorial-writer`, `deep-research`, `book-assembler` | "copy-edit mode" |
| `tests/test_skill_figure_step.py:71-74` | `### 6. Write the dossier back`, `### 7. Gate, reference, render` |
| `tests/test_skill_references.py:108-111` | `## Copy-edit mode`, `## Acronym-realignment mode`, `## Re-grounding after the corpus moves`, `## When there is no dossier`, each naming its reference |
| `bench/skill_bench_tasks.py:364` | figure-drawer's task: "carry on with draft-reviser's loop: write the dossier back, gate, references, render ..., stamp, the prose check, the verbatim scan and the draft diff" |
| `docs/HARNESS.md:604-605`, `bench/skill_commands.py:100` | the handoff sentence "hand it to `figure-drawer` and come back to step 6" |
| `docs/TOKENS.md:374` | the guardrail "never 'fix' a gate failure by inventing a plausible-looking key -- correct it or remove the claim" |
| `docs/USER-EDITS.md:178-182` | the step-1 offer, quoted ("ITER-RETGEN with you in the generation slot") |
| `chitragupta/dossier/_retrieval.py:230` | "`draft-reviser` step 4 decides no search is needed" |
| `chitragupta/render_output/_cli.py:63`, `tests/test_render_output_cli.py:187` | the skill's name only |

## For SK-5 and SK-7

What `agenda-reviser` and `corpus-reviser` may rely on in
`<harness>/skills/draft-reviser/SKILL.md`, all three copies, as this
branch leaves it:

- **`## The loop`**, holding exactly these, in this order:
  - `### 1. Locate the draft and read its state`: `dossier status`; the
    `CHANGED` drift table and the one-at-a-time rule; the hand-edit
    query offer; "Then read `scope.md` and `steering.md`. **Always
    both, always first**"; `dossier mark-revision`.
  - `### 2. Check the request against the recorded scope`
  - `### 3. Map the change onto sections`: `dossier sections`, read only
    the touched ranges; the two exceptions (argument change, copy-edit).
  - `### 4. Decide whether you need to search at all`: `evidence.md`
    and `rejected.md` first; the `retrieve search`/`evidence` fence; the
    `--y-prev ... --origin reground` fence. It no longer says
    "`survey-writer` step 2": scoring cites
    `.claude/skills-common/references/genre-steps.md` §5. corpus-reviser
    still says "the way `survey-writer` step 2 describes" (`:118`); SK-7
    may point it at `genre-steps.md` §5 too.
  - `### 5. Edit in place, inside the section`
  - `### 6. Write the dossier back`: the bullet list, `revisions.md`'s
    `Sections:` line.
  - `### 7. Gate, reference, render`: gate, references, render x3,
    `dossier stamp`, the `--heading` and tutorial bullets.
  - Then three **unnumbered** `###` steps, still outside 1-7:
    `### Run the prose check`, `### Run the verbatim scan`,
    `### Show what changed`. corpus-reviser's `:173` claim that steps
    1-7 do not reach them stays true.
- Every numbered step now ends on a `Done when` line. Nothing was
  renumbered, merged or renamed.
- `## Copy-edit mode`, `## Acronym-realignment mode`,
  `## Re-grounding after the corpus moves`, `## When there is no dossier`
  and `## Guardrails` keep their headings.
- **Gone:** `## When a whole-corpus pass is what's wanted` (merged into
  the `## When to invoke` table and `## Guardrails`) and `## Sources`.
  `## Collection scoping (#195): inherit it, do not re-ask` is now
  `## Collection scoping: inherit it, do not re-ask`. No file outside
  `plans/` cited any of the three.
- `references/draft-diff.md`, `copy-edit.md`, `acronyms.md`,
  `re-grounding.md` and `no-dossier.md` are unchanged.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/draft-reviser/SKILL.md` | 29,016 | 22,496 |
| `.agents/skills/draft-reviser/SKILL.md` | 29,067 | 22,547 |
| `.opencode/skills/draft-reviser-opencode/SKILL.md` | 29,193 | 22,583 |

The cap in `tests/test_skill_size.py` falls from 30,000 to 23,000, with
its reason. **It stays well above the 8,000 target**, and the plan's
"floor near 5.3 KB" does not survive contact with what this file must
hold:

- 1,000 bytes of frontmatter and title (Decision 7);
- about 1,500 bytes of fenced commands, plus the inline drift-table
  commands (Decision 2);
- **the whole loop, inline.** agenda-reviser and corpus-reviser follow
  `## The loop` by step number, and a model sent there from another
  skill must find each step complete, so no step became a pointer. Of
  the old 29 KB the loop is 13 KB now (it was 15 KB);
- the four mode sections, which stay as routing paragraphs: each
  already points at its own reference, and the three modes the bench
  cannot reach (re-grounding, acronyms, no dossier) were not trimmed
  past their history;
- the tested phrases below, and about 1,000 bytes of project-root
  paths in the eleven citations.

What did move was duplication: of `genre-steps.md` (§1, §2, §5, §7),
of `figures-tables-equations.md` (§1-§6), of the mode references, of
`docs/USER-EDITS.md` and of `docs/WRITING-STANDARDS.md` §2.

## `mathematical-prose.md`: cited, with a condition

**Decision: cite it.** A revision can write mathematics. The old text
already said so in three places: step 6's `math.md` bullet ("any edit
that adds, removes or rewords a quantity"), the equation bullet under
Prose standards ("whether a reworded equation should carry a number"),
and the `math.md` row of the step-1 drift table. A reviser editing a
textbook or thesis chapter's derivation writes the sentences around a
symbol exactly as the drafting skill did, and the reference governs
those sentences. But unlike the two chapter writers, a reviser touches
mathematics only on some runs, so it reads the file only then: "When the
change adds or rewords a symbol, a condition or a derivation, read
`.claude/skills-common/references/mathematical-prose.md` before writing
it" (Prose standards, the quantity bullet). `tests/test_skill_references.py`
pins "Read ... now" for the chapter genres only, so nothing else changed.

## Pinned phrases: what the tests read

"Raw" means the test reads `SKILL.md` as written (whitespace collapsed
at most); "expanded" means `tests/skill_text.py`'s `expanded()`. Every
phrase is still present; the suite is green on it.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_references.py` | "from the project root" no later than 250 characters after the first `.claude/skills…` path, all three copies | raw |
| `test_skill_references.py` | `## Copy-edit mode`, `## Acronym-realignment mode`, `## Re-grounding after the corpus moves`, `## When there is no dossier`, each section naming `.claude/skills/draft-reviser/references/<its file>.md` before the next heading | raw |
| `test_skill_references.py` | every named path exists; the three copies cite the same `` `path` §N `` set; every `## N.` of a reference is cited by some skill | raw |
| `test_skill_references.py` | no backticked skill name and no tool word in any reference | references |
| `test_skill_harness_copies.py` | `skill_path_draft_reviser` (not in this file, in its two citers), `read_ranges` "(`Read` with `offset=<start>`, `limit=<lines>`)", `use_edit_not_write`, `still_edit`, `gate_per_write` "the PostToolUse citation", `one_write`, `edit_never_write_gate` (re-wrapped to match the map's line break) | raw, all copies |
| `test_skill_harness_copies.py` | OpenCode copy: every backticked skill name suffixed `-opencode`; no foreign tool word | raw |
| `test_skill_figure_step.py` | `### 6. Write the dossier back`, `### 7. Gate, reference, render`, `` `figure-drawer` ``, "Touch a figure, touch both forms"; absent: the six `_RIDERS` | raw |
| `test_skill_table_step.py` | `<!-- table:`, `<!-- tableref:`, "§13" | raw |
| `test_skill_pregate_feedback_step.py` | absent: "Critique against the evidence packet" (draft-reviser is excluded) | expanded |
| `test_skill_style_check_step.py` | the `prose-check.md` pointer within 1,400 characters after `-m chitragupta.draft style`; "§9 marks decidable" and "fix none of them" within 1,400 after every mention | raw / expanded |
| `test_skill_verbatim_scan_step.py` | the `verbatim-scan.md` pointer within 1,200 after the scan; `dossier sections … --citekeys --write` then the scan within 200; "tiers_not_run" and "genuine restatement is only detected where the embedding tier can run" within 2,000; "never a condition of presenting"; absent: "Offer the verbatim scan" | raw / expanded |
| `test_skill_retrieval_logging.py` | `--log` within 220 characters of every `retrieve search\|evidence`, references included (re-grounding.md's three) | raw |
| `test_skill_size.py` | each copy under the cap; cap within 1,000 of the largest copy; a reason above 8,000 | raw |
| `bench/skill_commands.py` `expected_commands` | the 21 commands below, from `SKILL.md`, the references it names, and figure-drawer's (the step-6 handoff) | raw, references too |

**No citation was placed inside the prose-check or verbatim-scan steps**
except their own pointers, so no spliced reference moves a rider out of
its window (review focus 1). `mathematical-prose.md`, spliced into the
expanded text under Prose standards, holds none of the commands those
windows are measured from.

**Expected commands, before and after**, all three harnesses, 21 each,
the same set in the same order:

```text
draft gate, draft figures, draft dossier status, draft dossier prune,
draft dossier mark-revision, draft dossier sections,
draft retrieve search, draft retrieve evidence, draft references,
draft render, draft dossier stamp, draft style, review verbatim scan,
draft diff, draft dossier snapshot, draft dossier versions,
draft dossier init, figure new, figure sync, figure check, figure look
```

A first draft cited `render-and-references.md` §1 and §2 from step 7.
That file's §3 holds `draft evidence`, so the expected set grew by a
command no reviser runs. The citation was withdrawn: step 7 already
carries both commands and the reviser-specific `--heading` and
`## Further reading` rules, and its one sentence on render warnings is
all of §2 a reviser needs.

## Where each removed paragraph went

`genre-steps.md` is `.claude/skills-common/references/genre-steps.md`;
`fte.md` is `.claude/skills-common/references/figures-tables-equations.md`.

### Header, When to invoke, read-only

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "Revising a draft by re-running the genre skill that wrote it is the most expensive mistake" | stays, as the opening's second sentence; "This skill exists so that never has to happen" cut as restating the description |
| 14 | "The reason it can work is that the judgment behind a draft is on disk" | stays; "See `docs/DRAFT-ITERATION.md` for why" becomes a conditional citation of `genre-steps.md` §2, which points at the same doc |
| — | (new) "Paths in this skill are from the project root" | added before the first path (`test_skill_references.py`) |
| 22-32 | the When-to-invoke table | stays; rows 27 and 31 (new draft; different genre) merged into one; row 30 gains the "scope change agreed in step 2" trigger from old line 481 |
| 34 | "**Read-only over the corpus layer.** Never run" | the rule and both commands stay, now in `## Guardrails` with the reason (write lock, tens of minutes, the user's to run); the separate paragraph was a duplicate of the guardrail and of `genre-steps.md` §1 |

### Prose standards

| Old line | First words | Went to |
| --- | --- | --- |
| 41 | "`docs/WRITING-STANDARDS.md` applies unchanged. Two of its rules bind harder" | stays; the attribution link from old `## Sources` joins it |
| 45 | "**The reader is already fixed.**" | stays |
| 48 | "**Terminology is already fixed.**" | stays, with old `## Sources`' point (read the glossary before editing, not after) and a citation of `docs/WRITING-STANDARDS.md` §2, which states the one-concept-one-name rule |
| 51 | "**Figures follow the draft's own genre, not a fixed rule of this skill's own.**" | stays, shortened, as the figure bullet's first sentence; the five skill names are cut: "its genre skill" routes the same way and `scope.md`'s `genre:` line names it |
| 59 | "**You may consult a source figure before redrawing one**" | the command stays; "when it is worth running and what you may take" is cut as a description of `fte.md` §1, which the citation reaches; "(Paths in this skill are from the project root …)" moved to the opening |
| 64 | "**Touch a figure, touch both forms.**" | the rule, the pair, panel letters, the log, the `figure-drawer` handoff sentence (unchanged: `bench/skill_commands.py` `HANDOFF` and `docs/HARNESS.md` quote it) and the drop-the-figure fallback stay; "how to find the pair, the thesis chapter's inline `\input`, and why nothing checks it" cut as a description of `fte.md` §2 |
| 76 | "**Tables renumber themselves; ids do not.**" | merged with 83 and 88 into one bullet: the three `ref` markers, the `<!-- table: <id> -->` marker and §13 stay; the rest is `fte.md` §3 |
| 83 | "**A captioned figure renumbers itself too; its id does not.**" | merged (see 76); `FigureNoCaption` cut as a duplicate of `fte.md` §4 |
| 88 | "**An equation renumbers itself; its id does not.**" | merged (see 76); "your judgment call" stays; the §12 pointer now names `docs/writing-standards/mathematics.md` §12 |
| — | (new) "When the change adds or rewords a symbol … read `mathematical-prose.md`" | added: see the decision above |

### Collection scoping

| Old line | First words | Went to |
| --- | --- | --- |
| 95 | "## Collection scoping (#195): inherit it, do not re-ask" | stays; "(#195)" cut as history (Decision 4) |
| 97 | "`scope.md` may carry a `collection:` line" | stays |
| 101 | "This matters more here than it does at drafting time." | stays in one sentence; "(#254)" and "nothing in `retrieval.md` records that the scope moved" cut as history |
| 107 | "A missing line, or `- collection: (whole corpus)`" | stays; "exactly as this skill behaved before this section existed" cut as history. `collection-scoping.md` is deliberately not cited: its rule is to offer the choice, and a reviser never re-asks |

### Steps 1-4

| Old line | First words | Went to |
| --- | --- | --- |
| 118 | "This prints which dossier files are filled in" | stays; "A missing or unreadable ledger is reported rather than raised" cut as a restatement of `dossier status --help`; "(Only the plain form does that; `--json` … exits 0" cut as a duplicate of `re-grounding.md` R2 |
| 127 | "**If `status` reports the draft fingerprint `CHANGED since last stamp`**" | stays; "#454, FEATURE-ROADMAP.md's E3" cut as history; why each finding arises is `docs/USER-EDITS.md` ("What `draft-reviser` finds"), now cited |
| 138 | the five-finding table | stays, both commands inline; "the repair primitive that now exists for this" and "being a primitive, exactly as `dossier sections --citekeys --write` does not" cut as history |
| 146 | "A `not recorded` fingerprint means this draft has never been stamped" | the first sentence stays; "Note what that does *not* excuse any more … (#701)" cut as a duplicate of `docs/USER-EDITS.md` ("`not recorded` is not the same as `CHANGED`") |
| 153 | "**A `CHANGED` fingerprint is also FEATURE-ROADMAP.md's E4 trigger**" | the offer, its quoted wording, the verbatim-query rule, `--y-prev`, the no-offer case and once-per-section stay; the roadmap quote cut as history; "(Editing `outline.md`'s `queries:` alone … see `plans/e4-draft-is-the-query.md`)" kept as one clause, the plan pointer cut |
| 175 | "Then read `scope.md` and `steering.md`. **Always both, always first.**" | stays (agenda-reviser cites it) |
| 179 | "Mark the start of this revision session in `retrieval.md`" | stays, with its command |
| 186 | "`retrieval.md` rows otherwise carry only a date" | one sentence stays (per-revision cost); it gains what `draft-diff.md` "When" states, that the marker's snapshot is the diff's baseline. "Costs nothing if step 4 decides no search" cut as a restatement of `dossier mark-revision --help` |
| 194 | "If the change contradicts `scope.md`'s "Covers"" | stays |
| 206 | "Read **only** the sections the change touches" | stays |
| 211 | "Two exceptions, and only two." | stays, shortened; "see "Copy-edit mode" below for the rest of what that changes" cut: the mode section is where a copy-edit run already is |
| 222 | "Most revisions don't, and a copy-edit pass never does" | stays |
| 227 | "Check `evidence.md`" / "Check `rejected.md`" | stay |
| 235 | "Search only when the change opens genuinely new ground" + fence | stays |
| 242 | "**If step 1's offer was accepted**" + fence | stays |
| 251 | "The CLI bounds `--y-prev` itself (1500 characters, on a word boundary" | one clause stays; the bounds and merge detail cut as a restatement of `retrieve search --help` (also in `docs/USER-EDITS.md`); the `--origin reground` sentence stays |
| 258 | "(or `chitragupta.enrich.embed_index.search()` in place of `search`" | stays; "Score what you keep as `survey-writer` step 2 describes, and record both outcomes" becomes a citation of `genre-steps.md` §5, which is that step's content since PR 1 |
| 264 | "`--log` keeps `retrieval.md` honest" | cut: a duplicate of `genre-steps.md` §1 ("Every retrieval call logs to the draft") |
| 268 | "If `status` reported corpus drift" | stays |

### Steps 5-7

| Old line | First words | Went to |
| --- | --- | --- |
| 278 | "Use `Edit` on the specific passage." | stays (harness phrase) |
| 283 | "Never write a citekey that isn't already in the draft" | stays; "AGENTS.md's invariant is unchanged here" cut as restating the sentence after it |
| 292 | "`evidence.md` -- new kept citekeys, with `relevance:`, a `claim:`" | the field list becomes a citation of `genre-steps.md` §5, which defines the block |
| 294 | "`rejected.md` -- anything newly retrieved and turned down" | stays, shortened |
| 298-318 | `retrieval.md`, `sections.md`, `scope.md`, `steering.md`, `math.md`, `revisions.md` bullets | stay; "see "Copy-edit mode"" cut (the mode's reference covers it) |
| 329 | "Fix and re-run until the gate reports `OK`." | stays |
| 333 | "Once the gate passes, re-stamp the draft fingerprint -- the same point `scope.md`'s corpus line is re-stamped" | the order and command stay; why ("stamping before the gate passes would record a fingerprint for a draft that was never actually accepted") cut as a duplicate of `genre-steps.md` §7, now cited; the re-grounding comparison cut as a duplicate of `re-grounding.md` R4 |
| 342 | "Two things the genre decides" | stays |
| 345 | "**`--heading`, if the draft's references section is number-prefixed.**" | stays; "(#699 aligned the tutorial genre …)" cut as history, its instruction (rename `## Further reading`) kept; "or the numbering is silently dropped" and "Look at the draft's own heading before running this" cut as restating the bullet |
| 357 | "**A tutorial must still run.** `tutorial-writer`'s governing rule" | stays; the governing-rule sentence cut as a duplicate of tutorial-writer's own opening (`tutorial-writer/SKILL.md:20-22`) |

### The three unnumbered steps

| Old line | First words | Went to |
| --- | --- | --- |
| 369-375 | "After step 7 and before presenting" + command + pointer | stays; "what the check can and cannot see, and how to report what it finds" cut as a description of `prose-check.md` |
| 378 | "**Say which findings are yours.**" | stays; "this same skill, one `revisions.md` entry naming the convention" cut as a duplicate of `copy-edit.md` |
| 393 | "The first command matters more here than in any writing skill, and it is the one this skill never had" | one sentence stays; "the one this skill never had" cut as history; the embedding-tier explanation cut as a duplicate of `verbatim-scan.md`, "Why the section map is rebuilt first" |
| 401 | "It earns its place after a revision specifically" | one sentence stays (text rewritten toward a source); "can strand borrowed phrasing" folded into it; the bold not-a-gate clause stays |
| 407 | "Read `.claude/skills-common/references/verbatim-scan.md` now" | stays; "what to show, what the scan could not check" cut as a description of the file |
| 414-420 | "Last, once the entry is written" + command + pointer | stays |

### Modes, routing, guardrails, sources

| Old line | First words | Went to |
| --- | --- | --- |
| 425 | "A grammar pass, a spelling fix, a dialect conversion" | stays; "orthogonal to every axis the loop above is organised around" shortened |
| 431 | "Recognise it from the request -- "fix the grammar"" | "say you are in this mode before you start, naming the convention" stays; the example requests cut as a duplicate of the When-to-invoke row and the description |
| 437 | "Then read `.claude/skills/draft-reviser/references/copy-edit.md` now" | stays |
| 441 | "**Still `Edit`, never `Write`, and now for a second reason.**" | stays, with all three harness phrases; "the safety net that makes an aggressive whole-document rewrite safe to attempt at all" cut as restating the sentence before it |
| 451 | "The prose check above (§9's newest row -- `chitragupta/style_acronym_drift.py`)" | stays; "§9's newest row" and the module path cut as history (unmeasured mode: no command here, and none moved) |
| 459 | "Then read `.claude/skills/draft-reviser/references/acronyms.md` now" | stays, re-wrapped so the `edit_never_write_gate` phrase matches the map |
| 465-473 | "When `python -m chitragupta.corpus sync` adds papers" + pointer | stays (unmeasured mode) |
| 477 | "Everything above optimises for the common case" | cut: the When-to-invoke table and `## Guardrails` state the default and the way out |
| 481 | "The way out is a different skill. **`corpus-reviser`**" | the three triggers go to the When-to-invoke table (re-target row, whole-draft row, which gains the step-2 scope-change trigger); "keeps the dossier" joins the whole-draft row |
| 488 | "The rule was never "never re-search widely"" | "say what you think the request needs and let the user choose" goes to `## Guardrails`; "nothing above tells you how to run a wide search" cut as a duplicate of corpus-reviser's opening (`corpus-reviser/SKILL.md:15`) and `docs/DRAFT-ITERATION.md:523` |
| 493 | "What stays never, in either skill, is re-running the genre skill." | `## Guardrails`, first bullet, with its reason |
| 498 | "Drafts written before `chitragupta/dossier/` existed" | stays (unmeasured mode) |
| 506 | "- **Never re-run the genre skill to make a change.**" | stays, with old 493's reason |
| 510, 514 | "- **Never turn this into a wide pass.**", "- **Never refuse a wide pass either.**" | merged into one bullet |
| 517 | "- **Never run `python -m chitragupta.corpus sync` or `python -m chitragupta.enrich`.**" | stays, with old 34's reason |
| 518-531 | fabricate, scope/reader/terminology, copy-edit claim, rejection, report what you didn't do | stay unchanged (`docs/TOKENS.md:374` quotes the first) |
| 532 | "## Sources" | cut as a heading; its link joins Prose standards |
| 534 | "The prose standards this skill inherits are documented, with per-principle attribution" | the link stays, in Prose standards |
| 537 | "What bears on revision specifically is Google's *Technical Writing Courses*" | the rule is `docs/WRITING-STANDARDS.md` §2 ("Never two names for one concept"), now cited from the Terminology bullet, with the reviser's consequence (read the glossary before editing); the attribution is `docs/WRITING-STANDARDS.md`'s Sources, item 3 |

### Totals

- **71 rows** for the old file, one per paragraph, list item, table or
  fence (a row may cover adjacent items that went the same way), plus 3
  rows marked "(new)" for text added.
- **Stay, whole or shortened in place, with nothing cut or moved: 26.**
- **Moved: 22 rows** send text behind a citation (`genre-steps.md` §1,
  §2, §5, §7; `figures-tables-equations.md` §1-§6; `docs/USER-EDITS.md`;
  `docs/WRITING-STANDARDS.md` §2) or to another part of `SKILL.md` (the
  When-to-invoke table, `## Guardrails`, Prose standards).
- **Cut: 32 rows** cut some of their text, each with its reason:
  history (an issue number, "newest row", "never had"), a restatement of
  `--help`, a description of a reference the pointer reaches, or a
  duplicate of a named file and section. A row can be both moved and
  cut.
- **Without a destination: none.**

### What was added, not moved

A `Done when` line on each of steps 1-7 and the three unnumbered steps
(Decision 4); a conditional citation of `mathematical-prose.md`;
"Paths in this skill are from the project root"; a one-line
`## The loop` preamble saying the unnumbered steps follow steps 1-7; and
the sentence that `mark-revision`'s snapshot is the diff's baseline,
which `draft-diff.md` already stated. No reference file changed.

## The bench

Skill `draft-reviser`, Claude Code, 3 skill-only runs after, against the
3 before rows in `bench/results/2026-11-14-skill-bench-skill-only/tier2.json`.
The task (survey-writer, then a revision with a copy-edit on a draft
seeded with an unstamped section) reaches the ordinary loop, the
`CHANGED` drift table, copy-edit mode and "Show what changed". **It
cannot reach re-grounding, acronym realignment, the no-dossier bootstrap
or a whole-corpus hand-off; those are unmeasured.** For them only
history and duplicated rationale moved, and no command left `SKILL.md`.
The after rows are in
`bench/results/2026-11-15-draft-reviser-shrink/tier2.json`.

**Verdict: pass** (`--compare` exit 0). Every command is 3/3 or 0/3 in
both arms, and the same ones: `draft dossier status`, `mark-revision`,
`sections`, `retrieve evidence`, `gate`, `references`, `render`, `stamp`,
`style`, `review verbatim scan`, `draft diff`, `dossier snapshot` and
`dossier versions` ran in every run of both; `draft figures`,
`dossier prune`, `retrieve search`, `dossier init` and figure-drawer's
four ran in none, in either arm, as the task gives them no occasion. All
3 after runs passed their gate and their prerequisite survey's gate, and
none ran `corpus sync` or `enrich`. Each after run opened `copy-edit.md`,
`prose-check.md`, `verbatim-scan.md` and `draft-diff.md`; the before
runs opened the same four, except run 1, which skipped `prose-check.md`.
No run opened `genre-steps.md`: the task keeps nothing new, so §5's
condition never fired. After runs took 83-101 seconds; before, 117-135.

## For the plan

- PR 4's row: "floor is about 5.3 KB" is not reachable while
  agenda-reviser and corpus-reviser follow `## The loop` by step: the
  loop has to stay complete, inline, at about 13 KB. The cap is 23,000
  with a reason.
- PR 4's "decide whether it cites `mathematical-prose.md`": decided,
  yes, behind a condition (above).
- The plan's "one reference file per skill" does not fit a skill with
  modes. draft-reviser keeps its five, each read only on its own branch,
  and gained none.
- PR 5 and PR 7: see "For SK-5 and SK-7" above. corpus-reviser's
  `:118` ("the way `survey-writer` step 2 describes") is stale since PR 1
  and wants `genre-steps.md` §5.
