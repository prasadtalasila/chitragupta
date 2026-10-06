---
name: textbook-chapter-writer-opencode
description: Drafts an undergraduate textbook chapter -- learning objectives, motivation, worked examples, exercises -- for a student who is studying the topic, not yet doing it. Diataxis-wise this is explanation with worked application, not a tutorial; if the user wants a hands-on lesson the reader follows at a keyboard, use `tutorial-writer-opencode` instead. May cite grounding papers from the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) for motivation/background, but is not citation-dense; most content is original worked examples and exercises. Triggers when the user asks to draft a textbook chapter, lecture notes, course reader, teaching material, or worked-examples handout for students. To change one that already exists in content/drafts/, use draft-reviser-opencode instead -- never re-run this skill to make a change. Any citations it does include must pass `python -m chitragupta.draft gate` before the draft is presented -- never a fabricated citekey.
tags: [textbook, teaching, undergraduate, pedagogy, explanation]
---

# textbook-chapter-writer-opencode

Genre-specific drafting agent for undergraduate textbook-chapter output. The
drafting layer (generative, on-demand, user-reviewed).

Its register is teaching, not persuading a reviewer, which is what separates
it from `survey-writer-opencode` and `thesis-chapter-writer-opencode`. Its
reader is *studying* -- sitting with the text, following an argument, working
problems -- which is what separates it from `tutorial-writer-opencode`, whose
reader is at a keyboard producing a working result. Both are teaching genres;
they are not interchangeable, and the most common failure is writing this genre
when the user asked for the other one. See "When to invoke".

## Shared corpus layer (read, don't regenerate)

- `content/ledger.sqlite` -- per-citekey status, populated by `sync`
- `content/parsed/<citekey>.txt` -- extracted PDF text, useful for pulling a
  real worked example or dataset description from a paper if relevant
- `chitragupta/retrieval.py` -- `search(query, k, snippet_chars)` if you want to
  ground the motivation section in the corpus (citing the result is still
  optional -- see step 3)

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

Citations here are optional, not the point. Don't force them in.

## Collection scoping (#195): draft from the shelf, not the library

At step 0, before any retrieval, check whether the library is sorted
into collections:

```bash
python -m chitragupta.corpus ledger --collections     # what exists, with counts
```

If it reports none, say nothing, ask nothing, record
`- collection: (whole corpus)` in `scope.md`'s header, and skip the rest
of this section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run. If retrieval inside the shelf comes back thin, the
honest fix to offer is a whole-corpus pass with `corpus-reviser-opencode`, which
is the one skill allowed to widen.

## The dossier: write down what produced the draft

The chapter is only half of what this run produces. The other half is the
teaching judgment behind it -- who the student is, what they are assumed to
know already, which definition each term was pinned to, which worked example
was chosen and **which candidates were tried and dropped, and why** -- and it
belongs on disk, not in this conversation. Without it the next revision has to
reconstruct the whole pedagogical design in order to change one exercise.

`chitragupta/dossier/` owns that state, in Markdown, one directory per draft at
`content/dossiers/<the draft's path, minus its suffix>/`. Create it before you
draft anything (step 0) and fill it in as you go -- not at the end, when the
example you abandoned has already fallen out of your context.
`docs/DRAFT-ITERATION.md` is the full design.

What the dossier is worth here is not what it is worth in the citation-dense
genres. This chapter is mostly original worked examples and exercises, so
`evidence.md` stays thin and may well be empty -- there is no long evidence
table to build, and padding one out is not the job. On the rare occasion a
source is worth recording, it gets the same `relevance:`/`claim:`/optional
`quote:` block the citation-dense genres use -- `claim:` in your own words,
`quote:` only where a quotation is genuinely warranted -- not a shortcut
`support:` line. The weight sits instead in
`scope.md` (the reader, the prior knowledge assumed, the covers /
does-not-cover line, the glossary that keeps notation stable across a
revision) and in `rejected.md`, which in this genre records **pedagogical**
rejects rather than bibliographic ones: the worked example that turned out too
advanced for the course level, the analogy that broke down one step in, the
exercise cut because it mapped to no objective. That file has no schema and
nothing parses it beyond backticked citekeys, so a row naming an example
rather than a paper is exactly what it is for.

