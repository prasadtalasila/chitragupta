# Research paper: a seventh genre, grounded in a software artefact

Status: **plan.** Written 2026-11-07 for epic #1179 (#1175 to #1178).

**Written for** whoever builds the `research-paper-writer` skill and the
code it calls. **Assumed:** `thesis-chapter-writer`'s process, the
dossier as [docs/DOSSIER.md](../docs/DOSSIER.md) describes it, and
`outline.md` as `chitragupta/dossier/_outline.py` parses it.
**Not covered here:** venue templates beyond the three named below,
and any check that runs the software itself.

## The problem

Every genre so far writes about other people's work. An original
research paper writes about the author's own: a piece of software and
the results of running it. Its claims have two kinds of evidence, and
the pipeline grounds only one:

| Claim about | Grounded in | Checked by |
| --- | --- | --- |
| Prior work | a citekey in the ledger | the citation gate |
| The software, its results | a file under `sources/<software>/` | nothing yet |

A paper that invents a number about its own evaluation is the same
failure as one that invents a citekey, and this genre exists to stop
both.

## Decisions (user, 2026-11-07)

1. **One fragment per section**, with the template, figure and main
   `.tex` files needed to compile them into a single `md`, `tex` and
   `pdf`.
2. **The paper-level inputs live in `paper.md`**, in the dossier, beside
   `outline.md`. One software may feed several papers.
3. **A real genre**, `research-paper`, in `dossier.GENRES` -- not a
   reuse of `thesis-chapter`.

The software lives at `sources/<software>/code/` and
`sources/<software>/results/`. The literature is used exactly as every
other genre uses it: retrieval, `evidence.md`, the gate.

## Why not `outline.md`

`_outline.py` accepts `brief:`, `claim:` and `queries:` under a heading
and nothing else: a new label inside a `brief:` is silently absorbed
into its text, and anywhere else it is an "unrecognised line". Venue,
message, contributions and software path are per paper, not per
section. So `outline.md` keeps its job (sections and their literature
queries) unchanged, and `dossier outline --check` and `dossier status`
keep working on it.

## The inputs

### `sources/<software>/results/MANIFEST.md`, per software, by hand

A result file cannot say what produced it. One `##` block per result,
reused by every paper about the software:

```markdown
## Gate pass rate {#gate-pass-rate}
file: results/2026-10/gate.csv
measures: share of drafts passing the citation gate first time, %, higher is better
setup: 40 drafts, 6 genres, one corpus of 1,400 papers, 3 runs, median reported
compares: chitragupta 6.140 against plain retrieval-augmented drafting
caveats: one author's library
```

`file:`, `measures:` and `setup:` are required; `compares:` and
`caveats:` are optional. When the file is missing the skill drafts it
from the result files and stops for the human to confirm it, because a
setup it guessed is exactly the fabrication this genre exists to stop.

### `content/dossiers/<paper>/paper.md`, per paper, by hand

Written by `dossier init --genre research-paper`, filled in by the
human. Its headings follow two sources. **The message** is the
Researchers' Bible's (Bundy et al., §8): a few sentences that form the
steps of an argument and steer the title, abstract, introduction,
conclusion and structure. **The five questions** are the Stanford
InfoLab introduction Widom describes: the problem, why it matters, why
it is hard, why it is unsolved, and the approach.

```markdown
- software: sources/chitragupta
- venue: IEEE Software
- template: IEEEtran
- pages: 10
- reader: a software-engineering referee who knows RAG but not this tool

## Message
## Problem
## Why it matters
## Why it is hard
## Why prior work falls short
queries:
- citation hallucination in LLM literature review
## Approach
## Contributions
- C1: ...
  section: design
  evidence: code chitragupta/citation_gate.py
## Research questions
- RQ1: ...
  answered-by: gate-pass-rate
## Known threats
```

`evidence:` names a manifest id (`result <id>`) or a path under the
software (`code <path>`). Only `## Why prior work falls short` takes
`queries:`, spelled as in `outline.md` and logged `--origin declared`.

### `content/dossiers/<paper>/artefact.md`, by the skill

The software's `evidence.md`: one block per fact the paper uses.

```markdown
## `gate-pass-rate`
source: result gate-pass-rate
value: 97.5 %
claim: Most drafts pass the gate on the first attempt.
```

`value:` is copied from the file, never rounded by hand. A number in a
section carries `% artefact: <id>` on its line, which is what the
critique step checks it against.

## The draft's layout

```text
content/drafts/<paper>/main.tex          preamble from the venue template
content/drafts/<paper>/sections/NN-<id>.tex   one fragment per section
content/drafts/<paper>/figures/<name>.{tex,txt}
```

The dossier is keyed by `main.tex`. Every per-file check runs per
section fragment, as `book-assembler` does per unit: the gate does not
follow `\input`. The previews are `render main.tex --format md|tex|pdf`,
one file each; the venue build is `latexmk -lualatex main.tex`.
Whether pandoc's LaTeX reader and `_copy_local_tex_includes` resolve
`sections/` one level down is checked in PR 3 before the skill relies
on it. `latexpand` is not installed here, so a flattened submission
`.tex` is out of scope until someone needs one.

## The writing rules

`.claude/skills-common/references/research-paper.md`, layered on
`docs/WRITING-STANDARDS.md`:

- **Researchers' Bible §8.** One message, stated in the title,
  abstract, introduction and conclusion; the main idea on the first
  page; a reader who is intelligent, ignorant and given to wilful
  misunderstanding; say what is new and compare explicitly with close
  work; worked examples illustrate a procedure and never replace its
  description; draft the central idea first and the introduction last.
- **Widom.** The five-paragraph introduction ending in contributions
  that each name a section; a new contribution clear by page 3; each
  section tells the story of the results, not of finding them;
  experiments report absolute performance, comparison with naive and
  prior approaches, sensitivity and scale; no background in the
  abstract; a conclusion that sharpens rather than repeats; no "etc.",
  no "for various reasons", no "this" without a referent.
- **Open University.** Hedge with modal verbs in proportion to the
  evidence; present differing perspectives; link ideas explicitly.

## The genre's two table entries

- `_units.UNITS["research-paper"] = "paragraph"`: related work is where
  synthesis matters, as in a thesis chapter.
- `_units.UNCITED_PROSE["research-paper"] = "ordinary"`: the design and
  evaluation sections describe the author's own work and carry no
  citation by design, as a textbook chapter's worked examples do.

## Increments

1. **#1175, register the genre.** `GENRES`, both `_units` tables, and
   `dossier init --genre research-paper` writing the `paper.md`
   template from a new `dossier/_paper.py` (`_create.py` has no
   headroom). This plan.
2. **#1176, validate the inputs.** `dossier paper <draft> --check`: the
   software directory exists, every `result <id>` resolves in the
   manifest, every `code <path>` exists, every contribution names a
   section and evidence, and the manifest's required fields are
   present. Advisory and exit 0, like `dossier outline --check`.
3. **#1177, render one paper from many files**: `render main.tex`
   yields one `md`, `tex` and `pdf`, tested with `sections/` and
   `figures/` one directory down.
4. **#1178, the skill**, on all three harnesses, with the reference file,
   `docs/WRITE-A-RESEARCH-PAPER.md`, the `GENRE.md` entry and the sweep
   of every genre and skill count it moves.
