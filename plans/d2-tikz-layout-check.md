# D2: deterministic TikZ layout check

Status: **plan, unbuilt.** Written 2026-08-20. Implements
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s D2.

**Written for** whoever builds it. **Assumed:**
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10 for the
two-form figure contract, and the roadmap's Theme D for why this is
deterministic rather than a vision model. **Not covered here:** the
style guidance a figure is written against, which is D1's.

## The mechanism, already probed

A `standalone` + `tikz` document that emits node corner coordinates via
`\pgfpointanchor` and `\typeout` yields machine-readable geometry from
an ordinary `pdflatex` run. Verified on this host (`tikz.sty` and
`standalone.cls` both present):

```text
CGBOX a -42.87912pt -7.97742pt 42.87912pt 7.97742pt
CGBOX b -8.73592pt -6.94963pt 77.02232pt 6.94963pt
CGBOX c -20.78996pt -63.85512pt 20.78996pt -49.95586pt
```

`a` and `b` overlap by 51.6pt in x and overlap in y -- a real collision,
detected with no model in the loop.

**Reproduce the probe before writing code.** It is the one assumption
everything else rests on, and it is cheap to re-run.

## What it checks

| Check | Kind | From |
|---|---|---|
| Node overlap | **binary** | pairwise box intersection |
| Node text overload | **binary** | word count per node, ~15 words |
| Content protrusion | **binary** | picture bbox against union of node boxes |
| Edge list | **binary** | `\draw`/`\path` node-to-node pairs, reported for confirmation |
| Corner emptiness | **continuous** | proportion of the bbox left empty |

The binary/continuous split is not cosmetic. The roadmap's R3
constraint forbids a continuous score from being the thing optimised by
anything unattended, so **corner emptiness is reported to a human and
consumed by nothing**, and the report must label it as such. An
unlabelled mixture is how a score ends up being optimised by something
that should not be optimising anything.

Deliberately **not** checked: arrow crossings ("chaotic routing"). Not
cheaply reachable from node geometry, and a bad approximation of it
would be worse than its absence.

## The edge list is the point

Every published PaperBanana diagram failure is a wrong or missing edge
-- semantics, not layout -- and every one is invisible to a check over
pixels. In TikZ an edge is `\draw (a) -- (b);`, so the edge list is
recoverable from source. Report it plainly (*a -> b, b -> c*) for the
author to confirm against the prose the figure illustrates. This is the
cheapest possible implementation of a faithfulness check, needs no
model, and exists only because this pipeline generates source.

## Decisions this plan settles

**Where it lives.** A review-layer aid: advisory, exits 0 whatever it
finds, takes no lock. That means it carries the roadmap's R10 -- keys in
**both** `review.AIDS` and `__main__.AIDS`, plus AGENTS.md, CLI.md, the
README tables and `mkdocs.yml`. `review/__main__.py` raises at import if
the two dicts disagree; the `mkdocs.yml` omission is the silent one.

**What to call it.** Not `audit`, `verdict`, `reckoning` or `ruling` --
the judgement register belongs to the gate. Not `triage`, which
[docs/REJECTION.md](../docs/REJECTION.md) records as built and
withdrawn. `figure` is accurate and free.

**Compiling is a side effect, and must not litter.** Build in a
temporary directory and never beside the draft. A figure that fails to
compile is a **reported finding, not a crash** -- `_require_tikz()`
already models the missing-`tikz.sty` case, and this reuses it rather
than re-probing.

**No timestamp in the report**, per the layer's existing rule: two runs
over an unchanged figure produce byte-identical output.

## Files

| File | Change |
|---|---|
| `chitragupta/review/figure_layout.py` | new: probe emitter, log parser, the five checks |
| `chitragupta/review/__init__.py` | register in `AIDS` |
| `chitragupta/review/__main__.py` | register in `AIDS`, wire the subcommand |
| `chitragupta/render_output/_figures.py` | reuse `_require_tikz()`; no behaviour change |
| `docs/CLI.md`, `AGENTS.md`, `README.md`, `mkdocs.yml` | R10's sweep |
| `docs/WRITING-STANDARDS.md` | §10 gains a pointer, not a restatement |

## Tests

Failing first:

1. Two overlapping nodes are reported; two spaced nodes are not.
2. The probe's own output parses -- pin the `CGBOX` format against a
   real `pdflatex` run, not a fixture, since the format is the
   assumption.
3. A node of 30 words is reported; one of 5 is not.
4. The edge list of a three-node chain is exactly `a -> b, b -> c`.
5. A figure that fails to compile produces a finding and **exit 0**.
6. Byte-identical output over two runs.
7. `AIDS` disagreement raises -- likely already covered; assert it
   covers the new key.

## Done when

The probe in the roadmap is reproduced by the test suite rather than by
hand, and running the aid over the repository's own drafts reports
something a human agrees is worth fixing. If it reports nothing on real
figures, say so in the PR -- that is a result, and it would mean the
layout complaint lives somewhere this check cannot see.
