# Math typesetting convention: rollout

Status: **in progress.** Written 2026-08-24.

[docs/WRITING-STANDARDS.md §12](../docs/WRITING-STANDARDS.md#-12-mathematics)
now owns the rule -- every quantity is `$…$` / `$$…$$`, backticks mean
code. This file records why it was needed, what has already been
converted, and the drafts still carrying the old spelling.

## 🔍 What was wrong

A reader reported that some equations in the book's `.tex` chapters were
set as real math and others as ASCII typewriter text. The `.tex` files
are not hand-authored -- `book-assembler` generates them (`SKILL.md:182`,
`draft render --format tex --fragment`) -- so the split originated in the
Markdown sources, and pandoc preserved it faithfully:

| In the `.md` source | pandoc → `.tex` |
| --- | --- |
| `$$\n\frac{dW}{dt} = -\frac{W}{\tau}\n$$` | `\[ … \]`, real math |
| `` `k = 4` `` | `\texttt{k\ =\ 4}`, typewriter |

Nothing in `docs/`, `AGENTS.md` or any SKILL.md stated a math
convention, so this was unruled drift rather than a violated rule. It
was also not confined to one genre: `digital-twin-platforms.md` used
`$` 104 times while `digital-twin-life-cycle-considerations.md` used it
zero times and put the same kind of quantity in backticks.

The decisive measurement was **symbol clash** -- a symbol set in a
chapter's own display math *and* in a code span in the same chapter:

```text
04-just-enough-modeling      38    `k`x12 `g`x8 `W`x7 `m`x6
05-just-enough-simulation    51    `h`x32 `m`x13 `k`x3
07-should-you-trust-the-twin 44    `k`x24 `g`x20
12-platforms-and-composability 58  `a`x24 `r`x10 `F`x8 `p`x8
13-standards-and-open-source 46    `F`x16 `C`x15 `r`x10
                       TOTAL 253
```

Chapter 4 sets `\[ m(t) = m_0 - k\,t \]` and then writes `` `k = 4` ``.
Same `k`, two typefaces.

## ✅ Converted: the 15-chapter book

`content/drafts/books/digital-twins-for-software-engineers/`, **515 code
spans → inline math**, in three passes.

**Pass 1 (465 spans), whitelist-driven.** The whitelist was derived from
the documents themselves, not guessed: a span converted only if every
letter-token in it appears as a symbol in the book's own `$$` display
math, or if it was a pure numeric expression. That is why `` `k` ``
converted and `` `as_of` `` did not -- `as_of` appears in no display
math anywhere.

- **Document-derived symbols:** `B C F I N O W a d e f g h k m n p r t w`,
  plus `T_s` (from ch. 9), `W_0`, `m_0` and `\tau` (ch. 4's `\frac{W}{\tau}`).
- **Human-adjudicated, 4 symbols:** `H`, `b`, `c` and `T` are genuine
  symbols the book only ever wrote inline, so no display math vouches
  for them. Each was read in context before conversion -- e.g. ch. 5
  defines *simulated time* `$t$` and *wall-clock time* `` `T` `` in the
  same two-line box, which is the whole defect in miniature.
- **`k_day` / `k_night`** → `$k_\mathrm{day}$`, upright subscript.

**Passes 2 and 3 (50 spans), and why they were needed.** The whitelist
is built from *single-letter* display-math symbols, so it is structurally
blind to a multi-letter quantity. Ch. 1 was left self-contradictory:
`` `0.02 x 100 + 1.5 = 3.5` `` converted while `` `slope = 0.02` ``,
`` `offset = 1.5` `` and `` `t = slope * dose + offset` `` -- the same
three quantities in the same chapter -- did not. A second blind spot:
the path detector excluded any span containing `/`, which also excluded
every division (`1/64 = 0.015625`, `N(N-1)/2`).

- **Pass 2, 27 spans, hand-adjudicated:** multi-letter names
  (`$\mathrm{slope}$`, `$\mathrm{Assemble}(N)$`), and symbol expressions
  whose symbols were already `$…$` in the same chapter (`$C \times I > F$`,
  `$rB - F$`, `$a - p$`, `$k \times T_s$`).
- **Pass 3, 22 spans, division-bearing arithmetic:**
  `$0.05 \times 0.95 / (0.005)^{2} = 0.0475 / 0.000025 = 1{,}900$`,
  `$= \sqrt{1/0.022569} = 6.66$`,
  `$(12{,}000 + 3{,}000) / 10{,}000 = 1.5\ \text{years}$`.

**Not converted, correctly:** 410 `\texttt{}` remain -- field names,
endpoints, paths, JSON, SQL -- along with 415 citekeys. Of the 143 spans
still in the review bucket, the only two that are even math-*shaped* are
`quality = no_reading` and `if twin_name == ...`, both genuinely code.

**Verification.**

| Check | Before | After |
| --- | --- | --- |
| Math-shaped `\texttt{}` (multi-letter aware) | 64 | **0** |
| Single-letter symbol clash | 253 | **0** |
| Inline `\(…\)` in the book's `.tex` | 0 | 515 |
| `\texttt{}` total | 925 | 410 |
| Display `\[…\]` | 79 | 79 (untouched) |
| `pdflatex book.tex` | builds | builds, 0 errors |

`925 − 515 = 410` reconciles exactly, and 515 balanced `\(` is itself
evidence the `$` delimiters pair correctly -- pandoc could not emit an
odd count from unbalanced input.

**Use the multi-letter check, not the clash detector.** The clash
detector only matches single letters against display math, so "253 → 0"
proves no *single-letter display-math symbol* is set two ways. It does
not prove no *quantity* is -- ch. 1 passed it while still wrong. The
first row of the table is the check worth re-running.

The `.tex` were regenerated with `draft render`, then the two
post-render labels `\label{ch-NN}` and `\label{<unit-id>}` reapplied --
`book-assembler` adds those after pandoc (`SKILL.md:195-197`), so a plain
re-render drops them and every `\cref` in the book breaks. `book.md`
needed no change: it is a 30-line index of links, not inlined prose.

## 📋 Still carrying the old spelling

Neither is urgent; both are `draft-reviser` jobs, not a re-run of the
genre skill.

- `content/drafts/book-chapters/digital-twin-life-cycle-considerations/`
  -- 5 math spans in backticks, 0 display math, in both the base and
  `-corpus-revised` variants.
- The standalone drafts under `content/drafts/digital-twins-for-software-engineers/`
  are already clean: `book-chapter.md` uses `$$`, and the survey,
  tutorial and deep-research drafts contain no math at all.

## 🤔 Considered and rejected

**ASCII in `.md`, math in `.tex`, from one source.** Attractive, because
`--format md` never reaches pandoc so a rendered Markdown preview shows
`$k = 4$` literally. Three mechanisms exist and all three fail:

- Pandoc raw spans, `` `\(k = 4\)`{=latex} `` -- non-LaTeX writers
  *drop* raw LaTeX rather than falling back to ASCII, and the `--format
  md` path would leak the `{=latex}` attribute verbatim.
- A `math:` marker handled per output format, as [§10's figures](../docs/WRITING-STANDARDS.md#-10-figures)
  are (`render_output/_figures.py`). The figure precedent is line-based
  and inline math needs an inline marker, so the precedent does not
  carry -- and it means two spellings of every equation with nothing
  checking they agree.
- Promoting backtick spans to math at render time. Ruled out on
  evidence: of 1119 code spans in the book, `` `k` `` (math) and
  `` `as_of` `` (API field) are indistinguishable to a regex.

**Renumbering `§11` to make room.** `plans/b2-multi-source-synthesis.md:325`
already established *append, do not insert*, and `DEVELOPER.md:301`
cites `§11` by number. The math section is `§12`.

## 🧯 Recovery

`content/` is gitignored, so the conversion had no undo. The pre-change
`.md` and `.tex` are at `~/mathfix-backup-20260824/` -- outside
`content/`, so a later sweep of that tree cannot clobber the backup.
