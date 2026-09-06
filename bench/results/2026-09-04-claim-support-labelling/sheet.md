# Claim-support rating sheet

Read each item and judge whether the cited passage supports the
claim. Record one of `supported`, `unsupported`, `unclear` per item
in your own `ratings-<you>.json`. You are rating the *claim against
the passage*, not the writing.

The aid's score is deliberately absent, and the order is shuffled.
Do not consult `key.json` -- it exists to join your ratings back
afterwards, and reading it un-blinds the rating.

## item 0

**Claim.** **Regulation.** The compliance landscape for AI is real and moving, and in regulated sectors the pathway is the subject rather than a detail -- healthcare twin work treats the credibility assessment as the hardest part of getting an in-silico method accepted. **This chapter's position is narrow and deliberate:** a regulation is a given standard, so the only question is what it obliges you to produce, and the answer is almost always a form of Chapter 7's credibility argument plus Chapter 10's provenance.

**Cited source.** `viceconti_position_2024`, page 4

**Matched passage.**

> ThispositionpaperintroducestheVirtualHumanTwin(VHT) concept. While there is an ongoing consensus process to reach a robust definition for the VHT, led by the EDITH support action, its general features are defined. Whereas a Digital Twin in Healthcare is a vertical technology aimed to solve a particular clinical problem, the Virtual Human Twin will be a distributed, collaborative infrastructure, a collection of technologies and resources (data, models) that enables it, and a collection of Standard Operating Procedures (SOP) that regulate its use. The Virtual Human Twin infrastructure aims to help address all seven challenges listed above and facilitate researchers and developers in academia, public organisations, and industry to produce new and interoperable DTH solutions. Two essential features must be stressed from the outset. The first is that the Virtual Human Twin is not a model able to predict every aspect of human pathophysiology; it is an infrastructure which will allow the accumulation and interconnection of all the quantitative data and knowledge on human pathophysiology. The second is that the VHT will preferentially host quantitative (data that can be counted or measured in numerical values), individual data, and from humans . Preferential means that qualitative data, cohort averages, and animal data will be accepted only as surrogates of quantitative, individual human data when these are impossible to obtain.

## item 1

**Claim.** *Risk and trust:* for explainability in industrial settings, for the twin security landscape including attacks on learned models, and for the clearest statement that one-off credibility assessment does not transfer to data-driven models.

**Cited source.** `viceconti_position_2024`, page 1

**Matched passage.**

> Sabato Mellone is with the Department of Electrical, Electronic and Information Engineering, Alma Mater Studiorum, University of Bologna, 40126 Bologna, Italy (e-mail: sabato.mellone@unibo.it).

## item 2

**Claim.** **The two cautions, both from the corpus.** Open-source implementations are incompatible with each other, so choosing AAS does not finish the decision -- you also choose an implementation and inherit its interpretation.

**Cited source.** `jacoby_open-source_2023`, page 9

**Matched passage.**

> We based our tests on the AAS interfaces and operations defined in the AAS specification Part 2 v1.0RC02 [16] and the corresponding Swagger documentation labeled 'Entire Interface Collection v1.0RC01' [31]. As each implementation uses a (slightly) different API which prevents using a common test to evaluate all of them and instead needs to manually convert each test case to each of the implementations' APIs, we decided to limit the tests to a somewhat representative set of API calls. The test, therefore, includes operations for the three interfaces AAS Repository, AAS, and Submodel as these are the most important interface without an AAS implementation that is hardly usable in real-world applications. For the AAS Repository interface creating, reading, updating, and deleting AAS is tested. For the AAS interface, reading the AAS and its contained submodel references is tested as well as adding a new submodel For the Submodel interface, reading and updating submodels and submodel elements is tested as well as creating, updating, and deleting elements. Output modifiers are tested only for a single API call assuming that if an implementation provides the functionality to process an output modifier for one API call, they also do it for all others as the hard part with output modifiers is the implementation of the underlying logic.

## item 3

**Claim.** *Co-simulation and FMI:* for the model-exchange versus co-simulation split in the clearest terms; for a concrete master implementation; for what practitioners find hard; and for open frameworks built on FMI; for a worked multi-domain case; for coupling an equation-based tool to a legacy one; for runtime monitoring of master algorithms.

**Cited source.** `wetter_spawn_2024-1`, page 4

**Matched passage.**

> Second, for computational efficiency, Spawn places the heat and mass balance calculations for room air in the HVAC domain rather than the envelope domain, as earlier work had done. Room air state evolution exhibits fast dynamics at similar time scales to those of the HVAC system. Placing these in different simulation domains from HVAC requires short synchronization time steps that lead to longer simulation times, as we observed in earlier couplings that used the FMU import/export interface of EnergyPlus and the BCVTB. By placing the room air model in the HVACdomain,Spawnallowsthedynamicsofroomair and HVAC to be solved together and minimizes the burden of synchronization with the slower dynamics of the envelope domain.

## item 4

**Claim.** Operating expenditure often shows up as software licensing rather than machines.

**Cited source.** `noauthor_case_nodate`, page 101

**Matched passage.**

> SINTEF: As we have so far only reached proof-of-concept maturity for the SINTEF part of the digital twin solution, it is difficult to give an accurate estimate of costs. However, the main CAPEX costs for implementing the solution are limited to computer hardware and the time and costs associated with training machine learning models. The sensors that captured the data were already installed on the Additive Industries machines. There are several components to the software, including segmentation, reconstruction, alignment and visualization software, and the digital twin models we create are quite dense. They thus perform best on high-end consumer GPU hardware (e.g., NVIDIA GeForce GTX 3090, price ~ €1650). Regarding data collection, ideally this would be done continually during routine operation, thereby minimizing costs. However, time and costs associated with data curation and labelling remain. The OPEX costs would probably be covered by a licensing model for the software suite.

## item 5

**Claim.** *Consulted, not drawn on above:*, and on system-level and interoperability framings, and on distributed twin infrastructure.

**Cited source.** `altamiranda_system_2024`, page 9

**Matched passage.**

> Data Platforms: Cross Domain Data Contextualization, Distribution & Exchange for Digital Twins Level 1-5 (Digital Thread)

## item 6

**Claim.** *Consulted, not drawn on above:* for how a distributed-simulation standard handles participants with different notions of time, on consistency checks including step sizes inside a verification process, on simulators as training environments, for hardware-in-the-loop in the twin vocabulary, on augmenting twin models with behaviour, and on checking at runtime that co-simulation master algorithms are being used correctly.

**Cited source.** `honcak_mbse_2024`, page 4

**Matched passage.**

> Validation and Calibration: MBSE facilitates precise adjustment of the  Digital  Twin through comprehensive modeling and real-time data integration.

## item 7

**Claim.** **Training people.** Industry treats trained operators as a direct benefit, and the training cost of sending staff away is itself a line item the twin displaces.

**Cited source.** `grieves_digital_2024`, page 5

**Matched passage.**

> The digital/virtual environment of the digital twin, referred to as the Digital Twin Environment (DTE), requires that it have rules that are identical as possible to our physical environment. We need to be assured that the behavior of the digital twin in the DTE mirrors the behavior of its physical counterpart for the use cases we require.

## item 8

**Claim.** **DevOps for twin development and evolution** is being worked on directly, with an emphasis on the iterative development and evolution of twins rather than their initial construction, and the evolution literature explicitly asks how DevOps practice can support twin evolution and calls for evolution to be treated as a core principle.

**Cited source.** `aissat_devops_2025`, page 20

**Matched passage.**

> To ensure proper handling of this communication pattern, repositories in the DTServiceLayer are configured to subscribe and publish to the appropriate topics, with repository structures and CI/CD pipelines already prepared by software engineers. This allows domain experts to focus on the development of their service components without having to manage infrastructure concerns. Once complete, these services may expose their results via an external API (e.g., for UI consumption) or publish them through the pub/sub system (e.g., control messages to trigger actuators via ATController ). This modular organization enables systematic reuse of key elements such as pipeline configurations, microservice repositories, and data communication mechanisms.

## item 9

**Claim.** Interoperability at this boundary is exactly what the standards work is for, and Chapter 13 covers it.

**Cited source.** `marosi_interoperable_2022`, page 18

**Matched passage.**

> Tan, C.; Sun, F.; Kong, T.; Zhang, W.; Yang, C.; Liu, C. A Survey on Deep Transfer Learning. In Proceedings of the Artificial Neural Networks and Machine Learning-ICANN 2018 ; K˚ urková, V., Manolopoulos, Y., Hammer, B., Iliadis, L., Maglogiannis, I., Eds.; Springer International Publishing: Cham, Switzerland, 2018; pp. 270-279. Available online: https://link.springer.com/chapter/ 10.1007/978-3-030-01424-7_27 (accessed on 30 October 2021).

## item 10

**Claim.** A **reduced-order model** is a surrogate built by discarding structure the answer does not depend on; such models sit at the intersection of high-fidelity physics simulation and data-driven modelling, and trade some accuracy for much greater computational speed.

**Cited source.** `rasheed_digital_2020`, page 24

**Matched passage.**

> R. S. Sutton and A. G. Barto, Introduction to Reinforcement Learning , vol. 2, no. 4. Cambridge, MA, USA: MIT Press, 1998.

## item 11

**Claim.** That is why this sector is a heavy adopter of condition-based and predictive maintenance, with twins as the enabler.

**Cited source.** `stadtmann_diagnostic_2024`, page 1

**Matched passage.**

> nance costs based on average component lifetimes [6]. On one hand, these maintenance strategies result in the replacement of components long before their lifetimes expire and ultimately lead to the decommissioning of turbines that could be operated for several more years. On the other hand, unexpected failures and therefore unexpected downtime still occur. If the remaining useful lifetime of components could be estimated based on the actual locally experienced conditions and formerly unexpected failures could be predicted from small anomalies, the maintenance strategy could be changed from reactive and preventive to conditionbased and predictive. It is therefore not surprising that there is a large industrial interest in condition monitoring, condition-based maintenance, and predictive maintenance, especially by offshore industries with remote assets. Digital twins are a key enabler in facilitating this shift in maintenance strategies by monitoring and analyzing the asset condition.

## item 12

**Claim.** *Platforms, middleware and deployment:* for the as-a-service framing and its container decomposition, for what middleware actually does in published twins, and for microservice and serverless realisations, and on the edge-to-cloud continuum, and for open-source frameworks, on reusing reference architectures, and with for the industrial-architecture framing of connectivity and the twin-as-middleware pattern.

**Cited source.** `noauthor_industrial_nodate`, page 50

**Matched passage.**

> With the prevailing application DevOps trend, it is increasingly common for industrial applications to be implemented based on certain technology platforms, including some industrial platformas-a-service (PaaS). These  platforms  provide connectivity to equipment  and  real-world environments (through sensors), perform data collection, pre-processing, storage, and management, and enable application DevOps with micro-service support. The purpose of these platforms  is  to  enable  and  simplify  application  development  by  providing  proven  system architecture  and  ready-to-use  common functionalities  as  platform  services  thus  reducing the complexity and effort in application development. Take for example, a common IIoT application platform may combine an IIoT (connectivity, data management, etc. functionalities) framework with an application DevOps framework. As digital twin support becomes widely available, it is natural to provide a digital twin framework as part of the platform service, that is supported by the IIoT services and in turn supports the industrial applications. In a full-stack architecture for IIoT applications that leverage digital twin capabilities, the core capabilities of digital twins can be implemented as a middle layer, supporting individual applications in the upper applications layer, and relying on various supportive technologies and platforms provided in the lower support environment  layer.  Examples  of  support  functions  include  equipment  connectivity,  data collection, preprocessing and storage that can be readily provided by an IIoT system.

## item 13

**Claim.** Chapter 7 Sec. 7.13 asked what happens to a credibility argument when twins start composing, and Chapter 7 Sec. 7.7.5 pointed at the answer: an approach in which each side publishes, per trustworthiness characteristic, a link to a human- and machine-readable justification -- an assurance case -- so a composed system can reason about whether its parts are trustworthy enough for the job.

**Cited source.** `noauthor_assuring_2024`, page 21

**Matched passage.**

> In the example described above, all the systems exist in a single system of systems in which any systems instantiating connection profiles will be considered to be matched with other systems by the broker. In connection profile terminology, this is considered as a single context.

## item 14

**Claim.** Interview studies of continuous integration for cyber-physical systems show teams doing exactly this in production pipelines, sometimes with customer-mandated simulators.

**Cited source.** `zampetti_continuous_2023`, page 21

**Matched passage.**

> Table 8. Relations Between Challenges/Barriers and Mitigation Strategies as Seen from the Semi-Structured Interviews and the Member-Checking Survey
> 
> | Challenge/Barrier                 | Mitigation                                                                  | Organizations                                                                                                                           |
> |-----------------------------------|-----------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
> | B 2 : Limited hw/sw resources     | Test Prioritization Incremental Builds                                      | O 1 , O 2 , O 3 , O 4 , O 5 , O 6 , O 7 , O 8 , O 9 , O 10 O 1 , O 2 , O 4 , O 7 , O 8 , O 9                                            |
> | B 5 : Domain hinders HiL          | Rely on sim./mock-up                                                        | O 1 , O 2 , O 8 , O 9 , O 10                                                                                                            |
> | PC 1 : Long build                 | Test Prioritization Adopt Parallelization Nightly Builds Incremental Builds | O 1 , O 2 , O 4 , O 7 , O 8 O 2 , O 4 , O 5 , O 6 , O 7 , O 8 O 1 , O 2 , O 4 , O 5 , O 6 , O 7 , O 8 O 2 , O 4 , O 5 , O 6 , O 7 , O 8 |
> | PC 9 : Continuous installation    | Containerization                                                            | O 3 , O 4 , O 5 , O 7 , O 8                                                                                                             |
> | PC 13 : Sim. limited func.        | Combine sim. and HiL                                                        | O 4 , O 7 , O 8 , O 9 , O 10                                                                                                            |
> | PC 16 : Sim. coupled with env.    | Combine sim. and HiL                                                        | O 2 , O 3 , O 4 , O 8 , O 9                                                                                                             |
> | PC 17 : Sim. accessibility        | Timeout                                                                     | O 1 , O 5 , O 7 , O 10                                                                                                                  |
> | PC 21 : HiL costs and scalability | Combine sim. and HiL Green-build rule                                       | O 1 , O 2 , O 3 , O 4 , O 5 , O 7 , O 8 , O 9 O 2 , O 3 , O 4 , O 7                                                                     |
> | PC 26 : No resources' control     | Fix the code Fix pipeline config.                                           | O 4 , O 6 , O 7 , O 9 , O 10 O 6 , O 7 , O 9                                                                                            |
> | PC 27 : Network issues            | Retry                                                                       | O 2 , O 4 , O 5 , O 6 , O 7 , O 10                                                                                                      |

## item 15

**Claim.** And description formats more broadly present information incompatibly, which is why bridging work exists. **Run Chapter 12 Sec. 12.3.2's export test between your implementation and your counterparty's before designing around the exchange.**

**Cited source.** `mattila_interoperability_2025`, page 13

**Matched passage.**

> K. Wang, Z. Li, K. Nonomura, T. Yu, K. Sakaguchi, O. Hashash, and W. Saad, ''Smart mobility digital twin based automated vehicle navigation system: A proof of concept,'' IEEE Trans. Intell. Vehicles , vol. 9, no. 3, pp. 4348-4361, Mar. 2024.

## item 16

**Claim.** *Consulted, not drawn on above:*, and on system-level and interoperability framings, and on distributed twin infrastructure.

**Cited source.** `mckee_discs_2024`, page 4

**Matched passage.**

> Los Angeles Neighborhood Improvement: At the CES 2019 electronics trade show, the Itron Ideas Labs team collaborated with Microsoft Azure to use mixed reality for creating a virtual representation of a downtown Los Angeles neighborhood. This project demonstrated how city planners could virtually implement changes such as installing smart sensors or altering traffic patterns and directly observe the impact on the urban environment. This application of digital twins illustrates their utility in planning and executing neighborhood improvements [3].

## item 17

**Claim.** In classical modelling and simulation practice the model is calibrated, validated once, and then generally assumed finished; for a twin, validation has to be **continual**, with recalibration triggered when the model stops matching the world it is attached to.

**Cited source.** `ali_modeling_2024`, page 11

**Matched passage.**

> 4.2.2. Online and continual validation. Continual validation is the process of continually ensuring a DT, or more concretely the model(s) in the DT, remains a valid representation of their real-world counterpart. When the model becomes invalid, e.g., due to changes in the real-world system, a recalibration is needed to match the DT to the real world once again, as was shown in Stage 2.9 in Figure 5. This is conceptually different from model validation in M&S where, typically, a calibration attempt is performed first, after which the model is subjected to the validation procedure. Once positively validated, the model is generally also assumed ''finished.'' Besides this conceptual difference, there is a high level of similarity between traditional model validation and the validation of models in DTs. As such, the model validation techniques from M&S can largely be carried over. 85 However, one faces several challenges when continually attempting to apply those model validation techniques. They stem from the fact that only the runtime data of the system in operation are available. This leads to the following challenges:

## item 18

**Claim.** *Consulted, not drawn on above:* for the layer-by-layer threat classification behind Sec. 9.8.4, on twins paired with constrained devices, on communication interfaces as a named twin component, and on what open-source twin frameworks provide at this layer.

**Cited source.** `barbone_-device_2026`, page 14

**Matched passage.**

> F. De Vita, G. Nocera, D. Bruneo, V. Tomaselli, M. Falchetto, On-device training of deep learning models on edge microcontrollers, in: 2022 IEEE International Conferences on Internet of Things (iThings) and IEEE Green Computing & Communications (GreenCom) and IEEE Cyber, Physical & Social Computing (CPSCom) and IEEE Smart Data (SmartData) and IEEE Congress on Cybermatics (Cybermatics), 2022, pp. 62-69. https://doi.org/10.1109/ iThings-GreenCom-CPSCom-SmartData-Cybermatics55523.2022.00018

## item 19

**Claim.** *TwinOps and DevOps for twins:* and, which put model-based engineering and ordinary delivery practice into a single pipeline and then check what the running system actually did against what the engineering models said it would; and on a DevOps approach aimed specifically at the iterative development and evolution of twins rather than their construction.

