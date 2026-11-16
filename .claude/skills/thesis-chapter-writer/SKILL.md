---
name: thesis-chapter-writer
description: Drafts a thesis/dissertation chapter in LaTeX, with narrative framing tied to a specific research question, grounded in citekeys pulled from the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) -- never a fabricated one. Triggers when the user asks to write or draft a thesis chapter, dissertation section, or an RQ-driven narrative chapter. To change one that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Outputs a standalone .tex fragment (\citep/\citet, no document preamble) intended to be \input by the user's own thesis document, plus a rendered .md/.pdf preview when pandoc/LuaLaTeX are available. Must run `python -m chitragupta.draft gate` on its own output and only present the draft once it passes. Refuses if the ledger is empty until `python -m chitragupta.corpus sync` has been run.
tags: [thesis, dissertation, latex, citation]
---

# thesis-chapter-writer

Drafts a thesis chapter that argues toward a research question, as a
standalone LaTeX fragment the user `\input`s into their own thesis,
every claim cited from the ledger. Paths in this skill are from the
project root, not from this skill's own folder.

## Before you start

**The corpus is read-only: never run `python -m chitragupta.corpus sync`
or `python -m chitragupta.enrich`.** Before the first retrieval, read
`.claude/skills-common/references/genre-steps.md` §1: what the corpus
holds, and why those are the user's to run. **If the ledger is empty,
stop.** Check before drafting anything:

```bash
python -m chitragupta.corpus ledger
```

If it reports nothing `parsed`, say what you checked and found, and stop.
Tell the user to run `.venv-full/bin/python -m chitragupta.corpus sync`
and come back.

## When to invoke

A survey or literature review is `survey-writer`'s, a textbook chapter
`textbook-chapter-writer`'s, a hands-on tutorial `tutorial-writer`'s,
and a change to a chapter in `content/drafts/` is `draft-reviser`'s:
never re-run this skill to make one.

## Collection scoping

At step 0, before any retrieval, check whether the library is sorted
into collections:

```bash
python -m chitragupta.corpus ledger --collections
```

If it reports none, say nothing, ask nothing, record
`- collection: (whole corpus)` in `scope.md`'s header, and skip this
section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run. If retrieval inside the shelf comes back thin, the
honest fix to offer is a whole-corpus pass with `corpus-reviser`, which
is the one skill allowed to widen.

## Prose standards

Follow `docs/WRITING-STANDARDS.md` for the rules every genre shares, and
`docs/writing-standards/genres/thesis-chapter.md` for what a thesis
chapter owes its examiner: read it before step 5. A chapter states and
derives results, and a single formula brings in the rules for the
sentences around it, so on every run: Read
`.claude/skills-common/references/mathematical-prose.md` now and follow
it while drafting. The works these standards come from are credited in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#-sources-and-attribution);
if asked what bears on a thesis chapter, read
`.claude/skills/thesis-chapter-writer/references/thesis.md` §5.

## Process

