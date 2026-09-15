<!-- Outline. Edited by hand before drafting. Per `##`-or-deeper heading:
     `brief:` (steering, never appears in the draft) and/or one or more
     `claim:` blocks (your own prose, rewritten -- every sentence that
     can't be grounded is reported rather than shipped), and an
     optional `queries:` list of the search terms to run verbatim
     instead of the skill inventing sub-themes.

     A textbook chapter has few queries: most sections are the author's
     own explanation, with nothing to retrieve. That is expected here
     and not a thin outline.
-->

# Chapter 3 -- Estimating what you cannot measure

## Learning objectives

brief: The four objectives from scope.md, verbatim, as a numbered list.
No prose around them -- students skim this box before and after reading,
and framing sentences get in the way both times.

## Why a raw measurement is not enough

brief: Motivate before mechanism. One concrete scenario -- a delivery
robot whose wheel encoder drifts while its ultrasonic range-finder
jitters -- introduced here and carried through every example in the
chapter. Do not introduce a second scenario later.

queries:

- state estimation sensor noise motivation

## Two numbers, not one

brief: The idea that an estimate carries a variance. This is the
conceptual hinge of the chapter; if a student stops here they should
still have gained something real.

## The update, derived

brief: Build the gain from the two variances. Arithmetic only -- no
matrices, no integrals, no probability density functions. Show that the
gain lands between 0 and 1 and say in words what each extreme means.

## Worked example: two steps by hand

brief: Fully worked, every number shown, using the delivery robot's
numbers. Then immediately a faded version: same structure, the student
supplies step two. Give the answer to the faded one at the end of the
chapter, not inline.

## When the assumptions fail

brief: Non-Gaussian noise and an unmodelled bias, in that order, each in
a short subsection with the symptom a student would actually observe.
Honest about what breaks -- this is where the students who go on to
research get interested, and a chapter that pretends the method always
works loses them.

queries:

- kalman filter assumption violation bias
- sensor fault detection residual

## Exercises

brief: Six. Two that mirror the worked example with new numbers, two
that require reasoning about the gain's behaviour, one that asks what
happens when a measurement is missing entirely, and one open-ended.
Hints for the last two, full solutions for the first four.

## Summary, and where to go next

brief: Half a page of summary against the four objectives, then the
pointers: the matrix form in chapter 4, the lab for building one, and
one or two corpus papers for a student who wants the research framing.

queries:

- state estimation introduction survey
