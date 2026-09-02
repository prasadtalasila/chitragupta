# Claim support: content/drafts/dt-overview/survey.md

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/survey.md`
- Command: `python -m chitragupta.review support content/drafts/dt-overview/survey.md --write`
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

**0** citations scored, **5** citekeys could not be scored.

### Not scored

- `sample_dt_factory_2022`: the source's passages carry no readable text to score against (page-level only)
- `sample_dt_overview_2024`: the source's passages carry no readable text to score against (page-level only)
- `sample_dt_sync_2023`: the source's passages carry no readable text to score against (page-level only)
- `sample_ml_anomaly_2023`: the source's passages carry no readable text to score against (page-level only)
- `sample_std_interop_2021`: the source's passages carry no readable text to score against (page-level only)

## Findings

- **line 10** `[@sample_dt_overview_2024]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`442ec3a62d99`)
  > A digital model exchanges data with its physical counterpart only through manual steps; a digital shadow adds an automatic flow in one direction; a digital twin closes the loop, with data flowing automatically both ways.
- **line 14** `[@sample_dt_overview_2024]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`442ec3a62d99`)
  > A digital model exchanges data with its physical counterpart only through manual steps; a digital shadow adds an automatic flow in one direction; a digital twin closes the loop, with data flowing automatically both ways.
- **line 26** `[@sample_dt_sync_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`7ecdeb125fc6`)
  > Comparing periodic pull, threshold push and event-driven flows across nine simulated production cells, event-driven synchronisation reduced transmitted volume by 71 percent against one-second polling while holding worst-case staleness under two seconds.
- **line 29** `[@sample_dt_sync_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`7ecdeb125fc6`)
  > Comparing periodic pull, threshold push and event-driven flows across nine simulated production cells, event-driven synchronisation reduced transmitted volume by 71 percent against one-second polling while holding worst-case staleness under two seconds.
- **line 34** `[@sample_dt_sync_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`d4b32047f5f5`)
  > Marking staleness explicitly -- a twin that knows it is stale must say so on every read -- roughly halved operator mistrust incidents in the same trials.
- **line 39** `[@sample_dt_factory_2022]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`ec7a70a7c9ee`)
  > The eighteen-month factory case study reaches the same conclusion from the organisational side: its twin earned scheduling authority station by station, and the deciding argument was never abstract model accuracy but a published override log showing supervisors agreeing with the twin in over ninety-five percent of cases.
- **line 42** `[@sample_dt_factory_2022]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`ec7a70a7c9ee`)
  > The eighteen-month factory case study reaches the same conclusion from the organisational side: its twin earned scheduling authority station by station, and the deciding argument was never abstract model accuracy but a published override log showing supervisors agreeing with the twin in over ninety-five percent of cases.
- **line 52** `[@sample_ml_anomaly_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`e9b8d6700614`)
  > For anomaly detection, a layered configuration -- a rolling z-score everywhere, with a learned detector added only where the false-positive cost justifies its upkeep -- matched an autoencoder's precision on point faults while remaining immune to the baseline corruption that made the autoencoder miss the slowest drift entirely.
- **line 54** `[@sample_ml_anomaly_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`e9b8d6700614`)
  > For anomaly detection, a layered configuration -- a rolling z-score everywhere, with a learned detector added only where the false-positive cost justifies its upkeep -- matched an autoencoder's precision on point faults while remaining immune to the baseline corruption that made the autoencoder miss the slowest drift entirely.
- **line 61** `[@sample_std_interop_2021]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`63128f93cc87`)
  > Interoperability requires agreement at three layers -- transport, syntax and semantics -- and only the first two can be bought as mature standards.
- **line 65** `[@sample_std_interop_2021]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`63128f93cc87`)
  > Interoperability requires agreement at three layers -- transport, syntax and semantics -- and only the first two can be bought as mature standards.
- **line 68** `[@sample_std_interop_2021]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`63128f93cc87`)
  > Interoperability requires agreement at three layers -- transport, syntax and semantics -- and only the first two can be bought as mature standards.
- **line 76** `[@sample_dt_overview_2024]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`c56f48901ff3`)
  > Fidelity is argued to be purchased "decision by decision", yet no paper offers a costing method for that purchase.
- **line 78** `[@sample_dt_factory_2022]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`71b53d3718e0`)
  > And the organisational trust mechanisms of the factory study have no counterpart for the anomaly detectors of, whose false positives spend the same trust budget.
- **line 79** `[@sample_ml_anomaly_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`3b359a492dc9`)
  > And the organisational trust mechanisms of the factory study have no counterpart for the anomaly detectors of, whose false positives spend the same trust budget.
- **line 86** `[@sample_dt_overview_2024]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`39900b2ed3bc`)
  > Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.
- **line 86** `[@sample_dt_sync_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`3f3e55c69239`)
  > Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.
- **line 87** `[@sample_dt_factory_2022]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`390cf7cb63cb`)
  > Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.
- **line 88** `[@sample_ml_anomaly_2023]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`5bfdc2ab8fe8`)
  > Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.
- **line 89** `[@sample_std_interop_2021]` (not scored -- the source's passages carry no readable text to score against (page-level only)) (`37c58159f5ce`)
  > Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.