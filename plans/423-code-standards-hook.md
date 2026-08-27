# A developer-side hook: C1/C2 at the edit, not at the next test run

Status: **design, unbuilt.** Written 2026-08-27. Implements
[issue 423](https://github.com/prasadtalasila/chitragupta/issues/423).

`docs/HOOKS.md`'s registry has three rows and every one of them is
keyed on a write under `content/drafts/`. **Nothing in this repository
hooks a change to `chitragupta/`.** This plan is one advisory hook that
closes that asymmetry for the two size rules, and the three contracts
an implementer would otherwise have to invent on the way.

**Written for** whoever builds 423. It assumes
[docs/HOOKS.md](../docs/HOOKS.md), which governs every hook here and
whose three-layer rule is the constraint this design is mostly about;
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md) for what C1 and C2
are and why the register is a ratchet; and
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the cycle around the
change.

**Assumed, and not re-argued:** that a hook is the right shape at all.
`docs/HOOKS.md` settles it -- *"Hooks are how a check stops depending on
somebody remembering to run it"* -- and this plan applies that sentence
to this repository's own code rather than restating why it is true.

**Not covered here:** what C1 and C2 *are*, which is
`docs/CODE-STANDARDS.md`; which checks may block, which is
`docs/HOOKS.md`'s rule that decides everything; and the developer-side
auto-improvement loop, which
[plans/f-auto-improvement-adoption.md](f-auto-improvement-adoption.md)
retires. This hook is not that loop and must not grow into it -- see
"What it must not become".

## The gap this closes

Two sentences from two documents, which answer each other and have never
been put together.

`DEVELOPER-AGENTS.md`'s shipping cycle, step 3, on the review plugin:

> Nothing invokes it for you -- it is not in CI and not a dependency --
> so if this step is skipped it simply does not happen.

`style_check_hook.py`'s module docstring, on the prose checker:

> `python -m chitragupta.draft style` has existed since 5.13.0 and
> nothing called it. [...] This hook is the enforced invocation.

The second is the answer to the first, built and measured, and pointed
only at drafts. The C1/C2 ratchet is in the same position `draft style`
was in before #183: a working detector that nothing calls until someone
remembers to.

**What is actually wrong with the current timing.** The ratchet is not
missing and it is not wrong -- `test_no_new_function_exceeds_the_statement_limit`
catches every crossing. It catches it at the next full test run, which
may be a session later. By then the split is a separate piece of work
against code whose reasons have left the context that wrote it. At the
edit, it is an adjustment to the change in hand. That is the whole
value, and it is worth being honest that it is the *only* value: this
adds no detection.

## The class: advisory, and it cannot be a gate

`docs/HOOKS.md`'s rule that decides everything -- *"A hook fails loud or
fails silent, and which one it is follows from what it protects -- never
from what is convenient"* -- puts this on the silent side, and three
independent facts agree:

- **C1/C2 is a ratchet, not ground truth.** The citation gate may block
  because a citekey is in the ledger or it is not. A function at 26
  statements may be correct: `docs/CODE-STANDARDS.md`'s own failure
  message says "if the split is genuinely wrong, add it to
  LEGACY_LONG_FILES in this file and say why in the PR", and #405 took
  that path for `figure_layout/__init__.py`.
- **`docs/TECHNICAL-DEBT.md` forbids it.** Nothing goes red because a
  debt is unpaid, and "leaving an entry open forever is fine."
- **It would be the second blocking hook**, and
  [SOUL.md](../SOUL.md) has why there is exactly one.

So: never emits `{"decision": "block"}`, exits 0 whatever it finds
including its own crash, and says nothing when there is nothing to say
-- the three properties `style_check_hook.py` already documents for the
advisory class, inherited rather than re-derived.

## Contract 1: where the scanner lives

This is the substantive design decision, and it is forced by
`docs/HOOKS.md`'s three layers:

> **Layer 2, `.claude/hooks/`, holds adapters.** [...] an adapter
> contains no logic anyone could want to run by hand.

So the hook must shell out to something hand-runnable. Today there is
nothing to shell out to: the scanner is four functions --
`statement_count`, `code_lines`, `long_functions`, `long_files` --
inside `tests/test_code_standards_scan.py`, and `tests/` is in
`scripts/release.py`'s `EXCLUDE_TOP_LEVEL`. A shipped hook importing
them would work in this checkout and be **broken in every release**,
referencing a tree the archive never contains.

**Extract them to `scripts/code_standards.py`**, hand-runnable as:

```text
python3 scripts/code_standards.py [PATH ...]
```

with `--json` for the hook and human-readable output for a terminal.
No arguments scans the same roots the test does.

