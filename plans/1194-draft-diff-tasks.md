# Draft diff: implementation tasks

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **plan.** Written 2026-11-13.

**Goal:** Every revision pass leaves a snapshot of the draft it started
from, and `draft diff` turns any snapshot and the live draft into a
change report and a latexdiff redline PDF.

**Architecture:** Snapshots are a dossier concern
(`chitragupta/dossier/_versions.py`, taken by `mark_revision`). The diff
is a new drafting-layer verb, `chitragupta/draft_diff/`: a pure
`compare()` over two `VersionView`s for the report, and a redline path
that renders both sides through `render_output.render(...,
defer_citations=True)`, runs latexdiff, patches the result and compiles
it with LuaLaTeX and `bibtexu`.

**Tech Stack:** Python 3.14 stdlib (`difflib`, `json`, `shutil`,
`subprocess`), pandoc, latexdiff, LuaLaTeX, `lua-ul`, `marginnote`,
`bibtexu`.

**Spec:** [plans/1194-draft-diff.md](1194-draft-diff.md). Read it first; this file
does not restate its decisions or spike findings.

## Global Constraints

- A citekey is used only if it is in the `.bib` and the ledger. Test
  fixtures cite `sample_dt_overview_2024`, `sample_dt_sync_2023`,
  `sample_dt_factory_2022`, `sample_ml_anomaly_2023`,
  `sample_std_interop_2021` (the sample project's `.bib`) and nothing
  else, seeded with `tests/conftest.py`'s `add_citable`.
- The citation gate is never bypassed; `render()` gains no skip flag.
- Every path written stays under `content/`. Diff outputs live in
  `content/review/<topic>/`, i.e. `config.mirrored_dir(draft.parent,
  config.DRAFTS_DIR, config.REVIEW_DIR)`, the rule
  `chitragupta/review/_paths.py`'s `report_dir` uses (not imported: the
  drafting layer does not reach into the review layer).
- Programs are found through `programs.resolve_program` /
  `require_program`, never a bare name.
- Withdrawn-citation token, exactly: `(citation withdrawn)`.
- Header, exactly: `Changes since <ref> · <label or revision label> ·
  <YYYY-MM-DD> — review copy`; `<ref>` is the three-digit number, or the
  file name for `--against <path>`; the middle part is omitted when
  empty.
- latexdiff flags: `--math-markup=coarse` (retry: `whole`); never
  `--flatten`, never `--preamble`, never `--type=UNDERLINE`.
- Report bodies carry no timestamp other than the baseline's own date.
- Not-slow coverage stays at 100%; TeX/latexdiff execution is
  `@pytest.mark.slow` or `# pragma: no cover-windows`, as
  `render_output/__init__.py` already does.
- Version: MINOR bump, `6.171.0` → `6.172.0` (new module, new verb).
- Each reviser `SKILL.md` copy (`.claude/`, `.agents/`, `.opencode/`)
  changes identically except where `tests/fixtures/skill_harness_phrases.toml`
  says.

## Review Focus

1. **A draft whose text starts before its first heading, or has only a
   `#` title.** Text before the first `##`/`\section` is its own section
   titled `(before the first heading)`; it must compare like any other.
   Test in Task 3.
2. **Two sections with the same title** (a textbook's repeated
   "Exercises"). Matching is by `(title, occurrence)`, so the second
   "Exercises" never pairs with the first. Test in Task 3.
3. **A `figure:` marker naming a file that does not exist.** The
   snapshot records the name with no files and takes no error; the
   report lists it as `missing in <side>`. Tests in Tasks 1 and 3.
4. **A label with no ASCII letters or digits** (`"§4 → Ü"`). Its slug
   is empty, so it is refused with a message, not written as `003-`.
   Test in Task 1.
5. **A citation group mixing a withdrawn key with a citable one**
   (`[@sample_dt_sync_2023; @sample_std_interop_2021]` after the second
   left the corpus). Only the withdrawn key is removed; the group stays
   a citation. Test in Task 6.

---

### Task 1: The snapshot store

**Files:**

- Create: `chitragupta/dossier/_versions.py`
- Test: `tests/test_dossier_versions.py`

**Interfaces:**

- Consumes: `dossier.dossier_dir(draft)`, `spec.digest(text)`,
  `render_output._figures`'s marker regexes (`_FIGURE_MARKER_MD_RE`,
  `_FIGURE_MARKER_TEX_RE`; import them, do not copy).
- Produces:

