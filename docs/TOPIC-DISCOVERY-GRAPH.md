# Improving the Chitragupta topic graph: display, interactivity and network analysis

Recommendations for `chitragupta corpus discover --app` (and, where noted, the
static `--html` page), written against the design recorded in
`docs/TOPIC-DISCOVERY.md`.

---

## 1. What exists today

From the documentation, the interactive app currently:

- ships as a directory: `index.html`, `app.js`, `style.css`, a vendored and
  pinned cytoscape.js, and `data.js` carrying the payload as a JavaScript
  assignment (because `fetch()` of local JSON is blocked under `file://`);
- offers type-ahead search over topic labels and each topic's top terms, with
  matches pinned as removable chips that compose;
- filters on selection: with topics pinned, only the selected topics and those
  related to them over both edge families stay on the canvas, and the layout
  re-runs on that subgraph;
- encodes provenance as node colour (hand-written seed phrase, machine-extracted
  keyword, both, emergent cluster), member count as node size, and overlap
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

## 2. The architectural decision to make first

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

A schema diff, so the builder and the app can be changed in one pass. Everything
here is derived from data the stage already computes; nothing needs a new model
download and nothing needs an LLM.

```jsonc
{
  "model": "...",
  "n_docs": 497, "n_topics": 53,
  "p_value": 0.01, "neighbors": 5,
  "corpus_mean": [0.0],

  // --- existing ---
  "topics": [{
    "label": "digital twin", "provenance": "seed",
    "size": 12, "centroid": [0.0],

    // --- NEW: per-topic analysis, keyed by edge family ---
    "analysis": {
      "overlap": {
        "degree": 4,
        "pagerank": 0.031,
        "betweenness": 0.12,          // normalised
        "ego_density": 0.33,          // edges among alters / possible
        "effective_size": 2.7,        // Burt
        "constraint": 0.41            // Burt
      },
      "semantic": { "...": "same shape" }
    },

    // --- NEW: deterministic seed coordinates (classical MDS, centred space) ---
    "xy": [0.42, -0.17]               // unit square; the app scales
  }],

  // --- existing ---
  "edges_overlap": [{
    "a": "...", "b": "...", "jaccard": 0.21, "overlap_coeff": 0.83,
    "p_value": 0.0004, "shared": ["citekey1", "citekey2"]
  }],
  "edges_semantic": [{
    "a": "...", "b": "...", "similarity": 0.74,
    "bridge": ["citekeyA", "citekeyB"]
  }],
  "hierarchy": [{ "id": "node-0", "a": "...", "b": "...", "distance": 0.31 }],

  // --- NEW: pairs that were tested and refused, with the reason ---
  "edges_withheld": [{
    "a": "digital twin", "b": "machine learning",
    "shared": ["dt2022"], "jaccard": 0.25, "overlap_coeff": 0.50,
    "p_value": 1.0, "reason": "hypergeometric"
  }],

  // --- NEW: communities, one partition per family, never fused ---
  "communities": {
    "overlap":  { "method": "mcl", "inflation": 2.0,
                  "members": { "cluster-0": ["label", "..."] } },
    "semantic": { "method": "mcl", "inflation": 2.0,
                  "members": { "cluster-0": ["label", "..."] } }
  },

  // --- NEW: what the app used to draw, for the footer and for reproduction ---
  "layout_params": { "seed_positions": "classical-mds", "mds_dims": 2 }
}
```

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

```css
node.dimmed { opacity: 0.12; }
node.dimmed { label: ""; }          /* or: text-opacity: 0 */
edge.dimmed { opacity: 0.06; }
```

```js
cy.batch(() => {
  cy.elements().addClass('dimmed');
  ego.removeClass('dimmed');
});
```

Set `events: 'no'` on `.dimmed` so dimmed nodes are not clickable and do not
steal hover. Keep a "hide context" toggle for the reader who wants today's
behaviour, and remember the choice in the hash (section 7.3).

### 4.2 Concentric rings by hop distance, not a force layout

Hop distance from the pinned set maps directly onto concentric rings. It is
deterministic, needs no physics, and extends rather than contradicts the "a
circle is legible" argument already made for the static page.

```js
// hop distance from the pinned set, over the currently enabled edge families
const ring = new Map();
cy.elements().bfs({
  roots: pinned,
  directed: false,
  visit: (v, e, u, i, depth) => { ring.set(v.id(), depth); }
});

const view = cy.nodes().filter(n => (ring.get(n.id()) ?? 99) <= maxHops);

view.union(view.edgesWith(view)).layout({
  name: 'concentric',
  concentric: n => -(ring.get(n.id()) ?? 99),   // hop 0 innermost
  levelWidth: () => 1,
  minNodeSpacing: 30,
  animate: 'end',
  animationDuration: 350
}).run();
```

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

```js
function cutTree(hierarchy, threshold) {
  // union-find over merges with distance <= threshold
  const parent = new Map();
  const find = x => (parent.get(x) === x ? x : (parent.set(x, find(parent.get(x))), parent.get(x)));
  // ... standard union-find; returns Map<label, clusterId>
}

function applyCut(threshold) {
  const groups = cutTree(DATA.hierarchy, threshold);
  cy.batch(() => {
    // ensure parent nodes exist, then re-parent
    cy.nodes('[!isCluster]').forEach(n => n.move({ parent: 'cluster-' + groups.get(n.id()) }));
  });
  runLayout();
}
```

