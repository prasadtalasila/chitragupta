# Claim support: content/drafts/dt-overview/staleness-chapter.md

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/staleness-chapter.md`
- Command: `python -m chitragupta.review support content/drafts/dt-overview/staleness-chapter.md --write`
- chitragupta 6.61.0

## How to read this

Each entry pairs a citing sentence with the passage of its cited
source an entailment model scored as the best match, ranked
**worst first**. There are no bands here, unlike `provenance` --
retrieval already selected these passages by similarity, so the
model is discriminating inside a set chosen for being similar,
and a threshold would claim a precision this corpus does not
support (see docs/PLAGIARISM-DESIGN.md's tier 3 for the same
argument made about wording overlap instead of entailment).

**A low score is not a fact-check, and a high score is not proof.**
A correct paraphrase can score low if it drifts from the source's
own wording style; a claim that happens to echo its source's
vocabulary can score high while misrepresenting it. The score is
where to spend attention, not a verdict.

A citekey whose source has no passage with readable text (a
page-level scan, or nothing parsed at all) cannot be scored and
is noted rather than given a score of zero standing for "checked
and found wanting".

## Summary

**0** citations scored, **2** citekeys could not be scored.

### Not scored

- `sample_dt_factory_2022`: no parsed text with page breaks and no readable PDF
- `sample_dt_sync_2023`: no parsed text with page breaks and no readable PDF

## Findings

- **line 18** `[@sample_dt_factory_2022]` (not scored -- no parsed text with page breaks and no readable PDF) (`5ad855819b5f`)
  > Field studies report that the costly failures are precisely the quiet ones, where the representation and the asset part company without anyone being told, and that making the twin announce its own uncertainty measurably improves how far operators trust it.
- **line 20** `[@sample_dt_sync_2023]` (not scored -- no parsed text with page breaks and no readable PDF) (`ee2aa913e518`)
  > Field studies report that the costly failures are precisely the quiet ones, where the representation and the asset part company without anyone being told, and that making the twin announce its own uncertainty measurably improves how far operators trust it.
- **line 83** `[@sample_dt_sync_2023]` (not scored -- no parsed text with page breaks and no readable PDF) (`2c11f1c3447b`)
  > Staleness is the age of a value at the moment it is used; a budget turns a decision's tolerance into a test; and a twin that serves marked values converts silent failure into visible degradation -- the property the operational literature identifies as what trust is actually built on.
- **line 83** `[@sample_dt_factory_2022]` (not scored -- no parsed text with page breaks and no readable PDF) (`94314cccb028`)
  > Staleness is the age of a value at the moment it is used; a budget turns a decision's tolerance into a test; and a twin that serves marked values converts silent failure into visible degradation -- the property the operational literature identifies as what trust is actually built on.