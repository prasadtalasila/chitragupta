# 🖼 Figure quality: what has shipped, and what is still open

Status: **proposal.**

**Written for** someone deciding what to build next in the figure system,
or deciding whether a proposal already considered here is worth
re-opening. The first section lists what exists. Every open subsection
after it is sized to become one feature request on its own. Nothing here
has been measured on the corpus unless a section says so explicitly and
names the artefact that holds the number.

**Scope decision that shapes everything.** This project will mostly be
used to write technical books in **engineering, computer science and
software engineering**, optimising for the tutorial and textbook-chapter
genres, without restricting the thesis-chapter genre. Several proposals
that would be correct for a life-sciences or an empirical-results
pipeline are wrong here. They are recorded in
[Considered and set aside](#-considered-and-set-aside) instead of
deleted, so nobody has to re-derive the argument.

## 🧭 Table of contents

- [What has shipped](#-what-has-shipped)
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
- [A rule that may have to bend](#-a-rule-that-may-have-to-bend)
- [Borrowed, with attribution](#-borrowed-with-attribution)
- [Considered and set aside](#-considered-and-set-aside)
- [Build order](#-build-order)
- [What needs measuring first](#-what-needs-measuring-first)

## ✅ What has shipped

Each row was once a proposal on this page, or the reason for one. The
page that documents it now is in the last column. A proposal that
duplicates one of these is not worth filing.

| Item | What exists | Documented in |
| --- | --- | --- |
| Scaffolds | Eleven known-good scaffolds in `assets/tikz/`, one per layout, each with its ASCII twin and a `% cg-layout:` line: pipeline, map, layered stack, control loop, branching tree, hub-and-spoke network, zoned spine, state machine, comparison, sequence and timeline | [assets/tikz/README.md](../assets/tikz/README.md) |
| Sequence diagram (was II.2) | The `sequence` layout: lifelines, level messages, dashed replies | [TIKZ-STYLE.md](TIKZ-STYLE.md#-commit-to-a-layout-metaphor-before-you-draw) |
| State machine (was II.4) | The `state-machine` layout in pure TikZ (`cgstate`, `cgaccept`, `cgstart`), with a transition table as its twin | [TIKZ-STYLE.md](TIKZ-STYLE.md#-the-house-figure-style) |
| Comparison and timeline | Two more layouts: matched parts in two panels, and events placed by fraction along a time axis | [TIKZ-STYLE.md](TIKZ-STYLE.md#-commit-to-a-layout-metaphor-before-you-draw) |
| Exemplars (part of VI.4) | Seven finished figures in `assets/tikz/exemplars/`, laid out to the render's 453pt | [assets/tikz/README.md](../assets/tikz/README.md) |
| House style block | `assets/tikz/cg-figstyle.tex`: the Okabe-Ito palette, a `Line` and a `Text` shade per hue that clear WCAG 3:1 and 4.5:1, node roles, zone cards, edges, tags and compact spacing. Every figure carries it | [TIKZ-STYLE.md](TIKZ-STYLE.md#-the-house-figure-style) |
| Domain shapes (was V.2) | Five house `pic`s (store, docs, funnel, chip, shield), each drawn into a named `cgwell`. They travel inside the house block, so a figure stays one self-contained file | [TIKZ-STYLE.md](TIKZ-STYLE.md#-house-shapes-and-the-well-they-sit-in) |
| `figure sync` | Stamps and refreshes the house block in figure files, and refuses to touch a block edited by hand | [CLI.md](CLI.md#-chitragupta-figure-sync) |
| `figure new` and `figure look` | Start a figure from a scaffold; see it alone on the render's page, or on the draft's own page | [CLI.md](CLI.md#-chitragupta-figure-new) |
| `figure check` | 36 numbered rules (28 objective, 8 advisory) with reasoned `% cg-allow:` exceptions. It covers routing (was VI.5: `c1` to `c7`), contrast, the type floor, off-palette colours and tints, wording, and agreement between a figure and its twin | [figure-checks/README.md](figure-checks/README.md) |
| Element counts (most of VI.3) | Node and edge counts, height and slack, reported beside each layout's reference range and never as a cap | [figure-checks/size.md](figure-checks/size.md) |
| Per-layout reference files (was II.0) | One file per layout with its anti-patterns and reference ranges, and a pattern-to-layout router, under `.claude/skills/figure-drawer/references/` rather than `docs/figures/` | [FIGURE-DRAWER.md](FIGURE-DRAWER.md#-what-the-skill-reads) |
| Taste gate and anti-patterns (was VI.6) | Questions the skill answers before drawing anything, and a named anti-pattern list per layout | [FIGURE-DRAWER.md](FIGURE-DRAWER.md#-what-it-does-step-by-step) |
| The `figure-drawer` skill | One skill that every genre hands a figure to | [FIGURE-DRAWER.md](FIGURE-DRAWER.md) |
| Panels, numbering and captions | Panel letters in both forms; the renderer numbers figures; prose points via `<!-- figureref: name -->`; a figure with no caption is reported | [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10 |
| Millimetres inside a `pic` | Relative placement governs composition; explicit coordinates are allowed inside a `pic` definition | [TIKZ-STYLE.md](TIKZ-STYLE.md#-commit-to-a-layout-metaphor-before-you-draw) |
| The twin as a representation | A twin is the clearest 7-bit form of the information, not a tracing: `state-machine.txt` is a transition table | [assets/tikz/README.md](../assets/tikz/README.md) |
| Source-figure crops | Source-PDF figure crops, and `draft figures <citekey>` to look at them while drafting | [CLI.md](CLI.md#-chitragupta-draft-figures) |

## 📐 Where figures stand today

The open parts below have to preserve three properties:

- **Every figure has two forms.** A TikZ form and a 7-bit ASCII twin.
  `md`, `docx` and `html` output render only the twin
  ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10).
- **The checker measures, never places.** `figure check` compiles the
  figure with LuaLaTeX and reads back where every node and line landed.
  It never moves anything.
- **Nothing is a gate.** `figure check` exits 0 whatever it finds, and
  the feature-request template carries a standing checkbox against
  promoting a new check into one.

And these facts about the tree:

- Numbered artefact classes are exactly three: `figureref`,
  `equationref` and `tableref`. There is no listing or algorithm class.
- The renderer adds `\usepackage{tikz}` plus the union of the
  `\usetikzlibrary` names its figure files ask for (#781),
  conditionally, via `header-includes` in `render_output/_pandoc.py`.
  `fvextra` is added by the same mechanism for a draft with a code block.
- `\usetikzlibrary` is legal in the document body, so figure files
  *name* the libraries they need and the renderer hoists them into the
  preamble; loading one inside the `figure` float is #781's bug, since
  a float is a group. `\usepackage` is not body-legal at all, which makes
  any new package a renderer change and not a figure-file change.
- There is no `pgfplots`, no `matplotlib`, no data file and no axis
  anywhere in the figure path.
- Raster images already survive the renderer: `_pandoc.py` sets
  `--resource-path` so the PDF and DOCX writers can resolve Markdown's
  image syntax pointed at a raster file. What is missing is the
  **contract**, not the plumbing: such an image gets no number, no
  marker, no twin, no caption check.

## 🕳 The gap, stated precisely

The eleven layouts cover connection (pipeline, stack, loop, tree, hub,
spine, state machine), comparison (map, comparison) and order in time
(sequence, timeline). Three forms that carry much of the load in a CS or
SE textbook are still not expressible:

- **The same structure drawn at N successive moments**, with the
  differences marked. Heap sift-down, red-black rotations, a DP table
  filling in. This is the dominant figure form in the algorithms
  literature.
- **A resource against time.** Instructions against cycles, a scheduler
  trace, Gantt-shaped occupancy. A sequence diagram puts parties against
  time; this puts a grid of resources against it.
- **Layout drawn to scale.** A packet header, a struct, a stack frame, a
  page-table entry. Widths carry meaning.

Two further observations change the problem for this domain, and both
make it easier:

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
faithfully in 7-bit. The rule that would cap a biology pipeline is nearly
free here, and the roadmap below should be read as *endorsing* it, not
working around it.

---

## 📑 Part I: Two missing artefact classes

### The gap

A code listing is typographically handled: `_pandoc.py` detects
`has_code_block` and loads `fvextra` with `breaklines` so an over-wide
verbatim line wraps instead of running into the margin. But a listing
cannot be **numbered or referenced**. In a technical book, "Listing 4.2
shows the retry loop" is as frequent as "Figure 4.2 shows". With no
class, an author either hand-numbers it, which is the failure the
figure and equation numbering contracts existed to eliminate, or writes
"the code above", which breaks the moment a page splits or a section is
reordered.

The same argument holds for a pseudocode algorithm, which in this
literature is a distinct artefact from both a listing and a figure.
`WRITING-STANDARDS.md` already has to reason about pseudocode as a
special case (the seven-line pseudocode listing that is the shortest
false positive for one of its checks), which is a sign the concept is
already relied on without being a first-class artefact class.

### Proposal

Add `listingref` and `algorithmref` alongside the three existing classes,
with the identical contract:

- The renderer assigns the number. The author never writes one.
- Prose points at the artefact with `<!-- listingref: name -->` /
  `<!-- algorithmref: name -->`.
- A reference-in-prose check reports an artefact nothing points at, and a
  marker pointing at nothing.
- Every genre skill learns the vocabulary, the way the equation-numbering
  change taught nine skills the equation markers.

### Details worth pinning down before filing

- **Caption or title?** A listing conventionally carries a title above
  it, not a caption below. Decide whether the caption-presence check
  applies, and whether the ASCII/`md` route can express the distinction
  at all.
- **What is an algorithm's second form?** A figure has a TikZ form and an
  ASCII twin. Pseudocode is already text, so there is no twin to keep in
  sync. This class is simpler than figures, and the simplification
  should be explicit, not accidental.
- **Ordering interaction.** Four numbered classes sharing one document
  means four independent counters. Confirm the existing counter machinery
  generalises instead of assuming it.

### Why this is first

It is a correctness gap, not a quality one. It is also the smallest
item on this roadmap, and Parts III and IV both want a stable marker
vocabulary underneath them.

---

## 🧱 Part II: The metaphor vocabulary

Each subsection below is one new row in `TIKZ-STYLE.md`'s metaphor table
plus one scaffold in `assets/tikz/`, and each is independently
fileable. `tests/test_tikz_scaffolds.py` already enforces that the table,
the directory and the per-layout reference files agree, so a row cannot
ship without a scaffold and a reference file.

Common requirements for all of them:

- The scaffold compiles standalone, ships with its ASCII twin and a
  `% cg-layout:` line, and reports no finding from `figure check`.
- Nodes are placed relative to one another. No hand-computed millimetre
  coordinates outside a `pic` definition.
- Every node carries an explicit `(name)`, so a finding can name it.
- The `\usetikzlibrary` load sits at the top of the figure file, above
  the `tikzpicture`, which is where the renderer reads it from (#781)
  and what makes the scaffold compile standalone.
- A new layout that exempts a connector rule says so in
  `chitragupta/figure/_rules.py`, with the reason.

### II.1 State sequence (algorithm trace)

**The form.** One structure, N snapshots, differences marked. The single
most common figure in the algorithms literature and the highest-value
addition on this roadmap.

**Why it is not just panels.** Panel lettering letters panels as siblings. A
snapshot is not a sibling: it has an ordinal, a predecessor, and a
delta from it. The figure's whole meaning is the difference between
adjacent frames, and a reader needs to see which nodes changed.

**Mechanism.** The sound version is a `pic` (see Part V) drawn once per
frame with a per-frame highlight set, laid out left to right or in
wrapped rows, with the changed elements taking the accent colour. Without
`pic` reuse the author redraws the structure N times by hand and the
frames drift, which is the defect this metaphor exists to prevent. **This
subsection therefore depends on Part V** and should not be filed before
it.

**Twin strategy.** N ASCII frames stacked vertically, each with its
ordinal, and the changed elements marked with a character instead of a
colour. This works, and is arguably clearer than the TikZ form.

**Element counts do not apply here.** Whatever reference range a
pipeline's scaffold sets, a DP-table trace legitimately has forty
cells. The per-metaphor range is the point; a single global budget would
be wrong for exactly this metaphor.

**Open question.** Whether the highlight-the-delta step can be derived
instead of hand-specified. Given frames as data (Part III), the delta is
a set difference, so a derived trace could mark its own changes. That is
the strongest single argument for Part III.

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
`figure check` could compare each field's drawn width against its share of the
total and report the discrepancy. Two details decide whether it is
useful:

- **Relative, not absolute, error.** An absolute measure passes exactly
  the narrow fields most likely to be wrong. A one-bit flag drawn at
  four bits' width is a 300% error and a sub-millimetre one.
- **Rounding is legitimate.** A 3-bit field in a 32-bit header cannot
  always land on a clean grid. Report the number; do not band it.

This is the strongest deterministic figure check on the roadmap and is a
better version of Part IV's correspondence idea, because it compares the
figure against itself and not against prose.

**Correspondence opportunity.** A bit-field figure usually depicts a
struct or a spec table that also appears in the chapter as code. Field
names and widths are checkable against it. See Part IV.

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
specific compartment of a node instead of from the node's edge, which
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
are all the same form, and none of the eleven layouts can express
it because text lives *inside* boxes.

**It is a primitive, not a metaphor.** Annotation
composes with every other metaphor instead of competing with them. A
sequence diagram can carry a callout; so can a bit-field. Filing it as a
new row in the selection table would be a category error and would
push authors to choose it *instead of* the right metaphor. It belongs in
Part V's library as an annotation `pic`, with a line in the shared rules
instead of a metaphor row of its own.

**Mechanism.** `pin` and the `quotes` library for leader lines; TikZ's
`spy` library for the magnification callout. Both ship in
`texlive-pictures`.

**Twin strategy.** A label list with each label's relation to the object.
Not character art.

**Budget.** Two callouts per figure is a reasonable starting reference
range; past that the labels are competing with the drawing. Report,
never gate.

---

### II.8 Quadrant

**The form.** Items placed in four cells formed by two named axes. The
`map` layout covers two axes already; a quadrant names the four cells
and gives each a meaning of its own.

**Status.** Planned with the comparison, state-machine, sequence and
timeline scaffolds, and deferred because no figure in the reference book
needs it yet
([#1060](https://github.com/prasadtalasila/chitragupta/issues/1060)).

---

## ⚙ Part III: Derived figures

### The idea

In this domain a figure usually depicts something that **also exists as
text elsewhere in the chapter**: a transition table, a grammar, a struct
definition, pseudocode, a spec, a real import graph. Instead of asking
an author or a model to draw the automaton, derive it from the transition
table. Instead of hand-drawing a DP-table trace, run the algorithm and
emit the frames.

This is the same move the project already made for citekeys: stop
generating the artefact, derive it from a source of truth, and refuse to
guess. A derived figure is regenerable, auditable, and **cannot drift
from the text**.

No life-sciences pipeline can do this, because there is no ground truth
to derive from. This one has ground truth on nearly every page. It is the
most distinctive feature available here and the reason to prefer this
roadmap over "draw prettier boxes".

### Candidate derivations, easiest first

| Source of truth | Derived figure | Notes |
| --- | --- | --- |
| Transition table | State machine (the `state-machine` layout) | Fully determined. The obvious first one |
| Struct / spec table | Bit-field layout (II.3) | Widths and names both come from the source, and II.3's width check then verifies the derivation against its own source |
| Frame list or algorithm run | State sequence (II.1) | Also derives the per-frame delta highlight, which is otherwise hand-specified and error-prone |
| Grammar (BNF) | Parse tree / railroad diagram | Well-trodden ground; many existing generators to read first |
| Message log or protocol spec | Sequence diagram (the `sequence` layout) | Ordering is the whole content and is machine-readable |
| Real source imports | Dependency graph | Needs the reduction ladder below before it is worth filing |

### The reduction ladder and the fidelity ledger

A real import graph is too dense to be a teaching figure without a
filtering story. Here is one, borrowed wholesale in shape from
`diagram-design`'s import path.

**A fixed reduction ladder, applied in a fixed order** until the figure
falls inside its metaphor's reference range: drop decorative and
unconnected elements, then merge duplicates, then collapse leaf clusters
into a single labelled node, then drop infrastructure that every node
touches. Fixed order matters more than the specific rungs: it makes the
reduction deterministic and therefore re-runnable, which is the whole
reason a derived figure is worth more than a drawn one.

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
  layer's style, but it acts on a draft and not on the corpus, and
  belongs beside the draft.
- **Determinism is the whole point.** A derivation must not call an LLM. If a
  step needs judgement (which cluster to collapse, which node is focal),
  that judgement belongs in the ladder as a fixed rule, or in the
  author's hands, not in a model. This is the same argument the
  parse-time captioning rejection made one layer down.
- **Output is a real figure file.** The derivation writes
  `figures/<n>.tex` and its twin, which then go through `figure check`,
  the caption check and numbering unchanged. It must not become a
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
out of date. All three are invisible to every check this project has:
`figure check` measures geometry and compares the figure with its own
ASCII twin, never with the prose; the verbatim tiers scan prose and never
see inside a figure file; and the caption check only asks whether a
caption exists.

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
  here would be a mistake, and the claim-support aid's output for the shape
  to copy.
- **Measures nothing, says so.** A figure with no named nodes, or a
  section with no code, yields no comparison and must report that instead
  of reporting clean, as `figure check`'s `nothing-measurable` does.
- **Not a gate.**

### Details to settle before filing

- **What counts as an identifier** in the section: fenced-code tokens,
  inline code spans, table cells, defined terms. Starting narrow
  (fenced-code and inline-code tokens only) keeps the false-positive rate
  measurable.
- **What counts as a figure label**: `figure check`'s twin rules already
  extract a node label's first line, zone titles and legend entries
  from the source; the same extraction is the starting point here.
- **Scope of "the enclosing section"**: the section containing the
  `figureref` marker, or the whole chapter. The first is tighter and
  probably right, but a figure referenced from two sections breaks the
  assumption.
- **Case and separator normalisation**: `page_table`, `pageTable` and
  "page table" are the same identifier to a reader. Deciding this wrong
  makes the check useless in either direction.

---

## 🧩 Part V: A shared object vocabulary

The house block already carries five `pic`s, each standing for a
conventional shape whose node label says the same thing
([TIKZ-STYLE.md](TIKZ-STYLE.md#-house-shapes-and-the-well-they-sit-in)).
They travel inside the block, so every figure stays one self-contained
file. What is still missing is the structural vocabulary a CS book draws
over and over.

### V.1 The `pic` library

A set of reusable TikZ `pic`s for structures, not icons. Candidate
vocabulary for this domain: a memory cell with named compartments, a
queue, a stack frame, a node-with-pointer-slots, a clock tick, a
lifeline, a labelled bus, a register, and the annotation callout
promoted out of II.7.

### Why this is the highest-leverage structural item

1. **It compounds.** Quality invested in one `pic` pays out in every
   figure that uses it, across a whole book. Nothing else on this
   roadmap has that property.
2. **It matches what a language model is good at.** Writing
   `\pic{cell} at (head.east)` correctly is easy. Placing forty control
   points blind is not.
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
document now needs two files instead of one, and the fragment-portability
property is real and deliberate. Options, in rough order of preference:

1. Grow the house block, which every figure already carries whole.
   This is how the five house `pic`s travel today, at the cost of a
   larger block in every figure.
2. Inline the used `pic` definitions into the figure at authoring time,
   trading duplication for portability.
3. Accept two files and adjust the portability claim in the skills.

This decision should be made before any structural `pic` ships,
because reversing it means rewriting every figure that used it.

The test for adding a `pic` is the one the house shapes already pass:
the twin must be able to say the same thing in words. A drum labelled
`page table` and the twin's `[page table]` carry the same proposition,
so the shape is a rendering choice. A shape carrying meaning the label
does not is a twin violation, whatever it is drawn with.

---

## 🎯 Part VI: Quality levers that need no new drawing

Cheap items that raise the quality of existing figures without a new
layout.

### VI.1 Make the caption carry the load

The caption-presence check asks only that a caption **exists**. A good
technical caption is self-contained and states the takeaway as well as
the subject: "the write path, showing where the fsync barrier falls"
instead of "the write path". Captions currently escape `HOUSE-STYLE.md`'s
objective function entirely, because they live in markers and not in
prose.

**Proposal.** A caption-shape aid reporting a caption under some word
count, or one that names its subject without asserting anything. Report,
never gate; a very short caption is sometimes right. This is the highest
ratio of informativeness gained to code written on the whole roadmap,
because it raises figure quality without drawing anything.

**To settle:** whether the prose objective function can be applied to
caption text directly, or whether captions need their own smaller
predicate.

### VI.2 Report effective type size at final scale

`TIKZ-STYLE.md` names the defect precisely (`\footnotesize` inside a
picture scaled to 0.8). `figure check`'s `type-below-floor` reports text
set below the 12pt body size, read from the glyphs, but it measures the
figure at its natural size. The scale a draft applies, and the column it
lands in, are not measured.

**Proposal.** Report it as a number: "smallest label prints at 4.2 pt at
an 84 mm column". That turns a documented defect into a measurement,
with no threshold and no verdict.

**It depends on Part X.** The target column width is a property of the
output, and the figure file does not know it. Part X's named output
targets supply it.

### VI.3 Count colours and words too

`figure check` reports node and edge counts, height and slack beside the
range each layout's scaffold and exemplars measure, as advisory reports
that never cap a figure
([figure-checks/size.md](figure-checks/size.md)). Distinct colours and
words of text are not counted.

**To settle:** whether "distinct colours used" should count palette
members only or every colour expression appearing in the source. The
second is easier and noisier.

### VI.4 One exemplar per layout

`assets/tikz/exemplars/` holds seven finished figures for eleven layouts.
Skeletons produce skeletal figures: an author who copies a three-node
pipeline tends to ship a three-node pipeline.

**Proposal.** One **finished** figure per layout: fully labelled, real
content from this domain, at final column width, with a caption that
states a takeaway. The scaffold stays the starting point; the exemplar
becomes the target. The reference ranges VI.3 reports are measured from
the scaffold and its exemplars, so each new exemplar also widens its
layout's range.

**It needs no new code.** `tests/test_tikz_scaffolds.py` already keeps
the exemplars compiling and fitting the render's width.

---

## 📊 Part VII: Quantitative panels

### The plotting gap

No `pgfplots`, no `matplotlib`, no data file, no axis anywhere. Benchmark
curves, latency distributions, complexity growth and scaling plots cannot
be drawn at all.

### Priority note

Lower than it would be for a thesis or results pipeline. A teaching
figure is usually explanatory, not evidential, and a complexity curve is
often illustrative, not measured. It matters for the
thesis-chapter genre and for any book chapter reporting real benchmarks,
which is enough to keep it on the roadmap but not enough to put it first.

### Mechanism

- **This is a renderer change.** `\usetikzlibrary` is body-legal so
  figure files name their own libraries, but `\usepackage{pgfplots}` is
  not. It needs a conditional `header-includes` in `_pandoc.py`, which is
  architecturally identical to what the tikz header-includes change did,
  to the library union #781 added beside it, and to what already
  exists for `fvextra`. Precedented and small.
- **Data lives beside the figure** as `figures/<n>.dat`, drawn with
  `\addplot table`. The numbers become diffable and auditable, which
  most published figures are not.
- **The twin is the data table**, not an ASCII scatter. A table in the
  `.txt` output is more informative than the plot and is what a screen
  reader wants. Here the twin requirement helps instead of limiting.
  This is the same principle as the state-machine layout's
  transition-table twin.
- **The encoding claim is checkable here too.** A bar chart claims length
  encodes value, the same way II.3 claims width encodes bit count. The
  same relative-error check applies, and if II.3 ships first the
  machinery is already written.
- **Confirm which texlive package ships pgfplots** and whether
  `scripts/install_full_pipeline.sh` needs a line. `texlive-pictures`
  covers the tikz libraries; do not assume it covers this.

---

## 👁 Part VIII: Where a vision model earns its place

### The one place it belongs

`TIKZ-STYLE.md` names three defects that are hard to measure: chaotic
routing, illegible or inconsistent type, and literal copying. A vision
model is not needed for the first two:

- **Chaotic routing** is largely geometry. `figure check`'s connector
  rules `c1` to `c7` measure it
  ([figure-checks/connectors.md](figure-checks/connectors.md)).
- **Illegible type** is measured against the body size by
  `type-below-floor`, and becomes arithmetic at final scale once the
  output target is known. See VI.2 and Part X.
- **Literal copying** has its own deterministic-ish path. See Part IX.

What remains, and is beyond geometry, is **informativeness**:
whether the figure teaches the thing it is supposed to teach, and the
twin-equivalence test the style doc frames as reading the `.txt` and
asking whether the point still arrives. That is a smaller and better-posed
job than "look at the figure and judge it", and it should be filed that
way.

### Vision-critique mechanism

- `pypdfium2` is already a declared dependency of the `enrich` extra
  (added for the crop work), so rasterising a compiled figure needs no
  new package. `figure look` already writes a 300 dpi PNG of each
  figure, which is the obvious input.
- Serve the model **out of process** (a local vLLM endpoint or an API)
  instead of importing it. `adapters` pins `transformers` to
  `>=4.57.6,<4.58.0`, a single-patch window, and most current
  vision-language models want newer. Importing one into the `enrich` venv
  turns the next `poetry lock` into a fight.
- Advisory only, exit 0, in the review layer. This is a Layer 2
  (generative) capability and must not become a corpus-layer artefact,
  because it is not deterministic.

### Where it does not belong

Captioning source-PDF figures at parse time. A measured decision rejected
that on the grounds that it puts generated text in the corpus layer,
which may not call an LLM (`docs/ARCHITECTURE.md`: "LAYER 1 · CORPUS —
deterministic, no LLM, safe unattended"). That rejection stands.

Nor does it belong anywhere in Part III. A derived figure that consults a
model is a generated figure with extra steps, and loses the property that
makes derivation worth building.

### Adjacent: the unconsumed crops

`plans/651-multimodal-drafting-access.md` measured 8,769 figure crops
and 497 `figures.json` indices on the real 497-PDF corpus, then with
**zero consumers**. `draft figures <citekey>` now surfaces a source's
crops to a drafting skill; page-image retrieval is the route still open.
Two routes that respect the layer boundary:

- Surface the crops at the **drafting** layer, where a model is already
  in the loop, as "the figure anchored at this passage" alongside
  retrieved text. The passage-anchoring work is the mechanism.
- Retrieve by page image rather than parsed text, which sidesteps the
  fact that `retrieval.search()` reads exactly one artefact,
  `content/parsed/<citekey>.txt`. `colpali-engine` is the mature option.

Both are separate features from anything in Parts I–VII and should be
filed against the multimodal-drafting-access issue, not here.

---

## 🔍 Part IX: Figure-similarity provenance

`bench/bench_figure_similarity.py` has run, and
`plans/659-figure-similarity-tier.md` records the recommendation.
Summarised here so the roadmap is complete.

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
words, inside that range. No threshold separated them, and the declined
overlap-gate decision forbids
guessing one. There is no reason image similarity behaves better.

**Domain-specific warning.** In CS and SE the canonical
figures are common property. Everyone draws the OSI stack, the five-stage
pipeline and the standard red-black rotation the same way, legitimately.
The false-positive floor will be **worse** in this domain than the
biology framing implied, and that expectation should be written into
`bench/bench_figure_similarity.py` before it runs instead of discovered
afterwards. An outcome where the floor swallows the planted case is a
valid result and should close the issue, the way `bench_overlap_gate.py`
killed a proposed gate on its own numbers and the way C4 and C6 left the
roadmap.

**A self-inflicted floor this roadmap creates.** A structural `pic`
library (V.1) means every figure using the shared memory-cell `pic` shares
pixel-identical regions with every other one. That is the library working
as intended and it is indistinguishable from copying at the pixel level.
It needs handling by construction, not by threshold: the screen
should exclude regions drawn from the shared library before hashing,
instead of trying to tolerate them afterwards. This is a further
argument for benching Part IX before V.1 ships.

**Part XI makes the mechanism cheaper.** A rendered raster per figure is
exactly what the screen needs, so if Part XI lands first, Part IX
inherits the rasterisation path instead of building its own.

---

## 📐 Part X: Output targets

**Small, and it unblocks two other items.**

**Partly built (epic #1140).** The two pages this repository already
sets are recorded once, measured, in `chitragupta/page.py`: `draft
render`'s A4 article and `book-assembler`'s A4 book. `figure check` and
`figure look` measure a figure under a book's drafts directory against
the book's 437.5pt text block, and every other figure against the
article's 453pt.
Named targets beyond those two (A5, A6, letter, two-column, slide), a
project setting and a per-draft target are parked on the epic.

### The gap in output targets

Several checks want to know the size at which a figure will be printed,
and no artefact holds that number. VI.2 cannot report an effective type
size without a column width. `figure check`'s width finding takes its
target from `--width`, defaulting to the text width of the figure's
page, the article's 453pt or a book's 437.5pt. Part XI's PNG branch
needs a width and a resolution before it can rasterise anything. Each of
those items has independently parked on "where does the target width
come from", which is a sign the answer belongs in one place, not three.

### The proposal

A small, closed set of **named output targets**, declared once per
project instead of per figure, each fixing a column width and a base
type size. Something like: a single-column book page, a wide or
full-bleed page, a two-column paper, a slide. The names matter less than
the properties: the set is small, it is closed, it lives in project
configuration, and every size-dependent check reads it.

`diagram-design` does the same thing with a `size` dial whose options
also drive the type ramp, so a projected slide gets larger node labels
than an inline document figure. The idea to take from it is that
the target changes **type size** as well as the frame: a figure scaled
down to fit is a different figure from one authored for that width.

### To settle

- **Where the declaration lives.** Project config is the obvious home,
  but a book with one full-bleed foldout needs a per-figure override, and
  an override mechanism is where this gets complicated.
- **Whether a figure can declare its own target.** Probably yes, probably
  rarely, and probably as an explicit exception that `figure check` reports so
  it does not go unnoticed.
- **Interaction with fragment portability.** A figure `\input` into a
  foreign thesis lands in a column of unknown width. The target is a
  property of *this* project's output and the figure should not hard-code
  it into geometry; it informs the checks, not the drawing.

### Why it is worth its own part

It is a handful of constants and a config key, and it is a prerequisite
for VI.2 and for Part XI's PNG branch. Filing it as a shared dependency avoids three
issues each inventing their own answer.

---

## 🖨 Part XI: Rendered figure images in md, html and docx

Today `md`, `docx` and `html` output render only the
ASCII twin. The TikZ form reaches the PDF and nowhere else. This part
proposes rendering each figure to SVG or PNG and shipping that image
alongside the twin in the non-PDF outputs.

### Most of the plumbing already exists

- `figure look` already compiles each figure on the page it prints on
  and writes it as a cropped PDF and a 300 dpi PNG.
- `pypdfium2` is already declared in the `enrich` extra.
- `_pandoc.py` already sets `--resource-path` so the PDF and DOCX writers
  resolve Markdown image syntax pointed at a file on disk.

As with raster images generally, what is missing is the **contract**, not
the plumbing.

### The argument for it is not the obvious one

The obvious argument, that html readers should see the picture, is true
but weak. The stronger one is that this **removes a conflict the twin
currently has to absorb**.

The twin is asked to do two incompatible jobs: be the clearest 7-bit
representation of the information, and be visually adequate as the
*sole* figure in md, html and docx. Those pull opposite ways. The
state-machine layout's twin is a transition table because a table is
more precise than the picture, and a transition table standing alone in
an html export, where the reader's browser could have shown the diagram,
is a worse export. Ship both and each form does one job: the twin is the
precise representation, the image is the picture. The principle behind
that twin and VII's data-table twin stops being a compromise.

### The erosion risk, and the structural fix

Once the image is what a reader sees in md and html, nobody except
screen-reader users depends on the twin, and an artefact
nobody looks at rots. Six months of stale twins would be invisible.

The mitigation must be structural, not cultural: **the twin
becomes the image's alternative text.** `alt` in html, the alt-text field
in docx, image plus fenced twin in Markdown. That makes the twin a
required input to the image instead of a substitute for it, so it cannot
rot without the image visibly losing its accessible name, which is
itself checkable.

### Tradeoffs, in rough order of seriousness

- **A LaTeX toolchain becomes a dependency of every output path.** Today
  a person can render Markdown with no TeX installed, because
  `figure check` and `figure look` are optional. Rendering
  images makes LuaLaTeX plus a converter a prerequisite for producing any
  output at all. This is an architecture decision, not a feature
  decision, and it is the largest single question in this part. The
  answer is a documented fallback: **with no TeX available, emit
  the twin exactly as today and say so.** Degraded output, reported, not
  a failure.
- **Generated binaries versus diffs.** Committed renders are generated
  artefacts that drift from source; built renders require the toolchain
  everywhere. Worse, TeX output is not byte-reproducible across TeX
  distributions and font versions, so a committed SVG shows spurious
  diffs on a colleague's machine. Cache keyed on a content hash of the
  `.tex`, and treat the cache as build output, not source. The
  same instinct keeps golden images out of `diagram-design`'s repo:
  nothing to re-record means nothing to go stale.
- **SVG and PNG are different answers and both are probably needed.** SVG
  suits html: it scales, stays small, and keeps label text selectable
  and searchable, *but only if the converter embeds fonts instead of
  converting glyphs to paths.* Several `dvisvgm` configurations default
  to paths, which silently destroys that property. Verify it instead of
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
  assigning the number and the caption still pandoc-visible per the
  caption-visibility fix. That is the real work here, and it is larger
  than the rendering step.
- **Review-pass cost**, per `PERFORMANCE.md`. Hash-keyed caching should
  make this negligible after a first pass, but that needs measuring
  instead of assuming.

### One thing it gives away free

A rendered raster per figure is exactly what Part IX's similarity
screen needs. If this lands first, Part IX inherits the path instead
of building one.

### Shape of the proposal

SVG-first with a PNG branch for docx; twin-as-alt-text mandatory, not
conventional; TeX-absent falling back to today's behaviour with a
report; renders cached by content hash and never committed; the whole
thing routed through the existing figure numbering contract.

**Depends on Part X** for the PNG branch, which is unanswerable without a
target width. The SVG branch does not.

---

## ⚖ A rule that may have to bend

### The palette versus depiction

Less pressing in this domain than in biology, because CS figures are line
art and the Okabe-Ito palette suits them well. The distinction is
still worth recording: the palette and the greyscale test govern
**semantic** colour, where a hue encodes a variable. Depictive colour,
where a thing simply looks like something, encodes nothing and the
greyscale test does not apply to it. Almost nothing in this domain is
depictive, so the practical answer is to keep the rule as it stands and
note the distinction only if a real case appears.

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
wrong (HTML/SVG on a 4-pixel grid versus TikZ compiled by LuaLaTeX and
measured in millimetres); the palette model is wrong (brand-matched
tokens versus a fixed Okabe-Ito palette that must travel
inside the figure file); and the generation model is wrong for Part III
(an LLM picks the type and the cuts, where a derivation must be
deterministic). What transfers is design reasoning, a few hundred words of
it, embedded in a repository whose bulk is coordinates for a different
medium.

**What was taken, and where it landed:**

| Idea | Landed in |
| --- | --- |
| Connector rules stated precisely enough to check: label-to-line clearance, fanned attach points, no transit over non-endpoint boxes, no coincident strokes, orthogonal elbows | `figure check`'s `c1` to `c7`, and the consequent narrowing of Part VIII |
| Named output sizes that fix both frame and type ramp | Part X, unblocking VI.2 |
| A complexity budget expressed per diagram type | `figure check`'s per-layout reference ranges, deliberately as a report and not a budget |
| A fixed degrade ladder and a fidelity ledger for reductions | Part III, answering the dependency-graph filtering question |
| A pre-output taste gate distinct from post-hoc linting | the `figure-drawer` skill's taste gate |
| Anti-patterns as a named table with a "why it fails" column | each layout's reference file |
| One reference document per type, loaded only when chosen, with a sync check | the skill's `references/layouts/` |
| A geometric check that verifies an encoding's own claim, measured as relative error | II.3's field-width check, and VII's bar lengths |
| Bounding-box geometry is an unreliable oracle for clipping and clearance | the connector rules' bench, which set their thresholds over this repository's own figures |
| Behaviour patterns kept separate from layout types so the type count does not inflate | II.7 demoted from a metaphor to a primitive |
| No golden images in the repository, so there is nothing to re-record and nothing to go stale | Part XI's hash-keyed render cache, treated as build output, not source |
| The six connector rules as numbered rules, with the lone edge attached at the side's midpoint | `figure check`'s `c1` to `c6` |
| Every geometric rule ships with a checker and fixtures in both polarities (its ADR 0005) | `figure check`'s tests and rule examples |
| SKILL.md as a router under a byte cap, with a check that moved sections keep their links (its ADR 0004) | the `figure-drawer` skill |

**A second source.**
[`INTO-CPS-Association/DTaaS`](https://github.com/INTO-CPS-Association/DTaaS),
the `update-docs-diagrams` agent skill on its `feature/distributed-demo`
branch. It restyles and exports drawio diagrams. Taken, as ideas only:
one idempotent command per step with the skill reduced to running them;
exceptions recorded with a reason instead of a rule silently skipped;
WCAG contrast thresholds of 4.5:1 for text and 3:1 for lines; and a last
look at every changed image. All four landed in `figure new`, `figure
check`'s `cg-allow` and contrast rules, and `figure look`. Its dark
variant has no counterpart in print and was not taken.

**What was rejected, and why**, so nobody re-derives it: brand-token
onboarding (this project has a fixed palette by design, for greyscale
legibility); the 4-pixel grid (a print artefact has no pixel grid); a
target density of 4/10 (correct for editorial diagrams, wrong for a DP
trace); motion and animation (print); the no-shadows / max-radius
aesthetic (tied to a web look, and this project's figures are line art
already); and its export path (Playwright and Chromium for a project that
compiles PDFs).

A footnote: that project's own "when not to use this" list sends quick
unicode diagrams to a different tool. That tool's job is this project's
ASCII twin, which is mandatory here.
Its taste rules were never designed to survive a twin requirement, which
is the main reason its aesthetic guidance transfers so much less well
than its mechanical guidance.

**Third-party art.** None is proposed. Heroicons was evaluated and set
aside; the argument is in the table below, and it is
worth reading before anyone proposes an icon set again, because the
technical fit is good enough to be tempting.

---

## 🚫 Considered and set aside

Recorded with the argument, so nobody re-derives it.

| Proposal | Why not |
| --- | --- |
| **Licensed vector art libraries for life-sciences** (Bioicons ~3,000 CC0/CC-BY icons, Servier Medical Art CC BY 4.0, NIH BioArt public domain, PhyloPic) | Correct answer for a life-sciences pipeline, irrelevant here. The attribution machinery would have been a good fit for this project's provenance spine, which is the only reason it was considered at all |
| **A general icon library for CS figures**, e.g. Heroicons (MIT, ~300 icons) | Set aside twice. The technical fit is real: Heroicons' 24px outline set is `M`/`L`/`C`/`A`/`Z` path data, which is the subset TikZ's `\path svg {...}` parses natively, so an icon converts to a `pic` with no new package, no raster and a diffable source. But feasibility is not a reason. Because the ASCII twin cannot render an icon, an icon must be strictly redundant with its node's text label, and a mark that adds no proposition is a mark the TikZ form also loses nothing by deleting. Set against that: a Part IX false-positive source needing whitelisting by construction, exclusions in VI.3's counts and Part IV's label extraction, stroke rescaling tied to Part X, a silent axis flip (SVG's y-axis points down), and a vendored subset with a licence notice to carry. Five ongoing obligations across four other parts, bought for pre-attentive scanning in one metaphor family. Worse, it would be the first proposal to make the twin strictly poorer by design, which is a precedent later proposals would argue from. Coverage is also UI-shaped (no page table, no pipeline hazard, no red-black node), and upstream declines new-icon contributions, so there is no route to a domain icon. What survives is the five house-drawn shapes in the house block ([TIKZ-STYLE.md](TIKZ-STYLE.md#-house-shapes-and-the-well-they-sit-in)) |
| **Generated raster illustration** | Non-deterministic, non-diffable, non-editable, and factually unreliable in exactly the domain where a mislabelled figure is worse than no figure. Fails the properties `SOUL.md` is built on. The narrower "generate a base plate and trace it" version reintroduces the originality problem of Part IX and still needs an illustrator |
| **Bezier organic form, gradients, translucency** | Illustrator craft. Reachable in TikZ in principle, but a cell membrane's curve requires hand-placed control points and this domain has no organic objects to draw. Dropped entirely |
| **`detikzify` or image-to-TikZ synthesis** | The inverse of Part IX: it automates producing the artefact that check exists to catch |
| **Vision captioning of source figures at parse time** | Rejected on measurement. Puts generated text in the corpus layer, which may not call an LLM |
| **Nature-style data density as the benchmark** | Wrong target for tutorials and textbook chapters. A teaching figure is explanatory, not evidential. Tufte and the algorithms literature are the better references. Part VII keeps the quantitative capability for the thesis genre without making density the goal |
| **A figure-similarity gate** | See Part IX. Advisory and ranked only. The declined overlap-gate decision forbids guessing a threshold and the measured evidence says none exists |
| **Adopting `diagram-design` as a dependency or an invoked skill** | See [Borrowed, with attribution](#-borrowed-with-attribution). Wrong output substrate, wrong palette model, and an LLM in a path Part III needs to be deterministic. The design reasoning was worth taking; nothing else was |
| **A hard complexity budget with numeric caps** | Correct for editorial diagrams, wrong for a textbook. A forty-cell DP trace is not over budget, it is a DP trace. `figure check` reports the count against a per-layout reference range instead, and nothing gates on it |

---

## 🗺 Build order

Ordered by a mix of certainty, size and what unblocks what.

1. **Part I: listing and algorithm classes.** Smallest, most certain, a
   correctness gap, not a quality one. Parts III and IV both want
   the marker vocabulary stable underneath them.
2. **Part VI.4: one exemplar per layout.** No new code, and each one
   also sharpens its layout's reference range.
3. **Part X: output targets.** A handful of constants and a config key.
   Unblocks 4 and Part XI's PNG branch.
4. **Part VI.1 and VI.2: caption shape, then type size at final scale.**
   VI.1 is the best ratio of informativeness to code on the roadmap;
   VI.2 is arithmetic once 3 lands.
5. **Part V.1: structural `pic`s.** Compounding, and a prerequisite for
   II.1. Settle the portability question first.
6. **Part II.1: state sequence.** Highest-value layout. Depends on 5.
7. **Part II.3, II.5, II.6: bit-field, timing, box-and-pointer.** Mostly
   a scaffold plus the right library load. II.3 may carry a renderer
   change (`bytefield`) and carries the width-encoding check. II.7 ships
   as a primitive inside 5, not as a layout. II.8 waits for a figure
   that needs it.
8. **Part IV: correspondence.** Wants 1 done, and wants II.3 figures
   existing to check against.
9. **Part III: derived figures.** The distinctive feature, but it
   compounds on everything above. The state-machine layout is the best
   first target. The ledger and the ladder ship with the first
   derivation, not after it.
10. **Part XI: rendered figure images.** Sits anywhere after 3, since
    the PNG branch needs Part X and the SVG branch does not. The
    architecture question (whether a LaTeX toolchain may become a
    dependency of every output path) should be settled before the issue
    is written, not inside it.
11. **Part IX: figure similarity.** Independent of everything else, and
    may close on its own bench numbers. **Bench it before V.1 ships**,
    since a shared `pic` library plants a known false-positive source.
12. **Part VII: quantitative panels.** Real, lower priority for this
    genre mix. Reuses II.3's encoding check.
13. **Part VIII: the informativeness critique.** It judges quality
    instead of creating it, so it lands better once there is more
    quality to judge.

## 📏 What needs measuring first

Following the bench self-check convention
(`plans/356-bench-self-check-convention.md`), and the
precedent of `bench_overlap_gate.py`, which killed a proposed gate on its
own numbers:

- **Figure inventory of a real book.** Count the figures in this
  project's own 15-chapter book by form, and check the claim this
  roadmap rests on: that state sequences, bit-fields and timing
  diagrams are frequent in the target literature and the eleven layouts
  do not cover them. If that count comes back saying the eleven layouts
  cover 90% of the book's figures, Part II shrinks a great deal.
- **Correspondence false-positive floor (Part IV).** Run the two-way set
  difference over existing figures and their sections. Legitimate
  mismatches will dominate; the question is whether the signal is visible
  above them.
- **Figure-similarity floor and recall (Part IX).** Rank the 8,769 crops
  against each other to establish the noise level, plus a planted TikZ
  redraw of a known corpus figure to confirm it ranks above it. Add a
  figure built from shared `pic`s as a known negative, since V.1 would
  create that floor deliberately.
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
  images may be weak on line art, which is an empirical question, not a
  guess.
- **Review-pass cost** for anything added, per
  `PERFORMANCE.md`'s "What a review pass costs".
