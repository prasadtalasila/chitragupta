# ⌨ Explore the Graph — CLI

Status: **guide.** Written 2026-09-07.
[TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md) is the reference for how every
number here is computed; [CLI.md](CLI.md#-chitragupta-corpus-discover)
documents every flag; [EXPLORE-WEB.md](EXPLORE-WEB.md) is this page's
interactive twin, and records
[which computations live in the pipeline and which in the app](EXPLORE-WEB.md#-what-the-pipeline-computes-and-what-the-app-computes).
Every answer below comes from the same stored artefacts the app reads,
so the two surfaces can never disagree -- and every command honours
`--json` for scripts and the drafting skills.

**Written for** you at a terminal with a synced corpus, asking "what is
my corpus about, and where should the next draft start?" without
opening a browser.

## 🗺 The topic map

```console
$ chitragupta corpus discover
131 topics over 497 papers

  topic-0                       emergent  28 papers
  industry 4.0                  seed      60 papers
  devops                        seed      36 papers
  ...
```

*Real corpus, trimmed.* Every topic with its provenance (`seed` or
`emergent`, which is all the artefact records -- `--origins` is what
tells a hand-written seed from an extracted keyword and from a
corroborated phrase both files name), size and top terms -- plus the
seed phrases no topic covers, which is the "literature that has not met
itself" observation worth noticing first.

## 🔍 One topic

```console
chitragupta corpus discover "digital twin"
```

The topic's papers with full ledger entries and each paper's *other*
topics, both linked-topic families with their evidence (shared citekeys
on one side, the bridging pair on the other), and the topic's stored
brokerage numbers -- neighbours, ego density, Burt's effective size and
constraint, per family, with the theme-or-bridge reading. Any free
phrase resolves through the ladder (exact, fuzzy, hybrid BM25+cosine,
then paper search), and the output names which rung answered.

Add `--out overview.md` for an extractive Markdown overview grounded in
verbatim member-paper snippets, or `--hops N` to see the neighbourhood
as rings by hop distance instead of the flat lists -- ring one typed by
which family reached each neighbour, with an honest count of what the
topic cannot reach:

```console
$ chitragupta corpus discover "digital twin" --hops 1
digital twin — neighbourhood by hop distance

hop 1:
  asset  (via shared papers)
  digital shadow  (via both families)
  ...

unreached from here: 65 topics
```

The topic view itself closes with the stored brokerage numbers:

```console
brokerage (from the artefact):
  over shared papers: 13 neighbours, density 0.42, effective size 9.97,
    constraint 0.17 — reads as a bridge: its neighbours mostly do not connect
  over semantic nearness: 5 neighbours, density 0.20, effective size 4.19,
    constraint 0.34 — reads as a bridge: its neighbours mostly do not connect
```

## 🧩 The broad areas

```console
$ chitragupta corpus discover --groups 8
8 groups, cut at merge distance 0.813166

topic-23 +23
  topic-0
  topic-6
  ...
```

*Real corpus, trimmed.* The stored merge tree cut into as close to
eight groups as it allows --
the app's resolution slider as a view, with the same labels (biggest
member leads, the rest counted) and the same honesty when the target is
unreachable.

## 🤝 Where the families disagree

```console
$ chitragupta corpus discover --clusters --inflation 2.0
clusters at inflation 2, read from the artefact

over shared papers: 16 clusters
over semantic nearness: 39 clusters

talk alike, do not share papers (one semantic cluster, different paper-sharing clusters):
  structural health monitoring — design  (no shared papers at all)
  topic-8 — design  (1 shared paper)
  ...
```

*Real corpus, trimmed.* Both families' stored MCL partitions and the
two disagreement lists:
topics that talk alike but share no papers, and topics that share
papers but talk differently. Sharpest disagreements first, capped with
the drop reported.

## 🛤 The path between two topics

```console
$ chitragupta corpus discover --path "model-driven engineering" "physical twin" --family overlap
path over shared papers: model-driven engineering -> topic-60 -> physical twin

  model-driven engineering -> topic-60  (strength 0.80, via: beaumont_towards_2024, ...)
  topic-60 -> physical twin  (strength 0.31, via: combemale_model-based_2023, ...)
```

*Real corpus, evidence lists trimmed.* The strongest chain over one
family, hop by hop, each hop with its
evidence -- walked from the artefact's stored next-hop matrices.
`--family` is required: never one fused weight. "No path over this
family" is a real answer, and often the interesting one.

## 🚫 Why is there no edge here?

```console
$ chitragupta corpus discover --why "model-driven engineering" "physical twin"
model-driven engineering — physical twin
These share combemale_model-based_2023, ..., steinmetz_digital_2022, but
sharing 12 papers between topics of size 58 and 56 in a 497-paper corpus
is what chance predicts (p = 0.02, against a threshold of 0.01), so no
edge was drawn.
```

*Real corpus, citekey list trimmed.* The shared citekeys, both topic
sizes, the corpus size, the
hypergeometric tail the gate weighed, and the verdict -- including the
gate's stored threshold, which the app cannot show.

## ⚖ Several topics side by side

```console
$ chitragupta corpus discover --compare "digital twin" "model-driven engineering"
digital twin — model-driven engineering

union: 121 papers
held by all 2: heithoff_model-based_2024, pfeiffer_towards_2025, pfeiffer_towards_2025-1

pairwise shared papers:
  digital twin & model-driven engineering: 3: heithoff_model-based_2024, ...
...
```

*Real corpus, trimmed.* Pairwise shared papers, the papers held by
all of the named topics, the
bridge papers held by two or more (with full ledger entries), and the
edges among them with their evidence. Two to six topics; past six it
refuses with the count named rather than truncating silently.

## 💠 One paper, and the exports

```console
chitragupta corpus discover --paper kritzinger_digital_2018
chitragupta corpus discover --html topics.html
chitragupta corpus discover --app topicapp/
```

`--paper` inverts the question -- every topic one paper belongs to,
with scores. `--html` writes the one-file static page and `--app` the
interactive app directory; [EXPLORE-WEB.md](EXPLORE-WEB.md) is the tour
of what the app then shows.

## 🗒 The command map

| You want | Command |
| --- | --- |
| the topic map | `chitragupta corpus discover` |
| one topic's papers, neighbours and brokerage | `chitragupta corpus discover "PHRASE"` |
| one paper's topics | `chitragupta corpus discover --paper CITEKEY` |
| the broad areas, as N groups | `chitragupta corpus discover --groups N` |
| where the families disagree | `chitragupta corpus discover --clusters [--inflation X]` |
| the path between two topics | `chitragupta corpus discover --path "A" "B" --family F` |
| why two topics have no overlap edge | `chitragupta corpus discover --why "A" "B"` |
| several topics side by side | `chitragupta corpus discover --compare "A" "B" ["C" ...]` |
| a topic's neighbourhood as rings | `chitragupta corpus discover "PHRASE" --hops 2` |
| a Markdown overview to seed a draft | `chitragupta corpus discover "PHRASE" --out overview.md` |
| only the topics you named, or only the emergent ones | `chitragupta corpus discover --origins seed,corroborated` |
| the static one-file page | `chitragupta corpus discover --html topics.html` |
| the interactive app | `chitragupta corpus discover --app topicapp/` |
| any of the above, machine-readable | add `--json` |

Every one of the app's analytical views has a terminal twin here, each
pinned to the app's own arithmetic by a shared case file under
`tests/webapp/`;
[TOPIC-DISCOVERY-GRAPH.md §13](TOPIC-DISCOVERY-GRAPH.md#13-the-app-and-the-terminal-the-capability-gap-and-two-ways-to-close-it)
is the record of the gap this closed.
