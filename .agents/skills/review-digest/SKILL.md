---
name: review-digest
description: Builds a verbatim digest -- a private study survey of a topic, shaped like a literature survey but with its body in the source papers' own words, copied exactly from parsed PDFs, a citation closing each copied run, equations typeset -- through survey-writer's workflow, then runs `python -m chitragupta.review digest` on it and works the report down on request. Every citekey comes from content/ledger.sqlite via chitragupta.retrieval, never invented. Triggers when the user asks for a digest, study notes, a reading summary or an extract "in the papers' own words" on a topic. The digest is never a deliverable and never a source for a survey, chapter or any other draft; to summarise in your own words use survey-writer, and to change a digest that exists use draft-reviser. Must run `python -m chitragupta.draft gate` and `review digest` before presenting, and refuses (telling the user to run `python -m chitragupta.corpus sync`) if the ledger is empty.
tags: [digest, study-notes, verbatim, citation]
---

# review-digest

A verbatim digest is a **survey written in the sources' words**. It has
a survey's shape -- a reader and a scope, a framing, one section per
theme, a comparison table, the disagreements made visible, a gap
analysis -- and a survey's paragraph: each one braids passages from two
or more papers around what they agree and disagree on. What differs is
the body's wording: each passage is copied exactly from a parsed PDF and
closed by its citation, with no quotation marks, and the drafter's own
sentences are few, short, and there to compare, contrast or define.

It is private study text, not a deliverable, and **it is never a source
for drafting anything else**: its wording is the corpus's own, and the
verbatim scan (`review verbatim scan`) flags it the moment it reaches a
survey or a chapter.

A digest is a draft like any other: named by the user, kept at
`content/drafts/<topic>/<name>.md`, with a dossier whose `scope.md`
records `- genre: digest`. **Never run `agenda-reviser` on a digest**:
its `verbatim-run` repair paraphrases copied text unattended.

Paths in this skill are from the project root. Its writing rules -- the
three goals, the paragraph, your own sentences, figures, equations and
the reread -- are in `docs/writing-standards/genres/digest.md`: read it
before step 0.

## Before you start

**The corpus is read-only: never run `python -m chitragupta.corpus sync`,
and never run `python -m chitragupta.enrich` or any `chitragupta/enrich/*`
build stage.** Before the first retrieval, read
`.claude/skills-common/references/genre-steps.md` §1: what the corpus
holds, and why those are the user's to run.

You copy from `content/parsed/<citekey>.passages.json`, the Docling
sidecar: reading-ordered text, never memory. Its `formula` passages are
the source's equations. A source with no sidecar cannot be checked: do
not copy from `content/parsed/<citekey>.txt`, whose text has no reading
order. Tell the user which cited sources lack one and that `chitragupta
enrich --stages docling` (the user's to run, never yours) gives them one.

**If the ledger is empty, stop.** Check before anything else:

```bash
python -m chitragupta.corpus ledger
```

If it reports nothing `parsed`, say what you checked and found, and stop.
Tell the user to run `.venv-full/bin/python -m chitragupta.corpus sync`
and come back.

## Collection scoping

```bash
python -m chitragupta.corpus ledger --collections
```

If it reports none, record `- collection: (whole corpus)` in `scope.md`'s
header and skip this section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run.

## When to invoke

Not for a summary in your own words (`survey-writer`), not for changing
a digest that exists (`draft-reviser`), and not for anything that will
be submitted or published.

## The format

Copied runs are plain prose closed by a citation that covers every
sentence back to the previous citation or the start of the paragraph.
Your own sentences are closed by a `see` citation, which the report
checks for support instead of for copying:

```markdown
Copied sentence. Copied sentence. [@key, p. 4-5] Your own sentence
comparing the two. [see @key; @other] Another copied sentence.
[@other, p. 12]

<!-- own: gap analysis -->
A paragraph that is wholly yours, such as the framing or the gap analysis.
```

- **One paper per copied run**, closed by its citation and page: `p. N`
  or `pp. N-M`, counting the PDF's pages from 1 as the parser does, not
  the printed page number. It is a hint: the report says which page it
  actually found the text on.
- **Your own sentences** sit between runs, never inside one. Close each
  with `[see @a; @b]` naming the papers it rests on; one no source
  backs is `unsupported-text`, and one with no citation at all is
  `unquoted-text`.
- **`<!-- own: why -->`** on the line directly above a paragraph
  declares the whole paragraph yours: the framing, the gap analysis.
  Table rows are yours by construction. Use it for those, not to hide a
  run that failed to match.
- Pandoc-style citations only (`[@citekey, p. 4]`, `[@a; @b]`).

## Process

`survey-writer`'s steps, in its order. Steps 0-15 keep its numbers (this
skill has no 2a); step 16 replaces its verbatim scan, step 17 is this
skill's own, and step 18 is its step 17. Where a survey step exists to
keep source wording out of the draft, this one says what replaces it.

