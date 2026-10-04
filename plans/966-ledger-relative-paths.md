# 966: the ledger stores paths a relocated project can still read

Status: **built**, closed by PR #1004 (6.132.1). Written 2026-10-04
against `main` @ 3486366; its three decisions were reviewed by the user
the same day. Closes #966, and with it the consolidated #963.

What changed on the way:

- `_parse_outputs_present` moved to Task 3, because sync would otherwise
  re-parse everything between Tasks 3 and 4.
- The PDF root is one function, `ledger_paths.pdf_root()`, which returns
  `BIB_FILE_PATH.resolve().parent`. `bib_reader` and the verbatim aid
  share it. A different spelling crashed sync on a symlinked bib file.
- `read_only_uri` uses `absolute()`, not `resolve()`. On Windows,
  `resolve()` turns a mapped drive into a UNC path. A UNC authority is
  rewritten to SQLite's empty-authority `file:////` form.
- Task 5's plain move test passes even with the writers reverted, because
  `connect()` normalises `parsed_path`. The schema scan and the
  legacy-upgrade test are what pin the writers.

**Written for** whoever implements #966, working task by task. An agent
can follow it with `superpowers:subagent-driven-development` or
`superpowers:executing-plans`; steps use `- [ ]` checkboxes.

**Assumed:** the worktree test environment from DEVELOPER-AGENTS.md
(`.venv-full/bin/python`, `config.toml` present), and familiarity with
issue 821's `config.confined_path`, which every reader below already
calls. Nothing here weakens it.

**Not covered here:**

- Caches *outside* the ledger that key on a path string:
  `overlap_index_doc._fingerprint_key` and `content/overlap/`. They are
  rebuildable caches rather than ledger columns, so a relocated project
  costs one rebuild, never a re-parse. Leave them alone unless a test
  below shows otherwise.
- `retrieval_cache` and `retrieval_passages_cache` key on the stored
  `parsed_path` string. That string changes from absolute to relative
  once, so each index rebuilds once after the upgrade. That is expected,
  not a regression.

## Goal

A project that is moved, has its content directory renamed, is opened
from a container and then from the host, or is reached through a
relative `CHITRAGUPTA_PROJECT` re-parses nothing and prints no issue-821
refusal. The read-only ledger URI also opens the right file whatever
characters its path contains.

## Architecture

The ledger stores no host-absolute path. `parsed_path` is stored
relative to `config.PARSED_DIR` (it is always `<citekey>.txt`), and
`pdf_path` relative to the bib file's directory, which is the root
`bib_reader` already confines it to. One new module,
`chitragupta/ledger_paths.py`, owns both directions. Writers call
`stored_*`, readers call `*_file`, and those return
`confined_path(root / value, root)`. A legacy absolute value still
collapses to itself under `root / value` (pathlib), so an un-moved old
ledger reads exactly as before. `ledger.connect()` rewrites legacy
`parsed_path` values to `citekey || '.txt'` on every writer open, which
is idempotent and costs one indexed scan. The read-only URI comes from
`Path.resolve().as_uri()`.

**Decisions, recorded so a reviewer can tell them from accidents:**

1. **Relative to `PARSED_DIR`, not `CONTENT_DIR`.** The issue allows
   either. `PARSED_DIR` is the root every reader already confines to,
   so the stored value is a bare file name and one root serves both
   storing and checking.

   This does not reach the Docling output the enrichment layer writes.
   Two Docling runs write files, and the ledger stores only one of them:

   | Who runs Docling | Writes | In the ledger? |
   | --- | --- | --- |
   | `corpus sync` with `[parser].backend = "docling"` | `content/parsed/<citekey>.txt` (Docling Markdown despite the suffix) and `<citekey>.passages.json` beside it | the `.txt` only, as `parsed_path`; `passages.sidecar_path` derives the sidecar from the citekey |
   | `enrich`'s Docling stage (`enrich/docling_parse.py`) | `content/docling/<citekey>.md`, `.passages.json`, `.figures.json`, `<citekey>_artifacts/` | no; every reader derives them as `config.DOCLING_DIR / citekey` |

   The enrichment layer's own cache (`content/docling_cache.json`) is
   keyed by citekey with the PDF's `(size, mtime_ns)`, and holds no
   path, so it already survives a move. Enrich touches the ledger's
   paths in one place: `enrich/corpus.py` hands `parsed_path` and
   `pdf_path` to `CorpusDoc.text_path`/`.pdf_path`. `_docling_reuse`
   then opens them directly (to adopt a sync-time Docling parse instead
   of parsing twice), and so does `embed_text.get_text` (its fallback
   when `content/docling/` has no `.md`). Task 4 routes `corpus.py`
   through the resolvers, which return absolute paths, so those
   consumers are unchanged. A test there pins the reuse.
