# cg-collections and citekey renames: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **built, not merged.** Written 2026-11-22. Covers #1211 and
supersedes #1109 (closed). Final review fixes and rulings are recorded in
the PR.

**Goal:** chitragupta reads collections from chitragupta-importer's
`cg-collections` field and name table instead of `groups`. Sync
detects a renamed citekey, records it and reports it. The drafting
layer can then swap the old key for the new one.

**Architecture:** the corpus layer (`bib_reader`, `ledger`, `sync`)
parses two `@comment` blocks and one entry field. It stores slug paths,
collection names and renames in the ledger, and never edits a draft.
The drafting layer (`dossier status`, a new `dossier apply-renames`,
draft-reviser's re-grounding) reads the ledger's `renames` table and
applies key-for-key swaps that the ledger has verified.

**Tech stack:** Python 3.12 to 3.14, bibtexparser `>=1.4,<2.0`,
sqlite3, pytest.

**Spec:** issue #1211, as amended by the decisions below (owner's
answers, 2026-11-21/22). Importer side:
chitragupta-importer `src/chitragupta_importer/bibtex.py` and
`docs/adr/0004`, `0006`, `0007`, `0008`.

## Decisions that amend #1211

| # | Decision |
| --- | --- |
| D1 | #1109 is closed as superseded. `scripts/populate_bib_groups.py`, `tests/test_populate_bib_groups.py` and `docs/EXPORT-ZOTERO-GROUPS.md` are deleted here |
| D2 | `groups` is no longer read. If any entry has `groups` and no entry has `cg-collections`, sync prints one WARNING line pointing at chitragupta-importer. The exit code is unchanged. `[bib] collections_field` / `BIB_COLLECTIONS_FIELD` is removed |
| D3 | A `--collection` value that names no known collection exits 2 and names `corpus ledger --collections`. A value containing `>` gets an extra line saying paths are now slug paths or `/` display paths. A follow-up issue ports old drafts (text in Appendix A) |
| D4 | A display path shared by two collections (siblings `medical`, `medical-1`) exits 2 and lists both slug paths |
| D5 | Name table, any version: split each row on tabs, read field 1 (slug path) and field 2 (name), ignore any further fields. A row whose field 1 is not a valid slug path is skipped with a warning. A version other than `v1` prints a WARNING and adds a bib-integrity problem, so sync exits 3 (`EXIT_BIB_INTEGRITY`) |
| D6 | Renames come from two sources: (a) `pdf_hash`, where a stale key's hash equals the hash of exactly one key still in the bib; (b) a `@comment{cg-renames v1 …}` block in the bib (`old<TAB>new` rows, read under D5's rules). (b) wins when both apply. An importer issue asks for (b) (Appendix B). chitragupta reads no importer lock file (ADR-0007 holds) |
| D7 | Sync records each 1:1 rename in a ledger `renames` table **before** any prune, and adds `renamed to <new>` to the stale line. A hash shared by several bib keys is reported (`same PDF as a, b`) and not recorded |
| D8 | `sync_residue` gains a `drafts` artefact: `content/drafts/**/*.md` and `**/*.tex`, exact bounded match, read only |
| D9 | The drafting layer applies renames. `dossier status` gains a `renamed` list. `dossier apply-renames <draft>` swaps every recorded rename in the draft, `evidence.md`, `sections.md` and `rejected.md`, then logs to `revisions.md`. A rename whose PDFs differ (`same_pdf = 0`) is listed for a quotation re-check. The command refuses a key the ledger has not recorded |
| D10 | One PR. Version bump to **7.0.0** (MAJOR): a config key removed without fallback and the `--collection` argument shape changed |

## Global constraints

- The one rule: no citekey is generated, guessed or rewritten except by
  `apply-renames` swapping in a key that is present in both the bib and
  the ledger, as recorded by sync. Test fixtures use invented
  placeholder keys that are already in this repo's fixture bibs, or
  are built inside the test.
- Corpus-layer code never writes outside `content/ledger.sqlite`.
  `sync_residue` stays read-only.
