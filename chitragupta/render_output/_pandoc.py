"""Building the pandoc invocation itself: the CSL style a render actually
uses, the argv/environment pandoc runs under, and running it (#441).
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from chitragupta import config, install, pdf_fonts, programs, tex_engine
from chitragupta.render_output._csl import _collapsed_csl, _resolve_csl
from chitragupta.render_output._errors import MissingBinary, _require
from chitragupta.render_output import _floats, _index_terms, _tex_preview, _unit_labels
from chitragupta.render_output._tables import _LATEX_BOUND
from chitragupta.render_output._tikz_libraries import header_include, preamble_libraries
from chitragupta.render_output._unicode import font_header_path

# A table caption's width. pandoc writes tables as `longtable`, whose captions
# use `\LTcapwidth`, hardcoded to 4in, not `\textwidth`, so captions wrapped in
# the middle of the line (measured). Guarded with `\ifdefined` because the
# template loads `longtable` only when there is a table, and an unguarded
# `\setlength` would be an `Undefined control sequence`. LaTeX-bound only:
# HTML's template puts `header-includes` in `<head>`. A fragment's book sets it
# in its own preamble (book-assembler's SKILL.md).
_LONGTABLE_CAPTION_WIDTH = (
    r"header-includes=\ifdefined\LTcapwidth\setlength{\LTcapwidth}{\textwidth}\fi"
)

# chitragupta's pdf engine (#996): LuaLaTeX prints any character some font has.
# Over XeLaTeX for luaotfload's fallback chains; XeLaTeX's per-script switching
# still dropped Devanagari and symbols (plans/996-unicode-pdf-engine.md).
PDF_ENGINE = "lualatex"


def _render_csl(  # pragma: no cover-windows
    csl: str | Path | None, collapse_citations: bool | None, tmp_dir: Path
) -> Path:
    """The CSL style this render actually hands pandoc.

    `MissingBinary`, not a new type: the same class of failure (a missing
    render input), which every genre skill already warns-and-continues on.
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

    Both the Markdown fence and the `.tex` environment. Not `citation_gate`'s
    matchers: those need a complete block, but an unterminated fence should
    still load `fvextra`.
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
    preamble_files: list[Path] | None = None,
    index_terms: str | Path | None = None,
    defer_citations: bool = False,
) -> tuple[list[str], dict[str, str] | None]:
    """The pandoc argv and the environment to run it in.

    `defer_citations` takes a fragment's `--natbib` citations but none of its
    shape. `draft diff` renders both versions this way so latexdiff compares
    `\\citep{key}` with `\\citep{key}`; resolved numbers would shift and every
    renumbering would read as a change (plans/1194-draft-diff.md).
    """
    deferred = fragment or defer_citations
    # A fragment is `\input` into a larger document: no preamble, its `#` is a
    # chapter. Citations are deferred (`--natbib`) to one bibtex pass over the
    # whole book: per-unit citeproc gave two chapters the same `[2]` for different
    # sources (measured). The book supplies the style and `\bibliography{...}`.
    # `--no-highlight` too: `Shaded`/`Highlighting` exist only in the standalone
    # template, so a highlighted fragment fails in the book (see book-assembler's
    # references/latex-conventions.md).
    shape = ["--top-level-division=chapter", "--no-highlight"] if fragment else ["--standalone"]
    cmd = [
        "pandoc",
        str(safe_md),
        *shape,
        *_unit_labels.pandoc_args(input_path, fragment),
        *_index_terms.pandoc_args(input_path, index_terms, out_path.parent),
        # Images are relative to the draft's directory. Without this, pandoc's
        # PDF/DOCX writers silently replace a missing image with its alt text.
        "--resource-path",
        str(input_path.resolve().parent),
        "--variable",
        f"documentclass={documentclass}",
        "--variable",
        f"fontsize={fontsize}",
        # The template appends "paper" itself; "a4paper" here would become
        # "a4paperpaper" (pandoc 3.1.3). Don't "fix" this back to "a4paper".
        "--variable",
        f"papersize={papersize}",
        "--variable",
        f"geometry:margin={margin}",
        # Straight before `--citeproc` (filters run in argv order): a `.bib`
        # field's raw TeX (`\directlua{...}`) then prints as text, leaving the
        # author's prefix/suffix untouched (#1022). Before breakable_inline_code.lua
        # too, or a `\texttt` in a `.bib` title shows its `\penalty0` breaks. A
        # fragment has no reference list here to rewrite.
        *(
            []
            if deferred
            else [
                "--lua-filter",
                str(config.shipped("assets", "pandoc", "bib_raw_tex_as_text.lua")),
            ]
        ),
        # `--natbib` and `--citeproc` are alternatives, not additions:
        # one defers every citation to LaTeX, the other resolves it here.
        *(["--natbib"] if deferred else ["--citeproc", "--csl", str(csl_path)]),
        "--bibliography",
        str(safe_bib),
        # Lets a long inline code span break in LaTeX (see the filter's header);
        # a no-op for other writers, so safe unconditionally.
        "--lua-filter",
        str(config.shipped("assets", "pandoc", "breakable_inline_code.lua")),
    ]
    # A deferred standalone render names its own style (the template default
    # is author-year `plainnat`): IEEEtran with compressed numeric natbib,
    # matching the IEEE CSL of a plain render.
    if defer_citations:
        cmd += [
            "--variable",
            "biblio-style=IEEEtran",
            "--variable",
            "natbiboptions=numbers,sort&compress",
        ]
    # `tikz` only for a draft with a figure (#222); the template lacks it. The
    # libraries ride in the same string (#781; see `_tikz_libraries.py`). Not
    # gated on `_LATEX_BOUND`, matching the tikz load: html already gets this in
    # `<head>`, and changing that would be a second, unrelated fix.
    if figure_refs:  # pragma: no cover-windows
        cmd += [
            "--variable",
            "header-includes="
            + header_include(
                preamble_libraries(figure_refs, input_path.parent, fragment, output_format)
            ),
        ]
    # A fenced code block: `verbatim` lines are unbreakable boxes that overrun the
    # margin, so `fvextra`'s `breaklines` wraps them with a `,→` marker. Both
    # `verbatim` and `Highlighting` are redefined (the latter keeping its
    # `commandchars`, or highlight macros print literally). No `breakanywhere`,
    # so breaks fall at spaces. Conditional, like tikz, because `fvextra` is
    # texlive-latex-extra; a fragment's book supplies it itself.
    if has_code_block:  # pragma: no cover-windows
        cmd += [
            "--variable",
            "header-includes="
            r"\usepackage{fvextra}"
            r"\DefineVerbatimEnvironment{verbatim}{Verbatim}{breaklines}"
            r"\DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\},breaklines}",
        ]
    # `_unicode.preamble_files`: the `.sty` for a `.tex` (#948) and the project's
    # unicode-extra.tex. A file per -H, which pandoc emits after header-includes,
    # the order the .sty needs (after amssymb).
    for path in preamble_files or []:
        cmd += ["--include-in-header", str(path)]
    # A `.tex` draft's preview setup (#1164, #1120); before the font header,
    # which stays last. `_tex_preview` has why.
    cmd += _tex_preview.pandoc_args(input_path, output_format, fragment)
    # Where a figure may float (#1065): every standalone LaTeX-bound render,
    # and a copy beside a fragment that draws one. `_floats` has why.
    cmd += _floats.preamble_args(output_format, fragment, figure_refs, out_path.parent)
    if output_format in _LATEX_BOUND:  # pragma: no cover-windows
        cmd += ["--variable", _LONGTABLE_CAPTION_WIDTH]
    env = None
    if output_format == "pdf":  # pragma: no cover-windows
        _require_tex_readable_tmpdir()
        cmd += ["--pdf-engine", PDF_ENGINE]
        # Last in the preamble: sets the fonts and fallback chain itself, since
        # apt's pandoc 3.1.3 template lacks `mainfontfallback`.
        cmd += [
            "--include-in-header",
            str(font_header_path()),
        ]
        # No `\write18` at all, not even TeX Live's restricted allow-list: that is
        # still document-chosen code execution (#823). Casualty: `.eps` conversion
        # (docs/SECURITY.md says use PDF/PNG). The read fence rides along
        # (`tex_engine`, #1037).
        cmd += [f"--pdf-engine-opt={opt}" for opt in tex_engine.engine_opts()]
        # LaTeX's own \input search path, separate from --resource-path, so
        # figures/x.tex resolves from the draft's directory. The trailing separator
        # keeps the default path for style files; it is os.pathsep because TeX on
        # Windows uses ';' and ':' would split the drive letter (#950). Merged with
        # os.environ, or PATH is lost and pandoc is not found.
        env = tex_engine.engine_env({"TEXINPUTS": f"{input_path.resolve().parent}{os.pathsep}"})
        # Reads outside the draft are refused (#823), or a `.bib` title of
        # `\input{<some private file>}` would typeset it. pandoc's `--sandbox`
        # confines pandoc, not the engine, and drops docx images
        # (plans/823-tex-read-hardening.md). The fence checks names as TeX spells
        # them, so symlinks are invisible to it: hence `_refuse_escaping_refs`
        # and `_require_tex_readable_tmpdir`. Rules are set after the host env, so
        # a host cannot loosen them.
        #
        # It fences TeX's reads, not Lua's: `\directlua` in a draft or figure can
        # reach any user file (an accepted residual, docs/SECURITY.md). A `.bib`
        # field cannot: bib_raw_tex_as_text.lua prints its raw TeX as text.
    cmd += ["-o", str(out_path)]
    return cmd, env


