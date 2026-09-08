# Improving the Chitragupta topic graph: display, interactivity and network analysis

Recommendations for `chitragupta corpus discover --app` (and, where noted, the
static `--html` page), written against the design recorded in
`docs/TOPIC-DISCOVERY.md`.

---

## 1. What exists today

From the documentation, the interactive app currently:

- ships as a directory: `index.html`, the interaction code (`absence.js`,
  `graph.js`, `ego.js`, `families.js`, `panel.js`, `app.js`, `style.css`), a
  vendored and pinned cytoscape.js, and `data.js` carrying the payload as a
  JavaScript assignment (because `fetch()` of local JSON is blocked under
  `file://`);
- offers type-ahead search over topic labels and each topic's top terms, with
  matches pinned as removable chips that compose;
- focuses on selection: with topics pinned, the whole graph stays drawn with
  everything outside the neighbourhood dimmed, and the neighbourhood is laid
  out as concentric rings by hop distance (§4 below, shipped);
- encodes provenance as node colour (hand-written seed phrase, machine-extracted
  keyword, corroborated -- both files name it -- and emergent cluster), and is
  filterable by that class in the app and from `discover --origins` (#742);
  member count as node size, and overlap
  strength or similarity as edge width, with overlap edges solid and semantic
  edges dashed;
- lists a topic's papers as cards on click, the shared papers on a solid edge,
  and the bridging pair plus similarity on a dashed edge.

The static `--html` page places topics on a circle, described as a deliberate
non-choice of force layout: at tens of topics a circle is legible, renders
identically every run, and costs no physics code.

Three constraints from the project's own design govern everything below.

1. **Offline forever.** No network reference anywhere; the directory must open
   from `file://` after the corpus that produced it has moved on. Every
   extension must be vendored and justified in `assets/webapp/vendor/README.md`.
2. **Pure renderer.** `_app.build_app_payload` is `_page.build_payload` plus the
   `origin` annotation, and the app "cannot disagree with `--json` or with the
   terminal views". Interaction happens entirely in the browser over the
   embedded payload; nothing is recomputed and nothing is fetched.
3. **The two edge families are never merged**, because they answer different
   questions and their disagreement is itself a discovery cue.

A fourth, implicit constraint runs through the whole repository: reproducibility.
The project documents its non-reproducible corner (Docling under a worker pool)
rather than hiding it, and argues for the circle layout partly because it
"renders identically every run". A stochastic force layout in the app would
quietly violate that posture.

---

## 2. The architectural decision, and how it was decided

> **Decided (2026-09-05): compute in the browser, freely,
> with no artefact change.** The app is purely for exploration and
> discovery. Whatever a reader wants to bring back into the corpus, they
> bring back themselves by editing their topics and clusters; the app
> never writes and never claims. Read the rest of this section as the
> reasoning that led there, not as an open question -- the split below
> is real, but only its right-hand column was taken.
>
> Two consequences run through everything after this section. **The
> stored half is not being built**: `analysis`, `communities`, `xy`,
> `edges_withheld` and `layout_params` (section 3, and their rows in
> section 12) are new fields in `topic_graph.json` and are therefore out
> of scope (the 2026-09-07 amendment in the next box reopens this, under
> conditions). And **the renderer-contract objection dissolves**: the
> reason clustering, centrality and brokerage were pushed into the
> builder is that, computed in the browser, they would be a new claim
> about the corpus that `--json` could not confirm. An app that is
> explicitly exploratory, and that hands every decision back to the
> person, makes no such claim -- so those analytics come back as
> **view-derived** numbers, labelled in the UI as computed-in-view
> rather than read-from-artefact.
>
> One recommendation is out for a harder reason than policy. Section 6.1
> wants classical MDS over the topic centroids as a seed layout, but
> `_page.build_payload` constructs a fresh topic dict of
> `label`/`provenance`/`terms`/`members`/`linked`: `centroid` is in
> `topic_graph.json` and is *not forwarded*, so the browser cannot do
> that arithmetic on what it receives. The stage's `p_value` threshold
> and `neighbors` are not forwarded either, so a parameter footer
> (the last paragraph of this section) would need the same plumbing.
>
> The issue tracker carries the ranked ten features this filter left;
> nine of them are built.

Two decisions, two days apart, in one section -- the second box amends
the first rather than replacing it:

> **Amended (2026-09-07): stored analysis fields are
> allowed, under three conditions.** Section 13 records what shipping
> the app features did to this decision's premise: the bench scores
> the browser's partitions against gold data, the app/terminal gap grew
> a whole analytical layer, and the panel's own numbers are exactly the
> ones a survey introduction quotes. Section 13.5's sentence is now the
> contract: the pure-renderer clause promises *agreement between
> surfaces*, not silence from one of them -- any number either view
> presents must be derivable by the other from the same artefact,
> pinned by shared test vectors.
>
> A field may therefore be stored in `topic_graph.json` when all three
> hold:
>
> 1. it is a **deterministic function of data already in the artefact**
>    (edges, members, hierarchy) -- no new corpus reading, no model;
> 2. the **parameters used are recorded beside it**, section 3's
>    `analysis`/`layout_params` shape, so the number is reproducible
>    from the artefact alone;
> 3. a **shared case file pins every runtime that computes or consumes
>    it** to the same answers, the `hypergeometric_cases.js` /
>    `cut_cases.json` pattern.
>
> New fields take section 3's already-designed names (`analysis`,
> `communities`, `edges_withheld`, `layout_params`, `xy`) rather than
> inventing others. Two placement decisions travel with this amendment:
> the precompute lives in **`chitragupta/enrich/topic_graph.py`** (the
> discover layer computes nothing about topics -- `_data.py`'s boundary
> is load-bearing and stands); and if `networkx` is used it is declared
> **explicitly under the `enrich` extra** in `pyproject.toml`, where it
> today arrives only transitively -- section 14's verdict that
> numpy/scipy suffice also stands, so declaring it is a choice each
> implementing PR argues, not a default. Section 3's "not being built"
> banner and section 12's builder rows are partially reopened by
> exactly this amendment; the browser-side captions ("computed in your
> browser", "not a corpus claim") change only in the PRs that actually
> store each field, to "read from the artefact, parameters alongside"
> wording.

Cytoscape.js ships a substantial algorithms library in core, all of it available
without a single extra byte of vendored code:

| Family | Methods |
| --- | --- |
| Search / traversal | `bfs`, `dfs`, `aStar`, `dijkstra`, `bellmanFord`, `floydWarshall` |
| Centrality | `degreeCentrality(Normalized)`, `closenessCentrality(Normalized)`, `betweennessCentrality`, `pageRank` |
| Clustering | `markovClustering` (MCL), `hierarchicalClustering`, `kMeans`, `kMedoids`, `fuzzyCMeans`, `affinityPropagation` |
| Structure | `kruskal`, `kargerStein` (min-cut), `hopcroftTarjanBiconnected`, `tarjanStronglyConnected` |

Most of these are tempting and several of them would quietly break the renderer
contract. A community assignment or a betweenness rank is **a new claim about the
corpus**. If the browser makes that claim and `--json` does not, the app and the
terminal now disagree, no test pins the disagreement, and the property the
documentation puts in writing stops being true.

The workable split is by whether the answer is a property of *the corpus* or of
*the current view*:

**Compute in the `topic-graph` stage; store in `topic_graph.json`; expose via
`--json`; render in the app.**

- community partitions (per edge family)
- centrality and brokerage per topic
- seed layout coordinates
- withheld (near-miss) overlap edges

**Compute in the browser, freely, no artefact change.**

- hop distance from the current selection
- hover neighbourhoods
- shortest path between two pinned topics
- degree *within the visible subgraph*
- anything that changes when the reader changes the selection

The rule of thumb: if a reader could screenshot the panel and quote the number in
a paper, it belongs in the artefact. If the number changes when they click
something else, it belongs in the browser.

This split also gives the app the same honest-degradation story the rest of the
pipeline has. No enrich extra, no communities in the artefact, so the cluster
controls are hidden with a one-line note rather than silently substituting a
browser-side computation the terminal cannot confirm.

Record the analysis parameters (MCL inflation, PageRank damping, MDS variant)
in the payload alongside the existing `p_value` and `neighbors`, and print them
in the page footer. A view whose parameters are invisible is a view that cannot
be reproduced from the page alone.

---

## 3. Proposed `topic_graph.json` additions

> **Partially reopened by the 2026-09-07 amendment to section 2.** These fields
> may now be built, one PR at a time, under the amendment's three
> conditions; until a given field's PR lands, section 7.7's
> browser-side recomputation remains how the app reaches the
> `edges_withheld` answer without it.

Designed as one schema change, so the builder and the app can move in one
pass. Everything here is derived from data the stage already computes;
nothing needs a new model download and nothing needs an LLM. Beside the
artefact's existing top-level fields (the model id, the corpus and topic
counts, the gate's `p_value`, the semantic `neighbors`, the corpus mean,
the `topics` list, both edge families and the merge `hierarchy`), the
proposal added five:

