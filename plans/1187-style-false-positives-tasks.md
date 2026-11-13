# 1187 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **built, in review as [PR 1193](https://github.com/prasadtalasila/chitragupta/pull/1193).** Written 2026-11-12.

**Goal:** Stop `draft style` and the verbatim scan from handing
`agenda-reviser` unattended "repairs" that are false positives
(issue 1187). Declared exceptions suppress a finding; heuristics only
downgrade it to `repair: "review"`.

**Architecture:** There are two kinds of fix:

- house rules shipped in `assets/vale/`;
- one project-level term list, `style_exceptions.terms()`, which reads
  `content/style_exceptions.toml` plus every acronym expansion.

The term list is consumed by a Python filter over Vale's raw findings
and by the verbatim scan's existing allowlist masking. A new Python
rule, `AcronymCase`, and a match-aware `with_repair` turn guesses into
review items. A `names` flag on verbatim findings does the same for
the agenda.

**Tech stack:** Python 3.12+, `tomllib`, Vale 3.26.0 (pinned), pytest.

**Spec:** [plans/1187-style-false-positives.md](1187-style-false-positives.md).
Read it first; this plan argues from it.

## Global Constraints

- Suppress only what is declared. A heuristic may only set
  `repair: "review"` or make an item surfaced; it never drops a
  finding.
- Exceptions are dialect-agnostic and draft-agnostic.
- `content/style_exceptions.toml` has exactly one key, `terms`, a list
  of non-empty strings. Absent means no terms. Anything malformed
  raises `ValueError`.
- Every `TokenIgnores` / `BlockIgnores` pattern in `vale.ini` must be
  free of literal commas.
- The LaTeX `TokenIgnores` entry is one alternation,
  `(\\(?:(?:begin|end)\{[^}]*\}|[A-Za-z]+\*?))`, placed after the
  existing `\cite` entry. Never split it in two.
- Code standards C1 and C2: a function holds at most 25 statements and
  a module at most 250 code lines. `style_check.py` (278 physical
  lines) and `_scan.py` (257) are near the cap, so new logic goes in
  new modules.
- Coverage for non-slow tests is 100%. Use
  `/home/prasad/git/chitragupta-freja/.venv-full/bin/python` with
  `PYTHONPATH=<worktree, absolute>`, and run `-n auto`.
- Never write a real-looking citekey in a fixture. Use obviously
  synthetic keys such as `fixture_key_2000`, the way existing tests do.
- Bump `pyproject.toml` to the next minor (6.171.0 against today's
  6.170.2). Re-check `origin/main` before merging.

## Review Focus

1. **A term that spans a line break** ("Unified Modeling\nLanguage" in
   wrapped Markdown). The Vale filter works per line, so this finding
   survives, and that is acceptable because it fails loudly. The
   verbatim scan works on the word stream, so it must mask the term.
   Task 6 tests the verbatim side.
2. **A term that is a substring of a word** ("UML" as a term must not
   exempt "UMLs" or "SUMLINE"). The Vale filter matches whole words
   only. Tested in Task 3.
3. **An acronym whose expansion contains regex metacharacters**
   ("C++ Runtime", "Monitor, Analyse, Plan, Execute"). Every term is
   matched with `re.escape`. Tested in Tasks 3 and 5.
4. **An old `verbatim.json` baseline without `names`.** The agenda
   must read a missing `names` as `False`, so existing reports behave
   as today. Tested in Task 7.
5. **No ledger** (a fresh project, or `draft style` run on a draft
   outside `content/`). Bare-citekey masking degrades to no keys and
   must not raise. Tested in Task 6.

---

### Task 1: `style_exceptions` loader

**Files:**

- Create: `chitragupta/style_exceptions.py`
- Modify: `chitragupta/config.py`, next to `VERBATIM_ALLOWLIST_PATH`
  (:326). Add
  `STYLE_EXCEPTIONS_PATH = CONTENT_DIR / "style_exceptions.toml"`,
  with a comment saying it is project data, unlike the per-host
  allowlist.
