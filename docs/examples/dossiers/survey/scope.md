# Scope

- genre: survey
- language: en-GB
- draft: content/drafts/dt/survey.md
- created: 2026-09-15
- corpus: 214 citekeys, digest `a31f0c4b77de`
- draft digest: not recorded (run `dossier stamp` once the draft is ready)

## Reader

A first-year PhD student who has a control-engineering background, has
read perhaps five digital-twin papers, and needs to know what the field
agrees on, where it contradicts itself, and which questions are still
open enough to build a thesis on.

## Covers

Definitional families and how they differ; fidelity as a design choice
rather than a quality score; synchronisation between asset and model,
including staleness and dropped links; and validation practice -- how
little of it exists, and what the papers that attempt it actually do.

## Does not cover

Vendor platforms and middleware: the corpus holds three papers naming
products, none of which compares them, so anything written here would be
a summary of marketing rather than of evidence.

Manufacturing-floor case studies. Deliberate -- the reader's thesis is
in water infrastructure, and the transfer argument is a section of their
own chapter rather than of this survey.

Security and access control. **Not a scoping judgement but a corpus
one**: seven candidates were retrieved and all seven were position
papers with no evaluation, so the theme is named here rather than
written thinly.

## Glossary

- **Digital twin** -- a virtual representation of an asset with
  automatic, bidirectional data flow between the two.
- **Digital shadow** -- automatic flow from asset to model only. The
  distinction is load-bearing in this survey: several papers claim
  "twin" for what this definition calls a shadow.
- **Fidelity** -- how closely the model reproduces the asset's behaviour
  *on the quantities the twin's decision depends on*, never in general.
- **Staleness** -- the age of the newest synchronised value, in seconds.
- **Validation** -- comparison of twin output against measurements from
  the physical asset. Reserved for that; agreement between two models is
  called cross-verification here.