- Slug path regex: `^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)*$`.
- Block headers: `cg-collections v1` and `cg-renames v1`, the first line
  of an `@comment{…}` block. Name unescaping: `\{` → `{`, `\}` → `}`.
- Display path joiner on output: ` / `. Input comparison: casefold, strip,
  collapse whitespace around `/`; never split the input.
- `cg-collections` field: slug paths separated by a comma and a space.
  Ancestors are implied.
- Line and branch coverage stays at 100%. `markdownlint-cli2` and ruff
  stay clean.
- Skill files carry no issue or PR numbers. A skill edit is benched before
  merge (`skill-bench`, Claude Code, 3 before / 3 after).
- Do not touch `docs/WRITE-A-*.md`.
- In a `.claude/worktrees` checkout, `cp config.toml.example config.toml`
  before the full suite.

## Review focus

1. **A `config.toml` that still sets `[bib] collections_field`** loads
   without error. The key is ignored, with one deprecation line from
   `config`. Test in Task 2.
2. **A rename chain** (`a → b` in one sync, `b → c` later) resolves to
   `c` in `dossier status` and `apply-renames`. A cycle (`a → b → a`)
   stops and is reported, never looped. Test in Task 6.
3. **A rename that is later undone** (the old key returns to the bib)
   drops its `renames` row at the next sync. Test in Task 5.
4. **An old draft's `retrieval.md` collection** such as
   `Digital twins > Modelling`. `dossier status` reports it as
   `unresolved_collections` instead of filtering candidates down to
   nothing and saying the draft is clean. Test in Task 4.
5. **A table row whose slug path no entry uses** (a collection with no
   papers) is listed by `--collections` with count 0 and still resolves
   as a display path. Test in Task 1.

---

## File map

| File | Change |
| --- | --- |
| `chitragupta/bib_collections.py` | Rewrite internals for slug paths. Add the table parser, display paths, `resolve` and the errors |
| `chitragupta/bib_comments.py` | **New.** Splits `@comment` blocks into versioned tab tables (shared by both blocks) |
| `chitragupta/bib_reader.py` | Read the `cg-collections` field and both blocks into `Library`. Add the `groups` warning |
| `chitragupta/config.py` | Remove `BIB_COLLECTIONS_FIELD`. Add a deprecation line for the old key |
| `chitragupta/ledger.py` | Migration v5 adds tables `collection_names` and `renames` and nulls v4 `items.collections`. Add read/write helpers |
| `chitragupta/sync_renames.py` | **New.** Detects and records renames (corpus layer) |
| `chitragupta/sync_decide.py`, `chitragupta/sync.py` | Write the names table, then record renames before the stale report or prune |
| `chitragupta/sync_residue.py` | Add the `drafts` artefact |
| `chitragupta/ledger_cli.py`, `chitragupta/retrieval.py`, `chitragupta/retrieval_passages.py`, `chitragupta/retrieval_cli.py`, `chitragupta/retrieval_iterative.py`, `chitragupta/dossier/_retrieval.py`, `chitragupta/overlap_embed_scope.py` | Resolve `--collection` once. Refuse unknown or ambiguous values |
| `chitragupta/dossier/_drift.py`, `chitragupta/dossier/__init__.py` | Add the `renamed` and `unresolved_collections` lists |
| `chitragupta/dossier/_renames.py` + dossier CLI | **New** `apply-renames` subcommand |
| `.claude/skills-common/references/collection-scoping.md`, `.claude/skills/draft-reviser/references/re-grounding.md`, genre `SKILL.md` lines that mention `collection:` | Record slug paths. Add the renamed step |
| `docs/ZOTERO.md`, `docs/CLI.md`, `docs/CONFIG.md`, `docs/TECHNICAL-DEBT.md`, `mkdocs.yml`, `config.toml.example`, `docs/examples/{sample-project,opencode,codex}/config.toml` | Docs and config for the above |
| `scripts/populate_bib_groups.py`, `tests/test_populate_bib_groups.py`, `docs/EXPORT-ZOTERO-GROUPS.md` | Delete |
| `pyproject.toml` | `version = "7.0.0"` |

---

### Task 1: Slug paths, name table and resolution in `bib_collections`

