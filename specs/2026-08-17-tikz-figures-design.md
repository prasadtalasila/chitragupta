# Design: every ASCII figure also has a TikZ form

Status: **implemented 2026-08-17.** This document is the design as
built; where it first said something narrower, the "Scope, widened"
section below records what changed and why, rather than being quietly
rewritten.

## Scope, widened

This started as a thesis-only design: the `.tex` genre would gain TikZ,
and the three Markdown genres would keep ASCII in every format. The user
widened it before implementation to the general rule -- **any skill that
emits an ASCII figure must also carry a TikZ form, rendered in the `tex`
and `pdf` outputs.**

That makes the design symmetric rather than one-directional, and it is
the shape that shipped:

| Draft | Native form, inline | Sibling file | Marker |
|---|---|---|---|
| `.md` (tutorial, textbook, survey) | ASCII, in a fence | `figures/<name>.tex` | `<!-- tikz-alt: ... -->` |
| `.tex` (thesis) | TikZ, via `\input` | `figures/<name>.txt` | `%ascii-alt: ...` |

Each draft keeps its own native form inline and names the other in a
marker; the renderer swaps them per output format. **Only the other form
becomes a file.**

That last point was settled twice, so it is worth recording why it
landed where it did. A Markdown draft needs no `.txt`: its ASCII is
already the fence the `md` render emits, so a second copy is one nothing
reads and nothing keeps in step. An intermediate revision required the
`.txt` in every genre for uniformity, and added a drift check to stop it
rotting; that was then reverted, because a check that exists only to
guard a file nothing uses is cost without benefit.

**The `.tex` genre's `.txt` is not in that category -- it is
load-bearing**, and the distinction is the whole reason the rule is
per-genre rather than uniform. `_substitute_ascii_for_tikz` reads it to
build the `.md` preview. Demonstrated against the real function: with
the `.txt` present the preview carries the diagram in a `verbatim`
block; with it removed the `\input` survives untouched, pandoc resolves
it and drops the `tikzpicture`, and the figure disappears from the
preview entirely -- which is the exact hole this feature was built to
close.

One consequence the user should see recorded: #223 calibrated ASCII
figures as fitting `tutorial-writer` *most* naturally, and a tutorial's
pdf is a working document rather than a submitted artifact. The
per-use-value argument that justifies TikZ in a thesis fragment does not
transfer there. Implemented as asked; noted here so the trade is
visible.

## The base this is written against

**Rebased 2026-08-17 -- done, no action needed.** Recorded because the
reasoning matters if this ever has to be redone.

`support-tikz-figures` was #226's *own* branch: `5bf51e0b` and `main`'s
`1fcb9d83` had identical trees, but `5bf51e0b` was not an ancestor of
`origin/main` -- the signature of a squash-merge. So the branch
carried #226 but **not** #223, and `docs/WRITING-STANDARDS.md` §10 -- which this
document amends throughout -- did not exist on it.

`git rebase origin/main` resolved that by itself: git reported
`skipped previously applied commit 5bf51e0b` and the branch became
exactly `origin/main`, at **5.28.0** (#223 and #227 had landed
meanwhile). The rebase was against `origin/main`, not local `main`,
which is pinned stale in this worktree -- a merge-base squash against
the local ref silently swallows upstream commits.

Every §10 reference, every `docs/CODE-STANDARDS.md` line number and both
register entries quoted below were re-verified against that base after
the rebase.

Builds on two commits already on `main`:

- **#226** (`1fcb9d83`, 5.26.0) taught `src/render_output.py` to carry an
  `\input`-ed TikZ figure through a render: `_local_tex_include_refs`,
  `_copy_local_tex_includes`, a conditional `\usepackage{tikz}`, and
  `TEXINPUTS` on the pdf subprocess.
- **#223** (`3aa3d4c6`) documented the plain-ASCII diagram as the
  supported figure form (`docs/WRITING-STANDARDS.md` §10) and added a
  calibrated figure step to each writer skill.

## The problem

**No skill generates TikZ.** All four figure-bearing skills specify
ASCII only -- a fenced code block in Markdown, a `verbatim` environment
in the one LaTeX-sourced genre. Nothing writes a `figures/*.tex`, and
nothing emits an `\input{}`. So #226's plumbing is **shipped but
unexercised**: it fires only if a human hand-adds an `\input` line to a
draft.

The gap this closes: a thesis chapter's `.tex` fragment should carry a
real TikZ figure -- a vector picture that sets in the user's own thesis
at the document's own font and line width -- while every Markdown
artifact keeps the ASCII diagram §10 already promises.

