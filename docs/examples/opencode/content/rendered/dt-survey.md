# Digital Twins in Manufacturing: A Survey

This survey maps the literature on digital twins as they apply to manufacturing. It covers what a digital twin is and how it is distinguished from related concepts; how the twin is kept synchronised with its physical counterpart; how twins are deployed on the factory floor; and the interoperability standards that determine whether a twin project survives integration. It does not cover machine-learning anomaly detection except where a source ties it to a twin. The reader is assumed to be familiar with manufacturing systems at a general level and to need a structured map of the twin literature rather than an introduction to manufacturing itself.

## Definitions and a Three-Level Taxonomy

The term *digital twin* is used loosely across the literature, and much of the early literature disagrees about where a simulation ends and a twin begins. Author and Builder [1] resolve this by fixing the vocabulary around integration depth. They distinguish three levels.

At the lowest level, a **digital model** exchanges data with its physical counterpart only through manual steps: an engineer updates the model when the plant changes, and nothing flows back automatically. This is indistinguishable from a conventional CAD or CAE model and falls short of twin status.

A **digital shadow** adds an automatic data flow in one direction, from the physical object to the virtual one. The representation updates without human intervention, but the virtual side cannot influence the physical. This is still not a twin in the strict sense.

A **digital twin** completes the loop with bidirectional data flow: the virtual model can send commands or schedules back to the physical asset, and the twin is kept consistent with the physical system for the length of its operating life. This bidirectional coupling is the defining property that separates a twin from a shadow or a model.

These three levels are not merely terminological. They map onto a deployment trajectory: a site typically begins with a digital shadow, earns operator trust, and only then opens the feedback loop.

## Synchronisation Strategies

A digital twin is only as trustworthy as its last synchronisation. The engineering question underneath every twin deployment is how to keep the virtual state current without overwhelming the network or accepting stale data. Chen and Devi [2] compare three synchronisation strategies.

**Periodic pull** is the simplest: a central system polls the asset at a fixed interval, regardless of what the asset is doing. The advantage is implementation simplicity; the disadvantage is that quiet assets are polled as often as busy ones, wasting bandwidth on unchanged readings.

**Threshold push** reverses the initiative. The asset transmits only when a sensed value moves beyond a configured delta. Bandwidth follows activity, but a mis-set delta can hide slow drift entirely -- a subtle failure mode because the twin appears live while its data is stale.

**Event-driven flow** ties synchronisation to domain events: a job start, a valve close, a product passing a sensor. The twin's state history then reads as a process log rather than a time series. Operators in Chen and Devi's trials strongly preferred this representation, and in a synthetic benchmark across nine simulated production cells, event-driven flows reduced transmitted volume by 71 per cent against one-second periodic pull while keeping worst-case staleness bounded.

The choice of synchronisation strategy is not purely technical. It shapes how operators read the twin's state and, by extension, whether they trust it enough to act on it.

## Factory-Floor Applications

The factory floor is where digital twins move from pilots to production value. Eriksen [3] documents an eighteen-month deployment of a digital twin of a packaging line -- three filling stations, two labellers, one palletiser -- at a mid-size beverage plant. The twin began as a monitoring dashboard and ended as the plant's scheduling authority.

The first six months deliberately stopped at a digital shadow: sensor data flowed to the model automatically, and nothing flowed back. This was an explicit trust-building decision. Operators could compare the shadow against the line they could see, and its one visible product -- a per-station utilisation display -- was checked against manual logs. Only after the shadow was trusted did the deployment open the feedback loop.

The progression from shadow to twin is not unique to this case. It reflects a broader pattern: sites that attempt bidirectional control before earning trust tend to revert to monitoring, because operators will not follow a twin's instructions if they do not believe the twin.

## Interoperability Standards

Digital-twin pilots rarely die of modelling problems; they die of integration. Every asset on a real site speaks the protocol its vendor shipped a decade ago, and the cost of a twin is dominated by the adapters between those dialects and the twin's own model. Havel and Ismail [4] argue that standards are how that cost is paid once instead of per project.

Interoperability requires agreement at three distinct layers. At the **conceptual layer**, the parties agree what the asset model represents -- which physical components are in scope and what boundaries the model draws. At the **semantic layer**, they agree what the fields mean: that two systems' "temperature" is the same sensor, the same unit, and the same sampling discipline. At the **transport and syntax layer**, they agree how a message is structured -- a schema language and a serialisation format.