```python
VERSIONS_DIR = "versions"

@dataclass(frozen=True)
class Snapshot:
    number: int
    label: str            # "" for an automatic snapshot
    taken_at: str         # datetime.now().isoformat(timespec="seconds")
    trigger: str          # "mark-revision" | "manual"
    revision_label: str
    fingerprint: str      # spec.digest of the draft text
    draft_name: str       # "survey.md"
    path: Path            # the version directory

    @property
    def source(self) -> Path: ...   # path / draft_name
    @property
    def ref(self) -> str: ...       # f"{number:03d}"

class VersionError(ValueError): ...   # str() is the user-facing message

def label_slug(label: str) -> str: ...
def take(draft: Path, *, trigger: str, label: str = "", revision_label: str = "") -> Snapshot | None: ...
def list_versions(draft: Path) -> list[Snapshot]: ...     # ascending number
def latest(draft: Path) -> Snapshot | None: ...
def resolve(draft: Path, ref: str | None) -> Snapshot: ...
def figure_names(text: str, suffix: str) -> list[str]: ...  # "figures/<base>" as the marker writes it
```

- [ ] **Step 1: Write the failing tests**

```python
def test_first_snapshot_is_001_and_holds_draft_figures_and_manifest(isolated_config): ...
    # draft survey.md naming figures/estimator-loop; both .tex and .txt exist
    # -> versions/001/survey.md byte-identical, figures/estimator-loop.tex/.txt copied,
    #    snapshot.json has all eight fields, trigger == "mark-revision"
def test_only_figures_the_draft_names_are_copied(isolated_config): ...
def test_a_named_figure_with_no_files_is_skipped_silently(isolated_config): ...
def test_mark_revision_snapshot_is_skipped_when_unchanged(isolated_config): ...
    # take(trigger="mark-revision") twice with no edit -> second returns None, one dir
def test_manual_snapshot_is_taken_even_when_unchanged(isolated_config): ...
def test_label_becomes_a_slug_suffix(isolated_config): ...
    # "Sent to supervisor" -> versions/002-sent-to-supervisor
@pytest.mark.parametrize("bad", ["", "  ", "123", "§4 → Ü"])
def test_manual_label_refused(isolated_config, bad): ...   # VersionError
def test_duplicate_label_refused(isolated_config): ...     # after slugging
def test_resolve_by_number_label_and_latest(isolated_config): ...
    # resolve(d, "2"), resolve(d, "002"), resolve(d, "sent-to-supervisor"),
    # resolve(d, "Sent to supervisor"), resolve(d, None) == latest
def test_resolve_unknown_lists_what_exists(isolated_config): ...
    # VersionError message contains "001" and "sent-to-supervisor"
def test_resolve_with_no_versions_names_mark_revision_and_against(isolated_config): ...
def test_tex_fragment_snapshot_copies_its_figures(isolated_config): ...
    # `\input{figures/x.tex}` + `%figure: figures/x` -> both forms copied
```

Manual snapshots require a label (`take(trigger="manual", label="")`
raises `VersionError`); automatic ones take none.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv-full/bin/python -m pytest tests/test_dossier_versions.py -q`
Expected: FAIL, `ModuleNotFoundError: chitragupta.dossier._versions`.

- [ ] **Step 3: Implement `_versions.py`**

`label_slug`: NFKD, drop non-ASCII, lowercase, runs of anything but
`[a-z0-9]` become one `-`, strip `-`. Numbering is `max(existing) + 1`
over directory names matching `^\d{3}(-|$)`. Write into a temporary
sibling directory and `rename` it into place, so a crash never leaves a
half-written version that `list_versions` would read.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv-full/bin/python -m pytest tests/test_dossier_versions.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/dossier/_versions.py tests/test_dossier_versions.py
git commit -m "Keep numbered snapshots of a draft in its dossier"
```

### Task 2: Snapshots from `mark-revision`, and their commands

**Files:**

- Modify: `chitragupta/dossier/_retrieval.py` (`mark_revision`)
- Modify: `chitragupta/dossier/_cli.py` (two parsers),
  `chitragupta/dossier/_status.py` (one line),
  `chitragupta/dossier/__init__.py` (re-export `take`, `list_versions`,
  `resolve`, `Snapshot`, `VersionError`)
- Modify: `docs/DOSSIER.md` (a `versions/` row), `chitragupta/draft.py`
  docstring if it lists dossier commands
- Test: `tests/test_dossier_versions.py`, `tests/test_dossier.py`

**Interfaces:**

- Consumes: Task 1.
- Produces: `dossier snapshot <draft> --label TEXT` (prints
  `Snapshot 002-sent-to-supervisor of <draft>`), `dossier versions
  <draft> [--json]` (one line per version: `ref  date  trigger  label
  or "revision label"`; `--json` is a list of the `Snapshot` fields with
  `path` relative to `content/`). Both exit 1 on `VersionError` with
  `[error] <message>`.

