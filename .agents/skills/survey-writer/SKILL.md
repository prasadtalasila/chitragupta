---
name: survey-writer
description: Drafts a topic-clustered literature survey / background section / "state of the art" from the synced corpus, with a comparison table and a gap analysis. Every claim is grounded in a citekey pulled from content/ledger.sqlite via chitragupta.retrieval -- never a fabricated one. Triggers when the user asks to write or draft a survey paper, literature review, background section, or related-work section for a given topic. To change or update a survey that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Must run `python -m chitragupta.draft gate` on its own output and only present the draft once it passes. Refuses (and tells the user to run `python -m chitragupta.corpus sync` first) if the ledger is empty.
tags: [survey, literature-review, citation]
---

# survey-writer

Drafts a survey from the synced corpus: themes, a comparison table and a
gap analysis, every claim cited from the ledger. Paths in this skill are
from the project root, not from this skill's own folder.

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

A thesis chapter is `thesis-chapter-writer`'s, a textbook chapter
`textbook-chapter-writer`'s, a keyboard tutorial `tutorial-writer`'s,
and a change to a survey in `content/drafts/` is `draft-reviser`'s:
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
`docs/writing-standards/genres/survey.md` for what a survey owes its
reader: read it before step 6.
If asked what bears on a survey, read
`.claude/skills/survey-writer/references/survey.md` §4.

## Process

0. **Name the reader and the scope, and open the dossier.** Before
   creating it, read `.claude/skills-common/references/genre-steps.md`
   §2 and §3: the slug, `scope.md`, the dialect, the acronym vocabulary
   and the fingerprint. Settle `<slug>` with the user, then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<slug>.md --genre survey
   ```

   Done when `scope.md` records the reader, the scope and `language:`.
1. **Retrieve broadly, over-fetching on purpose.** First check for an
   `outline.md`:

   ```bash
   python -m chitragupta.draft dossier outline content/drafts/<slug>.md --check
   ```

   If it passes, read `.claude/skills-common/references/genre-steps.md`
   §4, then run each section's declared queries verbatim; a thin
   section's reformulations are `--origin extended`.
   `python -m chitragupta.review uncited` is the backstop for a `claim:`
   you could not ground.

   ```bash
   python -m chitragupta.draft retrieve search "<declared query>" --k 15 --collection "<from scope.md>" --origin declared --log content/drafts/<slug>.md
   ```

   With no `outline.md`, or one that fails `--check`, break the topic
   into 2-4 sub-themes and pull more candidates than you expect to use:

   ```bash
   python -m chitragupta.draft retrieve search "<sub-theme>" --k 15 --collection "<from scope.md>" --log content/drafts/<slug>.md
   ```

   Done when every query has run, each with `--log`.
2. **Score every candidate yourself before it counts as evidence.** Keep
   a source only if it supports a claim, not if it merely shares the
   query's words. Before your first `evidence.md` block, read
   `.claude/skills-common/references/genre-steps.md` §5. Where a snippet
   cannot settle a source you mean to keep:

   ```bash
   python -m chitragupta.draft retrieve evidence "<sub-theme>" --citekey <key> --log content/drafts/<slug>.md
   ```

   Before drafting, record what survives in `evidence.md`: a
   `relevance:` line, a `claim:` line in your own words and, where a
   passage is worth showing the reader as the source wrote it, a
   `quote:` line for each such passage. Record what doesn't in `rejected.md`, then:

   ```bash
   python -m chitragupta.draft dossier check-evidence content/drafts/<slug>.md
   ```

   Done when every candidate is in one of the two files.
2a. **On a broad topic, put steps 1-2 behind a subagent.** If your session
   offers subagent tools, spawn one per sub-theme, each told to
   run the retrieve-and-score loop above and return **only** the
   kept-evidence packet plus the rejected list -- never the raw
   candidates. Before dispatching, read
   `.claude/skills/survey-writer/references/survey.md` §1. Done when
   each packet is in the dossier.
3. **Reformulate and re-search if a sub-theme comes up thin.** When one
   does, read `.claude/skills-common/references/genre-steps.md` §6.
   Done when each is covered, or reported thin after real attempts.
4. **Cluster by judgment.** With a small corpus there's no BERTopic
   step: group the kept citekeys into themes by what the evidence says.
   Done when each sits in a theme.
5. **Check for disagreement across sources before writing.** When two
   kept sources conflict, read
   `.claude/skills-common/references/genre-steps.md` §6. Done when each
   conflict is noted for the draft.
6. **Draft**, in Markdown, citing as `[@citekey]` or `[@key1; @key2]`
   only from `evidence.md`: a framing paragraph, one subsection per
   theme, a comparison table and a gap-analysis paragraph. Before the
   table, read `.claude/skills/survey-writer/references/survey.md` §2.
   The table carries a caption and an id
   (`docs/writing-standards/tables.md` §13):

   ```markdown
   | Starting point | Citekey | Core idea | Stated limitation |
   |---|---|---|---|
   | ... | ... | ... | ... |

   : Where to start when building a first twin.
   <!-- table: start-here -->
   ```

   The prose names it with `<!-- tableref: start-here -->`. A body
   paragraph closes on two or more citekeys wherever the evidence
   allows, or carries `<!-- single-source: why -->` on the line beside
   it (`docs/WRITING-STANDARDS.md` §11;
   `python -m chitragupta.review synthesis <draft>` reports it). Done
   when every section is drafted.
7. **Never write a citekey you didn't get from a retrieval result.** If
   you want to cite something the ledger lacks, say so to the user in
   prose ("X is commonly discussed in this area but isn't in your synced
   library yet"); do not invent a key for it. Done when every key came
   from a retrieval result.
8. **Map sections to citekeys.** Save the draft, then:

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
   ```

   A citekey it reports above the first heading belongs to no section:
   fix the draft, not the table. Done when it reports none.
