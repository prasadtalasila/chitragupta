# 🧭 Exploring the topic graph: a view-by-view tour

Status: **guide.** Written 2026-09-07. [TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md)
is the reference for how every number here is computed;
[TOPIC-DISCOVERY-GRAPH.md](TOPIC-DISCOVERY-GRAPH.md) records the design
arguments and the improvement backlog. This page is the tour: what each
view of the interactive app is *for*, what it looks like on a real
corpus, and which terminal command answers the same question when one
does.

**Written for** you with a synced corpus in hand, deciding where the
next draft starts -- and for the reader someone handed the exported app
directory, who wants to know what the controls do without reading a
design document first.

The screenshots come from two corpora: a real 131-topic, 497-paper
library, and the five-paper
[sample project](examples/README.md) this repository commits so
every walkthrough has a reproducible subject. Each caption says which.

## 🧾 Getting the views in front of you

```console
chitragupta corpus discover --app topicapp/   # the interactive app (a directory)
chitragupta corpus discover --html topics.html # the one-file static page
```

Open `topicapp/index.html` straight from disk: the directory is
self-contained by construction -- no server, no install, no network,
and it keeps working after the corpus that produced it has moved on.
Every view below is a *view of the artefact*: nothing you do in the
app writes anything back, and the grouping and statistics it computes
in your browser are labelled as the view's own, not the corpus's.

## 🗺 The grouped opening view

![The app opens grouped: eight grey boxes, one per merge-tree
cut group, with bundled edges between them](images/discovery/grouped.png)

*Real corpus.* A 131-topic graph drawn loose is a hairball, so the app
opens at a cut of the stored merge tree yielding roughly eight groups,
each collapsed to one grey box carrying its member count. Edges between
boxes are bundles -- one per group pair per family, solid for shared
papers, dashed for semantic nearness, never fused. Click a box to list
what is in it; double-click to open just that one in place.

**Terminal:** `chitragupta corpus discover` prints the same corpus as a
topic map (every topic, its provenance and size), and `--groups 8`
prints this very cut.

The sidebar's collapsed "Uncovered seeds" panel lists the seed phrases
no topic covers -- the same `uncovered` list the terminal's topic map
reports -- and hides itself when every seed found a home.

## 🎚 The resolution slider

![The same corpus cut finer: twenty-five groups, singleton topics
emerging from their boxes](images/discovery/resolution.png)

*Real corpus.* The slider walks the same merge tree from one group to
no grouping at all; every position is a cut that actually exists in
the stored hierarchy, so the same position always gives the same
groups. This is a table of contents you can zoom continuously: start
at eight chapters, slide until the section you care about becomes its
own box, then open it.

**Terminal:** `chitragupta corpus discover --groups N` -- the same cut,
the same union-find, the same labels, and the same honesty about a
target the tree cannot reach.

## 🞋 Pinning topics: the ego view

![One pinned topic at the centre, its neighbourhood in concentric
rings by hop distance, the rest of the corpus dimmed to
background](images/discovery/ego-rings.png)

