"""The `python -m chitragupta.draft render` entry point."""

import argparse
import re
import subprocess
import sys

from pathlib import Path

from chitragupta import config, ledger, reference_entries
from chitragupta.page import ARTICLE
from chitragupta.render_output._errors import ConversionError, MissingBinary, OutsideContentDir
from chitragupta.render_output._figures import _figure_refs
from chitragupta.render_output._math import MathMappingError
from chitragupta.render_output._tex_preview import undefined_command_hint
from chitragupta.help_format import ClickParser
from chitragupta.progname import prog_for


def _format_arg(value: str) -> str:
    """argparse `type=` for `--format`: one format, not a list.

    A comma list once wrote `<stem>.md,tex,pdf` and exited 0 (#389). Not an
    allowlist: pandoc's `-o` infers many writers from the extension, and a
    comma is never part of one.
    """
    if "," in value:
        raise argparse.ArgumentTypeError(
            f"{value!r} looks like a list, not one format. --format takes exactly "
            "one (e.g. --format pdf, --format tex, --format docx) -- render each "
            "needed format with its own --format. A review aid's plural --formats "
            "is the one that takes a comma-separated list."
        )
    return value


def _figure_repair_hint(input_arg: str) -> str:
    r"""The `draft-reviser` pointer to append to a failed render, or "".

    A bad TikZ figure fails the whole pdf, and TeX names a file, not a fix.
    Only for a draft with a figure. No repair here: redrawing is a drafting
    judgement, and a silent ASCII fallback would hide the breakage in the
    artifact a thesis `\input`s.
    """
    try:
        refs = _figure_refs(Path(input_arg).read_text(encoding="utf-8"))
    except OSError:
        return ""
    if not refs:
        return ""
    named = ", ".join(refs)
    return (
        f"\n[figure] This draft has a TikZ figure ({named}). If the error above "
        'names one, run the draft-reviser skill: "the TikZ figure <file> fails to '
        'compile; repair it or drop the figure". A figure that does not compile '
        "here will not compile in the document that \\input-s this draft either."
    )


# The message assets/latex/chitragupta-lualatex.tex raises for a character no
# fallback font has, worded like TeX's own so either source matches.
_UNICODE_ERROR_RE = re.compile(r"Missing character: There is no (.) \(U\+([0-9A-F]{4,6})\)")


def _unicode_repair_hint(stderr: str | None) -> str:
    r"""The fix for a character no font in the render's chain has, or "".

    Failing the build is deliberate: the alternative is a silent gap in the PDF
    (#996). The build stops at the first such character, so the hint names that
    one. `content/unicode-extra.tex` works under LuaLaTeX too, via the
    `_unicode._overlay_header` shim.
    """
    match = _UNICODE_ERROR_RE.search(stderr or "")
    if match is None:
        return ""
    char, code = match.groups()
    extra = config.CONTENT_DIR / "unicode-extra.tex"
    return (
        f"\n[unicode] No installed font has {char} (U+{code}), the first such character "
        f"in this draft. Either write it as LaTeX in the draft (for a symbol, its math "
        f"command, e.g. $\\aleph$), or teach this project to print it: add "
        f"\\DeclareUnicodeCharacter{{{code}}}{{...}} to {extra}, e.g. "
        f"\\DeclareUnicodeCharacter{{{code}}}{{\\ensuremath{{\\ast}}}}."
    )


def _build_parser() -> argparse.ArgumentParser:
    """This command's flags, and nothing else."""

    parser = ClickParser(
        prog=f"{prog_for('draft')} render",
        description="Render a Pandoc-markdown or LaTeX draft to tex/pdf/docx.",
    )
    parser.add_argument("input", help="Path to the draft file (Markdown or LaTeX)")
    parser.add_argument(
        "--format",
        dest="output_format",
        default="pdf",
        type=_format_arg,
        help="Output format (default: pdf)",
    )
    parser.add_argument(
        "--documentclass",
        default=ARTICLE.documentclass,
        help=f"LaTeX documentclass (default: {ARTICLE.documentclass})",
    )
    parser.add_argument(
        "--fontsize",
        default=ARTICLE.fontsize,
        help=f"LaTeX font size (default: {ARTICLE.fontsize})",
    )
    parser.add_argument(
        "--papersize",
        default=ARTICLE.papersize,
        help='LaTeX paper size, without the "paper" suffix pandoc appends itself '
        f"(default: {ARTICLE.papersize})",
    )
    parser.add_argument(
        "--margin",
        default=ARTICLE.margin,
        help=f"Page margin, passed to the geometry package (default: {ARTICLE.margin})",
    )
    parser.add_argument(
        "--csl",
        default=None,
        help=f"CSL style for citations and the bibliography (default: {config.CSL_STYLE_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Write the output here instead of content/rendered/<mirrored path>, "
        "a pdf's figure looks included. "
        "A book's fragments need no override -- they mirror to the same "
        "directory book.tex is composed into. Confined to content/ like "
        "every other path this writes",
    )
    parser.add_argument(
        "--fragment",
        action="store_true",
        help="Emit an \\input-able LaTeX fragment (no preamble) whose top "
        "heading is a chapter, for assembling a book -- see docs/WRITE-A-BOOK.md",
    )
    parser.add_argument(
        "--index-terms",
        default=None,
        metavar="PATH",
        help="With --fragment: place the book index's entries, from the term "
        "table `registry build --index` wrote (docs/book/BOOK-INDEX.md)",
    )
    parser.add_argument(
        "--no-collapse-citations",
        dest="collapse_citations",
        action="store_false",
        default=None,
        help="Render a consecutive run as [3], [4], [5], [6] instead of [3]-[6] "
        "-- i.e. leave the CSL style exactly as it is on disk",
    )
    return parser


