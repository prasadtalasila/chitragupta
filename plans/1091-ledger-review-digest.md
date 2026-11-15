# Move ledger: review-digest (#1200, SK-3)

Status: **built on `feat-1091-review-digest`, above the 12,000 target,
as Decision 1's 2026-11-14 answer allows.** Written 2026-11-15 against
`cc65f47a` (6.173.3), for [plans/1091-skill-shrink.md](1091-skill-shrink.md)
PR 3, in the shape of [the survey-writer ledger](1091-ledger-survey-writer.md).

**Written for** the reviewer of PR 3. **Assumed:** the plan's
"Decisions" and "Review focus", and [docs/HARNESS.md](../docs/HARNESS.md)
on the three `SKILL.md` copies.

Every paragraph removed from review-digest's `SKILL.md` has one row
below: its first words, then where it went (file and section) or "cut"
with the reason. A row with no destination is a defect. Line references
are to the old `.claude` copy at `cc65f47a`; the `.agents` copy was
byte-identical to it and the `.opencode` copy differed only by the
`-opencode` suffixes, and both changed the same way.

## Size

| Copy | Before | After |
| --- | ---: | ---: |
| `.claude/skills/review-digest/SKILL.md` | 16,881 | 16,018 |
| `.agents/skills/review-digest/SKILL.md` | 16,881 | 16,018 |
| `.opencode/skills/review-digest-opencode/SKILL.md` | 16,989 | 16,126 |

review-digest joins `GENRES` in `tests/test_skill_size.py`, so its
target is 12,000. **Its cap stays at 17,000**, now with a reason of its
own instead of "shrinks in its own PR": the largest copy is within the
1,000-byte slack of it, and nothing is compressed to fit (Decision 1, as
answered on 2026-11-14). What the 16 KB holds, on the `.claude` copy:

- about 1,080 bytes of frontmatter and title, which Decision 7 leaves
  alone;
- about 760 bytes restoring the six passages #1173 cut (below), which
  the plan requires back;
- about 2,600 bytes of fenced commands (16 of them) and the format
  example, which Decision 2 keeps;
- about 1,900 bytes for "The format": the citation rules every run
  writes by, which no other file states for a digest;
- about 1,400 bytes for steps 16-18, the digest report, its reading
  order and the presentation, which every run does and which exist in
  no shared file;
- about 1,000 bytes of project-root paths in 15 pointers, and a
  one-line `Done when` on each of 19 steps (about 900 bytes).

The deduplication itself removed about 1,600 bytes: the corpus-layer
bullets, the dossier procedure, the reread checklist, the three goals,
the paragraph rules, the repair rules and Sources.

## Pinned phrases: what the tests read

Built before the rewrite. "Raw" means the test reads `SKILL.md` as
written; "expanded" means `tests/skill_text.py`'s `expanded()`, which
splices each named reference in after its path. Every phrase below is
still present (or still absent) after the rewrite; the suite is green.

| Test | Phrase, window or absence | Reads |
| --- | --- | --- |
| `test_skill_references.py` | "from the project root" within 250 characters after the first `.claude/skills…` path, all three copies | raw |
| `test_skill_references.py` | every named `.claude/skills…` path exists; the three copies cite the same `` `path` §N `` set; every cited section exists; every `## N.` of a reference is cited by some skill (the new `review-digest/references/digest.md` §1 is cited by step 17) | raw |
| `test_skill_references.py` | no backticked skill name and no tool word in any reference, including the new `digest.md` | the references |
| `test_skill_harness_copies.py` | the copies differ only by the phrase map; the `.opencode` copy suffixes every backticked skill name; no copy names another harness's tools | raw, all copies |
| `test_skill_frontmatter.py` | the frontmatter, unchanged | raw |
| `test_skill_pregate_feedback_step.py` | absent: "Critique against the evidence packet" (review-digest is in `_EXCLUDED_SKILLS`); no new citation splices it in | expanded |
| `test_skill_verbatim_scan_step.py` | review-digest is a `_HELPERS` skill: it names no scan step; "No verbatim scan" stays | expanded |
| `test_skill_style_check_step.py` | the pointer `` `.claude/skills-common/references/prose-check.md` `` within 1,400 characters after `-m chitragupta.draft style`, and "§9 marks decidable" and "fix none of them" in that window; step 15 carries no new citation before its pointer | raw, then expanded |
| `test_skill_retrieval_logging.py` | `--log` within 220 characters of every `retrieve search` or `evidence` invocation, in every `.md` under `.claude/` | raw, references too |
| `test_skill_size.py` | each copy under 17,000; the cap within 1,000 of the largest copy; a reason, since 17,000 is above the 12,000 genre target | raw |
| `test_writing_standards_layers.py` | `genres/digest.md` is a row of the index table in `docs/WRITING-STANDARDS.md`; every link and cited section in it resolves | the docs |
| `bench/skill_commands.py` `expected_commands` | the commands below | raw, references too |

