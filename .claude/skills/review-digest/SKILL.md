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
sentences are few, short, and there to compare, contrast or define. It
must read on its own: someone who has opened none of the papers can
follow it from the first page to the last.

It is private study text, not a deliverable, and **it is never a source
for drafting anything else**: its wording is the corpus's own, and the
verbatim scan (`review verbatim scan`) flags it the moment it reaches a
survey or a chapter.

Three goals, in this order (`docs/VERBATIM-DIGEST.md`):

1. **A self-sufficient survey** the reader can learn the topic from.
2. **As much of the body as possible in the sources' exact words.**
3. **Surface and minimise unsupported text.** The report lists every
   sentence no source backs; each repair pass leaves fewer.

A digest is a draft like any other: named by the user, kept at
`content/drafts/<topic>/<name>.md`, with a dossier whose `scope.md`
records `- genre: digest`. **Never run `agenda-reviser` on a digest**:
its `verbatim-run` repair paraphrases copied text unattended.

Paths in this skill are from the project root.

## Shared corpus layer (read, don't regenerate)

- `content/ledger.sqlite` -- per-citekey status, populated by `sync`
- `content/parsed/<citekey>.passages.json` -- the Docling sidecar, the
  reading-ordered text **you copy from**, never from memory. Its
  `formula` passages are the source's equations. A source with no
  sidecar cannot be checked: do not copy from
  `content/parsed/<citekey>.txt`, whose text has no reading order. Tell
  the user which cited sources lack one and that `chitragupta enrich
  --stages docling` (the user's to run, never yours) gives them one
- `python -m chitragupta.draft retrieve search "<q>" --k 15 --log <draft>`
  finds candidates; `... evidence "<q>" --citekey <key> --log <draft>`
  reads more of one document
- `python -m chitragupta.draft figures <citekey>` lists one paper's
  figures and their crops, when the Docling stage extracted them

**Read-only means read-only: never run `python -m chitragupta.corpus sync`,
and never run `python -m chitragupta.enrich` or any `chitragupta/enrich/*`
build stage.** Both take the pipeline's write lock and are the user's.

**If the ledger is empty, stop.** Check before anything else:

```bash
python -m chitragupta.corpus ledger
```

If it reports no items, or none with status `parsed`, say so and stop.
Tell the user to run `.venv-full/bin/python -m chitragupta.corpus sync`
and come back. Do not draft around it, do not sync, do not cite.

## Collection scoping (#195)

```bash
python -m chitragupta.corpus ledger --collections
```

If it reports none, record `- collection: (whole corpus)` in `scope.md`'s
header and skip this section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run.

## When to invoke

- "Give me a digest of what the corpus says about X."
- "Study notes on X, in the papers' own words."

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
  or `pp. N-M`, counting the PDF's pages from 1 as the parser does.
- **Your own sentences** sit between runs, never inside one. Close each
  with `[see @a; @b]` naming the papers it rests on; one no source
  backs is `unsupported-text`, and one with no citation at all is
  `unquoted-text`.
- **`<!-- own: why -->`** on the line directly above a paragraph
  declares the whole paragraph yours: the framing, the gap analysis.
  Table rows are yours by construction. Use it for those, not to hide a
  run that failed to match.
- Pandoc-style citations only. `.claude/skills-common/references/digest-copying.md`
  says what "copied exactly" means and how a run carries an equation or
  a figure; read it before step 6.

## Process

The same steps as `survey-writer`, in the same order. Where a survey
step exists to keep source wording out of the draft, this one says what
replaces it.

0. **Name the reader and the scope, and open the dossier.** Settle with
   the user what the digest covers and leaves out, and its path: a
   topic that holds other genres wants `content/drafts/<topic>/<name>.md`.
   Then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<topic>/<name>.md --genre digest
   ```

   Fill in `scope.md`'s **Reader**, **Covers**, **Does not cover** and
   **Glossary** now: every recurring term, with the one definition the
   whole digest uses. Settle the **dialect** and write it to `scope.md`'s
   `language:` line; it governs your own sentences, since copied text
   keeps its source's spelling. Name the reader as someone who has read
   none of the papers; never assume the reader's own projects, a book
   they are writing, or a running example from outside the corpus.

1. **Retrieve per theme, over-fetching.** Settle three to six themes
   with the user (an `outline.md` in the dossier, if the user wrote one,
   settles them and its queries run verbatim). For each, run
   `python -m chitragupta.draft retrieve search "<query>" --k 15 --log <draft>`,
   then read the candidates' parsed text.

2. **Score every candidate, and record its main passage as a
   `quote:`.** One block per citekey in `evidence.md` (`docs/DOSSIER.md`):
   `relevance:`, a `claim:` in your own words (what your `see`
   sentences are drafted from), and one `quote:` holding the passage you
   lean on most from that source, verbatim, with no quotation marks and
   no page. `review quotation` checks it; `review digest` checks every
   other copied run where it stands. Every candidate you turn down goes
   in `rejected.md` with why.

3. **Re-search a thin theme** with a reformulated query before settling
   for a weak passage.

4. **Cluster, then choose passages that stand on their own.** Group the
   kept sources by what they say, not by paper. For each theme choose
   passages -- a sentence to a paragraph -- that make one point each
   and need nothing before them: a whole paragraph beats three
   sentences from three places, and a passage that opens on "where",
   "thus" or "these" starts one sentence earlier. Aim for two or more
   papers per point. Run `python -m chitragupta.draft figures <citekey>`
   for each kept source and keep a crop where a figure says what a
   paragraph circles around
   (`.claude/skills-common/references/digest-copying.md` §3).

5. **Find the disagreements.** Where two papers say opposite things,
   both will be copied, each under its own citation, and a `see`
   sentence of yours will name the disagreement. Never resolve one
   silently.

6. **Draft the survey, copying exactly.** In this order:
   - **Opening** (`<!-- own: scope -->`): who the digest is for, what it
     covers and what it deliberately leaves out.
   - **Framing** (`<!-- own: framing -->`): one paragraph on why the
     topic matters and how the sections divide it, closed by `see`
     citations.
   - **One section per theme.** Each body paragraph opens with a
     sentence of yours stating its point, `[see @a; @b]`, then braids
     the copied runs that make it, two or more papers, ordered by the
     argument, never one paper after another. Where one paper genuinely
     is the only source for a point, keep it and write
     `<!-- single-source: why -->` on the line above. Define a term at
     first use, in the glossary's words; never write "the book" or "the
     tutorial" where the reader cannot tell which.
   - **A comparison table**, with a caption and an id
     (`docs/WRITING-STANDARDS.md` §13): one row per approach, a citekey
     column carrying `[@key]`, core idea and stated limitation in short
     phrases of your own. Introduce it before it and read a pattern off
     it after it.
   - **Disagreements**, inside the theme they belong to, both sides
     copied.
   - **Gap analysis** (`<!-- own: gap analysis -->`): what the corpus
     does not cover, the themes that stayed thin, and any disagreement
     the corpus does not settle.

   Copy each run from `content/parsed/<citekey>.passages.json`, words and
   numbers exactly, typography cleaned. Every equation, copied or your
   own, is typeset in a `<!-- math -->` display mapped in the dossier's
   `math.md`; one a run introduces or explains is never left out, and
   none is ever written as text
   (`.claude/skills-common/references/digest-copying.md` §1 and §2). Read `.claude/skills-common/references/mathematical-prose.md`
   for your own sentences around a symbol.

7. **Never write a citekey you did not get from a retrieval result.**
   `python -m chitragupta.draft gate` is the only exit, and a hook runs
   it on every write under `content/drafts/`. A `FAIL` names the key;
   fix or remove it.

8. **Map sections to citekeys.**

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<topic>/<name>.md --citekeys --write
   ```

9. **No drawn figure.** A digest draws nothing of its own; its figures
   are the sources', placed in step 4.

10. **Read it as someone who has opened none of the papers.** This
    replaces `survey-writer`'s step 10, which checks paraphrase a
    digest does not have. Go section by section and
    list, in priority order, up to five places where: a term or symbol
    is used before it is defined; a run names a figure, equation,
    section or reference the digest does not show; a run opens on a
    word pointing back at something not there; a paragraph is one paper
    after another rather than an argument; a sentence of yours narrates
    the sources ("the book then names...") instead of making a point; or
    the gap analysis omits a theme that stayed thin. Fix at most three,
    each by choosing a different passage, moving a run's start or end,
    adding the equation or figure, or rewriting a sentence of yours.

11. **Gate.**

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.md
    ```

    Re-run until it reports `OK`. Never show a digest that has not passed.

12. **Build the References section** from exactly the gated citekeys:

    ```bash
    python -m chitragupta.draft references content/drafts/<topic>/<name>.md
    ```

13. **Render tex, pdf and md.**

    ```bash
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format tex
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format pdf
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format md
    ```

    A `[missing-binary]` or `[error]` is a one-line warning in chat, never
    a block. A `[math]` warning is a missing or orphaned `math.md` row:
    fix it, since an equation set as text is exactly what step 6 rules
    out. **No evidence sidecar**: a digest *is* the sources' words.

14. **Run the digest report and the synthesis report.**

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
    block. **No verbatim scan**: in a digest, reuse is the design.

15. **Record any steering** the user gave in chat in the dossier's
    `steering.md`, dated.

16. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<topic>/<name>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it. Expect it to flag copied text, which keeps its source's style
    by design; say so, and fix none of them. A finding in a sentence of
    yours that the user wants acted on is `draft-reviser`'s copy-edit
    mode.

17. **Work the report, only if the user asked for a pass.** Say what the
    report found and ask. If they want it repaired, take the items one
    at a time, worst class first, as the report orders them:

    - `unsupported-text`: cite the source that says it, replace it with
      that source's words, or delete it.
    - `copy-mismatch`: open the source at the page named and restore
      the exact words.
    - `dangling-reference`: show the item, substitute it in brackets,
      delete the marker, or move the run's start or end
      (`.claude/skills-common/references/digest-copying.md` §4).
    - `unquoted-text`: close the sentence with a `see` citation, replace
      it with a copied passage that does its job, or delete it.

    After each repair:

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.md
    python -m chitragupta.review digest content/drafts/<topic>/<name>.md --baseline content/review/<topic>/<name>.digest.json --formats md
    ```

    Keep the repair only if the gate passes, the item is in `resolved`,
    no class count rose, `new` is empty, and the unsupported fraction did
    not rise; the comparison prints `fell: yes` exactly when the last
    four hold. Otherwise revert it. Log every attempt in the dossier's
    `revisions.md`: the date, the item id, the class, what you did, and
    the fraction before and after. Stop when the user says so, when no
    item is left, or after three passes whose fraction did not fall.
    Re-run step 13's renders once at the end of a pass that kept
    anything.

18. **Stamp the draft fingerprint, then present.**

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

## Sources

The copying discipline mirrors `docs/WRITING-STANDARDS.md` §9 (verbatim
wording has one home, and it is never the draft): a digest is that home
made explicit, with every run attributed. `SOUL.md`'s rule against
passing off a source's wording is kept by the citation that closes every
run and by the rule that a digest is never a drafting source.