**This is a new shape for layer 1, and the plan says so rather than
letting it look like an oversight.** `docs/HOOKS.md`'s diagram puts
layer 1 in `chitragupta/`, and every existing check is reachable as
`python -m chitragupta.draft <verb>`. This one is not, and must not be:
`DEVELOPER-AGENTS.md` places developer tooling in `scripts/`,
`docs/ARCHITECTURE.md`'s artefact graph has no node for a code-standards
scan, and putting it in `chitragupta/` would ship a developer tool
inside the importable package a drafting user installs. The rule that
survives is the one that matters -- *the adapter holds no logic* -- and
`docs/HOOKS.md` already has a precedent for naming an exception rather
than quietly breaking a boundary, in `hook_launchers.py`'s "layer 1 may
read the launcher config, never a payload or an envelope."

`scripts/` ships, `tests/` does not, and `scripts/release.py` and
`scripts/check_version_bump.py` are already stdlib-only modules with
full test coverage. This is the same category.

**The test keeps its authority.** `tests/test_code_standards_scan.py`
imports the scanner instead of defining it, and every assertion it makes
today stays exactly where it is. It still fails on a new offender, on a
stale entry, and on a drifted count. What moves is the implementation,
not the judgement -- and `test_this_scanner_obeys_its_own_statement_limit`
should move with it, since the module it names is now the one in
`scripts/`.

## Contract 2: the register, and Q2 reopened

The hook needs the register. Without it, every edit to any of the 20
registered offenders reports the offence they were registered *for*,
which is noise indistinguishable from a real crossing, and an advisory
hook that cries wolf is one people turn off.

So `scripts/code_standards.py` must read `LEGACY_LONG_FUNCTIONS` and
`LEGACY_LONG_FILES`, which live in `tests/`, which does not ship. **This
is exactly the situation `plans/f-auto-improvement-adoption.md`'s Q2
answered, and exactly the condition under which it reversed itself:**

> **Reopen this only with the aid.** If a seam proposer is ever built,
> the 2026-08-21 reasoning becomes live again unchanged -- and the
> comment question above is then the first thing to settle, not the
> last.

This is a different aid from the one that sentence names -- a hook, not
a seam proposer -- and the distinction does not matter, because the
reasoning it revives is about *placement*, not about what the aid does:
a shipped consumer in `scripts/` reading a register under `tests/` works
in this checkout and is broken in every release. That is true of any
consumer. So the reasoning becomes live again unchanged, and the
register moves to a **root-level `.toml`** read by both
`tests/test_code_standards_scan.py` and `scripts/code_standards.py`:
it ships, it is data rather than code so it is outside C1/C2, and
`tomllib` is stdlib and already used by `scripts/check_version_bump.py`.

**Settle the comment question first, as that reversal instructs.**
`tomllib` discards comments -- `tomllib.loads('a = 1  # 32')` returns
`{'a': 1}` -- so the trailing count that `_recorded_counts()` currently
regex-parses out of the test's own source cannot survive as a comment.
**Promote it to a real value.** An entry becomes a table:

```toml
[[c1]]
name = "tests/test_release.py::make_repo"
statements = 32
```

That keeps `test_every_registered_offender_records_its_current_count`
doing exactly what it does now, against a parsed number rather than a
scraped one, and it keeps the number visible to a reader opening the
file -- which is the property that comment existed for. The alternative,
text-parsing the TOML to recover comments, gains nothing over the status
quo and should be rejected explicitly rather than drifted into.

**The blast radius, enumerated, because the reversal's third finding was
that nobody had enumerated it:**

| Site | What changes |
| --- | --- |
| `tests/test_code_standards_scan.py` | the two literals and `_recorded_counts` are replaced by a read of the new file |
| `tests/test_technical_debt_scan.py` | imports the registers from the test module (`from test_code_standards_scan import ...`); repoint or re-read |
| `docs/CODE-STANDARDS.md` | its "**3 functions** and **17 modules**" sentence, pinned by `test_the_registers_are_the_size_this_document_says` |
| `docs/TECHNICAL-DEBT.md` | Tier 1's copy of the same pair, pinned by `tests/test_technical_debt_scan.py` |
| `scripts/release.py` | nothing -- a new root-level file **ships by default**, which is correct here and is the reason to check rather than assume |

That last row is a trap worth naming: `EXCLUDE_TOP_LEVEL` is a denylist,
so a new root-level file needs no edit to ship. It also means a
root-level file added carelessly ships whether or not anyone meant it
to.

## Contract 3: `chitragupta init` copies `.claude/` verbatim

`chitragupta/init.py`'s `COPY_VERBATIM` is
`(".claude", "docs", "assets", "AGENTS.md", "CLAUDE.md", "SOUL.md",
"README.md")`. So **every entry added to `.claude/settings.json` is
scaffolded into every `chitragupta init` project**, and those projects
have no `chitragupta/`, `scripts/` or `tests/` tree at all --
`CLAUDE.md`'s routing table says that is deliberate, not missing.

The hook will therefore be registered, and launched, in projects where
there is nothing for it to check. It must be **inert there, not broken**:

