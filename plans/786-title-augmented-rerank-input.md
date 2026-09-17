# Title-augmented reranker input

Status: **measured, and the issue is declined, 2026-09-17.** The bar
below was cleared and the change is still not built -- see *Outcome*,
which records why the bar turned out to be the wrong comparison. Kept as
a plan rather than deleted because the harness arm it specifies is
committed, and a future `rerank = true` would reopen the question.

Written for issue 786 (*"Give the reranker the source title, not just the
bare passage"*). The numbers are in
`bench/RESULTS.md`, section *2026-09-17 (issue 786)*; the short version
is at the foot of this file.

**Written for** whoever decides 786 -- which, per the issue's own
"a null or negative result is a legitimate outcome", may be a decision to
decline. It pre-registers the measurement and the bar *before* the
numbers exist, because that is the only ordering in which a null result
can still be read as one.

**Assumed**: `content/chroma/` built against
`sentence-transformers/all-mpnet-base-v2`; `[enrich].rerank`'s shipped
placement (over-fetch -> rerank -> per-citekey cap -> truncate, #380) is
not reopened here; `bench/RESULTS.md`'s 2026-08-26 section is the
baseline this extends rather than re-derives.

**Not covered here**: the embedding index (untouched -- 786 is
input-side only), `hit["snippet"]`'s value as returned to callers
(unchanged by construction), and the reranker's cost, which
`bench/bench_rerank_cost.py` already measures and which a prefix does
not move.

## The claim, and the two ways it can fail

786 proposes scoring `(query, f"{title}\n\n{snippet}")` instead of
`(query, snippet)`, on the reranker's input side only. The argument for
it is real: DPR and BEIR concatenate a title field onto the passage, and
MS MARCO-trained cross-encoders have seen that shape.

The two failure modes are both stated in the issue, and both are
measurable rather than arguable:

1. **The title dominates.** Every chunk of one paper carries the same
   prefix. Because the rerank runs *before* the per-citekey cap, the
   reranker's job includes choosing which of a paper's own chunks
   survive -- exactly the comparison a shared prefix cannot inform.
2. **The window binds.** `snippet_chars` (500) is the reranker's
   effective window; a prefix spends part of it.

## The arms

Extends `bench/bench_rerank_position.py` -- the issue names it, and a
new `bench/*.py` would move a count a test asserts on. One pool per
query, reused by every arm, so the arms differ only in the text handed
to `CrossEncoder.predict`:

| Arm | Reranker input |
| --- | --- |
| A | `snippet` -- the shipped input (= that section's arm 2) |
| B | `f"{title}\n\n{snippet}"` -- 786 as proposed |
| C | `title` alone, no passage |

Arm C is not a candidate for shipping. It is the diagnostic for failure
mode 1: if B's returned citekeys agree with C's more than with A's, the
passage has stopped carrying the ranking, and the concern is confirmed
by measurement rather than by argument.

A missing or empty `title` makes B and C degenerate to A and to an empty
string respectively; the run counts those hits, and the shipped code (if
it ships) falls back to the bare snippet.

## The leak this benchmark must control for

`build_keyword_ground_truth()` sets query = the paper's own
author-assigned `keywords`. Author keywords and that paper's own title
share vocabulary heavily, so prepending the title hands the
cross-encoder something close to a copy of the query for the *correct*
document and nothing comparable for its distractors. An unstratified win
on these 256 pairs would therefore be an artefact of the ground truth,
not a property of the change.

So the run stratifies: each row's query terms (via `retrieval`'s own
`_tokenize`, not a second tokenizer) are scored for containment in the
correct paper's title, the rows are split at the median, and B - A is
reported **per stratum**. A gain that lives only in the high-overlap half
is the leak, shown rather than suspected. The live-log ground truth (96
real drafting queries) is the confirmation arm where a snapshot with the
chapters' `retrieval.md` is available.

## The within-document diagnostic

No chunk-level relevance labels exist, and none are invented. Two
label-free measures, over each (query, citekey) group with >= 2 chunks in
the pool:

- **Score spread** (max - min) under A and under B. A shared prefix pulls
  a document's chunk scores toward each other; a collapse in spread is
  the discrimination loss, in the units the reranker actually works in.
- **Order unchanged from the bi-encoder's distance order.** Compressed
  scores plus a stable sort means the rerank quietly stops reordering at
  all. A rise here beside a fall in spread is failure mode 1 happening.

## The bar, fixed before the numbers

The headroom is already bounded by the 2026-08-26 section: across three
rerankers, reranking moved recall@5 by -4, 0 and +1 queries out of 256,
never moved `distinct@5` (the cap sets source diversity, not the
ordering), and its one consistent gain was recall@3 (+9, +10, +15). A
title prefix cannot touch the 27% of answers that never enter the pool at
all. So the realistic upside is "does that ~10-query recall@3 effect get
bigger", on a path that is off by default.

**Ship only if** recall@3 or nDCG@5 improves *and* the improvement
survives the low-overlap stratum *and* within-document score spread does
not collapse.

Anything else -- including a gain that lives entirely in the high-overlap
stratum -- is a decline, recorded as a `bench/RESULTS.md` entry beside
the overlap gate, reranking-BM25 and retrieval fusion, and the issue
closes with no change to `chitragupta/`.

## If it ships

One edit in `chitragupta/enrich/_rerank.py`: build the scored pair from
`hit.get("title")` and `hit["snippet"]`, falling back to the bare snippet
when the title is missing or empty, and leave the returned hit dicts
untouched. No config key -- a second on/off for a path that is already
off by default buys nothing. Tests: the existing stub-scorer tests assert
on ordering and keep working; one new test asserts the *pair text* the
stub was handed, which is the whole of the change.

## Outcome

Run before any of `chitragupta/` was touched, on both ground truths and
two rerankers. The pre-registered bar is met: recall@3 0.5508 -> 0.6133
and nDCG@5 0.5118 -> 0.5860 on the 256 keyword queries, the correct paper
lost 1x against gained 21x, and the gain **survives the low-overlap
stratum** (+3 recall@3 and +4 recall@5 queries, nDCG +0.036) where a
title-only reranker collapses from 0.4463 to 0.3306. `BAAI/bge-reranker-base`
agrees in direction, and the 96 real logged drafting queries do too
(recall@3 +5, recall@5 +4, lost 2x / gained 6x).

One qualification on failure mode 1, because the two ground truths
disagree about it. On the keyword queries dropping the passage entirely
costs 24 answers and gains 7, so the passage is still carrying the
ranking. On the live logs a title-only reranker is **indistinguishable**
from title+snippet -- recall@3 identical, recall@5 one query apart, lost
8x against gained 9x -- so on real queries the document-level signal is
most of what the cross-encoder is using. That is not a reason to decline;
it is the reason the change works, and it is also why `distinct@5` pays.

Neither failure mode fires as feared. The within-document score spread
compresses by 39% (5.52 -> 3.36) but the rerank still reorders a paper's
own chunks about as often as before (30.7% -> 31.5% of 822 groups left
alone), against the title-only arm's total collapse to ties (100%). The
input window never binds: 133 -> 146 median tokens against 512, and 0 of
5120 pooled chunks lack a title on this corpus.

Two costs the issue does not mention, and which belong in its close:

- **The unstratified gain is roughly double the real one.** Half of what
  the keyword ground truth reports is the query being a paraphrase of the
  title it is now being shown.
- **`distinct@5` falls 3.684 -> 3.449.** A shared prefix makes the
  reranker agree with itself across one paper's chunks, so more of them
  survive together -- the opposite direction from #310.

And one framing correction. Arm 0 -- no reranker, which is what ships --
beats the reranked arm on the live logs (recall@3 0.6354 against 0.5833).
Title augmentation brings the reranked path back to level rather than
past it. So this is a fix to an opt-in path that currently underperforms
its own default, **not** evidence for turning `[enrich].rerank` on.

## Why it was declined even so

The bar above compares B against **A**, the reranker as it exists. What
decides shipping is B against **arm 0** -- and `[enrich].rerank` is off by
default, so arm 0 is not arm A. Against arm 0, on the ground truth whose
queries no paper's metadata wrote, B is recall@5 **+3 of 96** and nDCG
**+0.002**.

That is a defect in this plan, not in the run. Pre-registering a bar does
not make it the right question; it makes the mismatch visible afterwards
instead of arguable, which is what happened here. The lesson for the next
plan against an opt-in path: **name the shipped default as the baseline
arm**, not the feature's own current form.
