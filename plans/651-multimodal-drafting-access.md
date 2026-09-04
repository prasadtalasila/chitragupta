# 🖼 Reaching the drafting stage with tables, equations and figures

Status: **done.** Written 2026-09-04; shipped the same day in PR
[#655](https://github.com/prasadtalasila/chitragupta/pull/655) (#651),
[#656](https://github.com/prasadtalasila/chitragupta/pull/656) (#652),
[#657](https://github.com/prasadtalasila/chitragupta/pull/657) (#653) and
[#658](https://github.com/prasadtalasila/chitragupta/pull/658) (#654), in
the order this file predicted.

**What changed on the way**, since a plan that no longer matches what
shipped is worse than no plan:

- **Figures carry `bbox` only, not also pixel `dimensions`.** The record
  shape below promised both. The real-PDF smoke run showed the pixel
  figure disagreeing with the written PNG by 1-2px on 7 of one paper's 17
  figures: pdfium sizes a crop from page-edge insets,
  `round((page_w - left - right) * scale)`, which is not float-equal to
  `round((r - l) * scale)`. Matching it exactly would have meant
  threading page geometry from the render path into the record path to
  publish a number the caller can derive. The box is exact and
  scale-independent; pixels are it times `docling_image_scale`.
- **The junk floor is in page points, not pixels.** Stated below as
  "tiny (<200px on a side)", which was how it was measured but not how it
  could be implemented: a pixel floor reclassifies the whole corpus when
  someone edits `docling_image_scale`. It ships as 33pt -- that same
  200px divided by the 6.0 it was measured at.
- **The table fix needed a second half nobody predicted.** Widening the
  window was not enough: `_clean_window` normalises whitespace, which
  collapses every row of a table onto one line. `retrieval_tables.py`
  renders a block line by line for that reason, and exists as its own
  module because `retrieval.py` was at 249 of the 250 code-line ceiling.
- **#651 shipped with a hole that #652 closed.** `isolated_config` pins
  `PARSER_OCR` and the new `PARSER_FORMULAS` was not added beside it, so
  a test asserting the default passed or failed by whether the host had
  turned the key on. CI copies `config.toml.example` and could not have
  caught it.
- **The rung-1 masking resolved itself, as predicted.** The corpus
  re-parse took `formula-not-decoded` from 148 documents to **0**, put
  `$$` math in **151**, and took corpus-layer sidecars carrying `formula`
  records from 0 to **156** (`table` records held, 324 -> 330).

Written 2026-09-04, for issues
[#651](https://github.com/prasadtalasila/chitragupta/issues/651),
[#652](https://github.com/prasadtalasila/chitragupta/issues/652),
[#653](https://github.com/prasadtalasila/chitragupta/issues/653) and
[#654](https://github.com/prasadtalasila/chitragupta/issues/654).

**Written for** the implementer of those four issues, in that order.
[#627](https://github.com/prasadtalasila/chitragupta/issues/627)'s
multimodal ingest landed on the *review* side of the corpus/drafting
seam. This says what it takes to land it on the drafting side too, and
why three of the four modalities need almost no new architecture.

**Assumed**: the corpus layer as it stands after #632 and #649 --
`chitragupta/pdf_text/_converter.py` builds the converter that writes
`content/parsed/*.txt`, `chitragupta/enrich/docling_parse.py` builds a
second one under its own settings, and `chitragupta/passages.py`'s
`source_passages()` prefers the enrichment sidecar (rung 1) over the
corpus one (rung 2).

**Not covered here**: video, which this pipeline does not support in any
form and which nothing below adds; caption pairing for source figures
that carry none; vision-model captioning, which #627 measured and
rejected and which nothing here revisits; and any change to how a
*draft's own* TikZ figures are numbered or panelled -- `plans/396` and
`plans/411` own that, and were read before writing this to confirm they
do not overlap.

## 🔑 The one fact the whole design turns on

> `retrieval.search()` and `retrieval.evidence()` read exactly one
> artefact: the ledger's `parsed_path`, i.e. `content/parsed/<citekey>.txt`.

That is the whole drafting-side surface. `retrieval.py`'s own docstring
states it twice, and says it never reads `content/docling/`. Every
consumer of `passages.source_passages()` is under `review/` or
`overlap_segments.py` -- none is a drafting skill.

So anything that reaches a draft either **lives in that text file**, or
**needs a route that does not exist yet**. That single test sorts the
four modalities into three genuinely different jobs, and it is why the
figure work is much larger than the equation work despite sounding
smaller.

## 📊 What is actually on disk, measured before proposing anything

Measured on the real 497-PDF corpus at `/workspace/content`, 2026-09-04.

| Modality | Reaches the draft today | Evidence |
| --- | --- | --- |
| **Passages** | Yes | The file *is* prose |
| **Tables** | Yes, and did before #632 | Pipe tables in **274/497** parsed texts |
| **Equations** | **No** | `formula-not-decoded` in **148/497**; decoded LaTeX in **0/497** |
| **Figures** | **No route exists** | 8,769 crops, 497 `figures.json`, **zero consumers** |

Three findings shaped the plan, and none was predictable from the code:

1. **`docling_formulas = true` is set in `config.toml` and does nothing
   for drafting.** #632 wired `do_formula_enrichment` into the
   *enrichment* converter only. The corpus converter -- the one whose
   output retrieval indexes -- never sets it.
2. **The enrichment artefacts predate the feature.** Everything in
   `content/docling/` is dated 2026-08-12; #632 landed 2026-09-03.
   `content/docling/*.passages.json` therefore holds **zero** `table` and
   **zero** `formula` records, and 149 `.md` files still carry the
   undecoded marker.
3. **The new table records are masked on the review side.** The *corpus*
   layer was re-parsed, so `content/parsed/*.passages.json` does carry
   `table` records in **324/497** documents -- but `source_passages()`
   prefers rung 1, the stale enrichment sidecar. For those documents the
   review aids read August's passages and never see the table units at
   all. A re-parse of the enrichment layer resolves it; no code change
   is needed, and none is proposed.

`content/docling_cache.json` reads `{version: 2, images: false, ocr: false}`
against a code `_CACHE_VERSION` of 3, so that re-parse is pending
regardless of this work. Two consequences are load-bearing below: the
figure filter costs no extra run, and the file's own mtime (2026-09-04,
59 bytes, `images: false` while `config.toml` says `true`) is the
signature of an enrichment run started from a directory with no
`config.toml`, which rewrote the header under defaults.

## 🧭 The four changes

### 1. Equations: a toggle on the right converter (#651)

The smallest change with the largest reach, because **equations are
text**. A decoded formula is LaTeX; LaTeX lands in the file BM25 already
indexes. No new route, no new artefact, no genre-skill change.

`pdf_text/_converter.py`'s `_docling_converter()` gains
`opts.do_formula_enrichment`, driven by a **new `[parser].formulas` key**
that mirrors `[parser].ocr` exactly.

A new key rather than reusing `[enrich].docling_formulas`, which would
also work and needs no config surface: the corpus layer reading an
`[enrich]` setting crosses the boundary
[ARCHITECTURE.md](../docs/ARCHITECTURE.md) draws, and the corpus layer's
parse is meaningful to a user who never runs the enrichment layer at
all. `[enrich].docling_formulas` stays and keeps driving the enrichment
parse; the two toggles are independent because the two parses are.

**The one trap.** `_DOCLING_CONVERTER_KEY` is keyed on
`(PARSER_OCR, threads, device, PARSER_DOCUMENT_TIMEOUT)`, and that
module's comment says why: keying on "was one built already" silently
serves a converter built under the old setting when a user edits
`config.toml` mid-session. A new toggle that is not added to the key
reintroduces precisely the bug the key exists to prevent. It goes in the
key, with a test that flipping it yields a different converter.

### 2. Tables: a window that respects the block (#652)

Nothing at ingest. Tables are already indexed; what fails is that a
500-character snippet cuts through a row that is itself ~450 characters
wide, so the draft receives a fragment with no header row -- the one part
that says what the columns mean.

When a snippet's window falls inside a contiguous run of lines beginning
with `|`, it extends to the block's bounds instead of the character
budget, subject to a cap so a 200-row table cannot swallow a result.

Self-activating, and that is the point. The alternative -- a `--table`
flag -- only helps a caller who already knew a table was there, which is
not the case that hurts; and every genre skill would need teaching to
pass it, with the ones that forget getting today's behaviour silently.

Two contracts to settle while implementing: what a table larger than the
cap does (truncate keeping the header row, never fall back to a mid-row
cut), and whether the block scan applies to `search` snippets,
`evidence` windows, or both. A hit outside a table must return
byte-identical output to today.

### 3. Figures: an index that means "figures" (#653)

`_figure_records` currently records every picture docling reports. On
this corpus that is 8,769 records, of which:

| | no caption | captioned |
| --- | --- | --- |
| **tiny** (<200px on a side) | **3,373 -- 38.5%** | 558 -- 6.4% |
| **large** | 1,039 -- 11.8% | **3,799 -- 43.3%** |

At `docling_image_scale = 6.0` (~432 DPI) a 20x24px crop is a ~3x4 point
region of the page: ORCID icons, publisher marks, journal badges, inline
glyphs. The tiny-**and**-caption-less conjunction discriminates almost
perfectly and costs nothing -- no classifier, no model, two fields
already in hand. Neither field alone would do: 6.4% of crops are tiny
*and* captioned, and 11.8% are large *and* caption-less.

The filter runs at **write time** -- a junk crop gets neither a PNG nor a
record -- because the docling cache is already invalid, so the re-parse
that makes it take effect is happening anyway, and because an index that
is 45% noise is wrong for every consumer, not just this one.

**The trap.** `write_figure_outputs` writes crops first so their names
exist to reference, and `_figure_records` pairs `image_names` against
`dl_doc.pictures` **by index**. The existing docstring already warns
that a shortened list points every later figure at its neighbour's
image, and drops every filename rather than risk it. A filter that
compacts the list re-creates exactly that fault. Filtering must preserve
positional correspondence, with a test that a filtered-out crop does not
shift its successors.

Each surviving record also gains `bbox` and pixel `dimensions`, so a
caller can judge a figure before opening it. The threshold is a named
constant carrying the measurement above, not a bare literal.

Deliberately out of scope: caption pairing for the 11.8%, structured
figure numbers, and panel letters. Each is a real gap and none is needed
to make the lookup useful.

**Raising the render scale is not the fix and would not help.**
`page.render(scale=…)` rasterises the page, so a figure embedded as a
150-DPI bitmap merely upsamples. `docling_image_scale` is already 6.0.
The quality ceiling is the source PDF; the richness ceiling is the
record shape.

### 4. Figures: the route that does not exist (#654)

`python -m chitragupta.draft figures <citekey>` -- read-only, returning
each figure's caption, page, cite string, image path, bbox and
dimensions.

In the **drafting** layer, for the same reason `draft tldr show` is
there: AGENTS.md already characterises that command as "browsing, not
drafting". It reads `content/docling/` **directly**, exactly as
`passages.py`'s rung 1 already does, and imports nothing from
`chitragupta/enrich/`. That precedent is what keeps AGENTS.md's "the
enrichment layer imports nothing from the drafting or review layers"
true in both directions -- a drafting module reaching into
`chitragupta/enrich/` would be the mirror-image violation.

The genre skills and `draft-reviser` are then taught when to consult a
source figure: while grounding a claim about what a paper's figure
shows, and while authoring the draft's *own* TikZ figure.

**Consider, never replicate.** `docs/CONFIG.md`'s `docling_images`
section already states that crops are a reading aid and that a figure's
copyright is not the paper's citekey to grant. This implements that
stance rather than revisiting it, and the skill text states the boundary
where an author will actually read it.

Issue #627 rejected vision captioning because it would write generated
text into the *corpus* layer. That rejection does not bind a drafting-time
*reader* that writes nothing back: the agent looks at the PNG, and only
the draft changes.

## ⚠ Risks named up front

- **The equation gain is unproven until a corpus re-parse runs.** The
  code change is small and testable; the 148 documents only benefit
  after `sync --reparse`. A PR that lands the toggle has not yet
  delivered the equations, and its test plan should say so rather than
  implying otherwise.
- **The figure filter can drop a real figure.** A small, caption-less but
  genuine figure exists; the measurement says it is rare, not absent. The
  threshold constant is the dial, and the write-time choice means
  changing it costs a re-parse. Accepted deliberately over a read-time
  filter, and recorded here so the trade is visible when someone hits it.
- **Wiring five skill files is the highest-blast-radius part of this
  run.** Skill contracts are cross-checked by several test modules and by
  `docs/`. #654 is last in the order for that reason, and the sweep
  DEVELOPER-AGENTS.md step 4 describes matters more there than anywhere
  else in these four.
- **Two of the four cannot be verified by unit tests alone.** #651 and
  #653 both change what a *parse* produces. Both need a real run against
  real PDFs before the claim is made, not merely a passing suite.

## 📋 Order, and why

1. **#651 equations** -- self-contained, and the corpus re-parse it
   requires is the long pole, so starting it first lets the run overlap
   the later work.
2. **#652 tables** -- independent of everything else, no re-parse.
3. **#653 figure index** -- must precede #654, which would otherwise
   return logos.
4. **#654 the lookup and the skill wiring** -- last, because it depends
   on #653's record shape and carries the most blast radius.

One MINOR release covers all four: new optional config key, new CLI
subcommand, no change to an existing output format or argument shape.
