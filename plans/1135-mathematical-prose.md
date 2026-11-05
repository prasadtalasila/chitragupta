# Mathematical prose: the sentences around a symbol (TB-7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Status: **planned.** Written 2026-11-05, for
[issue 1135](https://github.com/prasadtalasila/chitragupta/issues/1135).
Part of [epic 1128](https://github.com/prasadtalasila/chitragupta/issues/1128).

**Goal:** both chapter skills read one shared reference,
`.claude/skills-common/references/mathematical-prose.md`, on every run. It
tells the writer how the prose around a symbol, a condition and a
derivation is written.

**Architecture:** prose only, with no new check. It is one new shared
reference file, a pointer to it in all three harness copies of
`textbook-chapter-writer` and `thesis-chapter-writer`, a pointer
subsection in `docs/WRITING-STANDARDS.md` §12, and a credit to Wilkes in
its Sources section. One new test pins the two pointers.

**Tech stack:** Markdown and pytest (the existing `tests/test_skill_*.py`).

**Spec:** this file. The design was agreed in the session of 2026-11-05.
Its decisions are recorded below.

## What #1147 already delivered, and so is not built here

#1135 asked for three things beyond the prose. #1147 (v6.159.0, which
closed #1143) delivered them as data:

| #1135 asked for | Delivered by #1147 as |
| --- | --- |
| `draft style` reports a symbol defined twice with different role words | `math.md`'s `## Symbols` is the only place a meaning is written. `render` warns about a repeated row, and `registry check` reports a symbol naming two things or set two ways across a book |
| a symbols table once a chapter carries more than a handful | the `## Symbols` table itself, printed as a book's List of Symbols |
| no overloading | the same clash finding, within a book |

A prose-pattern check was measured and rejected. 0 of the 42 drafts in
`chitragupta-drafts` define a symbol in the form ``Let `x` be …``, and
only 26 use the form `` `x` is the …``. A regex check would find almost
nothing today and would duplicate #1147's data check. This was the
user's decision on 2026-11-05.

## Decisions

- **Shared reference, not a skill-local one.** Both chapter skills use
  it, so it lives in `.claude/skills-common/references/`, beside
  `figures-tables-equations.md`.
- **Read on every run, unconditionally** (the user's decision). There is
  no "only when the chapter has maths" trigger.
- **Headings in the reference are unnumbered.** `tests/test_skill_references.py`
  requires every numbered `## N.` section of a shared reference to be
  cited by a skill as "§N". This file is read whole, so it has no
  numbers to cite.
- **The examples come from one domain:** the greenhouse pot of the
  digital-twins book (moisture `m`, drying rate `d`, dose `V`, check
  interval `T_c`). This is the issue's own example domain. Every
  "after" example in Markdown writes symbols as mapped code spans. The
  thesis forms (`\(d\)`) appear once, in the section on `.tex`.
- **Wilkes is ideas only.** The guide states no licence. The reference
  paraphrases it, quotes nothing and copies no example. The credit goes
  in WRITING-STANDARDS' Sources as a fourth entry, separated from the
  three openly licensed works because it is not one of them.
- **Version: MINOR**, 6.159.1 → 6.160.0, because it changes what two
  drafting skills do. Re-read `main`'s version just before committing.
  If another PR has taken 6.160.0, take the next minor.

## Global constraints

- `tests/test_skill_size.py` caps: textbook-chapter-writer 33,000 bytes
  (largest copy 32,092 today), thesis-chapter-writer 34,000 (largest
  copy 33,748, which leaves **252 bytes**). Neither cap is raised.
- The reference names no skill in backticks and no harness tool
  (`Edit`, `Write`, `Read` …): see `test_neutral_files_name_no_skill_or_tool`.
- All three harness copies of a SKILL.md get the same edit
  (`.claude/skills/<s>/`, `.agents/skills/<s>/`, `.opencode/skills/<s>-opencode/`).
- No citekey appears anywhere in the new text (CLAUDE.md's one rule).
- House prose style: plain sentences, `--` for dashes as the skills
  already use, no em dashes.

## Review focus

1. **A thesis writer told to write a `## Symbols` row.** `.tex` units
   have no `math.md`, so the reference's section on `.tex` must say that
   the thesis's own front matter holds its list of symbols and that the
   skill does not write it. Task 1's test asserts that sentence exists.
2. **Rule 1 contradicting #1147.** The role word in the defining
   sentence must agree with the symbol's `## Symbols` meaning. The
   reference must never suggest writing the meaning a second time
   anywhere other than the prose sentence. Reviewers check this by
   reading the file.
3. **The thesis pointer pushing the copy over 34,000 bytes.** If the
   pointer does not fit, shorten an adjacent sentence in the same step
   instead of raising the cap. `test_skill_size.py` is the check.
4. **A copy drifting.** The pointer text must be the same across the
   three copies. `test_the_copies_of_a_skill_cite_the_same_sections` and
   the new test only check `.claude`, so Task 1 and Task 2 run a `diff`
   of the three copies' changed lines.
5. **Verbatim reuse of Wilkes.** A reviewer reads the reference beside
   the guide (DPMMS, rev. 2023-10-08) if they have it. No sentence or
   example should be the guide's.

---

### Task 1: The reference file and the textbook pointer

**Files:**
- Create: `.claude/skills-common/references/mathematical-prose.md`
- Modify: `.claude/skills/textbook-chapter-writer/SKILL.md` (the
  "**Equations follow `docs/WRITING-STANDARDS.md` §12 …**" paragraph in
  step 7, and the House-style bullet "Notation is introduced once …"),
  plus the same lines in `.agents/skills/textbook-chapter-writer/SKILL.md`
  and `.opencode/skills/textbook-chapter-writer-opencode/SKILL.md`
- Test: `tests/test_skill_references.py`

**Interfaces:**
- Produces: the path `.claude/skills-common/references/mathematical-prose.md`,
  which Task 2 and Task 3 point at; the constant `_MATH_PROSE` and the
  tuple `_MATH_PROSE_GENRES` in the test file, which Task 2 extends.

- [ ] **Step 1: Write the failing test** in `tests/test_skill_references.py`,
  after the `_CONDITIONAL` block:

```python
# Both chapter genres read the mathematical-prose rules on every run
# (#1135): the sentences around a symbol, which no check sees.
_MATH_PROSE = ".claude/skills-common/references/mathematical-prose.md"
_MATH_PROSE_GENRES = ("textbook-chapter-writer",)


@pytest.mark.parametrize("name", _MATH_PROSE_GENRES)
@pytest.mark.parametrize("harness", sorted(ROOTS))
def test_each_maths_genre_reads_the_mathematical_prose_reference(name, harness):
    text = (folder(harness, name) / "SKILL.md").read_text(encoding="utf-8")
    assert f"Read `{_MATH_PROSE}` now" in " ".join(text.split())


def test_the_mathematical_prose_reference_keeps_thesis_symbols_out_of_math_md():
    text = " ".join((REPO_ROOT / _MATH_PROSE).read_text(encoding="utf-8").split())
    assert "front matter" in text and "## Symbols" in text
```

- [ ] **Step 2: Run it and check that it fails**

Run: `PYTHONPATH=$PWD /home/prasad/git/chitragupta-freja/.venv-full/bin/python -m pytest tests/test_skill_references.py -k mathematical_prose -v`
Expected: FAIL (the file does not exist; no SKILL.md says "Read … now").

- [ ] **Step 3: Write the reference.** A one-paragraph opening says what
  the file governs: the prose around symbols and derivations. How a
  symbol is set belongs to WRITING-STANDARDS §12 and `math.md`, and the
  opening links both. Then one `##` section per rule, **each with exactly two
  before/after examples** in the greenhouse domain (the issue's
  acceptance criterion), in this order:

  1. **Define a symbol in its own sentence**, at the start of a line,
     with its type or unit and a role word. "Let `d` be the drying rate,
     in percentage points per hour." The role word agrees with the
     symbol's `## Symbols` row in `math.md` (the linked glossary term, or
     the words). The meaning is written in the table once, and the
     sentence is where the reader meets it.
  2. **Repeat the role word on reuse after a gap**: "the drying rate
     `d`". A gap is a new `##`/`###` section, or three or more paragraphs
     since the symbol's last mention.
  3. **Choose letters on purpose.** Prefer mnemonic letters (`d` for
     drying, `V` for volume). Keep regions consistent: `i, j, k, n` for
     indices and counts, `t` for time, `T_` for intervals and periods,
     `a, b, c` for constants fitted from data, and Greek for model
     parameters. One letter means one thing. In a book, `registry check`
     reports a symbol naming two things, but the clash is cheaper to
     avoid than to fix.
  4. **Write the "then".** Every "if" has its consequence stated, and no
     sentence starts with a symbol.
  5. **Claim first, conclusion last.** State what a derivation will show
     before the first step, and close it with "so we have shown …",
     restating the claim.
  6. **Keep the argument linear.** One paragraph per step, each opening
     with what it does ("Substituting the dose …"). There is no
     boxes-and-arrows argument map. A figure is for the objects, not
     for the logic.
  7. **Say which condition you checked.** Before applying a result, name
     its condition and the fact that meets it ("the dose is below the
     pot's capacity, so the linear model applies").
  8. **Where the notation table lives.** A Markdown draft writes no
     extra table: `math.md`'s `## Symbols` is the table, and a book
     prints it as its List of Symbols. When a section introduces many
     objects at once, a map figure (drawn through the figure step) can
     earn its place. A `.tex` unit has no `math.md`. Its symbols go in
     the thesis's own front matter, which the user owns and the skill
     never writes. This section shows rules 1 and 2 once in `\(d\)` form.

  Close with a "Source" paragraph: the ideas are Wilkes's, *A Brief
  Guide to Mathematical Writing* (§1 Diagrams, §2 Notation and
  definitions, §3 Formatting and structuring proofs), paraphrased, with
  no licence stated. Add a link to WRITING-STANDARDS' Sources.

- [ ] **Step 4: Point the textbook skill at it** in all three copies.
  - Put the sentence "Read `.claude/skills-common/references/mathematical-prose.md`
    now and follow it: it governs the sentences around every symbol and
    derivation." at the start of step 7's "**Equations follow …**"
    paragraph.
  - Replace the House-style bullet "Notation is introduced once, with a
    worked instance beside it, and never silently reused with a changed
    meaning in a later section." with "- Notation follows the
    mathematical-prose reference read in step 7, with a worked instance
    beside each new symbol."
  - Then check that the three copies changed the same lines:
    `git diff -U0 -- '*textbook-chapter-writer*/SKILL.md' | grep '^[-+][^-+]' | sort | uniq -c`.
    Every line should show count 3.

- [ ] **Step 5: Run the skill tests**

Run: `PYTHONPATH=$PWD /home/prasad/git/chitragupta-freja/.venv-full/bin/python -m pytest tests/test_skill_references.py tests/test_skill_size.py tests/test_skill_harness_copies.py -q`
Expected: all pass, including the three new parametrised cases and the
orphan test (`test_every_neutral_file_is_named_by_some_skill`).

- [ ] **Step 6: Commit**

```bash
git add .claude/skills-common/references/mathematical-prose.md \
  .claude/skills/textbook-chapter-writer/SKILL.md \
  .agents/skills/textbook-chapter-writer/SKILL.md \
  .opencode/skills/textbook-chapter-writer-opencode/SKILL.md \
  tests/test_skill_references.py
git commit -m "Give the textbook skill the mathematical-prose rules (#1135)"
```

### Task 2: The thesis pointer

**Files:**
- Modify: the "**An equation gets the same carve-out …**" paragraph in
  `.claude/skills/thesis-chapter-writer/SKILL.md`,
  `.agents/skills/thesis-chapter-writer/SKILL.md` and
  `.opencode/skills/thesis-chapter-writer-opencode/SKILL.md`
- Test: `tests/test_skill_references.py`

**Interfaces:**
- Consumes: `_MATH_PROSE`, `_MATH_PROSE_GENRES` from Task 1.

- [ ] **Step 1: Extend the test.** Set `_MATH_PROSE_GENRES = ("textbook-chapter-writer", "thesis-chapter-writer")`.
- [ ] **Step 2: Run** the `-k mathematical_prose` command from Task 1.
  Expected: three thesis cases FAIL.
- [ ] **Step 3: Add the same "Read … now and follow it" sentence** at the
  start of the equation paragraph in all three copies. The largest copy
  has 252 bytes of room and the sentence is about 160. If a copy goes
  over, cut "same as any other LaTeX document" from the paragraph's
  "Write ordinary math …" sentence rather than raising the cap.
  Then run the same three-copy `diff` check as in Task 1.
- [ ] **Step 4: Run** the Task 1 Step 5 command. Expected: all pass.
- [ ] **Step 5: Commit** the three SKILL.md copies and the test file:
  "Give the thesis skill the mathematical-prose rules (#1135)".

### Task 3: WRITING-STANDARDS pointer, credit and version

**Files:**
- Modify: `docs/WRITING-STANDARDS.md` (a new `### ✍ Prose around the
  maths` subsection at the end of §12, after "🔢 A number for a chosen
  few …" and before `## 🔢 13. Tables`; and Sources)
- Modify: `pyproject.toml` (`version`)

- [ ] **Step 1: Write the §12 subsection.** It is at most one short
  paragraph: §12 says how a symbol is set, the reference says how the
  sentence around it reads, and the subsection links
  `../.claude/skills-common/references/mathematical-prose.md` with the
  rule list in one line.
- [ ] **Step 2: Credit Wilkes.** After item 3 in "📖 Sources and
  attribution", add a paragraph headed "**Ideas, not text, from one
  further work.**" Give the full citation (the author's name as the guide's title page
  gives it, *A Brief
  Guide to Mathematical Writing*, Department of Pure Mathematics and
  Mathematical Statistics, University of Cambridge, revised
  2023-10-08), state that no licence is stated, that nothing is quoted,
  and which sections supplied which rules. Leave the "Three openly
  licensed works" sentence as is, because it stays true.
- [ ] **Step 3: Bump the version** to 6.160.0, after re-reading
  `origin/main`'s `pyproject.toml`.
- [ ] **Step 4: Run the docs and version checks**

Run: `PYTHONPATH=$PWD /home/prasad/git/chitragupta-freja/.venv-full/bin/python -m pytest tests/test_docs_pins.py tests/test_features_doc.py tests/test_skill_references.py tests/test_skill_size.py tests/test_skill_harness_copies.py -q && /home/prasad/git/chitragupta-freja/.venv-full/bin/python scripts/check_version_bump.py --offline`
Expected: all pass, and the bump check accepts the new version.

- [ ] **Step 5: Commit** `docs/WRITING-STANDARDS.md` and `pyproject.toml`:
  "Point WRITING-STANDARDS §12 at the mathematical-prose rules and credit Wilkes (#1135)".

### Task 4: Review, PR, issue upkeep

- [ ] **Step 1: Agent review** of the branch against this plan. Put
  Review focus items 2 and 5 in front of the reviewer. `ocr` skips
  `.md`, so it adds nothing here.
- [ ] **Step 2: Open the PR** with `Closes #1135`. The body says that
  the check and the symbols table were delivered by #1147, with the
  measurement above, and lists the version.
- [ ] **Step 3: Comment on #1135** with the same split, so that the
  issue's unchecked "`draft style` reports …" idea is visibly accounted
  for.
- [ ] **Step 4: After merge,** tag and release as
  DEVELOPER-AGENTS.md describes. The tag is minor, so PyPI publishes
  too.