**Files:**

- Modify: `chitragupta/bib_collections.py`
- Create: `chitragupta/bib_comments.py`
- Test: `tests/test_bib_collections.py` (rewrite), `tests/test_bib_comments.py`

**Interfaces:**

- Produces (`bib_comments`):
  - `TabTable(name: str, version: str, rows: list[tuple[str, str]],
    skipped: list[str])`, a dataclass
  - `read_tables(comments: list[str], name: str, valid_key:
    Callable[[str], bool]) -> TabTable | None`: finds the block whose
    first line is `<name> v<N>`, then splits each row on tabs (fields 1
    and 2, extra fields ignored). A row where `valid_key(field1)` is
    false, or that has fewer than 2 fields, goes to `skipped`. Returns
    None if there is no block. Two blocks of the same name: rows are
    merged and the first block wins on a duplicate key.
  - `KNOWN_VERSION = "v1"`
- Produces (`bib_collections`):
  - `is_slug_path(s: str) -> bool`
  - `parse(value: str | None) -> tuple[str, ...]`: the field's slug
    paths. Invalid ones are dropped. Order and dedup behave as they do
    today.
  - `display_paths(names: dict[str, str], paths: Iterable[str]) ->
    dict[str, str]`: every path plus its ancestors → `" / "`-joined
    names. A segment with no row shows its own slug segment.
  - `matches(collections, wanted_slug: str) -> bool`: `p == w or
    p.startswith(w + ".")`
  - `class UnknownCollection(ValueError)` with `.wanted` and
    `.old_syntax: bool`. `class AmbiguousCollection(ValueError)` with
    `.wanted` and `.slugs: list[str]`
  - `resolve(wanted: str, names: dict[str, str], paths: Iterable[str])
    -> str`: if `wanted.strip().casefold()` is a known slug path (from
    names keys ∪ paths ∪ their ancestors), return it. Otherwise compare
    against normalised display paths: one hit returns its slug, several
    raise `AmbiguousCollection`, none raise `UnknownCollection`.
  - `report(rows, names: dict[str, str]) -> list[str]`: one line per
    collection with three padded columns: slug path, display path,
    count. A count includes descendants. Table rows with no papers show
    `0`. The empty state is `No collections recorded.` plus a line
    naming chitragupta-importer.
  - `of_row` unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_reads_slug_paths_and_drops_invalid():
    assert parse("digital-twin.dt-platforms, a.b , Bad Path") == ("digital-twin.dt-platforms", "a.b")

def test_display_paths_any_depth():
    names = {"digital-twins": "Digital Twins", "digital-twins.platforms": "Platforms",
             "digital-twins.platforms.cloud": "Cloud", "digital-twins.platforms.cloud.public": "Public"}
    assert display_paths(names, ["digital-twins.platforms.cloud.public"])[
        "digital-twins.platforms.cloud.public"] == "Digital Twins / Platforms / Cloud / Public"

def test_display_path_missing_row_falls_back_to_segment():
    assert display_paths({"a": "A"}, ["a.b"])["a.b"] == "A / b"

def test_matches_is_subtree_per_segment():
    assert matches(("a.b.c",), "a.b") and not matches(("a.bc",), "a.b")

def test_resolve_slug_display_and_name_with_slash():
    names = {"net": "Networking", "net.tcp-ip": "TCP/IP"}
    assert resolve("net.tcp-ip", names, []) == "net.tcp-ip"
    assert resolve(" networking/TCP/IP ", names, []) == "net.tcp-ip"

def test_resolve_ambiguous_siblings_lists_both():
    names = {"u": "Use Cases", "u.medical": "Medical", "u.medical-1": "Medical"}
    with pytest.raises(AmbiguousCollection) as e:
        resolve("Use Cases/Medical", names, [])
    assert e.value.slugs == ["u.medical", "u.medical-1"]

def test_resolve_unknown_flags_old_syntax():
    with pytest.raises(UnknownCollection) as e:
        resolve("Digital twins > Modelling", {}, [])
    assert e.value.old_syntax is True