- Modify: `tests/conftest.py` `under_content` table: add
  `"STYLE_EXCEPTIONS_PATH": "style_exceptions.toml"`.
- Test: `tests/test_style_exceptions.py`

**Interfaces:**

- Produces `style_exceptions.file_terms() -> tuple[str, ...]`: the
  file's terms, in file order, stripped.
- Produces `style_exceptions.terms() -> tuple[str, ...]`: `file_terms()`
  plus every value of `acronyms.load_vocabulary()`, de-duplicated
  case-insensitively (first spelling wins), sorted longest first so
  callers match the longest term first.

- [ ] **Step 1: Write the failing tests.** Each test monkeypatches
  `config.STYLE_EXCEPTIONS_PATH` and `config.ACRONYMS_PATH` into
  `tmp_path`.
  - `test_absent_file_has_no_terms`: `file_terms() == ()`.
  - `test_terms_are_read_in_order`: the file
    `terms = ["Unified Process", "Rational Rose"]` gives that tuple.
  - `test_malformed_toml_raises`, `test_unknown_key_raises`
    (`trems = []`), `test_non_list_raises` (`terms = "x"`),
    `test_empty_string_raises` (`terms = [""]`): each raises
    `ValueError` with the path in its message.
  - `test_terms_merge_the_vocabulary`: an acronyms file with
    `UML = "Unified Modeling Language"` and an exceptions file with
    `terms = ["unified modeling language", "Rational Rose"]` give
    `terms()` holding exactly one spelling of the UML name (the file's,
    since it comes first) and "Rational Rose". The vendored floor
    expansions are present too.
  - `test_terms_are_longest_first`.
- [ ] **Step 2:** Run
  `.venv-full/bin/python -m pytest tests/test_style_exceptions.py -q`.
  Expected: it fails with `ModuleNotFoundError`.
- [ ] **Step 3: Implement the module.** Follow
  `verbatim_check/_allowlist.py:_load_allowlist_phrases` for the error
  shapes (`tomllib.TOMLDecodeError` and `OSError` both become
  `ValueError`). The module docstring states why a malformed file
  raises, quoting the spec's "Project data" reasoning.
- [ ] **Step 4:** Run the tests again. Expected: they pass.
- [ ] **Step 5: Commit** with the subject "Add the project
  style-exceptions term list".

### Task 2: House Vale rules and the exercise convention

**Files:**

- Modify: `assets/vale/vale.ini`
  - Append two entries to `TokenIgnores`: the LaTeX alternation from
    Global Constraints, then `(\*\*Exercise \d+[^*]*\*\*)`. Each gets
    a comment block like its neighbours, recording the measurement
    from the spec. The LaTeX block must say why it is one entry.
  - Rewrite the header paragraph that says the command "copies this
    file to a temp location". It actually passes this file plus
    `--filter`.
- Modify: `assets/vale/styles/chitragupta/Acronyms.yml`. Change
  `second:` to `'(?:\b[A-Za-z][a-z]+[\s-]){1,5}\(([A-Z]{2,6})\)'`.
  The comment says case is now `AcronymCase`'s question.
- Modify: `assets/vale/README.md`. Mention the two new ignores in the
  section on the config.
- Modify: `tests/fixtures/style/exemptions.tex`. Add `\begin{center}`,
  `\centering`, `\color{red}`, `\end{center}`.
- Modify: `tests/fixtures/style/exemptions.md` and `.tex`. Add
  `**Exercise 1 (Objective 2, easy).** Classify.` and
  "supervisory control and data acquisition (SCADA)".
- Modify: `docs/WRITING-STANDARDS.md` §2. Define the label
  `**Exercise N (Objective M, easy|medium|hard).**` and say the grade
  in it is not a defect marker. The marker table (around :177) stays
  as it is.
- Modify: `.claude/skills/textbook-chapter-writer/SKILL.md` (around
  :275, "Include a mix of difficulty") and
  `docs/WRITE-A-TEXTBOOK-CHAPTER.md` (around :262). Require that
  label shape and that grade vocabulary.
