# 🪝 Hooks: what runs automatically, and what is allowed to block

Status: **implemented.**

Four hooks exist: `citation_gate_hook.py`, `style_check_hook.py`,
`session_start_hook.py` and `code_standards_hook.py`. The first two share
one `draft_target.py` (and through it `patch_paths.py`), and all four
share one `safe_path.py`. All four launch as `python` in exec form from
`.claude/settings.json`. Codex's `.codex/hooks.json` launches the gate,
style and session-start hooks through a `python -P -c` one-liner, and
OpenCode's plugin runs the gate and style hooks
([HARNESS.md](HARNESS.md)). `code_standards_hook.py` is the one hook that
is not about a draft: it watches a change to this repository's own code.

Hooks are how a check stops depending on somebody remembering to run it.
[ARCHITECTURE.md](ARCHITECTURE.md) states the reason under "Grounding is
enforced, not requested": the citation gate runs once because the skill's
prose says to and once because the harness does it regardless. This page
is about that second run: what may be hooked, what a hook may do once it
fires, and which answers are measured.

**Written for** anyone adding a hook to this repository or changing
`.claude/settings.json`. It assumes `DEVELOPER-AGENTS.md` and
[CODE-STANDARDS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/CODE-STANDARDS.md).
What the checks themselves *do* is elsewhere: the citation gate in
[AGENTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/AGENTS.md)
and [ARCHITECTURE.md](ARCHITECTURE.md), the prose checker in
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §9 and
[HOUSE-STYLE.md](HOUSE-STYLE.md).

## 🔑 The rule that decides everything

> **A hook fails loud or fails silent, and which one it is follows from
> what it protects, never from what is convenient.**

The two failure modes are not symmetric, and the wrong one is invisible.
`citation_gate_hook.py` is the only automatic enforcement of the rule
[CLAUDE.md](../CLAUDE.md) opens with. A gate that stops running does not
announce itself: the hook file is still there, the settings file still
lists it, the tests still pass, and drafts land ungated. That is worse
than having no gate, because the absence is *believed to be a presence*.

A session-context injection has the opposite shape. If it fails, the
session is slightly less informed and everything else still works, so
crashing the session to report it would be the larger harm. The common
upstream pattern of exiting 0 silently when a hook cannot start is right
for that kind of hook, and may never be applied to the citation gate.

## 🧩 The two classes

Classify a hook once, when proposing it, and every later question is
already answered:

