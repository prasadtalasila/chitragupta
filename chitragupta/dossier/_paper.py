"""`paper.md`: the human's own paper-level inputs for a research paper.

The one genre whose evidence is partly the author's own software and
results (`sources/<software>/code/` and `.../results/`). Per-section
intent stays in `outline.md`; the software, venue, message and
contributions are here. Headings follow the Researchers' Bible's
message (section 8) and the Stanford InfoLab introduction questions
(plans/1179-research-paper-genre.md).
"""

GENRE = "research-paper"

PAPER_TEMPLATE = """<!-- Paper. Edited by hand before drafting; the skill never writes it.

     The list below is the paper's frame. `software:` is the directory
     holding `code/` and `results/`; `results/MANIFEST.md` there says
     what each result file measures. -->

- software: sources/<software-name>
- venue: not settled
- template: not settled (IEEEtran, acmart or llncs)
- pages: not settled
- reader: not settled

## Message

<!-- A few sentences, each one step of the argument the paper makes.
     The title, abstract, introduction and conclusion all state it. -->

## Problem

<!-- What is the problem? -->

## Why it matters

<!-- Why is it interesting and important? -->

## Why it is hard

<!-- Why do naive approaches fail? -->

## Why prior work falls short

<!-- What is wrong with previous solutions, and how does this one
     differ? Declare the literature to compare against as queries,
     spelled as in outline.md, and run verbatim:

     queries:
     - <a query> -->

## Approach

<!-- The key components of the approach and its results, with their
     limitations. -->

## Contributions

<!-- One bullet each, naming the section that delivers it and the
     evidence for it: `result <id>` from the manifest, or
     `code <path>` under the software directory.

     - C1: <the contribution>
       section: <section id>
       evidence: result <id> -->

## Research questions

<!-- - RQ1: <the question>
       answered-by: <manifest id> -->

## Known threats

<!-- What could make the results wrong or narrow. -->
"""