- The adapter decides "is this a write I care about?" the way
  `draft_target.py` already does for drafts -- resolve the path, take
  the repo root from the hook's own location, test containment with
  `is_relative_to` against `chitragupta/` and `scripts/`, require a
  `.py` suffix. In a scaffolded project nothing is ever under those
  roots, so the answer is always no and the hook says nothing.
- If `scripts/code_standards.py` is absent, exit 0 in silence. A missing
  developer tool in a drafting project is the expected state, not a
  fault, and it is the same distinction `session_start_hook.py` draws
  when it reports an unsynced corpus as a *stage* rather than a failure.

**Do not reuse `draft_target.py`.** It answers "was this write a draft?"
and its docstring is explicit that what must be shared between hooks is
the *definition of a draft*. This hook needs the opposite question. A
sibling helper is right if a second developer-side hook ever appears;
one hook does not need one yet.

## What it reports

One finding per crossing, and nothing else:

- a function in the written file now over 25 statements and **not in the
  C1 register**;
- the written file now over 250 code lines and **not in the C2 register**.

Each names the count and the limit, and nothing more.
`docs/HOOKS.md`'s "How much an advisory hook would actually say" is the
precedent for keeping this short: a whole chapter's prose report is a
dozen lines.

**A registered offender is silent even when it grows.** That is not an
oversight to fix later: `docs/CODE-STANDARDS.md` deliberately does not
cap the growth of a registered module -- *"Pinning each to today's exact
size would fail on every ordinary edit and would be turned off within a
week"* -- and a hook that reported it would be the same rule by another
route, arriving more often.

## What it must not become

- **Not a second source of truth.** `tests/test_code_standards_scan.py`
  stays the authority. The hook adds *invocation*, which is the same
  division `style_check_hook.py` holds against `draft style`, and the
  same one this plan's Contract 1 preserves by having both read one
  scanner.
- **Not a count-minimiser.** R3's discipline: the check is "is it under
  the threshold", never "minimise the count". A hook that reported the
  register's size, or nagged about unpaid debt, is the driver
  `plans/f-auto-improvement-adoption.md` retired, re-arriving on a
  different trigger.
- **Not a gate**, and not a route to becoming one later. The condition
  that would justify revisiting is new evidence that C1/C2 has become
  ground truth, which it cannot, because the register's escape hatch is
  part of the standard.
- **Not a fix path.** It reports; a person edits. The condition
  `docs/HOOKS.md` names for when a step becomes a skill -- *"if the step
  ever grows from one command into a multi-step judgement loop"* -- is
  the line, and this is one command.

## What it costs, in files

| File | Change |
| --- | --- |
| `scripts/code_standards.py` | new -- the scanner, extracted, plus a CLI and `--json` |
| `.claude/hooks/code_standards_hook.py` | new -- adapter only |
| `.claude/settings.json` | one exec-form `PostToolUse` entry, `python`, braced placeholder |
| the register file | new, root-level `.toml` |
| `tests/test_code_standards_scan.py` | imports the scanner and reads the register; assertions unchanged |
| `tests/test_technical_debt_scan.py` | its register import repointed |
| `tests/test_code_standards_hook.py` | new -- the subprocess contract |
| `tests/test_code_standards_hook_modules.py` | new -- branches, per `test_hook_modules.py`'s reason |
| `docs/HOOKS.md` | a fourth registry row, the layer-1 exception named, the three-layer diagram updated |
| `docs/CODE-STANDARDS.md`, `docs/TECHNICAL-DEBT.md` | the two pinned register-size sentences |
| `docs/INSPIRATION.md` | harness engineering -- jcode and OpenClaw, if the hook ships |

`tests/test_settings_launchers.py` needs **no** change and that is by
design: it iterates every entry rather than naming them, so a fourth
hook inherits the launcher contract instead of copying whichever line
was nearest. Its `target.is_file()` assertion will cover the new adapter
automatically.

## Open questions

1. **Does the advisory channel fire often enough to be annoying?**
   `docs/HOOKS.md` records #185's accepted cost -- the gate re-checks a
   whole draft on every edit of it. This hook parses one file, so the
   cost is smaller, but the *report* frequency is the open part: a
   function hovering at 26 statements reports on every edit until it is
   split or registered. Measure before shipping; if it is bad, the
   answer is a per-session dedup in the adapter, not silence.
2. **Should `scripts/` be in scope, or only `chitragupta/`?** C1 covers
   `chitragupta`, `scripts` and `tests`; C2 covers only the first two.
   Hooking `tests/` would report on the test file a developer is writing
   at the moment they are writing it, which is either the most useful
   case or the most annoying one, and nothing here decides it.
3. **Whether `hookSpecificOutput.additionalContext` is honoured on a
   `PostToolUse` from a non-draft path.** Measured for drafts (trials 1a
   and 3), and there is no reason the path would matter -- but
   `docs/HOOKS.md`'s standard is that a hook mechanism is measured or
   flagged as unmeasured, and this one is unmeasured.