**Cited source.** `aissat_devops_2025`, page 20

**Matched passage.**

> To ensure proper handling of this communication pattern, repositories in the DTServiceLayer are configured to subscribe and publish to the appropriate topics, with repository structures and CI/CD pipelines already prepared by software engineers. This allows domain experts to focus on the development of their service components without having to manage infrastructure concerns. Once complete, these services may expose their results via an external API (e.g., for UI consumption) or publish them through the pub/sub system (e.g., control messages to trigger actuators via ATController ). This modular organization enables systematic reuse of key elements such as pipeline configurations, microservice repositories, and data communication mechanisms.

## item 20

**Claim.** It has been used as the frame for key-component catalogues, mapped onto by other frameworks, and applied to worked use cases.

**Cited source.** `steinmetz_key-components_2022`, page 2

**Matched passage.**

> The paper is organized as follows: Section II brings a review of the state of the art in the context of DT; in section III the key-components are presented with two overviews: the fi rst, arranged in layers and the second, showing their relationship; in section IV a use case used to validate the proposed approach is implemented; in section V a discussion is presented and fi nally, in section VI conclusions are drawn and future research directions are signaled.

## item 21

**Claim.** Work in this direction covers decentralised approaches, asset-oriented exchange and data-driven cross-organisation architectures.

**Cited source.** `gleich_asset_2024`, page 2

**Matched passage.**

> Therefore, this paper presents a DPP using asset administration shells (AAS), i.e. a standardized digital representation of an asset [14], to enable standardized, decentralized information  exchange  using  REST  interfaces. Apart from this, the corresponding data model of the developed DPP enables accurate event-based tracking and specification of relevant product information along the whole product lifecycle. On the one hand, this may increase the transparency of products regarding sustainability criteria such as the origin of materials and components following legislative requirements (e.g. Corporate  Sustainability  Due  Diligence  Directive  CSDDD), emissions in the value chain, or usage data. On the other hand, detailed information regarding the input materials, the manufacturing  process, and  the  end  product itself facilitates circular activities and  especially  remanufacturing [15].  To further  guarantee  a  secure  and  decentralized  exchange  and storage of data, the developed DPP is implemented as a service offering within the European data infrastructure project Gaia-X. In contrast to existing proprietary platforms, the data in Gaia-X is stored decentralized at the respective companies and exchanged via common standards and centralized, standardized services, so-called federation services. Furthermore, the sovereignty  and  security  of  the  data  comply  with  European standards [16 -18].

## item 22

**Claim.** *Classification in practice, on real systems:* describes four twins against a fourteen-characteristic framework and is the best available answer to "what do real ones actually look like"; and are the closest published relatives of our demonstrator;,, and are worked examples in beer fermentation, shipboard cranes, operating rooms and hospital wards respectively.

**Cited source.** `kamburjan_greenhousedt_2024`, page 1

**Matched passage.**

> Eduard Kamburjan Riccardo Sieve Chinmayi Prabhu Baramashetru University of Oslo Oslo, Norway {eduard,riccasi,cpbarama}@ifi.uio.no

## item 23

**Claim.** The Digital-Twin-as-a-Service proposal starts from the observation that building a twin is hard partly because so many different assets, models, data sets and services have to be brought together, and proposes a generic platform from which twins are assembled out of reusable components and offered to users as a service, with platform-hosted services that individual twins consume on demand.

**Cited source.** `talasila_realising_2024`, page 1

**Matched passage.**

> Abstract Building a Digital Twin (DT) can be a challenge, in part because of the variety of assets, models, data and services that must be marshalled to satisfy the specific needs of stakeholders. In this chapter, we consider the possibility of a generic platform that allows DTs to be built from reusable components and offered as a service to users. We propose such a platform which we call Digital Twin as a Service (DTaaS) . The DTaaS is sufficiently generic to support DTs spanning multiple modelling and execution paradigms. The chapter compares DT frameworks and discusses the advantage of treating related DTs as a fleet.

## item 24

**Claim.** **13.10.2.** "ISO 23247 is a vocabulary standard -- it defines domains, roles and terms and specifies nothing on the wire, so conforming to it cannot make two systems interoperate; and 'compliant' is a claim we could not verify anyway, since measuring compliance with it is not currently possible.

**Cited source.** `ferko_standardisation_2023`, page 11

**Matched passage.**

> J. Trauer, S. Schweigert-Recksiek, C. Engel, K. Spreitzer, and M. Zimmermann, 'What is a digital twin?-definitions and insights from an industrial case study in technical product development,' in Proceedings of the Design Society: DESIGN Conference , vol. 1. Cambridge University Press, 2020, pp. 757-766.

## item 25

**Claim.** Twin evolution spans changes in the actual twin -- both discontinuous, such as component replacement after a failure, and continuous, such as wear -- and, separately, the twin's own lifecycle as a software system with its own evolution, which the same work argues should be treated as a core principle rather than an afterthought.

**Cited source.** `alskaif_evolution_2025`, page 5

**Matched passage.**

> To enable systematic evolution, EDT must leverage the best practices of software engineering [33], Agile and DevOps ([34], [35]), including: best practices of software architecture to support evolution; integration of the software engineering lifecycle phases in a unified iterative process focused on continuous improvement and evolution; and use of techniques and tools to automate as many software process tasks as possible to enable fast and reliable delivery of software updates. The goal is to make EDT as agile, systematic, and reliable as possible.

## item 26

**Claim.** *Platforms, middleware and deployment:* for the as-a-service framing and its container decomposition, for what middleware actually does in published twins, and for microservice and serverless realisations, and on the edge-to-cloud continuum, and for open-source frameworks, on reusing reference architectures, and with for the industrial-architecture framing of connectivity and the twin-as-middleware pattern.

**Cited source.** `barbone_digital_2024`, page 4

**Matched passage.**

> Package : The package implements the schema for a specified platform, incorporating configuration parameters, requirements, and executable code essential for DT operation. For example, consider a package designed to implement a predictive maintenance DT for an industrial IoT platform. It integrates platform-specific details, such as how declared communication protocols and data formats are implemented with a specific programming language and/or Software architecture (e.g., serverless or microservices) along with specific requirements to guarantee the declared fidelity, such as the need for a GPU for its execution. Internally, it contains the executable code necessary for the DT to operate effectively on the designated platform.

## item 27

**Claim.** The box metaphor is a systems-engineering framing: a box takes inputs, performs operations, and produces outputs, and the colour describes how much of the operation you can see.

**Cited source.** `grieves_digital_2024`, page 25

**Matched passage.**

> Olson, S., & Riordan, D. G. (2012). Engage to excel: Producing one million additional college graduates with degrees in science, technology, engineering, and mathematics. Report to the president. Executive Office of the President.

## item 28

**Claim.** Change the denominator to a 9-hectare irrigated field -- as in the OpenTwins agricultural case built around an irrigation pivot and soil-moisture data -- and water volume becomes a serious metric again.

**Cited source.** `infante_integrating_2024`, page 22

**Matched passage.**

> Vats T, Singh SK, Kumar S, et al. Explainable context-aware IoT framework using human digital twin for healthcare. Multimed Tools Appl . 2023;1-25.

## item 29

**Claim.** *The honest notes, and worth reading in full:* analyses 29 manufacturing twin architectures against ISO 23247 using a literature review, a survey and expert interviews, and is candid about how early adoption is; on incompatible twin-description formats; on incompatible open-source AAS implementations.

**Cited source.** `jacoby_open-source_2023`, page 20

**Matched passage.**

> | AAS     | Asset Administration Shell                                                    |
> |---------|-------------------------------------------------------------------------------|
> | AASX    | Asset Administration Shell Exchange Format                                    |
> | AML     | Automation Markup Language                                                    |
> | API     | Application Programming Interface                                             |
> | ARel    | Annotated Relationship Element                                                |
> | Blob    | Binary large object                                                           |
> | BMBF    | German Federal Ministry of Education and Research                             |
> | CLI     | Command-Line Interface                                                        |
> | CD      | Concept Description                                                           |
> | DT      | Digital Twin                                                                  |
> | DTC     | Digital Twin Consortium                                                       |
> | EDC     | Eclipse Dataspace Connector                                                   |
> | EU      | European Union                                                                |
> | e.V.    | incorporated association, in German: eingetragener Verein                     |
> | FA 3 ST | Fraunhofer Advanced Asset Administration Shell Tools for Digital Twins        |
> | GUI     | Graphical User Interface                                                      |
> | HTTP    | Hypertext Transfer Protocol                                                   |
> | I4.0    | Industry 4.0                                                                  |
> | IDTA    | Industrial Digital Twin Association                                           |
> | IETF    | Internet Engineering Task Force                                               |
> | IOSB    | Fraunhofer Institute of Optronics, System Technologies and Image Exploitation |
> | JSON    | JavaScript Object Notation                                                    |
> | MLP     | Multi Language Property                                                       |
> | MQTT    | Message Queuing Telemetry Transport                                           |
> | NOVAAS  | NOVA Asset Administration Shell                                               |
> | OASIS   | Organization for the Advancement of Structured Information Standards          |
> | OPCUA   | Open Platform Communications Unified Architecture                             |
> | RDF     | Resource Description Format                                                   |
> | Ref     | Reference Element                                                             |
> | Rel     | Relationship Element                                                          |
> | REST    | Representational State Transfer                                               |
> | SDK     | Software Development Kit                                                      |
> | SM      | Submodel                                                                      |
> | SMC     | Submodel Element Collection                                                   |
> | SMT     | Submodel Template                                                             |
> | UI      | User Interface                                                                |
> | URL     | Uniform Resource Locator                                                      |
> | XLS     | Microsoft Excel Spreadsheet                                                   |
> | XML     | Extensible Markup Language                                                    |

## item 30

**Claim.** *Book-length treatments of engineering twins for cyber-physical systems,* the closest fit to this book's angle:, with its chapter of worked case studies and its chapter on advanced services and what-if analysis.

**Cited source.** `fitzgerald_engineering_2024-1`, page 58

**Matched passage.**

> Jonas: This mainly depends on a combination of factors, including how quickly you need to close the loop and how expensive it is to communicate and store data from the PT. If the customer starts asking for SLAs, this will also influence what we need to sense. In general what we sense will depend upon what makes financial sense as well, since both communication and storage of data both have associated costs.

## item 31

**Claim.** Bespoke one-off integration is the field's structural cost problem.

**Cited source.** `niederer_scaling_2021`, page 5

**Matched passage.**

> Digital twins offer clear and exciting short-term benefits in monitoring,  control  and  decision  support;  however,  from  a  long-term perspective, their ubiquitous adoption will offer new applications and another layer of predictive and control capabilities. Once digital twins are ubiquitous and many physical assets or entities are paired with a digital version, twins will be able to be coupled into networks of digital twins (Fig. 3). Pooling data between twins and connecting twins could improve predictions. Digital twins of similar assets or entities could be coupled together, with historical data from older twins providing enhanced predictions for comparable newer twins. Co-located  twins  could  pool  data  to  reduce  uncertainty.  Digital twins  of  physically  connected  systems  could  provide  coupled boundary conditions  for  longer-term  prediction.  Digital  twins  of automated physical systems could link to other static,  automated or living digital twins to enable on-the-fly cooperation and interactions. Ubiquity of digital twins offers another level of monitoring, control and decision support beyond isolated digital twins.

## item 32

**Claim.** A standardisation study captured the same problem from the practitioner side, quoting a survey respondent's complaint that because there is no single definition, "many colleagues mean simulation when referring to DTs", and arguing that the standard ought to supply unified definitions of digital model, shadow and twin.

**Cited source.** `ferko_standardisation_2023`, page 8

**Matched passage.**

> Results from the literature review highlighted that only a few DT architectures implemented FEs of the ISO 23247 RA related to the control and actuation of the OMEs. In the survey, we asked whether this could be interpreted as current architectures proposing digital shadows rather than DTs. We used a dichotomous question (yes or no) sided with an open-ended question for remarks. The majority of the respondents (67%) agreed and some remarked that 'without a bidirectional interaction there is no digital twin' . Interestingly, one respondent said that it reached a similar conclusion during its research: 'I also investigated a large set of publications on DT. Most of them propose digital shadows [...] digital models that receive some measured data, but that do not give any feedback to the physical counterpart' . The respondents that disagreed with the above statement argued that: 'there is no single definition of DT in the scientific community. Hence, many colleagues mean simulation when referring to DTs. That is where this divergence comes from.' . Considering this, we believe that the ISO 23347 standard could and should provide unified definitions of the digital model, shadow, and twin. In addition, for each of them, the standard may identify the subset of FEs in the RA that needs to be implemented. Eventually, we believe that architectures for DTs should implement the FEs responsible for the actuation services.

## item 33

**Claim.** ISO 23247 -- **Borrow the vocabulary, do not claim conformance** -- Its words are useful in the documentation and cost nothing. "Conformant" is unverifiable and would be a claim we cannot support

**Cited source.** `ferko_standardisation_2023`, page 8

**Matched passage.**

> In a similar vein, experts link the lack of support for the Peer interface FE to the maturity of DTs: 'a peer interface with other digital twins is essential to construct a digital twin aggregate' . While more and more research efforts are focusing on investigating interoperability among different DTs, current DT applications focus on one single DT only and not on an ecosystem of DTs: 'many use cases are focusing on single implementations [...] I expect interfaces between digital twins to come later' . Respondents identified several challenges hampering the implementation of the Peer interface FE ranging from the diversity of DT models and interface specifications to the lack of semantic interoperability tools and insights into future requirements. Some of the survey respondents, as well as interviewed experts, mentioned the Asset Administration Shell [30] as a possible solution for standardising communication between DTs: '(in Germany) the Industrial Digital Twin Alliance and the Plattform Industrie 4.0 are specifying a standardised digital representation of assets called the Asset Administration Shell (AAS). AAS addresses exactly this FE. ' . When asked about the need for such a FE, respondents and experts agreed that Peer interface is pivotal when targeting scalability of DTs: 'this is [...] needed for smart and flexible production systems, e.g., by means of agentbased communications approaches [...]' . Besides foreseeing an increasing demand of standardised interfaces, experts also recognise that this would require a global, collaborative effort: 'this is not an issue that any company can solve on its own, but it is a collective effort' . Hence, we believe that the Peer interface FE will be crucial to future DT applications (not limited to a single supplier).

## item 34

**Claim.** *Diagnosis in the field:* for the diagnostic service on an operational floating turbine, and for the same asset validated against a prototype.

**Cited source.** `branlard_digital_2024`, page 1

**Matched passage.**

> A digital twin solution for floating offshore wind turbines validated using a full-scale prototype

## item 35

**Claim.** *Consulted, not drawn on above:* on automated twin testing and detecting performance shift online, on industrialising twin production, and on evolving twins by transfer learning, on model-based DevOps for cyber-physical systems, and for the layered view behind Sec. 14.6.4.

**Cited source.** `combemale_model-based_2023`, page 2

**Matched passage.**

> Social: We anticipate MBDO to increase transparency for factory stakeholders as it can make (i) information about

## item 36

**Claim.** *A worked service set on real hardware:* and show the incubator's services -- monitoring, state estimation, calibration, decision support -- wired together, which is Sec. 11.9 done by somebody else on a different physical twin.

**Cited source.** `oakes_case_2024`, page 44

**Matched passage.**

> Table 12.3: Data channels sensed onboard the R/V Gunnerus.
> 
> | Signal      | Channels                                                                                                          | Unit                                      |
> |-------------|-------------------------------------------------------------------------------------------------------------------|-------------------------------------------|
> | GPS         | Latitude Longitude Surge velocity Sway velocity Course angle Speed over ground                                    | ddmm.mmmm ddmm.mmmm knots knots deg knots |
> | MRU         | Heading angle Heading rate Roll angle Pitch angle Heave displacement Roll rate Pitch rate Heave rate              | deg deg/s deg deg m deg/s deg/s m/s       |
> | Wind sensor | Wind direction Wind speed                                                                                         | deg knots                                 |
> | Thruster    | Port thruster angle Starboard thruster rotational speed Starboard thruster angle Tunnel thruster rotational speed | deg % deg %                               |

## item 37

**Claim.** *Surrogates and reduced-order models:*,, and for the probabilistic-machine-learning side.

**Cited source.** `rasheed_digital_2020`, page 26

**Matched passage.**

> G. Berkooz, P. Holmes, and J. L. Lumley, ''The proper orthogonal decomposition in the analysis of turbulent ows,'' Annu. Rev. Fluid Mech. , vol. 25, no. 1, pp. 539 575, Jan. 1993.

## item 38

**Claim.** *Synchronisation, staleness and lag:* for twinning rate and age of twin as measurable metrics, for time discrepancy as a problem in its own right, for state synchronisation, and for fidelity, synchronisation and integration treated together.

**Cited source.** `wu_comprehensive_2023`, page 7

**Matched passage.**

> The realization of digital twin is mainly through the establishment of digital mirrors (called twin entities) for physical entities, through the integration and fusion of geometry, physics, behaviour and rules of the four-layer model, so that the each twin entity has the functions of evaluation, optimization, prediction, evaluation and other functions. Therefore, the modeling of twin entity is the core component of digital twin technology.

## item 39

**Claim.** This is what the literature means by continual validation: for a twin, validation must be continuous and recalibration triggered when the model stops matching the world, rather than a one-off finished at handover.

**Cited source.** `ali_modeling_2024`, page 11

**Matched passage.**

> 4.2.2. Online and continual validation. Continual validation is the process of continually ensuring a DT, or more concretely the model(s) in the DT, remains a valid representation of their real-world counterpart. When the model becomes invalid, e.g., due to changes in the real-world system, a recalibration is needed to match the DT to the real world once again, as was shown in Stage 2.9 in Figure 5. This is conceptually different from model validation in M&S where, typically, a calibration attempt is performed first, after which the model is subjected to the validation procedure. Once positively validated, the model is generally also assumed ''finished.'' Besides this conceptual difference, there is a high level of similarity between traditional model validation and the validation of models in DTs. As such, the model validation techniques from M&S can largely be carried over. 85 However, one faces several challenges when continually attempting to apply those model validation techniques. They stem from the fact that only the runtime data of the system in operation are available. This leads to the following challenges:

