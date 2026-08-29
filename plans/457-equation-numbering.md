# 🔢 Equation numbers, and prose that reads them

Status: **plan.** Written 2026-08-29, for issue 457.

A draft's displayed equations render with no number today -- `_math.py`
turns a marked `<!-- math -->` block into bare `$$...$$`/`\[...\]`, with
no id, no counter, and no cross-reference syntax at all. Figures (#411)
and tables (#395) each already have this contract; this is the same
contract for equations, plus the one thing tables/figures did not need:
deciding *which* equations get a number in the first place, since that
decision is an authoring judgement no check can make.

**Written for** whoever implements it -- `chitragupta/render_output/`,
`chitragupta/style_check.py`, `chitragupta/review/_claims.py` and the
genre skills all move together, mirroring plan 395's own list.
**Assumed** you have read [docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md)
§12 (mathematics) and §13 (tables), and
[plans/395-table-numbering-and-prose-alignment.md](395-table-numbering-and-prose-alignment.md),
whose contract this imitates throughout. **Not covered here:** retrofitting
existing drafts, which is a `draft-reviser` task and not this repository's
to do (same carve-out plan 395 makes).

## 🧭 Table of contents

- [The defect, measured](#-the-defect-measured)
- [Which equations get a number is not decidable](#-which-equations-get-a-number-is-not-decidable)
- [The contract](#-the-contract)
- [What the renderer does, per format](#-what-the-renderer-does-per-format)
- [The md-path exception to §12's no-op rule](#-the-md-path-exception-to-12s-no-op-rule)
- [What reports an equation nobody explains](#-what-reports-an-equation-nobody-explains)
- [One shared module, not three copies](#-one-shared-module-not-three-copies)
- [Where the review layer would start lying](#-where-the-review-layer-would-start-lying)
- [Rejected alternatives](#-rejected-alternatives)
- [What this deliberately leaves alone](#-what-this-deliberately-leaves-alone)
- [Build order](#-build-order)

## 📊 The defect, measured

`chitragupta/render_output/_math.py`'s `substitute()` turns a `<!-- math -->`
marker plus fence into `$$\n{latex}\n$$`, full stop -- no id, no label, no
counter. Pandoc's own writers give that block no number in any format:
LaTeX sets `\[...\]` (unnumbered display math, not an `equation`
environment), and md/docx/html have no counter to defer to either.
Compare tables and figures, both of which get a real `\label{}` on the
LaTeX-bound path and a hand-written number everywhere else. Equations are
the one displayed element left with no way to say "equation 3" anywhere,
in any format.

## 🤔 Which equations get a number is not decidable

Unlike a table or a figure -- every one of which earns a number simply by
existing -- not every displayed equation should be numbered. A derivation
with several intermediate steps conventionally numbers only the result;
numbering every step is noise. The rule this plan encodes as *authoring
guidance*, not a check:

- A **standalone** equation -- one that is not part of a longer
  derivation -- is numbered.
- In a **derivation or chain of logically continuous equations**, only
  the final, proved result may be numbered; the steps that lead to it are
  not.
- Any equation that is **reused by a later equation** (substituted into
  it, referred back to) is numbered, regardless of the rule above.
- Every numbered equation **must be referenced and explained in the
  prose** -- this one, and only this one, is mechanically checked.

Nothing in `_math.py` or the new modules below can tell a derivation step
from a standalone result; that is exactly why the marker is *opt-in*
rather than automatic. The four rules above become a new subsection of
§12, in the same voice as the rest of that document, not a checklist a
program executes.

## 📐 The contract

An equation opts into numbering with `<!-- equation: id -->` directly
above the existing `<!-- math -->` marker -- the same adjacency §11's
`<!-- single-source: -->`, §13's table caption/marker pair, and #411's
figure marker/caption pair all use:

```markdown
<!-- equation: energy-balance -->
<!-- math -->
```
E = m * c^2
```
```

An unmarked `<!-- math -->` block is untouched by every module this plan
adds -- this is the mechanism that leaves a derivation step unnumbered.
Prose reads a numbered equation with an inline marker, mirroring
`tableref`/`figureref`:

```markdown
Substituting <!-- equationref: energy-balance --> into the momentum
relation gives the result used throughout §4.
```

**Ids are kebab-case and unique within a draft**, the same rule and the
same regex tables and figures already use. **Numbers are never written
by an author** -- assigned by document order of `equation:` markers, the
same reasoning plan 395 gives for tables: document order is LaTeX's own
counting order, so the number this pipeline writes for md/docx and the
number LaTeX assigns for pdf point at the same equation.

## 🖨 What the renderer does, per format

A new `chitragupta/render_output/_equation_captions.py`, beside
`_tables.py`/`_figure_captions.py`. Two things make this module's timing
different from either of those, both because it wraps *content* `_math.py`
substitutes rather than a caption that sits beside untouched content:

| Draft | Output | An `equation:`-marked block becomes | `equationref` becomes |
| --- | --- | --- | --- |
| `.md` | `tex`, `latex`, `pdf`, `docx`, `html` | `\begin{equation}\n{latex}\n\label{eq:<id>}\n\end{equation}` (LaTeX-bound: LaTeX's own counter numbers it) or `**Equation N:**` on the line above the kept `$$...$$` (docx/html: pandoc numbers nothing outside LaTeX, so the number is written) | `` `Equation~\ref{eq:<id>}`{=latex} `` (LaTeX-bound) or `Equation N` (docx/html) |
| `.md` | `md` (never reaches pandoc) | `**Equation N:**` on the line above the **untouched** `<!-- math -->` marker and fence -- see below for why the content stays ASCII | `Equation N` |
| `.tex` | any | untouched | untouched |

Every format needs `_equation_captions.py` to run, unlike `_math.py`'s
single "does this reach pandoc?" predicate -- see the next section for
why numbering runs on the `md` path where `_math.py`'s own substitution
does not.

**Timing in `_substitution.py`'s composition chain.** The declared-equation
list (id, number, line) is computed once, off the pristine draft text,
before any substitution runs -- the same reasoning `_declared_figures` is
computed once and threaded through both figure passes. The *content*
substitution has to run **after** `_math.substitute`, not before: on
every format except `md`, `_math.check()` has already guaranteed a marked
block resolves to `$$...$$` by the time `_equation_captions.substitute`
runs (`_checked_math_mapping` calls `_math.check`, which raises before
`_substituted` is ever reached, on every path that is not the `md` early
return) -- so the module has exactly two shapes to recognise, keyed on
whether the block is still `<!-- math -->`+fence (only possible on `md`,
where `math_mapping` is `{}`) or already `$$...$$` (every other format).
`equationref` resolution runs in the same pass, against the precomputed
id→number map, the same way `_tables.substitute` resolves `tableref` in
the same call that numbers captions.

Warnings (an orphaned `equation:` marker with no math block after it, a
duplicate id, an unresolvable `equationref`) print with an `[equation]`
prefix on stderr, beside `[figure]`, `[table]` and `[math]`, before
`render()`'s Markdown-to-Markdown early return -- the same placement
`_draft_warnings` already gives the other three.

## 🚧 The md-path exception to §12's no-op rule

§12 currently states a blanket promise: rendering a Markdown draft to
Markdown leaves its mathematics untouched, because `render()` passes
`math_mapping={}` on that path and `_math.substitute(text, {})` is
therefore a no-op. That promise still holds for a block's *content* --
the ASCII inside an `equation:`-marked fence is exactly as byte-identical
on the `md` path as an unmarked one always was. It stops holding for
*numbering*: a marked equation gains a `**Equation N:**` label on every
format, `md` included, the same way a table already gains
`**Table N:**` there.

This is a deliberate, scoped exception, not an oversight, and §12 is
rewritten to say both halves explicitly: content substitution stays
gated on a real mapping; the equation-numbering pass introduced here is
not, and runs unconditionally like `_tables.substitute`/
`substitute_captions` already do.

## ✅ What reports an equation nobody explains

`python -m chitragupta.draft style` grows equation findings, in a new
`chitragupta/style_equations.py` reached from `style_check.check()`:

| Finding | What it catches |
| --- | --- |
| `chitragupta.EquationOrphanMarker` | An `equation:` marker with no `<!-- math -->` block directly below it, so nothing numbers it |
| `chitragupta.EquationDuplicateId` | Two equations claiming one id |
| `chitragupta.EquationMalformedId` | An id that is not kebab-case |
| `chitragupta.EquationUnreferenced` | A numbered equation no sentence points at |
| `chitragupta.EquationUnknownRef` | An `equationref` naming an id no equation declares |
| `chitragupta.EquationRefOutsideSection` | The only reference to an equation sits in a different section |

No `EquationNoCaption`/`EquationNoId` companion: an equation has no
caption text at all (§12's equations are never described inline the way
a table or figure caption describes them), and its id is only ever
declared by the marker itself, so there is no "described but not
declared" state to detect -- the same reasoning `style_figures.py`
already gives for skipping `FigureNoId`.

These are **soft, advisory findings**, not wired into `_math.check()`'s
existing hard `MathMappingError` gate. That gate is about a block being
unrenderable as mathematics at all; an unreferenced or duplicate-id
equation still renders correctly; it is a prose-alignment defect, exactly
the category `TableUnreferenced`/`FigureUnreferenced` already sit in.

`chitragupta.EquationUnreferenced` and `EquationRefOutsideSection` are
the prose-alignment half, and, as with tables and figures, that a
sentence *points at* an equation is decidable and *whether it explains*
the equation is not -- §9 gets a new row saying exactly that, matching
the table/figure rows already there. **Whether an equation should have
been marked for numbering at all -- standalone, final-of-derivation,
reused -- is not decidable either**, and unlike the reference question
there is no mechanical proxy for it: this is stated plainly in §12's new
subsection so nobody expects the tool to catch an unmarked equation that
should have been marked.

## 🧩 One shared module, not three copies

`style_tables.py` and `style_figures.py` already duplicate
`_finding`/`_section_starts`/`_section_of`/`_id_problems`/
`_reference_problems` almost verbatim -- two call sites, tolerated as
coincidence. A third (`style_equations.py`) crosses
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md)'s stated line:
"Two similar blocks are a coincidence; three are a pattern." A new
`chitragupta/style_elements.py` holds the genuinely identical parts --
id-shape/duplicate-id checking, section-tracking, and the
unreferenced/unknown-ref/ref-outside-section logic, parameterised over a
`kind`'s rule names, its `references()` function and its
`WRITING-STANDARDS.md` anchor.

**What does not move.** Each kind's own "is this declared at all"
detection stays in its own file: a table's is a pipe-table/caption-line
scan with a `no-id` vs. `no-caption` split; a figure's is a
marker-then-caption pairing gap; an equation's is a marker-then-fence
pairing gap. The three are only superficially alike -- each reads a
different marker shape -- and forcing them into one function would be
the wrong abstraction, the failure mode
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md) itself warns
"needless repetition" against overcorrecting into. `style_tables.py` and
`style_figures.py` therefore keep their own file, their own tests, and
their own `findings()` entry point, now calling into `style_elements.py`
for the parts they no longer need their own copy of -- a smaller, safer
diff than deleting and rewriting two already-tested modules, and the
same consolidation outcome: the shared logic is written once.

## ⚠ Where the review layer would start lying

Plan 395 found three places a new caption-like text form changes what
the review layer sees; equations hit the same two of them (verbatim is
unaffected, per that plan's own note):

- **`chitragupta/review/_claims.py`'s `CAPTION`** recognises a `Table 2:`/
  `Figure 1.` lead-in but not an `Equation 3:` one. Without a new
  alternative in that regex, `python -m chitragupta.review uncited` would
  report every equation's number label as a sentence carrying no
  citation -- a false finding per numbered equation. `CAPTION`'s
  alternation grows `equation` beside `figure|table|listing`.
- **The inline `equationref` marker** lands mid-sentence, same as
  `tableref`/`figureref`. `_claims.py` needs an `INLINE_EQUATION_REF`
  constant and a third `.sub()` in `_body()`'s substitution chain, or a
  quoted sentence in an uncited-prose finding would carry raw pipeline
  markup instead of the word it stands for.

## 🚫 Rejected alternatives

- **A full review aid**, checking figures/tables/equations together.
  Considered first, at the requester's suggestion, specifically to answer
  "can one aid replace three small checks?" Two objections, not one:
  cost (registering a new key in `review.AIDS` touches roughly fifteen
  places -- docs, diagrams, four enumerating test modules -- a genuinely
  smaller cost for one unified aid than three, but not zero) and category
  (a review aid in this codebase reads the corpus or needs machinery
  beyond the draft's own text -- `citation_provenance`, `coverage`,
  `verbatim`, `quotation`, and `figure_layout`'s pdflatex-measured TikZ
  geometry all do; a reference-in-prose check reads only the draft
  against WRITING-STANDARDS.md, which is definitionally `draft style`'s
  job, per plan 395's own rejection of this same alternative for tables
  alone). Moving `TableUnreferenced`/`FigureUnreferenced` into an aid
  would also make them the *first* aid-sourced finding class classified
  `unattended=True` -- every other aid's findings are surfaced to a human
  today -- reopening a policy question #421 already settled for the
  `prose` class, for no benefit this plan needs.
- **Automatic equation numbering with no marker.** Would number every
  displayed equation, including every derivation step -- exactly the
  noise "which equations get a number is not decidable" argues against.
  There is no heuristic that tells a standalone result from an
  intermediate step; asking the author to opt in is the only honest
  answer.
- **Baking the equation's `$$...$$` delimiters into the numbered form for
  every format**, rather than switching to `\begin{equation}` on the
  LaTeX-bound path. Tried against pandoc 3.1.11.1: `$$...$$` inside a raw
  LaTeX span still sets as unnumbered `\[...\]`; only a real `equation`
  environment gets LaTeX's own counter, mirroring exactly why
  `_figure_captions.py` emits a real `\begin{figure}` rather than trying
  to number a bare `\input`.
- **A `pandoc-crossref`-style `@eq:id` spelling.** Barred for the same
  reason plan 395 rejects it for tables: `citation_gate.py`'s bare-`@key`
  pattern would read `@eq:id` as the citekey `eq` and fail
  `python -m chitragupta.draft gate` as a fabricated reference.

## 🧊 What this deliberately leaves alone

**Existing drafts are not migrated.** Every equation in every draft
predates this contract and stays exactly as it renders today -- unmarked,
unnumbered. `draft-reviser` is the tool for adding a marker to a draft
that wants one; this repository's own drafts are not rewritten by this
PR, the same carve-out plan 395 makes for tables.

**The `.tex` fragment carve-out is unchanged.** `thesis-chapter-writer`
writes `\[...\]`/`\(...\)` directly today and may write a real
`\begin{equation}\label{}` by hand if it wants a number; nothing in this
plan gives that genre new marker vocabulary, mirroring §12's existing
"has no third option" note and §13's `.tex` carve-out.

## 🔨 Build order

Test-first at each step, per DEVELOPER-AGENTS.md:

1. `chitragupta/render_output/_equation_captions.py` -- parsing,
   numbering, both content-substitution shapes, warnings.
   `tests/test_render_output_equation_captions.py`.
2. Wire into `_substitution.py`: declared-list computed once, content
   substitution running after `_math.substitute`, warnings before the
   early return.
3. `chitragupta/style_elements.py`, and the `style_tables.py`/
   `style_figures.py` edits that call into it instead of keeping their
   own copy. `tests/test_style_elements.py` for the shared logic;
   existing table/figure style tests otherwise unchanged.
4. `chitragupta/style_equations.py`, reached from `style_check.check()`.
5. `chitragupta/review/_claims.py`: the `equation` CAPTION alternative
   and `INLINE_EQUATION_REF`, with the existing claim tests extended.
6. Prose: WRITING-STANDARDS.md's new §12 subsection and §9 row,
   docs/CLI.md's `draft style` findings table.
7. One real end-to-end render of a scratch draft to `md`, `tex` and
   `pdf` (where the toolchain is present), checked for the number and
   label in each.
