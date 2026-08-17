"""Figures: the ASCII/TikZ pair, and switching between them per format.

A figure has two forms -- a TikZ picture and the same diagram in
`docs/WRITING-STANDARDS.md` §10's plain ASCII -- and this module swaps
one for the other so each output format gets the one it can actually
draw: TikZ through LaTeX, ASCII everywhere else.

**A draft keeps its native form inline, and only the other form becomes
a file.** A Markdown draft holds the ASCII in its fence and names
`figures/<name>.tex` in a `tikz-alt` marker; a `.tex` fragment holds the
`\\input` and names `figures/<name>.txt` in an `ascii-alt` comment. So
there is no `.txt` for a Markdown draft, deliberately: its ASCII is
already the fence the `md` render emits, and a second copy would be one
nothing reads and nothing keeps in step. The `.tex` genre is the case
that needs the file -- `_substitute_ascii_for_tikz` reads it, and
without it pandoc resolves the `\\input`, drops the `tikzpicture`, and
the figure disappears from the `.md` preview entirely.

Every check here reports and carries on. A figure problem still leaves a
draft that renders -- with the other form, or without that one figure --
and warning is what a genre skill already knows how to react to. What
cannot be checked at all is whether the two forms still depict the same
thing; that is `draft-reviser`'s "touch a figure, touch both forms".
"""

import re
import shutil
import subprocess
from pathlib import Path

from src.citation_gate import _PANDOC_CITE_RE
from src.render_output._errors import MissingBinary
from src.render_output._paths import _MARKDOWN_SUFFIXES


# Matches raw-LaTeX \input{...}/\include{...}, however the draft spells
# it -- a bare line or a ```{=latex} fenced block around the same line
# both reach pandoc's LaTeX writer identically (#222), so this doesn't
# need to distinguish them. It also matches one inside a fenced code
# block that merely *discusses* LaTeX, the same property
# `_local_image_refs` already has for `![...]()` -- inert there (no such
# file, silently skipped below) and not worth special-casing.
_LATEX_INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def _local_tex_include_refs(text: str) -> list[str]:
    """Every `\\input{...}`/`\\include{...}` path a draft references --
    the TikZ-figure convention #222 exists for, not a general LaTeX
    feature this project otherwise supports."""
    return list(_LATEX_INCLUDE_RE.findall(text))


# The figure marker, in the two spellings the two draft languages force.
# One vocabulary -- `figure:` -- and one value in both: the figure's base
# name, *without* a suffix. The renderer derives `<base>.tex` and
# `<base>.txt` from it, so a draft never names the same figure twice and
# the two genres are one rule to learn rather than two.
#
# Both are comments *in their own language*, and the LaTeX one being a
# comment is load-bearing rather than tidy. A `.tex` fragment is the file
# a user `\input`s into their own thesis, so spelling the ASCII reference
# as a real `\input{figures/x.txt}` would make pdflatex read the ASCII art
# as LaTeX source: §10's own alphabet contains `^`, `<` and `>`, which are
# math-mode-only, and the build hard-fails with "! Missing $ inserted."
# That failure happens in a document *this* pipeline never renders, so
# nothing here would ever have caught it.
_FIGURE_MARKER_MD_RE = re.compile(
    r"^[ \t]*<!--[ \t]*figure:[ \t]*(\S+)[ \t]*-->[ \t]*$", re.MULTILINE
)
_FIGURE_MARKER_TEX_RE = re.compile(r"^[ \t]*%[ \t]*figure:[ \t]*(\S+)[ \t]*$", re.MULTILINE)


def _tikz_path(base: str) -> str:
    """The TikZ half of the figure a marker names."""
    return f"{base}.tex"


def _ascii_path(base: str) -> str:
    """The ASCII half of the figure a marker names."""
    return f"{base}.txt"


# A marked ASCII figure in a Markdown draft: the marker, then the fenced
# block holding the diagram. Both are replaced together by the `\input`,
# because leaving the fence in place puts the ASCII *and* the TikZ in the
# same PDF -- verified against pandoc, not assumed.
_MARKED_FENCE_RE = re.compile(
    r"^[ \t]*<!--[ \t]*figure:[ \t]*(\S+)[ \t]*-->[ \t]*\n"
    r"(?:[ \t]*\n)*"
    r"[ \t]*(`{3,}|~{3,})[^\n]*\n"
    r"(?:[^\n]*\n)*?"
    r"[ \t]*\2[ \t]*(?:\n|$)",
    re.MULTILINE,
)