9. **Add a figure only for what the table can't express**; absence is
   the default. A figure is a pair of files, `figures/<name>.tex` and
   `figures/<name>.txt`, named by a marker line of its own
   (`docs/writing-standards/figures.md` §10):

   ```html
   <!-- figure: figures/<name> -->
   ```

   Hand the drawing to `figure-drawer` and come back to this step when
   it returns. What holds even if that skill is never loaded:

   - **A topic directory is required.** Move a flat draft and its
     dossier first, or drop the figure: here, usually the right answer.
   - **Check for TikZ, and that the figure compiles.** If
     `figure-drawer` was not loaded, run `kpsewhich tikz.sty`: if it
     finds nothing, write the ASCII inline in a fence, no pair and no
     marker, and say so in chat. A figure you keep compiles on its own
     first, with `lualatex`: a malformed one fails the whole pdf render.
   - **No citekey inside either figure file.**
   - **Nothing redrawn from a source.**
   - **The `.txt` form is 7-bit ASCII, and the caption is in the
     draft**, never in a figure file. Never write the word "Figure" or
     a number yourself: the renderer assigns both.
   - **A caption line directly below the marker**, and
     `<!-- figureref: <name> -->` where the prose points at it.

   A quantity follows `docs/writing-standards/mathematics.md` §12. To
   number an equation, put `<!-- equation: <id> -->` above its
   `<!-- math -->` block and `<!-- equationref: <id> -->` in the
   sentence that explains it. Before adding a figure or numbering an
   equation, read `docs/writing-standards/genres/survey.md`. Done when
   each figure has both files and a caption.

10. **Critique against the evidence packet, before gating.** This step
    runs on every survey, once the draft is written and before step 11's
    gate. Read the dossier's `evidence.md` -- the `claim:`/`quote:` blocks
    step 2 recorded -- against the draft, section by section, and list in
    priority order up to five places where the prose claims more than
    its `claim:` supports, omits a kept `claim:`, or drifts from its
    wording. One inline judgement call: not a subagent dispatch and not
    a deterministic check.

    Read `.claude/skills-common/references/critique.md` now, before
    listing anything, and follow it with `content/drafts/<slug>.md` as
    `<draft>`; make each edit with an `apply_patch` hunk.
    **This step is not done until the loop the reference describes has
    run**: the baseline, then at most three repairs, each checked and
    logged in the dossier's `revisions.md`. It is never a condition of
    presenting. Come back with the list, each repair kept or reverted,
    the scan's `tiers_not_run` reason if it gave one, and whether the
    declared queries are exhausted; then continue to step 11. Done when
    the loop has returned and every attempt is logged, or you have said
    that nothing cleared the bar.
11. **Gate before presenting.** Save the draft as
    `content/drafts/<slug>.md` (the canonical, source-of-truth format),
    then:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.md
    ```

    On `FAIL`, fix the offending line -- correct the citekey or remove
    the claim -- and re-run. Never show the user a draft that hasn't
    passed. Done when it reports `OK`.
12. **Build the References section.** Follow
    `.claude/skills-common/references/render-and-references.md` §1 for
    `content/drafts/<slug>.md`. Done when `draft references` has run.
13. **Render tex, pdf and md, then the evidence sidecar.** Follow
    `.claude/skills-common/references/render-and-references.md` §2 and
    §3 for the same draft: tex, pdf and md, then the sidecar in pdf and
    md. **A survey emits one**: its reader is mapping a field and wants
    to see what the sources actually said, which the sidecar shows from
    the `quote:` lines. If the user asks for more on why, read
    `.claude/skills/survey-writer/references/survey.md` §3. Done when
    each command has run or its warning is reported.
14. **Read it once as the reader, and record any steering.** Reread
    against the checklist in `docs/writing-standards/genres/survey.md`.
    If the user shaped this draft in chat, append that to the dossier's
    `steering.md`, dated; read
    `.claude/skills-common/references/genre-steps.md` §2 if unsure what
    counts. If the reread changes a citation, run step 11's gate again.
    Done when both are done.
15. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it. If the user wants any finding acted on, that is
    `draft-reviser`'s copy-edit mode, never an edit made here. Done when
    every finding is reported.
16. **Run the verbatim scan.** Before presenting, rebuild the section map
    and scan:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md
    ```

    The first command is not optional and not a repeat of step 8.
    **A review aid, not a gate: it is never a condition of presenting.**
    Read `.claude/skills-common/references/verbatim-scan.md` now and
    follow it. Repairing a finding is `agenda-reviser`'s job, and only
    if the user asks. Done when the findings are shown.
17. **Stamp the draft fingerprint, then present.** Read
    `.claude/skills-common/references/genre-steps.md` §7 first, then:

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<slug>.md
    ```

    Present as that section says. Changes go through `draft-reviser`,
    and `python -m chitragupta.draft dossier export <slug>` backs a draft
    and its dossier up. Done when the user has the draft.
