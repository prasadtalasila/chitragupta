# Improving the Chitragupta topic graph: display, interactivity and network analysis

Status: **reasoning document.**

**Written for** someone changing `chitragupta corpus discover --app`, the
static `--html` page, or the `topic-graph` stage that feeds them.
[TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md) is the reference for how each
number is computed, and [EXPLORE-WEB.md](EXPLORE-WEB.md) is the tour of
what the app shows. This page records the rules any change has to keep,
and the ideas that were weighed and not built.

---

## 1. The constraints

Four constraints govern every change to the graph views.

1. **Offline forever.** No network reference anywhere. The exported app
   directory opens from `file://` after the corpus that produced it has
   moved on. Every vendored file is justified in
   `assets/webapp/vendor/README.md`, which today holds core cytoscape.js
   only.
2. **The surfaces agree.** Any number the app or the terminal shows must
   be derivable by the other from the same artefact, and a shared case
   file under `tests/webapp/` pins every runtime that computes it to the
   same answers.
3. **The two edge families are never merged.** Overlap edges (shared
   papers) and semantic edges (cosine nearness) answer different
   questions, and their disagreement is itself a discovery cue. No view
   fuses them into one weight, one ring, one partition or one path length.
4. **Reproducible pictures.** The same artefact gives the same picture.
   The static page places topics on a circle in the stored merge tree's
   leaf order (`_page.dendrogram_order`), and the app's layouts are
   deterministic: `preset` positions for the grouped and ego views, and a
   circle refined by `cose` with `randomize: false` for the ungrouped one.

---

## 2. What is stored, and what the browser computes

**The rule.** A number a reader could screenshot and quote in a paper is
a claim about the corpus, so the `topic-graph` stage computes it once and
stores it in `content/topic_graph.json`. A number that changes when the
reader clicks something else belongs to the view, so the browser
computes it.

**Stored by the stage** (`chitragupta/enrich/topic_graph.py`):

| Field | What it holds | Computed in |
| --- | --- | --- |
| `edges_withheld` | pairs sharing a paper that failed the gate, with citekeys and p | `topic_graph.py` |
| `analysis` (per topic, per family) | degree, ego density, Burt's effective size and constraint | `topic_brokerage.py` (networkx) |
| `communities` (per family) | MCL partitions at every slider inflation, 1.2 to 4.0 | `topic_mcl.py` (numpy) |
| `paths` (per family) | next-hop matrices, one Dijkstra per topic | `topic_paths.py` (networkx) |

Each terminal view reads the same field the app reads: `--why`,
the topic view's brokerage block, `--clusters` and `--path`.

**Computed in the browser:** rendering, pan and zoom, hover and
click-latched highlighting, type-ahead and chips, the resolution
slider's cut of the stored merge tree, the ego view's hop rings,
papers-as-nodes expansion, the origin and edge-family filters, and the
layouts.

**The fallback.** An app exported from an artefact that lacks a stored
field computes that field in the browser: `absence.js` recomputes the
hypergeometric tail, `ego.js` the brokerage numbers, `families.js` the
MCL partitions and the paths. The case files
(`hypergeometric_cases.js`, `brokerage_cases.json`, `mcl_cases.json`,
`path_cases.json`, `cut_cases.json`, `hop_cases.json`) keep the fallback
and the stage in agreement.

**When a new field may be stored.** All three must hold:

1. it is a deterministic function of data already in the artefact
   (edges, members, hierarchy), with no new corpus read and no model;
2. the parameters that produced it are recorded beside it, so the number
   is reproducible from the artefact alone;
3. a shared case file pins every runtime that computes or consumes it.

The precompute lives in `chitragupta/enrich/`. The discover layer
computes nothing about topics: `chitragupta/discover/_data.py` only
reads.

---

## 3. Ideas weighed and not built

Each of these was designed and left out. They are listed so that a
proposal can start from the recorded reasoning.

- **Stored seed coordinates (`xy`, `layout_params`).** Classical MDS over
  the centred topic centroids would give a layout whose distances mean
  centroid similarity. The app payload (`_page.build_payload`) does not
  forward `centroid`, and the app keeps the ungrouped layout as
  presentation, not as a corpus claim.
- **A parameter footer.** The gate's `p_value` and the semantic
  `neighbors` are in the artefact but not in the app payload, so the
  page cannot print them. `discover --why` prints the gate threshold.
- **PageRank and betweenness in `analysis`.** The stored brokerage
  covers degree, ego density, effective size and constraint only.
- **A cluster-aware layout (`cytoscape-cise`) and a relax layout
  (`cytoscape-fcose`).** Both need vendored extensions. Group collapse is
  hand-rolled in `graph.js` instead of using `cytoscape-expand-collapse`.
- **Origin as border style.** Origin is node colour today. Border style
  would free the fill for cluster membership and survives colour-vision
  differences better.
- **Semantic zoom for labels.** Labels that vanish below a zoom level and
  cluster labels that replace them.
- **A faint layer of withheld edges** drawn behind everything,
  toggleable.
- **A set-comparison panel for several pinned chips.** The terminal has
  `discover --compare`; the app has no twin.
- **View state in `location.hash`.** Bookmarkable and shareable views.
  No `location` reference exists in `assets/webapp/`.
- **Accessibility gaps.** `/` as a search shortcut, keyboard-removable
  chips, and a list view that hides the canvas. `Esc` deliberately does
  not clear chips; it closes the type-ahead, then an open picker, then
  releases a latched node.
- **Scoring the hierarchy cut against gold.**
  `bench/topic_cluster_eval.py` scores the MCL inflation against the
  `[[group]]` records in `content/topic_gold.toml`. The default cut of
  roughly eight groups is not scored.

---

## 4. Could networkx replace cytoscape.js?

For computation, it already has where it matters. The stage uses
networkx for brokerage and paths, numpy for MCL and scipy for the
hypergeometric gate and the merge tree. MCL is not in networkx, which is
why `topic_mcl.py` ports `families.js`'s own loop and `mcl_cases.json`
pins the two.

For rendering, no. networkx draws static matplotlib figures. The
offline, interactive canvas (compound nodes, collapse, hover, chips) is
what cytoscape.js is for. The app uses two cytoscape algorithms: the
`cose` layout for the ungrouped view and `closedNeighborhood()` for the
hover highlight, which runs over the drawn elements and so belongs to
rendering. The static `--html` page uses no cytoscape at all.
