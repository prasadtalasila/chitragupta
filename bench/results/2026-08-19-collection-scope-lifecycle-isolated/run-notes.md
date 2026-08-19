# Run notes: things found while running the isolated arms

Written as they were found, before the arms were both in.

## A version skew between the two checkouts, and what it cost

`/workspace` (the main working tree) sits at **b4b5cb0e**. This worktree
sits at **12e6f367**, which is *newer* and carries #247 -- "Make a
Markdown draft's ASCII figure a file, matching thesis-chapter-writer's
pair". The two checkouts therefore implement **different figure
contracts**, and `src/render_output/_figures.py` differs between them.

Measured on a throwaway draft under each checkout, marker-only being the
form `textbook-chapter-writer` SKILL.md step 7 and
`docs/WRITING-STANDARDS.md` §10 both document:

| Draft form | b4b5cb0e (`/workspace`) | 12e6f367 (this worktree, #247) |
|---|---|---|
| Marker only, `.tex` + `.txt` siblings -- **the documented form** | tex `\input` = 0, md ASCII = 0 -- **figure silently dropped from every format**, exit 0, no warning | tex `\input` = 1, md ASCII = 1 -- correct |
| Marker + inline fence -- the pre-#247 form | tex `\input` = 1, md ASCII = 1 -- correct | tex `\input` = 1, md ASCII = **2** -- the fence is kept *and* the `.txt` injected |

Two consequences worth carrying forward.

**1. The earlier, inline benchmark run's figures never rendered.** That
run (2026-08-18) wrote marker-only drafts and rendered them with
`cd /workspace`, i.e. under b4b5cb0e. Both chapters' PDFs were therefore
produced without their figures, silently. The same is true of the
`digital-twin-platforms` drafts from the run before it, which carry
markers and a `.tex` but no `.txt` at all.

**2. #247 does not warn about the form it replaced.** A draft written to
the pre-#247 contract renders under #247 with the ASCII appearing twice
in the `.md` -- once from the retained fence, once injected from the
`.txt` -- with no warning. Every draft already in `content/drafts/` was
written to that older contract, so this is a live migration hazard rather
than a hypothetical one. Not filed as an issue yet.

## Which checkout each arm ran under

Not controlled for, and it should have been. The subagents inherit this
worktree as their cwd, but the task prompt gave absolute
`/workspace/content/...` paths, so an agent that `cd`s to `/workspace`
executes b4b5cb0e's code instead of this worktree's.

Arm C demonstrably ran under **b4b5cb0e**: its report describes the
marker-only render producing "a `.tex` with zero `\input{figures/...}`
and an `.md` with no diagram", which is exactly b4b5cb0e's behaviour and
not this worktree's. It then worked around it by inlining the fences, so
its draft is written to the *pre-#247* contract while also carrying
`.txt` files -- the combination that double-renders under #247.

This affects only the pipeline-mechanics steps (render, and the figure
contract). It does **not** affect retrieval, the ledger, the index,
selection ratios or the verbatim scan, all of which read the same
`content/` and the same ledger regardless of which checkout's code ran.
The retrieval-facing measurements are therefore unaffected; the
render-facing observations are not comparable between arms unless both
arms turn out to have used the same checkout.

## Arm C incidental findings, from its own report

- **`retrieve evidence` takes no `--collection`.** The flag exists on
  `retrieve search` only, so "scope every retrieval call" is
  unsatisfiable for the `evidence` subcommand. The agent abandoned
  `evidence` and read `content/parsed/*.txt` directly instead -- which is
  a read, not a logged retrieval call, so that depth-reading is invisible
  in `retrieval.md`. Relevant to #254.
- **One retrieval call was lost to a relative `--log` path.** The tool
  answered `[not logged] ... is not under /workspace/content/drafts` and
  the agent re-ran it with an absolute path. So 10 searches happened and
  9 are on the record. `--log` failing open (the search still returns
  results, only the logging is skipped) is what makes this easy to miss.
- **Three orphan figure pairs** were authored and never referenced:
  `compatibility-triple`, `retention-tiers`, `two-clocks`. Six pairs on
  disk, three markers in the draft.
- **`noauthor_digital_2023` is a weak source.** Author-less `@misc`; the
  corpus owner's own `annote` reads "potentially low quality non-peer
  reviewed. Find better references." Both arms of the earlier run leaned
  on it for the 188-paper phase distribution, as does this one. Real,
  gate-verified, and worth replacing.
