# Five house `pic`s: finishing what #1026 shipped

Status: **designed, unbuilt.** Written 2026-10-06, for
[issue 1014](https://github.com/prasadtalasila/chitragupta/issues/1014),
F3 of [docs/FIGURE-ROADMAP.md](../docs/FIGURE-ROADMAP.md). The roadmap's
F-numbering is its own and has nothing to do with
[f3-agenda-reviser.md](f3-agenda-reviser.md), hence the `fig-` prefix.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Written for** whoever closes #1014. **It assumes**
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the branch, commit and
PR cycle, and `docs/TIKZ-STYLE.md` §"The house figure style" for how the
block is versioned and synced.

**Not covered here:** a `review figure` finding for a `pic` drawn
*outside* a well. That would be new code in `chitragupta/review/` and
the issue does not ask for it. The docs rule ("name every node you
draw" extends to wells) is the whole of the guard in this PR.

**Goal:** close #1014's acceptance list. Most of what the issue
describes is already on `main`. This plan does the rest and fixes the
one defect a measurement found.

**Architecture:** the work is docs and tests, plus one geometry fix and
a block version bump that the fix forces. No Python under `chitragupta/`
changes. The new tests go in `tests/test_tikz_scaffolds.py`, beside the
existing block guards, and reuse its `_pdflatex` helper.

**Tech Stack:** TikZ/PGF (`pics/.style`, `current bounding box`),
pytest, `python -m chitragupta figure sync`.

**Spec:** issue #1014 (body quoted in full in the PR), plus
`docs/FIGURE-ROADMAP.md` §V.2 and §"Rules that will have to bend".

## What #1026 already shipped, and what is left

| #1014 acceptance item | State on `main` at `043931f` |
| --- | --- |
| Five `pic`s in `assets/tikz/cg-figstyle.tex` | **Done**: `cgstore` `cgdocs` `cgfunnel` `cgchip` `cgshield`, lines 228-278 |
| …each with a one-line comment naming what it stands for **and what the twin says** | **Half**: comments name the meaning but not the twin text. `cgfunnel`'s comment also says "the gate", which is `cgshield`'s job |
| `cgwell` in the block | **Done**, line 132 |
| `cgwell` documented in `docs/TIKZ-STYLE.md` | **Half**: one table row and a sentence that defers to "#1014" |
| Millimetre carve-out written into TIKZ-STYLE.md | **Half**: a parenthetical at lines 67-69, not the rule |
| Carve-out marked resolved in FIGURE-ROADMAP.md | **Not done** |
| At least one *scaffold* uses a `pic` | **Not done**: only the exemplars (`architecture.tex`, `retrieval.tex`) do |
| A test asserting each `pic` renders inside a declared box | **Not done**, and see below |
| The "not an icon set" boundary stated in docs | **Not done** |

**The measurement that changes the plan.** Each `pic` was compiled alone
and its `current bounding box` (which includes half the stroke width)
was read back:

| `pic` | x extent (mm) | y extent (mm) | Inside the 10 × 10 mm well? |
| --- | --- | --- | --- |
| `cgstore` | −4.14 … 4.14 | −4.54 … 4.14 | yes |
| `cgdocs` | −3.14 … 4.52 | −4.14 … **5.92** | **no**: 0.92 mm through the top, and 0.7 mm off-centre |
| `cgfunnel` | −3.74 … 3.74 | −3.94 … 3.54 | yes |
| `cgchip` | −4.42 … 4.42 | −4.42 … 4.42 | yes |
| `cgshield` | −3.57 … 3.57 | −4.57 … 4.37 | yes |

`cgdocs` draws its two back pages up and to the right of the front page
without re-centring the stack. The issue's bounding-box test exists for
exactly this, and it already happens on `main`. The prototype geometry
in Task 1 measures −3.74 … 3.72 × −4.64 … 4.62 and was checked by eye
against a drawn well.

Fixing `cgdocs` edits the block. That means **v1 → v2**: bump the
marker, register the digest, and re-sync all ten carriers. That part is
mechanical; TIKZ-STYLE.md §"Changing the block means a new version"
already prescribes it.

## Global Constraints

- **No citekey anywhere.** Not in a test fixture, not in a doc example
  (CLAUDE.md's one rule). Nothing here needs one.
- Edit `cg-figstyle.tex` only. Carriers are refreshed by
  `python -m chitragupta figure sync`, never hand-edited between the
  markers.
- An existing line in `cg-figstyle.versions.toml` is never edited; v2 is
  a new line.
- Five `pic`s is the ceiling for v1 of the vocabulary. A sixth needs
  the argument made again, in writing, in its own PR.
- A `pic` is placed only into a named `cgwell`, and only where the
  node's own label already carries the proposition.
- Run the full local check list from DEVELOPER-AGENTS.md §"Before
  claiming a task complete" in the worktree venv (memory: worktree test
  env setup) before the PR. `needs_tikz` tests run here: `pdflatex` is
  at `/usr/bin/pdflatex`.

## Review Focus

1. **A `pic` that outgrows its well after a later edit.** The reader
   expects the zone card's `fit` to enclose the icon. Task 1's bbox
   test pins it, and its `oversize` probe test proves the bbox test can
   fail.
2. **`cg pic colour` leaking from one `pic` to the next.** The expected
   behaviour is that the next un-keyed `pic` in the same picture is
   `cgFlow` again. Verified by hand (`\pic[cg pic colour=cgAlt]` leaves
   `\cgPicColour` = `cgFlow` after it). Task 1 pins it.
3. **A sixth shape arriving by accretion.** The expectation is that it
   cannot land without a doc row. Task 3 pins the block's `pic` set
   against TIKZ-STYLE.md's table, in both directions.
4. **Tests that hard-code `" v1 "`** (`test_figure_block.py:30, 81, 173`,
   `test_figure_sync.py:63`). After the bump to v2 these `.replace`
   calls silently match nothing, so the "older" or "newer" block they
   build keeps the current version number and the tests test something
   else. The expectation is that they follow the block's version. Task 2
   rewrites them to `f" v{house.version} "`, and the existing assertions
   that compare versions then fail loudly if they ever drift again.
5. **The documented command path with a well in the figure.** An author
   copying `pipeline.tex` expects `review figure` to report no finding
   and nothing unmeasured. The well is a new named node, so the
   existing `TestThroughTheDocumentedCommand` and
   `test_compiles_and_measures_every_name_it_declares` cover it once
   Task 4 adds the well to `pipeline.tex`. No new test is needed, but
   watch those two tests in Task 4.

---

### Task 1: Pin every `pic` inside its well, and fix `cgdocs`

**Files:**
- Modify: `tests/test_tikz_scaffolds.py` (new helpers after `_region`,
  new class after `TestTheBlockTypesetsNothing`)
- Modify: `assets/tikz/cg-figstyle.tex:239-250` (`cgdocs`), plus the
  comments above each `pic`

**Interfaces:**
- Produces: `_pics() -> list[str]` (the `pic` names the block defines,
  in order) and `_WELL_RE`. Task 3 uses `_pics()`.

- [ ] **Step 1: Write the failing tests.** Add beside the other
  module-level helpers:

```python
# The well a `pic` is drawn into, and the `pic`s themselves, both read
# out of the block rather than restated, so the test follows an edit.
_WELL_RE = re.compile(
    r"cgwell/\.style=\{[^}]*minimum width=(?P<w>[\d.]+)mm, minimum height=(?P<h>[\d.]+)mm"
)
_PIC_RE = re.compile(r"pics/(?P<name>\w+)/\.style=")
_PT_PER_MM = 72.27 / 25.4
_CGPIC_RE = re.compile(r"CGPIC (\S+) (-?[\d.]+)pt (-?[\d.]+)pt (-?[\d.]+)pt (-?[\d.]+)pt")
_LIBRARIES = "arrows.meta,positioning,fit,backgrounds,calc,shadows.blur"


def _pics() -> list[str]:
    """Every `pic` the block defines, in the order it defines them."""
    return _PIC_RE.findall(BLOCK.read_text(encoding="utf-8"))
```

Then add, after `TestTheBlockTypesetsNothing`:

```python
@needs_tikz
class TestEveryPicFitsItsWell:
    """#1014: a `pic` is drawn into a `cgwell`, and a zone card `fit`s
    the well, not the `pic`. A `pic` that outgrows its well therefore
    pokes through its own zone card and nothing measures it, because a
    path has no name. `cgdocs` as #1026 shipped it did exactly that,
    0.92mm through the top."""

    @staticmethod
    def _extents(directory: Path, names: list[str], extra: str = "") -> dict:
        """Each `pic`'s ink box in mm, origin at the well's centre.
        `current bounding box` includes half the stroke width."""
        body = "".join(
            f"\\begin{{tikzpicture}}[cg]\\pic{{{name}}};"
            "\\pgfpointanchor{current bounding box}{south west}\\pgfgetlastxy\\cgxa\\cgya"
            "\\pgfpointanchor{current bounding box}{north east}\\pgfgetlastxy\\cgxb\\cgyb"
            f"\\typeout{{CGPIC {name} \\cgxa\\space\\cgya\\space\\cgxb\\space\\cgyb}}"
            "\\end{tikzpicture}\n"
            for name in names
        )
        result = _pdflatex(
            directory, f"\\usetikzlibrary{{{_LIBRARIES}}}\\input{{{BLOCK}}}{extra}\n{body}"
        )
        assert result.returncode == 0, result.stdout[-2000:]
        return {
            m.group(1): tuple(float(v) / _PT_PER_MM for v in m.groups()[1:])
            for m in _CGPIC_RE.finditer(result.stdout)
        }

    @staticmethod
    def _inside_the_well(box: tuple) -> bool:
        match = _WELL_RE.search(BLOCK.read_text(encoding="utf-8"))
        half_w, half_h = float(match["w"]) / 2, float(match["h"]) / 2
        x0, y0, x1, y1 = box
        return -half_w <= x0 and x1 <= half_w and -half_h <= y0 and y1 <= half_h

    def test_there_are_pics_to_measure(self):
        """The non-vacuous guard: a regex that stops matching makes every
        check below pass on an empty list."""
        assert len(_pics()) > 1 and _WELL_RE.search(BLOCK.read_text(encoding="utf-8"))

    def test_every_pic_is_measured_and_fits(self, tmp_path):
        extents = self._extents(tmp_path, _pics())

        assert set(extents) == set(_pics())
        assert [n for n, box in extents.items() if not self._inside_the_well(box)] == []

    def test_the_probe_sees_an_oversize_pic(self, tmp_path):
        """The probe against the shape it exists to catch."""
        oversize = (
            "\\tikzset{pics/cgoversize/.style={code={"
            "\\path[draw] (-6mm,-6mm) rectangle (6mm,6mm);}}}"
        )
        extents = self._extents(tmp_path, ["cgoversize"], oversize)

        assert not self._inside_the_well(extents["cgoversize"])

    def test_a_pic_colour_does_not_leak_to_the_next_pic(self, tmp_path):
        """`cg pic colour` is set per `\\pic`, so the next un-keyed one in
        the same picture is the default again, not the last zone's hue."""
        result = _pdflatex(
            tmp_path,
            f"\\usetikzlibrary{{{_LIBRARIES}}}\\input{{{BLOCK}}}\n"
            "\\begin{tikzpicture}[cg]\\pic[cg pic colour=cgAlt]{cgstore};"
            "\\typeout{CGCOL=\\cgPicColour}\\end{tikzpicture}",
        )

        assert result.returncode == 0, result.stdout[-2000:]
        assert "CGCOL=cgFlow" in result.stdout
```

- [ ] **Step 2: Run to verify the right test fails**

Run: `.venv-full/bin/python -m pytest tests/test_tikz_scaffolds.py -k TestEveryPicFitsItsWell -v`
Expected: `test_every_pic_is_measured_and_fits` FAILS, naming `['cgdocs']`.
The other three pass.

- [ ] **Step 3: Fix `cgdocs` and the five comments.** Replace the
  `cgdocs` definition with the prototype (measured −3.74…3.72 ×
  −4.64…4.62 mm):

```latex
  % A stack of pages: a document, or a set of them. Twin: [PDFs].
  pics/cgdocs/.style={code={
    \foreach \i in {2,1}{
      \path[fill=cgPaper, draw=\cgPicColour!55, line width=0.7pt,
            rounded corners=0.6pt]
        (-3.6mm+\i*0.8mm, -4.5mm+\i*0.8mm) rectangle (2mm+\i*0.8mm, 2.9mm+\i*0.8mm);}
    \path[fill=cgPaper, draw=\cgPicColour, line width=0.8pt, rounded corners=0.6pt]
      (-3.6mm,-4.5mm) rectangle (2mm,2.9mm);
    \foreach \y in {1.4,-0.1,-1.6,-3.1}{
      \path[draw=\cgPicColour!60, line width=0.55pt]
        (-2.6mm,\y mm) -- (1mm,\y mm);}
  }},
```

The other four comment lines become (geometry unchanged):

```latex
  % A drum: any persistent store. 8mm wide, 9mm tall. Twin: [ledger].
  % A funnel: any place the set gets smaller -- a cap, a top-k, a filter.
  % Twin: [cap 3 per source].
  % A chip: anything that computes -- a model, an encoder, a reranker.
  % Twin: [bi-encoder].
  % A shield: the one blocking check, at most once per figure.
  % Twin: [gate].
```

In the section header comment, correct `` `/cg/pic colour` `` to
`` `cg pic colour` `` (the key is defined at the `/tikz` root, line
229), and add one sentence: "Each fits the 10mm `cgwell` it is drawn
into; tests/test_tikz_scaffolds.py measures that."

Do **not** bump the version yet; Task 2 does that, so this task's diff
reads as the geometry change alone.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv-full/bin/python -m pytest tests/test_tikz_scaffolds.py -k TestEveryPicFitsItsWell -v`
Expected: 4 passed. (`TestTheBlockTravelsUnforked` and
`test_figure_block.py` now fail, because the carriers and the register
still hold v1. Task 2 fixes that; do not commit between the two
tasks if a green commit per task is wanted. Otherwise commit with
`--no-verify` only if the pre-commit hook blocks, and say so.)

- [ ] **Step 5: Look at it.** Render all five `pic`s, each inside a
  `cgwell` with `draw=red`, through a `standalone` document and
  `pdftoppm -r 1200`. Check that `cgdocs` still reads as a stack of
  pages. A test can measure the box but not whether the shape is still
  recognisable.

### Task 2: Ship the block as v2 and re-sync every carrier

**Files:**
- Modify: `assets/tikz/cg-figstyle.tex:1` (marker `v1` → `v2`)
- Modify: `assets/tikz/cg-figstyle.versions.toml` (append `v2`)
- Modify: the 7 scaffolds and 3 exemplars, via `figure sync` only
- Modify: `tests/test_figure_block.py:30, 81, 173`, `tests/test_figure_sync.py:63`

**Interfaces:**
- Consumes: Task 1's edited block.

- [ ] **Step 1: Make the version-literal tests follow the block.** In
  each of the four places, replace the hard-coded `" v1 "` with the
  block's own version:

```python
# tests/test_figure_block.py:30
text = house.text.replace(f" v{house.version} ", f" v{version} ", 1).replace("0.95pt", "0.9pt", 1)
# tests/test_figure_block.py:81 and :173, tests/test_figure_sync.py:63
newer = house.text.replace(f" v{house.version} ", " v9 ", 1)
```

(`house` is the fixture already in scope at each site. `0.95pt` is
`cgshield`'s stroke and survives Task 1.) Run
`.venv-full/bin/python -m pytest tests/test_figure_block.py tests/test_figure_sync.py -q`:
all pass on v1, which shows the rewrite is behaviour-neutral.

- [ ] **Step 2: Bump and register.** Change line 1 of `cg-figstyle.tex`
  to `% >>> chitragupta figure style v2 -- copy of assets/tikz/cg-figstyle.tex, do not edit <<<`, then:

```bash
.venv-full/bin/python -c "from pathlib import Path; from chitragupta import figure; \
print(figure.digest(Path('assets/tikz/cg-figstyle.tex').read_text(encoding='utf-8')))"
```

Append `v2 = "<that digest>"` under the `v1` line. Leave `v1` as it is.

- [ ] **Step 3: Re-sync**

Run: `.venv-full/bin/python -m chitragupta figure sync assets/tikz/*.tex assets/tikz/exemplars/*.tex`
Expected: `figure sync: 1 current, 10 refreshed` (the block file itself
is current). If any file reports `modified`, stop: someone edited
inside a marker, and that is a separate fix.

- [ ] **Step 4: Verify**

Run: `.venv-full/bin/python -m pytest tests/test_figure_block.py tests/test_figure_sync.py tests/test_tikz_scaffolds.py -q`
Expected: all pass, including `TestTheBlockTravelsUnforked` and the
geometry checks on the two exemplars that draw `cgdocs`/`cgstore`.
`git diff --stat` should show the ten carriers changing only inside
their markers: run `git diff -U0 assets/tikz | grep '^@@'` and check
each hunk lies between lines 1 and ~280 of the region.

- [ ] **Step 5: Commit** Tasks 1 and 2 together:

```bash
git add assets/tikz tests/test_tikz_scaffolds.py tests/test_figure_block.py tests/test_figure_sync.py
git commit -m "Fit cgdocs inside its well and pin every house pic to it (block v2)"
```

### Task 3: Write the rules into TIKZ-STYLE.md and close the roadmap's carve-out

**Files:**
- Modify: `docs/TIKZ-STYLE.md:65-74` (carve-out), `:457-462` (table row
  and the "#1014 documents" sentence), new subsection before
  `### 🖨 What the other two forms do with it` (line 513)
- Modify: `docs/FIGURE-ROADMAP.md:590-593` and §"No coordinate in millimetres" versus fixed objects (line 1160)
- Modify: `assets/tikz/README.md:144-147` (the parenthetical becomes a
  pointer)
- Test: `tests/test_tikz_scaffolds.py`

**Interfaces:**
- Consumes: `_pics()` from Task 1.
- Produces: the table header `` | `pic` | Stands for | Twin says | `` in
  TIKZ-STYLE.md, which the test reads.

- [ ] **Step 1: Write the failing test** (in `TestMetaphorCoverage`'s
  style, source-only, so it runs without TeX):

```python
_PIC_TABLE_HEADER = "| `pic` | Stands for | Twin says |"
_PIC_ROW_RE = re.compile(r"^\|\s*`(?P<name>\w+)`\s*\|")


def _documented_pics() -> list[str]:
    """The `pic`s docs/TIKZ-STYLE.md's house-shape table names."""
    lines = STYLE_DOC.read_text(encoding="utf-8").splitlines()
    start = lines.index(_PIC_TABLE_HEADER) + 2
    found = []
    for line in lines[start:]:
        match = _PIC_ROW_RE.match(line)
        if match is None:
            break
        found.append(match.group("name"))
    return found


class TestTheShapesAreTheDocumentedOnes:
    """#1014: a shape is added only when a metaphor wants it, and the
    argument is made in writing. The doc row is where that argument
    lands, so a `pic` the table does not name cannot ship, and a row
    for a `pic` that was removed cannot linger."""

    def test_the_table_was_read(self):
        assert len(_documented_pics()) > 1

    def test_the_block_and_the_table_name_the_same_pics(self):
        assert _documented_pics() == _pics()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv-full/bin/python -m pytest tests/test_tikz_scaffolds.py -k TestTheShapesAreTheDocumentedOnes -v`
Expected: FAIL with `ValueError: ... is not in list` (no table yet).

- [ ] **Step 3: Write the docs.**

(a) TIKZ-STYLE.md, §"Commit to a layout metaphor": replace the
parenthetical "(The house block's `pic` definitions do write
millimetres, … not the composition.)" with the issue's paragraph,
verbatim, as its own paragraph after the one it interrupted:

```markdown
**The millimetre rule governs composition, not objects.** Every node in
a figure is placed relative to another node, and that does not change.
Inside a `pic` definition, explicit millimetre coordinates are correct
and expected: a `pic` is a fixed object drawn once, whose internal
geometry does not reflow when a sibling's label changes. The boundary
is the `pic`, not the authoring method — a shape generated by a
derivation gets the same carve-out as a hand-drawn one. Hand-placing a
whole figure is still the defect the rule exists to prevent.
```

Use `--` or a comma in place of the em dash if the file's own style
avoids em dashes; check `grep -c '—' docs/TIKZ-STYLE.md` first.

(b) In "Name every node you draw", add one sentence: "That includes the
well a `pic` is drawn into: draw a `pic` only `at` a named `cgwell`
(see House shapes below)."

(c) Replace the "It also defines five house `pic`s … which #1014
documents …" paragraph with a one-line pointer to the new subsection.

(d) New subsection `### 🧰 House shapes, and the well they sit in`,
before `### 🖨 What the other two forms do with it`, containing in
order:

- The table, header exactly `` | `pic` | Stands for | Twin says | ``,
  with the issue's five rows in the block's order (`cgstore`, `cgdocs`,
  `cgfunnel`, `cgchip`, `cgshield`).
- Why each passes V.2's twin test: it sits directly above a node whose
  label already says it, so the shape is a rendering choice and never a
  proposition. `cgshield` appears at most once per figure.
- The well, with the issue's example, and the two reasons it is not
  cosmetic: `review figure` sees only named nodes, and a zone card can
  `fit` only a named node. Every `pic` fits inside its well, and
  `tests/test_tikz_scaffolds.py` measures that.

```latex
\node[cgwell, above=2.5mm of sync] (isync) {};
\pic[cg pic colour=cgFlow] at (isync) {cgstore};
```

- Colour: `cg pic colour` takes a palette name and is scoped to the one
  `\pic`. Give it the zone's hue, so the same drum is green in one zone
  and blue in another.
- The boundary, bolded: **not an icon set.** A shape is added only
  when a metaphor in the table above wants it, and only when the
  node's own label already carries the proposition. Five is the
  ceiling for now. A sixth needs the argument made again, in writing,
  in its pull request, and a row here, which the test above enforces.

(e) FIGURE-ROADMAP.md: change line 592's "(#1014 owns their
documentation)" to point at
`[TIKZ-STYLE.md](TIKZ-STYLE.md#-house-shapes-and-the-well-they-sit-in)`.
Under §"No coordinate in millimetres" versus fixed objects, add a first
line: `**Resolved 2026-10-0X (#1014):** written into
[TIKZ-STYLE.md](TIKZ-STYLE.md#-commit-to-a-layout-metaphor-before-you-draw)
as stated below.` Leave the reasoning beneath it, since the roadmap keeps
its history. Check the anchor slugs against how mkdocs renders the emoji
headings (copy an existing in-repo link to a heading with an emoji, for
example the `#-the-house-figure-style` link at line 598).

(f) `assets/tikz/README.md:146`: shorten the parenthetical to "(the
block's `pic`s are the one exception, and TIKZ-STYLE.md says why)".

- [ ] **Step 4: Verify**

Run: `.venv-full/bin/python -m pytest tests/test_tikz_scaffolds.py -q && markdownlint-cli2 docs/TIKZ-STYLE.md docs/FIGURE-ROADMAP.md assets/tikz/README.md plans/fig-f3-house-pics.md`
Expected: pass, and no lint finding. Also run the repo's docs link
check, if DEVELOPER-AGENTS.md's local check list names one, so the two
new anchors resolve.

- [ ] **Step 5: Commit**

```bash
git add docs/TIKZ-STYLE.md docs/FIGURE-ROADMAP.md assets/tikz/README.md tests/test_tikz_scaffolds.py
git commit -m "Document the house shapes, the well and the millimetre carve-out"
```

### Task 4: One scaffold draws a `pic`

**Files:**
- Modify: `assets/tikz/pipeline.tex` (picture body only, below the end marker)

`pipeline.tex` is the right carrier. It is the default copy in
`assets/tikz/README.md`, and `TestThroughTheDocumentedCommand` and
`TestTheTypeFloor` already run through it, so the well gets checked
along the documented `review figure` path as well as by the per-carrier
checks. Its first stage is `\cglab{Intake}{files in}`, so `cgdocs` is
redundant with the label, which is the twin test.

- [ ] **Step 1: Add the well and the `pic`** after the `intake` node:

```latex
  % A house shape, drawn into a named well so `review figure` measures
  % it and a zone card could `fit` it. It repeats what the label says;
  % the twin drops it and loses nothing (docs/TIKZ-STYLE.md).
  \node[cgwell, above=2.5mm of intake] (iintake) {};
  \pic[cg pic colour=cgFlow] at (iintake) {cgdocs};
```

- [ ] **Step 2: Verify**

Run: `.venv-full/bin/python -m pytest tests/test_tikz_scaffolds.py -q`
Expected: all pass. Watch three tests specifically:
`test_compiles_and_measures_every_name_it_declares[pipeline]`
(`iintake` is declared and measured),
`test_a_draft_that_starts_from_a_scaffold_reports_no_finding`, and
`test_fits_the_text_width_unscaled[pipeline]` (the well adds height,
not width). Also run
`.venv-full/bin/python -m chitragupta figure sync --check assets/tikz/pipeline.tex`:
`1 current`.

- [ ] **Step 3: Commit**

```bash
git add assets/tikz/pipeline.tex
git commit -m "Draw a house pic in the pipeline scaffold so every run compiles one"
```

### Task 5: Close out

- [ ] Run the full local check list (DEVELOPER-AGENTS.md §"Before
  claiming a task complete") in the worktree venv, with pylint under
  Python 3.13 as CI does.
- [ ] Add a `Status:` outcome line at the top of this plan naming the
  PR, per plans/README.md.
- [ ] Open the PR with `Closes #1014`, the `## Commit message` fence
  checked by `scripts/merge_pr.py --check`, and the `cgdocs`
  measurement table in the body. The fix is the one behaviour change
  here, and a reviewer should see the before and after numbers.
