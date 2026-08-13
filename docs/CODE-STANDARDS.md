# Code standards: what is binary, what is judgement, and the ratchet

Status: **standard, partly enforced.** Written 2026-08-13. The two
size rules below are enforced by `tests/test_code_standards_scan.py`;
everything under [Judgement, not a gate](#judgement-not-a-gate) is a
review standard with no detector, and
[Build order](#build-order) says which detectors would come next.

This is the code counterpart of
[WRITING-STANDARDS.md](WRITING-STANDARDS.md): that one is the standard the
genre skills write prose against, this one is the standard an agent
changes *this repository's own code* against.

**Written for** someone changing code in `src/` or `scripts/`, or
deciding whether a proposed rule is worth enforcing. It assumes
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the process around a
change -- test policy, the local check suite, commit/PR/release
conventions -- and states only what the code itself must look like.

**Not covered here:** prose standards for drafts
([WRITING-STANDARDS.md](WRITING-STANDARDS.md)), module boundaries and
which layer owns what ([ARCHITECTURE.md](ARCHITECTURE.md), and
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md)'s "Module boundaries"),
and the drafting loop this document borrows its shape from
([AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)).

## Table of contents

- [Where these rules come from](#where-these-rules-come-from)
- [The rule that decides everything](#the-rule-that-decides-everything)
- [Two overrides on the source material](#two-overrides-on-the-source-material)
- [Why statements, not lines](#why-statements-not-lines)
- [The binary rules](#the-binary-rules)
- [The debt register and the ratchet](#the-debt-register-and-the-ratchet)
- [Judgement, not a gate](#judgement-not-a-gate)
- [Behaviour before code](#behaviour-before-code)
- [Build order](#build-order)
- [What this does not change](#what-this-does-not-change)

## Where these rules come from

Two documents from the
[DTaaS](https://github.com/INTO-CPS-Association/DTaaS) project, adopted
here rather than invented:

| Source | What it contributes |
|---|---|
| DTaaS `AGENTS.md` | The code-shape rules: function and file size limits, DRY, SOLID, consistent naming, error handling, no unnecessary dependencies |
| DTaaS `CLAUDE.md` | The behavioural rules: think before coding, simplicity first, surgical changes, goal-driven execution |

Adopted with two explicit overrides, below. Everything else is taken as
written -- and where a rule already existed here under another name, this
document says so rather than restating it, because a rule stated twice is
a rule that will eventually be stated two different ways.

| DTaaS rule | Where it lives here |
|---|---|
| Functions below 25 lines | [The binary rules](#the-binary-rules), re-expressed as **statements** -- see [why](#why-statements-not-lines) |
| Files below 250 lines | [The binary rules](#the-binary-rules), re-expressed as **code lines** -- same reason |
| DRY | [Judgement, not a gate](#judgement-not-a-gate) |
| SOLID | [Override 2](#override-2-solid-is-named-per-principle-not-invoked-wholesale) |
| Comments only where non-obvious | [Override 1](#override-1-why-comments-are-required-what-comments-are-banned) -- **reversed in part** |
| Error handling in a controlled manner | Already here: DEVELOPER-AGENTS.md's "Classify a failure by cause on the exception" and "Report a partial result as a failure" |
| Security implications considered | Already here: `bib_reader.citekey_problem()`'s refusal to sanitise a path-bearing citekey is the live instance |
| No unnecessary dependencies | Already here: `pyproject.toml`'s one core dependency and its optional groups |
| Clear commit messages | Already here: DEVELOPER-AGENTS.md's "Commit messages" |
| Respect existing patterns | Already here: DEVELOPER-AGENTS.md's "Conventions a new stage has to follow" |
| Approval before breaking changes | Already here: DEVELOPER-AGENTS.md's MAJOR bump definition |
| Tests accompany changes | Already here: DEVELOPER-AGENTS.md's "Development process: agile, test-driven" |

## The rule that decides everything

> **R3:** "An unattended item's check is **binary**. No continuous score
> is ever the thing being optimised."
>
> -- [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#the-requirements), which
> owns the wording

That rule was written for drafts. It applies here unchanged, and it is
why this document is split the way it is. "No function exceeds 25
statements" is binary and is enforced. "This code is clean" is a score,
and a score invites the same Goodhart failure
[HOUSE-STYLE.md](HOUSE-STYLE.md#why-a-readability-index-is-a-trap)
describes for readability indices: a maintainability metric is minimised
by splitting functions past the point where the logic survives the break,
and every one of those edits passes its own re-check.

So: a small number of binary rules with a detector and a register, and a
larger number of judgement rules with neither. The judgement rules are
not weaker -- they are what review is for. They are simply not things a
machine may drive to zero.

**The loop stays open.** This document borrows AUTO-IMPROVEMENT.md's
shape, not its automation. Nothing here proposes a code-fixing loop;
[R11](AUTO-IMPROVEMENT.md#the-requirements) -- "its only trigger is a
person asking" -- is the reason, and it applies with more force to code
than to prose.

## Two overrides on the source material

### Override 1: *why*-comments are required, *what*-comments are banned

DTaaS `AGENTS.md` says "Add comments only where logic is non-obvious."
Adopted **only for the second half of that sentence**, and reversed for
the first.

This repository's comments are not explanations of mechanism. They are
the recorded reasoning behind a decision -- which alternative was tried,
what broke, why the obvious thing is wrong. `.github/workflows/ci.yml`
is roughly half prose by line count, and every paragraph of it answers a
question a future reader would otherwise re-litigate. That is not
verbosity to be trimmed; it is the executable form of
[SOUL.md](../SOUL.md)'s

> **Judgment is logged, not just made.**

An agent that reads "comment only where non-obvious", applies it to
`ci.yml` or `pdf_text.py`, and strips the rationale has destroyed the
most valuable thing in those files. So, stated as two rules:

- **Banned: the *what*-comment.** A comment that restates the line below
  it (`# increment the counter`) is noise, and the DTaaS rule is right
  about it.
- **Required: the *why*-comment**, wherever a reader could reasonably
  ask "why this way?" -- a non-obvious constraint, a rejected
  alternative, a bug that produced the current shape, a version pin that
  is load-bearing. Absence of one on a surprising decision is a review
  finding.

The tie-break, when the two seem to conflict, is SOUL.md.

**This override is why the size rules count statements.** A physical-line
limit taxes exactly the thing this section requires -- see below.

### Override 2: SOLID is named per principle, not invoked wholesale

DTaaS `AGENTS.md` says to "apply object-oriented design principles where
relevant." The qualifier is doing all the work, and this codebase is the
case that needs it spelled out: `src/` is stdlib-heavy, module-scoped and
almost entirely classless. Invoking SOLID as a slogan here would produce
classes that exist to satisfy an acronym.

Named individually instead:

| Principle | Status here |
|---|---|
| **S**ingle responsibility | **Adopted**, at module scope rather than class scope. This is DEVELOPER-AGENTS.md's "Module boundaries" section -- `references.py` formats an entry and must not parse the bib file; `bib_reader.py` is the sole reader of it. The file-size rule below is the mechanical proxy |
| **O**pen/closed | **Adopted in a specific form**: a new enrichment stage is added by registering it, not by editing the dispatcher's branches. `review.AIDS` + `__main__.AIDS` is the live instance |
| **L**iskov substitution | **Largely N/A** -- no inheritance hierarchy to violate |
| **I**nterface segregation | **Largely N/A** as stated; the nearest live rule is that `src/retrieval.py` and `src/enrich/embed_index.py` deliberately share one `search(query, k)` shape so either can be swapped in |
| **D**ependency inversion | **Adopted as the probe pattern**: a stage depends on "is pandoc on PATH?", answered at run time, never on a `--target` flag naming its environment. DEVELOPER-AGENTS.md's "Probe for a toolchain; never assume one" is this principle in this repo's own words |

Two of five are N/A, and saying so is the point. A standard that claims
all five apply teaches an agent to invent a justification rather than
notice the mismatch.

## Why statements, not lines

The DTaaS limits are physical-line counts. Applied literally to this
repository they measure the wrong thing, and the measurement says so:

| Scope | Functions over 25 **physical lines** | Functions over 25 **statements** |
|---|---|---|
| `src/` (365 functions) | 122 | 26 |
| `tests/` (1820 functions) | 61 | 1 |

The gap is [Override 1](#override-1-why-comments-are-required-what-comments-are-banned).
A function carrying twelve lines of rationale about why a partial Docling
parse must raise before anything is written is not a long function; it is
a short function with its reasoning attached. Counting physical lines
puts those two rules in direct conflict and rewards deleting the
rationale, which is the one edit this project least wants.

Counting **statements** measures what the rule is actually about -- how
much a function *does* -- and is blind to how well it is explained. On
that measure the codebase is in good shape: 26 offenders in `src/`, not
122, and the tests hold the bar almost perfectly at 1 in 1820.

The same correction applies to files: `src/config.py` is 509 physical
lines and 288 lines of code, the difference being 221 lines of
per-setting rationale. The file rule counts code lines -- non-blank,
non-comment -- for the same reason.

**This is a re-expression, not a relaxation.** One outlier gets stricter
under it, not looser: `src/sync.py::run` is 322 physical lines but **117
statements**, 4.7× the next worst function in the repository. Physical
lines rank it 2.4× the next worst and understate how far out it is.

## The binary rules

Two rules. Both are enforced by `tests/test_code_standards_scan.py`,
which rides the existing `pytest --cov` run rather than adding a second
quality gate to keep in sync -- the same idiom as
`tests/test_command_depth_scan.py`, `tests/test_cli_help_is_short.py` and
`tests/test_removed_command_scan.py`.

| | Rule | Scope | Counted as |
|---|---|---|---|
| **C1** | A function body holds at most **25 statements** | `src/`, `scripts/`, `tests/` | `ast` statement nodes in the body, excluding nested definitions' own bodies |
| **C2** | A module holds at most **250 lines of code** | `src/`, `scripts/` | Physical lines that are neither blank nor a whole-line comment |

**Why the scopes differ.** C1 covers the tests because the tests already
hold it -- 1 offender in 1820 -- so including them locks in a bar that is
met rather than declaring one that is not. C2 does not cover the tests
because a test module here is one-per-source-module by convention, and
its length tracks the surface of the module under test rather than a count
of responsibilities; `tests/test_pdf_text.py` at 1806 code lines is
thorough, not overloaded. Capping it would push tests into new files for
no reason other than the cap.

**`bench/` is out of scope for both.** It is the parser measurement
harness, it is one of the four trees `scripts/release.py` deliberately
excludes from the release archive, and its scripts are one-shot analysis
code whose `main()` reads top to bottom on purpose. Stating that plainly
is better than the alternative reading, which is that its 8 long
functions were quietly not counted.

## The debt register and the ratchet

C1 and C2 are violated by code that exists today. A rule that fails on
the day it lands is a rule that gets skipped, so both are enforced as a
**ratchet** rather than a wall:

- Today's offenders are frozen in `LEGACY_LONG_FUNCTIONS` and
  `LEGACY_LONG_FILES` in `tests/test_code_standards_scan.py` -- 27
  functions and 12 modules.
- **New offenders fail.** Anything not in the register that crosses
  either threshold fails the suite, with the count and the limit in the
  message.
- **Fixed offenders must be delisted.** When a registered function or
  module comes back under its threshold, the test fails and says to
  delete its entry. That is what makes this a ratchet and not a
  permanent amnesty: the register can only shrink, and every shrink is a
  visible diff.

The register is a debt list, not an allowance. `src/sync.py::run` at 117
statements and `src/dossier.py` at 1605 code lines are the two entries
worth taking first, and neither is taken in the change that introduces
this document -- refactoring them is a code change, this is a standard,
and DEVELOPER-AGENTS.md's "several small, reviewable PRs over one large
one" applies to the project's own housekeeping.

What the ratchet deliberately does **not** do: it does not cap the growth
of a module already on the list. A registered file may get longer without
failing. Capping each at today's exact size would fail on every ordinary
edit and would be turned off within a week; the growth of a registered
file is caught by C1 on its functions and by review.

## Judgement, not a gate

These have no detector and will not get one. They are what a reviewer --
human or Copilot, per DEVELOPER-AGENTS.md's PR cycle -- is looking for.

- **DRY, with a threshold.** Two similar blocks are a coincidence; three
  are a pattern. Extracting shared structure from two call sites is as
  likely to produce a wrongly-shaped abstraction as to remove real
  duplication -- and note that this repository's *tests* duplicate setup
  freely and correctly, because a test that reads top to bottom is worth
  more than a DRY one.
- **Naming.** A name says what a thing is for, not what type it holds.
  `unguarded(text)` in `test_command_depth_scan.py` is the standard.
- **A function does one thing at one level of abstraction.** The common
  smell here is a `main()` that parses arguments, does the work, and
  formats the output. Most of the C1 register has this shape.
- **Errors are classified by cause, not by message.** Already
  DEVELOPER-AGENTS.md's rule; repeated here only because it is the error
  handling rule the DTaaS source refers to generically.
- **No speculative configurability.** A `config.toml` key with one caller
  and no user asking for it is a maintenance cost, not flexibility.

## Behaviour before code

DTaaS `CLAUDE.md` is about how an agent should *work*, not what the code
should look like, so it lives with the process rules in
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md#behavioural-rules-think-before-coding)
rather than here. Its four rules -- think before coding, simplicity
first, surgical changes, goal-driven execution -- are reproduced there in
this repository's terms.

One of the four is worth naming here because it interacts with this
document directly. **Surgical changes**: DTaaS says "if unrelated dead
code is observed, report it without removing it." Under the ratchet that
becomes concrete -- noticing that `src/dossier.py` is on the C2 register
while fixing something unrelated in it is a reason to say so in the PR,
not a licence to refactor it in the same diff.

## Build order

What would extend the enforced half, cheapest first. None of it is built.

1. **A linter and formatter (`ruff`).** The obvious next rung: it
   subsumes naming, unused imports, and the orphan-cleanup half of
   surgical changes, and its `PLR0915`/`C901` overlap C1 from a different
   angle. Not adopted in the change that introduces this document, for a
   stated reason: it cannot be verified here without perturbing the
   pinned `.venv-full`, and DEVELOPER-AGENTS.md forbids shipping a check
   that has not actually been run. It needs its own PR, with a measured
   baseline and a `per-file-ignores` register of the same shape as this
   one.
2. **A `# noqa`-free policy for the ratchet.** Once ruff exists, the
   register above and ruff's ignore list are two debt lists; they should
   be one.
3. **Type annotations and a checker.** `src/` is partly annotated. A
   checker over a 100%-covered stdlib codebase is worth having and is its
   own project, not a step in this one.
4. **A doc-drift detector.** The staleness this document's own PR fixed
   in `docs/DESIGN.md` -- "Three layers", against ARCHITECTURE.md's and
   AGENTS.md's four -- had no detector and was found by reading. The
   layer count is the kind of fact a scanner test could pin across the
   documentation tree, in the shape `test_command_depth_scan.py` already
   uses.

   This document is itself an instance. The physical-line-versus-statement
   measurement above (122 against 26, 61 against 1) is quoted here, in
   `tests/test_code_standards_scan.py`'s docstring, and in the PR that
   introduced both; a refactor that moves those numbers leaves three
   copies to update by hand. The register beside them is checked on every
   run and cannot drift. The prose around it can, which is the asymmetry
   this item would close.

## What this does not change

- **No new gate.** `python -m src.draft gate` remains the only gate in
  the project. C1 and C2 are a test, and a test is not a gate on a
  draft -- [SOUL.md](../SOUL.md)'s review-layer rule is untouched.
- **No refactor.** The register freezes today's code exactly as it
  stands.
- **No new dependency.** The scanner is stdlib `ast`, like every other
  check in `tests/` that reads this repository's own tree.
- **No coverage change.** The 100% bar in `pyproject.toml` is unmoved,
  and the scanner is subject to it like everything else.