None of this depends on citing anything. **A chapter that carries no citations
at all still gets a dossier** -- including one drafted after the user was asked
about an empty ledger and said to proceed uncited. The reader, the scope, the
glossary and the rejected examples are what a later revision needs, and they
exist whether or not a single `[@citekey]` does.

## When to invoke

| Situation | Action |
| --- | --- |
| User asks for a textbook chapter / course reader / lecture notes / worked-examples handout | Invoke this skill |
| User asks for a hands-on lesson the reader follows step by step to a working result | Use `tutorial-writer-opencode` instead |
| User asks for a survey or lit review | Use `survey-writer-opencode` instead |
| User asks for a thesis chapter | Use `thesis-chapter-writer-opencode` instead |
| User asks to change a chapter that **already exists** in `content/drafts/` | Use `draft-reviser-opencode` instead -- never re-run this skill to make a change |

If the request is genuinely ambiguous ("write something teaching X"), ask one
question: *will the reader be reading this, or doing it?* Reading is this
skill; doing is `tutorial-writer-opencode`. Don't guess -- the two genres have opposite
rules about explanation, and a wrong guess produces a document that fails at
both.

## Prose standards

`docs/WRITING-STANDARDS.md` holds the cross-genre rules and all of them apply.
The genre-specific additions are below.

Where this genre departs from `tutorial-writer-opencode`: explanation is welcome
here and belongs here. Digression into *why* is a feature of a textbook chapter
and a defect in a tutorial.

## Audience first

Before drafting anything, write down -- in the dossier's `scope.md` (step 0),
not necessarily in the chapter itself -- who the reader is and what they
already know. Everything downstream depends on it: what can go unexplained,
which prerequisites need a recap, how much notation is safe.

Then check yourself against the **curse of knowledge**: you know this material
and the student does not, and the specific danger is the step that feels too
obvious to state. Every term you introduce gets defined once, at first use, and
then used consistently -- never two names for the same concept, never the same
name for two concepts. If you catch yourself writing "obviously", "simply",
"just", or "of course", that sentence is a candidate for expansion, not a
candidate for the chapter.

## Process

0. **Name the reader and the scope, and open the dossier.** Before drafting
   and before any retrieval, settle who this chapter is for and what they
   already know ("Audience first" above), and what it will and won't cover.
   Then create the dossier and record those decisions there:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<slug>.md --genre textbook-chapter
   ```

   **Settle `<slug>` with the user before running that.** It is a path
   under `content/drafts/` and it may contain directories: "a book
   chapter in `books/software-engineering`" means
   `content/drafts/books/software-engineering/book-chapter.md`, and a
   topic that will hold more than one genre wants
   `content/drafts/<topic>/book-chapter.md` so they sit together. A flat
   `content/drafts/<slug>.md` is the default when neither applies. Ask
   rather than guess: the dossier (`content/dossiers/<slug>/`) and every
   render (`content/rendered/<the draft's own directory>/`) mirror
   whatever you pick, so moving the draft later means moving both.
   Fill in `scope.md`'s **Reader**, **Covers**, **Does not cover** and
   **Glossary** now, while you are deciding them -- the glossary especially,
   since it is what stops a later revision renaming a concept this chapter has
   already defined once, which is the failure a student notices fastest.
   Settle the **dialect** with the reader in the same breath and write it to
   `scope.md`'s `language:` line, which ships unset -- the course's own
   institution decides it, and a chapter whose dialect nobody chose silently
   gets the model's own (`docs/WRITING-STANDARDS.md` §8). Read the acronym
   vocabulary too -- the vendored floor at `assets/style/acronyms.toml`,
   plus the user's own file if `[style].acronyms` in `config.toml` points
   at one -- and use its recorded expansion the first time a term comes
   up rather than inventing one. Where
   a ledger is present, `init` also stamps the corpus fingerprint, which is
   what lets a later revision tell whether the ledger has moved since. Do this
   even if the chapter will carry no citations.
1. **Establish the learning objectives** first -- 3-5 concrete "by the end of
   this chapter, students will be able to..." statements, each with an
   observable verb (*derive*, *compare*, *implement*, *predict*), not
   *understand* or *appreciate*, which can't be assessed. Let everything else
   in the chapter serve these, and drop anything that serves none of them.
