# Cloud Computing Technologies for Digital Twins

## Introduction

A digital twin does not run on the physical asset it mirrors. It runs
somewhere else -- a data center, an edge node bolted to a factory wall, a
Kubernetes cluster shared with a hundred other workloads -- and the choice
of where, and how that "somewhere else" is built, shapes almost every
other property the twin ends up having. This chapter is about that choice:
the cloud computing technologies that host a digital twin's model,
synchronize it with sensor data, and scale it from a single prototype to a
fleet of thousands.

The digital twin literature increasingly treats this as a first-class
architectural concern rather than deployment detail. A reference
architecture for cloud-based cyber-physical systems frames the twin
explicitly as a cloud-hosted counterpart to a physical object, with the
cloud layer responsible for the computation the physical device itself
cannot afford [@alam_c2ps_2017]. That framing has held up, but the
technology underneath it has not stood still: what "cloud-hosted" meant in
2017 -- a monolithic service in a data center -- is a small and
increasingly uncommon corner of what it means now.

## Cloud-native foundations: containers, microservices, orchestration

Most modern digital twin platforms are not single programs. They are
collections of small, independently deployable services -- one for
ingesting sensor data, one for running the physics model, one for serving
a dashboard -- packaged as containers and coordinated by an orchestrator.
This pattern, cloud-native computing, is not specific to digital twins; a
recent survey frames it broadly as a way of building and operating
applications that exploits the elasticity and distributed nature of the
cloud rather than merely renting a cloud provider's virtual machines to
run the same monolith a data center would have run [@deng_cloud-native_2024].
What makes it relevant here is that a digital twin's own structure --
many loosely coupled concerns, wildly different resource profiles, a need
to scale one part (ingestion) independently of another (rendering) --
is close to the textbook case cloud-native architecture was designed for.

Containers are the packaging unit underneath nearly all of this.
Kubernetes has become the default way to run many containers as one
coherent application, handling scheduling, restart, and networking so
that an individual twin's services do not have to reimplement any of it
[@deslauriers_everyday_2022]. That default has architectural consequences
for a twin platform: once a fleet of Kubernetes clusters is available,
whether one twin instance runs in the same cluster as another, or on a
cluster physically close to the asset it mirrors, becomes a scheduling
decision rather than a hand-wired deployment choice.

Splitting a monolithic twin into microservices is not free, though.
A systematic review of deployment and communication patterns in
microservice architectures catalogs the recurring failure modes --
cascading latency across service boundaries, inconsistent state when two
services disagree about the asset's current condition, and operational
complexity that grows faster than the number of services does
[@karabey_aksakalli_deployment_2021]. A digital twin platform inherits
every one of these risks the moment it adopts the pattern, and gets none
of the benefits for free just by containerizing what used to be one
program.

## Serverless and event-driven digital twins

Where cloud-native computing asks "how do we package and deploy this",
serverless computing asks a sharper question: does this code need to be
running at all when nothing is happening? A digital twin's ingestion and
recalibration logic is naturally event-driven -- it has real work to do
exactly when a new sensor reading arrives, and nothing to do between
readings -- which is precisely the shape serverless platforms are built
to exploit. Wermann et al.'s KTWIN platform builds a digital twin runtime
directly on Kubernetes-native serverless primitives, scaling a twin's
compute to zero when its physical counterpart is idle and back up the
moment new telemetry arrives, rather than paying for an always-on service
per twin instance [@wermann_ktwin_2024].

Bellavista et al. push this further, arguing that microservices and
serverless functions are not just an implementation convenience for
digital twins but the right default across the whole cloud-to-edge
continuum: a twin's heavier, less latency-sensitive components (model
training, long-horizon simulation) run as cloud microservices, while its
latency-critical components (safety interlocks, real-time control) run
as functions pushed out to the edge, with the same event-driven
programming model spanning both [@bellavista_exploiting_2024]. That
symmetry -- one execution model, two placements -- is what makes the
cloud-to-edge continuum a coherent architecture rather than two separate
systems bridged by custom glue code.

