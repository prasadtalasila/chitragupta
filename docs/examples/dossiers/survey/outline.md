<!-- Outline. Edited by hand before drafting. Per `##`-or-deeper heading:
     `brief:` (steering, never appears in the draft) and/or one or more
     `claim:` blocks (your own prose, rewritten -- every sentence that
     can't be grounded is reported rather than shipped), and an
     optional `queries:` list of the search terms to run verbatim
     instead of the skill inventing sub-themes. A section needs at
     least a brief or a claim; queries: is optional -- plenty of
     sections are pure framing prose with nothing to search for.
-->

# Digital twins: fidelity, synchronisation and the validation gap

## Scope and how to read this survey

brief: Framing only. State the reader, the three themes, and the
exclusions from scope.md in two short paragraphs. No citations here --
the exclusions are ours to declare, not the literature's.

## What the field means by "digital twin"

brief: Establish that the term is contested before anything rests on it.
Three or four definitional families, each with its strongest proponent.
Do not adjudicate; the survey's own working definition is in the
glossary and belongs in the framing section above.

queries:

- digital twin definition
- digital twin taxonomy classification
- digital shadow versus digital twin

## Fidelity is chosen, not maximised

claim: Higher model fidelity is not uniformly better. It is chosen
against the decision the twin supports, and a more faithful model that
misses its deadline is worse than a coarse one that does not.

claim: The field has no shared threshold for "faithful enough", which is
why fidelity claims across papers are not comparable.

queries:

- digital twin model fidelity
- surrogate model accuracy tradeoff
- real time simulation deadline fidelity

## Keeping the twin in step with the asset

brief: The data half. Sampling rate, staleness, and what each paper does
when the link drops -- that last one is where the corpus is most
practical and least cited.

queries:

- digital twin data synchronisation latency
- sensor sampling rate state estimation
- intermittent connectivity state reconstruction

## Comparison of the surveyed approaches

brief: This is the table, not prose. One row per approach, columns for
fidelity treatment, synchronisation strategy, validation performed, and
domain. A row that repeats a sentence from above should lose the
sentence, not the row.

## Validation, and why it is mostly absent

claim: Most of this corpus validates against another model rather than
against the physical asset, and the papers that do validate against an
asset do so on a single installation.

brief: Be blunt. This is the gap the reader's thesis can occupy, and
softening it wastes the survey's most useful paragraph.

queries:

- digital twin validation verification
- model validation physical experiment
- simulation credibility assessment

## Gaps and what would close them

brief: Three or four, each phrased as a question a study could answer,
each traceable to a thin spot named above. No new citations -- if a gap
needs a source the reader has not met yet, it belongs in an earlier
section.