def test_report_counts_include_descendants_and_empty_rows():
    ...  # rows: k1 in a.b, k2 in a; names has an "a.c" row with no papers
    assert lines contain "a  ... 2", "a.b ... 1", "a.c ... 0"

def test_read_tables_tolerant_of_extra_fields_and_unknown_version():
    t = read_tables(["cg-collections v2\na\tA\tK7Q2\nBad Row\tX\n"], "cg-collections", is_slug_path)
    assert (t.version, t.rows, t.skipped) == ("v2", [("a", "A")], ["Bad Row\tX"])

def test_read_tables_unescapes_braces():
    ...  # "a\tSet \\{x\\}" -> ("a", "Set {x}")
```

- [ ] **Step 2: Run `.venv-full/bin/python -m pytest
      tests/test_bib_collections.py tests/test_bib_comments.py -q`.**
      Expected: FAIL (ImportError).
- [ ] **Step 3: Implement the interfaces above.** Rewrite the module
      docstring: Better BibTeX and `groups` are gone, and the importer's
      format is described with its D5 tolerance rule.
- [ ] **Step 4: Re-run.** Expected: PASS, with 100% coverage of both modules.
- [ ] **Step 5: Commit** `Read slug-path collections and the importer's
      name table`.

### Task 2: `bib_reader` reads the field, both blocks and the `groups` warning

**Files:**

- Modify: `chitragupta/bib_reader.py` (`Reference`, `Library`,
  `_reference`, `read_library`), `chitragupta/config.py:142-149`
- Test: `tests/test_bib_reader.py` (or the existing reader test module
  that owns `read_library`), `tests/test_config.py`

**Interfaces:**

- Consumes: Task 1's `parse`, `read_tables`, `is_slug_path`.
  `citekey_safety.citekey_problem` (a valid citekey is one where it
  returns `None`).
- Produces: new `Library` fields.
  - `collection_names: dict[str, str]`
  - `declared_renames: dict[str, str]`, from `cg-renames` (old → new,
    both citekey-safe)
  - `table_notes: list[str]`, the warning lines
  - `integrity_problems` gains `{"cg-collections table v<N> (this
    chitragupta reads v1)": 1}` and the same for `cg-renames` when the
    version is not `v1`.
- `Reference.collections` comes from the field `cg-collections` (a
  constant `COLLECTIONS_FIELD = "cg-collections"` in `bib_reader`).

- [ ] **Step 1: Write the failing tests.**
  - `test_read_library_reads_cg_collections_and_names`: a fixture bib
    holding the importer's real shape (the table, then `@incollection`
    with `cg-collections = {a.b, c}`). Asserts `refs[0].collections ==
    ("a.b", "c")` and `library.collection_names["a.b"] == "B"`.
  - `test_unknown_table_version_is_integrity_problem`: the `v2` table
    still yields names, and `integrity_problems` has the v2 key.
  - `test_groups_without_cg_collections_warns_once`: captured output has
    exactly one line containing `chitragupta-importer`, and
    `integrity_problems` is unchanged.
  - `test_cg_renames_block_read_and_unsafe_keys_skipped`.
  - `test_old_collections_field_config_key_is_ignored` (Review focus 1):
    it writes a config with `[bib] collections_field = "groups"`, loads
    config without error, and finds the one deprecation line.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Read comment blocks from bibtexparser 1.x's
      `BibDatabase.comments`. Pass `table_notes` to
      `sync_report._preflight_warnings` so they print with the other
      warnings. Delete `BIB_COLLECTIONS_FIELD` and add the deprecation
      line where `config` reads `[bib]`.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** `Read cg-collections and cg-renames from the
      bibliography`.

### Task 3: Ledger migration v5 and storing names

**Files:**

- Modify: `chitragupta/ledger.py` (`_MIGRATIONS`, `_migrate`, new
  helpers), `chitragupta/sync.py` / `chitragupta/sync_decide.py` (write
  names after ingest)
- Test: `tests/test_ledger.py`, `tests/test_sync*.py` (whichever owns
  migration and run tests)

**Interfaces:**