- **`analysis`**, on each topic and keyed by edge family: degree,
  PageRank, normalised betweenness, ego density (edges among the alters
  over the pairs they could form), and Burt's effective size and
  constraint -- the same shape for `overlap` and `semantic`, never
  pooled.
- **`xy`**, on each topic: deterministic seed coordinates in the unit
  square (classical MDS over the centred centroids was the sketch; the
  app scales).
- **`edges_withheld`**, top-level: the pairs the gate tested and
  refused, each with its shared citekeys, both overlap coefficients,
  the p it was refused at, and the reason.
- **`communities`**, top-level and keyed by family: the clustering
  method, the inflation used, and each cluster's member labels -- one
  partition per family, never fused.
- **`layout_params`**, top-level: whatever drew the stored coordinates
  (algorithm and its parameters), for the page footer and for
  reproduction.

Notes on the additions:

- **Keys stay labels**, per the existing convention that topic ids are unstable
  across runs and anything downstream must key on labels or citekeys.
- **`edges_withheld` is bounded**: store only pairs sharing at least one paper,
  which is already the only set the hypergeometric test runs over. On a real
  corpus this is a few hundred rows at most.
- **`analysis` is duplicated per family** rather than computed on a fused graph.
  A topic that brokers between paper-sharing clusters is not the same object as
  a topic that brokers between vocabularies, and collapsing the two destroys
  exactly the signal the design is built around.
- **`xy` makes the layout reproducible** without pinning the reader to it; see
  section 6.

Computing all of this needs numpy and scipy, both already present in the enrich
extra. PageRank, betweenness and MCL are each a short function over a sparse
adjacency matrix; no new dependency is required, and adding `networkx` is a
reasonable alternative if the code-size ratchet prefers it.

---

## 4. Egocentric views

The current behaviour on selection is a hard filter plus a layout re-run. Two
changes make it read considerably better.

### 4.1 Dim rather than remove

Removing the unselected topics costs the reader their sense of scale and of where
they are in a 53-topic space. The standard focus-plus-context move is to keep
the whole graph drawn and push the context back:

The sketch: a `dimmed` class dropping node opacity to about 0.12 (labels
hidden) and edge opacity to 0.06, applied to everything and removed from
the ego set inside one `cy.batch`.

Set `events: 'no'` on `.dimmed` so dimmed nodes are not clickable and do not
steal hover. Keep a "hide context" toggle for the reader who wants today's
behaviour, and remember the choice in the hash (section 7.3).

### 4.2 Concentric rings by hop distance, not a force layout

Hop distance from the pinned set maps directly onto concentric rings. It is
deterministic, needs no physics, and extends rather than contradicts the "a
circle is legible" argument already made for the static page.

The sketch: an undirected `bfs` from the pinned set, over the currently
enabled edge families -- which the header's **Edges** picker is what
makes reachable, and until it shipped the walk was always over the union
of both -- recording each node's hop depth in a map; the
nodes within `maxHops` (and the edges among them) then run the built-in
`concentric` layout with the negated hop depth as the concentric value
(so hop 0 sits innermost), one hop per level, about 30px of node
spacing, and a short (~350ms) `animate: 'end'` transition.

A `maxHops` control (1 / 2 / all) is worth exposing. One hop answers "what is
next to this"; two hops answers "what would a chapter around this have to
cover".

### 4.3 Animate transitions

Object constancy matters more in graph reading than almost anywhere else. If a
node jumps to an unrelated position when the selection changes, the reader
re-parses the whole picture. `animate: 'end'` on the layout, or animating
positions directly with `cy.animate`, preserves the reader's mental map across
selections at essentially no cost.

### 4.4 Type the rings

A hop-1 neighbour reached only through a shared paper is a different object from
one reached only through cosine nearness. Three ways to keep them distinct, in
increasing order of effort:

1. **Edge style only** (already done: solid vs dashed) plus a legend that names
   the two questions rather than the two mechanisms.
2. **Split arcs.** Run `concentric` twice over disjoint sub-collections with
   different `startAngle`/`sweep`, overlap-only neighbours on one side of the
   ego, semantic-only on the other, and both-families neighbours straddling.
3. **Two rings.** Overlap neighbours inner, semantic outer, with a swap control.

What must not happen is a single ring whose radius averages the two strengths.
Averaging is the fusion the design explicitly refuses.

Shipped as option 2, proportional arcs, and with one thing this section
did not think to say: the rule binds the *distance metric* as well as
the placement. Typed arcs over a hop distance walked across both
families keep the two apart on the first ring and fuse them everywhere
outside it -- a topic one shared paper plus one cosine hop away lands on
ring 2 beside a topic two shared papers out, and the reader cannot tell
which they are looking at. The **Edges** picker is what closes that:
enabling a family decides which edges are drawn, which are walked, and
how ring 1 is typed, all from one piece of state. `--hops N --family F`
is the terminal's half of the same fix -- the port had the union
hardcoded, so closing it on one surface alone would have opened the
section 13.5 gap in the other direction.

### 4.5 Report ego statistics in the panel

The two numbers that matter most for survey scoping:

- **Ego density**: edges among the alters divided by the possible number. A
  dense ego network means the neighbourhood is a coherent theme; a sparse one
  means the topic sits between themes.
- **Burt's effective size / constraint**: the brokerage reading of the same
  thing. A topic whose neighbours do not touch each other is a bridge, and a
  bridge topic is where a survey section earns its keep.

Show them per edge family, side by side. A topic that brokers over shared papers
but not over vocabulary is a methods topic; the reverse is usually a
terminology split worth naming in the draft.

---

## 5. Clustering on topic overlap

Three candidate sources of cluster structure, ranked by value per unit of work.

### 5.1 The hierarchy you already store, as a resolution slider

The stage already computes an agglomerative merge tree over the topic centroids
(average linkage, cosine distance) and stores it for the tree view. Cutting that
tree at a distance the reader drags is:

- **deterministic** (it is a stored tree, not a re-fit);
- **free of new dependencies**;
- **not a new claim** (the tree is already in the artefact and already in
  `--json`).

Render each cut group as a cytoscape **compound parent node**. Start the app at
a cut yielding roughly 8 groups and let the reader slide toward 53.

The sketch: a `cutTree(hierarchy, threshold)` helper running standard
union-find over the stored merges whose distance is at or below the
threshold, returning a label-to-cluster map; applying a cut then means
ensuring the parent nodes exist, `move`-ing every non-cluster node under
its group's parent inside one `cy.batch`, and re-running the layout.

This is the single highest-value change on this list: it turns an unreadable
53-node hairball into a table of contents that the reader can zoom into
continuously, using data that is already on disk.

### 5.2 MCL over each edge family, separately

> **Shipped**, in the browser rather than the builder, which
> section 2's decision is what allows: the partitions are labelled as
> the view's own, the inflation is a visible control, and nothing is
> written back. Written out rather than taken from cytoscape's
> `markovClustering`, whose call needs a live canvas -- this way the
> clustering runs in a test with no browser at all.

Markov clustering is a good fit for this graph: weighted, undirected, no
target-`k` to guess, and deterministic given the same input and inflation.

Run it **twice**, never once on a fused graph:

- over `edges_overlap`, weighted by `overlap_coeff`, giving *clusters of topics
  that share papers*, which read as candidate survey sections;
- over `edges_semantic`, weighted by `similarity`, giving *clusters of topics
  that talk alike*.

The interesting artefact is the **disagreement**. A small co-membership grid in
the side panel showing which paper-sharing clusters split apart semantically, and
which semantic clusters share no papers at all, promotes the design's existing
discovery cue from a footnote to a view. Two topics in the same semantic cluster
with no shared papers is a literature that has not met itself; that is exactly
the observation a survey wants to open with.