## item 40

**Claim.** You will hear the combination called a **differential-algebraic** system, and it is standard in engineering practice; lumped-parameter system models are routinely formulated either as pure-rate systems or as this combined kind, and equation-based tooling explicitly transforms the implicit combined system before handing it to a numerical solver.

**Cited source.** `hartmann_executable_2022`, page 10

**Matched passage.**

> Future challenges involve the integrity and traceability of the Executable Digital Twin models, connecting directly to the cybersecurity domain [38], including the potential adoption of blockchain concepts [37].

## item 41

**Claim.** Practitioners recognise human-in-the-loop as its own twin *style*, distinct from a plain twin or shadow, and mobility twins have been demonstrated with a human driver deliberately kept in the loop.

**Cited source.** `liu_ai_2025`, page 18

**Matched passage.**

> There is a clear trend in the application domains of DTenabled AI simulation, with networks and robotics accounting for 17 of 22 (77.3%) of the sampled approaches (see Sect. 5.1). These numbers are rather unexpected after the recent cross-domain systematic mapping study on software engineering for digital twins by Dalibor et al. [16], who do not mention these fields as frequent adopters of digital twins [16, Fig. 5]. Granted, robotics might fit the 'manufacturing' in that classification, but the emergence of the networking domain as a top adopter suggests a shift in tonesetters as DT-enabled AI simulation might be growing out of domains different from traditional digital twinning. The strong showing of robotics might be explained by digital twinning being an already adopted technology. The high research activity in networking seems to be a transformative tendency, potentially due to the relative lack of digital twinning impediments [71, Sec. 3.3] in the domain.

## item 42

**Claim.** The pot-and-plant setting is a recognised exemplar for exactly this kind of reasoning -- a documented greenhouse twin uses plants in pots, drying soil, and per-plant sensor streams as its running case, and a closely related mini-greenhouse setup with soil-moisture sensors and pumps appears in work on twin lifecycle management.

**Cited source.** `kamburjan_declarative_2024`, page 5

**Matched passage.**

> Using declarative stages, the transitions between the stages in a lifecycle need not be modeled; it suffices to describe architectural coherence for each stage. A complete model of the lifecycles is not needed, it suffices to provide a declarative characterization of aspects relevant for architectural coherence of the digital twin.

## item 43

**Claim.** *ISO 23247 itself, as used:* is the clearest short analysis and names the Verification, Validation and Uncertainty Quantification (VVUQ) gap; and apply it; builds a component catalogue on it; gives the honest abstraction-level assessment; surveys the proliferation of reference models more generally.

**Cited source.** `heithoff_model-based_2024`, page 33

**Matched passage.**

> Bolender, T., Bürvenich, G., Dalibor, M., Rumpe, B., & Wortmann, A. (2021). Self-adaptive manufacturing with Digital Twins. In 2021 Int. Symp. on SE for Adaptive and Self-Managing Systems (SEAMS) , 2021. IEEE.

## item 44

**Claim.** A review of digital-twin integration, using a smart city as its worked example, names nine integration challenges it considers still outstanding and calls on the community to take them up.

**Cited source.** `combemale_challenges_2025`, page 2

**Matched passage.**

> Abstract -Digital Twins (DTs) are a key technology for smart ecosystems to provide accurate digital representation of their constituents, e.g., smart buildings, farms, transportation, and citizens, as well as synchronization between the digital and the real subject, and the exploration of what-if scenarios and tradeoff reasoning. To cope with emerging complex socio-technical ecosystems, we need to bring DTs together, which is a challenging endeavor. After giving a historical overview of system adaptation, we review the many enabling technologies that can help with DT integration. Using a smart city as an illuminating example to highlight scenarios that require integration of DTs, we discuss a model-based conceptual framework that identifies DT integration strategies and elaborate on nine key integration challenges that still need to be addressed. We call on the DT community to investigate these challenges.

## item 45

**Claim.** *Value and adoption specifically:* on the lean approach this chapter's method is built on, on enablers and barriers, on being realistic about return on investment, and on pilot experience, and for a small-manufacturer case.

**Cited source.** `van_schalkwyk_achieving_2023`, page 9

**Matched passage.**

> Integrating real-time IoT sensor data with GIS technology to create track-andtrace with geofencing capabilities.

## item 46

**Claim.** The demonstrator's closest published relative supports exactly this: the physical twin can be virtualised by replaying recorded data streams, specifically so results can be shared and reproduced.

**Cited source.** `kamburjan_greenhousedt_2024`, page 2

**Matched passage.**

> Approach. The GreenhouseDT exemplar consists of a greenhouse as its physical system and an extensible software architecture that realizes the digital twin. The physical twin is a low-cost alternative to industrial plants, yet it provides exactly the features needed to explore digital twin technology: an easy-to-install physical system with off-the-shelf sensors and actuators, and a modular digital twin software layer. To facilitate the sharing of research results, the physical twin can be virtualized by replaying recorded data streams. The main focus of GreenhouseDT is the modular software architecture of the digital twin, its interconnection with the asset model of the physical twin, and the use of simulation models for prediction. The core of the software architecture of GreenhouseDT consists of an external self-adaptive system which includes a knowledge base that formalizes the asset model of the physical twin, and support for model-based predictions; we here use simulation models for simplicity. We assume that we are given simulation models that correspond to the different entities of the asset model (these decide the granularity of the architectural self-adaptation, discussed below). Sensor data (e.g., from humidity sensors) connect the digital twin to the greenhouse; these are stored in a time-series database which can be queried from the digital twin. The managing subsystem of the digital twin uses model-based predictions to decide how to control the actuators of the managed subsystem; we use a watering pump as an example of an actuator in the greenhouse.

## item 47

**Claim.** **GreenhouseDT.** A greenhouse exemplar built around a knowledge graph that records how the physical system is structured *and how that structure changes*, with plants that move between shelves.

**Cited source.** `kamburjan_greenhousedt_2024`, page 1

**Matched passage.**

> Digital twins also need to adapt to changes in the structure of the physical assets, as they evolve over time; e.g., the twinned physical assets may pass through different stages of an engineering life cycle: commissioning, via operations, to decommissioning. Consequently, the digital twin itself (i.e., the managing subsystem of the self-adaptive system) is also necessarily self-adaptive; the structure and capabilities of the physical assets evolve over time. This architectural self-adaptation (or structural self-adaptation [9]) differs from behavior self-adaptation , and it is recommended to separate these concerns into different self-adaptive layers [3]. For digital twins, behavioral self-adaptation amounts to adjusting the behavior of the physical twin, whereas architectural self-adaptation corresponds to reconfiguring the digital twin itself to reflect changes in the structure and requirements of the twinned assets.

## item 48

**Claim.** *Risk and trust:* for explainability in industrial settings, for the twin security landscape including attacks on learned models, and for the clearest statement that one-off credibility assessment does not transfer to data-driven models.

**Cited source.** `trivedi_explainable_2024`, page 29

**Matched passage.**

> 'Germany's human-centred approach to AI is inclusive, evidence-based and capacity-building.' Accessed: Jan. 28, 2023. [Online]. Available: https://oecd.ai/en/wonk/germany-takes-aninclusive-and-evidence-based-approach-for-capacity-building-anda-human-centred-use-of-ai

## item 49

**Claim.** Related work takes the same system further into semantic self-adaptation.

**Cited source.** `kamburjan_declarative_2024`, page 10

**Matched passage.**

> In future work, we plan to consider dynamically changing declarative groups, i.e., allowing groups and requirements to evolve in response to, e.g., changing regulations, as well as hierarchical assets and groups that describe requirements for sets of assets by the further exploitation of runtime models.

## item 50

**Claim.** Fatigue monitoring of North Sea platforms has been done on an industrial basis with a twin approach, and wind-turbine prognostics is among the standard cited applications.

**Cited source.** `pezeshki_state_2023`, page 4

**Matched passage.**

> Table 1. List of signal processing methods compared in the study by Qarib and Adeli (2016)
> 
> | Non-parametric                                                                   | Parametric                                                                                                    |
> |----------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
> | Fourier transform Periodogram estimate of power spectral density WT EMD with HHT | Music EWT Pony method Matrix pencil method Estimation of signal parameters by rotational invariance technique |

## item 51

**Claim.** **The interoperability work around it is real and worth knowing exists**, including proposals for mapping between OPC UA and the Asset Administration Shell.

**Cited source.** `picone_harmonizing_2025`, page 8

**Matched passage.**

> In [17], a six-layer architecture for DTs is proposed, where the first two layers are dedicated to the PT (sensors and controllers), and the third to the fifth layers manage data storage, communication, and cloud integration. However, the architecture lacks a clear process for how these layers communicate with each other or how changes in the DT state are captured and updated across the layers. Similarly, in the Generic DT Architecture (GDTA) [21], a layered approach is used, where the DT state is computed at the information layer through data processing pipelines. However, this architecture does not incorporate an explicit mechanism for the integration of the different components of the DT, leaving gaps in how the evolving state of the DT is managed. Other models explicitly reference multiple components that contribute to the definition of the DT state. For example, in [1] and similarly in [13], the authors propose multi-layer DT architecture for cyberphysical systems (CPS), where DT state changes are driven by multiple functional units. However, in these models, the outputs of each unit are not mediated by a shadowing process, which would ensure consistency and synchronization of the DT state and lifecycle management. Our approach addresses these issues by proposing a more structured lifecycle for DTs, where the communication and interaction between the different components are clearly defined. By introducing a shadowing process that orchestrates the different models, we ensure that the DT state remains consistent and accurately reflects the evolving state of the PT.

## item 52

**Claim.** *Consulted, not drawn on above:* for how a distributed-simulation standard handles participants with different notions of time, on consistency checks including step sizes inside a verification process, on simulators as training environments, for hardware-in-the-loop in the twin vocabulary, on augmenting twin models with behaviour, and on checking at runtime that co-simulation master algorithms are being used correctly.

**Cited source.** `lehner_pattern_2023`, page 16

**Matched passage.**

> Addressing behavioral models for Digital Twins. The need for the availability of behavioral models in DT systems is becoming increasingly important. Rovere et al. [27] outline a supporting infrastructure for managing DTs, emphasizing the relevance of behavioral models for enabling simulations and the accessibility of these models throughout the factory lifecycle. Building on the DEVS formalism, Niyonkuru & Wainer [28] present an environment that includes DTs but also foresees a physical model to support simulations and study behavior under real-world conditions, e.g., time constraints in real-time systems. Using Reinforcement Learning, a model was learned from data collected at runtime and used to optimize behavior [29, 30]. Stary et al. [31] take a human-centric view of DTs by proposing behavioral models for capturing components and interactions in a Cyber-Physical System (CPS). They provide a subject-oriented approach for modeling both the structure and behavioral aspects of the system, aiming to provide a unified view for the various stakeholders involved in the design process of DTs. Tekinerdogan and Verdouw present a design pattern catalog for developing DTs [26]. Different from our mapping of specific object behaviors, the authors define the general behavior of DTs using Sequence Diagrams. In [32], Verdouw et al. discuss the typologies of different types of DTs which also utilize behavioral models in the context of smart farming. In contrast to our approach, the mentionedworksaddresstherequirementsforDTsinterms of planning, validation, and implementation at a conceptual level rather than concrete blueprints for capturing DTs in existing DT platforms.

## item 53

**Claim.** **TwinOps** couples model-based engineering, DevOps and digital twins: generating and deploying a system, its simulation and its twin through one pipeline, and collecting runtime execution traces to compare against the engineering artifacts -- model simulation and analysis -- so that diagnosis is rapid. **The idea worth taking is that comparison**, and this book has been building it since Chapter 1: the residual is a runtime trace compared against a model, and Sec. 14.2.3's simulate-the-physical-twin is the same comparison run the other way.

**Cited source.** `hugues_twinops_2020`, page 4

**Matched passage.**

> Finally, the same data can lead to model improvements. For instance, timing traces can be compared to theoretical time budgets used for latency or scheduling analyses, sensor biases can lead to a different mitigation policy, for instance, to force specific recalibration. Hence, such a comparison between execution traces and the initial model can inform updates of the system to improve its accuracy.

## item 54

**Claim.** *Consulted, not drawn on above:* on visualisation as a service (Chapter 11), on platforms (Chapter 12), on human-in-the-loop as a named twin style, on mobility twins with a human driver, and on how other authors pin the same definitions, and on keeping models current, on domain-specific readings of the term, and on composing twins (Chapter 15), on adoption barriers, and on the standards landscape (Chapter 13).

**Cited source.** `noauthor_summary_nodate`, page 39

**Matched passage.**

> Perform the SME compatibility test for the identified standards. Change2Twin focusses on SMEs, also with respect to their access to relevant standards. Small Business Standards (SBS) is a European non-profit association co-financed by the European Commission and EFTA Member States to represent and defend small and medium-sized enterprises' interests in the standardisation process at European and international levels. SBS has developed a test that evaluates the SME friendliness of standards:

## item 55

**Claim.** This is the pattern behind diagnostic twins for floating offshore wind, where the twin monitors and analyses asset condition to detect anomalies on equipment that is expensive and slow to visit, and behind fault-diagnosis twins for rotating equipment.

**Cited source.** `stadtmann_diagnostic_2024`, page 8

**Matched passage.**

> T Generator Rotor

## item 56

**Claim.** The physical object changes the digital object, and the digital object changes the physical object.

**Cited source.** `kritzinger_digital_2018`, page 1

**Matched passage.**

> Abstract: The  Digital  Twin (DT) is commonly known as a key enabler for the digital transformation, however, in literature is no common understanding concerning this term. It is used slightly different over the disparate disciplines. The aim of this paper is to provide a categorical literature review of the DT in manufacturing  and  to  classify  existing  publication  according  to  their  level  of  integration  of  the  DT. Therefore, it is distinct between Digital Model (DM), Digital Shadow (DS) and Digital Twin. The results are showing, that literature concerning the highest development stage, the DT, is scarce, whilst there is more literature about DM and DS. Abstract: The  Digital  Twin (DT) is commonly known as a key enabler for the digital transformation, however, in literature is no common understanding concerning this term. It is used slightly different over the disparate disciplines. The aim of this paper is to provide a categorical literature review of the DT in manufacturing  and  to  classify  existing  publication  according  to  their  level  of  integration  of  the  DT. Therefore, it is distinct between Digital Model (DM), Digital Shadow (DS) and Digital Twin. The results are showing, that literature concerning the highest development stage, the DT, is scarce, whilst there is Abstract: The  Digital  Twin (DT) is commonly known as a key enabler for the digital transformation, however, in literature is no common understanding concerning this term. It is used slightly different over the disparate disciplines. The aim of this paper is to provide a categorical literature review of the DT in manufacturing  and  to  classify  existing  publication  according  to  their  level  of  integration  of  the  DT. Therefore, it is distinct between Digital Model (DM), Digital Shadow (DS) and Digital Twin. The results are showing, that literature concerning the highest development stage, the DT, is scarce, whilst there is more literature about DM and DS. Abstract: The  Digital  Twin (DT) is commonly known as a key enabler for the digital transformation, however, in literature is no common understanding concerning this term. It is used slightly different over the disparate disciplines. The aim of this paper is to provide a categorical literature review of the DT in manufacturing  and  to  classify  existing  publication  according  to  their  level  of  integration  of  the  DT. Therefore, it is distinct between Digital Model (DM), Digital Shadow (DS) and Digital Twin. The results are showing, that literature concerning the highest development stage, the DT, is scarce, whilst there is Abstract: The  Digital  Twin (DT) is commonly known as a key enabler for the digital transformation, however, in literature is no common understanding concerning this term. It is used slightly different over the disparate disciplines. The aim of this paper is to provide a categorical literature review of the DT in manufacturing  and  to  classify  existing  publication  according  to  their  level  of  integration  of  the  DT. Therefore, it is distinct between Digital Model (DM), Digital Shadow (DS) and Digital Twin. The results are showing, that literature concerning the highest development stage, the DT, is scarce, whilst there is Austria (Tel: +43-676-888-61605; e-mail: werner.kritzinger@fraunhofer.at). Abstract: The  Digital  Twin (DT) is commonly known as a key enabler for the digital transformation, however, in literature is no common understanding concerning this term. It is used slightly different over the disparate disciplines. The aim of this paper is to provide a categorical literature review of the DT in manufacturing  and  to  classify  existing  publication  according  to  their  level  of  integration  of  the  DT. Therefore, it is distinct between Digital Model (DM), Digital Shadow (DS) and Digital Twin. The results

## item 57

**Claim.** Federated approaches let multiple parties contribute to a model without pooling raw data, with communication-efficient variants for twin settings. **If the answer is no, this is complexity with no purchaser**, and it is the one of the three most often adopted for reasons other than the question.

**Cited source.** `lu_communication-efficient_2021`, page 12

**Matched passage.**

> Ke Zhang received the Ph.D. degree from the University of Electronic Science and Technology of China, Chengdu, China, in 2017.

## item 58

**Claim.** *Consulted, not drawn on above:* on visualisation as a service (Chapter 11), on platforms (Chapter 12), on human-in-the-loop as a named twin style, on mobility twins with a human driver, and on how other authors pin the same definitions, and on keeping models current, on domain-specific readings of the term, and on composing twins (Chapter 15), on adoption barriers, and on the standards landscape (Chapter 13).

**Cited source.** `parle_comparative_2024`, page 10

**Matched passage.**

