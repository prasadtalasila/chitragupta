# 1232: spelling correction, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **done**, all five tasks. Written 2026-11-22.

**Goal:** opt-in, announced spelling correction of free-text retrieval
query words against the corpus vocabulary, per #1232.

**Architecture:** a new `chitragupta/retrieval_spelling.py` corrects
typed terms against a vocabulary that a shared read-only index builder
(moved from `dossier/_drift.py` into `retrieval_cache.py`) produces. A
new `chitragupta/retrieval_added.py` merges acronym and spelling
additions into tagged entries and renders them. `retrieval.query_terms()`
calls it, so every ranking path picks the corrections up, and the three
human-facing callers announce them.

**Tech stack:** Python 3 stdlib only, pytest, ruff, pylint.

**Spec:**
[plans/1232-retrieval-spelling-correction.md](1232-retrieval-spelling-correction.md).
Read it first. This plan argues from it.

## Global Constraints

- Tier 1: stdlib only. No `rapidfuzz`, no new dependency.
- `[retrieval].spelling_correction`, boolean, default `false`; env
  override `RETRIEVAL_SPELLING_CORRECTION`.
- Off is structural: with the setting off, no vocabulary is built and
  `query_terms` output is byte-identical to today's.
- A typed term is corrected only if it is all letters, ≥ 5 characters
  and appears in no paper's `term_freqs`.
- Candidates: every one-slip variant of the typed word (one deletion,
  adjacent swap, substitution or insertion over `a`-`z`) that is an
  all-letter word in ≥ 2 papers and not an interrogative; the most papers
  wins; a remaining tie goes to the alphabetically first. At most one
  addition per typed word. No `difflib`.
- Add, never replace. Corrections and acronym expansions read typed terms
  only, and neither feeds the other.
- The vocabulary build never writes the BM25 cache.
- C2: no module over 250 code lines (`python3 scripts/code_standards.py`).
  A file that goes over is split along an existing seam, never added to
  the register.
- 100% line and branch coverage. No fabricated citekeys in fixtures: use
  `tests/conftest.py`'s `add_citable` / `make_reference` / `parsed_file`.
- Log rendering: acronyms exactly as today (`dt -> digital twin`),
  spelling as `strucutral ~> structural`, entries joined by `"; "`.
- CLI note on stderr: `[note] spelling: searched 'structural' for 'strucutral'`,
  indented two spaces.
- Commits: imperative title, a bulleted body, no PR number, ending with
  the `Co-Authored-By` line. Version bump to `6.179.0` (MINOR: new
  backward-compatible functionality).

## Review Focus

1. **The ledger or the cache changes mid-process** (the discover web app
   is long-lived). Expect the next query to see the new vocabulary, not
   the one memoized before a sync. Pinned in Task 2.
2. **No ledger, a stale ledger, or an unreadable one** with the setting
   on. Expect no corrections and no exception from `query_terms`, so the
   caller fails or succeeds exactly as it does today. Pinned in Task 2.
3. **Digits and mixed tokens** (`iso26262x`, `5gnetwork`). Expect them
   never corrected and never offered as a correction, since a
   neighbouring number is never what was meant. Pinned in Task 2.
4. **The same typo twice in one query, or a typo whose correction the
   user also typed** (`strucutral structural`). Expect no duplicate added
   term. Pinned in Task 2.
5. **A query whose only term is an unseen typo**, with correction off.
   Expect `search` to return `[]` exactly as today, not an exception from
   a vocabulary that was never built. Pinned in Task 3.

## File map

