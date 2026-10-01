# #893: an aid that raises during `agenda --baseline`'s refresh

Status: **closed by PR #916 (6.127.0).** Written 2026-10-01 against
`origin/main` at `12c58bf`. Closes #893, a follow-up to #837. Three
things changed on the way:

- **The version is MINOR, not PATCH**, as the user asked: the payloads
  gain new fields (`refresh_errors`, `sources.aids.<aid>.refresh_error`).
- **The ledger check is `_refresh.ledger_refusal`, not a function in
  `agenda/__init__.py`.** Putting it there took that module to 270 code
  lines, over the 250 cap. This split was forced, not chosen.
- **`agenda-reviser` got a rule for a raise**, from the follow-up
  discussion, not only a wording change. When an aid raises, it reverts
  the repair and runs the recheck once on the reverted draft. If the
  aid no longer raises, the edit caused it and stays reverted. If it
  still raises, the host caused it, and the attempt does not count.
  The skill also stops the pass on the ledger refusal's exit 1.

**Written for** whoever implements #893. **Assumed:** the
`DEVELOPER-AGENTS.md` shipping cycle (TDD, 100% line and branch coverage,
ruff, markdownlint, OCR review, version bump). **Not covered here:** what
any aid should do differently when it fails. Each aid keeps its own
failure behaviour; this plan changes only how `refresh_aids` records it.

**Why this is a plan and not just the issue:** it changes the agenda
payload, which `agenda-reviser` and the next run's `--baseline` both
read. The field names below are decisions, not accidents.

## What happens today (reproduced)

Run in a scratch project with `config.toml` and a one-claim draft, and
no `content/ledger.sqlite`:

| Invocation | Result |
| --- | --- |
| `python -m chitragupta.review agenda <d>` | exit 0, report filed. The bare mode degrades without a ledger |
| `python -m chitragupta.review agenda <d> --baseline <d>.agenda.json` | `[error] No ledger ... Run ... sync`, exit 1, no traceback |
| `chitragupta.review.agenda.main([... "--baseline", ...])` | **traceback**: `chitragupta.ledger.NoLedger` |

So, through the CLI, success criterion 2 already holds, but only by
accident. `review/__main__.py:main` catches `NoLedger` around
`run(args)`, and `provenance` happens to be first in `AID_NAMES`, so it
raises before any other aid has spent time. If the registry order
changes, a no-ledger run would spend up to a minute on the other aids
(`support` alone has a model-load floor of about 21 to 60 s) before it
refuses. Calling `agenda.main` directly, which is what tests and any
in-process driver do, gets the traceback.

Criterion 1 does not hold on any route. Any other exception (an
`OSError`, `sqlite3.Error`, or a bug in one aid) propagates out of
`refresh_aids`. The run then never files the agenda, and the
comparison is lost along with the seven aids that did refresh.

## Decision 1: refuse a missing or stale ledger once, before refreshing

In `agenda.run`, when `--baseline` is given, check the ledger right
after `_recheck.load_baseline` succeeds and **before** `--accept` and
`refresh_aids`. That way a refused run writes nothing.

- **The check is `ledger.read_connection()`, closed straight away**,
  not `LEDGER_PATH.exists()`. It raises `NoLedger` for a missing file
  and `StaleLedger` (a `NoLedger` subclass) for one that needs a
  migration, and the aids would refuse both of those eight times.
  `ledger.reading()` is the same opener as a context manager, so use
  it if that reads more cleanly.
- **On `NoLedger`, print `[error] {exc}` to stderr and return 1.** That
  is the same text and exit code `review/__main__.py` gives today, so
  nothing reading the CLI changes. Return the code from `run` instead
  of letting the exception escape, so `agenda.main` and the CLI behave
  the same way.
- **The bare mode is not touched.** It runs no aid and already degrades
  without a ledger (the dossier drift source reports
  `corpus_available: false`). Making it refuse would be a regression.
- **Ordering:** a bad baseline (exit 2) is still reported before a
  missing ledger (exit 1). A usage error is the caller's mistake and
  costs nothing to report; this keeps `run`'s docstring rule that "the
  baseline is loaded before anything is refreshed".

## Decision 2: catch `Exception` per aid, and keep the reason separate

In `refresh_aids`, wrap each `AIDS[aid][0].main(argv)` call:

```python
try:
    with contextlib.redirect_stdout(io.StringIO()):
        code = AIDS[aid][0].main(argv)
except Exception as exc:  # noqa: BLE001 -- see docstring: one aid must not sink the recheck
    errors[aid] = _one_line(exc)
    refreshed[aid] = False
    continue
```

- **`Exception`, not `BaseException`.** `KeyboardInterrupt` must still
  stop the run. So must `SystemExit`: `_aid_argv`'s docstring says a
  wrong argv shows up as argparse's `SystemExit(2)`, and that is a bug
  in this module, which should fail loudly rather than be filed as "not
  refreshed". Ruff's `BLE` rule is selected (`pyproject.toml`), so the
  `noqa` is required, and `RUF100` checks that it stays justified.
- **A raised aid is `False` whatever is on disk.** An aid that wrote
  its `.json` and then raised has not reported a result. Do not check
  the mtime in that case.
- **`_one_line(exc)` is `f"{type(exc).__name__}: {first line of str(exc)}"`**,
  or just the type name when the message is empty. `NoLedger`'s message
  is two lines, and the second one is the sync instruction, which
  Decision 1 already prints. One line is enough to put in a header.
  A per-aid fallback for `NoLedger` is still needed when the ledger
  disappears or goes stale mid-run, after the up-front check passed.
- **Also print the line to stderr**, as `[warn] <aid> raised during
  refresh: <line>`. No traceback. stdout stays clean under `--json`,
  which is the rule the existing stdout redirect is there for. Without
  this, a bug in an aid would show up only as a word in a report header.