| | **Gate class** | **Advisory class** |
| --- | --- | --- |
| Members | `citation_gate_hook.py` | `session_start_hook.py`, `style_check_hook.py`, `code_standards_hook.py` |
| What it protects | the citekey invariant | a recorded preference, or the operator's attention |
| May emit a blocking decision | yes, the only one that may | never |
| On its own internal failure | must be detectable | exit 0, say nothing |
| May be skipped by a config key | no | yes |
| May use conditional spawning (`if`) | no | yes |
| May run `async` | no | no, see [below](#-deliberately-not-done) |

Only one hook is ever in the gate class. [SOUL.md](../SOUL.md) (*"A gate
`FAIL` is a failing test, not a lint warning"*) and
`DEVELOPER-AGENTS.md` both bar promoting any new check into a gate beside
`chitragupta/citation_gate.py`. The gate compares a citekey against the
ledger, which is ground truth. Every other check compares prose against
something a human typed, which can be wrong, stale or deliberately
overridden, so blocking on it refuses a *correct* draft on a *bad
target*.

The operating formula: **invocation is enforced, conformance is not.** A
hook guarantees the findings reach the agent. Only the gate guarantees
anything about what the agent then does.

## 🪢 A second mechanism: git's own hooks

The registry below is not everything that runs automatically.
`git-hooks/pre-commit` runs `actionlint` over `.github/workflows/` when a
commit stages one, and runs `python -m chitragupta figure sync --check`
over any staged figure file (`assets/tikz/*.tex`,
`content/drafts/**/figures/*.tex`). It is not a registry row, because it
is a different mechanism:

| | `.claude/hooks/` | `git-hooks/` |
| --- | --- | --- |
| Fired by | the agent harness on its file-write tools: Claude Code's `Write`/`Edit`, Codex's `apply_patch`, OpenCode's plugin | git, on `commit` |
| Sees | what *this agent* wrote | every path into a commit: a human in an editor, another agent, `git apply`, `sed` |
| Installed by | `.claude/settings.json`, which ships and is scaffolded | `core.hooksPath`, set by `install_full_pipeline.sh dev-deps` |
| May block | only the citation gate | the workflow check, yes (see below); the figure check, never |

**Why the workflow check may block.** The one-gate rule governs the
review layer, where a finding is a judgement about a draft. A workflow
file either parses and type-checks or it does not, and `ci.yml`'s lint
job already fails on the same check, so blocking at the commit only
moves an identical verdict earlier. The rule about not blocking when it
cannot tell still holds: an absent `actionlint` is silence, because the
install stage is opt-in.

**Why the figure check does not block.** A stale house figure-style
block still compiles and renders, and `figure sync` fixes it in one
command. Nothing in CI fails on a draft's figure, so blocking would make
the hook stricter than the build. (A stale scaffold under `assets/tikz/`
does fail CI, in `tests/test_figure_sync.py` and
`tests/test_tikz_scaffolds.py`.) The hook prints what `--check` found and
the command to run, and the commit goes ahead. When the interpreter it
finds (`CHITRAGUPTA_PYTHON`, else the checkout's `.venv/bin/python`, else
`python3`) cannot run the check, or crashes without printing sync's
summary line, it says once that figures were not checked.

`core.hooksPath` is per-clone config that cannot be committed, and a
hook directory git has not been pointed at runs nothing. That is why
`dev-deps` sets it, instead of a README asking you to.

## 🗄 The registry

| Event | Matcher | Script | Class | Status |
| --- | --- | --- | --- | --- |
| `PostToolUse` | `Write\|Edit` | `citation_gate_hook.py` | gate | built |
| `PostToolUse` | `Write\|Edit` | `style_check_hook.py` | advisory | built |
| `PostToolUse` | `Write\|Edit` | `code_standards_hook.py` | advisory | built |
| `SessionStart` | `startup\|clear` | `session_start_hook.py` | advisory | built |

**Separate entries on one matcher, not one dispatcher.** The
`PostToolUse` hooks are separate processes with separate settings
entries, for fault isolation: a defect in a prose checker must not be
able to weaken the citekey gate. The harness already merges several
hooks' findings correctly (see [the
trials](#-what-is-measured-and-what-is-merely-documented)), so the usual
argument for one dispatcher does not apply. The one decision the draft
hooks share, *is this write a draft?*, lives in one helper beside them
instead of being copied, because a copy is what drifts.

### 🛫 The session preflight

`session_start_hook.py` exists because a hook that fails to start cannot
report that it failed to start, and no test here can start a hook the
way the harness does. The preflight is launched by the same interpreter
name it vets, so if `python` is missing the preflight is missing too.
The check therefore lives in `chitragupta/hook_launchers.py`, and
`python -m chitragupta.draft gate`, which runs on an interpreter that has
demonstrably started and which every genre skill runs, makes it as well.

It makes three checks, of which **only the first two are faults**:

| Checked | How | Verdict |
| --- | --- | --- |
| Can each registered hook's launcher start, and can it import `chitragupta`? | `settings.json` parsed, each command looked up (a bare name on `PATH`'s absolute entries only), unbraced placeholders flagged, then one short `<program> -c "import chitragupta"` per distinct launcher **whose bare name (no path separators) names a Python interpreter**, run by the absolute path `chitragupta/programs.py` resolves from `PATH`'s absolute entries | fault |
| Does the gate still refuse a fabricated citekey? | run it in a throwaway tree | fault |
| Has the corpus been synced? | `python -m chitragupta.corpus ledger` | **stage**; a ledger that is there but cannot be read (its exit 3) is a fault |
| all three fine | -- | says nothing at all |

In the second check the alarm is the bad probe *passing*. Refused is
healthy; accepted (exit 0) means the invariant is unenforced; anything
else, a crash or the gate's exit 3, is reported as a gate that could not
run its self-test, with the exit code and output. A non-zero exit alone
is not enough: the probe insists on seeing the fabricated key in the
output, since a gate rejecting the probe for its *location* would also
exit non-zero.

#### 💡 Why a pre-sync corpus is a stage and not a fault

The normal sequence is clone -> `config.toml` ->
`python -m chitragupta.corpus sync` -> drafting. A user who starts a
session before the sync has done nothing wrong. A preflight that called
an empty ledger a failure would fire on every first session and teach
people to ignore the one channel reserved for real faults. So it is
reported as a position in that sequence, with the command that advances
it. There are two pre-sync states (no ledger file, and an empty one),
each with its own sentence, so the hook matches the instruction they
share.

Both fault checks are corpus-independent:

- The launcher check reads a config file and spawns each distinct
  launcher once only if it is a bare, Python-shaped name. The probe is a
  Python invocation, so a `bash` or `node` launcher would report a false
  "cannot import chitragupta" every session; it is not spawned. The
  bare-name rule is a security boundary: the settings file was found by
  walking up the working directory, so a planted one could name an
  attacker's `/that/tree/python3`. A bare name is resolved by
  `chitragupta/programs.py` against `PATH`'s absolute entries only,
  because on Windows the current directory is searched first and a
  relative `PATH` entry is the current directory by another name. The
  existence check uses the same lookup. A path-qualified launcher keeps
  the existence check and forgoes the import probe.
- **A fabricated citekey is absent from an empty ledger and a full one
  alike.** With no `ledger.sqlite` at all, `chitragupta.draft gate` exits
  0 on a citation-free draft and non-zero on a fabricated key (measured).

Cost: **126 ms** for both subprocesses, against 16 ms for a bare
interpreter. It writes nothing under the user's `content/` and reads no
draft of theirs.

## 🏗 The shared design, in files

The two draft hooks answer the same three questions in the same order
(*was this write a draft? what does the check say? how do I hand that
back?*) and differ only in the middle one. The design is three layers
with a rule about what may live in each.

```text
.claude/
├── settings.json               the launcher: one exec-form entry per hook
└── hooks/
    ├── draft_target.py         shared -- payload in, draft path or None out
    ├── patch_paths.py          shared -- the paths an apply_patch payload touches
    ├── safe_path.py            shared -- which `chitragupta` a child may import
    ├── session_start_hook.py   advisory class -- the preflight, never blocks
    ├── citation_gate_hook.py   gate class     -- may block
    ├── style_check_hook.py     advisory class -- never blocks
    └── code_standards_hook.py  advisory class -- never blocks

chitragupta/
├── draft.py                    `python -m chitragupta.draft <gate|style|...>`
├── citation_gate.py            what the gate hook shells out to
├── hook_launchers.py           can the registered launchers start?
├── import_probe.py             ...and can each import chitragupta?
└── style_check.py              what the style hook shells out to

scripts/
└── code_standards.py           what the size hook shells out to

tests/
├── test_draft_target.py        the shared helper, both classes of caller
├── test_safe_path.py           checkout or installed project, every shape
├── test_hook_launchers.py      the launcher check, every shape
├── test_settings_launchers.py  the real settings.json, against the contract
├── test_patch_paths.py         apply_patch payloads, every shape
├── test_citation_gate_hook.py  the model the other two follow
├── test_style_check_hook.py    the process contract, not the branches
├── test_code_standards_hook*.py  the size hook, process and module
└── test_session_start_hook.py  the preflight
```

**Layer 1 holds the checks.** They are importable, tested, and know
nothing about hooks, harnesses or JSON envelopes. Each is reachable by
hand: `python -m chitragupta.draft <verb>` for the three drafting
checks, and `python3 scripts/code_standards.py` for the fourth.

Two named exceptions. **`scripts/code_standards.py`** is about *where*:
it is developer tooling, which `DEVELOPER-AGENTS.md` places in
`scripts/`, and in the package it would ship inside what a drafting user
installs. It is still layer 1 because it is hand-runnable and the adapter
above it holds nothing. **`hook_launchers.py`** (and its split-out
`import_probe.py`) is the other: **layer 1 may read the launcher config,
never a payload or an envelope.** It reads `settings.json` and returns
English sentences, and it has to be here because the preflight cannot
report its own interpreter missing and [the
gate can](#-the-session-preflight).

**Layer 2, `.claude/hooks/`, holds adapters.** An adapter reads a
`PostToolUse` payload on stdin, decides whether it is interested, shells
out to layer 1, and writes one JSON document. **An adapter contains no
logic anyone could want to run by hand**, which is what makes each check
usable from a skill, a terminal or CI without the hook, and why a skill
that invoked the hook would be [inverting the
dependency](#-a-skill-that-runs-the-hook).

**Layer 3, `settings.json`, holds the launcher**, and nothing else. See
[the launcher contract](#-the-launcher-contract).

### 🔒 What the shared helper holds, and why sharing it is safe

`draft_target.py` answers *was this write a draft?* and nothing else.
`citation_gate_hook.py`'s docstring records each part as learned from a
real near-miss:

- `file_path` may be relative, so it is resolved against the repo root
  instead of ignored;
- the repo root comes from the hook's own on-disk location, never from the
  target path or the working directory;
- containment is tested with `is_relative_to` on resolved paths, not with a
  substring match on `/content/drafts/`;
- the suffix must be one this pipeline writes (`.md`, `.tex`).

Separate processes and a shared module do not conflict. What must not be
shared is the failure of a *check*: a prose checker that crashes or hangs
must not take the gate down, and separate processes guarantee that. What
must be shared is the *definition of a draft*, because two hooks
disagreeing about which writes they cover is a worse bug than either
could have alone. The helper is held to the same 100% line-and-branch
bar as everything else.

A hook is run by absolute path, so its own directory is first on
`sys.path` and `import draft_target` needs no path manipulation. So it
breaks under `python -P` or `PYTHONSAFEPATH`, neither of which the
launcher sets (`safe_path.py` sets it on a hook's *children*), and
`tests/test_citation_gate_hook.py`'s `hook_repo` fixture must copy all
three helpers beside the hook script.

### 🛡 Which `chitragupta` a hook's child imports

A hook's child (`python -m chitragupta.draft ...` or `python -c "import
chitragupta"`) runs from the project root, and `-m` and `-c` put that
directory first on `sys.path`. A checkout relies on that. In a project
`chitragupta init` scaffolded, a committed `chitragupta/` or
`chitragupta.py` would shadow the installed package and run with the
user's privileges. So `safe_path.py` asks where `chitragupta` resolves
*without* the cwd entry: outside the root means installed, and every
child gets `PYTHONSAFEPATH=1`; inside the root or nowhere leaves the
launch as it was. `code_standards_hook.py` starts no scanner at all in
an installed project, since `init` scaffolds no `scripts/`. The import
probe and `session_start_hook.py`'s own import make the same call from
their side.

The pipeline's own commands go through no hook, so `chitragupta init`
writes its copies of skills, agents, `AGENTS.md` and `docs/` with
`python -P` before each `-m chitragupta...` and `-c` snippet
(`MODULE_FORM` in `chitragupta/init.py`). This page, docs/PACKAGING.md
and docs/CLI.md are copied unchanged. An improvised or hand-typed
command gets no `-P`. To refresh a project's copies, scaffold afresh
elsewhere and copy them over; `chitragupta init --force` in the project
itself also resets `config.toml` and `content/acronyms.toml`.

**What this cannot close:** an interpreter that finds no installed
`chitragupta` at all looks exactly like a checkout. The gate still fails
closed, and the preflight reports "no installed chitragupta visible to
`<python>`". A checkout whose venv also holds a non-editable
`chitragupta-cli` reads as an installed project, so its hooks run that
copy instead of the working tree; install the checkout editable, or not
at all. `chitragupta init` refuses to scaffold into a directory already
holding `chitragupta/` or `chitragupta.py`, with or without `--force`.

## 📜 The launcher contract

The launcher is the line in `.claude/settings.json` that starts the hook
process. No test imports it and CI never executes it, which is why it is
the part most likely to be wrong without anyone noticing.

**Use exec form.** A command hook runs as exec form when `args` is set,
passing each element as one argument and ignoring the shell entirely:

```json
{
  "type": "command",
  "command": "python",
  "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/citation_gate_hook.py"],
  "timeout": 30,
  "statusMessage": "Checking citekeys against the ledger..."
}
```

This is what `.claude/settings.json` contains for all four hooks, and
`tests/test_settings_launchers.py` asserts it of every entry in that
file.

**Brace every placeholder.** Claude Code substitutes
`${CLAUDE_PROJECT_DIR}` itself, into `command` and each `args` element.
The unbraced `$CLAUDE_PROJECT_DIR` relies on *the shell*, which on
Windows without Git Bash is `powershell`, where it expands to nothing.
CI runs a blocking `windows-latest` leg, so that host is a real one.

**The interpreter name is `python`.** `python3` is generally absent on
Windows and `python` is often absent on Debian-family Linux, so the
choice is decided on three findings:

- **A venv guarantees `python` everywhere and `python3` only on POSIX.**
  CPython 3.13's `venv/__init__.py` writes no `python3.exe` on Windows.
- **The rest of this repository already requires `python`.** Every
  documented invocation is `python -m chitragupta.*`.
- **That makes the losing host a different kind of host.** Without
  `python`, nothing else here works either, so the user finds out from
  the first command. Without `python3`, on Windows, only the gate would
  go quiet.

The launcher need not be the venv's interpreter: the gate is [tier
1](CLI.md#-which-interpreter) and runs under a bare interpreter.
`install_full_pipeline.sh`'s opt-in `os-deps` stage installs
`python-is-python3` on Debian-family hosts, and `python-deps` reports
what `chitragupta/hook_launchers.py` finds, so a host that skipped
`os-deps` still hears about it. [WINDOWS.md](WINDOWS.md) has the other
platform's version of the question.

**A dead launcher is silent, so something else has to say so.** A hook
whose `command` does not resolve produces no error to the model and
nothing in a log (trial 4 below). `session_start_hook.py` and
`python -m chitragupta.draft gate` both report it through
`chitragupta/hook_launchers.py`.

**No polyglot launcher.** A file that is both a batch file and a shell
script solves the adjacent problem of bash being absent, but fails
outright under exec form, so the two cannot be layered. The hooks are
`.py`, so the Windows auto-detection that prepends `bash` to a command
containing `.sh` does not touch them; do not rename them defensively.

## 📜 The output contract

**Stdout is one JSON document, or nothing at all.** A single stray
`print()` ahead of the JSON makes stdout unparseable, and the whole
payload is discarded in silence while the hook still exits 0 (trial 1).

**The advisory channel is `hookSpecificOutput.additionalContext`, and only
that.** Plain stdout on exit 0 goes to the debug log and never reaches
the model (trial 1b).

**An advisory hook never emits a blocking decision.** The gate's shape is
`{"decision": "block", "reason": ...}` on stdout. Any other hook is
barred from it by the rule above, and printing anything beside its own
JSON object would destroy its delivery anyway.

**Fail open on malformed stdin.** Invalid JSON, valid JSON that is not an
object, and a `tool_input` that is not a dict all mean *no file path was
given*; each returns 0 and does not raise.

**Use `sys.executable` for any subprocess**, never a bare `python` or
`python3`. A name that fails to resolve raises `FileNotFoundError`, which
exits non-zero *without* the block, so the draft lands ungated. This
does not contradict the launcher's bare `python`: a running hook already
*is* an interpreter, while `settings.json` can only give the harness a
name. Resolve by name once, at the outermost edge. Where the lookup is
this repository's own code, as in `.opencode/chitragupta/gate.js`, it
resolves `python` on `PATH`'s absolute entries and spawns the absolute
path, the rule
[SECURITY.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/SECURITY.md)
gives for every launch.

**Finish inside the harness's timeout, or block.** Every hook gets
`"timeout": 30`, and a killed hook prints nothing, which for the gate is
a silent pass. So `citation_gate_hook.py` stops itself first and names
which way in its block reason: a draft over `MAX_GATED_LINES` (100,000)
is blocked as too large before any gate starts, and a gate still running
at `GATE_TIMEOUT` (20 s, leaving the import probe's 5 s) is stopped and
blocked. The gate is linear in draft length and well under a second at
100k lines.

**Tell "could not check" from "checked and failed".** The gate exits 3
when the ledger is there but cannot be read. `citation_gate_hook.py`
still blocks, because nothing passed, but passes on the gate's
diagnosis, never "fix the offending citekey(s)". The hook does not
import `chitragupta`, so it spells the code as `GATE_COULD_NOT_RUN`, and
a test pins that to `chitragupta.ledger_refusals.EXIT_UNREADABLE`.

**Emit only the field this host consumes.** Claude Code reads
`hookSpecificOutput.additionalContext`, Cursor a top-level
`additional_context`, and the SDK standard is a top-level
`additionalContext`. Claude Code reads more than one without
deduplicating, so emitting several delivers the payload twice. The hooks
do not branch: Codex documents the same block shape and
`hookSpecificOutput` field, and OpenCode's plugin reads the Claude Code
shape and hands it on, so one envelope serves all three ([HARNESS.md](HARNESS.md),
"Measured, and what is still not"). If a later harness reads another
field, the branch goes here, keyed on the harness, emitting only that one.

**Codex and OpenCode launch the same scripts.** `.codex/hooks.json`
registers the gate, style and session-start hooks on
`apply_patch|Edit|Write`, and `.opencode/plugins/chitragupta-gate.js`
pipes each file tool's arguments to `citation_gate_hook.py`, then
`style_check_hook.py`. Neither holds gate logic. The one payload shape
they added is `apply_patch`'s: the patch text in `tool_input.command`,
whose file headers `patch_paths.py` reads, so every draft one write
names is gated. A patch that mentions a draft but whose headers cannot
be read blocks: it is the one exception to failing open, because failing
open there is a silently inert gate.

**Codex's launcher cannot be a relative path.** Codex runs a hook in the
session's working directory and sets no project-directory placeholder,
so `python .claude/hooks/<x>.py` fails to start from any subfolder
(measured). Each `.codex/hooks.json` line is a `python -P -c` one-liner
that walks up to the folder holding `.codex/hooks.json` and runs the
hook from there. `tests/test_settings_launchers.py` runs the real line
from two levels down.

## 📊 What is measured, and what is merely documented

Six trials against this repository's gate hook with a throwaway second
entry beside it, on Claude Code:

| Trial | Tool | Hook stdout | Outcome |
| --- | --- | --- | --- |
| 1 | `Write` | plain text **then** JSON | nothing arrived |
| 1a | `Edit` | JSON only | `additionalContext` arrived |
| 1b | `Edit` | plain text only | nothing arrived |
| 2 | `Edit` | JSON only, gate blocking in the same turn | **both** arrived |
| 3 | `Write` | JSON only | `additionalContext` arrived |
| 4 | `Write` | *never ran*: `command` not on PATH | nothing arrived |

A disk log showed the hook fired in the first five, so their nulls are
delivery failures; in trial 4 nothing was invoked, and from outside the
two look identical. That silence is why a dead launcher needs a reporter
that does not share its interpreter.
So the advisory channel works on `Write` and `Edit`, advisory output
survives a co-firing block in the same turn, two entries on one matcher
both deliver, and mixing plain text with JSON destroys the payload.
Exec form with the braced placeholder was measured the same way: the
hook received the absolute path, and the gate still blocked a
fabricated citekey. `python -m chitragupta.corpus ledger` exits 0 in
both pre-sync states and 3 only on an unreadable ledger, and takes no
lock, so the preflight can call it every session.

**Two things rest on measurement alone.** `additionalContext` is not
documented for `PostToolUse` specifically, and the gate's top-level
`{"decision": "block"}` on `PostToolUse` is attested nowhere. Trial 2
proves it works today. `tests/test_citation_gate_hook.py` asserts only
that the shape is *emitted*, and nothing here re-checks that the
harness *honours* it. The Windows half of the `python` decision is
likewise read off CPython's `venv` module, not run on a Windows host
without Git Bash.

## 🧪 Testing a hook

`.claude/hooks` is inside `[tool.coverage.run].source`, so the same
100% line-and-branch bar applies to a hook as to `chitragupta/`. A hook
runs as `python <path>`, and **a spawned process contributes no
coverage**, so it needs both halves:

| | subprocess tests | module tests |
| --- | --- | --- |
| Files | `test_citation_gate_hook.py`, `test_session_start_hook.py`, `test_style_check_hook.py`, `test_code_standards_hook.py` | `test_hook_modules.py`, `test_code_standards_hook_modules.py` |
| Run the hook as | the harness does | an imported module |
| Prove | the stdin/stdout contract | every branch |
| Contribute coverage | no | yes |

A refactor that broke the stdin envelope would pass the module tests and
fail the subprocess ones. **Instrumenting the children instead is ruled
out**: `tests/test_citation_gate_hook.py`'s `_IS_COVERAGE_BOOTSTRAP`
documents how mixed statement and branch data kill the run at combine
time. The scope is declared once in `[tool.coverage.run].source` and the
suite runs a bare `--cov`, so a new path cannot be silently left out.

The tests worth having are the negative ones: a write outside
`content/drafts/` or with a non-gated suffix is ignored; each
malformed-stdin shape and a checker crash exit 0; an advisory hook never
emits a blocking decision; **stdout parses as JSON**; and every odd shape
a settings file can arrive in, since a raise there would silence the
whole preflight report.

**No test can start a hook the way the harness does.**
`tests/test_settings_launchers.py` narrows the gap: it reads the live
`.claude/settings.json` and asserts of every entry that it is exec form,
launches `python`, braces every placeholder, and names a script that
exists. Hook tests stay in pytest, where CI runs them, because ones kept
outside the suite rot.

## 🚫 Deliberately not done

**A dispatcher process.** Consolidating every `PostToolUse` check into
one process is tidier, and rejected because it trades fault isolation
for a merge problem the harness has already solved.

**`async: true` on the style hook.** Advisory findings that arrive after
the agent has moved on defeat their purpose, and whether async output
reaches the model at all is unprobed. Available only if a real pass
proves the synchronous cost unacceptable.

**Conditional spawning (`if`) on the gate.** `if` reportedly suppresses
the spawn when it does not match, which would save the style hook
re-checking a whole draft on every edit. That comes from a third-party
survey, is untested here, and is version-gated: if an older harness
skips a hook with an unrecognised key, the gate is silently inert.
Advisory hooks may use it. The gate may not. The in-script path check
stays either way.

**A `jq` dependency.** Incompatible with the stdlib-only posture
`chitragupta/style_check.py` documents, and `jq` is not reliably present.
Python's `json` module builds the envelope.

**A per-hook enable/disable config.** Rejected because the gate must not
be individually disableable, and a harness-level `disableAllHooks`
already exists for anyone who needs the escape hatch.

### 🤖 A skill that runs the hook

**Invoking `style_check_hook.py` from a skill is an antipattern.** The
hook is a harness adapter. A skill has no payload, so it would have to
fabricate one and parse the envelope back out: the dependency arrow
backwards, coupled to an output format that is measured rather than
documented. Anything that wants the check calls
`python -m chitragupta.draft style` directly.

**A generic skill wrapping `python -m chitragupta.draft style` is the
wrong shape here**, for three reasons. [GENRE.md](GENRE.md) already
states shared invariants in each `SKILL.md` or a shared reference and
pins them with a text scan over `.claude/skills/`. Skills are matched on
user intent, so routing the step through one would make invocation
discretionary again. And the step is one deterministic command, so a
wrapper costs a tool call and a context load to save nothing.

**The condition that would flip this:** if the step grows into a
multi-step judgement loop (read the findings, decide, edit, re-check,
log), it *is* a skill, as `agenda-reviser` is for verbatim findings.
Today a prose finding's fix path is `draft-reviser`'s copy-edit mode.
