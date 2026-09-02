# Digital Twins in Operation: a Short Survey of the Sample Corpus

## 1. Introduction

The phrase *digital twin* is applied to systems with very different
levels of ambition, and the corpus surveyed here begins by fixing that
vocabulary. A digital model exchanges data with its physical
counterpart only through manual steps; a digital shadow adds an
automatic flow in one direction; a digital twin closes the loop, with
data flowing automatically both ways [@sample_dt_overview_2024]. The
distinction is one of data flow rather than model sophistication, and
holding it strictly keeps expectations honest: in one synthetic survey
of forty deployments, twenty-eight systems described as twins were, by
this definition, shadows [@sample_dt_overview_2024].

This survey groups the sample corpus into three themes -- keeping the
twin true to its asset, using its state stream, and integrating it with
everything else -- and closes with the gaps the corpus leaves open.

## 2. Keeping the twin true

A twin is only as trustworthy as its last synchronisation. Comparing
periodic pull, threshold push and event-driven flows across nine
simulated production cells, event-driven synchronisation reduced
transmitted volume by 71 percent against one-second polling while
holding worst-case staleness under two seconds [@sample_dt_sync_2023].
Threshold push matched that volume but produced the study's two worst
staleness excursions, both during slow thermal drift that never crossed
its configured delta [@sample_dt_sync_2023].

Trust is behavioural as much as technical. Marking staleness explicitly
-- a twin that knows it is stale must say so on every read -- roughly
halved operator mistrust incidents in the same trials
[@sample_dt_sync_2023]. The eighteen-month factory case study reaches
the same conclusion from the organisational side: its twin earned
scheduling authority station by station, and the deciding argument was
never abstract model accuracy but a published override log showing
supervisors agreeing with the twin in over ninety-five percent of cases
[@sample_dt_factory_2022]. Both failures it records were silent
divergences between plant and model, and its recommendation is to treat
any such divergence as a severity-one defect
[@sample_dt_factory_2022].

## 3. Using the state stream

Once a twin exists, its state stream is a naturally clean substrate for
analytics. For anomaly detection, a layered configuration -- a rolling
z-score everywhere, with a learned detector added only where the
false-positive cost justifies its upkeep -- matched an autoencoder's
precision on point faults while remaining immune to the baseline
corruption that made the autoencoder miss the slowest drift entirely
[@sample_ml_anomaly_2023]. The cost asymmetry is stark: constant memory
per signal for the baseline against a weekly GPU hour and a human
retraining decision for the learned model [@sample_ml_anomaly_2023].

## 4. Integrating with everything else

Twin pilots rarely die of modelling problems; they die of integration.
Interoperability requires agreement at three layers -- transport,
syntax and semantics -- and only the first two can be bought as mature
standards [@sample_std_interop_2021]. The practical instrument for the
third is a shared asset-model registry with named owners: sites that
maintained one integrated a new asset in a median of six days, against
seven weeks where semantics were negotiated per project
[@sample_std_interop_2021]. Versioning discipline follows the same
logic; the corpus recommends append-only models, where a field is
deprecated and replaced but never repurposed
[@sample_std_interop_2021].

## 5. Gaps

Three gaps stand out. The corpus measures synchronisation and anomaly
detection separately, but no paper studies how detector accuracy
degrades under the staleness its own synchronisation strategy permits.
Fidelity is argued to be purchased "decision by decision"
[@sample_dt_overview_2024], yet no paper offers a costing method for
that purchase. And the organisational trust mechanisms of the factory
study [@sample_dt_factory_2022] have no counterpart for the anomaly
detectors of [@sample_ml_anomaly_2023], whose false positives spend
the same trust budget.

## 6. Conclusion

Across the sample corpus, the recurring finding is that twins succeed
on honesty rather than sophistication: strict vocabulary
[@sample_dt_overview_2024], marked staleness [@sample_dt_sync_2023],
published override logs [@sample_dt_factory_2022], incorruptible
baselines [@sample_ml_anomaly_2023] and owned semantics
[@sample_std_interop_2021] are all instances of one design value --
never let the representation be confidently wrong.

## References

[1] A. Author and B. Builder, "Digital Twins: Definitions, Distinctions, and a Short Taxonomy," *Synthetic Sample Papers*, vol. 1, pp. 1–5, 2024. `sample_dt_overview_2024`

[2] C. Chen and D. Devi, "State Synchronisation Strategies for Operational Digital Twins," *Synthetic Sample Papers*, vol. 1, pp. 6–11, 2023. `sample_dt_sync_2023`

[3] E. Eriksen, "A Digital Twin on the Factory Floor: an Eighteen-Month Case Study," *Synthetic Sample Papers*, vol. 1, pp. 12–17, 2022. `sample_dt_factory_2022`

[4] F. Farah and G. Gupta, "Lightweight Anomaly Detection over Digital-Twin State Streams," *Synthetic Sample Papers*, vol. 1, pp. 18–23, 2023. `sample_ml_anomaly_2023`

[5] H. Havel and I. Ismail, "Interoperability Standards for Industrial Asset Models: a Field Guide," *Synthetic Sample Papers*, vol. 1, pp. 24–29, 2021. `sample_std_interop_2021`
