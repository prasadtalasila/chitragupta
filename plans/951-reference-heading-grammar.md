# One reference-heading grammar for all three readers (#951)

Status: **plan.** Written 2026-10-02 against `main` @ b8e522f (6.129.0).

**Written for** whoever fixes #951 next, in this repository's own code.
**Assumed:** the dev venv and `config.toml` from `DEVELOPER-AGENTS.md`'s
environment section, so `.venv-full/bin/python -m pytest` runs.
**Not covered here:** `chitragupta/_reference_cut.py`'s heading set. It
cuts the reference list out of a *parsed source PDF*, not out of a
draft, and its vocabulary (`literature cited`, upper-case `7 REFERENCES`)
is measured on the corpus. It is a different grammar over different
input, and folding it in would couple the drafting layer to corpus
statistics.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a draft's bibliography is recognised by one grammar, so
`## Bibliography` and `## Works cited` are treated as the reference list
by the citeproc swap, the verbatim scan, the claims extractor and the
typeset check alike.

**Architecture:** `chitragupta/references_section.py` owns one pattern
*string*, `REFERENCE_TITLE` (optional section number, then one of three
titles). Each reader composes it into the regex its own job needs: a
heading line (`references_section`), a bare heading title after
`_blocks.text_of` has stripped the markup (`review/_claims.py`), and a
heading-plus-body region (`style_typeset.py`). This is the shape #832
used for `citation_gate.PANDOC_KEY`. The issue asks for a single
`REFERENCE_HEADING_RE` object, but the three readers match different
things (a stripped line, a title with its markup already removed, a
multi-line region), so one compiled object cannot serve all three. A
shared string they all compose can.

**Tech Stack:** Python 3 stdlib `re`, pytest.

**Spec:** issue #951 (parent #993). The issue body is the spec. Its
"Fix the class, test the class" section is the acceptance criterion.

## Global Constraints

- Stdlib only in `references_section.py`. It sits on the tier-1
  no-venv path (`docs/ARCHITECTURE.md`), and it must keep importing only
  `citation_gate`, so that nothing imports back into it.
- 100% line and branch coverage (`fail_under = 100`).
- Never a fabricated citekey, even in a fixture. Every fixture here uses
  `k` / `ghost2024`-style keys the existing tests already use, or none.
- PATCH bump (bug fix): `pyproject.toml` `version` to the next patch
  after whatever `origin/main` holds when the PR opens (6.129.1 today).
  Re-read `git show origin/main:pyproject.toml` before bumping.
- Commit body via the PR's `## Commit message` fence. Run
  `scripts/merge_pr.py --check` before opening the PR.

## Decisions this plan makes (a reviewer can reject them here)

1. **The title is anchored at both ends in all three readers.**
   *Settled 2026-10-03: the maintainer confirmed that titles such as
   `## References and notes` are not used, so narrowing costs nothing.*
   `references_section` already refuses `## References and notes` and
   `## Further References` (`tests/test_references.py`
   `test_does_not_match_a_heading_that_is_not_the_bibliography`),
   because `section_start`'s callers act destructively. `_claims` and
   `style_typeset` currently accept any title that *starts* with the
   word (`\b`). Agreement means one of them moves. The destructive
   reader sets the bar, so `_claims` and `style_typeset` get narrower.
2. **The number prefix is the union of the existing three**:
   multi-level digits with an optional `.`/`)` (`1.14 References`,
   `6) References`), or a single letter or a Roman numeral with a
   *required* `.`/`)` (`A. References`, `IV. Works cited`). The `_claims`
   form `[0-9A-Z]+[.)]` is narrowed to these so `## See. References`
   does not parse "See." as a number.
3. **`[ \t]*`, never `\s*`, inside the shared string.**
   `style_typeset` compiles it under `(?s)` across a whole document, and
   `\s` would let a heading's title run onto the next line.
4. **Case-insensitive everywhere.** `style_typeset` was case-sensitive.
   It now also exempts `## further reading`, which nothing relied on
   being reported.