- Test: `tests/test_style_check.py::TestAgainstRealVale`

- [ ] **Step 1: Write the failing tests** in `TestAgainstRealVale`. All
  use `tmp_path` drafts, so no dossier exists and the dialect comes
  from `--language` via `check(draft, override="en-GB")`.
  - `test_latex_command_names_are_not_prose`:
    `\begin{center}\n\centering\nInside, this is simply the center.\n\end{center}\n`
    in a `.tex` gives matches exactly `["simply", "center"]`, each once.
    This is the control that stops someone splitting the alternation.
  - `test_emph_argument_is_still_prose`: `\emph{obviously}` is reported.
  - `test_exercise_grade_is_not_a_marker` together with
    `test_easy_in_prose_is_still_a_marker`.
  - `test_lower_case_expansion_counts_as_expanded`:
    "We use supervisory control and data acquisition (SCADA). SCADA
    again." gives no `chitragupta.Acronyms` finding.
  - `test_unexpanded_acronym_is_still_reported`: "FOOB is unexpanded."
  - The existing fixture test stays green with the fixtures' new
    lines.
- [ ] **Step 2:** Run `pytest tests/test_style_check.py -k RealVale -q`.
  Expected: the new tests fail.
- [ ] **Step 3: Make the asset and documentation edits** listed above.
- [ ] **Step 4:** Run the same command, then
  `pytest tests/test_style_assets_match_the_standard.py -q`.
  Expected: both pass.
- [ ] **Step 5: Commit** with the subject "Ignore LaTeX command names
  and the exercise label in the prose check".

### Task 3: Filter Vale findings through the project terms

**Files:**

- Modify: `chitragupta/style_exceptions.py`. Add the filter below.
- Modify: `chitragupta/style_check.py` `run_vale`. Its return value
  becomes
  `style_exceptions.drop_exempt(flattened, Path(draft).read_text(encoding="utf-8"))`.
  Because the filter sits in `run_vale`, `propose_language`'s counts
  are filtered too.
- Test: `tests/test_style_exceptions.py`, and one real-Vale test in
  `tests/test_style_check.py`

**Interfaces:**

- Consumes `terms()` from Task 1.
- Produces
  `style_exceptions.drop_exempt(findings: list[dict], text: str) -> list[dict]`.
  - `findings` are Vale's raw dicts with `Check`, `Line` (1-based) and
    `Span` (`[start, end]`, 1-based columns, inclusive).
  - It returns those whose span does not lie wholly inside a
    case-insensitive, whole-word (`(?<!\w)…(?!\w)`), `re.escape`d
    occurrence of any term on that line.
  - `chitragupta.Acronyms` findings are never dropped.
  - Columns are character offsets, so a line with non-ASCII text
    before the term still lines up. Assert this with "Café" earlier in
    the line.

- [ ] **Step 1: Write the failing tests.** Hand-built finding dicts,
  no Vale.
  - `test_dialect_finding_inside_a_term_is_dropped`: the line
    "The Unified Modeling Language is used." with a DialectGB finding
    at Span `[13, 20]`, given the term.
  - `test_same_word_outside_the_term_is_kept`.
  - `test_acronyms_rule_is_never_dropped`.
  - `test_term_inside_a_longer_word_does_not_exempt` (Review Focus 2).
  - `test_regex_metacharacters_in_a_term` (Review Focus 3):
    "C++ Runtime".
  - `test_non_ascii_before_the_term`.
  - Real Vale: `test_declared_term_is_exempt_under_en_gb`, with
    `UML = "Unified Modeling Language"` in a monkeypatched
    `ACRONYMS_PATH`. Its control: "modeling" alone is still
    reported.
- [ ] **Step 2:** Run
  `pytest tests/test_style_exceptions.py tests/test_style_check.py -q`.
  Expected: the new tests fail.