### The return shape

`refresh_aids` returns `(refreshed, errors)`: the existing
`dict[str, bool | None]` unchanged, plus `dict[str, str]` for the aids
that raised. Two plain dicts, not a new dataclass: `collect`'s loop
gains one line, and every existing test reading the first dict keeps
passing.

### Where the reason goes

**Not in `AidSource.reason`.** That field already means "why this
`.json` could not be read", and `_render._aid_note` prints it as
`not run -- <reason>` when the source is unavailable. A raised aid
usually *has* a readable earlier `.json`, so reusing the field would
either be invisible or print "not run" for an aid that did run. Add a
new field instead:

| Where | Field | Value |
| --- | --- | --- |
| `_sources.AidSource` | `refresh_error: str \| None = None` | set by `collect` from `errors` |
| `AidSource.flags()` → filed payload's `sources.aids.<aid>` | `"refresh_error"` | the line, or `null` |
| `_render._aid_note` (report header) | | `**not refreshed** (raised: <line>; an earlier run's findings; not counted)` |
| recheck payload (stdout, `--json`) | `"refresh_errors": {aid: line}` | after `not_refreshed` |
| `format_recheck` (stdout, text) | | `not refreshed: provenance (raised: NoLedger: ...), support` |

**`not_refreshed` stays a list of aid names.** The issue says the aid
"appears in `not_refreshed` with its reason". Turning the list into
dicts would break `agenda-reviser` (SKILL.md, "Read `not_refreshed`
first", which branches on `verbatim` being in the list), `docs/AGENDA.md`
and `docs/CLI.md`, and a raised aid gets the same handling as one that
exited 1. So the aid goes into `not_refreshed` exactly as it does today,
and its reason goes in a parallel key. A reader that ignores the new key
loses nothing it had before. `_recheck.not_refreshed` does not change:
a baseline filed by an older release has no `refresh_error`, and absence
is not evidence of anything.

## Tests (in `tests/test_review_agenda.py`, using `aid_stubs`)

Give `_AidStub` a `raises: Exception | None` argument and raise it after
the optional write.

1. A stub raising `RuntimeError("boom\nmore")` → `refreshed[aid] is False`,
   `errors[aid] == "RuntimeError: boom"`, and every later aid is still
   called.
2. A stub that writes its `.json` and then raises → still `False`.
3. A stub raising with an empty message → `errors[aid] == "RuntimeError"`.
4. A stub raising `SystemExit(2)` and one raising `KeyboardInterrupt`
   → both propagate.
5. The `[warn]` line goes to stderr, and stdout stays valid JSON under
   `--json`.
6. `collect` → `AidSource.refresh_error` set; `flags()` carries it.
7. Header: the raised line is in the **not refreshed** note; an aid
   that is not refreshed but did not raise keeps today's wording.
8. Recheck payload has `refresh_errors`; text output names the reason;
   with no errors, the text is unchanged (extend
   `test_text_says_nothing_about_refreshing_when_every_aid_was`).
9. End to end through `agenda.main`, with a ledger present and one aid
   raising: exit 0, report filed, that aid in `not_refreshed`, its items
   in no group and in neither count.
10. No ledger (`isolated_config` without one): `agenda.main([...,
    "--baseline", ...])` returns 1, stderr has the sync instruction
    **once**, no stub was called, and neither the `.json` nor the
    acceptance record was rewritten. Repeat with a stale ledger
    (`user_version` 0).
11. No ledger, bad baseline → exit 2 (the ordering in Decision 1).
12. Bare mode with no ledger → still exit 0 (guards against making the
    bare mode refuse).

**The existing `--baseline` CLI tests will break, and should.** They
use `isolated_config` and `aid_stubs` with no ledger (only one test in
the file, near line 2970, takes `ledger_con`), so Decision 1 makes them
refuse. Add the existing `ledger_con` fixture to them, or wrap it in a
`baseline_ready` fixture. Do not add a way to skip the check.

## Docs

- `docs/AGENDA.md`, the "Read `not_refreshed`" paragraph: add a raised
  exception as a third kind of failed refresh, and name `refresh_errors`
  and `sources.aids.<aid>.refresh_error`. Say that `--baseline` refuses
  without a ledger and the bare mode does not.
- `docs/CLI.md` near line 1378: add `refresh_errors` to the payload's
  key list, and add the exit 1 for no ledger.
- `.claude/skills/agenda-reviser/SKILL.md`, "Read `not_refreshed`
  first": add "a raised exception, whose one-line reason is in
  `refresh_errors`" to the list of causes. The branching on which aid
  is listed does not change.
- Module docstrings: `_refresh.refresh_aids` (its three outcomes become
  four), `_sources.AidSource` (the new field and why it is not
  `reason`), and `agenda.run` (the ledger check's place in the
  ordering).

## Order of work

1. Tests 1–5, then `refresh_aids` and `_one_line`.
2. Tests 6–8, then `AidSource.refresh_error`, `collect`, `_render`,
   `_recheck.recheck_payload`/`format_recheck`, and `run`'s threading.
3. Tests 10–12 and any existing-test ledger setup, then Decision 1.
4. Test 9.
5. Docs, then the version bump, full suite and coverage, ruff,
   markdownlint, OCR.

## Out of scope

- Making any aid stop raising `NoLedger`. Since #843 that is the
  intended refusal; this plan only stops it taking down the recheck.
- Retrying a failed aid, or using a timeout for one that hangs.
- Showing the reason for a non-zero exit or an exit 0 that wrote
  nothing. Both are already `False`, and the aid's own stderr (which
  is not redirected) already says why.
