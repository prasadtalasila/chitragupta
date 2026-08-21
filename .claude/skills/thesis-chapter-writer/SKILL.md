---
name: thesis-chapter-writer
description: Drafts a thesis/dissertation chapter in LaTeX, with narrative framing tied to a specific research question, grounded in citekeys pulled from the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) -- never a fabricated one. Triggers when the user asks to write or draft a thesis chapter, dissertation section, or an RQ-driven narrative chapter. To change one that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Outputs a standalone .tex fragment (\citep/\citet, no document preamble) intended to be \input by the user's own thesis document, plus a rendered .md/.pdf preview when pandoc/pdflatex are available. Must run `python -m chitragupta.draft gate` on its own output and only present the draft once it passes. Refuses if the ledger is empty until `python -m chitragupta.corpus sync` has been run.
tags: [thesis, dissertation, latex, citation]
---

# thesis-chapter-writer

Genre-specific drafting agent for thesis-chapter output. The drafting
layer (generative, on-demand, user-reviewed) -- distinct from
`python -m chitragupta.corpus sync` (the corpus layer: deterministic, unattended-safe).

## Shared corpus layer (read, don't regenerate)

- `content/ledger.sqlite` -- per-citekey status, populated by `sync`
- `papers/bibliography.bib` (gitignored, per-host) -- the source of truth for citekeys/metadata;
  point the thesis document's `\addbibresource` (biblatex) or `\bibliography`
  (bibtex) at this file directly rather than a copy
- `content/parsed/<citekey>.txt` -- extracted PDF text
- `chitragupta/retrieval.py` --
  `python -m chitragupta.draft retrieve search "<q>" --k 15 --log <draft>`,
  which returns a citekey, title, score and a 500-character snippet per
  candidate. `... evidence "<q>" --citekey <key> --log <draft>` reads more of
  one document when a snippet is not enough to judge it

## Collection scoping (#195): draft from the shelf, not the library

A Zotero library usually spans several topics, and its owner has already
sorted it -- "these are the modelling papers". `chitragupta/bib_collections.py`
carries that judgement into the ledger and `search()` can honour it.

Use it. BM25 over a whole library and BM25 over one shelf do not return
the same papers, and the shelf is **not** a subset of the library's
ranking: measured over a 642-item corpus, a 19-item shelf surfaced ten
papers the whole-corpus search never returned at all, because a small
pool promotes what a large pool's competition buries
(`bench/RESULTS.md`, 2026-08-19).

**At step 0, before any retrieval, offer the choice once:**

```bash
python -m chitragupta.corpus ledger --collections     # what exists, with counts
```

Show what exists, ask which one this draft belongs to, and accept "none,
search everything" as an answer. Record the result in `scope.md`'s
header, beside `language:`:

```text
- collection: Digital twins > Modelling
- collection: (whole corpus)      # user declined, or the library has none
```

**Then pass it on every retrieval call in the run:**

```bash
python -m chitragupta.draft retrieve search "<query>" --k 15 \
    --collection "<the recorded name>" --log <draft>
```

Three rules, none of them negotiable:

- **Every call, or none.** One unflagged call silently widens the scope
  for that search, and nothing downstream detects it: `retrieval.md`
  records the query, the `--k` and the payload size but **not** the
  collection (#254), so the log cannot tell anyone afterwards which calls
  were scoped. The discipline has to hold while the run is happening.
- **`retrieve evidence` takes no `--collection`.** The flag is on
  `search` only, and rightly: `evidence` zooms into one citekey you have
  already chosen, so there is nothing left for a collection to filter.
  Use it as normal.
- **Degrade silently.** Most exports carry no collections at all --
  plain Zotero's BibTeX exporter drops them, and only Better BibTeX's
  JabRef-fields option keeps them (`docs/ZOTERO.md`). If
  `ledger --collections` reports none, say nothing, ask nothing, record
  `- collection: (whole corpus)`, and behave exactly as this skill did
  before this section existed.

Scoping is a **narrowing**, and a narrowing cannot surface a paper the
shelf does not hold. If retrieval inside the shelf comes back thin for a
sub-theme, say so -- in the draft and in `rejected.md` -- rather than
quietly widening mid-run. The honest fix to offer is a whole-corpus pass
with `corpus-reviser`, which is the one skill allowed to widen.

## The dossier: write down what produced the draft

The chapter is only half of what this run produces. The other half is the
judgment behind it -- the examiner you wrote for, the scope, the
terminology the chapter settled on, which candidates were kept and
**which were turned down and why** -- and it belongs on disk, not in this
conversation. Without it the next revision has to re-retrieve and
re-score the whole research question to change one paragraph.

`chitragupta/dossier/` owns that state, in Markdown, one directory per draft at
`content/dossiers/<the draft's path, minus its suffix>/`. Create it before
you search (step 0) and fill it in as you go -- not at the end, when what
you rejected has already fallen out of your context. `docs/DRAFT-ITERATION.md`
is the full design.

This skill writes both the dossier's Markdown files and, in the same
directory, `provenance.json`: the machine-readable section-to-citekey
record used for audit, beside the human-readable working state a later
revision reads (reader, scope, glossary, rejected candidates and why,
steering). Two shapes for two readers, one directory per draft.

**Read-only means read-only: never run `python -m chitragupta.corpus sync`, and
never
run `python -m chitragupta.enrich` or any `chitragupta/enrich/*` build stage.**
Both belong to the
corpus layer, both take the pipeline's write lock, and either can run for
tens of minutes -- a first full-corpus parse, or building the embedding
index. They are the user's to run, not yours. If a semantic index would
help and none exists, say so and use `chitragupta.retrieval.search()`; do not
build one.

**If the ledger is empty, stop.** Check before drafting anything:

```bash
python -m chitragupta.corpus ledger
```

If it reports no items, or none with status `parsed`, say so plainly --
name what you checked and what you found -- and stop there. Do not draft
around it, do not sync, do not cite. Tell the user to run
`.venv-full/bin/python -m chitragupta.corpus sync` and come back.

## When to invoke

| Situation | Action |
|---|---|
| User asks for a thesis chapter / dissertation section tied to an RQ | Invoke this skill |
| User asks for a survey paper / lit review, not chapter-specific | Use `survey-writer` instead |
| User asks for a textbook chapter / lecture notes | Use `textbook-chapter-writer` instead |
| User asks for a hands-on tutorial | Use `tutorial-writer` instead |
| User asks to change a chapter that **already exists** in `content/drafts/` | Use `draft-reviser` instead -- never re-run this skill to make a change |
| Ledger is empty, or nothing is `parsed` | Say so and stop. **Never** run `python -m chitragupta.corpus sync` yourself |

## Prose standards

Follow `docs/WRITING-STANDARDS.md` for the cross-genre rules: name the reader
before drafting, define terms once, state scope up front, active voice with a
named actor, ban "obviously/simply/just", and reread as the reader before
presenting. That file also carries the attribution for where these
principles come from -- Diátaxis, Last's *Technical Writing Essentials*, and
Google's Technical Writing courses, all CC-licensed and all requiring credit.
The genre-specific additions below layer on top of it.

### What a thesis chapter owes its reader

Its reader is an examiner: a domain expert reading adversarially, looking for
the claim that outruns its evidence. That shapes every rule below. Unlike the
survey genre, this chapter **does** take a position -- but every step of the
argument must be traceable to something cited, and the honest statement of a
limitation is worth more than the paragraph that hides it.

The genre boundary that matters most here: a chapter that only summarizes
papers in sequence is a survey with a chapter heading. If the argument toward
the RQ isn't visible in the section structure, the chapter isn't doing its
job -- see `docs/WRITING-STANDARDS.md` §5.

## Process

0. **Name the reader's starting point, and open the dossier.** Before
   searching, settle what an examiner in this subfield already knows, so
   background is recapped where it's genuinely needed and not where it's
   condescending. Settle too what the chapter will and won't cover, and
   the slug it will be saved under. Then create the dossier and record
   the same decisions there:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<slug>.tex --genre thesis-chapter
   ```

   **Settle `<slug>` with the user before running that.** It is a path
   under `content/drafts/` and it may contain directories: "the methods
   chapter of `thesis/`" means
   `content/drafts/thesis/methods.tex`, and a topic that will hold more
   than one genre wants `content/drafts/<topic>/thesis-chapter.tex` so
   they sit together. A flat `content/drafts/<slug>.tex` is the default
   when neither applies. Ask rather than guess: the dossier
   (`content/dossiers/<slug>/`) and every render
   (`content/rendered/<the draft's own directory>/`) mirror whatever you
   pick, so moving the draft later means moving both.
   Fill in `scope.md`'s **Reader**, **Covers**, **Does not cover** and
   **Glossary** now, while you are deciding them -- the glossary is where
   the chapter's terminology gets pinned, so a revision doesn't drift off
   it. Settle the **dialect** with the reader in the same breath and write
   it to `scope.md`'s `language:` line, which ships unset -- the examiner's
   institution decides it (an Indian university is `en-IN` or `en-GB`), and
   a chapter whose dialect nobody chose silently gets the model's own
   (`docs/WRITING-STANDARDS.md` §8). Read the acronym vocabulary too --
   the vendored floor at `assets/style/acronyms.toml`, plus the user's own
   file if `[style].acronyms` in `config.toml` points at one -- and use its
   recorded expansion at an acronym's first use rather than inventing one.
   `init` also stamps the corpus
   fingerprint, which is what lets a
   later revision tell whether the ledger has moved since.
1. **Clarify the research question** the chapter serves, if not already given
   by the user. The chapter's narrative arc should argue toward/around this RQ,
   not just summarize papers in sequence.
2. **Retrieve broadly, then filter.** Search against the RQ and its
   component concepts -- over-fetch rather than assuming the top few hits
   are automatically the right ones:

   ```bash
   python -m chitragupta.draft retrieve search "<concept>" --k 15 --collection "<from scope.md>" --log content/drafts/<slug>.tex
   ```

   `--log` records the query and the call's size in the dossier's
   `retrieval.md`. **Pass it on every call.** It is what makes the run's
   cost measurable instead of estimated, and it is also the list a later
   `dossier status` re-asks against the corpus to tell you which newly
   synced papers this chapter has never seen -- a chapter drafted without
   it can never be told that. This is
   keyword overlap, not embeddings -- read each 500-character snippet and
   judge relevance yourself; a high score is a proxy, not a verdict. Keep
   only what actually supports part of the argument. Record the judgment in
   the dossier while the snippets are still in front of you, before drafting
   prose: the kept citekeys into `evidence.md`, one ``## `citekey` `` block
   per source with a `relevance:` line, a `claim:` line -- what the source
   establishes, in your own words, the only field the chapter may draft from
   -- and, only where a quotation earns its place, a `quote:` line (verbatim,
   quotation marks and attribution only); every candidate you turned
   down into `rejected.md` with the query that surfaced it and a few words
   on why ("shares vocabulary only", "wrong domain", "superseded by X"),
   so the next revision doesn't re-judge the same papers. Then run
   `python -m chitragupta.draft dossier check-evidence content/drafts/<slug>.tex`
   -- advisory, flags a `claim:` that reads like its `quote:` reworded.
3. **Reformulate and re-search if a concept comes up thin.** Try synonyms
   or adjacent terms and search again before concluding the corpus doesn't
   cover something -- and if it genuinely doesn't after a real attempt, say
   so to the user rather than forcing a weak citation into the argument.
4. **Check for disagreement across kept sources.** If two sources conflict
   on a point relevant to the RQ, surface that explicitly in the chapter
   rather than silently picking a side.
5. **Draft** as a LaTeX fragment (no `\documentclass`/`\begin{document}` --
   this is `\input`-ed into the user's existing thesis document), citing
   only from your scored-evidence file:
   - Section/subsection structure that builds an argument toward the RQ
   - Citations via `\citep{key}` / `\citet{key}` — never a bare invented key
6. **Never write a citekey you didn't get from `search()`.** If a citation
   would strengthen the argument but isn't in the synced library, tell the
   user in prose rather than inventing a key -- see AGENTS.md's citekey
   invariant (fabricated placeholder references are exactly the failure
   mode this rule exists to prevent).
7. **Log provenance.** Write
   `content/dossiers/<draft path minus suffix>/provenance.json`:
   `{"section": "...", "citekeys": [...]}` per section, for later audit (in
   addition to the evidence file from step 2). It goes in the dossier
   directory because it is state this run produced, not a report generated
   from the finished draft -- the latter is the review layer's
   `content/review/`, which no skill writes.
8. **Map sections to citekeys in the dossier.** Save the fragment to
   `content/drafts/<slug>.tex` first, then derive the map rather than
   writing it by hand:

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<slug>.tex --citekeys --write
   ```

   It reads `\citep`/`\citet` as readily as `[@key]` and tracks
   `verbatim`/`lstlisting`/`minted`, so a `\section`-like line inside a
   code environment is neither a heading nor a citation. The result is
   the same mapping as step 7's provenance JSON, kept in the form a
   reviser reads. Drop `--write` to see the table first; a citekey cited
   above the first `\section` is reported on stderr rather than
   attributed to a section that does not contain it.
9. **Add a figure only if the argument needs one.** Place it beside the
   framework, architecture or study design it captures, when prose
   would otherwise take a paragraph to describe it --
   `docs/WRITING-STANDARDS.md` §10's figures are occasional here, not
   routine. Default to no figure.

   When one is earned, it is a **pair of files**, and §10 is the
   contract. This genre's native form is the TikZ picture -- vector art
   that sets at the thesis's own font and line width, which is the whole
   reason this genre gets one -- so the fragment carries the `\input`
   inline and names the ASCII form in a marker comment:

   ```latex
   \input{figures/<name>.tex}
   %figure: figures/<name>
   ```

   with both `content/drafts/<topic>/figures/<name>.tex` and
   `content/drafts/<topic>/figures/<name>.txt` written -- the `.txt` in
   §10's 7-bit alphabet, since a Unicode box character hard-fails
   `pdflatex`. The renderer
   swaps that `\input` for the `.txt` contents when it builds the `.md`
   preview (step 11); `--format tex` and `--format pdf` get the TikZ.
   Four things to hold onto, each of which §10 explains:

   - **The marker is a comment, never a second `\input`.** The fragment
     on disk is what the user `\input`s into their own thesis, and
     `\input{figures/<name>.txt}` makes their `pdflatex` read ASCII art
     as LaTeX source and fail with `! Missing $ inserted.` -- a break in
     their build that our own render would never show us.
   - **A topic directory is required.** If step 0 settled on a flat
     `content/drafts/<slug>.tex`, move the draft and its dossier before
     adding a figure, or drop the figure. Figures under a flat draft
     land in `content/drafts/figures/`, shared with every other flat
     draft.
   - **Verify it compiles before keeping it.** Run `kpsewhich tikz.sty`
     first: if it is absent, write the ASCII inline in a `verbatim`
     environment, no pair and no marker, and say so in chat. If it is
     present, wrap `figures/<name>.tex` in a minimal
     `\documentclass{article}` + `\usepackage{tikz}` document and run
     `pdflatex` on it. A malformed figure fails the *whole* pdf render
     in step 11, not just the figure, so a figure that will not compile
     alone never reaches the fragment.
   - **No citekey inside either figure file.** Step 10's gate reads the
     fragment and does not follow `\input`, so a citekey in a node label
     evades the one check this pipeline exists for. Cite in the prose
     that introduces the figure.

   The TikZ must be as original as the ASCII -- a picture redrawn from a
   source paper's figure is the same violation in different pixels.

10. **Gate before presenting.** Save the fragment as `content/drafts/<slug>.tex`
    (this remains the canonical deliverable -- the one meant to be `\input`-ed),
    then run:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.tex
    ```

    Fix and re-run until `OK`. Never present a draft that hasn't passed.
11. **Render md and pdf previews.** The `.tex` fragment stays the canonical
    deliverable exactly as-is -- don't wrap it in a preamble or change its
    `\input`-able shape. In addition, render an `.md` and a `.pdf` preview
    from that same fragment (pandoc's LaTeX reader handles a preamble-less
    fragment fine):

    ```bash
    python -m chitragupta.draft render content/drafts/<slug>.tex --format md
    python -m chitragupta.draft render content/drafts/<slug>.tex --format pdf
    ```

    Both previews land beside the fragment: a draft at
    `content/drafts/<topic>/<name>.tex` renders to
    `content/rendered/<topic>/<name>.{md,pdf}`, so one topic directory
    holds the chapter, its dossier and its previews.
    This needs only bare `python` plus `pandoc`/`pdflatex` on PATH -- don't
    assume either is present or absent without checking; probe (or just try
    the command and read the result) rather than assuming from a prior run
    on a different host. If either command reports `[missing-binary]` or
    `[error]`, print a one-line warning in chat with that message and
    continue anyway -- a rendering failure never blocks presenting the
    `.tex` fragment. The one failure worth chasing before you present is
    a pdf error naming a figure file: that fragment will not build in the
    user's thesis either, so repair the figure or drop it, rather than
    handing over a chapter that cannot be typeset.

    Unlike the Markdown-native genre skills, don't run `python -m
    chitragupta.draft references` on this fragment and don't add a manual References
    section to it -- the fragment is designed to inherit the thesis's own
    document-wide `\addbibresource`/`\bibliography` (the shared corpus
    layer above), and a per-chapter list would duplicate that. The `.pdf`
    preview still gets a real bibliography for free: `--citeproc` resolves
    `\citep`/`\citet` against `bibliography.bib` and appends one
    automatically, same as before this feature existed.

    Note the preview renders that bibliography in IEEE style, with numeric
    `[1]` markers, because that is what `render_output` now passes
    `--csl`. That styles the *preview only* -- the `.tex` fragment is
    unchanged, and the real thesis renders it in whatever style its own
    document class and `\bibliographystyle` specify. Don't rewrite
    `\citep`/`\citet` to match the preview.
12. **Read it once as the examiner** (`docs/WRITING-STANDARDS.md` §6, in its
    adversarial form). Check specifically for: a conclusion stated more
    strongly than its cited evidence supports, a section that summarizes
    rather than argues, notation or terminology that shifts mid-chapter, and
    any claim carrying no citation that isn't genuinely your own contribution.
    Where you find overreach, weaken the claim rather than adding a citation
    that doesn't quite support it.
13. **Record any steering.** If the user shaped this chapter in chat --
    "argue it harder against X", "the RQ is narrower than that", "cut the
    background recap" -- append it to the dossier's `steering.md`, dated.
    It is invisible in the prose and has nowhere else to live; a revision
    that doesn't know about it will undo it.
14. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.tex
    ```

    **It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable**
    -- §2's defect markers, an acronym never expanded at first use, a
    glossary acronym whose expansion has drifted from the vocabulary,
    and §8's dialect against `scope.md`'s `language:` line. It says nothing
    about whether a paragraph leads with its point or whether a hedge
    carries information, and it cannot tell a quotation from the chapter's own
    voice, so a marker inside a quoted passage reports and is correct as
    it stands. The fragment is scanned as Markdown, so
    `verbatim` environments and `\cite` arguments are skipped and the prose
    is not.

    **Report every finding and fix none of them.** A finding is a place to
    look, not a defect: the first pass of this check over this
    repository's own docs kept 59 of its 73 marker hits on inspection. If
    the user wants any of them acted on, that is `draft-reviser`'s
    copy-edit mode, which reads the recorded dialect and logs one
    `revisions.md` entry -- never an edit made here. Report the header
    lines too: `dialect: not checked` means nobody ever recorded one, so a
    short list is not a clean draft. A review aid, not a gate -- it
    exits 0 whatever it finds, and a missing `vale` binary is a one-line
    warning that blocks nothing.
15. **Offer the verbatim scan.** Before presenting, offer this -- don't run
    it silently, and never make it a condition of presenting:

    ```bash
    python -m chitragupta.review verbatim scan content/drafts/<slug>.tex
    ```

    It reports wording the chapter shares with **any** parsed source, cited or
    not -- including a source the citing paragraph never names, and reuse in
    the connective prose an examiner reads as your own. A review aid, not a
    gate: it exits 0 either way and cannot block the fragment. Say what it
    misses when you offer it -- it sees verbatim and near-verbatim reuse only,
    and **genuine restatement is only detected where the embedding tier can
    run**, so a clean scan is not a clean bill of health
    (`docs/PLAGIARISM.md`). If the user wants the finding kept, add `--write`:
    the report goes to `content/review/`, mirroring the draft's path, beside
    any provenance and coverage reports for the same draft.
16. Present the `.tex` fragment (the deliverable to `\input`) plus, if
    rendering succeeded, the `.md`/`.pdf` preview paths -- or the warning if
    it didn't. Tell the user where the dossier is, that changes to this
    chapter should go through `draft-reviser` rather than another run of this
    skill, and that `content/drafts/` and `content/dossiers/` are gitignored
    -- so `python -m chitragupta.draft dossier export <slug>` is how a draft and
    its
    working state get backed up.

## Sources

The prose standards this skill inherits are not original to this project.

Full citations, licences and a per-principle attribution table are in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#sources-and-attribution).
All three works are openly licensed (CC-BY or CC-BY-SA) and require credit.

What bears on *this* genre specifically:

- **Google, *Technical Writing Courses* (CC-BY 4.0)** -- the curse of
  knowledge, consistent terminology, defining each term once. Step 0's "what
  does an examiner already know" is audience analysis in the form this genre
  needs it.
- **Last, *Technical Writing Essentials* (CC-BY 4.0)** -- scope and assumed
  background stated up front; the argument against passive voice.
- **Procida, *Diátaxis* (CC-BY-SA 4.0)** -- the genre-separation principle
  behind the warning that a chapter which only summarises papers in sequence
  is a survey with a chapter heading. A thesis chapter is not a Diátaxis
  quadrant; only that insight transfers.