- [ ] **Step 3: Implement `drop_exempt`** and wire it into `run_vale`.
- [ ] **Step 4:** Run the same command. Expected: it passes.
- [ ] **Step 5: Commit** with the subject "Drop prose findings that
  fall inside a declared term".

### Task 4: Match-aware `with_repair` for dialect rules

**Files:**

- Modify: `chitragupta/style_rules.py` `with_repair` (:69-85) and its
  docstring.
- Test: `tests/test_style_check.py::TestWithRepair`

- [ ] **Step 1: Write the failing tests.** `_repair` gains a `match`
  parameter that defaults to `"x"`.
  - `test_a_capitalised_dialect_match_is_left_for_a_person`:
    `("chitragupta.DialectGB", "scope.md", "Modeling") == "review"`.
  - `test_a_lower_case_dialect_match_is_still_repaired`:
    `"modeling"` gives `"edit"`.
  - `test_capitalisation_does_not_touch_other_rules`:
    `DefectMarkers`, `"Simply"` gives `"edit"`.
- [ ] **Step 2:** Run the class. Expected: the first test fails.
- [ ] **Step 3: Implement.** The `review` condition gains
  `or (dialect and finding["match"][:1].isupper())`.
- [ ] **Step 4:** Run the class. Expected: it passes.
- [ ] **Step 5: Commit** with the subject "Leave a capitalised dialect
  match for a person".

### Task 5: `AcronymCase` rule

**Files:**

- Create: `chitragupta/style_acronym_case.py`
- Modify: `chitragupta/style_rules.py`. Import
  `findings as acronym_case_findings` and register it in
  `PYTHON_CHECKS` right after `acronym_drift_findings`.
- Modify: `assets/style/acronyms.toml.example` (header comment) and
  `assets/style/README.md`. State that the case of an expansion is
  authoritative: capitalised means proper name, lower case means
  common noun.
- Modify: `chitragupta/dossier/_acronyms.py` suggestion output (the
  `print` calls around :134-151). Add one line after the suggestions:
  "Case is authoritative: write a common noun in lower case
  (WRITING-STANDARDS.md §9)."
- Test: `tests/test_style_acronym_case.py`; extend
  `tests/test_dossier.py` or wherever `acronyms-suggest` output is
  asserted.

**Interfaces:**

- Consumes `acronyms.load_vocabulary()`, the existing References cut
  `acronyms._REFERENCES_HEADING`, and
  `style_elements.finding(rules, rule, match, line, message, repair)`.
- Produces `style_acronym_case.findings(draft: Path) -> list[dict]`.
  - `RULES = {"acronym-case": "chitragupta.AcronymCase"}`.
  - Every finding has `repair="review"`. Its `match` is the phrase as
    written, and its message names the vocabulary spelling.
  - One finding per distinct `(acronym, phrase)`, at the first line it
    occurs.

- [ ] **Step 1: Write the failing tests.** Vocabulary via a
  monkeypatched `ACRONYMS_PATH`.
  - `test_wrong_case_mid_sentence_is_reported`: vocabulary
    `SCADA = "supervisory control and data acquisition"`; the draft
    "We use Supervisory Control and Data Acquisition (SCADA)." gives
    one finding, with `repair == "review"`.
  - `test_matching_case_is_clean`.
  - `test_sentence_start_capital_is_tolerated`: "Supervisory control
    and data acquisition (SCADA) is old." at the start of a line, and
    again after ". ".
  - `test_heading_capital_is_tolerated`:
    `## Supervisory control and data acquisition (SCADA)`.
  - `test_proper_name_written_lower_case_is_reported`: vocabulary
    `UML = "Unified Modeling Language"`, text "the unified modeling
    language (UML)".
  - `test_references_section_is_ignored`.
  - `test_metacharacters_in_an_expansion` (Review Focus 3):
    `MAPE = "Monitor, Analyse, Plan, Execute"`.
  - `test_registered_in_python_checks`. The existing
    unregistered-module test in `tests/test_style_check.py` already
    guards this; make sure it passes.
