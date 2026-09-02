# 📐 The workflow, drawn eleven ways

Status: **reference.** Written 2026-08-06. Updated 2026-08-24.

Every diagram here describes the same pipeline. They come in three groups:

- **[The ladder](#-the-ladder)** -- six views of the whole workflow, ordered
  by how much you already know, from one that assumes nothing to one that
  assumes you are about to change the worker pool.
- **[By genre](#-by-genre)** -- three views of how the *writing* skills
  differ in what they ask of the pipeline. The five genre skills are not
  variations on one template; they disagree about how much of it is worth
  running.
- **[Appendix](#-appendix)** -- the same workflow in time order, and the
  ledger's state machine for one citekey.

Read the one that matches your question and ignore the rest.

One property holds in all eleven: **a genre skill loops on the citation
gate until it exits 0, and shows you nothing before that.** All five
SKILL.md files in `.claude/skills/` carry that instruction, four of them
in the same words: *"Fix and re-run until `OK`. Never present a draft
that hasn't passed."* A gate failure is normally something you never
see.

The fenced `mermaid` blocks below are the source of truth, and GitHub
renders them inline, so a change to the pipeline and a change to its
diagram land in the same diff. `docs/diagrams/` carries the same eleven as
standalone `.mmd` sources and `.svg` exports, for slides, a paper, or a
viewer that doesn't render Mermaid -- see [Editing these](#-editing-these)
at the end.

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

Deliberately the least detailed diagram here. Two properties do all the
work: phase 1 is the only entrance -- citekeys come from your BibTeX
export and nowhere else -- and phase 4 is the only exit, with no arrow
around it. This is the version in [the README](../README.md#-how-it-works).

The `GATE FAIL` arrow loops back to **drafting**, not to you. A failing
gate is normally invisible: the skill discards the unsupported claim,
rewrites it and runs the gate again. You only get involved in the rarer
case where the paper genuinely isn't in the corpus yet, and that means
going back to phase 1 and adding it.

It carries no commands and no file paths on purpose -- this is the diagram
for someone who has not decided to install anything yet, and a reader who
wants either has [CLI.md](CLI.md) for the commands and
[the artifacts diagram](#-4-everything-on-disk) for the paths.

**Two enclosures carry the division of labour.** `LLM` holds drafting,
the gate and the dossier: the part a model runs, loops over on its own,
and keeps its working state in. `Author Proofs` holds publishing and
review: the part you run once a draft is finished. Nothing crosses
between them except a draft that has passed the gate.

The two dashed boxes are stores and reports rather than steps.
**`DOSSIER`** ([DOSSIER.md](DOSSIER.md)) is written while a draft is
written and read back to change it -- the reason revision does not
re-run the genre skill. **`REVIEW`** ([REVIEW.md](REVIEW.md)) is seven
advisory aids for a finished draft; its arrow back to drafting is dotted
for the same reason the gate's is solid, namely that a review finding is
yours to weigh rather than something that blocks the pipeline.

```mermaid
flowchart LR

  P0["<b>1 · CURATE</b><br/><i>you, in Zotero</i><br/><br/>Add papers, export<br/>BibTeX + Export Files"]

  P1["<b>2 · SYNC</b><br/><i>the corpus layer — deterministic, no LLM</i><br/><br/>read bib → update ledger<br/>→ extract PDF text"]

  P2["<b>3 · DRAFT</b><br/><i>the drafting layer — generative</i><br/><br/>Ask a genre skill:<br/><i>“write a survey section on …”</i><br/>only use text from<br/>the parsed corpus"]

  P3{{"<b>4 · VERIFY</b><br/><i>machine-<br/>enforced</i><br/><br/>CITATION GATE"}}

  P4["<b>5 · PUBLISH</b><br/><i>as markdown, tex, pdf</i>"]

  DOSS[("<b>DOSSIER</b><br/><i>machine-facing working state</i>")]

  REV["<b>REVIEW</b><br/><i>author advisory"]

  P0 e1@==> P1 e2@==> P2
  e1@{ animate: true }
  e2@{ animate: true }
  P3 e3@== "CITATION GATE PASS" ==> P4
  e3@{ animate: true }
  subgraph LLM
    direction TB
    P2 ==> P3
    P2 <-. "writes it, then reads it back" .-> DOSS
    P3 -- "GATE FAIL · <b>loop until it passes</b>" --> P2
  end

  subgraph Author Proofs
    P4 -. "run it on a finished draft" .-> REV
    REV -. "a finding you act on —<br/>revise from the dossier, don't re-draft" .-> P2
  end

  classDef you fill:#fff7ed,stroke:#c2410c,stroke-width:1.5px,color:#431407
  classDef det fill:#eef2ff,stroke:#4f46e5,stroke-width:1.5px,color:#1e1b4b
  classDef gen fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px,color:#052e16
  classDef gate fill:#fef2f2,stroke:#dc2626,stroke-width:3px,color:#450a0a
  classDef out fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764
  classDef side fill:#f8fafc,stroke:#475569,stroke-width:1.5px,stroke-dasharray:4 3,color:#0f172a

  class P0 you
  class P1 det
  class P2 gen
  class P3 gate
  class P4 out
  class DOSS side
  class REV side
```

### 🚀 2. Your first run

**Written for:** Someone installing it today.
**Answers:** what do I type, in what order, and what does each step tell me?

The same path as [the Quickstart](../README.md#-quickstart), drawn with
the two checkpoints that actually catch people. The first is the **Export
Files** tick box, which silently produces a bibliography with no PDFs
attached. The second is the first `python -m chitragupta.corpus ledger` after a
sync, which is where you find out whether anything became citable.

Exit codes are on the diagram because at this stage they are the only
feedback you have.

```mermaid
flowchart TB

  A["<b>1 · Export from Zotero</b><br/><code>papers/bibliography.bib</code><br/><small>Format: BibTeX &nbsp;·&nbsp; tick <b>Export Files</b></small>"]
  A1{{"Did you tick<br/><b>Export Files</b>?"}}
  ATRAP["<b>The trap.</b> Without it you get metadata and no PDFs.<br/>Every entry then reports <i>no PDF attachment</i> — not an error,<br/>just an empty corpus. Same if you rename the companion folder:<br/><code>bib_reader</code> resolves <code>file</code> fields relative to the .bib.<br/><small>docs/ZOTERO.md</small>"]

  B["<b>2 · Make a config</b><br/><code>cp config.toml.example config.toml</code><br/><small>every key is optional — but the file must exist,<br/>or <code>chitragupta.config</code> refuses to import</small>"]

  C["<b>3 · Install</b><br/><code>pipx install poetry</code><br/><code>bash scripts/install_full_pipeline.sh all</code><br/><small><b>all</b> = OS packages (pdftotext, TeX Live, Pandoc) + Python.<br/>No stage argument = Python only.</small>"]

  D["<b>4 · Sync the corpus</b><br/><code>source .venv-full/bin/activate</code><br/><code>python -m chitragupta.corpus sync</code><br/><small>needs the venv — this is the one command that does</small>"]
  D1{{"exit code?"}}
  DFAIL["<b>1</b> — something didn't parse.<br/><small>The summary names each one.<br/>Fix or remove it; re-running is cheap.</small>"]
  DBUSY["<b>2</b> — another run holds the lock.<br/><small>Nothing was lost. Try again later.</small>"]

  E["<b>5 · Look at what it found</b><br/><code>python -m chitragupta.corpus ledger</code><br/><small>read-only, takes no lock, needs no venv —<br/>safe to run <i>while</i> a sync is going</small>"]
  E1{{"Rows with status<br/><code>parsed</code>?"}}
  EEMPTY["Nothing is citable yet.<br/><small>Almost always the Export Files trap above.<br/><code>--status no_pdf</code> tells you which entries and why.</small>"]

  F["<b>6 · Ask for a draft</b><br/><i>“write a survey section on digital twin composability”</i><br/><small>in Claude Code. The matching skill in <code>.claude/skills/</code><br/>picks it up and runs its own gate → references → render chain,<br/><b>looping on the gate until it exits 0</b> before showing you anything.</small>"]

  G["<b>7 · Or drive that chain by hand</b><br/><code>python -m chitragupta.draft gate &lt;draft&gt;</code> &nbsp;<i>← fix and repeat until OK</i><br/><code>python -m chitragupta.draft references &lt;draft&gt;</code><br/><code>python -m chitragupta.draft render &lt;draft&gt; --format pdf</code><br/><small>bare <code>python</code> — none of these need the venv</small>"]

  DONE(["<b>content/rendered/&lt;slug&gt;.pdf</b>"])

  A --> A1
  A1 -- no --> ATRAP
  ATRAP -. "re-export" .-> A
  A1 -- yes --> B --> C --> D --> D1
  D1 -- "1" --> DFAIL
  D1 -- "2" --> DBUSY
  DBUSY -. "re-run" .-> D
  DFAIL -. "re-run" .-> D
  D1 -- "<b>0</b> — corpus in sync" --> E --> E1
  E1 -- no --> EEMPTY
  EEMPTY -. "fix the export" .-> A
  E1 -- yes --> F --> DONE
  F -. "same chain, manually" .-> G
  G --> DONE

  classDef step fill:#eef2ff,stroke:#4f46e5,stroke-width:1.5px,color:#1e1b4b
  classDef check fill:#fefce8,stroke:#a16207,stroke-width:1.5px,color:#422006
  classDef trap fill:#fef2f2,stroke:#dc2626,stroke-width:1.5px,color:#450a0a
  classDef done fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#052e16

  class A,B,C,D,E,F,G step
  class A1,D1,E1 check
  class ATRAP,EEMPTY,DFAIL,DBUSY trap
  class DONE done
```

### 🔄 3. The full workflow

**Written for:** Someone reading the source.
**Answers:** what actually runs, what does it write, and where does the module
I'm looking at fit?

The reference diagram. Everything in `chitragupta/` appears here exactly once.
[ARCHITECTURE.md](ARCHITECTURE.md) is the prose companion to it -- the
same system in words, plus what each part needs to run.

Three things it is drawn to make unmissable. The thick edge from
`content/ledger.sqlite` to the gate is the entire safety argument -- the
gate consults the ledger and nothing else. The gate sits on the only path
from a draft to `content/rendered/`. And the `FAIL` edge does not leave
the system: it runs back into the skill, which re-drafts and re-runs the
gate until it exits 0.

Note that the enrichment layer's `docling` stage reads **the PDF itself**,
not `content/parsed/`. It is a second, independent extraction of the same
source, not a refinement of the first one -- which is why it can produce
figures and layout-aware passages that `pdftotext` cannot.

Dotted edges are optional or conditional: the enrichment layer is opt-in,
and each consumer checks the stack exists before using it and degrades to
the lightweight default when it doesn't.

```mermaid
flowchart TB

  %% ─────────────── 1 · CURATE ───────────────
  subgraph S0["<b>1 · CURATE</b> — you, in Zotero. The pipeline never fetches a paper."]
    direction TB
    ZOT[("Zotero library")]
    BIB["<b>papers/bibliography.bib</b><br/><i>the source of truth for citekeys</i>"]
    ATT[/"<b>papers/bibliography/files/&lt;id&gt;/*.pdf</b><br/><small>the companion folder Zotero writes beside the .bib —<br/>never rename it, the <code>file</code> fields are relative paths</small>"/]
    ZOT -- "Export · BibTeX + Export Files" --> BIB
    ZOT --> ATT
  end

  %% ─────────────── 2 · SYNC ───────────────
  subgraph S1["<b>2 · SYNC</b> — the corpus layer · deterministic, no LLM, safe to run unattended · <code>chitragupta corpus sync</code> · holds the run lock"]
    direction TB
    BR["<b>chitragupta/bib_reader.py</b><br/><small>the only module that reads the .bib</small>"]
    LED[("<b>content/ledger.sqlite</b><br/><small>one row per citekey: status, bib_fields,<br/>PDF fingerprint — re-parse only what moved</small>")]
    PT["<b>chitragupta/pdf_text/</b> — extract text<br/><small>backend <code>pdftotext</code> · or <code>docling</code><br/>serial by default; opt-in worker pool</small>"]
    TXT[/"<b>content/parsed/&lt;citekey&gt;.txt</b>"/]
    ADV["<i>reported, never fatal:</i><br/>near-duplicates · parse-quality warning · stale citekeys<br/><small>deletion needs <code>--remove-stale</code></small>"]
    BR --> LED --> PT --> TXT --> ADV
  end

  %% ─────────────── 3 · RETRIEVE ───────────────
  subgraph S2["<b>3 · RETRIEVE</b> — the only evidence a writer is given · <b>one ranker or the other, never both</b>"]
    direction LR
    XOR{{"which ranker?<br/><small>the genre skill picks</small>"}}
    BM25["<b>chitragupta/retrieval.py</b> · BM25<br/><small>stdlib keyword overlap, cached term-frequency index.<br/><b>the default every skill starts from</b></small>"]
    EMB["<b>chitragupta/enrich/embed_index.py</b> · semantic<br/><small>same <code>search(q, k)</code> signature, so it is a drop-in.<br/>Named as the alternative by <code>survey-writer</code><br/>and <code>deep-research</code> — and only by those two.</small>"]
    PASS["<b>chitragupta/passages.py</b> · evidence ladder<br/><small>docling sidecar → page → pdftotext</small>"]
    XOR -- "default" --> BM25
    XOR -. "only if content/chroma/ was built" .-> EMB
    BM25 --> PASS
    EMB --> PASS
  end

  %% ─────────────── 4 · DRAFT ───────────────
  subgraph S3["<b>4 · DRAFT</b> — the drafting layer · generative, on demand, reviewed by you"]
    direction TB
    SKILLS["<b>.claude/skills/</b> — five genre skills<br/>survey-writer · thesis-chapter-writer · textbook-chapter-writer<br/>tutorial-writer · deep-research"]
    DRAFT[/"<b>content/drafts/&lt;slug&gt;.md | .tex</b>"/]
    SKILLS --> DRAFT
  end

  %% ─────────────── 5 · GATE ───────────────
  GATE{{"<b>THE CITATION GATE</b> · <code>chitragupta draft gate</code><br/>Is every citekey in this draft present in the ledger?<br/><small>run twice: by the PostToolUse hook on every write under content/drafts/,<br/>and by the skill itself before it shows you anything</small>"}}
  BLOCK["<b>REFUSED</b> · exit 1<br/><small>the write is blocked and the chain stops</small>"]
  ITER["<b>the skill fixes it and re-runs — itself</b><br/><small>“Fix and re-run until <code>OK</code>. Never present a draft that hasn't<br/>passed.” — every SKILL.md carries this instruction.<br/>It swaps the bad key for one retrieval actually returned, or drops<br/>the claim. You are shown nothing until the gate is green.</small>"]

  %% ─────────────── 6 · PUBLISH ───────────────
  subgraph S5["<b>6 · PUBLISH</b> — stdlib only, no venv needed"]
    direction TB
    REFS["<b>chitragupta draft references</b><br/><small>IEEE ## References, numbered by first appearance,<br/>built only from citekeys the draft actually cites.<br/>Skipped for thesis .tex fragments, where the<br/>surrounding LaTeX owns the bibliography.</small>"]
    REND["<b>chitragupta draft render</b><br/><small>pandoc --citeproc + assets/csl/ieee.csl</small>"]
    OUT[/"<b>content/rendered/&lt;slug&gt;.pdf | .tex | .docx | .md</b>"/]
    REFS --> REND --> OUT
  end

  %% ─────────────── ENRICHMENT (side branch) ───────────────
  subgraph SH["<b>OPTIONAL · ENRICHMENT LAYER</b><br/><code>chitragupta enrich --stages …</code> · same run lock"]
    direction TB
    H1["<b>docling</b> — <i>reads the PDF itself, not content/parsed/</i><br/><small><b>content/docling/&lt;doc&gt;.md</b> — layout-aware text<br/><b>&lt;doc&gt;.passages.json</b> — the quotable-passage sidecar<br/><b>&lt;doc&gt;_artifacts/</b> — figure bitmaps, written by Docling<br/><b>&lt;doc&gt;.figures.json</b> — page, caption, cite string per figure<br/>the last two only when <code>[enrich].docling_images</code> is on</small>"]
    H2["<b>embed</b><br/><small>content/chroma/ — drop-in search(q,k)</small>"]
    H3["<b>bertopic</b><br/><small>content/topics.json — emergent clusters</small>"]
    H4["<b>seed-topics</b><br/><small>content/topic_seeds.json — the author's own topic phrases, many-to-many</small>"]
    H5["<b>converge</b><br/><small>content/topic_set.json — bertopic's clusters and seed-topics' phrases, joined</small>"]
    H6["<b>topic-graph</b><br/><small>content/topic_graph.json — how the topics relate: shared-member and semantic edges</small>"]
    H1 --> H2 --> H3 --> H4 --> H5 --> H6
  end

  %% ─────────────── AIDS (side branch) ───────────────
  subgraph SA["<b>REVIEW AIDS</b> — run these afterwards; none of them is a gate"]
    direction TB
    A1["<b>chitragupta review provenance</b><br/><small>what in the source supports this claim?</small>"]
    A2["<b>chitragupta review verbatim</b><br/><small>verbatim overlap · locate a phrase by page<br/><i>the scan runs at the end of every skill</i></small>"]
    A3["<b>chitragupta review coverage</b><br/><small>retrieval surfaced it — did the draft cite it?</small>"]
    A4["<b>chitragupta review synthesis</b><br/><small>how many sources does each unit rest on?</small>"]
    A5["<b>chitragupta review figure</b><br/><small>overlapping nodes · protrusion · overlong labels</small>"]
    A6["<b>chitragupta review uncited</b><br/><small>which sentences cite nothing at all?</small>"]
    A7["<b>chitragupta review quotation</b><br/><small>is each quoted span really in that source?</small>"]
    A8["<b>chitragupta review agenda</b><br/><small>merges the eight draft-level aids into one ranked worklist</small>"]
    A9["<b>chitragupta review support</b><br/><small>does the source entail this claim?</small>"]
    A10["<b>chitragupta review union</b><br/><small>did assembling the book lose a unit's citekey?</small>"]
  end

  %% ─────────────── SPINE ───────────────
  BIB --> BR
  ATT --> PT
  TXT --> XOR
  PASS --> SKILLS
  DRAFT --> GATE
  GATE -- "FAIL" --> BLOCK
  BLOCK --> ITER
  ITER == "re-draft · <b>loop until it passes</b>" ==> SKILLS
  GATE == "PASS · exit 0" ==> REFS
  LED == "the ledger is the<br/>only authority the<br/>gate consults" ==> GATE
  LED --> REFS
  ATT -. "the PDF, direct" .-> H1
  H1 -.-> PASS
  H2 -.-> EMB
  DRAFT --> SA

  %% ─────────────── STYLE ───────────────
  classDef src fill:#eef2ff,stroke:#4f46e5,stroke-width:1.5px,color:#1e1b4b
  classDef store fill:#fff7ed,stroke:#c2410c,stroke-width:1.5px,color:#431407
  classDef gate fill:#fef2f2,stroke:#dc2626,stroke-width:2.5px,color:#450a0a
  classDef bad fill:#dc2626,stroke:#7f1d1d,color:#ffffff
  classDef loop fill:#fefce8,stroke:#a16207,stroke-width:2px,color:#422006
  classDef gen fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px,color:#052e16
  classDef aid fill:#f8fafc,stroke:#94a3b8,stroke-dasharray:4 3,color:#0f172a
  classDef heavy fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764

  class BR,PT,BM25,PASS,REFS,REND src
  class ZOT,BIB,ATT,LED,TXT,DRAFT,OUT store
  class GATE,XOR gate
  class BLOCK bad
  class ITER loop
  class SKILLS gen
  class A1,A2,A3,A4,A5,A6,A7,A8,A9,A10,ADV aid
  class H1,H2,H3,EMB heavy
```

### 📁 4. Everything on disk

**Written for:** Someone deciding what to back up, or debugging a wrong file.
**Answers:** what are all these files, who wrote them, and what is safe to delete?

Same pipeline, but the files are the nodes and the modules are the edge
labels -- the inverse of the full workflow diagram.

The split that matters: everything under `content/` is disposable. Delete
the directory and one `sync` plus one enrichment run rebuilds all of it.
Nothing under `papers/` is disposable, and neither is `config.toml`; both
are gitignored and per-host, so they are also the only things a backup
needs to contain.

With `[enrich].docling_images` on, `docling` also writes each document's
figure bitmaps into `<doc>_artifacts/` and an index of them in
`<doc>.figures.json` -- page, caption, and the string to cite each figure
by. Those are a reading aid for checking a draft against its sources.
Having a paper in your library grants no right to reproduce its figures;
see DEVELOPER.md's "Figures and copyright".

```mermaid
flowchart TB

  subgraph IN["<b>YOURS</b> — hand-curated, gitignored, per host"]
    direction LR
    BIB[/"papers/bibliography.bib"/]
    PDF[/"<b>papers/bibliography/files/&lt;id&gt;/*.pdf</b><br/><small>Zotero's companion folder, written beside the .bib<br/>by <b>Export Files</b> — renaming it breaks every<br/><code>file</code> field silently</small>"/]
    CFG[/"config.toml"/]
  end

  subgraph GEN["<b>GENERATED</b> — <code>content/</code>, all of it disposable: delete it and re-run"]
    direction TB

    subgraph L1["written by <code>chitragupta corpus sync</code> — the corpus layer"]
      direction LR
      LED[("content/ledger.sqlite")]
      TXT[/"content/parsed/&lt;citekey&gt;.txt<br/><small>form feeds between pages, either backend</small>"/]
      CPS[/"content/parsed/&lt;citekey&gt;.passages.json<br/><small>only with <code>[parser].backend = docling</code>;<br/>cleared before every re-parse</small>"/]
    end

    subgraph L2["written by the enrichment layer — opt-in"]
      direction LR
      DOC[/"<b>content/docling/&lt;doc&gt;.md</b><br/>+ &lt;doc&gt;.passages.json<br/><b>+ &lt;doc&gt;_artifacts/*.png</b> — figure bitmaps<br/><b>+ &lt;doc&gt;.figures.json</b> — page, caption, cite string<br/><small>the last two only when <code>[enrich].docling_images</code><br/>is on; Docling reads the <b>PDF</b>, never content/parsed/</small>"/]
      CHR[("content/chroma/")]
      TOP[/"content/topics.json"/]
      SED[/"content/topic_seeds.json"/]
      CVG[/"content/topic_set.json"/]
      TGR[/"content/topic_graph.json"/]
    end

    subgraph L3["caches — rebuilt on demand, safe to delete, cost only time"]
      direction LR
      RIX[/"content/retrieval_index.json"/]
      DCA[/"content/docling_cache.json"/]
      TCA[/"content/topic_embed_cache.json"/]
    end

    subgraph L4["written by you, through a skill"]
      direction LR
      DRF[/"content/drafts/&lt;slug&gt;.md | .tex"/]
      REN[/"content/rendered/&lt;slug&gt;.pdf | .tex | .docx | .md"/]
      RVW[/"content/review/&lt;slug&gt;.{provenance,verbatim,coverage,synthesis,figure,uncited,quotation,agenda,support,union}.md<br/><small>the draft's path under drafts/, mirrored · renders land beside them</small>"/]
    end

    LCK[/"content/pipeline.lock.db<br/><small>held by whichever writer is running</small>"/]
  end

  CFG -. "read once at import,<br/>env vars override" .-> GEN

  BIB -- "chitragupta/bib_reader.py" --> LED
  PDF -- "chitragupta/pdf_text/" --> TXT
  PDF -- "chitragupta/pdf_text/<br/><small>docling backend only</small>" --> CPS
  LED -- "which PDFs need a parse" --> TXT
  LED -- "chitragupta/enrich/corpus.py<br/><small>every row, keyed by <code>citekey</code></small>" --> DOC
  TXT -- "chitragupta/enrich/embed_index.py" --> CHR
  PDF -- "chitragupta/enrich/docling_parse.py" --> DOC
  CPS -. "<b>chitragupta/enrich/_docling_reuse.py</b><br/><small>adopts the corpus layer's parse<br/>instead of repeating it</small>" .-> DOC
  DOC --> CHR
  TXT -- "chitragupta/enrich/topic_model.py<br/><small>whole-doc embeddings — its own cache,<br/>not the Chroma collection</small>" --> TOP
  TXT -- "chitragupta/enrich/topic_seeding.py<br/><small>the author's own topic phrases,<br/>matched against the same embeddings</small>" --> SED
  TOP -- "chitragupta/enrich/topic_converge.py<br/><small>emergent clusters and named phrases, joined</small>" --> CVG
  SED --> CVG
  CVG -- "chitragupta/enrich/topic_graph.py<br/><small>how the topics relate — shared-member<br/>and semantic edges, both explainable by papers</small>" --> TGR

  TXT -- "chitragupta/retrieval_cache.py" --> RIX

  RIX -- "<b>chitragupta/retrieval.py</b> · BM25 hits<br/><small>the default path</small>" --> DRF
  CHR -. "<b>chitragupta/enrich/embed_index.py</b> · semantic hits<br/><small><b>either this or BM25 — never both.</b> Only<br/>survey-writer and deep-research name it.</small>" .-> DRF
  DOC -- "chitragupta/passages.py<br/>quotable passages — rung 1" --> DRF
  CPS -- "chitragupta/passages.py<br/>quotable passages — rung 2" --> DRF
  LED -- "chitragupta/references.py<br/>bib_fields → IEEE entries" --> DRF
  DRF == "<b>chitragupta draft gate</b> — FAIL rewrites the draft in place,<br/>and the skill re-runs it until it exits 0" ==> DRF
  DRF -- "chitragupta draft render<br/><small>only after the gate passes</small>" --> REN
  DRF -- "the review layer<br/><small>chitragupta review provenance · verbatim scan --write<br/>coverage · synthesis · figure · uncited · quotation --write<br/>agenda · support --write · union (a book, not a draft)</small>" --> RVW

  classDef mine fill:#fff7ed,stroke:#c2410c,color:#431407
  classDef corpus fill:#eef2ff,stroke:#4f46e5,color:#1e1b4b
  classDef heavy fill:#faf5ff,stroke:#9333ea,color:#3b0764
  classDef cache fill:#f8fafc,stroke:#94a3b8,stroke-dasharray:4 3,color:#0f172a
  classDef draft fill:#f0fdf4,stroke:#16a34a,color:#052e16
  classDef lock fill:#fefce8,stroke:#a16207,color:#422006

  class BIB,PDF,CFG mine
  class LED,TXT,CPS corpus
  class DOC,CHR,TOP,SED,CVG,TGR heavy
  class RIX,DCA,TCA cache
  class DRF,REN,RVW draft
  class LCK lock
```

### ✅ 5. Gates and exit codes

**Written for:** Someone whose run just failed, or who is scripting it.
**Answers:** why did this exit 1, and what is safe to retry automatically?

Exit codes are the API for unattended callers: `0` corpus in sync, `1`
corpus not in sync and a human is needed, `2` cycle skipped and no work
was lost.

The distinction worth reading twice is in the failure branch. A document
the backend genuinely cannot read is **never retried** -- re-reading it
every run would spend the same minutes to reach the same answer -- but it
**never goes quiet either**, failing the run until someone deals with it.
A failure caused by the *run* rather than the *document* -- a dead worker,
a timeout, a CUDA OOM -- retries itself next time without being asked.

The gate's `exit 1` is the one failure on this diagram that usually
reaches nobody, because the skill loops on it itself.

```mermaid
flowchart TB

  START(["<code>chitragupta corpus sync</code>"]) --> Q2

  Q2{"<b>config.toml present?</b><br/><small>read once at import,<br/>before anything else happens</small>"}
  Q2 -- no --> EC["<b>refuses to import</b><br/><small>cp config.toml.example config.toml</small>"]
  Q2 -- yes --> Q1

  Q1{"<b>run lock free?</b><br/><small>content/pipeline.lock.db</small>"}
  Q1 -- "no · another writer holds it" --> E2["<b>exit 2</b><br/>cycle skipped, no work lost<br/><small>readers were never blocked</small>"]
  Q1 -- yes --> Q3

  Q3{"<b>bibliography.bib readable?</b>"}
  Q3 -- no --> EF["<b>FileNotFoundError</b><br/><small>export from Zotero first</small>"]
  Q3 -- yes --> LOOP

  LOOP["<b>for each citekey in the bib</b><br/><small>upsert the ledger row</small>"] --> Q4

  Q4{"<b>has a resolvable PDF?</b>"}
  Q4 -- no --> SN["status <code>no_pdf</code><br/><small>reported with a reason;<br/>the run still succeeds</small>"]
  Q4 -- yes --> Q5

  Q5{"<b>bytes changed since<br/>the last parse?</b><br/><small>size+mtime, then sha256</small>"}
  Q5 -- no --> SK["<b>skipped</b><br/><small>this is why a re-run costs<br/>close to nothing</small>"]
  Q5 -- yes --> PARSE["<b>parse the PDF</b><br/><small>pdftotext or docling ·<br/>serial, or a clamped worker pool</small>"]

  PARSE --> Q6
  Q6{"<b>parse result</b>"}
  Q6 -- "complete" --> OK["status <code>parsed</code><br/><small>content/parsed/&lt;citekey&gt;.txt written</small>"]
  Q6 -- "partial success" --> PF
  Q6 -- "backend can't read it" --> PF["status <code>parse_failed</code> · <i>deterministic</i><br/><small>never retried — same minutes, same answer —<br/>but fails every run until fixed</small>"]
  Q6 -- "worker died · timeout · CUDA OOM" --> PT2["status <code>parse_failed</code> · <i>transient</i><br/><small>retried automatically next run</small>"]

  OK --> AGG
  SN --> AGG
  SK --> AGG
  PF --> AGG
  PT2 --> AGG

  AGG{"<b>anything unresolved?</b>"} -- no --> E0["<b>exit 0</b><br/>corpus in sync"]
  AGG -- yes --> E1["<b>exit 1</b><br/>corpus not in sync,<br/>human attention needed"]

  E0 --> GATEIN(["a skill drafts against this corpus"])
  GATEIN --> G{"<b>chitragupta draft gate</b><br/>every citekey resolvable?"}
  G -- "yes · <b>exit 0</b>" --> GOOD["references → render<br/><small>the only path to a rendered draft</small>"]
  G -- "no · <b>exit 1</b>" --> GBAD["<b>the write is blocked.</b><br/><small>Treated like a failing test,<br/>not a lint warning.</small>"]
  GBAD --> GLOOP["<b>the skill re-drafts and re-runs the gate</b><br/><small>“Fix and re-run until <code>OK</code>. Never present a draft<br/>that hasn't passed.” — all five SKILL.md files.<br/>This exit 1 is the only one nobody has to see:<br/>the loop is inside the skill, not in front of you.</small>"]
  GLOOP == "<b>loop until exit 0</b>" ==> G
  GLOOP -. "unless the paper genuinely isn't in the corpus —<br/>then it stops and tells you to sync" .-> E1

  classDef q fill:#eef2ff,stroke:#4f46e5,color:#1e1b4b
  classDef ok fill:#f0fdf4,stroke:#16a34a,color:#052e16
  classDef warn fill:#fefce8,stroke:#a16207,color:#422006
  classDef bad fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#450a0a
  classDef hard fill:#dc2626,stroke:#7f1d1d,color:#ffffff

  class Q1,Q2,Q3,Q4,Q5,Q6,AGG,LOOP,PARSE,G q
  class E0,OK,SK,GOOD ok
  class GLOOP warn
  class E2,SN,PT2 warn
  class E1,PF,EC,EF bad
  class GBAD hard
```

### 📄 6. Inside one parse

**Written for:** Someone tuning `[parser].workers`, or changing the pool.
**Answers:** what does a worker pool actually do here, and what happens when
part of it dies?

The deepest view, and the only part of the repository that runs work in
parallel. Everything else -- retrieval, gating, rendering -- is
deliberately serial.

The through-line: **the pool is clamped to the host, not to the
request.** The ceiling counts the CPUs *this process* may run on
(`os.sched_getaffinity`), not the machine's. An over-large request is
clamped *and said out loud*: silently obeying thrashes, and silently
ignoring leaves someone believing they configured something they did
not.

Five failure modes hang off the pool, each handled where it can be, and
the parent process keeps everything only it can do: sqlite has a single
writer, and the parent is the only place that can order results
deterministically. Full component-by-component write-up in
[docs/PARALLELISM.md](PARALLELISM.md); the reasoning behind the lock is in
[docs/DESIGN.md](DESIGN.md).

```mermaid
flowchart TB

  subgraph PRE["<b>before the pool exists</b>"]
    direction TB
    P1["<b>prestart_pool()</b><br/><small>forkserver begins importing torch + docling<br/>in the background — and declines outright when<br/>no pool is coming (pdftotext, or workers = 1)</small>"]
    P2["<b>read bibliography.bib</b> — ~2.5s<br/><small>deliberately started <i>after</i> the pre-start, so the<br/>import overlaps the read: a fixed ~1.5-2s saved</small>"]
    P3["<b>ask the ledger</b><br/><small>which documents actually need a parse</small>"]
    P1 -.-> P2 --> P3
  end

  W{{"<b>resolve_workers(n_docs)</b><br/><code>max(1, min(requested, ceiling, n_docs))</code>"}}

  subgraph CEIL["<b>the ceiling is the host's, not the request's</b>"]
    direction TB
    C1["<b>allowed_cpus()</b> = <code>len(os.sched_getaffinity(0))</code><br/><small>the CPUs <i>this process</i> may run on — not <code>os.cpu_count()</code>.<br/>On the dev machine those are 48 and 96.</small>"]
    C2["<b>÷ 4 for docling</b><br/><small>one worker was measured holding ~300% CPU.<br/>A later full-corpus sweep found the divisor<br/>too conservative by ~1.41x — not yet changed.</small>"]
    C3["<b>clamped <i>and</i> reported</b><br/><small>silently obeying thrashes; silently ignoring leaves<br/>someone believing they configured something they didn't</small>"]
    C1 --> C2 --> C3
  end

  SER["<b>workers = 1 — the default</b><br/><small>a genuinely different code path: no executor,<br/>no pickling, no subprocess. Incremental skipping<br/>means a routine run has almost nothing to do,<br/>so pool setup would cost more than it saves.</small>"]

  subgraph POOL["<b>the pool</b> — each backend gets the concurrency it can use"]
    direction TB
    EXE{{"backend?"}}
    TP["<b>ThreadPoolExecutor</b> · <code>pdftotext</code><br/><small>external subprocess — releases the GIL.<br/>Processes would add pickling and spawn cost<br/>to buy the same OS-level concurrency.</small>"]
    PP["<b>ProcessPoolExecutor</b> · <code>docling</code><br/><small>runs in-process and holds the GIL.<br/><b>forkserver</b> or <b>spawn</b>, never plain fork —<br/>a forked child inherits a broken CUDA context.</small>"]
    LPT["<b>submit biggest-file-first</b><br/><small>one 675-page document is 5% of the corpus's pages.<br/>Picked up last it would define the wall clock by itself.<br/>File size, not page count — counting pages needs a<br/>PDF library the corpus layer refuses to depend on.</small>"]
    DEV["<b>init_worker</b> — one CUDA card each<br/><small>a shared counter under a lock, round-robin over<br/><code>usable_devices()</code> (≥ 2.5 GiB free). Without this,<br/>docling's <code>AcceleratorDevice.AUTO</code> resolves to<br/><code>cuda:0</code> in <i>every</i> process.</small>"]
    EXE -- pdftotext --> TP
    EXE -- docling --> PP
    TP --> LPT
    PP --> LPT --> DEV
  end

  RET["<b>workers return</b> <code>(citekey, out_path, exception)</code><br/><small>the exception is <i>returned</i>, not raised, so both the value<br/>and its type survive pickling — <code>sync</code> reports<br/><code>ExtractionError</code> and <code>BackendUnavailable</code> differently</small>"]

  subgraph FAIL["<b>five failure modes, each handled where it can be</b>"]
    direction TB
    F1["<b>a dead worker</b> → <code>BrokenProcessPool</code><br/><small>results collected with <code>as_completed</code>, not <code>map</code>,<br/>so documents that already finished are kept</small>"]
    F2["<b>a hung pool</b> → stall watchdog<br/><small>fires when <i>no</i> document completes for <code>stall_timeout</code>;<br/>warns at half. Not a per-document deadline — no threshold<br/>separates a hang from the legitimate 246s document.</small>"]
    F3["<b>a slow document</b> → <code>document_timeout</code><br/><small>a real kill for pdftotext; a cooperative between-stages<br/>check for docling. Not equally strong, and said so.</small>"]
    F4["<b>CUDA OOM</b> → demote that worker to CPU<br/><small>for the rest of the run, and retry immediately.<br/>Surviving the CPU retry marks it <i>transient</i>.</small>"]
    F5["<b>Ctrl+C</b> → explicit SIGINT handler<br/><small><code>except KeyboardInterrupt</code> around <code>as_completed()</code><br/>never fires. Terminate, grace, <code>kill()</code>, <code>os._exit</code> —<br/>safe only because the ledger commits incrementally.</small>"]
  end

  PARENT["<b>the parent keeps what only the parent can do</b><br/>every ledger and cache write · results replayed <b>in bib order</b><br/><small>sqlite has a single writer, and the parent is the only place<br/>that can order results deterministically</small>"]

  PARTIAL["<b>partial success is a failure</b><br/><small><code>convert(raises_on_error=True)</code> raises only on FAILURE.<br/>A PARTIAL_SUCCESS would hand the citation gate a source that<br/>silently ends at page k of n — so both call sites check the<br/>status and raise <i>before</i> anything is written.</small>"]

  LOCK["<b>and around all of it: one writer at a time</b><br/><code>content/pipeline.lock.db</code> · a dedicated sqlite file under <code>BEGIN IMMEDIATE</code><br/><small>a RESERVED lock does not block readers, so the gate, retrieval and the<br/>drafting skills keep working during a run. A second writer gets SQLITE_BUSY<br/>and exits 2. A killed holder releases it immediately — no staleness heuristic.</small>"]

  P3 --> W
  CEIL -.-> W
  W -- "= 1" --> SER
  W -- "&gt; 1" --> EXE
  DEV --> RET
  SER --> RET
  RET --> PARTIAL --> PARENT
  FAIL -.-> RET
  LOCK -.-> PRE

  classDef pre fill:#eef2ff,stroke:#4f46e5,stroke-width:1.5px,color:#1e1b4b
  classDef dec fill:#fefce8,stroke:#a16207,stroke-width:1.5px,color:#422006
  classDef pool fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764
  classDef fail fill:#fef2f2,stroke:#dc2626,stroke-width:1.5px,color:#450a0a
  classDef parent fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#052e16
  classDef lock fill:#fff7ed,stroke:#c2410c,stroke-width:1.5px,color:#431407

  class P1,P2,P3,C1,C2,C3,SER pre
  class W,EXE dec
  class TP,PP,LPT,DEV pool
  class F1,F2,F3,F4,F5,PARTIAL fail
  class RET,PARENT parent
  class LOCK lock
```

---

## 🎭 By genre

The ladder above draws the pipeline as one thing. It isn't, quite -- the
five genre skills in `.claude/skills/` use very different amounts of it.
The enrichment layer in particular is worth building for two of them,
largely wasted on two others, and reduced to a preview step for the fifth.

| Genre | Skills | Retrieval | Enrichment stages | `chitragupta.draft references` |
| --- | --- | --- | --- | --- |
| [Genre A: corpus-led](#-genre-a-corpus-led) | `survey-writer`, `deep-research` | BM25 **or** `embed_index` | `docling` + `embed`, both worth it | yes |
| [Genre B: teaching](#-genre-b-teaching) | `tutorial-writer`, `textbook-chapter-writer` | BM25 only | none | yes (custom heading) |
| [Genre C: LaTeX-native](#-genre-c-latex-native) | `thesis-chapter-writer` | BM25 only | none | **no -- skipped** |

All five run the same gate, in the same loop, with the same wording.

### 📚 Genre A: corpus-led

**Skills:** `survey-writer`, `deep-research`

**The corpus is the content.** Nearly every sentence is a cited claim, so
these are the two skills that pay off the enrichment layer. `docling`
gives passages good enough to survive review; `embed` gives semantic
recall, finding the paper that makes your point in words you did not
search for. They are also the only two skills whose SKILL.md names
`chitragupta.enrich.embed_index.search()` as an alternative to BM25.

Both read the same corpus the rest of the pipeline does, and that corpus
is the bibliography and nothing else -- so every document either skill can
reach carries a citekey the gate will accept, and there is no class of
source that has to be discussed by title because it may not be cited.

`bertopic` sits off to one side because **no skill calls it.** It is for
you, deciding what the survey should be about before anything is drafted.

Same reason, other direction: `chitragupta.review`'s `coverage` aid ("retrieval
surfaced
this paper -- did the draft actually cite it?") is only a meaningful
question in this genre.

```mermaid
flowchart LR

  P0["<b>1 · CURATE</b><br/><i>you, in Zotero</i><br/><br/>Breadth is the whole job here.<br/>A thin corpus shows up<br/>immediately as a thin survey.<br/><br/><b>papers/bibliography.bib</b><br/><small>the only source either skill can reach —<br/>everything retrieval returns is citable</small>"]

  P1["<b>2 · SYNC</b><br/><i>deterministic</i><br/><br/><code>chitragupta corpus sync</code><br/><br/><b>content/ledger.sqlite</b><br/><b>content/parsed/*.txt</b>"]

  HEAVY["<b>ENRICHMENT — worth it for this genre</b><br/><code>chitragupta enrich --stages docling,embed</code><br/><br/><b>docling</b> → layout-aware .md + .passages.json<br/><small>better quotable passages, so claims survive review</small><br/><br/><b>embed</b> → content/chroma/<br/><small>semantic recall: finds the paper that argues the<br/>point in different words. <b>Both skills name<br/><code>embed_index.search()</code> by hand.</b></small>"]

  P2["<b>3 · DRAFT</b><br/><i>every sentence is a cited claim</i><br/><br/><b>survey-writer</b> — over-fetch <code>k=15</code>,<br/>hand-cluster into 2-4 sub-themes,<br/>comparison table + gap analysis<br/><br/><b>deep-research</b> — perspectives,<br/>parallel interviews, contradiction map,<br/>then cited sections<br/><br/><b>content/drafts/&lt;slug&gt;.md</b>"]

  P3{{"<b>4 · VERIFY</b><br/><code>chitragupta draft gate</code><br/><br/>Highest citation density<br/>in the repo, so this<br/>is the genre where<br/>the gate earns its keep"}}

  FIX["<b>DISCARD DRAFT</b><br/><small>swap the key for one retrieval<br/>actually returned, or drop the claim.<br/>Never invent one.</small>"]

  P4["<b>5 · PUBLISH</b><br/><br/><code>chitragupta draft references</code> → IEEE list<br/><code>chitragupta draft render --format tex</code><br/><code>--format pdf</code> · <code>--format md</code><br/><br/><b>content/rendered/&lt;slug&gt;.pdf</b>"]

  AID["<b>LAYER 4 · REVIEW — afterwards, never a gate</b><br/><code>chitragupta review provenance</code> · <code>chitragupta review verbatim</code><br/><code>chitragupta review coverage</code> · <code>chitragupta review synthesis</code><br/><code>chitragupta review figure</code> · <code>chitragupta review uncited</code><br/><code>chitragupta review quotation</code> · <code>chitragupta review agenda</code><br/><code>chitragupta review support</code> · <code>chitragupta review union</code><br/><small>“retrieval surfaced it — did the draft cite it?”<br/>only meaningful when the corpus <i>is</i> the argument</small>"]

  BERT["<b>bertopic</b> → content/topics.json<br/><small>no skill calls this. It is for <i>you</i>, deciding what<br/>the survey should even be about.</small>"]

  P0 ==> P1 ==> P2 ==> P3
  P1 ==> HEAVY ==> P2
  P3 == "PASS · exit 0" ==> P4
  P3 -- "FAIL · exit 1" --> FIX
  FIX == "re-draft · <b>loop until it passes</b>" ==> P2
  P4 -.-> AID
  P1 -.-> BERT -.-> P0

  classDef you fill:#fff7ed,stroke:#c2410c,stroke-width:1.5px,color:#431407
  classDef det fill:#eef2ff,stroke:#4f46e5,stroke-width:1.5px,color:#1e1b4b
  classDef gen fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px,color:#052e16
  classDef gate fill:#fef2f2,stroke:#dc2626,stroke-width:3px,color:#450a0a
  classDef out fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764
  classDef bad fill:#fee2e2,stroke:#dc2626,stroke-width:1.5px,color:#450a0a
  classDef heavy fill:#faf5ff,stroke:#9333ea,stroke-width:2.5px,color:#3b0764
  classDef aid fill:#f8fafc,stroke:#94a3b8,stroke-dasharray:4 3,color:#0f172a

  class P0 you
  class P1 det
  class P2 gen
  class P3 gate
  class P4 out
  class FIX bad
  class HEAVY heavy
  class AID,BERT aid
```

### 🎓 Genre B: teaching

**Skills:** `tutorial-writer`, `textbook-chapter-writer`

**The corpus is a garnish.** Most of the content is original -- worked
examples, exercises, a lesson that has to actually run. Citations are
deliberately confined: `tutorial-writer` bans them mid-lesson and allows
them only in a closing "Where to go next", and `textbook-chapter-writer`
uses them for motivation and background.

So the enrichment layer is mostly wasted here. Neither SKILL.md mentions
`embed_index`; both use `chitragupta.retrieval.search()`, which is stdlib BM25.
Building a semantic index to place four citations is effort in the wrong
place. The rendering they do want at the end is not an enrichment stage
at all -- `render_output` is the drafting layer's own publish step, and
needs no package from the `enrich` group.

This is also the one genre where **the gate can legitimately pass with
zero citations**, and both SKILL.md files say so. An empty reference list
is a correct outcome for a tutorial.

Which points at the real risk: the failure mode in this genre is not a bad
citekey, it is writing the wrong genre -- a tutorial that explains instead
of instructing. Both skills open by warning about exactly that, and no
gate in this repository can catch it.

```mermaid
flowchart LR

  P0["<b>1 · CURATE</b><br/><i>you, in Zotero</i><br/><br/>A handful of grounding papers is<br/>enough. Breadth buys you<br/>very little in this genre.<br/><br/><b>papers/bibliography.bib</b>"]

  P1["<b>2 · SYNC</b><br/><i>deterministic</i><br/><br/><code>chitragupta corpus sync</code><br/><br/><b>content/ledger.sqlite</b><br/><b>content/parsed/*.txt</b>"]

  HEAVY["<b>ENRICHMENT — not worth it here</b><br/><br/><s>docling</s> · <s>embed</s> · <s>bertopic</s> · <s>seed-topics</s> · <s>converge</s> · <s>topic-graph</s><br/><small>Neither SKILL.md mentions <code>embed_index</code>.<br/>Both use <code>chitragupta.retrieval.search()</code> — <b>BM25, stdlib</b> —<br/>and building a semantic index to place four<br/>citations is effort spent in the wrong place.</small><br/><br/><b>render</b> is the drafting layer's own publish step<br/><small><code>chitragupta draft render</code> — it was never<br/>enrichment work, and is deliberately not a stage</small>"]

  P2["<b>3 · DRAFT</b><br/><i>mostly original content</i><br/><br/><b>tutorial-writer</b> — one path, keyboard-first,<br/>verified to actually run. Citations are<br/><b>banned mid-lesson</b>; they live only in<br/>a closing “Where to go next”.<br/><br/><b>textbook-chapter-writer</b> — objectives,<br/>worked examples, exercises. Cites for<br/><b>motivation and background only</b>.<br/><br/><b>content/drafts/&lt;slug&gt;.md</b>"]

  P3{{"<b>4 · VERIFY</b><br/><code>chitragupta draft gate</code><br/><br/><small><b>May legitimately pass with<br/>zero citations.</b> Both SKILL.md<br/>files say so explicitly — this is<br/>the one genre where an empty<br/>reference list is correct.</small>"}}

  FIX["<b>DISCARD DRAFT</b><br/><small>drop the claim; the lesson<br/>rarely needed it in the first place</small>"]

  P4["<b>5 · PUBLISH</b><br/><br/><code>chitragupta draft references</code><br/><small><b>tutorial-writer</b> passes<br/><code>--heading &quot;Further reading&quot;</code>,<br/>which then survives into the render<br/>instead of being stripped</small><br/><br/><code>chitragupta draft render --format pdf</code>"]

  RISK["<b>the real failure mode here isn't a bad citekey</b><br/><small>It is writing the wrong genre: a tutorial that explains<br/>instead of instructing, or a chapter that instructs instead<br/>of explaining. Both SKILL.md files open by warning about<br/>exactly that — and no gate in this repository can catch it.<br/><b>You are the check.</b></small>"]

  P0 ==> P1 ==> P2 ==> P3
  P1 -. "publish step only" .-> HEAVY
  HEAVY -.-> P4
  P3 == "PASS · exit 0<br/>(often trivially)" ==> P4
  P3 -- "FAIL · exit 1" --> FIX
  FIX == "re-draft · <b>loop until it passes</b>" ==> P2
  P2 -.-> RISK

  classDef you fill:#fff7ed,stroke:#c2410c,stroke-width:1.5px,color:#431407
  classDef det fill:#eef2ff,stroke:#4f46e5,stroke-width:1.5px,color:#1e1b4b
  classDef gen fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px,color:#052e16
  classDef gate fill:#fef2f2,stroke:#dc2626,stroke-width:3px,color:#450a0a
  classDef out fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764
  classDef bad fill:#fee2e2,stroke:#dc2626,stroke-width:1.5px,color:#450a0a
  classDef off fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:5 4,color:#334155
  classDef risk fill:#fefce8,stroke:#a16207,stroke-width:2px,color:#422006

  class P0 you
  class P1 det
  class P2 gen
  class P3 gate
  class P4 out
  class FIX bad
  class HEAVY off
  class RISK risk
```

### ✍ Genre C: LaTeX-native

**Skills:** `thesis-chapter-writer`

**The output isn't the deliverable.** This skill emits a standalone `.tex`
fragment with `\citep`/`\citet` and no preamble, meant to be `\input` by
your own thesis document -- so rendering produces a *preview*, not the
artifact that matters. A rendering failure
never blocks presenting the draft.

It is also the only skill that **deliberately skips `chitragupta.draft references`**.
Your thesis owns its own bibliography; a second reference list inside the
fragment would collide with it. That exception is easy to miss when
reading the README's `gate -> references -> render` chain, which is why
it gets its own diagram.

The gate is not relaxed for LaTeX: `chitragupta.draft gate` reads
`\citep`/`\citet` as readily as Markdown `[@key]`, and the loop-until-`OK`
rule is worded identically to the other four skills.

```mermaid
flowchart LR

  P0["<b>1 · CURATE</b><br/><i>you, in Zotero</i><br/><br/>Depth over breadth: everything<br/>bearing on one research question.<br/><br/><b>papers/bibliography.bib</b><br/><small>this same .bib is very likely already<br/>your thesis's <code>\\bibliography</code> — which is<br/>why the two stay consistent for free</small>"]

  P1["<b>2 · SYNC</b><br/><i>deterministic</i><br/><br/><code>chitragupta corpus sync</code><br/><br/><b>content/ledger.sqlite</b><br/><b>content/parsed/*.txt</b>"]

  HEAVY["<b>ENRICHMENT — not worth it here</b><br/><br/><s>docling</s> · <s>embed</s> · <s>bertopic</s> · <s>seed-topics</s> · <s>converge</s> · <s>topic-graph</s><br/><small>SKILL.md names <code>chitragupta/retrieval.py</code> alone —<br/><b>BM25, <code>k=15</code>, then filter by hand</b></small><br/><br/><b>render</b> is <i>not</i> an enrichment stage<br/><small>it is the drafting layer's own publish step, and here<br/>even that is disposable: <code>--format md</code>/<code>--format pdf</code><br/>to <i>look</i> at the chapter. The artifact that matters<br/>is the .tex you <code>\\input</code>. “A rendering failure<br/>never blocks presenting the draft.”</small>"]

  P2["<b>3 · DRAFT</b><br/><i>RQ-driven narrative</i><br/><br/>A standalone <b>.tex fragment</b> —<br/><code>\\citep</code> / <code>\\citet</code>, <b>no preamble</b>,<br/>meant to be <code>\\input</code> by your own<br/>thesis document.<br/><br/><b>content/drafts/&lt;slug&gt;.tex</b>"]

  P3{{"<b>4 · VERIFY</b><br/><code>chitragupta draft gate</code><br/><br/><small>Reads <code>\\citep</code>/<code>\\citet</code> as<br/>readily as Markdown <code>[@key]</code>,<br/>so the .tex path is gated<br/>exactly as hard</small>"}}

  FIX["<b>DISCARD DRAFT</b><br/><small>“Fix and re-run until <code>OK</code>.<br/>Never present a draft<br/>that hasn't passed.”</small>"]

  P4["<b>5 · PUBLISH</b> — <i>the odd one out</i><br/><br/><b>❌ <s>chitragupta draft references</s> — deliberately skipped</b><br/><small>the only genre that skips it. Your thesis's own<br/>bibliography owns the reference list; a second<br/>one inside the fragment would collide with it.</small><br/><br/><code>chitragupta draft render --format md | pdf</code><br/><small>a preview for you, not the deliverable</small>"]

  OUT["<b>the actual output</b><br/><code>\\input{chapter-4}</code><br/><small>into your own thesis, compiled by your own<br/>LaTeX toolchain against your own .bib</small>"]

  P0 ==> P1 ==> P2 ==> P3
  P1 -. "publish step only" .-> HEAVY
  HEAVY -.-> P4
  P3 == "PASS · exit 0" ==> P4
  P3 -- "FAIL · exit 1" --> FIX
  FIX == "re-draft · <b>loop until it passes</b>" ==> P2
  P4 ==> OUT

  classDef you fill:#fff7ed,stroke:#c2410c,stroke-width:1.5px,color:#431407
  classDef det fill:#eef2ff,stroke:#4f46e5,stroke-width:1.5px,color:#1e1b4b
  classDef gen fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px,color:#052e16
  classDef gate fill:#fef2f2,stroke:#dc2626,stroke-width:3px,color:#450a0a
  classDef out fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764
  classDef bad fill:#fee2e2,stroke:#dc2626,stroke-width:1.5px,color:#450a0a
  classDef off fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:5 4,color:#334155
  classDef final fill:#ecfdf5,stroke:#16a34a,stroke-width:2.5px,color:#052e16

  class P0 you
  class P1 det
  class P2 gen
  class P3 gate
  class P4 out
  class FIX bad
  class HEAVY off
  class OUT final
```

---

## 📎 Appendix

These two answer narrower questions than the groups above, and are kept
separate for that reason.

### ⏱ One draft, in time order

The full workflow with time on the vertical axis instead of dependency.
Useful for two things in particular. The first is seeing that **the gate
runs twice**: the PostToolUse hook fires on every write under
`content/drafts/`, so a bad citekey cannot reach disk even if a skill
forgets, and the skill then runs the gate itself, because the hook fires
only on the tool call that wrote the file. The second is seeing the
**loop** that wraps both of them.

```mermaid
sequenceDiagram
    autonumber
    actor You as You
    participant Z as Zotero
    participant Sync as chitragupta corpus sync<br/>(corpus layer)
    participant Led as content/<br/>ledger.sqlite
    participant Ret as chitragupta.retrieval<br/>+ chitragupta.passages
    participant Skill as genre skill<br/>(.claude/skills/)
    participant Hook as PostToolUse hook
    participant Gate as chitragupta draft gate
    participant Ref as chitragupta draft references
    participant Ren as chitragupta draft render<br/>(pandoc / TeX Live)

    rect rgba(255,247,237,0.6)
    Note over You,Z: CURATE — the only step that adds a paper
    You->>Z: add papers, then Export BibTeX + files
    Z-->>You: papers/bibliography.bib + attachment tree
    end

    rect rgba(238,242,255,0.6)
    Note over Sync,Led: SYNC — deterministic, incremental, holds the run lock
    You->>Sync: chitragupta corpus sync
    Sync->>Sync: take content/pipeline.lock.db
    Sync->>Led: upsert one row per citekey
    Led-->>Sync: which PDFs actually changed
    Sync->>Sync: extract text → content/parsed/*.txt
    Sync->>Led: mark parsed / parse_failed / no_pdf
    Sync-->>You: summary + stale list + exit 0 | 1 | 2
    end

    rect rgba(240,253,244,0.6)
    Note over You,Skill: DRAFT — the generative half
    You->>Skill: "write a survey section on digital twin composability"
    Skill->>Led: is the ledger populated?
    Led-->>Skill: N citekeys parsed
    Skill->>Ret: search(query, k)
    Ret-->>Skill: ranked snippets, each tied to a real citekey
    Skill->>Skill: write content/drafts/<slug>.md
    end

    rect rgba(254,242,242,0.7)
    Note over Hook,Gate: VERIFY — enforced mechanically, twice
    Hook->>Gate: every Write/Edit under content/drafts/
    Gate->>Led: are these citekeys in the ledger?
    loop until the gate exits 0 — you are shown nothing before that
        alt any citekey unresolved
            Led-->>Gate: no
            Gate-->>Hook: FAIL (exit 1)
            Hook-->>Skill: the write is blocked
            Skill->>Skill: swap the key for one retrieval returned,<br/>or drop the claim — never invent one
        else all resolvable
            Led-->>Gate: yes
            Gate-->>Skill: PASS (exit 0)
        end
    end
    Skill->>Gate: runs the gate again itself, before showing you anything
    Note right of Skill: If the paper genuinely isn't in the corpus,<br/>the loop stops and the skill tells you to<br/>add it in Zotero and re-run sync.
    end

    rect rgba(250,245,255,0.6)
    Note over Ref,Ren: PUBLISH
    Skill->>Ref: python -m chitragupta.draft references <draft>
    Ref->>Led: bib_fields for exactly the cited citekeys
    Ref-->>Skill: a ## References section, numbered by first appearance
    Skill->>Ren: chitragupta.draft render --format pdf
    Ren-->>You: content/rendered/<slug>.pdf
    end

    Note over You,Ren: Layer 4, the review layer — afterwards, never a gate:<br/>chitragupta review provenance · verbatim · coverage · synthesis<br/>figure · uncited · quotation · agenda · support · union<br/>the skill runs verbatim scan itself, the rest are yours to run<br/>reports land in content/review/, mirroring the draft
```

### 📖 The life of a single citekey

The ledger's own state machine, for when the question is "why can't I
cite this paper?". `parsed` is the only state that makes a citekey
citable, and the self-loop on it is the incremental path that makes a
routine re-run nearly free.

Note that `stale` deletes nothing. A bib export that comes back short a
citekey is far more often a botched re-export or a `BIB_FILE` pointing at
the wrong path than an intentional deletion, so the row survives until you
re-run with `--remove-stale`.

```mermaid
stateDiagram-v2
    direction TB

    [*] --> discovered : appears in bibliography.bib<br/>(chitragupta.bib_reader)

    discovered --> no_pdf : no resolvable<br/>file field
    discovered --> parsing : PDF found and<br/>its bytes changed

    no_pdf --> parsing : you attach the PDF in<br/>Zotero and re-export

    parsing --> parsed : text extracted in full
    parsing --> failed_deterministic : backend cannot read this<br/>PDF, or parsed it only partly
    parsing --> failed_transient : worker died, timeout,<br/>CUDA OOM, broken pool

    failed_transient --> parsing : retried automatically<br/>on the next sync
    failed_deterministic --> parsing : only on<br/>sync --reparse

    parsed --> parsing : PDF bytes changed<br/>(size+mtime, then sha256)
    parsed --> parsed : bytes unchanged, skipped —<br/>the incremental path

    parsed --> stale : dropped out of<br/>bibliography.bib
    no_pdf --> stale : dropped out of<br/>bibliography.bib
    stale --> parsed : it was a botched re-export —<br/>fix the export and re-sync
    stale --> [*] : sync --remove-stale<br/>opt-in, after you read the list

    note right of parsed
        Only this state makes the citekey citable.
        chitragupta draft gate resolves a citekey against
        the ledger, so a row that is not here
        cannot appear in a draft that renders.
    end note

    note left of failed_deterministic
        Never silent, never pointlessly expensive.
        Not re-parsed — the same minutes would
        reach the same answer — but every run
        exits 1 until a human deals with it.
    end note
```

---

## ✏ Editing these

Each diagram is plain Mermaid in a fenced block above. GitHub renders
them, and so does any Mermaid-aware editor. **That block is the source of
truth.**

The same eleven are also checked in as standalone files, so you can drop
one into a slide deck or a paper without copying it out of this document:

| Path | What it is |
| --- | --- |
| `docs/diagrams/<name>.mmd` | the Mermaid source, with a title line |
| `docs/diagrams/svg/<name>.svg` | the rendered export, ~1900px wide on a white background |

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

Those are exports, not a second source. Edit the fenced block first, then
re-render, or the two drift apart:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i docs/diagrams/v1-overview.mmd -o docs/diagrams/svg/v1-overview.svg -b white -w 1900
```

Keep them honest the way the rest of this repository stays honest: if a
diagram and the code disagree, the diagram is the bug.