This is the single highest-value change on this list: it turns an unreadable
53-node hairball into a table of contents that the reader can zoom into
continuously, using data that is already on disk.

### 5.2 MCL over each edge family, separately

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
in the browser first, cytoscape's own call is:

```js
const clusters = cy.elements().markovClustering({
  attributes: [e => e.data('overlap_coeff')],
  inflateFactor: 2.0
});
```

Note that MCL is sensitive to the inflation factor; it belongs in
`config.toml` under `[enrich]`, with the gold set (section 9) used to argue for
whatever default is chosen.

### 5.3 `cise` as the cluster-aware layout

Circular Spring Embedder takes explicit cluster assignments and draws each
cluster on its own circle, with inter-cluster edges between them. It is the
circle argument applied one level down, and it makes overlap communities legible
in a way a general force layout will not.

```js
view.layout({
  name: 'cise',
  clusters: node => groups.get(node.id()),
  animate: 'end',
  randomize: false,
  nodeSeparation: 12
}).run();
```

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
The app then uses `preset` as its base layout:

```js
view.layout({ name: 'preset', positions: n => scale(DATA.xy[n.id()]) }).run();
```

`fcose` becomes an optional "relax" button with `randomize: false`, seeded from
those positions. Same page, same machine, same picture, every time, and the
picture *means* something (proximity is centroid similarity) rather than being
whatever the force simulation settled into.

### 6.2 Order the circle by dendrogram leaf order

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
  machine-extracted keyword, double for a phrase both files name, none for an
  emergent cluster
- **size** → member count (unchanged)
- **shape** → reserved for node *type* if papers ever join the graph (7.5)

Border style carries a four-way categorical distinction perfectly well and is
robust to colour-vision differences, which fill is not.

### 7.3 Labels and semantic zoom

At 53 nodes labels collide; with papers expanded they are hopeless.

```js
cy.style()
  .selector('node')
    .style({
      'min-zoomed-font-size': 8,
      'text-wrap': 'wrap',
      'text-max-width': '90px',
      'text-background-color': '#fff',
      'text-background-opacity': 0.75,
      'text-background-padding': '2px'
    });

cy.on('zoom', () => {
  const z = cy.zoom();
  cy.batch(() => {
    cy.nodes('[isCluster]').toggleClass('show-label', z < 0.8);
    cy.nodes('[!isCluster]').toggleClass('show-label', z >= 0.8);
  });
});
```

Otherwise show labels only for the ego set and the top-N by member count, with
the full label on hover.

### 7.4 Hover neighbourhood highlighting

```js
cy.on('mouseover', 'node', e => {
  const nb = e.target.closedNeighborhood();
  cy.elements().not(nb).addClass('faded');
});
cy.on('mouseout', 'node', () => cy.elements().removeClass('faded'));
```

Cheap, and it is the interaction people expect from a graph.

### 7.5 Papers as nodes, on demand

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

`dijkstra` with weight `1 - strength` answers "what connects digital twins to
runtime verification in my corpus", and every hop arrives with either shared
citekeys or a bridge pair, so the path is explainable by naming real papers.

Offer it as **two buttons** — "path over shared papers" and "path over semantic
nearness" — rather than one fused weight. If a single mixed path is genuinely
wanted, show each hop's family on the hop itself and never report a single fused
distance for the path as a whole.

```js
const d = cy.elements('edge[family = "overlap"]').union(cy.nodes()).dijkstra({
  root: cy.$id(a),
  weight: e => 1 - e.data('overlap_coeff')
});
const path = d.pathTo(cy.$id(b));
```

### 7.7 Explain an absence

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

1. **Dendrogram-ordered circle** on the static `--html` page. One function, no
   new data, immediate legibility win, and it validates the ordering before
   anything depends on it.
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
   numbers to defend the inflation default.
7. **`cise`**, papers-as-nodes, and typed path finding, in whichever order the
   corpus's own questions demand.

---

## 12. Summary table

| Technique | Where it runs | New dependency | Answers |
| --- | --- | --- | --- |
| Concentric ego rings by hop | browser | none | what is next to this topic |
| Dim-not-remove context | browser | none | where am I in the whole corpus |
| Ego density, Burt brokerage | builder | none | is this a theme or a bridge |
| Hierarchy cut slider | browser (stored tree) | none | what are the broad areas |
| Compound parents + collapse | browser | expand-collapse | legibility at 50+ topics |
| MCL per edge family | builder | none | candidate survey sections |
| Overlap vs semantic disagreement | builder + browser | none | where the literature has not met itself |
| `cise` layout | browser | cise, cose-base | cluster structure at a glance |
| MDS seed coordinates | builder | none | a reproducible, meaningful layout |
| Typed shortest path | browser | none | what connects A to B, and via which papers |
| Withheld-edge explanation | builder + browser | none | why is there *no* edge here |
| Papers as nodes | browser | none | which papers bridge which topics |
| Hash-encoded view state | browser | none | shareable, bookmarkable views |

---

## Sources consulted

- `docs/TOPIC-DISCOVERY.md` (the `topic-graph` stage, the `corpus discover`
  reader, the resolution ladder, the precision tier, the graph page and the
  interactive app), `docs/RETRIEVAL.md`, `docs/examples/index.html` and the
  repository README, all at <https://prasad.talasila.in/chitragupta> and
  <https://github.com/prasadtalasila/chitragupta>.
- cytoscape.js layout and algorithm APIs, <https://js.cytoscape.org/>.