> | Digital Twin Platform   | Platform Provider   | Description                                                                                                                                                                                                              | Features                                                                                                           |
> |-------------------------|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
> | Apollo Protocol         | IET                 | Apollo Protocol provides a cross-sector framework for digital twins to standardise definitions, methodologies, and protocols, enabling collaboration and unlocking significant benefits [111].                           | Aligning the value chain. Circular supply chains. Performance optimisation. Human capital management.              |
> | Ditto                   | Eclipse             | Eclipse Ditto is an open-source framework for building digital twins of internet-connected devices [112].                                                                                                                | Various formats of data can be accepted. Structured API for things. Incoming and outgoing data can be transformed. |
> | iTwin.js                | Bentley             | iTwin.js is designed to be both flexible and open for easy access, leverage, and integration of digital twins with other systems [113].                                                                                  | Data aggregation. Data visualisation. Data Analysis.                                                               |
> | Azure IoT Explorer      | Microsoft           | Azure IoT Explorer is a graphical tool for interacting with IoT hub devices [114].                                                                                                                                       | IoT Hub connection. Device CRUD & Device functionalities.                                                          |
> | DigitalLab              | OpenCell            | OpenCell's Digital Lab cloud platform enables to plan and execute biological workflows and collect the associated equipment and metadata for better quality assurance and reproducibility of biological protocols [115]. | Plan a workflow. Lab monitoring. Data regulation.                                                                  |
> | Babylon.js Digital Twin | Babylon.js          | Babylon.js is a fully featured, open-source rendering engine that makes it easy to create interactive 3D digital twin experiences on the web [116].                                                                      | IoT data visualisation. Monitor and optimise the performance of physical systems.                                  |

## item 59

**Claim.** That distinction -- a range for what you have measured, an envelope for what you have not -- is the honest core of uncertainty quantification, and it is why the national-academies review of digital twins treats VVUQ as a foundational research need rather than a solved procedure, recommending it be made an integral part of new twin programmes rather than a stage at the end.

**Cited source.** `committee_on_foundational_research_gaps_and_future_directions_for_digital_twins_foundational_2024`, page 77

**Matched passage.**

> Integrated  simulation  of  blood  flow  through  the  cardiac  system  involves  a range of parameters. Models can capture genetic base characteristics, genetic variations,  gene  expression,  and  molecular  interactions  at  the  cellular  and  tis- sue  levels  to  understand  how  specific  genetic  factors  influence  physiological processes and disease susceptibility. Structural information collected by imaging technology  (e.g.,  magnetic  resonance  imaging,  computed  tomography  scans) provides anatomical orientation of chambers, valves, and major blood vessels. Electrical activity of the heart captures the generation and propagation of electrical signals that coordinate the contraction of cardiac muscle cells. Models based on the Hodgkin-Huxley equations or other electrophysiological models are utilized to replicate the cardiac action potential and activation patterns. Mechanical aspects involve  modeling  the  contraction  and  relaxation  of  cardiac  muscle  cells  using parameters  such  as  ventricular  pressure,  myocardial  deformation,  and  valve dynamics. Hemodynamic models use computational fluid dynamics to simulate blood flow within the cardiac system (blood pressure, flow rates, and resistance), accounting for the interaction between the heart and the vasculature. Techniques can be employed to simulate blood flow patterns. Modeling the interaction be- tween blood flow and the heart tissue captures the effects of fluid-structure inter- action. The digital twin can incorporate regulatory mechanisms that control heart rate, blood pressure, and other physiological variables that maintain homeostasis and  response  mechanisms.  However,  each  of  these  parameters  is  subject  to multiple uncertainties: physiological or genetic parameters may vary between indi- viduals; input data may be unreliable (e.g., imaging resolution); and experimental validation may contain measurement noise or other capture limitations.

## item 60

**Claim.** *Hybrid mechanics:* on physics-informed loss functions as the common realisation, for a worked white-box-plus-black-box combination against live data, and with for multi-fidelity and surrogate-assisted approaches in civil and structural settings.

**Cited source.** `thelen_comprehensive_2022`, page 50

**Matched passage.**

> Lu Q, Parlikad AK, Woodall P, Don Ranasinghe G, Xie X, Liang Z, Konstantinou E, Heaton J, Schooling J (2020a) Developing a digital twin at building and city levels: case study of west Cambridge campus. J Manag Eng 36(3):05020004

## item 61

**Claim.** Smart-city twin work provides real municipal framings for scenarios of exactly this kind -- energy, mobility, water -- and evidence-based decision making as the stated goal; architecture-pattern catalogues for agriculture and food systems offer a structured way to think about the systems side once the value case is settled.

**Cited source.** `mckee_discs_2024`, page 23

**Matched passage.**

> Table 3.4 List of capabilities across scenarios 2-4
> 
> | Scenario 2   | Scenario 2                                        | Scenario 3   | Scenario 3                        | Scenario 4   | Scenario 4                        |
> |--------------|---------------------------------------------------|--------------|-----------------------------------|--------------|-----------------------------------|
> | No           | Capabilities                                      | No           | Capabilities                      | No           | Capabilities                      |
> | 1            | Data Acquisition and Ingestion                    | 1            | Data Acquisition and Ingestion    | 1            | Data Acquisition and Ingestion    |
> | 2            | Data Streaming                                    | 2            | Data Streaming                    | 2            | Data Streaming                    |
> | 3            | Data Transformation and Wrangling                 | 5            | Batch Processing                  | 4            | Data Contextualization            |
> | 4            | Data Contextualization                            | 8            | Data Aggregation                  | 6            | Real-time processing              |
> | 5            | Batch Processing                                  | 10           | Ontology Management               | 11           | Digital Twin Model Repository     |
> | 6            | Real-time processing                              | 13           | Temporal (Time Series) Data Store | 14           | Data Storage and Archive Services |
> | 7            | Data Pub/Sub                                      | 14           | Data Storage and Archive Services | 22           | API Services                      |
> | 8            | Data Aggregation                                  | 19           | OT/IoT system integration         | 24           | Command and Control               |
> | 10           | Ontology Management                               | 20           | Digital Twin Integration          | 25           | Orchestration                     |
> | 11           | Digital Twin Model Repository                     | 22           | API Services                      | 26           | Alerts and Notification           |
> | 13           | Temporal (Time Series) Data Store                 | 24           | Command and Control               | 28           | Data Analysis and Analytics       |
> | 14           | Data Storage and Archive Services                 | 26           | Alerts and Notification           | 29           | Prediction                        |
> | 15           | Simulation Model Repository                       | 28           | Data Analysis and Analytics       | 33           | Simulation                        |
> | 17           | Enterprise system integration                     | 29           | Prediction                        | 35           | Prescriptive Recommendations      |
> | 19           | OT/IoT system integration                         | 33           | Simulation                        | 36           | Business Rules                    |
> | 20           | Digital Twin Integration                          | 36           | Business Rules                    | 41           | Real-time Monitoring              |
> | 21           | Collaboration platform integration                | 39           | Basic Visualization               | 45           | Dashboards                        |
> | 22           | API Services                                      | 42           | Entity Relationship Visualization | 53           | System Monitoring and Alerting    |
> | 23           | Edge AI and Intelligence                          | 45           | Dashboards                        | 54           | Logging                           |
> | 25           | Orchestration                                     |              |                                   | 58           | Security                          |
> | 26           | Alerts and Notification                           |              |                                   | 59           | Privacy                           |
> | 27           | Reporting                                         |              |                                   | 60           | Safety                            |
> | 28           | Data Analysis and Analytics                       |              |                                   | 61           | Reliability                       |
> | 29           | Prediction                                        |              |                                   | 62           | Resilience                        |
> | 30           | Machine Learning (ML)                             |              |                                   |              |                                   |
> | 31           | Artificial Intelligence                           |              |                                   |              |                                   |
> | 32           | Federated Learning                                |              |                                   |              |                                   |
> | 33           | Simulation                                        |              |                                   |              |                                   |
> | 34           | Mathematical Analytics (Engineering Calculations) |              |                                   |              |                                   |
> | 35           | Prescriptive                                      |              |                                   |              |                                   |
> | 36           | Business Rules                                    |              |                                   |              |                                   |

## item 62

**Claim.** Twin platform surveys track *warm startup time* as a measurable property: the time for a twin to resume from a partially initialised or suspended state, where lower is better for fault tolerance and downtime.

**Cited source.** `duran_toward_2026`, page 22

**Matched passage.**

> Warm startup time: It is the time required for a DT to resume operation from a partially initialised or suspended state. Lower warm startup times enhance fault tolerance and reduce service downtime [163].

## item 63

**Claim.** In the reported analysis of General Electric's D11 steam-turbine twins, per-component predictive cost evaluation is what makes plant-wide cost control approachable -- balancing revenue against maintenance cost across a fleet rather than one machine at a time.

**Cited source.** `jiang_industrial_2021`, page 1

**Matched passage.**

> Author for correspondence:

## item 64

**Claim.** In twin practice these are described as models that reproduce the input-output relationship from sampled data, of which the simplest example is a linear regression, and they are reached for exactly when the underlying physics or principles are not fully available.

**Cited source.** `jiang_industrial_2021`, page 12

**Matched passage.**

> DT of an ultrahigh-voltage converter station, located in Hunan, China [44].

## item 65

**Claim.** *Consulted, not drawn on above:* on visualisation as a service (Chapter 11), on platforms (Chapter 12), on human-in-the-loop as a named twin style, on mobility twins with a human driver, and on how other authors pin the same definitions, and on keeping models current, on domain-specific readings of the term, and on composing twins (Chapter 15), on adoption barriers, and on the standards landscape (Chapter 13).

**Cited source.** `dittler_agent-based_2022`, page 6

**Matched passage.**

> Järvenpää E., Siltala N. & Lanz M. (2016). Formal resource and capability descriptions supporting rapid reconfiguration of assembly systems. In 2016 IEEE International symposium on assembly and manufacturing (ISAM). Symposium conducted at the meeting of IEEE.

## item 66

**Claim.** The manufacturing framework organises a twin into four interconnected domains -- the observable manufacturing domain holding the real elements, the device communication domain holding sensors and actuators, the digital twin domain, and the user domain -- refined into *functional entities* including a data collection sub-entity and a device control sub-entity, plus a cross-system entity spanning the others.

**Cited source.** `anwer_developing_2025`, page 16

**Matched passage.**

> 4.3.3.22. Predictive maintenance and PHM. Van Dinter et al. [49]. developed and evaluated a reference architecture using UML diagrams based on the feature model. Negri et al. [166]. addressed the ongoing challenges in production scheduling under uncertainty by proposing a framework that exploits the DT synchronisation with health assessment models. Toothman et al. [235]. introduced a DTbased framework for standardised communication and resource organisation in health monitoring, featuring a reusable state-based model of mechanical system health. Huang et al. [93]. proposed a DTdriven anomaly detection framework for real-time health monitoring and anomaly prediction in industrial systems, leveraging edge AI for high-performance detection in a dynamic edge/cloud network. Marquez et al. [155]. designed a condition-based maintenance application for train axle bearings using a generic framework for digital maintenance management based on DT. Aivaliotis et al. [6]. developed a methodology for advanced physics-based modelling to enable DT in predictive maintenance. Ghosh et al. [70]. highlighted the role of DTs in autonomous monitoring and troubleshooting in smart manufacturing, developing a sensor signal-based digital twin for intelligent machine tools. Ghosh et al. [70]. underscored the role of DTs in enabling machine tools to autonomously monitor and troubleshoot. This research proposes a sensor signal-based DT for intelligent machine tools.

## item 67

**Claim.** *Hybrid mechanics:* on physics-informed loss functions as the common realisation, for a worked white-box-plus-black-box combination against live data, and with for multi-fidelity and surrogate-assisted approaches in civil and structural settings.

**Cited source.** `torzoni_deep_2023`, page 1

**Matched passage.**

> Extreme loading conditions and materials aging in civil structures are stressing the need for SHM procedures, to detect and identify structural conditions showing a drift from the damage-free baseline. Vibration-based SHM techniques investigate the structural health by recording and analyzing the vibration response of the monitored structure, e.g., in terms of acceleration or displacement time histories.

## item 68

**Claim.** *Do not assume a reference architecture is adopted.* ISO 23247 adoption is early and compliance is not yet measurable.

**Cited source.** `ferko_standardisation_2023`, page 8

**Matched passage.**

> In a similar vein, experts link the lack of support for the Peer interface FE to the maturity of DTs: 'a peer interface with other digital twins is essential to construct a digital twin aggregate' . While more and more research efforts are focusing on investigating interoperability among different DTs, current DT applications focus on one single DT only and not on an ecosystem of DTs: 'many use cases are focusing on single implementations [...] I expect interfaces between digital twins to come later' . Respondents identified several challenges hampering the implementation of the Peer interface FE ranging from the diversity of DT models and interface specifications to the lack of semantic interoperability tools and insights into future requirements. Some of the survey respondents, as well as interviewed experts, mentioned the Asset Administration Shell [30] as a possible solution for standardising communication between DTs: '(in Germany) the Industrial Digital Twin Alliance and the Plattform Industrie 4.0 are specifying a standardised digital representation of assets called the Asset Administration Shell (AAS). AAS addresses exactly this FE. ' . When asked about the need for such a FE, respondents and experts agreed that Peer interface is pivotal when targeting scalability of DTs: 'this is [...] needed for smart and flexible production systems, e.g., by means of agentbased communications approaches [...]' . Besides foreseeing an increasing demand of standardised interfaces, experts also recognise that this would require a global, collaborative effort: 'this is not an issue that any company can solve on its own, but it is a collective effort' . Hence, we believe that the Peer interface FE will be crucial to future DT applications (not limited to a single supplier).

## item 69

**Claim.** *Scale as a research problem:* on moving twins from the artisanal to the industrial, which is the reference Chapter 1 parked for here and which names validation speed as the binding constraint; on the open agenda, including at fleet scale.

**Cited source.** `niederer_scaling_2021`, page 7

**Matched passage.**

> Liebeck, R. H. Design of the blended wing body subsonic transport. J. Aircraft 41 , 10-25 (2004).

## item 70

**Claim.** Its practical value is breadth: a broad span of modelling and simulation tools support it and can export models as FMUs, and it is what open twin frameworks build their co-simulation on.

**Cited source.** `infante_integrating_2024`, page 7

**Matched passage.**

> FMI simulation : This simulation service adheres to the FMI standard, used in many different software and frameworks. FMI provides a standardized interface for exchanging simulation models and data between different simulation tools and environments. The FMI standard runs FMUs, which are the packaged models of simulation previously developed. It allows running different simulation models that were designed to be used in multiple frameworks. By supporting FMI-based simulations, the digital twin platform ensures compatibility with a wide range of simulation models developed using FMI-compliant tools. In order to accommodate the varying configurations and variables present in each FMU, the service has been designed to offer flexibility in configuring multiple parameters. The following are the configurable parameters available in the service:

## item 71

**Claim.** Chapter 5 gave the loop: load, initialise and exchange initial outputs, set time and step, exchange values, advance, repeat.

**Cited source.** `abbiati_modelling_2024`, page 10

**Matched passage.**

> Having defined the geometry of the model, the next step is to associate some specific physics to each portion of the model domain. Here, the term physics refers to the first principle laws that describe the spatio-temporal evolution of the relevant solution fi elds of the state variables. The latter, for the incubator example, are temperature, pressure and velocity for the air, but only temperature for the Styrofoam ™ box. Mathematical modelling of such physics relies on continuum mechanics [36], which is a branch of mechanics that deals with the mathematical description of materials as a continuous system rather than as set of discrete particles. In principle, mass, momentum and energy conservation laws together with constitutive laws are used to formulate PDEs that describe the physics of a material. For the specific case of the incubator, one has to distinguish between the box and the air volume.

## item 72

**Claim.** That is not a compromise, it is the design, and it is where a great deal of current practice sits.

**Cited source.** `rasheed_digital_2020`, page 28

**Matched passage.**

> M. V. Tabib, O. M. Lłvvik, K. Johannessen, A. Rasheed, E. Sagvolden, and A. M. Rustad, ''Discovering thermoelectric materials using machine learning: Insights and challenges,'' in Arti cial Neural Networks and Machine Learning-ICANN 2018 , V. K·rkovÆ, Y. Manolopoulos, B. Hammer, L. Iliadis, and I. Maglogiannis, Eds. Cham, Switzerland: Springer, 2018, pp. 392 401.

## item 73

**Claim.** It has its own systematic literature, its own reference architectures, and its own overviews.

**Cited source.** `zhong_overview_2023`, page 21

**Matched passage.**

> The authors declare no conflict of interest.

## item 74

**Claim.** This is the difference Sec. 7.4.7 drew from, stated as a document requirement.

**Cited source.** `ali_modeling_2024`, page 16

**Matched passage.**

> Kim G, Humble J, Debois P, et al. The DevOps handbook: how to create world-class agility, reliability, & security in technology organizations . Portland, OR: IT Revolution Press, 2021.

## item 75

**Claim.** *Consulted, not drawn on above:*, and on system-level and interoperability framings, and on distributed twin infrastructure.

**Cited source.** `marah_re-engineering_2025`, page 12

**Matched passage.**

> 4 Modelling and Engineering Federated Digital Twins

## item 76

**Claim.** *Consulted, not drawn on above:* on how platforms present twins -- the reference Chapter 2 parked for this chapter -- and on further framework comparisons, on twins as microservices, and on the platform properties a buyer should be able to measure.

**Cited source.** `wermann_ktwin_2024`, page 30

**Matched passage.**

> AirNow.gov - Home of the U.S. Air Quality Index. Air quality index (aqi) basics [online] (2023) [cited 2023-11-21].

## item 77

**Claim.** Reviews of the field consistently report finding more published work on digital models and digital shadows than on digital twins proper, which is a fair reflection of where value is actually being captured rather than a criticism of the field.

**Cited source.** `kritzinger_digital_2018`, page 1

**Matched passage.**

