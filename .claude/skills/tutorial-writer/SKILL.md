---
name: tutorial-writer
description: Drafts a Diataxis-style tutorial -- a hands-on lesson that a learner follows at a keyboard, start to finish, to a working result they can see. Concrete, single-path, minimally explained, and verified to actually run before it is presented. Not a textbook chapter and not a how-to guide; if the reader is studying rather than doing, use `textbook-chapter-writer`, and if they already know what they want and just need the steps, say so rather than writing a tutorial. May cite the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) but only in a closing "Where to go next" section, never mid-lesson. Triggers when the user asks for a tutorial, a hands-on lesson, a getting-started walkthrough, a lab exercise, or a "teach someone X by having them build Y" document. To change a tutorial that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Any citation must pass `python -m chitragupta.draft gate` before the draft is presented -- never a fabricated citekey.
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
   Same retrieval discipline as the other skills if you do search:
   over-fetch

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
   -- advisory, flags a `claim:` that reads like its `quote:` reworded; a
   warning is a cue to re-read your own judgment, not to reword until it
   stops.

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
   genre more naturally than any other in this pipeline. Most tutorials
   still don't need one: if nothing in the path is clearer as a diagram
   than as text, move on.

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
   non-LaTeX format, and `--format tex`/`--format pdf` (step 14) get
   `\input{figures/<name>.tex}`, so a learner reading the PDF gets a
   real picture instead of monospace art. Five riders, each of which §10
   explains:

   - **Commit to a layout metaphor before drawing, and start from the
     scaffold for it rather than from an empty picture.** `assets/tikz/`
     holds one known-good file per metaphor `docs/TIKZ-STYLE.md` names
     -- pipeline, map, layered stack, control loop, branching tree,
     hub-and-spoke. Copy the one that fits and re-label it. Each places
     its nodes relative to one another, which is the property worth
     keeping: a figure laid out in hand-computed millimetres re-opens
     every adjacency in it the moment any label changes length. Then
     check the result against that document's pre-flight defect list
     (occlusion, chaotic routing, illegible type, non-rectangular
     protrusion, an overlong node, literal copying) before keeping the
     figure.
   - **Panels get lettered sub-captions, in both forms.** A figure with
     more than one panel is still one figure and one marker; each panel
     carries a `(<letter>) <short title>` node -- `(a)` for the first
     panel in reading order, `(b)` for the second, on through the
     alphabet -- and
     the same letters appear in the `.txt` -- `docx`, `html` and `md`
     render only that form, so letters left out of it are letters the
     reader never sees. `docs/TIKZ-STYLE.md` has the worked example, the
     row-wrapping rule for a row that stops fitting, and why the
     `subcaption` package is not the answer.
   - **A topic directory is required.** If step 1 settled on a flat
     `content/drafts/<slug>.md`, move the draft and its dossier before
     adding a figure, or skip the figure. Figures under a flat draft
     land in `content/drafts/figures/`, shared with every other flat
     draft.
   - **Verify the TikZ compiles before keeping it** -- the same
     "actually run it" discipline step 8 applies to the lesson itself.
     Run `kpsewhich tikz.sty` first: if it is absent, write the ASCII
     inline in a fence instead, no pair and no marker, and say so in
     chat. If it is present, wrap `figures/<name>.tex` in a minimal
     `\documentclass{article}` + `\usepackage{tikz}` document and run
     `pdflatex` on it. A malformed figure fails the *whole* pdf render,
     not just the figure.
     If the figure uses `positioning`, `matrix`, `fit` or `tree`, put
     its `\usetikzlibrary` line at the top of `figures/<name>.tex` and
     copy that line into the probe too: the renderer's preamble loads
     `tikz` and no library, so a picture that relies on one and does not
     load it fails the whole render. `docs/TIKZ-STYLE.md` has the detail.
   - **No citekey inside either figure file.** Step 12's gate reads the
     draft and does not follow `\input`, so a citekey in a node label
     evades the one check this pipeline exists for. This genre's
     citations belong in "Where to go next" anyway.
   - **The TikZ must be as original as the ASCII.** A picture redrawn
     from a source paper's figure is the same violation in different
     pixels.

   **A quantity in the prose follows `docs/WRITING-STANDARDS.md` §12.**
   Rare in this genre and easy to get wrong when it appears: a value the
   learner *types* stays a plain code span, because it is literal input,
   while a value the lesson *reasons about* is a quantity and needs a row
   in the dossier's `math.md`. `` `DRY_THRESHOLD = 35.0` `` in a config
   file is code; "the threshold is `k = 4` reading units per hour" is
   mathematics. When in doubt here, prefer code -- a tutorial's job is
   the keyboard, not the derivation.

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