| File | Change |
| --- | --- |
| `chitragupta/retrieval_cache.py` | gains `read_only_index(rows, tokenize_item)` (moved from drift) |
| `chitragupta/dossier/_drift.py` | `_ephemeral_index` removed; `Corpus.index` calls the shared builder |
| `chitragupta/config.py` | `SPELLING_CORRECTION` |
| `chitragupta/retrieval_spelling.py` | **new**: vocabulary, one-slip variants, `correct` |
| `chitragupta/retrieval_added.py` | **new**: `Added`, `added_terms`, `describe`, `announce` (the last two moved from `retrieval_expansion.py`) |
| `chitragupta/retrieval_expansion.py` | loses `describe`/`announce`; keeps `expand` |
| `chitragupta/retrieval.py` | `query_terms` calls `retrieval_added.added_terms`; comment above it covers `--y-prev` |
| `chitragupta/retrieval_cli.py` | import and call `retrieval_added.announce` instead of `retrieval_expansion.announce` |
| `chitragupta/discover/__init__.py` | `_search_view` announces spelling corrections |
| `chitragupta/review/citation_coverage.py`, `_citation_coverage_render.py` | record and show corrections per query |
| `config.toml.example`, `docs/CONFIG.md`, `docs/RETRIEVAL.md` | the setting, drift note, bench figures |
| `bench/bench_retrieval_spelling.py`, `bench/results/<date>-spelling-correction/`, `bench/RESULTS.md`, `bench/README.md` | the three arms |
| `pyproject.toml` | version `6.179.0` |

**Setup, once per worktree:** `cp config.toml.example config.toml`.
Without it about 20 tests fail for reasons unrelated to this work.

---

### Task 1: Shared read-only index builder

**Files:**

- Modify: `chitragupta/retrieval_cache.py` (append the function)
- Modify: `chitragupta/dossier/_drift.py:53-92` (remove `_ephemeral_index`),
  `:114` (call site)
- Test: `tests/test_retrieval_cache.py` (create it if absent; otherwise add to
  it)

**Interfaces:**

- Produces: `retrieval_cache.read_only_index(rows: list[sqlite3.Row],
  tokenize_item: Callable[[sqlite3.Row], dict]) -> dict[str, dict]`,
  which is `_ephemeral_index`'s behaviour: seed from `_load_cache()`
  where `_fingerprint(row)` matches **and** the entry passes
  `_load_index`'s shape check (`term_freqs` a dict, `length` an int),
  `tokenize_item(row)` otherwise. It never calls `_save_cache` and never
  touches `_MISSING_PARSED`. It holds a one-entry memo keyed on
  `tuple((row["citekey"], _fingerprint(row)) for row in rows)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_read_only_index_never_saves(monkeypatch, ...):
    monkeypatch.setattr(retrieval_cache, "_save_cache", lambda *_: pytest.fail("saved"))
    index = retrieval_cache.read_only_index(rows, retrieval._tokenize_item)
    assert set(index) == {row["citekey"] for row in rows}

def test_read_only_index_reuses_a_matching_cache_entry(monkeypatch, ...):
    # a cached entry whose fingerprint matches is returned as-is;
    # tokenize_item is not called for it
    ...
    assert index["a2024"] is cached_entry

def test_read_only_index_retokenizes_a_malformed_entry(...):
    # cached entry with matching fingerprint but term_freqs = [] -> tokenize_item is called

def test_read_only_index_leaves_missing_parsed_alone(...):
    # retrieval_cache._MISSING_PARSED is unchanged after the call

def test_read_only_index_memoizes_unchanged_rows(...):
    # second call with the same rows calls tokenize_item zero more times
```

- [ ] **Step 2: Run, expect FAIL** (`AttributeError: read_only_index`):
  `.venv-full/bin/python -m pytest tests/test_retrieval_cache.py -k read_only
  -v`
- [ ] **Step 3: Move the function.** Move the body of `_ephemeral_index`
  and the parts of its docstring about why it exists. Drift's
  `Corpus.index` becomes `retrieval_cache.read_only_index(self.rows,
  retrieval._tokenize_item)`
  with a lazy import, as today.
- [ ] **Step 4: Run, expect PASS**, plus the drift tests unchanged:
  `.venv-full/bin/python -m pytest tests/test_retrieval_cache.py tests/ -k
  "drift or read_only" -v`
- [ ] **Step 5: Commit** `Share drift's read-only BM25 index builder through
      retrieval_cache`.

---

### Task 2: The correction module and its setting

**Files:**

