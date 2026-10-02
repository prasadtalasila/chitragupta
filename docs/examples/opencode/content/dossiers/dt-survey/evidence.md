# Evidence

## `sample_dt_overview_2024`

- relevance: Provides the definitional foundation for the survey, distinguishing three levels of integration between physical and virtual entities.
- claim: A digital twin is a virtual representation of a physical system kept consistent throughout its operating life; the literature distinguishes three integration levels -- a digital model (manual data exchange only), a digital shadow (automatic one-way data flow from physical to virtual), and a digital twin (bidirectional data flow with the virtual able to influence the physical).

## `sample_dt_sync_2023`

- relevance: Addresses the synchronisation problem directly, comparing three strategies for keeping a twin's state current.
- claim: A digital twin's trustworthiness depends on its last synchronisation; three strategies exist -- periodic pull (uniform polling interval regardless of asset activity), threshold push (asset transmits only when a sensed value moves beyond a configured delta, so bandwidth follows activity), and event-driven flows (domain events such as job start or valve close trigger synchronisation, yielding a process log that operators preferred in trials). In a synthetic benchmark across nine production cells, event-driven flows reduced transmitted volume by 71% against one-second periodic pull while keeping worst-case staleness bounded.

## `sample_dt_factory_2022`

- relevance: Provides a concrete factory-floor case study showing how a twin evolves from monitoring to control over an eighteen-month deployment.
- claim: A digital twin of a packaging line at a beverage plant began as a monitoring dashboard and progressed through phases -- first a digital shadow with only sensor-to-model flow (an explicit trust-building step allowing operators to compare the shadow against the visible line), then full bidirectional integration where the twin became the plant's scheduling authority.

## `sample_std_interop_2021`

- relevance: Maps the interoperability landscape that digital-twin pilots must navigate, arguing that integration cost -- not modelling -- is the primary failure mode.
- claim: Digital-twin pilots rarely fail from modelling problems but from integration; every asset on a site speaks a protocol its vendor shipped, and twin cost is dominated by adapters. Interoperability requires agreement at three layers -- conceptual (what the asset model represents), semantic (what fields mean, ensuring two systems' "temperature" is the same sensor and unit), and transport/syntax (message structure and serialisation). Semantic agreement cannot be bought, only negotiated, and is operationalised through shared asset-model registries that map every signal to a definition and unit.

## `sample_ml_anomaly_2023`

- relevance: Tangentially relevant -- examines anomaly detection on a twin's state stream, which is only applicable where a source ties anomaly detection to a twin.
- claim: A digital twin's state stream is a natural place to detect anomalies because it is already cleaned, aligned and semantically labelled -- which constitutes most of the work in industrial anomaly detection; the paper examines how minimal a model needs to be for this purpose.
