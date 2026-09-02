# Uncited prose: content/drafts/dt-overview/survey.md

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/survey.md`
- Command: `python -m chitragupta.review uncited content/drafts/dt-overview/survey.md --write`
- chitragupta 6.61.5

## How to read this

Read under a genre recorded as `survey` in this draft's dossier, where uncited prose is **exceptional**.

In this genre a claim is expected to rest on a source, so every sentence below carries no citation **and no explanation for why not**.

An uncited sentence is **not** a defect. A scope statement, a worked
example and the draft's own transitions all legitimately rest on
nothing. What this report does is stop them being silently mixed in
with cited prose.

**The fix for an uncited claim is evidence, not wording.** Rewording
one would make it look supported without making it supported, so
nothing in this pipeline repairs these findings for you.

A finding whose block cites nothing rests on nothing at all; one
whose block cites something sits beside evidence that may or may not
cover it. The first kind is listed first.

## Summary

**8** of 23 claim-bearing sentences carry no citation, **1** of them in a block that cites nothing.

## Findings

- **line 16** (`49ea2256160e`, block cites nothing)
  > This survey groups the sample corpus into three themes -- keeping the twin true to its asset, using its state stream, and integrating it with everything else -- and closes with the gaps the corpus leaves open.
- **line 5** (`4d7403ef038c`, block cites a source elsewhere)
  > The phrase *digital twin* is applied to systems with very different levels of ambition, and the corpus surveyed here begins by fixing that vocabulary.
- **line 22** (`841d1fb8bc75`, block cites a source elsewhere)
  > A twin is only as trustworthy as its last synchronisation.
- **line 31** (`fe47623570bf`, block cites a source elsewhere)
  > Trust is behavioural as much as technical.
- **line 46** (`14fc9d46f400`, block cites a source elsewhere)
  > Once a twin exists, its state stream is a naturally clean substrate for analytics.
- **line 58** (`562a15a8c78d`, block cites a source elsewhere)
  > Twin pilots rarely die of modelling problems; they die of integration.
- **line 72** (`ecdf4f5e661d`, block cites a source elsewhere)
  > Three gaps stand out.
- **line 72** (`2ba2d479ed94`, block cites a source elsewhere)
  > The corpus measures synchronisation and anomaly detection separately, but no paper studies how detector accuracy degrades under the staleness its own synchronisation strategy permits.
