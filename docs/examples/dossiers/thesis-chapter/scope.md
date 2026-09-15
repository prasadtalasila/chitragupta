# Scope

- genre: thesis-chapter
- language: en-GB
- draft: content/drafts/thesis/methods.tex
- created: 2026-09-15
- corpus: 214 citekeys, digest `a31f0c4b77de`
- draft digest: not recorded (run `dossier stamp` once the draft is ready)

## Reader

The external examiner: a control engineer who has supervised
reduced-order modelling work but has never built a digital twin, and who
will read adversarially for the claim that outruns its evidence. They
have just read chapters 1-3, so the motivation is established and must
not be re-argued here.

## Covers

RQ2 only: under what conditions a reduced-order surrogate stays faithful
enough to support a safety decision. The chapter states what "faithful
enough" has meant in the literature, the methods that bound the error,
and why those bounds do not transfer to the setting of chapter 5.

## Does not cover

The empirical evaluation. That is chapter 5, and moving any of it here
would leave chapter 5 as a results table with no argument.

Learned surrogates (neural). Deliberate: the thesis' contribution is in
projection-based reduction, and the two literatures have different
notions of error entirely. Named in the chapter's own framing paragraph
so the examiner sees it as a decision.

Uncertainty *propagation*. The corpus supports it well, but it belongs
to RQ3 and appears in chapter 6.

## Glossary

- **Surrogate** -- any cheaper model standing in for the full-order
  simulation. Reserved for the projection-based kind in this thesis; a
  learned stand-in is called an emulator.
- **Fidelity** -- error on the quantities the safety decision depends
  on, never a global norm. Pinned here because three cited papers use it
  the other way and the chapter must not drift into their sense.
- **Error bound** -- a guarantee that holds for every admissible input,
  as opposed to an observed maximum error on a test set, which is called
  an empirical fit throughout.
- **Safety decision** -- a decision whose wrong answer has a
  consequence the operator cannot undo within the twin's update period.
