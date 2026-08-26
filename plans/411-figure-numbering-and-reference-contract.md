# 🖼 Figure numbers, and prose that reads them

Status: **plan.** Written 2026-08-26, for issue 411.

A captioned figure's number is typed by a person today
(`\renewcommand{\thefigure}{N.M}`, hand-authored inside the figure file),
and nothing in a Markdown draft lets prose refer to a figure by number --
so a draft that mixes a renumbered figure with an auto-numbered one prints
a wrong sequence silently, and a hand-set number is wrong again the
moment the chapter is assembled into a book with different chapter
numbering. This is the fix, giving figures the same contract §13 gave
tables: a caption the author writes, a number nobody writes, and a
`draft style` finding for a figure no sentence explains.

**Written for** whoever implements it -- `chitragupta/render_output/`,
`chitragupta/style_check.py`, `chitragupta/review/_claims.py` and the
genre skills all move together, and the order matters.
**Assumed** you have read
[docs/RENDERING-FLOW.md](../docs/RENDERING-FLOW.md)'s figure and table
sections and [docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md)
§10 and §13, whose contract this one extends rather than replaces.
**Not covered here:** migrating any existing captioned figure -- there is
none. A grep of `content/` for `\begin{figure}` at plan-writing time
returns nothing, so this is purely forward-looking and costs no
migration.

## 🧭 Table of contents

