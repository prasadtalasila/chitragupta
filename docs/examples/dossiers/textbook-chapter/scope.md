# Scope

- genre: textbook-chapter
- language: en-GB
- draft: content/drafts/course/ch3-state-estimation.md
- created: 2026-09-15
- corpus: 214 citekeys, digest `a31f0c4b77de`
- draft digest: not recorded (run `dossier stamp` once the draft is ready)

## Reader

Second-year undergraduates who have had one linear-algebra course and no
signals or probability course beyond a first module. They have seen a
mean and a variance; they have not seen a covariance matrix, and will
not in this chapter.

## Covers

Why a raw measurement is not enough; the one-dimensional estimator built
from two variances; two steps worked by hand with every number shown; a
faded example the student finishes; and an honest section on which
assumptions break in practice.

Learning objectives, in the chapter's own words -- by the end a student
can:

1. state what a state estimator does and why a raw reading is not enough;
2. derive the one-dimensional update from the two variances;
3. hand-compute two steps on given numbers;
4. say when the assumptions fail and what happens then.

## Does not cover

The matrix form. That is chapter 4, and reaching for it here would cost
the derivation its arithmetic-only property, which is the whole reason
this chapter comes first.

Nonlinear filters entirely. Named in "where to go next" so a curious
student knows the word, with no treatment.

Implementation. There is no code in this chapter -- students who want to
build one are pointed at the lab, which is a tutorial and a separate
document.

## Glossary

- **State** -- the quantity we want to know and cannot measure directly.
  Used consistently; never "the system" or "the value".
- **Measurement** -- a single noisy observation.
- **Estimate** -- our current best guess of the state, always paired
  with its variance. A number without its variance is never called an
  estimate in this chapter.
- **Gain** -- the weight given to a new measurement against the current
  estimate, between 0 and 1.
- **Innovation** -- measurement minus predicted measurement. Introduced
  only in the "where to go next" section; not used in the derivation.
