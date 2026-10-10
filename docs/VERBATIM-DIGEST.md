# 📋 The verbatim digest

Status: **reference.** Written 2026-10-09, for
[discussion 991](https://github.com/prasadtalasila/chitragupta/discussions/991).

**Written for** someone studying a topic who wants the papers' own
words in one place, and for whoever reads the report that checks
them. **Assumed:** [GENRE.md](GENRE.md) for how the other genres differ,
[REVIEW.md](REVIEW.md) for what every review aid has in common, and
[DOSSIER.md](DOSSIER.md) for the `claim:`/`quote:` contract the digest
reads the other way round. **Not covered here:** the matcher's
normalisations, which are
[CLI.md](CLI.md#-chitragupta-review-quotation)'s and
`plans/c3-quotation-integrity.md`'s, and the review layer's reasons for
never gating, which are [ARCHITECTURE.md](ARCHITECTURE.md)'s.

A verbatim digest is **private study text**. Most of it is copied
exactly from parsed PDFs in the corpus; each copied run ends with a
citation; there are no quotation marks; and a few short sentences of
the drafter's own connect the runs. One person reads it to learn a
topic. It is not a deliverable, and it is never a source for drafting a
survey, a chapter or anything else, because its wording is the corpus's
own.

Three goals, in this order:

1. **Maximise copied text.**
2. **Surface unsupported text.** Every sentence that is not verified
   source text is listed for a person to judge.
3. **Minimise unsupported text.** Each repair pass leaves fewer such
   words than the one before, and a baseline recheck makes that a
   number.

A digest is a draft like any other. The user names it,
`content/drafts/<topic>/<name>.md`; its dossier's `scope.md` records
`- genre: digest`, which is the only thing that makes it one; it is
rendered beside the topic's other drafts; and it is per-host data under
`content/` like every draft, so the blanket rule in `.gitignore` keeps
it out of git without a rule of its own.

## 🧭 Table of contents

- [Writing one: `review-digest`](#-writing-one-review-digest)
- [Reading the report: `review digest`](#-reading-the-report-review-digest)
- [Pages, and what a page note means](#-pages-and-what-a-page-note-means)
- [The repair loop and `--baseline`](#-the-repair-loop-and---baseline)
- [Lexical support, and what the NLI `support` aid adds](#-lexical-support-and-what-the-nli-support-aid-adds)
- [Figures and equations](#-figures-and-equations)
- [What it does not do](#-what-it-does-not-do)
- [The rule it lives under](#-the-rule-it-lives-under)

## ✍ Writing one: `review-digest`

The format is plain prose plus a closing citation:

```markdown
Sentence one. Sentence two. Sentence three. [@key, p. 4-5]
A connecting sentence of your own.
Another copied sentence. [@other, p. 12]
```

**A citation covers every sentence back to the previous citation, or
to the start of the paragraph.** One citation can therefore cover a
sentence, several sentences or a whole paragraph, and a sentence of the
drafter's own placed *inside* a run, before its citation, is read as
part of the run and reported as not copied. The skill copies from one
paper per run, closes each run with its citation and a page, and keeps
its own sentences short, few and between runs.

The skill follows `survey-writer`'s draft-and-render workflow step for
step: dossier, retrieval per sub-theme, gate, references, render to
`tex`/`pdf`/`md`, a read as the reader, steering, the prose check, the
fingerprint stamp. A survey minimises copying and a digest maximises it,
so the survey's steps that exist to keep source wording out of the
draft are inverted where they stand, and the skill says so at each one:

| Survey step | In the digest |
| --- | --- |
| The evidence packet: `claim:` in the drafter's words, a `quote:` only when a quotation is warranted, prose drafted from `claim:` alone | Every passage to be copied is recorded as a `quote:`, since every run is an intended quotation; `claim:` still says what the passage establishes, and is drafted from only for the connecting sentences |
| Multi-source synthesis: a paragraph rests on two or more sources so it cannot be a transcription ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §11) | One source per run, a transcription by design. The unit is the whole document |
| The pre-gate critique against the evidence packet | Replaced by `review digest`: a digest is not drafted from the packet |
| The verbatim scan | Replaced by `review digest`: the scan would flag every run, which is the design |
| The evidence sidecar | Not rendered: the digest *is* the sources' words, attributed where they stand |
| The prose check | Run and reported, nothing fixed; copied text keeps its source's style |

The one rule the skill adds is a prohibition: **never run
`agenda-reviser` on a digest.** The agenda does not read the digest
report, but `agenda-reviser`'s `verbatim-run` repair paraphrases short
runs unattended, and on a digest that is the whole text.

## 🔍 Reading the report: `review digest`

```bash
python -m chitragupta.review digest content/drafts/<topic>/<name>.md
```

The report is filed at `content/review/<topic>/<name>.digest.md` with
its `.json` beside it, on every run, because the `.json` is the next
pass's baseline. It opens with three fractions that together account
for the whole digest, in the order a reader should take them:

| Line | Counts | Direction |
| --- | --- | --- |
| Unsupported fraction | the words of every sentence carrying any finding, a sentence counted once however many classes it carries, over all words | down: the headline, the number a repair pass drives |
| Copied fraction | the words of every verified copied span, over all words | up |
| Not checkable | the words of every run whose cited source has no reading-ordered passages: no Docling sidecar. The reason names the stage to run | a fact about the corpus, not the digest |

Each run is matched whole against the cited source, with the same
matcher `review quotation` uses: both sides flattened to one character
stream, an inline reference marker stripped from the source, and the
run looked for in each passage and each adjacent pair. The passages
are a Docling sidecar's, `content/parsed/<citekey>.passages.json`,
which `chitragupta enrich --stages docling` writes. **The aid needs the
enriched corpus.** A `pdftotext` parse has no reading order, and a run
copied from one can be a collage of two columns, which is the hazard
`review quotation` refuses to quote from; this aid refuses the same
way, reports the run as not checkable, and names the stage to run. A
run found
whole is one **copied span** and raises nothing. A run whose sentences
are all found but not contiguously is one span with the note
*assembled from N places*, which is information rather than a finding.
Only a run that breaks is split into sentences, and only to show where:

| Class | Means | Repair |
| --- | --- | --- |
| `unsupported-text` | a sentence of the drafter's own, and either no citation covers it or the cited source does not lexically support it | cite it correctly, replace it with the source's words, or delete it |
| `copy-mismatch` | a sentence not found verbatim but mostly on one page of the source; the item names the page and the missing words | open the source at that page and restore the exact wording |
| `unquoted-text` | a sentence of the drafter's own that the cited source does lexically support | replace it with a copied passage, or delete it |

A sentence of the drafter's own carries `unquoted-text` always, and
`unsupported-text` as well when the support test fails, so one sentence
can be two items; the fraction counts its words once. Items are listed
worst class first, then by line, in the agenda's own line format: a
stable twelve-character id (a hash of the sentence, never its line, so
an id survives an edit elsewhere), `[surfaced]`, the section, a one-line
summary. **Every item is `[surfaced]`.** Whether a source backs a
sentence, and which passage should replace it, are judgement calls, and
no re-run of a check can settle them. Nothing here is a gate, and the
command exits 0 whatever it finds.

## 📄 Pages, and what a page note means

A page here is the **parser's physical page index, counted from 1 over
the PDF as parsed**: the `page` a Docling passage sidecar records, or
the form feed `pdftotext` emits between pages. It is not the printed
folio. A paper whose first page is numbered 1203 in the journal is still
p. 1 here, and the skill's format rule says to cite pages that way.

The page in a citation is a **hint**. The aid matches text, not pages:
it searches every passage of the cited source and reports the page or
pages the run was actually found on. A run that crosses a page break
reports both pages. When no found page falls inside the cited range,
the copied span carries a note:

```text
cited p. 4-5, found on p. 7
```

A note is not a finding. It does not move any fraction, it does not
appear in the item list, and the repair is to correct the locator in
the citation. It can also mislead in one case worth knowing: the
passages a source yields depend on which rung of
[CITATION-PROVENANCE.md](CITATION-PROVENANCE.md)'s ladder answered, and
a re-run of the Docling stage can renumber them, so a note that
appears after one is worth a look before an edit.

## 🔁 The repair loop and `--baseline`

```bash
python -m chitragupta.review digest content/drafts/<topic>/<name>.md \
    --baseline content/review/<topic>/<name>.digest.json
```

The baseline is the `.json` a previous run filed. The aid recomputes
everything, refiles the report, and then compares: items are matched by
id into `resolved`, `persisting` and `new`; the per-class counts and
both fractions are printed before and after; and one line, `fell: yes`
or `fell: no`, says whether the repair counted. It counts when **no
class rose, at least one fell, nothing new appeared, and the
unsupported fraction did not rise**. The fraction is checked as well as
the counts because deleting a flagged sentence together with half the
copied text resolves an item and makes the digest worse.

The skill keeps a repair only under those conditions plus a passing
gate, logs every attempt in the dossier's `revisions.md`, and stops
when the user says so, when no item is left, or after three passes
whose fraction did not fall. It repairs only when a person asked for a
pass.

## 🧠 Lexical support, and what the NLI `support` aid adds

`unsupported-text` is decided lexically. The sentence's distinctive
words (content words, stemmed, with short tokens dropped) are counted
against the words of each passage of the cited source, and the best
passage's share is compared with the provenance aid's weak band,
`[provenance].weak_score` in `config.toml`, default 0.20. Below it the
sentence is `unsupported-text`. A sentence no citation covers is
`unsupported-text` without a test.

That catches the clear case: a sentence about something the source
never mentions. It cannot see two others. A correct paraphrase in
different words can score weak and be flagged although the source does
say it; and a sentence that *negates* the source shares all its content
words and scores strong, so it is not flagged. These are the limits
[CITATION-PROVENANCE.md](CITATION-PROVENANCE.md) records for the
provenance aid, inherited here deliberately rather than restated.

`python -m chitragupta.review support` closes the second gap. It runs a
real natural-language-inference entailment model over each citing
sentence and the passages that lexically match it, and reports whether
the source entails, is neutral to, or contradicts the sentence, so a
negation is caught. It is not wired into `review digest` for three
reasons: it needs the `enrich` extra, which installs a torch model of
several hundred megabytes; it costs tens of seconds per draft where
every other digest check is instant; and keeping the digest aid at
interpreter tier 1, stdlib only, means it runs on any host that can run
the gate. To use it on a digest, run it on the same file, read its
report beside the digest's, and treat an `unsupported-text` item the
model marks entailed as "cite it correctly" rather than "delete it". A
later change could add a `--support` flag that runs the two together;
the agenda's `claim-support` class is the shape it would take.

## 🖼 Figures and equations

Where the corpus was enriched with the Docling stage and
`[enrich].docling_images` on, `python -m chitragupta.draft figures
<citekey>` lists a paper's figures with a caption, a page, a crop and
the exact string to cite each by. The skill looks at them while choosing
passages, and the repository's rule for every genre holds here without
exception: **a figure is consulted, never reproduced**. A digest may
carry a figure's caption, copied verbatim as a run of the source's own
words, and a connecting sentence of the drafter's that names the figure
by its cite string; that sentence is the drafter's and is listed as
`unquoted-text` like any other.

A decoded equation is text. With `[parser].formulas` on, the Docling
parse writes each formula as LaTeX into the passage sidecar, and the
skill copies it inside its run exactly as it copies the words around
it; the matcher flattens both sides to one character stream, so a
copied formula matches its source like any sentence.

Neither is a precondition. A corpus parsed without images or without
formulas has no crops and no decoded equations; the figures command
says which of the two it is and exits 0, the skill tells the user in
one line, and the digest is built from the prose alone.

## 🚧 What it does not do

- **Attribution is coarse.** A sentence of the drafter's own placed
  inside a run before its citation is read as part of the run and
  reported as not copied. Two papers copied under one citation show the
  second paper's text as unmatched. The fix is to cite each paper at the
  end of its own part.
- **It needs the enriched corpus.** Without a Docling sidecar for a
  cited source, every run citing it is not checkable, including a run
  whose bracket also names a source that does have one (matching
  against the readable source alone would report text copied from the
  other as the drafter's own); the report names the stage to run.
  Within a sidecar, parse quality still bounds matching: a faithful
  copy of a mangled passage matches, a copy made
  from the PDF that the parse mangled shows as `copy-mismatch`. Copy
  from the sidecar's text, not the PDF.
- **A half-copied sentence is reported whole**, as a `copy-mismatch`
  naming the words that are not on the page, not split into a copied
  part and an original part.
- **Lexical support is weak evidence**, as the section above says.
- **An item's id is its sentence**, as an agenda item's is, so the same
  connecting sentence written twice in one section is one id, and a
  baseline comparison sees one item until both copies are gone.
- **A citation closes a run wherever it sits.** The format puts it
  after the last copied sentence; a narrative citation mid-sentence
  (`[-@key]`, or `@key` in prose) splits the sentence across two runs
  and is outside what the aid reads.
- **The agenda does not read it, and `agenda-reviser` never touches
  it.** The digest's classes mean nothing outside a digest, and wiring
  them into the agenda would add a line to every existing agenda for a
  report no survey or chapter has. The digest's report is its own
  worklist, worked by `review-digest` on request.

## ⚖ The rule it lives under

[SOUL.md](../SOUL.md) refuses to pass a source's wording off as the
drafter's. A digest keeps that rule by construction: every copied run
ends with the citation that names its source, the dossier records every
copied passage as a `quote:`, and the digest is never a source for any
other draft. [AGENTS.md](../AGENTS.md)'s statement that verbatim wording
has one legitimate home outside the draft names the digest as the one
genre that is that home, and [PLAGIARISM.md](PLAGIARISM.md)'s verbatim
scan is what catches the digest's wording if it ever reaches a draft
that is not one.
