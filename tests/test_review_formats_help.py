"""Every review aid's `--formats` help names the engine a pdf render runs
(#1022). Ten parsers each carried their own copy, which said
"pandoc/pdflatex" for two releases after #996 moved the render to
LuaLaTeX; they now share `review._emit.add_formats`."""

import argparse
import importlib

import pytest

from chitragupta import install
from chitragupta.review import _emit

AIDS = [
    "citation_provenance", "citation_coverage", "uncited_prose", "quotation",
    "synthesis", "citekey_union", "claim_support", "agenda", "verbatim_check",
    "figure_layout",
]  # fmt: skip


def _formats_action(parser):
    # verbatim_check takes --formats on its `scan` subcommand.
    for action in parser._actions:
        if "--formats" in action.option_strings:
            return action
        if isinstance(action, argparse._SubParsersAction):
            found = [_formats_action(sub) for sub in action.choices.values()]
            return next(a for a in found if a is not None)
    return None


@pytest.mark.parametrize("aid", AIDS)
def test_formats_help_names_the_engine_a_pdf_render_runs(aid):
    parser = importlib.import_module(f"chitragupta.review.{aid}").build_parser()
    action = _formats_action(parser)
    assert action.help == _emit.FORMATS_HELP
    assert action.default == "md,tex,pdf"


def test_the_shared_help_says_lualatex_and_how_to_install_it():
    assert "LuaLaTeX" in _emit.FORMATS_HELP and "pdflatex" not in _emit.FORMATS_HELP
    assert install.remedy("os-deps") in _emit.FORMATS_HELP