- Produces:
  - Table `collection_names(slug_path TEXT PRIMARY KEY, name TEXT NOT NULL)`
  - Table `renames(old TEXT PRIMARY KEY, new TEXT NOT NULL, source TEXT
    NOT NULL CHECK (source IN ('pdf_hash','cg-renames')), same_pdf
    INTEGER NOT NULL, seen_at TEXT NOT NULL)`
  - `ledger.replace_collection_names(con, names: dict[str, str]) ->
    None`, which deletes all rows and inserts the new ones
  - `ledger.collection_names(con) -> dict[str, str]`, which returns `{}`
    when the table is absent (a read-only connection to a v4 ledger)
  - `ledger.renames(con) -> dict[str, tuple[str, str, bool]]` (old →
    (new, source, same_pdf)), also `{}` when the table is absent
- The v5 step: run `_migrate` steps whose key is not an `items` column
  (the two `CREATE TABLE IF NOT EXISTS` statements and `UPDATE items SET
  collections = NULL`) exactly once, on the v4 → v5 move. Today
  `_migrate` only guards `ALTER TABLE` steps by column name. Extend that
  guard so a non-column step runs when `current < 5`.

- [ ] **Step 1: Write the failing tests.**
  - `test_v4_ledger_migrates_to_v5_and_clears_groups_paths`: the row's
    `collections` becomes NULL, both tables exist, and `user_version ==
    5`.
  - `test_fresh_ledger_has_v5_tables`.
  - `test_readers_tolerate_v4_ledger`: `collection_names`/`renames`
    return `{}` on an unmigrated read connection.
  - `test_sync_replaces_collection_names`: a second sync with a renamed
    collection overwrites the name. The slug is unchanged, so a
    `matches` on the old slug still works (#1211 checklist: a rename
    leaves a recorded slug working).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Call `replace_collection_names(con,
      library.collection_names)` inside `run`'s `with
      ledger.connection()` block, after `_dispatch_and_apply`.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** `Store collection names and renames in the
      ledger (schema v5)`.

### Task 4: `--collection` resolves once, refuses clearly, and drift notices

**Files:**

- Modify: `chitragupta/ledger_cli.py:72-175`,
  `chitragupta/retrieval.py:339-390`,
  `chitragupta/retrieval_passages.py:170-205`,
  `chitragupta/retrieval_cli.py:139-262`,
  `chitragupta/retrieval_iterative.py`,
  `chitragupta/dossier/_retrieval.py`,
  `chitragupta/overlap_embed_scope.py`, `chitragupta/dossier/_drift.py`
- Test: `tests/test_ledger_cli.py`, `tests/test_retrieval*.py`,
  `tests/test_dossier_*drift*.py`

**Interfaces:**

- Consumes: `bib_collections.resolve`, `report`, `ledger.collection_names`.
- Produces:
  - `retrieval.search(...)` and `search_passages(...)` call `resolve`
    once and filter with `matches`. They raise `UnknownCollection` /
    `AmbiguousCollection` to their caller.
  - The CLIs catch both errors and exit 2. Stderr lines:

    ```text
    no collection '<wanted>'; run `chitragupta corpus ledger --collections`
    collection paths are now slug paths (digital-twin.dt-platforms) or display paths with '/' ("Digital Twin/DT Platforms")
    '<wanted>' names <n> collections; pass one slug path:
    ```

    The first line is printed for an unknown value; the second is added
    when `old_syntax` is true. The third is printed for an ambiguous
    value, followed by one slug per line.
  - The retrieval log (`--log`) records the **resolved slug path** in
    its `collection` column.
  - `Drift.unresolved_collections: list[str]`, the recorded query
    collections that `resolve` rejects. `Drift.clean` is false while it
    is non-empty. It appears in `as_dict`.

- [ ] **Step 1: Write the failing tests.**
  - `test_ledger_collections_prints_slug_display_count` (#1211's format
    example).
  - `test_collection_filter_accepts_slug_or_display_path`.
  - `test_unknown_collection_exits_2_with_hint`, which also asserts the
    `>` line.
  - `test_ambiguous_display_path_exits_2_lists_slugs`.
  - `test_retrieval_log_records_resolved_slug`.
  - `test_drift_reports_unresolved_recorded_collection` (Review focus
    4): a recorded `Digital twins > Modelling` makes `clean` False and
    puts the value in `unresolved_collections`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** `Resolve --collection by slug or display path
      and refuse unknown ones`.

### Task 5: Detect and record renames in sync, and scan drafts for residue

**Files:**

- Create: `chitragupta/sync_renames.py`
- Modify: `chitragupta/sync_decide.py:117-215` (`_prune`,
  `_report_stale`), `chitragupta/sync_residue.py` (add `DRAFTS`)
- Test: `tests/test_sync_renames.py`, `tests/test_sync_residue.py`

**Interfaces:**

- Produces:
  - `Rename(old: str, new: str, source: str, same_pdf: bool)`, a frozen
    dataclass
  - `sync_renames.detect(con, stale: list[str], seen: set[str],
    declared: dict[str, str]) -> tuple[list[Rename], dict[str,
    list[str]]]`, which returns (the 1:1 renames, then old → several
    candidate keys for a shared hash).
    - **Declared first:** use `declared[old]` if `old` is stale and `new
      in seen`. `same_pdf` is true when both rows' `pdf_hash` match.
    - **Otherwise by hash:** the bib keys whose `pdf_hash` equals the
      stale row's non-NULL hash. Exactly one gives a `pdf_hash` rename;
      several go to the second map.
  - `sync_renames.record(con, renames: list[Rename], seen: set[str]) ->
    None`: upserts with `seen_at` set to today's ISO date, and deletes
    rows whose `old` is back in `seen` (Review focus 3).
  - Stale lines, and pruned lines with the same suffix:

    ```text
      stale   <old> (no longer in <bib>; renamed to <new>, same PDF)
      stale   <old> (no longer in <bib>; renamed to <new>, different PDF)
      stale   <old> (no longer in <bib>; same PDF as <a>, <b>)
    ```

  - `sync_residue.DRAFTS = "drafts"` scans `config.DRAFTS_DIR` (or the
    existing drafts-dir constant) for `*.md` and `*.tex`, excludes
    `content/dossiers/`, and uses the existing `_pattern`. It comes last
    in the fixed artefact order.
- Order inside `_report_stale` and `_prune`: run `detect` and then
  `record` **before** `find_stale`'s report, so the rows survive
  `prune_missing`.

- [ ] **Step 1: Write the failing tests.**
  - `test_same_hash_new_key_is_recorded_rename`
  - `test_declared_rename_wins_and_flags_different_pdf`
  - `test_shared_hash_reported_not_recorded`
  - `test_rename_recorded_before_prune` (with `--remove-stale`: the row
    survives in `renames` and the old item row is gone)
  - `test_undone_rename_row_deleted`
  - `test_null_hash_stale_key_is_plain_stale`
  - `test_residue_reports_draft_citing_old_key` (`.md` and `.tex`, plus
    a draft citing `keyX` that must not hit for `key`)
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Keep `sync_renames` free of imports from
      `chitragupta.dossier` and `chitragupta.enrich`, following the
      layering note in the `sync_residue` docstring.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** `Record renamed citekeys during sync and report
      drafts citing them`.

### Task 6: `dossier status` renamed list and `dossier apply-renames`

**Files:**

- Modify: `chitragupta/dossier/_drift.py` (`Drift`, `drift`),
  `chitragupta/dossier/__init__.py` (CLI subcommand)
- Create: `chitragupta/dossier/_renames.py`
- Test: `tests/test_dossier_renames.py`, the existing drift test module

**Interfaces:**

- Consumes: `ledger.renames(con)`,
  `dossier._retrieval.mark_revision`-style append to `revisions.md`, the
  existing bounded citekey pattern (move `sync_residue._pattern` into
  `citekey_safety` as `citekey_pattern(citekey) -> re.Pattern[str]` so
  both layers share it without a layering violation).
- Produces:
  - `_renames.final(renames: dict[str, tuple[str, str, bool]], old: str)
    -> tuple[str, bool] | None`: follows the chain to a key with no
    further rename. It returns `(final_key, all_same_pdf)`, or None on a
    cycle.
  - `Drift.renamed: dict[str, dict]`, with entries of the form old →
    `{"new": str, "same_pdf": bool, "sections": list[str]}`. It covers
    only keys cited in the draft or dossier whose final key is in the
    ledger. Such keys are excluded from `missing`, and `clean` is false
    while the dict is non-empty.
  - `apply_renames(draft: Path) -> list[AppliedRename]`, where
    `AppliedRename(old, new, same_pdf, files: list[str])`. It rewrites
    the draft file, `evidence.md`, `sections.md` and `rejected.md` using
    the bounded pattern. It appends one `revisions.md` entry listing
    each swap. It refuses (exit 1, writes nothing) if any target key is
    not in the ledger, or if a cycle is found.
  - CLI: `python -m chitragupta.draft dossier apply-renames <draft>
    [--json]`. It prints `renamed {old} -> {new} in {n} file(s)` for
    each swap, and then, if any swap had `same_pdf` false, `re-check
    quotes: python -m chitragupta.review quotation <draft>`.

- [ ] **Step 1: Write the failing tests.**
  - `test_status_lists_renamed_not_missing`
  - `test_chain_resolves_to_final_key` and
    `test_cycle_is_reported_not_looped` (Review focus 2)
  - `test_apply_renames_swaps_bounded_matches_in_four_files`
  - `test_apply_renames_refuses_key_absent_from_ledger_and_writes_nothing`
  - `test_apply_renames_logs_revision_and_flags_different_pdf`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** `Report and apply recorded citekey renames to a draft`.

### Task 7: Skills: record slug paths and apply renames in re-grounding

**Files:**

- Modify: `.claude/skills-common/references/collection-scoping.md`,
  `.claude/skills/draft-reviser/references/re-grounding.md` (R2/R3), and
  any genre `SKILL.md` line that shows a `>` example path
  (survey-writer:39-46 and its siblings, found with `grep -rn
  "collection" .claude/skills`)
- Test: `tests/test_skill_size.py` stays green. Bench.

- [ ] **Step 1: Edit `collection-scoping.md`.** The agent matches the
      user's words against the display paths `ledger --collections`
      prints, offers the choice once, then records `- collection: <slug
      path>   # <display path>` and passes **only the slug** to
      `--collection`. An exit-2 refusal is to be shown to the user, not
      retried with a guess. Replace the Better BibTeX "degrade silently"
      text with the importer.