Per section 2, run this in the builder and store it. If you prefer to prototype
in the browser first, cytoscape's own call is `markovClustering` over the
elements, with the edge's `overlap_coeff` as the weight attribute and an
`inflateFactor` of 2.0.

Note that MCL is sensitive to the inflation factor; it belongs in
`config.toml` under `[enrich]`, with the gold set (section 9) used to argue for
whatever default is chosen.

### 5.3 `cise` as the cluster-aware layout

Circular Spring Embedder takes explicit cluster assignments and draws each
cluster on its own circle, with inter-cluster edges between them. It is the
circle argument applied one level down, and it makes overlap communities legible
in a way a general force layout will not.

The sketch: run the `cise` layout over the view with the cut's
label-to-cluster map as the `clusters` function, `randomize: false` for
determinism, a node separation of 12, and an `animate: 'end'` transition.

Vendor `cytoscape-cise` plus `cose-base` and `layout-base`.

### 5.4 Collapse by default

`cytoscape-expand-collapse` turns a compound parent into a single meta-node with
an aggregated member count and bundled edges. Combined with the resolution
slider, this is the legibility fix: the app opens showing ~8 meta-nodes, and
double-clicking expands one in place while the rest stay collapsed. Bundled
inter-cluster edges should carry the count of underlying edges and remain
clickable, listing the constituent pairs.

---

## 6. Layout and reproducibility

`fcose` and `cose-bilkent` are stochastic. Opening the same exported directory
twice would give two different pictures, which sits badly beside a project that
documents its one non-reproducible parser corner as a known hazard.

### 6.1 Store seed coordinates

Compute classical MDS (not UMAP, which the design rejects for distorting global
distances by construction) over the centroid cosine distances in the same
mean-centred space the semantic edges use. Write the result as `xy` per topic.
The app then uses `preset` as its base layout, with each node's position
taken from the stored `xy` entry, scaled to the viewport.

`fcose` becomes an optional "relax" button with `randomize: false`, seeded from
those positions. Same page, same machine, same picture, every time, and the
picture *means* something (proximity is centroid similarity) rather than being
whatever the force simulation settled into.

### 6.2 Order the circle by dendrogram leaf order

> **Shipped**, on the static `--html` page only, as
> `_page.dendrogram_order`. The walk is Python rather than the
> template's inline script, which nothing executes: in the template it
> would have been an untested branch against a 100% coverage bar. A
> topic the tree does not mention keeps its artefact order and follows
> the leaves, and the `--app` payload is untouched.

Even for the existing static `--html` circle, this is free. The merge tree gives
a deterministic 1-D leaf ordering in which adjacent leaves are similar. Ordering
the circle by it makes chords short and clustered instead of arbitrary, and
turns the circle from a non-choice into a weak but real encoding. Zero new
dependencies; the data is already in the file.

### 6.3 A small, explicit layout menu

Rather than one layout for everything:

| Layout | For | Deterministic |
| --- | --- | --- |
| `preset` (stored MDS `xy`) | default global view | yes |
| `circle`, dendrogram-ordered | the static page, and a fallback | yes |
| `concentric` by hop | ego / selection view | yes |
| `cise` | cluster view | with `randomize: false` |
| `fcose` (`randomize: false`, seeded) | optional "relax" | effectively |
| `dagre` or `breadthfirst` | the hierarchy tree view | yes |

`fcose` also supports `fixedNodeConstraint`, so an ego view can pin the selected
topic dead centre and let the rest relax around it if force is preferred to
rings.

---

## 7. Visual encoding and interaction

### 7.1 Surface what is already stored but invisible

> **Shipped**: `p_value` is edge opacity on the overlap family
> only, the containment reading is named in words rather than left as
> two numbers, and the bridge pair is on hover as well as on click --
> through a positioned div, not `cytoscape-popper`.

- **`p_value` on overlap edges.** Every overlap edge carries the significance
  that let it exist, and nothing shows it. Map it to edge **opacity**: more
  surprising overlap, more solid edge. Width stays strength. The hypergeometric
  gate acquires a visual presence instead of being invisible arithmetic.
