# Recalibration of Models for Digital Twins

## Introduction

A digital twin is only as trustworthy as the model behind it, and every
model drifts. Sensors degrade, components wear, operating conditions
shift, and the physical asset a twin was calibrated against on day one is
rarely the asset it mirrors a year later. This chapter is about the
practice that keeps a twin honest over that lifetime: recalibration -- the
periodic or triggered re-estimation of a model's parameters against fresh
observations from the physical twin, rather than a one-time fit performed
at commissioning and never revisited.

The digital twin concept itself has matured quickly from a shipbuilding
and aerospace curiosity into a general pattern for cyber-physical systems
[@tao_digital_2019]. A twin is commonly described as a living model that
stays synchronized with its physical counterpart through a continuous
flow of sensor data, in contrast to a digital shadow that only observes
one direction of that flow [@liu_review_2021]. That synchronization
requirement is exactly what makes recalibration unavoidable: a twin that
never updates its own model parameters is not a twin, only a simulation
that happens to share a name with a real object [@qi_enabling_2021].

## Why models drift

Three sources of drift recur across the digital twin literature, and each
demands a different recalibration response. The first is physical
degradation of the asset itself -- wear, fatigue, corrosion -- which
changes the true parameters the model is supposed to represent
[@van_dinter_architecting_2023]. The second is sensor and instrumentation
drift, where the asset has not changed but the measurements feeding the
model have, silently biasing every downstream estimate. The third is
distributional drift in the operating envelope: a model validated on one
regime of temperatures, loads, or duty cycles is asked to extrapolate to
another it was never calibrated against.

Predictive maintenance applications make the cost of ignoring drift
concrete. A digital twin built for cable-joint degradation modelling, for
instance, has to track a slowly changing physical state over months or
years, and a model calibrated once at installation will systematically
mis-predict remaining useful life as that state evolves
[@van_dinter_architecting_2023]. Surveys of predictive-maintenance twins
consistently list model-updating and recalibration as an open, under-
addressed part of the pipeline, more often assumed than actually
implemented and evaluated in reported case studies
[@van_dinter_predictive_2022].

## Calibration as an inverse problem

Recalibration is, at its core, an inverse problem: given a model
structure and a stream of new observations, estimate the parameter
values that make the model's outputs consistent with what the physical
twin is now reporting. Gomes et al. frame the calibration of digital twin
models along exactly these lines, treating the ongoing update of model
parameters as a first-class part of the twin's lifecycle rather than a
one-off preprocessing step performed before deployment
[@gomes_calibration_2024]. Their framing treats a twin's model as a
living artifact with its own update schedule, not a fixed asset delivered
once and left alone.

That inverse-problem framing has direct consequences for how a
recalibration routine should be built. Because the mapping from
parameters to observed sensor readings is rarely invertible in closed
form, most practical recalibration schemes fall back on either
optimization (search for parameters that minimize a residual between
model and observation) or Bayesian updating (maintain a distribution over
parameters and update it as new evidence arrives). The choice between
them is not cosmetic: an optimization-based recalibration produces a
single best-fit parameter set and no direct notion of confidence in it,
while a Bayesian scheme naturally carries forward the uncertainty in that
estimate, which downstream twin consumers -- a remaining-useful-life
predictor, say -- can propagate rather than silently discard
[@gomes_calibration_2024].

As Gomes et al. put it directly, "calibration means estimating the values
for model parameters such that the model behaviour matches some
behavioural data derived from the real world" -- a definition this
chapter adopts throughout, and worth quoting exactly since it is the
working definition every later section builds on [@gomes_calibration_2024].

## Bayesian model updating and structural health monitoring

Structural health monitoring is one of the domains where Bayesian
recalibration has been worked out in the most operational detail, largely
because the cost of a wrong model is safety-critical rather than merely
inconvenient. Torzoni et al. describe a deep neural network surrogate
used inside a multi-fidelity Bayesian model-updating scheme, where the
expensive high-fidelity structural model is queried sparingly and a
cheap, trained surrogate absorbs most of the computational burden of
repeated recalibration [@torzoni_deep_2023]. The surrogate does not
replace calibration; it makes frequent calibration affordable, which is
the actual bottleneck once a structural digital twin is expected to
update on a timescale of hours rather than months.

