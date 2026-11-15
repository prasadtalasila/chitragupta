---
name: tutorial-writer-opencode
description: Drafts a Diataxis-style tutorial -- a hands-on lesson a learner follows at a keyboard, start to finish, to a working result they can see -- verified to actually run before it is presented. Not a textbook chapter and not a how-to guide; if the reader is studying rather than doing, use `textbook-chapter-writer-opencode`, and if they only need the steps, say so rather than writing a tutorial. May cite the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) only in a closing "Where to go next" section, never mid-lesson. Triggers when the user asks for a tutorial, a hands-on lesson, a getting-started walkthrough, a lab exercise, or a "teach someone X by having them build Y" document. To change a tutorial that already exists in content/drafts/, use draft-reviser-opencode instead -- never re-run this skill to make a change. Any citation must pass `python -m chitragupta.draft gate` before the draft is presented -- never a fabricated citekey.
tags: [tutorial, diataxis, hands-on, lesson, teaching]
---

# tutorial-writer-opencode

Drafts a lesson, in the Diataxis sense: a learner does something under
your guidance, at a keyboard, and comes out with a working result and the
skill to make it. **A tutorial that doesn't work is worse than no
tutorial**, so the lesson is run end to end before it is presented. Paths
in this skill are from the project root, not from this skill's own folder.

## What this genre is not

| Genre | Reader's state | Skill |
| --- | --- | --- |
| **Tutorial** (this one) | Doesn't know what they don't know; needs a guided first success | `tutorial-writer-opencode` |
| **Textbook chapter** | Studying the topic; reading, not typing | `textbook-chapter-writer-opencode` |
| **How-to guide** | Already competent; has a specific goal in mind | Not a skill here -- say so, and write it as a short procedure |
| **Reference** | Needs a fact, fast | Not a skill here |
| **Survey / thesis chapter** | Academic reader | `survey-writer-opencode` / `thesis-chapter-writer-opencode` |

If the user actually wants one of the others, tell them so and write that
instead. Changing a tutorial that **already exists** in `content/drafts/`
is `draft-reviser-opencode`'s, never another run of this skill: a fresh run
rewrites a lesson that already works and throws away its dossier.

## Prose standards

Follow `docs/WRITING-STANDARDS.md` for the rules every genre shares, and
`docs/writing-standards/genres/tutorial.md` for what a lesson owes its
learner, including the two ways a lesson drifts: read it before step 4.
The works these standards come from are credited in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#-sources-and-attribution);
if asked what bears on a tutorial, read
`.claude/skills/tutorial-writer/references/tutorial.md` §7.

## Before you start

**The corpus is read-only: never run `python -m chitragupta.corpus sync`
or `python -m chitragupta.enrich`.** Before the first retrieval, read
`.claude/skills-common/references/genre-steps.md` §1: what the corpus
holds, and why those are the user's to run, but not its empty-ledger
rule, which this genre replaces below. Check the ledger first:

```bash
python -m chitragupta.corpus ledger
```

If it reports nothing `parsed`, say so before you start. Citations are
optional in this genre, so the lesson is still possible, but it will
carry none: ask whether to proceed uncited or to sync first, and wait
for the answer.

## Collection scoping

Before the first retrieval, check whether the library is sorted into
collections:

```bash
python -m chitragupta.corpus ledger --collections
```

If it reports none, say nothing, ask nothing, record
`- collection: (whole corpus)` in `scope.md`'s header, and skip this
section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run. If retrieval inside the shelf comes back thin, the
honest fix to offer is a whole-corpus pass with `corpus-reviser-opencode`, which
is the one skill allowed to widen.

## Process

1. **Establish the destination artifact, and open the dossier.** Name
   the one concrete thing the learner will have working at the end,
   in a sentence; ask the user rather than inventing one. Before
   creating the dossier, read
   `.claude/skills-common/references/genre-steps.md` §2 and §3 (the
   slug, `scope.md`, the dialect, the acronym vocabulary and the
   fingerprint), and `.claude/skills/tutorial-writer/references/tutorial.md`
   §1 for what a lesson's `scope.md` records. Settle `<slug>` with the
   user, then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<slug>.md --genre tutorial
   ```

   Done when `scope.md` records the reader, the destination and
   `language:`.
2. **Do a task analysis.** Walk the entire path yourself first, actually
   running it (see step 8), and write down every command, file and
   decision it needs, including the ones you do without noticing. Record
   the happy path you chose, and every alternative you turned down,
   under a `## Rejected paths` heading in `rejected.md`. Before you
   start, read `.claude/skills/tutorial-writer/references/tutorial.md`
   §2. Done when the path is written down and each turned-down
   alternative has its row.