- **`jaccard` vs `overlap_coeff`.** Both travel on every edge for a documented
  reason: a rank-truncated seed topic sitting entirely inside a large emergent
  cluster scores low on Jaccard and 1.0 on overlap coefficient, and that gap
  *is* the sub-topic reading. A small badge on the edge panel ("contained:
  overlap 1.00, Jaccard 0.15") names the relationship rather than leaving the
  reader to compare two numbers.
- **`bridge` pairs on semantic edges.** Already listed on click; also worth
  showing on hover as a one-line tooltip, since it is the fastest available
  answer to "why is this edge here".

### 7.2 Free a channel

Four channels on a node (fill, size, border, halo) is one too many to read at a
glance. Once clusters exist, the reader is scanning for cluster membership, so:

- **fill** → cluster / hierarchy branch
- **border style** → origin: solid for a hand-written seed phrase, dotted for a
  machine-extracted keyword, double for a corroborated phrase (both files name
  it), none for an emergent cluster
- **size** → member count (unchanged)
- **shape** → reserved for node *type* if papers ever join the graph (7.5)

Border style carries a four-way categorical distinction perfectly well and is
robust to colour-vision differences, which fill is not.

### 7.3 Labels and semantic zoom

At 53 nodes labels collide; with papers expanded they are hopeless.

The sketch, in two parts. A node style setting `min-zoomed-font-size: 8`
(labels vanish rather than shrink into noise), wrapped text capped at
90px wide, and a mostly-opaque white text background with a little
padding so labels stay readable over edges. And a `zoom` handler that
toggles a `show-label` class inside one `cy.batch`: cluster nodes carry
labels below a zoom of 0.8, individual topics at or above it -- semantic
zoom with a single crossover point.

Otherwise show labels only for the ego set and the top-N by member count, with
the full label on hover.

### 7.4 Hover neighbourhood highlighting

> **Shipped**, and grown past the sketch below in two ways. First, the
> neighbourhood is not merely left alone while everything else fades --
> nodes get their own outline (`focus-near`, distinct from the pinned
> node's border and from the click-latched centre's own `focused`
> outline) and edges get a flat width bump on top of their strength
> encoding, both at full opacity, so the neighbourhood reads as
> actively highlighted rather than as "unaffected by the fade" -- edge
> family colour (indigo/purple) is kept throughout, so the overlap-vs-
> semantic vocabulary survives being highlighted. Second, the fade is
> not only a hover preview: clicking a node latches it -- the same
> paint, but it survives `mouseout`, so a reader can move the pointer
> into the side panel without the highlight evaporating. Released by
> clicking the same node again, clicking the canvas background, or Esc
> (7.10).

The sketch: on node `mouseover`, add a `faded` class to every element
outside the node's `closedNeighborhood()`; on `mouseout`, remove it
everywhere.

Cheap, and it is the interaction people expect from a graph.

### 7.5 Papers as nodes, on demand

> **Shipped**. Two departures from the sketch below, both
> deliberate: a paper's id is prefixed with a string computed from the
> payload rather than a fixed one, because node ids share a namespace
> and a topic labelled `paper:dt2022` would otherwise *be* the node for
> that paper; and the bridge highlight counts the topics on the canvas,
> not the topics in the corpus, since on a real corpus nearly every
> paper is in several and the corpus-wide count highlights everything.

Expanding a topic into its member papers as leaf nodes makes a paper belonging to
three topics *visibly* a bridge instead of a line of text repeated in three
panels. This is the heterogeneous single-graph shape the design takes from
MiniRAG, and the app is the natural place for it.

- Different node **shape** for papers; label is the citekey, title on hover.
- A paper in more than one *visible* topic connects to each, which is the whole
  point; cap expansion (say, 3 topics at a time) and make it opt-in.
- Turn on `hideEdgesOnViewport` and `textureOnViewport` once paper nodes are in
  play, and wrap every mutation in `cy.batch()`.

### 7.6 Path between two pinned topics

> **Shipped**: two buttons, one per family, each hop carrying
> its citekeys or its bridging pair. No fused weight and no total
> distance anywhere.

`dijkstra` with weight `1 - strength` answers "what connects digital twins to
runtime verification in my corpus", and every hop arrives with either shared
citekeys or a bridge pair, so the path is explainable by naming real papers.

Offer it as **two buttons** — "path over shared papers" and "path over semantic
nearness" — rather than one fused weight. If a single mixed path is genuinely
wanted, show each hop's family on the hop itself and never report a single fused
distance for the path as a whole.

The sketch: restrict the collection to one family's edges (plus all the
nodes), run `dijkstra` from the first pinned topic with each edge
weighted as one minus its strength (`overlap_coeff` or `similarity`),
and read the result's `pathTo` the second topic.

### 7.7 Explain an absence

> **Shipped**, originally without the `edges_withheld` field
> this section proposes -- the browser recomputed the tail from each
> topic's `members` and `n_docs`. A later change (2026-09-07) then
> stored the field: the stage
> writes its refusals (`{a, b, shared, p_value}`, bounded to pairs
> sharing a paper) beside the edges it drew, the payload forwards them,
> and both `absence.js` and `discover --why` prefer the stored p,
> recomputing only for an artefact from an older run.
> `tests/webapp/hypergeometric_cases.js` remains the contract that
> keeps that fallback agreeing with `enrich/topic_graph.py` -- scipy's
> own answers, checked from three runtimes. The faint dotted layer of
> withheld pairs is not built.

The most instructive moment in the documented worked session is the
hypergeometric gate computing p = 1.0 and withholding an edge between two topics
that *do* share a paper. Today that reasoning is invisible in every view.

With `edges_withheld` in the artefact, pinning two topics that have no overlap
edge can produce: *"These share dt2022, but sharing one paper between topics of
size 2 and 3 in a 4-paper corpus is what chance predicts (p = 1.00), so no edge
was drawn."* That is a distinctive feature, it is a few lines of builder code,
and it teaches the reader the gate rather than leaving them to wonder whether the
tool missed something.

Optionally render withheld pairs as very faint dotted lines behind everything
else, toggleable, so the refused structure is visible as a layer.

### 7.8 Set comparison on multiple chips

The chips already compose. With two or more pinned, add a small set panel:
shared papers, papers exclusive to each, and the overlap statistics. The `shared`
arrays are already in the artefact, so this is a join and some list rendering.
At three or more chips, an UpSet-style bar list beats any Venn diagram.

### 7.9 State in `location.hash`

`location.hash` works under `file://`. Encoding the view as
`#topics=digital-twin,machine-learning&mode=ego2&cut=0.40&ctx=dim` gives, for
free:

- bookmarkable and shareable views inside the exported directory;
- browser back/forward as selection undo/redo;
- a way for `docs/` to link a specific view of the sample corpus.

Parse defensively and treat every hash value as untrusted input, the same as a
topic label.

### 7.10 Accessibility

