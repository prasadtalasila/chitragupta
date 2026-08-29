---
name: survey-writer
description: Drafts a topic-clustered literature survey / background section / "state of the art" from the synced corpus, with a comparison table and a gap analysis. Every claim is grounded in a citekey pulled from content/ledger.sqlite via chitragupta.retrieval -- never a fabricated one. Triggers when the user asks to write or draft a survey paper, literature review, background section, or related-work section for a given topic. To change or update a survey that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Must run `python -m chitragupta.draft gate` on its own output and only present the draft once it passes. Refuses (and tells the user to run `python -m chitragupta.corpus sync` first) if the ledger is empty.
tags: [survey, literature-review, citation]
---

# survey-writer

Genre-specific drafting agent for survey-style output. This is the "generative
drafting" half of the pipeline (the drafting layer) -- it runs on demand and its
output is reviewed by the user, unlike `python -m chitragupta.corpus sync` (the
corpus
layer: deterministic, safe to run unattended).

## Shared corpus layer (read, don't regenerate)

- `content/ledger.sqlite` -- per-citekey status, populated by `sync`
- `papers/bibliography.bib` (gitignored, per-host) -- the source of truth for citekeys/metadata;
  `sync` reads it, it is never regenerated
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

The draft is only half of what this run produces. The other half is the
judgment behind it -- the reader, the scope, the glossary, which
candidates were kept and **which were turned down and why** -- and it
belongs on disk, not in this conversation. Without it the next revision
has to re-retrieve and re-score the whole topic to change one paragraph.

`chitragupta/dossier/` owns that state, in Markdown, one directory per draft at
`content/dossiers/<the draft's path, minus its suffix>/`. Create it before
you search (step 0) and fill it in as you go -- not at the end, when what
you rejected has already fallen out of your context. `docs/DRAFT-ITERATION.md`
is the full design.

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
| --- | --- |
| User asks for a survey / lit review / background / related-work section on topic X | Invoke this skill |
| User asks for a thesis chapter | Use `thesis-chapter-writer` instead |
| User asks for a textbook chapter / lecture notes / worked examples | Use `textbook-chapter-writer` instead |
| User asks for a hands-on tutorial the reader follows at a keyboard | Use `tutorial-writer` instead |
| User asks to change a survey that **already exists** in `content/drafts/` | Use `draft-reviser` instead -- never re-run this skill to make a change |
| Ledger is empty, or nothing is `parsed` | Say so and stop. **Never** run `python -m chitragupta.corpus sync` yourself |

## Prose standards

Follow `docs/WRITING-STANDARDS.md` for the cross-genre rules: name the reader
before drafting, define terms once, state scope up front, active voice with a
named actor, ban "obviously/simply/just", and reread as the reader before
presenting. That file also carries the attribution for where these
principles come from -- Diátaxis, Last's *Technical Writing Essentials*, and
Google's Technical Writing courses, all CC-licensed and all requiring credit.
The genre-specific additions below layer on top of it.

### What a survey owes its reader

A survey's job is to **organize a field and locate the gaps in it** -- not to
teach the topic and not to advocate a position. Two failure directions:

- **Drifting into a textbook chapter.** You start explaining the concepts for
  a reader who doesn't know them. A survey's reader is a researcher entering
  the area; they need the map, not the lesson. If the user actually wants the
  lesson, `textbook-chapter-writer` exists -- say so.
- **Drifting into an argument.** You start defending one approach as correct.
  Weighing alternatives is the deliverable here; picking a winner is the
  thesis chapter's job, and doing it in a survey hides the disagreement the
  reader came for.

Unlike the tutorial genre, **alternatives and options are the point**. Never
collapse them for the sake of a cleaner narrative.

## Process