This surrogate-assisted pattern generalizes beyond structural mechanics.
Any recalibration routine that would otherwise require repeated calls to
an expensive physics-based solver -- finite element models, computational
fluid dynamics, detailed thermal models -- faces the same tradeoff
Torzoni et al. resolve with a learned surrogate: either restrict
recalibration to a cadence the expensive solver can sustain, or invest in
a cheaper approximation that can be queried at the cadence the twin
actually needs [@torzoni_deep_2023]. Characterizations of digital twins
in structural mechanics make a similar point from the modelling side,
distinguishing a twin's physics-based backbone from the data-driven
components layered on top of it specifically to make frequent updates
tractable [@richstein_characterizing_2024].

## Uncertainty quantification as a recalibration primitive

A recalibrated model is only useful if a twin's consumers know how much
to trust it, which puts uncertainty quantification squarely inside the
recalibration problem rather than beside it. Thelen et al.'s review of
battery digital twins treats uncertainty quantification and optimization
as two of the roles a twin's modelling layer has to fill simultaneously,
alongside the physics-based or data-driven model itself
[@thelen_comprehensive_2022-1]. A battery twin that recalibrates its
capacity-fade model without also updating its confidence in that estimate
gives a false sense of precision exactly when degradation is accelerating
and the estimate matters most.

That same review frames uncertainty quantification as inseparable from
the twin's broader role in decision support: a maintenance or
operational decision downstream of the twin is only as good as the
uncertainty attached to the recalibrated parameters feeding it
[@thelen_comprehensive_2022-1]. This is the throughline connecting
Bayesian model updating in structural health monitoring back to
predictive maintenance more generally -- both treat the parameter
estimate and its uncertainty as a single recalibration output, not two
separate concerns computed by different teams at different times
[@torzoni_deep_2023].

## Triggering recalibration: scheduled, threshold, and event-driven

A recalibration routine has to decide not only how to update a model but
when. Three triggering strategies recur across the surveyed literature.
A scheduled trigger recalibrates on a fixed cadence -- daily, weekly,
after every maintenance cycle -- trading unnecessary recalibration during
stable periods for the simplicity of a predictable compute budget.
A threshold trigger instead watches a drift statistic, such as a residual
between model prediction and observation, and only recalibrates once that
statistic crosses a chosen bound. An event-driven trigger fires on
external signals -- a maintenance action, a sensor replacement, a known
change in operating regime -- that are known in advance to invalidate the
current calibration regardless of what the residual statistic currently
reads.

None of these strategies is universally correct, and the enabling-
technologies literature for digital twins treats trigger selection as a
platform-level design decision rather than a purely modelling one:
whichever strategy is chosen has to be supported by the twin's data
pipeline, since a threshold trigger is only as fast as the anomaly
detector feeding it and a scheduled trigger is only as cheap as the
compute the platform reserves for it [@qi_enabling_2021]. General surveys
of digital twin technology likewise treat the connection between
real-time data ingestion and model synchronization as one of the defining
technical challenges of the twin paradigm as a whole, independent of any
one domain's specific recalibration algorithm [@liu_review_2021].

## Recalibration in manufacturing and production twins

Manufacturing settings add a constraint the structural-mechanics and
battery examples do not share as sharply: a twin's model often has to
recalibrate while the physical process it mirrors keeps running, with no
tolerance for a maintenance window in which the model is simply wrong.
Foundational framings of the manufacturing digital twin scope this
requirement explicitly, describing the twin's model as something that
must track the physical process in near-real time across its entire
lifecycle rather than being fitted once during commissioning
[@tao_digital_2019]. The requirements documents that followed that
framing extended it into concrete scope statements for what a
manufacturing twin's synchronization layer -- and, by extension, its
recalibration cadence -- actually has to guarantee in production.