def _require_toolchain(output_format: str) -> None:  # pragma: no cover-windows
    """Raises `MissingBinary` unless this host has pandoc and, for a pdf,
    the LuaLaTeX toolchain `_require_pdf_toolchain` checks."""
    _require("pandoc")
    if output_format == "pdf":
        _require_pdf_toolchain()


def _require_pdf_toolchain() -> None:
    """Raises `MissingBinary` unless this host can render a pdf: `lualatex`,
    its font loader, and the fonts the header sets.

    `lualatex` can be on PATH without `luaotfload` (`texlive-luatex`), whose
    absence gives a misleading "font not loadable" error (plans/996, Q0).
    Missing `pdf_fonts.REQUIRED_FONTS` gave a fontspec error naming no remedy
    (#1022); ~0.2 s a font. No `kpsewhich` or `luaotfload-tool` means no probe.
    """
    _require(PDF_ENGINE)
    kpsewhich = programs.resolve_program("kpsewhich")
    if kpsewhich is None:
        return
    probe = subprocess.run([kpsewhich, "luaotfload.sty"], capture_output=True, check=False)
    if probe.returncode != 0:
        raise MissingBinary(
            "pdf rendering runs LuaLaTeX, but its font loader (luaotfload.sty) is "
            "not installed. On Debian/Ubuntu it is the 'texlive-luatex' package; "
            f"{install.remedy('os-deps')} installs it with the fonts a render uses."
        )
    # `is False`: None means no luaotfload-tool to ask, which says nothing.
    missing = [name for name in pdf_fonts.REQUIRED_FONTS if pdf_fonts.font_installed(name) is False]
    if missing:
        raise MissingBinary(
            f"pdf rendering needs {', '.join(missing)}, which LuaLaTeX cannot find, "
            f"and no pdf renders without {'them' if len(missing) > 1 else 'it'}. "
            f"{install.remedy('os-deps')} installs the fonts a render uses."
        )


