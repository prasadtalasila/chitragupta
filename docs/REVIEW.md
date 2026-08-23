# 🔍 The review layer

Status: **reference.** Written 2026-08-22, describing the six aids as
they stand.

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

## 🧩 The six aids

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
to fit, page-width overflow, and the edge list to confirm the figure
connects what you meant it to. The mechanical half of the figure style
guide: it checks what can be measured from the compiled geometry and
leaves taste to you ([TIKZ-STYLE.md](TIKZ-STYLE.md)).

**`review uncited` -- which sentences rest on nothing at all.** This
looks like `coverage` and is its mirror image. `coverage` asks a question
about the *corpus* side of the boundary -- were the surfaced candidates
used? `uncited` asks about the *prose* side -- which claims here are
supported by no citation? They share the word "uncited" and nothing else,
which is why one always says *candidates* and the other always says
*sentences*. It is also the only aid that reads no corpus, so it runs
before you have parsed anything.

## 📋 What every report looks like

One output contract, mirroring the draft's own path exactly as
`content/rendered/` and `content/dossiers/` do -- so a draft, its
dossier, its renders and its review artefacts are all findable from the
draft's path:

```text
content/drafts/<topic>/survey.md
  -> content/review/<topic>/survey.provenance.md   (+ .tex/.pdf)
     content/review/<topic>/survey.verbatim.md     (+ .tex/.pdf, .json)
     content/review/<topic>/survey.coverage.md     (+ .tex/.pdf)
     content/review/<topic>/survey.synthesis.md    (+ .tex/.pdf, .json)
     content/review/<topic>/survey.figure.md       (+ .tex/.pdf, .json)
     content/review/<topic>/survey.uncited.md      (+ .tex/.pdf, .json)
```

`review provenance` writes by default. The rest print, and write only
under `--write`, because printing is the usual use.

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

## 🚫 Two limits worth knowing

- **A clean verbatim scan is not a clean bill of health.** Detection runs
  in three tiers, and the third needs the optional enrichment layer. A
  scan names any tier it could not run rather than silently reporting
  less, so read that line ([PLAGIARISM.md](PLAGIARISM.md)).
- **`coverage` is not a gap-finder.** An uncited high-scorer may be a
  source the draft should have used, or a query that was too broad. The
  report deliberately declines to decide which.

## ➡ Where to go next

- Reading a verbatim report: [PLAGIARISM.md](PLAGIARISM.md); how the
  detector works: [PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md).
- Reading a provenance report:
  [CITATION-PROVENANCE.md](CITATION-PROVENANCE.md).
- Fixing what a verbatim scan found: the `overlap-reviser` skill
  ([GENRE.md](GENRE.md#-repairing-overlap-overlap-reviser)).
- The commands and their flags: [CLI.md](CLI.md).
