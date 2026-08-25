# #396: sub-captions for a figure's panels

Status: **plan, built.** Written 2026-08-25; built the same day in PR
409, which shipped every file in the list below and none of the
optional tiers. Implements
[#396](https://github.com/prasadtalasila/chitragupta/issues/396), "when
there are two sub-figures, add sub-captions to them" -- **read as *two or
more*, with no fixed number**, per the issue author. Two is the smallest
case, not the case. Everything below is stated for *n* panels, and the
one place *n* actually bites is width: see "How many panels fit". Not a
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md) item; it sits
beside Theme D's figure work without depending on any unbuilt part of
it.

**Why a plan at all**, since
[plans/README.md](README.md) says not to write one for a docs-only
change: the design is underdetermined in the way that README's first
test names. Nothing today says where a figure's caption lives, so
"sub-caption" has no parent contract to hang off, and the obvious
implementation (`subcaption`) fails in a build we never see. There is
also an optional code tier below. Both are decisions a later reviewer
would otherwise have no way to tell from accidents.

**Written for** whoever builds it. **Assumed:**
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10 for the
two-form figure contract and the `figure:` marker, and
[docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md) for the layout metaphors and
the pre-flight checklist. **Not covered here:** figure originality,
the ASCII alphabet, and the marker syntax, all of which stay in §10; and
the sub-captions `chitragupta/enrich/docling_parse.py` *discards* when
parsing a source PDF ([docs/PERFORMANCE.md](../docs/PERFORMANCE.md),
[docs/PDF-PARSER.md](../docs/PDF-PARSER.md)) -- opposite direction,
untouched.

## What the issue is actually asking for, and what it exposes

An author who draws several panels in one figure has nothing to follow.
The standards say a figure has two sibling forms named by one marker;
they say nothing about panels, sub-captions, or where a caption lives at
all -- and the book this pipeline has already drafted contains panelled
figures with two and with three panels, none of them lettered. Probed on
this host, the gap is wider than the issue's one sentence:

- A Markdown draft's figure is injected as a bare `\input{figures/<name>.tex}`
  with no float around it (`_substitute_tikz_for_ascii`). Verified by
  rendering a scaffold-based draft to `--format tex`: the body is the
  `\input` alone, so a figure drawn today is **uncaptioned and
  unnumbered** unless its own file carries the float.
- The renderer's preamble is pandoc's default plus
  `\usepackage{tikz}` and nothing else
  (`chitragupta/render_output/__init__.py`). No `caption`, no
  `subcaption`.

So "add sub-captions" cannot be answered without first settling where a
caption lives. That is the contract this plan fixes.

## The decision: sub-captions are drawn, not packaged

**An *n*-panel figure stays one figure, one marker, one `.tex`/`.txt`
pair, for any *n*. Each panel's sub-caption is an ordinary TikZ node
reading `(a) <short title>`, `(b) ...`, lettered in reading order.**
That is the whole requirement, and it holds in a bare `tikzpicture`.

Where the figure *is* captioned, the caption is the figure file's, in a
`figure` float around the picture -- which needs no package, since
`\caption` in a float is LaTeX itself. That is the book's established
convention rather than a new demand on every genre; the sample section
below has the counts that decide it.

Nothing in that is bounded by two, and the letter sequence is the only
thing that grows with *n*. What does not scale is width, which is its
own section below.

Verified end to end on this host before writing this, at *n* = 2, 3 and
4: panels grouped with `fit`, a label node under each, `\caption` on the
float. Each renders through
`python -m chitragupta.draft render --format pdf`, reports **no
finding** from `python -m chitragupta.review figure`, and has every name
it declares -- the empty `fit` group nodes included -- come back
measured by `figure_layout.node_boxes` (8, 12 and 16 names
respectively), which is the assertion the test in item 3 rests on.

**`fit` is the recommended grouping, not a requirement.** Every figure
in the sample below -- all 53 of them -- places its nodes at absolute
`x=1mm,y=1mm` coordinates and loads no TikZ library at all, so a rule
that *required* `fit` would make every existing figure non-conforming
for a reason unrelated to sub-captions. What the rule
requires is the label node and its letter; where the panel's extent
comes from is the author's.

