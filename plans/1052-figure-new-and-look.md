# 🖼 XII-2a: `chitragupta figure new` and `chitragupta figure look`

Status: **built.** Written 2026-10-29 against `main` at `227d7e6`,
from a brainstorming session on issue
[#1052](https://github.com/prasadtalasila/chitragupta/issues/1052), and
built in the same PR as this plan (the user asked for one PR, not a plan
PR first, as for #1053). Decisions marked *user* were put to the user
and answered in that session; the rest were the session's proposals,
approved section by section. What changed on the way is in **Changed in
the build** at the end.

**Written for** whoever builds #1052: a session that changes
`chitragupta/figure/`, `chitragupta/render_output/`,
`chitragupta/doctor.py`, the `figure-drawer` skill, `tests/` and
`docs/`, and is therefore governed by `DEVELOPER-AGENTS.md` and
`docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` ("The commands" and
phase 2), `plans/1053-figure-check-skeleton.md` (the `figure check`
command this sits beside), `docs/TIKZ-STYLE.md`, the figure-layout probe
in `chitragupta/review/figure_layout/_probe.py`, and the render in
`chitragupta/render_output/`.

**Not covered here:** `.txt` twins for the scaffolds (2e, #1056); the
`SKILL.md` router rewrite (1c, #1048); cropping a draft page to the
figure on it; PNG figures for the md, docx or html renders; any new gate.

## Where it lands

`main`, in one PR with the code (*user*). The v3 plan's integration
branch is folded back into `main`.

## What it is for

Two hand-assembled steps of the `figure-drawer` skill become one command
each:

- **Step 2** is `cp assets/tikz/<layout>.tex figures/<name>.tex` and
  then `figure sync` on it. The agent has to know the scaffold's path,
  remember the sync, and nothing stops the `cp` overwriting a figure.
- **Step 9** is a full pdf render, then guessing which page holds the
  figure, then `pdftoppm` on that page. It cannot be done before the
  draft carries the figure's marker, and it is the step that is skipped.

A figure that passes the compile probe and `figure check` can still
print with a hyphenated label, an arrow through a zone title, or
cramped boxes. Only looking catches those, and this item makes looking
one command.

## Decisions

| Question | Decision |
| --- | --- |
| A layout with no `.txt` twin (none ships one before 2e) | Copy the twin when the layout has one; otherwise write only the `.tex` and print one line saying a twin is still needed. 2e's twins are picked up with no code change |
| Where the look files go (*user*) | Mirrored under `content/rendered/`, like the render's own output: `content/drafts/rag/figures/flow.tex` looks to `content/rendered/rag/figures/`. Never into the draft's directory |
| Names (*user*) | `<stem>.look.pdf` and `<stem>.look.png` for the figure alone, `<stem>.page.png` for its page in the draft, and `<stem>.look.json` for bookkeeping |
| Crop (*user*) | The look PDF's page is the figure's own box plus a 1pt border, not an A4 page. The figure is still set at the render's text width |
| Resolution (*user*) | 300 dpi for every PNG, new or regenerated, look and page alike. Never scaled to a maximum size, so pixel size is proportional to the figure's real size |
| When looks are rebuilt (*user*) | Every pdf `draft render` refreshes the looks of every figure the draft references, rebuilding only figures whose inputs changed. The page PNGs are rebuilt on every pdf render, since any text edit can move a figure |
| Finding a figure's page (*user*) | A hidden PDF named destination, `cgfig:<base>`, just before each figure's `\input`, read back with `pdfinfo -dests`. It is a jump target, not a bookmark: the outline is unchanged |
| The hairline | Drawn only when the figure is wider than the text width, at the text width from the figure's left edge. A figure that fits gets no line; the command prints its width beside the text width |

The anchor was chosen over two alternatives. A `\typeout` of the page
number runs when a float is *built*, not when it is placed, so it names
the wrong page for any figure that drifts, and pandoc does not return
the engine's log in any case. Searching the PDF's text for the caption
is fragile: the caption repeats in a List of Figures, hyphenates, and
can resemble another. hyperref's own `figure.N` destination is named by
the figure's number, which moves whenever a figure is added before it.

## The commands

All exit 0 whatever they find, except on a usage error or a missing
toolchain (2), as `figure check` does.

### `chitragupta figure new <figures-dir> <name> --layout <id>`

```text
$ chitragupta figure new content/drafts/rag/figures flow --layout zoned-spine
created  content/drafts/rag/figures/flow.tex   (from zoned-spine)
no twin  zoned-spine ships no .txt twin; write content/drafts/rag/figures/flow.txt
figure sync: 1 current
```

1. **Arguments.** `<name>` is a bare stem (`[\w-]+`): no path, no
   suffix. `<figures-dir>` is named `figures`, the rule `figure sync`'s
   walk and WRITING-STANDARDS §10 use, so the figure is never invisible
   to `sync` and the render. `--layout` is one of the ids below; an
   unknown one is a usage error that lists them.
2. **Layout ids** are the stems of the shipped `assets/tikz/*.tex`
   whose own `% cg-layout:` line (added by #1057, read by
   `figure/_layout.declared_layout`) names that stem. That leaves out
   `cg-figstyle.tex`, and a phase 3 scaffold becomes an id the moment it
   ships. Found through `config.shipped`, as `figure sync` finds the
   house block, so a checkout and an install behave alike.
3. **Refuses to overwrite.** An existing `<name>.tex` or `<name>.txt`,
   or a symlink at either path, is exit 2 with nothing written.
4. **Copies** the scaffold, `% cg-layout:` line and all, and its twin
   when `<id>.txt` exists beside it.
5. **Syncs** the new file through `figure/_sync.sync_file`, so a
   scaffold whose block is older than the installed one is refreshed.

An unreadable house block or scaffold is exit 2 naming `chitragupta
doctor`. Nothing here needs TeX.

### `chitragupta figure look <figure.tex> [--draft <draft>]`

```text
$ chitragupta figure look content/drafts/rag/figures/flow.tex
wrote    content/rendered/rag/figures/flow.look.pdf   (431 x 180pt; text width 453pt)
wrote    content/rendered/rag/figures/flow.look.png   (1804 x 758 px at 300 dpi)
```

A second run on an unchanged figure prints `current` for both. A figure
wider than the text says `(470 x 120pt; 17pt past the text width, line
drawn)`.

**The document.** Built in `figure/_look.py`, beside the probe's
`scaffold()` and in its idiom:

```latex
\documentclass[12pt,a4paper]{article}
\usepackage[margin=1in]{geometry}          % \textwidth = the render's 453pt
\usepackage{fontspec}\usepackage{unicode-math}
<pdf_fonts.latex_fonts()>                  % the render's fonts, as the probe sets them
\usepackage{tikz}\usetikzlibrary{<libraries_in(source)>}
\begin{document}
\setbox\cgfigbox=\hbox{%
<the figure's source>%
}%
\typeout{CGLOOK <wd> <ht> <dp> <textwidth>}%
<page sized to the box plus 1pt; the box shipped at the corner; the
hairline overlaid when wd > textwidth>
\end{document}
```

- The libraries are preloaded, as the render loads them (#781): a load
  inside the box adds stray width (#1046), which the look must not show.
- The source is inlined, as the probe does, so the read fence has no
  second file to admit. TeX's own `\setbox...\hbox` for the reason
  `scaffold()` gives (`\sbox` freezes `&`'s catcode for a `matrix`).
- The page is sized by setting LuaTeX's `\pagewidth`/`\pageheight` and
  shipping the box at the page corner; no `standalone` class, which
  `_require_tikz` does not check for (the probe's reason).
- Engine: `lualatex` with `tex_engine.engine_opts()` and `engine_env()`,
  in a temporary directory, through this module's own `_run` patch
  point (#854).

**The files.** In `render_output._paths._output_dir(<figure>)`, the
render's own rule, so a figure outside `content/drafts/` (a scaffold
under `assets/tikz/`) lands flat in `content/rendered/`:

1. `lualatex look.tex` writes `look.pdf`, the cropped vector page.
2. `pdftoppm -r 300 -png -singlefile look.pdf look` writes `look.png`.
3. Both are written atomically as `<stem>.look.pdf` and
   `<stem>.look.png`, then `<stem>.look.json`.

**Only what changed.** `<stem>.look.json` holds a digest of the inputs
(the figure's bytes, `pdf_fonts.latex_fonts()`, the document's version
and the dpi) and what was measured (width, height and text width in
pt, and the PNG's pixel size). When the digest matches and all three
files exist, nothing is compiled and the lines say `current`.

**A figure that does not compile** prints TeX's first `!` line (the
probe's `_compile_error_detail`), deletes the figure's old `.look.*`
files so no stale preview outlives the failure, and exits 0.

**`--draft <draft>`** renders the draft to pdf through the same path as
`draft render` (below), then prints the lines for this figure, page PNG
included:

```text
wrote    content/rendered/rag/survey.pdf
current  content/rendered/rag/figures/flow.look.pdf   (431 x 180pt; text width 453pt)
current  content/rendered/rag/figures/flow.look.png   (1804 x 758 px at 300 dpi)
wrote    content/rendered/rag/figures/flow.page.png   (page 4 of survey.pdf; 2480 x 3508 px)
```

A draft with no marker for the figure says so, and the standalone look
is still written. A draft that does not render prints the render's
`[error]` line; both exit 0.

## In the render

**The anchor.** For **pdf** output only, `render_output/_figure_anchor.py`
puts

```latex
\pdfextension dest name{cgfig:figures/flow} xyz\relax
```

on the line before each figure's `\input`: in a Markdown draft, where
`_substitute_tikz_for_ascii` swaps the marker for the `\input`; in a
`.tex` draft, before each `\input` that carries a `% figure:` marker.
Not for tex output, which a user may compile with pdfLaTeX, where
`\pdfextension` does not exist. A base outside `[\w./-]+` gets no
anchor, so a TeX special in a name cannot reach the engine.

**After a pdf render**, `render_output/_cli.py` (the `draft render`
command) calls `figure/_look.refresh_for_draft(draft, pdf)`:

- every figure the draft references gets its look refreshed, rebuilt
  only where its digest changed;
- `pdfinfo -dests <pdf>` gives each `cgfig:` anchor's page, and
  `pdftoppm -r 300 -f N -l N -png -singlefile` writes `<stem>.page.png`.
  A figure with no anchor in the PDF (its marker did not resolve, so it
  never printed) gets its old page PNG deleted and a note.

None of it can fail the render: every outcome is a stderr note under
the render's own `[prefix]` convention, after the render succeeded, and
stdout's last line stays the output path that callers read:

```text
[figure-look] 1 wrote, 1 current; 2 page PNGs
[figure-look] skipped: pdftoppm not found on PATH (chitragupta install os-deps)
```

**Why in the CLI and not in `render()`**, which the design first said:
`render_output/__init__.py` sits at exactly the 250-line ceiling, and
`render()`'s other callers (`review/__init__.py`'s reports and
`evidence_appendix.py`) render documents that carry no figures. Every
draft, the book included, is rendered through `draft render`. The
import is deferred inside the CLI function, the pattern `_cli.py`
already uses for `render` itself, because `figure` imports from
`render_output` and a module-scope import back would be a cycle.

## Errors and exit codes

| Situation | `figure new` | `figure look` | pdf `draft render` |
| --- | --- | --- | --- |
| Bad arguments | 2, nothing written | 2 | n/a |
| Target exists, or is a symlink | 2, nothing written | n/a | n/a |
| Figure unreadable or not UTF-8 | n/a | 2 | n/a |
| Shipped scaffold or house block unreadable | 2, names `doctor` | n/a | n/a |
| No `lualatex` or `tikz.sty` | n/a | 2, nothing written | fails, as today |
| No `pdftoppm` | n/a | 2, nothing written | renders; a note |
| No `pdfinfo` | n/a | without `--draft` unaffected; with it, no page PNG, a note, 0 | renders; a note |
| Figure does not compile | n/a | first `!` line, old `.look.*` deleted, 0 | renders; that look reported failed |
| Draft does not render (`--draft`) | n/a | the render's `[error]`, 0 | fails, as today |
| Cannot write under `content/rendered/` | n/a | the reason, 2 | as today |

`look` needs `pdftoppm` because its PNG is the deliverable; the render
does not, because its looks are extras and never a reason a render that
succeeded before fails now.

`chitragupta doctor` adds `pdftoppm` and `pdfinfo` to `BINARIES` beside
`pdftotext`: all three are poppler-utils, which `install os-deps`
already installs.

## Tests

100% line and branch coverage holds. Toolchain-only lines carry
`# pragma: no cover-windows`, as `figure check`'s do.

- `tests/test_figure_new.py`: every layout id copies and syncs; refusals
  (existing `.tex` or `.txt`, a symlink, a name with a path or suffix, a
  directory not named `figures`, an unknown layout listing the ids); a
  twin copied when a fixture layout ships one, the no-twin line when
  not; an unreadable house block is 2.
- `tests/test_figure_look.py`: with `_run` faked, the document's text,
  the hairline only when too wide, `current` when the digest matches,
  a rebuild when the figure, the fonts or the dpi change, `.look.*`
  deleted after a failed compile, the mirrored and the flat output
  directory, exit 2 per missing tool. With `@needs_tikz` real compiles:
  the PDF page is the figure's box plus 2pt each way, the PNG's pixels
  are that size at 300 dpi, and the text width matches `render()`'s
  defaults (as `figure check`'s `DEFAULT_WIDTH_PT` is pinned).
- `tests/test_render_output_figure_anchor.py`: the anchor for pdf
  output only, in a Markdown and a `.tex` draft; `pdfinfo -dests` finds
  a figure's page, including one that floats onto the next page; a
  render with anchors and one without set every word in the same place
  (`pdftotext -bbox`); page PNGs written, an orphan deleted, missing
  poppler tools only a note.
- `tests/test_doctor.py`: `pdftoppm` and `pdfinfo` reported.

## Docs and the skill

- `docs/CLI.md`: `figure new` and `figure look` sections in the
  existing shape (prose, examples, sample output, flag and exit tables),
  and the `[figure-look]` notes in `draft render`'s section.
- `docs/FIGURE-DRAWER.md` and `docs/TIKZ-STYLE.md`: the manual look and
  the `cp` replaced by the commands.
- `plans/fig-xii-figure-drawer-v3.md`: `c1`'s exemption spelled
  `hub-and-spoke-network`, the id the scaffold declares.
- The `figure-drawer` skill, all three harness copies: step 2 becomes
  `figure new`; step 9 becomes `figure look`, then `--draft` once the
  marker is in, then view the PNG. The fallback stays: a host that
  cannot view an image says so and carries on. Only these two steps
  change; the router rewrite is 1c.

## Build order

Test first at each step, red before green.

1. `figure new`: `_new.py`, the subparser, its tests.
2. The look document and compile: `_look.py`'s document, the real
   compile tests for crop and pixel size, then the digest.
3. `figure look` CLI without `--draft`, exit codes.
4. The anchor in `render_output`, and the layout-unchanged test.
5. `refresh_for_draft`, the `draft render` hook, page PNGs, notes.
6. `look --draft`.
7. `doctor`, docs, the skill copies, the version bump (MINOR: two new
   commands).

## Changed in the build

- **The `% cg-layout:` lines were already there.** #1057 landed between
  the design and the build and gave every scaffold its line, with the
  file stem as the id, and `figure/_layout.declared_layout` to read it.
  `figure new` reuses both rather than adding either.
- **The mark goes after the figure, not before it.** Placed before the
  `\input`, it sat alone in the main vertical list with no glue between
  it and the paragraph above, which removes a page break TeX could
  take. Inside the figure's own paragraph it rides on the figure's last
  line. `tests/test_render_output_figure_anchor.py` compares every
  word's position, over three placements, with and without marks.
- **The mark travels in a raw ` ```{=latex} ` block, with the
  `\input`.** In Markdown text pandoc escapes the braces of a command it
  does not know, which breaks the mark.
- **No mark in a `.tex` draft.** Pandoc reads one through its LaTeX
  reader, which turns an unknown command into printed text (checked with
  pandoc 3.7). A `.tex` draft's figures get a look and no page picture,
  and the note says so.
- **The hook is in `draft render`'s CLI**, as the plan's "Why in the CLI"
  says, through a split of its `main` into `_rendered` and `main`, so
  `figure look --draft` renders through exactly the same refusals.
- **A look and a page are independent.** A figure whose look fails still
  gets its page picture, and the reverse.
- **`figure new` creates a missing `figures/`** whose parent exists, so
  a draft's first figure needs no `mkdir`.
- **A page is 2481 x 3508 px**, not 2480: pdftoppm rounds a page's pixel
  size up, and A4's 595.28pt is 2480.3 px at 300 dpi.