Predictive-maintenance twins built on top of a manufacturing or
industrial asset inherit both the degradation-driven and the
production-continuity constraints at once: the model has to track a
slowly degrading physical state, as in the cable-joint case, while never
falling far enough out of calibration to miss an actionable maintenance
window [@van_dinter_architecting_2023]. Systematic reviews of predictive
maintenance twins report this combination -- continuous operation plus
slow physical drift -- as the central reason recalibration is treated as
a first-class pipeline stage in mature implementations rather than an
afterthought bolted on once the base model stops performing
[@van_dinter_predictive_2022].

## A composite recalibration workflow

Drawing the preceding sections together, a recalibration workflow for a
production digital twin has four recurring stages, none of which is
optional in a mature deployment. First, a monitoring stage computes a
drift statistic from the residual between the current model's predictions
and the freshest sensor observations, feeding whichever trigger strategy
the platform has chosen [@qi_enabling_2021]. Second, a trigger evaluation
stage decides whether the current drift statistic, schedule position, or
external event justifies paying the cost of recalibration right now
rather than deferring it. Third, an estimation stage performs the actual
parameter update -- Bayesian or optimization-based, and increasingly
routed through a trained surrogate when the underlying physics-based
model is too expensive to query at the required cadence
[@torzoni_deep_2023]. Fourth, a validation stage checks the recalibrated
model against held-out observations before it is allowed to replace the
model currently driving the twin's decisions, closing the loop that
Gomes et al.'s calibration framing opens [@gomes_calibration_2024].

Every stage in that workflow carries its own uncertainty, and treating
uncertainty as a first-class output rather than an afterthought is what
separates a recalibration pipeline that supports real decisions from one
that merely keeps a model's point estimate current
[@thelen_comprehensive_2022-1]. A digital twin whose model recalibrates
promptly but reports an updated parameter with no attached confidence has
solved only half of the problem this chapter set out to describe.

## Recalibrating a fleet, not a single twin

Everything so far has described recalibration as though a digital twin
mirrors exactly one physical asset. Production deployments rarely look
like that: a manufacturer operates a fleet of nominally identical
machines, each with its own digital twin, and the recalibration problem
compounds across the fleet rather than staying isolated to one instance.
A naive approach recalibrates each twin independently, treating every
unit's drift as an unrelated estimation problem. That throws away
information: two units of the same machine type drifting in a similar
way is itself evidence about a shared root cause -- a batch of
out-of-spec components, a firmware change, a shift in the supplier's
manufacturing tolerances -- that a per-twin recalibration routine has no
way to see.

Community-level reporting on digital twin engineering practice has
started to treat this fleet-scale view as a first-class concern rather
than a hypothetical extension, describing shared calibration state and
cross-twin data pooling as recurring asks from practitioners running more
than a handful of twins in production [@qi_enabling_2021]. The
architectural implication is that a recalibration routine designed only
for a single twin instance -- fixed model, fixed parameter vector, fixed
trigger -- does not scale cleanly to a fleet without rethinking which
state is per-twin and which state is shared. A Bayesian formulation
handles this naturally in principle: a hierarchical prior over the
fleet's parameter distribution lets each twin's recalibration borrow
statistical strength from its siblings, and the same multi-fidelity
surrogate strategy that makes single-twin Bayesian updating affordable
extends directly to a fleet, since the expensive high-fidelity model is
shared across every unit that surrogate approximates
[@torzoni_deep_2023].

Manufacturing-specific framings of the digital twin concept anticipate
exactly this scaling requirement, describing a twin's model as something
that has to remain valid not just for one physical unit across its
lifecycle but across however many physical units the platform is asked to
represent simultaneously [@tao_digital_2019]. Requirements work that
followed those foundational framings pushed the same point into concrete
scope statements: a manufacturing digital twin platform's data
synchronization layer has to be specified at the fleet level from the
outset, not retrofitted once a second or third unit is onboarded. Recent
standards work on digital twin frameworks for manufacturing reflects the
same lesson, treating multi-asset scope as part of the baseline framework
rather than an extension profile bolted on afterward.

## Limitations and open problems

