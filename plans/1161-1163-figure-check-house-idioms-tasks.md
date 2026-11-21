# `figure check` house idioms: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **plan**, written 2026-11-21.

**Goal:** `figure check` reports a head set by a style, one connector
lying on another, and a tag hidden inside a card; the architecture
exemplar is clean, and a slow test holds every scaffold and exemplar to
every rule.

**Architecture:** Three independent rule changes, each in the module
that already owns the rule, plus one asset fix and one slow test. Arrow
tips are resolved by a new small module beside `_source.py`, because
resolving styles is its own concern and `_source.py` is already a list
of separate checks.

**Tech Stack:** Python 3.14, pytest (`slow` marker for TeX compiles),
TikZ/LuaLaTeX through `figure check`'s probe.

**Spec:** [plans/1161-1163-figure-check-house-idioms.md](1161-1163-figure-check-house-idioms.md)

## Global Constraints

- One branch, one PR: `fix-1161-1163-figure-check`, off `main`.
- No new finding on any figure a person would call correct. Measured
  against the 18 assets and the book's 55 figures (Task 5).
- The house block (`assets/tikz/cg-figstyle.tex`) is not edited: no
  block bump.
- Version: PATCH (bug fixes). Read `main`'s `pyproject.toml` at Task 5
  and bump its PATCH (6.177.1 today, so 6.177.2).
- 100% line and branch coverage holds; a new test is `slow` only if it
  compiles TeX.
- `chitragupta.review.figure_layout` must not import `chitragupta.figure`
  (the dependency runs the other way).
- Commit messages: imperative title, bulleted body, no PR number, no
  `Closes`. DEVELOPER-AGENTS.md "Commit messages".
- No citekey anywhere in a test fixture or doc example (CLAUDE.md).

## Review Focus

1. A bus-style fan-out whose shared trunk is long (30mm) must not fire
   c3. Task 2 pins it.
2. `shorten >=1.5pt` in a path's options (and inside `cgedge`'s own
   body) holds a `>` but is not a head. Task 3 pins it.
3. A style that names itself, or two styles that name each other, must
   resolve to no head, not loop forever. Task 3 pins it.
4. A continuing piece that draws its own start head through a style
   (`{Latex}-{Latex}` dimension bars) is not stranded. Task 3 pins it.
5. A style called with an argument (`cglead=cgFlow`, `cgzone=cgAlt`) is
   looked up by the name before `=` and does not crash. Task 3 pins it.

---

### Task 1: c6 excuses only a zone (#1163 item 4)

**Files:**

- Modify: `chitragupta/figure/_clearance_rules.py` (`tag_covered`, ~line 83)
- Test: `tests/test_figure_clearance_rules.py` (`TestTagCovered`)

**Interfaces:**

- Consumes: `zones(nodes) -> set[str]` from `chitragupta/figure/_connectors.py`.
- Produces: `tag_covered(cons, drawn) -> list[Finding]`, signature unchanged.

- [ ] **Step 1: Set up the checkout**

```bash
git switch -c fix-1161-1163-figure-check origin/main
cp config.toml.example config.toml
```

- [ ] **Step 2: Write the failing tests** in `TestTagCovered`, using the
  file's `_figure` and `_tag` helpers

```python
def test_c6_fires_on_a_tag_inside_a_card(self):
    figure, cons = _figure(node("card", (55, 8, 95, 25)), _tag("cgu-1", (60, 13, 80, 18)))

    (finding,) = tag_covered(cons, figure)

    assert (finding.target, finding.measurement) == ("a->b", "tag under card")

def test_c6_holds_on_a_tag_inside_a_framed_fit_group(self):
    group = node("group", (55, 8, 95, 40))  # framed: True is the fixture default
    member = node("q", (75, 25, 85, 35))
    figure, cons = _figure(group, member, _tag("cgu-1", (60, 13, 80, 18)))

    assert tag_covered(cons, figure) == []
```