- Modify: `chitragupta/config.py` (after `ACRONYM_EXPANSION`, line ~305),
  `config.toml.example` (after `acronym_expansion`, line ~455)
- Create: `chitragupta/retrieval_spelling.py`
- Test: `tests/test_retrieval_spelling.py`

**Interfaces:**

- Consumes: `retrieval_cache.read_only_index` (Task 1).
- Produces:
  - `config.SPELLING_CORRECTION: bool`
  - `retrieval_spelling.MIN_LENGTH = 5`, `MIN_PAPERS = 2`
  - `retrieval_spelling.one_slip_variants(word: str) -> set[str]`
  - `retrieval_spelling.vocabulary(tokenize_item) -> dict[str, int]` (word →
    number of papers; `{}` when there is no readable ledger)
  - `retrieval_spelling.correct(typed: list[str], tokenize_item, excluded:
    frozenset[str]) -> list[tuple[str, str]]`
    (`(typed word, correction)` in query order; `excluded` is
    `retrieval._INTERROGATIVES`, never a target)

- [ ] **Step 1: Write the failing tests**, monkeypatching `vocabulary`
  to a fixed dict for every rule test, and using a real ledger only for
  the vocabulary tests:

```python
VOCAB = {"structural": 9, "structure": 4, "ageing": 3, "being": 40,
         "architecutre": 1, "simulation": 30}

def test_the_shipped_default_is_off():
    assert config.SPELLING_CORRECTION is False

def test_off_never_builds_a_vocabulary(monkeypatch):
    monkeypatch.setattr(config, "SPELLING_CORRECTION", False)
    monkeypatch.setattr(retrieval_spelling, "vocabulary", lambda _: pytest.fail("read"))
    assert retrieval_spelling.correct(["strucutral"], None) == []

def test_an_unseen_typo_gains_its_corpus_spelling(on):  # `on` sets the switch and VOCAB
    assert retrieval_spelling.correct(["strucutral"], None) == [("strucutral", "structural")]

def test_a_word_in_one_paper_is_never_corrected(on):
    assert retrieval_spelling.correct(["architecutre"], None) == []

def test_a_word_in_one_paper_is_never_a_target(on):
    assert retrieval_spelling.correct(["architecure"], None) == []

def test_under_five_characters_is_never_corrected(on):
    assert retrieval_spelling.correct(["strc"], None) == []

def test_two_slips_away_is_not_corrected(on):
    assert retrieval_spelling.correct(["strcutrul"], None) == []

def test_the_most_papers_wins_a_tie(on):
    assert retrieval_spelling.correct(["aeing"], None) == [("aeing", "being")]

def test_an_alphabetical_tie_break_is_deterministic(on, monkeypatch): ...
def test_no_duplicate_when_the_correction_was_also_typed(on):
    assert retrieval_spelling.correct(["strucutral", "structural"], None) == []
def test_the_same_typo_twice_adds_once(on): ...
def test_a_token_with_a_digit_is_never_corrected(on):   # Review Focus 3
    assert retrieval_spelling.correct(["iso23247", "simul4tion"], None, frozenset()) == []
def test_a_word_with_a_digit_is_never_a_target(on): ...
def test_an_interrogative_is_never_a_target(on):
    # VOCAB has "where": 50; correct(["wherre"], None, frozenset({"where"})) == []
def test_a_non_ascii_fragment_is_treated_as_a_word(on): ...  # "dinger" pinned either way

@pytest.mark.parametrize("typed,word,expected", [
    ("acorss", "across", True),     # adjacent swap
    ("acorss", "actors", False),
    ("abert", "alert", True),       # substitution
    ("strctural", "structural", True),  # insertion into the typo
    ("structurral", "structural", True),  # deletion from the typo
    ("strcutrul", "structural", False),  # two slips
])
def test_one_slip_variants(typed, word, expected):
    assert (word in one_slip_variants(typed)) is expected

def test_vocabulary_counts_papers_not_occurrences(ledger_con, ...): ...
def test_vocabulary_is_empty_without_a_ledger(...):           # Review Focus 2
def test_vocabulary_is_rebuilt_after_the_ledger_changes(...):  # Review Focus 1
def test_two_project_trees_in_one_process_do_not_share_a_vocabulary(...):
def test_vocabulary_never_writes_the_cache(...):
def test_a_stale_or_unreadable_ledger_means_no_correction(...):  # Review Focus 2
```

