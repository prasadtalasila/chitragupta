"""Figures: the ASCII/TikZ pair, and switching between them per format.

A figure is two files, `figures/<name>.tex` and `figures/<name>.txt` (§10),
named by one `figure:` marker; this injects TikZ for LaTeX output and ASCII
elsewhere. Exception: a thesis `.tex` fragment keeps a real inline
`\\input{figures/<name>.tex}`, since the user `\\input`s it into their own
thesis where this module never runs (#247, #230).

Every check reports and carries on: a figure problem still leaves a
renderable draft. Whether both forms depict the same thing is
`draft-reviser`'s "touch a figure, touch both forms".
"""

import re
import subprocess
from pathlib import Path

from chitragupta import _pandoc_cites, config, install, programs
from chitragupta.render_output._errors import MissingBinary
from chitragupta.render_output._figure_anchor import figure_block
from chitragupta.render_output._figure_captions import warnings as _caption_warnings
from chitragupta.render_output._paths import _MARKDOWN_SUFFIXES


# Raw-LaTeX \input/\include, bare or in a ```{=latex} block (#222). Also matches
# inside a code block that discusses LaTeX; harmless, as no such file exists.
_LATEX_INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def _local_tex_include_refs(text: str) -> list[str]:
    """Every `\\input{...}`/`\\include{...}` path a draft references (#222)."""
    return list(_LATEX_INCLUDE_RE.findall(text))


# The figure marker, in the two spellings the two draft languages force: the
# base name without suffix, from which `<base>.tex` and `<base>.txt` derive.
#
# The LaTeX one must be a comment: a real `\input{figures/x.txt}` in a thesis
# would make pdflatex read ASCII art (`^`, `<`, `>`) as LaTeX and fail with
# "! Missing $ inserted." in a document this pipeline never renders.
#
# Tried and rejected: ASCII behind `\iffalse ... \fi` in one file (pandoc honours
# it too, so md gets nothing); no marker at all (readers and revisers cannot see
# the second form).
_FIGURE_MARKER_MD_RE = re.compile(
    r"^[ \t]*<!--[ \t]*figure:[ \t]*(\S+)[ \t]*-->[ \t]*$", re.MULTILINE
)
_FIGURE_MARKER_TEX_RE = re.compile(r"^[ \t]*%[ \t]*figure:[ \t]*(\S+)[ \t]*$", re.MULTILINE)

# Matched alone, never with a trailing fence: a leftover fence would double the
# figure in the rendered output (#230).


def _tikz_path(base: str) -> str:
    return f"{base}.tex"


def _ascii_path(base: str) -> str:
    return f"{base}.txt"


# The `.tex` fragment's mirror: the real `\input` and the comment naming its
# ASCII twin.
_INPUT_WITH_MARKER_RE = re.compile(
    r"^[ \t]*\\(?:input|include)\{([^}]+)\}[ \t]*\n"
    r"(?:[ \t]*\n)*"
    r"[ \t]*%[ \t]*figure:[ \t]*(\S+)[ \t]*(?:\n|$)",
    re.MULTILINE,
)

# Formats that go through LaTeX, the only ones a TikZ picture can draw in. pandoc
# silently drops a `tikzpicture` elsewhere, so other formats take the ASCII form.
_TEX_FORMATS = {"tex", "latex", "pdf"}


def _tikz_alt_refs(text: str) -> list[str]:
    return [_tikz_path(base) for base in _FIGURE_MARKER_MD_RE.findall(text)]


def _markdown_ascii_refs(text: str) -> list[str]:
    """Every ASCII figure a Markdown draft names in a `figure:` marker (the
    same marker that names the TikZ file)."""
    return [_ascii_path(base) for base in _FIGURE_MARKER_MD_RE.findall(text)]


def _figure_refs(text: str) -> list[str]:
    """Every TikZ figure file a draft references, however it spells it.

    Both the `.tex` `\\input` and the Markdown marker, since the copy beside
    a `tex` output and the `tikz` package load read the draft on disk.
    """
    return _local_tex_include_refs(text) + _tikz_alt_refs(text)


def _resolve_sibling(draft_dir: Path, ref: str) -> Path | None:
    """`ref` as a real file under `draft_dir`, or None.

    Shared skip rules for the copiers: an absolute or `..` reference is never
    resolved. `resolves_inside` catches a symlink out of the directory (#823).
    Returns the unresolved spelling, since the copiers write to `dest_dir / ref`.
    """
    ref_path = Path(ref)
    if ref_path.is_absolute() or ".." in ref_path.parts:
        return None
    candidate = draft_dir / ref_path
    if not candidate.is_file():
        return None
    return candidate if config.resolves_inside(candidate, draft_dir) else None


def _require_tikz() -> None:
    """Raises `MissingBinary` when `tikz.sty` is not installed.

    `tikz.sty` is `texlive-pictures`, separate from `texlive-latex-*`, so
    `pdflatex` on PATH proves nothing (#226). A hard failure, not an ASCII
    fallback: output must not depend silently on the host
    (docs/CODE-STANDARDS.md, "Repeatable"), and skills already handle
    `[missing-binary]`. No `kpsewhich` means no probe: let `pdflatex` report it.
    """
    kpsewhich = programs.resolve_program("kpsewhich")
    if kpsewhich is None:
        return
    probe = subprocess.run([kpsewhich, "tikz.sty"], capture_output=True, check=False)
    if probe.returncode != 0:
        raise MissingBinary(
            "This draft has a TikZ figure, but tikz.sty is not installed. On "
            "Debian/Ubuntu it is the 'texlive-pictures' package, which is "
            "separate from the texlive-latex-* packages the TeX engine itself "
            f"needs -- {install.remedy('os-deps')} installs both."
        )


