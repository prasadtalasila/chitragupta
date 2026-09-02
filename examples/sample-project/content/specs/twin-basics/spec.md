# Digital Twin Basics

- reader: an engineer new to digital twins who will operate one, not build one
- scope: vocabulary, keeping a twin honest, and integration; deliberately no vendor tooling

## Part I: What a Twin Is {#part-what}

### Vocabulary and levels of integration {#ch-vocabulary}

Establish the model/shadow/twin distinction as a property of data flow,
and why holding it strictly keeps expectations honest.

#### The three levels {#sec-levels}

Model, shadow, twin -- each defined by its data flow.

#### What a twin is for {#sec-uses}

Monitoring, prediction, optimisation, record-keeping.

## Part II: Keeping It Honest {#part-honest}

### Synchronisation and staleness {#ch-staleness}

The twin must know its own age: synchronisation strategies, staleness
budgets, and marked reads.

#### Synchronisation strategies {#sec-sync}

Pull, push and event-driven flows, and what each costs.

#### Marked reads {#sec-marked}

Staleness budgets from decision physics; every read carries its age.
