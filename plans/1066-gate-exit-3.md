# The gate's third answer: "I could not read the ledger"

Status: **designed, being built.** Written 2026-10-30, for
[issue 1066](https://github.com/prasadtalasila/chitragupta/issues/1066).

**Written for** whoever builds or reviews the fix. **It assumes**
`chitragupta/ledger.py`'s read side (#843: one read-only opener,
`read_connection`, and its two refusals `NoLedger` and `StaleLedger`).
**Not covered here:** healing a hot journal from a reader. That is
decided against below, not deferred.

## The problem

`draft gate` opens the ledger read-only. A hot rollback journal beside
it (left by any interrupted write, such as a killed `corpus sync`) has to
be rolled back before SQLite answers even `PRAGMA user_version`, and a
read-only handle cannot roll it back. The `sqlite3.OperationalError`
(`SQLITE_READONLY_ROLLBACK`) escapes `citation_gate.run`, and the
traceback exits 1, the code that means "at least one unresolved
citekey". A gate that compared nothing looks like a gate that refused.

A stale ledger is the quieter form of the same thing. `StaleLedger` is a
`NoLedger`, so the gate reads it as empty and reports every cited key as
"not found in ledger -- not sourced from bib sync", with exit 1, about
keys that may well be in it.

Every other reader of the ledger raises the same raw traceback on a hot
journal, a locked ledger or a damaged file.

## Decisions

1. **Exit 3 means "the gate could not read the ledger, so nothing was
   checked".** It is never a verdict. 2 stays "bad usage". Both a stale
   ledger and an unreadable one exit 3, before any file is checked, so
   one rule holds with no exception for citation-free drafts. A
   *missing* ledger is unchanged: it fails closed (exit 1 on a cited
   key, 0 on a citation-free draft), because there every key really is
   unsourced, and the session-start probe and `docs/HOOKS.md` rely on
   it.
2. **One new refusal, `UnreadableLedger`, a `NoLedger` subclass.** It is
   "refused wherever `NoLedger` is", which is the precedent `StaleLedger`
   set. Every command boundary that already turns `NoLedger` into an
   `[error]` line and exit 1 (`draft`, `review`, `enrich`,
   `retrieval_cli`, `references`, `render`, `discover`, the overlap
   scope) then reports it cleanly with no change. That is the follow-up
   work the first proposal deferred, done here by construction rather
   than by fourteen edits.
3. **The places that read `NoLedger` as "empty, carry on" are audited
   one by one**, since a subclass reaches them too:
   - `citation_gate.run`: catches `StaleLedger` and `UnreadableLedger`
     first and exits 3.
   - `overlap_index_ledger`: already re-raises `StaleLedger` so the
     verbatim check cannot pass silently against a corpus it never read;
     it re-raises `UnreadableLedger` for the same reason.
   - `ledger_cli` (`corpus ledger`): a missing or stale ledger is a
     position in clone -> sync and exits 0. An unreadable one is a
     fault, and exits 3 with the message on stderr.
   - `review/verbatim_check/_corpus` (a PDF path lookup that falls back
     to the parsed text) and `dossier` (which already swallows
     `sqlite3.Error` to skip the drift scan) degrade as they do today.
4. **The cause is diagnosed from `sqlite3.Error.sqlite_errorname`**
   (Python 3.11+, and the floor is 3.12), not from matching message
   text. Each cause has its own "what happened" and "what to do":
   hot journal, locked, not a database or damaged, cannot open, and a
   fallback quoting SQLite.
5. **Report, never heal.** Rolling back the journal writes to the user's
   data. The gate stays read-only, and the message sends the user to
   `corpus sync`, whose read-write open rolls the journal back. A test
   proves that, so the message is not a guess. A damaged file is moved
   aside, never deleted.
6. **The refusals move to `chitragupta/ledger_refusals.py`.** This is
   forced, not chosen: `ledger.py` is at 245 of 250 code lines, and the
   new class and its diagnosis do not fit. `ledger.py` re-exports all
   three, so `ledger.NoLedger` and friends keep working at every call
   site. That is the shape `ledger_upsert` and `ledger_paths` already use.
7. **The hooks learn the third answer.**
   - `citation_gate_hook` blocks on exit 3, as it must when nothing was
     checked, but says "could not read the ledger", not "fix the
     offending citekey(s)".
   - `session_start_hook`'s gate probe distinguishes "refused" (healthy),
     "accepted" (the existing alarm) and "could not run" (exit code and
     stderr tail). Its corpus stage reports an unreadable ledger as that,
     not as "no config file".
   - Both hooks run on bare python and do not import `chitragupta`, so
     each spells 3 as a named constant, and a test pins it to the
     package's.

## Steps, each with its check

| Step | Verified by |
| --- | --- |
| `ledger_refusals.py`: the three refusals, the diagnosis, `EXIT_UNREADABLE = 3`; `ledger.py` re-exports and raises `UnreadableLedger` from `read_connection` | a real hot journal (a child process killed mid-transaction) raises it with the journal named and leaves the ledger file byte-identical; locked, damaged and unopenable files each get their own cause |
| `corpus sync` clears the journal | the same fixture, then `ledger.connect()`: the interrupted write is rolled back and the journal is gone |
| `citation_gate.run` exits 3 | hot journal and stale ledger each give 3, stderr holds the message, and stdout holds no `FAIL` |
| `citation_gate_hook` | exit 3 blocks with the could-not-read wording, never "offending citekey" |
| `session_start_hook` | gate probe: refused / accepted / could not run; corpus stage: an unreadable ledger is reported as one |
| `ledger_cli`, `overlap_index_ledger` | exit 3 and re-raise respectively |
| every other reader | each ledger-reading CLI verb run against a hot-journal ledger prints the message and no `Traceback` |
| docs | `docs/CLI.md`'s gate and `corpus ledger` exit codes, `draft.py`'s module docstring, `docs/HOOKS.md` |