- [ ] **Step 1: Write the failing tests**

```python
def test_mark_revision_takes_a_snapshot_with_its_label(isolated_config): ...
    # mark_revision(d, "shorten §4") -> latest(d).revision_label == "shorten §4",
    # trigger "mark-revision", and the retrieval.md row is still written
def test_mark_revision_unchanged_draft_writes_row_but_no_snapshot(isolated_config): ...
def test_snapshot_command_prints_ref_and_exits_0(isolated_config, capsys): ...
def test_snapshot_command_bad_label_exits_1(isolated_config, capsys): ...
def test_versions_command_lists_and_json(isolated_config, capsys): ...
def test_status_reports_versions_line(isolated_config, capsys): ...
    # "Versions: 2, latest 002 (YYYY-MM-DD)"; "Versions: none yet" when empty
def test_export_restore_round_trip_keeps_versions(isolated_config, tmp_path): ...
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv-full/bin/python -m pytest tests/test_dossier_versions.py
tests/test_dossier.py -q -k "versions or snapshot or mark_revision"`
Expected: the new tests FAIL; existing `mark_revision` tests pass.

- [ ] **Step 3: Implement**

`mark_revision` calls `take(draft, trigger="mark-revision",
revision_label=label)` only when `draft` exists (existing tests mark
revisions on drafts that may not exist on disk; keep them passing).
Parser help strings follow `_add_mark_revision_parser`'s style.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv-full/bin/python -m pytest tests/test_dossier_versions.py
tests/test_dossier.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/dossier tests/test_dossier_versions.py tests/test_dossier.py docs/DOSSIER.md chitragupta/draft.py
git commit -m "Snapshot a draft at each revision boundary"
```

### Task 3: Sections, citekeys and figures compared

**Files:**

- Create: `chitragupta/draft_diff/__init__.py` (docstring only, plus
  `main` re-export added in Task 7), `chitragupta/draft_diff/_views.py`,
  `chitragupta/draft_diff/_sections.py`, `chitragupta/draft_diff/_compare.py`
- Test: `tests/test_draft_diff_compare.py`

**Interfaces:**

- Consumes: Task 1's `Snapshot`, `figure_names`;
  `citation_gate.extract_citekeys_for(path, text)`.
- Produces:

```python
# _views.py
@dataclass(frozen=True)
class VersionView:
    ref: str                     # "004", "current draft", or a file name
    label: str                   # manual label or revision label, may be ""
    date: str                    # "YYYY-MM-DD", or "" for a file
    text: str
    suffix: str                  # ".md" | ".tex"
    figures: "dict[str, FigureForms] | None"   # None: unknown (a bare --against file)

@dataclass(frozen=True)
class FigureForms:
    tikz: str | None
    ascii: str | None

def from_snapshot(s: Snapshot) -> VersionView: ...
def from_draft(draft: Path) -> VersionView: ...
def from_file(path: Path) -> VersionView: ...   # figures read if figures/ is beside it, else None

# _sections.py
@dataclass(frozen=True)
class Section:
    title: str                   # "(before the first heading)" for leading text
    occurrence: int              # 0 for the first section with this title
    body: str

def split(text: str, suffix: str) -> list[Section]: ...
    # .md: ATX headings of level 2+ ; .tex: \section, \subsection, \chapter (starred too)

# _compare.py
SectionKind = Literal["added", "removed", "moved", "changed", "unchanged"]

@dataclass
class SectionChange:
    title: str
    kind: SectionKind
    words_changed: int
    log: list[str] = field(default_factory=list)   # filled by Task 4

@dataclass
class FigureChange:
    name: str
    kind: Literal["added", "removed", "redrawn", "missing"]
    forms: Literal["both", "tikz only", "ascii only", ""]
    side: str = ""               # for "missing": "old" | "new"

@dataclass
class ChangeReport:
    old: VersionView
    new: VersionView
    sections: list[SectionChange]
    citekeys_added: list[tuple[str, str]]     # (key, section title)
    citekeys_dropped: list[tuple[str, str]]   # (key, "still citable" | "no longer parsed" | "no longer in the corpus")
    figures: list[FigureChange] | None        # None when old.figures is None
    log_entries: list[str] = field(default_factory=list)
    unmatched_log_sections: list[str] = field(default_factory=list)
    hand_edits: bool = False

    @property
    def words_changed(self) -> int: ...
    @property
    def unlogged(self) -> list[str]: ...      # changed/added/moved titles with empty log
    @property
    def has_changes(self) -> bool: ...

