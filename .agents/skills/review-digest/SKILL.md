---
name: review-digest
description: Builds a verbatim digest -- a private study summary of a topic written mostly in the source papers' own words, copied exactly from parsed PDFs in the corpus, with a citation closing each copied run and no quotation marks -- through the same draft-and-render workflow survey-writer uses, then runs `python -m chitragupta.review digest` on it and works the report down on request. Every citekey comes from content/ledger.sqlite via chitragupta.retrieval, never invented. Triggers when the user asks for a digest, study notes, a reading summary or an extract "in the papers' own words" on a topic. The digest is never a deliverable and never a source for a survey, chapter or any other draft; to summarise in your own words use survey-writer, and to change a digest that exists use draft-reviser. Must run `python -m chitragupta.draft gate` and `review digest` before presenting, and refuses (telling the user to run `python -m chitragupta.corpus sync`) if the ledger is empty.
tags: [digest, study-notes, verbatim, citation]
---

# review-digest

A verbatim digest is private study text: most of it is copied exactly
from parsed PDFs in the corpus, each copied run ends with a citation,
there are no quotation marks, and a few short sentences of your own
connect the runs. It is read by one person to learn a topic. It is not a
deliverable, and **it is never a source for drafting anything else**:
its wording is the corpus's own, and the verbatim scan (`review verbatim
scan`) will flag it the moment it reaches a survey or a chapter.

Three goals, in this order (`docs/VERBATIM-DIGEST.md`):

1. **Maximise copied text.**
2. **Surface unsupported text.** Every sentence that is not verified
   source text is listed for the person to judge.
3. **Minimise unsupported text.** The report leads with the unsupported
   fraction; each repair pass leaves it lower than the one before, and
   `--baseline` makes that a number.

A digest is a draft like any other: named by the user, kept at
`content/drafts/<topic>/<name>.md`, with a dossier whose `scope.md`
records `- genre: digest`, rendered beside the other drafts in the
topic, and per-host data like every file under `content/`. Nothing in
its name marks it as a digest; the dossier does.

**This skill runs `survey-writer`'s workflow with its purpose turned
round.** A survey minimises copying: it drafts from `claim:` lines in
the drafter's own words, fuses sources so no paragraph can be a
transcription, and scans for verbatim reuse. A digest maximises copying.
The mechanical chain below is the survey's; every step of the survey's
that exists to keep source wording out of the draft is inverted here and
says so where it stands. `docs/WRITING-STANDARDS.md` §4 and §11 govern
the connecting sentences only. **Never run `agenda-reviser` on a
digest**: its `verbatim-run` repair paraphrases copied text unattended,
which would undo the digest.

Paths in this skill are from the project root, not from this skill's
own folder.

## Shared corpus layer (read, don't regenerate)

- `content/ledger.sqlite` -- per-citekey status, populated by `sync`
- `content/parsed/<citekey>.passages.json` -- the Docling sidecar, the
  reading-ordered text **you copy from**, never from memory and never
  from a snippet you tidied: the aid matches what you wrote against this
  text, and a faithful copy of a bad parse is still a match. A source
  with no sidecar cannot be checked: `pdftotext` text has no reading
  order and a run copied from it can splice two columns, so do not copy
  from `content/parsed/<citekey>.txt`. Tell the user which cited sources
  lack a sidecar and that `chitragupta enrich --stages docling` (the
  user's to run, never yours) gives them one
- `python -m chitragupta.draft retrieve search "<q>" --k 15 --log <draft>`
  finds candidates; `... evidence "<q>" --citekey <key> --log <draft>`
  reads more of one document

**Read-only means read-only: never run `python -m chitragupta.corpus sync`,
and never run `python -m chitragupta.enrich` or any `chitragupta/enrich/*`
build stage.** Both take the pipeline's write lock and are the user's to run.

**If the ledger is empty, stop.** Check before anything else:

```bash
python -m chitragupta.corpus ledger
```

If it reports no items, or none with status `parsed`, say so plainly and
stop. Tell the user to run `.venv-full/bin/python -m chitragupta.corpus sync`
and come back. Do not draft around it, do not sync, do not cite.

## Collection scoping (#195)

Before any retrieval:

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
- "Pull the key passages on X together."

Not for a summary in your own words (`survey-writer`), not for changing
a digest that exists (`draft-reviser`, which reads the dossier), and not
for anything that will be submitted or published.

## The format

Plain prose plus a closing citation. No markup, no quotation marks:

```markdown
Sentence one. Sentence two. Sentence three. [@key, p. 4-5]
A connecting sentence of your own.
Another copied sentence. [@other, p. 12]
```

**A citation covers every sentence back to the previous citation, or to
the start of the paragraph.** So:

- Put the citation at the end of the last copied sentence, on the same
  line or the next, before any sentence of your own.
- Copy from one paper per run. Two papers under one citation leaves the
  second paper's text unmatched.
- Give the page as `p. N` or `pp. N-M`, counting the PDF's pages from 1
  as the parser does, not the printed page number. It is a hint: the
  report says which page it actually found the text on.
- Keep your own sentences short, few, and between runs, never inside
  one.
- Pandoc-style citations only (`[@citekey, p. 4]`, `[@a; @b]`).

## Process

The same steps as `survey-writer`, in the same order. Three of its
steps are replaced by `review digest` and say so below.

0. **Name the reader and the scope, and open the dossier.** Settle with
   the user what the digest covers and what it leaves out, and the path
   under `content/drafts/`: a topic that holds other genres wants
   `content/drafts/<topic>/<name>.md` so they sit together. Then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<topic>/<name>.md --genre digest
   ```

   Fill in `scope.md`'s **Reader**, **Covers** and **Does not cover**
   now. The reader is the user, studying. Settle the **dialect** and
   write it to `scope.md`'s `language:` line; it governs only your own
   connecting sentences, since copied text keeps its source's spelling.
   `init` also stamps the corpus fingerprint.

1. **Retrieve per sub-theme, over-fetching.** Decide three to six
   sub-themes with the user (an `outline.md` in the dossier, if the user
   wrote one, settles them and its queries run verbatim). For each, run
   `python -m chitragupta.draft retrieve search "<query>" --k 15 --log <draft>`,
   then read the candidates' parsed text.

2. **Score every candidate before it counts, and record the passage
   you will copy as a `quote:`.** Record every candidate you read in
   `evidence.md` as the dossier contract asks (`docs/DOSSIER.md`): one
   block per citekey with `relevance:`, a `claim:` saying in your own
   words what the passage establishes, and a `quote:` holding the exact
   passage you intend to copy. This is the survey's contract read the
   other way round: a survey captures a `quote:` only when a quotation
   is genuinely warranted, and in a digest every run is one, so every
   passage you will copy is a `quote:` and `claim:` is drafted from only
   for the connecting sentences. The `quote:` is what a later
   `draft-reviser` or `review quotation` checks against the source.
   Every candidate you turn down goes in `rejected.md` with why.

3. **Re-search a thin sub-theme** with a reformulated query before
   settling for a weak passage.

4. **Pick passages worth copying.** For each sub-theme choose the
   passages -- a sentence to a paragraph each -- that say the thing
   best. Prefer a whole paragraph to three sentences from three places:
   a run found whole is one clean span; one assembled from several
   places is reported as such.

5. **Note disagreement.** Where two papers say opposite things, copy
   both, each under its own citation, and let a connecting sentence of
   yours name the disagreement.

6. **Draft, copying exactly.** This is where the survey's rule is
   inverted: a survey paragraph must rest on two or more sources so it
   cannot be a transcription of any one (`docs/WRITING-STANDARDS.md`
   §11); a digest run rests on exactly one source and is a transcription
   of it by design. Open `content/parsed/<citekey>.passages.json` and
   copy each passage's text character for character, including the
   parse's own noise.
   Do not fix hyphenation, ligatures, a dropped word or a reference
   marker; do not reorder; do not shorten. If the parse is too broken to
   read, pick another passage or another paper. Close each run with its
   citation and page. Where two runs need a bridge, write one short
   sentence of your own between them; every such sentence will be
   listed as `unquoted-text`, and one no source supports is also
   `unsupported-text`. Fewer is better.

7. **Never write a citekey you did not get from a retrieval result.**
   `python -m chitragupta.draft gate` is the only exit, and a hook runs it
   on every write under `content/drafts/`. A `FAIL` names the key; fix
   or remove it. Never guess a key, never rewrite one.

8. **Map sections to citekeys.**

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<topic>/<name>.md --citekeys --write
   ```

9. **No figure, and no pre-gate critique.** A digest draws nothing.
   `survey-writer`'s critique loop reads the `claim:`/`quote:` packet to
   check prose it wrote from it; a digest is not written from the packet
   but copied from the sources, and the check that applies to it is
   step 14's `review digest`.

10. **Gate.**

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.md
    ```

    Re-run until it reports `OK`. Never show a digest that has not passed.

11. **Build the References section** from exactly the gated citekeys:

    ```bash
    python -m chitragupta.draft references content/drafts/<topic>/<name>.md
    ```

12. **Render tex and pdf.**

    ```bash
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format tex
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format pdf
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format md
    ```

    All three land at `content/rendered/<topic>/<name>.{tex,pdf,md}`.
    This needs only bare `python` plus `pandoc`/`pdflatex` on PATH. If
    either command reports `[missing-binary]` or `[error]`, print a
    one-line warning in chat with that message and continue; a
    rendering failure never blocks presenting the `.md`.

    **No evidence sidecar.** A survey renders one because its body
    paraphrases and the sidecar shows the sources' words beside it. A
    digest *is* the sources' words, each run attributed where it
    stands, so a sidecar would print the digest back.

13. **Read it once as the reader.** Check that every connecting
    sentence of yours is needed, that no sentence of yours sits inside
    a copied run before its citation, and that each citation names one
    paper.

14. **Run the digest report.**

    ```bash
    python -m chitragupta.review digest content/drafts/<topic>/<name>.md --formats md
    ```

    It files `content/review/<topic>/<name>.digest.md` and `.json` and
    prints where. Read the report: the unsupported fraction first, then
    the copied fraction and the not-checkable share, the per-class
    counts, and every item. A page note on a copied span (`cited p. 4,
    found on p. 7`) is a locator to correct, not a finding;
    `docs/VERBATIM-DIGEST.md` explains how a page is counted. It is a
    review aid: it advises and never blocks.

    **No verbatim scan.** `survey-writer` runs `review verbatim scan`
    here because reuse in a survey is a defect. In a digest it is the
    design, and the scan would report every run; `review digest` is the
    check that applies.

    If the enrichment extra is installed, `python -m chitragupta.review
    support content/drafts/<topic>/<name>.md` scores each citing
    sentence with an NLI entailment model and is worth running on the
    `unsupported-text` items, which `review digest` judges lexically
    only. `docs/VERBATIM-DIGEST.md` says what each check can and cannot
    see.

15. **Record any steering** the user gave in chat in the dossier's
    `steering.md`, dated.

16. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<topic>/<name>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it: what the check can and cannot see, and how to report what it
    finds. Expect it to flag copied text, which keeps its source's
    style by design; say so when you report, and fix none of them. If
    the user wants a finding acted on in a connecting sentence of
    yours, that is `draft-reviser`'s copy-edit mode, never an edit made
    here.

17. **Work the report, only if the user asked for a pass.** Say what
    the report found and ask. If they want it repaired, take the items
    one at a time, worst class first, exactly as the report orders them:

    - `copy-mismatch`: open the source at the page the item names and
      restore the exact wording.
    - `unquoted-text`: replace the sentence with a copied passage that
      does the same job, or delete it.
    - `unsupported-text`: cite it correctly if a source says it, replace
      it with that source's words, or delete it.

    After each repair:

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.md
    python -m chitragupta.review digest content/drafts/<topic>/<name>.md --baseline content/review/<topic>/<name>.digest.json --formats md
    ```

    Keep the repair only if all of these hold: the gate passes, the
    item is in `resolved`, no class count rose, `new` is empty, and the
    unsupported fraction did not rise. The comparison prints `fell: yes`
    exactly when the last four do. If any fails, revert the edit and
    move on. Log every attempt, kept or reverted, in the dossier's
    `revisions.md`: the date, the item id, the class, what you did, and
    the fraction before and after. Stop when the user says so, when no
    item is left, or after three passes whose fraction did not fall.
    Re-run step 12's renders once at the end of a pass that kept
    anything.

18. **Stamp the draft fingerprint, then present.**

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<topic>/<name>.md
    ```

    Present the digest's path, the unsupported fraction with the copied
    fraction and the not-checkable share beside it, the per-class
    counts, the runs the aid could not check and why, the render
    outcome, and where the dossier and the report are. Say that the
    digest is private study text and never a source for another draft,
    that like every draft it is per-host data under `content/`, that a
    change to it goes through `draft-reviser`, and that another pass
    over the report is this skill's step 17, on request.

## Sources

The copying discipline here is the mirror of `docs/WRITING-STANDARDS.md`'s
§9 (verbatim wording has one home, and it is never the draft): a digest
is that home made explicit, with every run attributed. `SOUL.md`'s rule
against passing off a source's wording is kept by the citation that
closes every run and by the rule that a digest is never a drafting source.
