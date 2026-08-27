# 💡 Inspiration: what this project borrowed, and from where

Status: **reference.** Written 2026-08-13. Updated 2026-08-24.

Every external idea this project took, what was taken, and -- where it
matters -- what was deliberately *not* taken. Credit is the first purpose;
the second is that knowing which upstream a design came from is the fastest
way to understand why it has the shape it does.

**Written for** anyone wanting the provenance of a design decision, and
anyone checking this project's licence hygiene.

**Not covered here:** the citation provenance of a *draft*, which is a
different question entirely and belongs to the review layer
([CITATION-PROVENANCE.md](CITATION-PROVENANCE.md)). This file is about
where the *pipeline's own* ideas came from, not where a draft's claims
came from.

## 🧭 Table of contents

- [The drafting layer's method](#-the-drafting-layers-method)
- [Code standards](#-code-standards)
- [Harness engineering](#-harness-engineering)
- [The feature roadmap](#-the-feature-roadmap)
- [The rule on borrowing](#-the-rule-on-borrowing)

## ✍ The drafting layer's method

- **[hadufer/claude-storm](https://github.com/hadufer/claude-storm)** (MIT
  License) -- the `.claude/skills/deep-research/` skill and its
  `deep-research-interviewer`/`deep-research-writer` subagents adapt its
  7-phase pipeline (perspective discovery, parallel grounded interviews,
  contradiction mapping, outline, cited writing, synthesis, self peer-review).
  Retooled here for a closed, citekey-grounded local corpus instead of live
  web sources -- see `reference.md` in that skill's directory for exactly
  what changed and why.
- **[stanford-oval/storm](https://github.com/stanford-oval/storm)** -- the
  original STORM method claude-storm implements: "Assisting in Writing
  Wikipedia-like Articles From Scratch with Large Language Models" (Shao,
  Jiang, Kanell, Xu, Khattab, Lam; NAACL 2024; arXiv:2402.14207).
- Nav Toor's (@heynavtoor) 4-prompt adaptation, fused into claude-storm's
  pipeline and carried through into `deep-research`'s synthesis-briefing
  and single-reviewer (`quick` depth) peer-review phases.
- **[Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills)**
  -- the *idea* behind `deep-research`'s `standard`/`deep`-depth peer review
  (an independent multi-reviewer panel including a dedicated adversarial
  reviewer, reconciled against a concession threshold) is credited to that
  project's Stage-3 peer-review design. That project is licensed CC-BY-NC
  4.0; **no text from it was copied** -- `.claude/agents/peer-reviewer.md`
  and `.claude/skills/deep-research/reference.md` §7 are written from
  scratch, adapting only the concept of an independent panel plus a
  Devil's Advocate role, not its implementation.

## 🤝 Code standards

- **[wojteklu/clean_code.md](https://gist.github.com/wojteklu/73c6914cc446146b8b533c0988cf8d29)**
  -- the widely-circulated summary of Robert C. Martin's *Clean Code:
  A Handbook of Agile Software Craftsmanship* (Prentice Hall, 2008). This
  is the source standard behind [CODE-STANDARDS.md](CODE-STANDARDS.md):
  its section structure (general rules, design, names, functions,
  comments, source structure, tests, code smells) is the checklist that
  document is written against, and the rule-by-rule table there records
  which rules are enforced, which are left to review, and which do not
  apply to a stdlib-heavy, classless Python codebase.

  Two of its rules are load-bearing here in a way worth naming:

  - Its comment rules -- *explain intent*, *clarify*, *warn of
    consequences* -- are the canonical support for this repository's
    house style of dense rationale comments. The rule the canon actually
    states is "don't be **redundant**", not "don't comment", and the
    difference is the whole of
    [CODE-STANDARDS.md's comment section](CODE-STANDARDS.md#-the-comment-rules-and-the-misreading-to-avoid).
  - Its **code smells** vocabulary -- rigidity, fragility, immobility,
    needless complexity, needless repetition, opacity -- is adopted
    directly as the review vocabulary, because naming a smell is what
    turns "this feels wrong" into a reviewable claim.

## 🪝 Harness engineering

- **[walkinglabs/awesome-harness-engineering](https://github.com/walkinglabs/awesome-harness-engineering)**
  -- a curated list for *harness engineering*: "the practice of shaping
  the environment around AI agents so they can work reliably." That is a
  fair description of what most of this repository actually is. The
  categories it tracks map onto parts of this project closely enough to be
  worth stating, both as credit and as a reading list for whichever part
  you are about to change:

  | Its category | Where this project does that |
  | --- | --- |
  | Specs, agent files & workflow design | [CLAUDE.md](../CLAUDE.md), [AGENTS.md](../AGENTS.md), `DEVELOPER-AGENTS.md` (git checkout only), `.claude/skills/` |
  | Constraints, guardrails & safe autonomy | The citation gate and its PostToolUse hook; the review layer's rule that it never blocks ([SOUL.md](../SOUL.md)) |
  | Context, memory & working state | The dossier ([DRAFT-ITERATION.md](DRAFT-ITERATION.md)), and [TOKENS.md](TOKENS.md) for what context costs |
  | Evals & observability | The review layer's seven aids, and [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s unbuilt `agenda` |
  | Foundations | [SOUL.md](../SOUL.md) and [DESIGN.md](DESIGN.md) |

  The gap that list makes most obvious is **evals**: this project has
  review aids and a gate, and no benchmark suite measuring whether the
  drafting layer is getting better. [PERFORMANCE.md](PERFORMANCE.md)
  measures the deterministic half only, and #63's parked evaluation
  harness is the open thread.

- **Four public hook collections**, read together when working out what a
  second `PostToolUse` hook should look like (#185) and why the existing
  launcher is not portable (#197). What each contributed, and what was
  refused, is set out in [HOOKS.md](HOOKS.md); in brief:

  | Upstream | Taken | Not taken |
  | --- | --- | --- |
  | [obra/superpowers](https://github.com/obra/superpowers) | The fail-silent contract for a context injection, and the caution that the advisory-context field name differs per host | The polyglot `run-hook.cmd`, which needs shell form and so cannot coexist with exec form |
  | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | The standard-envelope rule, and testing that a hook's payload parses | Its `jq` dependency, against the stdlib-only posture |
  | [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | The survey of hook events, output fields and version-gated options behind this project's `if` and `async` notes | Its per-hook enable/disable config -- the gate must not be individually disableable |
  | [affaan-m/ECC](https://github.com/affaan-m/ECC) | The principle that paths are resolved in the interpreter, not in the shell | The dispatcher process, which trades away fault isolation |

  The refusals matter as much as the borrowings. Three of the four are
  fail-silent by design, which is right for what they protect and would be
  a silently inert citation gate if copied across.

### 🪝 Hook architecture as a first-class layer

- **[jcode](https://jcode.sh/docs)** -- hooks as shell commands fired at
  turn, session and tool boundaries, alongside skills and memory, rather
  than as an add-on. Read against this repository's own hook layer in
  2026-08, which is what surfaced the asymmetry issue 431 fixes: every
  registry row was keyed on a write under `content/drafts/`, and nothing
  hooked a change to `chitragupta/`. Nothing of jcode's own architecture
  is adopted -- its daemon/client split, its semantic skill matching and
  its lane-aware queue all answer questions this project does not have.
- **OpenClaw** -- the same observation from the other direction: hooks on
  gateway events, and a four-tier memory stack. Its **heartbeat**, a
  periodic agent turn driven by a checklist, was considered as the
  "driver" the developer loop was said to lack and **rejected on this
  project's own terms**:
  [R3](AUTO-IMPROVEMENT.md#-the-requirements) rules out a mechanism
  aimed at minimising a count, and a timed turn whose job is to find debt
  to pay is a ranked worklist with a clock on it. Recorded in
  `plans/f-auto-improvement-adoption.md`, which retires that loop.

Both were read as secondary sources -- jcode's published documentation,
and third-party write-ups of OpenClaw rather than its own docs -- so what
is credited here is the *idea* each made visible, not a claim about
either implementation's detail.

## 🗺 The feature roadmap

Two upstreams behind [FEATURE-ROADMAP.md](FEATURE-ROADMAP.md). Both are
Apache-2.0, and **copying from both was offered and declined** -- the
cost of declining was measured at roughly one PR, and that document's
"borrowing posture" section has the working. Nothing is copied from
either; where the roadmap quotes them it quotes them as evidence for a
design claim, and every implementation is written here from scratch.
Which makes this the ordinary case for this file, not an exception to
it.

- **[AkariAsai/OpenScholar](https://github.com/AkariAsai/OpenScholar)**
  (Apache-2.0) -- "OpenScholar: Synthesizing Scientific Literature with
  Retrieval-Augmented Language Models" (Asai, He, Shao, Shi, Singh,
  Chang, Lo, Soldaini, et al.; arXiv:2411.14199). Four ideas behind the
  roadmap's synthesis half:
  - **Cap passages per source, then truncate** -- the ordering is what
    produces source diversity, because dropping one paper's fourth-best
    passage promotes another paper's into the window the drafter sees.
  - **Instruct synthesis across sources explicitly**, rather than a
    paper-by-paper summary, so a paragraph fuses several sources.
  - **A feedback pass before the final artefact**, and the observation
    that its safety guard has to be something other than a length ratio.
  - **Post-hoc citation attribution as a repair pass** -- taken chiefly
    as a *negative* result: it is a prompt, not a verifier, which is why
    the roadmap plans a real entailment check as new work rather than a
    port.

  *Not taken:* its positional `[n]` citation numbering, which reorders
  meaning whenever the passage list changes and is the opposite of a
  citekey; its dead code paths; and its import graph, which pulls a GPU
  stack unconditionally.

- **[dwzhu-pku/PaperBanana](https://github.com/dwzhu-pku/PaperBanana)**
  (Apache-2.0), and the Google Research project it forks,
  [PaperVizAgent](https://github.com/google-research/papervizagent) --
  a multi-agent framework for academic illustration. Three ideas behind
  the roadmap's figure half:
  - **Commit to a layout metaphor before drawing** -- pipeline, layered
    stack, control loop, branching tree, hub-and-spoke -- which is the
    idea most likely to fix figure sprawl at its source.
  - **A defect catalogue is more useful than a style guide** for layout.
    Its evaluation rubric, not its style guide, is where the concrete
    layout defects are, and one of them is written for LaTeX
    specifically.
  - **A critique loop's shape**: bounded rounds, a structured payload,
    an explicit "nothing to change" exit, and keeping the last good
    render.

  *Not taken:* image generation itself, and this is the substantive
  refusal. Its own published comparison shows the image route inverting
  a relationship between two series, duplicating a category, and drawing
  a bar taller than its own gridline where the code route was correct
  every time. A generator that draws a bar taller than its value is
  fabricating data, which is the failure this project exists to prevent.
  Its style guide's content is also raster-oriented and does not survive
  translation to TikZ.

## 🔑 The rule on borrowing

Stated once, because it is the same rule the pipeline applies to drafts:

**Attribute the idea, and never copy the text.** Where an upstream is
permissively licensed the adaptation is still written from scratch, and
where it is not (`academic-research-skills`, CC-BY-NC 4.0) only the
concept is taken and the entry above says so explicitly. The rule held
when it was tested: copying from two permissively-licensed upstreams was
offered for the feature roadmap and declined, at a measured cost of
about one PR. That is
[SOUL.md](../SOUL.md)'s refusal to manufacture support, pointed at this
project's own provenance rather than a draft's.