3. **Write the front matter the learner needs before starting:** what
   you'll build, what you'll learn, what you need (exact versions) and
   how long it takes, each as
   `.claude/skills/tutorial-writer/references/tutorial.md` §2 describes.
   Done when all four are in the draft.
4. **Write the steps.** Each step is one action the learner takes,
   opening on an imperative verb, with real values, never placeholders,
   and the result they should see; one path, no options. Before writing
   them, read `.claude/skills/tutorial-writer/references/tutorial.md`
   §3. Done when every step has its action and, where it produces one,
   its expected result.
5. **Land the ending.** Restate what the learner just built and what
   they can now do, tied back to step 3's promises. Done when the lesson
   closes on that.
6. **"Where to go next".** Deferred explanation, the alternatives you
   refused, and further reading live here, and this is the only section
   that may cite. Before searching, read
   `.claude/skills/tutorial-writer/references/tutorial.md` §4. First
   check for an `outline.md`:

   ```bash
   python -m chitragupta.draft dossier outline content/drafts/<slug>.md --check
   ```

   If it passes, read `.claude/skills-common/references/genre-steps.md`
   §4 and run this section's declared queries verbatim, logged
   `--origin declared`; a thin one's reformulations are
   `--origin extended`. Otherwise over-fetch on your own terms:

   ```bash
   python -m chitragupta.draft retrieve search "<topic>" --k 15 --collection "<from scope.md>" --log content/drafts/<slug>.md
   ```

   When a search comes back thin, read
   `.claude/skills-common/references/genre-steps.md` §6. Cite only a
   real citekey from a search result, and more than one where the corpus
   allows; with exactly one, put `<!-- single-source: why -->` beside
   the section (`docs/WRITING-STANDARDS.md` §11;
   `python -m chitragupta.review synthesis <draft>` reports
   `unit: document`). If you searched, read
   `.claude/skills-common/references/genre-steps.md` §5 before recording
   `evidence.md` and `rejected.md`, then:

   ```bash
   python -m chitragupta.draft dossier check-evidence content/drafts/<slug>.md
   ```

   Done when the section is written, and every candidate you retrieved
   is in one of the two files.
7. **Budget the length.** A tutorial is completable in one sitting; a
   path outgrowing that is split into a sequence of tutorials with
   explicit prerequisites. Done when the lesson fits one sitting, or is
   split.
8. **Run it. This step is not optional.**
   Execute every command in the draft, in order, in as clean an
   environment as you can reach (a fresh directory at minimum; a
   container if the tutorial involves installs). Confirm each stated
   expected result actually appears. Fix the draft, then run it again
   from the top -- a fix in step 4 routinely breaks step 7.
   If you genuinely cannot execute part of it in this environment, **say
   so explicitly in chat** when presenting, naming which steps are
   unverified. Never present an unrun tutorial as if it were tested.

   Then write what you actually ran against into `scope.md`, under a
   `## Verified environment` heading you add: the exact versions this
   run used, not the range step 3 advertises, and the steps you could
   not verify. If asked why, read
   `.claude/skills/tutorial-writer/references/tutorial.md` §5.

   A tutorial rarely needs a table, and a comparison table almost never.
   If the lesson calls for one (flags, or expected outputs),
   `docs/writing-standards/tables.md` §13 applies: a caption line,
   `<!-- table: <id> -->` under it, and `<!-- tableref: <id> -->` where
   a step points at it. Done when the lesson ran start to finish, every
   expected result appeared, and the verified environment is recorded.
9. **Add a figure, if the path needs one.** Go back to wherever it
   belongs -- what the learner is about to build in the front matter
   (step 3), or how data moves through a command beside that step
   (step 4) -- rather than appending a new section here. The test is per
   figure, never a budget: does *this* step read more clearly as a
   diagram? A figure is a pair of files, `figures/<name>.tex` and
   `figures/<name>.txt`, named by a marker line of its own
   (`docs/writing-standards/figures.md` §10); `--format tex` and
   `--format pdf` (step 15) get the TikZ:

   ```html
   <!-- figure: figures/<name> -->
   ```

   Hand the drawing to `figure-drawer-opencode` and come back to this step when
   it returns. What holds even if that skill is never loaded:

   - **A topic directory is required.** Move a flat draft and its
     dossier first, or skip the figure.
   - **Check for TikZ, and that the figure compiles.** If
     `figure-drawer-opencode` was not loaded, run `kpsewhich tikz.sty`: if it
     finds nothing, write the ASCII inline in a fence, no pair and no
     marker, and say so in chat. A figure you keep compiles on its own
     first, with `lualatex`: a malformed one fails the whole pdf render.
   - **No citekey inside either figure file.** Step 13's gate does not
     follow `\input`.
   - **Nothing redrawn from a source.**
   - **A caption line directly below the marker**, no blank line
     between, and `<!-- figureref: <name> -->` where a step points at
     it. Every figure has one.

   A quantity the lesson reasons about follows
   `docs/writing-standards/mathematics.md` §12; a value the learner
   types stays code. When the lesson reasons about one, read
   `.claude/skills-common/references/mathematical-prose.md` now and
   follow it. To number a reused formula, put `<!-- equation: <id> -->`
   above its `<!-- math -->` block and `<!-- equationref: <id> -->` at
   the reuse. Before adding a figure or a quantity, read
   `docs/writing-standards/genres/tutorial.md`. Done when each figure
   has both files and a caption.
