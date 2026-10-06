---
name: tutorial-writer
description: Drafts a Diataxis-style tutorial -- a hands-on lesson a learner follows at a keyboard, start to finish, to a working result they can see -- verified to actually run before it is presented. Not a textbook chapter and not a how-to guide; if the reader is studying rather than doing, use `textbook-chapter-writer`, and if they only need the steps, say so rather than writing a tutorial. May cite the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) only in a closing "Where to go next" section, never mid-lesson. Triggers when the user asks for a tutorial, a hands-on lesson, a getting-started walkthrough, a lab exercise, or a "teach someone X by having them build Y" document. To change a tutorial that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Any citation must pass `python -m chitragupta.draft gate` before the draft is presented -- never a fabricated citekey.
tags: [tutorial, diataxis, hands-on, lesson, teaching]
---

# tutorial-writer

Genre-specific drafting agent for tutorial output, in the Diataxis sense: a
**lesson**, in which a learner does something under your guidance and comes
out with skill and confidence they didn't have before. The drafting layer
(generative, on-demand, user-reviewed).

The governing analogy is a driving lesson. The point of a driving lesson is
not to get from A to B; the point is that the student can drive afterwards.
The route is a pretext. Everything in a tutorial is chosen for what it
teaches, not for what it produces -- and the instructor, not the student, is
responsible for the student arriving safely.

That responsibility is the whole discipline of this genre. **A tutorial that
doesn't work is worse than no tutorial**, because a learner who follows your
instructions exactly and gets an error concludes they are the problem. Every
rule below follows from that.

## What this genre is not

| Genre | Reader's state | Skill |
| --- | --- | --- |
| **Tutorial** (this one) | Doesn't know what they don't know; needs a guided first success | `tutorial-writer` |
| **Textbook chapter** | Studying the topic; reading, not typing | `textbook-chapter-writer` |
| **How-to guide** | Already competent; has a specific goal in mind | Not a skill here -- say so, and write it as a short procedure |
| **Reference** | Needs a fact, fast | Not a skill here |
| **Survey / thesis chapter** | Academic reader | `survey-writer` / `thesis-chapter-writer` |

Changing a tutorial that **already exists** in `content/drafts/` is not a
genre question at all: use `draft-reviser`, never another run of this
skill. Re-running it rewrites a lesson that already works, and throws
away the dossier that recorded why each step is the way it is.

The two failure directions, both common:

- **Drifting into explanation.** You get anxious that the learner should
  *know* things, and start explaining the architecture mid-step. The lesson
  stalls. Minimal inline explanation, link or defer the rest.