- [ ] **Step 3: Run them**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_figure_clearance_rules.py -k "inside_a_card or framed_fit" -v
```

Expected: `inside_a_card` FAILS (`not enough values to unpack`), `framed_fit` passes.

- [ ] **Step 4: Change `tag_covered`** so a node holding the whole tag
  is skipped only when it is in `zones(nodes)`. Unframed zones stay
  skipped outright, as now. Update the docstring: "A zone (a card or
  `fit` group holding another node) containing the tag is not counted;
  a card containing it is."

- [ ] **Step 5: Run the file**

Run: `.venv-full/bin/python -m pytest tests/test_figure_clearance_rules.py -v`
Expected: all PASS, including `test_c6_holds_on_a_tag_inside_its_zone`
and `test_c6_holds_under_an_unframed_group`.

- [ ] **Step 6: Commit** (`Report a tag hidden inside a card in c6-tag-covered`)

---

### Task 2: c3 reports one connector lying on another (#1163 item 3)

**Files:**

- Modify: `chitragupta/figure/_route_rules.py` (`coincident`, ~line 76)
- Test: `tests/test_figure_route_rules.py` (`TestCoincident`, `TestBenchedShapes`)

**Interfaces:**

- Produces: `coincident(cons) -> list[Finding]`, signature unchanged. A
  pair with no shared end keeps the measurement `share N.Nmm`. A pair
  sharing an end that is not a fork gets `"<lying> lies wholly on <under>"`.

- [ ] **Step 1: Write the failing tests** with the file's `node`, `line`
  and `_cons` helpers (`A` is `(0,0,40,20)`, `B` is `(100,0,140,20)`)

```python
def test_c3_fires_on_a_return_edge_on_its_forward_edge(self):
    cons = _cons([A, B], [line((40, 10), (100, 10)), line((100, 10), (41.5, 10), index=2)])

    (finding,) = coincident(cons)

    assert (finding.target, finding.measurement) == ("a->b+b->a", "b->a lies wholly on a->b")

def test_c3_fires_on_a_skip_edge_over_a_chain(self):
    S, P, G = node("s", (0, 0, 40, 20)), node("p", (100, 0, 140, 20)), node("g", (200, 0, 240, 20))
    cons = _cons(
        [S, P, G],
        [line((40, 10), (100, 10)), line((140, 10), (200, 10), index=2),
         line((40, 10), (200, 10), index=3)],
    )

    assert {(f.target, f.measurement) for f in coincident(cons)} == {
        ("s->p+s->g", "s->p lies wholly on s->g"),
        ("p->g+s->g", "p->g lies wholly on s->g"),
    }
```

In `TestBenchedShapes`, beside `test_c3_holds_on_a_fork_from_one_point`:

```python
def test_c3_holds_on_a_fork_with_a_long_trunk(self):
    """A bus fan-out: a 30mm trunk, then two branches."""
    far_b, far_c = node("b", (200, -20, 240, 0)), node("c", (200, 40, 240, 60))
    trunk = (40 + 30 * MM, 10)
    cons = _cons(
        [A, far_b, far_c],
        [line((40, 10), trunk, (trunk[0], -10), (200, -10)),
         line((40, 10), trunk, (trunk[0], 50), (200, 50), index=2)],
    )

    assert coincident(cons) == []
```

Before running, check the skip-edge test's targets against what
`connectors()` names the pair (the order follows `combinations` over
line order). Fix the expected strings if the order differs, not the code.

- [ ] **Step 2: Run them**

Run: `.venv-full/bin/python -m pytest tests/test_figure_route_rules.py -k c3 -v`
Expected: the two `fires_on` tests FAIL (no finding); `long_trunk` passes.

- [ ] **Step 3: Change `coincident`.** Work out `shared` for every pair
  (remove the early `continue`). For a pair that `_share_an_end`, find
  how much of each line lies outside the shared stretch: its length
  (add a `_length(line: DrawnLine) -> float` helper summing
  `math.dist` over `segments`) minus `shared`. If both are over
  `_SHARED_MM * MM`, it's a fork: skip it. Otherwise, if `shared` is
  over the threshold, report it. The lying connector is the one with
  less outside; on a tie, `other`. A pair with no shared end is
  unchanged. Docstring: "Two that share an end point are excused only
  when both leave the shared stretch, a fork (`retrieval.tex`); one
  lying on the other end to end is reported."

- [ ] **Step 4: Run the file**

Run: `.venv-full/bin/python -m pytest tests/test_figure_route_rules.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit** (`Report one connector lying on another in c3-coincident`)

