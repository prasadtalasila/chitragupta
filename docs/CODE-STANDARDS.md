# 🤝 Code standards: what is binary, what is judgement, and the ratchet

Status: **standard, partly enforced.** Written 2026-08-13. Updated 2026-08-24.
The two size rules below are enforced by `tests/test_code_standards_scan.py`;
everything under [The rest of the checklist](#-the-rest-of-the-checklist) is a
review standard with no detector, and [Build order](#-build-order) says which
detectors would come next.

This is the code counterpart of
[WRITING-STANDARDS.md](WRITING-STANDARDS.md): that one is the standard the
genre skills write prose against, this one is the standard an agent
changes *this repository's own code* against.

**Written for** someone changing code in `chitragupta/` or `scripts/`, or
deciding whether a proposed rule is worth enforcing. It assumes
`DEVELOPER-AGENTS.md` for the process around a
change -- test policy, the local check suite, commit/PR/release
conventions -- and states only what the code itself must look like.

**Not covered here:** prose standards for drafts
([WRITING-STANDARDS.md](WRITING-STANDARDS.md)), module boundaries and
which layer owns what ([ARCHITECTURE.md](ARCHITECTURE.md), and
`DEVELOPER-AGENTS.md`'s "Module boundaries"),
and the drafting loop this document borrows its shape from
([AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)).

## 🧭 Table of contents

- [Where these rules come from](#-where-these-rules-come-from)
- [The rule that decides everything](#-the-rule-that-decides-everything)
- [The comment rules, and the misreading to avoid](#-the-comment-rules-and-the-misreading-to-avoid)
- [Why statements, not lines](#-why-statements-not-lines)
- [The Boy Scout Rule, and surgical changes](#-the-boy-scout-rule-and-surgical-changes)
- [The binary rules](#-the-binary-rules)
- [What a ratchet is, and the debt register](#-what-a-ratchet-is-and-the-debt-register)
- [The rest of the checklist](#-the-rest-of-the-checklist)
- [Code smells: the review vocabulary](#-code-smells-the-review-vocabulary)
- [Behaviour before code](#-behaviour-before-code)
- [Build order](#-build-order)
- [What this does not change](#-what-this-does-not-change)

## 💡 Where these rules come from

The source standard is the widely-circulated
[clean-code summary](https://gist.github.com/wojteklu/73c6914cc446146b8b533c0988cf8d29)
of Robert C. Martin's *Clean Code* (Prentice Hall, 2008) --
[INSPIRATION.md](INSPIRATION.md#-code-standards) records the provenance.
Its nine sections are the checklist this document is written against, and
[The rest of the checklist](#-the-rest-of-the-checklist) maps every rule in
it to one of four fates: **enforced**, **already here** under another
name, **review standard**, or **not applicable** with the reason.

Two things follow from adopting a checklist rather than writing one.

**Nothing is restated.** Where a rule already existed in this project
under a different name, the table points at it instead of repeating it. A
rule stated twice is a rule that will eventually be stated two different
ways.

**Nothing is adopted unread.** Two of the nine sections land differently
here than a quick reading suggests -- the comment rules and the Boy Scout
Rule -- and both get their own section below rather than a row in a table.
A checklist applied without noticing where it collides with the codebase
is how a standard produces worse code than none.

## 🔑 The rule that decides everything

> **R3:** "An unattended item's check is **binary**. No continuous score
> is ever the thing being optimised."
>
> -- [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#-the-requirements), which
> owns the wording

That rule was written for drafts. It applies here unchanged, and it is
why this document is split the way it is. "No function exceeds 25
statements" is binary and is enforced. "This code is clean" is a score.

A score invites the same Goodhart failure
[HOUSE-STYLE.md](HOUSE-STYLE.md#-why-a-readability-index-is-a-trap)
describes for readability indices. A maintainability metric is minimised
by splitting functions past the point where the logic survives the break
-- and every one of those edits passes its own re-check.

So: a small number of binary rules with a detector and a register, and a
larger number of judgement rules with neither. The judgement rules are
not weaker -- they are what review is for. They are not things a
machine may drive to zero.

**The loop stays open.** This document borrows AUTO-IMPROVEMENT.md's
shape, not its automation. Nothing here proposes a code-fixing loop;
[R11](AUTO-IMPROVEMENT.md#-the-requirements) -- "its only trigger is a
person asking" -- is the reason, and it applies with more force to code
than to prose.

## 💬 The comment rules, and the misreading to avoid

The clean-code comment rules are eight, and they split cleanly in two:

| Banned | Required |
| --- | --- |
| 2. Don't be redundant | 6. Use as explanation of intent |
| 3. Don't add obvious noise | 7. Use as clarification of code |
| 4. Don't use closing brace comments | 8. Use as warning of consequences |
| 5. Don't comment out code. Just remove | |

Rule 1 -- "always try to explain yourself in code" -- governs both: reach
for a better name or an explanatory variable before reaching for a
comment.

**The misreading** is to compress all eight into "comment only where the
code is non-obvious", and then apply that to this repository. That reading
inverts rules 6 through 8. This project's comments are overwhelmingly
*intent*, *clarification* and *warning*: which alternative was tried, what
broke, why the obvious thing is wrong. `.github/workflows/ci.yml` is
roughly half prose by line count, and every paragraph of it answers a
question a future reader would otherwise re-litigate. An agent that
"cleans up" those comments has destroyed the most valuable thing in the
file, while believing it applied a clean-code rule.

The canon does not say that. It says don't be **redundant** -- and a
comment recording why a version pin is load-bearing is the opposite of
redundant, because that information exists nowhere in the code.

So, stated for this repository:

- **Banned: the *what*-comment.** A comment restating the line below it
  (`# increment the counter`) is noise. So is a commented-out block:
  delete it, git remembers.
- **Required: the *why*-comment**, wherever a reader could reasonably ask
  "why this way?" -- a non-obvious constraint, a rejected alternative, a
  bug that produced the current shape, a version pin that is
  load-bearing. Absence of one on a surprising decision is a review
  finding.

This is [SOUL.md](../SOUL.md)'s "**Judgment is logged, not just made**" in
executable form, and SOUL.md is the tie-break if the two ever seem to
conflict.

**This is also why the size rules count statements** -- a physical-line
limit taxes exactly the thing this section requires.

## 💡 Why statements, not lines

"Functions should be small" is the rule; a line count is the usual proxy.
Here that proxy mostly measures comment discipline:

| Scope | Functions over 25 **physical lines** | Functions over 25 **statements** |
| --- | --- | --- |
| `chitragupta/` (383 functions) | 128 | 26 |
| `tests/` (1926 functions) | 63 | 1 |

*Measured at 5.7.1.* These four numbers are dated rather than pinned by a
test, unlike the register sizes below, and deliberately: the
physical-line column moves whenever any function gains a comment, so
pinning it would make this document churn on unrelated PRs. The
conclusion it supports is an order-of-magnitude gap, which is stable; the
exact figures are an illustration and are re-measured when someone has
reason to.

The gap is the section above. A function carrying twelve lines of
rationale about why a partial Docling parse must raise before anything is
written is not a long function; it is a short function with its reasoning
attached. Counting physical lines puts the size rule and the comment rules
in direct conflict and rewards deleting the rationale, which is the one
edit this project least wants.

Counting **statements** measures what "do one thing" is actually about --
how much a function *does* -- and is blind to how well it is explained. On
that measure the codebase is in good shape: 26 offenders in `chitragupta/`, not
128, and the tests hold the bar almost perfectly at 1 in 1926.

The same correction applies to files: `chitragupta/config.py` is 941 physical
lines and 453 lines of code, the difference being 488 lines of
per-setting rationale. The file rule counts code lines -- non-blank,
non-comment -- for the same reason.

**This is a re-expression, not a relaxation.** One outlier got stricter
under it, not looser: at 5.7.1, `chitragupta/sync.py::run` was 322 physical lines
but **117 statements**, 4.7× the next worst function in the repository.
Physical lines ranked it 2.4× the next worst and understated how far out
it was. (It has since been split back under the limit and delisted -- the
ratchet doing its job -- but the measurement is what justified counting
statements, so it stays.)

## 🧹 The Boy Scout Rule, and surgical changes

The clean-code general rules include:

> **3. Boy scout rule.** Leave the campground cleaner than you found it.

Read as an instruction to each edit, that contradicts this project's
process rule, which is that a change should be **surgical**: don't
refactor unrelated code, match the local style, report pre-existing dead
code rather than deleting it in the same diff
(`DEVELOPER-AGENTS.md`'s "Behavioural rules: think before coding").
Both cannot be followed at the level of a single edit.

They are reconciled by moving the Boy Scout Rule up one level. **The
ratchet is this project's Boy Scout Rule** -- applied to the repository
across pull requests rather than to whatever file you happen to have
open:

- The register may only shrink, so the campground does get cleaner.
- It gets cleaner in its own pull request, where the cleanup is reviewed
  on its merits, rather than smuggled into an unrelated diff where a
  reviewer is looking at something else.

That keeps what the rule is *for* -- decay is not permitted -- while
keeping diffs reviewable. Concretely: noticing that a module is on the
register while fixing something unrelated in it is a reason to say so in
the PR, not a licence to refactor it there. `chitragupta/dossier.py` was
this example until #219 gave it its own PR and delisted it, and
`chitragupta/review/verbatim_check.py` was this example until #361 did
the same -- the ratchet doing exactly what it's for.

The one case where the rule applies to your own edit unchanged is the
orphan you created: an import, variable or helper that *your* change made
unused is yours to remove.

## ✅ The binary rules

Two rules. Both are enforced by `tests/test_code_standards_scan.py`,
which rides the existing `pytest --cov` run rather than adding a second
quality gate to keep in sync -- the same idiom as
`tests/test_command_depth_scan.py`, `tests/test_cli_help_is_short.py` and
`tests/test_removed_command_scan.py`.

| | Rule | Scope | Counted as |
| --- | --- | --- | --- |
| **C1** | A function body holds at most **25 statements** | `chitragupta/`, `scripts/`, `tests/` | `ast` statement nodes in the body, not descending into nested definitions |
| **C2** | A module holds at most **250 lines of code** | `chitragupta/`, `scripts/` | Physical lines that are neither blank nor a whole-line comment |

**Why the scopes differ.** C1 covers the tests because the tests already
hold it -- 1 offender in 1926 -- so including them locks in a bar that is
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
is better than the alternative reading, which is that its long
functions were quietly not counted -- see
`bench/README.md` for the current self-check count
and the reasoning behind each of the four things `bench/` sits outside.

### 📊 Cognitive complexity: the bar is 25, not SonarQube's default 15

SonarQube's Python analysis ships S3776 -- "Cognitive Complexity of
functions should not be too high" -- with a default threshold of **15**.
That default is not this project's standard. **The standard here is
25**, deliberately aligned with C1's 25-statement rule. The two measure
different things -- how much a function *does* against how hard its
control flow is to *follow* -- but they draw the line at the same
altitude.

A complexity bar lower than the statement bar would drive exactly the
over-splitting [R3](#-the-rule-that-decides-everything) warns about:
functions cut past the point where the logic survives the break, with
every cut passing its own re-check.

Operationally:

- A function with cognitive complexity **above 25** is treated like a C1
  offence: split it along its natural seams, or say in the PR why it
  cannot be split.
- A SonarCloud S3776 finding **at 25 or below** is marked *Accepted* in
  the SonarCloud UI, not "fixed" -- splitting a 16-complexity function
  to satisfy a tool's default is churn, not cleanup.
- The threshold itself lives in SonarCloud's **quality profile**, which
  is server-side configuration: set `python:S3776`'s `threshold`
  parameter to 25 there. It cannot be pinned from
  `sonar-project.properties`, so this section is the durable record of
  the decision, and the profile is what has to match it.

## 🗄 What a ratchet is, and the debt register

A **ratchet** is a mechanical pawl that lets a wheel turn one way and
blocks it turning back. As a software check it means: measure something,
freeze today's number, and fail the build if it gets *worse* -- while
saying nothing about it being imperfect today.

It exists because of the gap between the two options a new rule normally
has, both of which fail:

| Option | What happens here |
| --- | --- |
| Enforce the rule outright | 28 functions and 12 modules fail on day one. The build is red for reasons nobody in this PR caused, so the rule gets disabled or the threshold raised until it passes -- and a threshold tuned to today's worst code is not a standard |
| Write it down as guidance | It is followed until the first deadline. Nothing detects the drift, and two years later the document describes a codebase that no longer exists |

The ratchet takes the useful half of each. Concretely, here:

- Today's offenders are frozen in `code-standards-register.toml`'s
  `[[c1]]` and `[[c2]]` tables -- **3
  functions** and **15 modules**. Those two counts are themselves pinned
  by `test_the_registers_are_the_size_this_document_says`, so a shrinking
  register cannot leave this sentence stale. The register moved out of
  `tests/test_code_standards_scan.py` in issue 431, so that the
  edit-time hook could read it from a file the release archive ships;
  the test still enforces it and is still the authority.
- **New offenders fail.** Anything not in the register that crosses
  either threshold fails the suite, with the count and the limit in the
  message.
- **Fixed offenders must be delisted.** When a registered function or
  module comes back under its threshold, the test fails and says to
  delete its entry. That is what makes this a ratchet and not a permanent
  amnesty: the register can only shrink, and every shrink is a visible
  diff.
- **Each entry records its current size**, checked by
  `test_every_registered_offender_records_its_current_count`, so the
  register also answers "which debt is biggest" rather than only "which
  debts exist".

### 💡 Why a ratchet suits this project specifically

Three reasons beyond the general argument.

1. **It matches the one invariant's shape.** This project already
   believes that the way to prevent a bad outcome is a mechanical check
   that cannot be argued with, rather than a resolution to be careful --
   that is the citation gate. The ratchet is the same move applied to
   code decay: an agent cannot talk its way past a failing test, and a
   future session that has never read this document still cannot land a
   40-statement function.
2. **The work is agent-driven and session-scoped.** Each session wakes up
   fresh ([SOUL.md](../SOUL.md)'s "Continuity"). Guidance that lives only
   in prose depends on the right file being read at the right moment; a
   failing test reaches a session that read nothing.
3. **It makes the debt legible instead of ambient.** "The code quality is
   poor" is unactionable and, measured properly, was not even true here.
   "`chitragupta/sync.py::run` is 117 statements and `chitragupta/dossier.py` is
   1605
   code lines" -- the register's two worst entries on the day it was
   written -- is a worklist, ordered, with the entries worth taking
   first at the top.

The register is a debt list, not an allowance. Neither of those two is
taken in the change that introduces this document -- refactoring them is a
code change, this is a standard, and "several small, reviewable PRs over
one large one" applies to the project's own housekeeping.

**What the ratchet deliberately does not do** is cap the growth of a
module already on the C2 register. A registered file may get longer
without failing. Capping each at today's exact size would fail on every
ordinary edit and would be turned off within a week; the growth of a
registered file is caught by C1 on its functions and by review.

## 📋 The rest of the checklist

Every remaining rule from the source, and where it lands. **Review** means
a human or Copilot looks for it in a PR; there is no detector, and
[the rule above](#-the-rule-that-decides-everything) says why most of these
should not get one.

### 📜 General rules

| Rule | Fate |
| --- | --- |
| Follow standard conventions | Already here: DEVELOPER-AGENTS.md's "Conventions a new stage has to follow" |
| Keep it simple; reduce complexity | Already here: the "Simplicity first" behavioural rule |
| Boy scout rule | [Reconciled above](#-the-boy-scout-rule-and-surgical-changes) -- the ratchet is this project's form of it |
| Always find root cause | Already here, in a sharp form: "Classify a failure by cause on the exception, not by matching its message." Adding a cause means adding a mark, not a string match |

### 🏗 Design rules

| Rule | Fate |
| --- | --- |
| Keep configurable data at high levels | Already here: `config.toml` is the single source, every key overridable by an env var |
| Prefer polymorphism to if/else | **N/A as stated** -- `chitragupta/` is classless. Its functional equivalent *is* used: `review.AIDS` is a dispatch table, and a new aid is added by registering it rather than by editing a branch |
| Separate multi-threading code | Already here: the process pool lives in `chitragupta/pdf_text/` and `sync._parse_parallel`, and nothing else in the codebase knows about it |
| Prevent over-configurability | Review. A `config.toml` key with one caller and no user asking for it is a maintenance cost, not flexibility |
| Use dependency injection | Already here as **the probe pattern**: a stage depends on "is pandoc on PATH?", answered at run time, never on a `--target` flag naming its environment |
| Follow Law of Demeter | Already here as module boundaries: `references.py` reads the ledger's `bib_fields` column and must not reach through to `bibliography.bib` |

SOLID is not in the source list and is not adopted as a slogan here, for
the same reason polymorphism is N/A. Where its principles apply they
already appear above under the names this project uses: single
responsibility is "do one thing" plus module boundaries, and dependency
inversion is the probe pattern.

### 👓 Understandability

| Rule | Fate |
| --- | --- |
| Be consistent | Review, and the highest-value one in this list. A second way of doing something already done is the most common finding here |
| Use explanatory variables | Review |
| Encapsulate boundary conditions | Already here, as a whole module: `chitragupta/passages.py` is the single place that decides which span of a source may be shown, so no caller re-derives it |
| Prefer dedicated value objects to primitive types | **Mostly N/A.** A citekey is deliberately a bare `str`, because it is also a filename stem and a ledger key; the invariant is enforced at the one entrance (`bib_reader.citekey_problem()`) rather than by a wrapper type |
| Avoid logical dependency | Review |
| Avoid negative conditionals | Review |

### 🏷 Names

All six -- descriptive and unambiguous, meaningful distinction,
pronounceable, searchable, named constants instead of magic numbers, no
type prefixes -- are **review** standards, adopted as written. The house
example is `unguarded(text)` in `test_command_depth_scan.py`: it says what
the thing is for, not what type it returns. `MAX_STATEMENTS` and
`_GUARD_WINDOW` are the magic-number rule as practised.

### 🧩 Functions

| Rule | Fate |
| --- | --- |
| Small | **Enforced** as C1, counted in statements |
| Do one thing | Review, and the reason C1 works as a proxy. The common smell here is a `main()` that parses arguments, does the work, and formats the output -- most of the C1 register has that shape |
| Use descriptive names | Review (see Names) |
| Prefer fewer arguments | Review |
| Have no side effects | Review. Note the deliberate exception: the corpus layer's whole job is a side effect, and it is confined to the one layer that takes the write lock |
| Don't use flag arguments | Review, with a live precedent: `--target host\|docker` is documented as informational only, because the probes decide and nothing branches on it |

### 📁 Source code structure

All **review** standards, adopted as written: vertical separation of
concepts, related code dense, variables declared near use, dependent and
similar functions close, functions in downward dependency order, short
lines, no horizontal alignment, whitespace to group, consistent
indentation.

"Keep lines short" is the one that could cheaply become a detector.
[Build order](#-build-order) puts it with `ruff`, which enforces it as
`E501` rather than needing its own scanner.

### 🧱 Objects and data structures

Largely **N/A**, and the reason is worth stating rather than leaving as
an omission. `chitragupta/` has almost no classes, and the few it has --
`interrupt_guard`, `_AnnotatedStream` -- are small context managers and
wrappers.

"Prefer data structures" and "hide internal structure" are what the
codebase already does: modules expose functions over plain dicts, tuples
and `sqlite3` rows. "Should be small", "do one thing" and "small number
of instance variables" apply to any class that does appear, and C1
already covers its methods.

### 🧪 Tests

| Rule | Fate |
| --- | --- |
| One assert per test | **Adopted in spirit, not literally.** One *behaviour* per test, named for it. A literal single assert would split `test_a_deeper_path_is_flagged_and_reported_in_full` into two tests that mean nothing apart |
| Readable | Review -- and the reason the tests duplicate setup freely rather than DRYing it. A test that reads top to bottom is worth more than a DRY one |
| Fast | Already held: the whole suite runs in well under a minute |
| Independent | Already held, and load-bearing: `tests/conftest.py` isolates per-test state |
| Repeatable | Already held, and it is a *product* rule here too -- the review layer's reports carry no timestamp, so two runs over unchanged input produce byte-identical output |

## 🔍 Code smells: the review vocabulary

The six smells are adopted as the vocabulary for a review finding, because
naming the smell is what turns "this feels wrong" into a claim someone can
agree or disagree with.

| Smell | What it looks like here |
| --- | --- |
| **Rigidity** -- a small change cascades | Adding a parse failure cause that requires touching every caller, instead of adding a mark on the exception |
| **Fragility** -- one change breaks many places | The reason the review layer has one output contract in `review/__init__.py` rather than seven aids each writing their own path |
| **Immobility** -- code cannot be reused | The reason `chitragupta/passages.py` is a module and not logic inlined into `verbatim_check` |
| **Needless complexity** | Speculative configurability, an abstraction with one call site, defensive handling for an impossible state |
| **Needless repetition** | Two similar blocks are a coincidence; three are a pattern. Extracting from two call sites is as likely to produce a wrongly-shaped abstraction as to remove real duplication |
| **Opacity** -- hard to understand | Usually a missing *why*-comment rather than bad code |

## 🎯 Behaviour before code

Four rules about how an agent should *work* rather than what the code
should look like. They live with the process rules in
`DEVELOPER-AGENTS.md`'s "Behavioural rules: think before coding"
rather than here: think before coding, simplicity first, surgical changes,
goal-driven execution. The third is the one
[reconciled above](#-the-boy-scout-rule-and-surgical-changes).

## ▶ Build order

What would extend the enforced half, cheapest first, as proposed when
this document was written. All four items have since landed, each in a
different shape than proposed here -- see their own notes.

1. ~~**A linter and formatter (`ruff`).**~~ **Both halves are landed now,
   in two separate steps.** The linter landed first, as `pylint`, not
   `ruff`: `ci.yml`'s `lint` job runs
   `pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks` at a binary
   zero-messages bar (`docs/TECHNICAL-DEBT.md §5.1`), measured and
   enforced the way this item asked for -- a baseline first, a
   `.pylintrc` `disable=` register of the same shape this item wanted for
   `ruff`. It still subsumes what this rung was for: the Names rules,
   unused imports (`unused-import`), and `too-many-*` overlapping C1 from
   a different angle. `ruff` itself landed after, in two more rounds --
   item 2 as the linter, `BLE`/`E`/`F`/`RUF100`; #362 as the formatter,
   `ruff format --check` over `chitragupta`/`scripts`/`tests`/`bench`/
   `.claude/hooks` (wider than either linter's roots -- see
   `docs/TECHNICAL-DEBT.md`'s ruff-format subsection for why). Line
   length -- `docs/TECHNICAL-DEBT.md §5.1`'s "31 long lines", hand-fixed
   at the time -- is enforced now on both counts: `E501` from item 2, and
   the formatter refusing a line its own wrapping would have shortened.
2. ~~**A `# noqa`-free policy for the ratchet.**~~ **Landed as `ruff`**
   (`docs/TECHNICAL-DEBT.md`'s ruff subsection), at the same binary bar
   pylint and markdownlint hold. `ci.yml`'s `lint` job runs
   `ruff check chitragupta scripts .claude/hooks`, `pyproject.toml`'s
   `[tool.ruff.lint]` selects `BLE` (this item's own reason for existing)
   plus `E`/`F` (which subsumes item 1's remaining `E501` gap) and
   `RUF100` -- the rule that makes a `# noqa: BLE001` a checked claim
   rather than a comment nothing reads, which is what makes this a
   `# noqa`-free *policy* rather than just a second linter. One of the 12
   existing markers turned out to be unneeded on that evidence
   (`chitragupta/pdf_text/_backends.py`'s re-raising `except` -- BLE001's own
   definition exempts a block that ends in `raise`) and was removed;
   the rest were confirmed live, not assumed so.
3. ~~**Type annotations and a checker.**~~ **Annotated in full, in #355 --
   and the checker declined, not deferred.** Every `def` under
   `chitragupta/` now carries a return annotation, and
   `tests/test_annotation_scan.py` ratchets it the way C1/C2 are
   ratcheted: today's zero gaps are frozen, and a new one fails the
   suite. Its `ast`-walk is the count's own source of truth, not a figure
   copied here to go stale. What stayed unbuilt is a real type checker --
   `mypy` over a 100%-covered stdlib codebase is still worth having and
   is still its own project, not a step in this one, which is the same
   call this item made when it was written rather than a reopened
   question.
4. **A doc-drift detector.** **Half built, in #239** -- and the half
   that is worth naming is the half that was left, because it is not a
   matter of effort.

   **Built:** every claim about the *registers* is now binary.
   `test_the_registers_are_the_size_this_document_says` pins this
   document's copy of the two sizes;
   `tests/test_technical_debt_scan.py` pins TECHNICAL-DEBT.md's copy,
   and additionally fails when that document names a function or module
   as currently-open C1/C2 debt that the register no longer lists. Both
   incidents on record are caught by it, checked against the real
   historical files: the C1/C2 counts that read 26/13 against a real
   10/11 until #228, and `chitragupta/sync.py::run`, delisted in #178 and still
   named as the second-highest-priority open item four days later.

   **Not built, and not a backlog item:** `docs/DESIGN.md`'s "Three
   layers", against ARCHITECTURE.md's and AGENTS.md's four -- the
   staleness this document's own PR fixed, found by reading. That is a
   free-standing factual claim with no register behind it, so there is
   nothing binary to check it against, and
   [R3](AUTO-IMPROVEMENT.md#-the-requirements) rules out reaching for a
   prose-accuracy *score* instead. A claim becomes checkable when
   something machine-readable becomes its source of truth, not when
   someone writes a cleverer scanner.

   This document is itself an instance of the unbuilt half. The
   physical-line-versus-statement measurement above (128 against 26, 63
   against 1) is quoted here and in
   `tests/test_code_standards_scan.py`'s docstring; a refactor that moves
   those numbers leaves two copies to update by hand.

## 🚫 What this does not change

- **No new gate.** `python -m chitragupta.draft gate` remains the only gate in
  the project. C1 and C2 are a test, and a test is not a gate on a
  draft -- [SOUL.md](../SOUL.md)'s review-layer rule is untouched.
- **No refactor.** The register freezes today's code exactly as it
  stands.
- **No new dependency.** The scanner is stdlib `ast`, like every other
  check in `tests/` that reads this repository's own tree.
- **No coverage change.** The 100% bar in `pyproject.toml` is unmoved,
  and the scanner is subject to it like everything else.