def compare(old: VersionView, new: VersionView, key_status: Callable[[str], str]) -> ChangeReport: ...
```

- [ ] **Step 1: Write the failing tests**

```python
def test_reworded_section_is_changed_with_word_count(): ...
    # one phrase of 5 words replaced by 3 -> kind "changed", words_changed == 8
def test_identical_drafts_have_no_changes(): ...
def test_added_and_removed_sections(): ...
def test_moved_section_is_moved_not_changed(): ...
    # §4 before §3, bodies identical -> §4 "moved", §3 "unchanged" (relative order of the rest kept)
def test_moved_and_edited_section_is_changed(): ...
def test_renamed_section_is_removed_plus_added(): ...
def test_text_before_first_heading_is_a_section(): ...          # Review Focus 1
def test_repeated_titles_pair_by_occurrence(): ...              # Review Focus 2
def test_tex_sections_are_split_like_markdown(): ...
def test_added_citekey_names_its_section(): ...
def test_dropped_citekey_carries_its_status(): ...
    # key_status returns "no longer in the corpus" for sample_std_interop_2021
def test_figure_redrawn_both_forms_and_one_form_only(): ...
def test_figure_missing_on_one_side(): ...                      # Review Focus 3
def test_unknown_baseline_figures_gives_none(): ...
```

Fixture texts are short Markdown strings written in the test file,
citing only the five sample keys.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_compare.py -q`
Expected: FAIL, `ModuleNotFoundError: chitragupta.draft_diff`.

- [ ] **Step 3: Implement**

Words changed: `difflib.SequenceMatcher(None, old_words, new_words,
autojunk=False)` over whitespace tokens, summing both sides of every
non-equal opcode. Moved: a section present on both sides whose position
in the longest common subsequence of `(title, occurrence)` keys is
missing. `key_status` is injected so this module never opens the
ledger.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_compare.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/draft_diff tests/test_draft_diff_compare.py
git commit -m "Compare two versions of a draft by section, citekey and figure"
```

### Task 4: The revision log and hand edits

**Files:**

- Create: `chitragupta/draft_diff/_revlog.py`
- Modify: `chitragupta/dossier/_create.py` (`_REVISIONS_TEMPLATE`)
- Test: `tests/test_draft_diff_revlog.py`

**Interfaces:**

- Consumes: Task 3's `ChangeReport`;
  `dossier._draft_fingerprint.recorded_draft_digest(dossier)`;
  `spec.digest`.
- Produces:

```python
@dataclass(frozen=True)
class LogEntry:
    date: str             # "YYYY-MM-DD"
    title: str            # the rest of the entry's first line
    sections: list[str]   # from its "Sections:" line; [] when absent

def entries(revisions_md: str) -> list[LogEntry]: ...
def attach(report: ChangeReport, log: list[LogEntry], since: str) -> None: ...
    # since: the baseline date, "" for a file baseline (then nothing is attached).
    # Fills report.log_entries with f"{date} {title}", each changed
    # SectionChange.log with the same strings, and report.unmatched_log_sections.
def hand_edited(draft: Path) -> bool: ...
```

The template comment gains, verbatim: `End each entry with a line
"Sections: <heading>, <heading>" naming every section it changed;
draft diff links entries to sections through it.`

- [ ] **Step 1: Write the failing tests**

```python
def test_entries_parse_heading_and_plain_date_forms(): ...
    # "## 2026-11-12 -- shorten §4" and "2026-08-14 -- copy-edit: ..." both parse
def test_sections_line_is_split_on_commas(): ...
def test_entry_without_sections_line_has_none(): ...
def test_attach_links_entry_to_named_changed_sections(): ...
    # entry dated >= since naming "4. Integrating with everything else" -> that SectionChange.log