> In today's highly competitive markets, where mass customization of products and a rising importance of software components are presenting new challenges: digitalization  in  manufacturing  is  seen  as  an  opportunity  to achieve higher levels of productivity. (Uhlemann  et  al. 2017b) The digital technologies, also known as Industry 4.0 technologies, allow easy integration of interconnected intelligent  components  inside  the  shopfloor.  (Negri  et  al. 2017) These technologies  allow  a  remotely  sense,  real-time monitoring and control of devices and cyber physical production elements across network infrastructures and therefore provide a more direct integration and synchronization from the physical to the virtual world. (Negri et al. 2017; Lee et al. 2015) In today's highly competitive markets, where mass customization of products and a rising importance of software components are presenting new challenges: digitalization  in  manufacturing  is  seen  as  an  opportunity  to achieve higher levels of productivity. (Uhlemann  et  al. 2017b) The digital technologies, also known as Industry 4.0 technologies, allow easy integration of interconnected intelligent  components  inside  the  shopfloor.  (Negri  et  al. 2017) These technologies  allow  a  remotely  sense,  real-time monitoring and control of devices and cyber physical production elements across network infrastructures and therefore provide a more direct integration and synchronization from the physical to the virtual world. (Negri In today's highly competitive markets, where mass customization of products and a rising importance of software components are presenting new challenges: digitalization  in  manufacturing  is  seen  as  an  opportunity  to achieve higher levels of productivity. (Uhlemann  et  al. 2017b) The digital technologies, also known as Industry 4.0 technologies, allow easy integration of interconnected intelligent  components  inside  the  shopfloor.  (Negri  et  al. 2017) These technologies  allow  a  remotely  sense,  real-time monitoring and control of devices and cyber physical production elements across network infrastructures and therefore provide a more direct integration and synchronization from the physical to the virtual world. (Negri et al. 2017; Lee et al. 2015) In today's highly competitive markets, where mass customization of products and a rising importance of software components are presenting new challenges: digitalization  in  manufacturing  is  seen  as  an  opportunity  to achieve higher levels of productivity. (Uhlemann  et  al. 2017b) The digital technologies, also known as Industry 4.0 technologies, allow easy integration of interconnected intelligent  components  inside  the  shopfloor.  (Negri  et  al. 2017) These technologies  allow  a  remotely  sense,  real-time monitoring and control of devices and cyber physical production elements across network infrastructures and therefore provide a more direct integration and synchronization from the physical to the virtual world. (Negri et al. 2017; Lee et al. 2015) In today's highly competitive markets, where mass customization of products and a rising importance of software components are presenting new challenges: digitalization  in  manufacturing  is  seen  as  an  opportunity  to achieve higher levels of productivity. (Uhlemann  et  al. 2017b) The digital technologies, also known as Industry 4.0 technologies, allow easy integration of interconnected intelligent  components  inside  the  shopfloor.  (Negri  et  al. 2017) These technologies  allow  a  remotely  sense,  real-time monitoring and control of devices and cyber physical production elements across network infrastructures and therefore provide a more direct integration and synchronization from the physical to the virtual world. (Negri 1. INTRODUCTION In today's highly competitive markets, where mass customization of products and a rising importance of software components are presenting new challenges: digitalization  in  manufacturing  is  seen  as  an  opportunity  to achieve higher levels of productivity. (Uhlemann  et  al. 2017b) The digital technologies, also known as Industry 4.0 technologies, allow easy integration of interconnected intelligent  components  inside  the  shopfloor.  (Negri  et  al. 2017) These technologies  allow  a  remotely  sense,  real-time monitoring and control of devices and cyber physical production elements across network infrastructures and therefore provide a more direct integration and

## item 78

**Claim.** *Open source and exemplars:* implements the incubator across five frameworks; and are the incubator's own treatments; and are GreenhouseDT;, and are working open frameworks.

**Cited source.** `robles_opentwins_2023`, page 5

**Matched passage.**

> Message-oriented middleware

## item 79

**Claim.** *Why the hardware stages are the hard ones:*, an interview study of CI/CD practice for cyber-physical systems.

**Cited source.** `zampetti_continuous_2023`, page 1

**Matched passage.**

> Continuous Integration and Delivery Practices for Cyber-Physical Systems: An Interview-Based Study

## item 80

**Claim.** The literature is correspondingly focused on enablers and barriers to getting twins into the plant at all, and on where value shows up: predictive cost evaluation per component and plant-wide cost control in power generation, reference architectures for maintenance, and platform selection for specific goals such as net-zero targets.

**Cited source.** `parle_comparative_2024`, page 14

**Matched passage.**

> TABLE IX: MULTI-CRITERIA DECISION-MAKING FOR COMMERCIAL DIGITAL TWIN PLATFORMS.
> 
> | Digital Twin Platform                      | Features 1 - Energy Monitoring and Carbon Reduction 2 - Asset Monitoring and Management 3 - Process Optimisation and Operational Efficiency 4 - Data Visualisation 5 - Data Analysis and Modelling   | Features 1 - Energy Monitoring and Carbon Reduction 2 - Asset Monitoring and Management 3 - Process Optimisation and Operational Efficiency 4 - Data Visualisation 5 - Data Analysis and Modelling   | Features 1 - Energy Monitoring and Carbon Reduction 2 - Asset Monitoring and Management 3 - Process Optimisation and Operational Efficiency 4 - Data Visualisation 5 - Data Analysis and Modelling   | Features 1 - Energy Monitoring and Carbon Reduction 2 - Asset Monitoring and Management 3 - Process Optimisation and Operational Efficiency 4 - Data Visualisation 5 - Data Analysis and Modelling   | Features 1 - Energy Monitoring and Carbon Reduction 2 - Asset Monitoring and Management 3 - Process Optimisation and Operational Efficiency 4 - Data Visualisation 5 - Data Analysis and Modelling   | WSM Score   |
> |--------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
> |                                            | 1                                                                                                                                                                                                    | 2                                                                                                                                                                                                    | 3                                                                                                                                                                                                    | 4                                                                                                                                                                                                    | 5                                                                                                                                                                                                    | WSM Score   |
> |                                            | W1 = 0.457                                                                                                                                                                                           | W2 = 0.257                                                                                                                                                                                           | W3 = 0.157                                                                                                                                                                                           | W4 = 0.090                                                                                                                                                                                           | W5 = 0.040                                                                                                                                                                                           |             |
> | Twinn                                      | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | Azure Digital Twins                        | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1.001       |
> | SmartSignal & Asset Performance Management | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | Twin Builder                               | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | AWS IoT TwinMaker                          | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | PTC ThingWorx                              | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | IoT Things                                 | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | VU3D Digital Twin                          | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | Visual Digital Twin                        | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0                                                                                                                                                                                                    | 0.504       |
> | LogiDot Digital Twin                       | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | Honeywell Process Digital Twin             | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | Aveva Digital Twin Solution                | 0                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 0.544       |
> | Xcelerator                                 | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1                                                                                                                                                                                                    | 1.001       |

## item 81

**Claim.** *Surrogates and reduced-order models:*,, and for the probabilistic-machine-learning side.

**Cited source.** `hartmann_executable_2022`, page 17

**Matched passage.**

> M.  Grieves,  Virtually  Perfect:  Driving  Innovative  and  Lean  Products  through  Product  Lifecycle Management, Cocoa Beach, FL, USA: Space Coast Press, 2011.

## item 82

**Claim.** **Adoption lags the forecasts, and the adoption numbers also disagree.** The same 2022 survey that quotes 58% annual growth also relays an engineering-institution report finding industry-agnostic adoption at around 5% of enterprises, while a 2025 paper relays industry surveys in which only about 5% of companies place twins *outside* their digital-transformation strategy altogether.

**Cited source.** `mihai_digital_2022`, page 2

**Matched passage.**

> The implications of this idea were revolutionary for the manufacturing industry, and other economic domains would later pick up on this as well. The most important advantage of the original DT was the conjoined lifetimes of the real and virtual entities, starting from the creation of the pair, and ending in their disposal. This feature suggests that the virtual asset would, at all times, mirror the most recent representative characteristics of the physical system, allowing remote monitoring throughout the whole lifetime of the physical object. As such, while it was initially intended as a tool for monitoring the lifecycle of a manufactured product, academia and the industry soon realised that the DT concept can be fruitfully applied to other economic domains as well.

## item 83

**Claim.** surveys the uncertainty sources in that domain.

**Cited source.** `tygesen_state---art_2019`, page 1

**Matched passage.**

> Recent reviews performed by the International Oil & Gas Producers Association [1] of the industry methods and practices for structural design and re-assessment reveal potential inconsistencies in the methods adopted and even knowledge gaps. All structures shall be operated within required safety levels as specified by codes and standards, so it is of the utmost importance that the real uncertainties associated with the design methods are correctly quantified, so that the risks of operating the platform are controlled throughout the lifetime of the structure, either for the original design, for the reinforced/upgraded design, or for other extended lifetime activities performed for ageing platforms.

## item 84

**Claim.** *Consulted, not drawn on above:* on automated twin testing and detecting performance shift online, on industrialising twin production, and on evolving twins by transfer learning, on model-based DevOps for cyber-physical systems, and for the layered view behind Sec. 14.6.4.

**Cited source.** `ma_automated_2023`, page 7

**Matched passage.**

> As can be seen, the position sensor in Figure 6(b) shows a position error of -2.5mm to 1.0mm with a spike in the probability distribution function (PDF) around -0.8mm during normal production that indicates a fault in the DT. The error deviation during the hold mode (Figure 7(b)) is between -3 and 2mm with a spike between -1 and 0mm. Temperature sensor Sensor1 3 in Zone 1 deviates during normal production from the expected one by the DT between -15°C to 10°C as shown in Figure 6(c) with a PDF spike at 0°C (no deviation). According to the cumulative distribution function (CDF) graph, the probability that the DT deviates between -4°C and 5°C is approximately 95-10=85%. However, during the holding mode (Figure 7(c)), the deviation of the DT increases, and the probability of deviation between -4°C and 5°C during the holding mode is 85-20=65%. The second temperature sensor in zone 2 (Sensor2 2) deviates during normal production from the expected value calculated by the DT within the interval 70°C to 30°C (Figure 6(d)). In the holding mode, the deviation is between -90°C and 40°C (Figure 7(d)). The PDF in Figure 6(d) shows an error spike at around -45°C during normal production. However, during holding mode, errors are mainly distributed around -80° C and 0° C (Figure 7 (d)).

## item 85

**Claim.** **Sector reports are more useful than totals.** Oil and gas, health, smart cities and net-zero manufacturing each have their own literature with concrete application scenarios.

**Cited source.** `parle_comparative_2024`, page 13

**Matched passage.**

> MCMD Approach: The  next  stage  of  down  selection includes analysis of digital twin platforms. To understand which methodologies would be suitable for performing down-selection analysis, papers and journals containing down-selection methodologies were reviewed [130], [131] and [132]. This section describes two analysis methodologies for down selection of digital twin platforms. Multi-criteria decision-making (MCDM) is a branch of operations research models that aid  decision-making  using  several  decision  criteria. Some industrial engineering applications use MCDM to evaluate technology investment decisions, flexible manufacturing systems, layout designs, and other engineering  problems  [130].  MCDM  methods  have different models, but the most common model used in this  case  is  the  Weighted  Sum  Model (WSM). In this approach, the scale of the set of goals into a single goal by multiplying each of our objectives by a user-supplied weight  factor  [128].  The  formula  for  determining  the

## item 86

**Claim.** Automated in both directions: digital twin.

**Cited source.** `kritzinger_digital_2018`, page 6

**Matched passage.**

> Work  for  this  paper  has  been  supported  by  the  European Commission  through  the  H2020  project  EPIC  under  grant No. 739592.

## item 87

**Claim.** The manufacturing framework organises a twin into four interconnected domains -- the observable manufacturing domain holding the real elements, the device communication domain holding sensors and actuators, the digital twin domain, and the user domain -- refined into *functional entities* including a data collection sub-entity and a device control sub-entity, plus a cross-system entity spanning the others.

**Cited source.** `shao_analysis_2023`, page 6

**Matched passage.**

> o Application and service sub-entity provides functionalities  such  as  simulation,  analysis  of  data captured from OMEs, and reporting production status.

## item 88

**Claim.** Knowledge graphs are used to record the current structure of a physical system **and its changes**, and are a key technology for asset models in twin architectures -- the greenhouse exemplar this book has cited since Chapter 1 is built that way, precisely because plants move.

**Cited source.** `kamburjan_greenhousedt_2024`, page 5

**Matched passage.**

> Lastly, the digital twin infrastructure includes a graphical web interface that visualizes the data in the time series database, the logs of the simulation model (i.e., control decisions and reconfigurations) and the updating queries for the asset model.

## item 89

**Claim.** *Testing, from a software engineer's angle:* on automated and systematic twin testing, on multi-level testing frameworks, on carrying a requirement from simulation to reality, and on why continuous integration for cyber-physical systems is harder than you expect.

**Cited source.** `ma_automated_2023`, page 7

**Matched passage.**

> As can be seen, the position sensor in Figure 6(b) shows a position error of -2.5mm to 1.0mm with a spike in the probability distribution function (PDF) around -0.8mm during normal production that indicates a fault in the DT. The error deviation during the hold mode (Figure 7(b)) is between -3 and 2mm with a spike between -1 and 0mm. Temperature sensor Sensor1 3 in Zone 1 deviates during normal production from the expected one by the DT between -15°C to 10°C as shown in Figure 6(c) with a PDF spike at 0°C (no deviation). According to the cumulative distribution function (CDF) graph, the probability that the DT deviates between -4°C and 5°C is approximately 95-10=85%. However, during the holding mode (Figure 7(c)), the deviation of the DT increases, and the probability of deviation between -4°C and 5°C during the holding mode is 85-20=65%. The second temperature sensor in zone 2 (Sensor2 2) deviates during normal production from the expected value calculated by the DT within the interval 70°C to 30°C (Figure 6(d)). In the holding mode, the deviation is between -90°C and 40°C (Figure 7(d)). The PDF in Figure 6(d) shows an error spike at around -45°C during normal production. However, during holding mode, errors are mainly distributed around -80° C and 0° C (Figure 7 (d)).

## item 90

**Claim.** *Value and adoption specifically:* on the lean approach this chapter's method is built on, on enablers and barriers, on being realistic about return on investment, and on pilot experience, and for a small-manufacturer case.

**Cited source.** `bhandal_conceptualising_2024`, page 16

**Matched passage.**

> Hasan, R., Moore, M., & Handfield, R. (2021). Establishing operational norms for labor rights standards implementation in low-cost apparel production. Sustainability , 13 (21), 12120.

## item 91

**Claim.** Modelling techniques get placed on an explicit white-to-black scale when assembling a twin's overall model set.

**Cited source.** `anwer_developing_2025`, page 13

**Matched passage.**

> Sustainability:

## item 92

**Claim.** *Populations:* on population-based structural health monitoring and transfer across a fleet; on a calibration and updating process that scales to an entire fleet; on combining sources of information across wind farms.

**Cited source.** `gardner_foundations_2021`, page 7

**Matched passage.**

> At this point it is useful to compare transfer learning to other forms of learning that are also appropriate for a populationbased approach to SHM. As mentioned in the first paper of this series [1], a form is one approach to PBSHM for a homoge- neous population, and will assume consistent label spaces (with respect to the normal conditions) and can assume either consistent or inconsistent feature spaces. This technique seeks to create a general representation of a population within the data-domain. A form can be inferred from a group of structures and used to transfer this knowledge to remaining members of a population. When used in this manner, it can be seen as a type of transfer learning. However, a form can also be inferred across a complete population and in this scenario aims to infer an improved general learner for the complete population, in which it is a type of multi-task learning. The other difference for the form approximation in Part I [1] is that the model is usually learnt in the data-domain, and therefore the variance of a general learner will often be inflated, unlike transfer learning or multi-task learning that often project to a latent space, with the aim of removing uncertainty not related to the latent process. As stated previously, multi-task learning differs from transfer learning in that the aim is to infer a general learner over all domains rather than transfer from one group to another. Multi-task learning can be both consistent and inconsistent in the feature space but will be consistent in the label space. In a PBSHM context, multi-task learning may be useful in removing the effects of confounding influences [28] and improving a learner for a structure with minimal labels within a population.

## item 93

**Claim.** **Why the conflation is expensive.** Setting $h = T_s$ because both are "ten minutes" forces the solver to stop and restart on every sample, which is precisely the structure reported above as both slower and less responsive to its tolerance setting.

**Cited source.** `cimino_efficient_2023`, page 3

**Matched passage.**

> TABLE I SIMULATION RESULTS-SOLVER STEPS FOR THE THREE DTS
> 
> |           | Number of steps   | Number of steps   | Number of steps   | Normalised   | Normalised   | Normalised   |
> |-----------|-------------------|-------------------|-------------------|--------------|--------------|--------------|
> | Tolerance | CT                | CaA               | LCaA              | CT           | CaA          | LCaA         |
> | 10-2      | 254               | 2500              | 2750              | 1.00         | 1.00         | 1.00         |
> | 10-4      | 753               | 2977              | 3187              | 2.96         | 1.19         | 1.16         |
> | 10-6      | 1585              | 5496              | 6042              | 6.24         | 2.20         | 2.20         |
> | 10-8      | 2444              | 8853              | 9901              | 9.62         | 3.54         | 3.60         |
> | 10-10     | 4136              | 12810             | 14442             | 16.28        | 5.12         | 5.25         |
> | 10-12     | 7306              | 19491             | 20867             | 28.76        | 7.80         | 7.59         |

## item 94

**Claim.** *When volume forces the policy:* and, as in Chapter 9 -- Sec. 10.10(a)'s three-tier retention is what those architectures look like from the storage side.

**Cited source.** `gigli_next_2024`, page 1

**Matched passage.**

> Color versions of one or more figures in this article are available at https://doi.org/10.1109/TII.2023.3337391.

## item 95

**Claim.** *The closest single reference to this chapter:* covers physics-based models from rates to space, discrete formalisms, hybrid execution and FMI-based co-simulation, worked on an incubator; is the containing book.

**Cited source.** `abbiati_modelling_2024`, page 36

**Matched passage.**

> Abrial, J.R.: The B Book - Assigning Programs to Meanings. Cambridge University Press (1996)

## item 96

**Claim.** The platform proposals make the same bet from the supply side: a generic platform from which twins are built out of reusable components, rather than marshalling assets, models, data and services from scratch each time.

**Cited source.** `talasila_realising_2024`, page 17

**Matched passage.**

> [Person]

## item 97

**Claim.** **Costs you:** everything in *diagnose*, plus a model that stays accurate over a forecast horizon, plus a serious answer to "how wrong might this be?" Uncertainty quantification stops being optional here.

**Cited source.** `thelen_comprehensive_2022`, page 43

**Matched passage.**

> end for

## item 98

**Claim.** Its practical value is breadth: a broad span of modelling and simulation tools support it and can export models as FMUs, and it is what open twin frameworks build their co-simulation on.

**Cited source.** `abbiati_modelling_2024`, page 2

**Matched passage.**

> Against this background, what are the modelling options facing the engineer designing a DT for a CPS? The range is wide, and in this chapter we showcase modelling formalisms that are particularly useful to represent cyber and physical systems, and we will discuss how models can be coupled to represent systems. The incubator case study is used as a running example through the entire chapter, and so will not be separated out into break-out boxes. Through the chapter, we outline what is needed to produce models for DTs and why . The reader interested in the details of how this is done will guided to the relevant literature as the chapter unfolds.

## item 99

**Claim.** *Consulted, not drawn on above:* for how a distributed-simulation standard handles participants with different notions of time, on consistency checks including step sizes inside a verification process, on simulators as training environments, for hardware-in-the-loop in the twin vocabulary, on augmenting twin models with behaviour, and on checking at runtime that co-simulation master algorithms are being used correctly.

**Cited source.** `liu_ai_2025`, page 17

**Matched passage.**

> These demonstrated contributions to the surging AI market suggest a likely increased adoption rate of digital twin technology. We anticipate digitally adept domains to follow suit with networking and robotics (Sect. 5.1) and adopt digital twins for AI simulation and traditional control and governance-related purposes. Thus, the link between digital twins and AI is shaping up to be one of the impactful directions for digital twin researchers.

## item 100

**Claim.** The COVID-19 period is repeatedly credited with accelerating digital transformation and shifting executive focus from cost-saving toward digital investment -- so some of the growth in these curves is a step change in attention, not a smooth technology trend.

**Cited source.** `mihai_digital_2022`, page 6

**Matched passage.**

> TABLE II LIST OF ACRONYMS
> 
> | Acronym AGV AI ANN AR ARIMA AUC BIM BOCD CNC CNN CoAP CP-Lab CPPS CPS DA DBSCAN DCNN DDQN DL DNN DoS DQN   | Description Automated Guided Vehicle Artificial Intelligence Artificial Neural Network Augmented Reality Autoregressive Integrated Moving Average Area Under Curve Building Information Modelling Bayesian Online Change-point Detection Computerized Numerical Control Convolutional Neural Networks Constrained Application Protocol Festo Cyber-Physical Factory Cyber-Physical Production Systems Cyber-Physical Systems Diagnostic Analytics Density-based Spatial Clustering of Applications with Noise Deep Convolutional Neural Networks Double Q Network Deep Learning Deep Neural Network Denial of Service Deep Q Network   | Acronym LOF LSTM ME-GP MES ML MQTT MR O&M OPC OPC-UA OSA-CBM PCA PCB PdM PER PLC PPO RL RNN ROI RUL SDOF   | Description Local Outlier Factor Long Short Term Memory Mixture of Experts and Gaussian Processes Manufacturing Execution Systems Machine Learning MQ Telemetry Transport Mixed Reality Operations and Maintenance Open Platform Communications OPC - Unified Architecture Open System Architecture for Condition-Based Maintenance Principal Component Analysis Printed Circuit Board Predictive Maintenance Prioritized Experience Replay Programmable Logic Controller Proximal Policy Optimisation Reinforcement Learning Recurrent Neural Network Return On Investment Remaining Useful Life Single Degree of Freedom   |
> |------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|

## item 101

**Claim.** Hierarchical composition is a recognised architectural capability rather than an improvisation: the ability to compose two or more digitalised entities into a higher-level entity "that lives thanks to information flowing from the underlying structures" is one of the named properties such architectures set out to provide.

**Cited source.** `martinelli_hierarchical_2024`, page 3

**Matched passage.**

> To enable the described digitalisation of a manufacturing environment, five capabilities (see Figure 3) reported in [18] have been identified and implemented: (i) data ingestion and augmentation, i.e., the ability to ingest data in the digitalised entity that logically follows the state of affairs of the physical world, disregard the protocol used to obtain higher level information; (ii) physical world actionability, i.e., the ability to accept high level actions requests as an input to the digitalised entity, analyse them and pass such requests to associated physical counterparts, monitoring the outcome; (iii) cyber-physical relationships, i.e., the ability to represent any existing relationship between physical objects in their digital counterparts; (iv) composition and hierarchical views, i.e., the ability to compose two or more digitalised entities into one higher level entity, that lives thanks to information flowing from the underlying structures; (v) application interaction, i.e., the ability to offer to the digital domain the information represented by digital counterparts, and collaborating to reach an agreed state of affairs in the real world.

## item 102

**Claim.** *TwinOps and DevOps for twins:* and, which put model-based engineering and ordinary delivery practice into a single pipeline and then check what the running system actually did against what the engineering models said it would; and on a DevOps approach aimed specifically at the iterative development and evolution of twins rather than their construction.

**Cited source.** `hugues_twinops_2022`, page 3

**Matched passage.**

> | Executive Summary                                                                  | Executive Summary                                                                  | Executive Summary                                                                  | Executive Summary                                                                  | iv   |
> |------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|------|
> | Abstract                                                                           |                                                                                    |                                                                                    |                                                                                    | v    |
> | 1 Summary                                                                          | 1 Summary                                                                          | 1 Summary                                                                          | 1 Summary                                                                          | 1    |
> |                                                                                    | 1.1                                                                                | Context and Objectives of the TwinOps Project                                      | Context and Objectives of the TwinOps Project                                      | 1    |
> | 1.2 Delivered Contributions ModDevOps: Coupling Model-Based Engineering and DevOps | 1.2 Delivered Contributions ModDevOps: Coupling Model-Based Engineering and DevOps | 1.2 Delivered Contributions ModDevOps: Coupling Model-Based Engineering and DevOps | 1.2 Delivered Contributions ModDevOps: Coupling Model-Based Engineering and DevOps | 2    |
> | 2 2.1                                                                              |                                                                                    |                                                                                    |                                                                                    | 3    |
> |                                                                                    | 2.1.1                                                                              | Technology Overview                                                                | Technology Overview                                                                | 3    |
> |                                                                                    |                                                                                    | DevOps                                                                             |                                                                                    | 3    |
> |                                                                                    | 2.1.2                                                                              | Perspectives                                                                       | On Modeling                                                                        | 3    |
> |                                                                                    | 2.1.3                                                                              | Modeling Cyber-Physical                                                            | Systems                                                                            | 4    |
> |                                                                                    | 2.1.4                                                                              | Models and                                                                         | Processes                                                                          | 5    |
> |                                                                                    | 2.1.5                                                                              |                                                                                    | Conclusion                                                                         | 6    |
> | 2.2                                                                                | MBS2E Overview                                                                     | MBS2E Overview                                                                     | MBS2E Overview                                                                     | 6    |
> |                                                                                    | 2.3                                                                                | ModDevOps, a Primer                                                                | ModDevOps, a Primer                                                                | 8    |
> |                                                                                    | 2.3.1                                                                              |                                                                                    | ModDevOps Definition                                                               | 8    |
> |                                                                                    | 2.3.2                                                                              |                                                                                    | ModDevOps 'Infinity Loop'                                                          | 9    |
> |                                                                                    | 2.3.3                                                                              |                                                                                    | ModDevOps ⊄ Dev(*)Ops                                                              | 10   |
> |                                                                                    | 2.4                                                                                | ModDevOps Defined as SysML model                                                   | ModDevOps Defined as SysML model                                                   | 10   |
> |                                                                                    | 2.4.1                                                                              |                                                                                    | ModDevOps Use Cases                                                                | 11   |
> |                                                                                    | 2.4.2                                                                              |                                                                                    | ModDevOps Blocks                                                                   | 12   |
> |                                                                                    | 2.4.3                                                                              | ModDevOps                                                                          | Activities                                                                         | 12   |
> | 2.5                                                                                | Conclusion                                                                         | Conclusion                                                                         | Conclusion                                                                         | 15   |
> | 3                                                                                  | TwinOps Defined: ModDevOps for CPS                                                 | TwinOps Defined: ModDevOps for CPS                                                 | TwinOps Defined: ModDevOps for CPS                                                 | 16   |
> |                                                                                    | 3.1                                                                                | TwinOps Introduction                                                               | TwinOps Introduction                                                               | 16   |
> |                                                                                    | 3.2                                                                                | The SensorProcessing Demonstrator                                                  | The SensorProcessing Demonstrator                                                  | 17   |
> |                                                                                    | 3.3                                                                                | ModDevOps Applied to SensorProcessing: Models                                      | ModDevOps Applied to SensorProcessing: Models                                      | 17   |
> |                                                                                    |                                                                                    | 3.3.1                                                                              | TwinOps Solution #1: Use Containers for Delivering Modeling Environments           | 17   |
> |                                                                                    |                                                                                    | 3.3.2                                                                              | TwinOps Solution #2: Perform Virtual Integration from Models                       | 18   |
> |                                                                                    |                                                                                    | 3.3.3                                                                              | TwinOps Lessons Learned                                                            | 18   |
> |                                                                                    | 3.4                                                                                | ModDevOps Applied to SensorProcessing: Implementation                              | ModDevOps Applied to SensorProcessing: Implementation                              | 19   |
> |                                                                                    | 3.4.1                                                                              | TwinOps Solution #3: Multiple Targets Code                                         | Generation                                                                         | 20   |
> |                                                                                    |                                                                                    | 3.4.2                                                                              | TwinOps Solution #4: Integration as a DevOps CI/CD Pipeline                        | 21   |
> |                                                                                    | 3.4.3                                                                              | TwinOps Solution #5: System                                                        | Analytics                                                                          | 21   |
> |                                                                                    | 3.5 Conclusion                                                                     | 3.5 Conclusion                                                                     | 3.5 Conclusion                                                                     | 22   |
> | 4                                                                                  | TwinOps: The                                                                       | SensorProcessing IoT                                                               | Demo                                                                               | 23   |
> | 4.1                                                                                | Step 1: Defining the Modeling Process                                              | Step 1: Defining the Modeling Process                                              | Step 1: Defining the Modeling Process                                              | 23   |
> | 4.2                                                                                | Step 2: System Model / SysML                                                       | Step 2: System Model / SysML                                                       | Step 2: System Model / SysML                                                       | 24   |
> | 4.3                                                                                | Step 3: Embedded Software and Hardware Mode / AADL                                 | Step 3: Embedded Software and Hardware Mode / AADL                                 | Step 3: Embedded Software and Hardware Mode / AADL                                 | 24   |
> |                                                                                    | 4.3.1                                                                              | Setting Up the Modeling Environment                                                | Setting Up the Modeling Environment                                                | 25   |
> |                                                                                    | 4.3.2                                                                              | Modeling the System Requirements Using ALISA                                       | Modeling the System Requirements Using ALISA                                       | 25   |
> |                                                                                    | 4.3.3                                                                              | Modeling the System Architecture Using AADL                                        | Modeling the System Architecture Using AADL                                        | 26   |
> | 4.4                                                                                | Step                                                                               | IoT Concerns and Implementation of C Functions                                     | IoT Concerns and Implementation of C Functions                                     | 27   |
> | 4.5                                                                                | 4: Step 5: ModDevOps: A Model-Level CI/CD Pipeline                                 | 4: Step 5: ModDevOps: A Model-Level CI/CD Pipeline                                 | 4: Step 5: ModDevOps: A Model-Level CI/CD Pipeline                                 | 27   |
> |                                                                                    | 4.5.1                                                                              |                                                                                    |                                                                                    | 27   |
> |                                                                                    | 4.5.2                                                                              | Model-Only CI/CD Pipeline                                                          | Model-Only CI/CD Pipeline                                                          | 28   |
> |                                                                                    | 4.5.3                                                                              | Model-to-Code-to-Target CI/CD Conclusion                                           | Model-to-Code-to-Target CI/CD Conclusion                                           | 28   |

## item 103

**Claim.** *The three-family split and the hybrid argument:* is the clearest statement of why neither pure approach suffices and what combining them buys, with for the model-based / data-driven / hybrid classification, for the hybrid trend in one domain, and for the first-principles / data-driven / hybrid split applied to real manufacturing twins.

**Cited source.** `bottjer_review_2023-1`, page 3

**Matched passage.**

> Table 1 Related DT reviews and concept papers (title-abs-key('Digital Twin' AND ('Manufacturing' OR 'Production')) Scopus, 18-03-2022). Acronyms for labeling the specific focus of papers:  Cyber-Physical  System  (CPS),  Product  Life  Cycle  Management  (PLM),  Smart  Manufacturing  (SM),  Definition  (D),  Application  (A).  Key aspects  abbreviations  used  are: Reference model & Concept (RC), Modeling & Simulation (MS), Hardware (H), Software (S).
> Table 1 Related DT reviews and concept papers (title-abs-key('Digital Twin' AND ('Manufacturing' OR 'Production')) Scopus, 18-03-2022). Acronyms for labeling the specific focus of papers:  Cyber-Physical  System  (CPS),  Product  Life  Cycle  Management  (PLM),  Smart  Manufacturing  (SM),  Definition  (D),  Application  (A).  Key aspects  abbreviations  used  are: Reference model &amp; Concept (RC), Modeling &amp; Simulation (MS), Hardware (H), Software (S).
> 
> | Review and concept papers   | Area          | Digital Twin components   | Digital Twin components   | Digital Twin components   | Digital Twin components   | Digital Twin components   | Paper Scope   | Paper Scope   | Paper Scope   | Paper Scope   |
> |-----------------------------|---------------|---------------------------|---------------------------|---------------------------|---------------------------|---------------------------|---------------|---------------|---------------|---------------|
> | Review and concept papers   | Area          | R&C                       | MS                        | Data                      | H&S                       | Services                  | Factory       | Shopfloor     | Unit          | Product       |
> | Rosen et al. [113]          | CPS, I4.0     | x                         | x                         |                           | H                         |                           | x             | x             |               |               |
> | Negri et al. [94]           | D, CPS, I4.0  | x                         | x                         |                           | S                         | x                         | x             | x             | x             |               |
> | Schleich et al. [116]       | PLM           | x                         | x                         |                           | S                         | x                         |               |               | x             |               |
> | Tao and Zhang [132]         | SM, CPS, A    | x                         | x                         | x                         | S                         | x                         |               | x             |               |               |
> | Uhlemann et al. [135]       | CPS, I4.0, A  | x                         |                           | x                         | H                         |                           | x             | x             |               |               |
> | Kritzinger et al. [66]      | D, A, I4.0    | x                         |                           |                           |                           | x                         | x             | x             | x             |               |
> | Tao et al. [128]            | CPS, PLM      | x                         |                           | x                         |                           | x                         |               |               | x             | x             |
> | Qi and Tao [106]            | SM            | x                         |                           | x                         |                           | x                         | x             | x             | x             |               |
> | Zhuang et al. [154]         | SM            | x                         | x                         | x                         | H, S                      | x                         |               | x             |               |               |
> | Tao et al. [131]            | D, A          |                           | x                         | x                         | H, S                      | x                         |               |               |               | x             |
> | Cimino et al. [31]          | CPS, D, A     |                           | x                         | x                         | H, S                      | x                         |               | x             | x             | x             |
> | Lu et al. [81]              | SM, A         | x                         |                           | x                         | H                         | x                         | x             |               | x             |               |
> | Errandonea et al. [34]      | A             |                           |                           |                           |                           | x                         |               | x             | x             | x             |
> | Melesse et al. [88]         | A             |                           |                           |                           |                           | x                         |               | x             | x             | x             |
> | Sjarov et al. [121]         | D             | x                         |                           |                           |                           |                           |               |               |               |               |
> | Zhang et al. [146]          | A             | x                         | x                         |                           | H                         |                           |               |               | x             |               |
> | Wang et al. [137]           | A             | x                         | x                         | x                         | H, S                      | x                         |               |               | x             |               |
> | Ciano et al. [30]           | SM, I4.0, PLM | x                         |                           |                           |                           |                           |               |               |               |               |
> | Jones et al. [61]           | D             | x                         |                           |                           |                           | x                         |               |               |               |               |
> | Agnusdei et al. [3]         | A             | x                         |                           |                           |                           |                           |               |               |               |               |
> | Xie et al. [142]            | A, PLM        | x                         | x                         | x                         | H, S                      | x                         |               |               |               | x             |
> | Atalay et al. [11]          | A             | x                         |                           |                           |                           | x                         |               | x             | x             | x             |
> | He and Bai [47]             | A             | x                         |                           |                           |                           | x                         |               | x             | x             | x             |
> | Liu et al. [76]             | D, A, PLM     |                           | x                         | x                         |                           | x                         |               | x             | x             | x             |

## item 104

**Claim.** That is what the trust-vector proposal is for, and the obstacles named around composite twins are exactly the ones you would expect: trust, interoperability, governance, ownership, security and privacy. **Five of those six are not engineering problems**, which is the honest reason ecosystem twins are rarer than the literature's enthusiasm suggests.

**Cited source.** `kuruppuarachchi_architecture_2022`, page 2

**Matched passage.**

> The IIC introduced the term Composite Digital Twin (CDT) with respect to the need to connect multiple DTs in industrial settings. CDT is introduced on the basis of three possible types of CDT: hierarchical, associational, and peer-to-peer [5]. A hierarchical CDT is defined as a tiered connection of DTs, where equipment or system-based DTs are connected to form a production line DT and production line DTs can be connected to create a factory level DT. The incremental connection across DTs results in the final hierarchical CDT. The associational CDT is used to represent the association between two or more discrete DTs. For example, a production line can connect with another production line to create a composite associational DT. A hierarchical CDT can also refer to a collection of associational composite DTs. The peer-to-peer composite DT is based on connecting similar DTs, in terms of the type of functions such as wind farm with a collection of wind turbines or a fleet of cars. The envisaged compositions of CDT are derived from an operational standpoint. However, these create an additional layer of complexity from an operational management perspective. Some of the operational management questions are, who owns the data? Who is responsible for the CDT? If there is a conflict, who is going to resolve this? This motivates the need for clearly defined governance structures and policy enforcement strategies.

## item 105

**Claim.** Continuous-integration practice for cyber-physical systems is itself an uncomfortable fit, and an interview study of practitioners found the hardware-in-the-loop stages to be the awkward part -- a finding a software engineer should read as permission to expect this to be harder than it is for a web service.

**Cited source.** `zampetti_continuous_2023`, page 19

**Matched passage.**

> As reported later in Table 8, the analysis of the interviews' transcripts has elicited two mitigation strategies: (i) prioritize and select the test cases to be included within the pipeline (i.e., 'Some strategies rely on genetic algorithms to optimize the resources available for the testing execution environment' from O1), and (ii) adopt incremental builds mainly relying on impact analysis, as reported by O2: 'for what concerns rolling builds we try to limit the amount of testing being executed in them to be as fast as possible. ' The member-checking survey confirms the previous findings, and, as shown later in Table 8, 6 out of 10 organizations (O1, O2, O5, O6, O7, O10) report to rely on test prioritization, whereas O3, O4, O8, and O9 consider it useful while having never used it. With regard to the adoption of incremental builds, instead, O1, O2, O4, O7 , and O9 mention its adoption, whereas O8 considers it a useful approach to deal with limited hardware/software resources.

## item 106

**Claim.** Chapter 2 named the gap **time discrepancy** and cited work treating it as a problem in its own right, motivated by cases where delay is the whole failure -- a control loop destabilised by lag, or a warning arriving too late to act on.

**Cited source.** `frasheri_addressing_2023`, page 13

**Matched passage.**

> Table 5 Results for observed time measurements in the network drop scenario, where (i) the period represents the simulation time during the drop conditions, (ii) steps done represents the steps performed until the system was back in sync, (iii) all steps represents the number of steps that would have been taken if no bigger steps than the default (100 ms) were taken, (iv) sync time is the time it took the system to get back in sync, (v) time/step is the time it took for each individual step, (vi) estimated total time is the calculated value on how much time it would have taken to get back in sync if all steps were performed, (vii) using the time/step as a measure, (viii) saved is the amount of time that was saved by taking bigger step sizes, and (ix) the speedup is calculated as the total estimated time over the sync time.
> 
> |   Run# | Period      |   Steps done |   All steps | Sync time   | Time/Step   | Est. Tot. time   | Saved     |   Speedup |
> |--------|-------------|--------------|-------------|-------------|-------------|------------------|-----------|-----------|
> |      1 | 5.0-6.0 (s) |            5 |          11 | 17 (ms)     | 3.4 (ms)    | 37.4 (ms)        | 20.4 (ms) |       2.2 |
> |      2 | 5.2-6.1 (s) |            6 |          10 | 15 (ms)     | 2.5 (ms)    | 25(ms)           | 10 (ms)   |       2.5 |
> |      3 | 7.1-8.0 (s) |            6 |          10 | 15 (ms)     | 2.5 (ms)    | 25 (ms)          | 10(ms)    |       2.5 |
> |      4 | 6.8-8.0 (s) |            5 |          13 | 14 (ms)     | 2.8 (ms)    | 36.4 (ms)        | 22.4 (ms) |       2.6 |
> |      5 | 6.1-7.2 (s) |            6 |          12 | 16 (ms)     | 2.6 (ms)    | 31.2 (ms)        | 15.2 (ms) |      1.95 |

## item 107

**Claim.** *Platforms, middleware and deployment:* for the as-a-service framing and its container decomposition, for what middleware actually does in published twins, and for microservice and serverless realisations, and on the edge-to-cloud continuum, and for open-source frameworks, on reusing reference architectures, and with for the industrial-architecture framing of connectivity and the twin-as-middleware pattern.

**Cited source.** `bellavista_entanglement-aware_2024`, page 3

**Matched passage.**

> The most common network implementation of such a logical structure is arguably the Purdue model [42], which models the industrial network in three Zones and six Layers (see Figure 1). The Cell/Area Zone is the bottom one, comprises Layers from 0 to 2, and concerns the OT. The shop loor components crafting goods belong to Layers 0 and 1. Such Layers rely on a time-sensitive network connecting industrial machines and PLCs, while devices that control crafting processes, e.g., HMIs, reside on Layer 2. The Manufacturing Zone resides in the middle. It contains Layer 3, which embraces both OT and IT, including those components that manage the manufacturing process as a whole, e.g., the MES. At the top, there is the Enterprise Zone, which comprises Layers 4 and 5. Such Layers primarily provide IT-oriented functionalities and facilities, such as Web servers, email servers, databases, and the ERP system, to name a few. Recently, industrial network implementations have evolved towards multi-domain architectures with some of the software components deployed outside the factory environment in the so called edge-to-cloud continuum. For instance, Multi-access Edge Computing (MEC) nodes could host DTs in the cellular operator domain not too far from PTs, while delay-tolerant DTs could be remotely hosted on a public cloud infrastructure. Thus, nowadays the Enterprise Zone of the Purdue model embraces multiple heterogeneous domains, from on-premises plant network to telco operator and cloud provider networks.

## item 108

**Claim.** At this scale the platform question stops being a build-versus-buy decision and becomes an organisational one, which is what `van_schalkwyk_achieving_2023` means by composability as the route to scale and what work on industrialising twin production is responding to.

**Cited source.** `van_schalkwyk_achieving_2023`, page 26

**Matched passage.**

> Description

## item 109

**Claim.** Chapter 11 Sec. 11.7.2 named it and sent it here, correctly, because the literature frames it as a validation technique for dependability rather than as a twin service.

**Cited source.** `frasheri_advanced_2024`, page 13

**Matched passage.**

> Avizienis, A., Laprie, J.C., Randell, B., Landwehr, C.: Basic Concepts and Taxonomy of Dependable and Secure Computing. IEEE Transactions on Dependable and Secure Computing 1 , 11-33 (2004). doi : http://doi.ieeecomputersociety.org/10.1109/TDSC.2004. 2

## item 110

**Claim.** **Where they show up in twins.** Wherever the expensive model must run repeatedly: model updating driven by sampling procedures that need thousands of evaluations, evolutionary optimisation whose function-evaluation counts are otherwise prohibitive, and twins built from libraries of component-level reduced-order models so that a fleet can be served at scale.

**Cited source.** `torzoni_deep_2023`, page 4

**Matched passage.**

> The DNN used for the monitoring of the usage conditions NN US is a fullyconnected DNN devised to perform a nonlinear projection of the HF vibration recordings onto a low-dimensional feature space, wherein the operational conditions x LF can be easily discriminated. A prior dimensionality reduction is adopted to encode U HF ( x HF ) into v HF POD ( x HF ) ∈ R M US , through a set of M US ≪ L concat POD-basis functions Z = [ z 1 , . . . , z M LF ] ∈ R L concat × M US built upon D HF , as v HF POD ( x HF ) = Z ⊤ v HF ( x HF ), being v HF ( x HF ) the vectorization of U HF ( x HF ).

## item 111

**Claim.** *AI and twins, the overall picture:* for enabling technologies, for the modelling-perspective view of why hybrid arrangements dominate, and for AI-in-cyber-physical-systems including the safety and data-quality standards work now under development.

**Cited source.** `chae_survey_2023`, page 12

**Matched passage.**

> While AI models offer a multitude of advantages in the industrial sector, it is equally crucial to ensure that human experts can comprehend these models. In particular, it is essential to explain to the workers the control stability and equipment maintenance that the AI model is responsible for. To enhance user's comprehension of the AI model, simplifying the model may result in a trade-off with performance. Striking a delicate balance between the model's performance and its explainability becomes imperative.

## item 112

**Claim.** *Consulted, not drawn on above:* and on rethinking asset representation, on twin description approaches, on the regulatory framing in healthcare, and on machine-readable trust between twins, which is Chapter 15's direction.

**Cited source.** `ellwein_rethinking_2025`, page 10

**Matched passage.**

> [S15-{Concept}]

## item 113

**Claim.** *Sector deep-dives:* for oil and gas, and for health, for smart cities, and for aerospace and defence, for offshore structural health, and for net-zero manufacturing platforms.

**Cited source.** `katsoulakis_digital_2024`, page 11

**Matched passage.**

> Publisher ' snote Springer Nature remains neutral withregard tojurisdictional claims in published maps and institutional af fi liations.

## item 114

**Claim.** The same work notes that buying that speed usually costs accuracy, and that the exchange rate is a decision to settle when the system is designed rather than after.

**Cited source.** `gomes_sensing_2024`, page 10

**Matched passage.**

> Table 7.1: OSI Network Model.
> 
> | Layer           | Function                                   | Example Protocols                                                                                                                                |
> |-----------------|--------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
> | 7. Application  | Network services for end-user applications | Hypertext Transfer Protocol (HTTP), File Transfer Protocol (FTP), Simple Mail Transfer Protocol (SMTP), Advanced Message Queuing Protocol (AMQP) |
> | 6. Presentation | Data format translation and encryption     | Secure Sockets Layer (SSL)                                                                                                                       |
> | 5. Session      | Establishes/maintains/terminates sessions  | Remote Procedure Call (RPC)                                                                                                                      |
> | 4. Transport    | End-to-end communication, error recovery   | Transmission Control Protocol (TCP), User Datagram Protocol (UDP)                                                                                |
> | 3. Network      | Routing and logical addressing             | Internet Protocol, Internet Con- trol Message Protocol (ICMP)                                                                                    |
> | 2. Data Link    | Physical addressing, error detection       | Ethernet, Point-to-Point (PPP) Protocol, MediumAccessControl (MAC) protocols                                                                     |
> | 1. Physical     | Physical medium and signalling             | Universal Serial Bus (USB), Eth- ernet                                                                                                           |

## item 115

**Claim.** At this scale the platform question stops being a build-versus-buy decision and becomes an organisational one, which is what `van_schalkwyk_achieving_2023` means by composability as the route to scale and what work on industrialising twin production is responding to.

**Cited source.** `niederer_scaling_2021`, page 7

**Matched passage.**

> Rego, B. V . et al. A noninvasive method for the determination of in vivo mitral valve leaflet strains. Int. J. Numer. Methods Biomed. Eng. 34 , e3142 (2018).

## item 116

**Claim.** Industrialising twin production puts new demands specifically on the speed of validation, and this is where that pressure lands.

**Cited source.** `niederer_scaling_2021`, page 5

**Matched passage.**

> Digital twins offer clear and exciting short-term benefits in monitoring,  control  and  decision  support;  however,  from  a  long-term perspective, their ubiquitous adoption will offer new applications and another layer of predictive and control capabilities. Once digital twins are ubiquitous and many physical assets or entities are paired with a digital version, twins will be able to be coupled into networks of digital twins (Fig. 3). Pooling data between twins and connecting twins could improve predictions. Digital twins of similar assets or entities could be coupled together, with historical data from older twins providing enhanced predictions for comparable newer twins. Co-located  twins  could  pool  data  to  reduce  uncertainty.  Digital twins  of  physically  connected  systems  could  provide  coupled boundary conditions  for  longer-term  prediction.  Digital  twins  of automated physical systems could link to other static,  automated or living digital twins to enable on-the-fly cooperation and interactions. Ubiquity of digital twins offers another level of monitoring, control and decision support beyond isolated digital twins.

## item 117

**Claim.** It has: a tutorial-length treatment of the whole system, its services and its architecture; a case-study chapter that shows the calibration done properly, including a two-parameter model compared against a four-parameter one on real data; and -- the unusual part -- **a survey that implements the same case study across five open-source twin frameworks**.

**Cited source.** `gil_survey_2024`, page 4

**Matched passage.**

> TABLE 1 List of analyzed DT frameworks.
> 
> | Name                                           | Author/Organization                                            | Link                                                                               |
> |------------------------------------------------|----------------------------------------------------------------|------------------------------------------------------------------------------------|
> | Eclipse Ditto                                  | Eclipse Foundation &Bosch                                      | https://www.eclipse.org/ditto/                                                     |
> | Equinox                                        | Murat Artim                                                    | https://github.com/muratartim/Equinox                                              |
> | AASX Package Explorer                          | Industrial Digital Twin Association (IDTA)                     | https://github.com/admin-shell-io/aasx -package-explorer                           |
> | PYI40AAS                                       | RWTHAachen                                                     | https://git.rwth-aachen.de/acplt/pyi40aas                                          |
> | SAP I4.0 AAS                                   | SAP                                                            | https://github.com/SAP/i40-aas                                                     |
> | Eclipse Basyx                                  | Eclipse / Bosch / Fraunhofer Institute                         | https://projects.eclipse.org/projects /technology.basyx                            |
> | NOVA AAS                                       | NOVA School of Science and Technology (NOVA University Lisbon) | https://gitlab.com/gidouninova/novaas                                              |
> | CPS-Twinning                                   | SBA Research                                                   | https://github.com/sbaresearch/cps-twinning                                        |
> | Twined                                         | Octue Ltd                                                      | https://github.com/octue/twined                                                    |
> | Azure Digital Twins Definition Language (DTDL) | Microsoft Azure                                                | https://github.com/Azure/opendigitaltwins -dtdl                                    |
> | iTwin.js                                       | Bentley Systems, Incorporated                                  | https://www.itwinjs.org/                                                           |
> | Digital Twin Cities Centre Platform (DTCC)     | Chalmers University of Technology                              | https://gitlab.com/dtcc-platform                                                   |
> | TerriaJS (NSW Digital Twin implementation)     | New South Wales State, Australia                               | https://nsw.digitaltwin.terria.io/about.html, https://github.com/TerriaJS/terriajs |
> | INTO-CPS Co-simulation Framework               | INTO-CPS Association                                           | https://into-cps-association.readthedocs.io/en /latest/                            |

## item 118

**Claim.** *Asset description:* is the specification; on mapping between AAS and OPC UA; and on integration work around it; and on applications.

**Cited source.** `schmidt_integration_2025`, page 1

**Matched passage.**

> applied sciences

## item 119

**Claim.** It has been used as the frame for component catalogues, mapped onto by other frameworks, and applied to worked use cases.

**Cited source.** `shao_use_2021`, page 4

**Matched passage.**

> Digital Twin; Framework; Standards; Smart Manufacturing; Use Cases.

## item 120

**Claim.** Reviews of specific domains report the same trend: relying solely on data-driven models for precise prediction is difficult, physics-based modelling is often needed to aid the predictive models, and the result is a rising use of hybrid models.

**Cited source.** `chen_service_2024`, page 4

**Matched passage.**

> The relationship between the type of AM and modelling approach is compared in Fig. 2. Most research is from FDM as a result of its widespread applications. Data acquisition of FDM processes such as bed temperature, nozzle movement and layer thickness is convenient. Given the limited chemical changes involved, it makes it straightforward to use simulations to visualise the process. Therefore, most research towards FDM used physics-based models [41,44,46,51,52,56,59,63,64]. LPBF is the second research-intensive AM process in digital twin development. Compared to FDM, the LPBF process involves many more thermo-metallurgical interactions and more complex chemical changes, making it difficult to describe with purely physics-based models. As mentioned above, limited data limits the ability of data-driven models to learn implicit relationships, so most LPBF research has used hybrid models [38,39,42,43,49,60]. DED and WAAM showed similar trends to LPBF that the hybrid model has the highest number [40,48-50,60,62], which is because they also belong to metal 3D printing. To summarise, physics-based models and hybrid models are more popular. Due to the diversity of the AM process, variations in sensor configurations, and the high cost of data collection, the available data is limited. Consequently, it is challenging for the digital twin to rely solely on end-to-end datadriven models for accurate predictions, often necessitating the support of domain knowledge and physical models.

## item 121

**Claim.** Independently developed open-source Asset Administration Shell stacks turn out to be **incompatible with one another**.

**Cited source.** `jacoby_open-source_2023`, page 1

**Matched passage.**

> Abstract: The use of open-source software is crucial for the digitalization of manufacturing, including the implementation of Digital Twins as envisioned in Industry 4.0. This research paper provides a comprehensive comparison of free and open-source implementations of the reactive Asset Administration Shell (AAS) for creating Digital Twins. A structured search on GitHub and Google Scholar was conducted, leading to the selection of four implementations for detailed analysis. Objective evaluation criteria were defined, and a testing framework was created to test support for the most common AAS model elements and API calls. The results show that all implementations support at least a minimal set of required features while none implement the specification in all details, which highlights the challenges of implementing the AAS specification and the incompatibility between different implementations. This paper is therefore the first attempt at a comprehensive comparison of AAS implementations and identifies potential areas for improvement in future implementations. It also provides valuable insights for software developers and researchers in the field of AAS-based Digital Twins.

## item 122

**Claim.** *On there being no consensus, and why:*,,, and, with for the practitioner-survey view and the argument that standards should fix it.

**Cited source.** `paredis_family_2023`, page 5

**Matched passage.**

> Similar to the previous use case, a simplification of such a device is made for the purposes of this paper, to focus on the essential Digital T workflows and architectures. An incubator is a device that is able to maintain a specific temperature (or profile over time) within an insulated container. With an appropriate temperature profiel, microbiological or cell cultures can be grown and maintained.

## item 123

**Claim.** *Co-simulation and FMI:* for the model-exchange versus co-simulation split in the clearest terms; for a concrete master implementation; for what practitioners find hard; and for open frameworks built on FMI; for a worked multi-domain case; for coupling an equation-based tool to a legacy one; for runtime monitoring of master algorithms.

**Cited source.** `infante_integrating_2024`, page 10

**Matched passage.**

> Kafka broker : Once the simulations are completed, the resulting data is sent through a messaging broker. The messaging broker acts as an intermediary, facilitating the transfer of data between different components of the system.

## item 124

**Claim.** *Consulted, not drawn on above:* on solver choice and control representation, as a tutorial companion, for time discrepancy (Chapter 5), on models that learn their own structure, on updating a finite-element twin from measurements, on combining information sources across a wind farm, on uncertainty in evolving twins, and on testing twins systematically.

**Cited source.** `emmert-streib_complexity_2024`, page 5

**Matched passage.**

> Model evaluation

## item 125

**Claim.** Open-source twin frameworks exist precisely to make this option available to organisations that cannot afford a commercial solution, and the platform-as-a-service proposals in the literature are explicitly attempts to make assembly reusable -- building twins from reusable components and offering them as a service, rather than starting from scratch each time.

**Cited source.** `talasila_realising_2024`, page 1

**Matched passage.**

> Chapter 11 Realising Digital Twins

## item 126

**Claim.** Structural health monitoring reached this conclusion decades ago and it is the origin of the field's use of machine learning: represent normal conditions from measured data, then test for abnormality, because deriving the damage mechanism was not available.

**Cited source.** `worden_artificial_2023`, page 21

**Matched passage.**

> | Prediction   |   1 |   2 |   3 |   4 |   5 |   6 |   7 |   8 |   9 |
> |--------------|-----|-----|-----|-----|-----|-----|-----|-----|-----|
> | True class 1 |  62 |   1 |   0 |   0 |   2 |   0 |   0 |   1 |   0 |
> | True class 2 |   0 |  61 |   0 |   0 |   5 |   0 |   0 |   0 |   0 |
> | True class 3 |   0 |   1 |  52 |   0 |   7 |   4 |   0 |   2 |   0 |
> | True class 4 |   1 |   0 |   3 |  60 |   0 |   1 |   0 |   1 |   0 |
> | True class 5 |   2 |   1 |   0 |   0 |  60 |   3 |   0 |   0 |   0 |
> | True class 6 |   2 |   0 |   6 |   0 |   8 |  52 |   0 |   0 |   0 |
> | True class 7 |   1 |   0 |   4 |   0 |   1 |   1 |  58 |   1 |   0 |
> | True class 8 |   0 |   0 |   0 |   0 |   1 |   1 |   0 |  62 |   2 |
> | True class 9 |   2 |   1 |   1 |   0 |   0 |   0 |   0 |  15 |  47 |

## item 127

**Claim.** The word for the bundle is **credibility assessment**: verification and validation establish that the twin meets its intended purpose, and uncertainty quantification supplies a measure of performance that users apply as part of that assessment, applied across the twin's whole life cycle rather than once at the end.

**Cited source.** `shao_analysis_2023`, page 7

**Matched passage.**

> Other sub-entities in Section 5.2 are also similarly enriched by subdividing them into functional entities in [2]. Hierarchically, it can be seen that entities contain sub-entities, and sub-entities contain functional entities.

## item 128

**Claim.** *Consulted, not drawn on above:* on twins supporting on-device learning for constrained hardware, on federated training in twin settings, on stating twin fidelity as knowledge equivalence, on dependability across the data spectrum, and on why validation speed is the bottleneck when twins are produced industrially rather than one at a time.

**Cited source.** `barbone_-device_2026`, page 8

**Matched passage.**

> Crucially, this approach abstracts the complexity of multi-model evaluation from external digital applications, which interact with the DTs as if they were a single, unified intelligence layer. Unlike the previous model, the M-DT also governs the retraining process, deciding when and which models require updates based on their observed performance, further enhancing adaptability and optimization within the system. The synchronization approach adapts dynamically depending on whether replicas are deployed at the edge or in the cloud. Edge replicas maintain tighter, low-latency synchronization with the M-DT, often leveraging event-driven protocols for immediate responsiveness. Conversely, cloud replicas may synchronize less frequently, focusing on aggregated data analysis and long-term model training. This fl exible synchronization framework supports consistent and timely integration of data and results across heterogeneous computing environments.

## item 129

**Claim.** *Consulted, not drawn on above:* on solver choice and control representation, as a tutorial companion, for time discrepancy (Chapter 5), on models that learn their own structure, on updating a finite-element twin from measurements, on combining information sources across a wind farm, on uncertainty in evolving twins, and on testing twins systematically.

**Cited source.** `xu_pretrain_2024`, page 14

**Matched passage.**

> RQ1 aims to evaluate the overall effectiveness of PPT in TTE analysis by comparing it to two baselines: RISE-DT and NN. Table 3 presents the results of both Orona's elevator and DeepScenario's ADS case studies. Compared to RISE-DT in the elevator case study , we find that PPT demonstrates superiority in both traffic-variant evolutions (i.e., UpBest → LunchBest and LunchBest → UpBest ) and dispatcher-variant evolutions i.e., LunchWorse → LunchBest and UpWorse → UpBest ). The minimum improvement is 5.70 (109.49-103.79), for the case of LunchBest → UpBest ), while the maximum improvement is 9.62 for the case of UpWorse → UpBest . According to the statistical testing results, we find that the improvements in the traffic-variant evolutions are significant ( p -value < 0 . 01 ) with strong effect sizes ( A 12 > 0 . 71 ). The majority of the improvements in the dispatcher-variant evolutions are significant (21 out of 30) and the effect sizes are mostly strong (17 out of 30 for LunchWorse → LunchBest and 20 out of 30 for the case UpWorse → UpBest ). In the ADS case study , PPT outperforms RIST-DT by 14.410 and 10.75 for the Simple → Complex and Complex → Simple cases respectively. we observe significance and very strong effect sizes (close to 1) in both improvements.