5. **`Further reading` stays `style_typeset`'s own addition.** It is a
   URL exemption (a reading list is links by nature), not a reference
   list: the citeproc swap must not replace a further-reading list with
   `::: {#refs}`. It is therefore excluded from the agreement table, and
   a test pins that only the typeset reader accepts it.
6. **`draft references` replaces a hand-built `## Bibliography`
   instead of adding a second list, which fixes the two-heading
   tutorials.** No code in `references.py` changes; the new grammar is
   the whole fix. Reproduced on `main` @ b8e522f (2026-10-03) with a
   throwaway test that ran `references.apply` and then
   `render_output._swap_manual_refs_for_citeproc` on a tutorial whose
   "Where to go next" section is followed by a hand-built list:

   | Heading on the hand-built list | Draft after `draft references` | What pandoc gets |
   | --- | --- | --- |
   | `## References` | one `## References` | one heading + `::: {#refs}` |
   | `## Bibliography` | `## Bibliography` **and** an appended `## References` | both headings; the hand list survives beside citeproc's |
   | `## Further reading`, `## Sources`, `## References:` | same two-heading result | same |

   `apply` calls `section_start`. When that returns `None`, `apply`
   appends a fresh `## References` and leaves the unrecognised list where
   it is. `numbered_markdown` (`render --format md`) does the same. This
   is the mechanism behind #699 ("the references appear twice in the
   rendered tutorial"). #699 was fixed in the skill text only, by telling
   the tutorial skill to keep `## References`, so any other title still
   produces two headings.

   After this change, `apply(path, heading="References")` replaces a
   `## Bibliography` or `## Works cited` section with `## References`,
   and still keeps any later section, per `section_end`.
   `numbered_markdown` reuses the draft's own heading text, so it keeps
   `Bibliography`. `Further reading` (decision 5), `Sources` and a
   trailing colon remain unrecognised and still produce two headings;
   see "Settled" below.

## Settled: the other two-heading titles are left alone

Decision 6's table shows that `## Further reading`, `## Sources` and
`## References:` still give a tutorial two reference headings after this
change. *Settled 2026-10-03: leave them.* The tutorial skill already
tells the model to keep `## References`, and #951's scope is agreement
between the three readers. No task here touches these titles. The
rejected alternatives were accepting a trailing colon in
`REFERENCE_TITLE`, and making `draft references` refuse to append beside
a hand-built entry list it does not recognise.

## Review Focus

1. **A non-bibliography heading ending in the word**
   (`## References and notes`, `## Further References`): all three
   readers say "not the bibliography". Pinned in Task 2's table.
2. **A `## Bibliography` shown inside a code fence** in a tutorial is
   not a section start, or the citeproc swap eats the rest of the
   lesson. Pinned in Task 1.
3. **LaTeX `\section*{Works Cited}`** in a thesis fragment is excluded
   from claims, the same way `\section*{Bibliography}` already is.
   Pinned in Task 2.
4. **A heading title must not run across a line break**
   (`## 6.\nReferences`). Pinned in Task 1 (decision 3).
5. **The citeproc swap keeps the draft's own `## Bibliography` heading
   text**, since citeproc emits none. Pinned in Task 1.
6. **A tutorial with a hand-built `## Bibliography` ends with exactly
   one reference heading** after `draft references`, and after
   `render --format md`. Pinned in Task 1 (decision 6).

---

### Task 1: The shared grammar in `references_section`

**Files:**

- Modify: `chitragupta/references_section.py:17-35` (comment and `_HEADING_RE`)
- Test: `tests/test_references.py` (`TestHasSection`, `TestApply`,
  and `TestNumberedMarkdown`)
- Test: `tests/test_render_output_citeproc.py` (`TestSwapManualRefsForCiteproc`)
- Test: `tests/test_verbatim_check.py` (`TestMaskForScan`)
- Modify: `docs/RENDERING-FLOW.md` §"The manual References section..." (one sentence)
- Modify: the step-14 paragraph of the tutorial skill in all three
  harness copies: `.claude/skills/tutorial-writer/SKILL.md:650-657`,
  `.agents/skills/tutorial-writer/SKILL.md`, and
  `.opencode/skills/tutorial-writer-opencode/SKILL.md`.
  `tests/test_skill_harness_copies.py` holds the copies in step.

