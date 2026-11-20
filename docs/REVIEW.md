# 🔍 The review layer

Status: **reference.**

**Written for** you, after a draft is finished: someone deciding
whether it is good enough to hand over. **Assumed:**
[FEATURES.md](FEATURES.md) for where this sits among the pipeline's
features. **Not covered here:** why a review aid may never become a gate,
which is an architecture question and lives in
[ARCHITECTURE.md](ARCHITECTURE.md#-layer-4-the-review-layer); and how the
verbatim detector works internally, which is
[PLAGIARISM.md](PLAGIARISM.md#-how-the-tiers-were-chosen).

[DOSSIER.md](DOSSIER.md) documents working state a *model* reloads to
keep drafting; this page documents evidence *you* weigh before deciding
a draft is done. The two mirror the same draft path and are otherwise
unalike:

| | The dossier | A review report |
| --- | --- | --- |
| Read by | usually an LLM, resuming a run | you, once, near the end |
| Written | continuously, while drafting | on demand, after a draft exists |
| If nobody reads it | the next revision pays twice | nothing happened; it was advisory |
| Lives in | `content/dossiers/` | `content/review/` |

## 🔑 The one thing to understand first

**None of these is a gate, and none may become one.** Each produces
evidence for a human judgement, never a verdict, and each exits 0 whether
it finds something or not. The agenda and `agenda-reviser` read
reports to build a worklist, but no draft is blocked by what one says.

[SOUL.md](../SOUL.md) commits to this, and
[ARCHITECTURE.md](ARCHITECTURE.md#-layer-4-the-review-layer) argues why
decidability is not what earns a check the right to block. So **an aid
that finds nothing is not a clean bill of health, and an aid that finds
something is not an accusation.** They take no lock, so any of them runs
while `chitragupta corpus sync` is rebuilding the corpus.

## 🧩 The eleven aids

**`review provenance`: does the cited paper say this?** The gate answers
only "is this citekey real?", so a claim that drifted from its source
passes it. This report quotes, for each citation, the supporting passage
in the cited source and where it sits, making the check a two-minute
read.
[CITATION-PROVENANCE.md](CITATION-PROVENANCE.md) has the scoring.

**`review verbatim`: how much wording came along with the ideas.**
`overlap` and `locate` compare the draft against *one* cited source and
give the page a phrase is on; `scan` compares it against **any** parsed
source, so it finds reuse from a paper the paragraph never cites, and in
connective prose that cites nothing. `recheck` compares a fresh scan
with a recorded one, so a repair is judged by what it resolved.
Detection runs in three tiers (exact n-gram, skip-gram, embedding), and
the aid names any tier it could not run.

**`review coverage`: did the draft use what retrieval found?** Given the
queries, it reports which surfaced candidates were cited. An uncited
high-scorer is a source the draft skipped or a query that was too broad,
and the report deliberately does not decide which. It also shows
citekeys cited but surfaced by none of your queries, normally *not* a
gap (the skill ran other queries).

**`review synthesis`: how many sources is each unit standing on?**
Prose fusing two or more sources cannot be a transcription of any one,
which is the guarantee the writing standards ask for; this makes it
observable. The *unit* is the paragraph for a survey, thesis chapter and
deep-research report, the section for a textbook chapter, and the whole
document for a tutorial (whose body carries no citations by design). The
header names the unit used and where it came from.

**`review figure`: what a TikZ figure's own geometry says.** It reports
overlapping nodes, content past the frame, node text too long to fit, an
arrowhead stranded mid-line where one arrow is built from two `\draw`s,
the edge list, and a figure file that loads a TikZ library by hand
(which renders alone but multiplies node spacing once a second figure
joins it). It checks what the compiled geometry can measure and leaves
taste to you ([TIKZ-STYLE.md](TIKZ-STYLE.md)), and says **how much of a
figure it could measure at all**: a picture naming no node is reported
as unmeasured, not as passed.

It runs over a whole draft and reports 7 of the figure rule ids;
`chitragupta figure check` checks one figure file against all 36 rules
and measures every drawn node, not only named ones. Run `figure check`
on each figure as you draw it
([figure-checks/README.md](figure-checks/README.md)).

It **measures and never places.** Its thresholds are not something to
draw towards: fix a finding by changing what you asked TikZ for, not by
nudging a coordinate. `assets/tikz/` ships a known-good starting file
per layout metaphor. [CLI.md](CLI.md#-chitragupta-review-figure) has the
boundary in full, including the one way a clean report can mislead.

**`review uncited`: which sentences rest on nothing at all.** The mirror
of `coverage`: that asks whether surfaced *candidates* were used; this
asks which *sentences* are supported by no citation. Like `synthesis`
and `figure`, it reads no corpus, so it runs before you have parsed
anything.

**`review quotation`: is each quoted span in the source it cites?**
The only aid whose answer is binary. A dossier's `quote:` is verbatim by
contract and reaches a rendered evidence sidecar in quotation marks. A
quotation attributed to a source that does not contain it is the same
failure class as a fabricated citekey, and one the gate cannot see,
because the citekey *is* real.

It reports three outcomes. **Found** gives the page and how it matched.
**Absent** is the finding, with the page its distinctive words
concentrate on, so you can tell a fabrication from an edited quotation.
**Not checkable** is the honest third: where the only text is
`pdftotext -layout` output, a two-column page splices its columns and a
correct quotation is not contiguous, so the aid says it measured
nothing. That outcome is why this check stays advisory
([ARCHITECTURE.md](ARCHITECTURE.md)).

It often has nothing to check, because `quote:` is optional by design.
Its `universe` is
`no-dossier` for a draft with no dossier, `no-quotes` for a dossier
that publishes no quote the draft cites, and `checked` otherwise. Only
`checked` means a quote was looked at.

**`review agenda`: one ranked, deduplicated worklist across the eight
it reads.** It reads eight of the other ten aids (not `union`, which
reads a book, nor `digest`, whose classes mean nothing outside a
digest), plus the prose check, the dossier's drift report and its
recorded-but-uncited citekeys, and merges them into one ordered list a
person or the `agenda-reviser` skill can work down. An aid that never
ran is named as absent, not treated as clean. In its bare form it
**reads, never runs, an aid**: a stale or missing input is named in the
header. `--baseline` is the exception: it re-runs the eight aids, then
rebuilds and diffs against a previous agenda. Every item is either
`unattended` (safe for an automated pass) or surfaced for a person, and
some surfaced items can be accepted with `--accept <id>`.
[AGENDA.md](AGENDA.md) walks one report and owns the class table.

**`review support`: does the source entail this claim?** `provenance`
scores lexical overlap, enough to catch a citekey pointing at the wrong
paper. `support` uses an NLI entailment model, which catches a
paraphrase that subtly misstates a related paper: too reworded for a
verbatim scan, too on-topic for a lexical check. `provenance` bands its
findings ("no support found" / "weak" / "supported"); `support`
publishes a bare ranked score with no bands, because retrieval already
selected these passages by similarity, weakening the discriminator as
[PLAGIARISM.md](PLAGIARISM.md#-how-the-tiers-were-chosen) records for
its tier 3, so a band would claim a precision this corpus does not
support.

**`review union`: did assembling the book lose a source?** The only aid
that reads a *book*, and the only one whose answer is pure set
arithmetic. `python -m chitragupta.draft unit accept` records the
citekeys each unit's prose stands on; `book-assembler` composes the
units, and a combining step is where a source goes missing with no error
([RAG.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/RAG.md)
catalogues why). `book.tex` `\input`s its units, whose citations stay
`\citep{key}` for one `bibtexu` pass, so what goes missing is a *unit*,
with every source only it stood on. The finding is located:
"`02-twin-shadow` was left out, and 33 sources went with it."

The other direction is the assembly's **own** material: a citekey in a
title page, an appendix or an included preamble file entered outside
every acceptance record, which the gate cannot see because the citekey
is real.

Two things it deliberately will not do. A unit whose acceptance record
no longer describes its prose (unwritten, never accepted, or edited
since) is **named as unchecked rather than compared against**, because a
stale record would report a drop that is not one; if it was also left
out, the report says both, since the fixes differ. And the appeared
direction is **withheld entirely while any unit is unchecked**, because
that unit may record the citekey after all. It also names every
non-unit file it read and every include it could not find, so a report
cannot be misread as covering prose it never opened.

**`review digest`: how much of a verbatim digest is not the sources'
own words?** A digest ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)) is
private study text, a survey whose body is copied from the corpus, each
copied run closed by a citation. The aid finds each run in its cited
source with the quotation matcher, leads with the unsupported fraction
(words of sentences that are neither verified source text nor the
drafter's own words a cited source supports, over all words), and lists
each such sentence as a `[surfaced]` item in five classes:
`unsupported-text`, `copy-mismatch`, `dangling-reference`,
`repeated-text` and `unquoted-text`. `--baseline` compares with an
earlier run. It is the digest's own worklist; the agenda never reads
it.

## 📋 What every report looks like

One output contract mirrors the draft's path, as `content/rendered/` and
`content/dossiers/` do:

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
     content/review/<topic>/survey.digest.md       (+ .tex/.pdf, .json)
```

`union` reads a book, so its report mirrors the book's path:

```text
content/rendered/<book>/book.tex
  -> content/review/<book>/book.union.md           (+ .tex/.pdf, .json)
```

`review provenance`, `review agenda` and `review digest` write by
default; the rest print, and write only under `--write`.

`docs/examples/sample-project/content/review/dt-overview/` holds every
draft-reading aid's `.md` and `.json` for four real drafts (no `figure`
or `digest`: the samples have no TikZ figure and no digest). Compare
[`trust-chapter.agenda.md`](examples/sample-project/content/review/dt-overview/trust-chapter.agenda.md),
a draft that mostly passes, with
[`survey.agenda.md`](examples/sample-project/content/review/dt-overview/survey.agenda.md),
whose verbatim runs give a reviser items it may act on unasked.

Every report **opens with a banner saying it is not a verdict**, because
a report found on disk months later is beyond documentation's reach, and
**carries no timestamp**, so it diffs cleanly against the next
revision's. The `.json` beside it is the same findings as data, a
sibling of the report rather than a render; `.tex`/`.pdf` are another
document.

## ⏱ What the layer costs

The layer costs zero tokens, always. Ten of the eleven aids are
deterministic Python with no model call. `support`'s NLI model scores
rather than generates, so it has no token cost either, but it is the
only aid besides `verbatim`'s tier 3 with a real wall-clock and memory
floor. That is what makes [LADDERS.md](LADDERS.md)'s first rung free to
run to exhaustion before anything expensive begins.

Across five real drafts of 1,258 to 18,061 words, a full pass took 35 to
106 s, and two aids made up nearly all of it:

- **`verbatim`** is 447 ms where its embedding tier cannot run and
  19.7-41.0 s where it can, depending on whether the dossier, Docling
  sidecars, ledger and enrichment layer are present, not on the draft.
  It and `provenance` fetch each source once, so they cost roughly
  **1.0-1.5 s per distinct citekey**.
- **`support`** always loads the entailment model and scores every
  *citation* (two citations of one paper are two calls), costing
  21.2-62.3 s on every draft measured. That cost tracks the number of
  quotable passages per cited source, so it moves with how finely the
  corpus was parsed. `[enrich].support_premise_topk` caps the premises
  per citation and is uncapped by default ([CONFIG.md](CONFIG.md)).

Every other aid took between 88 ms and 1.3 s, most of the smallest being
interpreter startup. [PERFORMANCE.md](PERFORMANCE.md#-what-a-review-pass-costs)
has the per-aid table, the method and the caveats.

## 🚫 Three limits worth knowing

- **A clean verbatim scan is not a clean bill of health.** Detection runs
  in three tiers, and the third needs the optional enrichment layer. A
  scan names any tier it could not run instead of silently reporting
  less, so read that line ([PLAGIARISM.md](PLAGIARISM.md)).
- **`coverage` is not a gap-finder.** An uncited high-scorer may be a
  source the draft should have used, or a query that was too broad. The
  report deliberately declines to decide which.
- **`support`'s score is downstream of retrieval, and retrieval is the
  weaker link.** A human read of the 20 lowest-scored of 71 citations
  across four real drafts found the dominant failure was the
  passage-matching step handing the scorer the wrong passage from a
  relevant paper (a single index term, a bibliography entry), not the
  source failing to support the claim. Where the passage was right, the
  score separated cleanly (0.96-0.99 for genuine support). This is a
  qualitative read, not a precision number. Read a low score as "the
  matched passage doesn't say this" first, and "the source doesn't say
  this" only after checking the passage yourself.

## 🕳 The distinction all three limits are instances of

The three are one caveat, stated once as a rule the next aid should be
built to:

> **A finding can be absent for three reasons (there was nothing to
> find, the check could not run, or the case was out of scope), and an
> aid that collapses them is lying by omission.**

"Nothing found" and "not checked" look identical in any report that
prints only findings, and the second is the one a reader would act on.
This is why a verbatim scan names the tier it skipped, why `coverage`
declines to say which kind of gap it found, and why `support` reports a
score beside the passage it scored rather than alone.

**Where an aid publishes an aggregate, the same rule binds harder:
something not measured is never counted as a zero.** A zero says the
check ran and found nothing; averaging in an unmeasured item as zero
yields a number that is partly evidence of a missing dependency. An
aggregate that cannot say what share of its inputs were assessable
should say so beside itself.

Separating *rated* from *missing* from *not applicable* is credited to
[K-Dense-AI/scientific-agent-skills](https://github.com/prasadtalasila/chitragupta/blob/main/docs/INSPIRATION.md).
It is the reporting-side companion to
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s **R3**, which forbids a
continuous score from being the thing optimised: if a number is
published, publish what it could not see next to it.

## ➡ Where to go next

- Reading a verbatim report: [PLAGIARISM.md](PLAGIARISM.md); how the
  detector works: [PLAGIARISM.md](PLAGIARISM.md#-how-the-tiers-were-chosen).
- Reading a provenance report:
  [CITATION-PROVENANCE.md](CITATION-PROVENANCE.md).
- Fixing what a verbatim scan found: the `agenda-reviser` skill
  ([GENRE.md](GENRE.md#-working-the-agenda-agenda-reviser)).
- The commands and their flags: [CLI.md](CLI.md).
- What the layer costs, in full:
  [PERFORMANCE.md](PERFORMANCE.md#-what-a-review-pass-costs).