12. **Gate any citations.** Save the draft as `content/drafts/<slug>.md`. If
    it contains any `[@citekey]`, run:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.md
    ```

    Fix and re-run until `OK` before presenting. If there are no citations at
    all, the gate step is unnecessary -- just save the file.
    Note: the gate blanks fenced code, inline code spans and LaTeX verbatim
    environments before extracting citekeys, so `@dataclass`, `@property` and
    similar tokens in your worked code are not false positives. Don't mangle
    real teaching code to appease it.

13. **Build the References section**, only if the draft cites anything:

    ```bash
    python -m chitragupta.draft references content/drafts/<slug>.md --heading "Further reading"
    ```

    Stdlib-only, bare `python`, no venv. Entries are numbered IEEE-style;
    leave the inline citations as `[@citekey]` rather than hand-numbering
    them. `--heading "Further reading"` suits this genre better than the
    bare `## References` default; use whatever heading the draft's own
    "Where to go next" section flows into. Skip entirely if there are no
    citations.

    One consequence of a non-default heading: `render_output` only strips
    a section headed `References` before handing the draft to pandoc, so a
    `Further reading` list stays in the rendered `.tex`/`.pdf` *and*
    citeproc appends its own numbered bibliography below it. That is
    usually fine here -- the curated list is the point of the section, and
    the tutorial genre cites lightly. Pass the default heading instead if
    a single bibliography matters more for a given tutorial.

14. **Render tex, pdf, and numbered md.**

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

15. **Record any steering.** If the user shaped this lesson in chat -- "use
    FastAPI, not Flask", "no Docker", "keep it under twenty minutes", "assume
    they've never opened a terminal" -- append it to the dossier's
    `steering.md`, dated. In this genre it is usually what fixed the single
    path in the first place, it is invisible in the prose, and it has nowhere
    else to live; a revision that doesn't know about it will undo it.

16. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.md
    ```

    **It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable**
    -- §2's defect markers, an acronym never expanded at first use, a
    glossary acronym whose expansion has drifted from the vocabulary,
    and §8's dialect against `scope.md`'s `language:` line. It says nothing
    about whether a paragraph leads with its point or whether a hedge
    carries information, and it cannot tell a quotation from the lesson's own
    voice, so a marker inside a quoted passage reports and is correct as
    it stands. Fenced code is skipped, so your commands and
    their expected output are not scanned.

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
17. **Run the verbatim scan.** Before presenting, rebuild the section map
    and scan:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md
    ```

    The first command is not optional. The embedding tier compares each
    section against the citekeys that section's `sections.md` row records,
    so a table written earlier in this run describes a draft you have
    since edited. If it exits 1 for a missing dossier, say so and scan
    anyway.

    It reports wording the tutorial shares with **any** parsed source, cited or
    not. That matters here even though this genre barely cites: the prose
    between steps cites nothing, so it is exactly the text no per-citekey check
    can see. **A review aid, not a gate: it exits 0 either way, it cannot
    block the draft, and it is never a condition of presenting.** It skips
    fenced code, so your commands and file contents won't light it up. Show
    what it found rather than summarising it away, and lead with the `long`
    and `short` buckets -- a `quoted` run that also cites its source is a
    legitimate attributed quotation, so give those a count rather than a
    list.

    **Say what it did not check.** If `tiers_not_run` is not empty, quote
    each reason as the scan wrote it, and where the reason names a fix
    (`poetry install --with enrich`, `python -m chitragupta.enrich`) pass
    that on once. It sees verbatim and near-verbatim reuse only, and
    **genuine restatement is only detected where the embedding tier can
    run**, so a clean scan is not a clean bill of health
    (`docs/PLAGIARISM.md`). Repairing a finding is `overlap-reviser`'s job,
    and only if the user asks. If the user wants the finding kept, add
    `--write`: the report goes to `content/review/`, mirroring the draft's
    path, beside any provenance and coverage reports for the same draft.

18. **Present**, reporting: the draft path, the render outcome (or warning),
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
