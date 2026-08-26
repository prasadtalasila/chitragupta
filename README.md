<!-- The H1 follows the centred logo block rather than opening the file.
     MD033 is already relaxed for that <picture> element; this is the
     same exception for the heading rule it displaces. -->
<!-- markdownlint-disable-next-line MD041 -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)"
            srcset="docs/logo-dark.svg">
    <img src="docs/logo.svg" alt="chitragupta" height="72">
  </picture>
</p>

<p align="center">
<b>Turns a BibTeX bibliography into grounded survey papers, thesis chapters,
undergraduate textbook chapters and hands-on tutorials</b>, with every citation
traceable back to a paper the bibliography actually holds.
</p>

<p align="center">
Named for the Hindu god who keeps the ledger of every deed and audits souls
against it -- which is what this does to citations.
<!-- Absolute on purpose. This is a raw HTML anchor inside a centred block,
     and MkDocs only rewrites Markdown links, so a relative `docs/NAME.md`
     here resolves on GitHub and 404s on the docs site. Making it a Markdown
     link is not the fix: CommonMark treats the inside of an HTML block as
     raw text, so GitHub would stop rendering it. -->
<a href="https://github.com/prasadtalasila/chitragupta/blob/main/docs/NAME.md"
>See more</a>.
</p>

---

## 🔑 The one rule

Fabricated placeholder references have made it into real papers before.
This pipeline is built to make that impossible rather than unlikely:

> **A citekey may only be used if it appears in your own `.bib` export
> *and* was picked up into the ledger by a real parse of a real PDF.**

