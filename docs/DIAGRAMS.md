# 📐 The workflow, drawn fourteen ways

Status: **reference.**

Every diagram here describes the same pipeline. They come in four groups:

- [The ladder](#-the-ladder): six views of the whole workflow, ordered
  by how much you already know, from one that assumes nothing to one that
  assumes you are about to change the worker pool.
- [By genre](#-by-genre): three views of how the *writing* skills
  differ in what they ask of the pipeline. The six genre skills are not
  variations on one template; they disagree about how much of it is worth
  running.
- [Appendix](#-appendix): the same workflow in time order, and the
  ledger's state machine for one citekey.
- [Topic discovery](#-topic-discovery): two views of the corpus's
  topic structure and the reader over it, the one group here that applies
  *before* any draft exists ([TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md)).

Read the one that matches your question and ignore the rest.

One property holds in the eleven workflow views: **a genre skill loops on the citation
gate until it exits 0, and shows you nothing before that.** All six
genre skills' SKILL.md files carry that instruction, each in its own
words; `deep-research`'s reads *"Fix and re-run until `OK`. Never
present a draft that hasn't passed."* A gate failure is normally
something you never see.

**Drawing a figure is left out of every view.** When a genre skill
decides a figure is warranted, it hands off to the `figure-drawer`
skill, which starts the figure with `chitragupta figure new`, checks it
with `chitragupta figure check` and looks at it with
`chitragupta figure look`, then hands back
([FIGURE-DRAWER.md](FIGURE-DRAWER.md)). Where a view lists
`chitragupta review figure` among the review aids, that is the
draft-wide pass over a few of `figure check`'s rules, not the per-figure
check ([figure-checks/README.md](figure-checks/README.md)).

The fenced `mermaid` blocks below are the source of truth, and GitHub
renders them inline, so a change to the pipeline and a change to its
diagram land in the same diff. `docs/diagrams/` carries the same fourteen as
standalone `.mmd` sources and `.svg` exports, for slides, a paper, or a
viewer that doesn't render Mermaid, and does the same for every diagram
in the other documents; see [Editing these](#-editing-these) at the end.

---

## 🪜 The ladder

| # | Diagram | Written for | Answers |
| --- | --- | --- | --- |
| 1 | [One glance](#-1-one-glance) | Someone who has never heard of this | what are the steps, and who does each one? |
| 2 | [Your first run](#-2-your-first-run) | Someone installing it today | what do I type, in what order, and what does each step tell me? |
| 3 | [The full workflow](#-3-the-full-workflow) | Someone reading the source | what actually runs, what does it write, and where does the module I'm looking at fit? |
| 4 | [Everything on disk](#-4-everything-on-disk) | Someone deciding what to back up, or debugging a wrong file | what are all these files, who wrote them, and what is safe to delete? |
| 5 | [Gates and exit codes](#-5-gates-and-exit-codes) | Someone whose run just failed, or who is scripting it | why did this exit 1, and what is safe to retry automatically? |
| 6 | [Inside one parse](#-6-inside-one-parse) | Someone tuning `[parser].workers`, or changing the pool | what does a worker pool actually do here, and what happens when part of it dies? |

### 🔭 1. One glance

**Written for:** Someone who has never heard of this.
**Answers:** what are the steps, and who does each one?

This is deliberately the least detailed diagram here. Two properties do
all the work: phase 1 is the only entrance (citekeys come from your
BibTeX export and nowhere else), and phase 4 is the only exit, with no arrow
around it. This is the version in [the README](../README.md#-how-it-works).

The `FAIL` arrow loops back to **drafting**, not to you. A failing
gate is normally invisible: the skill discards the unsupported claim,
rewrites it and runs the gate again. You only get involved in the rarer
case where the paper isn't in the corpus yet, and that means going back
to phase 1 and adding it.

It carries no commands and no file paths on purpose, because it is for
someone who has not decided to install anything yet. A reader who
wants either has [CLI.md](CLI.md) for the commands and
[the artifacts diagram](#-4-everything-on-disk) for the paths.

Two enclosures show the division of labour. `LLM` holds drafting,
the gate and the dossier: the part a model runs, loops over on its own,
and keeps its working state in. `Author Proofs` holds publishing and
review: the part you run once a draft is finished. Nothing crosses
between them except a draft that has passed the gate.

The two dashed boxes are stores and reports, not steps.
`DOSSIER` ([DOSSIER.md](DOSSIER.md)) is written while a draft is
written and read back to change it, which is why revision does not
re-run the genre skill. `REVIEW` ([REVIEW.md](REVIEW.md)) is ten
advisory aids for a finished draft. Its arrow back to drafting is dotted
where the gate's is solid, because a review finding is yours to weigh
and does not block the pipeline.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  P0["<b>1 · CURATE</b><br/><i>you, in Zotero</i><br/>add papers, export BibTeX and files"]

  P1["<b>2 · SYNC</b><br/><i>deterministic, no LLM</i><br/>read bib → ledger → PDF text"]

  P2["<b>3 · DRAFT</b><br/><i>a genre skill, generative</i><br/>uses only the parsed corpus"]

  P3{{"<b>4 · VERIFY</b><br/>CITATION GATE"}}

  P4["<b>5 · PUBLISH</b><br/><i>markdown, tex, pdf</i>"]

  DOSS[("<b>DOSSIER</b><br/><i>working state</i>")]

  REV["<b>REVIEW</b><br/><i>advisory aids</i>"]

  P0 e1@==> P1 e2@==> P2
  e1@{ animate: true }
  e2@{ animate: true }
  P3 e3@== "PASS" ==> P4
  e3@{ animate: true }
  subgraph LLM
    direction TB
    P2 ==> P3
    P2 <-. "writes, reads back" .-> DOSS
    P3 -- "FAIL · loop until it passes" --> P2
  end

  subgraph Author Proofs
    direction TB
    P4 -. "on a finished draft" .-> REV
  end
  REV -. "a finding: revise from the dossier" .-> P2

  class P0 flow
  class P1 flow
  class P2 alt
  class P3 key
  class P4 flow
  class DOSS absent
  class REV absent

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### 🚀 2. Your first run

**Written for:** Someone installing it today.
**Answers:** what do I type, in what order, and what does each step tell me?

The same path as [the Quickstart](../README.md#-quickstart), drawn with
the two checkpoints where people most often go wrong. The first is the **Export
Files** tick box, which silently produces a bibliography with no PDFs
attached. The second is the first `python -m chitragupta.corpus ledger` after a
sync, which is where you find out whether anything became citable.

Exit codes are on the diagram because at this stage they are the only
feedback you have.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  A["<b>1 · Export from Zotero</b><br/>BibTeX, tick <b>Export Files</b>"]
  A1{{"Ticked<br/><b>Export Files</b>?"}}
  ATRAP["<b>The trap.</b> No PDFs,<br/>so an empty corpus (ZOTERO.md)"]

  B["<b>2 · Make a config</b><br/><code>cp config.toml.example config.toml</code>"]

  C["<b>3 · Install</b><br/><code>install_full_pipeline.sh all</code>"]

  D["<b>4 · Sync the corpus</b><br/><code>chitragupta corpus sync</code><br/>needs the venv"]
  D1{{"exit code?"}}
  DFAIL["<b>1</b>: a document didn't parse<br/><b>2</b>: another run holds the lock"]

  E["<b>5 · Look at what it found</b><br/><code>chitragupta corpus ledger</code>"]
  E1{{"Any rows<br/><code>parsed</code>?"}}
  EEMPTY["Nothing is citable yet;<br/>usually the Export Files trap"]

  F["<b>6 · Ask for a draft</b><br/><i>“write a survey section on …”</i><br/>the skill loops on the gate"]

  G["<b>7 · Or by hand</b><br/><code>draft gate</code> → <code>references</code> → <code>render</code>"]

  DONE(["<b>content/rendered/&lt;slug&gt;.pdf</b>"])

  A --> A1
  A1 -- yes --> B --> C --> D --> D1
  D1 -- "<b>0</b>" --> E --> E1
  E1 -- yes --> F --> DONE
  F -. "manually" .-> G
  G --> DONE
  A1 -- no --> ATRAP
  ATRAP -. "re-export" .-> A
  D1 -- "1 or 2" --> DFAIL
  DFAIL -. "re-run" .-> D
  E1 -- no --> EEMPTY
  EEMPTY -. "fix the export" .-> A

  class A,B,C,D,E,F,G flow
  class A1,D1,E1 flow
  class ATRAP,EEMPTY,DFAIL,DFAIL key
  class DONE alt

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### 🔄 3. The full workflow

**Written for:** Someone reading the source.
**Answers:** what actually runs, what does it write, and where does the module
I'm looking at fit?

The reference diagram. Every module on the corpus-to-gate-to-render spine
appears here exactly once.
[ARCHITECTURE.md](ARCHITECTURE.md) is the prose companion to it: the
same system in words, plus what each part needs to run.

It is drawn to make three things obvious. The thick edge from
`content/ledger.sqlite` to the gate is the entire safety argument: the
gate consults the ledger and nothing else. The gate sits on the only path
from a draft to `content/rendered/`. And the `FAIL` edge does not leave
the system: it runs back into the skill, which re-drafts and re-runs the
gate until it exits 0.

The enrichment layer's `docling` stage reads **the PDF itself**,
not `content/parsed/`. It is a second, independent extraction of the same
source, not a refinement of the first one, which is why it can produce
figures and layout-aware passages that `pdftotext` cannot.

Dotted edges are optional or conditional: the enrichment layer is opt-in,
and each consumer checks the stack exists before using it and degrades to
the lightweight default when it doesn't.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

    ZOT[("<b>1 · CURATE</b><br/>your Zotero library")]
    BIB["<b>papers/bibliography.bib</b> + <b>files/</b><br/>the source of truth for citekeys"]
    ZOT -- "Export, with files" --> BIB

    LED[("<b>2 · SYNC</b>, holds the lock<br/><b>content/ledger.sqlite</b><br/>one row per citekey, via <code>bib_reader.py</code>")]
    PT["<b>pdf_text/</b><br/>pdftotext or docling<br/><i>reports duplicates, stale keys</i>"]
    TXT["<b>content/parsed/&lt;citekey&gt;.txt</b>"]
    LED --> PT --> TXT

    XOR{{"<b>3 · RETRIEVE</b><br/>one ranker, never both"}}
    BM25["<b>retrieval.py</b> · BM25<br/>the default"]
    EMB["<b>embed_index.py</b> · semantic<br/>if chroma/ exists"]
    PASS["<b>passages.py</b><br/>the evidence ladder"]
    XOR -- "default" --> BM25
    XOR -.-> EMB
    BM25 --> PASS
    EMB --> PASS

    SKILLS["<b>4 · DRAFT</b>: genre skills<br/><code>.claude/skills/</code>"]
    DRAFT["<b>content/drafts/&lt;slug&gt;</b>"]
    SKILLS --> DRAFT

  GATE{{"<b>5 · THE CITATION GATE</b><br/>every citekey parsed in the ledger?"}}
  BLOCK["<b>REFUSED</b> · exit 1<br/>the write is blocked"]
  ITER["<b>the skill fixes it</b><br/>and re-runs the gate"]

    REFS["<b>6 · PUBLISH</b>: draft references<br/>IEEE list of cited keys"]
    REND["<b>draft render</b><br/>pandoc + citeproc"]
    OUT["<b>content/rendered/&lt;slug&gt;</b>"]
    REFS --> REND --> OUT

  SH["<b>OPTIONAL · ENRICHMENT</b>, same lock<br/>docling · embed · bertopic · extract-keywords<br/>seed-topics · converge · topic-graph"]

  SA["<b>REVIEW AIDS</b>, never a gate<br/>provenance · verbatim · coverage · synthesis<br/>figure · uncited · quotation · agenda<br/>support · union · digest"]

  BIB --> LED
  TXT --> XOR
  PASS --> SKILLS
  DRAFT --> GATE
  GATE -- "FAIL" --> BLOCK
  BLOCK --> ITER
  ITER == "until it passes" ==> SKILLS
  GATE == "PASS" ==> REFS
  BIB -. "the PDFs" .-> SH
  SH -.-> EMB
  OUT -. "afterwards" .-> SA

  class PT,BM25,PASS,REFS,REND flow
  class ZOT,BIB,LED,TXT,DRAFT,OUT alt
  class GATE,XOR key
  class BLOCK key
  class ITER flow
  class SKILLS flow
  class EMB,SH,SA absent

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### 📁 4. Everything on disk

**Written for:** Someone deciding what to back up, or debugging a wrong file.
**Answers:** what are all these files, who wrote them, and what is safe to delete?

Same pipeline, but the files are the nodes and the modules are the edge
labels: the inverse of the full workflow diagram.

Everything `sync` and `enrich` write under `content/` is disposable:
delete it and one `sync` plus one enrichment run rebuilds it. What you
author there is not: drafts, dossiers, book specs and seed topics
([MIGRATION.md](MIGRATION.md) lists them). Nothing under `papers/` is
disposable either, and neither is `config.toml`; both are gitignored and
per-host, so a backup needs them and the authored half of `content/`.

With `[enrich].docling_images` on, `docling` also writes each document's
figure bitmaps into `<doc>_artifacts/` and an index of them in
`<doc>.figures.json`: page, caption, bounding box and
the string to cite each figure by, for each picture that is a real
figure ([CONFIG.md](CONFIG.md#-docling_images) has what that excludes and
why). Those are a reading aid for checking a draft against its sources.
Having a paper in your library grants no right to reproduce its figures;
see DEVELOPER.md's "Figures and copyright".

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  IN["<b>YOURS</b>, per host<br/><code>papers/bibliography.bib</code><br/><code>papers/bibliography/files/</code><br/><code>config.toml</code>"]

  L1["<b>corpus sync</b> writes<br/><code>ledger.sqlite</code><br/><code>parsed/*.txt</code>, <code>*.passages.json</code><br/><code>pipeline.lock.db</code> while running"]

  L2["<b>enrichment</b> writes, opt-in<br/><code>docling/</code> · <code>chroma/</code><br/><code>topics.json</code> · <code>topic_set.json</code><br/><code>topic_seeds.json</code> · <code>topic_graph.json</code>"]

  L3["<b>caches</b>, safe to delete<br/><code>retrieval_index.json</code><br/><code>retrieval_passage_index.json</code><br/><code>docling_cache.json</code><br/><code>topic_embed_cache.json</code>"]

  L4["<b>through a skill</b><br/><code>drafts/</code> · <code>rendered/</code> · <code>review/</code>"]


  IN -- "bib_reader, pdf_text" --> L1
  IN -- "docling_parse" --> L2
  L1 -- "embed_index, topic_*" --> L2
  L1 -- "retrieval caches" --> L3
  L3 -- "BM25" --> L4
  L2 -. "semantic, passages" .-> L4
  L1 -- "references, passages" --> L4
  L4 == "<b>draft gate</b>, until exit 0" ==> L4
  L2 ~~~ L3


  class IN key
  class L1,L4 alt
  class L2,L3 absent

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### ✅ 5. Gates and exit codes

**Written for:** Someone whose run just failed, or who is scripting it.
**Answers:** why did this exit 1, and what is safe to retry automatically?

Exit codes are the API for unattended callers: `0` corpus in sync, `1`
corpus not in sync and a human is needed, `2` cycle skipped and no work
was lost.

Read the failure branch carefully. A document the backend cannot read
is **never retried**, since re-reading it every run would spend the same
minutes to reach the same answer, but it **never goes quiet either**: it
fails the run until someone deals with it. A failure caused by the *run*
instead of the *document* (a dead worker, a timeout, a CUDA OOM) retries
itself next time without being asked.

The gate's `exit 1` is the one failure on this diagram that usually
reaches nobody, because the skill loops on it itself.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  START(["<code>chitragupta corpus sync</code>"]) --> Q1

  Q1{{"<b>config present,<br/>lock free, .bib readable?</b>"}}
  Q1 -- yes --> LOOP
  Q1 -- no --> E2["<b>stops early</b><br/>no config: refuses to import<br/>lock held: <b>exit 2</b>, nothing lost<br/>no .bib: FileNotFoundError"]

  LOOP["<b>for each citekey</b><br/>upsert the ledger row"] --> Q4

  Q4{{"<b>resolvable PDF?</b>"}}
  Q4 -- yes --> Q5
  Q4 -- no --> SN["<code>no_pdf</code>"]

  Q5{{"<b>bytes changed?</b>"}}
  Q5 -- yes --> PARSE["<b>parse the PDF</b>"]
  Q5 -- no --> SK["<b>skipped</b>"]

  PARSE --> Q6
  Q6{{"<b>parse<br/>result</b>"}}
  Q6 -- "complete" --> OK["<code>parsed</code>"]
  Q6 -- "failed" --> PF["<code>parse_failed</code><br/>transient ones retried"]

  OK --> AGG
  SN --> AGG
  SK --> AGG
  PF --> AGG

  AGG{{"<b>anything<br/>unresolved?</b>"}} -- no --> E0["<b>exit 0</b><br/>corpus in sync"]
  AGG -- yes --> E1["<b>exit 1</b><br/>needs attention"]

  E0 --> GATEIN(["a skill drafts"])
  GATEIN --> G{{"<b>draft gate</b><br/>every citekey<br/>resolvable?"}}
  G -- "<b>exit 0</b>" --> GOOD["references → render"]
  G -- "<b>exit 1</b>" --> GBAD["<b>the write is blocked</b>"]
  GBAD --> GLOOP["<b>the skill re-drafts</b><br/>and re-runs the gate"]
  GLOOP == "<b>until exit 0</b>" ==> G
  GLOOP -. "paper not in corpus:<br/>it tells you to sync" .-> E1

  class Q1,Q4,Q5,Q6,AGG,LOOP,PARSE,G flow
  class E0,OK,SK,GOOD alt
  class GLOOP flow
  class E2,SN flow
  class E1,PF key
  class GBAD key

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### 📄 6. Inside one parse

**Written for:** Someone tuning `[parser].workers`, or changing the pool.
**Answers:** what does a worker pool actually do here, and what happens when
part of it dies?

The deepest view, and the only part of the repository that runs work in
parallel. Everything else (retrieval, gating, rendering) is
deliberately serial.

**The pool is clamped to the host, not to the
request.** The ceiling counts the CPUs *this process* may run on
(`os.sched_getaffinity`), not the machine's. An over-large request is
clamped *and said out loud*: silently obeying thrashes, and silently
ignoring leaves someone believing they configured something they did
not.

Five failure modes hang off the pool, each handled where it can be, and
the parent process keeps everything only it can do: sqlite has a single
writer, and the parent is the only place that can order results
deterministically. The full component-by-component write-up is in
[docs/PARALLELISM.md](PARALLELISM.md); the reasoning behind the lock is in
[docs/DESIGN.md](DESIGN.md).

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  subgraph PRE["<b>before the pool exists</b>"]
    direction TB
    P1["<b>prestart_pool()</b><br/>imports torch + docling in the background"]
    P2["<b>read bibliography.bib</b><br/>overlaps the import, ~1.5-2s saved"]
    P3["<b>ask the ledger</b><br/>which documents need a parse"]
    P1 -.-> P2 --> P3
  end

  W{{"<b>resolve_workers(n_docs)</b>"}}

  subgraph CEIL["<b>the ceiling is the host's</b>"]
    direction TB
    C1["<b>allowed_cpus()</b><br/>CPUs this process may use"]
    C2["<b>÷ 4 for docling</b><br/>one worker uses ~300% CPU"]
    C3["<b>clamped and reported</b>"]
    C1 --> C2 --> C3
  end

  SER["<b>workers = 1</b>, the default<br/>no executor, no pickling"]

  subgraph POOL["<b>the pool</b>"]
    direction TB
    EXE{{"backend?"}}
    TP["<b>ThreadPoolExecutor</b><br/><code>pdftotext</code> releases the GIL"]
    PP["<b>ProcessPoolExecutor</b><br/><code>docling</code>; forkserver, never fork"]
    LPT["<b>biggest file first</b><br/>so one long PDF never runs last"]
    DEV["<b>init_worker</b><br/>one CUDA card per worker"]
    EXE -- pdftotext --> TP
    EXE -- docling --> PP
    TP --> LPT
    PP --> LPT --> DEV
    FAIL["<b>five failure modes</b><br/>dead worker · hung pool · slow document<br/>CUDA OOM · Ctrl+C"]
    DEV --> FAIL
  end

  RET["<b>workers return</b> the exception<br/>instead of raising it"]

  PARENT["<b>the parent writes</b><br/>every ledger write, in bib order"]

  PARTIAL["<b>partial success is a failure</b><br/>raised before anything is written"]

  LOCK["<b>one writer at a time</b><br/><code>pipeline.lock.db</code>; a second writer exits 2"]

  P3 --> W
  CEIL -.-> W
  W -- "= 1" --> SER
  W -- "&gt; 1" --> EXE
  FAIL --> RET
  SER --> RET
  RET --> PARTIAL --> PARENT
  LOCK -.-> PRE

  class P1,P2,P3,C1,C2,C3,SER flow
  class W,EXE flow
  class TP,PP,LPT,DEV alt
  class FAIL,PARTIAL key
  class RET,PARENT flow
  class LOCK flow

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

---

## 🎭 By genre

The ladder above draws the pipeline as one thing. It is not quite one:
the six genre skills in `.claude/skills/` use very different amounts of
it.
The enrichment layer in particular is worth building for two of them,
largely wasted on two others, and reduced to a preview step for the fifth.

| Genre | Skills | Retrieval | Enrichment stages | `chitragupta.draft references` |
| --- | --- | --- | --- | --- |
| [Genre A: corpus-led](#-genre-a-corpus-led) | `survey-writer`, `deep-research` | BM25 **or** `embed_index` | `docling` + `embed`, both worth it | yes |
| [Genre B: teaching](#-genre-b-teaching) | `tutorial-writer`, `textbook-chapter-writer` | BM25 only | none | yes (custom heading) |
| [Genre C: LaTeX-native](#-genre-c-latex-native) | `thesis-chapter-writer` | BM25 only | none | **no, skipped** |

All five run the same gate, in the same loop.

### 📚 Genre A: corpus-led

**Skills:** `survey-writer`, `deep-research`

The corpus is the content. Nearly every sentence is a cited claim, so
these are the two skills that pay off the enrichment layer. `docling`
gives passages good enough to survive review; `embed` gives semantic
recall, finding the paper that makes your point in words you did not
search for. The shared genre steps every writer reads
(`.claude/skills-common/references/genre-steps.md` §1) name
`chitragupta/enrich/embed_index.py` as the ranker retrieval uses once it
is built, and these two genres gain the most from it.

Both read the same corpus the rest of the pipeline does, and that corpus
is the bibliography and nothing else, so every document either skill can
reach carries a citekey the gate will accept, and there is no class of
source that has to be discussed by title because it may not be cited.

`bertopic` sits off to one side because **no skill calls it.** It is for
you, deciding what the survey should be about before anything is drafted.

For the same reason, in the other direction, `chitragupta.review`'s
`coverage` aid ("retrieval surfaced
this paper: did the draft actually cite it?") only asks a meaningful
question in this genre.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  P0["<b>1 · CURATE</b><br/><i>you, in Zotero</i><br/>breadth is the whole job"]

  P1["<b>2 · SYNC</b><br/><code>chitragupta corpus sync</code><br/>ledger + parsed text"]

  HEAVY["<b>ENRICHMENT</b>, worth it here<br/><code>docling</code>: better passages<br/><code>embed</code>: semantic recall"]

  P2["<b>3 · DRAFT</b><br/><i>every sentence a cited claim</i><br/><b>survey-writer</b> · <b>deep-research</b>"]

  P3{{"<b>4 · VERIFY</b><br/><code>chitragupta draft gate</code><br/>densest citations: the gate earns its keep"}}

  FIX["<b>DISCARD DRAFT</b><br/>swap in a retrieved key, or drop the claim"]

  P4["<b>5 · PUBLISH</b><br/><code>draft references</code> · <code>draft render</code>"]

  AID["<b>REVIEW</b>, afterwards, never a gate<br/><code>coverage</code> matters most in this genre"]

  BERT["<b>bertopic</b><br/>for you, choosing the topic; no skill calls it"]

  P0 ==> P1 ==> P2 ==> P3
  P1 ==> HEAVY ==> P2
  P3 == "PASS" ==> P4
  P3 -- "FAIL" --> FIX
  FIX == "re-draft" ==> P2
  P4 -.-> AID
  P1 -.-> BERT -.-> P0

  class P0 flow
  class P1 flow
  class P2 alt
  class P3 key
  class P4 flow
  class FIX key
  class HEAVY flow
  class AID,BERT absent

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### 🎓 Genre B: teaching

**Skills:** `tutorial-writer`, `textbook-chapter-writer`

The corpus plays a minor part. Most of the content is original: worked
examples, exercises, a lesson that has to run. Citations are
deliberately confined: `tutorial-writer` bans them mid-lesson and allows
them only in a closing "Where to go next", and `textbook-chapter-writer`
uses them for motivation and background.

So the enrichment layer is mostly wasted here. Both skills read the same
shared genre steps that name `embed_index`, but they search so little
that `chitragupta.retrieval.search()`, which is stdlib BM25, serves them.
Building a semantic index to place four citations is not worth the
effort. The rendering they do want at the end is not an enrichment stage
at all: `render_output` is the drafting layer's own publish step, and
needs no package from the `enrich` group.

This is also the one genre where **the gate can legitimately pass with
zero citations**, and both SKILL.md files say so. An empty reference list
is a correct outcome for a tutorial.

The real risk in this genre is writing the wrong genre, such as a
tutorial that explains instead of instructing; a bad citekey is the
lesser risk.
Both skills open by warning about that, and no gate in this repository
can catch it.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  P0["<b>1 · CURATE</b><br/><i>you, in Zotero</i><br/>a handful of grounding papers"]

  P1["<b>2 · SYNC</b><br/><code>chitragupta corpus sync</code><br/>ledger + parsed text"]

  HEAVY["<b>ENRICHMENT</b><br/>not worth it here: BM25 is enough"]

  P2["<b>3 · DRAFT</b><br/><b>tutorial-writer</b>: cites only in “Where to go next”<br/><b>textbook-chapter-writer</b>: cites for background"]

  P3{{"<b>4 · VERIFY</b><br/><code>chitragupta draft gate</code><br/>may pass with zero citations"}}

  FIX["<b>DISCARD DRAFT</b><br/>drop the claim"]

  P4["<b>5 · PUBLISH</b><br/><code>draft references</code><br/><code>draft render</code>"]

  RISK["<b>the real risk</b><br/>writing the wrong genre; no gate catches it"]

  P0 ==> P1 ==> P2 ==> P3
  P1 -.-> HEAVY
  P3 == "PASS" ==> P4
  P3 -- "FAIL" --> FIX
  FIX == "re-draft" ==> P2
  P2 -.-> RISK

  class P0 flow
  class P1 flow
  class P2 alt
  class P3 flow
  class P4 flow
  class FIX flow
  class HEAVY absent
  class RISK key

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### ✍ Genre C: LaTeX-native

**Skills:** `thesis-chapter-writer`

The output isn't the deliverable. This skill emits a standalone `.tex`
fragment with `\citep`/`\citet` and no preamble, meant to be `\input` by
your own thesis document, so rendering produces a *preview*, not the
artifact that matters. A rendering failure
never blocks presenting the draft.

It is also the only skill that **deliberately skips `chitragupta.draft references`**.
Your thesis owns its own bibliography; a second reference list inside the
fragment would collide with it. That exception is easy to miss when
reading the README's `gate -> references -> render` chain, which is why
it gets its own diagram.

The gate is not relaxed for LaTeX: `chitragupta.draft gate` reads
`\citep`/`\citet` as readily as Markdown `[@key]`, and the loop-until-`OK`
rule is the same as in the other four skills.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  P0["<b>1 · CURATE</b><br/><i>you, in Zotero</i><br/>depth on one research question"]

  P1["<b>2 · SYNC</b><br/><code>chitragupta corpus sync</code><br/>ledger + parsed text"]

  HEAVY["<b>ENRICHMENT</b><br/>not worth it here: BM25, then filter by hand"]

  P2["<b>3 · DRAFT</b><br/><i>RQ-driven narrative</i><br/>a <code>.tex</code> fragment, <code>\citep</code>, no preamble"]

  P3{{"<b>4 · VERIFY</b><br/><code>chitragupta draft gate</code><br/>reads <code>\citep</code> as readily as Markdown"}}

  FIX["<b>DISCARD DRAFT</b><br/>fix and re-run until OK"]

  P4["<b>5 · PUBLISH</b>, the odd one out<br/>no <code>draft references</code>: your thesis owns them<br/><code>draft render</code> is a preview"]

  OUT["<b>the actual output</b><br/><code>\input{chapter-4}</code> in your thesis"]

  P0 ==> P1 ==> P2 ==> P3
  P1 -.-> HEAVY
  P3 == "PASS" ==> P4
  P3 -- "FAIL" --> FIX
  FIX == "re-draft" ==> P2
  P4 ==> OUT

  class P0 flow
  class P1 flow
  class P2 alt
  class P3 key
  class P4 flow
  class FIX key
  class HEAVY absent
  class OUT alt

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

---

## 📎 Appendix

These three answer narrower questions than the groups above, and are kept
separate for that reason.

### ⏱ One draft, in time order

The full workflow with time on the vertical axis instead of dependency. It
shows two things. The first is that **the gate runs
twice**: the PostToolUse hook fires on every write under `content/drafts/`, so
a bad citekey written to disk is refused straight back to the model even if a
skill forgets, and the skill then runs the gate itself, because the hook fires
only on the tool call that wrote the file. The second is the **loop**
that wraps both of them.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
sequenceDiagram
    autonumber
    actor You
    participant C as corpus<br/>sync + ledger
    participant Skill as genre skill
    participant Gate as draft gate

    rect rgba(255,247,237,0.6)
    Note over You: CURATE in Zotero
    end

    rect rgba(238,242,255,0.6)
    Note over You,C: SYNC, holding the lock
    You->>C: corpus sync
    C->>C: parse changed PDFs
    C-->>You: exit 0, 1 or 2
    end

    rect rgba(240,253,244,0.6)
    Note over You,Skill: DRAFT
    You->>Skill: "write a survey …"
    Skill->>C: search
    C-->>Skill: snippets, real citekeys
    Skill->>Skill: write the draft
    end

    rect rgba(254,242,242,0.7)
    Note over Skill,Gate: VERIFY, every write
    loop until exit 0
        Skill->>Gate: hook runs the gate
        Gate->>C: citekeys parsed?
        alt unresolved
            Gate-->>Skill: FAIL, blocked
            Skill->>Skill: swap or drop
        else all resolvable
            Gate-->>Skill: PASS
        end
    end
    Skill->>Gate: runs it again itself
    end

    rect rgba(250,245,255,0.6)
    Note over You,Skill: PUBLISH
    Skill-->>You: references, render: the PDF
    end

    Note over You,Gate: REVIEW afterwards, never a gate
```

### 📖 The life of a single citekey

The ledger's own state machine, for when the question is "why can't I
cite this paper?". `parsed` is the only state that makes a citekey
citable, and the self-loop on it is the incremental path that makes a
routine re-run nearly free.
`parse_failed` covers two kinds of failure: a transient one (a worker
died, a timeout) is retried on the next sync, and a deterministic one
only under `sync --reparse`.

Note that `stale` deletes nothing. A bib export that comes back short a
citekey is far more often a botched re-export or a `BIB_FILE` pointing at
the wrong path than an intentional deletion, so the row survives until you
re-run with `--remove-stale`.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
stateDiagram-v2
    direction TB

    [*] --> discovered : appears in the .bib

    discovered --> no_pdf : no file field
    discovered --> parsing : PDF bytes changed

    no_pdf --> parsing : you re-export with the PDF

    parsing --> parsed : text extracted
    parsing --> parse_failed : could not extract
    parse_failed --> parsing : transient: next sync<br/>otherwise: --reparse

    parsed --> parsing : PDF bytes changed
    parsed --> parsed : unchanged, skipped

    parsed --> stale : left the .bib
    no_pdf --> stale : left the .bib
    stale --> parsed : export fixed, re-synced
    stale --> [*] : sync --remove-stale

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### 🗺 Ladders and tiers, mapped

The six automatic-or-chosen decisions from
[LADDERS.md](LADDERS.md#-the-mapping),
each read left to right: the decision, what implements it, and what it
leaves on disk. Tiers are chosen before a run; ladders descend on their
own at run time. Two decisions leave nothing on disk, so neither shows up
in a backup. LADDERS.md holds the same mapping as a table.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  subgraph TIERS["<b>TIERS</b>: you choose, before the run"]
    direction LR
    PB["<b>parser backend</b><br/>config.toml"] --> M1["<code>pdf_text/</code>"] --> O1[/"parsed .txt"/]
    IN["<b>interpreter</b><br/>the command"] --> M2["<code>pyproject</code> groups"] --> O2(["nothing"])
    RF["<b>render format</b><br/><code>--format</code>"] --> M3["<code>render_output/</code>"] --> O3[/"rendered/"/]
  end

  subgraph LADDERS["<b>LADDERS</b>: the code descends, at run time"]
    direction LR
    EP["<b>evidence passages</b>"] --> M4["<code>passages.py</code>"] --> O4(["nothing: decides<br/>what may be quoted"])
    ET["<b>enrichment text</b>"] --> M5["<code>embed_index.py</code>"] --> O5[/"chroma/"/]
    AC["<b>accelerator</b>"] --> M6["<code>pdf_text/</code>"] --> O6(["nothing: decides<br/>parse speed"])
  end

  TIERS ~~~ LADDERS

  class PB,IN,RF flow
  class EP,ET,AC alt
  class O2,O4,O6 absent

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

---

## 🕸 Topic discovery

Two views of the discovery feature
([TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md)), the one group here that
lives before any draft exists: how a free phrase becomes a topic that
exists in the corpus, and what the two topic graphs are.

### 🪜 12. The resolution ladder

Which rung answered is part of the answer. The output's
`resolved_via` field names it, because a topic membership and a
plausible guess must never look alike.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  Q(["a phrase<br/><small><code>chitragupta corpus discover 'cyber replica'</code></small>"])
  E{"<b>1 · exact</b><br/><small>case-insensitive label match</small>"}
  F{"<b>2 · fuzzy</b><br/><small>difflib ≥ 0.75 — typos and near-forms only</small>"}

  subgraph H["<b>3 · hybrid</b> — two rankers, fused by rank"]
    direction TB
    BM["<b>BM25 over each topic's own vocabulary</b><br/><small>label + c-TF-IDF terms, one small document per topic —<br/>the same tokenizer and arithmetic as chitragupta/retrieval.py</small>"]
    SEM["<b>cosine vs the stored topic centroids</b><br/><small>query embedded, moved into centred space by the artefact's<br/>corpus_mean · needs the enrich extra — skipped with a note without it</small>"]
    RRF["<b>Reciprocal Rank Fusion</b><br/><small>score = Σ 1/(60 + rank) — Cormack et al. 2009<br/>rank-based, so the two scales never need calibrating</small>"]
    BM --> RRF
    SEM --> RRF
  end

  S["<b>4 · search fallback</b><br/><small>retrieval.search() over papers — labelled a search result, never<br/>a topic membership; each hit still annotated with its topics</small>"]
  T(["<b>the topic view</b><br/><small>members with ledger detail · each paper's other topics ·<br/>linked topics from both edge families · --out writes the overview</small>"])

  Q --> E
  E -- "hit" --> T
  E -- "miss" --> F
  F -- "hit" --> T
  F -- "miss" --> H
  RRF -- "cosine ≥ floor, or a<br/>lexical vocabulary hit" --> T
  RRF -- "below the floor" --> S

  class Q flow
  class E,F,BM,SEM,RRF flow
  class T alt
  class S absent

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

### 🕸 13. The two graphs

Two relations, two files, and the edge families are never merged into
one score. Where they disagree (many shared papers but different
subjects, or the same subject with none), the disagreement is itself a
discovery cue.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontSize": "14px",
    "primaryColor": "#E6F1F7",
    "primaryBorderColor": "#0072B2",
    "primaryTextColor": "#1A1A1A",
    "lineColor": "#0072B2",
    "secondaryColor": "#E6F5F1",
    "secondaryBorderColor": "#009E73",
    "tertiaryColor": "#FBEFE6",
    "tertiaryBorderColor": "#D55E00"
  }
}}%%
flowchart TB

  subgraph TP["<b>topic → papers</b> · content/topic_set.json<br/><small>written by the converge stage; discover displays it with ledger detail</small>"]
    direction TB
    DT1(("digital twin"))
    ML1(("machine learning"))
    P1["p1"]
    P2["p2"]
    P3["p3"]
    P4["p4"]
    DT1 --- P1
    DT1 --- P2
    ML1 --- P2
    ML1 --- P3
    ML1 --- P4
  end

  subgraph TT["<b>topic ↔ topic</b> · content/topic_graph.json<br/><small>written by the topic-graph stage; every edge is explainable by naming papers</small>"]
    direction TB
    DT2(("digital twin"))
    ML2(("machine learning"))
    DT2 ---|"<b>overlap</b><br/><small>shared members · jaccard + overlap coefficient ·<br/>kept only when hypergeometrically surprising · via: p2</small>"| ML2
    DT2 -.-|"<b>semantic</b><br/><small>average best-match cosine, centred space ·<br/>mutual top-k · bridge: p2 ↔ p3</small>"| ML2
  end

  TP -- "shared members are set arithmetic<br/>on the membership above" --> TT

  class DT1,ML1,DT2,ML2 flow
  class P1,P2,P3,P4 alt

  %% house roles: generated by scripts/render_diagrams.py --sync
  classDef flow fill:#E6F1F7,stroke:#0072B2,stroke-width:1.4px,color:#1A1A1A
  classDef alt fill:#E6F5F1,stroke:#009E73,stroke-width:1.4px,color:#1A1A1A
  classDef key fill:#FBEFE6,stroke:#D55E00,stroke-width:2px,color:#1A1A1A
  classDef absent fill:#FFFFFF,stroke:#8C8C8C,stroke-width:1.2px,stroke-dasharray:4 3,color:#1A1A1A
```

---

## ✏ Editing these

Each diagram is plain Mermaid in a fenced block above. GitHub renders
them, and so does any Mermaid-aware editor. **That block is the source of
truth.**

The same fourteen are also checked in as standalone files, so you can drop
one into a slide deck or a paper without copying it out of this document:

| Path | What it is |
| --- | --- |
| `docs/diagrams/<name>.mmd` | the Mermaid source, with a title line |
| `docs/diagrams/svg/<name>.svg` | for the web: GitHub, the docs site, a browser. On white, at the diagram's own width, laid out on a 1900px page |
| `docs/diagrams/pdf/<name>.pdf` | for a paper or slides: vector, one page cropped to the diagram, text selectable |

**Use the SVG only where a browser draws it.** Mermaid writes a
diagram's labels as HTML inside `<foreignObject>`, which every browser
renders and LaTeX, Inkscape, `rsvg-convert` and most slide tools do not:
they show the boxes and arrows with no text. The PDF comes from the same
browser render, so its labels survive anywhere. Turning
`htmlLabels` off instead was tried and rejected: the labels' `<b>`, `<i>`,
`<small>` and `<br/>` then print as literal tags and the spaces between
words collapse.

| Diagram | `<name>` |
| --- | --- |
| 1. One glance | `v1-overview` |
| 2. Your first run | `v2-first-run` |
| 3. The full workflow | `00-main-workflow` |
| 4. Everything on disk | `v3-artifacts` |
| 5. Gates and exit codes | `v4-gates-and-failure` |
| 6. Inside one parse | `v5-parallelism` |
| Genre A: corpus-led | `g1-corpus-led` |
| Genre B: teaching | `g2-teaching` |
| Genre C: LaTeX-native | `g3-thesis` |
| Appendix: one draft, in time order | `extra-sequence` |
| Appendix: the life of a single citekey | `extra-ledger-state` |
| Appendix: ladders and tiers, mapped | `ladders-mapping` |
| Topic discovery: the resolution ladder | `t1-discovery-ladder` |
| Topic discovery: the two graphs | `t2-topic-graphs` |

### 🗂 Diagrams in other documents

A Mermaid block anywhere else under `docs/` is exported the same way. The
line directly above its fence names it:

```markdown
<!-- diagram: book-index-flow -->
```

`--sync` refuses a block with no such line, and a name used twice, so no
diagram in the documentation goes without an export or overwrites
another's. There are fifteen:

| Diagram | In | `<name>` |
| --- | --- | --- |
| The four layers | [ARCHITECTURE.md](ARCHITECTURE.md) | `architecture-layers` |
| The four stages | [CORPUS-SEARCH.md](CORPUS-SEARCH.md) | `corpus-search-stages` |
| Why the rerank sits where it does | [CORPUS-SEARCH.md](CORPUS-SEARCH.md) | `corpus-search-rerank` |
| The guarantee everything else serves | [FEATURES.md](FEATURES.md) | `features-guarantee` |
| The four layers | [FEATURES.md](FEATURES.md) | `features-layers` |
| The dossier | [FEATURES.md](FEATURES.md) | `features-dossier` |
| Where the stage sits | [GROBID-CITATION-GRAPH.md](GROBID-CITATION-GRAPH.md) | `grobid-stage` |
| The citation graph | [GROBID-CITATION-GRAPH.md](GROBID-CITATION-GRAPH.md) | `grobid-citation-graph` |
| The terms | [LADDERS.md](LADDERS.md) | `ladders-terms` |
| The pipeline in one pass | [LADDERS.md](LADDERS.md) | `ladders-pipeline` |
| A single-context skill | [PROMPTS.md](PROMPTS.md) | `prompts-single-context` |
| The orchestrating context | [PROMPTS.md](PROMPTS.md) | `prompts-orchestrator` |
| A dispatched subagent's context | [PROMPTS.md](PROMPTS.md) | `prompts-subagent` |
| The short answer | [RETRIEVAL.md](RETRIEVAL.md) | `retrieval-short-answer` |
| How the book index is built | [book/BOOK-INDEX.md](book/BOOK-INDEX.md) | `book-index-flow` |

All twenty-nine are exports, not a second source. Edit the fenced block
first, then sync and re-render, or the two drift apart:

```bash
python scripts/render_diagrams.py --sync        # stamp the theme, copy blocks to .mmd
npm install -g @mermaid-js/mermaid-cli@11       # 12 dropped the -w flag used here
python scripts/render_diagrams.py v1-overview   # or no name, for all of them
```

`--sync` prints the names whose `.mmd` changed, which are the ones to
re-render. It touches no export itself. It stamps the house theme below
into every block it exports, in whichever document the block lives, and
writes `docs/stylesheets/mermaid.css`, which sets the docs site's own
Mermaid colours to the same palette: mkdocs-material's colour variables
otherwise override the theme, and an unclassed node turned amber.

### 🎨 The house theme

Every block opens with the same `%%{init: ...}%%` directive, and every
flowchart closes with the same four `classDef`s. Neither is typed by
hand: `--sync` generates both from the `\definecolor` block in
[TIKZ-STYLE.md](TIKZ-STYLE.md#-the-house-palette), so a diagram and a
paper figure share one palette with no hex written twice. GitHub renders
a fenced block as it stands and cannot include a shared file, so the
text has to be repeated in every block. Restamping replaces it rather
than adding a second copy, so after a palette change, `--sync` and a
re-render are the whole job. `tests/test_diagrams_in_sync.py` fails on
a block carrying an older theme, on a `classDef` of a diagram's own, and
on any hex the theme does not hold.

A node takes one of four roles, the same four the TikZ palette gives:

| Class | Drawn as | Use it for |
| --- | --- | --- |
| `flow` | blue tint, blue rule | the spine: steps, questions, anything a run passes through. An unclassed node looks the same |
| `alt` | green tint, green rule | a second class of node: a store beside the steps, a generative step beside the deterministic ones, a success end |
| `key` | vermilion tint, heavier rule | the one thing the figure is about, such as the citation gate and its refusal, or the ways a run stops |
| `absent` | white, grey dashed rule | off the path: review aids, caches, opt-in enrichment, things you may never see |

As in TikZ, `key` marks one idea per figure. Accent two things and
neither stands out. `--sync` adds the roles to flowcharts and state
diagrams, the two types Mermaid lets a `classDef` style. A sequence
diagram has no classes, and the directive alone gives it the palette.

The script runs `mmdc -i <name>.mmd -b white` twice, to
`svg/<name>.svg` with `-w 1900` and to `pdf/<name>.pdf` with `--pdfFit`,
and records the fingerprint of each `.mmd` whose two exports both
rendered in
`docs/diagrams/svg/sources.json`. `tests/test_diagrams_in_sync.py`
checks every export against that file, so an `.mmd` edited without a
re-render fails, naming the diagram to re-render. On a host that cannot
sandbox Chromium (a container, CI), pass `--puppeteer-config` a JSON
file holding `{"args": ["--no-sandbox"]}`. mermaid's layout is not
deterministic run to run, so a re-render of an unchanged source can move
edges; only the labels and the fingerprint are pinned.

If a diagram and the code disagree, the diagram is the bug.