10. **Reread as the beginner.** One pass as someone who has never seen
    the topic, against the reread and the self-check in
    `docs/writing-standards/genres/tutorial.md`, fixing what it finds.
    Done when every self-check question is answered "yes".
11. **Map the lesson's outline into the dossier.** Save the draft to
    `content/drafts/<slug>.md`, then derive `sections.md`:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    ```

    An empty citekey cell is the honest result in this genre. Done when
    the table is written.
12. **Critique against the evidence packet, before gating.** This step
    runs only if the lesson cites anything; with no citations there is
    no evidence packet, so skip to step 13. Read the dossier's
    `evidence.md` -- the `claim:`/`quote:` blocks step 6 recorded --
    against "Where to go next" alone, the only section that cites, and
    list in priority order up to five places where it claims more than
    its `claim:` supports, omits a kept `claim:`, or drifts from its
    wording. One inline judgement call: not a subagent dispatch and not
    a deterministic check.

    Read `.claude/skills-common/references/critique.md` now, before
    listing anything, and follow it with `content/drafts/<slug>.md` as
    `<draft>`; make each edit with `edit`, inside "Where to go next"
    only.
    **This step is not done until the loop the reference describes has
    run**: the baseline, then at most three repairs, each checked and
    logged in the dossier's `revisions.md`. It is never a condition of
    presenting. Come back with the list, each repair kept or reverted,
    the scan's `tiers_not_run` reason if it gave one, and whether the
    declared queries are exhausted; then continue to step 13. Done when
    the loop has returned and every attempt is logged, or you have said
    that nothing cleared the bar.
13. **Gate any citations.** Save the draft as `content/drafts/<slug>.md`.
    If it contains any `[@citekey]`, run:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.md
    ```

    Fix and re-run until `OK` before presenting; with no citations at
    all, just save the file. The gate blanks what pandoc does not render
    as prose (fenced and indented code, inline code spans, HTML comments,
    LaTeX verbatim environments), so `@dataclass` in worked code is no
    false positive: don't mangle teaching code to appease it, and close
    every fence you open, since pandoc and the gate read an unclosed one
    as prose. Done
    when it reports `OK`, or the lesson cites nothing.
14. **Build the References section**, only if the draft cites anything:
    follow `.claude/skills-common/references/render-and-references.md`
    §1 for `content/drafts/<slug>.md`, keeping the default
    `## References` heading. Done when `draft references` has run, or
    the lesson cites nothing.
15. **Render tex, pdf, and numbered md.** Follow
    `.claude/skills-common/references/render-and-references.md` §2 for
    the same draft, in all three formats. **Do not render an evidence
    sidecar** (`python -m chitragupta.draft evidence`): a recorded
    answer, not an omission. If asked why, read
    `.claude/skills/tutorial-writer/references/tutorial.md` §6. Done
    when each render has run or its warning is reported.
16. **Record any steering.** If the user shaped this lesson in chat
    ("use FastAPI, not Flask", "no Docker", "keep it under twenty
    minutes", "assume they've never opened a terminal"), append it to the
    dossier's
    `steering.md`, dated; read
    `.claude/skills-common/references/genre-steps.md` §2 if unsure what
    counts. Done when it is recorded, or there was none.
17. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it. If the user wants any finding acted on, that is
    `draft-reviser-opencode`'s copy-edit mode, never an edit made here. Done when
    every finding is reported.
18. **Run the verbatim scan.** Before presenting, rebuild the section map
    and scan:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md
    ```

    The first command is not optional and not a repeat of step 11.
    **A review aid, not a gate: it is never a condition of presenting.**
    Read `.claude/skills-common/references/verbatim-scan.md` now and
    follow it. Repairing a finding is `agenda-reviser-opencode`'s job, and only
    if the user asks. Done when the findings are shown.
19. **Stamp the draft fingerprint, then present.** Read
    `.claude/skills-common/references/genre-steps.md` §7 first, then:

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<slug>.md
    ```

    Present as that section says, and say explicitly whether step 8's
    verification passed in full, in part, or not at all. Changes go
    through `draft-reviser-opencode`, and
    `python -m chitragupta.draft dossier export <slug>` backs a lesson
    and its dossier up. Done when the user has the draft.