## What each format does today, verified

Probed on this host against the real toolchain (`pandoc 3.x`,
`pdflatex`, `tikz.sty` present at
`/usr/share/texlive/texmf-dist/tex/latex/pgf/frontendlayer/tikz.sty`),
not inferred from documentation:

| Draft | Format | Path through `render()` | Figure today |
|---|---|---|---|
| `.md` | `md` | Early return at `render_output.py:505` -- no pandoc at all | ASCII fence, passthrough |
| `.md` | `tex`/`pdf` | pandoc | ASCII in a verbatim block |
| `.tex` | `tex`/`pdf` | pandoc + `TEXINPUTS` | **TikZ, already working** (#226's own end-to-end tests) |
| `.tex` | `md` | pandoc | **nothing -- the figure vanishes** |

That last row is the whole design problem. Pandoc's LaTeX reader *does*
resolve `\input` (a plain-text include came through intact), but the
`tikzpicture` environment is then dropped, and stays dropped under
`-t markdown+raw_attribute`.

**`--format pdf` does not read the rendered `.tex`.** Each format is an
independent pandoc run from the draft (`render_output.py:531`,
`:588-603`). For the thesis genre this makes no practical difference --
the draft *is* the `.tex`, so pdf and tex come from one source -- but
the plan must not assume a tex-then-pdf pipeline, because there isn't
one.

## The convention

A figure is a **pair of forms** under the draft's own topic directory.
For the `.tex` genre both are files:

```text
content/drafts/<topic>/<slug>.tex          the fragment
content/drafts/<topic>/figures/<name>.tex  the TikZ picture
content/drafts/<topic>/figures/<name>.txt  the same diagram in §10 plain ASCII
```

The fragment references both at the figure's position:

```latex
\input{figures/<name>.tex}
%ascii-alt: figures/<name>.txt
```

**Why the second line is a comment and not a second `\input`.** The
`.tex` fragment is the canonical deliverable -- the file the user
`\input`s into their own thesis. Our renderer's substitutions happen in
a temp copy, so whatever is on disk is what a real thesis compiles. A
literal `\input{figures/<name>.txt}` makes pdflatex read the ASCII art
*as LaTeX source*, and §10's own alphabet (`+ - | / \ > < ^ v`) contains
math-mode-only characters. Verified:

```text
! Missing $ inserted.        exit=1
```

So the user's thesis would fail to build, in a way our own render never
shows us -- our render strips the line first. A LaTeX comment is inert
to pdflatex, dropped by pandoc, and meaningful only to this pipeline.

A distinct `%ascii-alt:` marker rather than a commented-out `\input`
reads as deliberate, not as code someone disabled -- and it is
greppable, which is what lets `draft-reviser` and the drift check find
figures without parsing LaTeX.

**Why a topic directory is mandatory.** `_copy_local_tex_includes`
refuses absolute and `..`-escaping paths, so a figure must live under
the draft's own directory. A flat `content/drafts/<slug>.tex` would put
its figures in `content/drafts/figures/`, shared with every other flat
draft -- two chapters with a `fig1.tex` silently overwrite each other in
`content/rendered/`. Requiring `content/drafts/<topic>/` is the norm the
skills already follow; this makes it a precondition for a figure.

## Renderer behaviour, per format

| Format | Change |
|---|---|
| `tex`, `pdf` | **No behaviour change.** #226 already carries the `\input`; pandoc drops the comment. (The refactor below changes how the draft text is *read*, not what these formats produce) |
| `md` (LaTeX input) | **New.** Substitute before pandoc |
| `md` (Markdown input) | None -- returns early without pandoc, so the fence passes straight through and the HTML marker stays invisible |

For `--format md` on a LaTeX draft, in the temp copy only: each
`\input{X.tex}` whose following `%ascii-alt:` marker names a readable
sibling becomes `\begin{verbatim}<contents>\end{verbatim}`, and the
marker line is dropped.

**Verified, and it corrects the obvious assumption.** Pandoc's Markdown
writer renders that `verbatim` as a **4-space indented code block, not a
fenced one** -- a `CodeBlock` carrying no attributes takes the indented
form. Probed with §10's full alphabet:

```text
      +-------+  read   +--------+
      | model | ------> | solver |
      +-------+         +--------+
           ^      \  v < 0.5     |
           +-----------------+
```

Both things that matter survive: **relative alignment** (every line
shifted by the same 4 spaces, so the diagram is intact) and `^ \ < >`
literally.

The shape differs cosmetically from the fence §10 gives the Markdown
genres. Accepted rather than fixed: the substitution happens *before*
pandoc, in LaTeX, so a fence is not reachable from there -- forcing one
would mean post-processing pandoc's Markdown output, new machinery for a
difference that renders identically in every Markdown consumer. If §10's
wording is read strictly, amend §10 to say "code block" rather than
build the post-processor.

An `\input` with no marker, or a marker naming a file that isn't there,
is left alone and **warned about** (see Drift). The md preview then
omits that figure, exactly as it does today.

### One text, read once

`render()` currently reads the draft three separate times --
`_copy_local_tex_includes` (`:530`), `_safe_render_inputs` (`:552`), the
tikz gate (`:585`) -- and `TEXINPUTS` (`:601`) uses `input_path`. Adding
a substitution to one of those makes them disagree: pandoc would read
the substituted text while the tikz gate read the original, which
diverges for a thesis fragment that also carries a References section.

So `render()` reads the draft **once** and threads that text through.
Order within the temp copy:

1. **Figure substitution** -- rewrites only `\input`/marker lines.
2. `_swap_manual_refs_for_citeproc`.
3. Citekey aliasing (`_safe_render_inputs`).

Figures go first so the inlined ASCII is then scanned for `@key` like
any other text. That is harmless **only because** figure files may not
contain citekeys (below). If they could, an `@key` in a figure label
would be aliased in the md output and not in the pdf, and the two
previews would disagree about the same figure.

## Failure handling

A malformed TikZ figure fails the **whole** pdf render, not just the
figure -- `subprocess.run(..., check=True)`. And `tikz.sty` is its own
apt package (`texlive-pictures`, added by #226); a host without it
hard-fails the same way. Three layers, cheapest first:

1. **Probe before authoring.** The skill runs `kpsewhich tikz.sty`. If
   absent, it writes no TikZ figure at all -- the fragment gets the
   `.txt` and no `\input` -- and says so in chat. Degrading to ASCII is
   the graceful failure this design is shaped around.
2. **Compile each figure standalone before keeping it.** Wrap
   `figures/<name>.tex` in a minimal `\documentclass{article}` +
   `\usepackage{tikz}` document and run `pdflatex`. A figure that
   doesn't compile alone never reaches the fragment. This is the
   tutorial-writer "verify it actually runs" discipline applied to a
   figure.
3. **Name the figure when a render still fails.** `main()`'s
   `subprocess.CalledProcessError` arm (`:664`) currently prints
   `[error] pandoc failed: <stderr>`. When the failing draft has figure
   includes, it also names the figure file and tells the user to run the
   `draft-reviser` skill with a specific prompt -- e.g. *"the TikZ figure
   `figures/fig1.tex` fails to compile; repair it or drop the figure"*.
   Decision: inform the human and route them to the repair skill, rather
   than attempt an automatic fallback to the ASCII form.

## Citekeys in figure files: forbidden, stated, not gated

A citekey inside a TikZ node in `figures/<name>.tex` is invisible to
`python -m src.draft gate`, which reads the draft file and does not
follow `\input`. The prohibition therefore lives in
`docs/WRITING-STANDARDS.md` §10 and in the skill, the same way §10
already handles figure originality ("This is not gated mechanically").

**The gate is not extended**, deliberately.
`docs/CODE-STANDARDS.md:504` states that `python -m src.draft gate`
remains the only gate in the project, and its contract is exactly one
thing: a fabricated citekey fails. Making it also fail on a *real*
citekey in a figure file would give the one gate two meanings -- against
the same document's own warning that "a rule stated twice is a rule that
will eventually be stated two different ways."

The drift check below warns if it sees one.

## Drift between the two forms

Nothing can check that a TikZ picture and an ASCII diagram depict the
same thing. What is checkable, and what the render path warns on:

- an `\input{X.tex}` with no `%ascii-alt:` marker;
- a marker naming a file that is not readable;
- a citekey (`\cite`, `[@key]`) inside a referenced figure file;
- a **Markdown** draft carrying a marker -- unsupported, and its `md`
  output would leak the marker literally (see Non-goals).

All four are **warnings on stderr**, never a gate and never a render
failure -- consistent with the decision above and with how a genre skill
already reacts to `[error]`: warn and carry on.

**The check runs whatever the format**, including the `--format md`
early return at `:505` that skips pandoc entirely. That early return is
exactly the path a Markdown draft carrying a marker takes, so a check
wired only into the pandoc branch would stay silent on the one case it
most needs to catch.

The durable half is a rule in `draft-reviser`: **touch a figure, touch
both forms.** A revision that edits the TikZ and not the ASCII produces
a pdf and an md preview that disagree, and no machine will catch it.

## The refactor

`src/render_output.py` is on **both** ratchet registers -- 488 code
lines against C2's 250, and `render()` at 37 statements against C1's 25
-- and #226 bumped both. Approved decision: split it in this PR,
`src/dossier/` style (#224), rather than ratchet it a third time.

**This deviates from `docs/CODE-STANDARDS.md`'s Boy Scout section on
purpose**, which says cleanup belongs in its own PR. Logged here because
this project logs judgement rather than only making it: the user was
shown the "split `render()` only" and "package split in its own PR
first" options and chose the full split in this PR.

### Module map

`src/render_output.py` becomes `src/render_output/` -- same name, so
every importer is unchanged:

| Module | Holds |
|---|---|
| `__init__.py` | `render()`, `MissingBinary`, the `OutsideContentDir` re-export, `_require`, and the private re-export surface |
| `_citeproc.py` | `_alias_for`, `_safe_render_inputs`, `_swap_manual_refs_for_citeproc`, `_REFS_ANCHOR` |
| `_csl.py` | `_CSL_CITATION_TAG_RE`, `_resolve_csl`, `_collapsed_csl` |
| `_assets.py` | `_MD_IMAGE_RE`, `_URI_SCHEME_RE`, `_LATEX_INCLUDE_RE`, the four ref/copy helpers |
| `_figures.py` | **New.** Marker scanning, ASCII substitution, the drift warnings |
| `_paths.py` | `_output_dir`, `_MARKDOWN_SUFFIXES` |
| `_cli.py` | `main()` and the argument parser |

`render()` itself splits into `render()` plus a pandoc-command builder,
landing under 25 statements.

The module's stdlib-plus-`config`/`citation_gate`/`references` dependency
floor is load-bearing (a genre skill renders under bare `python`) and
survives the split unchanged.

### Zero test churn, verified

Every importer uses `from src import render_output` and reaches
attributes off the module. The private surface is exactly 11 names:

```text
_output_dir (15)  _swap_manual_refs_for_citeproc (6)  _resolve_csl (5)
_copy_local_images (5)  _copy_local_tex_includes (4)  _collapsed_csl (4)
_local_tex_include_refs (3)  _local_image_refs (3)  _alias_for (3)
_safe_render_inputs (2)  _require (2)
```

`__init__.py` re-exports those 11 and all 104 references in
`tests/test_render_output.py` keep working untouched.

### The delisting chain

The ratchet requires a fixed offender to be **delisted**, and the
register counts are themselves pinned. Four places move together:

1. `LEGACY_LONG_FUNCTIONS` -- drop `src/render_output.py::render`.
2. `LEGACY_LONG_FILES` -- drop `src/render_output.py`.
3. `test_the_registers_are_the_size_this_document_says` -- 11 functions
   and 12 modules become 10 and 11.
4. `docs/CODE-STANDARDS.md:295` -- the prose quoting those two counts.

Every new module must land under 250 code lines and every function under
25 statements, or the split has traded one register entry for another.

Two notes for whoever does this. The register is ordered worst-first,
and `src/render_output.py::render` (37) currently sits *below*
`src/enrich/docling_parse.py::parse_doc` (36) -- #226 moved it one place
too few. Deleting the entry resolves that by itself, so don't also
"fix" the ordering in the same diff. And the register is live: adding
`test_excludes_specs`'s two fixture lines grew
`tests/test_release.py::make_repo` from 31 to 33 and the suite failed
until the entry was updated. Expect the same on any test-fixture growth
this feature needs.

### The risk worth naming

The 75-line module docstring is not decoration -- it records the pandoc
citekey-tokenizer bug, the `--format md` rationale, the mirrored output
directory, and the dependency floor. Redistributing it across seven
modules without losing or duplicating a paragraph is the largest review
surface in this PR, and it is prose, which no test covers.

## Rejected alternatives

| Alternative | Why not |
|---|---|
| `\input{figures/fig.txt}` as a real second include | pdflatex: `! Missing $ inserted.`, exit 1. Breaks the user's own thesis (verified) |
| ASCII hidden inside the figure file behind `\iffalse ... \fi` | Pandoc honours `\iffalse` too, so the md render drops it as well (verified). No zero-code trick exists |
| Sibling lookup by convention, no marker in the draft | Works, and keeps the fragment minimal -- but a reader of the fragment cannot see that an ASCII form exists, and nothing is greppable for the reviser |
| Inline `verbatim` ASCII in the fragment body, renderer strips it for tex/pdf | The canonical deliverable then carries two copies of every figure; anyone `\input`-ing it raw gets both |
| Accept the hole -- no figure in the `.md` preview | Cheapest, but the preview stops previewing, and a reviser reading the `.md` would not know a figure exists |
| Transpile ASCII to TikZ in code | Unreliable, and pointless when the author is already an LLM that can write both |
| Extend `src.draft gate` to figure files | Gives the project's one gate a second meaning (see above) |
| Apply the convention to the Markdown genres too | Every genre's pdf would change and every host would need `texlive-pictures` or hard-fail. Out of scope by decision |

## Non-goals

- **`deep-research` still has no figures at all.** Verified its §10
  exclusion still reads correctly against the widened section.
- **No silent per-host fallback.** If `tikz.sty` is absent, a `tex`/`pdf`
  render of a draft with a figure raises `MissingBinary` rather than
  quietly emitting the ASCII instead. Byte-identical output over
  unchanged input is a product rule here
  (`docs/CODE-STANDARDS.md`, "Repeatable"), and a draft that renders a
  vector figure on one machine and monospace art on another, with
  nothing in the output saying which happened, breaks it. The skills
  probe `kpsewhich tikz.sty` at drafting time so the marker is never
  written on a host that cannot render it.
- **No automatic ASCII fallback on a TikZ compile failure.** The user is
  told to run `draft-reviser`.

## Files this touches

### Already landed (groundwork for this document, not the feature)

- `scripts/release.py` -- `"specs"` added to `EXCLUDE_TOP_LEVEL`, so a
  design doc never ships in `chitragupta-<version>.zip`. The denylist is
  top-level only, so without the entry a new root directory ships by
  default
- `tests/test_release.py` -- `test_excludes_specs`, plus a `specs/` file
  in the synthetic repo fixture. Confirmed to **fail** when the entry is
  removed, so it is not passing vacuously

### Code

- `src/render_output.py` → `src/render_output/` (7 modules)
- `src/render_output/_figures.py` -- the substitution and warnings
- `src/render_output/_cli.py` -- the `draft-reviser` hint on a figure failure

### Tests

- `tests/test_render_output.py` -- new classes for the marker scan, the
  substitution and the warnings; existing 104 references unchanged
- `tests/test_code_standards_scan.py` -- both register entries deleted,
  both pinned counts updated

### Prose

- `docs/WRITING-STANDARDS.md` §10 -- the figure pair, the marker, the
  topic-directory requirement, the citekey prohibition, and that
  originality applies to a redrawn TikZ figure identically ("the same
  violation in different pixels" is already §10's own phrasing)
- `docs/CODE-STANDARDS.md` -- the two register counts
- `.claude/skills/thesis-chapter-writer/SKILL.md` -- step 9 gains the
  TikZ pair, the `kpsewhich` probe and the standalone compile check
- `.claude/skills/draft-reviser/SKILL.md` -- touch a figure, touch both
- `.claude/skills/corpus-reviser/SKILL.md` -- same rule, by reference
- `pyproject.toml` -- MINOR bump (new backward-compatible capability).
  Check the pushed tags, not just `main`, before picking the number

## Test plan

- Unit: marker scan (present, absent, missing target, multiple figures);
  substitution output shape; each warning.
- End-to-end, no mocking, gated on the existing `tikz_available` probe,
  mirroring #226's own two tests: a `.tex` fragment with a figure pair
  renders to `md` **with the ASCII visible**, and to `pdf` with the TikZ
  -- from the same source file in one test module.
- Regression: the fragment on disk still compiles under a bare
  `\documentclass{article}` + `\usepackage{tikz}` document with a real
  `pdflatex` subprocess. This is the test that would have caught the
  `\input{fig.txt}` design, and it is the most valuable one here.
- The 100% line-and-branch coverage bar is unmoved.

## Open risks

- **The two forms can silently disagree.** Mitigated by a rule, not a
  check. Accepted.
- **The docstring redistribution** (above).
- **`texlive-pictures` on a consumer's host.** #226 added it to
  `install_full_pipeline.sh`, but someone who installed before 5.26.0
  and does not re-run it gets a hard pdf failure. The `kpsewhich` probe
  in the authoring path is what keeps that from being written into a
  draft in the first place.
