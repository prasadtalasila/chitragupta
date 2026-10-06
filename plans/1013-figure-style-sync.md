# #1013: stamp the house figure-style block into figure files

Status: **plan, built.** Written 2026-10-06 against `main` at
`10ac21f` (#1026, which shipped #1012's block as
`assets/tikz/cg-figstyle.tex`). Implements issue #1013 (F2 in
[docs/FIGURE-ROADMAP.md](../docs/FIGURE-ROADMAP.md)'s Part V).

**Written for** whoever builds it. **Assumed:** #1026's block, its two
marker lines, and `tests/test_tikz_scaffolds.py`'s byte-identity test;
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10 for where
figure files live (`content/drafts/<topic>/figures/<name>.tex`); the
issue's own argument for an inlined region over `\input`. **Not covered
here:** a harness hook (`.claude/hooks/`) that runs the check on an
agent's figure write; a `figure sync` default that also walks a
project's copied `assets/tikz/` (pass the path explicitly); #1014's
`pic` documentation.

The issue says F2 "can wait" until a block change has to be hand-applied
in more than about five places. Ten files in `assets/tikz/` already
carry the block, so the first v2 crosses that line in this repository
alone.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a `chitragupta figure sync` command that keeps the house block
current inside every figure file and never overwrites an author's edit,
plus a renderer warning and an advisory git-hook check that report a
stale or missing block.

**Architecture:** a new package `chitragupta/figure/` owns the region:
reading the shipped block and a register of every released version's
digest, classifying a file's region, and computing the stamped text. The
CLI walks figure files and writes through `_atomic_write`. The renderer
imports only the classifier, reports, and never writes. Comment
stripping moves to a leaf module so `render_output` can import
`chitragupta.figure` without an import cycle.

**Tech Stack:** Python 3.12+ stdlib (`hashlib`, `tomllib`, `difflib`,
`argparse`), pytest, bash for the hook, pdflatex + tikz for the one
round-trip test.

**Spec:** issue #1013 (the body is the spec; quoted where it binds).

## Decisions this plan makes, which the issue left open

1. **The marker line stays as #1026 wrote it.** The issue sketches
   `-- generated, do not edit`; the shipped v1 line reads
   `-- copy of assets/tikz/cg-figstyle.tex, do not edit`. Changing it
   would be a v2 with no content change, so it stays. Matching uses the
   prefix `% >>> chitragupta figure style v<N>`, as the F1 test already
   does.
2. **"Any released version" is a register of digests**,
   `assets/tikz/cg-figstyle.versions.toml`, one `v<N> = "<sha256>"`
   line per version. The digest is over the region with markers
   included and CRLF folded to LF. A test fails when the block's bytes
   differ from its version's recorded digest. That turns "edited the
   block without bumping the version" into a CI failure, which is the
   silent fork the issue is most worried about.
3. **The command is a package-level entry, `figure`**, in `COMMANDS` in
   `chitragupta/__main__.py`, beside `init`/`doctor`/`install`. It is
   not added to `LAYERS`: `tests/test_package_entrypoint.py` pins the
   four layers, and this is a maintenance tool over files, not a fifth
   layer. The module form is `python -m chitragupta.figure sync`, one
   level deep, so the command-depth invariant holds.
4. **The renderer warns about a missing block too**, as the issue asks,
   including for a figure that uses no `cg` key. A user with older
   figures will see one line per figure until they run `figure sync`.
   That is what an advisory is for. Filtering on `cg` usage would be a
   second heuristic to maintain.