# The mirror of the above in a `.tex` fragment: the `\input` and the
# comment naming its ASCII twin.
_INPUT_WITH_MARKER_RE = re.compile(
    r"^[ \t]*\\(?:input|include)\{([^}]+)\}[ \t]*\n"
    r"(?:[ \t]*\n)*"
    r"[ \t]*%[ \t]*figure:[ \t]*(\S+)[ \t]*(?:\n|$)",
    re.MULTILINE,
)

# The formats that go through LaTeX, and so the only ones a TikZ picture
# can actually draw in. Everything else -- docx, html, and plain md --
# takes the ASCII form instead: pandoc cannot turn a `tikzpicture` into a
# Word drawing, and it drops the environment silently, so a figure that
# renders as nothing at all is the alternative.
_TEX_FORMATS = {"tex", "latex", "pdf"}


def _tikz_alt_refs(text: str) -> list[str]:
    """Every TikZ figure a Markdown draft names in a `figure:` marker."""
    return [_tikz_path(base) for base in _FIGURE_MARKER_MD_RE.findall(text)]


def _figure_refs(text: str) -> list[str]:
    """Every TikZ figure file a draft references, however it spells it.

    A `.tex` fragment says `\\input{...}` outright; a Markdown draft names
    the same file in a `tikz-alt` marker and only grows the `\\input` in
    the temp copy handed to pandoc. Both have to be visible *here*,
    because this is what decides whether the figure file is copied beside
    a `tex` output and whether `\\usepackage{tikz}` is loaded -- and both
    of those read the draft on disk, not the substituted copy.
    """
    return _local_tex_include_refs(text) + _tikz_alt_refs(text)


def _resolve_sibling(draft_dir: Path, ref: str) -> Path | None:
    """`ref` as a real file under `draft_dir`, or None.

    The skip rules are `_copy_local_tex_includes`'s, shared rather than
    restated: an absolute or `..`-escaping reference is not resolved, for
    the same reason it is not copied -- a draft's own text is never a
    reason to read or write outside its own directory.
    """
    ref_path = Path(ref)
    if ref_path.is_absolute() or ".." in ref_path.parts:
        return None
    candidate = draft_dir / ref_path
    return candidate if candidate.is_file() else None


def _require_tikz() -> None:
    """Raises `MissingBinary` when `tikz.sty` is not installed.

    `tikz.sty` is `texlive-pictures` on Debian/Ubuntu, a separate package
    from the `texlive-latex-*` ones the rest of this stage needs, so
    `pdflatex` being on PATH says nothing about it --
    `scripts/install_full_pipeline.sh` installs both, but a host set up
    before #226 has only the first.

    Deliberately a hard failure rather than a silent fall back to the
    ASCII form. Falling back would make the same draft render a vector
    figure on one host and monospace art on another with nothing in the
    output saying which happened, and byte-identical output over
    unchanged input is a product rule here, not just a test convention
    (`docs/CODE-STANDARDS.md`, "Repeatable"). `MissingBinary` is also the
    failure every genre skill already knows how to handle: `main()`
    prints `[missing-binary]` and the skill warns and carries on
    presenting the draft.

    A host with no `kpsewhich` at all cannot be probed, so this says
    nothing and lets `pdflatex` report the missing package itself --
    guessing "absent" there would refuse to render on a working TeX
    installation that simply ships its own tooling.
    """
    if shutil.which("kpsewhich") is None:
        return
    probe = subprocess.run(["kpsewhich", "tikz.sty"], capture_output=True, check=False)
    if probe.returncode != 0:
        raise MissingBinary(
            "This draft has a TikZ figure, but tikz.sty is not installed. On "
            "Debian/Ubuntu it is the 'texlive-pictures' package, which is "
            "separate from the texlive-latex-* packages pdflatex itself needs "
            "-- run scripts/install_full_pipeline.sh, which installs both."
        )


def _substitute_tikz_for_ascii(text: str, draft_dir: Path) -> str:
    """Markdown draft, LaTeX-bound output: marked ASCII fence -> `\\input`.

    The fence goes as well as the marker. Keeping it would put the ASCII
    diagram *and* the TikZ picture in the same PDF, one under the other
    -- confirmed by rendering both through pandoc rather than reasoned
    about.

    A marker naming something that isn't a readable file under the
    draft's own directory is left exactly as it was, so the draft still
    renders with its ASCII figure. `_figure_warnings` is what tells the
    user, rather than this failing the render over a figure.
    """
    def replace(match: re.Match) -> str:
        ref = _tikz_path(match.group(1))
        if _resolve_sibling(draft_dir, ref) is None:
            return match.group(0)
        return f"\\input{{{ref}}}\n"

    return _MARKED_FENCE_RE.sub(replace, text)


