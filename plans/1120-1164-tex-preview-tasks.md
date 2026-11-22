# `.tex` preview fixes: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **built** (v6.179.1), written 2026-11-22.

**Goal:** a `.tex` draft's tex/pdf preview keeps its figures at full
width, wraps absolute-width tables, numbers its headings so `\ref`
names one, titles its reference list, and loads an optional thesis
preamble file, with a hint naming that file when a command is
undefined.

**Architecture:** one new module, `chitragupta/render_output/_tex_preview.py`,
owns every decision about a `.tex` draft's preview: the text rewrite
(widths, lone `\centering`), the pandoc arguments (reader, numbering,
references title, preamble), and where the preamble file is. The
existing code gets one-line hooks only, because `__init__.py` is at the
250-code-line limit and `_pandoc_command` and `render` are at 24 of 25
statements (`scripts/code_standards.py`).

**Tech Stack:** Python 3.13+, pandoc (3.1.11 here), LuaLaTeX, pytest
(`slow` for TeX compiles).

**Spec:** [plans/1120-1164-tex-preview.md](1120-1164-tex-preview.md)

## Global Constraints

- Branch `fix-1120-1164-tex-preview`, rebased on `main` before Task 1.
- Only a `.tex` draft's **non-fragment** renders change. A Markdown
  draft's renders, and every `--fragment` render, are byte for byte what
  they were.
- The reader change (`-f latex+raw_tex`) and `--number-sections` apply
  to LaTeX-bound outputs (`tex`, `latex`, `pdf`) only.
- The draft file on disk is never changed.
- The author's preamble file loads before the font header, which stays
  last.
- No module crosses C1 (25 statements a function) or C2 (250 code lines
  a module); check with `python scripts/code_standards.py <files>`.
- The skill never writes the preamble file (decision 4).
- PATCH version bump, read from `main` at the end.
- No citekey in any fixture beyond the existing test bib conventions;
  never fabricate one.

## Review Focus

1. A `p{}` width inside a cell's text, not a column spec (`\parbox{2cm}`,
   `\rule{3cm}{1pt}`), must not be rewritten. Task 1 pins it.
2. A `\centering` outside a figure (in a `table` float, in a `center`
   block) must stay. Task 1 pins it.
3. A raw `\input{/etc/hostname}` in a `.tex` draft must still be refused
   by the #823 fence under the new reader. Task 2 pins it (slow).
4. A `.tex` draft with neither preamble file renders with no
   `--include-in-header` for one, and a `.preamble.tex` file is
   preferred over a shared `preamble.tex`. Task 1 pins it.
5. A pandoc failure on a Markdown draft, or one with no
   `Undefined control sequence`, gets no new hint. Task 3 pins it.

---

### Task 1: `_tex_preview.py`, pure Python

**Files:**

- Create: `chitragupta/render_output/_tex_preview.py`
- Test: `tests/test_render_output_tex_preview.py` (new; no pandoc)

**Interfaces (produced):**

- `is_tex_draft(input_path: Path) -> bool`: suffix not in
  `_paths._MARKDOWN_SUFFIXES`.
- `preamble_file(input_path: Path) -> Path | None`:
  `<dir>/<stem>.preamble.tex` if it is a file, else `<dir>/preamble.tex`
  if it is a file, else `None`.