5. **The git hook is advisory, and it runs only in a developer
   checkout.** `chitragupta init` does not scaffold `git-hooks/`
   (`chitragupta/init.py`'s `EXCLUDE` comment says why), so in this
   repository the hook guards `assets/tikz/` and any staged
   `content/drafts/**/figures/*.tex`. A user project gets the renderer
   warning instead.
6. **Exit codes.** `figure sync` exits 0 whatever it found. With
   `--check` it writes nothing and exits 1 if any file is not current.
   It exits 2 for a usage error or when the shipped block or register
   cannot be read (a broken install, not a finding).

## Global Constraints

- One-rule check: no citekey appears in any fixture, doc example or test
  written here. Figure fixtures carry node text only.
- Code standards (`docs/CODE-STANDARDS.md`): a module holds at most
  **250 lines of code**; a function at most **25 statements**; cognitive
  complexity at most **25**. `chitragupta/render_output/_figures.py` is
  at 244 code lines, so nothing is added to it.
- 100% coverage is enforced on the Windows CI leg too
  (`windows-ci-has-no-pandoc` memory): every new branch needs a test
  that runs without TeX. Only the round-trip compile test may use
  `needs_tikz`.
- Text written to disk is UTF-8 via `write_atomically(path, bytes)`. Use
  bytes so a CRLF file stays CRLF on every platform.
- `render_output` never writes a figure source file. A renderer that
  edits its inputs is ruled out by the issue.
- Version bump: minor (a new command). Take the next minor of whatever
  `pyproject.toml` says on `origin/main` when the PR opens, which was
  6.135.0 → **6.136.0** at writing.
- Branch from the latest `origin/main`. A PR body's `## Commit message`
  fence must pass `scripts/merge_pr.py --check`.

## Review Focus

The five inputs the issue implies but does not test, most likely first.
Each has a test in the task that owns it.

1. **A figure file with CRLF line endings** (Windows editor, user
   project, no `.gitattributes`). Expect a current region to read as
   current, a stale one to refresh with CRLF kept throughout, and no
   "modified" report caused only by line endings. Tested in Tasks 2 and 3.
2. **A region stamped by a newer chitragupta**, so its version is not in
   this install's register (a user with two venvs, or a downgrade).
   Expect "modified, not touched", plus a line saying the marker names
   v<N> and this install knows up to v<M>. Never a downgrade. Tested in
   Tasks 2 and 3.
3. **An indented or partially deleted marker pair**: one start and no
   end, two starts, the end above the start, or a marker re-indented by
   an editor. Expect `malformed` or `modified`, and never a second block
   inserted beside the first. Tested in Task 2.
4. **A figure file that is a symlink, is not UTF-8, or is read-only.**
   Expect one report line each, nothing written through the symlink, and
   the walk carrying on to the next file with exit 0. Tested in Task 3.
5. **Existing "renders clean" tests whose fixture figure has no block**
   (`tests/conftest.py::TIKZ_FIGURE`). Expect each to keep asserting
   "no warning" against a stamped fixture, not to have that assertion
   dropped. Tested in Task 4.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `chitragupta/_tex_comments.py` (new) | `strip_comments`, the canonical TeX comment regex. A leaf, imported by `render_output`, `review` and `figure` |
| `chitragupta/render_output/_tikz_libraries.py` | imports `strip_comments` from the leaf and keeps re-exporting it |
| `chitragupta/review/figure_layout/_source.py` | imports `strip_comments` from the leaf |
| `assets/tikz/cg-figstyle.versions.toml` (new) | every released block version and its digest |
| `chitragupta/figure/__init__.py` (new) | re-exports the public names |
| `chitragupta/figure/_block.py` (new) | `House`, `State`, `Region`, `load_house`, `classify`, `stamp`, `finding` (pure, no I/O except `load_house`) |
| `chitragupta/figure/_sync.py` (new) | `Outcome`, `figure_files`, `sync_file`, `run` (file walk and writes) |
| `chitragupta/figure/__main__.py` (new) | argparse, output, exit codes; `main(argv=None) -> int` |
| `chitragupta/__main__.py` | one `COMMANDS` entry |
| `chitragupta/render_output/_figure_style.py` (new) | `warnings(text, input_path) -> list[str]` |
| `chitragupta/render_output/_substitution.py` | `_draft_warnings` adds those under the `figure` tag |
| `git-hooks/pre-commit` | an advisory figure section ahead of the actionlint section |
| `tests/test_figure_block.py`, `tests/test_figure_sync.py`, `tests/test_render_output_figure_style.py` (new) | as named |
| `tests/test_git_hooks.py`, `tests/test_package_entrypoint.py`, `tests/conftest.py` | extended |
| docs and the 12 genre-skill copies | Task 6 |

---

### Task 1: Move comment stripping to a leaf module

No behaviour change. It exists so Task 4's import of `chitragupta.figure`
from `render_output` does not cycle through `_tikz_libraries` →
`_figures`, which is mid-import at that point.

**Files:**

- Create: `chitragupta/_tex_comments.py`
- Modify: `chitragupta/render_output/_tikz_libraries.py:29-71` (the
  `_COMMENT_RE` block and `strip_comments`)
- Modify: `chitragupta/review/figure_layout/_source.py:16,23`
- Test: `tests/test_tex_comments.py`

**Interfaces:**

- Produces: `chitragupta._tex_comments.strip_comments(source: str) -> str`
  and `_COMMENT_RE`. `_tikz_libraries.strip_comments` stays importable.

- [ ] **Step 1: Write the failing test**

```python
"""The one TeX comment stripper every figure-source reader shares."""

from chitragupta import _tex_comments
from chitragupta.render_output import _tikz_libraries


class TestStripComments:
    def test_a_comment_goes_and_the_line_break_stays(self):
        assert _tex_comments.strip_comments("a % note\nb\n") == "a \nb\n"

    def test_an_escaped_percent_is_text(self):
        assert _tex_comments.strip_comments(r"50\% done") == r"50\% done"

    def test_the_renderer_still_exports_the_same_function(self):
        assert _tikz_libraries.strip_comments is _tex_comments.strip_comments
```

- [ ] **Step 2: Run it and see it fail**

Run: `pytest tests/test_tex_comments.py -v`
Expected: FAIL, `ImportError: cannot import name '_tex_comments'`.

- [ ] **Step 3: Move the code**

Create `chitragupta/_tex_comments.py`. Move the whole comment block
above `_COMMENT_RE` (the #404 history and the `\\%` caveat) with it,
replacing its last paragraph with "This is the canonical definition;
`render_output/_tikz_libraries.py`, `review/figure_layout/_source.py`
and `chitragupta/figure/` import it from here. It is a leaf so that
any of them can import it without an import cycle."

```python
"""TeX comment stripping, the first step of every reader of figure source.

<the moved comment block, as described above>
"""

import re

_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")


def strip_comments(source: str) -> str:
    """`source` with every TeX comment removed, line breaks kept.

    See `_COMMENT_RE` for what that fixes and what it deliberately does not.
    """
    return _COMMENT_RE.sub("", source)
```

In `_tikz_libraries.py`, delete `_COMMENT_RE`, its comment and
`strip_comments`, and add
`from chitragupta._tex_comments import strip_comments` with a one-line
comment: "Re-exported: `libraries_in` uses it, and older callers import
it from here." In `review/figure_layout/_source.py`, import from
`chitragupta._tex_comments` and update the comment at line 23 to name
the new home.

- [ ] **Step 4: Run the tests that touch it**

Run:

```bash
pytest tests/test_tex_comments.py tests/test_figure_layout.py \
       tests/test_render_output_figures.py -q
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/_tex_comments.py chitragupta/render_output/_tikz_libraries.py \
        chitragupta/review/figure_layout/_source.py tests/test_tex_comments.py
git commit -m "Move TeX comment stripping to a leaf module"
```

---

### Task 2: The block, its register, and the region classifier

**Files:**

- Create: `assets/tikz/cg-figstyle.versions.toml`
- Create: `chitragupta/figure/__init__.py`, `chitragupta/figure/_block.py`
- Test: `tests/test_figure_block.py`

**Interfaces:**

- Consumes: `chitragupta._tex_comments.strip_comments`,
  `chitragupta.config.shipped(*parts) -> Path`.
- Produces (re-exported from `chitragupta.figure`):
  - `class State(Enum)`: `CURRENT`, `STALE`, `MODIFIED`, `MISSING`,
    `MALFORMED`
  - `@dataclass(frozen=True) class House`: `text: str` (current block,
    LF), `version: int`, `released: dict[str, int]` (digest → version)
  - `@dataclass(frozen=True) class Region`: `state: State`,
    `marker_version: int | None`, `start: int | None`, `end: int | None`
    (character offsets into the original text, `end` past the end
    marker's line break)
  - `digest(text: str) -> str`
  - `load_house(block: Path | None = None, register: Path | None = None) -> House`.
    It raises `OSError` or `ValueError` on a broken install.
  - `classify(text: str, house: House) -> Region`
  - `stamp(text: str, house: House) -> str | None`: the new text, the
    input unchanged when current, `None` when it must not or cannot be
    placed
  - `finding(text: str, house: House) -> str | None`: one advisory
    sentence, `None` when current

- [ ] **Step 1: Write the register**

`assets/tikz/cg-figstyle.versions.toml`:

```toml
# Every released version of the house figure-style block
# (cg-figstyle.tex), by the version its start marker carries, and the
# sha256 of the region -- both marker lines included, CRLF folded to LF.
#
# `chitragupta figure sync` refreshes a region only when its digest is
# one of these, and leaves any other region alone: a region matching no
# released version was edited by hand, and overwriting it would delete
# the author's work (#1013).
#
# Changing cg-figstyle.tex means bumping the version in its first line
# and adding a line here. Never edit an existing line: a figure stamped
# with that version would stop being recognised and become "modified".
# tests/test_figure_block.py fails if the block and this file disagree.
v1 = "f2aed6cbb46107d304468b080883d7c826e53c70402fe531a9ae9b4c3f9c7401"
```

Re-check the digest before committing, since it was computed at
`10ac21f`:

```bash
python -c "import hashlib,pathlib;t=pathlib.Path('assets/tikz/cg-figstyle.tex').read_text(encoding='utf-8');print(hashlib.sha256(t.replace('\r\n','\n').encode()).hexdigest())"
```

- [ ] **Step 2: Write the failing tests**

`tests/test_figure_block.py`. The figures here are made from the real
shipped block, so they cannot drift from it.

```python
"""The house block's region inside a figure file (#1013): what state it
is in, and what stamping it produces. No TeX, no file walk."""

import re
import tomllib
from pathlib import Path

import pytest

from chitragupta import figure
from chitragupta.figure import State

REPO_ROOT = Path(__file__).resolve().parent.parent
BLOCK = REPO_ROOT / "assets" / "tikz" / "cg-figstyle.tex"
REGISTER = REPO_ROOT / "assets" / "tikz" / "cg-figstyle.versions.toml"

LIBS = "\\usetikzlibrary{arrows.meta,positioning}%\n"
PICTURE = "\\begin{tikzpicture}[cg]\n  \\node[cgbox] (a) {A};\n\\end{tikzpicture}%\n"
HEAD = "% A pipeline.\n"


@pytest.fixture(scope="module")
def house():
    return figure.load_house()


def old_block(house, version=0):
    """A stand-in for a past release: the current block with one value
    changed and its marker naming `version`."""
    text = house.text.replace(" v1 ", f" v{version} ", 1).replace("0.95pt", "0.9pt", 1)
    return text


def house_with_history(house):
    """`house`, plus a released v0 that `old_block` reproduces."""
    released = {**house.released, figure.digest(old_block(house)): 0}
    return figure.House(text=house.text, version=house.version, released=released)


class TestTheRegisterAndTheBlockAgree:
    def test_the_current_block_is_registered_under_its_own_version(self, house):
        register = tomllib.loads(REGISTER.read_text(encoding="utf-8"))
        assert register[f"v{house.version}"] == figure.digest(house.text)

    def test_the_block_names_the_highest_registered_version(self, house):
        register = tomllib.loads(REGISTER.read_text(encoding="utf-8"))
        assert house.version == max(int(key[1:]) for key in register)

    def test_every_register_key_is_a_version(self):
        register = tomllib.loads(REGISTER.read_text(encoding="utf-8"))
        assert register and all(re.fullmatch(r"v\d+", key) for key in register)

    def test_the_block_file_is_one_whole_region(self, house):
        region = figure.classify(house.text, house)
        assert (region.state, region.start, region.end) == (State.CURRENT, 0, len(house.text))


class TestClassify:
    def test_no_markers_is_missing(self, house):
        assert figure.classify(HEAD + LIBS + PICTURE, house).state is State.MISSING

    def test_the_current_block_is_current(self, house):
        text = HEAD + house.text + LIBS + PICTURE
        assert figure.classify(text, house).state is State.CURRENT

    def test_a_released_older_block_is_stale(self, house):
        history = house_with_history(house)
        text = HEAD + old_block(house) + LIBS + PICTURE
        assert figure.classify(text, history).state is State.STALE

    def test_one_edited_value_is_modified(self, house):
        edited = house.text.replace("0.95pt", "0.9pt", 1)
        assert figure.classify(HEAD + edited + PICTURE, house).state is State.MODIFIED

    def test_a_style_added_inside_the_markers_is_modified(self, house):
        lines = house.text.splitlines(keepends=True)
        edited = "".join(lines[:-1] + ["\\tikzset{mine/.style={red}}%\n", lines[-1]])
        assert figure.classify(edited + PICTURE, house).state is State.MODIFIED

    def test_a_newer_unknown_version_is_modified_and_keeps_its_number(self, house):
        newer = house.text.replace(" v1 ", " v9 ", 1)
        region = figure.classify(newer + PICTURE, house)
        assert (region.state, region.marker_version) == (State.MODIFIED, 9)

    def test_crlf_line_endings_alone_do_not_make_it_modified(self, house):
        text = (HEAD + house.text + PICTURE).replace("\n", "\r\n")
        assert figure.classify(text, house).state is State.CURRENT

    def test_a_missing_final_newline_after_the_end_marker_is_still_current(self, house):
        assert figure.classify(house.text.rstrip("\n"), house).state is State.CURRENT

    def test_a_reindented_region_is_modified_not_missing(self, house):
        indented = "".join("  " + line for line in house.text.splitlines(keepends=True))
        assert figure.classify(indented + PICTURE, house).state is State.MODIFIED

    @pytest.mark.parametrize(
        "make",
        [
            lambda b: b.rsplit("% >>> end", 1)[0] + PICTURE,  # start, no end
            lambda b: b.split("\n", 1)[1] + PICTURE,  # end, no start
            lambda b: b + b + PICTURE,  # two regions
            lambda b: b.split("\n", 1)[1] + b.split("\n", 1)[0] + "\n",  # end above start
        ],
        ids=["no-end", "no-start", "twice", "inverted"],
    )
    def test_unpaired_or_repeated_markers_are_malformed(self, house, make):
        assert figure.classify(make(house.text), house).state is State.MALFORMED


class TestStamp:
    def test_a_missing_block_goes_above_the_first_library_line(self, house):
        stamped = figure.stamp(HEAD + LIBS + PICTURE, house)
        assert stamped == HEAD + house.text + LIBS + PICTURE

    def test_with_no_library_line_it_goes_above_the_picture(self, house):
        assert figure.stamp(HEAD + PICTURE, house) == HEAD + house.text + PICTURE

    def test_a_commented_out_library_line_is_not_an_anchor(self, house):
        text = "% \\usetikzlibrary{calc}\n" + PICTURE
        assert figure.stamp(text, house) == "% \\usetikzlibrary{calc}\n" + house.text + PICTURE

    def test_a_file_with_no_picture_cannot_be_stamped(self, house):
        assert figure.stamp("% only a comment\n", house) is None

    def test_a_current_file_comes_back_unchanged(self, house):
        text = HEAD + house.text + LIBS + PICTURE
        assert figure.stamp(text, house) == text

    def test_stamping_twice_is_stamping_once(self, house):
        once = figure.stamp(HEAD + LIBS + PICTURE, house)
        assert figure.stamp(once, house) == once

    def test_a_stale_block_is_replaced_and_nothing_else_moves(self, house):
        history = house_with_history(house)
        text = HEAD + old_block(house) + LIBS + PICTURE
        assert figure.stamp(text, history) == HEAD + house.text + LIBS + PICTURE

    def test_crlf_is_kept_throughout(self, house):
        text = (HEAD + LIBS + PICTURE).replace("\n", "\r\n")
        stamped = figure.stamp(text, house)
        assert stamped == (HEAD + house.text + LIBS + PICTURE).replace("\n", "\r\n")

    @pytest.mark.parametrize("state", ["modified", "malformed"])
    def test_an_edited_or_broken_region_is_never_stamped(self, house, state):
        text = {
            "modified": house.text.replace("0.95pt", "0.9pt", 1) + PICTURE,
            "malformed": house.text + house.text + PICTURE,
        }[state]
        assert figure.stamp(text, house) is None


class TestFinding:
    def test_current_says_nothing(self, house):
        assert figure.finding(house.text + PICTURE, house) is None

    def test_missing_names_the_command(self, house):
        assert "python -m chitragupta figure sync" in figure.finding(PICTURE, house)

    def test_stale_names_both_versions(self, house):
        history = house_with_history(house)
        message = figure.finding(old_block(house) + PICTURE, history)
        assert "v0" in message and f"v{house.version}" in message

    def test_modified_says_sync_will_not_touch_it(self, house):
        edited = house.text.replace("0.95pt", "0.9pt", 1)
        assert "will not touch" in figure.finding(edited + PICTURE, house)

    def test_a_newer_version_says_to_upgrade(self, house):
        newer = house.text.replace(" v1 ", " v9 ", 1)
        assert "newer" in figure.finding(newer + PICTURE, house)


class TestLoadHouse:
    def test_a_missing_block_raises_oserror(self, tmp_path):
        with pytest.raises(OSError):
            figure.load_house(block=tmp_path / "absent.tex", register=REGISTER)

    def test_a_block_with_no_start_marker_raises_valueerror(self, tmp_path):
        bad = tmp_path / "b.tex"
        bad.write_text("\\tikzset{}\n", encoding="utf-8")
        with pytest.raises(ValueError):
            figure.load_house(block=bad, register=REGISTER)
```

`old_block` assumes `0.95pt` occurs in the block (it does, in the
`cgshield` pic). If a later block drops it, change the literal. The
test only needs a one-value edit.

- [ ] **Step 3: Run them and see them fail**

Run: `pytest tests/test_figure_block.py -q`
Expected: FAIL at collection, `cannot import name 'figure'`.

- [ ] **Step 4: Implement `_block.py`**

```python
"""The house figure-style block as a region inside a figure file (#1013).

<module docstring: why a marker region and not \\input (one paragraph,
pointing at issue #1013 and docs/TIKZ-STYLE.md); what the five states
mean; why a modified region is never overwritten -- "a modified region
is a conversation, not a merge". Match the house docstring density.>
"""

import hashlib
import re
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from chitragupta import config
from chitragupta._tex_comments import strip_comments

# Leading whitespace is tolerated when *finding* a marker so that a
# re-indented region reads as modified rather than missing -- missing
# would stamp a second copy beside it.
_START_RE = re.compile(r"^[ \t]*% >>> chitragupta figure style v(\d+)\b[^\n]*$", re.M)
_END_RE = re.compile(r"^[ \t]*% >>> end chitragupta figure style <<<[ \t]*\r?$", re.M)
_ANCHOR_RE = re.compile(r"\\usetikzlibrary\b|\\begin\s*\{tikzpicture\}")
_COMMAND = "python -m chitragupta figure sync"


class State(Enum):
    CURRENT = "current"
    STALE = "stale"
    MODIFIED = "modified"
    MISSING = "missing"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class House:
    text: str
    version: int
    released: dict[str, int]


@dataclass(frozen=True)
class Region:
    state: State
    marker_version: int | None = None
    start: int | None = None
    end: int | None = None


def digest(text: str) -> str:
    """sha256 of a region, CRLF folded and one final newline ensured."""
    lf = text.replace("\r\n", "\n")
    if not lf.endswith("\n"):
        lf += "\n"
    return hashlib.sha256(lf.encode("utf-8")).hexdigest()


def load_house(block: Path | None = None, register: Path | None = None) -> House:
    block = block or config.shipped("assets", "tikz", "cg-figstyle.tex")
    register = register or config.shipped("assets", "tikz", "cg-figstyle.versions.toml")
    text = block.read_text(encoding="utf-8").replace("\r\n", "\n")
    marker = _START_RE.match(text)
    if marker is None:
        raise ValueError(f"{block}: no figure-style start marker on its first line")
    with register.open("rb") as handle:
        recorded = tomllib.load(handle)
    released = {value: int(key[1:]) for key, value in recorded.items()}
    return House(text=text, version=int(marker.group(1)), released=released)


def _line_end(text: str, offset: int) -> int:
    """`offset` moved past the line break that ends its line, if any."""
    if text.startswith("\r\n", offset):
        return offset + 2
    return offset + 1 if text.startswith("\n", offset) else offset


def classify(text: str, house: House) -> Region:
    starts = list(_START_RE.finditer(text))
    ends = list(_END_RE.finditer(text))
    if not starts and not ends:
        return Region(State.MISSING)
    if len(starts) != 1 or len(ends) != 1 or ends[0].start() < starts[0].start():
        return Region(State.MALFORMED)
    start, end = starts[0].start(), _line_end(text, ends[0].end())
    marker_version = int(starts[0].group(1))
    known = house.released.get(digest(text[start:end]))
    if known is None:
        state = State.MODIFIED
    else:
        state = State.CURRENT if known == house.version else State.STALE
    return Region(state, marker_version, start, end)


def _anchor(text: str) -> int | None:
    """Offset of the first line whose uncommented part loads a library
    or opens a picture."""
    offset = 0
    for line in text.splitlines(keepends=True):
        if _ANCHOR_RE.search(strip_comments(line)):
            return offset
        offset += len(line)
    return None


def stamp(text: str, house: House) -> str | None:
    region = classify(text, house)
    if region.state is State.CURRENT:
        return text
    newline = "\r\n" if "\r\n" in text else "\n"
    block = house.text.replace("\n", newline)
    if region.state is State.STALE:
        return text[: region.start] + block + text[region.end :]
    if region.state is State.MISSING:
        at = _anchor(text)
        return None if at is None else text[:at] + block + text[at:]
    return None


def finding(text: str, house: House) -> str | None:
    region = classify(text, house)
    if region.state is State.CURRENT:
        return None
    if region.state is State.MISSING:
        return f"carries no house figure-style block -- `{_COMMAND}` stamps one"
    if region.state is State.STALE:
        old = house.released[digest(text[region.start : region.end])]
        return f"house figure-style block is v{old}, current is v{house.version} -- `{_COMMAND}` refreshes it"
    if region.state is State.MALFORMED:
        return f"house figure-style markers are unpaired or repeated; `{_COMMAND}` will not touch it"
    if (region.marker_version or 0) > house.version:
        return (f"house figure-style block is v{region.marker_version}, newer than this "
                f"install's v{house.version}; upgrade chitragupta rather than edit it")
    return (f"house figure-style block was edited inside its markers; `{_COMMAND}` will not "
            "touch it -- move a local style below the block (docs/TIKZ-STYLE.md)")
```

Note on the "missing final newline" test: when the end marker is the
last line with no break, `_line_end` returns the marker's end and
`digest` adds the newline, so the region still matches. `stamp` on a
CURRENT file returns it unchanged, so the missing newline is not "fixed"
either. That is correct: the file is current.

`chitragupta/figure/__init__.py` re-exports
`House, Region, State, classify, digest, finding, load_house, stamp`
from `_block` (and, after Task 3, `Outcome, run` from `_sync`), with a
short docstring naming #1013 and pointing at `_block`.

Wrap any line over the project's line length (run `ruff format`).
`finding` is 9 statements, within the limit.

- [ ] **Step 5: Run the tests**

Run: `pytest tests/test_figure_block.py -q`
Expected: all PASS. If the v1 digest test fails, the block changed after
`10ac21f`. Recompute with Step 1's command and fix the register.

- [ ] **Step 6: Commit**

```bash
git add assets/tikz/cg-figstyle.versions.toml chitragupta/figure tests/test_figure_block.py
git commit -m "Classify and stamp the house figure-style region"
```

---

### Task 3: `chitragupta figure sync`

**Files:**

- Create: `chitragupta/figure/_sync.py`, `chitragupta/figure/__main__.py`
- Modify: `chitragupta/figure/__init__.py` (re-exports)
- Modify: `chitragupta/__main__.py` (`COMMANDS`; add `figure` to the
  module docstring's package-command list)
- Modify: `tests/test_package_entrypoint.py` (assert `"figure" in entry.COMMANDS`)
- Test: `tests/test_figure_sync.py`

**Interfaces:**

- Consumes: everything Task 2 produces;
  `chitragupta._atomic_write.write_atomically(path, data: bytes | str)`;
  `chitragupta.config.DRAFTS_DIR`.
- Produces:
  - `@dataclass(frozen=True) class Outcome`: `path: Path`, `action: str`,
    `detail: str = ""`. `action` is one of `current`, `stamped`,
    `refreshed`, `missing`, `stale` (the last two in `--check` mode
    only), `modified`, `malformed`, `no-picture`, `skipped`.
  - `figure_files(paths: list[Path]) -> list[Path]`. With no paths, it
    returns every `*.tex` whose parent directory is named `figures`
    under `config.DRAFTS_DIR`. A file path is taken as given, and a
    directory contributes `sorted(dir.rglob("*.tex"))`. The result is
    sorted and deduplicated.
  - `sync_file(path: Path, house: House, *, check: bool) -> Outcome`
  - `run(paths: list[Path], house: House, *, check: bool) -> list[Outcome]`
  - `chitragupta.figure.__main__.main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing tests**

`tests/test_figure_sync.py`:

```python
"""`chitragupta figure sync`: the walk, the writes, and the exit codes."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import figure
from chitragupta.figure import __main__ as cli
from tests.conftest import needs_tikz

REPO_ROOT = Path(__file__).resolve().parent.parent
PICTURE = "\\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc,shadows.blur}%\n" \
          "\\begin{tikzpicture}[cg]\n  \\node[cgbox] (a) {\\cglab{Parse}{text out}};\n\\end{tikzpicture}%\n"


@pytest.fixture(scope="module")
def house():
    return figure.load_house()


@pytest.fixture
def figures(tmp_path):
    directory = tmp_path / "drafts" / "topic" / "figures"
    directory.mkdir(parents=True)
    return directory


def write(path: Path, text: str) -> Path:
    path.write_bytes(text.encode("utf-8"))
    return path


class TestSync:
    def test_a_bare_figure_is_stamped(self, figures, house):
        path = write(figures / "a.tex", PICTURE)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "stamped"
        assert path.read_text(encoding="utf-8") == house.text + PICTURE

    def test_running_it_twice_changes_nothing_the_second_time(self, figures, house):
        path = write(figures / "a.tex", PICTURE)
        figure.run([figures], house, check=False)
        first = path.read_bytes()
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "current" and path.read_bytes() == first

    def test_a_modified_region_is_reported_with_a_diff_and_not_touched(self, figures, house):
        edited = house.text.replace("0.95pt", "0.9pt", 1) + PICTURE
        path = write(figures / "a.tex", edited)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "modified"
        assert "-" in outcome.detail and "0.9pt" in outcome.detail
        assert path.read_text(encoding="utf-8") == edited

    def test_check_writes_nothing(self, figures, house):
        path = write(figures / "a.tex", PICTURE)
        [outcome] = figure.run([figures], house, check=True)
        assert outcome.action == "missing" and path.read_text(encoding="utf-8") == PICTURE

    def test_crlf_survives_a_stamp(self, figures, house):
        path = write(figures / "a.tex", PICTURE.replace("\n", "\r\n"))
        figure.run([figures], house, check=False)
        assert path.read_bytes() == (house.text + PICTURE).replace("\n", "\r\n").encode()

    def test_not_utf8_is_skipped_and_the_walk_goes_on(self, figures, house):
        (figures / "a.tex").write_bytes(b"\xff\xfe junk")
        write(figures / "b.tex", PICTURE)
        outcomes = figure.run([figures], house, check=False)
        assert [o.action for o in outcomes] == ["skipped", "stamped"]

    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
    def test_a_symlink_is_never_written_through(self, figures, house, tmp_path):
        target = write(tmp_path / "elsewhere.tex", PICTURE)
        (figures / "a.tex").symlink_to(target)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "skipped" and target.read_text(encoding="utf-8") == PICTURE

    @pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="chmod is not enforced")
    def test_an_unwritable_file_is_reported_not_raised(self, figures, house):
        path = write(figures / "a.tex", PICTURE)
        # write_atomically creates a temp sibling, so the *directory* is
        # what has to refuse the write.
        figures.chmod(0o500)
        try:
            [outcome] = figure.run([figures], house, check=False)
        finally:
            figures.chmod(0o700)
        assert outcome.action == "skipped" and outcome.path == path
        assert path.read_text(encoding="utf-8") == PICTURE

    def test_no_picture_is_reported(self, figures, house):
        write(figures / "a.tex", "% nothing drawn\n")
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "no-picture"


class TestFigureFiles:
    def test_the_default_walk_is_every_figures_dir_under_drafts(self, tmp_path, monkeypatch):
        drafts = tmp_path / "drafts"
        for rel in ["t/figures/a.tex", "book/unit/figures/b.tex", "t/chapter.tex", "t/figures/a.txt"]:
            (drafts / rel).parent.mkdir(parents=True, exist_ok=True)
            (drafts / rel).write_text("x", encoding="utf-8")
        monkeypatch.setattr("chitragupta.config.DRAFTS_DIR", drafts)
        found = figure.figure_files([])
        assert [p.relative_to(drafts).as_posix() for p in found] == [
            "book/unit/figures/b.tex", "t/figures/a.tex"
        ]


class TestCli:
    def test_sync_exits_zero_even_with_a_modified_file(self, figures, house, capsys):
        write(figures / "a.tex", house.text.replace("0.95pt", "0.9pt", 1) + PICTURE)
        assert cli.main(["sync", str(figures)]) == 0
        assert "modified" in capsys.readouterr().out

    def test_check_exits_one_when_anything_is_not_current(self, figures):
        write(figures / "a.tex", PICTURE)
        assert cli.main(["sync", "--check", str(figures)]) == 1

    def test_check_exits_zero_when_everything_is_current(self, figures, house):
        write(figures / "a.tex", house.text + PICTURE)
        assert cli.main(["sync", "--check", str(figures)]) == 0

    def test_no_figure_files_says_so_and_exits_zero(self, tmp_path, capsys):
        assert cli.main(["sync", str(tmp_path)]) == 0
        assert "no figure files" in capsys.readouterr().out

    def test_a_broken_install_exits_two(self, figures, monkeypatch, capsys):
        def broken():
            raise OSError("cg-figstyle.tex: not found")
        monkeypatch.setattr(cli, "load_house", broken)
        assert cli.main(["sync", str(figures)]) == 2
        assert "cg-figstyle.tex" in capsys.readouterr().err

    def test_the_top_level_entry_point_reaches_it(self):
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta", "figure", "sync", "--help"],
            capture_output=True, text=True, cwd=REPO_ROOT, check=False,
        )
        assert result.returncode == 0 and "--check" in result.stdout


class TestThisRepositorysOwnFigures:
    def test_every_shipped_scaffold_and_exemplar_is_current(self, house):
        outcomes = figure.run([REPO_ROOT / "assets" / "tikz"], house, check=True)
        assert len(outcomes) > 1
        assert {o.action for o in outcomes} == {"current"}


@needs_tikz
class TestRoundTrip:
    def test_a_stamped_figure_compiles_under_tikz_alone(self, figures, house, tmp_path):
        """The property the travel rule exists for (#1013's acceptance)."""
        path = write(figures / "a.tex", PICTURE)
        figure.run([figures], house, check=False)
        doc = tmp_path / "probe.tex"
        doc.write_text(
            "\\documentclass{article}\n\\usepackage{tikz}\n\\begin{document}\n"
            f"\\input{{{path.as_posix()}}}\n\\end{{document}}\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [shutil.which("pdflatex"), "-interaction=nonstopmode", "-halt-on-error", doc.name],
            cwd=tmp_path, capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stdout[-2000:]
```

`TestThisRepositorysOwnFigures` passes `assets/tikz`, which includes
`cg-figstyle.tex` itself. The block file is one whole region, so it is
current (Task 2 asserts this).

- [ ] **Step 2: Run them and see them fail**

Run: `pytest tests/test_figure_sync.py -q`
Expected: FAIL, `cannot import name '__main__'` / `figure.run` missing.

- [ ] **Step 3: Implement `_sync.py`**

```python
"""Walk figure files and bring each one's house block up to date (#1013).

<docstring: what gets walked by default and why `figures/` only
(docs/WRITING-STANDARDS.md §10); why a symlink is skipped rather than
followed (a write would land outside the tree the user named); why a
failure on one file never stops the walk -- an aid reports and carries
on, like every aid in the review layer.>
"""

import difflib
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config
from chitragupta._atomic_write import write_atomically
from chitragupta.figure._block import House, State, classify, stamp


@dataclass(frozen=True)
class Outcome:
    path: Path
    action: str
    detail: str = ""


def figure_files(paths: list[Path]) -> list[Path]:
    if not paths:
        found = (p for p in config.DRAFTS_DIR.rglob("*.tex") if p.parent.name == "figures")
        return sorted(set(found))
    found: set[Path] = set()
    for path in paths:
        found.update(sorted(path.rglob("*.tex")) if path.is_dir() else [path])
    return sorted(found)


def _diff(region: str, house: House, name: str) -> str:
    lines = difflib.unified_diff(
        house.text.splitlines(keepends=True),
        region.replace("\r\n", "\n").splitlines(keepends=True),
        fromfile=f"house block v{house.version}", tofile=name,
    )
    return "".join(lines)


def _read(path: Path) -> str | Outcome:
    if path.is_symlink():
        return Outcome(path, "skipped", "a symlink; sync the file it points to directly")
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return Outcome(path, "skipped", "not UTF-8")
    except OSError as exc:
        return Outcome(path, "skipped", str(exc))


def sync_file(path: Path, house: House, *, check: bool) -> Outcome:
    text = _read(path)
    if isinstance(text, Outcome):
        return text
    region = classify(text, house)
    if region.state is State.CURRENT:
        return Outcome(path, "current")
    if region.state is State.MALFORMED:
        return Outcome(path, "malformed", "markers unpaired or repeated; not touched")
    if region.state is State.MODIFIED:
        return Outcome(path, "modified", _diff(text[region.start : region.end], house, path.name))
    new = stamp(text, house)
    if new is None:
        return Outcome(path, "no-picture", "no \\usetikzlibrary or tikzpicture to stamp above")
    if check:
        return Outcome(path, region.state.value)  # "missing" or "stale"
    try:
        write_atomically(path, new.encode("utf-8"))
    except OSError as exc:
        return Outcome(path, "skipped", str(exc))
    return Outcome(path, "stamped" if region.state is State.MISSING else "refreshed")


def run(paths: list[Path], house: House, *, check: bool) -> list[Outcome]:
    return [sync_file(path, house, check=check) for path in figure_files(paths)]
```

`sync_file` has about 17 statements. If cognitive complexity goes over
25, move the three early returns for MALFORMED, MODIFIED and no-picture
into a `_refusal(path, text, region, house) -> Outcome | None` helper.

For a modified region whose marker names a version newer than the
house's, prefix `detail` with the same "newer than this install"
sentence `finding` uses. Add a test for it beside
`test_a_modified_region_is_reported_with_a_diff_and_not_touched`
(Review Focus 2).

- [ ] **Step 4: Implement `__main__.py`**

```python
"""`python -m chitragupta figure sync [PATH ...] [--check]` (#1013).

<docstring: what each exit code means and why 0 on findings -- an aid
reports; `--check` is the one mode that fails, and it exists for a
hook. Name docs/TIKZ-STYLE.md for what to do with a modified region.>
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from chitragupta.figure._block import load_house
from chitragupta.figure._sync import Outcome, run
from chitragupta.progname import prog_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog_for("figure"),
        description="Keep the house figure-style block current in every figure file.",
    )
    verbs = parser.add_subparsers(dest="verb", required=True)
    sync = verbs.add_parser("sync", help="stamp, refresh and report the block in figure files")
    sync.add_argument("paths", nargs="*", type=Path,
                      help="files or directories (default: content/drafts/**/figures/*.tex)")
    sync.add_argument("--check", action="store_true",
                      help="write nothing; exit 1 if any file is not current")
    return parser


def _print(outcomes: list[Outcome]) -> None:
    for outcome in outcomes:
        if outcome.action != "current":
            print(f"{outcome.action:<10} {outcome.path}")
            for line in outcome.detail.splitlines():
                print(f"    {line}")
    counts = Counter(o.action for o in outcomes)
    print("figure sync: " + ", ".join(f"{n} {a}" for a, n in sorted(counts.items())))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        house = load_house()
    except (OSError, ValueError) as exc:
        print(f"figure sync: cannot read the house block: {exc}. "
              "`chitragupta doctor` checks the install.", file=sys.stderr)
        return 2
    outcomes = run(args.paths, house, check=args.check)
    if not outcomes:
        print("figure sync: no figure files found")
        return 0
    _print(outcomes)
    return 1 if args.check and any(o.action != "current" for o in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
```

`tomllib.TOMLDecodeError` is a `ValueError` subclass, so a corrupt
register is covered by the same `except`. Check how `prog_for` is called
by `chitragupta/init.py` and match it.

- [ ] **Step 5: Wire the top-level entry**

In `chitragupta/__main__.py`'s `COMMANDS`:

```python
    "figure": (
        "chitragupta.figure.__main__",
        "keep the house figure-style block current in figure files -- sync, sync --check",
    ),
```

Extend the module docstring's package-command list with
`chitragupta figure sync [PATH] ... stamp the house figure-style block (#1013)`,
and add `assert "figure" in entry.COMMANDS` to
`tests/test_package_entrypoint.py::TestDispatch::test_commands_are_reachable_beside_the_layers`.

- [ ] **Step 6: Run the tests**

Run:

```bash
pytest tests/test_figure_sync.py tests/test_figure_block.py \
       tests/test_package_entrypoint.py -q
```

Expected: PASS (`TestRoundTrip` skips without TeX; run it on a host with
TeX Live before opening the PR and say so in the test plan).
`tests/test_packaging_command_table.py` will fail until Task 6 adds the
docs row. That is expected; note it and move on.

- [ ] **Step 7: Commit**

```bash
git add chitragupta/figure chitragupta/__main__.py tests/test_figure_sync.py tests/test_package_entrypoint.py
git commit -m "Add chitragupta figure sync"
```

---

### Task 4: The renderer reports a stale or missing block

**Files:**

- Create: `chitragupta/render_output/_figure_style.py`
- Modify: `chitragupta/render_output/_substitution.py:63-70` (`_draft_warnings`)
- Modify: `tests/conftest.py` (a stamped figure for "clean" fixtures)
- Test: `tests/test_render_output_figure_style.py`

**Interfaces:**

- Consumes: `chitragupta.figure.load_house`, `chitragupta.figure.finding`;
  `render_output._figures._figure_refs(text) -> list[str]` and
  `_resolve_sibling(draft_dir, ref) -> Path | None`.
- Produces:
  `render_output._figure_style.warnings(text: str, input_path: Path) -> list[str]`.
  Each item reads `"<ref>: <finding>"`. The list is empty when every
  referenced `.tex` figure is current, unresolvable (already reported by
  `_figure_warnings`) or unreadable.

- [ ] **Step 1: Write the failing tests**

```python
"""The renderer reports a figure's house block and never rewrites it (#1013)."""

from chitragupta import figure
from chitragupta.render_output import _figure_style
from tests.conftest import MARKED_INPUT, MARKED_MD, TIKZ_FIGURE, figure_pair


def draft(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


class TestWarnings:
    def test_a_missing_block_is_reported_with_the_command(self, tmp_path):
        figure_pair(tmp_path)
        [line] = _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert line.startswith("figures/fig1.tex: ") and "figure sync" in line

    def test_a_latex_draft_is_checked_too(self, tmp_path):
        figure_pair(tmp_path)
        assert _figure_style.warnings(MARKED_INPUT, draft(tmp_path, "d.tex", MARKED_INPUT))

    def test_a_current_block_says_nothing(self, tmp_path):
        figure_pair(tmp_path)
        source = tmp_path / "figures" / "fig1.tex"
        source.write_text(figure.load_house().text + TIKZ_FIGURE, encoding="utf-8")
        assert _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD)) == []

    def test_the_figure_file_is_not_written(self, tmp_path):
        figure_pair(tmp_path)
        source = tmp_path / "figures" / "fig1.tex"
        before = source.read_bytes()
        _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert source.read_bytes() == before

    def test_an_unresolvable_figure_is_left_to_figure_warnings(self, tmp_path):
        assert _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD)) == []

    def test_a_figure_named_twice_is_reported_once(self, tmp_path):
        figure_pair(tmp_path)
        body = MARKED_MD + MARKED_MD
        assert len(_figure_style.warnings(body, draft(tmp_path, "d.md", body))) == 1

    def test_a_broken_install_is_one_line_not_a_crash(self, tmp_path, monkeypatch):
        figure_pair(tmp_path)
        def broken():
            raise OSError("gone")
        monkeypatch.setattr(_figure_style, "load_house", broken)
        [line] = _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert "not checked" in line

    def test_no_figures_never_loads_the_block(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_figure_style, "load_house", lambda: 1 / 0)
        assert _figure_style.warnings("No figure.\n", draft(tmp_path, "d.md", "x")) == []


class TestItReachesTheRenderWarnings:
    def test_draft_warnings_carries_it_under_the_figure_tag(self, tmp_path):
        from chitragupta.render_output._substitution import _draft_warnings
        figure_pair(tmp_path)
        tags = _draft_warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert any(tag == "figure" and "figure sync" in text for tag, text in tags)
```

- [ ] **Step 2: Run them and see them fail**

Run: `pytest tests/test_render_output_figure_style.py -q`
Expected: FAIL, no module `_figure_style`.

- [ ] **Step 3: Implement**

```python
"""Whether each figure a draft names carries the current house block (#1013).

Reports; never writes. A renderer that rewrites its inputs at render
time is ruled out by #1013: the source a person reviewed would no
longer be the source that rendered. `python -m chitragupta figure sync`
is the writer, and every line here names it.
"""

from pathlib import Path

from chitragupta.figure import finding, load_house
from chitragupta.render_output._figures import _figure_refs, _resolve_sibling


def warnings(text: str, input_path: Path) -> list[str]:
    refs = [ref for ref in dict.fromkeys(_figure_refs(text)) if ref.endswith(".tex")]
    if not refs:
        return []
    try:
        house = load_house()
    except (OSError, ValueError) as exc:
        return [f"house figure-style block unreadable ({exc}); figures not checked"]
    found = []
    for ref in refs:
        resolved = _resolve_sibling(input_path.parent, ref)
        if resolved is None:
            continue
        message = finding(resolved.read_text(encoding="utf-8", errors="replace"), house)
        if message:
            found.append(f"{ref}: {message}")
    return found
```

`errors="replace"` for `_figure_has_citekey`'s reason: an advisory
check must not be what stops a render. In `_substitution.py`:

```python
        [("figure", w) for w in _figure_warnings(draft_text, input_path)]
        + [("figure", w) for w in _figure_style.warnings(draft_text, input_path)]
```

with `from chitragupta.render_output import _figure_style` beside the
other imports. If importing `chitragupta.figure` from `render_output`
raises a circular-import error, Task 1 missed an importer of
`_tikz_libraries._COMMENT_RE`. Grep for it, don't work around it.

- [ ] **Step 4: Fix the "renders clean" fixtures**

Run: `pytest -q -x tests/test_render_output*.py tests/test_figure_layout.py tests/test_tikz_scaffolds.py`

Every failure should be a test asserting no figure warning (e.g.
`test_a_clean_markdown_pair_warns_about_nothing`, and any test that
asserts empty stderr from a figure render) whose fixture is
`conftest.TIKZ_FIGURE`. Fix the fixture, not the assertion. Add to
`tests/conftest.py`:

```python
def stamped(tikz: str = TIKZ_FIGURE) -> str:
    """`tikz` with the current house block above it, as `figure sync`
    leaves a figure: what a *clean* figure file looks like since #1013."""
    from chitragupta import figure
    return figure.stamp(tikz, figure.load_house())
```

Give `figure_pair` a keyword `house: bool = False` that writes
`stamped()` instead of `TIKZ_FIGURE`, and pass `house=True` from the
clean-pair tests. Leave `TIKZ_FIGURE` and the default alone: other tests
compare rendered output against it byte for byte. `TIKZ_FIGURE` has no
`\usetikzlibrary`, so `stamp` places the block above the
`\begin{tikzpicture}` line. Check that `stamped()` is not `None`.

- [ ] **Step 5: Run the render suite**

Run: `pytest -q tests/test_render_output*.py tests/test_render_output_figure_style.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add chitragupta/render_output/_figure_style.py chitragupta/render_output/_substitution.py \
        tests/conftest.py tests/test_render_output_figure_style.py tests/test_render_output*.py
git commit -m "Report a figure's stale or missing house block at render time"
```

---

### Task 5: An advisory check in the git pre-commit hook

**Files:**

- Modify: `git-hooks/pre-commit`
- Test: `tests/test_git_hooks.py`

**Interfaces:**

- Consumes: `python -m chitragupta figure sync --check PATH...`, exit 0/1/2.
- Produces: the hook's interpreter override, `CHITRAGUPTA_PYTHON`
  (default: `.venv/bin/python` if executable, else `python3`). Tests use
  it to supply a fake.

- [ ] **Step 1: Write the failing tests**

Add beside `fake_actionlint` in `tests/test_git_hooks.py`:

```python
def fake_python(bin_dir: Path, exit_code: int) -> Path:
    """A stand-in interpreter that records its argv and exits `exit_code`."""
    script = bin_dir / "fake-python"
    script.write_text(
        f'#!/usr/bin/env bash\necho "$@" > "{bin_dir}/python-args"\n'
        f'echo "stale      figures/a.tex"\nexit {exit_code}\n'
    )
    script.chmod(0o755)
    return script
```

Read `HookRepo.run` first and extend it with an optional `python`
argument that sets `CHITRAGUPTA_PYTHON` in the hook's environment.
Follow its existing style for `with_actionlint`. Then:

```python
class TestTheFigureCheck:
    def test_a_staged_figure_is_checked(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        result = repo.run(python=fake_python(tmp_path, 0))
        assert "figure sync --check content/drafts/t/figures/a.tex" in (tmp_path / "python-args").read_text()
        assert result.returncode == 0

    def test_a_staged_scaffold_is_checked(self, repo, tmp_path):
        repo.stage("assets/tikz/pipeline.tex", "x")
        repo.run(python=fake_python(tmp_path, 0))
        assert "assets/tikz/pipeline.tex" in (tmp_path / "python-args").read_text()

    def test_a_stale_figure_is_reported_and_does_not_block(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        result = repo.run(python=fake_python(tmp_path, 1))
        assert result.returncode == 0
        assert "figure sync" in result.stderr

    def test_an_interpreter_that_cannot_run_it_is_one_line(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        result = repo.run(python=fake_python(tmp_path, 2))
        assert result.returncode == 0 and "not checked" in result.stderr

    def test_an_unrelated_tex_file_is_not_a_figure(self, repo, tmp_path):
        repo.stage("content/drafts/t/chapter.tex", "x")
        repo.run(python=fake_python(tmp_path, 0))
        assert not (tmp_path / "python-args").exists()

    def test_the_workflow_lint_still_runs_after_it(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        repo.stage(".github/workflows/ci.yml", "on: push\n")
        result = repo.run(with_actionlint=1, python=fake_python(tmp_path, 1))
        assert result.returncode == 1  # actionlint's block, not the figure's
```

If `fake_python` writes its args file to `bin_dir` and `bin_dir` is the
same `tmp_path` the repo lives in, keep them apart (e.g. `tmp_path / "bin"`).
Adjust to how `HookRepo` lays out its directories.

- [ ] **Step 2: Run them and see them fail**

Run: `pytest tests/test_git_hooks.py -q -k Figure`
Expected: FAIL, no `python-args` written.

- [ ] **Step 3: Restructure the hook**

The hook currently ends with `[ "$staged" -eq 1 ] || exit 0` before the
actionlint section, so the figure section has to come first and must
never `exit`. Replace the single staged-workflow loop with one loop that
collects both lists (keep `-z` and `ACMR`, and their comments):

```bash
staged=0
figures=()
while IFS= read -r -d '' file; do
    case "$file" in
        .github/workflows/*.yml|.github/workflows/*.yaml) staged=1 ;;
        assets/tikz/*.tex|content/drafts/*/figures/*.tex) figures+=("$file") ;;
    esac
done < <(git diff --cached --name-only --diff-filter=ACMR -z)

# The house figure-style block (#1013). Advisory: a stale block renders
# fine and `figure sync` fixes it in one command, so this reports and
# never refuses the commit -- the opposite of actionlint below, whose
# verdict CI would enforce anyway. It checks the working tree, not the
# index: a partially staged figure is checked as it is on disk.
if [ "${#figures[@]}" -gt 0 ]; then
    py="${CHITRAGUPTA_PYTHON:-}"
    if [ -z "$py" ]; then
        if [ -x .venv/bin/python ]; then py=.venv/bin/python; else py=python3; fi
    fi
    set +e
    report="$("$py" -m chitragupta figure sync --check "${figures[@]}" 2>&1)"
    status=$?
    set -e
    case "$status" in
        0) ;;
        1) echo "$report" >&2
           echo "pre-commit: a figure's house style block is not current (advisory)." >&2
           echo "            python -m chitragupta figure sync" >&2 ;;
        *) echo "pre-commit: figure sync could not run, figures not checked." >&2 ;;
    esac
fi

[ "$staged" -eq 1 ] || exit 0
```

In bash a `case` glob's `*` matches `/`, so
`content/drafts/*/figures/*.tex` also matches a book's
`content/drafts/<book>/<unit>/figures/x.tex`. That is the intended
behaviour. Pin it with a test if you rely on it. Update the header
comment to say the hook now does two things, and that only the workflow
half blocks.

- [ ] **Step 4: Run the hook tests**

Run: `pytest tests/test_git_hooks.py -q`
Expected: all PASS, the existing actionlint tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add git-hooks/pre-commit tests/test_git_hooks.py
git commit -m "Report a stale house figure block from the pre-commit hook"
```

---

### Task 6: Docs, skills, version

**Files:**

- Modify: `docs/CLI.md`, `docs/PACKAGING.md` (command table row),
  `docs/TIKZ-STYLE.md` (§ "The house figure style"), `assets/tikz/README.md`,
  `docs/FIGURE-ROADMAP.md` (Part V update line), `docs/HOOKS.md`
  (§ "A second mechanism: git's own hooks"), `README.md` if it lists
  package commands
- Modify: the figure step in the four genre skills, in all three harness
  copies (`.claude/skills/`, `.agents/skills/`, `.opencode/skills/*-opencode/`):
  survey-writer, textbook-chapter-writer, thesis-chapter-writer, tutorial-writer
- Modify: `pyproject.toml` version; this plan's `Status:` line

- [ ] **Step 1: `docs/TIKZ-STYLE.md`.** Replace the closing paragraph of
  "The house figure style" ("Carry the block whole…") with text that
  says:
  - the block travels between its two markers, and
    `python -m chitragupta figure sync` stamps it into a figure that
    lacks it and refreshes a stale one, leaving everything outside the
    markers byte-identical;
  - a style one figure needs goes in the picture's options or in a
    `\tikzset` **below** the end marker, never inside it, and sync
    refuses to touch an edited region and prints the diff;
  - a style three or more figures need is a pull request against
    `cg-figstyle.tex`, not a local override;
  - changing the block means bumping `v<N>` in its first line and adding
    a line to `cg-figstyle.versions.toml`, and the test that enforces
    this.
- [ ] **Step 2: `docs/CLI.md` and `docs/PACKAGING.md`.** Add the
  command, its flags and its exit codes (0 / `--check` 1 / 2) where
  `init` and `doctor` sit. Run `pytest tests/test_packaging_command_table.py -q`
  until it passes. Say there that the renderer's `[figure]` warnings
  name this command.
- [ ] **Step 3: `assets/tikz/README.md`.** Replace the "byte-identical
  copy" maintenance note: after editing `cg-figstyle.tex`, bump its
  version, add the register line, and run
  `python -m chitragupta figure sync assets/tikz` to refresh every
  scaffold and exemplar.
- [ ] **Step 4: `docs/HOOKS.md`.** In the git-hooks section, add that
  the hook also runs `figure sync --check` on staged figure files,
  advisorily, and why it does not block when the actionlint half does.
- [ ] **Step 5: `docs/FIGURE-ROADMAP.md`.** Add an update line under
  Part V saying #1013 shipped `figure sync`.
- [ ] **Step 6: The 12 skill copies.** After "leaving the house style
  block it carries unedited.", add one sentence: "Then run
  `python -m chitragupta figure sync`, which refreshes the block if the
  scaffold's copy is older than the installed one, and reports instead
  of overwriting if you edited inside it." Apply identical wording to all
  three harness copies of each skill. Run
  `pytest tests/test_skill_harness_copies.py tests/test_skill_frontmatter.py -q`.
- [ ] **Step 7: Version and plan status.** Bump `pyproject.toml` to the
  next minor of `origin/main`'s version. Set this plan's `Status:` to
  "plan, built" (the PR number is added when it merges, per
  `plans/README.md`).
- [ ] **Step 8: Lint and the full suite.** Follow the
  `worktree-test-env-setup` routine: run the full `pytest`, `ruff`,
  pylint under Python 3.13, `scripts/code_standards.py`, and
  markdownlint-cli2 with `DEVELOPER-AGENTS.md`'s glob (which covers
  `plans/**/*.md`). Expected: all clean, 100% coverage on the new
  modules.
- [ ] **Step 9: Commit**

```bash
git add docs assets/tikz/README.md .claude/skills .agents/skills .opencode/skills \
        pyproject.toml plans/1013-figure-style-sync.md README.md
git commit -m "Document figure sync and bump the version"
```

---

## Acceptance, traced to tasks

| Issue acceptance line | Where |
| --- | --- |
| `figure sync` stamps, refreshes and reports; `--check` exits non-zero when anything is stale | Task 3 `TestSync`, `TestCli` |
| No region gets one; a current region is byte-unchanged; idempotence by running twice | Task 2 `TestStamp`, Task 3 `test_running_it_twice_…` |
| A modified region is reported and not touched | Task 2 `test_an_edited_or_broken_region_…`, Task 3 `test_a_modified_region_…` |
| The renderer reports stale or missing, names the command, renders anyway | Task 4 |
| `git-hooks/` gains the `--check` call, advisory | Task 5 |
| Round-trip: stamp, compile under `\usepackage{tikz}` alone, exit 0 | Task 3 `TestRoundTrip` |
| Mitigation 1 (refuse to overwrite a region matching no released version) | Task 2 register + `classify` |
| Mitigations 2 and 3 (a local `\tikzset` below the region; three or more figures means a PR) | Task 6 Step 1 |