None of the recalibration machinery surveyed in this chapter is free, and
the literature is candid about where it still falls short. Surrogate-
assisted Bayesian updating trades an expensive physics-based query for a
cheap trained one, but that surrogate itself has to be trained,
validated, and -- eventually -- recalibrated against the physics-based
model it approximates, which reintroduces a smaller version of the exact
problem it was built to solve [@torzoni_deep_2023]. Reviews of
predictive-maintenance twins are similarly candid that most reported case
studies describe a recalibration strategy in principle without reporting
how often it actually triggered in a real deployment, which makes it
hard to compare triggering strategies on anything but qualitative grounds
[@van_dinter_predictive_2022].

Uncertainty quantification carries its own open problem: propagating a
calibrated parameter's uncertainty through every downstream consumer of a
digital twin -- a remaining-useful-life estimator, a scheduling
optimizer, a human operator reading a dashboard -- is conceptually
straightforward and operationally rare, because most twin platforms were
not built with an uncertainty-carrying data model from the start
[@thelen_comprehensive_2022-1]. Retrofitting that capability into an
existing twin platform is a larger undertaking than adding a
recalibration routine to a platform designed for it from day one, and the
literature surveyed here mostly describes the latter case rather than the
former. Finally, almost every recalibration strategy discussed assumes
the model structure itself is correct and only its parameters have
drifted -- a strictly narrower problem than structural model drift, where
the functional form the model assumes no longer matches the physical
asset at all. That harder problem -- deciding when a twin's model needs
to be replaced rather than merely recalibrated -- remains open across
essentially every domain this chapter has touched.

## A practical checklist

For a team building the recalibration layer of a new digital twin rather
than reading about someone else's, the preceding sections compress into
a short checklist worth stating plainly. Decide, in writing, which of
physical degradation, sensor drift, or operating-envelope shift the twin
is actually expected to track, since each implies a different monitoring
signal and a different validation test for "did the recalibration help."
Pick a triggering strategy that the platform's data pipeline can actually
support at the required cadence, rather than the strategy that reads best
on paper -- a threshold trigger is worthless if the anomaly detector
feeding it lags the process it is meant to catch [@qi_enabling_2021].
Choose, explicitly, whether the estimation stage needs to carry
uncertainty forward, and if it does, verify that every downstream
consumer of the twin's output can actually accept a distribution rather
than a point estimate before promising that capability to stakeholders
[@thelen_comprehensive_2022-1]. Budget for surrogate maintenance if a
surrogate is used to make Bayesian updating affordable, since the
surrogate is itself a model subject to the same drift problem this
chapter describes [@torzoni_deep_2023]. And if the twin is one of a
fleet rather than a singleton, decide early which calibration state is
shared and which is per-unit, because that decision is far more
disruptive to retrofit after the fact than to design in from the start.

None of these are algorithmic decisions in the narrow sense; they are
scoping decisions that determine which algorithm is even appropriate.
A team that settles them clearly before writing the estimation code
tends to end up with a recalibration layer that matches the maintenance
literature's account of what mature deployments actually do
[@van_dinter_predictive_2022], rather than a research prototype that
recalibrates beautifully in a notebook and never runs unattended in
production.

## Conclusion

Recalibration is not a maintenance chore bolted onto an otherwise-finished
digital twin; it is one of the properties that makes something a digital
twin rather than a static simulation carrying a fashionable name
[@qi_enabling_2021]. The literature surveyed here converges on a small
number of durable ideas: treat calibration as an ongoing inverse problem
rather than a one-time fit [@gomes_calibration_2024], use surrogates to
make Bayesian updating affordable at the cadence a twin actually needs
[@torzoni_deep_2023], carry uncertainty forward through every
recalibration rather than discarding it at the point estimate
[@thelen_comprehensive_2022-1], and choose a triggering strategy that
matches the platform's data pipeline rather than the algorithm's
theoretical elegance [@liu_review_2021]. A twin that gets all four right
stays trustworthy for as long as the asset it mirrors keeps changing,
which, for any physical asset, is for as long as it exists
[@van_dinter_architecting_2023].