2. **Normalise in `connect()`, not a `_MIGRATIONS` step.** A version
   bump would make every *reader* raise `StaleLedger` ("run sync") until
   one sync had run, and it would buy nothing: the resolver already
   reads legacy absolute values. `_MIGRATIONS` is ADD COLUMN-shaped and
   checked against `PRAGMA table_info`, so a data rewrite does not fit
   it.
3. **The value is derived from the citekey during normalisation**,
   which is what the issue proposes ("the filename is fully determined
   by the citekey"). `pdf_text.extract_text` writes
   `config.PARSED_DIR / f"{citekey}.txt"` (`chitragupta/pdf_text/__init__.py:267`)
   and nothing else. This turns a key into a file name the same way
   `pdf_text` already does. It never turns a file name back into a key,
   so SOUL.md's rule is not touched.
4. **`pdf_path` is not normalised in `connect()`.** `upsert_reference`
   rewrites it for every bib entry on every sync (both its INSERT and
   UPDATE write the column), and sync prunes rows that leave the bib.
   One sync therefore clears every legacy value.
5. **`ledger.py` is at exactly 250 code lines (C2).** `mark_parsed`
   moves to `ledger_paths.py` and is re-exported, following the
   `upsert_reference` precedent at `chitragupta/ledger.py:22-29`. That
   frees room for the new calls. If more room is needed, a larger
   refactor of `ledger.py` is in scope (the user agreed on 2026-10-04).
   Split it by responsibility, for example the read-only half
   (`NoLedger`, `StaleLedger`, `read_connection`, `reading`) into its
   own module behind the same re-export, rather than squeezing lines.

**Tech stack:** Python 3 stdlib (`pathlib`, `sqlite3`), pytest.

## Global constraints

- **The one rule:** no fabricated citekey. Test fixtures use the
  citekeys the existing fixtures use (`smith_example_2024`) or obvious
  synthetic ones in the `leaky2024` style that `test_path_confinement.py`
  uses. None of them reaches a draft.
- C2: every module under `chitragupta/` and `scripts/` stays at or below
  250 code lines. Check with `python3 scripts/code_standards.py <files>`.
- C1 and the rest: docs/CODE-STANDARDS.md.
- A path column in `items` is named `*_path`. The schema scan in Task 5
  relies on that name to find it.
- Stored relative values use `/` (`as_posix()`), so a ledger written on
  Windows reads on Linux and the other way round.
- Commit messages and the PR follow DEVELOPER-AGENTS.md (`merge_pr.py`
  commit-message fence, the version bump decided at PR time).

## Review focus

1. **A reader still opens the raw column.** A relative value opened
   as-is resolves against the process cwd and silently reads nothing.
   Task 4 lists every reader, and its grep step must show no
   `parsed_path`/`pdf_path` column value reaching `open`, `Path(...)`,
   `stat` or `read_text` except through `ledger_paths`.
2. **`discover/_overview.py` anchors at `PROJECT_ROOT`.** After this
   change, `PROJECT_ROOT / "x.txt"` lands outside `content/parsed/` and
   is refused. Task 4 replaces the anchoring, and the existing
   `test_path_confinement` case plus a new positive case pin it.
3. **The overlap layer hands `parsed_path` to code that opens it
   directly** (`overlap_index_doc._pages_from_parsed_text`,
   `overlap_source_text`). `overlap_index_ledger` must return the
   *resolved* path. Task 4 tests that.
4. **A hand-edited relative escape** (`../../secret.txt`) must still be
   refused with a warning. `confined_path` resolves `..`. A Task 3 test
   pins it.
5. **Upgrade then move in one step.** The old version wrote absolute
   paths, the project moves, and the new version syncs. The `connect()`
   normalisation must run before `_next_status` reads the old row.
   Task 5's legacy case pins it.

---

### Task 1: resolve `CHITRAGUPTA_PROJECT`

**Files:**

- Modify: `chitragupta/config.py:109-112` (`discover_project_root`)
- Test: `tests/test_config.py` (the `discover_project_root` class around line 880)

**Interfaces:**

- Produces: `discover_project_root(cwd=None, environ=None)` now returns
  an *absolute, resolved* path in every branch. A relative
  `CHITRAGUPTA_PROJECT` resolves against `cwd` when one is given, else
  against the process cwd.

- [ ] **Step 1: Write the failing tests**

```python
    def test_a_relative_env_var_resolves_against_the_cwd(self, tmp_path):
        """A relative CHITRAGUPTA_PROJECT names one directory, whichever
        cwd later code runs from (#966). Unresolved, every stored path
        derived from it depended on where the process started."""
        (tmp_path / "proj").mkdir()
        here = tmp_path / "elsewhere"
        here.mkdir()
        found = config.discover_project_root(
            cwd=here, environ={"CHITRAGUPTA_PROJECT": "../proj"}
        )
        assert found == (tmp_path / "proj").resolve()
        assert found.is_absolute()

    def test_a_relative_env_var_is_absolute_in_a_real_child(self, tmp_path):
        """The same, through a real import, as the issue reproduces it."""
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        other = tmp_path / "other"
        other.mkdir()
        result = run_python(
            "-c",
            "from chitragupta import config; print(config.PARSED_DIR)",
            cwd=other,
            env={**os.environ, "CHITRAGUPTA_PROJECT": "../proj"},
            capture_output=True,
            text=True,
            check=True,
        )
        assert Path(result.stdout.strip()) == proj.resolve() / "content" / "parsed"
```

Also change `test_explicit_env_var_wins` to assert `found == chosen.resolve()`,
because on macOS `tmp_path` sits behind the `/var` -> `/private/var` symlink.
Import `os`, `Path` and `run_python` (`from tests.conftest import run_python`)
if the file does not already.

- [ ] **Step 2: Run them, expect FAIL**

Run: `.venv-full/bin/python -m pytest tests/test_config.py -k "env_var" -v`
Expected: both new tests FAIL. The first returns `PosixPath('../proj')`,
and the second prints a relative path.

- [ ] **Step 3: Implement**

```python
    explicit = environ.get("CHITRAGUPTA_PROJECT")
    if explicit:
        # Resolved (#966): a relative value is relative to where the
        # user stood when they set it, and leaving it unresolved made
        # every path derived from PROJECT_ROOT depend on the cwd of
        # whichever process read it later.
        return ((Path.cwd() if cwd is None else Path(cwd)) / explicit).resolve()
```

Extend the docstring's step 1 to say that a relative value resolves
against `cwd`.

- [ ] **Step 4: Run them, expect PASS.** Run the whole of
  `tests/test_config.py` as well.

- [ ] **Step 5: Commit** with the subject
  `Resolve a relative CHITRAGUPTA_PROJECT against the cwd (#966)`

---

### Task 2: build every read-only sqlite URI with `as_uri()` (closes #963's row)

**Files:**

- Create: `chitragupta/ledger_paths.py` (it holds only `read_only_uri`
  in this task; Task 3 adds the rest)
- Modify: `chitragupta/ledger.py:226` (`read_connection`)
- Modify: `scripts/populate_bib_groups.py:66`. This script is standalone
  and imports no `chitragupta`, so inline the same expression there
- Modify: `bench/bench_drift.py:264`, and the docstring at `bench/bench_overlap.py:6`
- Test: `tests/test_ledger_read.py`, plus a new `tests/test_sqlite_uri_scan.py`

**Interfaces:**

- Produces: `ledger_paths.read_only_uri(path: Path) -> str`, returning
  `path.resolve().as_uri() + "?mode=ro"`

- [ ] **Step 1: Write the failing tests**

In `tests/test_ledger_read.py`:

```python
@pytest.mark.parametrize("dirname", ["q?dir", "h#sh", "pct%41", "a space", "ñandú"])
def test_read_connection_opens_the_named_file_read_only(isolated_config, monkeypatch, dirname):
    """#963: a raw `file:{path}?mode=ro` let `?` end the path early, so
    sqlite opened -- and created -- a prefix of it, dropped `mode=ro`,
    and reported the real ledger as stale."""
    parent = isolated_config.CONTENT_DIR.parent / dirname
    parent.mkdir()
    monkeypatch.setattr(config, "LEDGER_PATH", parent / "ledger.sqlite")
    monkeypatch.setattr(config, "CONTENT_DIR", parent)
    ledger.connect().close()
    before = sorted(p.name for p in parent.parent.iterdir())

    with ledger.reading() as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(ledger._MIGRATIONS)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            con.execute("DELETE FROM items")

    assert sorted(p.name for p in parent.parent.iterdir()) == before
```

`tests/test_sqlite_uri_scan.py`. The issue's class is "any `file:` URI
built without encoding", so the test scans for it:

```python
"""#963's class: a sqlite `file:` URI built by string formatting.

Nothing under chitragupta/, scripts/ or bench/ may build one: a path
holding `?`, `#` or `%` silently names a different file. Build it with
`Path.resolve().as_uri()` (chitragupta.ledger_paths.read_only_uri).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMATTED_URI = re.compile(r"""f["']file:""")


def test_no_file_uri_is_built_by_formatting():
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for top in ("chitragupta", "scripts", "bench")
        for path in sorted((ROOT / top).rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORMATTED_URI.search(line)
    ]
    assert offenders == []
```

- [ ] **Step 2: Run them, expect FAIL.** The `q?dir` and `h#sh` cases
  report `StaleLedger` or create a stray file, and the scan lists three
  offenders.

- [ ] **Step 3: Implement**

`chitragupta/ledger_paths.py`:

```python
"""How a path goes into the ledger and comes back out (#966, #963).

Every path this module hands sqlite, or reads back out of a ledger
column, crosses here, so the two rules hold in one place:

- a URI is built by `Path.as_uri()`, never by formatting. `?`, `#` and
  `%` are URI syntax, and a raw path holding one names a different
  file; and
- a stored path is relative to the root its readers confine it to,
  never host-absolute. A moved project, a renamed `content/`, or the
  same ledger read from a container and then from the host all name the
  file that is actually there.
"""

from __future__ import annotations

from pathlib import Path


def read_only_uri(path: Path) -> str:
    """`path` as a sqlite URI that opens it read-only and creates nothing.
    Resolved first: `as_uri()` accepts only an absolute path, and on
    Windows this yields the `file:///C:/...` form sqlite expects."""
    return path.resolve().as_uri() + "?mode=ro"
```

In `ledger.py`, add `from chitragupta import config, ledger_paths` (or a
separate import line, whichever keeps C2), then:

```python
    con = sqlite3.connect(ledger_paths.read_only_uri(config.LEDGER_PATH), uri=True, timeout=5.0)
```

In `scripts/populate_bib_groups.py` (add `from pathlib import Path`):

```python
    return sqlite3.connect(Path(sqlite_path).resolve().as_uri() + "?mode=ro", uri=True)
```

In `bench/bench_drift.py`, use `ledger_paths.read_only_uri(dest)`.
Reword `bench/bench_overlap.py:6` to "a read-only URI
(`ledger_paths.read_only_uri`)" so the scan no longer flags a docstring.

- [ ] **Step 4: Run them, expect PASS,** plus `tests/test_ledger*.py`
  and `python3 scripts/code_standards.py chitragupta/ledger.py chitragupta/ledger_paths.py`.
  If `ledger.py` goes over 250, do Task 3's `mark_parsed` move now.

- [ ] **Step 5: Commit** with the subject
  `Build every read-only sqlite URI with Path.as_uri() (#963, #966)`

---

### Task 3: store paths relative to their root, and normalise legacy rows

**Files:**

- Modify: `chitragupta/ledger_paths.py`
- Modify: `chitragupta/ledger.py`. Move `mark_parsed` (lines 252-256)
  out and re-export it. Call `ledger_paths.normalise_legacy(con)` in
  `connect()` after `_migrate(con)`, inside the same `BEGIN IMMEDIATE`
- Modify: `chitragupta/ledger_upsert.py:234` and `:269`. Write
  `ledger_paths.stored_pdf(ref.pdf_path)` instead of `ref.pdf_path`
- Test: `tests/test_ledger.py` (the `TestMarkParsed` class, and the
  assertion at line 661)

**Interfaces:**

- Produces, all in `chitragupta.ledger_paths`:
  - `stored(path: str | Path | None, root: Path) -> str | None`: the
    POSIX path of `path` relative to `root`, both resolved. Returns
    `None` for an empty value. Raises `ValueError` when `path` is
    outside `root`, because a writer handed an unconfined path is a bug
    and not data.
  - `stored_parsed(path) -> str | None` = `stored(path, config.PARSED_DIR)`
  - `stored_pdf(path) -> str | None` = `stored(path, config.BIB_FILE_PATH.parent)`
  - `resolved(value: str | None, root: Path) -> Path | None` =
    `config.confined_path(root / value, root)`, and `None` for an empty value
  - `parsed_file(value) -> Path | None` = `resolved(value, config.PARSED_DIR)`
  - `pdf_file(value) -> Path | None` = `resolved(value, config.BIB_FILE_PATH.parent)`
  - `mark_parsed(con, citekey: str, parsed_path: Path) -> None`, which
    stores `stored_parsed(parsed_path)`. `ledger.mark_parsed` is
    re-exported, so `sync.py:151` is unchanged
  - `normalise_legacy(con) -> None`

- [ ] **Step 1: Write the failing tests** (in `tests/test_ledger.py`)

```python
class TestStoredPaths:
    """#966: no column holds a host-absolute path."""

    def test_mark_parsed_stores_the_name_under_parsed(self, ledger_con, isolated_config):
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith_example_2024"))
        out = isolated_config.PARSED_DIR / "smith_example_2024.txt"
        ledger.mark_parsed(ledger_con, "smith_example_2024", out)
        (stored,) = ledger_con.execute("SELECT parsed_path FROM items").fetchone()
        assert stored == "smith_example_2024.txt"
        assert ledger_paths.parsed_file(stored) == out

    def test_pdf_path_is_stored_relative_to_the_bib_directory(self, ledger_con, isolated_config):
        pdf = isolated_config.BIB_FILE_PATH.parent / "pdfs" / "a.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF")
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith_example_2024", pdf_path=str(pdf)))
        (stored,) = ledger_con.execute("SELECT pdf_path FROM items").fetchone()
        assert stored == "pdfs/a.pdf"
        assert ledger_paths.pdf_file(stored) == pdf

    def test_a_legacy_absolute_value_still_reads_in_place(self, isolated_config):
        out = isolated_config.PARSED_DIR / "k.txt"
        assert ledger_paths.parsed_file(str(out)) == out

    def test_a_relative_escape_is_refused_loudly(self, isolated_config, capsys):
        assert ledger_paths.parsed_file("../../secret.txt") is None
        assert "WARNING refusing" in capsys.readouterr().err

    def test_storing_a_path_outside_the_root_is_a_bug(self, isolated_config, tmp_path_factory):
        with pytest.raises(ValueError):
            ledger_paths.stored_parsed(tmp_path_factory.mktemp("x") / "k.txt")

    def test_connect_rewrites_legacy_absolute_parsed_paths(self, isolated_config):
        con = ledger.connect()
        con.execute(
            "INSERT INTO items (citekey, status, parsed_path, last_synced) "
            "VALUES ('smith_example_2024', 'parsed', '/old/host/content/parsed/smith_example_2024.txt', 'x')"
        )
        con.commit()
        con.close()
        con = ledger.connect()
        try:
            (stored,) = con.execute("SELECT parsed_path FROM items").fetchone()
        finally:
            con.close()
        assert stored == "smith_example_2024.txt"
