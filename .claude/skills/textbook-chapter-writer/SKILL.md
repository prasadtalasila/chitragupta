---
name: textbook-chapter-writer
description: Drafts an undergraduate textbook chapter -- learning objectives, motivation, worked examples, exercises -- for a student who is studying the topic, not yet doing it. Diataxis-wise this is explanation with worked application, not a tutorial; if the user wants a hands-on lesson the reader follows at a keyboard, use `tutorial-writer` instead. May cite grounding papers from the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) for motivation/background, but is not citation-dense; most content is original worked examples and exercises. Triggers when the user asks to draft a textbook chapter, lecture notes, course reader, teaching material, or worked-examples handout for students. To change one that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Any citations it does include must pass `python -m chitragupta.draft gate` before the draft is presented -- never a fabricated citekey.
tags: [textbook, teaching, undergraduate, pedagogy, explanation]
---

# textbook-chapter-writer

Genre-specific drafting agent for undergraduate textbook-chapter output. The
drafting layer (generative, on-demand, user-reviewed).

Its register is teaching, not persuading a reviewer, which is what separates
it from `survey-writer` and `thesis-chapter-writer`. Its reader is *studying*
-- sitting with the text, following an argument, working problems -- which is
what separates it from `tutorial-writer`, whose reader is at a keyboard
producing a working result. Both are teaching genres; they are not
interchangeable, and the most common failure is writing this genre when the
user asked for the other one. See "When to invoke".

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
|---|---|
| User asks for a textbook chapter / course reader / lecture notes / worked-examples handout | Invoke this skill |
| User asks for a hands-on lesson the reader follows step by step to a working result | Use `tutorial-writer` instead |
| User asks for a survey or lit review | Use `survey-writer` instead |
| User asks for a thesis chapter | Use `thesis-chapter-writer` instead |
| User asks to change a chapter that **already exists** in `content/drafts/` | Use `draft-reviser` instead -- never re-run this skill to make a change |

If the request is genuinely ambiguous ("write something teaching X"), ask one
question: *will the reader be reading this, or doing it?* Reading is this
skill; doing is `tutorial-writer`. Don't guess -- the two genres have opposite
rules about explanation, and a wrong guess produces a document that fails at
both.

## Prose standards

`docs/WRITING-STANDARDS.md` holds the cross-genre rules and all of them apply.
The genre-specific additions are below.

Where this genre departs from `tutorial-writer`: explanation is welcome here
and belongs here. Digression into *why* is a feature of a textbook chapter and
a defect in a tutorial.

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
   If you search the synced corpus for a motivating example, use the same
   retrieval discipline as the other skills: over-fetch

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
4. **Diversify sources within a section.** Citing at all stays optional
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
   non-LaTeX format, and `--format tex`/`--format pdf` (step 13) get
   `\input{figures/<name>.tex}`, so the printed chapter a student reads
   carries a real picture rather than monospace art. Five riders, each
   of which §10 explains:

   - **Commit to a layout metaphor before drawing, then check the
     result against §10's pre-flight defect list** (occlusion, chaotic
     routing, illegible type, non-rectangular protrusion, an
     overlong node, literal copying) before keeping the figure.
   - **A topic directory is required.** If step 0 settled on a flat
     `content/drafts/<slug>.md`, move the draft and its dossier before
     adding a figure, or drop the figure. Figures under a flat draft
     land in `content/drafts/figures/`, shared with every other flat
     draft.
   - **Verify the TikZ compiles before keeping it.** Run
     `kpsewhich tikz.sty` first: if it is absent, write the ASCII inline
     in a fence instead, no pair and no marker, and say so in chat. If
     it is present, wrap `figures/<name>.tex` in a minimal
     `\documentclass{article}` + `\usepackage{tikz}` document and run
     `pdflatex` on it. A malformed figure fails the *whole* pdf render,
     not just the figure -- and in this genre that render is the
     artifact a class actually reads.
   - **No citekey inside either figure file.** Step 11's gate reads the
     draft and does not follow `\input`, so a citekey in a node label
     evades the one check this pipeline exists for. Cite in the prose
     around the figure instead.
   - **The TikZ must be as original as the ASCII.** A picture redrawn
     from a source paper's figure is the same violation in different
     pixels -- which bites hardest here, where the temptation is to
     reproduce the textbook diagram everyone in the field already knows.

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
11. **Never write a citekey you didn't get from `search()`.** If you do include
    any citations, save the draft as `content/drafts/<slug>.md` and gate it:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.md
    ```

    Fix and re-run until `OK` before presenting. If there are no citations at
    all, the gate step is unnecessary -- just save to
    `content/drafts/<slug>.md`.
12. **Build the References section.** Once the gate passes, generate it from
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
13. **Render tex and pdf.** Once saved (and gated/referenced, if it has
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
14. **Record any steering.** If the user shaped this chapter in chat --
    "second-years, not first-years", "assume no probability", "more exercises
    and fewer worked examples", "drop the compiler example" -- append it to
    the dossier's `steering.md`, dated. It is invisible in the prose and has
    nowhere else to live; a revision that doesn't know about it will undo it,
    and pedagogical steering is the kind that undoes most quietly, because
    nothing in the finished chapter shows that an easier example was ever on
    the table.
15. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.md
    ```

    **It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable**
    -- §2's defect markers, an acronym never expanded at first use, a
    glossary acronym whose expansion has drifted from the vocabulary,
    and §8's dialect against `scope.md`'s `language:` line. It says nothing
    about whether a paragraph leads with its point or whether a hedge
    carries information, and it cannot tell a quotation from the chapter's own
    voice, so a marker inside a quoted passage reports and is correct as
    it stands. Read the acronym findings rather than skipping
    them: a student is precisely the outsider an unexpanded acronym is a
    defect for.

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
16. **Offer the verbatim scan.** Before presenting, offer this -- don't run
    it silently, and never make it a condition of presenting:

    ```bash
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md
    ```

    It reports wording the chapter shares with **any** parsed source, cited or
    not -- including a source the citing paragraph never names, and reuse in
    the connective prose between worked examples, which cites nothing. A review
    aid, not a gate: it exits 0 either way and cannot block the draft. Say what
    it misses when you offer it -- it sees verbatim and near-verbatim reuse
    only, and **genuine restatement is only detected where the embedding tier
    can run**, so a clean scan is not a clean bill of health
    (`docs/PLAGIARISM.md`). If the user wants the finding kept, add `--write`:
    the report goes to `content/review/`, mirroring the draft's path, beside
    any provenance and coverage reports for the same draft.
17. **Present the draft** plus a short note on what it assumes as prior
    knowledge, what it deliberately leaves out, and where a student is meant
    to go next -- and report the render outcome (paths to the `.tex`/`.pdf` if
    they succeeded, or the warning if not). Tell the user where the dossier
    is, that changes to this chapter should go through `draft-reviser` rather
    than another run of this skill, and that `content/drafts/` and
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
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#sources-and-attribution).
In short: the genre model is Procida's Diátaxis, the audience and
clarity discipline is Google's Technical Writing courses and Last's
*Technical Writing Essentials*. All three are openly licensed and require
attribution.
