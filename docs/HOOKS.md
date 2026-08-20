# Hooks: what runs automatically, and what is allowed to block

Status: **built, as of 5.20.0.** Written 2026-08-15. Three hooks exist --
`citation_gate_hook.py`, `style_check_hook.py` and
`session_start_hook.py` -- sharing one `draft_target.py`, all launching in
exec form, as `python`. #197 is closed: the placeholder is braced, the
interpreter name is settled below, and a launcher that cannot start is now
reported from two sides rather than one.

Hooks are how a check stops depending on somebody remembering to run it.
[ARCHITECTURE.md](ARCHITECTURE.md) states the reason under "Grounding is
enforced, not requested" -- the citation gate runs twice on the same draft,
once because the skill's own prose says to and once because the harness
does it regardless, and *neither run is the skill's own good intentions*.
This document is about that second run: what may be hooked, what a hook may
do once it fires, and which of the answers here are measured rather than
assumed.

**Written for** anyone adding a hook to this repository or changing
`.claude/settings.json`. It assumes
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md), which governs any change to
this repository's code, and [CODE-STANDARDS.md](CODE-STANDARDS.md) for what
that code must look like.

**Not covered here:** what the checks themselves *do*. The citation gate is
[AGENTS.md](../AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md); the prose
checker is [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §9 and
[HOUSE-STYLE.md](HOUSE-STYLE.md). This file is about *invocation*, which is
a separate question and has separate rules.

## Table of contents

- [The rule that decides everything](#the-rule-that-decides-everything)
- [The two classes](#the-two-classes)
- [The registry](#the-registry)
- [The shared design, in files](#the-shared-design-in-files)
- [The launcher contract](#the-launcher-contract)
- [The output contract](#the-output-contract)
- [What is measured, and what is merely documented](#what-is-measured-and-what-is-merely-documented)
- [Testing a hook](#testing-a-hook)
- [Deliberately not done](#deliberately-not-done)
- [Prior art](#prior-art)
- [Open questions](#open-questions)

## The rule that decides everything

> **A hook fails loud or fails silent, and which one it is follows from
> what it protects -- never from what is convenient.**

Everything else in this document is a consequence. The rule exists because
the two failure modes are not symmetric and the wrong one is invisible.

`citation_gate_hook.py` is the only automatic enforcement of the rule
[CLAUDE.md](../CLAUDE.md) opens with -- a citekey may be used only if it
came from a real parse of a real PDF. A gate that quietly stops running
does not announce itself: the tree still contains a hook file, the settings
file still lists it, the tests still pass, and drafts land ungated. That is
strictly worse than having no gate, because the absence is now *believed
to be a presence*.

A session-context injection has the opposite shape. If it fails, the
session is slightly less informed and everything else still works.
Crashing the session to report it would be the larger harm.

Both upstream collections this document borrows from encode the
fail-silent half explicitly, and both are right to:

```bat
REM No bash found - exit silently rather than error
REM (plugin still works, just without SessionStart context injection)
exit /b 0
```

-- `obra/superpowers`, `hooks/run-hook.cmd`

```bash
[ -f "$SCRIPT" ] && bash "$SCRIPT" || true
```

-- `addyosmani/agent-skills`, `hooks/hooks.json`

Neither may be applied to the citation gate.

## The two classes

Classify a hook once, at the point of proposing it, and every subsequent
question is already answered:

| | **Gate class** | **Advisory class** |
|---|---|---|
| Members | `citation_gate_hook.py` | `session_start_hook.py`, `style_check_hook.py` (#185) |
| What it protects | the citekey invariant | a recorded preference, or the operator's attention |
| May emit a blocking decision | yes -- the only one that may | never |
| On its own internal failure | must be detectable | exit 0, say nothing |
| May be skipped by a config key | no | yes |
| May use conditional spawning (`if`) | no | yes |
| May run `async` | no | no, see [below](#deliberately-not-done) |

Only one hook is ever in the gate class. [SOUL.md](../SOUL.md) -- *"A gate
`FAIL` is a failing test, not a lint warning"* -- and
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) both bar promoting any new
check into a gate beside `chitragupta/citation_gate.py`. #183 records the argument
in full.

The gate compares a citekey against the ledger, which is ground truth.
Every other check compares prose against something a human typed, which
can be wrong, stale, or deliberately overridden. Blocking on the second
kind refuses a *correct* draft on a *bad target* -- a failure the gate
cannot have by construction.

The operating formula, from #183: **invocation is enforced, conformance is
not.** A hook guarantees the findings reach the agent. Only the gate
guarantees anything about what the agent then does.

## The registry

| Event | Matcher | Script | Class | Status |
|---|---|---|---|---|
| `PostToolUse` | `Write\|Edit` | `citation_gate_hook.py` | gate | built |
| `PostToolUse` | `Write\|Edit` | `style_check_hook.py` | advisory | built |
| `SessionStart` | `startup\|clear` | `session_start_hook.py` | advisory | built |

**Two entries on one matcher, not one dispatcher.** Both `PostToolUse`
hooks are separate processes with separate settings entries. The reason is
fault isolation: a defect in a prose checker must not be able to weaken the
citekey gate, and one process means one crash takes both. The usual
argument for consolidating -- controlling how several checks' findings
merge into a single stdout -- does not apply, because the harness already
merges them correctly; see [the trial table](#what-is-measured-and-what-is-merely-documented).

The two share exactly one decision -- *is this write a draft?* -- and it
is factored into one helper beside them rather than copied, because a
copy is what drifts.

The subtleties it holds are recorded in `citation_gate_hook.py`'s
docstring, and were learned from a real near-miss. `file_path` may be
relative. The repo root must be derived from the hook's own location
rather than from the target path. And containment must be tested with
`is_relative_to`, not a substring match on `/content/drafts/`.

### The session preflight

`session_start_hook.py` exists because a hook that fails to start cannot
report that it failed to start. The settings file still lists it, its tests
still pass, and the citation gate silently stops enforcing anything. No
test in this repository can start a hook the way the harness does -- a
launcher is a line in a config file the harness consumes, not code the
suite imports -- so the detector has to be something that looks from
outside.

**One such detector is not enough, and this took a second attempt to
see.** The preflight is launched by the same interpreter name it vets. If
`python` is missing, the preflight is missing too, and the report that was
supposed to arrive never does -- on precisely the host where the gate is
dead. The check therefore lives in `chitragupta/hook_launchers.py`, and
`python -m chitragupta.draft gate` makes it as well: that command runs on an
interpreter which has demonstrably started, and every genre skill runs it.
The two reporters share one implementation.

It makes three checks, of which **only the first two are faults**:

| Checked | How | Verdict |
|---|---|---|
| Can each registered hook's launcher start, and can it import `chitragupta`? | `settings.json` parsed, `shutil.which` on each command, unbraced placeholders flagged, then one short `<program> -c "import chitragupta"` per distinct resolved launcher | fault |
| Does the gate still refuse a fabricated citekey? | run it in a throwaway tree | fault |
| Has the corpus been synced? | `python -m chitragupta.corpus ledger` | **stage** |
| all three fine | -- | says nothing at all |

Note the inversion in the second: the alarm is the bad probe *passing*.

#### Why a pre-sync corpus is a stage and not a fault

This is the design decision the hook turns on, and the naive version gets
it wrong. The normal sequence is clone -> `config.toml` ->
`python -m chitragupta.corpus sync` -> drafting. A user who starts a session before
that third step has done nothing wrong; they are not there yet. A
preflight that called an empty ledger a failure would fire on every first
session in every clone, and would teach people to ignore the one channel
reserved for real faults. So it is reported as a position in that sequence,
with the command that advances it, and never as `BROKEN`.

That distinction is what lets the hook run this early at all. Both fault
checks are corpus-independent by construction:

- The launcher check reads a config file, calls `shutil.which`, and -- for
  each distinct launcher that resolves -- spawns it once to ask whether it
  can import `chitragupta`. No corpus either way.
- **A fabricated citekey is absent from an empty ledger and a full one
  alike.** Measured before it was relied on: with no `ledger.sqlite`
  present at all, `chitragupta.draft gate` exits 0 on a citation-free draft and
  non-zero on a fabricated key, exactly as against a populated one.

Two smaller things learned building it, both from a failing test rather
than from reasoning. There are **two** pre-sync states, not one -- no
ledger file, and a ledger file with no rows -- and the corpus layer prints
a different sentence for each, so matching either one alone leaves the
other silent; the hook matches the instruction they share instead. And a
non-zero exit is not enough to call the gate live: a gate rejecting the
probe for its *location* would also exit non-zero, so the probe insists on
seeing the fabricated key in the output, or a broken gate would report as a
working one.

Cost: **126 ms** for both subprocesses, against 16 ms for a bare
interpreter. It writes nothing under the user's `content/` and reads no
draft of theirs.

## The shared design, in files

Both `PostToolUse` hooks answer the same three questions in the same order
-- *was this write a draft? what does the check say? how do I hand that
back?* -- and differ only in the middle one. The design that serves both is
three layers with a rule about what may live in each.

```text
.claude/
├── settings.json               the launcher: one exec-form entry per hook
└── hooks/
    ├── draft_target.py         shared -- payload in, draft path or None out
    ├── citation_gate_hook.py   gate class     -- may block
    └── style_check_hook.py     advisory class -- never blocks

chitragupta/
├── draft.py                    `python -m chitragupta.draft <gate|style|...>`
├── citation_gate.py            what the gate hook shells out to
├── hook_launchers.py           can the registered launchers start?
└── style_check.py              what the style hook shells out to

tests/
├── test_draft_target.py        the shared helper, both classes of caller
├── test_hook_launchers.py      the launcher check, every shape
├── test_settings_launchers.py  the real settings.json, against the contract
├── test_citation_gate_hook.py  the model the other two follow
└── test_style_check_hook.py    the process contract, not the branches
```

**Layer 1, `chitragupta/`, holds the checks.** They are importable, tested, and
know nothing about hooks, harnesses or JSON envelopes. Each is reachable by
hand as `python -m chitragupta.draft <verb>`.

`hook_launchers.py` is the one exception, and the rule names it rather than
being quietly broken: **layer 1 may read the launcher config, never a
payload or an envelope.** That line is where the boundary actually falls.
An adapter is defined by handling the harness's stdin/stdout contract, and
this module handles neither -- it reads `settings.json` and returns English
sentences. It has to be here, because the preflight cannot report its own
interpreter missing and [the gate can](#the-session-preflight).

**Layer 2, `.claude/hooks/`, holds adapters.** An adapter reads a
`PostToolUse` payload on stdin, decides whether it is interested, shells
out to layer 1, and writes one JSON document.

One rule keeps this layer honest: **an adapter contains no logic anyone
could want to run by hand.** That is what makes the check usable from a
skill, a terminal or CI without going near the hook. It is also why a
skill that invoked the hook would be [inverting the
dependency](#a-skill-that-runs-the-hook).

**Layer 3, `settings.json`, holds the launcher**, and nothing else. See
[the launcher contract](#the-launcher-contract).

### What the shared helper holds, and why sharing it is safe

`draft_target.py` answers *was this write a draft?* and nothing else. It
was described here before it existed, and extracted when the second hook
arrived rather than after there were two copies to drift apart. Both
hooks need the identical answer, and the question is subtler than it looks
-- `citation_gate_hook.py`'s docstring records each part as learned from a
real near-miss:

- `file_path` may be relative, so it is resolved against the repo root
  rather than ignored;
- the repo root comes from the hook's own on-disk location, never from the
  target path or the working directory;
- containment is tested with `is_relative_to` on resolved paths, not with a
  substring match on `/content/drafts/`;
- the suffix must be one this pipeline writes (`.md`, `.tex`).

The obvious objection is that this document argues for two separate
processes on fault-isolation grounds and then has them import the same
module. The distinction is between **runtime** and **agreement**. What must
not be shared is the failure of a *check*: a prose checker that crashes,
hangs or emits nonsense must not be able to take the gate down with it, and
separate processes guarantee that. What must be shared is the *definition
of a draft*, because two hooks disagreeing about which writes they cover is
a worse bug than either could have alone -- and it is the bug a copied
forty lines produces the first time one copy is fixed. The helper is held
to the same 100% line-and-branch bar as everything else.

A hook is run by absolute path, so Python puts the hook's own directory on
`sys.path` first and `import draft_target` resolves with no path
manipulation. Two consequences worth knowing before they surprise someone:
this breaks under `python -P` or `PYTHONSAFEPATH`, neither of which the
launcher sets; and `tests/test_citation_gate_hook.py`'s `hook_repo`
fixture, which copies the hook script into a temporary root so that
`Path(__file__).resolve()` lands there, must copy the helper beside it.

## The launcher contract

The launcher is the line in `.claude/settings.json` that starts the hook
process. It is not code, no test imports it, and CI never executes it --
which is why it is the part most likely to be quietly wrong.

**Use exec form.** A command hook runs as exec form when `args` is set and
shell form when it is omitted. Exec form passes each element as one
argument with no quoting, and ignores the shell entirely:

```json
{
  "type": "command",
  "command": "python",
  "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/citation_gate_hook.py"],
  "timeout": 30,
  "statusMessage": "Checking citekeys against the ledger..."
}
```

That is not an example: it is what `.claude/settings.json` now contains,
for all three hooks, and `tests/test_settings_launchers.py` asserts it of
every entry in that file rather than of any named one. Exec form and the
braced placeholder were confirmed working before being adopted -- the
harness substituted the placeholder to an absolute path and the gate still
returned its blocking decision on a fabricated citekey.

**Brace every placeholder.** `${CLAUDE_PROJECT_DIR}` is substituted by
Claude Code itself, into `command` and into each `args` element, before any
shell sees it. The unbraced `$CLAUDE_PROJECT_DIR` in shell form is instead
relying on *the shell* to expand it -- and the shell defaults to
`powershell` on Windows when Git Bash is not installed, where that syntax
names an undefined variable and expands to nothing. This repository runs a
blocking `windows-latest` leg in CI, so that is not a hypothetical host.

**The interpreter name is `python`.** It has no *portable* answer --
`python3` is standard on Linux and generally absent on Windows, `python` is
present on Windows and often absent on Debian-family Linux -- so it was
the second hazard of #197, and it is decided rather than inherited, on
three findings:

- **A venv guarantees `python` everywhere and `python3` only on POSIX.**
  Read out of CPython 3.13's `venv/__init__.py`: the POSIX branch creates
  `python`, `python3` and `python3.13`; the Windows branch writes
  `python.exe` and `pythonw.exe`, with debug and free-threaded variants,
  and no `python3.exe` at all.
- **The rest of this repository already requires `python`.** Every
  documented invocation across `.claude/skills/`, `AGENTS.md`,
  `README.md` and `docs/` is `python -m src.*` -- some 470 of them,
  against a handful of `python3` in `bench/RESULTS.md`. The hook launcher
  was the outlier, not the standard-bearer.
- **That makes the losing host a different kind of host.** `python`'s
  failure case is a Debian or Homebrew clone with no venv active, where
  *nothing else here works either*, so the user finds out from the first
  command they run. `python3`'s failure case is Windows, where the rest of
  the pipeline runs fine and only the gate goes quiet -- which is the
  silent degradation this document exists to prevent.

The launcher does not have to be the venv's interpreter, which is what
makes the choice this narrow: the gate is [tier 1](CLI.md#which-interpreter)
and runs under a bare interpreter with no venv, measured.

**A dead launcher is silent, so something else has to say so.** A hook
whose `command` does not resolve produces nothing at all -- no error to the
model, nothing in a log (see [the trials](#what-is-measured-and-what-is-merely-documented)).
`session_start_hook.py` cannot cover that alone, being launched by the same
name; `python -m chitragupta.draft gate` prints the same warning from an
interpreter that has demonstrably started. Both call
`chitragupta/hook_launchers.py`.

**What does not transfer.** `obra/superpowers` solves the adjacent
problem -- bash being absent, rather than a variable being unexpanded --
with a polyglot `run-hook.cmd`. That file is simultaneously a valid batch
file and a valid shell script, so `cmd.exe` runs the batch half and finds
Git Bash, while `bash` reads the batch half as a no-op heredoc.

It is a good trick, and it is **incompatible with exec form**, which is
what this repository needs: a shebang-less polyglot invoked through
`execve` fails outright. The two fixes are alternatives, not layers.

One narrower thing does transfer, as a caution rather than a change: that
file's scripts are deliberately *extensionless* because Claude Code's
Windows auto-detection prepends `bash` to any command containing `.sh`.
The hooks here are `.py` and unaffected -- recorded so that nobody renames
them defensively on the strength of that comment.

## The output contract

**Stdout is one JSON document, or nothing at all.** This is the rule most
often broken by accident and the one whose breach is hardest to see. A
single stray `print()` ahead of the JSON makes stdout unparseable, after
which the entire payload is discarded in silence -- the hook still exits 0,
still looks installed, and reports nothing for the rest of its life. It was
measured here, not theorised; `addyosmani/agent-skills` carries the same
warning in its own hook header, that hosts which validate hook output
reject any other shape.

**The advisory channel is `hookSpecificOutput.additionalContext`, and only
that.** Plain stdout on exit 0 goes to the debug log and does not reach the
model. Both facts are measured; see the next section.

**An advisory hook never emits a blocking decision.** For the gate that
shape is `{"decision": "block", "reason": ...}` on stdout, printed by
`citation_gate_hook.py`. For everything else it is forbidden twice over --
once because #183 says conformance may not block, and once because a hook
that prints anything other than its own single JSON object has already
destroyed its own delivery.

**Fail open on malformed stdin.** Three shapes, all of which have been hit:
invalid JSON, valid JSON that is not an object, and a `tool_input` that is
not a dict. Each means *no file path was given*, and each must return 0
rather than raise.

**Use `sys.executable` for any subprocess**, never a bare `python` or
`python3`. The reasoning is in `citation_gate_hook.py`'s comment: an
interpreter name that fails to resolve raises `FileNotFoundError`, which
exits non-zero *without* the block, so the draft lands ungated. A hard gate
that degrades to advisory depending on which interpreter aliases a host
happens to have is the worst of the available failure modes.

This does not contradict [the launcher](#the-launcher-contract), which is
a bare `python` by decision. The difference is what each process has to
inherit from: a hook already running *is* an interpreter, so naming it
again is a needless second chance to fail, while the launcher has nothing
to inherit and a name is the only thing `settings.json` can give the
harness. Resolve by name once, at the outermost edge, and never again.

**Emit only the field this host consumes.** A hook written for several
harnesses has to branch: Claude Code reads
`hookSpecificOutput.additionalContext`, Cursor reads a top-level
`additional_context`, and the SDK standard is a top-level
`additionalContext` -- and Claude Code reads more than one of them without
deduplicating, so emitting several delivers the payload twice. This
repository targets Claude Code and does not branch; the branch point is
recorded because it is not guessable from the field names.

## What is measured, and what is merely documented

Six trials, run against this repository's own gate hook with a throwaway
second entry beside it, on 2026-08-15. Recorded because two of the answers
are not in the documentation and one contradicts a reasonable reading of
it:

| Trial | Tool | Hook stdout | Outcome |
|---|---|---|---|
| 1 | `Write` | plain text **then** JSON | nothing arrived |
| 1a | `Edit` | JSON only | `additionalContext` arrived |
| 1b | `Edit` | plain text only | nothing arrived |
| 2 | `Edit` | JSON only, gate blocking in the same turn | **both** arrived |
| 3 | `Write` | JSON only | `additionalContext` arrived |
| 4 | `Write` | *never ran* -- `command` not on PATH | nothing arrived |

Trial 4 is #197's premise, and it was measured the same way rather than
assumed: a bogus launcher and a working control hook in one entry, one
`Write`, and the control's payload arrived while the bogus one produced
nothing whatever -- no error to the model, nothing findable under
`~/.claude/`. Whether the user's terminal shows something transiently is
*not* measured. That silence is why a dead launcher needs a reporter that
does not share its interpreter.

Each arrival reached the model as a system reminder reading
`PostToolUse:<Tool> hook additional context: <payload>`. A disk log in the
probe confirmed the hook fired in the first five, so the two nulls there
are delivery failures rather than invocation failures -- unlike trial 4,
where nothing was invoked at all and the outcome is identical from the
outside. That indistinguishability is the whole problem.

What that settles:

- The advisory channel works, on `Write` as well as `Edit`. Both matter:
  the genre skills save a draft with `Write`, and only the reviser skills
  reach it by `Edit`.
- Advisory output survives a co-firing blocking hook, in the same turn,
  with no special handling and no deferral.
- Two entries on one matcher both deliver, which is what makes a single
  dispatcher process unnecessary here.
- Mixing plain text with JSON on stdout destroys the payload.

Also observed incidentally: a `settings.json` hook change took effect
**mid-session**, with no restart.

Three further facts were measured the same way while building the
preflight, each before it was relied on:

- **Exec form works, and the harness substitutes the braced placeholder.**
  A probe hook launched as `{"command": "python3", "args":
  ["${CLAUDE_PROJECT_DIR}/…"]}` received the absolute path in `argv[1]`,
  and the citation gate converted to that form still returned its blocking
  decision on a fabricated citekey.
- **The gate is corpus-independent in both directions.** With no
  `ledger.sqlite` present at all, it exits 0 on a citation-free draft and
  non-zero on a fabricated citekey. That is what makes the preflight's
  liveness probe runnable before a first sync.
- **`python -m chitragupta.corpus ledger` exits 0 whether the corpus is synced or
  not**, and prints a different sentence for each of the two pre-sync
  states. It is read-only and takes no lock, so the preflight can call it
  at every session start without contending with anything.

### How much an advisory hook would actually say

The standing worry about a per-write check is noise. Measured rather than
argued, on the fifteen-chapter book in `content/backup/`: **123 findings
across sixteen files**, of which seventeen are §2 defect-marker
occurrences (`easy` fifteen times over six chapters, `clearly` twice) and
almost all the rest are acronym-expansion suggestions. A whole chapter's
report is a dozen lines. Two findings from that run are worth naming
because they are the kind a per-write hook exists to catch early: the book
records no `language:` anywhere, so its dialect went unchecked for its
whole life; and while all fifteen chapters read as en-GB, the table of
contents reads as en-US and writes `modeling` against the chapters'
`modelling` -- a disagreement no reader of a single file could see.

**Two things rest on measurement alone.** `additionalContext` is not
documented for `PostToolUse` specifically -- the documentation describes it
as a universal output field without confirming this event honours it. And
the gate's own top-level `{"decision": "block"}` on `PostToolUse` is
attested nowhere: the fullest decision-control tables available, in a
third-party survey rather than the official documentation, list top-level
`decision` for `Stop`, `SubagentStop` and `ConfigChange`, do not mention
`PostToolUse`, and record the equivalent `PreToolUse` pair as deprecated in
favour of `hookSpecificOutput.permissionDecision`. Trial 2 proves it works
today. `tests/test_citation_gate_hook.py` asserts only that the shape is
*emitted*; no test in this repository can assert that the harness *honours*
it. That is precisely what the session preflight would check live.

## Testing a hook

Hook tests live in `tests/`, run under pytest with the rest of the suite,
and **`.claude/hooks` is inside `[tool.coverage.run].source`**, so the same
100% line-and-branch bar applies to a hook as to anything under `chitragupta/`.
Given what these two files enforce, a lower bar for them than for the code
they call would be the wrong way round.

Getting there needs both halves of a deliberate split, because a hook is
run by the harness as `python <path>` and **a spawned process contributes
no coverage**:

| | subprocess tests | module tests |
|---|---|---|
| Files | `test_citation_gate_hook.py`, `test_session_start_hook.py` | `test_hook_modules.py` |
| Run the hook as | the harness does | an imported module |
| Prove | the stdin/stdout contract | every branch |
| Contribute coverage | no | yes |

Neither half is redundant: a refactor that broke the stdin envelope would
pass the module tests and fail the subprocess ones. The numbers behind
this, measured before the split existed: 22 passing subprocess tests left
`session_start_hook.py` at **0.00%**, while `citation_gate_hook.py` sat at
an accidental 76.74% -- accidental because it depended on which tests
happened to inherit pytest-cov's subprocess bootstrap rather than strip it,
so it measured the test harness and not the hook.

**Instrumenting the children instead is ruled out, on the record.**
`tests/test_citation_gate_hook.py`'s `_IS_COVERAGE_BOOTSTRAP` documents
what happens: coverage started in a child with a different working
directory records statement-only data while the parent records branch
data, and the run then dies at combine time *after* every test has passed.
Importing the module avoids the problem rather than fighting it.

One consequence worth knowing before it surprises someone: the scope is
declared once, in `[tool.coverage.run].source`, and the suite is run with a
bare `--cov` rather than `--cov=src --cov=scripts`. A command line naming
the paths would silently keep measuring the old set after a new one is
added.

The tests worth having are the negative ones:

- a write outside `content/drafts/` is ignored;
- a write with a non-gated suffix is ignored;
- each of the three malformed-stdin shapes exits 0;
- a checker crash still exits 0;
- for an advisory hook, a findings payload never emits a blocking decision;
- **stdout parses as JSON**, because that failure is otherwise invisible;
- every shape a settings file can arrive in. This one is worth spelling
  out, because it is the failure the preflight is least able to report: a
  raise anywhere in reading that file reaches the catch-all that keeps a
  broken preflight from breaking a session, so the *whole* report goes
  silent -- the corpus stage and the gate check with it -- over a settings
  file it merely found odd. Five shapes did exactly that before they were
  fixed: a `hooks` key that was a string, an event holding a mapping
  instead of a list, an entry or hook that was a bare string, a
  whitespace-only `command`, and an `args` element that was not a string.

Two limits to state plainly rather than paper over. First, **no test can
start a hook the way the harness does**, so a hook that never spawns still
passes every test in the repository. `tests/test_settings_launchers.py`
narrows that gap without closing it: it is the one test that reads the
*live* `.claude/settings.json`, and it asserts of every entry -- so the
prose check's entry inherited the contract without a line being added here
-- that the entry is exec form, launches `python`, braces every
placeholder, and names a script that exists. What it cannot assert is that
the harness ran any of it. The other hook tests still
write a settings file into a throwaway root, which is how they check the
rule rather than this repository's current answer to it. Second, hook tests
that live outside the normal suite rot: one upstream collection ships a
hook test asserting fields (`priority`, `message`) that its own hook no
longer emits. Keeping these in pytest, where CI runs them, is the whole
defence.

## Deliberately not done

**A dispatcher process.** Consolidating every `PostToolUse` check into one
process, with per-check controls inside it, is tidier and is what
`affaan-m/ECC` does. Rejected here because it trades fault isolation for a
merge problem the harness has already solved.

**`async: true` on the style hook.** Advisory findings that arrive after
the agent has moved on defeat their own purpose, and whether async output
reaches the model at all is unprobed. Available if a real pass proves the
synchronous cost unacceptable, and only then.

**Conditional spawning (`if`) on the gate.** `if` is reported to take
permission-rule syntax and to suppress the process spawn entirely when it
does not match, which would make it a genuine answer to #185's accepted
cost of re-checking a whole draft on every edit of it. That description
comes from a third-party survey of the settings schema rather than from
the official documentation, and has not been tested here. It is also
version-gated, and the
behaviour of an older harness meeting an unrecognised key is unknown --
skip the hook, or ignore the key? If it skips, that is a silently inert
gate, which is the one outcome this document exists to prevent. Advisory
hooks may use it. The gate may not. The in-script path check stays either
way.

**A `jq` dependency.** One upstream hook shells out to `jq` to build its
JSON and degrades to a warning when it is missing. Incompatible with the
stdlib-only posture `chitragupta/style_check.py` documents, and `jq` is not
reliably present here in any case. Python's `json` module builds the
envelope.

**A per-hook enable/disable config.** One upstream ships a thirty-one-key
config with a git-ignored local override, which is real ergonomics.
Rejected because the gate must not be individually disableable, and a
harness-level `disableAllHooks` already exists for anyone who genuinely
needs the escape hatch.

### A skill that runs the hook

Asked directly, and recorded because the answer differs for the two things
the question can mean.

**Invoking `style_check_hook.py` from a skill is an antipattern.** The hook
is a harness adapter: it exists to read a `PostToolUse` payload on stdin
and write a JSON envelope on stdout. A skill has no payload, so it would
have to fabricate one to satisfy the adapter and then parse the envelope
back out to recover what it wanted. That is the dependency arrow backwards.
The hook depends on `python -m chitragupta.draft style`; anything else that wants
the check calls that command directly. It would also couple every skill to
a harness output format this document describes as measured rather than
documented, and therefore liable to change.

**A generic skill wrapping `python -m chitragupta.draft style` is not an
antipattern in general, but is the wrong shape here**, for three reasons.
[GENRE.md](GENRE.md) already sets the precedent for shared invariants --
*"These are not per-skill choices. They are the same rules restated in
eight `SKILL.md` files, and a skill that broke one would be the bug"* --
and pins
them with a text scan over `.claude/skills/`, which is exactly what #186
proposes for this step. Skills are also matched on *user intent*, and
"another skill is midway through its own loop" is not user intent; routing
the step through one would make invocation discretionary again, which is
the thing #183 exists to end. And the step is a single deterministic
command, so wrapping it costs a tool call and a context load to save
nothing.

**The condition that would flip this:** if the step ever grows from one
command into a multi-step judgement loop -- read the findings, decide which
to act on, edit, re-check, log the attempt -- then it *is* a skill, and
`overlap-reviser` is the proof, since that is precisely its shape for
verbatim findings. Today the fix path for a prose finding already has a
home in `draft-reviser`'s copy-edit mode (#103), so the loop does not need
a second one.

## Prior art

Credited properly in [INSPIRATION.md](INSPIRATION.md); summarised here for
whoever is changing a hook and wants the sources.

- **`obra/superpowers`** -- the fail-silent contract for a context
  injection, the polyglot launcher (not adopted, see above), the
  extensionless-filename caution, and the observation that the advisory
  field name differs per host.
- **`addyosmani/agent-skills`** -- the standard-envelope rule stated in a
  hook header, and a hook test that checks the payload parses. Its `jq`
  dependency is not adopted.
- **`shanraisshan/claude-code-best-practice`** -- the most complete public
  survey of hook events, output fields, decision-control shapes and
  version-gated options; the source of this document's `if`, `async` and
  decision-control notes. Its enable/disable config is not adopted.
- **`affaan-m/ECC`** -- the dispatcher pattern, and the principle behind
  it: resolve paths inside the interpreter rather than in the shell. The
  principle is adopted via exec form; the dispatcher is not.

## Open questions

1. **Whether `python` really starts a hook on a bare Windows clone.**
   The name is [settled](#the-launcher-contract) and #197 is closed, but
   the Windows half of the reasoning is read off CPython's `venv` module
   and the harness documentation -- no Windows host without Git Bash was
   available to try it on. The Linux half is measured. If the answer there
   is ever *no*, the failure is at least audible now: `python -m chitragupta.draft
   gate` says so.
2. **Whether `{"decision": "block"}` on `PostToolUse` stays supported.**
   Measured working, documented nowhere. The preflight is the tripwire.
3. **Whether `async` output reaches the model.** One probe would settle it
   and none has been run.
4. **What an older harness does with an unrecognised `if` key.** Decides
   whether conditional spawning is safe for advisory hooks on every host or
   only on recent ones.
5. **Whether a session-start message is the right register for a fault.**
   The preflight reports once and cannot re-report: a user who runs
   `python -m chitragupta.corpus sync` two minutes later keeps stale advice in
   context for the rest of the session, which is why the message says so
   in its own last line. Whether that is good enough will only be answered
   by living with it.
