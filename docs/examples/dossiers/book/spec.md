# Composable Twins {#book}

This outline is signed before any prose is generated. Text up here is
the preamble: it belongs to no heading, is never handed to a generator,
and exists for whoever opens the file next. Audience: practising
engineers who have built one twin and are now asked for five.

## Part I: Foundations {#part-i}

### What a twin is, and is not {#ch-what}

Establish the vocabulary the rest of the book leans on, and settle the
twin/shadow distinction early -- later chapters assume it. Must not
drift into architecture; that is Part II's job.

#### The model half {#sec-model}

What the model must reproduce, and the fidelity question stated but not
answered. The answer is `ch-fidelity`.

#### The data half {#sec-data}

Synchronisation, sampling and staleness, as vocabulary only.

### What a twin costs {#ch-cost}

The honest chapter. Build cost, maintenance cost, and the cost of a twin
nobody trusts. Leans on `ch-what`'s vocabulary and nothing else.

#### What you pay to build one {#sec-build-cost}

#### What you pay to keep one {#sec-keep-cost}

## Part II: Building one {#part-ii}

### Choosing fidelity {#ch-fidelity}

Answers the question `sec-model` raised. This is the book's technical
core and the chapter most likely to need two passes.

#### Fidelity against a decision {#sec-decision}

The chapter's central claim: fidelity is chosen against the decision the
twin supports, never maximised in the abstract.

#### When more fidelity makes things worse {#sec-worse}

The deadline argument. A more faithful model that misses its update
window is worse than a coarse one that does not.

### Keeping it in step {#ch-sync}

Staleness, dropped links, and what an operator should see when the twin
is behind. Cross-references `sec-data` for the vocabulary it does not
re-introduce.

#### Staleness, and how to show it {#sec-staleness}

#### When the link drops {#sec-dropped}

## Part III: Living with one {#part-iii}

### Trust and what earns it {#ch-trust}

Why an operator ignores a twin that has been wrong once, and what the
literature says about rebuilding that. Leans on `ch-cost`'s "cost of a
twin nobody trusts" and pays it off.

### Where this goes next {#ch-next}

Short. Open problems, with the validation gap named as the largest.
No new vocabulary.