- [ ] **Step 2: Edit `re-grounding.md`.** R3 gets a fourth list,
      `renamed`, described as a mechanical fix done first: run `dossier
      apply-renames`, then `review quotation` when the command says to,
      and hand quote failures to the user. `unresolved_collections`
      means: ask the user for the slug, rewrite `scope.md`, and note it
      in `revisions.md`. No issue numbers.
- [ ] **Step 3: Run `markdownlint-cli2` on the touched files and `pytest
      tests/test_skill_size.py`.** Expected: clean.
- [ ] **Step 4: Bench with `skill-bench`.** Covers draft-reviser and
      survey-writer, Claude Code, 3 before / 3 after. Expected: the
      `--collection` value is a slug in every after run, and
      `apply-renames` runs in a re-grounding fixture.
- [ ] **Step 5: Commit** `Record collection slugs and apply renamed
      citekeys in the skills`.

### Task 8: Remove `groups`, update the docs and bump to 7.0.0

**Files:**

- Delete: `scripts/populate_bib_groups.py`,
  `tests/test_populate_bib_groups.py`, `docs/EXPORT-ZOTERO-GROUPS.md`
- Modify: `mkdocs.yml:289` (nav entry), `docs/ZOTERO.md`, `docs/CLI.md`
  (`--collection`, `--collections`, `dossier apply-renames`, the sync
  stale line), `docs/CONFIG.md:73-80`, `docs/TECHNICAL-DEBT.md`,
  `config.toml.example:33`,
  `docs/examples/{sample-project,opencode,codex}/config.toml:32`,
  `pyproject.toml` version

