"""Stage 7: Pandoc/LaTeX rendering of generated Markdown into PDF/DOCX.

Needs the `pandoc` and TeX Live binaries (apt packages, not pip); a pdf is
LuaLaTeX with the fonts `install_full_pipeline.sh os-deps` installs (#996).
Without them this fails cleanly with MissingBinary (docker/Dockerfile
installs them on a host without root).

`[@citekey]` markers resolve via `--citeproc` against `config.BIB_FILE_PATH`
in IEEE style (`assets/csl/ieee.csl`, `--csl` to override). All fixups (a `--`
citekey alias, control-character stripping, the manual References swap, the
CSL collapse attribute) happen on temp copies; the draft and the real
`bibliography.bib` are never modified.

`--format md` on a Markdown draft skips pandoc, whose Markdown writer escapes
markers and emits fenced divs that render as literal punctuation elsewhere.

**Every path this module reads or writes resolves inside
`config.CONTENT_DIR`**; violations raise `OutsideContentDir`. Output mirrors
the draft's place under `content/drafts/` into `content/rendered/`.

Runs under bare `python` (stdlib plus config/citation_gate/references),
independent of `chitragupta/enrich/__main__.py`; genre skills call it directly.
"""

import os
import sys
import tempfile
from pathlib import Path

from chitragupta import config, references
from chitragupta.page import ARTICLE
from chitragupta.render_output._assets import (
    _MD_IMAGE_RE,
    _URI_SCHEME_RE,
    _copy_local_images,
    _copy_local_tex_includes,
    _local_image_refs,
    _refuse_escaping_refs,
)
from chitragupta.render_output._citeproc import (
    _REFS_ANCHOR,
    _alias_for,
    _safe_render_inputs,
    _sanitize_for_latex,
    _swap_manual_refs_for_citeproc,
)
from chitragupta.render_output import _assets, _equation_captions, _math, _tables, _unicode
from chitragupta.render_output._csl import _CSL_CITATION_TAG_RE, _collapsed_csl, _resolve_csl
from chitragupta.render_output._errors import MissingBinary, OutsideContentDir, _require
from chitragupta.render_output._figure_captions import figures as _declared_figures
from chitragupta.render_output._figure_captions import substitute_captions, substitute_refs
from chitragupta.render_output._figures import (
    _FIGURE_MARKER_MD_RE,
    _FIGURE_MARKER_TEX_RE,
    _INPUT_WITH_MARKER_RE,
    _LATEX_CITE_RE,
    _LATEX_INCLUDE_RE,
    _TEX_FORMATS,
    _ascii_alt_refs,
    _ascii_path,
    _figure_has_citekey,
    _tikz_path,
    _figure_refs,
    _figure_warnings,
    _local_tex_include_refs,
    _markdown_ascii_refs,
    _require_tikz,
    _resolve_sibling,
    _substitute_ascii_for_marker,
    _substitute_ascii_for_tikz,
    _substitute_tikz_for_ascii,
    _tikz_alt_refs,
    _with_figures_for,
)
from chitragupta.render_output._cli import main
from chitragupta.render_output._pandoc import _has_code_block, _pandoc_command, _render_csl
from chitragupta.render_output._pandoc import _require_pdf_toolchain, _require_toolchain
from chitragupta.render_output._pandoc import _run_pandoc
from chitragupta.render_output._paths import _MARKDOWN_SUFFIXES, _output_dir, _target_dir
from chitragupta.render_output._gate import gated_warnings
from chitragupta.render_output._substitution import _checked_math_mapping, _substituted

# Re-exported deliberately: callers and tests reach these (private helpers
# included) as `render_output._X`, so the package's attribute surface must stay
# identical to the single module it replaced.
__all__ = ["MissingBinary", "OutsideContentDir", "render", "main"]


def _copy_local_assets(input_path: Path, dest_dir: Path, deferred: bool = False) -> None:
    """Every local file the output needs beside it, copied there.

    Called together so no kind is forgotten. `deferred` (a fragment or deferred
    citations) adds the aliased `.bib` for bibtex.
    """
    _copy_local_images(input_path, dest_dir)
    _copy_local_tex_includes(input_path, dest_dir)
    if deferred:
        _assets._copy_book_bibliography(dest_dir)


def _refuse_misdeferred(output_format: str, fragment: bool, defer_citations: bool) -> None:
    """Raises `ValueError` for a deferred render that is not a standalone
    `tex`: pdf/docx would need a bibtex pass pandoc does not run, and a
    fragment is deferred already. A caller's mistake, outside `RENDER_FAILURES`.
    """
    if defer_citations and (fragment or output_format != "tex"):
        raise ValueError(
            "defer_citations renders a standalone tex document; it takes "
            f"output_format='tex' and no fragment (got {output_format!r}, "
            f"fragment={fragment})"
        )


