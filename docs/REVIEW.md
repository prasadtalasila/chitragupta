# 🔍 The review layer

Status: **reference.** Written 2026-08-22. Updated 2026-08-31, describing the
ten aids as they stand.

**Written for** you, after a draft is finished -- someone deciding
whether it is good enough to hand over. **Assumed:**
[FEATURES.md](FEATURES.md) for where this sits among the pipeline's
features. **Not covered here:** why a review aid may never become a gate,
which is an architecture question and lives in
[ARCHITECTURE.md](ARCHITECTURE.md#-layer-4-the-review-layer); and how the
verbatim detector works internally, which is
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md).

**This is the human-facing half of the pipeline's record-keeping**, and
that is the clean split from its counterpart. [DOSSIER.md](DOSSIER.md)
documents working state a *model* reloads to keep drafting; this
documents evidence *you* weigh before deciding a draft is done. The two
mirror the same draft path and are otherwise unalike:

| | The dossier | A review report |
| --- | --- | --- |
| Read by | usually an LLM, resuming a run | you, once, near the end |
| Written | continuously, while drafting | on demand, after a draft exists |
| If nobody reads it | the next revision pays twice | nothing happened; it was advisory |
| Lives in | `content/dossiers/` | `content/review/` |

## 🔑 The one thing to understand first

**None of these is a gate, and none may become one.** Each produces
evidence for a human judgement, never a verdict, and each exits 0 whether
it finds something or not. Nothing in the pipeline reads a report back;
no draft is blocked by what one says.