0. **Name the reader's starting point, and open the dossier.** Before
   creating it, read `.claude/skills-common/references/genre-steps.md`
   §2 and §3: the slug, `scope.md`, the dialect, the acronym vocabulary
   and the fingerprint. Settle what an examiner in this subfield already
   knows, and `<slug>` with the user; the glossary pins the chapter's
   terminology, and the examiner's institution decides the dialect (an
   Indian university is `en-IN` or `en-GB`). Then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<slug>.tex --genre thesis-chapter
   ```

   Done when `scope.md` records the reader, the scope and `language:`.
1. **Clarify the research question** the chapter serves, if the user has
   not given it. Done when it is stated in one sentence.
2. **Retrieve broadly, then filter.** First check for an `outline.md`:

   ```bash
   python -m chitragupta.draft dossier outline content/drafts/<slug>.tex --check
   ```

   If it passes, read `.claude/skills-common/references/genre-steps.md`
   §4, then run each section's declared queries verbatim; a thin
   section's reformulations are `--origin extended`.
   `python -m chitragupta.review uncited` is the backstop for a `claim:`
   you could not ground.

   ```bash
   python -m chitragupta.draft retrieve search "<declared query>" --k 15 --collection "<from scope.md>" --origin declared --log content/drafts/<slug>.tex
   ```

   With no `outline.md`, or one that fails `--check`, search against the
   research question and its component concepts, over-fetching:

   ```bash
   python -m chitragupta.draft retrieve search "<concept>" --k 15 --collection "<from scope.md>" --log content/drafts/<slug>.tex
   ```

   Keep a source only if it supports part of the argument, not if it
   merely shares the query's words. Before your first `evidence.md`
   block, read `.claude/skills-common/references/genre-steps.md` §5.
   Where a snippet cannot settle a source you mean to keep:

   ```bash
   python -m chitragupta.draft retrieve evidence "<concept>" --citekey <key> --log content/drafts/<slug>.tex
   ```

   Before drafting, record what survives in `evidence.md` and what
   doesn't in `rejected.md`, then:

   ```bash
   python -m chitragupta.draft dossier check-evidence content/drafts/<slug>.tex
   ```

   Done when every query has run with `--log` and every candidate is in
   one of the two files.
3. **Reformulate and re-search if a concept comes up thin.** When one
   does, read `.claude/skills-common/references/genre-steps.md` §6.
   Done when each is covered, or reported thin after real attempts.
4. **Check for disagreement across kept sources.** When two conflict on
   a point relevant to the research question, read
   `.claude/skills-common/references/genre-steps.md` §6. Done when each
   conflict is noted for the chapter.
5. **Draft** as a LaTeX fragment, with no `\documentclass` and no
   `\begin{document}`, citing as `\citep{key}` or `\citet{key}` only
   from `evidence.md`, in sections that build an argument toward the
   research question. A body paragraph closes on two or more citekeys
   wherever the evidence allows, or carries `% single-source: why` on
   the line above or below it, with no blank line between
   (`docs/WRITING-STANDARDS.md` §11;
   `python -m chitragupta.review synthesis <draft>` reports it). A table
   is real LaTeX with no marker (`docs/writing-standards/tables.md` §13):
   `\begin{table}` with its own `\caption{...}\label{tab:<id>}`, referred
   to as `Table~\ref{tab:<id>}`. Before writing a table, a figure
   float or a numbered equation, read
   `.claude/skills/thesis-chapter-writer/references/thesis.md` §1. Done
   when every section is drafted.
6. **Never write a citekey you didn't get from a retrieval result.** If
   a citation would strengthen the argument but isn't in the synced
   library, tell the user in prose rather than inventing a key. Done
   when every key came from a retrieval result.
7. **Log provenance.** Write
   `content/dossiers/<draft path minus suffix>/provenance.json`, one
   `{"section": "...", "citekeys": [...]}` per section. Before writing
   it, read `.claude/skills/thesis-chapter-writer/references/thesis.md`
   §2. Done when every section has an entry.
8. **Map sections to citekeys.** Save the fragment to
   `content/drafts/<slug>.tex`, then:

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<slug>.tex --citekeys --write
   ```

   A citekey it reports above the first `\section` belongs to no
   section: fix the fragment, not the table. Done when it reports none.
9. **Add a figure only if the argument needs one**; absence is the
   default. A figure is a pair of files, `figures/<name>.tex` and
   `figures/<name>.txt` (`docs/writing-standards/figures.md` §10). This
   genre keeps the TikZ inline and names the ASCII form in a marker
   comment:

   ```latex
   \input{figures/<name>.tex}
   %figure: figures/<name>
   ```

   Hand the drawing itself to `figure-drawer`, and come back to this
   step when it returns. What holds even if that skill is never loaded:

   - **The marker is a comment, never a second `\input`.**
   - **Check for TikZ, and that the figure compiles.** If
     `figure-drawer` was not loaded, run `kpsewhich tikz.sty`: if it
     finds nothing, write the ASCII inline in a `verbatim` environment,
     no pair and no marker, and say so in chat. A figure you keep
     compiles on its own first, with `lualatex`, the engine the pdf
     render uses: a malformed one fails the whole pdf render.
   - **A topic directory is required.** Move a flat draft and its
     dossier first, or drop the figure.
   - **No citekey inside either figure file.** The gate does not follow
     `\input`; cite in the prose that introduces the figure.
   - **Nothing redrawn from a source.**
   - **Every figure is a real float with its caption**, around the
     inline `\input`:
     `\begin{figure}...\caption{...}\label{fig:<id>}\end{figure}`,
     referred to as `Figure~\ref{fig:<id>}`. Never write
     `\renewcommand{\thefigure}`.
   - **Tell the user what their thesis preamble must load.** When a
     render prints a `[tikz-libraries]`, `[unicode]` or `[floats]` line,
     read `.claude/skills/figure-drawer/references/placement.md` §4,
     quote the line, and tell the user what it means;
     `.claude/skills/thesis-chapter-writer/references/thesis.md` §3
     shows each line. Never edit their thesis or a figure file to work
     around one.

   A numbered equation is real LaTeX too, with no marker:
   `\begin{equation}...\label{eq:<id>}\end{equation}`, referred to as
   `Equation~\ref{eq:<id>}`; any other displayed mathematics is
   `\[...\]`. Done when each figure has both files, and each caption and
   number is LaTeX's own.

