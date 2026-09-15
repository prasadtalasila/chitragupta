# #781: hoist `\usetikzlibrary` out of figure floats

Status: **plan, built.** Written 2026-09-15 and built the same day.
Four things changed on the way, all forced by this repository's own size
rules and worth reading before the tasks below:

1. **There is no `tikz_libraries` parameter on `_pandoc_command`.**
   `render_output/__init__.py` sits one line under C2's 250-line limit
   on `main`, so the two lines Task 2 wanted there did not fit.
   `_pandoc_command` already receives `figure_refs` and `input_path`, so
   it derives the union itself and `__init__.py` is untouched.
2. **Tasks 2 and 3 are one commit**, for the same reason: the fragment
   report lives in `_tikz_libraries.preamble_libraries()` beside the
   union it reports, not in `render()`.
3. **`figure_layout/__init__.py` grew 3 lines (257 -> 260)**, which is a
   registered C2 offender, so `code-standards-register.toml` records the
   new count and the entry moves one place worst-first. Visible debt
   growth, which is what that register is for.
4. **`_figure_lines` crossed C1's 25-statement limit** when the finding
   was added, so its `stranded` and `by_hand` loops are comprehensions.

Implements
[#781](https://github.com/prasadtalasila/chitragupta/issues/781), "[BUG]
Incorrect rendering of figures in a book": TikZ figures that fit in a
single-chapter PDF have their node spacing multiplied several-fold in an
assembled `book.pdf`, because `\usetikzlibrary` runs inside a `figure`
float and the per-figure workarounds for that are themselves global.

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** the renderer collects the union of `\usetikzlibrary` names a
draft's figure files ask for and loads them **once, in the preamble**, so
no library is ever loaded inside a float and no figure file needs a
workaround.

**Architecture:** one new collector module under
`chitragupta/render_output/`, read by `_pandoc.py`'s existing
`header-includes` mechanism (the same shape `fvextra` and `\LTcapwidth`
already use); a stderr report of the union for `--fragment`, which has no
preamble of its own, consumed by `book-assembler`; a source-level check
in the `review figure` aid that flags a figure file still carrying a
hand-rolled load; and the convention documents rewritten to match.

**Tech stack:** Python 3.12 (CI) / 3.13 (this host), pytest, pandoc +
pdflatex + TeX Live (`texlive-pictures` for `tikz.sty`).

**Spec:** the issue body of
[#781](https://github.com/prasadtalasila/chitragupta/issues/781), whose
"Root cause" section is the mechanism this plan is argued from, plus
[docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md) for the convention being
changed.

**Written for** whoever builds it. **Assumed:**
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10 for the
two-form figure contract and the `figure:` marker,
[docs/BOOKS.md](../docs/BOOKS.md) and
`.claude/skills/book-assembler/SKILL.md` for how a unit becomes a
chapter, and [DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the
commit, lint and release conventions. **Not covered here:** the
`pgfplots` work in [docs/FIGURE-ROADMAP.md](../docs/FIGURE-ROADMAP.md)
Part VII, which needs the same `header-includes` mechanism for a
*package* rather than a library and is a separate item; and anything
about figure *content*, which `review figure` and TIKZ-STYLE.md already
own.

---

## Why a plan at all

[plans/README.md](README.md) says not to write one for a mechanical
change. Two of its three triggers fire here:

- **The design is underdetermined at the fragment boundary.** A
  `--fragment` render emits no preamble, so the union has to reach the
  assembling document by some channel that does not exist yet. Whether
  that is a stderr line, a JSON surface or a sidecar file is a contract a
  later reviewer could not tell from an accident.
- **It changes an artefact other work depends on.** Every figure file in
  every drafted book carries a `\usetikzlibrary` line today, and two
  generations of workaround are sitting in trees this repository cannot
  see. The migration question is real, and item 8 below is where it is
  answered rather than left to whoever hits it.

---

## The mechanism, stated once

This is the part every task below depends on, so it is stated here and
not repeated.

`\usetikzlibrary{positioning}` does two things with different scopes. It
defines the library's macros **locally** -- so they die at the end of the
group, and a `figure` float is a group -- and it sets
`\tikz@library@positioning@loaded` **globally**, so the *next* float sees
the flag, skips the load, and finds none of the macros. That is the
first-order bug: `right=6mm of x` fails in the second figure.

The workarounds make it worse rather than better.
`tikzlibrarypositioning.code.tex:29` does a
`\pgfutil@g@addto@macro\tikz@node@reset@hook{...}` -- a *global* append --
on every load. So clearing the flag and reloading per figure (the first
generation) appends the placement transform once per figure, and by the
Nth figure every node's shift is applied N times. Saving and restoring
the hook (the second generation) is correct only in a document where
*every* figure is second-generation; in a book where the two meet, the
second generation saves an already-polluted hook as "pristine".

**The fix is to load once, ungrouped, before any float.** The preamble
load sets the flags and appends the hook exactly once; a figure file's
own `\usetikzlibrary` line then finds the flag already set and is a
no-op that appends nothing. That is why the figure file **keeps** its
plain load line and only the workarounds are removed:

- `thesis-chapter-writer`'s `.tex` fragment is `\input` into the user's
  own thesis, whose preamble this pipeline never writes. Strip the line
  and that genre's figures break outside this pipeline entirely.
- `review figure`'s probe and WRITING-STANDARDS.md §10's compile check
  both build a minimal document around the figure file and rely on the
  file to say what it needs.

The issue's own verified fix says the same thing: preamble load **plus**
workarounds removed; "Preamble load alone is NOT enough while
first-generation files still reload."

**Both halves verified on this host before this plan was written**, with
the documents Task 7 builds -- a `book`-class file inputting one
`positioning` figure (`\node[draw,right=20mm of a] (b)`) into several
`figure` floats, reading back `(b)`'s *x* with `\pgfpointanchor`:

| Document | node *x* per float | `pdflatex` | `Overfull` |
| --- | --- | --- | --- |
| library loaded in the preamble | `71.26312pt`, `71.26312pt` | exit 0 | 0 |
| loaded only inside the floats | `71.26312pt`, `7.07465pt` | exit **1** | -- |
| flag cleared and reloaded per float | `71.26312pt`, `128.16862pt`, `185.07413pt` | exit **0** | 0 |

Row 2 is the grouping bug, and its message is the one TIKZ-STYLE.md
already quotes: `! Package PGF Math Error: Unknown operator 'o' or 'of'
(in '20mm of a')`. Row 3 is the issue's actual reported symptom --
spacing growing by a constant `56.9pt` per figure, with `pdflatex`
exiting 0 and nothing in the log, because the placement transform has
been appended to the global `\tikz@node@reset@hook` once per load.
Neither is an inference; both are the mechanism this plan fixes.

## Global constraints

Every task's requirements implicitly include these.

- **Never fabricate a citekey** ([CLAUDE.md](../CLAUDE.md)). Nothing in
  this plan touches citekeys; the fixture figure files below must contain
  none, or `_figure_warnings` will flag them.
- **Byte-identical output over unchanged input**
  ([docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md), "Repeatable").
  The library union is emitted **sorted**; a bare `set` iterates in hash
  order and Python randomises string hashing per process, so an unsorted
  union changes the preamble between runs.
- **250-line file limit** (docs/CODE-STANDARDS.md; docstrings count,
  comments do not). `_figures.py` is 345 lines and already registered in
  `code-standards-register.toml`; growing a registered offender reddens
  the suite. That is why the collector is a new module.
- **Dependency direction.** `chitragupta/review/figure_layout/` imports
  `chitragupta.render_output._figures`, never the reverse. The collector
  therefore lives in `render_output/` and the review-layer check imports
  *from* it.
- **CI enforces 100% coverage** and CI's tests run on Python 3.12 while
  this host is 3.13. Every new branch needs a test that runs *without*
  TeX Live, because most of this aid's tests are written to run on a host
  with no TeX at all.
- **Every PR bumps the version** in `pyproject.toml` (docs-only
  included). `main` is at `6.107.0` at the time of writing and moves
  during a PR -- re-read it before pushing.

## Before the first test run, in this worktree

```bash
cp config.toml.example config.toml   # a worktree has none; 15 tests fail without it
git fetch origin && git log --oneline -1 origin/main   # diff against origin/main, never local main
```

Every command below is written `.venv-full/bin/python`, which is the
in-pin environment. **It lives at the repository root, not in a
worktree** -- from a worktree, spell it `/workspace/.venv-full/bin/python`
(or wherever the primary checkout is). `.venv-313` is out of pin; do not
reach for it. Note also that the local interpreter is 3.13 while CI's
tests run on 3.12, and there is no 3.12 on this host -- nothing in this
plan uses a version-sensitive API, but a 3.13-only one would pass
everything here and fail both CI test legs.

## File structure

| File | Responsibility |
| --- | --- |
| `chitragupta/render_output/_tikz_libraries.py` (**new**) | Read `\usetikzlibrary` names out of figure source; the sorted union over a draft's figures; the `header-includes` string. Also the canonical TeX-comment stripper, moved here. |
| `chitragupta/render_output/_pandoc.py` | Emit `\usepackage{tikz}\usetikzlibrary{...}` as one `header-includes` value. |
| `chitragupta/render_output/__init__.py` | Compute the union; pass it down; report it on stderr for `--fragment`. |
| `chitragupta/review/figure_layout/_source.py` | New `loads_library_by_hand()` check; re-export `strip_comments` from its new home. |
| `chitragupta/review/figure_layout/_result.py` | New `by_hand` field, counted in `has_findings`. |
| `chitragupta/review/figure_layout/_report.py` | The finding in all three output shapes. |
| `scripts/strip_tikz_load_workarounds.py` (**new**) | The migration, for trees this repository cannot see. |
| `.claude/skills/book-assembler/SKILL.md` | The book preamble carries the union. |
| `docs/TIKZ-STYLE.md`, `docs/WRITING-STANDARDS.md`, `docs/FIGURE-ROADMAP.md`, `docs/REVIEW.md`, `docs/CLI.md`, `assets/tikz/README.md` | The convention, and four now-false claims about what the renderer supplies. |
| `tests/test_render_output_tikz_libraries.py` (**new**), `tests/test_render_output_cli.py`, `tests/test_figure_layout.py`, `tests/test_tikz_library_scope.py` (**new**) | Cover. |

---

## Task 1: the collector

**Files:**

- Create: `chitragupta/render_output/_tikz_libraries.py`
- Modify: `chitragupta/render_output/__init__.py` (re-export, `__all__`
  untouched -- the package re-exports privates by name, see its comment
  at line 145)
- Modify: `chitragupta/review/figure_layout/_source.py` (import
  `strip_comments` from its new home instead of defining it)
- Test: `tests/test_render_output_tikz_libraries.py`

**Interfaces produced** (later tasks call these by these exact names):

```python
def strip_comments(source: str) -> str: ...
def libraries_in(source: str) -> list[str]: ...          # one file, source order, deduped
def library_union(figure_refs: list[str], draft_dir: Path) -> list[str]: ...  # sorted
def header_include(libraries: list[str]) -> str: ...     # the header-includes VALUE, no prefix
```

- [ ] **Step 1: write the failing tests**

```python
"""Collecting the TikZ libraries a draft's figures ask for (#781)."""

from pathlib import Path

from chitragupta.render_output import _tikz_libraries as tl


class TestLibrariesIn:
    def test_one_name(self):
        assert tl.libraries_in(r"\usetikzlibrary{positioning}") == ["positioning"]

    def test_a_comma_list_with_spaces(self):
        assert tl.libraries_in(r"\usetikzlibrary{positioning, fit}") == [
            "positioning",
            "fit",
        ]

    def test_a_dotted_name(self):
        assert tl.libraries_in(r"\usetikzlibrary{arrows.meta}") == ["arrows.meta"]

    def test_several_lines(self):
        source = "\\usetikzlibrary{positioning}\n\\usetikzlibrary{fit}\n"
        assert tl.libraries_in(source) == ["positioning", "fit"]

    def test_a_repeat_is_named_once(self):
        source = "\\usetikzlibrary{fit}\n\\usetikzlibrary{fit}\n"
        assert tl.libraries_in(source) == ["fit"]

    def test_a_commented_out_load_is_not_collected(self):
        # A commented load is inert in TeX, so collecting it would put a
        # library in the preamble the figure does not use -- and, if it
        # is misspelled, fail the whole render over a comment.
        assert tl.libraries_in("% \\usetikzlibrary{positioning}") == []

    def test_an_escaped_percent_does_not_start_a_comment(self):
        source = r"\draw (0,0) node {50\%}; \usetikzlibrary{fit}"
        assert tl.libraries_in(source) == ["fit"]

    def test_an_empty_call_yields_nothing(self):
        # `\usetikzlibrary{}` is fatal in TeX; it must not become an
        # empty name that we then re-emit.
        assert tl.libraries_in(r"\usetikzlibrary{}") == []

    def test_a_figure_with_no_load(self):
        assert tl.libraries_in(r"\begin{tikzpicture}\end{tikzpicture}") == []


class TestLibraryUnion:
    def _figure(self, tmp_path, name, body):
        path = tmp_path / "figures" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def test_union_over_two_figures(self, tmp_path):
        self._figure(tmp_path, "a.tex", r"\usetikzlibrary{positioning}")
        self._figure(tmp_path, "b.tex", r"\usetikzlibrary{fit,positioning}")
        assert tl.library_union(
            ["figures/a.tex", "figures/b.tex"], tmp_path
        ) == ["fit", "positioning"]

    def test_the_result_is_sorted(self, tmp_path):
        self._figure(tmp_path, "a.tex", r"\usetikzlibrary{positioning,arrows.meta,fit}")
        assert tl.library_union(["figures/a.tex"], tmp_path) == [
            "arrows.meta",
            "fit",
            "positioning",
        ]

    def test_a_missing_figure_is_skipped(self, tmp_path):
        # `_figure_warnings` is what tells the user about a missing
        # figure; this must not be a second, fatal report of the same
        # thing.
        assert tl.library_union(["figures/absent.tex"], tmp_path) == []

    def test_an_escaping_reference_is_not_read(self, tmp_path):
        # `_resolve_sibling`'s rule: a draft's own text is never a reason
        # to read outside its directory.
        assert tl.library_union(["../secrets.tex"], tmp_path) == []

    def test_unreadable_bytes_do_not_stop_the_render(self, tmp_path):
        path = tmp_path / "figures" / "bad.tex"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\\usetikzlibrary{fit}\n\xff\xfe")
        assert tl.library_union(["figures/bad.tex"], tmp_path) == ["fit"]


class TestHeaderInclude:
    def test_no_library_loads_tikz_alone(self):
        # `\usetikzlibrary{}` fails fatally on the comma list rather than
        # skipping, so an empty union must emit no call at all.
        assert tl.header_include([]) == r"\usepackage{tikz}"

    def test_libraries_follow_the_package(self):
        # Order is load-bearing: \usetikzlibrary needs tikz loaded.
        assert tl.header_include(["fit", "positioning"]) == (
            r"\usepackage{tikz}\usetikzlibrary{fit,positioning}"
        )
```

- [ ] **Step 2: run them and watch them fail**

```bash
.venv-full/bin/python -m pytest tests/test_render_output_tikz_libraries.py -v
```

Expected: collection error, `No module named
chitragupta.render_output._tikz_libraries`.

- [ ] **Step 3: write the module**

```python
"""Which TikZ libraries a draft's figures ask for, as one preamble load.

#781. `\\usetikzlibrary` is legal in the document body, and figure files
have always carried their own -- but a figure file is `\\input` inside a
`figure` float, and a float is a group. The library's macros are defined
*locally* there while `\\tikz@library@<name>@loaded` is set *globally*,
so the second float skips the load and finds none of the macros; and
every workaround for that is worse, because
`tikzlibrarypositioning.code.tex` appends to `\\tikz@node@reset@hook`
globally on each load, so N loads shift every node N times. In this
repository's own assembled book that spilled figures off the page while
`pdflatex` exited 0.

So the renderer loads them once, ungrouped, in the preamble. A figure
file keeps its own plain load line -- it is then a no-op that appends
nothing, and it is still needed by the two documents this pipeline does
not write: `thesis-chapter-writer`'s fragment inside a user's thesis,
and the minimal probe document `review figure` and WRITING-STANDARDS.md
§10 build around a single figure.

This module reads figure *source* and never compiles anything, which is
what keeps it (and its tests) working on a host with no TeX Live.
"""

import re
from pathlib import Path

from chitragupta.render_output._figures import _resolve_sibling

# A TeX comment: `%` to the end of the line. Every pattern here runs over
# stripped source -- a commented-out load is inert in TeX, so collecting
# it would put a library in the preamble no figure uses, and a misspelled
# one inside a comment would fail the whole render (TIKZ-STYLE.md: a
# missing name takes the whole call down).
#
# `\%` is a literal percent sign and does not start a comment, hence the
# lookbehind. `\\%` -- an escaped backslash then a real comment -- is
# read the wrong way by that lookbehind and is left alone: it needs a
# character-by-character scan rather than a regex, and no figure this
# pipeline draws has produced one.
#
# This is the canonical definition. `review/figure_layout/_source.py`
# imports it from here rather than keeping its own, because the
# dependency runs review -> render_output and never back.
_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")

# The load itself. Deliberately regex over TikZ rather than a LaTeX
# parser, matching how `_figures.py` already reads these same files. The
# optional-argument form `\usetikzlibrary[...]{...}` does not exist in
# PGF, so there is nothing between the macro and its brace but space.
_USETIKZLIBRARY_RE = re.compile(r"\\usetikzlibrary\s*\{([^}]*)\}")


def strip_comments(source: str) -> str:
    """`source` with every TeX comment removed."""
    return _COMMENT_RE.sub("", source)


def libraries_in(source: str) -> list[str]:
    """Every library one figure file loads, in source order, deduped.

    An empty name is dropped rather than carried: `\\usetikzlibrary{}`
    fails fatally in TeX, and re-emitting one into the preamble would
    turn one figure's typo into every render's failure.
    """
    names: list[str] = []
    for group in _USETIKZLIBRARY_RE.findall(strip_comments(source)):
        for name in group.split(","):
            name = name.strip()
            if name and name not in names:
                names.append(name)
    return names


def library_union(figure_refs: list[str], draft_dir: Path) -> list[str]:
    """Every library the draft's figures ask for, sorted.

    Sorted rather than first-seen: this string lands in the preamble of
    every render, and byte-identical output over unchanged input is a
    product rule here (docs/CODE-STANDARDS.md, "Repeatable").

    A reference that does not resolve to a readable file under the
    draft's own directory contributes nothing and says nothing --
    `_figure_warnings` is what reports a missing figure, and a second
    report of the same fact from the preamble builder would be noise.
    `errors="replace"` for the same reason `_figure_has_citekey` uses it:
    a figure file that is not valid UTF-8 is its own problem, and failing
    here would make the preamble builder the thing that stops a render.
    """
    found: set[str] = set()
    for ref in figure_refs:
        resolved = _resolve_sibling(draft_dir, ref)
        if resolved is not None:
            found.update(libraries_in(resolved.read_text(encoding="utf-8", errors="replace")))
    return sorted(found)


def header_include(libraries: list[str]) -> str:
    """The `header-includes` value for a draft with figures.

    One string rather than two `--variable` arguments, because
    `\\usetikzlibrary` needs `tikz` already loaded and pandoc's
    concatenation order for repeated variables is not a contract this
    should be leaning on.
    """
    load = r"\usepackage{tikz}"
    if not libraries:
        return load
    return load + r"\usetikzlibrary{" + ",".join(libraries) + "}"
```

- [ ] **Step 4: move `strip_comments` out of `_source.py`**

In `chitragupta/review/figure_layout/_source.py`, delete `_COMMENT_RE`
and the `def strip_comments` body, and replace them with a re-export that
keeps the name where every caller and test already reaches for it:

```python
# The comment stripper lives in `render_output` (#781), where the
# preamble-library collector needs the same one. Re-exported under its
# old name because this module is where every reader of a figure's
# source looks for it, and because the dependency only runs one way:
# review imports render_output, never the reverse.
from chitragupta.render_output._tikz_libraries import (  # noqa: F401
    strip_comments,
)

__all__ = ["MAX_NODE_WORDS", "edge_list", "overlong_nodes", "stranded_arrowheads",
           "strip_comments", "loads_library_by_hand"]
```

**Both linters, not one.** `# noqa: F401` silences ruff; pylint's
`unused-import` is a separate check whose exit code CI reads, and
`__all__` is what settles it. Verify before committing:

```bash
.venv-full/bin/python -m pylint chitragupta/review/figure_layout/_source.py ; echo "exit: $?"
```

If this turns into a fight, the cheaper option is still open and is not a
worse plan: define a private `_COMMENT_RE` in `_tikz_libraries.py`, leave
`_source.py` completely untouched, and accept one duplicated four-line
regex. The DRY version is preferred only while it costs nothing -- do not
pay for it with a red pylint discovered at push time.

Keep the big comment block that explained what the stripper fixes (#404)
by moving it to the new module's `_COMMENT_RE` -- it is the record of a
real bug and must not be lost in the move.

- [ ] **Step 5: re-export from the package**

In `chitragupta/render_output/__init__.py`, beside the other `_X.py`
imports, add:

```python
from chitragupta.render_output._tikz_libraries import (
    header_include,
    libraries_in,
    library_union,
)
```

- [ ] **Step 6: run the tests**

```bash
.venv-full/bin/python -m pytest tests/test_render_output_tikz_libraries.py \
    tests/test_figure_layout.py -v
```

Expected: PASS, including the existing `_source.strip_comments` tests
untouched.

- [ ] **Step 7: commit**

```bash
git add chitragupta/render_output/_tikz_libraries.py \
        chitragupta/render_output/__init__.py \
        chitragupta/review/figure_layout/_source.py \
        tests/test_render_output_tikz_libraries.py
git commit -m "feat(render): collect the TikZ library union from a draft's figures (#781)"
```

---

## Task 2: load the union in the preamble

**Files:**

- Modify: `chitragupta/render_output/_pandoc.py:176-177`
- Modify: `chitragupta/render_output/__init__.py` (inside `render`)
- Test: `tests/test_render_output_cli.py`

**Interfaces consumed:** `header_include`, `library_union` from Task 1.

**Interface produced:** `_pandoc_command(..., tikz_libraries: list[str] |
None = None)`. The new parameter goes **last**, after `has_code_block`:
existing tests call this function positionally with eleven-to-thirteen
arguments, and inserting it anywhere else silently rebinds them.

- [ ] **Step 1: write the failing tests**

Add to `tests/test_render_output_cli.py`, beside
`TestBreakableCodeBlocks` (reuse its `_header_includes` helper shape):

```python
class TestTikzLibraryPreamble:
    """#781: the libraries a draft's figures ask for are loaded once, in
    the preamble, never inside a `figure` float."""

    def _header_includes(self, cmd):
        return [
            cmd[i + 1]
            for i, flag in enumerate(cmd)
            if flag == "--variable"
            and cmd[i + 1].startswith("header-includes")
            and "LTcapwidth" not in cmd[i + 1]
        ]

    def _cmd(self, figure_refs, tikz_libraries):
        cmd, _ = render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path("out.tex"),
            Path("in.md"),
            "tex",
            "article",
            "12pt",
            "a4",
            "1in",
            figure_refs,
            False,
            False,
            tikz_libraries,
        )
        return cmd

    def test_the_union_is_loaded_after_the_package(self):
        includes = self._header_includes(self._cmd(["figures/a.tex"], ["fit", "positioning"]))
        assert includes == [
            r"header-includes=\usepackage{tikz}\usetikzlibrary{fit,positioning}"
        ]

    def test_a_figure_with_no_library_gets_no_call(self):
        # `\usetikzlibrary{}` is fatal, so an empty union emits nothing.
        includes = self._header_includes(self._cmd(["figures/a.tex"], []))
        assert includes == [r"header-includes=\usepackage{tikz}"]

    def test_a_draft_with_no_figure_loads_nothing(self):
        assert self._header_includes(self._cmd([], ["fit"])) == []

    def test_one_variable_not_two(self):
        # Two `--variable header-includes` arguments would leave the
        # order pandoc concatenates them in load-bearing, and
        # `\usetikzlibrary` before `\usepackage{tikz}` is an undefined
        # control sequence.
        assert len(self._header_includes(self._cmd(["figures/a.tex"], ["fit"]))) == 1
```

- [ ] **Step 2: run them and watch them fail**

```bash
.venv-full/bin/python -m pytest tests/test_render_output_cli.py -k Tikz -v
```

Expected: `TypeError: _pandoc_command() takes ... positional arguments
but 14 were given`.

- [ ] **Step 3: implement**

In `_pandoc.py`, add the parameter to the signature after
`has_code_block: bool = False`:

```python
    tikz_libraries: list[str] | None = None,
```

and replace lines 176-177 with:

```python
    # Loaded only for a draft that actually has a figure (#222) --
    # pandoc's default LaTeX template has no \usepackage{tikz}, so a bare
    # tikzpicture environment fails with "Environment tikzpicture
    # undefined" without it, but the package load itself is inert for a
    # draft that never draws one, so this stays conditional.
    #
    # The libraries ride in the same string (#781), not a second
    # `--variable`: `\usetikzlibrary` needs `tikz` already loaded, and
    # they are loaded *here* rather than in the figure file because a
    # figure file is `\input` inside a float, and a float is a group --
    # see `_tikz_libraries.py` for what that does to node placement.
    # Not conditioned on `_LATEX_BOUND`, matching the tikz load it
    # extends: `_figure_refs` reads the draft on disk, so an html render
    # of a figure-bearing draft already interpolates this into `<head>`.
    # Deliberate rather than inherited -- changing it would be a second,
    # unrelated fix.
    if figure_refs:  # pragma: no cover-windows
        cmd += ["--variable", "header-includes=" + header_include(tikz_libraries or [])]
```

with `from chitragupta.render_output._tikz_libraries import header_include`
at the top.

In `chitragupta/render_output/__init__.py`'s `render`, right after
`figure_refs` is computed (currently line ~277):

```python
    figure_refs = _figure_refs(draft_text)  # pragma: no cover-windows
    tikz_libraries = library_union(figure_refs, input_path.parent)  # pragma: no cover-windows
    if figure_refs and output_format in _TEX_FORMATS:  # pragma: no cover-windows
        _require_tikz()
```

and pass `tikz_libraries` as the last argument to `_pandoc_command`.

- [ ] **Step 4: run the tests**

```bash
.venv-full/bin/python -m pytest tests/test_render_output_cli.py tests/test_render_output.py -v
```

Expected: PASS, with the existing `TestBreakableCodeBlocks` cases
unchanged (they pass thirteen positional arguments and the new one
defaults).

- [ ] **Step 5: render a real draft end to end**

```bash
mkdir -p content/drafts/_scratch/tikz781/figures
```

Write `content/drafts/_scratch/tikz781/draft.md` with two `figure:`
markers and two figure files that each load `positioning`, then:

```bash
.venv-full/bin/python -m chitragupta.draft render content/drafts/_scratch/tikz781/draft.md --format pdf
```

Expected: exit 0, and `grep -c Overfull` over the pdflatex log is 0.
**Work in `content/drafts/_scratch/` only** -- `content/drafts/` is
gitignored, so an accidental edit to a real draft has no undo.

- [ ] **Step 6: commit**

```bash
git add chitragupta/render_output/_pandoc.py chitragupta/render_output/__init__.py \
        tests/test_render_output_cli.py
git commit -m "fix(render): load the TikZ library union in the preamble, not in a float (#781)"
```

---

## Task 3: report the union for `--fragment`

A `--fragment` render emits no preamble, so the load above reaches
nothing there and the assembling book has to carry it. The channel is a
stderr line in the shape the renderer already uses for figure, table and
equation warnings (`[prefix] message`, `render_output/__init__.py:248`) --
a skill already reads that stream, and this needs no new file, no new
flag and no JSON surface.

**Files:**

- Modify: `chitragupta/render_output/__init__.py`
- Test: `tests/test_render_output.py`

**Interface produced:** on a `--fragment` render of a LaTeX-bound format
whose figures load at least one library, exactly one stderr line:

```text
[tikz-libraries] positioning,fit -- a fragment has no preamble; load these in the assembling document
```

The names are the sorted union, comma-joined with no spaces, so the
consumer can paste them straight into `\usetikzlibrary{...}`.

- [ ] **Step 1: write the failing test**

This is a **real-toolchain** test, in the shape
`test_a_tikz_figure_renders_to_pdf` already uses in this module
(`tests/test_render_output.py:508-534`): the `isolated_config` fixture
from `tests/conftest.py` points every `config` path constant at a
throwaway `tmp_path/content` tree, the draft is written under it because
`render` calls `config.require_inside_content`, and the module-level
`pandoc_available` / `pdflatex_available` / `tikz_available` flags gate
the skip. There is no pandoc stub here and inventing one would be wrong:
the line under test sits *after* `_require("pandoc")` in `render`, so a
stubbed run would either not reach it or would stub out the very call
ordering the test is about.

```python
class TestFragmentReportsItsTikzLibraries:
    """#781: a fragment has no preamble, so the union has to reach the
    book by some other channel. stderr, in the shape every other render
    warning already uses."""

    def _draft_with(self, isolated_config, tmp_path, monkeypatch, *figures):
        """A draft under the isolated content dir, with one `figure:`
        marker per (name, body) pair given."""
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts"
        (draft_dir / "figures").mkdir(parents=True)
        markers = []
        for name, body in figures:
            (draft_dir / "figures" / f"{name}.tex").write_text(body)
            markers.append(f"<!-- figure: figures/{name} -->\n")
        draft = draft_dir / "draft.md"
        draft.write_text("# Title\n\n" + "\n".join(markers) + "\nNo citations.\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        return draft

    _POSITIONING = "\\usetikzlibrary{positioning}\n\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n"
    _FIT = "\\usetikzlibrary{fit}\n\\begin{tikzpicture}\\node (b) {B};\\end{tikzpicture}\n"
    _BARE = "\\begin{tikzpicture}\\draw (0,0) circle (1);\\end{tikzpicture}\n"

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_the_union_is_printed_once(self, isolated_config, tmp_path, capsys, monkeypatch):
        draft = self._draft_with(
            isolated_config,
            tmp_path,
            monkeypatch,
            ("fig1", self._POSITIONING),
            ("fig2", self._FIT),
        )
        render_output.render(str(draft), output_format="tex", fragment=True)
        err = capsys.readouterr().err
        assert err.count("[tikz-libraries]") == 1
        assert "[tikz-libraries] fit,positioning" in err

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_a_standalone_render_says_nothing(
        self, isolated_config, tmp_path, capsys, monkeypatch
    ):
        # It is in the preamble there, so a line about it would be noise
        # on every ordinary render.
        draft = self._draft_with(
            isolated_config, tmp_path, monkeypatch, ("fig1", self._POSITIONING)
        )
        render_output.render(str(draft), output_format="tex", fragment=False)
        assert "[tikz-libraries]" not in capsys.readouterr().err

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_a_fragment_whose_figures_load_nothing_says_nothing(
        self, isolated_config, tmp_path, capsys, monkeypatch
    ):
        draft = self._draft_with(isolated_config, tmp_path, monkeypatch, ("fig1", self._BARE))
        render_output.render(str(draft), output_format="tex", fragment=True)
        assert "[tikz-libraries]" not in capsys.readouterr().err
```

- [ ] **Step 2: run and watch it fail**

```bash
.venv-full/bin/python -m pytest tests/test_render_output.py -k tikz_libraries -v
```

Expected: FAIL, `assert 0 == 1`.

- [ ] **Step 3: implement**

Immediately after `tikz_libraries` is computed in `render`:

```python
    # A fragment has no preamble for the load above to land in, so the
    # assembling book has to carry it -- the same structural reason
    # `fvextra` and `\LTcapwidth` are in book-assembler's own preamble
    # (docs/BOOKS.md). Printed rather than returned because `render`'s
    # return value is the output path and every consumer of this is a
    # skill reading the render's output. One line, only when there is
    # something to say.
    if fragment and tikz_libraries and output_format in _TEX_FORMATS:  # pragma: no cover-windows
        print(
            f"[tikz-libraries] {','.join(tikz_libraries)} -- a fragment has no "
            "preamble; load these in the assembling document",
            file=sys.stderr,
        )
```

- [ ] **Step 4: run the tests**

```bash
.venv-full/bin/python -m pytest tests/test_render_output.py -v
```

Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add chitragupta/render_output/__init__.py tests/test_render_output.py
git commit -m "feat(render): report a fragment's TikZ library union for the assembler (#781)"
```

---

## Task 4: the book carries the union

**Files:**

- Modify: `.claude/skills/book-assembler/SKILL.md` (the skeleton at lines
  53-80, and the prose after it)
- Modify: `docs/BOOKS.md` if it restates the preamble (grep first:
  `grep -n 'fvextra\|LTcapwidth' docs/BOOKS.md`)

No test: this is a skill instruction, not code. It is the *only*
uncovered link in the chain, which is why Task 7's regression test exists.

- [ ] **Step 1: add the load to the skeleton**

In the ````latex` block, after `\usepackage{graphicx}`:

```latex
\usepackage{tikz}
\usetikzlibrary{positioning,fit}             % see "TikZ libraries" below
```

- [ ] **Step 2: add the prose, in the idiom of the three notes beside it**

After the "Table captions" paragraph:

````markdown
**TikZ libraries: the book must load them, and no figure file may.** Same
structural reason as `fvextra` and `\LTcapwidth` above -- `draft render`
puts the union of a draft's `\usetikzlibrary` names in its own preamble,
and a unit converted `--fragment` has no preamble for that to land in.

It is not merely a convenience here. A figure file is `\input` **inside a
`figure` float**, and a float is a group: the library's macros are defined
locally and die with the float, while `\tikz@library@<name>@loaded` is set
globally, so the second figure in the book skips the load and finds no
macros. Every per-figure workaround for that is worse, because
`tikzlibrarypositioning.code.tex` appends to `\tikz@node@reset@hook`
*globally* on every load -- so N loads apply every node's placement shift
N times. Measured on this project's own book (#781): figures that fit in
their single-chapter PDF spilled off the page in `book.pdf`, with
`pdflatex` exiting 0 and nothing but `Overfull \hbox` and `Float too
large for page` in `book.log`.

**Take the union from the renders, not by guessing.** Each
`draft render --fragment` prints one line per unit when its figures ask
for a library:

```text
[tikz-libraries] fit,positioning -- a fragment has no preamble; load these in the assembling document
```

Collect those across every unit, deduplicate, and write the result as the
single `\usetikzlibrary` line above. Never write `\usetikzlibrary{}` --
an empty comma list fails fatally rather than skipping, so a book whose
units draw no figure simply omits both lines.

A unit's figure file still carries its own plain `\usetikzlibrary` line
and that is correct: with the book's preamble load already done, it is a
no-op that appends nothing, and it is what lets the same figure compile
in `thesis-chapter-writer`'s fragment and in `review figure`'s probe. What
a figure file must **never** contain is a hand-rolled load: no clearing of
`\tikz@library@...@loaded`, no saving or restoring of
`\tikz@node@reset@hook`. `python -m chitragupta.review figure` reports one
as `loads-library-by-hand`.
````

- [ ] **Step 3: check markdownlint, which runs locally and in CI**

```bash
npx --yes markdownlint-cli2@0.23.2 ".claude/skills/book-assembler/SKILL.md" "docs/BOOKS.md"
```

Expected: 0 errors. (A nested fenced block inside a fenced block is an
MD046 trap -- if the quoted block above is transcribed inside another
fence, use a longer outer fence.)

- [ ] **Step 4: commit**

```bash
git add .claude/skills/book-assembler/SKILL.md docs/BOOKS.md
git commit -m "docs(book-assembler): load the TikZ library union in the book preamble (#781)"
```

---

## Task 5: the convention, and four now-false claims

Four documents say outright that the renderer supplies no library and
that the figure file is the only place one can be loaded. All four are
false after Task 2, and the docs sweep in this repository has repeatedly
been the thing that catches a defect -- so this is not cosmetic.

**Files:**

- Modify: `docs/TIKZ-STYLE.md:76-113` (the `\usetikzlibrary` section) and
  the Panels example at :198
- Modify: `docs/WRITING-STANDARDS.md:394-400` (§10's probe instruction)
- Modify: `docs/FIGURE-ROADMAP.md:84-89`, `:220`, `:843-850`
- Modify: `assets/tikz/README.md:56-61`

- [ ] **Step 1: rewrite TIKZ-STYLE.md's section**

Replace "**Every idiom in that table needs a `\usetikzlibrary` line, and
the figure file has to carry it itself.** The renderer adds
`\usepackage{tikz}` to the preamble and nothing else..." through to the
`\begin{tikzpicture}` example with:

````markdown
**Every idiom in that table needs a `\usetikzlibrary` line, and the
figure file carries it at the top, above the `tikzpicture`:**

```latex
\usetikzlibrary{positioning}
\begin{tikzpicture}[thick,x=1mm,y=1mm]
```

**The renderer collects those lines and loads the union in the preamble**
(`chitragupta/render_output/_tikz_libraries.py`, #781), so by the time
your figure is `\input` the library is already there and your own line is
a no-op. Keep the line anyway -- it is what lets the same file compile in
the two documents this pipeline does not write: `thesis-chapter-writer`'s
fragment inside a user's own thesis, and the minimal probe document
`review figure` and [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10
build around one figure.

**Write nothing else about loading.** No clearing of
`\tikz@library@<name>@loaded`, no saving or restoring of
`\tikz@node@reset@hook`, no `\ifdefined` guard around the load. Those
workarounds exist in older figure files and they are the bug, not the
fix: a figure file is `\input` inside a `figure` float, a float is a
group, and `\usetikzlibrary` defines its macros *locally* while setting
the loaded flag *globally*. Clearing the flag to force a reload makes
`positioning` append its placement transform to a **global** hook once
per figure, so the Nth figure shifts every node N times. In this
project's own assembled book that pushed figures off the page while
`pdflatex` exited 0. `python -m chitragupta.review figure` reports one as
`loads-library-by-hand`.

Two things to know before you reach for a library:
````

(the existing two bullets -- "A missing name takes the whole call down"
and "`shapes.geometric`, not `shapes.geometry`" -- follow unchanged, and
both are still true: the union is emitted into one comma list, so one
typo still takes the whole render down.)

- [ ] **Step 2: fix §10's probe instruction**

The sentence "the probe preamble loads no library, exactly as the
renderer's does not" is now wrong about the renderer. Keep the
instruction, fix the reason:

```markdown
  **Copy the figure's own `\usetikzlibrary` line into that probe**, or
  the check fails for a reason the figure does not have: a bare
  `\usepackage{tikz}` preamble loads no library, so anything using
  `positioning`, `matrix`, `fit` or `tree` errors there whether or not it
  is sound. The renderer loads the union of those lines in its own
  preamble (#781) and your probe is standing in for that preamble, which
  is why the line has to be copied rather than assumed.
```

- [ ] **Step 3: fix `assets/tikz/README.md`**

```markdown
Each file carries its own `\usetikzlibrary` line at the top. Keep it: the
renderer collects those lines across a draft's figures and loads the
union in the preamble (#781), so the line is a no-op in a rendered draft
-- but it is what makes the file compile on its own, which is how you are
told to check one, and what `thesis-chapter-writer`'s fragment needs
inside a thesis this pipeline never sees. Do not add anything else about
loading: no flag clearing, no hook save/restore. See
`docs/TIKZ-STYLE.md`.
```

- [ ] **Step 4: fix FIGURE-ROADMAP.md's three claims**

- `:84-86` -- "The renderer adds `\usepackage{tikz}` and nothing else"
  becomes "...adds `\usepackage{tikz}` plus the union of the
  `\usetikzlibrary` names its figure files ask for (#781), conditionally,
  via `header-includes`".
- `:87-89` -- "figure files carry their own library loads" becomes
  "figure files still *name* the libraries they need and the renderer
  hoists them; loading one inside the float is #781's bug".
- `:220` -- "because the renderer will not supply it" becomes "which is
  where the renderer reads it from".
- `:845` -- the Part VII note that a `pgfplots` load "is architecturally
  identical to what the tikz header-includes change did" is still true
  and gains "and to the library union #781 added beside it".

- [ ] **Step 5: fix the four genre skills, which state the old rule verbatim**

These are the files a *drafting* session actually loads first;
TIKZ-STYLE.md is what it is routed to afterwards. All four carry the same
sentence, at `thesis-chapter-writer/SKILL.md:394-398`,
`survey-writer/SKILL.md:470-474`, `textbook-chapter-writer/SKILL.md:402-406`
and `tutorial-writer/SKILL.md:449-453`:

```text
     If the figure uses `positioning`, `matrix`, `fit` or `tree`, put
     its `\usetikzlibrary` line at the top of `figures/<name>.tex` and
     copy that line into the probe too: the renderer's preamble loads
     `tikz` and no library, so a picture that relies on one and does not
     load it fails the whole render. `docs/TIKZ-STYLE.md` has the detail.
```

Replace it in all four with:

```text
     If the figure uses `positioning`, `matrix`, `fit` or `tree`, put
     its `\usetikzlibrary` line at the top of `figures/<name>.tex` and
     copy that line into the probe too: the probe's own preamble loads
     `tikz` and no library, so a picture that relies on one errors there
     whether or not it is sound. Keep the line and write nothing else
     about loading -- no clearing of `\tikz@library@...@loaded`, no
     saving or restoring of `\tikz@node@reset@hook`. The renderer
     collects those lines and loads the union in its own preamble
     (#781); a load *inside* the figure float is the bug that multiplied
     node spacing in this project's own book. `docs/TIKZ-STYLE.md` has
     the detail.
```

- [ ] **Step 6: the thesis genre needs one more instruction**

The hoist cannot reach it, and this is the gap that matters most.

`thesis-chapter-writer`'s `.tex` fragment is the one output this pipeline
stops touching: it keeps a real inline
`\begin{figure}...\input{figures/x.tex}...\end{figure}` and is `\input`
into a thesis whose preamble is the user's
(`render_output/_figures.py`'s module docstring, #247/#230). The preamble
hoist fixes *this* pipeline's render of that fragment and reaches nothing
in the consuming thesis -- so a thesis chapter with two `positioning`
figures reproduces #781 exactly, in the genre whose whole purpose is
leaving here. Nothing in code can fix that; the skill has to tell the
user. Add to `.claude/skills/thesis-chapter-writer/SKILL.md`, in the
step that hands the fragment over:

````text
   - **Tell the user what their thesis preamble must load.** The
     fragment's figures are `\input` inside `figure` floats, and a float
     is a group: `\usetikzlibrary` there defines its macros locally but
     sets the loaded flag globally, so the *second* figure in their
     thesis skips the load and finds no macros (#781). This pipeline
     loads the union in its own preamble for its own renders and cannot
     touch theirs. Run the render with `--fragment` and quote the line it
     prints:

     ```text
     [tikz-libraries] fit,positioning -- a fragment has no preamble; load these in the assembling document
     ```

     Say plainly that `\usetikzlibrary{fit,positioning}` belongs in their
     thesis preamble, beside `\usepackage{tikz}`. Never suggest working
     around it inside a figure file -- clearing the loaded flag makes
     `positioning` append its placement transform to a global hook once
     per figure, so the Nth figure shifts every node N times, with
     `pdflatex` exiting 0 and nothing in the log.
````

- [ ] **Step 7: run the docs checks**

```bash
.venv-full/bin/python -m mkdocs build --strict 2>&1 | tail -5
npx --yes markdownlint-cli2 "docs/**/*.md" "assets/**/*.md"
.venv-full/bin/python -m pytest tests/test_tikz_scaffolds.py tests/test_tikz_subcaptions.py -v
```

Expected: strict build clean, 0 markdownlint errors, tests pass. The
scaffold test enforces that TIKZ-STYLE.md's metaphor table and
`assets/tikz/` agree -- neither is being changed here, so it must stay
green.

- [ ] **Step 8: commit**

```bash
git add docs/TIKZ-STYLE.md docs/WRITING-STANDARDS.md docs/FIGURE-ROADMAP.md \
        assets/tikz/README.md .claude/skills/
git commit -m "docs(tikz): the renderer hoists the library union; figure files never load by hand (#781)"
```

---

## Task 6: `review figure` flags a hand-rolled load

The issue names this `FigureLoadsLibraryByHand`. **The JSON kind is
`loads-library-by-hand`**, because that is this aid's convention --
`nothing-measurable`, `stranded-arrowhead`, `node-text-overload` -- while
`chitragupta.X` names belong to the style rules in `style_typeset.py`, a
different layer with a different consumer. Recorded here so the deviation
from the issue's wording reads as a decision.

**Files:**

- Modify: `chitragupta/review/figure_layout/_source.py`
- Modify: `chitragupta/review/figure_layout/_result.py`
- Modify: `chitragupta/review/figure_layout/_report.py`
- Modify: `chitragupta/review/figure_layout/__init__.py` (call the check
  when building each `FigureResult`)
- Modify: `docs/REVIEW.md:85-94`, `docs/CLI.md` (the `review figure`
  section)
- Test: `tests/test_figure_layout.py`

**Interface produced:**

```python
def loads_library_by_hand(source: str) -> list[str]: ...  # the internals found, source order, deduped
```

and `FigureResult.by_hand: list[str] = field(default_factory=list)`.

- [ ] **Step 1: write the failing tests**

```python
class TestLoadsLibraryByHand:
    """#781: a figure file may name the libraries it needs and nothing
    more. Clearing the loaded flag or restoring the node-reset hook is
    the bug the preamble hoist fixed, and it is invisible in a
    single-chapter render."""

    def test_a_plain_load_is_fine(self):
        assert loads_library_by_hand(r"\usetikzlibrary{positioning}") == []

    def test_clearing_the_loaded_flag(self):
        source = r"\expandafter\let\csname tikz@library@positioning@loaded\endcsname\relax"
        assert loads_library_by_hand(source) == ["tikz@library@positioning@loaded"]

    def test_touching_the_node_reset_hook(self):
        source = r"\let\savedhook\tikz@node@reset@hook"
        assert loads_library_by_hand(source) == ["tikz@node@reset@hook"]

    def test_both_generations_in_one_file(self):
        source = (
            "\\csname tikz@library@fit@loaded\\endcsname\n"
            "\\let\\saved\\tikz@node@reset@hook\n"
        )
        assert loads_library_by_hand(source) == [
            "tikz@library@fit@loaded",
            "tikz@node@reset@hook",
        ]

    def test_a_repeat_is_named_once(self):
        source = "\\tikz@node@reset@hook\n\\tikz@node@reset@hook\n"
        assert loads_library_by_hand(source) == ["tikz@node@reset@hook"]

    def test_a_commented_out_workaround_is_not_flagged(self):
        # Inert in TeX, so flagging it would send an author to fix
        # something that does nothing.
        assert loads_library_by_hand("% \\tikz@node@reset@hook") == []


class TestByHandIsAFinding:
    def test_it_counts_as_a_finding(self):
        result = FigureResult(path=Path("figures/a.tex"), by_hand=["tikz@node@reset@hook"])
        assert result.has_findings

    def test_it_reaches_the_text_report(self):
        result = FigureResult(path=Path("figures/a.tex"), by_hand=["tikz@node@reset@hook"])
        text = format_report(Path("d.md"), [result])
        assert "tikz@node@reset@hook" in text
        assert "preamble" in text

    def test_it_reaches_the_payload(self):
        result = FigureResult(path=Path("figures/a.tex"), by_hand=["tikz@node@reset@hook"])
        body = payload(Path("d.md"), [result], "cmd")
        assert body["findings"] == [
            {
                "figure": "figures/a.tex",
                "kind": "loads-library-by-hand",
                "internal": "tikz@node@reset@hook",
            }
        ]

    def test_a_clean_figure_reports_none(self):
        body = payload(Path("d.md"), [FigureResult(path=Path("figures/a.tex"))], "cmd")
        assert [f["kind"] for f in body["findings"]] == []
```

- [ ] **Step 2: run and watch them fail**

```bash
.venv-full/bin/python -m pytest tests/test_figure_layout.py -k ByHand -v
```

Expected: `ImportError`/`TypeError` on the unknown name and field.

- [ ] **Step 3: implement the check in `_source.py`**

```python
# The two TeX internals a figure file has no business naming (#781).
# `\tikz@library@<name>@loaded` is the flag `\usetikzlibrary` sets
# globally; clearing it forces a reload. `\tikz@node@reset@hook` is the
# macro `positioning` appends to globally on every load, which is what
# makes those reloads multiply every node's placement shift. Either one
# in a figure file is a workaround for the float-grouping bug the
# preamble hoist fixed, and it is invisible in a single-chapter render --
# it only misbehaves once a second figure exists in the same document.
#
# Matched with or without the leading backslash, because both spellings
# occur in the wild: `\tikz@node@reset@hook` directly, and
# `tikz@library@x@loaded` bare inside a `\csname ... \endcsname`.
_BY_HAND_RE = re.compile(r"\\?(tikz@library@[A-Za-z.]+@loaded|tikz@node@reset@hook)")


def loads_library_by_hand(source: str) -> list[str]:
    """Every TeX internal this figure file touches to manage a library
    load itself, in source order, deduped.

    Comments stripped first, for the reason every other check here strips
    them: a commented-out workaround is inert, and sending an author to
    fix something that does nothing is a wrong answer, not a cautious
    one.
    """
    found: list[str] = []
    for name in _BY_HAND_RE.findall(strip_comments(source)):
        if name not in found:
            found.append(name)
    return found
```

- [ ] **Step 4: carry it through result, report and payload**

`_result.py`: add the field beside `stranded`, and add `or self.by_hand`
to `has_findings`'s boolean:

```python
    by_hand: list[str] = field(default_factory=list)
```

`_report.py`, in `_figure_lines`, after the `stranded` loop:

```python
    for internal in result.by_hand:
        lines.append(
            f"  - loads its TikZ library by hand (`{internal}`) -- the renderer "
            f"loads the union in the preamble, so delete this and keep only the "
            f"plain `\\usetikzlibrary` line"
        )
```

and in `_findings`, after the `stranded-arrowhead` block:

```python
        findings += [
            {"figure": figure, "kind": "loads-library-by-hand", "internal": internal}
            for internal in result.by_hand
        ]
```

`figure_layout/__init__.py`: where the other `_source` checks are called
to build a `FigureResult`, add
`by_hand=loads_library_by_hand(source)` and import the name.

- [ ] **Step 5: run the tests**

```bash
.venv-full/bin/python -m pytest tests/test_figure_layout.py -v
```

Expected: PASS.

- [ ] **Step 6: sweep the two documents that list this aid's findings**

`docs/REVIEW.md:85-89` -- add to the list of what `review figure`
reports: "and a figure file that manages a TikZ library load by hand,
which renders correctly alone and multiplies node spacing the moment a
second figure joins it in one document (#781)".

`docs/CLI.md`'s `review figure` section -- add `loads-library-by-hand`
wherever the other kinds are enumerated, with the same one-sentence
meaning. Find the spot with:

```bash
grep -n "nothing-measurable\|stranded-arrowhead" docs/CLI.md
```

Also confirm no test pins the *set* of kinds, which would redden here
rather than in Task 5:

```bash
grep -rn "kind" tests/test_figure_layout.py | grep -E "sorted|set\(|== \["
```

At the time of writing this returns two per-case assertions
(`== ["nothing-measurable"]`, `== ["does-not-compile"]`) and no
enumeration, so adding a kind is additive. Re-run it rather than
trusting that.

- [ ] **Step 7: commit**

```bash
git add chitragupta/review/figure_layout/ tests/test_figure_layout.py docs/REVIEW.md docs/CLI.md
git commit -m "feat(review): flag a figure file that loads its TikZ library by hand (#781)"
```

---

## Task 7: the regression test, in a real compile

Everything above is unit-tested against strings. This is the one test
that would have caught the original bug, and it needs TeX.

**Files:**

- Create: `tests/test_tikz_library_scope.py`

- [ ] **Step 1: write it**

```python
"""#781: two `figure` floats inputting the same positioning-based figure
must place their nodes identically.

The bug this pins was invisible to every other test here: each figure
renders correctly *on its own*, and `pdflatex` exits 0 on the document
where they are wrong. The only trace in a real book was `Overfull \\hbox`
in a log nobody reads.

TeX-guarded, so it skips where TeX Live is absent -- which is most of
this aid's test hosts. It is therefore an *extra* on top of the unit
tests in tests/test_render_output_tikz_libraries.py, never the only cover
for any branch.
"""

import shutil
import subprocess
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="needs a TeX Live installation"
)

FIGURE = textwrap.dedent(
    r"""
    \usetikzlibrary{positioning}
    \begin{tikzpicture}
      \node[draw] (a) {A};
      \node[draw,right=20mm of a] (b) {B};
      \pgfpointanchor{b}{center}\pgfgetlastxy{\bx}{\by}
      \typeout{BX=\bx}
    \end{tikzpicture}
    """
)

DOCUMENT = textwrap.dedent(
    r"""
    \documentclass{book}
    \usepackage{tikz}
    \usetikzlibrary{positioning}
    \begin{document}
    \begin{figure}\input{fig}\end{figure}
    \begin{figure}\input{fig}\end{figure}
    \end{document}
    """
)


def _bx_values(tmp_path):
    (tmp_path / "fig.tex").write_text(FIGURE, encoding="utf-8")
    (tmp_path / "doc.tex").write_text(DOCUMENT, encoding="utf-8")
    run = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "doc.tex"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout[-2000:]
    return [line for line in run.stdout.splitlines() if line.startswith("BX=")]


def test_two_floats_place_the_node_identically(tmp_path):
    # The whole bug in one assertion: with the library loaded once in the
    # preamble, the second float's node sits exactly where the first
    # one's does. Before #781 the second was shifted again by a globally
    # appended hook, or failed outright once the flag was set and the
    # macros were not.
    values = _bx_values(tmp_path)
    assert len(values) == 2
    assert values[0] == values[1]


# The first-generation workaround, as a document. This is the shape that
# produced the *reported* symptom -- spacing multiplied, `pdflatex`
# exiting 0, nothing in the log -- as opposed to the outright error a
# missing load gives. Measured on this host at 71.26pt, 128.17pt,
# 185.07pt: a constant 56.9pt of extra shift per reload, because
# `positioning` appends its placement transform to the *global*
# `\tikz@node@reset@hook` on every load.
RELOADING_DOCUMENT = textwrap.dedent(
    r"""
    \documentclass{book}
    \usepackage{tikz}
    \makeatletter
    \def\cgreload{\expandafter\let\csname tikz@library@positioning@loaded\endcsname\relax}
    \makeatother
    \begin{document}
    \begin{figure}\cgreload\input{fig}\end{figure}
    \begin{figure}\cgreload\input{fig}\end{figure}
    \begin{figure}\cgreload\input{fig}\end{figure}
    \end{document}
    """
)


def test_clearing_the_flag_per_float_multiplies_the_shift(tmp_path):
    # Not a test of our code -- a test that the defect `review figure`'s
    # `loads-library-by-hand` check exists to catch is real, and that it
    # is silent. If this ever stops holding (a PGF release making the
    # hook append idempotent), the check is still right but its rationale
    # in TIKZ-STYLE.md needs revisiting rather than quietly rotting.
    (tmp_path / "fig.tex").write_text(FIGURE, encoding="utf-8")
    (tmp_path / "doc.tex").write_text(RELOADING_DOCUMENT, encoding="utf-8")
    run = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "doc.tex"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, "the symptom is that this build *succeeds*"
    values = [line for line in run.stdout.splitlines() if line.startswith("BX=")]
    assert len(values) == 3
    assert len(set(values)) == 3, values


def test_the_document_reports_no_overfull_box(tmp_path):
    # The only symptom the original bug left in a passing build.
    (tmp_path / "fig.tex").write_text(FIGURE, encoding="utf-8")
    (tmp_path / "doc.tex").write_text(DOCUMENT, encoding="utf-8")
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "doc.tex"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    log = (tmp_path / "doc.log").read_text(encoding="utf-8", errors="replace")
    assert "Overfull" not in log
```

- [ ] **Step 2: run it**

```bash
.venv-full/bin/python -m pytest tests/test_tikz_library_scope.py -v
```

Expected: 3 passed on this host (pdflatex and `texlive-pictures` are
installed, and all three cases were run by hand while this plan was
written -- see the table in "The mechanism, stated once"). If any
*fails*, stop: the mechanism above is wrong and the rest of this plan
rests on it.

- [ ] **Step 3: confirm it would have caught the bug**

Edit the local copy of `DOCUMENT` to drop the preamble
`\usetikzlibrary{positioning}` line and re-run. Expected: FAIL (the
second float errors on `right=20mm of a`, or the two `BX=` values
differ). Restore the line. Do this as a scratch edit and `git diff` to
confirm nothing was left behind -- `git restore` reads the index, not
`main`, so do not rely on it after committing.

- [ ] **Step 4: commit**

```bash
git add tests/test_tikz_library_scope.py
git commit -m "test: pin that two floats place a positioning node identically (#781)"
```

---

## Task 8: the migration script

**The 20 files named in the issue are not in this repository or on this
host.** Verified: `grep -rl 'tikz@library@\|tikz@node@reset@hook'` over
the worktree, over `/workspace/content` (drafts, dossiers and the backup
snapshots) and over `/workspace` returns zero files. `content/drafts/` is
gitignored and the drafted book has left it before. So this script ships
with fixture tests and **no in-repo target to migrate**; whoever has the
affected tree runs it there. Say exactly that in the PR body rather than
claiming a migration was performed.

**Files:**

- Create: `scripts/strip_tikz_load_workarounds.py`
- Test: `tests/test_strip_tikz_load_workarounds.py`

- [ ] **Step 1: write the failing tests**

```python
"""#781's migration: strip both generations of hand-rolled TikZ library
loading from figure files, leaving the plain `\\usetikzlibrary` line."""

from pathlib import Path

from scripts.strip_tikz_load_workarounds import strip_workarounds


def test_the_plain_load_survives():
    source = "\\usetikzlibrary{positioning}\n\\begin{tikzpicture}\n\\end{tikzpicture}\n"
    assert strip_workarounds(source) == source


def test_a_flag_clearing_line_goes():
    source = (
        "\\expandafter\\let\\csname tikz@library@positioning@loaded\\endcsname\\relax\n"
        "\\usetikzlibrary{positioning}\n"
    )
    assert strip_workarounds(source) == "\\usetikzlibrary{positioning}\n"


def test_a_hook_save_and_restore_goes():
    source = (
        "\\let\\cgsavedhook\\tikz@node@reset@hook\n"
        "\\usetikzlibrary{fit}\n"
        "\\global\\let\\tikz@node@reset@hook\\cgsavedhook\n"
        "\\begin{tikzpicture}\n"
    )
    assert strip_workarounds(source) == "\\usetikzlibrary{fit}\n\\begin{tikzpicture}\n"


def test_a_file_with_nothing_to_strip_is_returned_unchanged():
    source = "\\begin{tikzpicture}\n\\end{tikzpicture}\n"
    assert strip_workarounds(source) == source


def test_a_line_that_merely_draws_is_never_touched():
    source = "\\draw (a) -- (b);\n"
    assert strip_workarounds(source) == source
```

- [ ] **Step 2: run and watch them fail**

```bash
.venv-full/bin/python -m pytest tests/test_strip_tikz_load_workarounds.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: implement**

A line-oriented strip: drop any **whole line** whose only content is a
statement naming `tikz@library@...@loaded` or `tikz@node@reset@hook`.
Line-oriented deliberately -- both workaround generations were written as
their own lines above the `tikzpicture`, and a regex that reached inside
a line could cut a `\draw` in half. Provide:

```python
def strip_workarounds(source: str) -> str: ...        # the new source
def main(argv: list[str] | None = None) -> int: ...   # --dry-run by default
```

The test imports it as `from scripts.strip_tikz_load_workarounds import
strip_workarounds`, which is how `tests/test_release.py:12` and
`tests/test_populate_bib_groups.py:27` already reach a script -- so
`scripts/` is importable as a package from the test root and needs no
`sys.path` fiddling. Confirm with `.venv-full/bin/python -c "import
scripts.release"` from the repo root before writing the test.

`main` walks the paths given on argv (files or directories), prints a
unified diff per file, and writes **only** when `--write` is passed.
Default-dry-run because the target of this script is by definition
somebody's gitignored `content/drafts/`, where an accidental edit has no
undo.

- [ ] **Step 4: bench/scripts conventions**

This goes in `scripts/`, not `bench/`, so the bench self-check
convention and the script-counting test do not apply. Confirm no test
counts `scripts/*.py`:

```bash
grep -rn "scripts/" tests/*.py | grep -i "count\|len(" | head
```

If one does, update it in this commit.

- [ ] **Step 5: run the tests and the lints**

```bash
.venv-full/bin/python -m pytest tests/test_strip_tikz_load_workarounds.py -v
```

Expected: PASS.

- [ ] **Step 6: commit**

```bash
git add scripts/strip_tikz_load_workarounds.py tests/test_strip_tikz_load_workarounds.py
git commit -m "feat(scripts): strip both generations of hand-rolled TikZ library loading (#781)"
```

---

## Task 9: ship it

- [ ] **Step 1: stage every new root-adjacent file before the suite**

Tests that read the tree via `git ls-files` do not see an unstaged file.
Everything created above is under `chitragupta/`, `tests/` or `scripts/`,
but stage it all before running the full suite anyway:

```bash
git status --porcelain
```

Expected: clean (each task committed its own files).

- [ ] **Step 2: bump the version**

Every PR bumps it, docs-only included; the check runs first in `lint` and
skips every later step, so a missing bump reads as "lint fail" with no
lint output. `main` was at `6.107.0`; **re-read it** rather than
trusting that:

```bash
git fetch origin && git show origin/main:pyproject.toml | grep '^version'
```

Bump the minor in `pyproject.toml` and commit.

- [ ] **Step 3: run the full pre-push set on the branch tip**

```bash
.venv-full/bin/python -m ruff format --check .
.venv-full/bin/python -m ruff check .
.venv-full/bin/python -m pylint chitragupta scripts bench tests .claude/hooks ; echo "pylint exit: $?"
.venv-full/bin/python -m pytest
npx --yes markdownlint-cli2@0.23.2 "**/*.md"
```

Read pylint's **exit code**, not its score -- 10.00/10 and a failing exit
code coexist here. Run `ruff format` *before* any coverage run; a
reformat mid-run yields a phantom coverage number.

- [ ] **Step 4: the coverage bar**

CI fails the test job at 99.94% with every test passing. In a worktree a
full `--cov` run reports every module twice and craters the total, so do
not read the worktree's TOTAL as real -- diff pass/fail counts instead,
and check the new modules specifically:

```bash
.venv-full/bin/python -m pytest \
    tests/test_render_output_tikz_libraries.py tests/test_figure_layout.py \
    tests/test_render_output_cli.py tests/test_render_output.py \
    tests/test_strip_tikz_load_workarounds.py \
    --cov=chitragupta.render_output._tikz_libraries \
    --cov=chitragupta.review.figure_layout \
    --cov=scripts.strip_tikz_load_workarounds --cov-report=term-missing
```

Expected: 100% on all three, or a `# pragma: no cover-windows` matching
the neighbours it sits among.

- [ ] **Step 5: open the PR from a branch based on `main`**

Not on another branch -- `ci.yml` filters on `base=main`, so a stacked PR
runs zero checks and reads as a slow queue.

```bash
export GH_TOKEN=$(git remote get-url origin | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
gh pr create --base main --title "Hoist \usetikzlibrary out of figure floats (#781)" --body "..."
```

The body must be **bulleted** -- `scripts/merge_pr.py` composes the
commit message by scraping bullets, and a prose-only body lands a
truncated subject in `main`. Include, verbatim:

- `Closes #781` (one keyword per issue; a comma list closes only the
  first, and a closing keyword fires even inside a sentence denying it).
- A test-plan line saying the migration script has **no in-repo targets**
  and was verified against fixtures only.
- A note that Copilot review has been dormant on this repository since
  2026-09-03, so its absence is expected rather than a pending check.

- [ ] **Step 6: watch CI by head SHA**

`gh pr checks` is blind to a queued run, so poll `gh run list` by head
SHA instead. If zero check-runs appear at all, read `mergeable_state`
first -- a conflicted PR gets no CI and looks identical to a slow one.
Use `gh --jq`; there is no standalone `jq` on this host.

---

## Self-review against the issue

| Issue's proposed change | Task |
| --- | --- |
| 1. Renderer collects the union into `header-includes` | 1, 2 |
| 1b. For `--fragment`, report the union for the assembler | 3 |
| 2. `book-assembler` writes the union into `book.tex` | 4 |
| 3. Convention: a plain `\usetikzlibrary` line and nothing else -- TIKZ-STYLE.md, WRITING-STANDARDS.md §10, `assets/tikz/` scaffolds, **and the four genre SKILL.md files that state the old rule verbatim** | 5 (steps 1-5) |
| 3b. The one place the hoist cannot reach: `thesis-chapter-writer`'s fragment inside a user's own thesis | 5 (step 6) |
| 4. `review figure` flags the internals | 6 |
| 5. Two-float test asserting identical bounding boxes | 7 |
| 6. Migration script for both workaround generations | 8 |

Two deliberate departures from the issue's wording, both argued above:
the finding's JSON kind is `loads-library-by-hand` rather than
`FigureLoadsLibraryByHand` (Task 6's opening), and the "20 files here"
have no counterpart in this repository or on this host, so Task 8 ships
with fixtures instead of a performed migration.