- **Drifting into a how-to.** You start offering options ("you could also use
  X"), covering edge cases, and handling alternate environments. A learner who
  doesn't yet know the domain cannot evaluate an option; every choice you
  offer is a place to get lost. **One path. No branches.**

If the user actually wants either of those, tell them so and write that
instead. Writing a tutorial when a how-to was wanted wastes everyone's time.

## Prose standards

`docs/WRITING-STANDARDS.md` holds the cross-genre rules -- name the reader,
define terms once, active voice, ban "obviously/simply/just", reread as the
reader. They all apply here.

Where this genre departs from it: §5's "don't let a document do two jobs" is
strictest in this skill, and the structural rules below (single path, no
options, minimal explanation) are *tutorial-only*. Do not carry them into any
other genre -- in a survey they'd delete the deliverable.

## Shared corpus layer (read, don't regenerate)

- `content/ledger.sqlite` -- per-citekey status, populated by `sync`
- `content/parsed/<citekey>.txt` -- extracted PDF text
- `chitragupta/retrieval.py` -- `search(query, k, snippet_chars)`

**Read-only means read-only: never run `python -m chitragupta.corpus sync`, and
never
run `python -m chitragupta.enrich` or any `chitragupta/enrich/*` build stage.**
Both belong to the
corpus layer, both take the pipeline's write lock, and either can run for
tens of minutes -- a first full-corpus parse, or building the embedding
index. They are the user's to run, not yours. If a semantic index would
help and none exists, say so and use `chitragupta.retrieval.search()`; do not
build one.

If `python -m chitragupta.corpus ledger` reports an empty ledger, say so before
you
start. Citations are optional in this genre, so the draft is still
possible -- but it will carry none, and that is the user's call to make,
not something to discover at the end. Ask whether to proceed uncited or to
sync first, and wait for the answer.

**Citations are rare in this genre and belong only in the closing "Where to go
next" section.** A `[@citekey]` inside a step is a distraction from the task at
hand -- the learner is typing, not evaluating literature. If corpus material
shapes the lesson (a real system worth imitating, a dataset worth using), let
it inform your choices silently and point at it at the end.

## Collection scoping (#195): draft from the shelf, not the library

At step 0, before any retrieval, check whether the library is sorted
into collections:

```bash
python -m chitragupta.corpus ledger --collections     # what exists, with counts
```

Paths in this skill are from the project root, not from this skill's
own folder.

If it reports none, say nothing, ask nothing, record
`- collection: (whole corpus)` in `scope.md`'s header, and skip the rest
of this section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run. If retrieval inside the shelf comes back thin, the
honest fix to offer is a whole-corpus pass with `corpus-reviser`, which
is the one skill allowed to widen.

## The dossier: write down what produced the draft

The lesson is only half of what this run produces. The other half is the
design behind it -- who the learner is, what they were assumed to already
know, the one happy path you chose, **which alternative paths you turned
down and why**, and the environment the steps were actually verified
against. A tutorial is single-path by definition, so the branches you
refused are precisely the judgment the finished prose cannot show.
Without them on disk, the next revision has to re-derive the whole lesson
design in order to change one step.

`chitragupta/dossier/` owns that state, in Markdown, one directory per draft at
`content/dossiers/<the draft's path, minus its suffix>/`. Create it in
step 1, before you write anything, and fill it in as you go -- not at the
end, when the alternatives you rejected have already fallen out of your
context. `docs/DRAFT-ITERATION.md` is the full design.

None of this depends on the draft citing anything. A tutorial with zero
citations still gets a dossier, and an empty `evidence.md` is honest --
the lesson design is the part worth keeping either way.

## Process

1. **Establish the destination artifact, and open the dossier.** Decide the
   one concrete thing the learner will have working at the end -- small, real,
   and visibly functioning. "A working X that does Y when you run it," not "an
   understanding of X." If you can't name it in a sentence, the tutorial isn't
   scoped yet. Ask the user rather than inventing one, if it wasn't given.

   Then, once the artifact and the draft's path are settled and before any
   retrieval or drafting, create the dossier:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<slug>.md --genre tutorial
   ```

   **Settle `<slug>` with the user before running that.** It is a path
   under `content/drafts/` and it may contain directories: "a lab for
   the `books/software-engineering` course" means
   `content/drafts/books/software-engineering/tutorial.md`, and a topic
   that will hold more than one genre wants
   `content/drafts/<topic>/tutorial.md` so they sit together. A flat
   `content/drafts/<slug>.md` is the default when neither applies. Ask
   rather than guess: the dossier (`content/dossiers/<slug>/`) and every
   render (`content/rendered/<the draft's own directory>/`) mirror
   whatever you pick, so moving the draft later means moving both.
   Fill in `scope.md` now, while you are deciding these things rather than
   reconstructing them later:
   - **Reader** -- the learner in one concrete sentence, including what they
     are assumed to know already. Step 3's prerequisites follow from this.
   - **Covers** -- the destination artifact, and the capability the lesson
     leaves the learner with.
   - **Does not cover** -- the variations, edge cases and alternate
     environments you are deliberately refusing, so a later session can tell
     a scope decision from an oversight.
   - **Glossary** -- each recurring term with the one definition the whole
     lesson uses. Check the acronym vocabulary first --
     `assets/style/acronyms.toml`, plus the user's own file if
     `[style].acronyms` in `config.toml` points at one -- for a term's
     recorded expansion before inventing one.
   - **`language:`** -- the dialect, a BCP-47 tag, settled with the reader.
     The line ships unset, and a lesson whose dialect nobody chose silently
     gets the model's own (`docs/WRITING-STANDARDS.md` §8). Command output
     and file contents are quoted material and keep whatever spelling the
     tool actually emits.

   `init` also stamps the corpus fingerprint, which is what lets a later
   revision tell whether the ledger has moved since.

2. **Do a task analysis.** Walk the entire path yourself first, actually
   running it (see step 8), and write down every command, file and decision
   the path requires -- including the ones you'd normally do without noticing.
   The steps you perform automatically are exactly the ones your draft will
   omit and your learner will fail on.

   Record the outcome in the dossier while you have it: the single happy path
   you settled on, and every alternative you walked away from. Add a
   `## Rejected paths` section to `rejected.md` with its own two-column table
   -- `alternative | why not chosen` -- and leave the citekey table above it
   for retrieved candidates. "Poetry instead of venv: one more install before
   the lesson starts." "Docker instead of a local interpreter: hides the thing
   being taught." This is the most valuable entry a tutorial's dossier holds,
   because the prose can only show the path you kept; a revision without this
   list re-argues every branch you already decided.

3. **Write the front matter the learner needs before starting:**
   - **What you'll build** -- one or two sentences, ideally with the end
     result shown up front (output, screenshot description, sample response).
     Seeing the destination is what makes someone willing to start.
   - **What you'll learn** -- phrased as capability, not curriculum.
   - **What you need** -- exact prerequisites: versions, installed tools,
     accounts, prior tutorials. Be specific ("Python 3.11+, Docker 24+"), not
     vague ("a recent Python").
   - **How long it takes** -- an honest estimate.

4. **Write the steps.** Rules, in priority order:
   - **Every step is an action the learner takes.** If a step has no verb the
     learner performs, it's explanation; move it or cut it.
   - **Start each step with an imperative verb.** One action per step.
   - **Be concrete, never abstract.** Real filenames, real values, real
     commands -- never `<your-project-name>` where a literal `demo-app` would
     do. Placeholders make the learner make a decision, and decisions are
     where they stall.
   - **Show the expected result after every step that produces one.** "You
     should see `Listening on port 8080`." This is the learner's only way to
     know they're still on the path, and the single highest-value thing you
     can add to a draft.
   - **Guarantee results.** Nothing may depend on the learner's environment,
     prior state, or judgement. If something can vary, pin it (a version, a
     seed, a container).
   - **No options, no alternatives, no "depending on your setup".** Choose for
     them.
   - **Minimal explanation inline.** One clause where it prevents confusion
     ("we use HTTPS here because it's safer"), then move on. Park the real
     explanation in step 6.
   - **Repetition is fine.** Don't refactor the lesson for elegance; a
     learner benefits from doing a thing three times.
   - **Warnings go before the step they concern, not after.** A caution the
     learner reads after destroying their state is not a caution.
   - **Never say "simply", "just", "obviously", or "easy".** When it isn't,
     the learner concludes the failure is theirs.

5. **Land the ending.** Close by restating what the learner just built and
   what they can now do -- explicitly, tied back to step 3's promises. A
   tutorial that stops at the last command leaves the learner unsure whether
   they succeeded.

6. **"Where to go next".** This is where deferred explanation, alternatives,
   and further reading live. Link the concepts you passed over quickly, name
   the how-to guides for the variations you refused to cover, and -- if the
   corpus genuinely has something -- cite it here.

   If the dossier has an `outline.md` (`dossier init --outline`, or
   added later) with declared `queries:` for this section, run those
   verbatim instead of choosing your own search terms, logged `--origin
   declared`; a search that comes up thin still gets the reformulation
   below, logged `--origin extended` instead -- check first with
   `python -m chitragupta.draft dossier outline content/drafts/<slug>.md
   --check`. Citing stays optional here regardless, so a `claim:` block
   is a steer toward a specific assertion worth grounding if the corpus
   supports it, not an obligation the way it is in the citation-dense
   genres.

   Otherwise, same retrieval discipline as the other skills if you do
   search: over-fetch

   ```bash
   python -m chitragupta.draft retrieve search "<topic>" --k 15 --collection "<from scope.md>" --log content/drafts/<slug>.md
   ```

   `--log` records the query in the dossier's `retrieval.md`. **Pass it on
   every call**, even here where citing is optional -- it is what a later
   `dossier status` re-asks against the corpus to say which newly synced
   papers this lesson has never seen. Then read each 500-character
   snippet yourself rather than trusting the score, and reformulate and
   search again rather than settling for a weak top hit. Citing remains
   optional; a tutorial with zero citations is the normal case, not a
   deficiency. Anything you do cite must be a real citekey from a `search()`
   result -- never a fabricated one.

   **The multi-source floor here is the whole document, not the
   paragraph.** A tutorial's body carries no citations by design, so the
   thing that can go wrong is one level up: the lesson being a walkthrough
   of a single source's procedure from end to end. That failure is
   invisible at every scale below the document. So when you do cite, cite
   more than one source -- two or more distinct citekeys in this section
   are the evidence that the lesson was derived rather than transcribed.
   Where the corpus genuinely holds one relevant paper, or none, that is
   not a deficiency either; say so with `<!-- single-source: why -->`
   adjacent to the section if you cited exactly one.
   docs/WRITING-STANDARDS.md §11 is the rule; `python -m
   chitragupta.review synthesis <draft>` reports it, and on a tutorial it
   will say `unit: document` -- that is the measurement working, not a
   missing paragraph-level check.
   If you did search, record both outcomes in the dossier before you draft
   the section: what you keep into `evidence.md`, one ``## `citekey` `` block
   with a `relevance:` line, a `claim:` line -- what the source establishes,
   in your own words, the only field you may draft prose from -- and, only
   where a quotation is genuinely warranted, a `quote:` line (verbatim,
   usable only inside quotation marks with an attribution); what you
   retrieved and turned down into `rejected.md`'s citekey table, with the
   query that surfaced it and a few words on why. Then run
   `python -m chitragupta.draft dossier check-evidence content/drafts/<slug>.md`
   -- advisory. Flags a citekey carrying more than one `evidence.md`
   block (the first is the one every reader gets, so merge them), and a
   `claim:` that reads like its `quote:` reworded; a reword warning is a
   cue to re-read your own judgment, not to reword until it stops.

7. **Budget the length.** A tutorial should be completable in one sitting.
   If the path is outgrowing that, split it into a sequence of tutorials with
   explicit prerequisites rather than shipping one the learner abandons
   halfway.

8. **Run it. This step is not optional.**
   Execute every command in the draft, in order, in as clean an environment as
   you can reach (a fresh directory at minimum; a container if the tutorial
   involves installs). Confirm each stated expected result actually appears.
   Fix the draft, then run it again from the top -- a fix in step 4 routinely
   breaks step 7.
   If you genuinely cannot execute part of it in this environment, **say so
   explicitly in chat** when presenting, naming which steps are unverified.
   Never present an unrun tutorial as if it were tested; an untested tutorial
   is the exact artifact this genre exists to avoid.

   Then write what you actually ran against into `scope.md`, under a
   `## Verified environment` heading you add: the exact versions this run
   used ("verified 2026-08-07 on Python 3.11.9, Docker 24.0.7"), not the
   range step 3 advertises. The front matter states what the tutorial
   supports; the dossier states what was executed, which is what a revision
   months later needs in order to tell a rotted step from a mistyped one.
   Name the steps you could not verify there too -- that is the durable half
   of the disclosure you make in chat.

   A tutorial rarely needs a table, and a comparison table almost never
   belongs in one -- weighing alternatives is a different genre's job. If
   the lesson genuinely calls for one (a table of flags, or of expected
   outputs), `docs/WRITING-STANDARDS.md` §13 applies unchanged: a caption
   line, `<!-- table: <id> -->` under it, and an inline
   `<!-- tableref: <id> -->` where the step points at it. Never write the
   number yourself.

9. **Add a figure, if the path needs one.** Go back to wherever it
   belongs -- what the learner is about to build in the front matter
   (step 3), or how data moves through a command beside that step
   (step 4) -- rather than appending a new section here.
   `docs/WRITING-STANDARDS.md` §10's original ASCII diagrams fit this
   genre more naturally than any other in this pipeline, and this is the
   genre most free to use them: a hands-on lesson can legitimately carry
   a lot of figures -- what the learner is about to build, how data moves,
   what the screen should look like at a checkpoint -- and a heavily
   illustrated tutorial is a good tutorial, not an overgrown one. The
   test is per figure and never a budget: does *this* step read more
   clearly as a diagram than as text? Draw every one that passes, and
   none that doesn't.

   A figure that does earn its place is a **pair of files**, and §10 is
   the contract. This genre carries no inline form of either -- the
   draft names the figure in a marker line of its own, with nothing
   beside it:

   ```html
   <!-- figure: figures/<name> -->
   ```

   Write both `content/drafts/<topic>/figures/<name>.tex` (the TikZ
   picture) and `content/drafts/<topic>/figures/<name>.txt` (the ASCII
   form, in §10's 7-bit alphabet). The renderer swaps the marker for the
   `.txt` contents in a fence on `--format md` and every other
   non-LaTeX format, and `--format tex`/`--format pdf` (step 15) get
   `\input{figures/<name>.tex}`, so a learner reading the PDF gets a
   real picture instead of monospace art.

   Hand the drawing itself to `figure-drawer`, and come back to this
   step when it returns: it owns the layout metaphor and scaffold,
   panel letters, the ASCII twin, the compile probe and the geometry
   review. What stays here must hold even if that skill is never
   loaded:

   - **A topic directory is required.** If step 1 settled on a flat
     `content/drafts/<slug>.md`, move the draft and its dossier before
     adding a figure, or skip the figure. Figures under a flat draft
     land in `content/drafts/figures/`, shared with every other flat
     draft.
   - **Check for TikZ, and that the figure compiles.** If
     `figure-drawer` was not loaded, run `kpsewhich tikz.sty`
     yourself: if it finds nothing, write the ASCII inline in
     a fence instead, no pair and no marker, and say so in
     chat. A figure you keep compiles on its own first: a malformed
     one fails the whole pdf render, not just the figure.
   - **No citekey inside either figure file.** Step 13's gate reads the
     draft and does not follow `\input`, so a citekey in a node label
     evades the one check this pipeline exists for. This genre's
     citations belong in "Where to go next" anyway.
   - **Nothing redrawn from a source.**
     A picture redrawn from a source paper's figure is the same
     violation in different pixels.
   - **A caption, if this figure warrants one, goes in the draft, never
     in the figure file.** A caption line directly below the marker, no
     blank line between, and an inline `<!-- figureref: <name> -->`
     wherever the lesson points at it -- never write the word "Figure"
     or a number; the renderer assigns both. Most of this genre's rare
     figures need no caption at all, and that is the accepted case, not
     a gap.

   **A quantity in the prose follows `docs/WRITING-STANDARDS.md` §12.**
   Rare in this genre and easy to get wrong when it appears: a value the
   learner *types* stays a plain code span, because it is literal input,
   while a value the lesson *reasons about* is a quantity and needs a row
   in the dossier's `math.md`. `` `DRY_THRESHOLD = 35.0` `` in a config
   file is code; "the threshold is `k = 4` reading units per hour" is
   mathematics. When in doubt here, prefer code -- a tutorial's job is
   the keyboard, not the derivation.

   **Numbering one is rarer still.** §12 numbers an equation only if it
   is standalone, the last step of a derivation, or reused later, and a
   tutorial that keeps to the keyboard has no derivations to conclude.
   If a genuine formula does get reused across steps, mark it like a
   table -- `<!-- equation: <id> -->` directly above the
   `<!-- math -->` block, an inline `<!-- equationref: <id> -->` at the
   reuse -- rather than
   restating "the formula from step 3" in prose.

10. **Reread as the beginner.** One pass as someone who has never seen the
   topic. Flag: undefined terms, steps that assume a prior action you never
   instructed, any point where the learner must decide something, any step
   with no way to tell whether it worked.

11. **Map the lesson's outline into the dossier.** Save the draft to
    `content/drafts/<slug>.md` first if you haven't already -- `sections`
    reads the file and reports `No such draft` if it isn't on disk yet. Then
    derive `sections.md` rather than writing it by hand:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    ```

    It writes one row per heading, and it skips fenced code -- which matters
    more here than anywhere else, since a `# Step 1: ...` comment inside a
    shell block is indistinguishable from a heading to anything that doesn't
    track fences. The citekey column is thin in this genre by design:
    citations live only in "Where to go next", so usually that one section
    carries every key in the file, and often there are none at all. A row
    with an empty cell is the honest result, and it comes out that way
    without a judgement call. The outline is the real payload here. It is
    what lets `draft-reviser` repair one step of the lesson, at its recorded
    line range, without reading the whole thing.

12. **Critique against the evidence packet, before gating.** Skip this
    entirely if the lesson has no citations at all -- a tutorial with
    zero citations is the normal case, not a gap, and there is no
    evidence packet to critique against. Otherwise, since this genre
    cites only in "Where to go next," read the dossier's `evidence.md`
    -- the `claim:`/`quote:` blocks step 6 recorded -- against that
    section's own prose. List, in priority order, up to five places
    where the prose claims more than its `claim:` line supports, omits
    a kept `claim:` the section never used, or drifts from the wording
    `claim:` actually recorded. This is one inline judgement call, not
    a subagent dispatch and not a deterministic check -- nothing in
    this pipeline scores this automatically.

    **Run this step: it is never a condition of presenting, but it is not done
    until you have run its commands.** Read
    `.claude/skills-common/references/critique.md` now, before listing
    anything, and work it through with `content/drafts/<slug>.md` as
    `<draft>`. In outline:

    1. Where the dossier has an `outline.md`, read what the corpus could not
       answer:

       ```bash
       python -m chitragupta.draft dossier status content/drafts/<slug>.md
       ```

    2. Take the baseline:

       ```bash
       python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
       python -m chitragupta.review verbatim scan content/drafts/<slug>.md --write --json
       python -m chitragupta.draft style content/drafts/<slug>.md --json
       ```

       If the scan's `tiers_not_run` is not empty, quote the reason: **genuine
       restatement is only detected where the embedding tier can run**.
       `style` reports only what WRITING-STANDARDS.md §9 marks decidable, and
       this step is told to fix none of them: its count is a proxy for a new
       defect, not a work list.

    3. Repair at most three items, each edit with an `apply_patch` hunk,
       inside "Where to go next" only. Keep an edit only if all three checks
       pass the reference's test; otherwise restore the text you kept:

       ```bash
       python -m chitragupta.draft gate content/drafts/<slug>.md
       python -m chitragupta.review verbatim recheck content/drafts/<slug>.md \
           --baseline content/review/<topic>/<stem>.verbatim.json --json
       python -m chitragupta.draft style content/drafts/<slug>.md --json
       ```

       Read `style`'s count only as a number: it reports what §9 marks
       decidable, and you fix none of them here.

    4. Log every attempt, kept or reverted, in the dossier's `revisions.md`.

    If nothing on the list clears the bar, or the list was empty, say so and
    continue to the gate.
13. **Gate any citations.** Save the draft as `content/drafts/<slug>.md`. If
    it contains any `[@citekey]`, run:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.md
    ```

    Fix and re-run until `OK` before presenting. If there are no citations at
    all, the gate step is unnecessary -- just save the file.
    Note: the gate blanks what pandoc does not render as prose -- fenced and
    indented code (code indented under a numbered step included), inline
    code spans, HTML comments and LaTeX verbatim environments -- before
    extracting citekeys, so `@dataclass`, `@property` and similar tokens in
    your worked code are not false positives. Don't mangle real teaching
    code to appease it. Close every fence you open: pandoc reads an
    unclosed one as prose, and so does the gate.

14. **Build the References section**, only if the draft cites anything:

    ```bash
    python -m chitragupta.draft references content/drafts/<slug>.md
    ```

    Stdlib-only, bare `python`, no venv. Entries are numbered IEEE-style;
    leave the inline citations as `[@citekey]` rather than hand-numbering
    them. Skip entirely if there are no citations.

    Keep the default `## References` heading -- the same contract as
    `textbook-chapter-writer` (#699). `render_output` recognises the
    section only by a heading whose text is `References`, `Bibliography`
    or `Works cited`, bare or number-prefixed, and swaps its entries for
    citeproc's own bibliography; any other heading (an earlier draft of
    this skill said `Further reading`) leaves the manual list in the
    rendered `.tex`/`.pdf` *and* citeproc's bibliography below it, so
    every reference appears twice.

15. **Render tex, pdf, and numbered md.**

    ```bash
    python -m chitragupta.draft render content/drafts/<slug>.md --format tex
    python -m chitragupta.draft render content/drafts/<slug>.md --format pdf
    python -m chitragupta.draft render content/drafts/<slug>.md --format md
    ```

    All three land beside the draft: a draft at
    `content/drafts/<topic>/<name>.md` renders to
    `content/rendered/<topic>/<name>.{tex,pdf,md}`, so one topic
    directory holds the draft, its dossier and its renders. The `md`
    output is a numbered copy -- the same IEEE numbers as the PDF, for a
    reader who won't open one. The draft itself keeps its `[@citekey]`
    markers.

    Bare `python` plus `pandoc`/`pdflatex` on PATH -- no enrich group. If
    either reports `[missing-binary]` or `[error]`, print a one-line warning
    in chat with that message and continue anyway; a rendering failure never
    blocks presenting the `.md` draft.

    **Do not render an evidence sidecar, and this is a recorded answer
    rather than an omission.** The other four genres run
    `python -m chitragupta.draft evidence` here; a tutorial does not, and
    would produce nothing if it did.

    The reason is what a tutorial *is*. It cites only in the closing
    "Where to go next" section and never mid-lesson, so there is almost
    nothing for a sidecar to be about. More to the point, a quotation has
    no use in this genre: a learner at a keyboard needs the next command,
    not what a paper said about the idea behind it, and pausing a lesson
    to attribute a sentence to a source is precisely the digression this
    skill exists to refuse. So no `quote:` is captured, and a sidecar
    built from no quotes is no sidecar.

    If you find yourself wanting one, that is a signal you have written a
    textbook chapter -- see `textbook-chapter-writer`, whose reader is
    studying rather than doing.

16. **Record any steering.** If the user shaped this lesson in chat -- "use
    FastAPI, not Flask", "no Docker", "keep it under twenty minutes", "assume
    they've never opened a terminal" -- append it to the dossier's
    `steering.md`, dated. In this genre it is usually what fixed the single
    path in the first place, it is invisible in the prose, and it has nowhere
    else to live; a revision that doesn't know about it will undo it.

17. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it: what the check can and cannot see, and how to report what it
    finds. If the user wants any finding acted on, that is
    `draft-reviser`'s copy-edit mode, never an edit made here.
18. **Run the verbatim scan.** Before presenting, rebuild the section map
    and scan:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md
    ```

    The first command is not optional: a section map written earlier in
    this run describes a draft you have since edited.

    It matters here even though this genre barely cites: the prose
    between steps cites nothing, so it is exactly the text no per-citekey
    check can see. **A review aid, not a gate: it is never a condition of
    presenting.**

    Read `.claude/skills-common/references/verbatim-scan.md`
    now and follow it: what to show, what the scan could not check, and
    how to keep the report. Repairing a finding is `agenda-reviser`'s
    job, and only if the user asks.

19. **Stamp the draft fingerprint, then present.** Nothing edits the
    lesson's text after this point, so this is where `dossier status`
    records the baseline a later hand edit is compared against (#454):

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<slug>.md
    ```

    Then **present**, reporting: the draft path, the render outcome (or warning),
    and -- explicitly -- whether step 8 verification passed in full, in part,
    or not at all. Then say where the dossier is, that changes to this
    tutorial should go through `draft-reviser` rather than another run of
    this skill, and that `content/drafts/` and `content/dossiers/` are
    gitignored -- so `python -m chitragupta.draft dossier export <slug>` is how
    a lesson
    and its working state get backed up.

## Self-check before presenting

Every one of these should be answerable "yes":

- [ ] Can the learner see, at the top, what they will have at the end?
- [ ] Does every step start with a verb they perform?
- [ ] Does every step that produces output state what they should see?
- [ ] Is there exactly one path -- no options, no "if you prefer"?
- [ ] Are all values concrete rather than placeholders?
- [ ] Is every warning placed before its step?
- [ ] Has the whole thing been run end to end, and does it work?
- [ ] Is all substantive explanation in "Where to go next", not in the steps?
- [ ] Would a beginner who follows it exactly succeed, without judgement calls?

## Sources

The principles in this file are not original to this project. Full
citations, licences and a per-principle attribution table are in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#-sources-and-attribution).
In short: the genre model is Procida's Diátaxis, the audience and
clarity discipline is Google's Technical Writing courses and Last's
*Technical Writing Essentials*. All three are openly licensed and require
attribution.