## item 130

**Claim.** Reviews group twin content into geometric, physical, behaviour and rule models for exactly this reason, and practical modelling stacks place continuous time, discrete time, state machines and discrete-event models on one scale.

**Cited source.** `zheng_visual_2023`, page 16

**Matched passage.**

> Wu, M., Su, W., Chen, L., Liu, Z., Cao, W., & Hirota, K. (2019). Weight-adapted convolution neural network for facial expression recognition in human-robot interaction. IEEETransactions on Systems, Man, and Cybernetics: Systems, 51 (3), 1473-1484. https:// doi.org/10.1007/978-3-030-61577-2_5

## item 131

**Claim.** *Where the concept came from:* for the 2002 origin, for the naming history and the NASA definition, for the Apollo lineage, and for the question of whether twins are an evolution of modelling and simulation or something new.

**Cited source.** `grieves_digital_2017`, page 20

**Matched passage.**

> However, because of the importance of the visual sense, we are going to only focus on a Sensory Visual Test. We will leave it up to the reader to fashion tests for the other senses. It will be along the lines of the sensory visual test.

## item 132

**Claim.** Structural-health work in this family uses twin approaches for life prediction under unpredictable operational conditions, and monitoring engine wear and pressure tolerance is a standard cited application.

**Cited source.** `pezeshki_state_2023`, page 4