- [ ] **Step 2:** Run the new file. Expected: `ModuleNotFoundError`.
- [ ] **Step 3: Implement.** For each `(acronym, expansion)`, compile
  `(?i)(?<!\w)(re.escape(expansion))\s*\(acronym\)`. Tolerance: the
  written phrase equals the expansion with only its first character's
  case changed, and the match starts a line, follows `[.!?]\s+`, or
  sits on a `#` heading line.
- [ ] **Step 4:** Run the new file and `tests/test_style_check.py`.
  Expected: both pass.
- [ ] **Step 5: Commit** with the subject "Report an acronym expansion
  written in a different case from the vocabulary".

### Task 6: Verbatim masking for LaTeX cites, bare citekeys and terms

**Files:**

- Modify: `chitragupta/review/verbatim_check/_masking.py`.
  - `_tokenize_draft(text, *, latex=False, citekeys=frozenset())`.
  - When `latex`, blank `_LATEX_CITE_RE`
    (`r"\\cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*)*\{[^}]*\}"`) with
    `_blank_span`, as `_CITE_MARKER_RE` is blanked now, and pass
    `latex=latex` to `extract_citekeys_from_line`.
  - Blank every whole-token occurrence of a key in `citekeys`, using
    one alternation regex with the longest key first and the
    boundaries `(?<![\w:.-])` and `(?![\w:-])`.
- Modify: `chitragupta/review/verbatim_check/_scan.py` `scan_findings`.
  - Pass `latex=Path(draft).suffix == ".tex"` and
    `citekeys=_known_citekeys()`.
  - Extend `allowlist` with
    `[t for t in (tuple(norm(term)) for term in style_exceptions.terms()) if t]`.
- Create the `_known_citekeys() -> frozenset[str]` helper in a new
  `chitragupta/review/verbatim_check/_citekeys.py`.
  - It opens `ledger.reading()` and returns `ledger.known_citekeys(con)`.
  - On `ledger.NoLedger`, `StaleLedger`, `UnreadableLedger` or
    `sqlite3.Error` it returns an empty set, mirroring
    `style_bare_citekeys._ledger_keys`.
- Test: `tests/test_verbatim_check.py` (`TestTokenizeDraft`, plus a
  new `TestProjectTerms`)

- [ ] **Step 1: Write the failing tests.**
  - `test_latex_cite_command_is_blanked`: `\citep[p.~3]{fixture_key_2000}`
    contributes no words, and the paragraph's citekeys include
    `fixture_key_2000`.
  - `test_bare_citekey_is_blanked`: `fixture_key_2000` in prose with
    `citekeys={"fixture_key_2000"}` contributes no word, and the
    character offsets of the words after it are unchanged.
  - `test_no_ledger_means_no_keys` (Review Focus 5).
  - `test_declared_term_suppresses_a_run_it_accounts_for`. Patch the
    allowlist path empty and `style_exceptions.terms` to return
    `("National Institute of Standards and Technology",)`. Run
    `scan_findings` over a corpus fixture, reusing the existing
    `TestAllowlistSuppression` setup, where the run is that name plus
    fewer than `min_run` other words. It is suppressed, and the
    returned `suppressed` count includes it.
  - `test_term_across_a_line_break_is_masked` (Review Focus 1).
- [ ] **Step 2:** Run `pytest tests/test_verbatim_check.py -q`.
  Expected: the new tests fail.
- [ ] **Step 3: Implement** the changes listed above.
- [ ] **Step 4:** Run `tests/test_verbatim_check.py` and
  `tests/test_skill_verbatim_scan_step.py`. Expected: both pass.
- [ ] **Step 5: Commit** with the subject "Mask LaTeX cites, bare
  citekeys and declared terms in the verbatim scan".

### Task 7: The `names` flag and its agenda mapping

**Files:**

- Create: `chitragupta/review/verbatim_check/_names.py`
- Modify: `chitragupta/review/verbatim_check/_scan.py`.
  - In `scan_findings`, set
    `f["names"] = names_heavy(f.get("draft_text") or "")` on every
    finding before sorting.
  - Add `"names"` to `_PAYLOAD_FIELDS` (:207).
