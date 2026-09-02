# Claim support: content/drafts/dt-overview/trust-chapter.tex

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/trust-chapter.tex`
- Command: `python -m chitragupta.review support content/drafts/dt-overview/trust-chapter.tex --write`
- chitragupta 6.60.3

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

**0** citations scored, **4** citekeys could not be scored.

### Not scored

- `sample_dt_factory_2022`: no parsed text with page breaks and no readable PDF
- `sample_dt_overview_2024`: no parsed text with page breaks and no readable PDF
- `sample_dt_sync_2023`: no parsed text with page breaks and no readable PDF
- `sample_ml_anomaly_2023`: no parsed text with page breaks and no readable PDF

## Findings

- **line 26** `[@sample_dt_sync_2023]` (not scored -- no parsed text with page breaks and no readable PDF) (`08929896014b`)
  > In comparative trials, explicit staleness marking -- returning every value with its age, so a twin that has stopped tracking reality says so -- roughly halved operator mistrust incidents without any change to the underlying model.
- **line 31** `[@sample_dt_factory_2022]` (not scored -- no parsed text with page breaks and no readable PDF) (`5b6f8760160e`)
  > The packaging line twin of gained scheduling authority station by station, and each extension was argued from a published override log -- supervisors observed agreeing with the twin in over ninety-five percent of cases -- not from validation statistics.
- **line 38** `[@sample_dt_factory_2022]` (not scored -- no parsed text with page breaks and no readable PDF) (`5b6f8760160e`)
  > The packaging line twin of gained scheduling authority station by station, and each extension was argued from a published override log -- supervisors observed agreeing with the twin in over ninety-five percent of cases -- not from validation statistics.
- **line 45** `[@sample_ml_anomaly_2023]` (not scored -- no parsed text with page breaks and no readable PDF) (`b615334a17de`)
  > Comparing anomaly detectors over twin state streams, the learned model with the best mean precision was also the one whose failure was invisible: it absorbed a slow drift into its own retraining baseline and missed it entirely, while an incorruptible statistical baseline flagged it.
- **line 55** `[@sample_dt_overview_2024]` (not scored -- no parsed text with page breaks and no readable PDF) (`4324aaca7f52`)
  > The vocabulary of sharpens the claim: what distinguishes a twin from a shadow is a closed actuation loop, and closing that loop is precisely the step organisations refuse until the audit trail exists.