That is a design commitment rather than a current limitation --
[SOUL.md](../SOUL.md) commits to it, and
[ARCHITECTURE.md](ARCHITECTURE.md#-layer-4-the-review-layer) has the
argument for why decidability is not what earns a check the right to
block. What matters here is the consequence: **an aid that finds nothing
is not a clean bill of health, and an aid that finds something is not an
accusation.** Both are input to your judgement.

They also **take no lock**, so any of them runs happily while
`chitragupta corpus sync` is rebuilding the corpus.

## 🧩 The ten aids

**`review provenance` -- does the cited paper actually say this?** The
gate answers "is this citekey real?" exactly, and that is all it can
answer. A claim that drifted away from its source during drafting passes
the gate cleanly, because the citekey is perfectly real; only reading the
source catches it. This report quotes, for each citation, the passage in
the cited source that supports it and where it sits, so the question
becomes a two-minute read rather than a re-derivation.
[CITATION-PROVENANCE.md](CITATION-PROVENANCE.md) has the scoring.

**`review verbatim` -- how much wording came along with the ideas.** Two
shapes of question behind one aid. `overlap` and `locate` compare the
draft against *one* cited source and tell you which page a phrase is on;
`scan` compares it against **any** parsed source, cited or not -- which is
the one that finds reuse from a paper the paragraph never cites, and
reuse in connective prose that cites nothing at all. Detection runs in
three tiers (exact n-gram, skip-gram, embedding), and it names the tier
it could not run rather than silently reporting less.

**`review coverage` -- did the draft use what retrieval found?** Give it
the queries, and it reports which surfaced candidates were cited and
which were not. An uncited high-scorer is either a source the draft
skipped or a query that was too broad, and the report deliberately does
not decide which. It also shows citekeys cited but surfaced by none of
your queries, which is normally *not* a gap -- the skill ran other
queries -- and is shown so the report cannot be misread as a gap-finder.

**`review synthesis` -- how many sources is each unit standing on?**
Prose required to fuse two or more sources cannot be a transcription of
any one of them: you cannot transcribe two sources simultaneously. That
is the guarantee the writing standards ask for, and this makes it
observable. The *unit* differs by genre -- paragraph for a survey, a
thesis chapter and a deep-research report; the section for a textbook
chapter; the whole document for a tutorial, whose body carries no
citations by design -- and the report's header names which unit it used
and where that came from, so a tutorial's report is not read against a
survey's expectations.

**`review figure` -- what a TikZ figure's own geometry says.**
Overlapping nodes, content protruding past the frame, node text too long
to fit, page-width overflow, an arrowhead stranded mid-line where a
figure builds one arrow out of two `\draw`s, and the edge list to
confirm the figure connects what you meant it to. The mechanical half of
the figure style guide: it checks what can be measured from the compiled
geometry and leaves taste to you ([TIKZ-STYLE.md](TIKZ-STYLE.md)). It
also says **how much of a figure it could measure at all** -- a picture
that names no node has no geometry to check, and that no longer reads
the same as a picture that passed.

It **measures and never places.** TikZ computes the layout; this reads
the result back out of a real compile and reports on it, which is why
its thresholds are not something to draw towards -- fix a finding by
changing what you asked TikZ for, not by nudging a coordinate until the
number moves. `assets/tikz/` ships a known-good starting file per layout
metaphor so that is a file rather than a blank picture.
[CLI.md](CLI.md#-chitragupta-review-figure) has the boundary in full,
including the one way a clean report can mislead.

**`review uncited` -- which sentences rest on nothing at all.** This
looks like `coverage` and is its mirror image. `coverage` asks a question
about the *corpus* side of the boundary -- were the surfaced candidates
used? `uncited` asks about the *prose* side -- which claims here are
supported by no citation? They share the word "uncited" and nothing else,
which is why one always says *candidates* and the other always says
*sentences*. It is also the only aid that reads no corpus, so it runs
before you have parsed anything.

**`review quotation` -- is each quoted span really in the source it
cites?** The only aid whose answer is binary. A `quote:` recorded in a
dossier is verbatim by contract and reaches a rendered evidence sidecar
in quotation marks, under an attribution; nothing before this checked
that the span is in the paper it names. A quotation attributed to a
source that does not contain it is the same failure class as a
fabricated citekey, and the one part of that class the citation gate
cannot see -- because the citekey *is* real.

It reports three outcomes, not two. **Found** gives you the page and how
it matched. **Absent** is the finding, and carries the page its
distinctive words concentrate on, so you can tell a fabrication from a
quotation someone edited. **Not checkable** is the third, and it is the
honest one: where the only text available is `pdftotext -layout` output,
a two-column page splices its columns together and a perfectly correct
quotation is simply not contiguous. Calling that absent would accuse a
draft of something it did not do, so the aid says it measured nothing
instead. That third outcome is also why this check, binary as it is,
stays advisory -- [ARCHITECTURE.md](ARCHITECTURE.md) works it through.

Today it will tell you there is nothing to check: no dossier in this
project carries a `quote:` yet, because A2's contract makes one a
deliberate act rather than the residue of retrieval. That is the
expected answer, not a clean bill of health, and the report says so.

**`review agenda` -- one ranked, deduplicated worklist across the eight
it reads.** Eight, not nine: `union` reads a book rather than a draft, so
its findings are about a different object than the agenda's other inputs
and it is deliberately not among them. Each of the aids above answers its
own question in isolation; this one reads what they already wrote (each
optional -- an aid that
never ran is named as absent, not treated as clean), plus the drafting
layer's prose check and the dossier's drift report, and merges them into
one ordered list a person or a future reviser skill can work down. In its
bare form it **reads, never runs, an aid** -- a stale or missing input is
named in the report's header rather than triggering a live re-run.
`--baseline` is the one exception: it re-runs the eight aids first so the
comparison it reports means something, then rebuilds and diffs against a
previous agenda. Every item carries whether it is `unattended` (safe for
a future automated pass) or merely surfaced for a human to decide;
`missing-citekey`, `prose`, and the short runs a verbatim scan finds are
the former, everything judgement-shaped -- `unsupported-claim`,
`claim-support`, `uncited-source`, `uncited-claim`, `misquoted` and
`candidate` -- is the latter.

**`review support` -- does the source actually entail this claim?** Same
underlying question as `provenance`, asked a different way. `provenance`
scores lexical overlap -- cheap, and enough to catch a citekey pointing
at the wrong paper. `support` scores with a real NLI entailment model,
which is what it takes to catch a paraphrase that subtly misstates a
paper it is genuinely citing: the citekey is real, the wording no longer
matches the source closely enough for a verbatim scan to flag, and the
source is topically related enough to pass a lexical check -- only
reading whether the source's own words actually entail the claim catches
that. The output shape differs too: `provenance` bands its findings
("no support found" / "weak" / "supported"); `support` publishes a bare
ranked score and no bands, because retrieval already selected these
passages by similarity, which weakens the discriminator in the same way
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md) records for its own tier 3,
and a band here would claim a precision this corpus does not support.

**`review union` -- did assembling the book lose a source?** The only aid
that reads a *book* rather than a draft, and the only one whose answer is
pure set arithmetic. Every unit of a book records, when
`python -m chitragupta.draft unit accept` accepts it, the citekeys its
prose stands on. `book-assembler` then composes those units into one
document, and a combining step is exactly where a source goes missing
with no error and no log ([RAG.md](RAG.md) catalogues why).

**A book is composed by reference, and that is what makes this
checkable.** `book.tex` is a skeleton: it `\input`s its units, and
citeproc resolved each unit's citations inside that unit, so the
assembly's own text states no citekey at all. Reading it for citekeys and
subtracting would report every source in a correct book as lost. What
actually goes missing here is a *unit* -- including one includes all of
its prose, so omitting one drops every source only it stood on. The
finding is located: "`02-twin-shadow` was left out, and 33 sources went
with it."

The other direction is the assembly's **own** material: a citekey in a
title page, an appendix, or a preamble file it includes. That entered
outside every acceptance record, which the gate cannot see because the
citekey is perfectly real.

Two things it deliberately will not do. A unit whose acceptance record no
longer describes its prose -- unwritten, never accepted, or edited since
-- is **named as unchecked rather than compared against**, because a
stale record's citekeys answer for text that no longer exists and would
report a drop that is not one; if it was also left out of the assembly,
the report says both, because the two want different fixes. And the
appeared direction is **withheld entirely while any unit is unchecked**:
that unit may record the citekey after all, and this aid does not guess.
Run it once the outstanding units are accepted for an answer. It also
names every non-unit file it read and every include it could not find on
disk, so a report cannot be misread as covering prose it never opened.

## 📋 What every report looks like

One output contract, mirroring the draft's own path exactly as
`content/rendered/` and `content/dossiers/` do -- so a draft, its
dossier, its renders and its review artefacts are all findable from the
draft's path:

```text
content/drafts/<topic>/survey.md
  -> content/review/<topic>/survey.provenance.md   (+ .tex/.pdf, .json)
     content/review/<topic>/survey.verbatim.md     (+ .tex/.pdf, .json)
     content/review/<topic>/survey.coverage.md     (+ .tex/.pdf, .json)
     content/review/<topic>/survey.synthesis.md    (+ .tex/.pdf, .json)
     content/review/<topic>/survey.figure.md       (+ .tex/.pdf, .json)
     content/review/<topic>/survey.uncited.md      (+ .tex/.pdf, .json)
     content/review/<topic>/survey.quotation.md    (+ .tex/.pdf, .json)
     content/review/<topic>/survey.agenda.md       (+ .tex/.pdf, .json)
     content/review/<topic>/survey.support.md      (+ .tex/.pdf, .json)
```

`union` is the one aid this example cannot show, because it reads a book
rather than a single-topic draft. The contract is the same rule applied
to the book's own path:

```text
content/drafts/<book>/book.tex
  -> content/review/<book>/book.union.md           (+ .tex/.pdf, .json)
```

`review provenance` and `review agenda` write by default. The rest
print, and write only under `--write`, because printing is the usual
use.

Two properties of every report, both deliberate:

- **It opens with a banner saying it is not a verdict.** A report found
  on disk months later is exactly the case documentation cannot reach, so
  the file carries its own caveat.
- **It carries no timestamp**, so it diffs cleanly against the next
  revision's. You can see *what* changed rather than merely that
  something did.

The `.json` beside a report is the same findings as data, for a caller
that would otherwise parse the printed form. It is a sibling of the
report, not a render of it -- `.tex`/`.pdf` are another document.

## ⏱ What the layer costs

**Zero tokens, always.** Nine of the ten aids are deterministic
Python with no model call at all. `support`'s real NLI entailment
model has no token cost either -- it scores, it does not generate --
but it is a real model load, and the only aid besides `verbatim`'s
tier 3 with a real wall-clock and memory floor. That is what makes
[LADDERS.md](LADDERS.md)'s first rung free to run to exhaustion before
anything expensive begins.

Measured on one machine across five real drafts, at `--formats md`, in
milliseconds. Read it for ratios, not absolutes --
[PERFORMANCE.md](PERFORMANCE.md#-what-a-review-pass-costs) has the full
method, the peak-memory figures and the caveats:

| words | dossier | prov | verbatim | cover | synth | figure | uncited | quote | agenda | support | all nine |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,258 | no | 180 | 447 | 303 | 90 | 87 | 88 | 89 | 575 | 33,464 | **35,323** |
| 2,448 | no | 366 | 474 | 303 | 90 | 89 | 92 | 92 | 577 | 40,832 | **42,915** |
| 5,723 | yes | 144 | 19,737 | 310 | 95 | 486 | 99 | 88 | 508 | 21,160 | **42,627** |
| 10,003 | yes | 332 | 41,019 | 314 | 96 | 818 | 109 | 88 | 1,017 | 62,292 | **106,085** |
| 18,061 | yes | 277 | 35,698 | 315 | 98 | 641 | 121 | 90 | 1,282 | 45,902 | **84,424** |

**Two aids are the cost of the layer now, not one.** `verbatim` is
90--94% of any run where its embedding tier can execute, and 447 ms
where it cannot -- a 44--86x difference that depends on whether the
dossier, the Docling sidecars, the ledger and the enrichment layer are
all present,
not on the draft. `support` has no such off switch: it always loads
the entailment model and scores every citation, so it costs
21.2--62.3 s on every draft measured, dossier or not. Where `verbatim`'s
tier 3 cannot run, `support` alone is ~95% of the total; where both run,
they split it -- 39%/59% on the 10,003-word draft. **The layer's floor
moved.** Before `support`, the cheapest and dearest run differed by a
factor of 23 (1,859 ms to 43,793 ms), entirely from whether tier 3
executed. Now they differ by a factor of 3 (35,323 ms to 106,085 ms),
because `support` puts a 21-second-plus floor under every run. Every
other aid is between 88 ms and 1.3 s.

**And it scales on cited sources -- a different count each.**
`verbatim` and `provenance` fetch each source once, so their cost
tracks *distinct citekeys*: the 18,061-word chapter cites 28 and scans
in 35.7 s, the 10,003-word chapter cites 40 and takes 41.0 s, roughly
**1.0--1.5 s per distinct citekey**
([PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md)). `support` scores every
*citation*, not every source -- two citations of the same paper are two
entailment calls, not one -- so its cost tracks citation count instead:
835--962 ms per citation on the four larger drafts, rising to 1.5 s on
the smallest (11 citekeys, 23 citations), where a largely fixed
model-load cost is spread over the fewest calls.

**Two rows are not what they look like.** `quotation` returns in ~90 ms
because no dossier on this machine carries a `quote:` line, so its input
universe is empty -- that is the cost of finding no work, not of doing
it. And ~86 ms of every row is interpreter startup, which is most of
what `synthesis`, `uncited` and `quotation` report.

## 🚫 Three limits worth knowing

- **A clean verbatim scan is not a clean bill of health.** Detection runs
  in three tiers, and the third needs the optional enrichment layer. A
  scan names any tier it could not run rather than silently reporting
  less, so read that line ([PLAGIARISM.md](PLAGIARISM.md)).
- **`coverage` is not a gap-finder.** An uncited high-scorer may be a
  source the draft should have used, or a query that was too broad. The
  report deliberately declines to decide which.
- **`support`'s score is downstream of retrieval, and retrieval is the
  weaker link.** Measured over the four real drafts of
  `digital-twins-for-software-engineers` (71 scored citations,
  `bench/RESULTS.md`'s 2026-08-27 entry): a human read of the 20
  lowest-scored candidates found the dominant failure was not the source
  failing to support the claim, but the passage-matching step handing the
  scorer the wrong passage from an otherwise-relevant paper -- single
  index terms ("light sensor", "DevOps"), bibliography entries, and
  once, a page about supply chains and COVID-era shopping habits scored
  against a claim about the Digital Twin Consortium's definition. Where
  the matched passage was actually the right one, the score separated
  cleanly (0.96-0.99 for genuine support). No structured per-claim
  labelling pass was run, so there is no crosscheck statistic to cite --
  this is a qualitative read, not a precision number. Read a low score as
  "the matched passage doesn't say this" first, and "the source doesn't
  say this" only after checking the passage yourself.

## 🕳 The distinction all three limits are instances of

Those three read as separate caveats. They are the same one, and it is
worth stating once as a rule the next aid should be built to rather than
re-derive:

> **A finding can be absent for three reasons -- there was nothing to
> find, the check could not run, or the case was out of scope -- and an
> aid that collapses them is lying by omission.**

"Nothing found" and "not checked" look identical in any report that
prints only findings, and the second is the one a reader would act on.
This is why a verbatim scan names the tier it skipped, why `coverage`
declines to say which kind of gap it found, and why `support` reports a
score beside the passage it scored rather than alone.

**Where an aid publishes an aggregate, the same rule binds harder:
something not measured is never counted as a zero.** A zero is a
finding -- it says the check ran and found nothing. Averaging an
unmeasured item in as zero produces a number that looks like evidence of
quality and is partly evidence of a missing dependency. An aggregate
that cannot say what share of its inputs were actually assessable should
say so beside itself.

The idea of separating *rated* from *missing* from *not applicable*, and
of refusing to encode missing as zero, is credited to
[K-Dense-AI/scientific-agent-skills](INSPIRATION.md). It fits this
project's existing posture rather than changing it:
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s **R3** already forbids a
continuous score from being the thing optimised, and this is the
reporting-side companion -- if a number is published at all, publish
what it could not see next to it.

## ➡ Where to go next

- Reading a verbatim report: [PLAGIARISM.md](PLAGIARISM.md); how the
  detector works: [PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md).
- Reading a provenance report:
  [CITATION-PROVENANCE.md](CITATION-PROVENANCE.md).
- Fixing what a verbatim scan found: the `agenda-reviser` skill
  ([GENRE.md](GENRE.md#-working-the-agenda-agenda-reviser)).
- The commands and their flags: [CLI.md](CLI.md).
- What the layer costs, in full:
  [PERFORMANCE.md](PERFORMANCE.md#-what-a-review-pass-costs).
