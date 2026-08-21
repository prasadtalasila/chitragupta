"""Stage 7: Pandoc/LaTeX rendering of generated Markdown into PDF/DOCX.

Needs the `pandoc` and TeX Live binaries (apt packages, not pip -- not
installable via pyproject.toml/Poetry or any other venv mechanism). Verified working
on this host (2026-07-28): `pandoc`, `pdflatex`, `latexmk` are all on
PATH. Where they aren't, this stage fails cleanly with MissingBinary
rather than hanging or stack-tracing -- see docker/Dockerfile for a
target that installs them when the host doesn't have root.

Every genre-skill draft cites sources with Pandoc-style `[@citekey]`
markers (see chitragupta/citation_gate.py), so rendering always resolves them via
pandoc's built-in `--citeproc` against `config.BIB_FILE_PATH` -- without
it, citations would come out as literal, unresolved `[@key]` text with no
bibliography. Pandoc's own citation-key tokenizer has a real limitation
that surfaces on this corpus: a double hyphen (`--`) inside a citekey
(bibtexparser produces these, e.g. `zech_digital-twins-as--service_2024`)
truncates the key mid-token, silently losing the citation. `_safe_render_inputs`
works around this by aliasing just the affected citekey(s) in temporary
copies of the input and the bib file -- never touching the real
`bibliography.bib` -- before handing both to pandoc.

Citations render in IEEE style -- numeric `[1]` markers, `[3]-[6]` for a
consecutive run, over a numbered list of complete entries -- via the CSL
style vendored at `assets/csl/ieee.csl` (`config.CSL_STYLE_PATH`,
`--csl` to override). Two notes on how that is wired, both explained
where they're implemented: the collapsing needs one attribute upstream
IEEE omits, injected into a temp copy by `_collapsed_csl` so the vendored
file stays byte-identical to upstream; and a draft's own citekey-labeled
References section (added by `python -m chitragupta.draft references`) has its entries
swapped out in the temp copy by `_swap_manual_refs_for_citeproc` --
heading kept, entries replaced by the anchor citeproc fills in -- so
citeproc's bibliography is the only one in the output, and it appears
under the draft's own heading. citeproc's is the one that can be numbered
consistently with the inline markers, and the one with authors and venues
in it, because it reads `bibliography.bib` directly. Inputs with no such
section (e.g. thesis-chapter-writer's preamble-less `.tex` fragment,
which defers to the user's own thesis-wide bibliography) are unaffected.

`--format md` on a Markdown draft does not go through pandoc at all --
see render() and references.numbered_markdown. Markdown in, Markdown out
is a citation-numbering job, and pandoc's Markdown writer mangles it:
escaped `\\[1\\]` markers and a bibliography wrapped in `:::` fenced divs
and `[...]{.csl-left-margin}` spans, which render as literal punctuation
anywhere that isn't pandoc.

Every format lands beside the draft: `_output_dir` mirrors the draft's
own path under `config.DRAFTS_DIR` into `config.RENDERED_DIR`, so
`content/drafts/dt/survey.md` renders to `content/rendered/dt/survey.*`
and a flat `content/drafts/survey.md` renders to
`content/rendered/survey.*` as it always has. Before that, every format
wrote flat, which lost two things quietly: two topics with a same-named
draft overwrote each other's output, and `dossier export <topic>
--with-rendered` matched nothing, because it matches a rendered file by
its path relative to `RENDERED_DIR`.

**Every path this module reads or writes resolves inside
`config.CONTENT_DIR`**, and the cases that would break that raise
`OutsideContentDir` rather than being quietly redirected. `render()`
checks its input; `_output_dir` checks where the output would land. That
one directory is then the whole record of the work, which is what makes
`dossier export` or a copy of it complete.

Every render also passes documentclass/fontsize/papersize/geometry
variables so a tex/pdf output always opens with a 12pt, a4paper article
class and 1-inch margins via the geometry package -- overridable per
call, but those are the project's fixed defaults.

`python -m chitragupta.draft render <file> --format tex|pdf|...` runs standalone
with bare `python` (no enrich group) -- it depends only on stdlib plus
`chitragupta.config`/`chitragupta.citation_gate`/`chitragupta.references` (all three stdlib-only,
same as this module), deliberately independent of `chitragupta/enrich/__main__.py`,
which drags in the full corpus build and the docling/embed/topic_model
imports for stages this one doesn't need. The genre-writing skills under
`.claude/skills/` call this CLI directly.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from chitragupta import config, references
from chitragupta.render_output._assets import (
    _MD_IMAGE_RE, _URI_SCHEME_RE, _copy_local_images, _copy_local_tex_includes,
    _local_image_refs,
)
from chitragupta.render_output._citeproc import (
    _REFS_ANCHOR, _alias_for, _safe_render_inputs, _swap_manual_refs_for_citeproc,
)
from chitragupta.render_output._csl import _CSL_CITATION_TAG_RE, _collapsed_csl, _resolve_csl
from chitragupta.render_output._errors import MissingBinary, OutsideContentDir, _require
from chitragupta.render_output._figures import (
    _FIGURE_MARKER_MD_RE, _FIGURE_MARKER_TEX_RE, _INPUT_WITH_MARKER_RE, _LATEX_CITE_RE,
    _LATEX_INCLUDE_RE, _TEX_FORMATS, _ascii_alt_refs, _ascii_path,
    _figure_has_citekey, _tikz_path,
    _figure_refs, _figure_warnings, _local_tex_include_refs, _markdown_ascii_refs,
    _require_tikz, _resolve_sibling, _substitute_ascii_for_marker,
    _substitute_ascii_for_tikz, _substitute_tikz_for_ascii,
    _tikz_alt_refs, _with_figures_for,
)
from chitragupta.render_output._cli import main
from chitragupta.render_output._paths import _MARKDOWN_SUFFIXES, _output_dir

# Everything above is re-exported deliberately, not incidentally. Every
# caller in this repository reaches these off the module
# (`from chitragupta import render_output`, then `render_output._output_dir`), and
# the tests reach eleven of the private helpers that way too. Keeping the
# package's name and its attribute surface identical to the single module
# it replaced is what makes the split invisible to all 104 of those
# references -- a rename would have been a second, unrelated change
# smuggled into a refactor.
__all__ = ["MissingBinary", "OutsideContentDir", "render", "main"]


def _target_dir(input_path: Path, output_dir: str | Path | None) -> Path:
    """Where this render lands: the mirrored default, or the caller's own.

    A caller naming a directory does not widen where this pipeline may
    write -- `output_dir` is confined to `content/` exactly like the
    mirrored default it replaces.
    """
    if output_dir is None:
        return _output_dir(input_path)
    out_dir = Path(output_dir)
    if not config.resolves_inside(out_dir, config.CONTENT_DIR):
        raise OutsideContentDir(
            f"{out_dir} resolves to {out_dir.resolve()}, outside the content "
            f"directory {config.CONTENT_DIR.resolve()}. Naming an output "
            "directory does not widen where this pipeline may write -- see "
            "config.require_inside_content, and point [content].dir "
            "(config.toml) at the tree you are really working in."
        )
    return out_dir


def _copy_local_assets(input_path: Path, dest_dir: Path) -> None:
    """Every local file the draft references, copied beside the output.

    The two kinds travel together on every path that produces output, so
    they are called together rather than separately at each site -- one of
    them being forgotten is precisely how a `tex` output stops compiling
    on its own.
    """
    _copy_local_images(input_path, dest_dir)
    _copy_local_tex_includes(input_path, dest_dir)


def _render_csl(  # pragma: no cover-windows
    csl: str | Path | None, collapse_citations: bool | None, tmp_dir: Path
) -> Path:
    """The CSL style this render actually hands pandoc.

    `MissingBinary` rather than a new exception type, even though a style
    file isn't a binary: it is the same class of failure (a render input
    this host doesn't have), and every genre skill's documented behaviour
    is to warn-and-continue on the `[missing-binary]` prefix `main()`
    prints for it, rather than blocking the draft. A new type would need
    its own handler here and a matching line in all five SKILL.md files
    to get the same outcome.
    """
    csl_path = _resolve_csl(csl) if csl is not None else config.CSL_STYLE_PATH
    if not csl_path.is_file():
        raise MissingBinary(
            f"CSL style not found at {csl_path}. A relative --csl is looked for "
            "under the current directory first, then the repo root. The IEEE "
            "style ships with this repo at assets/csl/ieee.csl -- pass --csl to "
            "point somewhere else, or see assets/csl/README.md to re-fetch it."
        )
    if collapse_citations is None:
        collapse_citations = config.RENDER_COLLAPSE_CITATIONS
    return _collapsed_csl(csl_path, tmp_dir) if collapse_citations else csl_path


def _pandoc_command(
    safe_md: Path, safe_bib: Path, csl_path: Path, out_path: Path, input_path: Path,
    output_format: str, documentclass: str, fontsize: str, papersize: str, margin: str,
    figure_refs: list[str], fragment: bool = False,
) -> tuple[list[str], dict[str, str] | None]:
    """The pandoc argv and the environment to run it in."""
    # A fragment is for `\input` into a larger document, so it gets no
    # preamble and no `\begin{document}` -- and its own `#` heading is
    # that document's chapter, not a section, which is why the two flags
    # travel together (docs/BOOKS.md's assembly step is the caller).
    # Everything else is unchanged: the citations are still resolved by
    # citeproc against the same CSL, so a fragment carries its own IEEE
    # reference list under its own heading rather than deferring to a
    # bibliography at the end of the book.
    # `--no-highlight` travels with it for the same reason: pandoc's
    # syntax-highlighting output uses `Shaded`/`Highlighting` environments
    # that only the standalone template defines, so a highlighted fragment
    # fails to compile in the book that \input-s it. Plain `verbatim` is
    # what a fragment can promise. The citeproc macros are the one
    # exception a book must supply itself -- see docs/BOOKS.md.
    shape = (["--top-level-division=chapter", "--no-highlight"]
             if fragment else ["--standalone"])
    cmd = [
        "pandoc", str(safe_md), *shape,
        # Local image references (`![...](figure.png)`) in the draft are
        # relative to input_path's own directory, not whatever directory
        # this CLI happened to be invoked from. Without this, pandoc's
        # PDF/DOCX writers (which read the image file themselves, unlike
        # the tex writer, which just emits an unverified \includegraphics
        # path) can't find it, and silently replace the image with its
        # alt-text caption instead of erroring -- a wrong-but-successful
        # render that's easy to miss without diffing file sizes.
        "--resource-path", str(input_path.resolve().parent),
        "--variable", f"documentclass={documentclass}",
        "--variable", f"fontsize={fontsize}",
        # Pandoc's own default LaTeX template appends "paper" itself
        # (papersize=a4 -> "...,a4paper,..."); passing "a4paper" here
        # would double up to "a4paperpaper" -- verified empirically
        # against pandoc 3.1.3's default template, not documented
        # anywhere obvious, so don't "fix" this back to "a4paper".
        "--variable", f"papersize={papersize}",
        "--variable", f"geometry:margin={margin}",
        "--citeproc", "--bibliography", str(safe_bib),
        "--csl", str(csl_path),
    ]
    # Loaded only for a draft that actually has a figure (#222) --
    # pandoc's default LaTeX template has no \usepackage{tikz}, so a bare
    # tikzpicture environment fails with "Environment tikzpicture
    # undefined" without it, but the package load itself is inert for a
    # draft that never draws one, so this stays conditional.
    if figure_refs:  # pragma: no cover-windows
        cmd += ["--variable", r"header-includes=\usepackage{tikz}"]
    env = None
    if output_format == "pdf":  # pragma: no cover-windows
        cmd += ["--pdf-engine", "pdflatex"]
        # LaTeX's own \input/\include search path is separate from
        # --resource-path above (that's pandoc's, for images pandoc
        # reads itself). Without TEXINPUTS, pdflatex looks for
        # figures/fig1.tex relative to its own working directory, not
        # the draft's -- confirmed failing with "! LaTeX Error: File
        # 'figures/fig1.tex' not found" otherwise. The trailing ':' is
        # not optional: TEXINPUTS is a prefix, not a replacement, and
        # dropping it loses the default search path pdflatex needs for
        # its own style files. Merges with os.environ rather than
        # replacing it -- env={"TEXINPUTS": ...} alone drops PATH, and
        # the subprocess can't find pandoc at all.
        env = {**os.environ, "TEXINPUTS": f"{input_path.resolve().parent}:"}
    cmd += ["-o", str(out_path)]
    return cmd, env


def render(
    input_path: str,
    output_format: str = "pdf",
    documentclass: str = "article",
    fontsize: str = "12pt",
    papersize: str = "a4",
    margin: str = "1in",
    csl: str | Path | None = None,
    collapse_citations: bool | None = None,
    output_dir: str | Path | None = None,
    fragment: bool = False,
) -> Path:
    """Renders `input_path` (Pandoc markdown) to `output_format` (pdf/tex/docx/...).

    The output lands in `_output_dir(input_path)` -- `content/rendered/`
    with the draft's own place under `content/drafts/` mirrored into it.

    `output_dir` overrides that, for a caller rendering something that is
    not a draft and so has no business in `content/rendered/`:
    `chitragupta/review/__init__.py` passes the review report's own directory so a
    report's `.tex`/`.pdf` land beside its `.md` rather than in the
    drafting layer's publish output. It is confined to `content/` like
    every other path this module writes, and it is the caller's whole
    answer -- nothing is mirrored into it, because the caller has already
    done that.

    Citations and the bibliography are formatted with `csl` (default:
    `config.CSL_STYLE_PATH`, the vendored IEEE style), so a rendered draft
    carries numeric markers -- `[1]`, and `[3]-[6]` for a consecutive run
    when `collapse_citations` (default: `config.RENDER_COLLAPSE_CITATIONS`)
    -- over a numbered reference list of complete entries. Without a
    `--csl`, pandoc falls back to Chicago author-date, which is what this
    rendered before.

    `--standalone` is passed so a `tex` output is a complete, compilable
    LaTeX document (documentclass + preamble), not a bare fragment --
    matching what pandoc already builds internally on the way to a `pdf`
    output. `fragment=True` is the exception, for a unit destined to be
    `\\input` into a book (docs/BOOKS.md): no preamble, and its own top
    heading becomes a `\\chapter`. `documentclass` defaults to LaTeX's
    plain `article`
    class, the right shape for the short, section-based genre drafts this
    project produces (no chapters, no front matter); pass a different
    value only if a specific draft genuinely needs one. `fontsize`/
    `papersize`/`margin` default to this project's fixed house style --
    `\\documentclass[12pt,a4paper]{article}` plus
    `\\usepackage[margin=1in]{geometry}`.
    """
    input_path = config.require_inside_content(Path(input_path))
    out_dir = _target_dir(input_path, output_dir)
    # Read once, here, and thread it through everything below. Three
    # separate `.read_text()` calls used to answer three questions about
    # the same draft; once a figure substitution rewrites the copy pandoc
    # sees, "the draft" and "what is being rendered" are different strings
    # and any two of them can disagree.
    draft_text = input_path.read_text(encoding="utf-8")
    # Before the early return below, so a Markdown draft rendered to
    # Markdown -- the one path that never reaches pandoc -- still reports
    # a figure whose marker or twin is wrong.
    for warning in _figure_warnings(draft_text, input_path):
        print(f"[figure] {warning}", file=sys.stderr)
    if output_format == "md" and input_path.suffix.lower() in _MARKDOWN_SUFFIXES:
        # Markdown in, Markdown out: this is a citation-numbering job, not
        # a format conversion, and pandoc is the wrong tool for it. Its
        # Markdown writer escapes every marker (`\[1\]`, because `[1]`
        # could be a link reference) and emits citeproc's bibliography as
        # `::: {#refs}` fenced divs full of `[...]{.csl-left-margin}`
        # spans -- all of which render as literal punctuation anywhere
        # that isn't pandoc, which is the whole audience for a .md.
        #
        # A LaTeX input still goes through pandoc below: converting a
        # thesis fragment's `\citep{...}` into Markdown genuinely is a
        # format conversion, and that fragment deliberately carries no
        # reference list of its own.
        _copy_local_assets(input_path, out_dir)
        return references.write_numbered(
            input_path, out_dir, _with_figures_for(draft_text, input_path, output_format),
        )

    # Everything from here on needs the real pandoc/pdflatex/TeX Live
    # toolchain to exercise -- see #291. Marked per-line rather than by
    # extracting a helper, since there is no single enclosing block to tag
    # and this trailing tail is otherwise ordinary sequential code.
    _require("pandoc")  # pragma: no cover-windows
    if output_format == "pdf":  # pragma: no cover-windows
        _require("pdflatex")
    figure_refs = _figure_refs(draft_text)  # pragma: no cover-windows
    if figure_refs and output_format in _TEX_FORMATS:  # pragma: no cover-windows
        _require_tikz()

    out_dir.mkdir(parents=True, exist_ok=True)  # pragma: no cover-windows
    _copy_local_assets(input_path, out_dir)  # pragma: no cover-windows
    out_path = out_dir / f"{input_path.stem}.{output_format}"  # pragma: no cover-windows

    with tempfile.TemporaryDirectory() as tmp:  # pragma: no cover-windows
        safe_md, safe_bib = _safe_render_inputs(
            input_path, config.BIB_FILE_PATH, Path(tmp),
            _with_figures_for(draft_text, input_path, output_format),
        )
        cmd, env = _pandoc_command(
            safe_md, safe_bib, _render_csl(csl, collapse_citations, Path(tmp)),
            out_path, input_path, output_format, documentclass, fontsize,
            papersize, margin, figure_refs, fragment,
        )
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)

    return out_path  # pragma: no cover-windows
