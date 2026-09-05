# 🖼 Figure quality: where it stands, and where it should go

Status: **discussion notes, nothing implemented.** Written 2026-09-04
against `c4ee19a`; revised 2026-09-05 to fold in material borrowed from
`cathrynlavery/diagram-design` (see
[Borrowed, with attribution](#-borrowed-with-attribution)). Nothing here
has been measured on the corpus unless a section says so explicitly and
names the artefact that holds the number.

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
- [Part X: Output targets](#-part-x-output-targets)
- [Part XI: Rendered figure images in md, html and docx](#-part-xi-rendered-figure-images-in-md-html-and-docx)
- [Rules that will have to bend](#-rules-that-will-have-to-bend)
- [Borrowed, with attribution](#-borrowed-with-attribution)
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

**A third observation, added in revision.** Several defects this roadmap
originally routed to human judgement or to a vision model (Part VIII) are
plain geometry once you write the rule down precisely. That realisation
came from reading another project's connector rules, and it moves the
single most expensive item on this roadmap into the cheapest part. See
[VI.5](#vi5-routing-findings).

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

### II.0 Split the style doc before adding seven metaphors

**Filed first within Part II, and cheap.** `TIKZ-STYLE.md` currently
holds the whole metaphor table plus the conventions for six metaphors.
Part II proposes seven more. Thirteen sets of layout convention,
anti-patterns, twin strategy and worked example will not sit in one
document, and a skill that has to read all thirteen to draw one figure
wastes most of its context on metaphors it is not using.

**Proposal.** One `docs/figures/metaphor-<name>.md` per metaphor,
holding that metaphor's conventions, its anti-patterns, its twin strategy
and a pointer to its scaffold and exemplar. `TIKZ-STYLE.md` keeps the
selection table, the palette, the shared rules and nothing else. Skills
load the selection table plus exactly one metaphor file.

**Enforcement is already built.** `tests/test_tikz_scaffolds.py` enforces
that a table row has a scaffold file. Extend it to a third column: a row
must have a scaffold, a doc, and (after VI.4) an exemplar. That keeps the
routing surface honest as the count grows, which is exactly the failure
mode a thirteen-row table invites.

**Why now rather than later.** This is a small change against six
metaphors and an expensive one against thirteen. Doing it after Part II
ships means rewriting every metaphor's prose out of a merged document.

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

**Element counts do not apply here.** Whatever reference range VI.3
establishes for a pipeline, a DP-table trace legitimately has forty
cells. The per-metaphor range is the point; a single global budget would
be wrong for exactly this metaphor.

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
spacing are caught by the existing overlap check, and that VI.5's
label-gap and shared-attach-point findings behave sensibly on a lifeline,
where many arrows legitimately meet the same vertical line.

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

**A geometric check this metaphor uniquely permits.** A bit-field figure
makes a claim no other metaphor makes: *width is the encoding*. That
claim is checkable. Given the declared bit width in each field's label,
the aid can compare each field's drawn width against its share of the
total and report the discrepancy. Two details decide whether it is
useful:

- **Relative, not absolute, error.** An absolute measure passes exactly
  the narrow fields most likely to be wrong. A one-bit flag drawn at
  four bits' width is a 300% error and a sub-millimetre one.
- **Rounding is legitimate.** A 3-bit field in a 32-bit header cannot
  always land on a clean grid. Report the number; do not band it.

This is the strongest deterministic figure check on the roadmap and is a
better version of Part IV's correspondence idea, because it compares the
figure against itself rather than against prose.

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

**It is a primitive, not a metaphor.** Noted in revision: annotation
composes with every other metaphor rather than competing with them. A
sequence diagram can carry a callout; so can a bit-field. Filing it as a
thirteenth row in the selection table would be a category error and would
push authors to choose it *instead of* the right metaphor. It belongs in
Part V's library as an annotation `pic`, with a line in the shared rules
rather than a metaphor row of its own.

**Mechanism.** `pin` and the `quotes` library for leader lines; TikZ's
`spy` library for the magnification callout. Both ship in
`texlive-pictures`.

**Twin strategy.** A label list with each label's relation to the object.
Not character art.

**Budget.** Two callouts per figure is a reasonable starting reference
range; past that the labels are competing with the drawing. Report,
never gate.

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
| Struct / spec table | Bit-field layout (II.3) | Widths and names both come from the source, and II.3's width check then verifies the derivation against its own source |
| Frame list or algorithm run | State sequence (II.1) | Also derives the per-frame delta highlight, which is otherwise hand-specified and error-prone |
| Grammar (BNF) | Parse tree / railroad diagram | Well-trodden ground; many existing generators to read first |
| Message log or protocol spec | Sequence diagram (II.2) | Ordering is the whole content and is machine-readable |
| Real source imports | Dependency graph | Needs the reduction ladder below before it is worth filing |

### The reduction ladder and the fidelity ledger

The dependency-graph row was previously parked on the grounds that a real
import graph is too dense to be a teaching figure and "needs a filtering
story". Here is the filtering story, borrowed wholesale in shape from
`diagram-design`'s import path.

**A fixed reduction ladder, applied in a fixed order** until the figure
falls inside its metaphor's reference range: drop decorative and
unconnected elements, then merge duplicates, then collapse leaf clusters
into a single labelled node, then drop infrastructure that every node
touches. Fixed order matters more than the specific rungs: it is what
makes the reduction deterministic and therefore re-runnable, which is the
whole reason a derived figure is worth more than a drawn one.

**Every derivation emits a ledger** naming what it merged, collapsed and
dropped, and what it kept in full. Something like:

```text
Derived: dependency graph from src/chitragupta/review/
Reduction: 41 source modules → 9 drawn
Collapsed: 6 leaf modules under review.figure_layout → one node
Merged:    _probe.py + _probe_util.py (always co-imported)
Dropped:   4 test-only modules; stdlib imports
Kept in full: the render_output → _pandoc → figure path
```

The ledger is worth more for a derived figure than for an imported one,
because it is the audit trail that makes the derivation trustworthy to a
reader who did not run it. It also partly answers the idempotence problem
below: a regeneration whose ledger is unchanged produced the same figure,
and a ledger diff is readable in a way a TikZ diff is not.

**Where the ledger lives** needs deciding. Beside the figure as
`figures/<n>.ledger`, or as a comment block inside the `.tex`. The second
keeps the fragment-portability property; the first is easier to diff. Pin
this before the first derivation ships.

### Design constraints

- **Layer.** This is a drafting-layer or authoring-tool concern, not a
  corpus-layer one. It is deterministic, so it *could* live in the corpus
  layer's style, but it acts on a draft rather than on the corpus and
  belongs beside the draft.
- **Determinism is the whole point.** A derivation must not call an LLM.
  If a step needs judgement — which cluster to collapse, which node is
  focal — that judgement belongs in the ladder as a fixed rule, or in the
  author's hands, not in a model. This is the same argument #627 made one
  layer down.
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

### V.1 The `pic` library

A `assets/tikz/lib/` of reusable TikZ `pic`s, `\input` by a figure that
needs them. Candidate vocabulary for this domain: a memory cell with
named compartments, a queue, a stack frame, a node-with-pointer-slots, a
clock tick, a lifeline, a labelled bus, a register, and the annotation
callout promoted out of II.7.

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

### V.2 A few domain shapes, not an icon set

An icon library was reconsidered during this revision and set aside
again; the argument is in
[Considered and set aside](#-considered-and-set-aside) and should not be
re-opened without new information.

What survives from that discussion is much smaller and belongs in V.1
rather than in an issue of its own. If a metaphor wants a conventional
shape — a drum for a store, a cylinder for a queue, a boundary marker for
a trust or process edge — draw two or three of them as `pic`s in the
house line weight, sized against Part X's output target. That is the
`pic` library doing the job it exists for. It carries no licence notice,
no conversion script, no Part IX whitelist and no exclusion rules in
VI.3 or Part IV, because a shape drawn in the house vocabulary is not
third-party art recurring verbatim across a corpus.

The test for adding one: **can the twin say the same thing in words?** A
drum labelled `page table` and the twin's `[page table]` carry the same
proposition, so the shape is a rendering choice. A shape carrying meaning
the label does not is a twin violation, whatever it is drawn with.

---

## 🎯 Part VI: Quality levers that need no new drawing

Six cheap items. Together they probably raise the perceived quality of
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

**Previously blocked; now unblocked.** The open question was where the
target column width comes from, since it is a property of the output and
the figure file does not know it. Part X answers it with a small set of
named output targets declared once per project. This item moves well up
the build order as a result.

### VI.3 Report element counts, against a per-metaphor reference range

Nodes, edges, distinct colours used, words of text. A schematic with six
nodes and one with forty are different problems, and right now neither
the author nor the aid can see which one it is looking at. Fits the
measure-never-place contract exactly.

**A bare count means little.** "14 nodes" tells an author nothing.
"14 nodes; the pipeline exemplar has 6" tells them something immediately.
So the aid should report the count **alongside the same count taken from
that metaphor's exemplar** (VI.4), which makes VI.3 and VI.4 mutually
reinforcing rather than merely adjacent in the build order.

**Ranges are per metaphor and are not budgets.** A general-purpose
diagram tool can say "max 9 nodes" because its figures are editorial. A
textbook DP-table trace has forty cells and is correct. The reference
range describes what the exemplar does; it does not authorise a finding
when a figure exceeds it, and it must never become a gate.

**To settle:** whether "distinct colours used" should count palette
members only or every colour expression appearing in the source. The
second is easier and noisier.

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

**Second use.** The exemplar is where VI.3's reference range comes from,
so the two should be filed together or in immediate succession.

### VI.5 Routing findings

**The gap this closes.** `TIKZ-STYLE.md` leaves three defects to human
judgement — chaotic routing, illegible or inconsistent type, and literal
copying — and Part VIII proposes a vision model to reach the first two.
That framing was too pessimistic. Once the routing rules are stated
precisely, most of "chaotic routing" is plain geometry, measurable from
the same probe output the aid already reads.

**Findings this aid can report, none of which needs vision:**

| Finding | What it measures |
| --- | --- |
| Label sitting on its connector | Gap between the label's bounding box and the nearest point of the edge it annotates, in millimetres. A label with zero clearance hides the line it describes |
| Shared attach point | Two or more edges meeting a node's boundary within some small distance of each other, so the reader cannot tell them apart |
| Transit over a non-endpoint node | An edge whose path crosses the bounding box of a node that is neither its source nor its destination |
| Coincident edges | Two edges running along substantially the same path, so one hides the other |
| Off-axis straight connectors | Edges between nodes sharing neither an x nor a y coordinate, drawn as a single straight segment rather than an orthogonal path — relevant to the metaphors where orthogonal routing is the convention, not to all of them |

**Report the measurement, not a verdict.** "Label `WRITE` sits 0.0 mm
from its edge" is a finding. "Bad routing" is not. Each of the above is a
number or a pair of node names, in the style the layout aid already uses.

**The false-positive floor this inherits, and it is a real one.** The
probe reads node boxes from the pdflatex log. A TikZ node's recorded box
does not account for stroke width, arrowheads, or decoration bleed. The
same class of error is documented in `diagram-design`'s renderer linter,
which found that a geometric bounding box both misses real clipping and
invents clipping that is not there, and moved to a paint-based
comparison. Chitragupta will hit this in the opposite direction: a label
that clears the node box by 0.1 mm may still be overprinted by the
arrowhead. Expect it, write it into the bench, and consider whether the
rasterisation route (`pypdfium2`, already declared) is the honest measure
for the clearance findings specifically. If Part XI ships, it already
produces a rendered form per figure, and the two should share one path
rather than compiling the same figure twice.

**Where the convention varies by metaphor.** Orthogonal routing is right
for a pipeline and wrong for an automaton, where curved transitions and
self-loops are the convention. The off-axis finding must therefore be
metaphor-aware, which is another reason II.0's per-metaphor doc split
should land early.

**Why this matters beyond its own value.** It removes two of the three
things Part VIII exists to reach, which shrinks the most expensive and
least deterministic item on the roadmap to roughly one thing:
informativeness.

### VI.6 A pre-output checklist, and a named anti-pattern table

**The gap.** The project has scaffolds (before drawing) and review aids
(after drawing) and nothing in between. Nothing tells the author or the
model what to verify at the moment of emitting a figure. Every existing
check is post-hoc, which means every defect it catches has already been
written.

**Proposal, in two halves, neither of which needs code:**

- **A pre-output checklist** in the skills: the questions to answer
  before emitting a figure. Does this need to be a figure at all, or
  would a paragraph or a table do the job better? Is this the right
  metaphor? Does every node carry an explicit `(name)`? Does the twin
  carry the same information, not the same picture? Does the caption
  state a takeaway? Is the accent colour doing one job or five? The
  delivery mechanism already exists: #464 taught nine skills the equation
  markers.
- **A named anti-pattern table** in `TIKZ-STYLE.md` and, after II.0, in
  each metaphor's own doc. Failure mode in one column, why it fails in
  the other. A table of named failures teaches a model considerably
  better than the same content as prose, and it gives review findings
  something to name.

**Why this is near the top of the build order.** It is the second-cheapest
item on the roadmap after VI.4, it needs no new code, and unlike every
aid here it acts before the defect exists rather than after.

**One thing to be careful about.** A checklist is a hair's breadth from a
gate, and the standing checkbox in the feature-request template exists
because that drift is easy. The checklist is guidance to an author, not a
predicate anything evaluates. If someone later wants to mechanise a line
of it, that is a new aid with its own issue and its own bench, not a
promotion of the checklist.

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
- **The encoding claim is checkable here too.** A bar chart claims length
  encodes value, the same way II.3 claims width encodes bit count. The
  same relative-error check applies, and if II.3 ships first the
  machinery is already written.
- **Confirm which texlive package ships pgfplots** and whether
  `scripts/install_full_pipeline.sh` needs a line. `texlive-pictures`
  covers the tikz libraries; do not assume it covers this.

---

## 👁 Part VIII: Where a vision model earns its place

### The one place it belongs — now smaller than it was

`TIKZ-STYLE.md` leaves three defects to human judgement: chaotic routing,
illegible or inconsistent type, and literal copying. This part originally
claimed a vision model was the only mechanism that reached the first two.
That is no longer true:

- **Chaotic routing** is largely geometry. See VI.5.
- **Illegible type** is arithmetic once the output target is known. See
  VI.2 and Part X.
- **Literal copying** has its own deterministic-ish path. See Part IX.

What remains, and it is genuinely beyond geometry, is **informativeness**:
whether the figure teaches the thing it is supposed to teach, and the
twin-equivalence test the style doc frames as reading the `.txt` and
asking whether the point still arrives. That is a smaller and better-posed
job than "look at the figure and judge it", and it should be filed that
way.

### Vision-critique mechanism

- `pypdfium2` is already a declared dependency of the `enrich` extra
  (added for the crop work in #600/#602), so rasterising the probe's
  compiled PDF needs no new package. VI.5 may want the same rasterisation
  for its clearance findings, so the two should agree on one path.
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

Nor does it belong anywhere in Part III. A derived figure that consults a
model is a generated figure with extra steps, and loses the property that
makes derivation worth building.

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

**A self-inflicted floor this roadmap now creates.** The `pic` library
(V.1) means every figure using the shared memory-cell `pic` shares
pixel-identical regions with every other one. That is the library working
as intended and it is indistinguishable from copying at the pixel level.
It needs handling by construction rather than by threshold: the screen
should exclude regions drawn from the shared library before hashing,
rather than trying to tolerate them afterwards. This is a further
argument for benching Part IX before V.1 ships.

**Part XI makes the mechanism cheaper.** A rendered raster per figure is
exactly what the screen needs, so if Part XI lands first, Part IX
inherits the rasterisation path instead of building its own.

---

## 📐 Part X: Output targets

**New in revision. Small, and it unblocks two other items.**

### The gap in output targets

Several checks want to know the size at which a figure will actually be
printed, and no artefact holds that number. VI.2 cannot report an
effective type size without a column width. VI.5's clearance findings are
in millimetres on the page, not in TikZ units. Part XI's PNG branch needs
a width and a resolution before it can rasterise anything. Each of those
items has independently parked on "where does the target width come
from", which is a sign the answer belongs in one place rather than three.

### The proposal

A small, closed set of **named output targets**, declared once per
project rather than per figure, each fixing a column width and a base
type size. Something like: a single-column book page, a wide or
full-bleed page, a two-column paper, a slide. The names matter less than
the properties: the set is small, it is closed, it lives in project
configuration, and every size-dependent check reads it.

`diagram-design` does the same thing with a `size` dial whose options
also drive the type ramp, so a projected slide gets larger node labels
than an inline document figure. The observation worth stealing is that
the target changes **type size**, not just the frame: a figure scaled
down to fit is a different figure from one authored for that width.

### To settle

- **Where the declaration lives.** Project config is the obvious home,
  but a book with one full-bleed foldout needs a per-figure override, and
  an override mechanism is where this gets complicated.
- **Whether a figure can declare its own target.** Probably yes, probably
  rarely, and probably as an explicit exception that the aid reports so
  it does not go unnoticed.
- **Interaction with fragment portability.** A figure `\input` into a
  foreign thesis lands in a column of unknown width. The target is a
  property of *this* project's output and the figure should not hard-code
  it into geometry — it informs the checks, not the drawing.

### Why it is worth its own part

It is a handful of constants and a config key, and it is a prerequisite
for VI.2 and part of VI.5. Filing it as a shared dependency avoids three
issues each inventing their own answer.

---

## 🖨 Part XI: Rendered figure images in md, html and docx

**New in revision.** Today `md`, `docx` and `html` output render only the
ASCII twin. The TikZ form reaches the PDF and nowhere else. This part
proposes rendering each figure to SVG or PNG and shipping that image
alongside the twin in the non-PDF outputs.

### Most of the plumbing already exists

- The probe already compiles each figure under a minimal preamble to read
  node boxes out of the pdflatex log, so a compiled PDF per figure is a
  by-product of a path that already runs.
- `pypdfium2` is already declared in the `enrich` extra.
- `_pandoc.py` already sets `--resource-path` so the PDF and DOCX writers
  resolve Markdown image syntax pointed at a file on disk.

As with raster images generally, what is missing is the **contract**, not
the plumbing.

### The argument for it is not the obvious one

The obvious argument — html readers should see the picture — is true but
weak. The stronger one is that this **removes a conflict the twin
currently has to absorb**.

The twin is asked to do two incompatible jobs: be the clearest 7-bit
representation of the information, and be visually adequate as the *sole*
figure in md, html and docx. Those pull opposite ways. II.4 argues an
automaton's twin should be a transition table because a table is more
precise than the picture — and a transition table standing alone in an
html export, where the reader's browser could have shown the diagram, is
a worse export. Ship both and each form does one job: the twin is the
precise representation, the image is the picture. The II.4 and VII
principle stops being a compromise.

### The erosion risk, and the structural fix

Once the image is what a reader sees in md and html, the twin stops being
load-bearing for anyone except screen-reader users, and an artefact
nobody looks at rots. Six months of stale twins would be invisible.

The mitigation must be structural rather than cultural: **the twin
becomes the image's alternative text.** `alt` in html, the alt-text field
in docx, image plus fenced twin in Markdown. That makes the twin a
required input to the image rather than a substitute for it, so it cannot
rot without the image visibly losing its accessible name — which is
itself checkable.

### Tradeoffs, in rough order of seriousness

- **A LaTeX toolchain becomes a dependency of every output path.** Today
  a person can render Markdown with no TeX installed, because the figure
  probe lives in the review layer and review is optional. Rendering
  images makes pdflatex plus a converter a prerequisite for producing any
  output at all. This is an architecture decision, not a feature
  decision, and it is the largest single question in this part. The
  honest answer is a documented fallback: **with no TeX available, emit
  the twin exactly as today and say so.** Degraded output, reported, not
  a failure.
- **Generated binaries versus diffs.** Committed renders are generated
  artefacts that drift from source; built renders require the toolchain
  everywhere. Worse, pdflatex output is not byte-reproducible across TeX
  distributions and font versions, so a committed SVG shows spurious
  diffs on a colleague's machine. Cache keyed on a content hash of the
  `.tex`, and treat the cache as build output rather than source. The
  same instinct keeps golden images out of `diagram-design`'s repo:
  nothing to re-record means nothing to go stale.
- **SVG and PNG are different answers and both are probably needed.** SVG
  suits html — it scales, stays small, and keeps label text selectable
  and searchable, *but only if the converter embeds fonts rather than
  converting glyphs to paths.* Several `dvisvgm` configurations default
  to paths, which silently destroys that property. Verify it rather than
  assuming it. PNG is the safer choice for docx, where SVG support across
  Word and the pandoc writer is jointly unreliable.
- **PNG re-raises Part X's question; SVG dodges it.** A raster needs a
  target width and a resolution, which is exactly the "where does the
  column width come from" blocker VI.2 had. SVG needs neither. That
  argues for SVG-first, with PNG only on the path where SVG cannot go.
- **The numbering contract must not be bypassed.** A figure arriving as
  plain Markdown image syntax gets no number, no marker, no caption
  check. So this cannot be "insert an image tag": the rendered image must
  flow through the same `figureref` machinery, with the renderer still
  assigning the number and the caption still pandoc-visible per #535.
  That is the real work here, and it is larger than the rendering step.
- **Review-pass cost**, per `PERFORMANCE.md`. Hash-keyed caching should
  make this negligible after a first pass, but that needs measuring
  rather than assuming.

### One thing it gives away free

A rendered raster per figure is precisely what Part IX's similarity
screen needs, and what VI.5 may need for its clearance findings. If this
lands first, both inherit the path instead of building one.

### Shape of the proposal

SVG-first with a PNG branch for docx; twin-as-alt-text mandatory rather
than conventional; TeX-absent falling back to today's behaviour with a
report; renders cached by content hash and never committed; the whole
thing routed through the existing figure numbering contract.

**Depends on Part X** for the PNG branch, which is unanswerable without a
target width. The SVG branch does not.

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

**The carve-out is about objects, not about origin.** Any fixed shape —
hand-drawn, or generated by a derivation — may use explicit coordinates
inside its own definition. The boundary is the `pic`, not the authoring
method.

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

**The corollary is sharper than it looks, and it decided two proposals in
this revision.** If the twin must carry the same *information*, then
anything the TikZ form conveys and the twin cannot is a rule violation
rather than a stylistic loss. That is what ruled out an icon set, since
an icon must then be strictly redundant with its label and therefore adds
nothing. And it is what Part XI has to respect from the other direction:
shipping a rendered image into `md` and `html` is only acceptable while
the twin remains a complete representation, which is why the twin becomes
the image's alt text rather than an alternative to it.

---

## 📎 Borrowed, with attribution

This project maintains a provenance spine and is proposing, in Part IX, a
checker for figures that borrow without attribution. A roadmap that
silently adopted another project's design rules while building that
checker would be a poor look. So, explicitly:

**Source.** [`cathrynlavery/diagram-design`](https://github.com/cathrynlavery/diagram-design),
MIT licensed. An agent skill that produces self-contained HTML with
inline SVG for editorial and product diagrams, with brand-matched design
tokens.

**Relationship: ideas, not a dependency.** Nothing from it is vendored,
imported or installed, and there is no reason to. The output substrate is
wrong (HTML/SVG on a 4-pixel grid versus TikZ compiled by pdflatex and
measured in millimetres); the palette model is wrong (brand-matched
tokens versus a fixed five-colour Okabe-Ito palette that must travel
inside the figure file); and the generation model is wrong for Part III
(an LLM picks the type and the cuts, where a derivation must be
deterministic). What transfers is design reasoning, a few hundred words of
it, embedded in a repository whose bulk is coordinates for a different
medium.

**What was taken, and where it landed:**

| Idea | Landed in |
| --- | --- |
| Connector rules stated precisely enough to check: label-to-line clearance, fanned attach points, no transit over non-endpoint boxes, no coincident strokes, orthogonal elbows | VI.5, and the consequent narrowing of Part VIII |
| Named output sizes that fix both frame and type ramp | Part X, unblocking VI.2 |
| A complexity budget expressed per diagram type | VI.3's per-metaphor reference range, deliberately as a report rather than a budget |
| A fixed degrade ladder and a fidelity ledger for reductions | Part III, answering the dependency-graph filtering question |
| A pre-output taste gate distinct from post-hoc linting | VI.6 |
| Anti-patterns as a named table with a "why it fails" column | VI.6 |
| One reference document per type, loaded only when chosen, with a sync check | II.0 |
| A geometric check that verifies an encoding's own claim, measured as relative error | II.3's field-width check, and VII's bar lengths |
| Bounding-box geometry is an unreliable oracle for clipping and clearance | VI.5's false-positive warning |
| Behaviour patterns kept separate from layout types so the type count does not inflate | II.7 demoted from a metaphor to a primitive |
| No golden images in the repository, so there is nothing to re-record and nothing to go stale | Part XI's hash-keyed render cache, treated as build output rather than source |

**What was rejected, and why**, so nobody re-derives it: brand-token
onboarding (this project has a fixed palette by design, for greyscale
legibility); the 4-pixel grid (a print artefact has no pixel grid); a
target density of 4/10 (correct for editorial diagrams, wrong for a DP
trace); motion and animation (print); the no-shadows / max-radius
aesthetic (tied to a web look, and this project's figures are line art
already); and its export path (Playwright and Chromium for a project that
compiles PDFs).

One footnote worth recording. That project's own "when not to use this"
list sends quick unicode diagrams to a different tool. That tool's job is
this project's ASCII twin, which is mandatory rather than optional here.
Its taste rules were never designed to survive a twin requirement, which
is the main reason its aesthetic guidance transfers so much less well
than its mechanical guidance.

**Third-party art.** None is proposed. Heroicons was evaluated in this
revision and set aside; the argument is in the table below, and it is
worth reading before anyone proposes an icon set again, because the
technical fit is good enough to be tempting.

---

## 🚫 Considered and set aside

Recorded with the argument, so nobody re-derives it.

| Proposal | Why not |
| --- | --- |
| **Licensed vector art libraries for life-sciences** (Bioicons ~3,000 CC0/CC-BY icons, Servier Medical Art CC BY 4.0, NIH BioArt public domain, PhyloPic) | Correct answer for a life-sciences pipeline, irrelevant here. The attribution machinery would have been a good fit for this project's provenance spine, which is the only reason it was considered at all |
| **A general icon library for CS figures**, e.g. Heroicons (MIT, ~300 icons) | Re-opened in this revision and set aside again, with a better argument than the first time. The technical fit is real: Heroicons' 24px outline set is `M`/`L`/`C`/`A`/`Z` path data, which is the subset TikZ's `\path svg {...}` parses natively, so an icon converts to a `pic` with no new package, no raster and a diffable source. But feasibility is not a reason. Because the ASCII twin cannot render an icon, an icon must be strictly redundant with its node's text label — and a mark that adds no proposition is a mark the TikZ form also loses nothing by deleting. Set against that: a Part IX false-positive source needing whitelisting by construction, exclusions in VI.3's counts and Part IV's label extraction, stroke rescaling tied to Part X, a silent axis flip (SVG's y-axis points down), and a vendored subset with a licence notice to carry. Five ongoing obligations across four other parts, bought for pre-attentive scanning in one metaphor family. Worse, it would be the first proposal to make the twin strictly poorer by design, which is a precedent later proposals would argue from. Coverage is also UI-shaped — no page table, no pipeline hazard, no red-black node — and upstream declines new-icon contributions, so there is no route to a domain icon. What survives is [V.2](#v2-a-few-domain-shapes-not-an-icon-set): two or three house-drawn shapes in the `pic` library |
| **Generated raster illustration** | Non-deterministic, non-diffable, non-editable, and factually unreliable in exactly the domain where a mislabelled figure is worse than no figure. Fails the properties `SOUL.md` is built on. The narrower "generate a base plate and trace it" version reintroduces the originality problem of Part IX and still needs an illustrator |
| **Bezier organic form, gradients, translucency** | Illustrator craft. Reachable in TikZ in principle, but a cell membrane's curve requires hand-placed control points and this domain has no organic objects to draw. Dropped entirely |
| **`detikzify` or image-to-TikZ synthesis** | The inverse of Part IX: it automates producing the artefact that check exists to catch |
| **Vision captioning of source figures at parse time** | Rejected in #627. Puts generated text in the corpus layer, which may not call an LLM |
| **Nature-style data density as the benchmark** | Wrong target for tutorials and textbook chapters. A teaching figure is explanatory, not evidential. Tufte and the algorithms literature are the better references. Part VII keeps the quantitative capability for the thesis genre without making density the goal |
| **A figure-similarity gate** | See Part IX. Advisory and ranked only. #130 forbids guessing a threshold and the measured evidence says none exists |
| **Adopting `diagram-design` as a dependency or an invoked skill** | See [Borrowed, with attribution](#-borrowed-with-attribution). Wrong output substrate, wrong palette model, and an LLM in a path Part III needs to be deterministic. The design reasoning was worth taking; nothing else was |
| **A hard complexity budget with numeric caps** | Correct for editorial diagrams, wrong for a textbook. A forty-cell DP trace is not over budget, it is a DP trace. VI.3 reports the count against a per-metaphor reference range instead, and nothing gates on it |

---

## 🗺 Build order

Ordered by a mix of certainty, size and what unblocks what. Revised: the
cheap non-drawing items moved up, and Part VIII moved down as VI.5 took
most of its scope.

1. **Part I — listing and algorithm classes.** Smallest, most certain, a
   correctness gap rather than a quality one. Parts III and IV both want
   the marker vocabulary stable underneath them.
2. **Part VI.4 and VI.3 — exemplar figures, then element counts against
   them.** Nearly free. VI.4 needs no new code and is plausibly the
   largest single perceived-quality jump available; VI.3 is what gives
   its counts meaning. File them in that order or together.
3. **Part VI.6 — pre-output checklist and anti-pattern table.** No code
   at all, and the only item on the roadmap that acts before the defect
   exists rather than after.
4. **Part II.0 — split the metaphor docs.** Cheap now, expensive after
   Part II ships, and every later metaphor depends on the shape.
5. **Part X — output targets.** A handful of constants and a config key.
   Unblocks 6 and part of 7.
6. **Part VI.1 and VI.2 — caption shape, then type size at final scale.**
   VI.1 is the best ratio of informativeness to code on the roadmap;
   VI.2 is arithmetic once 5 lands.
7. **Part VI.5 — routing findings.** Deterministic, reuses the existing
   probe, and removes most of Part VIII's scope. Bench the
   bounding-box floor first.
8. **Part V.1 — the `pic` library.** Structural, compounding, and a
   prerequisite for II.1. Settle the portability question first.
9. **Part II.1 — state sequence.** Highest-value metaphor. Depends on 8.
10. **Part II.2, II.3, II.4 — sequence diagram, bit-field, automaton.**
    Mostly a scaffold plus the right library load. II.3 may carry a
    renderer change (`bytefield`) and carries the width-encoding check;
    II.4 is the best derivation target. II.7 ships as a primitive inside
    8, not as a metaphor.
11. **Part IV — correspondence.** Wants 1 done, and wants II.3/II.4
    figures existing to check against.
12. **Part III — derived figures.** The distinctive feature, but it
    compounds on everything above. The ledger and the ladder ship with
    the first derivation, not after it.
13. **Part XI — rendered figure images.** Sits anywhere after 5, since
    the PNG branch needs Part X and the SVG branch does not. Placed here
    because it hands a rasterisation path to both 14 and VI.5, so
    building it earlier saves work in two places. The architecture
    question — whether a LaTeX toolchain may become a dependency of every
    output path — should be settled before the issue is written, not
    inside it.
14. **Part IX — figure similarity.** Independent of everything else, and
    may close on its own bench numbers. **Bench it before V.1 ships**,
    since the shared `pic` library plants a known false-positive source.
15. **Part VII — quantitative panels.** Real, lower priority for this
    genre mix. Reuses II.3's encoding check.
16. **Part VIII — the informativeness critique.** Now much smaller than
    it was. It judges quality rather than creating it, so it lands
    better once there is more quality to judge.

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
- **Routing-finding false-positive floor (VI.5).** Run each proposed
  finding over the existing figures and the six scaffolds, which are
  known-good. Any finding that fires on a scaffold is either a real
  defect in the scaffold or a broken check, and both outcomes are
  informative. Include cases that must **not** fire — a legitimate
  crossing, a lifeline with many arrows at one x-coordinate, an automaton
  self-loop — and make them the majority of the bench, the way a checker
  that only tests positives learns nothing about its own noise.
- **Bounding box versus paint (VI.5).** Measure how far a node's recorded
  box diverges from its inked extent once stroke width and arrowheads are
  counted, on real figures. That number decides whether the clearance
  findings can use the log or need rasterisation.
- **Correspondence false-positive floor (Part IV).** Run the two-way set
  difference over existing figures and their sections. Legitimate
  mismatches will dominate; the question is whether the signal is visible
  above them.
- **Figure-similarity floor and recall (Part IX).** Rank the 8,769 crops
  against each other to establish the noise level, plus a planted TikZ
  redraw of a known corpus figure to confirm it ranks above it. Add a
  figure built from shared `pic`s as a known negative, since V.1 creates
  that floor deliberately.
- **Render cost and cache hit rate (Part XI).** Time a full render of the
  15-chapter book with a cold cache and with a warm one. The cold number
  decides whether a TeX-absent fallback is a nicety or the common case;
  the warm number decides whether this is viable in an edit loop at all.
- **Whether SVG keeps text as text (Part XI).** Convert a scaffold and
  check whether labels survive as selectable text or arrive as outlined
  paths. If they are outlined, the accessibility and searchability
  arguments for SVG-first evaporate and the choice between SVG and PNG is
  reopened. This is one command and should be run before the issue is
  written.
- **Encoder choice (Part IX)**, in the style of
  `bench_embed_model_compare.py`. A CLIP-class model trained on natural
  images may be weak on line art, which is an empirical question rather
  than a guess.
- **Element-count spread (VI.3).** Before deciding what a reference range
  even means, count nodes, edges and colours across the existing figures
  per metaphor. If the spread within one metaphor is as wide as the
  spread between metaphors, the per-metaphor range is not carrying
  information and VI.3 should report bare counts after all.
- **Review-pass cost** for anything added, per
  `PERFORMANCE.md`'s "What a review pass costs".