- [ ] **Step 1: Make the edits.** Then run `grep -rn
      "populate_bib_groups\|EXPORT-ZOTERO-GROUPS\|collections_field\|JabRef-specific"
      --include=*.md --include=*.py --include=*.toml --include=*.yml . |
      grep -v "^./plans/"`. Expected: no output.
- [ ] **Step 2: Run the full local checks from DEVELOPER-AGENTS.md**
      ("Before claiming a task complete"): full pytest with coverage at
      100%, ruff, markdownlint, `mkdocs build --strict`,
      `scripts/check_version_bump.py --offline`. Expected: all pass.
- [ ] **Step 3: Commit** `Drop the groups reader and its Zotero script;
      release as 7.0.0`.

### Task 9: Issues and PR

- [ ] Close #1109 with a comment: superseded by #1211. The importer
      writes `cg-collections`, and this PR deletes
      `populate_bib_groups.py`.
- [ ] Open the porting issue (Appendix A) on chitragupta.
- [ ] Open the cg-renames issue (Appendix B) on chitragupta-importer.
- [ ] Open the PR. Title: `Read collections from cg-collections and
      record renamed citekeys`. The body links this plan and says
      `Closes #1211`.

---

## Appendix A: porting issue (chitragupta)

**Title:** Port existing drafts' collection scopes to slug paths