**Expected commands, before and after** (`.claude` copy plus the
references it names). Before, 12:

```text
review digest, draft gate, draft retrieve search, draft figures,
corpus ledger, draft dossier init, draft dossier sections,
draft references, draft render, review synthesis, draft style,
draft dossier stamp
```

After, 15: the same 12, plus `review support` (restored, below),
`draft dossier export` (the backup `genre-steps.md` §7 says the step
names) and `draft evidence`. The last is only there because step 13 now
cites `render-and-references.md`, whose §3 renders a survey's evidence
sidecar; step 13 says to skip §3, and a digest never runs it. None of
the three ran in the before arm, so each scores 0/3 against 0/3 and
cannot fail the comparison.

## The six passages #1173 cut, restored

Each was checked against the code on `cc65f47a` before it went back.
All six still hold, so all six are restored, in their original wording
except where noted.

| Passage | Was at | Checked against | Went to |
| --- | --- | --- | --- |
| "If the enrichment extra is installed, `python -m chitragupta.review support content/drafts/<topic>/<name>.md` scores each citing sentence with an NLI entailment model and is worth running on the `unsupported-text` items, which `review digest` judges lexically only. `docs/VERBATIM-DIGEST.md` says what each check can and cannot see." | `f72a8e8f^` :295-300 (step 14) | `review support --help`; `chitragupta/review/claim_support.py` ("Needs the `enrich` extra", "a real NLI entailment model, never lexical overlap"); `docs/VERBATIM-DIGEST.md`, "Lexical support, and what the NLI `support` aid adds" | `SKILL.md` step 16 (the old step 14), verbatim. `references/digest.md` §1 adds, from that same `docs/VERBATIM-DIGEST.md` section, what the repair is when the NLI report marks an `unsupported-text` sentence entailed |
| "Never guess a key, never rewrite one." | `c3bc0b9` :222, `f72a8e8f^` :222 (step 7) | the one rule (`CLAUDE.md`) | `SKILL.md` step 7, verbatim |
| "None of this is a precondition: a corpus parsed without `docling_images` has no crops, the command says so, you note it to the user in one line, and the digest goes on from the prose alone. Never run the enrichment stage yourself to change that." | `c3bc0b9` :195-198 (step 4) | `chitragupta/draft_figures.py`: with no `<citekey>.figures.json` (which the Docling stage writes only with `[enrich].docling_images` on) it prints the reason, naming the stage and the setting, and exits 0; `docs/VERBATIM-DIGEST.md`, "Figures" | `SKILL.md` step 4, verbatim. Inline rather than in `digest-copying.md` §3, because every run reaches the figures command and the command's own message names `python -m chitragupta.enrich --stages docling`, which the guardrail answers |
| "All three land at `content/rendered/<topic>/<name>.{tex,pdf,md}`. This needs only bare `python` plus `pandoc` (and, for pdf, LuaLaTeX) on PATH." | `c3bc0b9` :259-261 (step 12, now 13) | `draft render --help` ("content/rendered/<mirrored path>"); `.claude/skills-common/references/render-and-references.md` §2, which says both in the same words ("a draft at `content/drafts/<topic>/<name>.md` renders to `content/rendered/<topic>/<name>.{tex,pdf,md}`"; "This needs only bare `python` plus `pandoc` (and, for pdf, LuaLaTeX) on PATH") | restored by citation: step 13 now reads `render-and-references.md` §2, "where the renders land, what they need, and what to do with a warning", rather than repeating it. Step 12 cites §1 the same way |
| "Pandoc-style citations only (`[@citekey, p. 4]`, `[@a; @b]`)." | `c3bc0b9` :126, `f72a8e8f^` :126 ("A citation covers…" list) | the gate's and the renderer's citation syntax; `[see @key]` is pandoc's prefix form | `SKILL.md` "The format", last bullet, verbatim |
| "It is a hint: the report says which page it actually found the text on." | `c3bc0b9` :121-123, `f72a8e8f^` :121-123 | `docs/VERBATIM-DIGEST.md`, "Pages, and what a page note means" ("The page in a citation is a **hint**… reports the page or pages the run was actually found on") | `SKILL.md` "The format", first bullet, with the clause before it that #1173 also cut: "not the printed page number" |