**Interfaces:**

- Produces: `references_section.REFERENCE_TITLE: str`, an uncompiled
  pattern with no anchors, no flags and no capture groups. Callers
  compile it with `re.IGNORECASE`. `_HEADING_RE` stays private and keeps
  its name.

- [ ] **Step 1: Write the failing tests.** Extend the two parametrize
  lists in `tests/test_references.py`:

```python
    @pytest.mark.parametrize(
        "heading",
        [
            "## References",
            "# References",
            "###### References",
            "## 6. References",
            "## 6) References",
            "## 1.14 References",
            "### 12.14 References",
            "## 1.2.3.4 References",
            # #951: the claims and typeset readers already took these, so a
            # draft headed `## Bibliography` kept its hand-built entries
            # beside citeproc's and had its bibliography verbatim-scanned.
            "## Bibliography",
            "## Works cited",
            "## Works Cited",
            "## 7. Bibliography",
            "## A. References",
            "## IV. Works cited",
        ],
    )
    def test_matches_bare_and_numbered_headings(self, heading):
```

and add to the negative list:

```python
            "## Bibliographic notes",
            "## Further reading",
            "## See. References",
            "####### References",
```

Add to `TestHasSection`:

```python
    def test_no_match_for_a_bibliography_heading_inside_a_code_fence(self):
        draft = "# Lesson\n\n```markdown\n## Bibliography\n- an example\n```\n\nMore lesson.\n"
        assert not references_section.has_section(draft)

    def test_a_title_does_not_run_onto_the_next_line(self):
        assert not references_section.has_section("# D\n\n## 6.\nReferences\n")
```

In `tests/test_render_output_citeproc.py`, `TestSwapManualRefsForCiteproc`:

```python
    def test_swaps_a_bibliography_heading_and_keeps_its_text(self):
        # #951: section_start knew only "References", so this draft kept
        # its hand-built list and got citeproc's appended after it.
        text = "A claim [@k].\n\n## Bibliography\n\n[1] A Paper, 2024. `k`\n"
        assert render_output._swap_manual_refs_for_citeproc(text) == (
            "A claim [@k].\n\n## Bibliography\n\n::: {#refs}\n:::\n"
        )
```

In `tests/test_references.py`, `TestApply`, the tutorial regression
from decision 6. It uses the `smith2024` fixture key that
`test_appends_section_when_none_exists` already seeds:

```python
    def test_a_hand_built_bibliography_is_replaced_not_followed_by_a_second_list(
        self, isolated_config
    ):
        # #951 / #699: section_start knew only "References", so apply()
        # appended a fresh `## References` after a tutorial's hand-built
        # `## Bibliography`, and the draft carried two reference lists.
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith2024", title="A Paper", year="2024")
        )
        con.close()
        draft = content_draft(isolated_config, "tutorial.md")
        draft.write_text(
            "# Lesson\n\n## Where to go next\n\nA filter helps [@smith2024].\n\n"
            "## Bibliography\n\n[1] A Paper, 2024. `smith2024`\n"
        )
        references.apply(draft)

        text = draft.read_text()
        assert "## Bibliography" not in text
        assert text.count("## References") == 1
        assert text.count("[1] ") == 1
```

In `TestNumberedMarkdown`, next to
`test_replaces_an_existing_section_and_keeps_its_heading`:

```python
    def test_replaces_a_bibliography_section_and_keeps_its_title(self, ledger_con):
        self._seed(ledger_con)
        draft = (
            "One [@b2024].\n\n## Bibliography\n\n"
            '[1] J. Doe, "B Paper," *J. Things*, 2024. `b2024`\n'
        )
        out = references.numbered_markdown(draft, ledger_con)

        assert "## Bibliography" in out
        assert "References" not in out
        assert out.count("[1] J. Doe") == 1