- [How it works](#-how-it-works)
- [Quickstart](#-quickstart)
- [The enrichment layer](#-the-enrichment-layer)
- [Hardware requirements](#-hardware-requirements)
- [Documentation](#-documentation)
- [Acknowledgements](#-acknowledgements)

## 🏗 How it works

Five phases along the spine, and two layers beside it. You own phase 1;
nothing reaches phase 5 without passing phase 4.

<p align="center">
  <img src="docs/diagrams/svg/v1-overview.svg"
       alt="Five phases: curate in Zotero, sync the corpus, draft with a
            genre skill, verify with the citation gate, publish. Drafting,
            the gate and the dossier are grouped as the part an LLM runs;
            publishing and the advisory review aids are grouped as the
            part the author runs on a finished draft. A failing gate sends
            the draft back to be rewritten."
       width="100%">
</p>

Two properties of the spine do all the work:

- **Phase 1 is the only entrance.** Citekeys come from your reference
  manager's BibTeX export. The pipeline never fetches a paper, never
  invents a citekey, and never renames one.
- **Phase 4 is the only exit.** `chitragupta.draft gate` sits on the single
  path between a draft and a rendered document. There is no arrow around
  it, and a `FAIL` is treated like a failing test rather than a lint
  warning. The loop back goes to *drafting*, not to you.

The two layers beside it are where the pipeline keeps its memory and its
conscience:

- **The dossier** is written as a draft is written -- scope, kept
  evidence, rejected candidates, a revision log -- and read back to
  change it. That is why a draft is never revised by re-running the
  skill that produced it ([docs/DOSSIER.md](docs/DOSSIER.md)).
- **The review layer** is seven advisory aids for a finished draft:
  provenance, verbatim, coverage, synthesis, figure layout, uncited
  prose and claim support. None of them is a gate -- which is not the same as borrowed
  wording being fine to leave once you have found it
  ([docs/REVIEW.md](docs/REVIEW.md)).

Nine skills sit behind phase 3, all obeying the same grounding rules:
five that write a draft (survey, thesis chapter, undergraduate textbook
chapter, tutorial, and a heavier multi-perspective deep-research mode),
three that change one that already exists, and one that assembles
accepted units into a book ([docs/GENRE.md](docs/GENRE.md)).
**Enrichment** is a separate optional pass that deepens the same corpus
with layout-aware parsing, semantic search and topic clustering; nothing
above needs it.

[docs/DIAGRAMS.md](docs/DIAGRAMS.md) draws this workflow eleven ways --
by depth, by genre, and in time order -- and is where the figure above
comes from.

### 🚫 One thing the corpus layer does not promise

The corpus layer is deterministic in the sense that matters most -- no
LLM, no judgement calls, same bibliography in, same citekeys out -- but it
is **not** bit-reproducible with every parser. With the default
`pdftotext` backend it is: parsed text comes back byte-identical, every
ledger column stable except the `last_synced` timestamp.

With the opt-in `docling` backend *and* a worker pool, it isn't -- and the
instability reaches the *quotable passage*, so the exact span quoted from
a source can change between runs. That is Docling's behaviour under load
rather than something this pipeline adds, and it cannot be switched off;
serial parsing (`[parser].workers = 1`, the default) has not been observed
to vary. The artifact-by-artifact contract, the measured rates and how
little they can pin down are in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).

## 🚀 Quickstart

Two ways to get a project directory, and everything from step 2 onward
is identical either way. Pick whichever matches what you're doing:

```bash
# pip install: for using the pipeline. The venv is what avoids Debian/
# Ubuntu's PEP 668 error and keeps Claude Code's hooks able to import
# chitragupta -- docs/CLI.md's Installing says why the name matters.
mkdir my-project && cd my-project
python3 -m venv .venv-full && source .venv-full/bin/activate
pip install chitragupta-cli
chitragupta init                      # config.toml, .claude/, papers/, content/, prose docs
chitragupta install os-deps           # TeX Live, Pandoc, poppler. Debian/Ubuntu, needs root
pip install chitragupta-cli[enrich]   # optional, several GB -- only step 4 uses it
```

```bash
# git checkout: for working on the pipeline itself -- see DEVELOPER-AGENTS.md.
# Same .venv-full; the script creates it if absent, reuses it if not.
git clone https://github.com/prasadtalasila/chitragupta && cd chitragupta
cp config.toml.example config.toml   # git checkout only
pipx install poetry
bash scripts/install_full_pipeline.sh all
source .venv-full/bin/activate
```

```bash
# 1. Export Zotero's library: format BibTeX, tick "Export Files", save it
#    as `bibliography` inside papers/. Each entry's file field is relative
#    to the .bib, so don't rename or move the companion folder afterwards
#    -- see docs/ZOTERO.md.
#      papers/bibliography.bib
#      papers/bibliography/files/<id>/<name>.pdf
mkdir -p papers && cp -r /path/to/your/export/. papers/

# ...only if your field has its own acronyms (DT, FMU, ...) beyond the
#    PDF/CPU/URL/API/HTML every draft already gets. assets/style/README.md.
# cp assets/style/acronyms.toml.example content/acronyms.toml
# # then point [style].acronyms in config.toml at it

# 2. Sync the corpus layer from papers/bibliography.bib. A citekey that
#    later drops out of the bib file is only *reported*; --remove-stale
#    deletes the row once you've read that list. docs/ZOTERO.md has why
#    the default is report rather than delete.
chitragupta corpus sync            # or: python -m chitragupta.corpus sync
# chitragupta corpus sync --remove-stale

# 3. Inspect what it found. Read-only, takes no lock.
chitragupta corpus ledger

# 4. Optional: the enrichment layer -- layout-aware parsing, semantic
#    search, topic clustering. No skill builds it for you, so skip it on a
#    first run. Needs the enrich extra above; chitragupta doctor says
#    whether you have it. "The enrichment layer" below, then
#    docs/RETRIEVAL.md, say which stage is worth the cost.

# 5. In Claude Code, ask for a draft, e.g.:
#    "write a survey section on digital twin composability"
#    "draft a thesis chapter on runtime verification for autonomous robots"
#    "write a textbook chapter introducing digital twin asset reuse"
#    "write a tutorial that builds a minimal digital twin asset from scratch"
#    "do deep research on fault injection for digital twin testbeds"
# The matching skill in .claude/skills/ picks this up automatically,
# including its own gate -> references -> render chain (chitragupta draft <verb>)
```

Every command that chain runs, every way to re-run one by hand, and all
six review-layer commands for checking a finished draft against its
sources are in
[docs/CLI.md](docs/CLI.md) -- see [The full first run, step by
step](docs/CLI.md#-the-full-first-run-step-by-step), which walks the whole
sequence above and everything that follows it, in order.

## 🧠 The enrichment layer

Everything above works without it. The enrichment layer is a second,
optional pass over the same corpus that buys three things: layout-aware
parsing that yields quotable passages, semantic search that finds a paper
arguing your point in different words, and topic clustering over the whole
corpus.

```bash
chitragupta enrich --stages docling,embed          # or: python -m chitragupta.enrich --stages docling,embed
```

It costs real time and disk -- a first full-corpus parse is measured in
tens of minutes, and the enrich dependency group is several gigabytes -- so
you build it deliberately. **No genre skill builds it for you.** The
skills read what is already there and fall back to the lightweight default
when it isn't.

Which stage is worth that cost, and what each one actually answers, is in
[docs/RETRIEVAL.md](docs/RETRIEVAL.md). How the stages fit into the rest
of the system, including how to call them from your own script or skill,
is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#-layer-3-the-enrichment-layer).

No stage needs an LLM API key -- this repository intentionally has none.
Every stage probes its own prerequisites and reports `ok`, `skipped` or
`missing-binary` rather than assuming they are present.

## 💻 Hardware requirements

What the pipeline needs, not what it was developed on. The split below is
the one that matters: the **corpus layer** -- `sync`, the citation gate,
keyword retrieval -- is light enough for any laptop, and the optional
**enrichment layer** is what costs real disk and real time.

| Resource | Minimum (corpus layer only) | Recommended (enrichment layer in regular use) |
| --- | --- | --- |
| Disk | ~1GB | **10-20GB+** -- the full venv alone is **6.0GB** (torch pulled in twice over via sentence-transformers/docling, plus docling's own layout/OCR models); TeX Live adds several GB more |
| RAM | ~1-2GB | **8GB minimum, 16GB+ better**. At ~3GB free, Docling on a 17-page PDF pushed the process to 3.6GB RSS and the host swapped 6.3GB -- it finished, just slowly |
| CPU | 1-2 cores | **4+ cores** -- without a GPU, Docling's layout inference and BERTopic's UMAP/HDBSCAN are CPU-bound, and more cores directly cut wall-clock time |
| GPU | none needed | **none required.** If one is present the installer detects it and torch is set up to use it automatically -- worth ~4.7x on the parse |
| Network | once, for `poetry install` | also for first-run model downloads (the embedding model, Docling's layout/OCR models) |

**For a sense of scale at the top end:** this project's own bibliography
-- 501 PDFs, 13,400 pages, 1.54GB -- parses in **about 4 minutes** on a
96-core machine with four A40s, against **1h 56m** serially on that same
host. On ordinary hardware a first full Docling parse is measured in tens
of minutes. A *second* run over an unchanged corpus costs close to
nothing either way, because every stage skips what hasn't changed -- which
is what makes it safe to put `sync` on a schedule.

Every measured figure in this project comes from one of two reference
machines: **the small machine** (4 cores, 9.7GB RAM, no GPU) and **the
multi-GPU machine** (96 cores, 251GB RAM, 4x NVIDIA A40 -- the one in the
paragraph above). **Treat each figure as that machine's, and expect yours
to differ.** [docs/PERFORMANCE.md](docs/PERFORMANCE.md) has their full
specifications, what each setting costs, and the two install-time traps
worth knowing before you start (a CPU-only host pulling several GB of
unused CUDA packages, and a GPU host where `torch.cuda.is_available()`
comes back `False`).

## 📖 Research Citation

When Chitragupta is used in academic work, the following reference may be used:

```bibtex
@software{talasila2026chitragupta,
author = {Prasad Talasila},
title = {Chitragupta: An automated research pipeline for literature review and thesis drafting},
year = {2026},
url = {https://github.com/prasadtalasila/chitragupta},
publisher = {GitHub}
}
```

## 🗂 Documentation

This file is the overview: what the pipeline is, how to get it running,
and what it needs. Everything else lives in one document per question,
split by what you are doing -- using the pipeline, or working on it.
Which of those you are doing can change within a session, and the split
follows the task rather than the person; [CLAUDE.md](CLAUDE.md) is the
one-screen router for exactly that.

### ▶ Using it

#### 🚀 Getting started

| Document | Answers |
| --- | --- |
| [SOUL.md](SOUL.md) | One page: why this exists, the one invariant, and what it refuses to become |
| [CLAUDE.md](CLAUDE.md) | One screen: which of the two agent guides applies to the task you are about to start, and the one rule that binds both |
| [AGENTS.md](AGENTS.md) | The rules an agent *drafting with* this pipeline must follow -- above all, never fabricate a citekey |
| [docs/GENRE.md](docs/GENRE.md) | Which of the nine skills writes what? How to pick a genre, what each one refuses to do, and why changing an existing draft never goes back through the genre skill |
| [docs/ZOTERO.md](docs/ZOTERO.md) | How do I get my library and its PDFs into the shape this expects? Includes the attachment-path trap that silently leaves every entry without a PDF |
| [docs/CLI.md](docs/CLI.md) | What commands are there, what flags does each take, and which interpreter does it need? |
| [docs/CONFIG.md](docs/CONFIG.md) | What settings exist, what values does each accept, and what is the default? Starts with a minimal `config.toml`. Includes `[parser].backend`, which decides how faithfully your PDFs are read |

#### 🔭 Understanding the system

| Document | Answers |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | What actually runs, what does each part write, which parts are optional, and why do some commands need the venv? |
| [docs/RENDERING-FLOW.md](docs/RENDERING-FLOW.md) | How does a draft's citation actually resolve into a rendered bibliography, which of four possible stores does a `.tex` fragment's citation defer to, and what happens to a figure on the way through? |
| [docs/DIAGRAMS.md](docs/DIAGRAMS.md) | The workflow drawn eleven ways -- six by depth, three by genre, two in an appendix. Pick the one that matches what you already know |
| [docs/LADDERS.md](docs/LADDERS.md) | Where does the pipeline choose between two ways of doing one job? Every ladder it walks for you and every tier you pick yourself, and what the bottom rung costs |
| [docs/RETRIEVAL.md](docs/RETRIEVAL.md) | BM25, embeddings, topic models -- which one answers my question, and which is worth building? |
| [docs/REJECTION.md](docs/REJECTION.md) | Why is turning a source *down* the judgment this pipeline is most careful about? The reasoning behind a retrieval change that was built and then withdrawn, and what was kept from it |
| [docs/TOKENS.md](docs/TOKENS.md) | Where do a run's tokens actually go, which of them get billed once and which get billed every turn, and how do I measure that without paying for a full run? |
| [docs/DRAFT-ITERATION.md](docs/DRAFT-ITERATION.md) | What does a draft's dossier hold, and how do I change a draft weeks later without re-running the pipeline that produced it? |
| [docs/PROMPTS.md](docs/PROMPTS.md) | What does the prompt sent to the model actually contain, layer by layer -- for a single-context genre skill and for the multi-agent `deep-research` skill -- and why don't the two look the same? |

#### ⚙ Choosing settings

| Document | Answers |
| --- | --- |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | What does each setting *cost*? Every measured figure in one place, organised by setting |
| [docs/PDF-PARSER.md](docs/PDF-PARSER.md) | Which PDF backend should I use, why were two dropped, and why was each newer candidate not adopted? |

#### 🔍 Reading the output

| Document | Answers |
| --- | --- |
| [docs/CITATION-PROVENANCE.md](docs/CITATION-PROVENANCE.md) | What does the provenance report say, and how do I read it? |
| [docs/PLAGIARISM.md](docs/PLAGIARISM.md) | How much of a draft's wording came from its sources? What the verbatim `overlap`/`scan` checks catch, and -- just as important -- what they cannot see, since these drafts are LLM-written and the tier that catches a genuine restatement does not run everywhere |
| [docs/WRITING-STANDARDS.md](docs/WRITING-STANDARDS.md) | What prose standards do the genre skills follow, and where in the technical-communication literature do they come from? |

### 🤝 Working on it

| Document | Answers |
| --- | --- |
| [docs/DESIGN.md](docs/DESIGN.md) | Why does this refuse what it refuses? The hard constraints, the conflict policy when two runs collide, and the failure analysis behind both |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | What must a grounded long-form writing system do, how does the closed- and open-source landscape stack up against that bar, and where does this pipeline stand against its own requirement set -- what's built, what was measured and declined, and what's left? |
| [docs/PARALLELISM.md](docs/PARALLELISM.md) | How does the parallel parse actually work, what is each component for, and what is planned next? |
| [docs/GROBID-CITATION-GRAPH.md](docs/GROBID-CITATION-GRAPH.md) | **A proposal, not a plan.** What would it take to build a corpus-internal citation graph, and is it worth a JDK and a long-running service? |
| [docs/TLDR.md](docs/TLDR.md) | What does `chitragupta draft tldr` cache today, and -- **parked, not built** -- what would it take to generate it unattended: the two-path design, what was measured on the real corpus, and why it's waiting on an acceptance workflow that doesn't exist yet? |
| [docs/AUTO-IMPROVEMENT.md](docs/AUTO-IMPROVEMENT.md) | **Unbuilt.** If the pipeline assembled its own worklist and attempted the mechanical repairs, what exactly would be built, and what would it have to satisfy? Normative, and carries no argument |
| [docs/AUTO-IMPROVEMENT-RATIONALE.md](docs/AUTO-IMPROVEMENT-RATIONALE.md) | Why that loop, and where its line falls: why every quality signal here currently ends in prose a human must act on, what a machine may never repair, and the one documented rule this cannot satisfy without the user's approval |
| [docs/HOUSE-STYLE.md](docs/HOUSE-STYLE.md) | Why prose is the axis a machine improves *best*, why a readability score is the wrong target, and which of your preferences should outlive the draft that prompted them |
| `DEVELOPER.md` (git checkout only -- `chitragupta init` deliberately does not scaffold it) | How do I run the tests, where does everything live, and what is unbuilt? |
| `DOCKER.md` (git checkout only) | How do I run this in a container? |
| `DEVELOPER-AGENTS.md` (git checkout only) | The rules an agent *changing this repo* must follow -- test policy, the local check suite, code standards, commit/PR/release conventions |
| [docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) | What must the code itself look like? The clean-code checklist mapped rule by rule, the two size rules that are machine-checked as a ratchet, why they count statements rather than lines, and why the rest is left to review |
| [docs/INSPIRATION.md](docs/INSPIRATION.md) | What did this project borrow, and from whom? Every external idea, what was taken, and -- where the licence requires it -- what was deliberately not |
| [docs/EXPORT-ZOTERO-GROUPS.md](docs/EXPORT-ZOTERO-GROUPS.md) | **Discouraged, and says so.** How the one script that reads `zotero.sqlite` directly recovers collection labels when Better BibTeX cannot, which two project rules it bends to do it, and why you should use Better BibTeX instead |

Every prose document ships in the release archive -- everything under
`docs/`, plus `SOUL.md`, `CLAUDE.md`, `AGENTS.md`, `DEVELOPER-AGENTS.md`
and `DEVELOPER.md` -- as do `.claude/`'s genre skills. Only this repo's own
machinery stays behind: `tests/`, `bench/` (the measurement harness and its
raw timings), `.github/` and `.gitignore`.

## 🙏 Acknowledgements

This project borrows from several others -- the deep-research skill's
7-phase method, the clean-code checklist its own code standard is written
against, and the harness-engineering reading list behind much of
`.claude/`. Each is credited, with what was taken and what deliberately
was not, in **[docs/INSPIRATION.md](docs/INSPIRATION.md)**.