10. **Critique against the evidence packet, before gating.** This step
    runs on every chapter, once the fragment is written and before step
    11's gate. Read the dossier's `evidence.md` -- the `claim:`/`quote:`
    blocks step 2 recorded -- against the fragment's own prose, section
    by section, and list in priority order up to five places where the
    prose claims more than its `claim:` supports, omits a kept `claim:`,
    or drifts from its wording. One inline judgement call: not a
    subagent dispatch and not a deterministic check.

    Read `.claude/skills-common/references/critique.md` now, before
    listing anything, and follow it with `content/drafts/<slug>.tex` as
    `<draft>`; make each edit with `Edit`.
    **This step is not done until the loop the reference describes has
    run**: the baseline, then at most three repairs, each checked and
    logged in the dossier's `revisions.md`. It is never a condition of
    presenting. Come back with the list, each repair kept or reverted,
    the scan's `tiers_not_run` reason if it gave one, and whether the
    declared queries are exhausted; then continue to step 11. Done when
    the loop has returned and every attempt is logged, or you have said
    that nothing cleared the bar.
11. **Gate before presenting.** Save the fragment as
    `content/drafts/<slug>.tex`, the canonical deliverable the user
    `\input`s, then:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.tex
    ```

    On `FAIL`, fix the offending line -- correct the citekey or remove
    the claim -- and re-run. Never show the user a draft that hasn't
    passed. Done when it reports `OK`.
12. **Render md and pdf previews, then the evidence sidecar.** The `.tex`
    fragment stays the deliverable exactly as it is: never wrap it in a
    preamble. Follow
    `.claude/skills-common/references/render-and-references.md` §2 for
    `content/drafts/<slug>.tex` in **md and pdf only**, then §3 in **pdf
    only**. Skip its §1: the fragment gets no References section. A
    rendering failure never blocks presenting the fragment, except a pdf
    error naming a figure file: the fragment will not build in the
    user's thesis either, so repair the figure or drop it. If the user
    asks why there is no References section or why the sidecar is
    rendered, read
    `.claude/skills/thesis-chapter-writer/references/thesis.md` §4. Done
    when each command has run or its warning is reported.
13. **Read it once as the examiner, and record any steering.** Reread
    against the checklist in
    `docs/writing-standards/genres/thesis-chapter.md`, weakening any
    claim that outruns its evidence. If the user shaped this chapter in
    chat, append that to the dossier's `steering.md`, dated; read
    `.claude/skills-common/references/genre-steps.md` §2 if unsure what
    counts. Done when both are done.
14. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.tex
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it. If the user wants any finding acted on, that is
    `draft-reviser`'s copy-edit mode, never an edit made here. Done when
    every finding is reported.
15. **Run the verbatim scan.** Before presenting, rebuild the section map
    and scan:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.tex --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.tex
    ```

    The first command is not optional and not a repeat of step 8. It
    matters most in the connective prose an examiner reads as your own.
    **A review aid, not a gate: it is never a condition of presenting.**
    Read `.claude/skills-common/references/verbatim-scan.md` now and
    follow it. Repairing a finding is `agenda-reviser`'s job, and only
    if the user asks. Done when the findings are shown.
16. **Stamp the draft fingerprint, then present.** Read
    `.claude/skills-common/references/genre-steps.md` §7 first, then:

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<slug>.tex
    ```

    Present the `.tex` fragment, the deliverable to `\input`, as that
    section says, with the preview paths or the render's warning. Changes
    go through `draft-reviser`, and
    `python -m chitragupta.draft dossier export <slug>` backs a draft
    and its dossier up. Done when the user has the fragment.