- Modify: `chitragupta/review/agenda/_items_findings.py:74`. The
  condition becomes
  `severity == "short" and tier != "embedding" and not finding.get("names", False)`,
  with a comment citing #1187.
- Test: `tests/test_verbatim_check.py`, `tests/test_review_agenda.py`

**Interfaces:**

- Produces `names_heavy(text: str) -> bool`.
  - Words are `re.findall(r"[^\W\d_][\w'-]*", text)`.
  - A word is "initial" if it is the first word or follows `[.!?:]`
    plus whitespace.
  - True when there are at least 2 words and
    `capitalised non-initial words * 2 >= len(words)`.

- [ ] **Step 1: Write the failing tests.**
  - `names_heavy`:
    - "established by the National Institute of Standards and
      Technology in" gives True.
    - "the model is updated from sensor data at each step" gives
      False.
    - "Data. Models" gives False, because both words are initial.
    - `""` gives False.
  - Agenda, in `test_review_agenda.py` next to the existing verbatim
    item tests:
    - `test_short_names_run_is_surfaced`: a short exact finding with
      `"names": True` gives `unattended is False`.
    - `test_baseline_without_names_is_unchanged` (Review Focus 4): the
      same finding with no `names` key gives `unattended is True`.
  - `published()` output contains `names`.
- [ ] **Step 2:** Run both test files. Expected: the new tests fail.
- [ ] **Step 3: Implement** `_names.py`, the `_scan.py` lines and the
  agenda condition.
- [ ] **Step 4:** Run `tests/test_verbatim_check.py`,
  `tests/test_review_agenda.py` and
  `tests/test_skill_agenda_reviser_e2e.py`. Expected: all pass.
- [ ] **Step 5: Commit** with the subject "Surface a short verbatim
  run made mostly of names".

### Task 8: Documentation, skill references, version

**Files:**

- Modify: `docs/WRITING-STANDARDS.md`.
  - §8: a capitalised dialect match is `review`.
  - §9: add `AcronymCase` to the checked table, and add
    `content/style_exceptions.toml`.
- Modify: `docs/CONFIG.md`. List the new `content/` file. (Check with
  `grep -n verbatim_allowlist docs/*.md` where the content files are
  listed, and follow that.)
- Modify: `docs/PLAGIARISM.md`. Add the new masks (LaTeX cites, bare
  citekeys, declared terms) and the `names` field.
- Modify: `.claude/skills/agenda-reviser/SKILL.md`, the `prose` row of
  the class table (:79) and the verbatim row. List `AcronymCase`,
  capitalised dialect matches and `names` runs among the surfaced
  ones.
- Modify:
  `.claude/skills/agenda-reviser/references/repair-missing-citekey.md`
  (:9-32). Both items persist until the author runs `dossier prune`,
  and the report names that command. Mirror the change in `SKILL.md`
  :80-81.
- Modify: `pyproject.toml` (version 6.171.0) and the lock file, if
  the repository's bump procedure in `DEVELOPER-AGENTS.md` says so.
- Modify: `plans/1187-style-false-positives.md`. Change its status
  line to "built", with the PR number, once the PR is open.

- [ ] **Step 1:** Make the edits.
- [ ] **Step 2: Run every local check `DEVELOPER-AGENTS.md` lists**
  before claiming done: the full non-slow suite with coverage,
  `ruff`, the C1/C2 checks, markdownlint over the changed `.md` files,
  and `python -m chitragupta.draft style` on one `.md` and one `.tex`
  sample draft. Expected: all pass, coverage is 100%.
- [ ] **Step 3: Commit** with the subject "Document the 1187 exception
  rules and bump to 6.171.0".
- [ ] **Step 4: Post a comment on #1187** for item 5, after the user
  approves the wording. No 60-second timeout exists in the repo, and
  the aids run in-process. Pausing a job with SIGSTOP under an outside
  timeout kills it, so serialise launches instead.