0. **Name the reader and the scope, and open the dossier.** Before
   creating it, read `.claude/skills-common/references/genre-steps.md`
   §2 and §3: the path, `scope.md`, the dialect, the acronym vocabulary
   and the fingerprint. Settle the path with the user. A digest always has a
   topic directory, `content/drafts/<topic>/<name>.md`: §3's flat default
   does not apply here, since the figure crops go in the topic's
   `figures/`. Then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<topic>/<name>.md --genre digest
   ```

   Done when `scope.md` records the reader, the scope, the glossary and
   `language:`.

1. **Retrieve per theme, over-fetching.** First check for an
   `outline.md`:

   ```bash
   python -m chitragupta.draft dossier outline content/drafts/<topic>/<name>.md --check
   ```

   If it passes, it settles the themes: read
   `.claude/skills-common/references/genre-steps.md` §4, then run each
   section's declared queries verbatim; a thin theme's reformulations
   are `--origin extended`.

   ```bash
   python -m chitragupta.draft retrieve search "<declared query>" --k 15 --origin declared --log content/drafts/<topic>/<name>.md
   ```

   With no `outline.md`, or one that fails `--check`, settle three to
   six themes with the user, and for each theme:

   ```bash
   python -m chitragupta.draft retrieve search "<query>" --k 15 --log content/drafts/<topic>/<name>.md
   ```

   Then read the candidates' sidecar text. Done when every theme's
   query has run, each with `--log`.

2. **Score every candidate, and record its main passages as
   `quote:` lines.** Before your first `evidence.md` block, read
   `.claude/skills-common/references/genre-steps.md` §5, with one
   difference: a digest records, for each kept source, a `quote:` line
   per passage you lean on most (not one per copied run), verbatim,
   with no quotation marks and no page. `claim:` stays in your own words and is what your
   `see` sentences are drafted from. §5's two rules on drafting, prose
   only from `claim:` and a `quote:` only inside quotation marks, do not
   bind a digest's body: it is copied runs, each closed by its citation,
   with no marks. `review quotation` checks the
   `quote:` lines; `review digest` checks every other copied run where it
   stands. Done when every candidate is in `evidence.md` or
   `rejected.md`.

3. **Re-search a thin theme** with a reformulated query before settling
   for a weak passage; when one comes up thin, read
   `.claude/skills-common/references/genre-steps.md` §6. Done when each
   theme is covered, or reported thin after real attempts.

4. **Cluster, then choose passages that stand on their own.** Group the
   kept sources by what they say, not by paper. For each theme choose
   passages -- a sentence to a paragraph -- that make one point each
   and need nothing before them
   (`.claude/skills-common/references/digest-copying.md` §4): a whole
   paragraph beats three sentences from three places. Aim for two or
   more papers per point. For each kept source, list its figures:

   ```bash
   python -m chitragupta.draft figures <citekey>
   ```

   Keep a crop where a figure says what a paragraph circles around
   (`.claude/skills-common/references/digest-copying.md` §3). None of
   this is a precondition: a corpus parsed without `docling_images` has
   no crops, the command says so, you note it to the user in one line,
   and the digest goes on from the prose alone. Never run the
   enrichment stage yourself to change that. Done when every theme has
   its passages and every kept source's figures were listed.

5. **Find the disagreements.** Where two papers say opposite things,
   both will be copied, each under its own citation, and a `see`
   sentence of yours will name the disagreement. Never resolve one
   silently. Done when each is noted for the draft.

6. **Draft the survey, copying exactly.** In this order:
   - **Opening** (`<!-- own: scope -->`): the reader and the scope.
   - **Framing** (`<!-- own: framing -->`): one paragraph on why the
     topic matters and how the sections divide it, closed by `see`
     citations.
   - **One section per theme**, each paragraph built as
     `docs/writing-standards/genres/digest.md` says, its disagreements
     inside it. Where one paper genuinely is the only source for a
     point, keep it and write `<!-- single-source: why -->` on the line
     above.
   - **A comparison table**, with a caption and an id
     (`docs/writing-standards/tables.md` §13): one row per approach, a
     citekey column carrying `[@key]`, core idea and stated limitation
     in short phrases of your own.
   - **Gap analysis** (`<!-- own: gap analysis -->`).

   Before the first run, read
   `.claude/skills-common/references/digest-copying.md` §1 and §2. Copy
   each run from the sidecar, words and numbers exactly, typography
   cleaned. Every equation, copied or your own, is typeset in a
   `<!-- math -->` display mapped in the dossier's `math.md`; one a run
   introduces or explains is never left out, and none is ever written
   as text. Before you write a sentence of your own around a symbol, or
   an equation of your own, read
   `.claude/skills-common/references/mathematical-prose.md`. Done when
   every section is drafted.

7. **Never write a citekey you did not get from a retrieval result.**
   `python -m chitragupta.draft gate` is the only exit, and a hook runs
   it on every write under `content/drafts/`. A `FAIL` names the key;
   fix or remove it. Never guess a key, never rewrite one. Done when
   every key came from a retrieval result.

8. **Map sections to citekeys.**

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<topic>/<name>.md --citekeys --write
   ```

   Done when the map is written.

