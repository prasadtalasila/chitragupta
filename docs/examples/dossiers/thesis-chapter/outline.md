<!-- Outline. Edited by hand before drafting. Per `##`-or-deeper heading:
     `brief:` (steering, never appears in the draft) and/or one or more
     `claim:` blocks (your own prose, rewritten -- every sentence that
     can't be grounded is reported rather than shipped), and an
     optional `queries:` list of the search terms to run verbatim
     instead of the skill inventing sub-themes.
-->

# Chapter 4 -- When a surrogate is faithful enough (RQ2)

## Why the question arises here

brief: Two paragraphs. Connect to chapter 3's result -- the full-order
model missed its deadline on 40% of the operating envelope -- and say
what RQ2 asks. No literature dump; the examiner has just read three
chapters and wants the thread, not a re-introduction.

## What "faithful enough" has meant

claim: Fidelity in this literature is defined against a decision rather
than in the abstract, but the field has no shared threshold, so
published fidelity claims are not comparable across papers.

brief: This section carries the chapter's terminology load. Every term
in the glossary should be used in its pinned sense at least once here,
because the examiner reads later sections against this one.

queries:

- surrogate model fidelity criterion
- reduced order model validation
- model accuracy requirement safety critical

## Methods that bound the error

brief: The technical core. Prefer a source that states a bound over one
that reports an empirical fit -- and where a paper reports a fit and
calls it a bound, say so rather than repeating its claim.

queries:

- reduced order model error bound
- a posteriori error estimator projection
- surrogate uncertainty quantification

### Projection-based bounds

brief: The family this thesis extends. Deepest treatment in the chapter.

queries:

- proper orthogonal decomposition error bound
- greedy reduced basis a posteriori

### Bounds that assume linearity

claim: The available a-priori bounds assume a linearity that the
water-network model of chapter 5 does not satisfy anywhere near its
operating point.

queries:

- error bound linear assumption violated
- nonlinear model order reduction guarantee

## Why the existing bounds do not transfer

brief: The gap that motivates chapter 5, argued rather than asserted.
Be explicit that the argument is mine and mark exactly which step the
corpus supports and which it does not -- an examiner will find the seam
anyway, and finding it flagged reads as rigour.

queries:

- error bound assumptions violated nonlinear
- reduced model extrapolation operating envelope

## What this chapter establishes

brief: Half a page. State what RQ2 is now answered with, and hand over
to chapter 5. No new citations.
