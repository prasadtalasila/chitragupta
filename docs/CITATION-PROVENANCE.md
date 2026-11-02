# 📖 Citation provenance

Status: **implemented.**

**Written for** anyone reading a provenance report and deciding what to
do about a low-scoring claim. **Assumed:** a drafted, gated document.
**Not covered here:** the scoring internals a change to them would need,
which are in the module's own docstrings.

If you have a report open and want to know what to do, start at the
[worked example](#-worked-example) and read on through
[the calibration caveat](#-a-calibration-caveat-found-by-running-it):
those two sections are the whole answer. The sections between here and
there explain the problem and the design decisions. They are aimed at
whoever changes this feature, not at you.

## 💡 Background: what this repository does

Skip this section if you already know the codebase.

This project turns a personal reference library into cited prose. It runs
as two layers that never mix.

**The corpus layer is deterministic and has no AI in it.** You export a
`.bib` file from your reference manager.
`python -m chitragupta.corpus sync` reads it, records every
entry in a small SQLite "ledger" (`content/ledger.sqlite`), and extracts
each attached PDF's text into `content/parsed/<citekey>.txt`. Nothing is
generated; the bib file is the source of truth.

**The drafting layer drafts documents**, on demand, using those extracted
sources.

A **citekey** is the identifier BibTeX assigns an entry, for example
`larsen_engineering_2024`. In a draft it appears as
`[@larsen_engineering_2024]`.
The project's one hard rule is that **a citekey may only be used if it
came from the bib file**, because fabricated references have made it into
real published papers before. `python -m chitragupta.draft gate` enforces
this mechanically: it extracts every citekey from a draft and fails if
any is absent from the ledger. That is a *gate*: drafting is blocked
until it passes.

Some tools in the repo are gates. Others are **advisory**: they report something
for a human to judge, and never block. They form the **review layer**
(layer 4), and [REVIEW.md](REVIEW.md) is the page for it. The rest of
this page depends on the difference between the two.

Two other terms used here:

- **Parser backend**: how a PDF becomes text. `pdftotext` (fast, the
  default) or `docling` (slow, layout-aware). Set in `config.toml`.
- **The enrichment layer**: optional, opt-in stages under `chitragupta/enrich/`
  run by `python -m chitragupta.enrich`: layout-aware Docling parsing,
  embeddings and topic modelling.

## ❗ The problem

You are reading a draft. A sentence carries a citation:

> Simulation has become a cornerstone of developing and validating these
> systems [@zampetti_continuous_2023].

You have a doubt. It is not "is this citekey real?", which
`citation_gate` already answers as a hard gate. The doubt is different
and harder:

**Does the cited paper actually say this?**

Without this report, answering that means opening the PDF and reading
until you find the passage, or convincing yourself it isn't there. That is slow
enough that in practice it doesn't get done, so the failure it would
catch, a claim that drifted away from its source during drafting, ships.

### 💡 Why the existing tools don't cover it

Two other review aids sit close to this question, and neither answers
it.

`chitragupta/review/citation_coverage.py` asks the inverse: *of the sources
retrieval surfaced for a query, which ones did the draft actually cite?* That
finds sources you missed. It says nothing about whether the ones you did cite
support what you wrote.

The `verbatim` aid is closer but needs you to already know the answer's
shape. Two of its four modes take the citekey as an argument, so they
answer a question you have to have asked first:

- `overlap <draft> <citekey>`: longest verbatim word runs shared
  between the paragraphs citing that key and the source.
- `locate <citekey> "<phrase>"`: which page a phrase appears on.

(The other two take no citekey. `scan` slides the whole draft across the whole
corpus, which answers a different question, *did I reuse anyone's wording
anywhere*, and docs/PLAGIARISM.md is where it belongs. `recheck` re-scans the
draft against a baseline `scan --write` filed earlier.)

So it verifies a suspicion you have already formed about a specific
citekey. It cannot tell you *which* of a draft's forty citations deserve
suspicion in the first place.

There is also a subtler gap. `overlap` matches **exact word n-grams
(default n=8)**. That is the right tool for its own job, catching
borrowed wording (accidental plagiarism), but it is the wrong tool here.
A correctly paraphrased claim shares *no* 8-word run with its source and
scores zero, indistinguishable from a claim the source never made, and
a paraphrase is the case this report has to handle.

## 🎯 What it is for

A **citation provenance document**: for a given draft, a report that
walks every citation and shows what in the source supports it, so a
human reading the draft can jump straight to the doubtful ones.

It is a manual review step, run when you want it. It is not a gate and
not part of any automatic chain.

## 🏗 What it does

```bash
python -m chitragupta.review provenance content/drafts/<slug>.md
```

Writes a `.provenance.md` report, plus `.tex` and `.pdf` renders of the
same report beside it when `pandoc` (and, for `.pdf`, LuaLaTeX) are
available. It needs no venv.
([`survey.provenance.md`](examples/sample-project/content/review/dt-overview/survey.provenance.md)
in the committed sample project is one such report, written over the
sample corpus.)

The report mirrors the draft's own place under `content/drafts/`, the
same rule `content/rendered/` and `content/dossiers/` follow: a draft at
`content/drafts/<topic>/survey.md` reports to
`content/review/<topic>/survey.provenance.md`, alongside the same draft's
`survey.verbatim.md` and `survey.coverage.md`. A draft directly in
`content/drafts/`, or outside it altogether, has no path to mirror and
keeps the flat directory; a draft resolving outside `content/` is
refused. `chitragupta/review/__init__.py` owns that contract for every
review-layer command; see
[ARCHITECTURE.md](ARCHITECTURE.md#-layer-4-the-review-layer).

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
worth your attention instead of making you read forty entries to find
three.

### ⚖ Design decisions

**Advisory, not a gate.** This mirrors `citation_coverage.py`'s stated
position exactly, which is why the two share a layer. The reason is not
caution for its own sake: a lexical matcher cannot tell "this claim is
unsupported" from "this claim is supported in vocabulary the matcher
didn't recognise". Anything that *blocks* on that distinction would train
people to work around it, the corrosion `citation_gate` avoids by only
ever asserting something it can check exactly: ledger membership.

**Lexical overlap, not exact n-grams.** Scoring follows `locate`'s
approach (distinctive words from the claim, counted against the words in
each candidate source passage), not `overlap`'s verbatim runs. A
paraphrase keeps most of its content words while changing their order
and function words, so overlap scoring degrades gracefully where n-gram
matching falls off a cliff. Stopwords are dropped
(`passages.distinctive()`).

**Source text and pages come from the passage ladder.**
`passages.source_passages()` picks the best text available for each
citekey, from a Docling passage sidecar down to a fresh `pdftotext -layout`
run, so page resolution works whichever parser backend produced
`content/parsed/`. [LADDERS.md](LADDERS.md#-ladder-1-evidence-passages)
has the rungs.

**Stdlib only.** `citation_gate.py`, `references.py` and
`citation_coverage.py` all run under bare `python` with no venv, and so
does this. It reuses `citation_gate.extract_citekeys` (which returns
`(line_number, citekey)` pairs, and the line numbers are exactly what the
report needs) and `chitragupta/passages.py`, both stdlib-only.

## 🚫 What this deliberately does not do

**It does not judge whether the claim is true**, or whether the citation
is appropriate. It surfaces the evidence and leaves the judgment where it
belongs.

**It does not call an LLM.** Everything in the deterministic half of this
pipeline (the corpus layer) is local and reproducible; a semantic matcher
would be both non-deterministic and a new dependency, for a tool whose
output a human reads anyway.

**It will not catch every drift.** A claim paraphrased into different
vocabulary can score low despite being well supported, and a
claim that shares vocabulary with its source can score high while
misrepresenting it. The report is a reading order, not a verdict. This is
the limit of lexical matching, and the reason the tool warns instead of
gating.

## 📄 The Docling provenance sidecar

Docling's document model carries full provenance. On a real 17-page
paper we verified that **336 of 336 text items** had both a page number
and a bounding box, plus a semantic label. `export_to_markdown()` discards all
of it; Docling never loses it.

It is tempting to read this as a straight upgrade to the report's
*pointing*: cite an exact rectangle instead of a page. That part is
marginal. A reviewer opening a PDF at page 7 finds the passage in
seconds, and a bounding box only pays off if something renders a
highlight, which nothing here does. Reading order matters more.

### 💡 Reading order, and why it matters more than coordinates

`pdftotext -layout` preserves the *visual* arrangement of a page, not its
reading order. On a two-column paper that means two unrelated columns
share each output line:

```text
Ning and Wang provided an architecture of Future Internet    sequences transduce into different power management plan
of Things (IoT) using human neural network structure [10].   sequences. They used Moore's machine to represent power
```

Those are two different discussions, interleaved. Measured across a
10-paper sample:

| Papers | Long lines carrying two columns |
| --- | --- |
| 4 of 10 | **82%-89%** |
| 6 of 10 | 3%-9% (single-column; residue from tables) |

So roughly **40% of this corpus cannot yield a clean quotable passage**
from `content/parsed/` at all. Any window drawn over that text is a
splice of two arguments.

### ⚠ What this does and doesn't break

Interleaving affects *scoring* and *quoting* differently.

**Page-level locating survives interleaving.** `locate` scores a
page by how many distinctive words from the phrase appear anywhere in
it: a bag of words, order-independent. Column splicing moves words
around within a page; it doesn't move them to a different page. So
page-level matching works on all ten papers.

**Passage quoting does not survive it.** The "best-matching source
passage" field in the report above would, on those four papers, show a
reviewer two spliced half-sentences. That is worse than showing nothing,
because it reads as evidence.

Docling fixes this: its text items are reading-order-resolved and
semantically labelled, so a passage is a real passage. The bounding box
arrives in the same sidecar, essentially free, but the value is in the
reading order. So the report quotes a passage only where a Docling
sidecar supplies one, and otherwise reports the page and the score
without quoting. A precise rectangle around a badly matched paragraph
would be worse than a page number, because false precision invites
trust.

A full Docling parse costs about 6.65 s per PDF serially, 3330 s for a
501-PDF corpus, and 310 s at twelve workers
([PERFORMANCE.md](PERFORMANCE.md#-parserworkers----document-level-parallelism)).
The per-document cache is invalidated wholesale when the image, OCR or
cache-version settings change, so *those* re-parses cost full price.

## 📚 What the corpus layer keeps when it uses docling

Docling appears twice in this repository, for two different purposes. The
corpus layer's parser (`[parser].backend = "docling"`) and the enrichment
layer's `docling` stage are separate consumers of the same library, and
what each keeps decides what you can quote.

Markdown alone would lose what the passage ladder needs: it carries no
form feeds, so the ladder would find a single "page", decline it, and
fall through to a fresh `pdftotext` run, the column-splicing tool the
ladder exists to avoid quoting from. So the corpus layer keeps two
things from a Docling parse:

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
back to `pdftotext`, a parse that fails outright, and a re-parse of an
edited PDF all end at "no sidecar" instead of at last week's sentences
attributed to today's document.

The passage ladder that reads these files is in
[LADDERS.md](LADDERS.md#-ladder-1-evidence-passages): the enrichment
sidecar first, then the corpus sidecar, then the parsed text split on
form feeds, then a fresh `pdftotext -layout` run. Only the first two
rungs yield a quotable passage; the others report a page and refuse to
quote.

Rungs 1 and 2 hold the same kind of record from the same function; they
are separate files because the two layers own separate directories and
re-run on separate schedules. The corpus layer has to be able to
invalidate *its* sidecar on every re-parse without deleting an enrichment
sidecar it did not write and could not reproduce. Rung 1 is tried first
because the enrichment stage parses the PDF a second time under its own
OCR and figure settings.

**Which backend to choose, then.** Choose `docling` if you want quotable
passages without running the enrichment layer at all. That is the whole
reason to pay the slower parse. `pdftotext` (the default) is the right
choice if you only need page-level locating and want the fastest sync;
it lands on rung 3, which reports a real page and refuses to quote.
Docling in the corpus layer with no enrichment stage gives you the most
for a single parse.

`python -m chitragupta.review verbatim locate` reads the same files: it
splits `content/parsed/<citekey>.txt` on form feeds, so it reports the page
a phrase sits on instead of `pdf p.1` for every hit.

There is one limit. Docling emits a page break *between* consecutive
pages that carry items, and none before the first, so the nth segment is
page n, but a page carrying no items at all contributes no break and
shifts the pages after it. The sidecar is unaffected, because it records
each item's own `page_no` instead of counting separators. Where the two
disagree, the sidecar is right.

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

This is why the bands are described as a reading order and not a
measurement, and why the report says so in its own header. A single
absolute threshold that meant the same thing for both sources would
require normalising by passage length, which buys precision the tool
does not claim to have.

## ✂ How a claim is cut from the draft

The claim a citation is scored against has a *correct size*. Too small,
and it matches nothing; too large, and it dilutes the score. Three rules
set it.

### 📏 The unit is the block

Every draft this project produces is hard-wrapped, so a sentence spans
several lines and a citation lands on whichever one holds it. A claim is
therefore reconstructed from its whole block, then split into sentences
with an abbreviation-aware splitter, so `Fig. 1`, `e.g.` and
`Smith et al. (2020)` do not end a sentence early. Reading the citing
line alone produces claims like `.` that match nothing and report false
"no support found" findings.

A block is not everything between two blank lines. A Markdown table has
no blank lines in it, so that rule would make a citation in a table cell
take the **entire table** as its claim. Scoring divides by the claim's
own distinctive words, so a whole-table claim cuts the maximum
achievable score to roughly a quarter and pushes supported citations
under the band thresholds; and five citekeys in one table would share a
single claim. So a table row and a list item are each their own claim. A
row is flattened to `cell -- cell -- cell` prose, so no pipe reaches the
report, and a heading is not glued to the paragraph beneath it.

### 🧾 LaTeX follows the same rules

Every genre skill exports `.tex` and `.pdf` beside the Markdown, and a
`tabular` has the same problem with one extra cost: `\begin{tabular}{lll}`,
`\toprule` and `\midrule` would reach the scorer as content words no
source can match. The LaTeX rules mirror the Markdown ones, with one
structural difference: a `tabular` row ends at `\\`, not at a newline,
so a row hard-wrapped over three lines is still one claim.

| | Markdown | LaTeX |
| --- | --- | --- |
| Row | a `\|` line | text up to `\\` |
| Cells | split on unescaped `\|` | split on unescaped `&` |
| List item | `-`, `*`, `+`, `1.` | `\item` |
| Heading | `#`..`######` | `\chapter`, `\section`, `\subsection`, `\paragraph` |
| Dropped as structure | the `\|---\|` separator row | `\begin`/`\end`, `\toprule`, `\midrule`, `\bottomrule`, `\hline`, `\cline` |

### 🔖 Narrative citations become an elision

Citation markup is removed before scoring, so the markers do not read as
content words the cited paper ought to contain. That is right for
`[@key]` and `\citep{key}`, which stand *outside* the sentence's grammar.
It is wrong for `\citet{key}`, which renders as "Smith et al. (2024)"
and *is* a noun phrase in the sentence. Deleting it would quote back
claims like "The vocabulary of sharpens the claim".

Narrative markers are therefore replaced by `[...]`. The replacement is
an elision, not the author-year text it stands for. This report scores a
claim by word overlap against the cited paper's own text, and that text
contains its own authors' names: on the title page, in the running head,
in its self-citations. Substituting "Smith" would hand every narrative
citation a hit unrelated to the claim, inflating the band that flags
weak support, silently and in the direction that hides a problem.
`[...]` contributes no word to `distinctive()`, so the score is
unchanged and only the quoted text moves.

## 🧱 Where the code lives

The sidecar -> form-feed pages -> `pdftotext` ladder, and the rule that a
source with no reading order reports a page and not a quotation, live
in `chitragupta/passages.py`, because retrieval and the other review aids
read the same ladder: a snippet shown to a drafting
agent *as evidence* is under the same constraint as a passage shown to a
reviewer, and the two must not answer "what does this source say here?"
from different text. `citation_provenance` owns everything above
the ladder: which sentence carries a citation, how it scores, how the
report reads.