> **Partly shipped, and one clause below withdrawn.** `#detail` carries
> `aria-live="polite"` and its topic/edge links carry `tabindex="0"`
> and `role="link"` (they have no `href`, so nothing marks them as
> links without it), so Enter reaches a node's neighbourhood (7.4) with
> no pointer. `Esc` does **not** clear chips: releasing several minutes
> of pinning on the same key that dismisses a dropdown or a hover latch
> is a worse failure mode than three gestures that each do one thing,
> so `Esc` only releases a latched node (once the type-ahead, which
> still wins, and then an open filter picker have been closed -- one
> policy, `escapeAction`, ordered by how wide the gesture is) and chips
> keep their own removal gesture. `/`
> as a focus shortcut, keyboard-removable chips and the list-view
> toggle remain unbuilt.

The canvas is opaque to assistive technology, so the **side panel is the
accessible representation** of the graph. Keep it real DOM (a `<ul>` of topics
and papers, not canvas-drawn text), add `aria-live="polite"` so selection changes
are announced, give the search input `/` as a focus shortcut and `Esc` to clear
chips, and make chips removable by keyboard. Provide a "list view" toggle that
hides the canvas entirely and shows topics, their papers and their linked topics
as nested lists; that view is also the one that prints.

---

## 8. Performance

At 53 topics none of this matters. It starts to matter the moment paper nodes
join the graph (500+ nodes, several thousand edges).

- `hideEdgesOnViewport: true`, `textureOnViewport: true`, `pixelRatio: 1` on
  init.
- Wrap every multi-element mutation in `cy.batch()`.
- Debounce the type-ahead so the layout does not re-run per keystroke; re-run on
  chip commit, not on input.
- `layout.stop()` the previous layout before starting a new one.
- Call `cy.style().update()` sparingly; prefer class toggles over style mutation.
- Precompute anything O(V·E) (betweenness in particular) in the builder rather
  than in the browser, which section 2 already argues for on contract grounds.

---

## 9. Testing, and keeping the contract true

- **Snapshot the artefact, not the browser.** Every new field
  (`analysis`, `communities`, `xy`, `edges_withheld`) gets a builder test with a
  fixture graph whose expected values are computed by hand or by an independent
  implementation. The browser then has nothing to be right or wrong about.
- **Pin the parity property.** A test that asserts the app payload and the
  `--json` payload agree on every shared field is the mechanical form of "the
  app cannot disagree with the terminal", and it is currently a prose promise.
- **Determinism test.** Build the app twice from the same artefact and assert
  byte equality of `data.js`, including `xy`. This is the app-level analogue of
  the corpus layer's reproducibility contract.
- **Extend the gold set.** `bench/topic_discovery_eval.py` scores the resolution
  ladder; clustering deserves the same treatment. Adding a handful of hand-written
  "these topics belong together" groupings to `content/topic_gold.toml` turns
  the MCL inflation factor and the default hierarchy cut from a feel into a
  measurement, exactly as the gold set did for `[discover].min_similarity`.

  > **The inflation half is shipped**: `[[group]]` records in the
  > same gold file, scored by `bench/topic_cluster_eval.py`, which drives
  > `assets/webapp/families.js` through `node` rather than
  > re-implementing MCL beside it. Pairwise over the gold-covered topics
  > only, since grouping gold is partial by design. The **hierarchy cut**
  > is not scored yet -- same gold file, different control.
- **Escaping, again, on every new surface.** Tooltips, cluster labels, path
  panels, set-comparison lists and hash-parsed state all interpolate
  semi-trusted topic labels, which may have ridden in through a PDF's extracted
  keywords. Prefer `textContent` over HTML string building in every new code
  path, keep the five-character escape for the paths that must build markup, and
  keep the null-prototype lookup tables.

---

## 10. Vendoring

Minimum useful set, all with permissive licences, all UMD-loadable from
`file://`:

| Package | For | Notes |
| --- | --- | --- |
| `cytoscape-fcose` | optional relax layout | needs `cose-base` |
| `cytoscape-cise` | cluster-per-circle layout | needs `cose-base`, `layout-base` |
| `cose-base`, `layout-base` | shared dependency | |
| `cytoscape-expand-collapse` | collapse clusters into meta-nodes | |
| `cytoscape-dagre` | hierarchy tree view | needs `dagre`; skip if `breadthfirst` suffices |

I would **skip `cytoscape-popper`**: it drags in Popper for tooltips that an
absolutely-positioned div handles fine, and every file in
`assets/webapp/vendor/` has to be justified in its README.

`concentric`, `circle`, `preset`, `breadthfirst` and the entire algorithms
library are core, so a meaningful subset of everything above (all of section 4,
section 5.1, sections 6.2, 7.1–7.4 and 7.6–7.10) needs **no new vendored code at
all**.

---

## 11. Suggested order of work

> The order below still holds for the recommendations section 2's
> decision kept; the issue tracker has the ranked list as it now
> stands. Item 1 below is not among the nine: it improves the static
> page rather than the app, so it is tracked separately.

1. **Dendrogram-ordered circle** on the static `--html` page. One function, no
   new data, immediate legibility win, and it validates the ordering before
   anything depends on it. *(shipped -- §6.2.)*
2. **Dim-not-remove plus concentric ego rings plus hover neighbourhoods** in the
   app. Core cytoscape only; this is the biggest interaction improvement per
   line of code.
3. **`edges_withheld` and `p_value` as edge opacity.** Small builder change,
   distinctive feature, teaches the gate.
4. **Hierarchy cut slider with compound parents**, then
   `cytoscape-expand-collapse`. This is where the 53-node hairball becomes
   readable.
5. **`analysis` and `xy` in the artefact**, with `preset` as the default layout
   and brokerage statistics in the panel.