def _require_tex_readable_tmpdir() -> None:
    """Raises `MissingBinary` when the TeX engine could not read pandoc's
    own temp copy of the draft.

    kpathsea's `openin_any=r` (#823) refuses a path with a dotted directory,
    so `TMPDIR=~/.cache/tmp` (common on HPC) failed every pdf with exit 43.
    `MissingBinary` for `_render_csl`'s reason.
    """
    tmp = Path(tempfile.gettempdir())
    dotted = [part for part in tmp.parts if part.startswith(".")]
    if dotted:
        raise MissingBinary(
            f"pdf rendering cannot use the temp directory {tmp}: {PDF_ENGINE} runs "
            "with openin_any=r (docs/SECURITY.md), which refuses any path with a "
            f"dot-directory in it ({', '.join(dotted)}), and pandoc compiles "
            "there. Set TMPDIR to a directory without one, e.g. TMPDIR=/tmp."
        )


def _run_pandoc(cmd: list[str], env: dict[str, str] | None) -> None:
    """Runs pandoc, then forwards any stderr it printed even though it
    exited 0: citeproc's "citation not found" and missing images exit 0 (M-7).
    """
    # Both programs by absolute path (#974): on Windows the engine named by
    # `--pdf-engine` is looked up in cwd before PATH. Resolved here, not where
    # `cmd` is built, because tests build it on hosts with no TeX.
    argv = [programs.require_program(cmd[0]), *cmd[1:]]
    if "--pdf-engine" in argv:
        engine = argv.index("--pdf-engine") + 1
        argv[engine] = programs.require_program(argv[engine])
    result = subprocess.run(argv, check=True, capture_output=True, text=True, env=env)
    if result.stderr.strip():
        for line in result.stderr.splitlines():
            print(f"[pandoc] {line}", file=sys.stderr)
    # A figure alone on a float-only page, recorded in the pdf since its log is
    # gone (#1065). Advisory: printed, never raised.
    if "--pdf-engine" in argv:
        _floats.print_report(Path(argv[argv.index("-o") + 1]))