def render(
    input_path: str,
    output_format: str = "pdf",
    # Passed to pandoc as documentclass, fontsize, papersize and geometry for
    # every tex/pdf render: the article page (`page.ARTICLE`) by default.
    documentclass: str = ARTICLE.documentclass,
    fontsize: str = ARTICLE.fontsize,
    papersize: str = ARTICLE.papersize,
    margin: str = ARTICLE.margin,
    csl: str | Path | None = None,
    collapse_citations: bool | None = None,
    output_dir: str | Path | None = None,
    fragment: bool = False,
    index_terms: str | Path | None = None,
    defer_citations: bool = False,
    # The `math.md` for a copy of a draft rendered from outside
    # `content/drafts/`, where none mirrors: `draft diff`'s sides (#1194).
    math_mapping_path: str | Path | None = None,
) -> Path:
    """Renders `input_path` (Pandoc markdown) to `output_format` (pdf/tex/docx/...).

    Lands in `_output_dir(input_path)`. `output_dir` overrides it for a
    non-draft (a review report's renders go beside the report), confined to
    `content/` and not mirrored into.

    Citations use `csl` (default IEEE), collapsing runs when
    `collapse_citations`. `--standalone` makes a `tex` output compilable alone;
    `fragment=True` is for a unit `\\input` into a book (docs/WRITE-A-BOOK.md):
    no preamble, top heading becomes `\\chapter`. `index_terms` adds a book's
    `\\index{}` entries (#1168). `defer_citations=True` keeps the standalone
    article but leaves citations to bibtex; the gate runs as for any render.
    """
    _refuse_misdeferred(output_format, fragment, defer_citations)
    input_path = config.require_inside_content(Path(input_path))
    out_dir = _target_dir(input_path, output_dir)
    # Read once and threaded through: after figure substitution, "the draft" and
    # "what is rendered" differ, and separate reads could disagree.
    draft_text = input_path.read_text(encoding="utf-8")
    # Before the early return, so an md-to-md render still reports figure problems.
    for prefix, warning in gated_warnings(draft_text, input_path):
        print(f"[{prefix}] {warning}", file=sys.stderr)
    if output_format == "md" and input_path.suffix.lower() in _MARKDOWN_SUFFIXES:
        # Markdown in, Markdown out is citation numbering, not conversion; see
        # the module docstring for why not pandoc. A LaTeX input still goes
        # through pandoc below. `_substituted` drops raw LaTeX here (#1144).
        _copy_local_assets(input_path, out_dir)
        return references.write_numbered(
            input_path, out_dir, _substituted(draft_text, input_path, output_format, {})
        )

    math_mapping = _checked_math_mapping(draft_text, input_path, math_mapping_path)
    _refuse_escaping_refs(input_path, draft_text)

    # From here on needs the real pandoc/LuaLaTeX toolchain (#291); marked
    # per-line since there is no single enclosing block to tag.
    _require_toolchain(output_format)  # pragma: no cover-windows
    figure_refs = _figure_refs(draft_text)  # pragma: no cover-windows
    if figure_refs and output_format in _TEX_FORMATS:  # pragma: no cover-windows
        _require_tikz()

    out_dir.mkdir(parents=True, exist_ok=True)  # pragma: no cover-windows
    _copy_local_assets(input_path, out_dir, fragment or defer_citations)  # pragma: no cover-windows
    out_path = out_dir / f"{input_path.stem}.{output_format}"  # pragma: no cover-windows

    with tempfile.TemporaryDirectory() as tmp:  # pragma: no cover-windows
        safe_md, safe_bib = _safe_render_inputs(
            input_path,
            config.BIB_FILE_PATH,
            Path(tmp),
            _substituted(
                draft_text, input_path, output_format, math_mapping, fragment, defer_citations
            ),
        )
        cmd, env = _pandoc_command(
            safe_md,
            safe_bib,
            _render_csl(csl, collapse_citations, Path(tmp)),
            out_path,
            input_path,
            output_format,
            documentclass,
            fontsize,
            papersize,
            margin,
            figure_refs,
            fragment,
            _has_code_block(draft_text),
            _unicode.preamble_files(draft_text, output_format, fragment, Path(tmp), out_dir),
            index_terms,
            defer_citations,
        )
        _run_pandoc(cmd, env)

    return out_path  # pragma: no cover-windows