2. **State scope and prerequisites** near the top: what this chapter covers,
   what it deliberately doesn't, and what the reader is assumed to know
   already. A student who can't tell whether they're equipped for a chapter
   will either bounce off it or waste an hour discovering they were missing
   background.
3. **Motivation: establish the need before the mechanism.** A short
   section on why this topic
   matters, pitched at an undergraduate who has not read the literature. A
   chapter that presents mechanism without ever answering "why would anyone
   need this" produces students who can follow the steps and can't transfer
   them.
   If the dossier has an `outline.md` (`dossier init --outline`, or
   added later) with declared `queries:` for this section, run those
   verbatim instead of choosing your own search terms, logged `--origin
   declared`; a section that comes up thin still gets the reformulation
   below, logged `--origin extended` instead -- check first with
   `python -m chitragupta.draft dossier outline content/drafts/<slug>.md
   --check`. Citing stays optional here regardless, so a `claim:` block
   is a steer toward a specific assertion worth grounding if the corpus
   supports it, not an obligation the way it is in the citation-dense
   genres.

   Otherwise, if you search the synced corpus for a motivating example,
   use the same retrieval discipline as the other skills: over-fetch

   ```bash
   python -m chitragupta.draft retrieve search "<topic>" --k 15 --collection "<from scope.md>" --log content/drafts/<slug>.md
   ```

   `--log` records the query in the dossier's `retrieval.md`. **Pass it on
   every call**, even here where citing is optional -- it is what a later
   `dossier status` re-asks against the corpus to say which newly synced
   papers this chapter has never seen. Then read each 500-character snippet
   yourself rather than trusting the score, and reformulate and search again
   if the first pass turns up nothing genuinely useful -- don't settle for a
   weak match just because it was the top hit.
   **Whether to cite at all stays optional here, unlike the other skills.**
   Finding a good example doesn't obligate a citation -- cite it
   (`[@citekey]`) only if attributing it to a specific paper actually helps
   the student (e.g. "this is a real system described in [@citekey]");
   otherwise let it inform a well-chosen analogy without a reference. Don't
   manufacture a citation just to have one, and don't feel obligated to
   search at all if you already have a good example. Anything you do cite
   still must be a real citekey from a `search()` result -- never a
   fabricated one.
4. **Diversify sources within a section -- the unit here is the section,
   not the paragraph.** A multi-source *paragraph* is a distraction in a
   chapter whose job is explanation, so don't write one. The floor sits one
   level up: **a section that cites at all spans two or more citekeys, and
   its consecutive paragraphs do not rest on the same single citekey.**
   Spread alone is not enough -- three paragraphs on one paper followed by
   three on the next spans two sources and fuses neither, and every
   paragraph in it could still be a transcription. Interleave. Where one
   paper genuinely is the only source for a sustained point, keep it and say
   so with `<!-- single-source: why -->` on the line above or below, no blank
   line between. docs/WRITING-STANDARDS.md §11 is the rule; `python -m
   chitragupta.review synthesis <draft>` reports both the spread and the
   longest single-source run.

   The rest of this step is how you get there. Citing at all stays optional
   (step 3), but once a section ends up citing more than one paper, don't
   let a single citekey carry every paragraph in it just because it was the
   first good hit. When `search()` turns up more than one paper that
   plausibly supports a paragraph, actually compare them and prefer whichever
   adds a distinct angle, rather than defaulting to whichever key you already
   used a paragraph or two ago. Before reusing the same citekey a third time
   within one section, do one more `search()` pass specifically to check
   whether a different paper in the corpus covers the same point -- if it
   does, cite that one instead (or alongside it) so the section's point of
   view doesn't narrow to a single author's framing. It's fine for one source
   to genuinely be the only one that covers a niche point -- don't force in a
   second citation where none fits -- but repeated, unexamined reuse of the
   same key across a whole section is the failure mode to watch for, not
   deliberate reliance on a source that really is the best fit every time.
5. **Worked example(s), then faded ones.** Concrete, step-by-step, with
   enough detail a student could reproduce it, and with the *reasoning*
   visible at each step -- why this move, not just what the move is. A worked
   example that shows only the steps teaches imitation; one that shows the
   choice behind each step teaches the method.
   Prefer originally-constructed examples suited to the target course level
   over lifting a paper's (likely more advanced) treatment.
   Where the chapter has room for more than one, **fade the support**: the
   first example fully worked, the next with one step left to the reader, the
   last posed as a problem. Dropping a student straight from a fully worked
   example to an unaided exercise is the standard cliff, and fading is the
   standard fix.