def _substitute_ascii_for_tikz(text: str, draft_dir: Path) -> str:
    """`.tex` fragment, non-LaTeX output: `\\input` -> the ASCII twin.

    Without this the figure vanishes from the `.md` preview entirely:
    pandoc's LaTeX reader resolves the `\\input` but then drops the
    `tikzpicture` environment, and keeps dropping it under
    `-t markdown+raw_attribute`.

    Pandoc renders the `verbatim` this emits as a 4-space *indented* code
    block rather than a fenced one -- a `CodeBlock` with no attributes
    takes the indented form. Relative alignment and `^ \\ < >` all
    survive, which is what the diagram actually needs.
    """
    def replace(match: re.Match) -> str:
        target = _resolve_sibling(draft_dir, _ascii_path(match.group(2)))
        if target is None:
            return match.group(0)
        body = target.read_text(encoding="utf-8").rstrip("\n")
        return f"\\begin{{verbatim}}\n{body}\n\\end{{verbatim}}\n"

    return _INPUT_WITH_MARKER_RE.sub(replace, text)


def _ascii_alt_refs(text: str) -> list[str]:
    """Every ASCII twin a `.tex` fragment names in a `figure:` marker."""
    return [_ascii_path(base) for base in _FIGURE_MARKER_TEX_RE.findall(text)]


# `\cite`, `\citep`, `\citet` and friends. `_PANDOC_CITE_RE` covers the
# `[@key]` spelling; a figure file is checked for both because a Markdown
# draft's figures and a fragment's figures are the same kind of file.
_LATEX_CITE_RE = re.compile(r"\\cite[a-zA-Z]*\s*[\[{]")


def _figure_has_citekey(path: Path) -> bool:
    return bool(
        _PANDOC_CITE_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        or _LATEX_CITE_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    )


def _figure_warnings(text: str, input_path: Path) -> list[str]:
    """Everything checkable about a figure pair, none of it worth failing over.

    All of these are reported and then ignored, deliberately. A figure
    problem leaves a draft that still renders -- with the other form of
    the figure, or without that one figure -- and a genre skill's
    documented reaction to a render complaint is to warn and carry on
    presenting. What cannot be checked at all is whether the two forms
    still *depict the same thing*; that is `draft-reviser`'s "touch a
    figure, touch both forms" rule, and no detector replaces it.
    """
    is_markdown = input_path.suffix.lower() in _MARKDOWN_SUFFIXES
    language = "Markdown" if is_markdown else "LaTeX"
    wrong_marker = _FIGURE_MARKER_TEX_RE if is_markdown else _FIGURE_MARKER_MD_RE
    found = [
        f"{ref}: marker is the wrong kind for a {language} draft, so the figure "
        "will not be substituted"
        for ref in wrong_marker.findall(text)
    ]
    for ref in _figure_refs(text) + _ascii_alt_refs(text):
        resolved = _resolve_sibling(input_path.parent, ref)
        if resolved is None:
            found.append(f"{ref}: not a readable file under {input_path.parent}")
        elif _figure_has_citekey(resolved):
            found.append(
                f"{ref}: contains a citekey. Figure files are not read by "
                "`python -m src.draft gate`, so a citekey here is ungated -- "
                "move the claim into the prose"
            )
    if not is_markdown:
        paired = {ref for ref, _ in _INPUT_WITH_MARKER_RE.findall(text)}
        found += [
            f"{ref}: no `%figure:` marker, so every non-LaTeX render omits this figure"
            for ref in _local_tex_include_refs(text) if ref not in paired
        ]
    return found


def _with_figures_for(text: str, input_path: Path, output_format: str) -> str:
    """`text` with each figure switched to the form `output_format` can draw.

    Two directions, one per draft language, and both are no-ops when the
    draft's native form is already the right one: a Markdown draft
    rendered to Markdown keeps its fence, and a `.tex` fragment rendered
    to `tex`/`pdf` keeps its `\\input`.
    """
    is_markdown = input_path.suffix.lower() in _MARKDOWN_SUFFIXES
    wants_latex = output_format in _TEX_FORMATS
    if is_markdown and wants_latex:
        return _substitute_tikz_for_ascii(text, input_path.parent)
    if not is_markdown and not wants_latex:
        return _substitute_ascii_for_tikz(text, input_path.parent)
    return text
