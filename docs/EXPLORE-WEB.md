# 🕸 Explore the graph in the web app

Status: **how-to.**

What the exported app's controls do, for whoever was handed the app
directory or is deciding where the next draft starts.
[TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md) is the reference for how every
number is computed; [EXPLORE-CLI.md](EXPLORE-CLI.md) is the terminal
twin, and each view below names the command that answers the same
question there.

The screenshots come from a real 129-topic, 497-paper library and the
five-paper [sample project](examples/README.md) this repository
commits. Each caption says which.

## 🧾 Getting the app in front of you

```console
chitragupta corpus discover --app topicapp/
```

Open `topicapp/index.html` straight from disk. The directory needs no
server, install or network, keeps working after the corpus moves on,
and nothing you do in the app writes anything back.

## ⚖ What the pipeline computes, and what the app computes

Almost all the analytics are computed once, in Python, by the
`topic-graph` enrichment stage and stored in `content/topic_graph.json`,
which the app and the terminal both read, so the two agree to the
digit. Shared case files under `tests/webapp/` pin every runtime that
computes or consumes it to the same answers.

**Stored in the artefact:**

- the two edge families (overlap edges gated by the hypergeometric
  test, and mutual-top-k semantic edges) and the agglomerative merge
  `hierarchy`;
- **`edges_withheld`**: the pairs the gate refused, so the absence
  verdict quotes the stage instead of recomputing it;
- **`analysis`**: per topic and family, the degree, ego density, and
  Burt's effective size and constraint, behind the panel's
  theme-or-bridge reading;
- **`communities`**: MCL partitions of each family at every inflation
  the slider can take, behind the disagreement grid;
- **`paths`**: next-hop matrices from one Dijkstra per topic per
  family, so a path is a walk over stored data.

**Computed in the app**, because it depends on the live view, not the
corpus:

- rendering and interaction on the cytoscape canvas;
- click-to-latch focus: a click holds a node's neighbourhood
  highlighted while you read the panel, until you re-click it, click
  empty canvas, or press Esc (which first closes an open type-ahead,
  then an open filter picker, and never touches pinned chips);
- the slider's cut, the ego rings and papers-as-nodes expansion;
- the ungrouped layout (a deterministic circle refined by `cose`), left
  in the app deliberately because coordinates are presentation, not a
  corpus claim;
- fallbacks: an app exported from an artefact lacking a stored field
  computes it in the browser, pinned by the same case files, and its
  panel captions say which it shows.

## 🗺 The grouped opening view

![The app opens grouped: eight grey boxes, one per merge-tree
cut group, with bundled edges between them](images/discovery/grouped.png)

*Real corpus.* A 129-topic graph drawn loose is a hairball, so the app
opens at a cut of the stored merge tree yielding roughly eight groups,
each a grey box carrying its member count. Edges between boxes are
bundles, one per group pair per family: solid for shared papers, dashed
for semantic nearness, never fused. Click a box to list its members;
double-click to open it in place.