Serverless is not free of its own costs, though. A survey of serverless
edge computing is candid that cold-start latency -- the delay before a
scaled-to-zero function is ready to handle its first request -- is the
technology's most persistent unsolved problem, and it matters more at the
edge than in a data center because edge hardware is smaller and slower to
spin up a fresh execution environment on [@raith_serverless_2023]. For a
digital twin whose safety-relevant control loop is implemented as an edge
function, a cold start is not an inconvenience; it is a window where the
twin is not actually watching its physical counterpart.

## The edge-cloud continuum

"Cloud" and "edge" increasingly name two ends of one continuum rather
than two separate systems a twin platform has to choose between. Savaglio
et al. describe generative digital twins explicitly in these terms: a
twin whose model itself is partly generated and adapted at runtime needs
compute close to the asset for the adaptation loop's latency, and compute
in the cloud for the heavier generative process feeding it, with the
continuum's job being to make that split invisible to the twin's own
logic [@savaglio_generative_2025]. Orchestration platforms built
specifically for this continuum, like MiCADO-Edge, treat "which tier runs
this container" as a policy the orchestrator resolves at deploy time
rather than a decision baked into the application, which is what makes
moving a twin's workload from edge to cloud (or back) an operational
choice instead of a rewrite [@ullah_micado-edge_2021].

Structural health monitoring is one of the domains where this continuum
has been worked out most concretely, because the alternative -- running
everything in the cloud -- has a latency and bandwidth cost that is
simply not acceptable for a bridge or a building under continuous sensor
load. Gigli et al.'s edge-cloud continuum architecture for structural
health monitoring pushes anomaly detection to the edge, where it can run
on every incoming reading without a network round trip, and reserves the
cloud tier for the twin's long-horizon model updates and cross-structure
comparison -- work that benefits from more compute and does not need to
happen in real time [@gigli_next_2024]. Martin et al. describe a closely
related edge/fog/cloud architecture for civil infrastructure monitoring,
with the same three-tier shape and the same underlying reasoning: latency-
critical processing stays close to the sensor, and anything that can
tolerate delay moves toward the tier with more compute available
[@martin_facilitating_2022].

## Resource scheduling and task offloading

Once a digital twin's workload can run at multiple tiers, something has
to decide, continuously, where each piece of it actually runs -- this is
the task offloading and resource scheduling problem, and it is where a
meaningful fraction of recent digital twin systems research concentrates.
Xu et al. treat this as an optimization problem specific to distributed
edge computing networks: given a digital twin's current workload and the
edge network's current capacity, choose a task-to-node assignment and a
virtual object placement that minimizes latency without overloading any
one edge node [@xu_optimized_2023]. Zhou et al. work the same problem
from the resource-scheduling side for a different domain -- 5G-connected
distribution grids -- where a digital twin has to make a scheduling
decision that is both latency-aware and secure, since a compromised
scheduling decision in a power distribution context is not merely a
performance regression [@zhou_secure_2022].

What both share is the recognition that a digital twin's resource
placement problem is not static. A twin commissioned to run entirely at
the edge can find itself starved of compute the moment its model grows
more complex, and a twin commissioned to run entirely in the cloud can
find its safety-relevant control loop unacceptably slow the moment
network conditions degrade. The systems that treat placement as a
continuous, re-evaluated decision -- not a one-time deployment choice --
are the ones built to survive either failure mode.

## Data movement and storage across the continuum

Every layer described so far assumes data can move cheaply between
tiers, and that assumption is not free either. A digital twin ingesting
high-frequency sensor data faces a storage and query problem before it
faces a compute problem: raw time series from hundreds of sensors,
sampled continuously, is expensive to store in full at every tier and
slow to query if it has to be pulled back from the cloud every time an
edge component needs recent history. ModelarDB addresses this directly
for the digital twin setting by storing time series as compact models
rather than raw samples, and by keeping that model-based representation
consistent whether the query is answered at the edge, in the cloud, or
by a client application -- one representation, queried the same way
regardless of which tier is physically holding it at the time
[@jensen_modelardb_2023]. That consistency is what lets an edge component
answer "what has this sensor read for the last hour" without a network
round trip, while the same historical data remains queryable from the
cloud tier for the twin's longer-horizon analysis.

