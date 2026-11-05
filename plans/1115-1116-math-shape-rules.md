# 1115/1116: which backtick spans are mathematics

Status: **designed, unbuilt; reviewed.** Written 2026-11-05, for
[issue 1115](https://github.com/prasadtalasila/chitragupta/issues/1115)
and [issue 1116](https://github.com/prasadtalasila/chitragupta/issues/1116),
fixed together at the user's request because both change the same test.

**Written for** whoever builds the fix. **It assumes**
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §12 (mapped
mathematics, `math.md`) and the module docstrings of
`chitragupta/render_output/_math.py` and `_math_findings.py`.

**Not covered here:** catching every quantity. A bare `0.5` and a bare
`404`, or `SoC` and `seq`, are the same characters; no rule over the
span's text separates them (measured below). The rules catch what the
text decides, the draft's own `math.md` decides some more, and a new
"not mathematics" table lets the author settle the rest in one line.
Nor is a `math.md` migration: every existing file stays valid.

## The defects

`findings()` calls an unmapped span a gap when `_MATH_SHAPED_RE`
(`[=<>]|\d\s*[-+*/^]\s*\d`) matches it, or when it equals a symbol the
mapping's LaTeX uses. That one test is wrong both ways.

| Wrongly warned (#1115) | Why |
| --- | --- |
| `02-02-math-model-solution.md`, `code/02-01-create-mock-physical-twin/` | `2-0` read as subtraction |
| `GET /sensing/plant_1/moisture?limit=1`, `?limit=`, `?since_timestamp=` | the `=` |
| `<unit>_<parameter>` | `<` and `>` |
| a review report's header: the draft path and the command line | `review <aid> --write` renders its own report |

| Wrongly silent (#1116) | Why |
| --- | --- |
| `-1`, `-0.074` | no digit left of the operator |
| `[1 0]`, `[120.0, 1.5]` | no operator |
| `A * P_est * A^T + Q` | operators between letters |
| two `math.md` rows for one key with different LaTeX | `load_mapping` builds a dict; the last row wins silently |

Over the user's drafts (`chitragupta-freja/content`, `chitragupta-drafts`;
42 drafts, 13 `math.md` files, 1,132 rows) every one of today's six gap
warnings is a false positive.

## Measurement method

Recall is **leave-one-out**: for each `math.md` row, delete it and ask
whether the draft would now warn, judged against the rest of *that*
draft's `math.md`. That is the question that matters ("would a forgotten
row be noticed?"). False positives are every unmapped span in every
draft, with and without a `math.md`.

| | Today | After |
| --- | --- | --- |
| rows a forgotten-row warning would catch | ~616 by shape + symbols | **1,130 of 1,132** |
| false warnings on code spans | 6 | 6, all bare numbers in drafts that have a `math.md`, silenced by the new table |

The two still missed: `SoC` in a chapter whose `math.md` mentions it in
no other row, and `ds`, a lowercase two-letter word dropped on purpose
(rule C3). `mu_i` in `07-simulators.md` newly warns; it is a real
unmapped quantity.

## Design

### 1. A new module, `_math_shapes.py`: "is this span mathematics, and by which rule?"

One public function, roughly:

```python
def rule_for(span: str, symbols: frozenset[str], has_mapping: bool) -> str | None:
    """The name of the first rule that calls `span` mathematics, or None."""
```

It owns everything that judges a span's shape, so `_math_findings`
keeps only reporting and `_math` keeps only resolving.
`_MATH_SHAPED_RE` moves here from `_math.py` (only `_math_findings`
imports it). Each rule is its own small named regex in an ordered
table, not one alternation: each gets its own test, the warning names
the rule that fired, and a false alarm points straight at it.

**Order.** C3 (known names) first; then the whole-span *anchored* rules
of step B on the **raw** span; then step A's blanking; then step B's
*search* rules on what is left; then C1/C2. Anchored rules run before
blanking because blanking can eat what they need: `dV/dSoC` is
path-shaped to step A.

**Step A: blank what is plainly not mathematics.** Whitespace-separated
tokens are replaced by a space before the search rules run, so a command
line with a path in it is judged on what is left:

| Blank | Pattern idea | Example |
| --- | --- | --- |
| path | path characters `[\w.~/-]`, a `/`, and a run of 3+ letters | `code/02-01-x/`, `/a/b/02-01-s.md` |
| file name | path characters ending `.ext` (letter-led, ≤5 chars) | `02-02-math-model-solution.md` |
| hyphenated word | a hyphen next to a run of 2+ letters | `02-01-create`, `fastapi-0.115.12` |
| query string | `?name=…`, `&name=…` | `?limit=1` |
| placeholder | `<word>` | `<unit>` |
| date / timestamp | `\d{4}-\d{2}-\d{2}` with optional `T…` | `2026-02-01` (§12: dates are not math) |
| version | `v?\d+\.\d+\.\d+` | `6.157.0` |

The path rule needs **3+** letters so `dT/dt` and `dW/dt` are not paths.

**Step B: shape rules.** These apply to every draft, with or without a `math.md`.

Anchored rules, matched against the whole raw span:

| Rule | Example |
| --- | --- |
| `signed-number` | `-1`, `-0.074` (numbers only: `-m` is a flag) |
| `vector` | `[1 0]`, `[120.0, 1.5]`, `[1; -1]` (numbers only) |
| `matrix` | `[a, b; c, d]` (brackets holding a `;`) |
| `derivative` | `dT/dt`, `d^2x/dt^2`, `dV/dSoC`: `^d\^?\d?[A-Za-z]\w*/d[A-Za-z]\w*(\^\d)?$` (accepted side effect: `docs/dt`) |
| `conditional` | `P(A \| B)`, `p(x_k \| z_{1:k})` |
| `greek-subscript` | `sigma_2`, `Pi_ij`, `mu_i` (lower or Capitalised name plus a subscript; not `PI`) |
| `index-step` | `T_k+1`, `x_{k+1}` |
| `sci-number` | `1e-12`, `1.44e6` |
| `number-list` | `0, 3`, `0.65, 0.3, 0.05` |

Search rules, matched anywhere in the span after step A:

| Rule | Example |
| --- | --- |
| `relation` | `h = 9` |
| `digit-op-digit` (today's rule) | `3 - 1` |
| `star-caret` | `A * x`, `A^T`, `a^2` |
| `spaced-op` | `t + h`, `a / b` (`Ctrl+C` stays code) |

**Step C: context rules.** These decide on the author's own declared
mathematics. A draft without a `math.md` never saw them, and gains none.

| Rule | Gate | Fires when | Example |
| --- | --- | --- | --- |
| C3 `symbol` (runs **first**) | the known-name set is non-empty, as today | the span, minus a leading sign and a subscript, is a **known name**; or a function or tuple whose name or at least one argument is a known name (numbers alone never qualify: `sleep(5)` stays code) | `k`, `-k`, `T_k`, `EC_0`, `OCV(SoC)`, `f(T_k)`, `N(mu, 9.25)`, `(A, B, C)` |
| C1 `single-letter` | `found_file` | one Latin letter | `t`, `Q` |
| C2 `bare-number` | `found_file` | a plain number `^[-+]?\d+(\.\d+)?$` | `0.5`, `2000` |
| C4 `greek` | `found_file` | a bare Greek name, lower or Capitalised | `lambda`, `Pi`, not `PI`; a tutorial's "`beta` release" stays quiet without a `math.md` |

C3 runs before the shape rules so a known symbol keeps today's
`symbol` kind and sentence (tests at `test_render_output_math.py:174,
182, 439` rely on it, including `found_file=False` with a mapping).

**Known names** are today's `_symbols_of(mapping)` (single letters and
Greek names in the LaTeX column) **plus**, by extending `_symbols_of`
itself in `_math.py`, the identifiers in the ASCII column (new) that look like a symbol: one letter, a capital letter in
the name (`SoC`, `EC`, `OCV`), or a Greek name. Lowercase words are
dropped. A key like `level + h * (pump_flow - demand) / area` would
otherwise make `` `level` `` and `` `demand` `` warn, and `mean` and
`time` already occur as code spans in these drafts. Citekey-shaped keys
contribute nothing.

### 2. `findings()` uses it

- `MathFinding`'s docstring enumerates the kinds; add `duplicate` and
  `unused-code`.
- A gap's message names its rule:
  `` `-1` looks like a quantity (signed-number) but has no row in math.md ``.
  C3 keeps the `symbol` kind with today's sentence; every other rule is
  kind `gap`. A span in the not-mathematics table is skipped before any
  rule runs.
- `_fence_gaps` applies **step B (with step A before its search rules)
  only**, line by line, with
  the 4-line and snake-case guards unchanged. No untagged fence in these
  drafts changes verdict.
- The `found_file` parameter already says whether the draft has a
  `math.md`, and it gates C1, C2 and C4.

### 3. The "not mathematics" table in `math.md`

A one-column table anywhere in the file:

```markdown
## Not mathematics

| Code in the draft |
| --- |
| `404` |
| `21.4` |
```

- `_math.not_math(draft) -> frozenset[str]` reads rows matching
  `^\|\s*`(?P<ascii>[^`]+)`\s*\|\s*$`. `_ROW_RE` needs two cells, so
  these rows never enter the mapping, and `load_mapping`,
  `registry/_terms.py` and `substitute` are untouched.
- `findings()` skips a span listed there (spans only; fences keep their
  own remedy).
- A listed span that appears nowhere in the draft is reported, kind
  `unused-code`: `` `404` is listed as not mathematics in math.md but
  appears nowhere in the draft ``. It is a separate kind from `orphan`,
  so `dossier`'s `_math_desync` (which selects `orphan`) does not treat a
  stale code row as evidence the mathematics moved.
- A span that is both mapped and listed: the mapping wins (it is
  substituted), and the finding is kind `duplicate` (below).

### 4. Duplicate rows

`_math.mapping_rows(draft) -> list[tuple[str, str]]` returns the rows in
file order. `load_mapping` becomes `dict(mapping_rows(draft))`, which is
behaviour-identical (the last row wins). A new
`_math_findings.duplicates(rows, not_math)` reports kind `duplicate`:

- a key with two or more **different** LaTeX values:
  `` `eps_k = …` has 2 rows in math.md with different LaTeX: `\epsilon_k …`, `\varepsilon_k …`; the last is rendered ``;
- a key both mapped and listed as not mathematics.

Identical repeated rows stay silent: the output does not change. It is a
warning, not a `MathMappingError`, as #1116 asks; a refusal would stop
renders that work today.

### 5. Files that can have no `math.md`

When `_math.mapping_path(input_path)` is `None` (a review report under
`content/review/`, anything outside `content/drafts/`),
`_checked_math_mapping` prints no `[math]` findings at all, because a row
cannot be added there. This includes a draft under a topic directory
that is a symlink out of the tree, for which `mapping_path` also answers
`None` (`_math.py:161`); that draft cannot have a readable `math.md`
either. `_math.check` still runs: an unresolved
`<!-- math -->` marker is certain, not heuristic. Nothing in
`chitragupta/review/` changes. With step A in place the report header
would be quiet anyway, but a report may quote draft spans, and those
belong to the draft's warnings, not the report's.

### 6. Wiring

`_checked_math_mapping` (in `_substitution.py`) reads the rows once,
prints `duplicates(...)` and then `findings(...)`, each as
`[math] <message>`. `findings()` gains a keyword `not_math` (default
empty) so `dossier._draft_fingerprint._math_desync`, which wants only
orphans, needs no change.

## Module sizes (C2: 250)

| Module | Now | After (est.) |
| --- | --- | --- |
| `_math.py` | 185 | ~200 (+`mapping_rows`, `not_math`, −`_MATH_SHAPED_RE`) |
| `_math_findings.py` | 100 | ~140 |
| `_math_shapes.py` | new | ~120, mostly the commented rule tables |

Import direction: `_math_shapes` and `_math_findings` import `_math`;
`_math` imports neither. `_math_shapes` imports nothing beyond `re` and
`_math`, and joins `_math.py` in the bare-python import-guard test
(`test_render_output_math.py` ~393).

## Tasks (test-first; each test red before its code)

All tests go in `tests/test_render_output_math.py` unless noted.

1. **Shapes, step B.** One parametrised test per rule, each with a
   positive span and a near-miss negative (`-m`, `Ctrl+C`, `PI`,
   `[DIGITAL MODEL]`). Include all six #1116 spans. Red: they are not
   gaps today. Build `_math_shapes.py` with the step B table, and move
   `_MATH_SHAPED_RE` there.
2. **Blanking, step A.** The #1115 spans and the corpus false positives
   (`?limit=`, `?since_timestamp=`, `GET /sensing/plant_1/moisture?limit=1`,
   `<unit>_<parameter>`, `2026-02-01`, `6.157.0`, the report-header
   command line) give no gap. `x = 02-01-a.md` still does. Red on the
   first group today.
3. **Context, step C.** `single-letter` and `bare-number` warn only with
   `has_mapping`. ASCII-side names: `EC_0` against a mapping holding
   `EC - EC_0`; `OCV(SoC)` and `SoC` against `V_t = OCV(SoC) - …`;
   `level` against `level + h * (pump_flow - demand) / area` stays
   silent. `-k`, `(A, B, C)`. `sleep(5)` and `N(118.5, 9.25)` stay
   silent with no known names. `dV/dSoC` warns (anchored before
   blanking). Existing tests at lines 174, 182 and 439 keep their kind.
4. **Wire into `findings()`** with rule names in messages, and keep every
   existing test green. Existing assertions on exact message text are
   updated in the same commit, and only for the added `(rule)`.
5. **Fences.** A 2-line untagged fence holding `x = A * x` warns (an
   underscore would trip the unchanged snake-case guard); a
   fence holding a `code/02-01-x/` path does not.
6. **Not-mathematics table**: parsing, suppression, `unused-code`,
   one-column rows absent from `load_mapping`, and `_math_desync`
   ignoring `unused-code`.
7. **Duplicates**: differing LaTeX warns, naming both values; identical
   rows are silent; mapped-and-listed warns; `load_mapping` still takes
   the last row.
8. **No `math.md` possible**: render a file under `config.REVIEW_DIR`
   whose text holds `` `h = 9` `` → no `[math]` line on stderr, while the
   same text under `DRAFTS_DIR` prints one. A `<!-- math -->` marker in a
   report still raises.
9. **End to end**: the issue's two reproductions, through
   `python -m chitragupta.draft render --format tex` (or the in-process
   `render`), assert the expected `[math]` lines.

## Documentation the change makes false (step 4 of the shipping cycle)

- `docs/WRITING-STANDARDS.md` §12 "What is checked": "Three heuristics"
  becomes the rule tables in short form, plus the not-mathematics table,
  duplicate rows, and "no `math.md` possible → no warnings". The "What no
  check sees" paragraph changes: `/` expressions with spaces and
  derivatives are now seen; spelled-out quantities still are not;
  operators between multi-letter names must be spaced (`EC-EC_0` is
  blanked as a hyphenated word, `EC - EC_0` is seen); a known false
  positive is SQL's `SELECT * FROM t`, whose remedy is the table.
- `docs/DOSSIER.md`: `math.md`'s row describes the optional second table,
  and that it is the only one-cell table `math.md` may hold (a mapping
  row with a forgotten LaTeX cell would read as a suppression).
- `.claude/skills-common/references/figures-tables-equations.md` §6: the
  remedy for a code false positive is a not-mathematics row.
- `docs/RENDERING-FLOW.md` line ~176, if its sentence enumerates kinds.
- Mirrors of edited skill references (`.agents/`, `.opencode/`) if the
  sync script generates them. Check with `grep` after editing.
- Sweep for the claim, not the file: `grep -rn "looks like a quantity\|Three heuristics\|math-shaped"`.

## Review

Fable reviewed this plan on 2026-11-05: signed off with changes. Its
four should-fix findings (C3 order and gate, the fence example, the
vacuous function-of-numbers case, anchored rules before blanking) and
nits 5, 8 and 9 are folded in above; nits 6 and 7 are documented as
known limits.

## Version

The not-mathematics table is new, backward-compatible input, which
makes this **MINOR** under DEVELOPER-AGENTS.md "Versioning and releases":
6.157.0 → 6.158.0. A MINOR tag also publishes to PyPI, so the fix
reaches `pip install` users.