## Where each removed paragraph went

`genre-steps.md` is `.claude/skills-common/references/genre-steps.md`;
`digest.md` is `.claude/skills/review-digest/references/digest.md`;
`genres/digest.md` is `docs/writing-standards/genres/digest.md`;
`digest-copying.md` and `render-and-references.md` are under
`.claude/skills-common/references/`.

### Header, corpus layer, collection scoping

| Old line | First words | Went to |
| --- | --- | --- |
| 9 | "A verbatim digest is a **survey written in the sources' words**" | stays; its last sentence, "It must read on its own…", goes to `genres/digest.md`, "What a digest owes its reader" |
| 20 | "It is private study text, not a deliverable" | stays |
| 25 | "Three goals, in this order" and the list | `genres/digest.md`, "What a digest owes its reader"; the pointer under the opening names them |
| 32 | "A digest is a draft like any other" | stays, with the `agenda-reviser` prohibition |
| 37 | "Paths in this skill are from the project root." | stays; the pointer to `genres/digest.md` joins it |
| 39 | "## Shared corpus layer (read, don't regenerate)" (heading) | becomes "## Before you start", as in survey-writer |
| 41 | "`content/ledger.sqlite` -- per-citekey status" | `genre-steps.md` §1 |
| 42 | "`content/parsed/<citekey>.passages.json` -- the Docling sidecar" | stays, as its own paragraph under "Before you start": it is the digest's alone and every run copies from it |
| 49 | "`python -m chitragupta.draft retrieve search` … finds candidates; `... evidence`" | `genre-steps.md` §1 (what each call returns); the search command stays in step 1 |
| 52 | "`python -m chitragupta.draft figures <citekey>` lists one paper's figures" | the command stays, fenced, in step 4; what it lists is `digest-copying.md` §3 |
| 55 | "**Read-only means read-only: never run `python -m chitragupta.corpus sync`" | the rule and both commands stay; "Both take the pipeline's write lock and are the user's" goes to `genre-steps.md` §1 |
| 59 | "**If the ledger is empty, stop.**" | stays, with its command |
| 65 | "If it reports no items, or none with status `parsed`" | stays, with the remedy command, in survey-writer's wording; "Do not draft around it, do not sync, do not cite" goes to `genre-steps.md` §1 |
| 69 | "## Collection scoping (#195)" | stays as "## Collection scoping"; "(#195)" cut as history (Decision 4) |

### When to invoke, the format

| Old line | First words | Went to |
| --- | --- | --- |
| 82 | "\"Give me a digest of what the corpus says about X.\"" | cut: the frontmatter description routes it ("a digest, study notes…") |
| 83 | "\"Study notes on X, in the papers' own words.\"" | cut: as above |
| 85 | "Not for a summary in your own words (`survey-writer`)" | stays |
| 91 | "Copied runs are plain prose closed by a citation" and the example | stays |
| 105 | "**One paper per copied run**" | stays, with two passages restored (above) |
| 107 | "**Your own sentences** sit between runs" | stays |
| 111 | "**`<!-- own: why -->`** on the line directly above" | stays |
| 115 | "`.claude/skills-common/references/digest-copying.md` says what \"copied exactly\" means … read it before step 6" | cut as a pointer: step 6 now cites `digest-copying.md` §1 and §2 at the point of use, step 4 §3 and §4, and step 17 §4 and §5 |

### Steps 0-9

