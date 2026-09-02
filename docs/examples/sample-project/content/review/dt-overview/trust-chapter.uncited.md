# Uncited prose: content/drafts/dt-overview/trust-chapter.tex

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/trust-chapter.tex`
- Command: `python -m chitragupta.review uncited content/drafts/dt-overview/trust-chapter.tex --write`
- chitragupta 6.61.5

## How to read this

Read under a genre recorded as `thesis-chapter` in this draft's dossier, where uncited prose is **exceptional**.

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

**16** of 21 claim-bearing sentences carry no citation, **9** of them in a block that cites nothing.

## Findings

- **line 4** (`1bd9a671d309`, block cites nothing)
  > \label{ch:trust}
- **line 7** (`38b4f646e700`, block cites nothing)
  > \label{sec:trust-rq}
- **line 9** (`7ecf34614eeb`, block cites nothing)
  > This chapter addresses RQ2: \emph{what limits the operational authority a digital twin is granted -- model accuracy, or something else?} The question matters because deployment decisions are usually argued in accuracy terms, while the corpus examined here suggests the binding constraint lies elsewhere.
- **line 16** (`7a8f2a2c0026`, block cites nothing)
  > \label{sec:trust-argument}
- **line 18** (`f988e6a59cc2`, block cites nothing)
  > Three strands of evidence converge on the same answer: the limiting resource is \emph{operator trust}, and trust responds to the twin's honesty about its own state rather than to its accuracy in the mean.
- **line 50** (`a072943f6005`, block cites nothing)
  > \label{sec:trust-synthesis}
- **line 62** (`99544f7d9ead`, block cites nothing)
  > \label{sec:trust-limitations}
- **line 64** (`0f4700a7622a`, block cites nothing)
  > The corpus is small and synthetic, its trust measures are behavioural proxies (mistrust incidents, override rates) rather than instruments, and no study in it manipulates honesty and accuracy independently.
- **line 66** (`dd959254e9f8`, block cites nothing)
  > The claim this chapter defends is therefore directional: where the two have been separated at all, honesty dominated.
- **line 22** (`8c7d8312f926`, block cites a source elsewhere)
  > First, the synchronisation literature separates the two directly.
- **line 26** (`e10b7482cd7e`, block cites a source elsewhere)
  > Accuracy was held constant; honesty moved; trust followed the honesty.
- **line 29** (`b08c41c6c202`, block cites a source elsewhere)
  > Second, the longest observational record in the corpus shows authority following audited agreement rather than claimed accuracy.
- **line 40** (`7884b5a69100`, block cites a source elsewhere)
  > Third, the same asymmetry appears at the analytics layer.
- **line 45** (`99a871315851`, block cites a source elsewhere)
  > The recommended layered configuration buys accuracy where it is cheap but anchors trust to the component whose errors are legible.
- **line 52** (`5782654d3d89`, block cites a source elsewhere)
  > Across all three strands, the mechanism that converts a working twin into a trusted one is the same: make its uncertainty visible at the point of use, and let humans audit the record on their own schedule.
- **line 58** (`2e22445b63a8`, block cites a source elsewhere)
  > Authority, in other words, is granted against the override log, not against the validation report.