```

Change line 661's `assert parsed_path == str(out)` to
`assert parsed_path == out.name`. Import `ledger_paths` and
`make_reference` (`from tests.conftest import make_reference`) if they
are missing. Check that the `ledger_con` fixture builds on
`isolated_config`, and if it does not, have these tests request both.

- [ ] **Step 2: Run them, expect FAIL** (`AttributeError: ledger_paths has no ...`,
  then absolute values stored)

- [ ] **Step 3: Implement.** Append to `chitragupta/ledger_paths.py`:

```python
import sqlite3

from chitragupta import config


def stored(path: "str | Path | None", root: Path) -> "str | None":
    """`path` as this ledger stores it: relative to `root`, `/`-separated."""
    if not path:
        return None
    return Path(path).resolve().relative_to(root.resolve()).as_posix()


def resolved(value: "str | None", root: Path) -> "Path | None":
    """A stored value as a path a reader may open, or `None`.

    `root / value` is the whole of the anchoring: a legacy absolute value
    collapses to itself (pathlib), so a ledger an older release wrote
    still reads in place, and `confined_path` refuses -- loudly -- one
    that lands outside `root`, `..` included (issue 821)."""
    if not value:
        return None
    return config.confined_path(root / value, root)


def stored_parsed(path):
    return stored(path, config.PARSED_DIR)