0. **Name the reader and the scope, and open the dossier.** Before
   searching, settle who this survey is for (a thesis reader? a grant
   reviewer? a paper's related-work section?) and what it will and won't
   cover. Write the scope statement into the draft's opening paragraph --
   including what's deliberately excluded, so a reader can tell an
   omission from an oversight. Then create the dossier and record the same
   decisions there:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<slug>.md --genre survey
   ```

   **Settle `<slug>` with the user before running that.** It is a path
   under `content/drafts/` and it may contain directories: "a survey for
   the `books/software-engineering` book" means
   `content/drafts/books/software-engineering/survey.md`, and a topic
   that will hold more than one genre wants
   `content/drafts/<topic>/survey.md` so they sit together. A flat
   `content/drafts/<slug>.md` is the default when neither applies. Ask
   rather than guess: the dossier (`content/dossiers/<slug>/`) and every
   render (`content/rendered/<the draft's own directory>/`) mirror
   whatever you pick, so moving the draft later means moving both.
   Fill in `scope.md`'s **Reader**, **Covers**, **Does not cover** and
   **Glossary** now, while you are deciding them. Settle the **dialect**
   with the reader in the same breath and write it to `scope.md`'s
   `language:` line, which ships unset: a survey for an IEEE submission is
   `en-US` and one for a European funder is usually `en-GB`, and a draft
   whose dialect nobody chose silently gets the model's own
   (`docs/WRITING-STANDARDS.md` §8). Read the acronym vocabulary too --
   the vendored floor at `assets/style/acronyms.toml`, plus the user's
   own file if `[style].acronyms` in `config.toml` points at one -- and
   use its recorded expansion at an acronym's first use rather than
   inventing one. `init` also stamps the
   corpus fingerprint, which is what lets a later revision tell whether
   the ledger has moved since.
1. **Retrieve broadly, over-fetching on purpose.** Break the requested topic
   into 2-4 sub-themes if it's broad. For each:

   ```bash
   python -m chitragupta.draft retrieve search "<sub-theme>" --k 15 --collection "<from scope.md>" --log content/drafts/<slug>.md
   ```

   Pull more candidates than you expect to use. This is a keyword-overlap
   ranker, not embeddings (unless `chitragupta/enrich/embed_index.py` has been built
   for this corpus) -- a high score means the query's words are in the
   document, not that it supports your claim.

   `--log` records the call's size in the dossier's `retrieval.md`, which is
   what makes the cost of a run measurable instead of estimated. Pass it on
   every call.
2. **Score every candidate yourself before it counts as evidence.** Read the
   full snippet -- 500 characters, sized so you have enough to judge and not
   just a title -- and decide: does this actually support a claim about the
   sub-theme, or did it just share vocabulary with the query? Keep only the
   ones that pass. This is the discipline PaperQA2 calls "gather evidence"
   (retrieve, then judge relevance, *then* write); the difference here is you
   judge inline rather than via a second API call.

   Where a snippet is not enough to decide on a source you are minded to
   keep, read more of that one document:

   ```bash
   python -m chitragupta.draft retrieve evidence "<sub-theme>" --citekey <key> --log content/drafts/<slug>.md
   ```

   Use it to be **more careful about something you are about to cite** -- not
   as a routine second pass over everything. `docs/REJECTION.md` explains why
   the reverse, a cheap screen used to reject faster, was tried and withdrawn:
   a wrong rejection is invisible, unrecoverable, and then entrenched in
   `rejected.md`, which later revisions are told to trust.

   **Record both outcomes in the dossier before you start drafting prose**,
   while the passages are still in front of you:
   - what survives, into `evidence.md` -- one `## \`citekey\`` block with a
     `relevance:` line (why it supports the claim), a `claim:` line -- what
     the source establishes, written in your own words -- and, only when a
     quotation is genuinely warranted, a `quote:` line (the verbatim span).
     `claim:` is the only field you may draft prose from later; `quote:` is
     usable in the draft solely inside quotation marks with an attribution.
     Write `claim:` from what you now understand the source to say, not by
     lightly editing the passage still on screen -- the two produce
     different sentences, and only the first is yours;
   - what doesn't, into `rejected.md` -- one table row per candidate:
     citekey, the query that surfaced it, and a few words on why it was
     turned down ("shares vocabulary only", "wrong domain", "superseded by
     X").

   The rejected list is the more valuable of the two and the easier to
   skip. It is what stops the next revision retrieving and re-judging the
   same twelve papers you just turned down -- the single most expensive
   piece of repeated work in this pipeline.

   Then run the advisory self-check, which flags a `claim:` that reads like
   its own `quote:` with the words moved:

   ```bash
   python -m chitragupta.draft dossier check-evidence content/drafts/<slug>.md
   ```

   A warning means re-read whether that claim is really your own reading of
   the source -- not a cue to keep rewording until the warning stops.
2a. **On a broad topic, put steps 1-2 behind a subagent.** Dispatch one
   `general-purpose` subagent per sub-theme, all in one message, each told to
   run the retrieve-and-score loop above and return **only** the kept-evidence
   packet plus the rejected list -- never the raw candidates.

   **The packet itself is `claim:`/`quote:` shaped, not a paste of what the
   subagent read.** Tell each subagent explicitly: write `claim:` in your own
   words, after you've judged the source, not by lightly editing the snippet
   or evidence window still on screen; capture `quote:` only where a
   quotation is genuinely warranted. A subagent that returns a `relevance:`
   line next to a pasted 500-character snippet or 600-character evidence
   window has satisfied "never the raw candidates" in name only -- the raw
   retrieval window still reaches your context, just wearing a `relevance:`
   label. The rule is on the *content* of what comes back, not only on which
   candidates are excluded.

   The reason is not parallelism. This is where the reliable token saving is:
   it costs nothing in retrieval quality, unlike trimming what you read.
   Anything you read yourself stays in
   your context and is re-sent on every later turn of the run; anything a
   subagent reads is paid for once. Four sub-themes retrieved inline is tens
   of thousands of characters you will then carry through clustering,
   drafting, gating and rendering, most of it material you already rejected.

   Skip this for a narrow topic with one sub-theme -- a subagent that returns
   almost everything it read saves nothing and costs a dispatch.
3. **Reformulate and re-search if a sub-theme comes up thin.** A single
   query wording is not the ceiling -- if scoring leaves you with little or
   nothing for a sub-theme, try synonyms, broader/narrower terms, or an
   adjacent concept, and search again. Do this a few times before concluding
   "thin coverage" is real rather than a wording problem. Only after genuine
   reformulation attempts should you report a sub-theme as thin -- and then
   say so explicitly rather than padding it with uncited claims.
4. **Cluster by judgment.** With a small corpus there's no BERTopic step;
   group the surviving (scored, kept) citekeys into themes yourself based on
   what the evidence actually says.
5. **Check for disagreement across sources before writing.** If two kept
   pieces of evidence conflict on a claim, don't silently pick one side --
   note the disagreement explicitly in the draft (which source says what).
   Silently resolving a real contradiction is a worse failure than leaving
   it visible.
6. **Draft**, in Markdown, using Pandoc-style citations (`[@citekey]`,
   `[@key1; @key2]`), citing only from your scored-evidence file:
   - Framing paragraph for the overall topic
   - One subsection per theme, citing the papers that actually support each claim
   - A comparison table: columns for approach/paper, citekey, core idea,
     stated limitations. **It carries a caption and an id, and the prose
     reads it** -- `docs/WRITING-STANDARDS.md` §13 is the contract, and
     this genre's table is the one it was written for:

     ```markdown
     | Starting point | Citekey | Core idea | Stated limitation |
     |---|---|---|---|
     | ... | ... | ... | ... |

     : Where to start when building a first twin.
     <!-- table: start-here -->
     ```

     Refer to it with an inline `<!-- tableref: start-here -->`, which
     the renderer expands to "Table 3" or `\ref{}` depending on the
     format -- never write the number yourself, and never write the word
     "Table" beside the marker. Introduce the table before it appears
     (what is compared, on what axis) and read a pattern off it
     afterwards (the outlier row, the column where everything agrees).
     A comparison nobody reads aloud is a table the reader has to
     interpret unaided.
   - A gap-analysis paragraph: what the retrieved corpus does *not* cover
     (including sub-themes that stayed thin after reformulation, and any
     cross-source disagreement from step 5)
   - **Every body paragraph closes on two or more citekeys wherever the
     evidence allows.** A paragraph fusing three papers cannot be a
     transcription of any one of them -- that is the point, and it is a
     stronger defence than paraphrasing harder. Organise a paragraph around
     what its sources agree and disagree about, rather than summarising them
     one after another. Where one paper genuinely is the only source for a
     point, keep it and say so with
     `<!-- single-source: why -->` on the line above or below, no blank line
     between. docs/WRITING-STANDARDS.md §11 is the rule; `python -m
     chitragupta.review synthesis <draft>` reports it.
7. **Never write a citekey you didn't get from a retrieval result.** If you
   want to cite something you know about from general knowledge but that isn't
   in the ledger, say so in prose to the user instead ("X is commonly discussed
   in this area but isn't in your synced library yet") -- do not invent a key
   for it.
8. **Map sections to citekeys.** Save the draft to
   `content/drafts/<slug>.md` first if you haven't already, then derive
   the map rather than writing it by hand:

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
   ```

   It joins each heading's line range to the citekeys cited inside it and
   writes the dossier's `sections.md`, so a later revision can tell which
   section owns a citation without reading the draft. Drop `--write` to
   see the table first. Read what it prints on stderr: a citekey cited
   above the first heading belongs to no section, and it says so rather
   than dropping it. Fix that in the draft (the claim wants a section) --
   don't hand-edit the table, which is regenerated from the draft.
9. **Add a figure only for what the table can't express.** Place it
   beside the relationship it captures, such as a taxonomy no
   comparison row shows -- `docs/WRITING-STANDARDS.md` §10's figures
   are rare here, the rarest of any genre in this pipeline, because the
   comparison table already carries that structural work. Absence is
   the default, not an oversight.

   On the rare occasion one is warranted, it is a **pair of files**, and
   §10 is the contract. This genre carries no inline form of either --
   the draft names the figure in a marker line of its own, with nothing
   beside it:

   ```html
   <!-- figure: figures/<name> -->
   ```

   Write both `content/drafts/<topic>/figures/<name>.tex` (the TikZ
   picture) and `content/drafts/<topic>/figures/<name>.txt` (the ASCII
   form, in §10's 7-bit alphabet). The renderer swaps the marker for the
   `.txt` contents in a fence on `--format md` (step 13) and every other
   non-LaTeX format, and for `\input{figures/<name>.tex}` on
   `--format tex`/`--format pdf`, which is what makes a survey figure
   usable in the paper this draft feeds. Six riders, each of which §10
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
   - **A topic directory is required.** If step 0 settled on a flat
     `content/drafts/<slug>.md`, move the draft and its dossier before
     adding a figure, or drop the figure -- and in this genre dropping
     it is usually the right answer. Figures under a flat draft land in
     `content/drafts/figures/`, shared with every other flat draft.
   - **Verify the TikZ compiles before keeping it.** Run
     `kpsewhich tikz.sty` first: if it is absent, write the ASCII inline
     in a fence instead, no pair and no marker, and say so in chat. If
     it is present, wrap `figures/<name>.tex` in a minimal
     `\documentclass{article}` + `\usepackage{tikz}` document and run
     `pdflatex` on it. A malformed figure fails the *whole* pdf render,
     not just the figure.
     If the figure uses `positioning`, `matrix`, `fit` or `tree`, put
     its `\usetikzlibrary` line at the top of `figures/<name>.tex` and
     copy that line into the probe too: the renderer's preamble loads
     `tikz` and no library, so a picture that relies on one and does not
     load it fails the whole render. `docs/TIKZ-STYLE.md` has the detail.
   - **No citekey inside either figure file.** Step 11's gate reads the
     draft and does not follow `\input`, so a citekey in a node label
     evades the one check this pipeline exists for. This is the genre
     most likely to want one -- a taxonomy figure naturally attributes
     each branch -- and it is exactly the wrong place for it: attribute
     in the prose or the comparison table, where the gate can see the
     key.
   - **The TikZ must be as original as the ASCII.** A taxonomy redrawn
     from a source survey's own figure is the same violation in
     different pixels, whichever notation it is drawn in.
   - **A caption, if this figure warrants one, goes in the draft, never
     in the figure file.** A caption line directly below the marker, no
     blank line between, and an inline `<!-- figureref: <name> -->`
     wherever prose points at it -- never write the word "Figure" or a
     number yourself; the renderer assigns both. Every figure needs a
     caption: since #421 an uncaptioned marker is reported as
     `chitragupta.FigureNoCaption` by this skill's own prose-check step.

   **Any quantity in the prose follows `docs/WRITING-STANDARDS.md` §12,
   not this step.** Write it as ASCII in a code span and give it a row in
   the dossier's `math.md`; `render` turns those into real mathematics for
   every format that reaches pandoc, and leaves the `.md` alone. A survey
   rarely has much, but a threshold or an error bound quoted from a source
   is a quantity, and a bare `` `k = 4` `` renders as typewriter text.

10. **Critique against the evidence packet, before gating.** Read the
    dossier's `evidence.md` -- the `claim:`/`quote:` blocks step 2
    recorded -- against the draft's own prose, section by section. List,
    in priority order, up to five places where the prose claims more
    than its `claim:` line supports, omits a kept `claim:` the draft
    never used, or drifts from the wording `claim:` actually recorded.
    This is one inline judgement call, not a subagent dispatch and not a
    deterministic check -- nothing in this pipeline scores this
    automatically.

    Take the baseline before touching anything:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md --write --json
    python -m chitragupta.draft style content/drafts/<slug>.md --json
    ```

    The first two are `agenda-reviser`'s own baseline discipline
    (uncapped, never `--limit`): they file
    `content/review/<topic>/<stem>.verbatim.json`, the file every edit
    below is rechecked against. The third's finding count -- not the
    file, `style` never writes one -- is the number you compare after
    each edit; note it down. Take all three fresh now rather than
    reusing anything on disk from an earlier run. If the scan's
    `tiers_not_run` is not empty, quote the reason: **genuine
    restatement is only detected where the embedding tier can run**, so
    the recheck below only ever compares what the tiers that did run
    can see.
    `style` reports only what WRITING-STANDARDS.md §9 marks
    decidable, and this step -- like every other -- is told to fix
    none of them: its count is a proxy for whether the edit
    introduced a new defect, not a work list to act on.

    Work the top of your list, **at most three items, one edit each, no
    retry and no second critique pass** once the three are done or the
    list runs out first. For each:

    1. Keep the pre-edit text of the section you are about to touch.
    2. Edit with `Edit`, inside that section only. Preserve the citekey;
       reword the claim to match what `claim:` says, or drop a sentence
       that overstates it. Never add a claim `evidence.md` does not
       already record, and never touch a `quote:` span -- a quotation is
       captured when the evidence is judged, never rewritten here.
    3. Check, all three required:

       ```bash
       python -m chitragupta.draft gate content/drafts/<slug>.md
       python -m chitragupta.review verbatim recheck content/drafts/<slug>.md \
           --baseline content/review/<topic>/<stem>.verbatim.json --json
       python -m chitragupta.draft style content/drafts/<slug>.md --json
       ```

       Accept the edit only if: the gate exits `OK`; the recheck's
       `objective_delta` is not positive; and the fresh `style` finding
       count -- read only as a number, since `style` reports what §9
       marks decidable and this step is told to fix none of them -- is
       no higher than the count noted before editing. Also check the
       edited section did not fall under 90% of its own pre-edit length
       -- a secondary sanity floor against a rewrite that deletes its
       way to a lower count, never itself a reason to accept one that
       the three checks above already failed.
    4. If any check fails, restore the text you kept in step 1 and move
       to the next item. Do not retry the same item.
    5. Log the attempt in the dossier's `revisions.md`: which gap, what
       you changed, and the outcome -- accepted or reverted. Never write
       any of this to `rejected.md`.

    If nothing on the list clears the bar, or the list was empty,
    continue to the gate exactly as if this step had not run -- the
    gate remains the only thing that blocks a draft, and this step is
    never a condition of presenting.
11. **Gate before presenting.** Save the draft as `content/drafts/<slug>.md`
    (this is the canonical, source-of-truth format), then run:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.md
    ```

    If it reports `FAIL`, fix the offending line(s) — either correct the citekey
    or remove the claim — and re-run until it reports `OK`. Never show the user
    a draft that hasn't passed.
12. **Build the References section.** Once the gate passes, generate it from
    exactly the gated citekeys rather than writing it by hand:

    ```bash
    python -m chitragupta.draft references content/drafts/<slug>.md
    ```

    Stdlib-only, like the citation gate — bare `python`, no venv. Writes
    numbered IEEE-style entries (`[1] J. Doe and R. Roe, "A Paper," *IEEE
    Trans. Testing*, vol. 3, pp. 1–9, 2024. \`doe_paper_2024\``) from
    `content/ledger.sqlite`, ordered by first appearance so the numbers
    match the rendered PDF's. Each entry keeps its citekey in a trailing
    code span, so a reader can trace every`[@citekey]` marker in the body
    back to an entry by that same key.

    Leave the body's inline citations as `[@citekey]` — do **not**
    hand-number them to `[1]`. The literal key is what the gate and the
    hook verify; pandoc assigns the numbers at render time.
13. **Render tex and pdf.** Once the gate passes and the references section
    is built, also render the other three formats:

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

    This needs only bare `python` plus `pandoc`/`pdflatex` on PATH — no
    enrich group required. If either command reports `[missing-binary]` or
    `[error]`, print a one-line warning in chat with that message and
    continue anyway — a rendering failure never blocks presenting the
    `.md` draft.

    **Then render the evidence sidecar**, in the same formats:

    ```bash
    python -m chitragupta.draft evidence content/drafts/<slug>.md --format pdf
    python -m chitragupta.draft evidence content/drafts/<slug>.md --format md
    ```

    **A survey emits one.** This genre is the natural fit: it is
    citation-dense, and its reader is mapping a field and wants to see
    what the sources actually said. The sidecar lands as
    `content/rendered/<topic>/<name>.evidence.{pdf,md}`, beside the
    render, and lists each cited source with the verbatim spans your
    step-2 `quote:` fields recorded, grouped by the section that leans on
    them.

    You do not write it and you cannot add to it: it is built from
    `evidence.md`, and it can only name citekeys the draft already cites.
    A draft whose blocks carry no `quote:` produces no sidecar and prints
    `no quoted evidence recorded` — that is the expected answer, not a
    failure, and it means you captured no quotation you meant to use.
    Never add a `quote:` after the fact to populate it; a quote is
    captured when the evidence is judged or not at all.
14. **Read it once as the reader** (`docs/WRITING-STANDARDS.md` §6). Check
    specifically for: terms used before they're defined, a theme heading that
    doesn't match what the subsection actually argues, a comparison-table row
    that repeats prose already above it, and any paragraph whose first
    sentence doesn't carry its point.
15. **Record any steering.** If the user shaped this draft in chat --
    "don't lead with tooling", "shorter", "drop the adoption angle" --
    append it to the dossier's `steering.md`, dated. It is invisible in
    the prose and has nowhere else to live; a revision that doesn't know
    about it will undo it.
16. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.md
    ```

    **It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable**
    — §2's defect markers, an acronym never expanded at first use, a
    glossary acronym whose expansion has drifted from the vocabulary,
    and §8's dialect against `scope.md`'s `language:` line. It says nothing
    about whether a paragraph leads with its point or whether a hedge
    carries information, and it cannot tell a quotation from the draft's own
    voice, so a marker inside a quoted passage reports and is correct as
    it stands.

    **Report every finding and fix none of them.** A finding is a place to
    look, not a defect: the first pass of this check over this
    repository's own docs kept 59 of its 73 marker hits on inspection. If
    the user wants any of them acted on, that is `draft-reviser`'s
    copy-edit mode, which reads the recorded dialect and logs one
    `revisions.md` entry — never an edit made here. Report the header
    lines too: `dialect: not checked` means nobody ever recorded one, so a
    short list is not a clean draft. A review aid, not a gate — it
    exits 0 whatever it finds, and a missing `vale` binary is a one-line
    warning that blocks nothing.
17. **Run the verbatim scan.** Before presenting, rebuild the section map
    and scan:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md
    ```

    The first command is not optional and not a repeat of step 8. The
    embedding tier compares each section against the citekeys that
    section's `sections.md` row records, so a table written ten steps ago
    describes a draft you have since edited. If it exits 1 for a missing
    dossier, say so and scan anyway.

    It reports wording the draft shares with **any** parsed source, cited or
    not — including a source the citing paragraph never names, and reuse in
    connective prose that cites nothing. **A review aid, not a gate: it
    exits 0 either way, it cannot block the draft, and it is never a
    condition of presenting.** Show what it found rather than summarising
    it away, and lead with the `long` and `short` buckets — a `quoted` run
    that also cites its source is a legitimate attributed quotation, so
    give those a count rather than a list.

    **Say what it did not check.** If `tiers_not_run` is not empty, quote
    each reason as the scan wrote it, and where the reason names a fix
    (`poetry install --with enrich`, `python -m chitragupta.enrich`) pass
    that on once. It sees verbatim and near-verbatim reuse only, and
    **genuine restatement is only detected where the embedding tier can
    run**, so a clean scan is not a clean bill of health
    (`docs/PLAGIARISM.md`). Repairing a finding is `agenda-reviser`'s job,
    and only if the user asks. If the user wants the
    finding kept, add `--write`: the report goes to `content/review/`,
    mirroring the draft's path, beside any provenance and coverage reports for
    the same draft.
18. Present the draft plus a one-paragraph summary of thin-coverage areas and
    any unresolved cross-source disagreement, and report the render outcome
    (paths to the `.tex`/`.pdf` if they succeeded, or the warning if not).
    Tell the user where the dossier is, that changes to this draft should go
    through `draft-reviser` rather than another run of this skill, and that
    `content/drafts/` and `content/dossiers/` are gitignored -- so `python -m
    chitragupta.draft dossier export <slug>` is how a draft and its working
    state get
    backed up.

## Sources

The prose standards this skill inherits are not original to this project.

Full citations, licences and a per-principle attribution table are in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#-sources-and-attribution).
All three works are openly licensed (CC-BY or CC-BY-SA) and require credit.

What bears on *this* genre specifically:

- **Last, *Technical Writing Essentials* (CC-BY 4.0)** -- audience and task
  analysis as a step before drafting, and the introduction checklist that
  asks for scope and the reader's assumed background. Step 0 is that
  checklist applied to a survey.
- **Google, *Technical Writing Courses* (CC-BY 4.0)** -- the curse of
  knowledge, defining each term once, and leading a paragraph with its
  point. The last matters more here than in any other genre, because a
  survey is read by skimming.
- **Procida, *Diátaxis* (CC-BY-SA 4.0)** -- the genre-separation principle
  behind "What a survey owes its reader". Note that a literature survey is
  **not** one of Diátaxis's four quadrants: Diátaxis describes software
  documentation, and its tutorial/how-to rules (single path, no options)
  would destroy a survey. Only the underlying insight transfers -- that a
  document trying to do two jobs does both badly.