- [ ] **Step 2: Run, expect FAIL** (module missing):
  `.venv-full/bin/python -m pytest tests/test_retrieval_spelling.py -v`
- [ ] **Step 3: Implement.**
  - `config.SPELLING_CORRECTION = _get_bool("RETRIEVAL_SPELLING_CORRECTION",
    "retrieval", "spelling_correction", default=False)`,
    with a comment in `config.py`'s style saying why it ships off (the drift
    baselines, and zero real typos in the logged queries).
  - `config.toml.example`: the key, commented like `acronym_expansion`.
    It says that switching it on re-baselines `dossier status` drift.
  - `vocabulary`: parsed rows via `ledger.reading()` + `ledger.all_items`
    filtered on `status == PARSED`, catching `(ledger.NoLedger, sqlite3.Error)`
    and returning `{}`;
    then `read_only_index(rows, tokenize_item)`, counting each paper's
    `term_freqs` keys once. Memoize on
    `(LEDGER_PATH, its size and mtime_ns, RETRIEVAL_INDEX_PATH mtime_ns or
    None)`,
    path included as `_json_cache.MemoisedJson` does, so a sync, a cache
    rewrite or another test tree invalidates it. No reset hook is needed.
    `ledger.NoLedger` is the base of `StaleLedger` and `UnreadableLedger`,
    so one `except (ledger.NoLedger, sqlite3.Error)` covers all three.
  - `one_slip_variants`: the four edit sets over `a`-`z`, as a set. The
    parametrized cases pin it.
  - `correct`: return `[]` before anything else when the setting is off.
    The typed word must be `isalpha()`, ≥ `MIN_LENGTH` and absent from
    `vocab`. The pool is `{w: n for w, n in vocab.items() if n >= MIN_PAPERS and
    w.isalpha() and w not in excluded}`.
    The final pick is an explicit `min(candidates, key=lambda w: (-pool[w],
    w))`.
- [ ] **Step 4: Run, expect PASS**, plus
  `python3 scripts/code_standards.py chitragupta/retrieval_spelling.py
  chitragupta/config.py`
  printing no findings. If `config.py` goes over 250, split it along an
  existing seam (its `[retrieval]` block is one) before moving on.
- [ ] **Step 5: Commit** `Add opt-in spelling correction of unseen query words`.

---

### Task 3: Tagged additions in `query_terms`, and the `retrieve` note

**Files:**

- Create: `chitragupta/retrieval_added.py`
- Modify: `chitragupta/retrieval_expansion.py` (remove `describe`, `announce`,
  and their docstrings move with them)
- Modify: `chitragupta/retrieval.py:62-70` (import), `:140-163` (comment +
  `query_terms`)
- Modify: `chitragupta/retrieval_cli.py:34`, `:323`
- Test: `tests/test_retrieval_added.py` (new); move
  `TestDescribe`/`TestAnnounce` out of `tests/test_retrieval_expansion.py` into
  it; add to `tests/test_retrieval.py`

**Interfaces:**

- Consumes: `retrieval_expansion.expand(typed, tokenize) -> list[tuple[str,
  str]]` (unchanged), `retrieval_spelling.correct` (Task 2).
- Produces:
  - `retrieval_added.ACRONYM = "acronym"`, `SPELLING = "spelling"`
  - `class Added(NamedTuple): typed: str; term: str; source: str`
  - `retrieval_added.added_terms(typed: list[str], tokenize, tokenize_item) ->
    list[Added]`:
    acronym entries first, in `expand`'s order, then spelling entries,
    with no term added twice across the two sources
  - `retrieval_added.describe(added: list[Added]) -> str`
  - `retrieval_added.announce(added: list[Added]) -> str` (prints the acronym
    note as today, plus one spelling note per correction; returns
    `describe(added)`)
  - `retrieval.query_terms(query) -> tuple[list[str], list[Added]]`