The alternative -- storing raw data at the tier that produced it and
shipping copies elsewhere on demand -- is simpler to build and is what
most first-generation twin platforms actually do, but it reintroduces
exactly the latency-versus-completeness tension the rest of this
chapter's architecture is built to avoid: a query that needs data from
two tiers now pays for a network round trip regardless of how well the
compute layer above it is orchestrated. A model-based, tier-consistent
storage layer is not a cosmetic optimization on top of a working
edge-cloud architecture; it is what keeps the compute layer's tier
independence from being undermined by the storage layer underneath it.

## Security and multi-tenancy

A cloud-native digital twin platform is, by construction, a multi-tenant
system: the same Kubernetes clusters, the same serverless runtimes, and
increasingly the same multi-cloud infrastructure host more than one
twin, more than one customer, and more than one trust boundary at once.
Chandramouli et al.'s zero trust architecture model for cloud-native,
multi-cloud applications treats this as the default threat model rather
than an edge case: no request is trusted merely because it originated
inside the platform's own network perimeter, and every service-to-service
call -- including calls between a twin's own microservices -- has to
authenticate and authorize independently [@chandramouli_zero_2023]. For a
digital twin whose microservices span a cloud-to-edge continuum with
orchestration decisions made at deploy time and runtime alike, that
per-call authentication is not optional hardening; it is the only model
that still makes sense once "which physical machine is this service
running on" is a question the orchestrator answers dynamically rather
than a fact baked into a network diagram.

Multi-tenancy compounds the platform risks the earlier sections already
named. A cold-start delay in one tenant's serverless function is an
inconvenience; a scheduling decision that lets one tenant's workload
starve another tenant's latency-critical control loop of edge compute is
a much more serious failure, and it is exactly the kind of cross-tenant
interference a shared cloud-to-edge continuum makes structurally
possible in a way a dedicated, single-tenant deployment never was. None
of the resource-scheduling systems surveyed earlier in this chapter treat
multi-tenant isolation as a first-class scheduling constraint alongside
latency and cost -- which is a gap worth naming plainly, since it is
precisely the gap a zero-trust security model addresses at the network
layer but does not, by itself, solve at the scheduling layer above it.

## A reference shape

Drawing the preceding sections together, a cloud-native digital twin
platform converges on a recurring shape across the systems surveyed here,
even though no two of them describe it in exactly the same words. An
ingestion layer, close to the physical asset, accepts sensor data and
performs the latency-critical part of the twin's logic -- often as an
edge-deployed serverless function, for the reasons Wermann et al. and
Bellavista et al. both argue [@wermann_ktwin_2024; @bellavista_exploiting_2024].
A model layer, typically running as one or more cloud-hosted
microservices, holds the twin's heavier computation: simulation, model
recalibration, cross-asset comparison -- work that tolerates latency and
benefits from the cloud's larger compute pool [@deng_cloud-native_2024].
An orchestration layer decides, continuously, which tier each piece of
work actually runs on, informed by current network and resource
conditions rather than a fixed deployment map
[@ullah_micado-edge_2021; @xu_optimized_2023]. And a scheduling policy
underneath all three balances latency, cost, and -- in domains where it
matters, such as grid infrastructure -- security, rather than optimizing
any single one of those in isolation [@zhou_secure_2022].

None of these four layers is optional in a system meant to run
unattended for the asset's whole lifecycle. A twin missing the
orchestration layer is really just two separately deployed systems (an
edge component and a cloud component) that happen to share a name; a
twin missing the scheduling policy inherits whatever placement its
developers guessed was right on day one and never revisits it, the same
staleness problem a model's own parameters have if nobody recalibrates
them.

## Limitations and open problems