---

### Task 3: `stranded-arrowhead` reads heads set by a style (#1162 item 2)

**Files:**

- Create: `chitragupta/review/figure_layout/_tips.py`
- Modify: `chitragupta/review/figure_layout/_source.py` (`stranded_arrowheads`
  and the `_END_ARROW`/`_START_ARROW` comment block, ~lines 240-330)
- Test: `tests/test_figure_tips.py` (new), `tests/test_figure_source_spellings.py`

**Interfaces:**

- Produces, in `_tips.py`:
  - `style_definitions(text: str) -> dict[str, str]`: `{name: body}` for
    every `name/.style={body}` in `text` (comments already stripped by
    the caller). A name starts after `{`, `[`, `,`, whitespace or the
    start of the text, is `[A-Za-z][\w ]*`, and is stripped; the body
    is read with `_scan.braced`. `/.style n args`
    and `/.append style` are not read.
  - `house_styles() -> dict[str, str]`: `style_definitions` over the
    shipped `config.shipped("assets", "tikz", "cg-figstyle.tex")`,
    comments stripped, `functools.cache`d.
  - `tips(options: str, styles: dict[str, str]) -> tuple[bool, bool]`:
    `(start head, end head)` for a path's leading options.
- Consumes in `_source.py`: `styles = {**house_styles(), **style_definitions(text)}`
  once per call, then `tips(options, styles)` per statement.

