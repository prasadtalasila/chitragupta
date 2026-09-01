"""The `python -m chitragupta.draft render` entry point."""

import argparse
import subprocess

from pathlib import Path

from chitragupta import config, references
from chitragupta.render_output._errors import MissingBinary, OutsideContentDir
from chitragupta.render_output._figures import _figure_refs
from chitragupta.render_output._math import MathMappingError


def _format_arg(value: str) -> str:
    """argparse `type=` for `--format`: one format, not a list.

    `--format md,tex,pdf` used to reach render() unexamined, which built
    the output path as `f"{stem}.{output_format}"` -- so it wrote a file
    literally named `<stem>.md,tex,pdf`, printed a success path and
    exited 0, and the real `.pdf` was never touched (#389). Rejected here
    rather than validated against a fixed list of formats: render() hands
    this straight to pandoc's `-o`, which infers its writer from the
    extension and accepts many (docx, html, odt, ...) this project has no
    reason to enumerate. A comma is never part of one of those, so it is
    the one shape this can check without inventing an allowlist.
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

    A malformed TikZ figure fails the *whole* pdf, not just the figure,
    and pdflatex's own error names a file rather than saying what to do
    about it. Only added for a draft that actually has a figure, so an
    unrelated pandoc failure is not sent chasing one.

    Repairing it is deliberately not attempted here. Redrawing a figure
    is a drafting judgement -- it may be the TikZ that is wrong, or the
    claim the figure makes -- and `draft-reviser` is the skill that owns
    changing a draft. Falling back to the ASCII form silently would also
    hide the breakage in exactly the artifact a thesis `\input`s.
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


def _build_parser() -> argparse.ArgumentParser:
    """This command's flags, and nothing else.

    Split from `main` when `--fragment` and `--output-dir` took it over
    the 25-statement limit -- the same seam `chitragupta/draft.py` already draws
    between `build_parser` and `main`, and the same one docs/CODE-
    STANDARDS.md names as the usual shape of a C1 offender: a `main` that
    parses arguments, does the work, and formats the output.
    """

    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft render",
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
        "--documentclass", default="article", help="LaTeX documentclass (default: article)"
    )
    parser.add_argument("--fontsize", default="12pt", help="LaTeX font size (default: 12pt)")
    parser.add_argument(
        "--papersize",
        default="a4",
        help='LaTeX paper size, without the "paper" suffix pandoc appends itself (default: a4)',
    )
    parser.add_argument(
        "--margin", default="1in", help="Page margin, passed to the geometry package (default: 1in)"
    )
    parser.add_argument(
        "--csl",
        default=None,
        help=f"CSL style for citations and the bibliography (default: {config.CSL_STYLE_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Write the output here instead of content/rendered/<mirrored path> "
        "-- for a book unit, the directory book.tex \\input-s it from. "
        "Confined to content/ like every other path this writes",
    )
    parser.add_argument(
        "--fragment",
        action="store_true",
        help="Emit an \\input-able LaTeX fragment (no preamble) whose top "
        "heading is a chapter, for assembling a book -- see docs/BOOKS.md",
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


def main(argv: list[str] | None = None) -> int:
    """CLI entry point -- deliberately independent of chitragupta/enrich/__main__.py.

    That script imports docling/embed/topic_model at module load and
    builds the whole corpus before any stage runs, which drags in the
    multi-GB `.venv-full` for a stage that itself only needs stdlib +
    `chitragupta.config` + `chitragupta.citation_gate`. Genre skills that just want a
    tex/pdf rendering of a draft should be able to run this with bare
    `python`, no enrich group required.
    """
    args = _build_parser().parse_args(argv)

    # Deferred, and it has to be: the package root imports this module at
    # its top, before `render` is defined, so a module-scope import here
    # would be a genuine circular-import failure rather than a style
    # choice. `.pylintrc` disables import-outside-toplevel for this
    # pattern, and chitragupta/review/__init__.py reaches this package the same way.
    from chitragupta.render_output import render

    try:
        out_path = render(
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
        )
    except MissingBinary as exc:
        print(f"[missing-binary] {exc}")
        return 1
    except MathMappingError as exc:
        # Non-zero, and deliberately so. A `<!-- math -->` marker is the
        # author stating a displayed equation is here; rendering it as
        # verbatim text instead is the exact defect
        # docs/WRITING-STANDARDS.md §12 exists to prevent, and a warning
        # a skill may carry on past is not enough to stop it shipping.
        # The heuristic gaps stay warnings -- only this is certain.
        print(f"[error] {exc}")
        return 1
    except OutsideContentDir as exc:
        # Reported like any other render failure rather than as a
        # traceback, same as the KeyError below: a genre skill's
        # documented reaction to `[error]` is to warn and carry on
        # presenting the draft, which is right here too -- the draft is
        # fine, and it is the place this copy would have gone that is
        # wrong.
        print(f"[error] {exc}")
        return 1
    except subprocess.CalledProcessError as exc:  # pragma: no cover-windows
        print(f"[error] pandoc failed: {exc.stderr or exc}{_figure_repair_hint(args.input)}")
        return 1
    except references.MissingCitekey as exc:
        # `--format md` builds its reference list from the ledger, so a
        # cited key that isn't there stops it (references.build_section's
        # own error names the keys and what to run). Reported the same way
        # as any other render failure rather than as a traceback: a genre
        # skill's documented reaction to `[error]` is to warn and carry on
        # presenting the draft, which is right here too -- the draft is
        # fine, only this one derived copy could not be built. Caught by
        # this specific exception, not a bare `except KeyError`, so a
        # genuine bug elsewhere in the pipeline surfaces as itself instead
        # of being reported as though it were this refusal (m-60).
        print(f"[error] {exc.args[0] if exc.args else exc}")
        return 1

    print(str(out_path))
    return 0
