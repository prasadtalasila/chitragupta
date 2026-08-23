# D2: deterministic TikZ layout check

Status: **plan, built.** Written 2026-08-20; the mechanism section
revised 2026-08-22 after re-probing it on this host, which is what
that section itself asked the implementer to do. D1 shipped in 6.16.2
(#329) as [docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md); this is D2.
Implements [docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s D2.

**Written for** whoever builds it. **Assumed:**
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10 for the
two-form figure contract, and the roadmap's Theme D for why this is
deterministic rather than a vision model. **Not covered here:** the
style guidance a figure is written against, which is D1's --
[docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md) now.

## The mechanism, re-probed 2026-08-22

Each figure is wrapped in a scaffold document and compiled with an
ordinary `pdflatex`. That much was always the plan. What the re-probe
changed is what the scaffold looks like, and it changed three things --
each one verified by compiling, not reasoned about:

**1. `article`, not `standalone`.** `standalone.cls` ships in
`texlive-latex-extra`; `tikz.sty` ships in `texlive-pictures`. They are
separate packages, so a scaffold built on `standalone` depends on a
toolchain fact nothing in this project checks -- reintroducing exactly
the class of bug `_require_tikz()` exists to prevent (#226, where
`pdflatex` being on PATH was wrongly taken to imply `tikz.sty`).
`\documentclass{article}` + `\usepackage{tikz}` is the same minimal
wrapper [docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10
and every genre skill's "verify it compiles" step already specify, it
needs no package beyond what `_require_tikz()` checks, and it yields
byte-identical `\pgfpointanchor` output. Use it.

**2. `\pgfgetlastxy`, not raw `\pgf@x`/`\pgf@y`.** The original probe
read pgf's internal registers directly, which needs `\makeatletter` in
the emitted document -- `@` is a non-letter catcode outside one, and
without it the `\typeout` degrades silently to the literal text
`\the \pgf` plus a stream of "Undefined control sequence" errors while
still exiting 0. `\pgfgetlastxy{\x}{\y}` is pgf's public accessor for
the same values, needs no `\makeatletter`, and cannot break on a pgf
version that reorganises its internals.

**3. The picture's own bounding box is `current bounding box`.** The
original section covered node-to-node overlap only and left the
protrusion and corner-emptiness checks without a source for the
picture-wide box. TikZ's `current bounding box` is a real pseudo-node,
so `\pgfpointanchor{current bounding box}{south west}` works through
the identical mechanism -- one probe shape serves all three
geometry-dependent checks rather than two.

The emitted scaffold therefore looks like this, and yields:

```text
CGBOX a -42.87912pt -7.97742pt 42.87912pt 7.97742pt
CGBOX b -8.73592pt -6.94963pt 77.02232pt 6.94963pt
CGBOX c -20.78996pt -63.85512pt 20.78996pt -49.95586pt
```

`a` and `b` overlap by 51.6pt in x and overlap in y -- a real collision,
detected with no model in the loop.

**Why the instrumentation, rather than just compiling and reading the
PDF.** Worth stating because "compile the figure and look at it" is the
obvious first thought and it does not work. Verified on this host: a
compiled figure's PDF contains **zero** occurrences of its own node
names. The content stream is anonymous drawing operators
(`1 0 0 1 155.769 660.474 cm`, `[(A)]TJ`) -- TikZ knows a node's name
only at compile time, and the PDF has already forgotten it. So a bare
compile answers exactly one of the five checks, "does it compile?", and
cannot answer "does node `a`'s box overlap node `b`'s", because nothing
in the artefact still says which box was `a`. The `\typeout` is what
makes TikZ print the name-to-box mapping while it still knows it.

**Reproduce the probe before writing code.** It is the one assumption
everything else rests on, it is cheap to re-run, and re-running it is
what produced all three corrections above.

## What it checks

| Check | Kind | From |
| --- | --- | --- |
| Node overlap | **binary** | pairwise box intersection, excluding containment |
| Node text overload | **binary** | word count per node, ~15 words |
| Content protrusion | **binary** | the largest empty horizontal band |
| Edge list | **binary** | `\draw`/`\path` node-to-node pairs, reported for confirmation |
| Corner emptiness | **continuous** | proportion of the bbox left empty |

Two of those rows differ from what this plan first specified, and both
changed because the original could not work:

- **Protrusion is a band, not a bbox-versus-union comparison.** Where the
  protruding element is itself a node -- the usual case, and the one the
  veto describes -- the union already contains it, so the two agree
  exactly and nothing is ever reported. The largest empty horizontal band
  is what the defect actually is, and including the bounding box as a
  band boundary makes one mechanism catch both a stranded node and
  non-node content reaching past every node. Vertical only: the veto is
  about vertical space, and horizontal gaps are what a pipeline and a
  hub-and-spoke layout are *made* of.
- **Overlap excludes containment.** A box wholly inside another is a zone
  or grouping box, which is an idiom docs/TIKZ-STYLE.md recommends. See
  the real-draft findings at the end of this document.

The binary/continuous split is not cosmetic. The roadmap's R3
constraint forbids a continuous score from being the thing optimised by
anything unattended, so **corner emptiness is reported to a human and
consumed by nothing**, and the report must label it as such. An
unlabelled mixture is how a score ends up being optimised by something
that should not be optimising anything.

Deliberately **not** checked: arrow crossings ("chaotic routing"). Not
cheaply reachable from node geometry, and a bad approximation of it
would be worse than its absence.

## The edge list is the point

Every published PaperBanana diagram failure is a wrong or missing edge
-- semantics, not layout -- and every one is invisible to a check over
pixels. In TikZ an edge is `\draw (a) -- (b);`, so the edge list is
recoverable from source. Report it plainly (*a -> b, b -> c*) for the
author to confirm against the prose the figure illustrates. This is the
cheapest possible implementation of a faithfulness check, needs no
model, and exists only because this pipeline generates source.

## Decisions this plan settles

**Where it lives.** A review-layer aid: advisory, exits 0 whatever it
finds, takes no lock. That means it carries the roadmap's R10 -- keys in
**both** `review.AIDS` and `__main__.AIDS`, plus AGENTS.md, CLI.md, the
README tables and `mkdocs.yml`. `review/__main__.py` raises at import if
the two dicts disagree; the `mkdocs.yml` omission is the silent one.

**What to call it.** Not `audit`, `verdict`, `reckoning` or `ruling` --
the judgement register belongs to the gate. Not `triage`, which
[docs/REJECTION.md](../docs/REJECTION.md) records as built and
withdrawn. `figure` is accurate and free.

**Compiling is a side effect, and must not litter.** Build in a
temporary directory and never beside the draft. Two different failures
hide in one sentence here, and they want opposite handling:

- **`tikz.sty` absent on the host.** One fact for the whole run, checked
  once, and `_require_tikz()` already models it -- reuse it rather than
  writing a second `kpsewhich` probe. Because the scaffold is now
  `article`-based (above), that one call covers the scaffold's entire
  dependency surface, so there is no second toolchain fact to check.
- **One figure's own TikZ is broken**, on a host where `tikz.sty` is
  present. Catch the `CalledProcessError` per figure, turn it into a
  finding, and **keep checking the other figures** -- one bad figure must
  not end the run or take the exit code with it. `review/__init__.py`'s
  own `write()` already does exactly this warn-and-continue for a failing
  pandoc render; follow it.

Either way the aid **reports and exits 0**. It is an aid, not a gate.

**No timestamp in the report**, per the layer's existing rule: two runs
over an unchanged figure produce byte-identical output.

**Reuse the renderer's figure discovery, do not re-parse.**
`render_output/_figures.py` already owns both spellings a draft uses for
a figure -- a Markdown draft's `<!-- figure: ... -->` marker and a
`.tex` fragment's real `\input{...}` -- in `_figure_refs()`, and owns
the never-read-outside-the-draft-directory rule in `_resolve_sibling()`.
A second parser here would mean a marker convention changes in two
places, and the one that drifts is the one nothing renders.

## Files

| File | Change |
| --- | --- |
| `chitragupta/review/figure_layout.py` | new: probe emitter, log parser, the five checks. Split into a package if it crosses `MAX_CODE_LINES = 250` -- a new offender is never added to the register |
| `chitragupta/review/__init__.py` | register in `AIDS`; its docstring says "Three commands" twice |
| `chitragupta/review/__main__.py` | register in `AIDS`, wire the subcommand; docstring and `DESCRIPTION` both say "three aids" |
| `chitragupta/render_output/_figures.py` | reuse `_require_tikz()`, `_figure_refs()`, `_resolve_sibling()`; no behaviour change |
| `docs/PACKAGING.md` | a row in the `review` table -- `tests/test_packaging_command_table.py` checks this file against live `--help`, so it is required, not optional |
| `tests/test_review_entrypoint.py`, `tests/test_packaging_command_table.py`, `tests/test_review.py` | each hard-codes the aid count or list |
| `docs/CLI.md`, `AGENTS.md`, `README.md` | R10's sweep, plus the stale "all three aids" counts |
| `mkdocs.yml` | **nothing to add.** R10 names it, but the precedent is against: `coverage` has no nav entry either. The nav lists *documents*, and only aids with a dedicated doc (`CITATION-PROVENANCE.md`, `PLAGIARISM.md`) appear. This aid adds no doc page |
| `docs/WRITING-STANDARDS.md` | **nothing to add.** §10's TikZ advice moved to `docs/TIKZ-STYLE.md` in #329; that file is where a pointer belongs if one is wanted |

## Tests

Failing first:

1. Two overlapping nodes are reported; two spaced nodes are not.
2. The probe's own output parses -- pin the `CGBOX` format against a
   real `pdflatex` run, not a fixture, since the format is the
   assumption.
3. A node of 30 words is reported; one of 5 is not.
4. The edge list of a three-node chain is exactly `a -> b, b -> c`.
5. A figure that fails to compile produces a finding and **exit 0**,
   *and* a well-formed figure in the same draft is still checked -- the
   second half is the one that would regress silently.
6. Byte-identical output over two runs.
7. `AIDS` disagreement raises -- likely already covered; assert it
   covers the new key.
8. Discovery finds a Markdown draft's marked figure and a `.tex`
   fragment's real `\input`, and drops a marker naming a file that is
   not there.

**Tests 1, 2, 5 and 6 need a real `pdflatex` with `tikz.sty`; 3, 4 and 8
do not.** Mark the first group to self-skip on a host without the
toolchain, the way this repository's render tests already do -- CI's
Windows leg installs no `os-deps` and would otherwise fail them for a
missing binary rather than a missing behaviour. Keeping the static
checks free of that dependency is why the module splits them out.

## Build order

Each step is one commit, test first:

1. Discovery (`figures_in`), reusing `_figures.py`. **Done.**
2. Static check: node text over 15 words.
3. Static check: the edge list.
4. The scaffold emitter, `pdflatex` runner and `CGBOX` parser.
5. Compile-failure handling, both kinds (see "Decisions").
6. Node overlap, from the parsed boxes.
7. Protrusion and corner emptiness, from `current bounding box` against
   the union of node boxes. Note in the docstring that the union
   over-estimates where nodes overlap, which is acceptable precisely
   because overlap is independently reported by step 6.
8. Report and CLI -- text and JSON, following `citation_coverage.py`'s
   `format_report`/`run()` shape and `review.header()`/`envelope()`.
9. Register in both `AIDS` dicts.
10. The doc and test sweep from the Files table.

## Done when

The probe in the roadmap is reproduced by the test suite rather than by
hand, and running the aid over the repository's own drafts reports
something a human agrees is worth fixing. If it reports nothing on real
figures, say so in the PR -- that is a result, and it would mean the
layout complaint lives somewhere this check cannot see.

## What the real-draft run found, and what it changed

Running the finished aid over `content/drafts/` was not a formality: it
found four defects the unit tests could not, because each needed a real
figure written by someone who was not thinking about this checker.

- **The picture's bounding box came back as TikZ's empty sentinel**
  (16000pt, 16000pt, -16000pt, -16000pt) for every figure. Node anchors
  survive into a later `tikzpicture`, so probing from an appended one
  *looks* correct -- every node box was right -- but `current bounding
  box` belongs to the picture being built, and a fresh empty picture has
  none. The vast sentinel area made every real figure report "100%
  empty". Fixed by splicing the probes in before the figure's own last
  `\end{tikzpicture}`.
- **`\foreach` bodies produced junk edges** like `\x,-0.12 -> \x,0.12`.
  The coordinate filter tested for digits, and a macro-valued coordinate
  has none. Fixed by keying on the comma, which a TikZ node name cannot
  contain and a coordinate always has.
- **A figure with no *named* nodes reported "100% empty"** about a
  visibly full picture -- two of this repository's own figures are drawn
  entirely from `\draw` paths. There is no node area to subtract, so the
  arithmetic is meaningless rather than extreme; it now reports nothing.
- **Zone nodes were reported as overlaps.** A two-zone architecture
  figure produced eight, every one a labelled `CONTROL PLANE`/`DATA
  PLANE` rectangle containing the nodes it exists to group. That idiom is
  one docs/TIKZ-STYLE.md *recommends*, so the check was firing on the
  standard's own advice. Fixed by excluding containment: a box wholly
  inside another is a zone, not a collision.

After those four, the same figure reports **two** overlaps, and both are
real: `cmdexec` and `svc` extend about 13pt below the bottom edge of the
`dp` zone that groups them, so they visibly hang outside it. That is the
"something a human agrees is worth fixing" this section asks for.
