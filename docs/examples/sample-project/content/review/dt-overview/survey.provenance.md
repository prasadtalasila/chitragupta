# Citation provenance: content/drafts/dt-overview/survey.md

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/survey.md`
- Command: `python -m chitragupta.review provenance content/drafts/dt-overview/survey.md`
- chitragupta 6.60.2

## How to read this

Each entry pairs a citing sentence from the draft with the passage of
the cited paper that best matches it, scored by how many of the
sentence's distinctive words appear there. Entries are ordered
**worst match first**, so the ones worth checking come first.

This is a **review aid, not a gate**. A low score means *go look* --
it does not mean the citation is wrong. A claim correctly paraphrased
into different vocabulary scores low, and a claim that happens to
share wording with its source scores high while misrepresenting it.
The report tells you where to spend attention; it does not adjudicate.

Bands: **no support found** below 20%, **weak** below 50%, **supported** at or above 50%.

**Scores are comparable within a source kind, not across them.** A
quoted paragraph is a much smaller haystack than a whole page, so
the same quality of support scores lower against a paragraph than
against a page. On one real draft the identical citations banded as
8 weak / 5 supported page-level and 12 weak / 1 supported once
paragraphs were available -- the matches did not get worse, the
denominator got smaller. Compare entries with each other, and treat
the band as a rough reading order rather than a measurement.

## Summary

- 3 no support found
- 5 weak
- 12 supported

## Findings

### No support found

#### Line 88 -- `[@sample_ml_anomaly_2023]` (13% match)

> Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 89 -- `[@sample_std_interop_2021]` (13% match)

> Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.

Best match is on **page 2** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 87 -- `[@sample_dt_factory_2022]` (19% match)

> Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

### Weak

#### Line 78 -- `[@sample_dt_factory_2022]` (21% match)

> And the organisational trust mechanisms of the factory study have no counterpart for the anomaly detectors of, whose false positives spend the same trust budget.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 86 -- `[@sample_dt_overview_2024]` (23% match)

> Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 79 -- `[@sample_ml_anomaly_2023]` (29% match)

> And the organisational trust mechanisms of the factory study have no counterpart for the anomaly detectors of, whose false positives spend the same trust budget.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 76 -- `[@sample_dt_overview_2024]` (30% match)

> Fidelity is argued to be purchased "decision by decision", yet no paper offers a costing method for that purchase.

Best match is on **page 2** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 86 -- `[@sample_dt_sync_2023]` (32% match)

> Across the sample corpus, the recurring finding is that twins succeed on honesty rather than sophistication: strict vocabulary, marked staleness, published override logs, incorruptible baselines and owned semantics are all instances of one design value -- never let the representation be confidently wrong.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

### Supported

#### Line 34 -- `[@sample_dt_sync_2023]` (59% match)

> Marking staleness explicitly -- a twin that knows it is stale must say so on every read -- roughly halved operator mistrust incidents in the same trials.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 52 -- `[@sample_ml_anomaly_2023]` (66% match)

> For anomaly detection, a layered configuration -- a rolling z-score everywhere, with a learned detector added only where the false-positive cost justifies its upkeep -- matched an autoencoder's precision on point faults while remaining immune to the baseline corruption that made the autoencoder miss the slowest drift entirely.

Best match is on **page 2** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 54 -- `[@sample_ml_anomaly_2023]` (66% match)

> For anomaly detection, a layered configuration -- a rolling z-score everywhere, with a learned detector added only where the false-positive cost justifies its upkeep -- matched an autoencoder's precision on point faults while remaining immune to the baseline corruption that made the autoencoder miss the slowest drift entirely.

Best match is on **page 2** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 39 -- `[@sample_dt_factory_2022]` (78% match)

> The eighteen-month factory case study reaches the same conclusion from the organisational side: its twin earned scheduling authority station by station, and the deciding argument was never abstract model accuracy but a published override log showing supervisors agreeing with the twin in over ninety-five percent of cases.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 42 -- `[@sample_dt_factory_2022]` (78% match)

> The eighteen-month factory case study reaches the same conclusion from the organisational side: its twin earned scheduling authority station by station, and the deciding argument was never abstract model accuracy but a published override log showing supervisors agreeing with the twin in over ninety-five percent of cases.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 26 -- `[@sample_dt_sync_2023]` (90% match)

> Comparing periodic pull, threshold push and event-driven flows across nine simulated production cells, event-driven synchronisation reduced transmitted volume by 71 percent against one-second polling while holding worst-case staleness under two seconds.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 29 -- `[@sample_dt_sync_2023]` (90% match)

> Comparing periodic pull, threshold push and event-driven flows across nine simulated production cells, event-driven synchronisation reduced transmitted volume by 71 percent against one-second polling while holding worst-case staleness under two seconds.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 10 -- `[@sample_dt_overview_2024]` (91% match)

> A digital model exchanges data with its physical counterpart only through manual steps; a digital shadow adds an automatic flow in one direction; a digital twin closes the loop, with data flowing automatically both ways.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 14 -- `[@sample_dt_overview_2024]` (91% match)

> A digital model exchanges data with its physical counterpart only through manual steps; a digital shadow adds an automatic flow in one direction; a digital twin closes the loop, with data flowing automatically both ways.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 61 -- `[@sample_std_interop_2021]` (93% match)

> Interoperability requires agreement at three layers -- transport, syntax and semantics -- and only the first two can be bought as mature standards.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 65 -- `[@sample_std_interop_2021]` (93% match)

> Interoperability requires agreement at three layers -- transport, syntax and semantics -- and only the first two can be bought as mature standards.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.

#### Line 68 -- `[@sample_std_interop_2021]` (93% match)

> Interoperability requires agreement at three layers -- transport, syntax and semantics -- and only the first two can be bought as mature standards.

Best match is on **page 1** of the source. The text for this citekey has no reading order (see chitragupta/passages.py), so the page is reported without quoting from it.
