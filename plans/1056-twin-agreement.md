# 🪞 XII-2e: twin agreement in `figure check`

Status: **built.** Written 2026-10-29 against `main` at `227d7e6`, built
on `9175cbf`, from a brainstorming session on issue
[#1056](https://github.com/prasadtalasila/chitragupta/issues/1056), and
implemented in the same PR as this plan, as #1053 and #1057 were. The
decisions marked *user* were agreed in that session; the rest was the
session's proposal.

**Written for** whoever builds #1056: a session that changes
`chitragupta/figure/`, `assets/tikz/`, the three copies of the
`figure-drawer` skill, `tests/` and `docs/`, and is therefore governed by
`DEVELOPER-AGENTS.md` and `docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` ("Twin agreement"
table), `plans/1053-figure-check-skeleton.md` (the registry, report and
allow grammar this plugs into), `plans/1057-figure-check-size.md`, and
`docs/WRITING-STANDARDS.md` §10 (the twin's 7-bit alphabet).

**Not covered here:** edge topology in ASCII, which stays an eyeball
check (the issue); generating the twin from the TikZ graph, and parsing
ASCII arrows, both offered on the issue and not chosen; element-scope
`cg-allow` (#1058), so a deliberate abbreviation cannot be excused until
it lands; `figure new` (#1052), which will copy the pairs this item
writes.

## What it is for

The `.txt` twin is the only figure a reader of the `md`, `docx` or
`html` render sees. The two forms are written separately, by hand, and
drift: a box renamed in one, a tag added to the TikZ and never to the
ASCII. Until now the skill said "nothing checks that the two forms
agree, so check it yourself". `figure check` now does, for names, tags
and panel letters, and reports a figure with no twin at all.

## Decisions

| Question | Decision |
| --- | --- |
| What `t1-labels` compares | **Names only** (*user*): a node label's first line (for `\cglab{name}{gloss}`, the name), every `\cgzonelabel` title and every `\cglegenditem` text. Glosses and a label's later lines are not compared: that is where a twin legitimately rewords to fit a 20-column box |
| What `t2-tags` compares | Every node placed on a `\draw` or `\path` statement, whatever its style. The drafts tag edges with `cgtag`, `lbl` and plain `node[midway]`, so a style test would miss most of them. Every line of a tag is compared |
| What `t3-panels` compares | The set of `(a)`, `(b)`, ... letters opening a label line in the `.tex`, against the set of `(<letter>)` tokens in the `.txt` |
| How a name is "present" | **Every word of it appears in the twin as a whole word**, case-insensitively, in any order. Words are runs of `[a-z0-9]`. Not ordered and not a substring, because ASCII boxes wrap a label across lines and interleave neighbouring boxes (see Bench) |
| TeX markup | Stripped before comparison: `\\` (with any `[len]`) splits lines, `~` and `\,` `\;` `\:` `\!` `\ ` are spaces, `\&` `\%` `\_` `\#` are their character, any other control word is dropped with its braces kept as text. **Maths (`$...$`, `\(...\)`) is dropped**: ASCII cannot spell `\hat{x}`. A name left empty is not compared |
| Skipped labels | Empty labels, labels inside the house block, labels carrying a macro parameter (`#1`), and labels carrying a `\foreach` variable anywhere (`{e\n}`): each pass sets a different label, so the source text is none of them |
| No twin | **A fourth rule, `twin-missing`** (*user*): figure-scope, objective, **not allowable** (*user*: it is fixed, never excused). When it fires, `t1` to `t3` are listed under "not measured" with "no twin", not reported three times. This adds a rule the v3 plan's table did not list; the plan records it |
| Targets | `t1`: the node's TikZ name, the zone's fit-node name or the legend item's name; the name's text where the node is unnamed. `t2`: `<from>-><to>` from the path's first and last named node, or the tag's text where either is missing. `t3` and `twin-missing`: `figure`. So #1058 can name them in an allow |
| Measurement | `t1`/`t2`: `missing "<words>"` (the words not found). `t3`: `tex (a),(b); twin (a)`. `twin-missing`: `no <name>.txt beside <name>.tex` |
| Compile | None. All four read source only, like `focal-count`, so they run on a host without TeX and hold whether or not the figure compiles |
| Where the twin is read | `check()` reads `<path>.with_suffix(".txt")` as UTF-8 with `errors="replace"`, so a stray non-ASCII byte is a WRITING-STANDARDS matter and not a crash. `apply()` takes it as `twin: str \| None` (`None`: absent) |
| Scaffolds and exemplars | **All ten get a twin** (*user*: the three exemplars too), so every figure in `assets/tikz/` is a pair and one test holds it, at 7-bit ASCII and at most 72 columns. Written **after #1083 (1e) and #1054 (2c, shipped as #1086) merged** (*user*), because both rewrote every scaffold's labels; both had merged by the time the code was done |
| Reuse | The label reader is its own module, `chitragupta/figure/_twin.py`, so #1055 (wording rules `w1` to `w3`, which also need names, glosses and tags) reuses it rather than writing a second |

## Bench

A throwaway prototype of this matching, run over the 49 draft figure
pairs of the reference book (`content/drafts/`, local):

| Matching | `t1` misses | `t2` misses |
| --- | --- | --- |
| Whole label line as a substring of the twin | 140 of 651 lines | 25 of 141 |
| Every word of a line, anywhere in the twin | 31 of 651 | 6 of 141 |
| Same, names only (the decision) | 11 of 389 | 6 of 141 |

- Substring matching misses mostly on reflow: a label wrapped across
  two lines of an ASCII box, or two panels' captions interleaved.
- What word matching finds is mostly real: `pctrl-blocks` has "12 V
  power supply" in the TikZ and "12 V PSU" in the twin; `seven-blocks`'
  tag "reads" and `turbine-mode-machine`'s "rated speed reached" are not
  in their twins.
- The rest is maths (`$\hat{x}$` written `x_est`), hence maths is
  dropped.
- Panel letters already agree in all 49.

## Changed in the build

Running the reader over the 49 draft pairs, after its unit tests passed,
found four reading defects, each fixed with a test first:

- `{innovation\\$z - C\hat{x}$}`: the `$` after `\\` read as an
  escaped dollar, so the maths was compared. Line breaks are now split
  before maths is dropped.
- `{\scriptsize e\n}` inside a `\foreach`: stripping `\n` left `e`,
  which no pass of the loop prints. A label carrying a loop variable is
  now skipped.
- A raw newline inside a label (`{the one⏎blocking check}`) split it
  into two lines; TeX sets it as a space, and so does the reader now.
- `(hub) edge node {ask} (s1)`: `_source.py`'s node keyword does not
  see a node after `edge`, so the tag was never read. `_twin.py` adds
  that form to its own pattern rather than widening the shared one,
  which the probe also uses.

`figure new` (#1052, merged as #1088 while this was being built) already
copied a twin where a layout shipped one, and said "no twin" otherwise.
With every shipped layout now a pair, its tests reach the "no twin" path
through a scaffold directory of their own, a test pins that every
shipped layout's twin is copied, and the skill's step 4 says to redraw
the copied twin rather than to write one.

After the fixes the 49 pairs give 5 `t1` and 6 `t2` findings, all real
drift or a twin's spelling of maths, and no `t3`.

## Components

| Unit | Does |
| --- | --- |
| `chitragupta/figure/_twin.py` | `Text` (target, text); `names(source)`, `tags(source)`, `panels_tex(source)`, `panels_twin(twin)`, `plain(label) -> list[str]`, `words(text) -> set[str]`, and `agree(source, twin) -> (findings, not_measured)` |
| `chitragupta/figure/_rules.py` | `twin-missing` (figure, objective, not allowable), `t1-labels`, `t2-tags` (element, objective), `t3-panels` (figure, objective), after `stranded-arrowhead` |
| `chitragupta/figure/_check.py` | `check()` reads the twin; `apply(..., twin=None)` and `evaluate()` add `agree()`'s findings and not-measured rows |
| `docs/TIKZ-STYLE.md`, `references/check.md` | The four rows; the test in `tests/test_figure_rule_ids.py` keeps them and the registry one set |
| `SKILL.md` step 4, three copies | "Nothing checks..." becomes "`figure check` compares them (`t1` to `t3`); edge topology is still yours to check by eye" |
| `assets/tikz/*.txt`, `assets/tikz/exemplars/*.txt` | Ten twins |
| `assets/tikz/README.md` | Every figure here is a pair |
| `plans/fig-xii-figure-drawer-v3.md` | The 2e row and the Twin agreement table record `twin-missing`, names only and maths dropped |

---

# Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `figure check` reports `twin-missing`, `t1-labels`,
`t2-tags` and `t3-panels`, and every figure in `assets/tikz/` has a twin
that passes them.

**Architecture:** One source-only reader, `_twin.py`, extracts names,
tags and panel letters from the `.tex` and compares them word by word
against the `.txt`. `_check.apply()` gains the twin text and folds the
findings into the existing report, so the text and JSON outputs need no
change.

**Tech Stack:** Python 3.12+ (`re`, `dataclasses`), pytest.

**Spec:** the Decisions table above.

## Global Constraints

- Every rule exits 0; none becomes a gate (SOUL.md's one gate).
- No citekey anywhere: not in a twin, a fixture or a doc example.
- Line and branch coverage stays at 100%.
- Twins are 7-bit ASCII (WRITING-STANDARDS §10).
- PR body says "Part of #1056", never "Closes"; the issue stays open for
  its lessons comment. MINOR version bump in `pyproject.toml`, taken
  from `main` at PR time.
- Run tests with `/home/prasad/git/chitragupta-freja/.venv-full/bin/python -m pytest`
  and `PYTHONPATH=<worktree>`, with `config.toml` copied from the example.

## Review Focus

1. A twin that is present but empty: every name fires `t1`, nothing
   crashes. Test in Task 1.
2. A name that is maths only (`{$x_1$}`) or a loop variable (`{\x}`):
   not compared, no finding. Test in Task 1.
3. A hyphenated name (`4-channel relay` against `4-ch relay`): fires on
   `channel`. Test in Task 1.
4. A twin with non-UTF-8 bytes: read with replacement, no crash. Test in
   Task 2.
5. `% cg-allow: twin-missing -- ...`: reported malformed, "cannot be
   allowed", and the finding stays. Test in Task 2.

---

### Task 1: The twin reader, `_twin.py`

**Files:**
- Create: `chitragupta/figure/_twin.py`
- Test: `tests/test_figure_twin.py`

**Interfaces:**
- Consumes: `strip_comments` (`chitragupta/_tex_comments.py`),
  `_NODE_KEYWORD` (`review/figure_layout/_source.py`), `Finding`
  (`_rules.py`), and the house block's end marker as `_block.py`
  defines it (so the block's own `\node` definitions are skipped).
- Produces:
  - `@dataclass(frozen=True) class Text: target: str; text: str`
  - `plain(label: str) -> list[str]`: the label's lines, markup
    stripped, maths dropped, whitespace collapsed, empty lines removed.
  - `words(text: str) -> set[str]`: lower-cased `[a-z0-9]+` runs.
  - `names(source: str) -> list[Text]`, `tags(source: str) -> list[Text]`.
  - `panels_tex(source: str) -> set[str]`, `panels_twin(twin: str) -> set[str]`.
  - `agree(source: str, twin: str | None) -> tuple[list[Finding], list[tuple[str, str]]]`.
  - `NO_TWIN = "no twin"` (the not-measured reason).

- [x] **Step 1: Write the failing tests.** Source-only, no TeX:
  - `plain`: `r"\textbf{Plan}\\[2pt]gloss"` gives `["plan", "gloss"]`
    (case kept or lowered, pick one and compare lowered); `"$x_1$ state"`
    gives `["state"]`; `"$x$"` gives `[]`; `r"A~B\,C \& D"` gives
    `["a b c & d"]`.
  - `names`: `\node (relay) {CS-IO404\\4-channel relay};` gives
    `Text("relay", "cs-io404")`; `\cglab{Plan}{a gloss}` gives the name
    only; `\cgzonelabel{fixed}{cgFlow}{Deterministic}` gives
    `Text("fixed", "deterministic")`; `\cglegenditem{lg}{0,0}{cgFlow}{flow}`
    gives `Text("lg", "flow")`; an unnamed node's target is its text;
    `{}`, `{$x$}` and `{\x}` give nothing; nothing from the house block.
  - `tags`: `\draw (a) -- node[cgtag] {water} (b);` gives
    `Text("a->b", "water")`; `node[midway,right] {12 V switched}` after
    `(relay.south) -- (pump.north)` gives `Text("relay->pump", ...)`;
    a `child { node (c) {C} }` is a name, not a tag.
  - `panels_tex` over `{(a) lumps}` and `{(b) mesh}` is `{"a","b"}`;
    `panels_twin("( x_3 )  (a) lumps")` is `{"a"}`.
  - `agree`, each rule in both polarities: agreeing pair gives `([], [])`;
    renamed box fires `t1-labels relay missing "channel"`
    (`4-channel` vs `4-ch`); dropped tag fires `t2-tags`; panel `(b)`
    absent from the twin fires `t3-panels` with `tex (a),(b); twin (a)`;
    `twin=None` gives one `twin-missing` finding and `t1`/`t2`/`t3`
    under not measured with `NO_TWIN`; `twin=""` fires `t1` once per name.
- [x] **Step 2: Run** `pytest tests/test_figure_twin.py -v`; expect
  import failure.
- [x] **Step 3: Implement `_twin.py`.** Node declarations by the same
  balanced-bracket scan `_focal._declaration` uses, extended to read the
  label's balanced `{...}` (a label nests `\cglab{..}{..}`, so `_NODE_RE`'s
  non-greedy `.*?\}` cannot). A node is a tag when its keyword sits
  inside a `\draw`/`\path` statement and is not preceded by `{` (the
  `child {` form). The macros are read by name with their balanced
  arguments. Module docstring states the Decisions rows it implements.
- [x] **Step 4: Run** the tests; expect pass, and 100% coverage of
  `_twin.py` (`--cov=chitragupta.figure._twin --cov-branch`).
- [x] **Step 5: Commit** `Read a figure's names, tags and panels for twin agreement (#1056)`.

### Task 2: The four rules in `figure check`

**Files:**
- Modify: `chitragupta/figure/_rules.py`, `chitragupta/figure/_check.py`
- Modify: `docs/TIKZ-STYLE.md` (rules table), `.claude/skills/figure-drawer/references/check.md` (table)
- Create: `tests/fixtures/figure/check/*.txt` (a twin for each existing fixture), `tests/fixtures/figure/twin/` (`agrees`, `renamed`, `untagged`, `panels`, `no-twin`, each `.tex` with its `.txt` but the last)
- Test: `tests/test_figure_check.py`, `tests/test_figure_twin.py`

**Interfaces:**
- Consumes: `agree()`, `NO_TWIN` from Task 1.
- Produces: `apply(path, width_pt, figure, source, layout="", twin=None)`;
  `check()` reads `path.with_suffix(".txt")` when it exists.

- [x] **Step 1: Write the failing tests.**
  - `test_figure_rule_ids.py` already fails once the registry has the
    four ids and the tables do not: add the registry entries first and
    watch it fail.
  - In `test_figure_check.py`: a missing twin reports `twin-missing`
    and lists `t1-labels`, `t2-tags`, `t3-panels` as not measured; a
    `% cg-allow: twin-missing -- ...` is malformed with "cannot be
    allowed" and the finding stays; a twin file with `b"\xff"` is read
    without raising; a figure that does not compile still gets the twin
    rules. Existing `apply()` callers pass a `twin=` that agrees with
    their source (a module constant beside `ONE_PICTURE`), so every
    existing assertion keeps its meaning.
  - The `TestAgainstRealLualatex` clean fixtures stay clean once each
    has its twin; the firing fixtures still fire only their own rule.
  - The `tests/fixtures/figure/twin/` pairs fire their rule and only it.
- [x] **Step 2: Run** `pytest tests/test_figure_check.py tests/test_figure_rule_ids.py tests/test_figure_twin.py`; expect the new tests to fail.
- [x] **Step 3: Implement.** Registry order: `twin-missing`, `t1-labels`,
  `t2-tags`, `t3-panels` after `stranded-arrowhead`. `evaluate()` takes
  `twin` and appends `agree()`'s findings before the sort; its
  not-measured rows join the others. Add the four table rows with their
  usual fix ("write the twin"; "use the TikZ's words for the name in the
  twin"; "put the tag on the twin's arrow"; "letter the twin's panels as
  the TikZ's").
- [x] **Step 4: Run** the three test files, then the whole `tests/test_figure_*.py`; expect pass.
- [x] **Step 5: Commit** `Report twin agreement in figure check: t1-t3 and twin-missing (#1056)`.

### Task 3: Skill, docs and the v3 plan

**Files:**
- Modify: `.claude/skills/figure-drawer/SKILL.md`, `.agents/skills/figure-drawer/SKILL.md`, `.opencode/skills/figure-drawer-opencode/SKILL.md` (step 4)
- Modify: `plans/fig-xii-figure-drawer-v3.md` (2e row, Twin agreement table), `docs/CLI.md` if it lists rule ids
- Test: `tests/test_skill_figure_step.py`

- [x] **Step 1: Write the failing test**: every `SKILL.md` copy names
  `t1` to `t3` in its twin step and none says "Nothing checks".
- [x] **Step 2: Run** it; expect FAIL.
- [x] **Step 3: Edit** the three copies and the v3 plan.
- [x] **Step 4: Run** `tests/test_skill_figure_step.py` and the skill
  byte-cap test; expect pass.
- [x] **Step 5: Commit** `Tell the figure-drawer skill that figure check compares the twin (#1056)`.

### Task 4: Ten twins

**Files:**
- Create: `assets/tikz/{pipeline,zoned-spine,branching-tree,hub-and-spoke-network,map,control-loop,layered-stack}.txt`, `assets/tikz/exemplars/{architecture,rag-stages,retrieval}.txt`
- Modify: `assets/tikz/README.md`
- Test: `tests/test_tikz_scaffolds.py`

- [x] **Step 1: Rebase** onto `main` (#1083 and #1086 have merged);
  re-read the version and the files they touched.
- [x] **Step 2: Write the failing test**: every `.tex` under
  `assets/tikz/` except `cg-figstyle.tex` has a sibling `.txt`, the
  `.txt` is 7-bit ASCII, and `agree(tex, txt)` returns no findings.
- [x] **Step 3: Run** it; expect ten `twin-missing` failures.
- [x] **Step 4: Write the ten twins**, each laid out as its TikZ is
  (same boxes, tags and panel letters), so the scaffold teaches how a
  twin is written. Add the README line.
- [x] **Step 5: Run** `tests/test_tikz_scaffolds.py` and
  `tests/test_figure_check.py`; expect pass.
- [x] **Step 6: Commit** `Give every scaffold and exemplar its ASCII twin (#1056)`.

### Task 5: Release prep

- [ ] Bump `pyproject.toml` to the next MINOR above `main`.
- [ ] Mark this plan's status **built**, with a "Changed in the build"
  section if anything moved.
- [ ] Full suite and coverage; known host-only failures (#1037's
  `test_render_output*`, the Python 3.14 symlink and unicode tests) are
  named as such, not hidden.
- [ ] Independent review of the branch, then PR "Part of #1056".