The cloud-to-edge continuum this chapter describes is not a solved
problem, and the systems surveyed here are candid about where it still
falls short. Cold-start latency remains serverless edge computing's
central unsolved cost, and no platform surveyed here claims to have
eliminated it -- only to have engineered around it for their specific
workload shape, which does not necessarily generalize
[@raith_serverless_2023]. Microservice decomposition, similarly, trades
one set of problems (a monolith's inflexibility) for another
(cross-service latency, partial-failure handling, and the operational
burden of running many small things instead of one big one), and the
systematic review of deployment patterns is explicit that most published
architectures under-report the operational cost side of that trade
[@karabey_aksakalli_deployment_2021].

Continuous resource scheduling across a cloud-to-edge continuum is
harder still to evaluate rigorously: both scheduling systems surveyed
here are validated against simulated or narrowly scoped deployments
rather than a long-running production fleet, which is a reasonable
starting point but leaves open how a scheduling policy tuned in
simulation degrades against the messier failure modes -- partial network
partitions, a node silently underperforming rather than cleanly failing
-- that a real multi-year deployment eventually produces
[@xu_optimized_2023; @zhou_secure_2022]. And every architecture surveyed
here assumes the orchestration layer itself is trustworthy and
available; none directly addresses what a digital twin platform should
do when the orchestrator, not the twin, is the component that has
failed.

## Choosing among these technologies

None of the technologies surveyed in this chapter is a default a team
should reach for without first asking what their own twin's workload
actually looks like. A twin whose safety-relevant logic tolerates
sub-second cold starts, or whose physical counterpart produces sensor
readings only intermittently, is a strong candidate for the serverless,
scale-to-zero pattern Wermann et al. and Raith et al. both describe
[@wermann_ktwin_2024; @raith_serverless_2023]; a twin with a genuinely
continuous, latency-critical control loop -- a robot arm, a grid
protection relay -- is not, and forcing it onto a scale-to-zero runtime
just to follow the pattern trades a real correctness risk for an
architectural fashion.

Similarly, splitting a twin's logic into microservices is worth its
operational cost only when the components actually need to scale
independently or be owned by different teams; a small, single-purpose
twin gains little from the pattern and inherits all of the cross-service
latency and partial-failure risk the deployment-patterns review catalogs
[@karabey_aksakalli_deployment_2021]. The edge-cloud continuum
architectures surveyed here earn their complexity specifically in
domains -- structural health monitoring, grid infrastructure, mobile
robotics -- where the latency cost of a purely cloud-hosted twin would be
unacceptable and the compute cost of a purely edge-hosted one would be
unaffordable [@gigli_next_2024; @martin_facilitating_2022; @zhou_secure_2022].
A twin that fits comfortably inside one data center's own compute budget,
talking to an asset that tolerates a few hundred milliseconds of latency,
does not need a continuum at all, and adopting one anyway is complexity
spent on a problem the twin never had.

The practical takeaway is not "use serverless" or "use microservices" or
"deploy at the edge" as a rule of thumb -- it is that every technology in
this chapter trades a specific cost for a specific benefit, and the
right architecture is the one where that trade actually matches the
twin's own latency, scale, and operational constraints, not the one that
happens to be the most discussed in the current literature.

## Migrating twin state across the continuum

A related and easily overlooked problem is what happens to a twin's own
in-flight state when its workload actually moves between tiers rather
than merely being scheduled there from the start. Handoff matters
because a twin migrating mid-computation cannot simply restart from
scratch without losing continuity with the physical asset it mirrors.
Earlier work on this problem focused on the Web of Things setting: we
rigorously formulate the WT allocation as a multi-objective optimization
problem and propose a graph-based heuristic, describing a stateful
migration process for web things moving between hosts as network and
load conditions change. The same handoff discipline -- state preserved
across a migration, not merely the code -- applies just as directly to a
digital twin moving between edge and cloud tiers.

## Conclusion

Cloud computing technology has moved a long way past "the twin's model
runs on a rented virtual machine somewhere", and the digital twin
literature has moved with it. A twin today is more accurately described
as a small distributed system spanning a continuum from edge to cloud,
built from containerized microservices, increasingly event-driven and
serverless at its latency-sensitive edges, and held together by an
orchestration and scheduling layer that treats placement as a continuous
decision rather than a one-time deployment choice
[@alam_c2ps_2017; @deng_cloud-native_2024; @ullah_micado-edge_2021]. The
throughline across every domain surveyed here -- structural health
monitoring, distribution grids, cognitive robotics -- is that the right
cloud architecture is the one that puts each piece of a twin's logic at
the tier best suited to its own latency and compute needs, and keeps that
placement free to change as conditions do
[@gigli_next_2024; @martin_facilitating_2022; @niedzwiecki_cloud-based_2024].
Getting the architecture right does not make a twin's model any more
accurate; it makes the twin capable of running the accurate model it has,
continuously, for as long as the asset it mirrors keeps operating.