| Old line | First words | Went to |
| --- | --- | --- |
| 121 | "The same steps as `survey-writer`, in the same order." | rewritten so it is true again: survey-writer's #1215 merge made its prose check, scan and stamp 15, 16 and 17. The digest's tail is reordered to match (steering 14, prose check 15, digest report 16, the repair pass 17, stamp 18), so steps 0-15 share survey-writer's numbers, 16 replaces its scan, 17 is the digest's own, 18 is its 17 |
| 125 | "0. **Name the reader and the scope, and open the dossier.** Settle with the user" | title, command and the path sentence stay; what the path decides goes to `genre-steps.md` §3, cited |
| 134 | "Fill in `scope.md`'s **Reader**, **Covers**" | `genre-steps.md` §3 (the fields); "the one definition the whole digest uses" to `genres/digest.md`, "What a digest owes its reader"; `Done when` names the fields |
| 136 | "Settle the **dialect** … it governs your own sentences" | settling it: `genre-steps.md` §3; that it governs your sentences alone: `genres/digest.md`, "The paragraph, and your own sentences in it" |
| 138 | "Name the reader as someone who has read none of the papers" | `genres/digest.md`, "What a digest owes its reader" |
| 142 | "1. **Retrieve per theme, over-fetching.**" | stays, the command now fenced; the `outline.md` clause cites `genre-steps.md` §4 |
| 148 | "2. **Score every candidate, and record its main passage as a `quote:`.**" | title stays; the block format and `rejected.md` go to `genre-steps.md` §5, cited; the digest's one difference from §5 (one verbatim `quote:` per kept source, no marks, no page) stays, as does what checks it |
| 157 | "3. **Re-search a thin theme**" | stays; how goes to `genre-steps.md` §6, cited |
| 160 | "4. **Cluster, then choose passages that stand on their own.**" | stays; "a passage that opens on \"where\", \"thus\" or \"these\" starts one sentence earlier" is cut as a duplicate of `digest-copying.md` §4 ("Start the run one sentence earlier"), now cited there |
| 171 | "5. **Find the disagreements.**" | stays |
| 176 | "6. **Draft the survey, copying exactly.**" | stays, with its list and markers |
| 177 | "**Opening** (`<!-- own: scope -->`): who the digest is for, what it covers and what it deliberately leaves out" | the marker stays; the content is `genre-steps.md` §3 ("write the scope statement into the draft's opening, including what is deliberately excluded") |
| 179 | "**Framing** (`<!-- own: framing -->`)" | stays |
| 182 | "**One section per theme.** Each body paragraph opens with a sentence of yours" | the `single-source` marker stays; the paragraph's shape, "never one paper after another", "Define a term at first use" and "never write \"the book\"" go to `genres/digest.md`, "The paragraph, and your own sentences in it", cited |
| 190 | "**A comparison table**, with a caption and an id" | stays, now citing `docs/writing-standards/tables.md` §13 directly; "Introduce it before it and read a pattern off it after it" cut as a duplicate of `tables.md` §13, "The sentence that reads the table" |
| 195 | "**Disagreements**, inside the theme they belong to, both sides copied." | folded into the theme item ("its disagreements inside it"); both sides copied: step 5 and `genres/digest.md` |
| 197 | "**Gap analysis** (`<!-- own: gap analysis -->`): what the corpus does not cover" | the marker stays; what it holds goes to `genres/digest.md`, "The paragraph, and your own sentences in it" |
| 201 | "Copy each run from `content/parsed/<citekey>.passages.json`" | stays; the pointer to `digest-copying.md` §1 and §2 now comes first; `mathematical-prose.md` stays with a condition (below) |
| 209 | "7. **Never write a citekey you did not get from a retrieval result.**" | stays, with "Never guess a key, never rewrite one." restored |
| 214 | "8. **Map sections to citekeys.**" | stays |
| 220 | "9. **No drawn figure**" | stays |

### Steps 10-18

| Old line | First words | Went to |
| --- | --- | --- |
| 222 | "10. **Read it as someone who has opened none of the papers.**" | title and "replaces `survey-writer`'s step 10" stay (still true: its critique is still step 10); the six-item checklist goes to `genres/digest.md`, "The reread", cited; the three fix moves stay |
| 235 | "11. **Gate.**" | stays |
| 243 | "12. **Build the References section**" | stays, now citing `render-and-references.md` §1 |
| 249 | "13. **Render tex, pdf and md.**" | stays, now citing `render-and-references.md` §2; "A `[missing-binary]` or `[error]` is a one-line warning in chat, never a block" cut as a duplicate of §2; the `[math]` sentence and "No evidence sidecar" stay |
| 262 | "14. **Run the digest report and the synthesis report.**" | now step 16, after the prose check, as survey-writer's scan is; otherwise stays, with the NLI `support` paragraph restored |
| 277 | "15. **Record any steering**" | now step 14, as in survey-writer |
| 280 | "16. **Run the prose check.**" | now step 15, as in survey-writer; text unchanged |
| 293 | "17. **Work the report, only if the user asked for a pass.**" | title, "Say what the report found and ask", both commands, "Log every attempt in the dossier's `revisions.md`" and the closing render sentence stay |
| 297 | the five per-class repairs (`unsupported-text` … `unquoted-text`) | `digest.md` §1; the `digest-copying.md` §4 and §5 citation stays in the step |
| 316 | "Keep the repair only if the gate passes, the item is in `resolved`" | `digest.md` §1, with what goes in a `revisions.md` row and the stop rule; the stop rule is also the step's `Done when` |
| 326 | "18. **Stamp the draft fingerprint, then present.**" | stays, citing `genre-steps.md` §7 first; the presentation list and the `draft-reviser` sentence stay; `python -m chitragupta.draft dossier export` added, since §7 says the step names the export |
| 341 | "## Sources" and its paragraph | `genres/digest.md`, "What a digest owes its reader", as "Why it may copy at all" |