**Body:** since 7.0.0, `--collection` takes a slug path or a `/` display
path and refuses an unknown value. A draft written earlier records
`- collection: Digital twins > Modelling` in `scope.md` and the same
value in `retrieval.md`'s `collection` column. Its next retrieval exits
2, and `dossier status` lists it under `unresolved_collections`. Each
such draft needs its scope ported once. Agent prompt:

````md
```md
Port this project's drafts from the old `groups` collection paths to
chitragupta 7.0.0 slug paths. Change nothing else.

1. Run `chitragupta corpus sync`, then
   `chitragupta corpus ledger --collections`, and keep the listing
   (slug path, display path, count).
2. For every `content/dossiers/*/scope.md` whose header has a
   `- collection:` line that contains `>` or is not a slug path from
   step 1:
   a. Turn the old value into a display path: split on `>`, strip each
      part, join with ` / `.
   b. Find the row in step 1's listing whose display path equals it,
      ignoring case. Exactly one row: take its slug path. None or
      several: do not guess. List the draft, the old value and the
      candidate rows, and ask me.
   c. Replace the line with
      `- collection: <slug path>   # <display path>`.
   d. Append to that dossier's `revisions.md` one entry: "Ported
      collection scope `<old>` to `<slug>` (chitragupta 7.0.0)."
3. Leave `retrieval.md` as it is: it is a log of what ran. `dossier
   status` runs an old logged query against the slug `scope.md` now
   records.
4. For each ported draft run
   `python -m chitragupta.draft dossier status content/drafts/<path>`
   and confirm `unresolved_collections` is empty. Then run
   `python -m chitragupta.draft gate content/drafts/<path>`.
5. Report a table: draft, old value, new slug, or "asked".

Never edit a citekey, the bibliography or the ledger.
```
````

## Appendix B: cg-renames issue (chitragupta-importer)

**Title:** Write a `cg-renames v1` block for dropped and retired citekeys

**Body:** chitragupta 7.0.0 reads an optional block at the top of
`bibliography.bib`:

```bibtex
@comment{cg-renames v1
lehner_pattern_2023-1<TAB>lehner_pattern_2023
}
```

Rows are `old<TAB>new`, sorted by old key. They are read with the same
tolerance as `cg-collections`: fields 1 and 2 only, and an unknown
version is read but flagged. chitragupta detects a rename on its own
only when the old and new PDFs hash the same. The block covers the
cases it cannot see:

- **A bootstrap-dropped duplicate whose PDF differed from the
  survivor's** (ADR-0008). Today `citekeys.lock` records only
  `dropped:<key>`, not which key survived. The importer needs to keep
  that survivor key.
- **A Zotero-side merge whose master is not the survivor**, which
  retires the frozen key (ADR-0008 consequences).

A row is written only when the importer knows the mapping. A key
retired with no successor gets no row. chitragupta still reads no lock
file (ADR-0007).