6. **MCL communities per family, plus the disagreement grid**, with gold-set
   numbers to defend the inflation default. *(shipped -- §9 has the
   numbers.)*
7. **`cise`**, papers-as-nodes, and typed path finding, in whichever order the
   corpus's own questions demand.

---

## 12. Summary table

> This is the *design* table, not a shipped-feature inventory -- filing
> work from it without checking the app source repeats §11's mistake.
> The **builder** rows are the ones section 2's decision did not take.
> Of them, only "withheld-edge explanation" survives, recomputed in
> the browser (section 7.7); brokerage and the MCL partitions survive
> as view-derived numbers; MDS seed coordinates do not survive at all,
> because `centroid` is not forwarded into the app payload. The
> **Shipped** column is what the app actually does today: collapse is
> hand-rolled over a `collapsed` Set in `graph.js` (no
> `cytoscape-expand-collapse` -- `vendor/` holds core cytoscape only),
> the ungrouped view runs core `cose` rather than `cise`, and no
> `location`/`hash` reference exists anywhere in `assets/webapp/`, so
> nothing is shareable or bookmarkable.

| Technique | Where it runs | New dependency | Answers | Shipped |
| --- | --- | --- | --- | --- |
| Concentric ego rings by hop | browser | none | what is next to this topic | yes, walked over the families the reader has on |
| Dim-not-remove context | browser | none | where am I in the whole corpus | yes |
| Ego density, Burt brokerage | builder | none | is this a theme or a bridge | as view-derived numbers |
| Hierarchy cut slider | browser (stored tree) | none | what are the broad areas | yes |
| Compound parents + collapse | browser | expand-collapse | legibility at 50+ topics | yes, hand-rolled, no extension |
| MCL per edge family | builder | none | candidate survey sections | as view-derived numbers |
| Overlap vs semantic disagreement | builder + browser | none | where the literature has not met itself | as view-derived numbers |
| `cise` layout | browser | cise, cose-base | cluster structure at a glance | no -- core `cose` instead |
| MDS seed coordinates | builder | none | a reproducible, meaningful layout | no |
| Typed shortest path | browser | none | what connects A to B, and via which papers | yes |
| Withheld-edge explanation | builder + browser | none | why is there *no* edge here | yes, recomputed in-browser (§7.7) |
| Papers as nodes | browser | none | which papers bridge which topics | yes |
| Hash-encoded view state | browser | none | shareable, bookmarkable views | no |

---

## 13. The app and the terminal: the capability gap, and two ways to close it

Written 2026-09-07, after the nine app features landed. Everything above
still holds; this section records what shipping them *did* to the
renderer contract, in plainer language than the sections that argued for
them.

### 13.1 The gap as it stood, and the twins that closed it

`corpus discover` and the `--app` page read the same artefact, and the
contract says the app "cannot disagree with `--json` or with the
terminal views". For two days after section 2's decision, that sentence
was true only because the terminal was silent: the app computed a whole
analytical layer -- the merge-tree grouping, the MCL partitions and
their disagreement grid, ego density and Burt brokerage, typed shortest
paths, the withheld-edge explanation -- and the terminal could produce
none of it. You cannot disagree with someone who says nothing, and a
scripted consumer, which in this project includes every drafting skill,
could not reach any answer the panel showed. Closing that, one twin per
day's work on 2026-09-07, is what the table below records -- every row
now names a shipped command, each pinned to the app's own arithmetic by
a shared case file under `tests/webapp/`.

| The app answers | The terminal's answer |
| --- | --- |
| what are the broad areas (resolution cut) | `discover --groups N` -- the same cut, pinned by `tests/webapp/cut_cases.json` |
| candidate survey sections (MCL per family) | `discover --clusters [--inflation X]`, read from the stored `communities` |
| where the families disagree | the same `--clusters` view's two disagreement lists |
| is this topic a theme or a bridge | the topic view's brokerage section, read from the stored `analysis` |
| what connects A to B, via which papers | `discover --path A B --family F`, walked from the stored matrices |
| why is there *no* edge here | `discover --why A B` -- the first twin shipped, path A's shape |
| set comparison across pinned topics | `discover --compare A B [C ...]` -- pairwise shared papers, bridges with ledger entries, mutual edges |
| how far is this over *one* family | `discover TOPIC --hops N --family F` -- the twin of the app's **Edges** picker, pinned to it by the single-family rows in `tests/webapp/hop_cases.json`. Both surfaces walked the union until the picker shipped; the flag reached only `--path` before that |

The terminal's own exclusives -- the resolution ladder, the
cross-encoder rescoring, the plural-match PageRank `neighbourhood` --
are all about *resolving a phrase*, not about exploring the graph. The
gap is one-directional.

### 13.2 Why "view-derived, not a corpus claim" frayed

Three developments in the two days after the decision undercut its
central premise, and are what motivated the amendment in section 2:

1. **The bench treats the browser's numbers as corpus claims.**
   `bench/topic_cluster_eval.py` drives `families.js` through `node`,
   scores its partitions against `content/topic_gold.toml`, and the
   measured inflation default is quoted in PRs. A number defended
   against gold data in a PR is a claim about the corpus, whatever the
   panel's caption says.
2. **Section 2's own screenshot rule condemns the placement.** Ego
   density, a community partition, "these two semantic clusters share
   no papers" -- these are exactly the numbers a survey introduction
   quotes, and this document says so itself (section 5.2).
3. **The drift problem is solved but used once.**
   `tests/webapp/hypergeometric_cases.js` pins the browser's absence
   arithmetic to scipy's answers from both runtimes. That pattern is
   the general answer to "two implementations would disagree", and it
   currently protects only the absence feature.