def _rendered(args: argparse.Namespace) -> Path | None:
    """`render()` for `args`, every refusal printed as the `[error]` or
    `[missing-binary]` line a skill reacts to; `None` when it refused.

    Shared by `figure look --draft` (#1052), refusals and all.
    """
    # Deferred: the package root imports this module before `render` exists, so a
    # module-scope import would be circular (.pylintrc allows this pattern).
    from chitragupta.render_output import render
    from chitragupta.render_output._gate import UngatedDraft

    try:
        return render(
            args.input,
            args.output_format,
            args.documentclass,
            args.fontsize,
            args.papersize,
            args.margin,
            args.csl,
            args.collapse_citations,
            args.output_dir,
            fragment=args.fragment,
            index_terms=args.index_terms,
        )
    except MissingBinary as exc:
        print(f"[missing-binary] {exc}")
        return None
    except MathMappingError as exc:
        # Non-zero, deliberately: rendering a marked equation as verbatim is the
        # defect §12 exists to prevent, and a warning can be carried past. The
        # heuristic gaps stay warnings -- only this is certain.
        print(f"[error] {exc}")
        return None
    except (OutsideContentDir, ConversionError) as exc:
        # `[error]`, not a traceback: skills warn and carry on, as the draft is fine.
        # `ConversionError` is caught because every RENDER_FAILURES member is.
        print(f"[error] {exc}")
        return None
    except subprocess.CalledProcessError as exc:  # pragma: no cover-windows
        print(
            f"[error] pandoc failed: {exc.stderr or exc}"
            f"{_figure_repair_hint(args.input)}{_unicode_repair_hint(exc.stderr)}"
            f"{undefined_command_hint(exc.stderr, args.input)}"
        )
        return None
    except ledger.NoLedger as exc:
        # `--format md` numbers a citing draft from the ledger; with none
        # to read, the same `[error]` a skill warns on and carries past.
        print(f"[error] {exc}")
        return None
    except UngatedDraft as exc:
        # The gate refused the draft before any format was produced (#812),
        # with its own report naming each key and line.
        print(f"[error] {exc}")
        return None
    except reference_entries.MissingCitekey as exc:
        # Reached only if the ledger changes between the gate and the reference
        # list (a sync mid-render). The specific exception, not a bare KeyError,
        # so real bugs surface as themselves (m-60).
        print(f"[error] {exc.args[0] if exc.args else exc}")
        return None


def _report_looks(draft: Path, pdf: Path, output_dir: str | None) -> None:
    """Refresh the looks and page pictures of `draft`'s figures (#1052),
    as `[figure-look]` notes, under `output_dir` when given (#1114). Never
    a reason the render fails: see `figure/_look_draft.py`."""
    # Deferred: `figure` imports from this package, so a module-scope import is a cycle.
    from chitragupta.figure._look_draft import notes, refresh

    target = None if output_dir is None else Path(output_dir)
    for line in notes(refresh(draft, pdf, target)):
        print(line, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point -- deliberately independent of chitragupta/enrich/__main__.py.

    That one drags in the multi-GB `.venv-full`; this must run under bare `python`.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.index_terms and not args.fragment:
        parser.error("--index-terms needs --fragment: only a book's chapters carry index entries")
    out_path = _rendered(args)
    if out_path is None:
        return 1
    if args.output_format == "pdf":
        _report_looks(Path(args.input), out_path, args.output_dir)
    print(str(out_path))
    return 0
