# Digital Twins in Manufacturing: A Survey

## Introduction

The phrase *digital twin* denotes a virtual model that stays aligned with a physical asset across its entire service life [@sample_dt_overview_2024]. Although the term has gained wide traction in engineering, early publications disagree on where a standalone simulation ends and a twin begins. This survey covers the manufacturing context: the meaning of a digital twin, the synchronisation mechanisms that keep the model aligned with its asset, documented factory-floor deployments, and the interoperability standards that are beginning to shape the field. Machine-learning anomaly detection is excluded as a standalone topic, except where a source treats it as a direct application of the twin's state stream.

## What a Digital Twin Is

A digital twin is distinguished from a conventional simulation not by model fidelity but by the continuous, bidirectional data flow that links it to a physical system [@sample_dt_overview_2024]. A simulation that executes once and terminates is not a twin; a twin persists, updates in response to its asset, and may exert control over it. [@sample_dt_overview_2024] categorises the relationship between asset and model into three tiers. A *digital shadow* pushes information from the physical to the virtual side only, which suffices for monitoring but precludes any form of closed-loop action. A *twin* exchanges data in both directions, allowing the model to inform operator decisions. A *twin controller* goes further, permitting the virtual model to issue commands back to the physical system.

This distinction is practically important because several published demonstrations stop at the shadow tier while being labelled full twins. The difference is not purely terminological: a shadow cannot support the trust-building phase that [@sample_dt_factory_2022] describes as a prerequisite for any closed-loop deployment on a live production line.

## Synchronisation Strategies

Maintaining alignment between the virtual model and the physical asset is the synchronisation problem, and it is where many twin projects encounter difficulty in practice. [@sample_dt_sync_2023] presents synchronisation as a design space encompassing event-driven updates, periodic polling, and hybrid approaches, with each strategy offering a different trade-off between model freshness and communication overhead. The optimal choice depends on the dynamics of the physical system and the latency requirements of downstream applications that consume the twin's state.

A further point from [@sample_dt_sync_2023] is that synchronisation is an ongoing engineering concern rather than a one-off configuration: network conditions fluctuate, sensor calibration drifts, and the model itself may require updates to reflect physical retrofits. The synchronisation layer must be designed to handle all three kinds of change.

## Factory Applications

The factory floor is where digital twins have progressed from concept to working systems, and field-deployment evidence carries a different weight from purely conceptual papers. [@sample_dt_factory_2022] describes an eighteen-month case study in which a digital twin started as a monitoring dashboard — effectively a digital shadow — and gradually assumed the role of the plant's scheduling authority. The evolution was intentional: the first six months were devoted to shadow-level monitoring so that operators could compare the model's predictions against the visible production line, establishing trust before any closed-loop functionality was introduced.

This staged pattern — shadow first, twin second — appears to be a recurring theme in industrial deployments. It reflects a wider observation: the modelling challenge is often the simpler half, while the harder problem is gaining the operational trust needed to let a virtual model influence a live process.

## Interoperability Standards

Integration, not modelling, is the bottleneck for digital-twin pilots [@sample_std_interop_2021]. A real factory floor contains assets from many vendors, each speaking its own legacy protocol, and the majority of a twin's cost comes from building the adapters between those protocols and the twin's internal data model. Standards address this problem economically by allowing the integration cost to be amortised across projects rather than paid anew each time.

[@sample_std_interop_2021] separates interoperability into three distinct layers — data model, semantics, and communication — and cautions against treating them as interchangeable. A twin may implement a correct data model schema yet still fail to interoperate if two systems disagree on the meaning of the fields it carries. This layered perspective has a practical implication for manufacturers evaluating twin platforms: compatibility at one layer does not guarantee compatibility at the others.

## Gaps and Future Directions

The corpus examined here is modest in size, and several areas would benefit from broader coverage. The synchronisation literature is particularly thin: [@sample_dt_sync_2023] is the sole source that tackles the problem directly, and its strategies are presented without empirical comparison. Factory-applications research is similarly sparse, with [@sample_dt_factory_2022] the only longitudinal field study in the set. Interoperability standards evolve rapidly; the landscape described by [@sample_std_interop_2021] is necessarily provisional and will need revision as new standards mature.

One conspicuous gap is the position of digital twins within the wider industrial IoT architecture. None of the surveyed sources situates the twin explicitly inside an IoT stack, and a survey that treats the twin in isolation risks presenting it as a standalone technology rather than one component of a larger system.

## References

- [@sample_dt_overview_2024]
- [@sample_dt_sync_2023]
- [@sample_dt_factory_2022]
- [@sample_std_interop_2021]