def stored_pdf(path):
    return stored(path, config.BIB_FILE_PATH.parent)


def parsed_file(value):
    return resolved(value, config.PARSED_DIR)


def pdf_file(value):
    return resolved(value, config.BIB_FILE_PATH.parent)


def mark_parsed(con: sqlite3.Connection, citekey: str, parsed_path: Path) -> None:
    con.execute(
        "UPDATE items SET status = 'parsed', parsed_path = ?, parse_error = NULL WHERE citekey = ?",
        (stored_parsed(parsed_path), citekey),
    )
    con.commit()


# The file a parse writes is fully determined by its citekey
# (pdf_text.extract_text), so a legacy host-absolute value is rewritten
# to that name whatever host it named. Idempotent: once every row is
# relative, the WHERE matches nothing.
_NORMALISE_PARSED = (
    "UPDATE items SET parsed_path = citekey || '.txt' "
    "WHERE parsed_path IS NOT NULL AND parsed_path <> citekey || '.txt'"
)


def normalise_legacy(con: sqlite3.Connection) -> None:
    """Rewrite what an older release stored host-absolute (#966)."""
    con.execute(_NORMALISE_PARSED)
```

The original has no docstring and commits after the UPDATE, as the
code above does; keep that commit, because `sync._record_result`
relies on it. Give the four
one-line wrappers type hints and one-line docstrings, as the C1 rules
require. In `ledger.py`, replace the function with a re-export beside
the `upsert_reference` one:

```python
from chitragupta.ledger_paths import mark_parsed  # noqa: F401  # pylint: disable=unused-import
```

In `connect()`:

```python
        con.execute(_SCHEMA)
        _migrate(con)
        ledger_paths.normalise_legacy(con)