```

In `tests/test_verbatim_check.py`, `TestMaskForScan`:

```python
    def test_blanks_a_works_cited_section(self):
        text = "Prose.\n\n## Works cited\n\nSmith, Blockchain consensus.\n"
        masked = vc._mask_for_scan(text)
        assert "Smith" not in masked
        assert "Prose." in masked
```

- [ ] **Step 2: Run them and see them fail.**

Run:

```bash
.venv-full/bin/python -m pytest \
  tests/test_references.py \
  tests/test_render_output_citeproc.py \
  tests/test_verbatim_check.py::TestMaskForScan -q
```

Expected: the new `Bibliography`/`Works cited`/`A.`/`IV.` cases FAIL.
`## See. References` and the fenced case pass already, which is
expected: they pin the boundary.

- [ ] **Step 3: Implement.** Replace `_HEADING_RE` and extend the
  comment above it, keeping the existing history paragraphs:

```python
# ... (existing paragraphs kept) ...
#
# The title itself is shared: `review/_claims.py` and `style_typeset.py`
# compose `REFERENCE_TITLE` into their own patterns rather than each
# restating which words open a bibliography, which is how `## Bibliography`
# came to be the reference list for two readers and prose for the third
# (#951). It is a string, not a compiled pattern, because the three match
# different things -- a heading line here, a title with its markup already
# stripped there, a heading-to-next-heading region in the typeset check --
# the same reason `citation_gate.PANDOC_KEY` is one. Anchored at both ends
# by every caller: `## References and notes` is not the bibliography, and
# this module's callers act on the answer destructively. `[ \t]`, not
# `\s`, so a caller compiling it under DOTALL cannot let a title run
# onto the next line. A letter or Roman-numeral number needs its `.` or
# `)`, so "See. References" is not read as section "See".
REFERENCE_TITLE = (
    r"(?:(?:\d+(?:\.\d+)*[.)]?|(?:[A-Z]|[IVXLC]+)[.)])[ \t]*)?"
    r"(?:References|Bibliography|Works[ \t]+cited)"
)
_HEADING_RE = re.compile(rf"^#{{1,6}}[ \t]*{REFERENCE_TITLE}[ \t]*$", re.IGNORECASE)
```

Update `section_start`'s and the module docstring's "References heading"
wording only where it now misleads, for example "the bibliography heading
(References, Bibliography or Works cited)".

- [ ] **Step 4: Run them and see them pass.** Same command as in Step 2.
  Expected: all PASS, including every pre-existing case.

- [ ] **Step 5: Docs.** In `docs/RENDERING-FLOW.md`'s manual-References
  section, after the sentence introducing `section_start`, add:
  "`section_start` recognises the bibliography under any of the three
  titles `references_section.REFERENCE_TITLE` names (References,
  Bibliography, Works cited), numbered or not, so a hand-titled
  `## Bibliography` is swapped like a generated `## References`."
  In the tutorial skill's step 14, in all three copies, replace "recognises
  the section only by a heading whose text is `References`, bare or
  number-prefixed" with "recognises the section only by a heading whose
  text is `References`, `Bibliography` or `Works cited`, bare or
  number-prefixed". Keep the instruction to use the default
  `## References`. Then run
  `.venv-full/bin/python -m pytest tests/test_skill_harness_copies.py -q`.
  Then grep `docs/CLI.md` lines ~2127, ~2386 and ~2654 and
  `docs/PLAGIARISM*.md` for a sentence that states the heading must be
  literally "References". If one does, fix it; if none does, change
  nothing.

- [ ] **Step 6: Commit.**

```bash
git add chitragupta/references_section.py tests/test_references.py \
  tests/test_render_output_citeproc.py tests/test_verbatim_check.py docs/RENDERING-FLOW.md \
  .claude/skills/tutorial-writer/SKILL.md .agents/skills/tutorial-writer/SKILL.md \
  .opencode/skills/tutorial-writer-opencode/SKILL.md
git commit -m "Recognise Bibliography and Works cited as the reference heading in references_section"
```

### Task 2: `_claims` and `style_typeset` share the title; an agreement test

**Files:**