6. **Exercises.** Include a mix of difficulty, and either solutions or hints
   -- state which. Each exercise should map to a stated learning objective
   (step 1); say which one, at least in your own notes, and cut any exercise
   that maps to none. Exercises should exercise the objectives, not just
   recall the reading. Note each cut in the dossier's `rejected.md` -- one row
   naming the exercise and why it went -- so a later revision doesn't
   reintroduce a problem you already judged and dropped. The same goes for a
   worked example you drafted and abandoned.

   Wherever a step above puts a table in the chapter -- a table of
   symbols, units or parameter values is the common case here -- **it
   gets a caption, an id, and a sentence that reads it**, per
   `docs/WRITING-STANDARDS.md` §13: a caption line under the table,
   `<!-- table: <id> -->` on the line below it, and an inline
   `<!-- tableref: <id> -->` wherever the prose points at it. Never write
   the number; the renderer assigns it, and a number typed into a chapter
   is wrong the moment that chapter is assembled into a book. A student
   meeting a table with no lead-in has to guess what to compare.

7. **Add a figure, if a worked example or concept earns one.** Place it
   beside the worked example (step 5) or concept it clarifies.
   `docs/WRITING-STANDARDS.md` §10's original ASCII diagrams suit this
   genre almost as well as they do in a tutorial -- less automatic,
   since this genre also leans on prose explanation to do that work, so
   most sections still won't need one. A figure you considered and
   dropped is a `rejected.md` row, the same as an abandoned worked
   example.

   A figure that stays is a **pair of files**, and §10 is the contract.
   This genre carries no inline form of either -- the draft names the
   figure in a marker line of its own, with nothing beside it:

   ```html
   <!-- figure: figures/<name> -->
   ```

   Write both `content/drafts/<topic>/figures/<name>.tex` (the TikZ
   picture) and `content/drafts/<topic>/figures/<name>.txt` (the ASCII
   form, in §10's 7-bit alphabet). The renderer swaps the marker for the
   `.txt` contents in a fence on `--format md` and every other
   non-LaTeX format, and `--format tex`/`--format pdf` (step 14) get
   `\input{figures/<name>.tex}`, so the printed chapter a student reads
   carries a real picture rather than monospace art.

   Hand the drawing itself to `figure-drawer-opencode`, and come back to this
   step when it returns: it owns the layout metaphor and scaffold,
   panel letters, the ASCII twin, the compile probe and the geometry
   review. What stays here must hold even if that skill is never
   loaded:

   - **A topic directory is required.** If step 0 settled on a flat
     `content/drafts/<slug>.md`, move the draft and its dossier before
     adding a figure, or drop the figure. Figures under a flat draft
     land in `content/drafts/figures/`, shared with every other flat
     draft.
   - **Check for TikZ, and that the figure compiles.** If
     `figure-drawer-opencode` was not loaded, run `kpsewhich tikz.sty`
     yourself: if it finds nothing, write the ASCII inline in
     a fence instead, no pair and no marker, and say so in
     chat. A figure you keep compiles on its own first: a malformed
     one fails the whole pdf render, not just the figure.
   - **No citekey inside either figure file.** Step 12's gate reads the
     draft and does not follow `\input`, so a citekey in a node label
     evades the one check this pipeline exists for. Cite in the prose
     around the figure instead.
   - **Nothing redrawn from a source.**
     A diagram redrawn from a source paper's figure is the same
     violation in different pixels -- which bites hardest here, where the
     temptation is to reproduce the textbook diagram everyone in the field
     already knows.
   - **A caption, if the figure earns one, goes in the draft, never in
     the figure file.** A caption line directly below the marker, no
     blank line between, and an inline `<!-- figureref: <name> -->`
     wherever the prose points at it -- never write the word "Figure" or
     a number; the renderer assigns both, the same contract §13 gives
     the table above. Every figure needs a caption -- an uncaptioned
     marker is reported as `chitragupta.FigureNoCaption` (#421).

   **Equations follow `docs/WRITING-STANDARDS.md` §12, not this step, and
   this genre has more of them than any other here.** A worked example is
   mostly quantities. Write each as ASCII in a code span -- `` `k = 4` ``,
   `` `m = a * W + b` `` -- and give it a row in the dossier's `math.md`;
   a displayed equation is an untagged fence under a `<!-- math -->`
   marker. `render` turns those into real mathematics for the pdf a
   student reads, and leaves the `.md` legible. A quantity in a bare code
   span with no row renders as typewriter text beside the equation that
   defines it, which is the exact thing §12 exists to stop.

   **This genre also has more of §12's numbered equations than any
   other, because it has more derivations.** A worked example that
   chains several displayed steps to a result numbers only the last
   one -- the one the student is meant to cite back to, not every
   intermediate line -- with an `<!-- equation: <id> -->` marker directly
   above it and an inline `<!-- equationref: <id> -->` in the sentence that
   names it, most often in "Close the loop" or a later example that
   reuses the result. A standalone definition (not part of a chain) is
   numbered the same way if the chapter names it again later; a
   quantity that appears once and is never pointed back at stays
   unnumbered like any other. Never write "Equation 3" yourself -- the
   renderer assigns the number, the same contract §13 gives the table
   above -- and an id left with no referencing sentence is
   `chitragupta.EquationUnreferenced`, this skill's own prose-check
   step.

8. **Close the loop.** End with a short summary of what the chapter
   established, tied back to the objectives it opened with, plus pointers to
   where a student who wants more should go next -- including, where it fits,
   the corpus papers you consulted but didn't need to cite inline.
9. **Read it once as the student.** Before presenting, reread the draft as
   the reader defined in "Audience first" -- not as yourself. Flag anywhere a
   term arrives undefined, a step skips reasoning, or notation changes
   meaning mid-chapter. This pass catches more real problems than any other
   single step here.
10. **Map the chapter's sections.** Once the draft is saved, derive the
    dossier's `sections.md` rather than writing it by hand:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    ```

    so a later revision can find the section that owns a change without
    reading the whole chapter. It skips fenced code, so a `# Step 1`
    comment inside an example listing is neither mistaken for a heading
    nor read as a citation. A chapter with no citations still gets this
    map -- every row comes out with an empty citekey cell, and the outline
    is what a reviser navigates by either way.
11. **Critique against the evidence packet, before gating.** Skip this
    entirely if the chapter has no citations at all -- same as the gate
    step below. Otherwise, read the dossier's `evidence.md` -- the
    `claim:`/`quote:` blocks recorded when a source was judged -- against
    the draft's own prose, section by section. List, in priority order,
    up to five places where the prose claims more than its `claim:` line
    supports, omits a kept `claim:` the draft never used, or drifts from
    the wording `claim:` actually recorded. This is one inline judgement
    call, not a subagent dispatch and not a deterministic check --
    nothing in this pipeline scores this automatically.

    This step is never a condition of presenting. Read
    `.claude/skills-common/references/critique.md` now and follow it, with
    `content/drafts/<slug>.md` as `<draft>`. Make each edit with `edit`,
    inside that section only. If nothing on the list clears the bar, or
    the list was empty, continue to the gate.
12. **Never write a citekey you didn't get from `search()`.** If you do include
    any citations, save the draft as `content/drafts/<slug>.md` and gate it:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.md
    ```

    Fix and re-run until `OK` before presenting. If there are no citations at
    all, the gate step is unnecessary -- just save to
    `content/drafts/<slug>.md`.
13. **Build the References section.** Once the gate passes, generate it from
    exactly the gated citekeys rather than writing it by hand:

    ```bash
    python -m chitragupta.draft references content/drafts/<slug>.md
    ```

    Stdlib-only, like the citation gate -- bare `python`, no venv. Writes
    numbered IEEE-style entries from `content/ledger.sqlite`, ordered by
    first appearance so the numbers match the rendered PDF's, each keeping
    its citekey in a trailing code span so a reader can trace every
    `[@citekey]` marker in the body back to an entry by that same key.
    Leave the body's inline citations as `[@citekey]` -- do **not**
    hand-number them to `[1]`; pandoc assigns the numbers at render time,
    and the literal key is what the gate verifies. If this chapter's
    other section headings are manually numbered (e.g. `## 6. Challenges and
    Open Issues`), pass `--heading "N. References"` with the next number so
    the new section matches the draft's own numbering instead of the bare
    `## References` default. Skip this step entirely if there are no
    citations at all -- same as the gate step.
14. **Render tex and pdf.** Once saved (and gated/referenced, if it has
    citations), also render the other three formats:

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

    This needs only bare `python` plus `pandoc`/`pdflatex` on PATH -- no
    enrich group required. If either command reports `[missing-binary]` or
    `[error]`, print a one-line warning in chat with that message and
    continue anyway -- a rendering failure never blocks presenting the
    `.md` draft.

    **Then render the evidence sidecar** -- and expect it to be thin, or
    absent:

    ```bash
    python -m chitragupta.draft evidence content/drafts/<slug>.md --format pdf
    ```

    **This chapter emits one when it has anything to show, which is
    often not.** That follows from what this genre already is rather than
    from a separate decision: it is deliberately not citation-dense, most
    of it is original worked examples and exercises, and its `evidence.md`
    is kept thin by design. Sources here are cited for motivation and
    background, and motivation is the last place a verbatim quotation
    earns its keep -- so most chapters capture no `quote:` at all and the
    command prints `no quoted evidence recorded`.

    **That is the right outcome, not a gap to fill.** Do not go back and
    add a `quote:` so that a sidecar appears. Where a chapter does quote
    a source deliberately -- a definition worth giving in its originator's
    exact words -- the sidecar is where a student can see it attributed.
15. **Record any steering.** If the user shaped this chapter in chat --
    "second-years, not first-years", "assume no probability", "more exercises
    and fewer worked examples", "drop the compiler example" -- append it to
    the dossier's `steering.md`, dated. It is invisible in the prose and has
    nowhere else to live; a revision that doesn't know about it will undo it,
    and pedagogical steering is the kind that undoes most quietly, because
    nothing in the finished chapter shows that an easier example was ever on
    the table.
16. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it: what the check can and cannot see, and how to report what it
    finds. If the user wants any finding acted on, that is
    `draft-reviser-opencode`'s copy-edit mode, never an edit made here.

    Read the acronym findings rather than skipping them: a student is
    precisely the outsider an unexpanded acronym is a defect for.
17. **Run the verbatim scan.** Before presenting, rebuild the section map
    and scan:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md
    ```

    The first command is not optional: a section map written earlier in
    this run describes a draft you have since edited.

    It matters most in the connective prose between worked examples,
    which cites nothing. **A review aid, not a gate: it is never a
    condition of presenting.**

    Read `.claude/skills-common/references/verbatim-scan.md`
    now and follow it: what to show, what the scan could not check, and
    how to keep the report. Repairing a finding is `agenda-reviser-opencode`'s
    job, and only if the user asks.
18. **Stamp the draft fingerprint, then present.** Nothing edits the
    chapter's text after this point, so this is where `dossier status`
    records the baseline a later hand edit is compared against (#454):

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<slug>.md
    ```

    Then **present the draft** plus a short note on what it assumes as prior
    knowledge, what it deliberately leaves out, and where a student is meant
    to go next -- and report the render outcome (paths to the `.tex`/`.pdf` if
    they succeeded, or the warning if not). Tell the user where the dossier
    is, that changes to this chapter should go through `draft-reviser-opencode`
    rather than another run of this skill, and that `content/drafts/` and
    `content/dossiers/` are gitignored -- so `python -m chitragupta.draft dossier
    export <slug>` is how a draft and its working state get backed up.

## House style for this genre

Beyond `docs/WRITING-STANDARDS.md` §4:

- Prefer a concrete instance over an abstract statement of the general case,
  then generalize from it -- students build the general rule from instances,
  not the reverse. This matters more here than in any other genre.
- Notation is introduced once, with a worked instance beside it, and never
  silently reused with a changed meaning in a later section.

## Sources

The principles in this file are not original to this project. Full
citations, licences and a per-principle attribution table are in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#-sources-and-attribution).
In short: the genre model is Procida's Diátaxis, the audience and
clarity discipline is Google's Technical Writing courses and Last's
*Technical Writing Essentials*. All three are openly licensed and require
attribution.