*Real corpus, "digital twin" pinned.* Type in the search box (labels
and each topic's own terms both match), Enter pins the topic as a
removable chip, and several chips compose. The whole corpus stays
drawn -- context is dimmed, not deleted, so you keep your sense of how
much of the corpus your selection is -- and the neighbourhood lays out
as rings by hop distance: one hop answers "what is next to this",
two answers "what would a chapter around this have to cover". The
panel lists the pinned topic's papers with their ledger detail.

**Terminal:** `chitragupta corpus discover "digital twin"` -- the same
papers, the same one-hop linked-topic lists with their evidence -- and
`--hops 2` (or `--hops all`) prints the rings themselves, ring one
typed by the family that reached each neighbour, with an honest count
of what the topic cannot reach. The dimmed context is the app's own.

## 🤝 Where the two families disagree

![The disagreement grid: pairs that share a semantic cluster but no
papers, and pairs that share papers but split
semantically](images/discovery/disagreement.png)

*Real corpus.* The button shows where the two families' stored MCL
partitions split -- Markov clustering, run once per family in the
pipeline at every inflation the slider can take, never on a merged
graph. Two topics in one semantic cluster that share no papers are a
literature that has not met itself: the observation a survey wants to
open with. The panel names the inflation it used and says the
partitions come from the artefact; the
[plain-terms section](TOPIC-DISCOVERY.md#-in-plain-terms-the-two-families-and-the-inflation-dial)
explains what moving it means. While the grid is showing, releasing
the slider re-reads at the new inflation, and only an export from an
older artefact still clusters in the browser.

**Terminal:** `chitragupta corpus discover --clusters [--inflation X]`
-- the same partitions, the same two disagreement lists, read from the
same artefact.

## 🛤 The path between two pinned topics

![Two pinned topics, the strongest chain of shared papers between
them highlighted on the canvas and itemised hop by hop in the
panel](images/discovery/path.png)

*Real corpus, "digital twin" and "application" pinned.* With exactly
two chips pinned, two buttons appear -- "path over shared papers" and
"path over semantic nearness", never one fused weight. Every hop
arrives with its evidence (shared citekeys, or the bridging pair), so
the whole chain is explainable by naming real papers. "No path over
semantic nearness" is a real answer, and often the interesting one.

**Terminal:** `chitragupta corpus discover --path "A" "B" --family
overlap|semantic` -- the same chain, walked from the same stored
matrices the app walks, every hop carrying its evidence, and "no path
over this family" as a real answer.

## 🚫 Why is there *no* edge here?

![Two pinned topics with no edge: the panel names their twelve shared
papers and reports that the overlap is what chance predicts, so no
edge was drawn](images/discovery/absence.png)

*Real corpus, "model-driven engineering" and "physical twin" pinned.*
The most instructive answer the app gives. These two topics share
twelve papers and still have no overlap edge -- because sharing twelve
papers between topics of size 58 and 56 in a 497-paper corpus is what
chance predicts (p = 0.02), and the hypergeometric gate refuses edges
chance explains. The app reads the refusal the pipeline stored
(`edges_withheld`, beside the edges it drew) and says it in words --
recomputing the same tail only for an export from an older run.
Nothing else in any view shows the gate's reasoning.

**Terminal:** `chitragupta corpus discover --why "model-driven
engineering" "physical twin"` -- the same shared citekeys, the same
tail, the same verdict, from the same artefacts, plus the one number
the app cannot show: the gate's stored threshold.

## 💠 Papers as nodes

![Two topics opened into their member papers, drawn as diamonds; a
paper belonging to both is highlighted as a
bridge](images/discovery/papers.png)

*Sample corpus, both seed topics opened.* Double-click a topic and its
member papers join the canvas as diamonds, labelled by citekey, with
the ledger title on hover. A paper held by more than one opened topic
is drawn once, linked to each, and highlighted -- the bridge becomes a
shape instead of a citekey repeated in two panels. Expansion is opt-in
and capped at three topics at a time.

**Terminal:** `chitragupta corpus discover --paper CITEKEY` answers the
inverse question -- every topic one paper belongs to, with scores --
and `--compare "A" "B"` names the bridge papers between named topics
directly, with their full ledger entries, which the app payload cannot
even carry.

## ⌨ The command map

All flags are documented per-flag in
[CLI.md](CLI.md#-chitragupta-corpus-discover); this is the view-to-verb
map in one place:

| You want | Command |
| --- | --- |
| the topic map | `chitragupta corpus discover` |
| one topic's papers and neighbours | `chitragupta corpus discover "PHRASE"` |
| one paper's topics | `chitragupta corpus discover --paper CITEKEY` |
| several topics side by side | `chitragupta corpus discover --compare "A" "B" ["C" ...]` |
| where the families disagree | `chitragupta corpus discover --clusters [--inflation X]` |
| the path between two topics | `chitragupta corpus discover --path "A" "B" --family F` |
| a topic's neighbourhood as rings | `chitragupta corpus discover "PHRASE" --hops 2` |
| why two topics have no overlap edge | `chitragupta corpus discover --why "A" "B"` |
| a Markdown overview to seed a draft | `chitragupta corpus discover "PHRASE" --out overview.md` |
| the static one-file page | `chitragupta corpus discover --html topics.html` |
| the interactive app | `chitragupta corpus discover --app topicapp/` |
| any of the above, machine-readable | add `--json` |

Every view now has a terminal twin;
[TOPIC-DISCOVERY-GRAPH.md §13](TOPIC-DISCOVERY-GRAPH.md#13-the-app-and-the-terminal-the-capability-gap-and-two-ways-to-close-it)
is the record of the gap this closed and how each twin is pinned.

## 📷 How the screenshots were made

Each view was exported by `corpus discover --app`, opened from
`file://` in headless Chrome, driven into the state shown by
dispatching the same DOM events a reader's clicks would, and captured
at 1440x900. No screenshot was edited; the sample-corpus shots are
reproducible from the committed
[sample project](examples/README.md) after a `corpus sync` there.