```

Add a comment above `_SCHEMA`: a column holding a path is named `*_path`
and is stored through `ledger_paths`, and
`tests/test_ledger_relocation.py` scans for both.

- [ ] **Step 4: Run** `tests/test_ledger.py tests/test_sync.py tests/test_ledger_upsert*.py`,
  expect PASS, and fix the tests that asserted absolute stored values.
  Also run `python3 scripts/code_standards.py` over `ledger.py`,
  `ledger_paths.py` and `ledger_upsert.py`.

- [ ] **Step 5: Commit** with the subject
  `Store ledger paths relative to their root, never host-absolute (#966)`

---

### Task 4: route every reader through `ledger_paths`

After Task 3, some rows are relative, and any reader that opens the raw
value now reads nothing. This task is the one most likely to leave a
hole.

**Files (every reader found on `main` @ 3486366):**

| Site | Today | Becomes |
| --- | --- | --- |
| `chitragupta/ledger_upsert.py:160` (`_parse_outputs_present`) | `config.confined_path(parsed_path, config.PARSED_DIR)` | `ledger_paths.parsed_file(parsed_path)` |
| `chitragupta/retrieval.py:294` (`_full_text`) | same | same |
| `chitragupta/retrieval_cache.py:77` | same | same |
| `chitragupta/tldr.py:93` | same | same |
| `chitragupta/passages.py:271-272` | both confined calls | `parsed_file(row[0])`, `pdf_file(row[1])` |
| `chitragupta/enrich/corpus.py:65-67` | `_confined(...)` for both | `str()` of `parsed_file` / `pdf_file`, or `None`; delete `_confined` |
| `chitragupta/overlap_index_ledger.py:42,65-67,90` | confined check, then **returns the raw value** | resolve once and return `str(resolved)`, so `overlap_index_doc`, `overlap_skipgram`, `overlap_source_text` and `review/verbatim_check/_overlap.py` open a real path |
| `chitragupta/discover/_overview.py:49-50` | `config.PROJECT_ROOT / parsed_path`, then confined | `ledger_paths.parsed_file(parsed_path)` (**the anchoring is now wrong**) |
| `bench/bench_drift.py:265-271` | `Path(parsed_path).stat()` | `ledger_paths.parsed_file(parsed_path)` |
| `chitragupta/_reference_cut.py:120` | `Path(parsed_path).stem` | unchanged: the stem of `x.txt` is the same as before |

Update each site's comment as you go. The issue-821 rationale stays,
and gains "relative to the root (#966)".

**Interfaces:**

- Consumes: `ledger_paths.parsed_file`, `ledger_paths.pdf_file` (Task 3)
- Produces: `overlap_index_ledger.ledger_item` and `_ledger_items` now
  return an absolute, confined `parsed_path` string

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_path_confinement.py`,
  reusing its `insert` helper. Here a positive case matters as much as
  a refusal, because a relative value that reads nothing would pass
  every existing refusal test.

```python
RELATIVE_TEXT = "the relocated corpus text"


@pytest.fixture
def relative_row(isolated_config):
    """A row as #966 writes it: names relative to their roots."""
    isolated_config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    (isolated_config.PARSED_DIR / "rel2024.txt").write_text(RELATIVE_TEXT, encoding="utf-8")
    with ledger.connection() as con:
        insert(con, "rel2024", parsed_path="rel2024.txt")
    return isolated_config


class TestRelativeRowsAreRead:
    """Every reader must find the file a relative row names (#966).
    Opened raw, `rel2024.txt` resolves against the process cwd."""

    def test_overview(self, relative_row, monkeypatch, tmp_path_factory):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        assert _overview._parsed_texts(["rel2024"]) == {"rel2024": RELATIVE_TEXT}

    def test_overlap_ledger_returns_an_openable_path(self, relative_row, monkeypatch, tmp_path_factory):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        _hash, path = overlap_index_ledger.ledger_item("rel2024")
        assert Path(path).read_text(encoding="utf-8") == RELATIVE_TEXT

    def test_outputs_present(self, relative_row, monkeypatch, tmp_path_factory):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        assert ledger_upsert._parse_outputs_present("rel2024", "rel2024.txt")

    def test_tldr_fingerprint(self, relative_row, monkeypatch, tmp_path_factory):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        with ledger.reading() as con:
            assert tldr._fingerprint(con, "rel2024")
```

Use the real function names in `retrieval.py:280-300`,
`passages.py:260-295` and `enrich/corpus.py`, and add one positive case
for each in the same shape: `chdir` away, then assert the text is read.
For `passages`, also insert `pdf_path="paper.pdf"` with a file at
`BIB_FILE_PATH.parent / "paper.pdf"`, and assert
`enrich_corpus.build_corpus()` returns that absolute path.

The enrichment layer adopts a sync-time Docling parse through these
same two fields. A relative value would make it parse every document a
second time, about 6.65 s per PDF, without saying so. Pin that:

```python
    def test_enrich_reuses_a_relative_corpus_parse(self, relative_row, monkeypatch, tmp_path_factory):
        """`_docling_reuse` opens `CorpusDoc.text_path` and stats
        `.pdf_path` directly, so both must come back absolute (#966)."""
        from chitragupta.enrich import _docling_reuse

        pdf = relative_row.BIB_FILE_PATH.parent / "rel2024.pdf"
        pdf.write_bytes(b"%PDF")
        os.utime(pdf, ns=(1, 1))  # older than the parse, so reuse is allowed
        with ledger.connection() as con:
            con.execute("UPDATE items SET pdf_path = 'rel2024.pdf' WHERE citekey = 'rel2024'")
            con.commit()
        passages.sidecar_path("rel2024").write_text("[]", encoding="utf-8")
        monkeypatch.setattr(config, "DOCLING_IMAGES", False)
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))

        (doc,) = [d for d in enrich_corpus.build_corpus() if d.citekey == "rel2024"]
        assert Path(doc.text_path).is_absolute() and Path(doc.pdf_path).is_absolute()
        assert _docling_reuse._corpus_parse_available(doc)
