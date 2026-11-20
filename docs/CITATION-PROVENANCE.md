# 📖 Citation provenance

Status: **implemented.**

**Written for** anyone reading a provenance report and deciding what to
do about a low-scoring claim. **Assumed:** a drafted, gated document.
**Not covered here:** the scoring internals a change to them would need,
which are in the module's own docstrings.

If you have a report open, the [worked example](#-worked-example) and
[the calibration caveat](#-a-calibration-caveat-found-by-running-it) are
the whole answer. The other sections explain the design, for whoever
changes this feature.

This is an advisory review aid: it reports for a human to judge and
never blocks, unlike `python -m chitragupta.draft gate`, which fails a
draft whose citekeys are not in the ledger. [REVIEW.md](REVIEW.md) covers
the review layer it belongs to, and [GLOSSARY.md](GLOSSARY.md) the terms.

## ❗ The problem

You are reading a draft. A sentence carries a citation:

> Simulation has become a cornerstone of developing and validating these
> systems [@zampetti_continuous_2023].

`citation_gate` already answers "is this citekey real?". The harder
question is: **does the cited paper actually say this?** Answering it by
hand means reading the PDF until you find the passage, which in practice
does not get done, so a claim that drifted from its source ships.

### 💡 Why the existing tools don't cover it

`chitragupta/review/citation_coverage.py` asks the inverse: which of
the sources retrieval surfaced did the draft cite? It finds sources you
missed, not whether the ones you cited support what you wrote.

The `verbatim` aid's `overlap <draft> <citekey>` and
`locate <citekey> "<phrase>"` take a citekey, so they verify a suspicion
you have already formed; they cannot tell you *which* of a draft's forty
citations deserve suspicion. (Its `scan` and `recheck` modes answer a
different question, reused wording, which
[PLAGIARISM.md](PLAGIARISM.md) covers.) And `overlap` matches **exact
word n-grams (default n=8)**, right for catching borrowed wording but
wrong here: a correct paraphrase shares no 8-word run with its source and
scores zero, like a claim the source never made.

## 🎯 What it is for

A **citation provenance document**: for a given draft, a report that
walks every citation and shows what in the source supports it, so a
human can jump straight to the doubtful ones. It is a manual review step,
not a gate and not part of any automatic chain.

## 🏗 What it does

```bash
python -m chitragupta.review provenance content/drafts/<slug>.md
```

Writes a `.provenance.md` report, plus `.tex` and `.pdf` renders beside
it when `pandoc` (and, for `.pdf`, LuaLaTeX) are available. It needs no
venv. The sample project's
[`survey.provenance.md`](examples/sample-project/content/review/dt-overview/survey.provenance.md)
is one such report. A draft at `content/drafts/<topic>/survey.md`
reports to `content/review/<topic>/survey.provenance.md`; the path rule
is shared by every review-layer command
([ARCHITECTURE.md](ARCHITECTURE.md#-layer-4-the-review-layer)).

For each citing passage in the draft, it emits:

| Field | Meaning |
| --- | --- |
| Draft location | Line number and the citing sentence or, where the citation sits in a table, a list or a heading (Markdown or LaTeX), that row, item or heading alone |
| Citekey | The key cited there |
| Best-matching source passage | The span of that paper's text closest to the claim |
| Page | Where that passage sits in the PDF |
| Score | How strong the lexical match is |
| Flag | Explicit **NO SUPPORT FOUND** when nothing clears a floor |

Sorted **worst match first**, so the report opens on the citations most
worth your attention.

### ⚖ Design decisions

**Advisory, not a gate**, like `citation_coverage.py`. A lexical
matcher cannot tell "this claim is unsupported" from "this claim is
supported in vocabulary the matcher didn't recognise", and anything that
blocks on that distinction would train people to work around it.
`citation_gate` avoids that by asserting only what it can check exactly:
ledger membership.

**Lexical overlap, not exact n-grams.** Scoring follows `locate`:
distinctive words from the claim (stopwords dropped by
`passages.distinctive()`), counted against each candidate source passage.
A paraphrase keeps most of its content words, so this degrades
gracefully where n-gram matching falls off a cliff.

**Source text and pages come from the passage ladder.**
`passages.source_passages()` picks the best text available for each
citekey, from a Docling passage sidecar down to a fresh `pdftotext -layout`
run, so page resolution works whichever parser backend produced
`content/parsed/`. [LADDERS.md](LADDERS.md#-ladder-1-evidence-passages)
has the rungs.

**Stdlib only**, like `citation_gate.py` and `citation_coverage.py`. It
reuses `citation_gate.extract_citekeys` (whose `(line_number, citekey)`
pairs give the report its line numbers) and `chitragupta/passages.py`.

## 🚫 What this deliberately does not do

**It does not judge whether the claim is true**, or whether the citation
is appropriate. It surfaces the evidence and leaves the judgment where it
belongs.

**It does not call an LLM.** A semantic matcher would be
non-deterministic and a new dependency, for output a human reads anyway.

**It will not catch every drift.** A well-supported claim in different
vocabulary can score low, and a misrepresentation sharing vocabulary can
score high. The report is a reading order, not a verdict, which is why
it warns instead of gating.

## 📄 The Docling provenance sidecar

Docling's document model carries full provenance: on a real 17-page
paper, **336 of 336 text items** had a page number, a bounding box and a
semantic label. `export_to_markdown()` discards all of it. The bounding
box is marginal, since a reviewer finds a passage on page 7 in seconds
and nothing here renders a highlight. Reading order matters more.

### 💡 Reading order, and why it matters more than coordinates

`pdftotext -layout` preserves the *visual* arrangement of a page, not its
reading order. On a two-column paper that means two unrelated columns
share each output line:

```text
Ning and Wang provided an architecture of Future Internet    sequences transduce into different power management plan
of Things (IoT) using human neural network structure [10].   sequences. They used Moore's machine to represent power
```

Measured across a 10-paper sample:

| Papers | Long lines carrying two columns |
| --- | --- |
| 4 of 10 | **82%-89%** |
| 6 of 10 | 3%-9% (single-column; residue from tables) |

So roughly **40% of this corpus cannot yield a clean quotable passage**
from `content/parsed/` at all.

### ⚠ What this does and doesn't break

**Page-level locating survives interleaving.** `locate` scores a page as
an order-independent bag of distinctive words, and splicing does not
move words to a different page, so it works on all ten papers.

**Passage quoting does not survive it.** On those four papers the
"best-matching source passage" would show two spliced half-sentences,
which is worse than nothing because it reads as evidence.

Docling's text items are reading-order-resolved, so a passage is a real
passage. The report therefore quotes a passage only where a Docling
sidecar supplies one, and otherwise reports the page and the score
without quoting. For what a Docling parse costs, see
[PERFORMANCE.md](PERFORMANCE.md#-parserworkers----document-level-parallelism).

## 📚 What the corpus layer keeps when it uses docling

The corpus layer's parser (`[parser].backend = "docling"`) and the
enrichment layer's `docling` stage are separate consumers of Docling.
Markdown alone carries no form feeds, so the passage ladder would find a
single "page" and fall through to a fresh `pdftotext` run. The corpus
layer therefore keeps two things from a Docling parse:

- `export_to_markdown(page_break_placeholder="\f")` writes the page
  boundaries into `content/parsed/<citekey>.txt`, so it has the same
  shape as `pdftotext`'s output. Checked on a real 51-page paper: 51
  pages in the model, 51 form-feed-separated segments in the file.
- The structure Markdown cannot carry leaves by a second door, as
  `content/parsed/<citekey>.passages.json`, the same records
  `chitragupta/passages.py`'s `passage_records()` produces for the enrichment
  layer. On that same paper: 592 records spanning pages 1 to 51, every one
  carrying both a page number and a bounding box.

A sidecar quotes the PDF *as parsed when it was written*, so it is
dropped before every re-parse instead of replaced after one. A switch
back to `pdftotext`, a failed parse, and a re-parse of an edited PDF all
end at "no sidecar", never at last week's sentences attributed to
today's document.

[LADDERS.md](LADDERS.md#-ladder-1-evidence-passages) has the ladder that
reads these files: the enrichment sidecar, the corpus sidecar, the
parsed text split on form feeds, then a fresh `pdftotext -layout` run.
Only the first two rungs yield a quotable passage. Rungs 1 and 2 are
separate files because the two layers own separate directories and
re-run on separate schedules: the corpus layer must invalidate *its*
sidecar on every re-parse without deleting an enrichment sidecar it
could not reproduce.

**Which backend to choose, then.** Choose `docling` if you want quotable
passages without running the enrichment layer; that is the whole reason
to pay the slower parse. `pdftotext` (the default) suits page-level
locating and the fastest sync; it lands on rung 3, which reports a real
page and refuses to quote. `verbatim locate` reads the same files, so it
too reports the real page a phrase sits on.

One limit: a page carrying no Docling items contributes no form feed and
shifts the page numbers after it in the `.txt`. The sidecar records each
item's own `page_no`, so where the two disagree, the sidecar is right.

## 📝 Worked example

Run against a real 13-citation draft over a 10-paper corpus, the report
opens like this:

```markdown
## Summary

- 8 weak
- 5 supported

## Findings

### Weak

#### Line 29 -- `[@aldalur_microservice-based_2024]` (40% match)

> A cyber-physical system is a program whose input is the physical world
> and whose output *changes* that world -- a definition captured in the
> literature as systems that "integrate digital cyber computations with
> physical processes", or equivalently as combinations of computing and
> physical processes.

Best match is on **page 2** of the source.
```

With a Docling sidecar present, that last line is replaced by the actual
paragraph from the paper.

## ⚠ A calibration caveat, found by running it

Scores are comparable *within* a passage source, not across them. A
quoted paragraph is a far smaller haystack than a whole page, so the
same quality of support scores lower against a paragraph.

On one real 13-citation draft, the identical citations banded as **8
weak / 5 supported** with page-level fallback, and **12 weak / 1
supported** once Docling paragraphs were available. The matches did not
get worse; the denominator got smaller.

This is why the bands are a reading order and not a measurement, and
the report says so in its header. Normalising by passage length would buy
precision the tool does not claim to have.

## ✂ How a claim is cut from the draft

The claim a citation is scored against has a *correct size*: too small
matches nothing, too large dilutes the score.

### 📏 The unit is the block

Drafts are hard-wrapped, so a claim is reconstructed from its whole
block, then split into sentences with an abbreviation-aware splitter, so
`Fig. 1`, `e.g.` and `Smith et al. (2020)` do not end a sentence early.
Reading the citing line alone produces claims like `.` that report false
"no support found" findings.

A block is not everything between two blank lines: a citation in a table
cell would then take the **entire table** as its claim, cutting the
maximum score to roughly a quarter. So a table row and a list item are
each their own claim. A row is flattened to `cell -- cell -- cell`
prose, and a heading is not glued to the paragraph beneath it.

### 🧾 LaTeX follows the same rules

Every genre skill exports `.tex` beside the Markdown, where structure
such as `\toprule` would otherwise reach the scorer as content words. The
rules mirror the Markdown ones, except that a `tabular` row ends at
`\\`, not at a newline.

| | Markdown | LaTeX |
| --- | --- | --- |
| Row | a `\|` line | text up to `\\` |
| Cells | split on unescaped `\|` | split on unescaped `&` |
| List item | `-`, `*`, `+`, `1.` | `\item` |
| Heading | `#`..`######` | `\chapter`, `\section`, `\subsection`, `\paragraph` |
| Dropped as structure | the `\|---\|` separator row | `\begin`/`\end`, `\toprule`, `\midrule`, `\bottomrule`, `\hline`, `\cline` |

### 🔖 Narrative citations become an elision

Citation markup is removed before scoring. That is right for `[@key]`
and `\citep{key}`, which stand outside the sentence's grammar, but
`\citet{key}` *is* a noun phrase ("Smith et al. (2024)"), and deleting it
would quote back claims like "The vocabulary of sharpens the claim".

Narrative markers are therefore replaced by `[...]`, not by the
author-year text. The cited paper contains its own authors' names, so
substituting "Smith" would hand every narrative citation a hit unrelated
to the claim, hiding weak support. `[...]` contributes no word to
`distinctive()`, so the score is unchanged.

## 🧱 Where the code lives

The passage ladder, and the rule that a source with no reading order
reports a page and not a quotation, live in `chitragupta/passages.py`,
because retrieval and the other review aids read the same ladder: a
snippet shown to a drafting agent and a passage shown to a reviewer must
not answer "what does this source say here?" from different text.
`citation_provenance` owns which sentence carries a citation, how it
scores, and how the report reads.
