# 🔎 XII-2b: `chitragupta figure check`, the skeleton

Status: **design, not built.** Written 2026-10-28 against `main` at
`e072bc0`, from a brainstorming session on issue
[#1053](https://github.com/prasadtalasila/chitragupta/issues/1053).
The components (section "Components") and the four decisions marked
*user* were agreed in that session; the rule details, report format,
probe change and tests below are the session's proposal, put up for
review with this plan rather than walked through one by one.

**Written for** whoever builds #1053: a session that changes
`chitragupta/figure/`, `chitragupta/review/figure_layout/`, the
`figure-drawer` skill, `tests/` and `docs/`, and is therefore governed
by `DEVELOPER-AGENTS.md` and `docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` (the v3 design this is
item 2b of, especially "The rules", "Exceptions: `cg-allow`" and "The
commands"), `docs/TIKZ-STYLE.md`, the `review figure` aid in
`chitragupta/review/figure_layout/`, and the lessons recorded on
issues #1037, #1047 and #1049 when those items landed.

**Not covered here:** connector rules `c1` to `c6` (#1054), contrast and
wording (#1055), twin agreement (#1056), size reporting beyond width and
stray space (#1057), element-scope `cg-allow` and stale-allow detection
(#1058), `figure new` and `figure look` (#1052), and the `SKILL.md`
router rewrite (#1048).

## Where it lands

**`main`, not `improve-figures`** (user, 2026-10-28). The v3 plan put
every item on the integration branch; `main` now carries everything
that branch had (#1071, #1073, #1077, and 1b as #1078), so nothing this
item depends on is missing. Branch off `origin/main`, PR into `main`.

## What it is for

A drafting agent runs one command on one figure file and gets every
rule the figure breaks, by rule id, with what was measured. It fixes
what is wrong and records what is deliberate as a reasoned
`% cg-allow:` line in the figure itself. The command exits 0 whatever
it finds: SOUL.md allows one gate, and this is not it. The skill's
procedure, not an exit code, is what tells the agent to resolve or
allow each objective finding.

2b is the skeleton every later rule plugs into, so the parts that must
be right now are the rule registry, the report format and the allow
grammar. It ships three new rules of its own: `size-width`,
`size-stray` and `focal-count`.

## Decisions

| Question | Decision |
| --- | --- |
| Ids for the existing `review figure` findings | **The `kind` strings `review figure --json` already ships** (*user*): `does-not-compile`, `node-text-overload`, `node-overlap`, `stranded-arrowhead`, `loads-library-by-hand`, `content-protrusion`, `nothing-measurable`. The v3 plan's `overlap`, `overlong-node` and `library-by-hand` are corrected to match in the implementing PR. One name per finding across both commands, and no JSON consumer breaks |
| Where the rule list lives for the skill | **A new shared reference, `.claude/skills/figure-drawer/references/check.md`** (*user*), named by all three `SKILL.md` copies. Keeps the copies small ahead of #1048's 8,000-byte cap |
| No `lualatex` or no `tikz.sty` on the host | **Exit 2 and check nothing** (*user*), with the missing binary named and `chitragupta doctor` suggested, as `figure sync` does for a broken install. A partial report would let a skill read "no `size-width` line" as "fits" |
| A well-formed allow for an element-scope rule, before #1058 | **Listed as "not honoured until #1058"** (*user*). It is parsed and validated, the finding it names still prints, and a line written correctly today does not change status when 2g lands |
| Code layout | New modules in `chitragupta/figure/`, reusing `review.figure_layout` for the probe and the existing findings (*user*, as approach A against building it inside the review aid or shelling out to `review figure --json`) |
| Class of the existing findings | All seven are binary, so all seven are **objective**. Emptiness, the unmeasured-names list and the edge list stay diagnostics outside the findings, as R3 already requires of `review figure` |
| Default `--width` | 453pt: A4 (8.27in) less two 1in margins, times 72.27pt/in. A constant, with a test that pins it to `render_output`'s `a4` and `1in` defaults so a change there is caught. Part X replaces it with output targets |

## Components

| Unit | Does | Depends on |
| --- | --- | --- |
| `chitragupta/figure/_rules.py` | `RULES`, the one registry: rule id to scope (`figure`/`element`), class (`objective`/`advisory`) and whether an allow may name it. The cross-check test reads it | nothing |
| `chitragupta/figure/_allow.py` | `parse_allows(source)`: every `% cg-allow:` line, sorted into honoured candidates, deferred (element scope) and malformed, each with its line number | `_rules` |
| `chitragupta/figure/_check.py` | `check(path, width_pt)`: runs the probe once, evaluates the three new rules, maps the `FigureResult` findings onto rule ids, applies the allows, orders objective first | `_rules`, `_allow`, `review.figure_layout` |
| `chitragupta/figure/_check_report.py` | Text report and the `--json` payload. Checks nothing | `_check` |
| `chitragupta/figure/__main__.py` | The `check` verb: `figure check <figure.tex> [--width PT] [--json]` | the above |
| `chitragupta/review/figure_layout/_check_one.py` | `check_figure(path, skipped, *, boxed=False)`: the per-figure body `check_draft` has inline today, so both commands build a `FigureResult` the same way | existing |
| `chitragupta/review/figure_layout/_probe.py` | `scaffold()` and the compile gain `preload` (the figure's own libraries in the preamble) and `boxed` (see "The probe") | existing |

**The `_check_one.py` split is forced, not chosen.**
`chitragupta/review/figure_layout/__init__.py` is at 250 of 250 code
lines, so `check_figure` cannot be added beside `check_draft`. Moving
the loop body out is the boundary the module already has (one draft,
many figures), and the PR says it is the forced kind of split.
`FigureResult` gains `input_width: float | None`; `review figure`'s
report and JSON do not serialise it, so that aid's output is unchanged.

## The rules in 2b

Every rule's target and measurement as the report prints them. A
figure-scope rule's target is the literal `figure`.

| Id | Scope | How it is measured | Prints |
| --- | --- | --- | --- |
| `size-width` | figure | The picture's width from `current bounding box`. A file with more than one `tikzpicture` is measured as the whole `\hbox` instead, since panels set side by side are what a reader sees | `475.2pt wide, target 453.0pt` |
| `size-stray` | figure | `\hbox` width less picture width, over 0.5pt. **Not measured** (listed as such, never silently skipped) when the file has no picture or more than one, since side-by-side panels and their spacing are not stray | `13.1pt stray (input 320.4pt, picture 307.3pt)` |
| `focal-count` | figure | From source, comments stripped: `\node` or path `node` declarations whose option list contains `cgkey`. More than one fires. A `cgkey` reached only through a style the figure defines itself is not seen; documented, not guessed at | `2 cgkey nodes: retriever, reranker` |
| `does-not-compile` | figure | Existing. Every geometry rule is then listed as not measured. **Cannot be allowed** | the first `!` line |
| `nothing-measurable` | figure | Existing | `names no node` |
| `content-protrusion` | figure | Existing | `content protrudes past the main block` |
| `loads-library-by-hand` | figure | Existing. One finding listing every internal macro | `\tikz@library@...` |
| `node-overlap` | element | Existing. Target is the pair, `a+b` | `boxes intersect` |
| `node-text-overload` | element | Existing. Target is the node | `17 words (over 15)` |
| `stranded-arrowhead` | element | Existing. Target is the point, `(3,2)` | `arrowhead mid-line` |

`size-stray` with the libraries preloaded can still fire: a line in the
figure file outside the picture that ends without `%` is a space in
horizontal mode. That is what it is for. The render inputs a figure in
vertical mode and never sees it, but a thesis that sets the figure
inline or in `\sbox` does (#1046).

## `cg-allow` in 2b

Form, from the v3 plan: `% cg-allow: <rule-id> [<target>] -- <reason>`,
one per full-line comment, anywhere in the file. Parsed from raw lines,
since the comment is the content.

| Line | Outcome |
| --- | --- |
| Figure-scope id, no target, non-empty reason | **Honoured.** The finding, if it fired, moves out of the findings into the allowed list with its measurement; if it did not fire, the allow is still listed, marked `did not fire` |
| Element-scope id, a target, non-empty reason | **Deferred**: listed under "not honoured until #1058"; the finding still prints |
| No ` -- `, or an empty reason | Malformed: `no reason` |
| An id not in `RULES` | Malformed: `unknown rule` |
| A figure-scope id with a target | Malformed: `figure-scope rule takes no target` |
| An element-scope id without a target | Malformed: `element-scope rule needs a target` |
| `does-not-compile` | Malformed: `cannot be allowed` |

"Did not fire" is stated, not judged: reporting a stale allow as a
finding is #1058's.

## The probe

`scaffold(source, names)` keeps its current output byte for byte when
called as `review figure` calls it. `figure check` calls it with:

- **`preload`**: `\usetikzlibrary{...}` in the preamble with
  `render_output._tikz_libraries.libraries_in(source)`, as the renderer
  does since #781. The figure's own load line then adds nothing.
- **`boxed`**: the figure is set with `\sbox` into a box, the probe
  prints `CGWIDTH <wd>`, and the box is then shipped with `\usebox`.
  The shipping matters: LuaTeX refuses a run that wrote PDF objects
  (the `shadows.blur` fadings) and shipped no page (#1037's lessons).

One compile per check, through `tex_engine`'s flags, read fence and
environment, as #1037 requires of every new compile.

**Risk, settled by the bench below:** a figure that compiles in a float
but not inside a box, for instance one carrying a `\caption` or a
display environment outside its picture. If the bench finds any, the
fallback is a second, unboxed compile for that figure, with
`size-stray` and the whole-box width reported as not measured.

## The report

Text, one line per finding, objective first, in `RULES` order then by
target:

```text
figures/flow.tex
  size-width          figure      475.2pt wide, target 453.0pt
  focal-count         figure      2 cgkey nodes: retriever, reranker
  node-overlap        legend+pot  boxes intersect
allowed
  content-protrusion  figure      content protrudes past the main block -- the legend hangs below on purpose (line 4)
not honoured until #1058
  node-overlap        legend+pot  -- the legend sits on purpose (line 5)
malformed allows
  line 6: % cg-allow: size-width --   (no reason)
not measured
  size-stray: 2 tikzpictures; panels and their spacing are not stray
diagnostics (not findings)
  edges (confirm against the prose): a -> b, b -> c
  41% of the figure's box is empty (advisory, human-read only -- nothing consumes this)
figure check: 3 objective, 0 advisory, 1 allowed, 1 deferred, 1 malformed
```

A section with nothing in it is left out; the summary line always
prints, and a run with no findings ends with the same "not a verdict on
the figure" sentence `review figure` uses.

`--json` carries the same content, never a second computation:
`figure`, `width_pt`, `findings` (each `rule`, `class`, `scope`,
`target`, `measurement`), `allowed` and `deferred` (each `rule`,
`target`, `reason`, `line`, and for `allowed` the suppressed
`measurement` or `null`), `malformed` (`line`, `text`, `problem`),
`not_measured` (`rule`, `why`), and `diagnostics` (`edges`,
`empty_fraction` with its note, `names_unmeasured`).

**Exit codes:** 0 after any run, whatever it found. 2 for a usage
error, a path that is not a readable file, or a missing `lualatex` or
`tikz.sty`.

## Skill and documentation

- **`references/check.md`** (new, once under `.claude/`): the rule
  table (id, scope, class, one line on what fixes it), the `cg-allow`
  form with two examples, and the procedure: resolve or allow every
  objective finding, read the advisory ones, report the allows to the
  caller.
- **Each `SKILL.md` copy, step 8**: `chitragupta figure check
  figures/<name>.tex` replaces `python -m chitragupta.review figure
  <draft>`, and names `references/check.md`. Steps 4 to 7 wait for
  #1048, which rewrites the skill as a router.
- **`docs/TIKZ-STYLE.md`**: a rules table under the pre-flight
  checklist, the `cg-allow` section, and "Nothing here is a gate"
  extended to `figure check`.
- **`docs/CLI.md`**: `chitragupta figure check`. The packaging test's
  `FIGURE_VERBS` gains `check`.
- **`plans/fig-xii-figure-drawer-v3.md`**: the existing-finding names
  corrected, and the integration-branch note updated for the move to
  `main`.
- The usual sweep for every place that says `figure` has one verb.

## Tests

No citekey appears in any fixture or example; figure files carry none
by construction, and the fixtures are synthetic.

- **Unit, no TeX** (every host, CI's Windows leg included): every row of
  the `cg-allow` table above; `focal-count` over strings in both
  polarities; rule evaluation over hand-built `FigureResult`s
  (over-width and under-width, stray over and under 0.5pt, zero, one and
  two pictures); report and JSON from fixed results; `RULES` order;
  the 453pt constant against `render_output`'s defaults; exit 2 for a
  missing file and, with `_require` faked, for a missing toolchain.
- **With TeX** (Linux leg; the TeX-only lines carry
  `# pragma: no cover-windows` as `_probe.py`'s do): fixtures under
  `tests/fixtures/figure/check/`, a firing and a clean one per rule:
  `wide`/`narrow`, `stray`/`tight`, `two-keys`/`one-key`,
  `two-pictures` (must not fire `size-stray`), and `allowed-wide` end to
  end. The seven scaffolds are clean under `focal-count` and
  `size-stray`; `exemplars/rag-stages` fires `size-width` (1.09 of the
  text width, owned by #1050), which pins the firing case on a real
  figure.
- **`review figure` unchanged**: its existing tests pass untouched, and
  a test asserts `scaffold(source, names)` with default arguments is
  byte-identical to today's.
- **The cross-check** (`tests/test_figure_rule_ids.py`): the ids in
  `RULES`, in TIKZ-STYLE.md's rules table and in `references/check.md`'s
  table are the same set, and every `SKILL.md` copy names
  `references/check.md`. Per DEVELOPER-AGENTS.md's "a guard is tested
  against the exact shape it was blind to", a test feeds the comparison
  a table with one id missing and one id extra and confirms it fails.
- Coverage stays at 100% line and branch.

## Bench, before the thresholds are final

Run `figure check` over the seven scaffolds, the three exemplars and
the 49 draft figures on the development host (`content/drafts/`, never
committed). Record per-rule counts in the PR and on #1053, and the
boxed-versus-unboxed compile result for each figure (see the probe
risk). The 0.5pt stray tolerance and the multi-picture rule are judged
against that run, not set ahead of it.

## Build order

Each step is test-first: write the test, see it red, make it green.

1. `_check_one.py` split. Check: the existing `review figure` suite
   passes unchanged, and `__init__.py` is under 250 code lines.
2. `_rules.py` and `_allow.py`. Check: the unit tests for the allow
   table.
3. Probe `preload` and `boxed`. Check: the default-arguments
   byte-identity test, and a boxed compile of a scaffold reporting a
   `CGWIDTH`.
4. `_check.py` with the three rules. Check: the unit rule tests, then
   the TeX fixtures.
5. `_check_report.py` and the `check` verb. Check: report and JSON
   tests, exit codes, the packaging command table.
6. Bench. Check: counts recorded; tolerance confirmed or changed.
7. Docs and skill, then the cross-check test. Check: the cross-check,
   markdownlint, and the documentation sweep.
8. MINOR version bump (a new CLI verb), full local checks, PR into
   `main`.