The rule for `tips` (the tests don't settle it):

1. Split `options` at commas outside `{}` and `[]`.
2. For each token, the name is the part before a top-level `=`, stripped.
   If the name is in `styles` and not already visited on this path,
   recurse into its body and OR the result in.
3. Otherwise, if the token has no top-level `=`, read it as an arrow
   spec: replace each top-level `{...}` and `[...]` with `X`, then
   full-match `SIDE-SIDE`. A side is empty, a run of `<`, `>`, `|`, an
   `X`, a capitalised tip name with an optional `X` (`Latex`,
   `StealthX`), or `latex`, `stealth`, `to`. A non-empty start side is
   a start head; a non-empty end side is an end head.

So `->` is (False, True), `<->` (True, True), `-{Latex[length=2.6mm]}`
(False, True), `shorten >=1.5pt` nothing (top-level `=`), `thick`
nothing.

- [ ] **Step 1: Write the failing tests** in `tests/test_figure_tips.py`

```python
HOUSE = (
    r"\tikzset{cgedge/.style={draw=cgFlowLine, -{Latex[length=2.6mm, width=2.1mm]}, shorten >=1.5pt},"
    r" cgback/.style={cgedge, dash pattern=on 2.8pt off 2.2pt},"
    r" cgbar/.style={{Latex}-{Latex}}, cglead/.style={draw=#1Line}}"
)

def test_the_plain_spellings_are_read():
    assert tips("->", {}) == (False, True)
    assert tips("<->, thick", {}) == (True, True)
    assert tips("<-", {}) == (True, False)
    assert tips("thick, draw=red", {}) == (False, False)

def test_an_arrows_meta_tip_is_read():
    assert tips("-{Stealth[length=2mm]}", {}) == (False, True)
    assert tips("-Latex", {}) == (False, True)

def test_shorten_is_not_a_head():
    assert tips("shorten >=2pt", {}) == (False, False)

def test_a_style_is_followed_through_inheritance():
    styles = style_definitions(HOUSE)
    assert tips("cgback", styles) == (False, True)
    assert tips("cgbar", styles) == (True, True)

def test_a_style_called_with_an_argument_is_looked_up_by_name():
    assert tips("cglead=cgFlow", style_definitions(HOUSE)) == (False, False)

def test_a_cycle_of_styles_ends():
    styles = {"a": "b", "b": "a, ->"}
    assert tips("a", styles) == (False, True)
    assert tips("x", {"x": "x"}) == (False, False)

def test_the_house_block_defines_cgedge_with_an_end_head():
    assert tips("cgedge", house_styles()) == (False, True)
```

In `tests/test_figure_source_spellings.py`, a class `TestHeadsFromStyles`:

```python
def test_the_issues_reproduction_is_reported(self):
    source = r"\draw[cgedge] (a) -- (46,36); \draw[cgedge] (46,36) -- (b);"
    assert stranded_arrowheads(source) == ["46,36"]

def test_a_style_the_figure_defines_is_read(self):
    source = r"\tikzset{mine/.style={-{Stealth}}}\draw[mine] (a) -- (1,2); \draw[mine] (1,2) -- (b);"
    assert stranded_arrowheads(source) == ["1,2"]

def test_bars_that_draw_their_own_start_head_are_not_stranded(self):
    source = r"\tikzset{bar/.style={{Latex}-{Latex}}}\draw[bar] (0,0) -- (5,0); \draw[bar] (5,0) -- (9,0);"
    assert stranded_arrowheads(source) == []

def test_shorten_alone_draws_no_head(self):
    source = r"\draw[shorten >=2pt] (a) -- (1,2); \draw[shorten >=2pt] (1,2) -- (b);"
    assert stranded_arrowheads(source) == []
```

- [ ] **Step 2: Run them**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_figure_tips.py tests/test_figure_source_spellings.py -v
```

Expected: `test_figure_tips.py` errors on import (`_tips` missing); the
two `is_reported`/`is_read` spellings FAIL with `[]`.

- [ ] **Step 3: Write `_tips.py`** with the three functions above, and
  rewrite `stranded_arrowheads` to use `tips` in place of the two
  substring tests. Move the "why substrings" comment into `_tips.py`,
  rewritten as the rule above, and state what is still missed: a style
  from a file neither the figure nor the house block defines, and
  `/.append style`. Add `_tips` to nothing public: `figure_layout/__init__.py`
  is unchanged.

- [ ] **Step 4: Run the source tests and the old stranded tests**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_figure_tips.py tests/test_figure_source_spellings.py tests/test_figure_layout.py -v
```

Expected: all PASS (the nine existing `stranded_arrowheads` asserts in
`test_figure_layout.py` unchanged).

- [ ] **Step 5: Commit** (`Read arrowheads set by a style in stranded-arrowhead`)

---

### Task 4: the exemplar, and every rule over every asset (#1161, #1163 item 5)

**Files:**

- Modify: `assets/tikz/exemplars/architecture.tex:418`, `assets/tikz/exemplars/architecture.txt:8`
- Test: `tests/test_tikz_scaffolds.py` (new class after `TestThroughTheDocumentedCommand`)

**Interfaces:**

- Consumes: `_check.check(path, width_pt) -> CheckResult` from
  `chitragupta/figure/_check.py`; `_carriers()` (scaffolds plus
  exemplars) already in the test file.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.slow
@needs_tikz
@pytest.mark.parametrize("figure", _carriers(), ids=lambda p: p.stem)
def test_every_asset_passes_every_rule(figure):
    """What figure-drawer copies from must not hand a defect on (#1161)."""
    result = _check.check(figure, ARTICLE.text_width_pt)

    assert [(f.rule, f.target) for f in result.findings] == []
    assert result.malformed == []
```

(Import `_check` from `chitragupta.figure` and `ARTICLE` from
`chitragupta.page` if the file does not already.)

- [ ] **Step 2: Run it**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_tikz_scaffolds.py -k every_asset -v
```

Expected: 17 PASS, `architecture` FAILS with
`[('c6-tag-covered', 'sync->draft'), ('c6-tag-covered', 'sync->draft')]`.

- [ ] **Step 3: Drop the tag.** Line 418 becomes
  `\draw[cgedge] (sync) -- (draft);`. In the twin, line 8's `ledger |`
  becomes spaces then `|`, keeping the column.

- [ ] **Step 4: Run the scaffold tests**

Run: `.venv-full/bin/python -m pytest tests/test_tikz_scaffolds.py -v`
Expected: all PASS, including the twin-agreement test.

- [ ] **Step 5: Commit**
  (`Drop the architecture exemplar's covered tag and check every asset`)

---

### Task 5: docs, measurement, version, checks

**Files:**

- Modify: `.claude/skills/figure-drawer/references/check.md` (rows
  `stranded-arrowhead`, `c3-coincident`)
- Modify: `docs/figure-checks/CONNECTORS.md` (c3, c6) and
  `docs/figure-checks/NODES.md` (`stranded-arrowhead`)
- Modify: `pyproject.toml` (version)
- Modify: `plans/1161-1163-figure-check-house-idioms.md` (Status line)

- [ ] **Step 1: Edit check.md's two rows**

  `stranded-arrowhead`:

  ```text
  Draw the whole line as one `\draw`, so only its last piece carries the head
  ```

  `c3-coincident` (one cell, shown wrapped):

  ```text
  Give each edge its own lane: attach at a different point, or offset one.
  A pair running both ways goes either side of the line; a skip edge goes
  around the chain, or is deleted
  ```

- [ ] **Step 2: Edit the pages.** Make each **Fix.** paragraph check.md's
  cell word for word. c3's **Catches**: "Two that share an end point
  are a fork, and excused, only when both leave the shared stretch."
  Then add a short "Also caught" paragraph with the return-edge
  snippet, the skip-edge snippet, and their `lies wholly on` lines.
  c6's **Catches**: "A zone (a card or group holding another node)
  containing the tag is not counted; a card containing it is."
  NODES.md: "The check reads a head from `->`, an `arrows.meta` tip,
  or a style that sets one (`cgedge`)."

- [ ] **Step 3: Run the examples test**

Run: `.venv-full/bin/python -m pytest tests/test_figure_check_examples.py -v`
Expected: all PASS (the faulty/fixed pairs and the word-for-word fix test).

- [ ] **Step 4: Measure the book**, on `main` and on this branch

```bash
SCRATCH=/tmp/claude-1001/fig-1161   # or the session scratchpad
mkdir -p "$SCRATCH" && git worktree add "$SCRATCH/main" origin/main
cp config.toml.example "$SCRATCH/main/config.toml"
measure() {  # $1: checkout to run from, $2: output file
  for f in /workspace/content/drafts/*/figures/*.tex; do
    echo "== $f"
    (cd "$1" && python -m chitragupta figure check "$f" 2>&1 | grep -E '^  (c[0-9]|stranded)')
  done > "$2"
}
measure "$SCRATCH/main" "$SCRATCH/before.txt"
measure "$PWD" "$SCRATCH/after.txt"
diff "$SCRATCH/before.txt" "$SCRATCH/after.txt"
git worktree remove "$SCRATCH/main"
```

Expected: no diff. Any new line goes in the PR description, read in
the rendered figure (`figure look`) and shown to be a real defect, or
it is a bug in this branch.

- [ ] **Step 5: Sweep the docs** (DEVELOPER-AGENTS.md "Shipping", step 4):

  ```bash
  grep -rn "share an end\|shared end\|fork\|_END_ARROW\|literal \`->\`" \
    docs .claude/skills/figure-drawer chitragupta
  ```

  and fix every sentence this branch made false.

- [ ] **Step 6: Bump the version.** Read `main`'s version; raise its
  PATCH in `pyproject.toml`.

- [ ] **Step 7: Run all local checks**

```bash
.venv-full/bin/python -m pytest -n auto --cov --cov-report=term-missing
bash scripts/check_local.sh
```

Expected: no failure, coverage 100%.

- [ ] **Step 8: Run OpenCodeReview** over the branch
  (`open-code-review:review`) and act on its findings.

- [ ] **Step 9: Set the spec's Status** to `built, on branch
  fix-1161-1163-figure-check (v<version>)`, noting anything changed on
  the way, and commit (`Document the c3, c6 and stranded-arrowhead changes`).

- [ ] **Step 10: Stop.** Report to the owner and wait for their go
  before pushing or opening the PR. The PR description closes #1161,
  #1162 and #1163 and ticks items 1 to 5 of #1108.