The sidebar's collapsed "Uncovered papers" panel lists the citekeys no
topic holds (the topic map's `uncovered` list), and hides itself when
there are none.

**Terminal:** `chitragupta corpus discover`, and `--groups 8` prints
this very cut.

## 🎚 The resolution slider

![The same corpus cut finer: twenty-five groups, singleton topics
emerging from their boxes](images/discovery/resolution.png)

*Real corpus.* The slider walks the same merge tree from one group to
none; every position is a cut in the stored hierarchy, so a position
always gives the same groups. Slide until the section you care about
becomes its own box, then open it.

**Terminal:** `chitragupta corpus discover --groups N`.

## 🞋 Pinning topics: the ego view

![One pinned topic at the centre, its neighbourhood in concentric
rings by hop distance, the rest of the corpus dimmed to
background](images/discovery/ego-rings.png)

*Real corpus, "digital twin" pinned.* Type in the search box (labels
and topic terms both match) and Enter pins the topic as a removable
chip; several chips compose. The rest of the corpus stays drawn,
dimmed. Rings show hop distance: one hop is "what is next to this", two
is "what would a chapter around this have to cover". The panel lists
the topic's papers with ledger detail, then its stored brokerage
numbers (theme or bridge?).

**Terminal:** `chitragupta corpus discover "digital twin"`; `--hops 2`
for the rings.

## 🤝 Where the two families disagree

![The disagreement grid: pairs that share a semantic cluster but no
papers, and pairs that share papers but split
semantically](images/discovery/disagreement.png)

*Real corpus.* The button shows where the two families' stored MCL
partitions split. Two topics in one semantic cluster that share no
papers are a literature that has not met itself, which a survey wants
to open with. The panel names the inflation used; the
[plain-terms section](TOPIC-DISCOVERY.md#-in-plain-terms-the-two-families-and-the-inflation-dial)
explains it. While the grid shows, releasing the slider re-reads at the
new inflation.

**Terminal:** `chitragupta corpus discover --clusters [--inflation X]`.

## 🛤 The path between two pinned topics

![Two pinned topics, the strongest chain of shared papers between
them highlighted on the canvas and itemised hop by hop in the
panel](images/discovery/path.png)

*Real corpus, "digital twin" and "application" pinned.* With exactly
two chips pinned, buttons appear for "path over shared papers" and
"path over semantic nearness", never fused into one weight. Every hop
carries its evidence (shared citekeys, or the bridging pair), so the
route is explained by real papers. "No path over semantic nearness" is
a real answer, and often the interesting one.

**Terminal:** `chitragupta corpus discover --path "A" "B" --family
overlap|semantic`.

## 🚫 Why is there *no* edge here?

![Two pinned topics with no edge: the panel names their nine shared
papers and reports that the overlap is what chance predicts, so no
edge was drawn](images/discovery/absence.png)

*Real corpus, "physical twin" and "topic-20" pinned.* These topics
share nine papers and have no overlap edge: nine shared papers between
topics of size 66 and 51 in a 497-paper corpus is what chance predicts
(p = 0.22), and the hypergeometric gate refuses edges chance explains.
The app reads the stored refusal (`edges_withheld`) and says it in
words.

**Terminal:** `chitragupta corpus discover --why "A" "B"`, which also
prints the gate's stored threshold.

## 💠 Papers as nodes

![Two topics opened into their member papers, drawn as diamonds; a
paper belonging to both is highlighted as a
bridge](images/discovery/papers.png)

*Sample corpus, two seed topics opened.* Double-click a topic and its
papers join the canvas as diamonds labelled by citekey, with the ledger
title on hover. A paper in more than one opened topic is drawn once,
linked to each, and highlighted as a bridge. Expansion is capped at
three topics at a time.

**Terminal:** `chitragupta corpus discover --paper CITEKEY` for one
paper's topics; `--compare "A" "B"` for the bridges between named
topics, with full ledger entries the app payload cannot carry.

## 🏷 Filtering by where a topic came from

![The header's Nodes picker open, reading "all but emergent", with seed,
keyword and corroborated ticked; the canvas shows only the groups that
survive](images/discovery/origins.png)

*Real corpus, emergent unticked.* The **Nodes** picker shows its state
when closed ("all 4 origins", or "all but emergent") and opens to one
row per class: **seed** (you wrote the phrase in
`content/seed_topics.toml`), **keyword** (the extractor proposed it into
`content/keywords.toml`), **corroborated** (both files name it), and
**emergent** (the topic model found it alone). Untick classes to see
only the literature you went looking for, or only what the corpus
proposed back.

The whole view follows: the type-ahead stops offering what is not
drawn, a pinned topic whose class goes out is un-pinned, a merge row
naming a hidden topic leaves the hierarchy panel, and a group box is
re-labelled from its visible members. The corpus's own arithmetic does
not change: the merge tree is not recut, and the absence verdict and
withheld-edge counts stay corpus-wide. The disagreement grid keeps the
pipeline's partitions and lists only pairs with both topics on the
canvas. A typed path still names every hop, and says when the route
left the filter. Unticking the last class is refused: an empty canvas
reads as an empty corpus.

**Terminal:** `chitragupta corpus discover --origins seed,corroborated`
takes the same four class names and composes with the topic map,
`--json`, `--html` and `--app`. `seed` and `keyword` each include the
corroborated topics, so a topic you named is not hidden because the
extractor agreed; `corroborated` alone asks for the intersection. Under
`--app` the flag decides what ships, and a class the export left out is
a disabled checkbox naming the run that excluded it, so "filtered out
at export" never looks like "this corpus has none".

## 🔗 Filtering by which kind of edge

![The header's Edges picker open, reading "shares papers only", with
semantically near unticked; the ego rings around a pinned topic are drawn
entirely in solid lines](images/discovery/families.png)

*Real corpus, one topic pinned at two hops, semantic nearness off.* The
**Edges** picker does the same for the two edge families: **shares
papers** (a shared-paper link that survived the hypergeometric gate)
and **semantically near** (cosine nearness between topic centroids),
each row carrying the legend's solid or dashed key.

Switching a family off takes its edges out of the hop walk as well as
off the canvas. With semantic nearness off, the second ring means "two
shared papers out", and a topic reached by one shared paper then one
cosine hop is not on it at all. Ring 1 is still split by which of the
families you have on reached each neighbour; past one hop nothing is
typed, since labelling a path with one family would claim more than the
graph supports. Unticking the last family is refused.

A switched-off family's path button is hidden and its path withdrawn.
Brokerage, the absence verdict and withheld-edge counts stay
corpus-wide, as the header caption says.

**Terminal:** `chitragupta corpus discover TOPIC --hops N --family
overlap|semantic` prints the same walk's rings over one family.
`--path A B --family F` walks a chain over one family, and `--clusters`
reports the two partitions separately.

## 📷 How the screenshots were made

Each view was exported by `corpus discover --app`, opened from
`file://` in headless Chrome, driven into the state shown by
dispatching the same DOM events a reader's clicks would, and captured
at 900x650 and twice the pixel density on 2026-11-20, narrow enough that
the page shows the app's text near its own size. No screenshot was
edited beyond `pngquant` compression; the sample-corpus shots are
reproducible from the committed
[sample project](examples/README.md) after a `corpus sync` there.