- [ ] **Step 1: Write the failing tests**

```python
def test_describe_renders_both_sources():
    added = [Added("dt", "digital", ACRONYM), Added("dt", "twin", ACRONYM),
             Added("strucutral", "structural", SPELLING)]
    assert describe(added) == "dt -> digital twin; strucutral ~> structural"

def test_announce_prints_a_spelling_note(capsys):
    announce([Added("strucutral", "structural", SPELLING)])
    assert "[note] spelling: searched 'structural' for 'strucutral'" in capsys.readouterr().err

def test_a_correction_is_never_acronym_expanded(...): ...
def test_an_acronym_expansion_is_never_spelling_corrected(...): ...

# tests/test_retrieval.py
def test_query_terms_is_byte_identical_with_correction_off(...):
    # for the existing test queries: terms equal, and every Added has source ACRONYM
def test_a_corrected_typo_reaches_the_paper(ledger_con, monkeypatch):
    # add_citable a paper titled "... Structural Health ...";
    # off: search("strucutral") == []   (Review Focus 5)
    # on:  [r.citekey for r in search("strucutral")] == [that citekey]
def test_evidence_windows_anchor_on_the_correction(...): ...
def test_retrieve_logs_the_correction(...):   # --log writes "strucutral ~> structural" in `expanded`
```

- [ ] **Step 2: Run, expect FAIL**:
  `.venv-full/bin/python -m pytest tests/test_retrieval_added.py
  tests/test_retrieval.py tests/test_retrieval_expansion.py -v`
- [ ] **Step 3: Implement.** `query_terms` becomes:
  `added = retrieval_added.added_terms(typed, _tokenize, _tokenize_item) if
  typed else []`
  and `return typed + [a.term for a in added], added`. Extend the comment
  above it to say that `--y-prev` prose is corrected without a note, as
  acronyms are. `retrieval_cli` swaps `retrieval_expansion` for
  `retrieval_added` in its import and at `:323`.
- [ ] **Step 4: Run, expect PASS**, then the full retrieval and dossier
  tests: `.venv-full/bin/python -m pytest tests/ -k "retriev or dossier or
  drift" -q`.
  Check `scripts/code_standards.py` on `retrieval.py` and `retrieval_cli.py`;
  split along a seam if either goes over.
- [ ] **Step 5: Commit** `Tag acronym and spelling additions, and announce
      corrections in retrieve`.

---

### Task 4: Announce in `discover search` and citation coverage

**Files:**

- Modify: `chitragupta/discover/__init__.py:203-218` (`_search_view`)
- Modify: `chitragupta/review/citation_coverage.py:49-88` (`CoverageResult`,
  `compute_coverage`), `:140-157` (`coverage_payload`)
- Modify: `chitragupta/review/_citation_coverage_render.py` (`format_report`,
  `render_markdown`)
- Test: `tests/test_discover.py`, `tests/test_citation_coverage.py`

**Interfaces:**

- Consumes: `retrieval.query_terms`, `retrieval_added.Added`, `SPELLING`,
  `describe`, `announce` (Task 3).
- Produces: `CoverageResult.corrections: dict[str, str]`, mapping a query to
  `describe` of its spelling entries; only queries that received a
  correction appear. Payload key `"corrections"` with the same dict,
  **omitted when empty**, so the payload with the setting off is identical to
  today's.

- [ ] **Step 1: Write the failing tests**

```python
def test_discover_search_announces_a_correction(capsys, ...):
    # setting on, a paper with "structural"; discover search "strucutral" --json
    out = capsys.readouterr()
    assert "searched 'structural' for 'strucutral'" in out.err
    json.loads(out.out)            # stdout stays a clean payload

def test_discover_search_prints_no_acronym_note(capsys, ...): ...  # behaviour unchanged

def test_coverage_records_corrections_per_query(...):
    result = compute_coverage(draft, ["strucutral health"], k=5)
    assert result.corrections == {"strucutral health": "strucutral ~> structural"}

def test_coverage_payload_and_reports_show_corrections(...):
    # payload["corrections"] == {...}; format_report and render_markdown each
    # contain a "Spelling corrections" line naming the query
def test_coverage_without_corrections_is_unchanged(...):
    # corrections == {}; "corrections" not in payload; the report text has no "Spelling corrections" line
```