def test_attach_matches_by_heading_number_too(): ...           # "Sections: 4, 5a"
def test_attach_reports_names_matching_no_heading(): ...
def test_unlogged_lists_changed_sections_no_entry_names(): ...
def test_entries_before_baseline_are_ignored(): ...
def test_hand_edited_true_when_stamp_differs(isolated_config): ...
def test_hand_edited_false_without_a_stamp(isolated_config): ...
def test_revisions_template_names_the_sections_line(): ...
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_revlog.py -q`
Expected: FAIL, missing module.

- [ ] **Step 3: Implement**

An entry starts at a line matching
`^(#+\s*)?(\d{4}-\d{2}-\d{2})\s*(?:--|—|-)?\s*(.*)$`
and runs to the next. A heading number matches the leading
`\d+[a-z]?(\.\d+)*` of a section title. Entries dated on the baseline's
own day count as after it: over-inclusion is the safe direction.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_revlog.py
tests/test_dossier.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/draft_diff/_revlog.py chitragupta/dossier/_create.py tests/test_draft_diff_revlog.py
git commit -m "Link a diff's changed sections to their revision-log entries"
```

### Task 5: The report as Markdown and JSON

**Files:**

- Create: `chitragupta/draft_diff/_report.py`
- Test: `tests/test_draft_diff_report.py`

**Interfaces:**

- Consumes: Tasks 3–4.
- Produces: `to_markdown(report: ChangeReport) -> str`,
  `to_json(report: ChangeReport) -> dict`, `header(report) -> str` (the
  Global Constraints header, reused by Task 6).

Markdown order: `# Changes since …` header; summary line (`412 words
changed in 3 of 9 sections · citekeys +2 −1 · figures 1 redrawn`);
`The draft differs from its last dossier stamp.` when `hand_edits`
(worded as what is measured since the #1194 sign-off review);
`## Revision log` (entries); `## Sections` (non-unchanged rows, each
with `↳` log lines, then `N unchanged`); `## Citekeys`; `## Figures`
(`Baseline figures unknown.` when `None`); `## Needs a log entry`
(`unlogged`, omitted when empty). No changes: the header and `No
changes.` only.

- [ ] **Step 1: Write the failing tests**

```python
def test_markdown_sections_in_order_and_summary_counts(): ...
def test_markdown_no_changes_is_two_lines(): ...
def test_markdown_unknown_figures_says_so(): ...
def test_markdown_has_no_timestamp_besides_baseline_date(): ...
def test_json_round_trips_counts_and_lists(): ...
def test_header_forms_for_number_label_and_file(): ...
    # "Changes since 004 · shorten §4 · 2026-11-12 — review copy"
    # "Changes since old-survey.md — review copy"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_report.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement** the three functions; Markdown passes
  `markdownlint` (one H1, blank lines around lists).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_report.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/draft_diff/_report.py tests/test_draft_diff_report.py
git commit -m "Write a draft diff's change report as Markdown and JSON"
```

### Task 6: A render with citations deferred, and the two prepared sides

**Files:**

- Modify: `chitragupta/render_output/__init__.py` (`render`),
  `chitragupta/render_output/_pandoc.py` (`_pandoc_command`)
- Create: `chitragupta/draft_diff/_sides.py`
- Test: `tests/test_render_output.py` (argv tests),
  `tests/test_draft_diff_sides.py`

**Interfaces:**

- Consumes: Task 3's `VersionView`; `ledger_citable.citable_citekeys`,
  `unparsed_citekeys`.
- Produces:
  - `render(..., defer_citations: bool = False)`. With it: `--standalone`
    (not the fragment shape), `--natbib` instead of `--citeproc`/`--csl`,
    no `bib_raw_tex_as_text.lua`, `--variable biblio-style=IEEEtran`,
    `--variable natbiboptions=numbers,sort&compress`, the draft's
    manual references list handled as for a fragment (so the PDF has one
    References heading), and `_copy_book_bibliography(out_dir)`. Labels
    are not fragment-prefixed. Refused with `fragment=True` (`ValueError`).
  - `_sides.py`:

```python
WITHDRAWN = "(citation withdrawn)"

def key_status(con) -> Callable[[str], str]: ...
    # "still citable" | "no longer parsed" | "no longer in the corpus"
def withdraw(text: str, suffix: str, citable: Callable[[str], bool]) -> str: ...
def prepare(old: VersionView, new: VersionView, work: Path, citable: Callable[[str], bool]) -> tuple[Path, Path]: ...
    # writes work/old/<stem><suffix>, work/new/..., each with figures/; returns the two source paths
```

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_render_output.py
def test_defer_citations_argv_is_standalone_natbib(): ...
    # "--standalone" and "--natbib" in argv; "--citeproc" and "--csl" not;
    # "biblio-style=IEEEtran" present; no "--top-level-division=chapter"
def test_defer_citations_with_fragment_refused(): ...

# tests/test_draft_diff_sides.py
def test_withdraw_whole_bracket_group_becomes_token(): ...
    # "per project [@sample_std_interop_2021]." -> "per project (citation withdrawn)."
def test_withdraw_mixed_group_drops_only_the_withdrawn_key(): ...   # Review Focus 5
    # "[@sample_dt_sync_2023; @sample_std_interop_2021]" -> "[@sample_dt_sync_2023]"
def test_withdraw_narrative_citation(): ...
def test_withdraw_tex_citep_whole_and_mixed(): ...
    # "\citep{sample_std_interop_2021}" -> token; "\citep{sample_dt_sync_2023, sample_std_interop_2021}" -> "\citep{sample_dt_sync_2023}"
