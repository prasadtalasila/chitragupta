# 🖼 Figure quality: where it stands, and where it should go

Status: **discussion notes, nothing implemented.** Written 2026-09-04
against `c4ee19a`. Nothing here has been measured on the corpus unless a
section says so explicitly and names the artefact that holds the number.

**Written for** someone deciding what to build next in the figure system,
or deciding whether a proposal already considered here is worth
re-opening. Every subsection below is sized to become one feature request
on its own.

**Scope decision that shapes everything.** This project will mostly be
used to write technical books in **engineering, computer science and
software engineering**, optimising for the tutorial and textbook-chapter
genres, without restricting the thesis-chapter genre. Several proposals
that would be correct for a life-sciences or an empirical-results
pipeline are wrong here, and they are recorded in
[Considered and set aside](#-considered-and-set-aside) rather than
deleted, so nobody has to re-derive the argument.

## 🧭 Table of contents

- [Where figures stand today](#-where-figures-stand-today)
- [The gap, stated precisely](#-the-gap-stated-precisely)
- [Part I: Two missing artefact classes](#-part-i-two-missing-artefact-classes)
- [Part II: The metaphor vocabulary](#-part-ii-the-metaphor-vocabulary)
- [Part III: Derived figures](#-part-iii-derived-figures)
- [Part IV: Figure–text correspondence](#-part-iv-figuretext-correspondence)
- [Part V: A shared object vocabulary](#-part-v-a-shared-object-vocabulary)
- [Part VI: Quality levers that need no new drawing](#-part-vi-quality-levers-that-need-no-new-drawing)
- [Part VII: Quantitative panels](#-part-vii-quantitative-panels)
- [Part VIII: Where a vision model earns its place](#-part-viii-where-a-vision-model-earns-its-place)
- [Part IX: Figure-similarity provenance](#-part-ix-figure-similarity-provenance)
- [Rules that will have to bend](#-rules-that-will-have-to-bend)
- [Considered and set aside](#-considered-and-set-aside)
- [Build order](#-build-order)
- [What needs measuring first](#-what-needs-measuring-first)

## 📐 Where figures stand today

The figure system got a lot of attention between 2026-08-25 and
2026-09-04. Recorded here because the roadmap below builds directly on
it, and because a proposal that duplicates one of these is not worth
filing.

| PR | What it added |
| --- | --- |
| #403 | Six known-good TikZ scaffolds in `assets/tikz/`, one per layout metaphor. `tests/test_tikz_scaffolds.py` keeps them passing the layout aid and cross-checks the metaphor table in `docs/TIKZ-STYLE.md`, so a table row with no file fails |
| #408 | The layout aid reports when it measured **nothing**. A picture with no explicitly named nodes previously reported zero findings, indistinguishable from a clean figure. Also caught the stranded arrowhead (two colinear `->` draws meeting at a bare coordinate) |
| #409 | Panel lettering `(a)`, `(b)`… in both the TikZ and ASCII forms, any panel count, with a row-wrapping rule |
| #417 | Figures got the numbering contract tables already had: the renderer assigns the number, prose points via `<!-- figureref: name -->`, authors never write "Figure 3" |
| #430 | A figure with no caption is reported |
| #439 | The house palette: five Okabe-Ito colours (`cgInk`, `cgFlow`, `cgAccent`, `cgAlt`, `cgAux`) whose `\definecolor` block travels **inside** the figure file, so a fragment `\input` into a foreign thesis still compiles |
| #459, #464 | Equations numbered like figures and tables, with a reference-in-prose check; nine skills taught the marker vocabulary |
| #535, #533, #537 | Captions kept pandoc-visible rather than raw-interpolated into `\caption{}`; swallowed pandoc diagnostics fixed; five review aids stopped crashing or silently under-reporting, the figure layout aid among them |
| #600, #602 | Source-PDF figure crops extracted and, later, rendered one at a time rather than held in memory |

**What that leaves in place.** Three properties are worth naming because
the roadmap has to preserve all three:

- **Every figure has two forms.** A TikZ form and a 7-bit ASCII twin.
  `md`, `docx` and `html` output render only the twin
  (`docs/WRITING-STANDARDS.md`, "A figure's ASCII form is a diagram in a
  code block").
- **The aid measures, never places.** `review/figure_layout/_probe.py`
  compiles the figure under a minimal preamble and reads node boxes back
  out of the pdflatex log in millimetres. It only sees nodes the source
  gave an explicit `(name)`.
- **Nothing is a gate.** `docs/TIKZ-STYLE.md` closes on this
  deliberately, and the feature-request template carries a standing
  checkbox against promoting a new check into one.

**And these facts, each verified against the tree at `c4ee19a`:**

- Numbered artefact classes are exactly three: `figureref` (21 uses),
  `equationref` (11), `tableref` (9). There is no listing or algorithm
  class.
- The renderer adds `\usepackage{tikz}` and nothing else, conditionally,
  via `header-includes` in `render_output/_pandoc.py` (#222). `fvextra`
  is added by the same mechanism for a draft with a code block.
- `\usetikzlibrary` is legal in the document body, so figure files carry
  their own library loads. `\usepackage` is not, which makes any new
  package a renderer change rather than a figure-file change.
- There is **no** `\tikzset{pics/...}` and no `tikzset` of any kind in
  `assets/tikz/`. Every scaffold is standalone and every figure is drawn
  from nothing.
- There is no `pgfplots`, no `matplotlib`, no data file and no axis
  anywhere in the figure path.
- Raster images already survive the renderer: `_pandoc.py` sets
  `--resource-path` so the PDF and DOCX writers can resolve Markdown's
  image syntax pointed at a raster file. What is missing is the
  **contract**, not the plumbing: such an image gets no number, no
  marker, no twin, no caption check.

## 🕳 The gap, stated precisely

The six metaphors — pipeline, map, layered stack, control loop,
branching tree, hub-and-spoke — are all **topological**. Each one
answers "how do these things connect". That is one figure form among
several, and in a CS or SE textbook it is not the most common one.

Three forms carry most of the load in the target literature and none of
them is expressible today:

- **The same structure drawn at N successive moments**, with the
  differences marked. Heap sift-down, red-black rotations, a DP table
  filling in. This is the dominant figure form in the algorithms
  literature.
- **Time as an axis.** Lifelines with messages between them; instructions
  against cycles. Protocols, concurrency, distributed systems, pipelines.
- **Layout drawn to scale.** A packet header, a struct, a stack frame, a
  page-table entry. Widths carry meaning.

Two further observations reframe the whole problem for this domain, and
both are good news:

**Illustration craft is not the bottleneck here.** A cell has no
canonical visual form, which is why a life-sciences textbook needs a
trained illustrator. A red-black tree rotation, a TCP header, a
five-stage pipeline and a UML sequence diagram all have conventional,
agreed renderings made of lines and text. These figures are natively
TikZ-shaped. The reachable ceiling in this domain is far higher than in
biology and needs no illustrator, no licensed art and no raster.

**The ASCII twin stops being a constraint.** ASCII diagrams are a native
idiom in this field; RFC 793's TCP header is one. Box-and-pointer
diagrams, layered stacks, bit-field layouts and state machines all render
honestly in 7-bit. The rule that would cap a biology pipeline is nearly
free here, and the roadmap below should be read as *endorsing* it rather
than working around it.

---

## 📑 Part I: Two missing artefact classes

### The gap

A code listing is typographically handled: `_pandoc.py` detects
`has_code_block` and loads `fvextra` with `breaklines` so an over-wide
verbatim line wraps rather than running into the margin. But a listing
cannot be **numbered or referenced**. In a technical book, "Listing 4.2
shows the retry loop" is as frequent as "Figure 4.2 shows". With no
class, an author either hand-numbers it, which is precisely the failure
issues #417 and #459 existed to eliminate, or writes "the code above",
which breaks the moment a page splits or a section is reordered.

The same argument holds for a pseudocode algorithm, which in this
literature is a distinct artefact from both a listing and a figure.
`WRITING-STANDARDS.md` already has to reason about pseudocode as a
special case (the seven-line pseudocode listing that is the shortest
false positive for one of its checks), which is a sign the concept is
already load-bearing without being a first-class citizen.

### Proposal

Add `listingref` and `algorithmref` alongside the three existing classes,
with the identical contract:

- The renderer assigns the number. The author never writes one.
- Prose points at the artefact with `<!-- listingref: name -->` /
  `<!-- algorithmref: name -->`.
- A reference-in-prose check reports an artefact nothing points at, and a
  marker pointing at nothing.
- Every genre skill learns the vocabulary, the way #464 taught nine
  skills the equation markers.

### Details worth pinning down before filing

- **Caption or title?** A listing conventionally carries a title above
  it, not a caption below. Decide whether #430's caption-presence check
  applies, and whether the ASCII/`md` route can express the distinction
  at all.
- **What is an algorithm's second form?** A figure has a TikZ form and an
  ASCII twin. Pseudocode is already text, so there is no twin to keep in
  sync. This class is simpler than figures, not harder, and the
  simplification should be explicit rather than accidental.
- **Ordering interaction.** Four numbered classes sharing one document
  means four independent counters. Confirm the existing counter machinery
  generalises rather than assuming it.

### Why this is first

It is a correctness gap rather than a quality one, it is the smallest
item on this roadmap, and Parts III and IV both want a stable marker
vocabulary underneath them.

---

## 🧱 Part II: The metaphor vocabulary

Each subsection below is one new row in `TIKZ-STYLE.md`'s metaphor table
plus one scaffold in `assets/tikz/`, and each is independently
fileable. `tests/test_tikz_scaffolds.py` already enforces that the table
and the directory agree, so a row cannot ship without a file.

Common requirements for all of them:

- The scaffold compiles standalone and reports no binary finding from
  `python -m chitragupta.review figure`.
- Nodes are placed relative to one another. No hand-computed millimetre
  coordinates (see [Rules that will have to bend](#-rules-that-will-have-to-bend)
  for the one exception this roadmap proposes).
- Every node carries an explicit `(name)`, or the aid measures nothing
  and says so (#408).
- The `\usetikzlibrary` load sits at the top of the figure file, above
  the `tikzpicture`, because the renderer will not supply it.
- The scaffold ships with its ASCII twin, and the twin is part of what
  makes the metaphor acceptable.

### II.1 State sequence (algorithm trace)

**The form.** One structure, N snapshots, differences marked. The single
most common figure in the algorithms literature and the highest-value
addition on this roadmap.

**Why it is not just panels.** #409 letters panels as siblings. A
snapshot is not a sibling: it has an ordinal, a predecessor, and a
delta from it. The figure's whole meaning is the difference between
adjacent frames, and a reader needs to see which nodes changed.

**Mechanism.** The honest version is a `pic` (see Part V) drawn once per
frame with a per-frame highlight set, laid out left to right or in
wrapped rows, with the changed elements taking the accent colour. Without
`pic` reuse the author redraws the structure N times by hand and the
frames drift, which is the defect this metaphor exists to prevent. **This
subsection therefore depends on Part V** and should not be filed before
it.

**Twin strategy.** N ASCII frames stacked vertically, each with its
ordinal, and the changed elements marked with a character rather than a
colour. This works, and is arguably clearer than the TikZ form.

**Open question.** Whether the highlight-the-delta step can be derived
rather than hand-specified. Given frames as data (Part III), the delta is
a set difference, so a derived trace could mark its own changes. That is
the strongest single argument for Part III.

### II.2 Sequence / message diagram

**The form.** Vertical lifelines, time flowing down, messages as
arrows between them. Protocols, concurrency, distributed systems.

**Mechanism.** Achievable with `positioning` and `calc` on a plain
`tikzpicture`; lifelines are long thin nodes or `\draw` verticals with
named coordinates at each message height. There are third-party TikZ
packages for UML sequence diagrams; prefer the hand-rolled scaffold
unless one is already in `texlive-pictures`, because
`scripts/install_full_pipeline.sh` should not grow a dependency for one
metaphor.

**Twin strategy.** Native. A sequence diagram in ASCII is a standard,
readable form and appears in RFCs constantly.

**Interaction with the aid.** Message arrows are `\draw` statements, so
the edge list the aid reports will be populated, unlike the `tree` case.
Worth confirming that near-parallel horizontal arrows at close vertical
spacing are caught by the existing overlap check.

### II.3 Bit-field / memory layout

**The form.** A packet header, a struct, a stack frame, a page-table
entry. Fields drawn to scale so width carries meaning.

**Mechanism.** This is closer to a table with geometry than to a diagram.
The `bytefield` package does it natively and is the obvious candidate,
but it is a `\usepackage`, which makes this a **renderer change** on the
same conditional `header-includes` pattern as tikz and `fvextra`. A pure
TikZ `matrix`-based scaffold avoids the dependency at the cost of doing
the width arithmetic by hand. Decide which before filing; the
`bytefield` route is probably right but it changes the shape of the
issue.

**Twin strategy.** Native and excellent. This is exactly what RFC-style
ASCII diagrams do best.

**Correspondence opportunity.** A bit-field figure usually depicts a
struct or a spec table that also appears in the chapter as code. Field
names and widths are checkable against it. See Part IV.

### II.4 State machine / automaton

**The form.** States, labelled transitions, an initial marker, accepting
states, self-loops.

**Mechanism.** TikZ's `automata` library exists for precisely this and
ships in `texlive-pictures`, so no new dependency. The current tree and
hub-and-spoke scaffolds approximate this badly: neither can express a
self-loop or an accepting state.

**Twin strategy.** A transition table is the right twin, not an ASCII
drawing. A table is more precise than the picture and is what a screen
reader wants. This is a **general principle worth adopting**: the twin
should be the clearest 7-bit representation of the same information, not
a character-art tracing of the same picture.

**Derivation opportunity.** Strongest case on the roadmap. Given a
transition table, the figure is fully determined. See Part III.

### II.5 Timing / occupancy diagram

**The form.** One axis is time, the other is a resource or an
instruction. Pipeline stage diagrams, scheduler traces, Gantt-shaped
occupancy.

**Mechanism.** A `matrix` of cells, or `pgfgantt` if a dependency is
acceptable. The `matrix` route probably suffices and keeps the
dependency list flat.

**Twin strategy.** Native. A character grid is the conventional ASCII
form for this and appears in architecture texts directly.

### II.6 Box-and-pointer / memory graph

**The form.** Linked structures with real pointer arrows: linked lists,
trees with parent pointers, SICP environment diagrams, CS:APP stack
frames.

**Mechanism.** `positioning` plus `fit`, with a `pic` per cell (Part V).
The distinguishing requirement is that an arrow must start from a
specific compartment of a node rather than from the node's edge, which
means named sub-anchors, which means the cell wants to be a `pic` with
declared anchors.

**Twin strategy.** Native, and a long-standing idiom.

### II.7 Annotated object and detail callout

**The form.** Labels sitting outside the drawing, connected by hairlines
to precise anchor points; and a magnified inset of one region with
connecting lines to its source.

**Why it is here even though it came from the biology discussion.** It
generalises. A datapath schematic with labelled buses, a screenshot with
callouts, a code listing with leader lines pointing at specific tokens
are all the same form, and none of the six current metaphors can express
it because text lives *inside* boxes.

**Mechanism.** `pin` and the `quotes` library for leader lines; TikZ's
`spy` library for the magnification callout. Both ship in
`texlive-pictures`.

**Twin strategy.** A label list with each label's relation to the object.
Not character art.

---

## ⚙ Part III: Derived figures

### The idea

In this domain a figure usually depicts something that **also exists as
text elsewhere in the chapter**: a transition table, a grammar, a struct
definition, pseudocode, a spec, a real import graph. Rather than asking
an author or a model to draw the automaton, derive it from the transition
table. Rather than hand-drawing a DP-table trace, run the algorithm and
emit the frames.

This is the same move the project already made for citekeys: stop
generating the artefact, derive it from a source of truth, and refuse to
guess. A derived figure is regenerable, auditable, and **cannot drift
from the text**.

No life-sciences pipeline can do this, because there is no ground truth
to derive from. This one has ground truth on nearly every page. It is the
most distinctive feature available and the reason to prefer this roadmap
over "draw prettier boxes".

### Candidate derivations, easiest first

| Source of truth | Derived figure | Notes |
| --- | --- | --- |
| Transition table | State machine (II.4) | Fully determined. The obvious first one |
| Struct / spec table | Bit-field layout (II.3) | Widths and names both come from the source |
| Frame list or algorithm run | State sequence (II.1) | Also derives the per-frame delta highlight, which is otherwise hand-specified and error-prone |
| Grammar (BNF) | Parse tree / railroad diagram | Well-trodden ground; many existing generators to read first |
| Message log or protocol spec | Sequence diagram (II.2) | Ordering is the whole content and is machine-readable |
| Real source imports | Dependency graph | Tempting, but a real import graph is usually too dense to be a teaching figure. Needs a filtering story before it is worth filing |

### Design constraints

- **Layer.** This is a drafting-layer or authoring-tool concern, not a
  corpus-layer one. It is deterministic, so it *could* live in the corpus
  layer's style, but it acts on a draft rather than on the corpus and
  belongs beside the draft.
- **Output is a real figure file.** The derivation writes
  `figures/<n>.tex` and its twin, which then go through the existing
  layout aid, caption check and numbering unchanged. It must not become a
  parallel figure path with its own rules.
- **The source of truth stays in the draft.** The transition table is
  a table the reader sees, not a hidden sidecar. That is what makes the
  figure verifiable by the reader as well as by the tool.
- **Regeneration must be idempotent and visible.** A derived figure that
  an author then hand-edits, and which is later regenerated, silently
  loses the edit. Either mark derived files as generated and refuse to
  regenerate over local changes, or accept one-shot generation with no
  regeneration at all. The second is smaller and probably right first.

---

## 🔗 Part IV: Figure–text correspondence

### The correspondence gap

Figure–text divergence is the characteristic defect of technical books.
The figure shows five pipeline stages and the prose says four. The state
machine has a transition the table lacks. The struct diagram is one field
out of date. All three are invisible to every check this project has: the
layout aid measures geometry, the verbatim tiers scan prose and never see
inside a figure file, and the caption check only asks whether a caption
exists.

No other domain offers this affordance. Nobody can validate a
life-sciences illustration against ground truth. Here you frequently can,
because the figure's labels are identifiers that appear in the adjacent
listing, table or prose.

### The correspondence proposal

A review aid that reports, per figure, the two-way set difference:

- Node labels in the figure that appear **nowhere** in the enclosing
  section.
- Identifiers in the enclosing section that appear **nowhere** in the
  figure.

Both directions matter. The first catches a stale or invented label; the
second catches a figure that has fallen behind the text.

### Properties

- **Deterministic.** No LLM, no embedding, no threshold. Same input, same
  findings.
- **Ranked, never banded.** Report the differences and let the author
  judge. Many will be legitimate: an article, a verb, a label that
  paraphrases. See
  [PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md)'s "The
  threshold is not a discriminating variable" for why guessing a cutoff
  here would be a mistake, and #428's claim-support output for the shape
  to copy.
- **Measures nothing, says so.** A figure with no named nodes, or a
  section with no code, yields no comparison and must report that rather
  than reporting clean (#408's lesson).
- **Not a gate.**

### Details to settle before filing

- **What counts as an identifier** in the section: fenced-code tokens,
  inline code spans, table cells, defined terms. Starting narrow
  (fenced-code and inline-code tokens only) keeps the false-positive rate
  measurable.
- **What counts as a figure label**: the aid already extracts explicitly
  named nodes; label *text* is a separate extraction from the source.
- **Scope of "the enclosing section"**: the section containing the
  `figureref` marker, or the whole chapter. The first is tighter and
  probably right, but a figure referenced from two sections breaks the
  assumption.
- **Case and separator normalisation**: `page_table`, `pageTable` and
  "page table" are the same identifier to a reader. Deciding this wrong
  makes the aid useless in either direction.

---

## 🧩 Part V: A shared object vocabulary

### The vocabulary gap

There is no `\tikzset{pics/...}` and no `tikzset` at all in
`assets/tikz/`. Every scaffold stands alone; every figure is drawn from
nothing. Consistency across a whole book is therefore an act of authorial
discipline repeated once per figure, which is exactly the kind of thing
that does not survive fifteen chapters.

### The vocabulary proposal

A `assets/tikz/lib/` of reusable TikZ `pic`s, `\input` by a figure that
needs them. Candidate vocabulary for this domain: a memory cell with
named compartments, a queue, a stack frame, a node-with-pointer-slots, a
clock tick, a lifeline, a labelled bus, a register.

### Why this is the highest-leverage structural item

1. **It compounds.** Quality invested in one `pic` pays out in every
   figure that uses it, across a whole book. Nothing else on this
   roadmap has that property.
2. **It matches what a language model is actually good at.** Writing
   `\pic{cell} at (head.east)` correctly is easy. Placing forty control
   points blind is not. The current setup asks for the second and the
   figures show it.
3. **Part II.1 depends on it.** A state-sequence figure without object
   reuse means redrawing the structure N times by hand, and the frames
   drift.

### The tension it creates

A shared library is state across figures, which cuts against the rule
that a figure file must be self-contained and `\input`-able into a
foreign thesis. `assets/` is already copied into a project by
`chitragupta init`, so shipping the library as a single file the figure
`\input`s keeps it beside a scaffolded draft with nothing to download.
But a figure lifted out of the project and dropped into someone else's
document now needs two files rather than one, and the fragment-portability
property is real and deliberate. Options, in rough order of preference:

1. Ship the library as one file; document that a portable fragment needs
   it alongside, the way the palette's `\definecolor` block travels
   inside the figure.
2. Inline the used `pic` definitions into the figure at authoring time,
   trading duplication for portability.
3. Accept two files and adjust the portability claim in the skills.

This decision should be made before any `pic` ships, because reversing it
means rewriting every figure that used the library.

---

## 🎯 Part VI: Quality levers that need no new drawing

Four cheap items. Together they probably raise the perceived quality of
existing figures more than any single new metaphor.

### VI.1 Make the caption carry the load

Issue #430 checks that a caption **exists**. A good technical caption is
self-contained and states the takeaway, not just the subject: "the
write path, showing where the fsync barrier falls" rather than "the write
path". Captions currently escape `HOUSE-STYLE.md`'s objective function
entirely, because they live in markers rather than in prose.

**Proposal.** A caption-shape aid reporting a caption under some word
count, or one that names its subject without asserting anything. Report,
never gate; a very short caption is sometimes right. This is the highest
ratio of informativeness gained to code written on the whole roadmap,
because it raises figure quality without drawing anything.

**To settle:** whether the prose objective function can be applied to
caption text directly, or whether captions need their own smaller
predicate.

### VI.2 Report effective type size at final scale

`TIKZ-STYLE.md` names the defect precisely — `\footnotesize` inside a
picture scaled to 0.8 — and there is no check for it. The probe already
has the bounding box in millimetres and the source has the scale factor,
so the smallest type's printed size is arithmetic.

**Proposal.** Report it as a number: "smallest label prints at 4.2 pt at
an 84 mm column". Turns a documented defect into a measurement. No
threshold, no verdict.

**To settle:** where the target column width comes from. It is a property
of the output, not of the figure, and the figure file does not know it.

### VI.3 Report element counts

Nodes, edges, distinct colours used, words of text. A schematic with six
nodes and one with forty are different problems, and right now neither
the author nor the aid can see which one it is looking at. Fits the
measure-never-place contract exactly.

**To settle:** nothing much. This is the smallest item in the document
and a reasonable first contribution for someone learning the aid.

### VI.4 Replace the skeletons with exemplars

`assets/tikz/` ships six structurally-correct, deliberately minimal
scaffolds. Skeletons produce skeletal figures: an author who copies a
three-node pipeline tends to ship a three-node pipeline.

**Proposal.** Alongside each scaffold, one **finished** figure per
metaphor: fully labelled, real content from this domain, at final column
width, with a caption that states a takeaway. The scaffold stays the
starting point; the exemplar becomes the target.

**Why it may be the cheapest quality lever here.** It needs no new code
at all, and `tests/test_tikz_scaffolds.py` already provides the machinery
to keep the new files compiling and finding-free.

---

## 📊 Part VII: Quantitative panels

### The plotting gap

No `pgfplots`, no `matplotlib`, no data file, no axis anywhere. Benchmark
curves, latency distributions, complexity growth and scaling plots cannot
be drawn at all.

### Priority note

Lower than I would put it for a thesis or results pipeline. A teaching
figure is usually explanatory rather than evidential, and a complexity
curve is often illustrative rather than measured. It matters for the
thesis-chapter genre and for any book chapter reporting real benchmarks,
which is enough to keep it on the roadmap but not enough to put it first.

### Mechanism

- **This is a renderer change.** `\usetikzlibrary` is body-legal so
  figure files carry their own libraries, but `\usepackage{pgfplots}` is
  not. It needs a conditional `header-includes` in `_pandoc.py`, which is
  architecturally identical to what #222 did for tikz and what already
  exists for `fvextra`. Precedented and small.
- **Data lives beside the figure** as `figures/<n>.dat`, drawn with
  `\addplot table`. The numbers become diffable and auditable, which is
  more than most published figures manage.
- **The twin is the data table**, not an ASCII scatter. A table in the
  `.txt` output is more informative than the plot and is what a screen
  reader wants. The twin requirement stops being a ceiling and becomes a
  feature. This is the same principle as II.4's transition table.
- **Confirm which texlive package ships pgfplots** and whether
  `scripts/install_full_pipeline.sh` needs a line. `texlive-pictures`
  covers the tikz libraries; do not assume it covers this.

---

## 👁 Part VIII: Where a vision model earns its place

### The one place it belongs

Geometry cannot judge informativeness. `TIKZ-STYLE.md` explicitly leaves
three defects to human judgement: chaotic routing, illegible or
inconsistent type, and literal copying. A model that **looks at the
rendered figure** is the only mechanism that reaches the first two, plus
the twin-equivalence test the doc frames as reading the `.txt` and asking
whether the point still arrives.

### Vision-critique mechanism

- `pypdfium2` is already a declared dependency of the `enrich` extra
  (added for the crop work in #600/#602), so rasterising the probe's
  compiled PDF needs no new package.
- Serve the model **out of process** — a local vLLM endpoint or an API —
  rather than importing it. `adapters` pins `transformers` to
  `>=4.57.6,<4.58.0`, a single-patch window, and most current
  vision-language models want newer. Importing one into the `enrich` venv
  turns the next `poetry lock` into a fight.
- Advisory only, exit 0, in the review layer. This is a Layer 2
  (generative) capability and must not become a corpus-layer artefact,
  because it is not deterministic.

### Where it does not belong

Captioning source-PDF figures at parse time. #627 measured and rejected
that on the grounds that it puts generated text in the corpus layer,
which may not call an LLM (`docs/ARCHITECTURE.md`: "LAYER 1 · CORPUS —
deterministic, no LLM, safe unattended"). That rejection stands.

### Adjacent: the unconsumed crops

`plans/651-multimodal-drafting-access.md` measured 8,769 figure crops and
497 `figures.json` indices on the real 497-PDF corpus, with **zero
consumers**. Source figures reach no draft. Two routes that respect the
layer boundary:

- Surface the crops at the **drafting** layer, where a model is already
  in the loop, as "the figure anchored at this passage" alongside
  retrieved text. #632's passage anchoring is the mechanism.
- Retrieve by page image rather than parsed text, which sidesteps the
  fact that `retrieval.search()` reads exactly one artefact,
  `content/parsed/<citekey>.txt`. `colpali-engine` is the mature option.

Both are separate features from anything in Parts I–VII and should be
filed against #651 rather than here.

---

## 🔍 Part IX: Figure-similarity provenance

Written up in full separately as a candidate issue; summarised here so
the roadmap is complete.

**The hole.** `TIKZ-STYLE.md` states it directly: a figure can launder
borrowed material past every detector in `PLAGIARISM.md`, because a
citekey is deliberately kept out of figure files and the draft gate does
not follow `\input`. Three individually-correct decisions compose into
it. The originality rule for figures is the only rule in the project with
no mechanical support of any kind.

**The proposal.** Rasterise the compiled draft figure, screen against the
8,769 corpus crops with a perceptual hash, then rank by image-embedding
similarity. `sentence-transformers`, `chromadb` and `pypdfium2` are all
already declared. Report the top few candidates with their citekey and
the source paper's own figure number, which `_docling_figures.py` already
captures.

**Ranked, never banded.** `PLAGIARISM-DESIGN.md` measured 16 long runs
across a 178,077-word book, found all 14 actionable ones to be false
positives at 15–29 words, and found the only genuine planted lift at 18
words, inside that range. No threshold separated them, and #130 forbids
guessing one. There is no reason image similarity behaves better.

**Domain-specific warning, and this is new.** In CS and SE the canonical
figures are common property. Everyone draws the OSI stack, the five-stage
pipeline and the standard red-black rotation the same way, legitimately.
The false-positive floor will be **worse** in this domain than the
biology framing implied, and that expectation should be written into
`bench/bench_figure_similarity.py` before it runs rather than discovered
afterwards. An outcome where the floor swallows the planted case is a
valid result and should close the issue, the way `bench_overlap_gate.py`
killed a proposed gate on its own numbers and the way C4 and C6 left the
roadmap (#485, #483).

---

## ⚖ Rules that will have to bend

Three existing rules collide with proposals above. Each needs a decision
made deliberately rather than discovered mid-implementation.

### "No coordinate in millimetres" versus fixed objects

The rule exists because a figure laid out in hand-computed absolute
millimetres cannot express "do not collide": re-wording one label
re-opens every adjacency at once. That argument is exactly right for
**composition** and does not apply **inside a `pic`**. A `pic` is a
fixed object drawn once, whose internal geometry does not reflow when a
sibling's label changes.

**Proposed carve-out.** Relative placement governs composition;
explicit coordinates are permitted inside a `pic` definition. Document
the reason alongside the rule, or the next reader will take the carve-out
as licence to hand-place a whole figure.

### The five-colour palette versus depiction

Less pressing in this domain than in biology, because CS figures are line
art and the Okabe-Ito palette suits them well. But the distinction is
still worth recording: the palette and the greyscale test govern
**semantic** colour, where a hue encodes a variable. Depictive colour,
where a thing simply looks like something, encodes nothing and the
greyscale test does not apply to it. Almost nothing in this domain is
depictive, so the practical answer is **keep the rule as it stands** and
note the distinction only if a genuine case appears.

### The ASCII twin as tracing versus as representation

Several proposals above (II.4's transition table, VII's data table,
II.7's label list) share one principle worth promoting to a rule: **the
twin is the clearest 7-bit representation of the same information, not
character art tracing the same picture.** For most of this domain the
clearest representation happens to *be* a diagram, which is why the twin
requirement is nearly free here. Where it is not, a table beats
character art and should be allowed to.

---

## 🚫 Considered and set aside

Recorded with the argument, so nobody re-derives it.

| Proposal | Why not |
| --- | --- |
| **Licensed vector art libraries** (Bioicons ~3,000 CC0/CC-BY icons, Servier Medical Art CC BY 4.0, NIH BioArt public domain, PhyloPic) | Correct answer for a life-sciences pipeline, irrelevant here. There is no icon library for a page table or a pipeline hazard. The attribution machinery would have been a good fit for this project's provenance spine, which is the only reason it was considered at all |
| **Generated raster illustration** | Non-deterministic, non-diffable, non-editable, and factually unreliable in exactly the domain where a mislabelled figure is worse than no figure. Fails the properties `SOUL.md` is built on. The narrower "generate a base plate and trace it" version reintroduces the originality problem of Part IX and still needs an illustrator |
| **Bezier organic form, gradients, translucency** | Illustrator craft. Reachable in TikZ in principle, but a cell membrane's curve requires hand-placed control points and this domain has no organic objects to draw. Dropped entirely |
| **`detikzify` or image-to-TikZ synthesis** | The inverse of Part IX: it automates producing the artefact that check exists to catch |
| **Vision captioning of source figures at parse time** | Rejected in #627. Puts generated text in the corpus layer, which may not call an LLM |
| **Nature-style data density as the benchmark** | Wrong target for tutorials and textbook chapters. A teaching figure is explanatory, not evidential. Tufte and the algorithms literature are the better references. Part VII keeps the quantitative capability for the thesis genre without making density the goal |
| **A figure-similarity gate** | See Part IX. Advisory and ranked only. #130 forbids guessing a threshold and the measured evidence says none exists |

---

## 🗺 Build order

Ordered by a mix of certainty, size and what unblocks what.

1. **Part I — listing and algorithm classes.** Smallest, most certain, a
   correctness gap rather than a quality one. Parts III and IV both want
   the marker vocabulary stable underneath them.
2. **Part VI.3 and VI.4 — element counts, exemplar figures.** Nearly free.
   VI.4 needs no new code and is plausibly the largest single perceived-
   quality jump available.
3. **Part VI.1 — caption shape.** Best ratio of informativeness to code
   on the roadmap.
4. **Part V — the `pic` library.** Structural, compounding, and a
   prerequisite for II.1. Settle the portability question first.
5. **Part II.1 — state sequence.** Highest-value metaphor. Depends on 4.
6. **Part II.2, II.3, II.4 — sequence diagram, bit-field, automaton.**
   Mostly a scaffold plus the right library load. II.3 may carry a
   renderer change (`bytefield`); II.4 is the best derivation target.
7. **Part IV — correspondence.** Wants I done, and wants II.3/II.4
   figures existing to check against.
8. **Part III — derived figures.** The distinctive feature, but it
   compounds on everything above.
9. **Part VI.2 — type size at final scale.** Blocked on deciding where
   the target column width comes from.
10. **Part VII — quantitative panels.** Real, lower priority for this
    genre mix.
11. **Part VIII — the vision critique loop.** Genuinely useful, but it
    judges quality rather than creating it, so it lands better once there
    is more quality to judge.
12. **Part IX — figure similarity.** Independent of everything else, and
    may close on its own bench numbers.

## 📏 What needs measuring first

Following the bench self-check convention (`plans/356`), and the
precedent of `bench_overlap_gate.py`, which killed a proposed gate on its
own numbers:

- **Figure inventory of a real book.** Count the figures in this
  project's own 15-chapter book by form, and check the claim this whole
  roadmap rests on: that state sequences, sequence diagrams, bit-fields
  and automata are frequent in the target literature and the six current
  metaphors do not cover them. If that count comes back saying the six
  metaphors cover 90% of the book's figures, Part II shrinks a great
  deal.
- **Correspondence false-positive floor (Part IV).** Run the two-way set
  difference over existing figures and their sections. Legitimate
  mismatches will dominate; the question is whether the signal is visible
  above them.
- **Figure-similarity floor and recall (Part IX).** Rank the 8,769 crops
  against each other to establish the noise level, plus a planted TikZ
  redraw of a known corpus figure to confirm it ranks above it.
- **Encoder choice (Part IX)**, in the style of
  `bench_embed_model_compare.py`. A CLIP-class model trained on natural
  images may be weak on line art, which is an empirical question rather
  than a guess.
- **Review-pass cost** for anything added, per
  `PERFORMANCE.md`'s "What a review pass costs".