### Totals

- **55 rows**, one per paragraph, list item or heading of the old file
  that changed or moved (the fences that stayed whole are not listed).
- **Stay whole or nearly: 27**, some with a citation added or a clause
  moved out.
- **Moved: 25 rows** send text to `genre-steps.md` (12, all
  citations of existing text), `genres/digest.md` (11), `digest.md` (2)
  or `digest-copying.md` / `render-and-references.md` (by citation).
- **Cut: 7 rows**, each a duplicate of a named file and section, the
  frontmatter description, or history.
- **Without a destination: none.**

### What was added, not moved

- The six restored passages (above).
- A `Done when` on each of the 19 steps, and a condition on each
  pointer (Decision 4).
- `python -m chitragupta.draft dossier export <topic>/<name>` in step
  18, which `genre-steps.md` §7 assumes the step names.
- In `digest.md` §1, one sentence from `docs/VERBATIM-DIGEST.md`, "Lexical
  support, and what the NLI `support` aid adds": an `unsupported-text`
  item the NLI report marks entailed is cited correctly, not deleted.
- In `genres/digest.md`, the framing sentences a genre file opens with,
  and "Organise it around what the sources agree and disagree on",
  which restates the opening paragraph of `SKILL.md` as a rule.

## Decisions this PR made

**A genre file, not only the skill's reference.** What applies to a
digest alone and is a rule the draft is held to (the three goals, the
reader, the paragraph, the drafter's own sentences, figures and
equations, the reread, and why it may copy) came to about 4.3 KB, above
the roughly 3 KB the index asks of a layer file, so it is
`docs/writing-standards/genres/digest.md`, named by
`dossier init --genre digest`'s value. It is a row of the index table in
`docs/WRITING-STANDARDS.md`, in `mkdocs.yml`'s nav after `genres/survey.md`,
and named in `genres/README.md`.

**The skill's own reference holds one section.** Only the repair pass
(step 17) is both the digest's alone and reached by some runs only, so
`references/digest.md` has a single section. The figure, equation,
copying and dangling-reference procedure was already shared in
`digest-copying.md` and stays there.

**`mathematical-prose.md` stays cited, with a condition.** A digest
writes mathematics as well as copying it: `digest-copying.md` §2 has an
equation of the drafter's own ("A relation you write to compare two
sources, or a symbol you define in a sentence of yours") set as a
`<!-- math -->` display, and the Tier 2 task asks for one (the rolling
z-score rule). The sentences around such a symbol are what
`mathematical-prose.md` governs. It does not edit the sources'
mathematics, which is copied from the `formula` passages, so the
pointer now reads "Before you write a sentence of your own around a
symbol, or an equation of your own", where it read "for your own
sentences around a symbol".

**The tail is reordered, not just renumbered.** "The same steps as
`survey-writer`, in the same order" was false twice over after #1215:
survey-writer's prose check, scan and stamp became 15, 16 and 17, and
the digest ran its report (in the scan's place) before the prose check
and steering. Rather than a sentence listing the differences, the
digest's tail now follows survey-writer's order: steering 14, prose
check 15, digest report 16. No file outside the skill cites a digest
step number (`git grep` for "step" near "digest" in `docs/`,
`chitragupta/` and the skills), and the two internal references ("step
13's renders", "this skill's step 17") still point at the same steps.

## For the plan

- PR 3's row can be marked done on this branch: all six passages are
  restored, `:121`'s sentence is true again, and `:223`'s reference
  (survey-writer's step 10) was already true, since #1215 kept the
  critique at 10.
- review-digest's cap stays at 17,000, above the 12,000 target, with a
  reason. As for survey-writer, the floor is commands, the format the
  report reads, and the restored passages.
- `docs/VERBATIM-DIGEST.md`'s list of the workflow ("a read as the
  reader, steering, the prose check, the fingerprint stamp") already
  matches the new order; nothing there changed.