def _substitute_tikz_for_ascii(text: str, draft_dir: Path, anchored: bool = False) -> str:
    """Markdown draft, LaTeX-bound output: `figure:` marker -> `\\input`.

    Centred via `_figure_anchor.figure_block`; `anchored` (pdf) marks each
    page. A marker naming no readable file is left alone so the draft still
    renders; `_figure_warnings` reports it.
    """

    def replace(match: re.Match) -> str:
        ref = _tikz_path(match.group(1))
        if _resolve_sibling(draft_dir, ref) is None:
            return match.group(0)
        return figure_block(ref, match.group(1), anchored)

    return _FIGURE_MARKER_MD_RE.sub(replace, text)


def _substitute_ascii_for_marker(text: str, draft_dir: Path) -> str:
    """Markdown draft, non-LaTeX-bound output: `figure:` marker -> a fence,
    including the `md` render. A missing file is left alone, as above.
    """

    def replace(match: re.Match) -> str:
        target = _resolve_sibling(draft_dir, _ascii_path(match.group(1)))
        if target is None:
            return match.group(0)
        body = target.read_text(encoding="utf-8").rstrip("\n")
        return f"```\n{body}\n```\n"

    return _FIGURE_MARKER_MD_RE.sub(replace, text)


def _substitute_ascii_for_tikz(text: str, draft_dir: Path) -> str:
    """`.tex` fragment, non-LaTeX output: `\\input` -> the ASCII twin.

    Otherwise pandoc's LaTeX reader drops the `tikzpicture` and the figure
    vanishes from the preview. The `verbatim` becomes an indented code block,
    which keeps alignment and `^ \\ < >`.
    """

    def replace(match: re.Match) -> str:
        target = _resolve_sibling(draft_dir, _ascii_path(match.group(2)))
        if target is None:
            return match.group(0)
        body = target.read_text(encoding="utf-8").rstrip("\n")
        return f"\\begin{{verbatim}}\n{body}\n\\end{{verbatim}}\n"

    return _INPUT_WITH_MARKER_RE.sub(replace, text)


def _ascii_alt_refs(text: str) -> list[str]:
    return [_ascii_path(base) for base in _FIGURE_MARKER_TEX_RE.findall(text)]


# `\cite`, `\citep`, `\citet` and friends. `_pandoc_cites` covers the
# `[@key]` spelling; figure files are checked for both.
_LATEX_CITE_RE = re.compile(r"\\cite[a-zA-Z]*\s*[\[{]")


def _figure_has_citekey(path: Path) -> bool:
    """Whether a figure file contains a citekey in either spelling.

    `errors="replace"`: an advisory check must not be what stops a render.
    """
    body = path.read_text(encoding="utf-8", errors="replace")
    return bool(_pandoc_cites.citations(body) or _LATEX_CITE_RE.search(body))


def _figure_warnings(text: str, input_path: Path) -> list[str]:
    """Everything checkable about a figure pair, none of it worth failing over
    (see the module docstring)."""
    is_markdown = input_path.suffix.lower() in _MARKDOWN_SUFFIXES
    language = "Markdown" if is_markdown else "LaTeX"
    wrong_marker = _FIGURE_MARKER_TEX_RE if is_markdown else _FIGURE_MARKER_MD_RE
    found = [
        f"{ref}: marker is the wrong kind for a {language} draft, so the figure "
        "will not be substituted"
        for ref in wrong_marker.findall(text)
    ]
    for ref in _figure_refs(text) + _ascii_alt_refs(text) + _markdown_ascii_refs(text):
        resolved = _resolve_sibling(input_path.parent, ref)
        if resolved is None:
            found.append(f"{ref}: not a readable file under {input_path.parent}")
        elif _figure_has_citekey(resolved):
            found.append(
                f"{ref}: contains a citekey. Figure files are not read by "
                "`python -m chitragupta.draft gate`, so a citekey here is ungated -- "
                "move the claim into the prose"
            )
    if not is_markdown:
        paired = {ref for ref, _ in _INPUT_WITH_MARKER_RE.findall(text)}
        found += [
            f"{ref}: no `%figure:` marker, so every non-LaTeX render omits this figure"
            for ref in _local_tex_include_refs(text)
            if ref not in paired
        ]
    # Issue 411: a captioned figure's id, and a `figureref` naming one --
    # `_figure_captions.warnings`'s own concern, not this module's.
    return found + _caption_warnings(text)


def _with_figures_for(text: str, input_path: Path, output_format: str) -> str:
    """`text` with each figure switched to the form `output_format` can draw.

    The one no-op is a `.tex` fragment to `tex`/`pdf`: its TikZ is already
    inline and self-contained (#230).
    """
    is_markdown = input_path.suffix.lower() in _MARKDOWN_SUFFIXES
    wants_latex = output_format in _TEX_FORMATS
    if is_markdown and wants_latex:
        return _substitute_tikz_for_ascii(text, input_path.parent, output_format == "pdf")
    if is_markdown and not wants_latex:
        return _substitute_ascii_for_marker(text, input_path.parent)
    if not is_markdown and not wants_latex:
        return _substitute_ascii_for_tikz(text, input_path.parent)
    return text