def test_withdraw_leaves_citable_text_byte_identical(): ...
def test_prepare_writes_both_sides_with_figures(tmp_path): ...
def test_prepare_applies_withdraw_to_old_side_only(tmp_path): ...
def test_key_status_reads_the_ledger(ledger_con): ...
    # add_citable for one key, upsert_reference only for another, nothing for a third
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv-full/bin/python -m pytest tests/test_render_output.py
tests/test_draft_diff_sides.py -q -k "defer or withdraw or prepare or
key_status"`
Expected: FAIL.

- [ ] **Step 3: Implement**

Thread `defer_citations` beside `fragment` in `_pandoc_command`; each
`if fragment` that concerns citations becomes `if fragment or
defer_citations`, each that concerns shape or labels stays `fragment`.
`withdraw` locates keys with `citation_gate.extract_citekeys_for` and
edits from the end of the text backwards so offsets stay valid.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv-full/bin/python -m pytest tests/test_render_output.py
tests/test_render_output_citeproc.py tests/test_draft_diff_sides.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/render_output chitragupta/draft_diff/_sides.py tests/test_render_output.py tests/test_draft_diff_sides.py
git commit -m "Render with citations deferred, and prepare a diff's two sides"
```

### Task 7: The redline

**Files:**

- Create: `chitragupta/draft_diff/_redline.py`
- Test: `tests/test_draft_diff_redline.py`, fixture
  `tests/fixtures/draft_diff/latexdiff-output.tex` (a trimmed real
  latexdiff output from the spike scenario, regenerated by the slow test
  in Task 9 if it ever drifts)

**Interfaces:**

- Consumes: Tasks 5–6.
- Produces:

```python
class RedlineFailed(RuntimeError): ...   # str() names the kept .diff.tex and .log

def patch(diff_tex: str, report: ChangeReport) -> str: ...
def redline(old_tex: Path, new_tex: Path, report: ChangeReport, out_dir: Path, stem: str) -> Path: ...
    # returns out_dir / f"{stem}.diff.pdf"; raises render_output.MissingBinary or RedlineFailed