```

Add `import os` to the test file if it is missing.

- [ ] **Step 2: Run them, expect FAIL.** `_overview` refuses
  `PROJECT_ROOT/rel2024.txt`, and the overlap path does not open.

- [ ] **Step 3: Implement** the table above.

- [ ] **Step 4: Grep for holes.** These must show only `ledger_paths`
  calls or code that does not open the value:

```bash
grep -rn "parsed_path\|pdf_path" --include=*.py chitragupta bench | grep -n "confined_path\|Path(\|PROJECT_ROOT\|\.stat()\|open("
```

Then run the whole suite:
`.venv-full/bin/python -m pytest -x -q`.

- [ ] **Step 5: Commit** `Read every ledger path through ledger_paths (#966)`

---

### Task 5: the class tests (relocation, legacy upgrade, schema scan)

**Files:**

- Create: `tests/test_ledger_relocation.py`

**Interfaces:**

- Consumes: `sync.run()`, `ledger.connect()`, `pdf_text.extract_text`
  (monkeypatched), the `isolated_config` fixture

- [ ] **Step 1: Write the tests**

```python
"""#966: a ledger survives its project moving.

Moved directory, renamed content dir, a container path then the host
path: all the same case. The stored paths must not name the host, so
the second sync re-parses nothing and refuses nothing. The schema scan
is the class test: every `*_path` column, including one added later.
"""

import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from chitragupta import config, ledger, pdf_text, sync

BIB = """
@article{smith_example_2024,
  title = {An Example Paper},
  author = {Smith, Jane},
  year = {2024},
  file = {paper.pdf:paper.pdf:application/pdf},
}
"""


def point_at(monkeypatch, root: Path, content: str = "content") -> None:
    """Every path sync reads or writes, under `root`."""
    monkeypatch.setattr(config, "CONTENT_DIR", root / content)
    monkeypatch.setattr(config, "PARSED_DIR", root / content / "parsed")
    monkeypatch.setattr(config, "LEDGER_PATH", root / content / "ledger.sqlite")
    monkeypatch.setattr(config, "BIB_FILE_PATH", root / "papers" / "bibliography.bib")


@pytest.fixture
def parses(isolated_config, monkeypatch):
    """The citekeys sync actually parsed, in order."""
    seen = []
    monkeypatch.setattr(pdf_text, "is_available", lambda: True)

    def fake_extract_text(pdf_path, citekey, *_args):
        seen.append(citekey)
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        out = config.PARSED_DIR / f"{citekey}.txt"
        out.write_text(f"text of {citekey}", encoding="utf-8")
        return out

    monkeypatch.setattr(pdf_text, "extract_text", fake_extract_text)
    return seen


def make_project(root: Path) -> None:
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "bibliography.bib").write_text(BIB, encoding="utf-8")
    (root / "papers" / "paper.pdf").write_bytes(b"%PDF-1.4 content")


def absolute_path_values(con) -> list:
    columns = [row[1] for row in con.execute("PRAGMA table_info(items)") if row[1].endswith("_path")]
    assert {"parsed_path", "pdf_path"} <= set(columns)
    return [
        (column, value)
        for column in columns
        for (value,) in con.execute(f"SELECT {column} FROM items WHERE {column} IS NOT NULL")
        if PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive
    ]


@pytest.mark.parametrize(
    "relocate",
    [
        pytest.param(lambda tmp, mp: (shutil.move(tmp / "a", tmp / "b"), point_at(mp, tmp / "b")), id="moved"),
        pytest.param(
            lambda tmp, mp: ((tmp / "a" / "content").rename(tmp / "a" / "corpus"), point_at(mp, tmp / "a", "corpus")),
            id="content-renamed",
        ),
    ],
)
def test_a_relocated_project_reparses_nothing(tmp_path, monkeypatch, parses, capsys, relocate):
    make_project(tmp_path / "a")
    point_at(monkeypatch, tmp_path / "a")
    assert sync.run() == 0
    assert parses == ["smith_example_2024"]

    relocate(tmp_path, monkeypatch)
    parses.clear()
    capsys.readouterr()
    assert sync.run() == 0
    out = capsys.readouterr()
    assert parses == []
    assert "WARNING refusing" not in out.err + out.out


def test_a_legacy_absolute_ledger_survives_upgrade_and_move(tmp_path, monkeypatch, parses, capsys):
    """An older release wrote host-absolute paths. Upgrade and move in
    one step, and the next sync must still re-parse nothing."""
    make_project(tmp_path / "a")
    point_at(monkeypatch, tmp_path / "a")
    sync.run()
    with ledger.connection() as con:
        con.execute(
            "UPDATE items SET parsed_path = ?, pdf_path = ?",
            (str(config.PARSED_DIR / "smith_example_2024.txt"), str(tmp_path / "a" / "papers" / "paper.pdf")),
        )
        con.commit()

    shutil.move(tmp_path / "a", tmp_path / "b")
    point_at(monkeypatch, tmp_path / "b")
    parses.clear()
    capsys.readouterr()
    assert sync.run() == 0
    assert parses == []
    assert "WARNING refusing" not in capsys.readouterr().err
    with ledger.connection() as con:
        assert absolute_path_values(con) == []


def test_no_ledger_column_stores_an_absolute_path(tmp_path, monkeypatch, parses):
    make_project(tmp_path / "a")
    point_at(monkeypatch, tmp_path / "a")
    sync.run()
    with ledger.connection() as con:
        assert absolute_path_values(con) == []
```

Before running: check `sync.run()`'s real call signature for
`extract_text` (`tests/test_sync.py:88` passes `(pdf_path, citekey)`)
and its return code on a clean run. In the legacy test,
`ledger.connection()` runs `connect()`, and so the normalisation,
*before* the UPDATE writes absolute values back. The move-then-sync
therefore really does start from an old release's ledger.

- [ ] **Step 2: Run them against the branch, expect PASS.** Then confirm
  they would have caught the bug. Run them once with Task 3's writers
  reverted: make a WIP commit that has `mark_parsed` store
  `str(parsed_path)` again. Do not use `git stash`, because the stash
  stack is shared with other worktrees. Expect
  `test_a_relocated_project_reparses_nothing[moved]` to FAIL with one
  re-parse and a `WARNING refusing` line. Drop the WIP commit and
  record the outcome in the PR's test plan.

- [ ] **Step 3: Commit** with the subject
  `Test the class: a relocated ledger re-parses nothing (#966)`

---

### Task 6: documentation, checks, PR

**Files:**

- Modify: `docs/ARCHITECTURE.md:485`. Say that `parsed_path` and
  `pdf_path` are stored relative to `content/parsed/` and to the bib
  file's directory, so the ledger stays byte-stable across hosts too
- Modify: `chitragupta/config_path.py:60-62`, the `confined_path`
  docstring, so it says that ledger values reach it through
  `ledger_paths`, anchored at their root
- Check `docs/` for any statement that `parsed_path` is absolute
  (`grep -rn "parsed_path" docs`), and for DOCKER/PACKAGING text about
  moving a project between the container and the host. Update what is
  now wrong
- Add a line at the top of this plan naming the PR that closed it

- [ ] Run every local check that DEVELOPER-AGENTS.md's "Before claiming
  a task complete" lists (full pytest, pylint under 3.13, ruff,
  `scripts/code_standards.py`, markdownlint over `plans/**/*.md`)
- [ ] Decide the version bump per DEVELOPER-AGENTS.md "Versioning and
  releases"; it is a fix with no interface change. Write the PR's
  `## Commit message` fence and run `merge_pr.py --check`
- [ ] The PR body says `Closes #966` and notes that #963 is covered,
  and its test plan records Task 5 Step 2's against-`main` run