- Modify: `chitragupta/review/_claims.py:41-56` (import; `REFERENCE_TITLE`)
- Modify: `chitragupta/style_typeset.py:46,111-114` (import; `_REFERENCES_RE`)
- Create: `tests/test_reference_heading_grammar.py`
- Test: `tests/test_review_uncited.py` (`TestTheExclusions`), `tests/test_style_typeset.py`

**Interfaces:**

- Consumes: `references_section.REFERENCE_TITLE: str` (Task 1).
- Produces: `_claims.REFERENCE_TITLE` keeps its name and type
  (`re.Pattern`), so `_opens_the_reference_list` does not change.
  `style_typeset._REFERENCES_RE` keeps its name and its one capture
  group.

- [ ] **Step 1: Write the agreement test.** Create
  `tests/test_reference_heading_grammar.py`:

```python
"""#951: three readers, one answer to "is this the bibliography?".

`references_section` (citeproc swap, verbatim masking, `draft references`),
`review/_claims` (uncited-prose report) and `style_typeset` (bare-URL
check) each used to restate which headings open a draft's reference
list, and disagreed: `## Bibliography` was the bibliography for two of
them and prose for the third. Each reader is asked through its public
behaviour, not its regex, so the test still holds if one of them stops
using a regex at all.
"""

import pytest

from chitragupta import references_section, style_typeset
from chitragupta.review import _claims
from tests.conftest import draft_with

URL = "https://github.com/INTO-CPS-Association/plant-controller"

HEADINGS = [
    ("## References", True),
    ("## Bibliography", True),
    ("## Works cited", True),
    ("## Works Cited", True),
    ("## REFERENCES", True),
    ("## 6. References", True),
    ("## 6) Bibliography", True),
    ("## 1.14 Works cited", True),
    ("## A. References", True),
    ("## IV. Bibliography", True),
    ("## Introduction", False),
    ("## References and notes", False),
    ("## Further References", False),
    ("## Reference", False),
    ("## Bibliographic notes", False),
    ("## See. References", False),
]


def section_reader(heading: str) -> bool:
    return references_section.has_section(f"# D\n\nProse.\n\n{heading}\n\nEntry.\n")


def claims_reader(heading: str) -> bool:
    sentences = _claims.claim_sentences(f"# D\n\nProse here.\n\n{heading}\n\nThe entry asserts.\n")
    return "The entry asserts." not in [s.text for s in sentences]


def typeset_reader(heading: str, tmp_path) -> bool:
    body = f"# D\n\nProse.\n\n{heading}\n\n[1] A. Author, {URL}\n"
    return style_typeset.findings(draft_with(body, tmp_path)) == []


@pytest.mark.parametrize(("heading", "is_bibliography"), HEADINGS)
def test_all_three_readers_agree(heading, is_bibliography, tmp_path):
    assert section_reader(heading) is is_bibliography
    assert claims_reader(heading) is is_bibliography
    assert typeset_reader(heading, tmp_path) is is_bibliography


def test_the_two_composing_readers_use_the_shared_title():
    # Composed from the one string, not merely agreeing with it today: a
    # copy that agrees now is the duplication #951 removed, waiting to drift.
    assert references_section.REFERENCE_TITLE in _claims.REFERENCE_TITLE.pattern
    assert references_section.REFERENCE_TITLE in style_typeset._REFERENCES_RE.pattern


def test_further_reading_is_the_typeset_check_s_exemption_alone(tmp_path):
    # A reading list is links by nature, so its URLs are not findings, but
    # it is not the reference list: the citeproc swap must not replace it.
    assert typeset_reader("## Further reading", tmp_path)
    assert not section_reader("## Further reading")
    assert not claims_reader("## Further reading")
```

Before relying on `claims_reader`, run `_claims.claim_sentences` once
on the `## Introduction` case and confirm that `"The entry asserts."`
comes back as a sentence's `.text`, verbatim. If the splitter
normalises the text, match on `"entry asserts"` with `any(... in
s.text ...)` instead. Confirm the same way that `Sentence` exposes
`.text` (`_claims.py:110`).

Add in `tests/test_review_uncited.py` `TestTheExclusions`:

```python
    def test_a_latex_works_cited_heading_is_excluded(self, isolated_config):
        draft = a_draft("\\section*{Works Cited}\n\nA paper.\n", name="thesis.tex")
        assert found_text(draft) == []
```

- [ ] **Step 2: Run them and see them fail.**

Run:

```bash
.venv-full/bin/python -m pytest \
  tests/test_reference_heading_grammar.py \
  tests/test_review_uncited.py::TestTheExclusions -q
```

Expected: the shared-title test FAILS. The `References and notes` / `Further
References` rows FAIL on the claims and typeset readers (decision 1).
`A.` / `IV.` / `REFERENCES` FAIL on the typeset reader.

- [ ] **Step 3: Implement `_claims`.** Import `references_section` beside
  `citation_gate`, then:

```python
from chitragupta import citation_gate, references_section, sentences

# A heading that opens a draft's own bibliography, matched against the
# heading's *title* rather than its markup -- `_blocks` already knows what
# a heading looks like in both markups and how to strip one down to its
# title. Which titles count is `references_section.REFERENCE_TITLE`'s, so
# this reader, the citeproc swap and the typeset check give one answer
# (#951); anchored at both ends for the reason given there.
REFERENCE_TITLE = re.compile(
    rf"^[ \t]*{references_section.REFERENCE_TITLE}[ \t]*$",
    re.IGNORECASE,
)
```

Keep the paragraph about `## 7. References` and move it beside the
shared string's number prefix if that reads better. Before you commit,
check that `text_of` on `\section*{Works Cited}` returns `Works Cited`
with no trailing `}` or whitespace that the `$` anchor would reject.

- [ ] **Step 4: Implement `style_typeset`.** Import `references_section`
  in the existing `from chitragupta import ...` line, then:

```python
# ... (existing comment kept, plus:) Which headings count as the reference
# list is `references_section.REFERENCE_TITLE`'s (#951); "Further reading"
# is this check's own addition -- a reading list is links by nature, but
# it is not the bibliography the citeproc swap replaces.
_REFERENCES_RE = re.compile(
    rf"(?ism)^(#{{1,6}}[ \t]*(?:{references_section.REFERENCE_TITLE}|Further[ \t]+reading)[ \t]*$.*?)"
    r"(?:\n#+ |\Z)"
)
```

- [ ] **Step 5: Run the touched suites and see them pass.**

Run:

```bash
.venv-full/bin/python -m pytest \
  tests/test_reference_heading_grammar.py \
  tests/test_review_uncited.py \
  tests/test_style_typeset.py \
  tests/test_references.py \
  -q
```

Expected: all PASS.

- [ ] **Step 6: Commit.**

```bash
git add chitragupta/review/_claims.py chitragupta/style_typeset.py \
  tests/test_reference_heading_grammar.py tests/test_review_uncited.py
git commit -m "Compose the claims and typeset reference headings from references_section's one title grammar"
```

### Task 3: Whole-repo checks, version bump, PR

**Files:**

- Modify: `pyproject.toml` (`version`), plus whatever
  `scripts/check_version_bump.py` names as also carrying the version.
- Modify: this plan (an outcome line at the top once merged).

- [ ] **Step 1:** `git fetch origin main`. If `main` moved, rebase now,
  before bumping (memory: branch off the latest `origin/main`).
- [ ] **Step 2:** Bump to the next PATCH after `origin/main`'s version.
- [ ] **Step 3:** Run the full suite with coverage:
  `.venv-full/bin/python -m pytest --cov --cov-report=term-missing`.
  Expected: green, 100% line and branch. Then run
  `bash scripts/check_local.sh`. Expected: green.
- [ ] **Step 4:** Review with the `pr-review-toolkit:code-reviewer` agent
  (`ocr review` has no LLM endpoint in this container, so the test plan
  says so).
- [ ] **Step 5:** Open the PR with a `## Commit message` fence, run
  `scripts/merge_pr.py --check`, and include `Closes #951` and a link to
  this plan. One Copilot round, then merge on green CI.