**Matched passage.**

> Table 1. List of signal processing methods compared in the study by Qarib and Adeli (2016)
> 
> | Non-parametric                                                                   | Parametric                                                                                                    |
> |----------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
> | Fourier transform Periodogram estimate of power spectral density WT EMD with HHT | Music EWT Pony method Matrix pencil method Estimation of signal parameters by rotational invariance technique |

## item 133

**Claim.** The principle is stated bluntly in the literature: every use of a model, twins included, depends critically on the model being applied only inside the range where it is valid.

**Cited source.** `lugaresi_digital_2025`, page 13

**Matched passage.**

> Dalibor, M., N. Jansen, B. Rumpe, D. Schmalzing, L. Wachtmeister, M. Wimmer et al . 2022. 'A Cross-Domain Systematic Mapping Study on Software Engineering for Digital Twins'. Journal of Systems and Software 193:111361 https://doi.org/https: //doi.org/10.1016/j.jss.2022.111361.

## item 134

**Claim.** Interoperability at this boundary is exactly what the standards work is for, and Chapter 13 covers it.

**Cited source.** `picone_harmonizing_2025`, page 8

**Matched passage.**

> M. Picone, M. Mamei, and F. Zambonelli, 'Wldt: A general purpose library to build iot digital twins,' SoftwareX , vol. 13, p. 100661, 2021.