- [ ] **Step 2: Run, expect FAIL**:
  `.venv-full/bin/python -m pytest tests/test_discover.py
  tests/test_citation_coverage.py -v`
- [ ] **Step 3: Implement.** `_search_view`: after `retrieval.search`,
  call `retrieval_added.announce([a for a in retrieval.query_terms(phrase)[1] if
  a.source == SPELLING])`.
  `compute_coverage`: the same filter per query, storing non-empty
  `describe(...)` results. Renderers add the line only when
  `result.corrections` is non-empty.
- [ ] **Step 4: Run, expect PASS**, and `scripts/code_standards.py` on
  `discover/__init__.py` (245 today). Split along a seam if it goes over.
- [ ] **Step 5: Commit** `Announce spelling corrections in discover search and
      citation coverage`.

---

### Task 5: Bench, docs and version

**Files:**

- Create: `bench/bench_retrieval_spelling.py`,
  `bench/results/<date>-spelling-correction/spelling_correction.json`
- Modify: `bench/README.md` (table row), `bench/RESULTS.md` (index row +
  section), `docs/CONFIG.md`, `docs/RETRIEVAL.md`, `pyproject.toml` (`version =
  "6.179.0"`), and the spec's `Status:` line

**Interfaces:**

- Consumes: `retrieval_spelling.correct`, `vocabulary`, `retrieval.query_terms`,
  `retrieval.search`;
  `bench_retrieval_acronym_expansion.self_retrieval_rows` and `live_logged_rows`
  for ground truth.

- [ ] **Step 1: Write the script**, in the shape of
  `bench/bench_retrieval_acronym_expansion.py`: `--tag`, `--self-check`,
  every `[retrieval]` weight pinned, `config.SPELLING_CORRECTION` pinned per
  arm.
  - **Arm 1:** synthetic typos (one swap, deletion, substitution and
    insertion per 5+-letter query word, `random.Random(1232)`) through
    `retrieval_spelling.correct`. Record right, wrong and none, with
    "typo is a corpus word" and "under 5 characters" as their own buckets
    in the denominator. Record time per word next to the pool size, and
    cold- and warm-cache vocabulary build times separately.
  - **Arm 2 (harm check, labelled so):** every live-logged query, off vs
    on. Record which queries gained a correction and their rank movement.
  - **Arm 3:** self-retrieval queries with one typo injected into a
    5+-letter word. Record recall@1/@5 and MRR off vs on against the
    source paper, overall and on affected queries only.
  - Acronym expansion held fixed across arms; vocabulary built through
    the read-only builder, so the bench never writes the cache.
  - `--self-check` asserts the off arm equals a plain `search()` and that
    the typo generator is deterministic.
- [ ] **Step 2: Run** `--self-check`, then the full run against the real
  corpus with `CHITRAGUPTA_PROJECT=/workspace` and `--tag
  <date>-spelling-correction`.
  Expect arm 1 near the spec's 95.7% / 94.3%. A large gap means a bug,
  not a finding: stop and investigate.
- [ ] **Step 3: Write it up.** Add a `bench/RESULTS.md` section and
  index row. Add the figures and the drift note to `docs/RETRIEVAL.md`
  and the setting to `docs/CONFIG.md`. Bump the version. Set the spec's
  `Status:` to built.
- [ ] **Step 4: Verify everything.**
  `.venv-full/bin/python -m pytest -n auto --cov --cov-report=term-missing`
  must print 100% and no failures; `bash scripts/check_local.sh` must
  exit 0; `python3 scripts/code_standards.py` must print no findings.
- [ ] **Step 5: Commit** `Bench spelling correction and document the setting`.
