# Verbatim scan: content/drafts/dt-overview/staleness-tutorial.md

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/staleness-tutorial.md`
- Command: `python -m chitragupta.review verbatim scan content/drafts/dt-overview/staleness-tutorial.md --min-run 8 --gap 1 --write`
- chitragupta 6.60.2
- Allowlist: none configured (`content/verbatim_allowlist.toml` not found)

## How to read this

Every run of at least `--min-run` words this draft shares with **any**
parsed source in the corpus, cited or not. Sharing wording is not by
itself misconduct -- a defined term, a standard's name and a correctly
quoted sentence all show up here -- so each finding is a place to look,
not a charge.

Two flags narrow the reading:

- **UNCITED SOURCE** -- the paragraph the run sits in does not cite the
  source it matched. That is the finding `overlap` structurally cannot
  make, and the one most worth reading first.
- **quoted** -- the run touches quote delimiters, so it is most likely
  a deliberate quotation. A run is usually wider than the quotation
  inside it -- it can open in the draft's own framing prose -- so this
  reads as overlap, not containment.

Each finding names its `tier`: **exact** is a verbatim run; **skip-gram**
is a tolerant stemmed-subsequence match that also catches a passage
with a handful of words substituted. A skip-gram finding's word count
is `matched words / span`: how many words the tier actually matched,
out of the raw width of text those matches span -- the two can differ
a lot, since a skip-gram window can stretch across stopwords and
opposite-family words that were not themselves matched.

**embedding** is the third tier: a sentence-level alignment between a
section of this draft and the sources its dossier records that section
as written from. It matches meaning rather than wording, so it is the
only tier that can see a genuine restatement -- and the only one whose
findings are not reproducible from the draft and the corpus alone,
since the vectors change with `[enrich].embedding_model`. Its `score`
is that alignment's strength, not a probability and not comparable to
anything the other two report; a passage a deterministic tier already
flagged is left to that tier rather than reported twice.

Findings below are grouped most-damning-first: long runs, then short
ones, then quoted runs -- but a quoted run only drops into the last
group when it also cites the source it matched. A quoted run from an
uncited source is still grouped by length (on matched words, not raw
span), not buried under `quoted`.

The allowlist bullet above names a per-host, gitignored file
(`content/verbatim_allowlist.toml`, see docs/PLAGIARISM.md) of
boilerplate this host's owner has decided never to flag -- a run is
only dropped when what's left after discounting the allowlisted text
would no longer clear `--min-run` on its own, so a real lift that
merely contains a defined term still shows up below.

**A clean run is not a clean bill of health.** This draft has been
checked against all three tiers, but they do not cover the same
ground: the two deterministic ones see wording, and the embedding
tier sees meaning only within each section's own recorded sources.
Reuse from a source a section's dossier does not record is outside
what any of the three can find by restatement alone. See
docs/PLAGIARISM.md.

## Findings

No verbatim run of 8 words or more was found anywhere in the draft.
