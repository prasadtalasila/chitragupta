"""Building the pandoc invocation itself: the CSL style a render actually
uses, the argv/environment pandoc runs under, and running it.

Split from `chitragupta/render_output/__init__.py` (#441). Re-exported
from there like every other `_X.py` sibling in this package -- see that
module's own docstring on why the package's attribute surface has to
stay identical to the single module it replaced.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from chitragupta import config
from chitragupta.render_output._csl import _collapsed_csl, _resolve_csl
from chitragupta.render_output._errors import MissingBinary


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


def _has_code_block(text: str) -> bool:
    """Whether a draft has anything that renders as a LaTeX `verbatim`.

    Both spellings, for the reason `_figure_refs` reads both of its own:
    a Markdown draft fences its code and a `.tex` fragment writes the
    environment outright, and this decides whether `fvextra` is loaded
    for either. Deliberately not `citation_gate`'s equivalents -- those
    match a *complete* block in order to blank it, and an unterminated
    fence should still load the package rather than silently not.
    """
    return bool(re.search(r"^[ \t]*(`{3,}|~{3,})", text, re.MULTILINE)) or bool(
        re.search(r"\\begin\{(verbatim|lstlisting|minted)\*?\}", text)
    )


def _pandoc_command(
    safe_md: Path,
    safe_bib: Path,
    csl_path: Path,
    out_path: Path,
    input_path: Path,
    output_format: str,
    documentclass: str,
    fontsize: str,
    papersize: str,
    margin: str,
    figure_refs: list[str],
    fragment: bool = False,
    has_code_block: bool = False,
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
    shape = ["--top-level-division=chapter", "--no-highlight"] if fragment else ["--standalone"]
    cmd = [
        "pandoc",
        str(safe_md),
        *shape,
        # Local image references (`![...](figure.png)`) in the draft are
        # relative to input_path's own directory, not whatever directory
        # this CLI happened to be invoked from. Without this, pandoc's
        # PDF/DOCX writers (which read the image file themselves, unlike
        # the tex writer, which just emits an unverified \includegraphics
        # path) can't find it, and silently replace the image with its
        # alt-text caption instead of erroring -- a wrong-but-successful
        # render that's easy to miss without diffing file sizes.
        "--resource-path",
        str(input_path.resolve().parent),
        "--variable",
        f"documentclass={documentclass}",
        "--variable",
        f"fontsize={fontsize}",
        # Pandoc's own default LaTeX template appends "paper" itself
        # (papersize=a4 -> "...,a4paper,..."); passing "a4paper" here
        # would double up to "a4paperpaper" -- verified empirically
        # against pandoc 3.1.3's default template, not documented
        # anywhere obvious, so don't "fix" this back to "a4paper".
        "--variable",
        f"papersize={papersize}",
        "--variable",
        f"geometry:margin={margin}",
        "--citeproc",
        "--bibliography",
        str(safe_bib),
        "--csl",
        str(csl_path),
        # Gives a long inline code span (a URL, a REST path, a file
        # path) somewhere to break in LaTeX/PDF output -- see the
        # filter's own header comment for why pandoc's default
        # \texttt{...} can't. It no-ops for every other writer
        # (FORMAT ~= "latex"), so it's safe to pass unconditionally.
        "--lua-filter",
        str(config.shipped("assets", "pandoc", "breakable_inline_code.lua")),
    ]
    # Loaded only for a draft that actually has a figure (#222) --
    # pandoc's default LaTeX template has no \usepackage{tikz}, so a bare
    # tikzpicture environment fails with "Environment tikzpicture
    # undefined" without it, but the package load itself is inert for a
    # draft that never draws one, so this stays conditional.
    if figure_refs:  # pragma: no cover-windows
        cmd += ["--variable", r"header-includes=\usepackage{tikz}"]
    # Same shape, same reason, for a draft that has a fenced code block:
    # a LaTeX `verbatim` line is one unbreakable box, so a line wider
    # than the page runs into the margin and `pdflatex` reports an
    # Overfull \hbox. `fvextra`'s `breaklines` wraps it instead, marking
    # each continuation with a `,→` so a wrapped line cannot be misread
    # as two. Both environments are redefined because which one pandoc
    # emits depends on highlighting: a plain fence becomes `verbatim`,
    # and a language-tagged one becomes `Highlighting` (whose
    # `commandchars` has to be carried over, or every highlight macro
    # prints literally).
    #
    # `breaklines` without `breakanywhere`, so a break lands at a space
    # rather than mid-identifier -- checked against this project's own
    # book, where no over-wide line lacks a space before the limit.
    #
    # Conditional for the reason the tikz load is: `fvextra` ships in
    # texlive-latex-extra, and a host with a smaller TeX should not lose
    # a render that works today over a package its draft never needs.
    # A `--fragment` render emits no preamble at all, so this reaches
    # nothing there -- a book supplies it from its own preamble, the
    # same way it supplies the citeproc macros (docs/BOOKS.md).
    if has_code_block:  # pragma: no cover-windows
        cmd += [
            "--variable",
            "header-includes="
            r"\usepackage{fvextra}"
            r"\DefineVerbatimEnvironment{verbatim}{Verbatim}{breaklines}"
            r"\DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\},breaklines}",
        ]
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


def _run_pandoc(cmd: list[str], env: dict[str, str] | None) -> None:
    """Runs pandoc, then forwards any stderr it printed even though it
    exited 0.

    `capture_output=True` was silently discarding it on the success path
    (M-7) -- citeproc's own diagnostics ("citation not found", a missing
    image) land on pandoc's stderr with a zero exit code, not a raised
    `CalledProcessError`, so nothing surfaced them. `check=True` still
    raises on a nonzero exit; that exception already carries its own
    stderr, so this is only for the case a raise never reaches.
    """
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    if result.stderr.strip():
        for line in result.stderr.splitlines():
            print(f"[pandoc] {line}", file=sys.stderr)
