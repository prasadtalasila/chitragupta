# Claim support: content/drafts/dt-overview/staleness-tutorial.md

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/staleness-tutorial.md`
- Command: `python -m chitragupta.review support content/drafts/dt-overview/staleness-tutorial.md --write`
- chitragupta 6.59.1

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

**0** citations scored, **3** citekeys could not be scored.

### Not scored

- `sample_dt_factory_2022`: the source's passages carry no readable text to score against (page-level only)
- `sample_dt_overview_2024`: the source's passages carry no readable text to score against (page-level only)
- `sample_dt_sync_2023`: the source's passages carry no readable text to score against (page-level only)

## Findings

- **line 107** `[@sample_dt_sync_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`a2f8f98703b5`)
  > Explicit staleness marking roughly halved operator mistrust incidents in a comparative study of synchronisation strategies, and the factory case study shows what silent staleness costs when it is not marked: both of its recorded failures were divergences nobody was told about.
- **line 109** `[@sample_dt_factory_2022]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`09fb4da73bdb`)
  > Explicit staleness marking roughly halved operator mistrust incidents in a comparative study of synchronisation strategies, and the factory case study shows what silent staleness costs when it is not marked: both of its recorded failures were divergences nobody was told about.
- **line 111** `[@sample_dt_overview_2024]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`0fab0f944cc3`)
  > For the vocabulary of what you just built -- and why it is a shadow, not yet a twin -- see.