9. **No drawn figure**: a digest's figures are the sources' (step 4).
   Done when the draft holds no figure of your own.

10. **Read it as someone who has opened none of the papers.** This
    replaces `survey-writer`'s step 10, which checks paraphrase a
    digest does not have. Go section by section against the reread
    checklist in `docs/writing-standards/genres/digest.md` and list, in
    priority order, up to five places it finds. Fix at most three, each
    by choosing a different passage, moving a run's start or end,
    adding the equation or figure, or rewriting a sentence of yours.
    Done when the list is made and at most three are fixed.

11. **Gate.**

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.md
    ```

    Re-run until it reports `OK`. Never show a digest that has not
    passed. Done when it reports `OK`.

12. **Build the References section** from exactly the gated citekeys,
    as `.claude/skills-common/references/render-and-references.md` §1
    says:

    ```bash
    python -m chitragupta.draft references content/drafts/<topic>/<name>.md
    ```

    Done when it has run.

13. **Render tex, pdf and md.** Follow
    `.claude/skills-common/references/render-and-references.md` §2:
    where the renders land, what they need, and what to do with a
    warning.

    ```bash
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format tex
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format pdf
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format md
    ```

    A `[math]` warning is a missing or orphaned `math.md` row: fix it,
    since an equation set as text is exactly what step 6 rules out.
    **No evidence sidecar**, so skip that file's §3: a digest *is* the
    sources' words. Done when
    each command has run or its warning is reported.

14. **Record any steering** the user gave in chat in the dossier's
    `steering.md`, dated; your reread was step 10. Done when it is
    recorded.

15. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<topic>/<name>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it. Expect it to flag copied text, which keeps its source's style
    by design; say so, and fix none of them. A finding in a sentence of
    yours that the user wants acted on is `draft-reviser`'s copy-edit
    mode. Done when every finding is reported.

16. **Run the digest report and the synthesis report.** **No verbatim
    scan**: in a digest, reuse is the design.

    ```bash
    python -m chitragupta.review digest content/drafts/<topic>/<name>.md --formats md
    python -m chitragupta.review synthesis content/drafts/<topic>/<name>.md --write
    ```

    The digest report files `content/review/<topic>/<name>.digest.md`
    and `.json`. Read the unsupported fraction first, then the copied
    fraction, the own-words share and the not-checkable share, the
    per-class counts and every item. A page note (`cited p. 4, found on
    p. 7`) is a locator to correct, not a finding. The synthesis report
    lists the paragraphs resting on one paper. Both advise and never
    block.

    If the enrichment extra is installed,
    `python -m chitragupta.review support content/drafts/<topic>/<name>.md`
    scores each citing sentence with an NLI entailment model and is
    worth running on the `unsupported-text` items, which `review digest`
    judges lexically only. `docs/VERBATIM-DIGEST.md` says what each
    check can and cannot see. Done when you have read every report you
    ran.

17. **Work the report, only if the user asked for a pass.** Say what the
    report found and ask. If they want it repaired, read
    `.claude/skills/review-digest/references/digest.md` §1 now: how
    each class is repaired, when a repair is kept, and when to stop. For
    a `dangling-reference` or a `repeated-text` item, read
    `.claude/skills-common/references/digest-copying.md` §4 and §5.
    After each repair:

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.md
    python -m chitragupta.review digest content/drafts/<topic>/<name>.md --baseline content/review/<topic>/<name>.digest.json --formats md
    ```

    Log every attempt in the dossier's `revisions.md`. Re-run step 13's
    renders once at the end of a pass that kept anything. Done when the
    user says stop, no item is left, or three passes did not lower the
    fraction.

18. **Stamp the draft fingerprint, then present.** Read
    `.claude/skills-common/references/genre-steps.md` §7 first, then:

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<topic>/<name>.md
    ```

    Present the digest's path, the unsupported fraction with the copied
    and own-words shares and the not-checkable share beside it, the
    per-class counts, the single-source paragraphs, the runs the aid
    could not check and why, the render outcome, and where the dossier
    and reports are. Say that the digest is private study text and never
    a source for another draft, that a change to it goes through
    `draft-reviser`, and that another pass over the report is this
    skill's step 17, on request.
    `python -m chitragupta.draft dossier export <topic>/<name>` backs a
    digest and its dossier up. Done when the user has the digest.