Transport and syntax standards are mature and plentiful. Semantic agreement is where projects stall, because it cannot be bought, only negotiated. The practical instrument of semantic agreement is a shared asset-model registry: a versioned catalogue mapping every signal to a definition, a unit, and a provenance trail. When a new asset arrives on site, its signals are looked up in the registry rather than reverse-engineered from a vendor manual.

The three-layer model is not specific to digital twins, but it explains a recurring pattern: twin projects that invest in semantic agreement early survive integration, while those that treat it as a post-deployment afterthought accumulate adapter debt that no amount of modelling sophistication can offset.

## Anomaly Detection on Twin State Streams

Machine-learning anomaly detection falls outside this survey's scope, but one source ties it directly to the twin and is worth noting briefly. Farah and Gupta [5] observe that a digital twin's state stream is a natural place to detect anomalies because it is already cleaned, aligned and semantically labelled -- which constitutes most of the work in industrial anomaly detection. The question their paper examines is how minimal a detection model can be when it operates on a twin's state stream rather than on raw sensor data. This is a narrow but instructive example of how twin infrastructure can reduce the cost of downstream analytics.

## Comparison of Approaches

The following table summarises the papers surveyed, on the axis of what each contributes to the twin literature.

| Starting point | Citekey | Core idea | Stated limitation |
|---|---|---|---|
| Definition | [1] | Three-level taxonomy (model, shadow, twin) based on integration depth | Taxonomy is illustrative; no empirical validation |
| Synchronisation | [2] | Three synchronisation strategies compared; event-driven preferred by operators | Synthetic benchmark across simulated cells only |
| Factory deployment | [3] | Eighteen-month case study showing shadow-to-twin progression | Single site; beverage packaging domain |
| Interoperability | [4] | Three-layer standards model; semantic agreement as negotiation | Standards landscape simplified for illustration |
| Anomaly detection | [5] | Twin state stream as natural anomaly-detection input | Minimal model requirements unquantified |

**Table 1:** Where to start when building a first twin.

Table 1

The table reveals a pattern: every paper that focuses on a single technical layer (synchronisation, interoperability, anomaly detection) is strongest at that layer but does not address the others. The overview paper [1] is the only one that attempts a cross-cutting taxonomy, and its limitation -- illustrative rather than empirical -- is the limitation of the field at large: few papers sit at the intersection of definition, deployment, and standards.

## Gaps

The retrieved corpus is small and covers the four scope themes, but several gaps remain. First, there is no empirical comparison of synchronisation strategies outside a synthetic benchmark; the event-driven preference reported by Chen and Devi [2] has not been validated on a live production line. Second, the interoperability literature surveyed here is conceptual; there is no paper in the corpus that measures the integration cost of a twin project before and after adopting an asset-model registry. Third, the factory-floor case study by Eriksen [3] is a single-site study in one domain; whether the shadow-to-twin progression generalises to discrete manufacturing or process industries is unknown.

These gaps are not failures of retrieval. The declared scope -- definitions, synchronisation, factory applications, and interoperability -- is covered by the corpus. What the corpus does not contain is empirical, multi-site validation of the patterns it describes, or a quantitative study of integration cost as a function of standards adoption. A later revision that widens the corpus should look for these explicitly.

## References

[1] A. Author and B. Builder, "Digital Twins: Definitions, Distinctions, and a Short Taxonomy," *Synthetic Sample Papers*, vol. 1, pp. 1–5, 2024.

[2] C. Chen and D. Devi, "State Synchronisation Strategies for Operational Digital Twins," *Synthetic Sample Papers*, vol. 1, pp. 6–11, 2023.

[3] E. Eriksen, "A Digital Twin on the Factory Floor: an Eighteen-Month Case Study," *Synthetic Sample Papers*, vol. 1, pp. 12–17, 2022.

[4] H. Havel and I. Ismail, "Interoperability Standards for Industrial Asset Models: a Field Guide," *Synthetic Sample Papers*, vol. 1, pp. 24–29, 2021.

[5] F. Farah and G. Gupta, "Lightweight Anomaly Detection over Digital-Twin State Streams," *Synthetic Sample Papers*, vol. 1, pp. 18–23, 2023.
