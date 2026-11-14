# 🔢 Mathematics

Status: **reference.** An element file of the
[writing standards](../WRITING-STANDARDS.md), listed in the core's index.

Assumes the core, §1–9 of [WRITING-STANDARDS.md](../WRITING-STANDARDS.md).
This file holds §12, under the number it had in the core, so a
citation reads `docs/writing-standards/mathematics.md` §12.
`chitragupta/style_equations.py` reports its numbered-equation part as
`draft style` findings, and `render` reports its `[math]` warnings.

## 🔢 12. Mathematics

**A quantity is never left as a bare code span. Backticks mean code, and
only code.** There are two ways to honour that, and a Markdown draft may
use either, but only one of them per quantity, and consistently.

| | In the draft | Where the LaTeX lives |
| --- | --- | --- |
| **Mapped** (preferred for a new draft) | `` `k = 4` ``, ASCII | the dossier's `math.md` |
| **Inline** | `$k = 4$` / `$$…$$` | the draft itself |

A `.tex` draft (`thesis-chapter-writer`'s) writes `\(…\)` and `\[…\]`
directly and has no third option; the rest of this section still applies
to it.

The failure is invisible in the draft and appears only downstream.
Pandoc's Markdown reader turns a code span into `\texttt{}` and escapes
its spaces, so an unhandled `` `k = 4` `` becomes `\texttt{k\ =\ 4}` in
the rendered LaTeX (upright, typewriter, with `=` set as ordinary text),
while a real equation two paragraphs earlier becomes `\[…\]`. Both look
plausible in the Markdown source. Only the pdf shows that the same
symbol has been set two ways.

### 🗺 The mapped form, and why it is preferred

`$k = 4$` fixes the pdf and costs the Markdown. `--format md` never
reaches pandoc ([RENDERING-FLOW.md](../RENDERING-FLOW.md)), so those
delimiters land verbatim in `content/rendered/`. That is fine where the
Markdown is a step towards a pdf, and wrong where somebody reads it.

The mapped form keeps the draft ASCII and puts the LaTeX in the
dossier's `math.md` ([DOSSIER.md](../DOSSIER.md)):

```markdown
| ASCII in the draft | LaTeX |
| --- | --- |
| `k = 4`          | `k = 4` |
| `tau`            | `\tau` |
| `dW/dt = -W/tau` | `\frac{dW}{dt} = -\frac{W}{\tau}` |
```

`render` substitutes those into a temp copy for every format that reaches
pandoc, so `tex`, `pdf` and the rest get real mathematics while
`--format md` is a byte-perfect no-op. **The key is the span already in
the draft**, so nothing new is invented and nothing is guessed: a span
with a row is a quantity because the mapping says so, and `as_of` stays
code because it has no row.

A **displayed** equation is an untagged fence with a `<!-- math -->`
marker on the line above:

````markdown
<!-- math -->
```
dW/dt = -W/tau
```
````

The marker, not a ```` ```math ```` tag, for two reasons: GitHub and
GitLab typeset a `math`-tagged fence as LaTeX, so ASCII inside one is
rendered wrongly there; and every other fence in a draft holds code, so
something has to say which is which. It is the same device as
[§10's figure marker](figures.md#-10-figures), for the same reason: inert to
pdflatex, dropped by pandoc, meaningful only to this pipeline.

**A marker with no row is a hard error, not a warning.** `render` exits
non-zero, because a marker is you stating that a displayed equation is
here, and rendering it as verbatim text is the defect this section exists to
prevent. A missing `math.md` for a draft that has markers
usually means the draft was renamed and its dossier did not follow: the
two are tied by path alone and there is no `dossier rename`.

### 📐 The rule in practice

Written below in the inline spelling; in the mapped form the same rules
govern the mapping's LaTeX column, which is the only place LaTeX appears.

- **A symbol is math wherever it appears.** If `\[ m(t) = m_0 - k\,t \]`
  defines `k`, then every later mention of it is a quantity too: `$k$`,
  or `` `k` `` with a row. What is never right is a bare `` `k` `` with
  no row, and that is the shape a check cannot see from punctuation
  alone: `render` closes the world instead, flagging any span equal to a
  symbol your own mapped equations already use.
- **One form per draft.** Do not mix `$k$` in one section with a mapped
  `` `k` `` in another; a reader diffing two sections cannot tell whether
  the difference is deliberate.
- **Arithmetic is math too.** `$12 \times 2 \times 365 = 8{,}760$`, not
  `` `12 x 2 x 365 = 8,760` ``. ASCII `x` and `*` are not multiplication
  signs, and a thousands comma needs `{,}` or LaTeX sets it as a
  punctuation comma with the wrong spacing after it.
- **An equation is never a fenced code block.** A fence means code
  exactly as backticks do, and pandoc sets it as `\begin{verbatim}`:
  upright, monospace, `x` still a letter. A displayed equation is the
  marker plus fence above, or `$$…$$`; a *symbol legend* is a list, with
  each symbol set as math like every other mention of it. **A fence
  inside a blockquote is still a fence**. The case that prompted this
  rule was one relation set three ways in one chapter, and the wrong one
  was a fence inside a blockquote.
- **A matrix with two or more columns is displayed, not set inline.** TeX
  cannot break a line inside `\begin{bmatrix}`, so an inline matrix is
  one box the paragraph has to fit around, and two in a sentence leave
  it nowhere to break. Write the marker and fence above, with both
  matrices on one line if the sentence names two. Set inline,
  `F = [1, 0; 0, 0.7]` and `G = [1.0e-4, 0; 0, 3.0e-4]` ran 58pt into
  the margin of this repository's own book. A short column
  vector such as `x = [1.70; 48.0]` is narrow enough to stay inline.
- **A text subscript is upright.** `$k_\mathrm{day}$`, not `$k_{day}$`;
  the latter sets *d*, *a*, *y* as three italic variables multiplied
  together.
- **Backticks keep everything they were always for**: field names
  (`as_of`, `event_time`), endpoints, filenames, literal values,
  identifiers. A parameter named in an API *and* used in an equation is
  the ambiguous case; pick by which role the sentence is
  playing, and be consistent within the section.
- **Dates, versions and timestamps are not math.** `2026-02-01` in math
  mode sets its hyphens as minus signs.
- **A literal dollar sign must be escaped** (`\$`) once a draft uses
  `$…$`, or it opens math mode and swallows the rest of the paragraph.

### ⚖ Which form to choose

**A new draft should use the mapped form**, unless nobody will ever read
its `.md`. Both forms are supported: a draft written with `$…$` renders
as written, and `_math.py` only ever touches a span that has a row.

Pick the inline form when the draft is a step on the way to a pdf and
the equation count is small: one `$k$` is cheaper than a dossier file.
Pick the mapped form when the Markdown is read, when there are enough
equations that a table earns its keep, or when the ASCII should read
naturally: `` `t = tau * ln(2)` `` maps to `t = \tau \ln 2`, so the
source stays legible while the LaTeX stays typographically right.

### 🔍 What is checked, and what you still have to look for

**Two certain things stop a render** (`render` exits non-zero): a
`<!-- math -->` marker with no row to resolve it, and a marker with no
mapping file at all. Both mean the pdf would carry verbatim text where
you said an equation goes.

**Everything else only warns**, because a wrong guess must not stop a
render. A span with no row is a `[math]` gap when a named rule calls it
a quantity, and the warning names the rule
(`` `-1` looks like a quantity (signed-number) ``), so a false alarm
points at what fired. In order:

1. **Your own symbols.** A span that is, or is built from, a name your
   `math.md` already uses: `k`, `-k`, `T_k`, `EC_0`, `OCV(SoC)`,
   `(A, B, C)`. The names come from the LaTeX column (single letters,
   Greek control words) and from the ASCII column when they look like a
   symbol: one letter, a capital in it (`SoC`), or a Greek name.
   Lowercase words such as `level` never count. Single symbols were the
   *dominant* shape when this was first measured, roughly 296 of 515 in
   one book, and no operator rule can see them.
2. **Shape, anywhere.** A relation (`h = 9`), arithmetic between digits
   (`3 - 1`), a signed number (`-0.074`), a bracketed list of numbers
   (`[1 0]`) or a `;` matrix, `*` or `^` between operands
   (`A * P_est * A^T`), a spaced `+ - /` (`t + h`), a derivative
   (`dT/dt`), a conditional (`P(A | B)`), a subscripted Greek name
   (`sigma_2`), an index step (`x_{k+1}`), scientific notation
   (`1e-12`), or a list of numbers (`0, 3`). Before the rules that look
   *inside* a span, tokens that are plainly paths, file names, URL
   queries, `<placeholders>`, dates or versions are set aside, so
   `` `code/02-01-x/` `` and a command line naming `02-01-s.md` are not
   read as subtraction.
3. **Only in a draft with a `math.md`.** A single letter, a bare number
   (`0.5`) and a bare Greek name (`lambda`, `Pi`). These are as often
   code (`404`) as mathematics, so they count only for an author who
   declared mapped mathematics.

When one of these is code, say so once, in a one-column table anywhere
in the same `math.md`:

```markdown
## Not mathematics

| Code in the draft |
| --- |
| `404` |
```

A listed span is never a gap, and a listed span the draft no longer
contains is reported, as the orphan of a mapping row is. Two rows with
the same ASCII and different LaTeX are reported too (the last one is
what renders), and so is a span both mapped and listed.

An untagged fence that looks like a displayed equation nobody marked is
the last warning, judged line by line on shape alone.

A file that can have no `math.md`, such as a review report or anything
outside `content/drafts/`, gets none of these warnings, since each asks
for a row nobody can add. A `<!-- math -->` marker in one still fails.

The fence warning names both remedies, because a bare fence leaves the
question open in both directions: mark it if it is an equation, tag it
if it is code. It fires on a fence of **at most four lines** matching a
shape rule and no underscore identifier. `as_of` and `predicted_next`
are code, and length is what separates an equation from the other thing
a bare fence holds, an [§10 figure](figures.md#-10-figures), whose box borders are
not math-shaped but whose `->` arrows are. Measured over every untagged
fence in this repository's own drafts, the genuine equations run one to
four lines and the shortest false positive is a seven-line pseudocode
listing.

**Still not gated, deliberately.** `python -m chitragupta.draft gate`
means exactly one thing (a fabricated citekey fails), and
[docs/CODE-STANDARDS.md](../CODE-STANDARDS.md) keeps it that way. `render`
refusing is a different thing from the gate, and refuses only what is
certain.

**What no check sees.** A quantity spelled out (`slope`, `offset`,
`Assemble(N)`) reads like an identifier, so unless it has a row it
looks like ordinary code to everything above, and so does a name such
as `SoC` that no other row of the draft's `math.md` mentions. Operators
between multi-letter names must be spaced to be seen: `EC - EC_0` is a
gap, `EC-EC_0` is set aside as a hyphenated word. A draft using the
*inline* form has no mapping to close the world against, so it gets the
shape rules only. The known false alarm the other way is SQL's
`SELECT * FROM t`, whose remedy is the table above.
`plans/math-typesetting-convention.md` records what the gaps cost this
repository's own book, and `plans/1115-1116-math-shape-rules.md` how the
rules were measured.

An inline matrix wide enough to overflow is not checked either. Whether
it fits depends on the math font as much as on the matrix: the hint
in that book set without overflow under Computer Modern and ran 58pt into
the margin under STIX Two Math. Flagging every inline matrix instead would
have been mostly noise: the same book has seven others, and none of them
overflows. The rule above is the guard, and it is stricter than the
overflow on purpose: the appendix's inline `A = [2, 1; 0, 3]` fits today
and breaks the rule, because a different font or a narrower page is all
it takes to push it past the margin.

A long aligned array in an *unmarked* fence is past the four-line bar and
goes unreported too, deliberately, since that is the shape whose marker
is worth writing by hand. And nothing here reads a rendered `.tex`: a
post-render grep for math-shaped `\texttt{}` is what reported this book
clean while a `\begin{verbatim}` equation sat in it, because a fence
never becomes a `\texttt{}`.

### 📖 Symbols: what each mapped symbol means

The mapping says how a symbol is set; `math.md`'s `## Symbols` says
what it means, and since #1143 it is the only place a symbol's meaning
is written. The glossary keeps terms, never symbols, and a symbol list
in `scope.md`'s House style is read by nothing.

```markdown
## Symbols

| Symbol | Meaning |
| --- | --- |
| `m_t`  | **Target moisture** |
| `m_lo` | **Moisture thresholds**, lower |
| `T_c`  | see 02-plant-demonstrator |
| `e_q`  | quantisation error |
```

- **A bold term is a link** to the glossary entry that defines it, so
  the definition is written once. In a book it may name a term any
  accepted unit defines. Text after a comma is a note, telling two
  symbols of one term apart.
- **`see <unit>` reuses another unit's row** for the same symbol, which
  is how a book's chapters share notation. The other unit must have a
  row that is a link or words (never another pointer), and the two
  units must map the symbol to the same LaTeX.
- **Anything else is the meaning in words.** Write a `|` inside it as
  `\|`.

The table runs from its heading to the next `##` heading, so it may come before
or after the "Not mathematics" table, and nothing under it is read as a
mapping row.

**Every bare symbol the mapping table holds needs a row**: a name of
letters and digits with `_` subscripts, such as `m`, `T_oil` or
`x_hat`. An expression, `T_c = 6`, `h^2` or a function application such
as `r(t)`, may have a row and needs none. The symbol's LaTeX stays in
the mapping table, so a meaning with no mapping row cannot be typeset.
`render` reports both, among its `[math]` warnings: a mapped symbol with
no meaning (one summary line for a `math.md` with no `## Symbols` at
all), a meaning with no mapping row, and a row that is empty, half bold
or repeated. A book's `registry check` adds the cross-unit half: a link
no glossary defines, a pointer that does not land, a symbol naming two
things or set two ways, and a glossary span that is mathematics with no
mapping row in its own unit, which would print as code.

**Glossary spans use rows too.** A definition such as "the reciprocal of
the sampling interval, `1 / T_s`" is typeset through the unit's own
mapping, so `1 / T_s` needs a row even when the draft never writes it,
and that row is not an orphan. A bare symbol is also used when it is a
whole token inside a mapped span or block (`T_r` inside `T_r = 10`), so
a symbol only ever written inside formulas can have the row its meaning
needs. Only *mapped* spans count: `range(n)` keeps no `n` row alive.

### 🔢 A number for a chosen few, not for every displayed equation

A table or a figure gets a number by existing; a displayed equation
does not. Numbering every step of a derivation is noise, so the choice
is the author's. Unlike everything else `render` checks in this
section, **nothing here can decide which equations deserve one**; the
list below is guidance for making that call.

Number an equation when:

- it is **standalone**: not one step among several leading somewhere
  else;
- it is the **final result of a derivation or a chain of logically
  continuous equations**: the steps that lead to it are not numbered,
  only the one that was proved;
- it is **reused by a later equation** (substituted into it, referred
  back to), regardless of the two rules above.

Every equation numbered by any of the three rules above must then be
**referenced and explained in the prose**. This is the one part of the
decision a machine can check: `chitragupta.EquationUnreferenced` reports a
numbered equation no sentence points at, the same way
`chitragupta.TableUnreferenced` does for §13. That a sentence *refers to*
a numbered equation is decidable; that the sentence *explains* it is not,
same as a table's or a figure's row in §9's table below.

An equation opts into a number with `<!-- equation: id -->` directly
above the `<!-- math -->` marker this section already uses:

````markdown
<!-- equation: energy -->
<!-- math -->
```
E = m * c^2
```
````

and prose reads it with `<!-- equationref: id -->`, mirroring §10's
`figureref` and §13's `tableref`:

```markdown
Substituting <!-- equationref: energy --> into the momentum relation
gives the result used throughout this section.
```

**Ids are kebab-case and unique within a draft**, the same rule §10 and
§13 state for a figure or table id. **Numbers are never written by an
author**; they are assigned by document order of `equation:` markers, the same
reasoning §13 gives for a table: document order is LaTeX's own counting
order, so the number this pipeline writes for `md`/`docx` and the number
LaTeX assigns for `pdf` point at the same equation. Unlike a table's
caption, an equation carries no number in the *draft* on either path,
only in what each format renders to.

**A marked equation gets a number in every rendered format, `md`
included**, matching the table/figure precedent above rather than this
section's own "the `md` path is a no-op" rule. That rule still holds for
an equation's *content*: the ASCII inside a marked fence is exactly as
untouched on the `md` path as an unmarked one always was. It does not
hold for the *number*: a marked equation gains a `**Equation N:**` label
there, the same way a table already gains `**Table N:**`. This is a
deliberate, narrow exception: content substitution is still gated on a
real `math.md` mapping; equation numbering is not, and runs
unconditionally the way a table's or figure's numbering already does.

An unmarked `<!-- math -->` block (a derivation step, or any equation
the author chose not to number) is untouched by every check in this
subsection. There is no finding for "this equation should have been
numbered and was not": that would require the tool to tell a standalone
result from an intermediate step, which nothing here can do.

### ✍ Prose around the maths

This section says how a symbol is set; the sentences around it follow
`.claude/skills-common/references/mathematical-prose.md`, which both
chapter skills read on every run. In short: define each symbol in its own
sentence with its unit and a role word (in a Markdown draft, one that
agrees with its `## Symbols` row), repeat the role word after a gap, give
one letter one meaning, write the "then", state a derivation's claim
first and what it showed last, keep the argument to one paragraph per
step, and name the condition checked before applying a result. None of it
is checked by a tool.