**The float is the author's, not the scaffold's.** `assets/tikz/`'s six
files are bare `tikzpicture` fragments and stay that way: adding a float
to each would be six edits and a re-run of the whole geometry suite for
no gain, and a scaffold is copied into a figure file rather than being
one. So the rule has to be stated where the copy instruction already
lives ([docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md)'s "copy the one whose
metaphor fits and re-label it") -- wrapping the copy in a `figure` float
with a `\caption` is a step of that copy, for one panel or two. Without
that sentence the standard's own starting file would not meet the
standard.

### Why not `subcaption`

`subcaption.sty` is installed here (`/usr/share/texlive/texmf-dist/tex/latex/caption/`),
so this is a design rejection, not a missing-package one.

**`\usepackage` is preamble-only; `\usetikzlibrary` is not.** Probed:
`\usepackage{subcaption}` after `\begin{document}` fails with
`! LaTeX Error: Can be used only in preamble.` That asymmetry is what
decides it. A figure file can load its own TikZ library --
[docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md) requires it to -- but it
cannot load its own package, so `subcaption` would have to be added to
every preamble a figure can reach, and one of those is not ours:

| Preamble | Owner | Adding `subcaption` |
| --- | --- | --- |
| `render_output/__init__.py`'s `header-includes` | us | possible |
| `review/figure_layout/_probe.py`'s scaffold document | us | possible; without it the aid reports a false defect on a valid figure |
| `book-assembler`'s document skeleton | us (a skill) | possible |
| **the user's own thesis** | **them** | **impossible** |

`thesis-chapter-writer` exists to produce a fragment the user `\input`s
into their own document. A figure needing `subcaption` compiles here and
fails there, in a build we never see -- the same failure class §10
already refuses for `\input{figures/<name>.txt}`. Drawn sub-captions
work in all four columns and change no preamble.

The cost is honest and should be written down where the rule is: drawn
labels are not `subcaption`'s, so there is no `\subref` and no automatic
"Figure 1a". Prose refers to "Figure~\ref{fig:x}(a)", with the `(a)`
typed. The cost does not grow with *n* -- it is one typed letter per
reference either way.

### Why not one marker per panel

*n* `figure:` markers give *n* floats, *n* figure numbers and *n*
captions -- *n* figures in a row, which is not what a sub-figure is. It
would also multiply every §10 obligation (*n* `.txt` twins for one
diagram) by *n*, for no gain.

### How many panels fit

This is the one place *n* is really bounded, and it is bounded by the
text block rather than by any rule worth writing. Probed on this host,
through the real render path:

| Arrangement | Result |
| --- | --- |
| 3 panels of ~48mm in one row | **`Overfull \hbox (71.81378pt too wide)`** -- the figure runs into the margin |
| the same 4 panels as a 2x2 grid | 0 overfull boxes, no layout finding |

pdflatex only *warns* on that, so an author who never reads the log
ships a figure past the margin. So the guidance is: **when a row stops
fitting, wrap into another row -- never scale the picture down.**
`\resizebox` or a `scale=` key would shrink the node text with it, and
[docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md)'s "node text matches the
document's own font size" already forbids exactly that trade. Rows also
keep the bounding box rectangular, which is the same document's
"inefficient non-rectangular composition" item.

Panels stacked vertically are equally legitimate and need no special
rule -- the book's own `5-2-inaccurate-vs-unstable` is two panels one
above the other. Reading order is what fixes the letters: left to right,
then top to bottom.

## The other half: the ASCII twin

The `.txt` is what every non-LaTeX render shows, and it carries no
caption today because nothing injects one. The rule must therefore say:

- **Every panel label appears in both forms.** `(a)`, `(b)`, `(c)`, ...
  in the ASCII diagram, same letters and same reading order as the
  picture, 7-bit as §10 requires. This is the whole of what #396 adds to
  the `.txt`.
- **The arrangement need not match.** Three panels that sit in a row in
  the picture may have to stack in the ASCII form, because §10 caps that
  form at ~70 columns and the picture is capped by `\linewidth` instead
  -- two different budgets. What has to agree is the letters, the titles
  and the order, not the geometry.
- `draft-reviser`'s "touch a figure, touch both forms" already covers
  keeping them in step; sub-captions add a third thing to keep in step
  and are worth naming there.
- **The caption line the `.txt` already carries stays.** All 43 figures
  in the book repeat their caption as a trailing `Figure N.M ...` block
  in the ASCII twin (measured: 43/43), which is what keeps a caption
  visible in the `md` render -- the `md` path substitutes the `.txt` and
  never reads the `.tex`, so a `\caption` alone would vanish there. This
  is existing practice to write down, not a new obligation.

## Which formats this reaches -- all of them, not just `tex`/`pdf`

The panels are TikZ, so it is tempting to scope the rule to the
LaTeX-bound formats. That is wrong, and it is the reason "the letters
appear in both forms" is a requirement rather than a nicety.
`_TEX_FORMATS` is `{tex, latex, pdf}`; **every other format the renderer
supports takes the ASCII twin instead**, so for those the `.txt` is the
*only* carrier the sub-captions have. Verified by rendering one lettered
three-panel figure to four formats and looking for the letters in each
output:

| Format | What carries the panels | `(a)`/`(b)`/`(c)` found in the output |
| --- | --- | --- |
| `pdf`, `tex` | the TikZ picture, via `\input{figures/<name>.tex}` | in the figure file (the rendered `.tex` carries only the `\input`) |
| `md` | the ASCII twin, in a fence | yes |
| `html` | the ASCII twin | yes |
| `docx` | the ASCII twin | yes -- all three, in `word/document.xml` |

So an author who letters only the TikZ half ships a `docx` and an
`html` whose panels are unlabelled, and no check anywhere reports it.
That asymmetry is worth one sentence in §10 next to the rule.

## Where this is recorded: the dossier

**Yes, and §8 already says where.**
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §8 makes
house style the second half of the dialect field -- its own example of a
house-style decision is *"how a figure is captioned"* -- and says to
record it beside the dialect, in the dossier's `scope.md`. Panel
lettering is exactly that kind of decision: a venue may want `(a)`,
`(i)`, `A`, or panel titles with no letters at all, and the pipeline
should not re-decide it section by section or session by session.

Two consequences for this plan, neither of which it had before:

- **§10's new rule must point at `scope.md`**, in one clause, the way §8
  points at it for the dialect. `draft-reviser` reads `scope.md` and
  `steering.md` before every edit
  (`.claude/skills/draft-reviser/SKILL.md`), so a convention on disk
  reaches every future revision; a convention agreed in chat does not
  survive the session.
- **A figure edit is already a `revisions.md` entry**, and lettering an
  existing figure's panels is a figure edit touching both forms. No new
  mechanism -- just say so, so that a reviser who letters panels logs it
  like any other change.

**Optionally, and only if wanted:** `scope.md`'s generated template
(`chitragupta/dossier/_create.py::_scope`) has a `- language:` line and
**no house-style line at all**, so §8's "record it beside the dialect"
currently has nothing to sit beside. Adding one commented line there,
with a `tests/test_dossier.py` assertion beside the existing
`test_scope_carries_a_language_line_marked_unsettled`, would make the
slot exist. It is a one-line change to a template, affects new dossiers
only, and is genuinely a different issue -- take it only if you want the
recording path left complete rather than merely named.

## The sample this was checked against

`content/drafts/books/digital-twins-for-software-engineers/figures/` --
43 TikZ figures and their 43 ASCII twins, the largest body of real
figures this pipeline has produced, plus the 10 figures in the three
other drafts that carry any (`da/`, and the two under `book-chapters/`).
Not exhaustive, and not a substitute for judgement, but enough to tell a
rule that fits practice from one that does not. Measured, not assumed:

| Property | The book | The other three drafts |
| --- | --- | --- |
| Wrapped in a `figure` float, with `\caption`, `\label` and `\renewcommand{\thefigure}{N.M}` | 43/43 | **0/10** |
| ASCII twin repeating the caption as a trailing `Figure N.M ...` block | 43/43 | **0/8** |
| Loading a TikZ library (`\usetikzlibrary`) | 0/43 | 0/10 |
| Naming at least one node, the aid's measurability precondition | **1/43** | 7/10 |
| Lettering a panel `(a)`/`(b)` | 0/43 | 0/10 |

Five things follow, and four of them changed this plan:

1. **The float and the caption are the *book's* convention, not the
   pipeline's.** Universal in the book, absent from every other draft --
   a book needs numbered, cross-referenced floats and a standalone
   survey does not. So the rule must **require only the lettering**,
   which is what #396 asks for and what works in a bare picture, and
   present the float-plus-`\caption` (plus `\label` and the
   `\renewcommand{\thefigure}{N.M}` that makes `\ref` print "15.2")
   as the captioned-figure convention the book already follows. Making
   floats mandatory everywhere would be a second, larger change riding
   in on this one, and would put 10 existing figures out of
   conformance for a reason unrelated to panels.
2. **`fit` cannot be mandatory.** No figure anywhere in the sample loads
   a library; they are absolute-coordinate pictures. Hence the
   "recommended, not required" wording above.
3. **Multi-panel figures are already common, and none of them is
   two-panel by nature.** Hand-checked examples, which are also the
   right regression sample for whoever builds this:
   `12-1-three-levels` (**three** panels in a row -- HOSTS /
   IMPLEMENTS / OPINIONATES), `6-3-fmi-variants` (two, side by side),
   `5-2-inaccurate-vs-unstable` (two, stacked vertically),
   `3-3-edge-central-split` (two, separated by a drawn divider **with an
   arrow crossing it**), `15-2-mesh-versus-hub` (two, the left one
   containing two sub-cases of its own). Every one of them titles its
   panels in bold capitals and none letters them.
4. **The TikZ half migrates by prefixing; the ASCII half does not.**
   Verified by copying `12-1-three-levels` into
   `content/drafts/_scratch/` and lettering it: in the `.tex`,
   prefixing the three `\textbf{...}` titles renders with 0 errors, 0
   overfull boxes and no layout finding. In the `.txt` it is not a
   prefix, because the titles sit *exactly* over their boxes -- title
   words and box left edges both start at columns 3, 24 and 45 -- so a
   naive prefix slides every later title off its panel. Each label has
   to absorb its 4 columns from the gap to its left instead, which
   leaves the art untouched and the letters overhanging their panels by
   4 columns (measured: 56 -> 57 characters, against §10's ~70 cap).
   There is room in this sample -- the widest twin is exactly 70 and
   none exceeds it -- but only because the labels overhang; re-spacing
   the panels to keep the letters flush would add 4 columns *per panel*
   and push the widest three-panel figures past the cap. Say the
   overhang is the intended form, or an author will re-space and quietly
   break the fence.
5. **It kills the geometry-based check.** See the tier below.

## Files to change

Docs first; this is a standards change, and the code half is optional.

1. **[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10** --
   under "What the pair requires": a figure with *any* number of panels
   is one figure, one marker, one pair; every panel lettered in both
   forms, in reading order; and where a figure *is* captioned, the
   caption is the figure file's, in a `figure` float -- with `\label`
   and `\renewcommand{\thefigure}{N.M}` beside it, which is what makes
   `\ref` print the chapter-relative number the book's prose already
   uses, and which is invisible to anyone who has not opened one of
   those 43 files. Two or three bullets, no worked TikZ (that is
   TIKZ-STYLE's). State the count-independence explicitly -- #396's own
   wording says "two", and a reader who takes that literally is the
   failure mode this bullet exists to prevent. Two further clauses,
   both from the sections above: the letters must be in the ASCII form
   because `docx` and `html` have nothing else to show, and the
   lettering convention is a §8 house-style decision recorded in the
   dossier's `scope.md`.
2. **[docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md)** -- a new section,
   "Panels in one figure", after the metaphor table: group each panel
   (`fit` recommended), put the `(a) <title>` node below it, and the
   `figure` float with `\caption` around the picture; then the width
   rule -- wrap into rows, never scale -- with the overfull measurement
   as its evidence. One compiled example, fenced, showing **three**
   panels rather than two, so the pattern cannot be read as a pair.
   Plus the `subcaption` rejection above, in the "recorded so it is not
   tried again" idiom this repo already uses -- including that the
   package *is* installed, so the next reader does not re-probe it.
   **And one sentence beside the existing copy instruction** saying the
   float and caption are added at the copy step, per the decision above
   -- without it the six scaffolds read as violating the new rule.
3. **`tests/test_tikz_subcaptions.py`** (new) -- reads the fenced example
   **out of TIKZ-STYLE.md** rather than restating it, exactly as
   `tests/test_tikz_scaffolds.py::_metaphors` reads the metaphor table,
   with the same non-vacuous-scan guard. Asserts it compiles, that every
   name it declares comes back measured, that `overlaps` and `protrudes`
   are clean, and that it survives `check_draft()` when copied beside a
   draft. `@needs_tikz`-skipped on the Windows leg, same as that file.
   The letter assertion is about *that example*, not a general rule:
   the doc's figure declares exactly three label nodes, lettered `(a)`
   to `(c)` in source order. Hard-coding three is right here and would
   be wrong anywhere else -- panel count is not recoverable in general,
   which is the whole argument of the section below, and
   `figure_layout` exposes no node *text* accessor to build one from.
4. **The four genre skills' figure steps** --
   `survey-writer`, `tutorial-writer`, `thesis-chapter-writer`,
   `textbook-chapter-writer` each already link to TIKZ-STYLE.md from
   their figure step; one clause pointing at the new section is enough.
   Do not restate the rule in four places.
5. **`.claude/skills/draft-reviser/SKILL.md`** -- its "touch a figure,
   touch both forms" rule gains a third thing to keep in step: the panel
   letters, in the same order in both. One clause, beside the existing
   rule, and a reminder that lettering an existing figure is a
   `revisions.md` entry like any other figure edit.
6. **`assets/tikz/README.md`** -- one line: panels are composed by
   repeating one of these scaffolds in a single picture, however many
   times the figure needs, and the how-to is TIKZ-STYLE's.
7. **[docs/RENDERING-FLOW.md](../docs/RENDERING-FLOW.md)** -- its
   four-row substitution table says the marker becomes
   `\input{figures/<name>.tex}` and is silent on the float, which is
   what makes "the caption is the figure file's" surprising. One
   clause pointing at §10's new rule.

**Do not add a `panels.tex` scaffold to `assets/tikz/`.**
`tests/test_tikz_scaffolds.py::test_no_scaffold_names_a_metaphor_the_doc_dropped`
asserts the file set equals the metaphor table's slugs exactly, so a
seventh file fails the suite unless a row is added to a table where it
does not belong -- panelling is a composition applied to a metaphor, not
a metaphor. That is also why it cannot be one file: the panels of
`12-1-three-levels` are three instances of one metaphor, while a
before/after pair may be two different ones. The compiled example lives
in the doc and is read from there by a test.
`docs/TIKZ-STYLE.md` and `docs/CLI.md` both say "six scaffolds" and stay
true.

**The book's own 43 figures are not part of this change.**
`content/` is product, gitignored, and the author's to revise with
`draft-reviser`; the standard binds figures written after it lands. The
`12-1-three-levels` migration above is evidence that retrofitting is a
prefix when someone chooses to do it, not a task this issue owns.

## The mechanical check, and why not to build it

The obvious second tier is a `review figure` check that counts panels
and complains when *k* panels carry fewer than *k* letters: cluster the
measured boxes by their gutters, and treat a cluster no edge reaches
into as a panel. Do not build it. The sample above refutes it three
times over, and each refutation is independent:

- **It would be blind on 42 of the book's 43 figures**, and on 45 of the
  53 in the sample overall. The aid measures only nodes the source
  names; one figure in the book names any, and 7 of the other 10 do.
  A check that reports nothing on most of the corpus is worse than no
  check, because "no finding" is indistinguishable from "clean" -- the
  vacuous-clean trap [docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md) already
  warns about. Confirmed on the migrated three-panel figure: it renders
  correctly, is visibly three panels, and the aid prints no measurement
  at all.
- **"No edge crosses the gutter" is not what a panel is.**
  `3-3-edge-central-split` is two panels with an arrow drawn from one to
  the other, which is the point of that figure.
- **The existing checks already misread multi-panel figures.**
  `15-2-mesh-versus-hub`, the one figure that does name nodes, reports
  `content protrudes past the main block` and `96% of the figure's box
  is empty` -- both artefacts of a wide multi-panel layout in which only
  a small cluster of nodes is named. Adding a panel-counting check on
  top of a geometry layer that already misjudges this shape would
  compound the error rather than catch anything.

If a check is wanted later it has to be **source-level** -- counting
label nodes and asserting the letters are consecutive from `(a)`, which
needs no measurement and would work on all 53 -- and that is a different
design worth its own issue. Either way it stays advisory, exit 0,
consumed by nobody ([docs/REVIEW.md](../docs/REVIEW.md),
[docs/CLI.md](../docs/CLI.md)).

## Verification, and the release

- Compile the doc's example through
  `python -m chitragupta.draft render --format pdf` on a scratch draft in
  `content/drafts/_scratch/`, never against real content, and run
  `python -m chitragupta.review figure` on it. Both were
  already done once for this plan; do them again on the example as
  written, since a re-worded label moves the geometry.
- **Read the `.log` for `Overfull \hbox`, not just the exit code, and
  read it for the ASCII form too.** A figure past the margin still
  renders and still exits 0, so a green render is not evidence the
  panels fit -- this is how a fourth panel would slip past. The same
  warning is the *only* signal that a lettered ASCII twin has crossed
  §10's column cap, since a fence is typeset verbatim and nothing
  wraps it; check the widest line of the `.txt` directly as well.
- **Re-run the row-wrapping guidance against the sample**: copy
  `12-1-three-levels`, `6-3-fmi-variants`, `5-2-inaccurate-vs-unstable`
  and `3-3-edge-central-split` into `content/drafts/_scratch/`, letter
  their panels in both forms, and confirm each renders with no overfull
  box and no new layout finding. Three panels, two side by side, two
  stacked, and two with an arrow across the divider -- four shapes the
  rule has to survive, and the whole reason to check against a real
  sample rather than an invented pair.
- Full local checks per [DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) --
  pytest from `.venv-full`, the linters including markdownlint over
  `plans/`, and `mkdocs --strict`.
- **PATCH**: every file in the list is prose or a test, and no CLI,
  output format or config key changes.