- [The defect, as issue 411 states it](#-the-defect-as-issue-411-states-it)
- [What was verified before choosing](#-what-was-verified-before-choosing)
- [The contract](#-the-contract)
- [What the renderer does, per format](#-what-the-renderer-does-per-format)
- [The `.tex` fragment carve-out](#-the-tex-fragment-carve-out)
- [What reports a figure nobody explains](#-what-reports-a-figure-nobody-explains)
- [Where the review layer would start lying](#-where-the-review-layer-would-start-lying)
- [Rejected alternatives](#-rejected-alternatives)
- [What this deliberately leaves alone](#-what-this-deliberately-leaves-alone)
- [Build order](#-build-order)

## 📊 The defect, as issue 411 states it

Three gaps, all measured against the table contract rather than treated
as renderer defects:

1. `\renewcommand{\thefigure}{N.M}` is authored by hand, inside the
   figure file, beside a hand-written `\caption`/`\label`. The redefinition
   does not leak into later figures, but the `figure` counter keeps
   counting independently of it -- a document with one renumbered figure
   and one auto-numbered one prints "Figure 3.1" and then "Figure 2".
2. No Markdown draft has any way to refer to a figure. A grep for
   `\ref{fig` across every `SKILL.md` returns nothing, so prose writes
   "Figure 2" literally -- the exact drift #395 removed for tables --
   and reaching for `Figure~\ref{fig:x}` by hand hits the same `~`-escaping
   trap #410 found: pandoc's Markdown reader owns `~` and escapes it to
   `\textasciitilde{}`.
3. `chitragupta.TableUnreferenced` has no figure counterpart. §10 already
   accepts an uncaptioned figure by design, so only the *unreferenced*
   case -- a captioned figure no sentence points at -- is the gap.

## 🔬 What was verified before choosing

Run against this host's pandoc 3.1.11.1, not inferred, because the whole
design rests on one assumption #395 never had to test at this shape: a
*multi-line* raw block, not a single inline raw command.

| Question | Answer |
| --- | --- |
| Does a raw `\begin{figure}...\end{figure}` block -- `\input`, `\caption`, `\label` all included -- survive a bare `pandoc draft.md --standalone -o out.tex`, no reader flag? | **Yes.** Reproduced directly: the whole block reaches `out.tex` byte-identical, inside `\begin{document}`, with no escaping of any line in it. This is the same mechanism #395 measured for a single raw `\label{}` inside a caption line, now confirmed to hold for a five-line block too. |
| Does this pipeline's own `_pandoc_command` add a reader flag that could change that? | No -- confirmed by reading `chitragupta/render_output/__init__.py:203`: no `-f`/`--from` is passed for a Markdown draft, so pandoc guesses the reader from the extension exactly as the bare probe above does. |
| Are there existing captioned figures in `content/` that this change would need to migrate? | No. `grep -rl "begin{figure}" content/` returns nothing at plan-writing time. |
| Does the existing `fig:<name>` label convention already match the id this plan derives? | Yes -- `docs/TIKZ-STYLE.md`'s own worked example already writes `\label{fig:delivery-modes}` for a figure file named `delivery-modes.tex`, which is exactly "id = the marker's base name" with no new vocabulary. |

## 📐 The contract

**A Markdown draft writes the figure marker, then its caption directly
below -- no blank line between, the same adjacency §11's
`<!-- single-source: -->` and §13's table-caption-then-marker pair both
use:**

```markdown
<!-- figure: figures/delivery-modes -->
One reading path under three delivery modes.
```

Marker first, caption second -- the reverse of a table's caption-then-id
order, and deliberately so: a table's marker is bolted onto a caption
line pandoc already recognises, so it has to trail it; a figure's marker
*is* the figure, playing the role a table's rows play, and the caption
reads the same way a caption reads after a picture in a finished
document.

Prose points at it with an inline marker, exactly as a `tableref` does:

```markdown
<!-- figureref: delivery-modes --> shows the same request handled three ways.
```

**The id is derived, not written.** `<!-- figure: figures/<name> -->`
already names the figure's base name; the id is that name with no
`figures/` prefix and no extension (`delivery-modes` from
`figures/delivery-modes`). No new marker field, no second thing to keep
in sync with the file name.

**A figure with no caption line below it is unchanged.** §10's
uncaptioned case stays legal and stays exactly as it renders today -- a
bare `\input` or a bare ASCII fence, no float, no number, invisible to
`figureref` resolution (see "What reports a figure nobody explains").

**Numbers are counted in document order, among captioned figures only.**
An uncaptioned figure is not a `\begin{figure}` environment and does not
increment LaTeX's own counter, so this module's own count for `md`/`docx`/
`html` has to skip it too, for the two counts to agree -- the same
reasoning `_tables.tables()` numbers by position rather than by id.

## 🖨 What the renderer does, per format

Two independent passes, run in this order, both in
`chitragupta/render_output/_figures.py`:

**Pass 1 -- caption wrapping**, new, Markdown drafts only, run *before*
the existing `_with_figures_for`. Finds every `[marker, caption]` pair
(the marker's own regex is unchanged; the caption line is matched only
when adjacent, is not itself a marker, a heading, or blank) and replaces
the pair with a format-specific wrapper that leaves the **original marker
line untouched inside it** -- so pass 2 still finds and substitutes it
exactly as it does today:

| Output | The `[marker, caption]` pair becomes |
| --- | --- |
| `tex`, `latex`, `pdf` | `\begin{figure}`⏎`<marker, unchanged>`⏎`\caption{<caption>}`⏎`\label{fig:<id>}`⏎`\end{figure}` |
| `md`, `docx`, `html`, ... | `<marker, unchanged>`⏎`**Figure N:** <caption>` |
| A marker with no caption below | untouched |

**Pass 2 -- content substitution**, the existing `_with_figures_for`,
unchanged: replaces the (now possibly float-wrapped) marker with
`\input{figures/<name>.tex}` (LaTeX-bound) or the `.txt` contents in a
fence (everything else). Because pass 1 never touches the marker's own
text, pass 2's regex still matches it wherever pass 1 left it -- inside a
`\begin{figure}` block or bare in the draft.

The result for a LaTeX-bound render of the example above:

```latex
\begin{figure}
\input{figures/delivery-modes.tex}
\caption{One reading path under three delivery modes.}
\label{fig:delivery-modes}
\end{figure}
```

`figureref` resolution is a third, independent pass, mirroring
`_tables._reference_for`:

| Output | `<!-- figureref: <id> -->` becomes |
| --- | --- |
| `tex`, `latex`, `pdf` | `` `Figure~\ref{fig:<id>}`{=latex} `` -- the raw-attribute span, for the same `~`-escaping reason #410 and #395 both found |
| everything else | `Figure N` |

A `figureref` naming an id no *captioned* figure declares (including one
naming an uncaptioned figure -- see "The contract") is left exactly as
written; `warnings()` reports it, the same non-failing convention
`_tables.warnings()` and `_figure_warnings` already use.

Substitution order in the pipeline becomes: figure captions, figure
content, figure references, tables, mathematics -- the new steps slot in
beside the existing figure step rather than after it, since `_tables`'s
own caption numbering does not depend on anything figures do.

## 📄 The `.tex` fragment carve-out

`thesis-chapter-writer`'s `.tex` fragment is unchanged in shape: it still
hand-authors a real `\begin{figure}...\input{...}...\caption{}...\label{fig:<id>}...\end{figure}`
inline, exactly as it does today, and carries no `figure:`/`figureref`
marker for this contract to reach -- the same carve-out §13 gives tables
and §10 already gives this genre's inline TikZ. **The one change there is
one line removed**: stop writing `\renewcommand{\thefigure}{N.M}`. LaTeX's
own `figure` counter numbers the float, consistent with whatever chapter
numbering the user's own thesis uses -- the fragment is `\input` into a
document this pipeline never renders, so nothing here does the counting
for it, same as tables.

## ✅ What reports a figure nobody explains

`chitragupta/style_figures.py`, sibling to `style_tables.py`, wired into
`style_check.check()` the same way, ahead of `run_vale()`:

| Finding | What it catches |
| --- | --- |
| `chitragupta.FigureUnreferenced` | A captioned figure no sentence refers to -- the issue's stated gap |
| `chitragupta.FigureUnknownRef` | A `figureref` naming an id no captioned figure declares |
| `chitragupta.FigureDuplicateId` | Two captioned figures sharing an id -- a silently-wrong `\ref` risk in an assembled book, same as tables |
| `chitragupta.FigureMalformedId` | An id (the marker's base name) that is not kebab-case, so it cannot become a safe `\label` |
| `chitragupta.FigureRefOutsideSection` | The only reference to a figure sits in a different section than the figure |

**Deliberately no `FigureNoCaption` or `FigureNoId`.** Both have table
analogues and neither applies to figures: §10 already accepts an
uncaptioned figure as a design choice, not a defect, and a figure marker
always carries an id by construction (it names the file), so there is no
"marker with no id" state to report. Reporting either would contradict
§10's own accepted case.

A `.tex` fragment is out of scope for this module, the same as it is for
`style_tables.py` -- the marker vocabulary this checks for does not exist
there.

## ⚠ Where the review layer would start lying

`chitragupta/review/_claims.py` needs one addition, smaller than #395's
predicted -- it turned out to need *no* change at all for the caption
half, once measured.

- **A figure's caption is plain prose with no self-identifying prefix**
  (`"One reading path..."`, not `: ...` or `\caption{...}` the way a
  table's or a hand-written figure's caption is), so `CAPTION`'s
  per-line-prefix match cannot recognise it on its own. But `_blocks.spans`
  merges the marker and its adjacent caption into one block (no blank line
  between them, same as a table's caption+marker pair) -- and because the
  contract puts the marker *first*, `block[0]` is the marker line, which
  `_excluded`'s existing `COMMENT.match(first_line)` check already
  matches. The whole block, caption included, is excluded with no code
  change at all. Confirmed by writing the test before touching
  `_claims.py`: it passed against the unmodified module.
- **The inline `figureref` marker** needs the same treatment
  `INLINE_TABLE_REF` already gets: stripped and replaced with the word it
  stands for (`" Figure "`) before sentence-splitting, so a reference does
  not read as markup and does not split a sentence in two.
- **`review verbatim`** needs no change: a figure's caption is prose like
  any other, and a caption borrowed verbatim from a source is exactly the
  overlap that scan exists to catch.

## 🚫 Rejected alternatives

- **Move the caption into the figure file and just stop hand-typing
  `\thefigure`, leaving everything else alone.** The issue's own stated
  fallback, and the smaller diff -- no new marker, no change to
  `review/_claims.py`, no migration risk because there was never a
  caption in the draft to move. Not chosen because it leaves the other
  two gaps open: no `figureref` for Markdown prose to use, and no
  `FigureUnreferenced` finding, since without a caption *in the draft*
  there is nothing for a style check to say a sentence never explains.
  The user explicitly chose full parity with tables over this smaller
  fix.
- **Caption text inside the marker itself**
  (`<!-- figure: figures/x "One reading path..." -->`). Rejected for the
  same reason §13 rejects it for tables: a caption may cite, and
  `citation_gate.py` reads the draft's visible prose, not text buried in
  an HTML comment -- hiding it there would make the draft on disk
  misleading about what the rendered document says.
- **pandoc-crossref's `@fig:id` syntax.** Barred by this project's own
  gate exactly as `@tbl:id` is: `citation_gate.py`'s `_PANDOC_CITE_RE`
  reads a bare `@key` as a citekey, so `@fig:delivery-modes` would fail
  `python -m chitragupta.draft gate` as a fabricated reference.
- **A second id field in the marker**, so the id need not be derived from
  the base name. Issue 411 itself names this as the alternative to
  deriving; rejected because deriving costs no new vocabulary and the
  `fig:<name>` label convention already in `docs/TIKZ-STYLE.md`'s own
  example matches it exactly -- a second field would be a second thing to
  keep in sync with the file name, for no gain.

## 🧊 What this deliberately leaves alone

**No migration, because there is nothing to migrate.** Every real draft
in `content/drafts/` carries no captioned figure today (`grep -rl
"begin{figure}" content/` is empty), so nothing written before this
change needs revising -- unlike #395, which found a real production table
that had to keep working.

**Existing figure files that are already captioned by hand outside
`content/`** -- a scaffold under `assets/tikz/`, say -- are not this
plan's concern: `docs/TIKZ-STYLE.md` already says the float is "part of
*your* copy of a scaffold, not of the scaffold", so a scaffold file
carries no float to begin with.

## 🔨 Build order

Test-first at each step, per `DEVELOPER-AGENTS.md`:

1. `chitragupta/render_output/_figures.py` -- the `Figure` namedtuple,
   `figures()`, `references()`, the caption-wrapping pass, the
   `figureref`-resolution pass, `warnings()`. Extend
   `tests/test_render_output_figures.py`.
2. Wire into `render_output/__init__.py`: caption wrapping before the
   existing `_with_figures_for` call, `figureref` resolution alongside
   it, warnings before the Markdown-to-Markdown early return.
3. `chitragupta/style_figures.py` plus the `style_check.check()` wiring,
   ahead of `run_vale()` like the table findings.
   `tests/test_style_check_figures.py`.
4. `chitragupta/review/_claims.py`: the figure-marker clause in
   `_excluded`, and `INLINE_FIGURE_REF`, with the existing claim tests
   extended.
5. Prose: `WRITING-STANDARDS.md` §10 gets the caption/`figureref`
   contract (mirroring §13's shape), `RENDERING-FLOW.md`'s figure section
   gets a numbering table like the table one, `TIKZ-STYLE.md` drops the
   `\thefigure` instruction, `CLI.md`'s `draft style` findings list grows
   the five figure findings.
6. The skills: the five Markdown genres and `book-assembler` learn the
   caption line and the explain-the-figure rule; `thesis-chapter-writer`
   stops emitting `\thefigure`; `draft-reviser` learns that figure numbers
   renumber themselves and ids must not be reused, mirroring what it
   already knows about tables.
7. One real end-to-end render of a scratch draft carrying a captioned
   figure, to `md`, `tex`, `pdf` and `docx`, checked for the number in
   each.