- `widths_as_fractions(text: str, text_width_pt: float) -> str`: in the
  column spec of every `\begin{tabular}`, `tabular*`, `longtable` and
  `tabularx` (the braced argument after the environment name, after
  `tabular*`/`tabularx`'s width argument and any `[pos]`), each
  `p{N<unit>}`, `m{...}`, `b{...}` with unit `cm`, `mm`, `in`, `pt` or
  `bp` becomes `p{F\linewidth}` with `F` = width in pt / `text_width_pt`,
  four decimals. Factors: cm 28.4528, mm 2.84528, in 72.27, pt 1,
  bp 1.00375.
- `without_lone_centering(text: str) -> str`: inside every
  `\begin{figure}`/`figure*` ... `\end{...}`, delete each `\centering`
  together with the whitespace after it.
- `rewrite(text: str, input_path: Path, output_format: str, fragment: bool) -> str`:
  unchanged unless `is_tex_draft` and not `fragment`; then
  `widths_as_fractions(text, ARTICLE.text_width_pt)`, plus
  `without_lone_centering` when `output_format` is LaTeX-bound.
- `pandoc_args(input_path: Path, output_format: str, fragment: bool) -> list[str]`:
  `[]` unless `is_tex_draft` and not `fragment`. Otherwise
  `["--metadata", "reference-section-title=References"]`, plus, when
  LaTeX-bound, `["-f", "latex+raw_tex", "--number-sections"]`, plus
  `["--include-in-header", str(preamble)]` when `preamble_file` finds one.

- [ ] **Step 1: Write the failing tests**

```python
def test_absolute_widths_become_fractions_of_the_text_width():
    spec = "\\begin{tabular}{p{2.6cm}p{4.5cm}l}\nA & B & C \\\\\n\\end{tabular}"
    out = widths_as_fractions(spec, 452.97)
    assert "p{0.1633\\linewidth}p{0.2827\\linewidth}l" in out

def test_relative_widths_and_cell_text_are_left_alone():
    text = ("\\begin{tabular}{p{0.2\\linewidth}l}\n\\parbox{2cm}{x} & "
            "\\rule{3cm}{1pt} \\\\\n\\end{tabular}")
    assert widths_as_fractions(text, 452.97) == text

def test_tabularx_and_longtable_specs_are_read_after_their_arguments():
    text = "\\begin{tabularx}{\\linewidth}[t]{p{1in}X}\\end{tabularx}"
    assert "p{0.1595\\linewidth}X" in widths_as_fractions(text, 452.97)

def test_em_widths_are_left_alone():
    text = "\\begin{tabular}{p{10em}}\\end{tabular}"
    assert widths_as_fractions(text, 452.97) == text

def test_a_figures_centering_is_dropped_and_others_kept():
    text = ("\\begin{figure}[t]\\centering\n\\input{figures/f.tex}\n\\end{figure}\n"
            "\\begin{table}\\centering x\\end{table}")
    out = without_lone_centering(text)
    assert "\\begin{figure}[t]\\input{figures/f.tex}" in out
    assert "\\begin{table}\\centering x" in out

def test_rewrite_leaves_markdown_and_fragments_alone(tmp_path):
    md, tex = tmp_path / "a.md", tmp_path / "a.tex"
    text = "\\begin{tabular}{p{2cm}}\\end{tabular}"
    assert rewrite(text, md, "pdf", False) == text
    assert rewrite(text, tex, "pdf", True) == text
    assert "\\linewidth" in rewrite(text, tex, "docx", False)

def test_the_drafts_own_preamble_beats_the_shared_one(tmp_path):
    draft = tmp_path / "ch.tex"
    assert preamble_file(draft) is None
    (tmp_path / "preamble.tex").write_text("", encoding="utf-8")
    assert preamble_file(draft) == tmp_path / "preamble.tex"
    (tmp_path / "ch.preamble.tex").write_text("", encoding="utf-8")
    assert preamble_file(draft) == tmp_path / "ch.preamble.tex"

def test_pandoc_args_by_draft_kind_and_format(tmp_path):
    tex = tmp_path / "ch.tex"
    assert pandoc_args(tmp_path / "a.md", "pdf", False) == []
    assert pandoc_args(tex, "pdf", True) == []
    assert pandoc_args(tex, "md", False) == ["--metadata", "reference-section-title=References"]
    pdf = pandoc_args(tex, "pdf", False)
    assert pdf[:2] == ["--metadata", "reference-section-title=References"]
    assert {"-f", "latex+raw_tex", "--number-sections"} <= set(pdf)
    assert "--include-in-header" not in pdf
    (tmp_path / "ch.preamble.tex").write_text("", encoding="utf-8")
    assert pandoc_args(tex, "tex", False)[-2:] == ["--include-in-header", str(tmp_path / "ch.preamble.tex")]
```

Compute the expected fractions before writing them in
(2.6 × 28.4528 / 452.97 and so on) and fix the literals if a digit
differs; the rule, not the literal, is the requirement.

- [ ] **Step 2: Run**
  `python -m pytest tests/test_render_output_tex_preview.py -q`.
  Expected: collection error, module missing.
- [ ] **Step 3: Write `_tex_preview.py`** to the interfaces above. A
  module docstring states why it exists (the two issues, raw_tex's
  cost) and what it leaves alone (em/ex widths, Markdown, fragments).
- [ ] **Step 4: Run** the same command. Expected: all pass, and
  `--cov=chitragupta.render_output._tex_preview --cov-branch` 100%.
- [ ] **Step 5: Commit** (`Add the .tex preview's rewrite and pandoc arguments`).

---

### Task 2: wire it in, with end-to-end tests (#1164, #1120)

**Files:**

- Modify: `chitragupta/render_output/_substitution.py` (`_substituted`)
- Modify: `chitragupta/render_output/_pandoc.py` (`_pandoc_command`)
- Test: `tests/test_render_output_tex_preview.py` (pandoc tests,
  `skipif(not pandoc_available)`; the pdf ones `slow` + `needs_tikz`)

**Interfaces (consumed):** `rewrite`, `pandoc_args` from Task 1.

- [ ] **Step 1: Write the failing tests**, each rendering a `.tex` draft
  under `isolated_config.DRAFTS_DIR` with `render_output.render(...,
  output_format="tex")` and reading the output:
  - `test_a_tex_drafts_figure_reaches_the_tex_output`: `figure_pair`
    plus a draft `\section{A}\n\begin{figure}\centering\n\input{figures/fig1.tex}\n\caption{C.}\label{fig:c}\end{figure}`;
    assert `\input{figures/fig1.tex}` is in the output and `minipage`
    is not.
  - `test_a_tex_drafts_ref_is_left_to_latex_and_headings_are_numbered`:
    `#1120`'s `th.tex` minus the citation; assert `\ref{sec:framing}` in
    the output, `hyperref[sec:framing]` not, and
    `secnumdepth}{-\maxdimen}` not.
  - `test_a_tex_drafts_absolute_widths_survive_as_fractions`: assert
    `\linewidth` in the column spec and `@{}lll@{}` not.
  - `test_a_tex_drafts_reference_list_has_a_heading`: one `\citep{}` of
    a key in the test bib (use the file's existing bib fixture pattern);
    assert `References` heads the `CSLReferences` block.
  - `test_a_markdown_draft_and_a_fragment_render_as_before`: render a
    Markdown draft to tex and a `.tex` draft with `fragment=True`;
    assert neither output has `-f`-driven changes: no `--number-sections`
    numbering (`secnumdepth}{-\maxdimen}` present for the Markdown one),
    no `References` title.
  - `slow`, `needs_tikz`: `test_a_tex_drafts_pdf_renders_with_its_figure`:
    the figure draft rendered to `pdf` succeeds. (That the figure is in
    it is the `tex` test's job: the pdf is built from that same `.tex`.)
  - `slow`: `test_the_read_fence_still_refuses_an_input_outside_the_draft`:
    a `.tex` draft holding `\input{/etc/hostname}`; `pytest.raises(subprocess.CalledProcessError)`
    on a pdf render.
  - `slow`: `test_a_thesis_macro_renders_once_the_preamble_defines_it`:
    a draft using `\todo{x}` fails the pdf render; with
    `\newcommand{\todo}[1]{}` in `<stem>.preamble.tex` it succeeds.
- [ ] **Step 2: Run** them. Expected: each fails on today's code
  (figure dropped, `hyperref[...]`, `lll`, no heading); the
  Markdown/fragment test passes (it is the guard); the fence test
  passes (guard); the macro test fails on the second render.
- [ ] **Step 3: Hook it in.** In `_substituted`, one statement before
  `declared = ...`: `draft_text = _tex_preview.rewrite(draft_text,
  input_path, output_format, fragment)`. In `_pandoc_command`, one
  statement immediately before `cmd += _floats.preamble_args(...)`:
  `cmd += _tex_preview.pandoc_args(input_path, output_format, fragment)`.
  The font header is appended later, inside the `pdf` branch, so it
  stays last.
- [ ] **Step 4: Run** the new file plus `tests/test_render_output.py`,
  `tests/test_render_output_figures.py`, `tests/test_render_output_cli.py`
  and `python scripts/code_standards.py chitragupta/render_output`.
  Expected: all pass; no C1/C2 finding.
- [ ] **Step 5: Commit**
  (`Keep a .tex draft's figures, widths, numbers and references in its preview`).

---

### Task 3: the hint, and `draft diff`'s preamble

**Files:**

- Modify: `chitragupta/render_output/_cli.py` (a third hint beside
  `_unicode_repair_hint`, appended in the `CalledProcessError` branch)
- Modify: `chitragupta/draft_diff/_cli.py` (copy the preamble beside
  each side)
- Test: `tests/test_render_output_cli.py`, `tests/test_draft_diff*.py`
  (the existing file that covers `_render_sides` or its caller)

**Interfaces:**

- `_undefined_command_hint(stderr: str | None, input_arg: str) -> str`:
  `""` unless `input_arg` is a `.tex` draft and `stderr` holds
  `Undefined control sequence`. The command is the last `\name` on the
  `l.<n>` line after that error. For `cite`, `citep`, `citet`, `citealp`
  and `citeauthor`: "a citation inside a command pandoc does not know is
  not resolved in the preview; move it out of that command". Otherwise:
  "the preview loads none of your thesis's preamble: define `\<name>`
  in `<dir>/<stem>.preamble.tex` (or a shared `preamble.tex` beside the
  draft)". Without a readable command, the same line with "the
  undefined command".

- [ ] **Step 1: Write the failing tests**: the hint for `\todo`; for
  `\citep`; for a stderr with no `l.` line; `""` for a `.md` input; `""`
  for a stderr without the error. A `draft diff` test: with
  `<stem>.preamble.tex` beside the draft, both side directories get a
  copy named after the side's stem.
- [ ] **Step 2: Run** them. Expected: fail (no function; no copy).
- [ ] **Step 3: Implement.** In `draft_diff/_cli.py`, after `prepare(...)`
  returns the two sides: if `_tex_preview.preamble_file(draft)` is not
  `None`, copy it to `src.with_name(f"{src.stem}.preamble.tex")` for
  each side.
- [ ] **Step 4: Run** the two test files and
  `python scripts/code_standards.py chitragupta/render_output chitragupta/draft_diff`.
  Expected: pass; no finding.
- [ ] **Step 5: Commit**
  (`Name the thesis preamble file when a .tex preview hits an undefined command`).

---

### Task 4: docs, version, checks, PR, merge

**Files:** `docs/RENDERING-FLOW.md`, `docs/WRITE-A-THESIS-CHAPTER.md`,
`.claude/skills/thesis-chapter-writer/SKILL.md` (step 12) or its
`references/thesis.md`, `pyproject.toml`, both plan files' Status lines.

- [ ] **Step 1: Docs.** RENDERING-FLOW.md: drop the first "Open gaps"
  bullet, add the md preview's section numbers as a gap, rewrite the
  figure table's fourth row, and describe the `.tex` path's reader,
  numbering, width rewrite, references title and preamble file.
  WRITE-A-THESIS-CHAPTER.md: the preamble file, beside the book guide's
  `preamble.tex` wording. The skill: quote the hint, name the command,
  leave the file to the user, never write it.
- [ ] **Step 2: Sweep** for `raw_tex`, `Open gaps`, `no-op by design`,
  `secnumdepth` and `reference-section-title` across `docs`,
  `.claude/skills` and `chitragupta`
  and fix every sentence this branch made false.
- [ ] **Step 3: Measure** every `.tex` draft under `docs/examples/` and
  `/workspace/content/drafts/` (if any): render `tex` on `main` and on
  this branch, and read the differences; each must be one of the four
  intended changes.
- [ ] **Step 4: Bump** `main`'s PATCH in `pyproject.toml`.
- [ ] **Step 5: Fable reviews the branch** (user's instruction); one fix
  pass for Critical/Important, each test-first.
- [ ] **Step 6: Local checks**, after the fix pass: `python -m pytest -n
  auto --cov --cov-report=term-missing` (100%) and
  `bash scripts/check_local.sh` (exit 0).
- [ ] **Step 7: OpenCodeReview** `delegate-review`; act on findings.
- [ ] **Step 8: PR** with the template; `python scripts/merge_pr.py --check`
  on the body; wait for CI green; if `main` moved, rebase, re-bump,
  re-check.
- [ ] **Step 9: Merge** with `python scripts/merge_pr.py <N>`; confirm
  #1120 and #1164 closed and comment on #1108 that item 6 is done.