## item 135

**Claim.** *Consulted, not drawn on above:* on visualisation as a service (Chapter 11), on platforms (Chapter 12), on human-in-the-loop as a named twin style, on mobility twins with a human driver, and on how other authors pin the same definitions, and on keeping models current, on domain-specific readings of the term, and on composing twins (Chapter 15), on adoption barriers, and on the standards landscape (Chapter 13).

**Cited source.** `gill_toward_2024`, page 1

**Matched passage.**

> Institute of Control Engineering of Machine Tools and Manufacturing Units University of Stuttgart, Germany

## item 136

**Claim.** You will hear the combination called a **differential-algebraic** system, and it is standard in engineering practice; lumped-parameter system models are routinely formulated either as pure-rate systems or as this combined kind, and equation-based tooling explicitly transforms the implicit combined system before handing it to a numerical solver.

**Cited source.** `carreira_foundations_2020`, page 209

**Matched passage.**

> Our new High-level Petri net drone controller is presented in Figure 7.11 On the first view we can see three distinct groupings for vertical movement , horizontal movement and orientation . Each one of these three groups contains one place with an initial token with value stay . The behaviour of the groups follows the same scheme. From the initial place we can use transitions to create tokens with different values. The transitions' preconditions are guarded. This means that if the token's value is stay , we can only fire transitions whose guards require a stay -token (there are two in each group). Once we fire the transition, the stay -token is consumed and a new one is produced. For example from the place altitude we can either fire a transition move up , which produces an up -token, or move down , that creates a down -token. This behaviour matches the pushing of a joystick on the drone's physical remote to either direction. There are two more transitions within this group that are guarded by up and down , respectively. Firing these transitions will consume the token respective token and produce a stay token. In other words, we can use them to 'reset' the token (i.e. to stop movement into that direction). On an actual drone remote, this behaviour matches the releasing of the drone's altitude joystick to neutral position. The groups that express the horizontal movement and orientation behave correspondingly.

## item 137

**Claim.** Handling discrete and continuous behaviour together in one principled execution is a named problem with named machinery, and it is Chapter 6's.

**Cited source.** `carreira_foundations_2020`, page 100

**Matched passage.**

> Many programming languages, e.g., Java and Ada as well as Modelica provide a safer and more systematic way of avoiding name collisions through the concept of package . A package is simply a container or name space for names of classes, functions, constants, and other allowed definitions. The package name is prefixed to all definitions in the package using standard dot notation. Definitions can be imported into the name space of a package.

## item 138

**Claim.** *Consulted, not drawn on above:* on scaling a decomposition from simple to complex twins, on an industrial-IoT architecture with an explicit human dimension, on adding humans as a first-class architectural element, on tooling, on model-driven construction, and for a framework mapped onto ISO 23247's entities.

**Cited source.** `xu_survey_2023`, page 6

**Matched passage.**

> For the Z-axis, the digital twin applications can be classified into three granularity levels for the digital replications, such as model, data&model, and data&model&process. The coarse-grained digital twin uses simulation data for the system models and generates simulation results [7]. The data&model case uses the real data for the physical process, computing platform, and communication network models [66]. Note that simulation data is generated by following certain statistical distributions and assumptions, whereas real data is collected from real-world smart IIoT systems. For the data&model&process case, the fine-grained digital twin collects real data, system models, and intercorrelated 3C processes. The fine-grained digital twin aggregates 3C processes and considers their intercorrelations.

## item 139

**Claim.** Also called parameter estimation. **Validation** -- did we build the *right* model?

**Cited source.** `gomes_calibration_2024`, page 3

**Matched passage.**

> where 𝑎 ∈ R and 𝑏 ∈ R are the parameters in the model that can be adjusted in the light of the experimental data and × is multiplication. This model represents the relation between system inputs and outputs, which means that if we suggest values for 𝑎 and 𝑏 are known, then using Eq. (6.2) we can predict the outputs of the system that correspond to the given inputs. So, to use the model, the values for 𝑎 and 𝑏 need to be estimated, i.e., Eq. (6.2) needs to be calibrated for the real system that can be observed.

## item 140

**Claim.** *Co-simulation:* is an empirical survey of practitioners and the source for macro step size and stability being hard in practice; gives the orchestration loop step by step; is a concrete master-algorithm implementation; places co-simulation inside multi-paradigm modelling; couples an architecture description to a simulation engine as a master algorithm.

**Cited source.** `carreira_foundations_2020`, page 100

**Matched passage.**

> Many programming languages, e.g., Java and Ada as well as Modelica provide a safer and more systematic way of avoiding name collisions through the concept of package . A package is simply a container or name space for names of classes, functions, constants, and other allowed definitions. The package name is prefixed to all definitions in the package using standard dot notation. Definitions can be imported into the name space of a package.

## item 141

**Claim.** **The PT changes faster than you can re-validate the model.** If the plant is reconfigured monthly, model maintenance may exceed the benefit.

**Cited source.** `alskaif_evolution_2025`, page 4

**Matched passage.**

> frequency

## item 142

**Claim.** *The box scale:* and for the systems-engineering framing, and for its use in structural and offshore work.

**Cited source.** `grieves_digital_2024`, page 11

**Matched passage.**

> 6. How well do you think the fresh university graduates are prepared as a Digital Twin expertise?

## item 143

**Claim.** *Synchronisation, staleness and lag:* for twinning rate and age of twin as measurable metrics, for time discrepancy as a problem in its own right, for state synchronisation, and for fidelity, synchronisation and integration treated together.

**Cited source.** `frasheri_addressing_2023`, page 3

**Matched passage.**

> (a) Read n (specified by the user) messages from the RabbitMQ queue, merge them with the FMU's internal queue and sort the result.

## item 144

**Claim.** This is the natural formalism for factory flow, queues, batches and resource contention, and it is used that way in twin practice -- reviews of smart-manufacturing twins report discrete-event simulation as the tool for process flow design and planning, including in non-automated processes, and roadmaps for twin construction list it among the formalisms to be chosen deliberately at design time alongside differential equations and Petri nets.

**Cited source.** `leng_digital_2021`, page 15

**Matched passage.**

> Table 2 Manufacturing system design cases for different manufacturing paradigms.
> 
> | Paradigms                | Mass Production                        | Mass Customization                            | Mass Individualization            |
> |--------------------------|----------------------------------------|-----------------------------------------------|-----------------------------------|
> | Typical Mfg. Systems     | Dedicated Production Line              | Flexible/ Reconfigurable Manufacturing System | Smart Manufacturing System        |
> | Design Goal              | Efficiency and Quality, etc.           | + Flexibility and Reconfigurability, etc.     | + Sustainability, etc.            |
> | Mfg. System Architecture | Unified Architecture                   | Modular Architecture                          | + Open Architecture               |
> | IP Protection Major      | Closed Source System Reliability, etc. | Closed Source + Module Reusbility,            | + Open Source + Cost Effectivity, |
> | Challenges               |                                        | etc. Furniture, Automobile                    | etc.                              |
> | Typical Industries       | Mobile Phone, Chemicals                |                                               | Apparel, Printed Circuit Board    |
> | Ref.                     |                                        | [119,152]                                     | [80,89,122,151,                   |
> |                          | -                                      |                                               | 153]                              |

## item 145

**Claim.** Industrial architecture guidance treats connectivity as a framework in its own right with a named middleware set.

**Cited source.** `heaton_platform_nodate`, page 30

**Matched passage.**

> The IEC 61131 Asset Administration Shell is a result of the collaboration between the Platform Industrie 4.0 and the ZVEI in Germany. It is a cross-platform data sharing service with a defined data exchange and packaging format (part 1 of the specification) as well as a standardized REST interface for hosting Asset Admin Shells in a web server (part 2 of the specification).

## item 146

**Claim.** *The platform view:* proposes assembling twins out of reusable parts and delivering them as a service, and is Chapter 3 Sec. 3.5.4's source; is a cloud-hosted instance of the same idea in construction; and show a working open framework built around a broker, including simulation and learned models side by side.

**Cited source.** `robles_opentwins_2023`, page 7

**Matched passage.**

> To sum up, the integration of the digital twin platform with KafkaML allows the provision of intelligence to digital twins through deep/ machine learning models and streaming data, and even to model the data disruption behavior of different sensors with the generation of simulated data.

## item 147

**Claim.** Comparative work notes it is a reference *model*, pitched too abstractly for code to be generated straight from it, and that is the honest summary: reach for ISO 23247 when you need a shared vocabulary with a manufacturing customer or an auditor, and for something closer to the code when you are assigning work to a team.

**Cited source.** `heithoff_model-based_2024`, page 27

**Matched passage.**

> Table 5.1 Placing of our reference architecture in the concepts of the Digital Twin Consortium reference architecture and in the concepts of the ISO-23247 standard
> 
> | Model-Driven Engineering DT Reference Architecture                    | Concept in the DTC Reference Architecture                                | Concept in ISO-23247                    |
> |-----------------------------------------------------------------------|--------------------------------------------------------------------------|-----------------------------------------|
> | Data Processor (Preprocessor, Processor, DS Caster) Process Discovery | Applications Analytics Synchronization Mechanisms                        | Data Collection Application and Service |
> | Evaluator                                                             | Applications Analytics                                                   | Application and Service                 |
> | Reasoner Conformance Checker                                          | Applications Analytics                                                   | Application and Service                 |
> | Executor                                                              | Applications Analytics Synchronization Mechanisms                        | Device Control                          |
> | Database Interface Database Layer                                     | Data Storage                                                             | Data Collection                         |
> | DT Cockpit                                                            | Integration Presenta- tion/Functions Visualization Services Data Storage | Resource Access and Interchange         |
> | Gateways                                                              | Integration Service Interfaces Platform APIs                             | Cross-System                            |
> | Process Orchestrator                                                  | Orchestration/Middleware                                                 | Operation and Management                |

## item 148

**Claim.** Deliver a rung that pays for itself, then climb.

**Cited source.** `van_schalkwyk_achieving_2023`, page 3

**Matched passage.**

> The recent pandemic will go down in history as one of the most disruptive, uncertain, and transformative times for people and organizations worldwide. Or, as one of my learned friends explained, 'overnight it exposed the systemic fragility in the operating capabilities of enterprises and organizations'.

## item 149

**Claim.** Related work pushes twins onto microservice and serverless runtimes across the edge-to-cloud continuum, and argues that fragmentation of protocols, formats and deployment architectures is itself the obstacle.

**Cited source.** `bellavista_exploiting_2024`, page 7

**Matched passage.**

> Table 1 Experimental evaluation: DT implementations, deployment locations, and adopted platforms.
> 
> | Acronym   | Name                                               | Deployment location   | Platform(s)                  |
> |-----------|----------------------------------------------------|-----------------------|------------------------------|
> | SCDT      | Serverless Cloud Digital Twin                      | Cloud                 | Microsoft Azure              |
> | SEDT      | Serverless Edge Digital Twin                       | Edge                  | Kubernetes and Fission       |
> | MDT       | Microservices Digital Twin                         | Edge                  | Kubernetes and WLDT          |
> | MDT-f     | MDT with Resource-Constrained Function Flexibility | Edge                  | Kubernetes and Extended WLDT |