### 13.3 Path A: terminal twins, no artefact change

Keep section 2's decision intact and give the reader-side verbs the
same view-derived answers, labelled the same way: `discover
--clusters [--inflation X]`, `discover <topic> --brokerage`,
`discover --path A B --family overlap|semantic`, `discover --why A B`.
Each is computed on the fly from the artefact, written back nowhere,
and pinned to the JavaScript by a shared case file asserted from both
runtimes -- the `hypergeometric_cases.js` shape, once per twinned
computation. `--why` cost almost nothing -- `absence.js`'s inputs
(`members`, `n_docs`) were already read by the Python side -- and is
the first twin shipped: `chitragupta/discover/_absence.py`,
pinned to the same case file from a third runtime by
`tests/test_discover_why.py`. As a bonus,
`bench/topic_cluster_eval.py` could shed its `node` dependency, or keep
it as a third cross-check.

This is the recommended path: it restores parity without reopening the
artefact schema, and the maintenance cost -- one case file per twin --
is the cost the project has already accepted once.

### 13.4 Path B: reopen section 3's stored half, partially

Store only the quotable, selection-independent subset -- `communities`
at the gold-measured inflations, per-family `analysis` -- and let both
surfaces render it. The stronger fix for the screenshot rule, but it
means builder work, schema migration, and the configuration knobs
below. Worth reopening if path A's twin maintenance ever bites; the
gold set work has already produced exactly the evidence section 5.2
said a stored default would need.

What path B needs in `config.toml`, and nothing more:

- **Two MCL inflations, one per family** (`[enrich]`
  `topic_graph_mcl_inflation_overlap` / `_semantic`). Two because the
  gold measurement already shows the families peak at different values
  -- paper-sharing well above 2.0, semantic at 2.0 -- and one shared
  knob would fuse what the design refuses to fuse.
- **A default hierarchy cut** (target group count, ~8) -- only if the
  artefact records a canonical partition rather than leaving the cut to
  the slider. Prerequisite: extend `bench/topic_cluster_eval.py` to
  score cuts, which section 9 already lists as unscored.
- **PageRank damping** for `analysis.pagerank` -- a named constant
  (0.85) more than a knob, but section 2 requires it recorded and
  visible.

Deliberately knob-free: `edges_withheld` needs no cap (it is already
bounded to pairs sharing a paper); the MDS variant and dimensions and
the Burt formulas have no defensible alternative values (payload
entries, not knobs); and there is no master on/off switch -- the
honest-degradation pattern (fields absent, controls hidden with a note)
already produces that behaviour without a second mechanism.

### 13.5 Either way, one sentence of contract changes

The pure-renderer clause should promise *agreement between surfaces*,
not silence from one of them: any number either view presents must be
derivable by the other from the same artefact, pinned by shared test
vectors.

---

## 14. Could networkx replace cytoscape.js?

Asked when weighing path B, since consolidating the analytics into the
builder makes Python the place they run. The answer splits cleanly
along the computation/rendering line, and the app's own code has
already drawn it.

**Computation: yes, trivially -- because almost nothing uses
cytoscape's algorithms today.** Despite section 2's inventory of the
library, `families.js`, `ego.js` and `absence.js` ship their own MCL,
Dijkstra, BFS and hypergeometric tail, written out precisely so they
run under `node --test` with no canvas. Exactly two cytoscape
algorithms are live, both in `app.js`: the `cose` force layout that
places the ungrouped view (the grouped and ego regimes are `preset`
over positions `graph.js`/`ego.js` compute), and `closedNeighborhood()`
for the hover highlight -- which runs over the currently *drawn*
elements, bundles and paper diamonds included, so it is rendering-side
by nature and stays. So a builder-side consolidation takes nothing
away from the app that the app actually uses for analysis. On the
Python side:

- `networkx` covers PageRank, betweenness, and -- directly -- Burt's
  `effective_size` and `constraint`, plus ego-subgraph density.
- **MCL is not in networkx.** The options are a short scipy
  implementation over the sparse adjacency matrix (section 3 already
  notes numpy/scipy suffice for everything), a port of `families.js`'s
  own loop pinned by a shared case file, or continuing to drive the
  JavaScript through `node` as the bench does. What must not happen is
  an unpinned second implementation free to disagree with the one the
  browser shows.
- Classical MDS is scipy (one eigendecomposition), and the hierarchy
  is already `scipy.cluster.hierarchy`.

So networkx is a convenience, not a requirement -- section 3's verdict
("no new dependency is required, and adding `networkx` is a reasonable
alternative if the code-size ratchet prefers it") stands, with the MCL
caveat now explicit.

**Rendering: no.** networkx draws static matplotlib figures; the
offline, interactive, `file://`-forever canvas -- compound nodes,
expand/collapse, hover, chips -- is exactly the part cytoscape.js
exists for, and the static `--html` circle does not use cytoscape at
all. Consolidation would empty cytoscape's algorithms role, which is
already nearly empty (the `cose` layout above is the one removable
occupant -- precomputed coordinates would retire it), and leave its
rendering role, which nothing in Python replaces.

---

## Sources consulted

- `docs/TOPIC-DISCOVERY.md` (the `topic-graph` stage, the `corpus discover`
  reader, the resolution ladder, the precision tier, the graph page and the
  interactive app), `docs/RETRIEVAL.md`, `docs/examples/index.html` and the
  repository README, all at <https://prasad.talasila.in/chitragupta> and
  <https://github.com/prasadtalasila/chitragupta>.
- cytoscape.js layout and algorithm APIs, <https://js.cytoscape.org/>.
