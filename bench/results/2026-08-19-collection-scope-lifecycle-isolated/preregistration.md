# Pre-registration: `--collection`, measured with isolated arms

Written **2026-08-19, before either arm ran**, after the previous day's
run of this design was found to be confounded.

## Why this run exists

`bench/results/2026-08-18-collection-scope-lifecycle/` ran both arms
**inline in one agent session**. That session's context is append-only,
so the second arm inherited the first arm's entire draft. The measured
consequence was severe and is recorded in that run's own results:
draft-vs-draft Jaccard **0.483**, with a **487-word** contiguous shared
run. The two "independent" chapters were not independent documents.

That confound damages two of the six measurements:

- **Tokens.** One shared context pool. The second arm re-sent the first
  arm's tokens on every turn, so its input figure is mostly cache reads
  of the other arm and its output figure is depressed by having the
  first chapter's prose available to adapt.
- **Draft-vs-draft overlap.** Uninterpretable -- it measured the session,
  not the retrieval scope.

The other four (retrieval payload, index cost, surfaced/selected/
rejected, per-arm corpus overlap) are unaffected, because they are read
from disk artefacts and a deterministic replay rather than from the
session. They are expected to reproduce, and reproduction is itself a
result.

## The fix

Each arm is written by a **separate subagent with an empty context
window**. Each is given the task specification and its own retrieval
scope, and nothing else: no scope statement, no section skeleton, no
query list, no prose, and no knowledge that the other arm exists.

The two agents are dispatched **in parallel**, which removes the second
confound the previous run had to live with. That run had to order the
arms deliberately (control first) so the ordering bias worked against
the hypothesis. With independent context pools there is no ordering bias
to compensate for, so **neither arm's figure is a bound -- both are
direct measurements.**

## The two arms

| | Arm F | Arm C |
|---|---|---|
| Retrieval | whole corpus, 642 items | `--collection "Lifecycle"`, 19 items |
| Context | empty | empty |
| Dispatch | parallel | parallel |
| Draft | `…-full-corpus.md` | `…-life-cycle-considerations.md` |

## Held fixed

The two prompts are **byte-identical except for one paragraph**: the
retrieval-scope instruction. Same title, same ten-thousand-word target,
same reader, same dialect, same instruction to complete the whole
pipeline, same host setup, same requested final report.

## Deliberately NOT held fixed -- and why this is the right call

The previous run pre-registered a shared **section skeleton** and a
shared **ten-query list**, so that the arms differed in exactly one
variable. This run cannot do that, because handing both agents a
skeleton and a query list *is* context, and context is the thing being
eliminated.

So each arm formulates its own queries and derives its own structure.
That is a deliberate trade, and it changes what the benchmark measures:

- **Previous run:** what the filter does to retrieval, holding the
  drafting plan constant. Cleanly attributable, but written by a
  polluted process.
- **This run:** what the filter does to a *real drafting run*, plan
  included. The arms differ in more than one variable -- queries and
  structure will diverge -- but the process is honest, and it is what a
  user actually experiences.

Query counts and texts will therefore differ between arms and are
reported per arm rather than assumed equal. **The retrieval payload
comparison is consequently no longer apples-to-apples** and must be
read per query, not as a total.

## What gets measured

| Metric | Source | Changed from the previous run? |
|---|---|---|
| Tokens per arm | each subagent's own transcript JSONL -- one pool per agent, no sharing | **Yes -- this is now a real measurement rather than a confounded one** |
| Words per arm | `wc -w` on each draft body, References excluded | no |
| Retrieval payload and query count | each dossier's `retrieval.md` | now per-query, since counts may differ |
| Index cost | md5 of index + ledger at three checkpoints | no |
| Surfaced / selected / rejected | replay of each arm's own logged queries at its own `--k` | no |
| Common papers | intersection of cited and of surfaced sets | no |
| Per-arm corpus overlap | `src.review verbatim scan --json` | no |
| **Draft-vs-draft overlap** | shared word runs | **Yes -- now a real test.** With independent contexts this should fall sharply from 0.483. If it does not, the pollution was not the cause and the previous run's interpretation was wrong |

## Predictions, recorded before the arms finished

Stated so they can be scored rather than rationalised afterwards:

1. **Draft-vs-draft Jaccard falls well below 0.483**, and the longest
   shared run falls far below 487 words. This is the point of the
   redesign; if it fails, the redesign failed.
2. **Retrieval payload stays near-parity per query** (~7,400 chars at
   `--k 15 --chars 500`), because the filter does not change how many
   results a call returns.
3. **Index cost stays zero** -- three identical hashes.
4. **Arm C's selection ratio stays far above Arm F's**, though the exact
   figures will move because the queries are no longer shared.
5. **Arm C surfaces papers Arm F does not.** The previous run found 8;
   if the effect is real rather than an artefact of one query list, it
   should survive different queries.

## Known limitations, stated in advance

1. **One variable is no longer isolated.** See above. This measures the
   feature in use, not the feature in a vacuum.
2. **The shelf is small.** 19 items; `--k 15` nearly exhausts it in two
   calls. Surfaced counts remain comparable only as ratios.
3. **Two agents, one run each.** No repetition, so nothing here
   separates the arm effect from run-to-run variance in agent behaviour.
   A third arm re-running the same scope would be needed for that, and
   was not run.
4. **Citations are optional in this genre**, so selection ratios rest on
   small denominators.
5. **The agents differ in more than their prompt paragraph** only by
   chance -- same model, same tools, same skill, dispatched together.
