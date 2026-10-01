# 838: say which empty answer the quotation aid gave

Status: **built** on `fix/838-quotation-universe`, released as
6.127.1. Written 2026-10-01 for issue #838. What changed on the way:
the sample reports were regenerated with the real pipeline, not
hand-edited as Task 2 says, because DEVELOPER-AGENTS.md forbids that.
All four samples carried the false "every checked quote was found"
line, not only `staleness-chapter`. The "nothing to check today"
paragraphs in `docs/CLI.md`, `docs/REVIEW.md` and the module docstring
were rewritten, because the sample dossiers do carry quotes. After the
rebase onto #916, `agenda/_render.py` was at 253 code lines, so Task
3's note table became one line and the guard a walrus: the agenda
now reads `nothing checked -- no dossier` / `-- no quote the draft
cites`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Written for** the person fixing #838: `review quotation` prints the
same `quotes_total: 0, findings: []` whether the draft has no dossier,
has a dossier that quotes nothing the draft cites, or had every quote
checked and found clean. This plan meets
[plans/README.md](README.md)'s second test: the quotation aid's JSON is
an input `review agenda` already reads (`_sources.AID_NAMES`), so a new
field there is a change to an artefact other code depends on, and an
older sidecar without the field has to keep working.

**Assumed:** `review agenda` reads aid JSON from disk and never imports
an aid module to compute anything (`agenda/_sources.py`'s docstring).
`dossier_dir()` *names* a directory without checking that it exists.
`agenda/_sources.py::_read_drift` already treats "no `content/drafts/`
mirror" and "mirror but no directory" as the same *no dossier* state.

**Not covered here:** the `figure` aid (the issue audited it and found
it fine), and any agenda JSON field. The issue asks for the agenda's
*header* to show the universe. `sources.aids.<aid>` is a generic
three-flag object for every aid, and a reader wanting the universe can
read `<stem>.quotation.json` itself.

**Goal:** Make the three empty-findings situations distinguishable in
`review quotation`'s JSON and Markdown, and in `review agenda`'s source
header.

**Architecture:** `quotation.build_report` already returns early on each
path. Each return now records which path it took in a new
`Report.universe`. The render module adds the value to the payload and
puts one line at the top of the shared body. `agenda/_render._aid_note`
reads the value back off the aid's JSON and adds a note for the two
nothing-checked values only. An older sidecar without the key renders
exactly as it does today.

**Tech Stack:** Python 3 stdlib, pytest, the repo's C1/C2 code-standards
scan.

**Spec:** issue #838 (quoted in full under "The issue" below).

## The issue

> `review quotation` reports `quotes_total: 0, findings: []` for three
> different situations: the draft has no dossier, the dossier has no
> quoted spans, and the quotes were checked and are clean. The first two
> read as the third.
>
> Proposed: a `universe` field in the payload and the Markdown header:
> `"no-dossier" | "no-quotes" | "checked"`. The agenda's header for the
> quotation source shows it. Tests: one per value.
>
> Success: the three cases are distinguishable from the JSON and the
> Markdown; line and branch coverage stays at 100%.

The issue's line numbers (`quotation.py:96-105, 175-179`) are stale.
The payload moved to `chitragupta/review/_quotation_render.py` when the
render was split out.

## Decisions an implementer would otherwise invent

1. **`no-dossier` covers a missing directory, not only `DossierError`.**
   A draft under `content/drafts/` that never had a dossier written
   (hand-written, or drafted outside a genre skill) gets a path from
   `dossier_dir()` without raising. `evidence_blocks` then returns `{}`
   for the missing `evidence.md`, and the run ends as `no-quotes`, which
   claims a dossier exists. So `build_report` checks `directory.is_dir()`,
   the same test `agenda/_sources.py::_read_drift` uses. One meaning of
   "no dossier" across the review layer.
2. **A dossier directory without `evidence.md` is `no-quotes`.** A
   dossier exists and quotes nothing, which is literally what
   `no-quotes` says. Splitting it into a fourth value would answer no
   question a reader has.
3. **`no-quotes` means no *published* quote.** A dossier that quotes
   only citekeys the draft no longer cites, or cites only inside a TeX
   comment, gives `no-quotes`. That follows from the aid checking
   exactly what `evidence_appendix.quoted_spans` publishes (the module
   docstring's first decision).
4. **The vocabulary lives in `quotation.py` as `UNIVERSES`.** The agenda
   does not import it, because the agenda reads JSON and does not
   compute. Its note table is pinned against `UNIVERSES` by a test,
   the same way `_SOURCE_LABELS` is pinned against `AID_NAMES`.
5. **The agenda only annotates the two nothing-checked values.**
   `checked`, and an absent key (a sidecar written before this
   change), leave the line as `- Quotation integrity: read`. That keeps
   every existing agenda header byte-identical.
6. **The Markdown token is the first body line,** ``- Universe: `<value>` ``.
   It goes in `_body`, so stdout and the written report share it.
   `review.header()` is shared by all ten aids and does not change.

## Global Constraints

- C2: at most **250 lines of code** per module under `chitragupta/`
  (counted by `scripts/code_standards.py::code_lines`). Measured today:
  `quotation.py` 183, `_quotation_render.py` 131,
  `agenda/_render.py` **239** (11 of headroom, so the agenda change
  must stay small).
- C1: at most **25 statements** per function.
- 100% line *and* branch coverage: `.venv-full/bin/python -m pytest
  --cov --cov-report=term-missing` (`fail_under = 100`).
- The aid stays advisory and exits 0 on every universe.
- Never fabricate a citekey, not even in a test fixture. Reuse the test
  module's existing `KEY = "shao_analysis_2023"` and
  `other_paper_2020`.
- Linters and formatter at their full paths, as in DEVELOPER-AGENTS.md's
  "The linters, which are enforced". That includes `markdownlint-cli2`
  over `plans/**/*.md` for this file.
- Branch from the latest `origin/main`; one PR; the body follows the
  repo's PR template and links this plan.

## Review Focus

1. **A draft under `content/drafts/` with no dossier directory at all.**
   It must say `no-dossier`, not `no-quotes`. Checking only for
   `DossierError` misses it. Pinned in Task 1 (`test_a_draft_with_no_dossier_directory_is_no_dossier`).
2. **A sidecar written before this change, read by `review agenda`.**
   There is no `universe` key. The header must stay `read`, with no
   `KeyError` and no invented note. Pinned in Task 3
   (`test_a_quotation_sidecar_without_a_universe_renders_as_before`).
3. **Every quote checked and all of them unverifiable.** The universe
   is `checked` and the tally shows the unverifiable count. Today the
   body also says *"Every checked quote was found in its cited
   source"*, which is false. The frozen sample
   `staleness-chapter.quotation.md` (0 found, 2 unverifiable) shows the
   bug. It is the same failure class as #838 (a zero-findings report
   that reads as clean), and the fix is in the function this plan
   already edits. Pinned in Task 2
   (`test_all_unverifiable_does_not_claim_every_quote_was_found`).
   **Scope addition:** drop it if the reviewer wants #838 kept exact.
4. **A dossier that quotes only keys the draft does not cite.** This is
   `no-quotes`, not `checked`. Pinned in Task 1 by extending
   `test_a_quote_the_draft_no_longer_cites_is_not_checked`.
5. **A dossier directory without `evidence.md`.** This is `no-quotes`
   (decision 2). Pinned in Task 1
   (`test_a_dossier_without_evidence_md_is_no_quotes`).

---

## File map

| File | Change |
| --- | --- |
| `chitragupta/review/quotation.py` | `UNIVERSES`, `Report.universe`, the `is_dir()` check, one universe per return |
| `chitragupta/review/_quotation_render.py` | `universe` in the payload; the `- Universe:` line; separate empty-universe prose; the all-unverifiable wording |
| `chitragupta/review/agenda/_render.py` | `_QUOTATION_UNIVERSE_NOTES` and a few lines in `_aid_note` |
| `tests/test_review_quotation.py` | one test per universe, plus Review Focus 1, 3, 4 and 5 |
| `tests/test_review_agenda.py` | header tests for each value, the old sidecar, and the pin against `UNIVERSES` |
| `docs/CLI.md` (~line 1955) | document `universe` |
| `docs/examples/sample-project/content/review/dt-overview/*.quotation.{json,md}` | the frozen sample output, edited by hand to match (no generator exists) |

---

### Task 1: `build_report` records which universe it answered from

**Files:**

- Modify: `chitragupta/review/quotation.py:75-112`
- Test: `tests/test_review_quotation.py` (class `TestTheUniverse`, ~line 110)

**Interfaces:**

- Produces: `quotation.UNIVERSES: tuple[str, str, str] = ("no-dossier",
  "no-quotes", "checked")`; `Report(draft: Path, checked:
  list[Checked], universe: str)`, where `universe` is always one of
  `UNIVERSES`.

- [ ] **Step 1: Write the failing tests.** Add this helper next to
  `checked()`:

```python
def universe_of(draft: Path) -> str:
    return quotation.build_report(draft).universe
```

Add to `TestTheUniverse`:

```python
    def test_the_three_universes_are_the_published_vocabulary(self):
        assert quotation.UNIVERSES == ("no-dossier", "no-quotes", "checked")

    def test_a_draft_with_no_dossier_directory_is_no_dossier(self, isolated_config):
        """#838: under content/drafts/, so
        `dossier_dir` names a directory without raising -- but nothing
        was ever written there. Reporting `no-quotes` would claim a
        dossier exists."""
        draft = a_draft()
        assert not dossier.dossier_dir(draft).exists()
        assert universe_of(draft) == "no-dossier"
        assert checked(draft) == []

    def test_a_dossier_without_evidence_md_is_no_quotes(self, isolated_config):
        draft = a_draft()
        dossier.dossier_dir(draft).mkdir(parents=True)
        assert universe_of(draft) == "no-quotes"

    def test_a_checked_run_is_checked(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, SPAN))
        a_source(KEY, (7, f"ISO 23247 defines {SPAN}."))
        assert universe_of(draft) == "checked"
```

Then extend three existing tests, one line each:

- `test_a_pre_a2_dossier_checks_nothing`: add
  `assert universe_of(draft) == "no-quotes"`.
- `test_a_draft_outside_drafts_dir_checks_nothing`: add
  `assert universe_of(draft) == "no-dossier"`.
- `test_a_quote_the_draft_no_longer_cites_is_not_checked`: add
  `assert universe_of(draft) == "no-quotes"` (Review Focus 4).

- [ ] **Step 2: Run them and watch them fail.**
  Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_review_quotation.py -k TestTheUniverse -v
  ```

  Expected: FAIL, `AttributeError: module ... has no attribute 'UNIVERSES'`
  and `'Report' object has no attribute 'universe'`.

- [ ] **Step 3: Implement.** In `quotation.py`, above `Report`:

```python
# What `build_report` could see, before any verdict (#838). Three
# reports that all say "no findings" are three different statements --
# no dossier to read, a dossier that publishes no quote, and quotes
# checked -- and only the last is a clean bill of health.
# agenda/_render.py's `_QUOTATION_UNIVERSE_NOTES` is pinned against it.
UNIVERSES = ("no-dossier", "no-quotes", "checked")
```

Add `universe: str` to `Report` after `checked`. Then rewrite the body
of `build_report` from `try:` down:

```python
    try:
        directory = dossier_dir(draft)
    except DossierError:
        # Under content/ but not content/drafts/ -- report_dir's
        # documented flat fallback for this layer (#496). Every sibling
        # aid degrades to an empty report here rather than raising, so
        # this one must too.
        return Report(draft, [], "no-dossier")
    if not directory.is_dir():
        # `dossier_dir` names the mirror without checking it exists;
        # agenda's `_read_drift` treats this as "no dossier" too (#838).
        return Report(draft, [], "no-dossier")
    text = draft.read_text(encoding="utf-8")
    spans = evidence_appendix.quoted_spans(text, directory, latex=draft.suffix.lower() == ".tex")
    if not spans:
        return Report(draft, [], "no-quotes")
    with ledger.reading() as con:
        return Report(
            draft,
            [
                check_one(citekey, quote, *passages.source_passages(con, citekey))
                for citekey, quote in spans.items()
            ],
            "checked",
        )
```

Update the module docstring's "**Today it checks nothing on any real
draft**" paragraph with one sentence: the report now says which empty
answer it gave (`universe`), so "nothing checked" no longer reads as
"checked, clean".

- [ ] **Step 4: Run the module's tests.**
  Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_review_quotation.py -v
  ```

  Expected: all PASS.

- [ ] **Step 5: Commit.**

```bash
git add chitragupta/review/quotation.py tests/test_review_quotation.py
git commit -m "Record which universe the quotation aid answered from (#838)"
```

### Task 2: The payload and both printed forms carry the universe

**Files:**

- Modify: `chitragupta/review/_quotation_render.py:78-99, 130-161`
- Modify: `docs/CLI.md` (~line 1955)
- Modify: `docs/examples/sample-project/content/review/dt-overview/{survey,trust-chapter,staleness-chapter,staleness-tutorial}.quotation.{json,md}`
- Test: `tests/test_review_quotation.py` (class `TestOutput`, ~line 390)

**Interfaces:**

- Consumes: `Report.universe` from Task 1.
- Produces: payload key `"universe"` (a value from `quotation.UNIVERSES`),
  placed right after the envelope and before `quotes_total`. Task 3
  reads it from the on-disk `<stem>.quotation.json`.

- [ ] **Step 1: Write the failing tests** in `TestOutput`:

```python
    @pytest.mark.parametrize(
        "setup, universe, says",
        [
            ("none", "no-dossier", "No dossier for this draft"),
            ("bare", "no-quotes", "No `quote:` in this draft's dossier"),
            ("quoted", "checked", "Quotes checked: 1"),
        ],
    )
    def test_each_universe_is_named_in_json_and_markdown(
        self, isolated_config, setup, universe, says
    ):
        """#838: three reports that all have no findings must be told
        apart from either form, by a machine and by a reader."""
        draft = a_draft()
        if setup == "bare":
            a_dossier(draft, f"## `{KEY}`\n\nSome prose.\n")
        if setup == "quoted":
            a_dossier(draft, block(KEY, SPAN))
            a_source(KEY, (7, f"ISO 23247 defines {SPAN}."))
        report = quotation.build_report(draft)
        found = quotation.findings(report)
        assert _quotation_render.quotation_payload(report, "cmd", found)["universe"] == universe
        markdown = _quotation_render.render_markdown(report, "cmd", found)
        assert f"- Universe: `{universe}`" in markdown
        assert says in markdown
        assert f"- Universe: `{universe}`" in quotation.run_text(draft)

    def test_all_unverifiable_does_not_claim_every_quote_was_found(self, isolated_config):
        """Review Focus 3: zero absent and zero found is not "every
        checked quote was found" -- the sample's staleness-chapter
        report said exactly that over two unverifiable quotes."""
        draft = a_draft()
        a_dossier(draft, block(KEY, SPAN))
        a_page_level_source(KEY, f"It has {SPAN} in it.")
        text = quotation.run_text(draft)
        assert "Every checked quote was found" not in text
        assert "1 could not be checked from this parse" in text
```

- [ ] **Step 2: Run them and watch them fail.**
  Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_review_quotation.py -k "universe_is_named or all_unverifiable" -v
  ```

  Expected: FAIL with `KeyError: 'universe'`, and the unverifiable test
  failing on the "Every checked quote was found" assertion.

- [ ] **Step 3: Implement.** In `_quotation_render.py`, replace `_body`
  with:

```python
_EMPTY = {
    "no-dossier": [
        "No dossier for this draft, so there is nothing to check.",
        "",
        "A draft outside `content/drafts/`, or one no genre skill wrote a "
        "dossier for, has no `quote:` to read. It is not a clean bill of health.",
    ],
    "no-quotes": [
        "No `quote:` in this draft's dossier, so there is nothing to check.",
        "",
        "That is the expected answer for a dossier written before A2's "
        "`claim:`/`quote:` contract, and for any genre that captures no "
        "deliberate quotation. It is not a clean bill of health.",
    ],
}


def _clean(report) -> list[str]:
    """The no-absent-span paragraph, which must not claim a quote the
    parse could not check was found."""
    skipped = len(report.of("unverifiable"))
    if not skipped:
        return ["Every checked quote was found in its cited source."]
    return [
        f"None was absent; {len(report.of('found'))} found, "
        f"{skipped} could not be checked from this parse."
    ]


def _body(report, found) -> list[str]:
    """Everything below the header, shared by both printed forms. The
    universe line leads so `grep '^- Universe:'` answers #838's question."""
    out = [f"- Universe: `{report.universe}`", ""]
    if report.universe in _EMPTY:
        return out + _EMPTY[report.universe]
    out = [out[0]] + _tally(report) + ["", _NOT_A_VERDICT, ""]
    if found:
        out += ["## Absent from the source they cite", ""] + _finding_lines(report)
    else:
        out += ["## No absent span", ""] + _clean(report) + [""]
    for title, lines in (
        ("Confirmed", _confirmed_lines(report)),
        ("Not checkable from this parse", _skipped_lines(report)),
    ):
        if lines:
            out += [f"## {title}", ""] + lines + [""]
    return out
```

In `quotation_payload`, add `"universe": report.universe,` as the first
key in the `payload.update({...})` dict. Add one sentence to that
function's docstring: `universe` is what separates "no dossier", "no
quote" and "checked" when all three have zero findings (#838).

Also update the module docstring's "nineteen checked, all clean"
paragraph so it names the universe line as the other half of that
distinction.

- [ ] **Step 4: Run the module's tests.**
  Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_review_quotation.py -v
  ```

  Expected: all PASS, `test_two_runs_over_an_unchanged_draft_are_byte_identical`
  included.

- [ ] **Step 5: Update the docs and the frozen sample output.**
  - `docs/CLI.md`: in the `**`--json`**` paragraph, change "plus
    `quotes_total`, ..." to "plus `universe` (`no-dossier`, `no-quotes`
    or `checked`: which of the three zero-findings situations this is),
    `quotes_total`, ...".
  - Each of the four sample `*.quotation.json`: add
    `"universe": "checked",` directly above `"quotes_total"`. All four
    have `quotes_total` > 0.
  - Each of the four sample `*.quotation.md`: insert ``- Universe:
    `checked` `` directly above `- Quotes checked:`.
  - `staleness-chapter.quotation.md` only: replace "Every checked quote
    was found in its cited source." with "None was absent; 0 found, 2
    could not be checked from this parse."
  - To confirm the sample text, generate one report with
    `quotation.run_text` from a scratch draft in the same shape (0 found,
    2 unverifiable) and diff its body against the edited file.

- [ ] **Step 6: Commit.**

```bash
git add chitragupta/review/_quotation_render.py tests/test_review_quotation.py docs/CLI.md docs/examples/sample-project/content/review/dt-overview/
git commit -m "Name the quotation universe in the payload and the report (#838)"
```

### Task 3: The agenda header says why there are zero quotation findings

**Files:**

- Modify: `chitragupta/review/agenda/_render.py:22-38`
- Test: `tests/test_review_agenda.py` (class `TestRenderMarkdown`, near
  `test_absent_stale_and_partial_sources_are_all_named`, ~line 1088)

**Interfaces:**

- Consumes: `AidSource.data["universe"]` for the `quotation` aid, as
  Task 2 writes it; `quotation.UNIVERSES` (tests only).
- Produces: `_render._QUOTATION_UNIVERSE_NOTES: dict[str, str]`, keyed
  by `"no-dossier"` and `"no-quotes"`.

- [ ] **Step 1: Write the failing tests** in `TestRenderMarkdown`. Add
  `from chitragupta.review import quotation` to the imports if it is not
  already there.

```python
    @staticmethod
    def _quotation_line(data):
        sources = _sources_stub(aids={"quotation": _sources.AidSource(available=True, data=data)})
        rendered = _render.render_markdown(
            agenda.Agenda(draft=Path("content/drafts/t/survey.md"), sources=sources, items=[]),
            "cmd",
        )
        return next(line for line in rendered.splitlines() if "Quotation integrity" in line)

    @pytest.mark.parametrize(
        "universe, says",
        [("no-dossier", "no dossier for this draft"), ("no-quotes", "dossier publishes no quote")],
    )
    def test_a_nothing_checked_quotation_run_says_why(self, universe, says):
        """#838: an agenda showing no `misquoted` items must say whether
        any quote was checked at all."""
        line = self._quotation_line({"universe": universe, "findings": []})
        assert "nothing checked" in line and says in line

    def test_a_checked_quotation_run_reads_as_before(self):
        assert self._quotation_line({"universe": "checked", "findings": []}) == (
            "- Quotation integrity: read"
        )

    def test_a_quotation_sidecar_without_a_universe_renders_as_before(self):
        """Review Focus 2: a `.quotation.json` written before #838."""
        assert self._quotation_line({"findings": []}) == "- Quotation integrity: read"

    def test_the_notes_cover_every_nothing_checked_universe(self):
        assert set(_render._QUOTATION_UNIVERSE_NOTES) == set(quotation.UNIVERSES) - {"checked"}
```

Check the label first. `review.AIDS["quotation"]` is the label
`_SOURCE_LABELS` uses. If it is not exactly `"Quotation integrity"`,
use the real label in `_quotation_line` and in both expected strings.

- [ ] **Step 2: Run them and watch them fail.**
  Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_review_agenda.py -k "quotation" -v
  ```

  Expected: the two `says_why` cases and the pin FAIL. The two
  "reads as before" tests already PASS: they are regression guards and
  should stay green through Step 3.

- [ ] **Step 3: Implement.** In `agenda/_render.py`, under
  `_NO_CLASS_AIDS`:

```python
# The quotation aid's two nothing-checked universes (#838), so a header
# above zero `misquoted` items says whether any quote was looked at.
# `checked`, and a sidecar older than the field, add nothing. Pinned
# against `quotation.UNIVERSES` by TestRenderMarkdown.
_QUOTATION_UNIVERSE_NOTES = {
    "no-dossier": "nothing checked -- no dossier for this draft",
    "no-quotes": "nothing checked -- the dossier publishes no quote the draft cites",
}
```

In `_aid_note`, after the `state = ...` line and before the `stale`
check:

```python
    if aid == "quotation":
        note = _QUOTATION_UNIVERSE_NOTES.get((source.data or {}).get("universe"))
        if note:
            state += f", {note}"
```

That is +11 code lines including the dict. Re-measure:

```bash
python3 -c "import sys; sys.path.insert(0, 'scripts'); import code_standards as c; \
  print(c.code_lines(open('chitragupta/review/agenda/_render.py').read()))"
```

It must print ≤ 250. If it is over, collapse the dict to one line per
entry or inline the `if note:`.

- [ ] **Step 4: Run the agenda tests.**
  Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_review_agenda.py tests/test_skill_agenda_reviser_e2e.py -v
  ```

  Expected: all PASS.

- [ ] **Step 5: Commit.**

```bash
git add chitragupta/review/agenda/_render.py tests/test_review_agenda.py
git commit -m "Show the quotation universe in the agenda's source header (#838)"
```

### Task 4: Full local checks, and record the outcome

- [ ] **Step 1:** `.venv-full/bin/python -m pytest --cov --cov-report=term-missing`.
  Expected: exits 0 at 100% line and branch. Pay particular attention to
  the new `is_dir()` branch in `quotation.py`, the `_clean` branches,
  and the `if note:` branch in `_render.py`.
- [ ] **Step 2:** Run the three linters and the formatter at their full
  paths, as DEVELOPER-AGENTS.md's "The linters, which are enforced"
  lists them, including `markdownlint-cli2` over `plans/**/*.md` and
  `docs/**/*.md`.
- [ ] **Step 3:** Run `tests/test_code_standards_scan.py` explicitly to
  confirm C1/C2 for the three touched modules.
- [ ] **Step 4:** Add a line under `Status:` at the top of this file:
  "Closed by #NNN" and anything that changed on the way. Commit with the
  PR.