```

`patch` inserts before `\begin{document}`: `\usepackage{lua-ul}`,
`\usepackage{marginnote}`, `\geometry{right=2.2in,marginparwidth=1.8in}`,
colours `DIFaddcolor` (0,0.30,0.75) and `DIFdelcolor` (0.75,0,0),
`\RenewDocumentCommand` for `\DIFadd`, `\DIFdel`, `\DIFaddFL`,
`\DIFdelFL` (`\underLine` / `\strikeThrough` in those colours), and
`\cgchangenote{#1}` as a `\marginnote` in `\footnotesize\sffamily`. After
`\begin{document}`: the header in an `\fbox` with the legend
`\DIFadd{added} \DIFdel{removed}`. It rewrites `\bibliography{…}` to
`\bibliography{bibliography}`, and adds `\cgchangenote{figure redrawn
since <ref>}` before each changed figure's `\input{figures/<name>.tex}`,
`\cgchangenote{moved}` after each moved section's heading, and
`\cgchangenote{log: <entry title>}` after each logged section's heading.

`redline` runs, in `out_dir`: latexdiff `--math-markup=coarse` →
`patch` → `lualatex -interaction=nonstopmode`, `bibtexu`, `lualatex`
×2. On a LuaLaTeX failure it re-runs latexdiff with
`--math-markup=whole` once. `bibtexu`'s exit status is ignored; its
`.blg` is read for `error`, as book-assembler step 9 does.

- [ ] **Step 1: Write the failing tests**

```python
def test_patch_inserts_house_markup_before_document(): ...
def test_patch_header_and_legend_after_begin_document(): ...
def test_patch_rewrites_bibliography_path(): ...
def test_patch_flags_redrawn_figure_moved_and_logged_sections(): ...
def test_patch_leaves_no_ulem_dependency(): ...       # "ulem" not in output
def test_redline_requires_latexdiff(monkeypatch, tmp_path): ...   # MissingBinary, install hint
def test_redline_retries_with_whole_math_then_fails(monkeypatch, tmp_path): ...
    # subprocess mocked: first lualatex fails, second fails -> RedlineFailed naming .diff.tex and .log
def test_redline_command_lines(monkeypatch, tmp_path): ...
    # recorded argv: latexdiff with --math-markup=coarse and no --flatten/--preamble/--type
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_redline.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement** with `programs.require_program`; the
  `MissingBinary` message for latexdiff names `texlive-extra-utils` and
  `python -m chitragupta doctor`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_redline.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/draft_diff/_redline.py tests/test_draft_diff_redline.py tests/fixtures/draft_diff
git commit -m "Build a redline PDF from two rendered versions with latexdiff"
```

### Task 8: `draft diff`

**Files:**

- Create: `chitragupta/draft_diff/_cli.py`
- Modify: `chitragupta/draft_diff/__init__.py` (`main`),
  `chitragupta/draft.py` (`VERBS["diff"]`, the docstring's command
  count and list), `docs/CLI.md`, `docs/FEATURES.md`, the packaging
  command table, `docs/ARCHITECTURE.md` (drafting-layer module list)
- Test: `tests/test_draft_diff_cli.py`; existing
  `tests/test_draft_entrypoint.py`, `tests/test_features_doc.py`,
  `tests/test_packaging_command_table.py` say which docs still lack the
  verb

**Interfaces:**

- Consumes: Tasks 1–7.
- Produces: `python -m chitragupta.draft diff <draft> [--against REF]
  [--format md|pdf] [--json]`. `REF` is a number, a label, or a path
  (a path wins when it exists as a file). Writes `<stem>.diff.md` and
  `<stem>.diff.json` in `content/review/<topic>/`; `pdf` adds
  `.diff.tex`/`.diff.pdf` with the work directory `<stem>.diff/`.
  `--json` prints `to_json` instead of the Markdown.

Exit codes: 0 done (including "No changes."), 1 for `VersionError`, a
`.md`/`.tex` mismatch, `RedlineFailed`, or `MissingBinary` (after the
report is written), each as one `[error]` line.

- [ ] **Step 1: Write the failing tests**

```python
def test_diff_against_latest_writes_report(isolated_config, ledger_con, capsys): ...
def test_diff_against_label_number_and_path(isolated_config, ledger_con): ...
def test_diff_no_versions_exits_1_with_hint(isolated_config, capsys): ...
def test_diff_unknown_ref_lists_versions(isolated_config, capsys): ...
def test_diff_format_mismatch_refused(isolated_config, capsys): ...
def test_diff_no_changes_exits_0_writes_no_pdf(isolated_config, ledger_con, monkeypatch): ...
def test_diff_pdf_without_latexdiff_keeps_report_and_exits_1(isolated_config, ledger_con, monkeypatch, capsys): ...
def test_diff_json_flag_prints_json(isolated_config, ledger_con, capsys): ...
def test_diff_is_a_draft_verb(): ...   # "diff" in draft.VERBS
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_cli.py
tests/test_draft_entrypoint.py tests/test_features_doc.py
tests/test_packaging_command_table.py -q`
Expected: the new tests FAIL; the doc-table tests FAIL once the verb is
registered, naming the documents to update.

- [ ] **Step 3: Implement** the CLI and the docs entries the table tests name.

- [ ] **Step 4: Run the tests to verify they pass**

Run: the same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/draft_diff chitragupta/draft.py docs tests/test_draft_diff_cli.py
git commit -m "Add draft diff: a change report and redline against a snapshot"
```

### Task 9: End to end on the sample project

**Files:**

- Test: `tests/test_draft_diff_slow.py`

- [ ] **Step 1: Write the test** (`@pytest.mark.slow`, skipped unless
  `latexdiff`, `lualatex`, `bibtexu` and `pandoc` resolve)

```python
def test_spike_scenario_redline(isolated_config, ledger_con): ...
    # sample survey + estimator-loop figure; snapshot; apply the spike's edits
    # (reword, new [@sample_ml_anomaly_2023] in §1, multi-cite, \frac edit,
    #  table cell, §4 moved above §3, a sentence dropped, figure label changed);
    # old side cites sample_std_interop_2021 after it is removed from the ledger
    # assert: .diff.pdf exists; .diff.tex has exactly one
    #   r"\DIFadd{\citep{sample_ml_anomaly_2023}}"; no "\DIF" on any line whose
    #   only change would be a citation number; "figure redrawn since 001" present;
    #   "(citation withdrawn)" inside a \DIFdel; report names
    #   sample_std_interop_2021 as "no longer in the corpus"
```

- [ ] **Step 2: Run it**

Run: `.venv-full/bin/python -m pytest tests/test_draft_diff_slow.py -q -m slow`
Expected: PASS locally with the toolchain; SKIP without it.

- [ ] **Step 3: Commit**

```bash
git add tests/test_draft_diff_slow.py
git commit -m "Pin the redline's citation and figure behaviour end to end"
```

### Task 10: Installing latexdiff

**Files:**

- Modify: `scripts/install_full_pipeline.sh` (`os-deps`),
  `chitragupta/doctor.py` (`BINARIES`), `docs/DEV-ENV.md`,
  `docs/RENDERING-FLOW.md`, `docker/Dockerfile` (size comment only, if
  it names one), `docs/WINDOWS.md` (only after the check below)
- Test: `tests/test_doctor.py`, any test pinning `os-deps`'s package list

- [ ] **Step 1: Write the failing test**: `"latexdiff" in
  doctor.BINARIES`, and the os-deps test (if one exists) expecting
  `texlive-extra-utils`.
- [ ] **Step 2: Run it**: `.venv-full/bin/python -m pytest
  tests/test_doctor.py -q` → FAIL.
- [ ] **Step 3: Implement**: add `texlive-extra-utils` to the apt line
  with a comment: latexdiff for `draft diff --format pdf`; its markup
  uses `lua-ul` (texlive-luatex) because `ulem` is not installed.
- [ ] **Step 4: Verify the install**: run
  `scripts/install_full_pipeline.sh os-deps` on this host (it needs
  sudo; ask the user first), then `python -m chitragupta doctor` shows
  `[ok] latexdiff found`.
- [ ] **Step 5: Windows**: check MiKTeX's latexdiff package and whether
  it needs a separate Perl. Write the `docs/WINDOWS.md` row from what is
  found; if it cannot be checked, write nothing there and say so in the
  PR.
- [ ] **Step 6: Run the tests** → PASS, then commit:

```bash
git add scripts/install_full_pipeline.sh chitragupta/doctor.py docs tests/test_doctor.py docker/Dockerfile
git commit -m "Install latexdiff with the full pipeline and check it in doctor"
```

### Task 11: The revisers show the diff

**Files:**

- Create: `.claude/skills/draft-reviser/references/draft-diff.md` and its
  `.agents/` and `.opencode/` copies
- Modify: the three copies each of `draft-reviser/SKILL.md`,
  `corpus-reviser/SKILL.md`, `agenda-reviser/SKILL.md`;
  `tests/test_skill_size.py` (caps, only if needed)
- Test: `tests/test_skill_harness_copies.py`, `tests/test_skill_size.py`

`references/draft-diff.md` holds: when to run (after gate, stamp and
render, once the `revisions.md` entry with its `Sections:` line is
written); the command (`--format pdf`, falling back to `--format md` on
`MissingBinary`); what to show the user (header, summary, non-unchanged
sections, citekey changes, the PDF path); that `Needs a log entry`
means completing the entry and re-running before presenting; that a
milestone snapshot is taken only with a name the user gave.

`SKILL.md` changes: draft-reviser gets one closing step pointing at the
reference (about five lines) and the `Sections:` line in its
`revisions.md` instruction; corpus-reviser adds that its entry names
every section touched; agenda-reviser's "Show the diff and the
`revisions.md` entries" becomes the `draft diff` command against the
snapshot its `mark-revision` took.

- [ ] **Step 1: Edit the `.claude/` copies, then mirror** to `.agents/`
  and `.opencode/` (backticked skill names in the OpenCode copy carry
  `-opencode`).
- [ ] **Step 2: Run** `.venv-full/bin/python -m pytest
  tests/test_skill_harness_copies.py tests/test_skill_size.py -q`.
  Expected: PASS; if a cap fails, raise it to the next 1,000 above the
  largest copy with the reason `"draft diff closing step (<issue>)"`,
  and no further.
- [ ] **Step 3: Commit**

```bash
git add .claude/skills .agents/skills .opencode/skills tests/test_skill_size.py
git commit -m "Have every reviser end by showing what it changed"
```

### Task 12: Docs, version, and every local check

**Files:**

- Modify: `docs/DRAFT-ITERATION.md` (a section on reviewing a revision:
  the commands an author runs, from the spec's §4), `pyproject.toml`
  (`6.172.0`), `plans/1194-draft-diff.md` (renamed from `draft-diff.md`
  once #1194 was filed, and this file to match)

- [ ] **Step 1: Write the docs section** with the five author commands
  (doctor, snapshot, versions, diff three ways, where the outputs land).
- [ ] **Step 2: Bump the version** to `6.172.0`.
- [ ] **Step 3: Run every local check** that DEVELOPER-AGENTS.md's
  "Before claiming a task complete" lists (full pytest including slow,
  ruff, markdownlint over the documented globs, Vale), from
  `.venv-full`. Expected: all green; any red is fixed or named in the
  PR.
- [ ] **Step 4: Commit**

```bash
git add docs pyproject.toml plans
git commit -m "Document reviewing a revision, and release draft diff as 6.172.0"
```
