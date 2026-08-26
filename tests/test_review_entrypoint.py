"""chitragupta/review/__main__.py: the review layer's single entry point.

What the three aids *compute* is covered in tests/test_citation_provenance.py,
tests/test_citation_coverage.py and tests/test_verbatim_check.py. This
file pins only the dispatch, and the invariant the dispatch exists to
serve: **one entry point per layer, one level deep**, the same shape
`python -m chitragupta.corpus sync` gives the corpus layer.

That invariant went untested for a long time, and the review layer was
one design review away from shipping `python -m chitragupta.review.verbatim_check`
as this repo's first working nested command. The two-level form had been
tried once already, as `chitragupta.heavy.render_output`, and was reverted with
the directory that held it. Nothing noticed either time except a reader
comparing files by eye.

The docs half is tests/test_command_depth_scan.py, which fails when a
doc or a skill introduces a `python -m chitragupta.a.b` invocation in prose.
"""

import importlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import review
from chitragupta.review import __main__ as entrypoint

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every module under chitragupta/review/ that is an aid rather than the entry
# point or the shared helper.
AID_MODULES = [
    "citation_provenance",
    "citation_coverage",
    "verbatim_check",
    "synthesis",
    "figure_layout",
    "agenda",
]

# A real top-level entry-point block, anchored at column 0 -- not the
# string wherever it appears. chitragupta/enrich/docling_parse.py discusses
# `if __name__ == "__main__":` at length in a comment about forkserver
# workers, and a substring check would read that prose as a second entry
# point.
_MAIN_BLOCK = re.compile(r'^if __name__ == ["\']__main__["\']:', re.MULTILINE)

# Every read below passes encoding="utf-8" explicitly. Without it
# read_text() uses the locale codec, which is cp1252 on the Windows CI
# leg, and these sources contain non-ASCII punctuation -- so the check
# died with a UnicodeDecodeError there while passing on Linux. Same
# reason tests/test_skill_verbatim_scan_step.py pins it.


def _aid_sources(module: str) -> list[Path]:
    """Every source file making up one aid, whichever shape it takes.

    An aid is usually one `.py`; `figure_layout` is a package, because
    its three parts need different things (source parsing, arithmetic,
    and the one that shells out to pdflatex) and the whole would cross
    the 250-code-line limit. Both shapes are one subcommand, which is
    what the invariant is actually about.
    """
    base = REPO_ROOT / "chitragupta" / "review" / module
    return sorted(base.glob("*.py")) if base.is_dir() else [base.with_suffix(".py")]


def _run(*argv):
    return subprocess.run(
        [sys.executable, *argv],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


class TestTheSubcommandsAreTheAids:
    # No "the sets are equal" test here, deliberately. `__main__.py`
    # raises on drift at import time, so the import at the top of this
    # file would fail during collection and such an assertion could
    # never be the thing that reports it. What follows tests the guard
    # instead, which is the only falsifiable form of that claim.

    def test_a_drifted_subcommand_set_is_refused_at_import(self, monkeypatch):
        """`review.AIDS` owns the report suffixes, so a subcommand that
        drifted out of it would write a report under a name the rest of
        the layer cannot find -- `dossier` checks `stem.suffix in
        review.AIDS`.

        The guard is a raise rather than an assert because `python -O`
        strips assertions, which would leave the invariant stated but
        unenforced exactly when someone had optimised the interpreter
        and stopped watching.
        """
        monkeypatch.setitem(review.AIDS, "invented", "Not a real aid")
        try:
            with pytest.raises(RuntimeError, match="drifted apart"):
                importlib.reload(entrypoint)
        finally:
            # Undo before the final reload, so the module is left importable
            # for every test after this one.
            monkeypatch.undo()
            importlib.reload(entrypoint)

    @pytest.mark.parametrize("aid", ["provenance", "verbatim", "coverage"])
    def test_every_aid_is_reachable_and_declares_its_own_flags(self, aid):
        """--help rather than a run: this pins that the aid's parser was
        wired in, without needing a corpus."""
        result = _run("-m", "chitragupta.review", aid, "--help")
        assert result.returncode == 0
        assert f"usage: python -m chitragupta.review {aid}" in result.stdout

    def test_no_aid_prints_the_layers_usage_and_exits_zero(self):
        """ "Tell me how to use this" is not an error -- the same rule
        each aid already applies to a missing mode."""
        result = _run("-m", "chitragupta.review")
        assert result.returncode == 0
        assert "provenance" in result.stdout
        assert "verbatim" in result.stdout
        assert "coverage" in result.stdout

    def test_an_unknown_aid_is_a_usage_error(self):
        result = _run("-m", "chitragupta.review", "bogus")
        assert result.returncode == 2
        assert "invalid choice: 'bogus'" in result.stderr


class TestTheCommandSurfaceStaysOneLevelDeep:
    """The invariant this file exists for. See docs/ARCHITECTURE.md."""

    @pytest.mark.parametrize("module", AID_MODULES)
    def test_an_aid_module_has_no_main_block(self, module):
        """`python -m chitragupta.review.<aid>` must not become a second,
        undocumented way in. Without a __main__ block it imports the
        module and exits 0 having done nothing -- which is a trap, but a
        silent and harmless one, and the same one `chitragupta/enrich/`'s stage
        modules carry by design (docs/ARCHITECTURE.md). With one, the
        layer would have five entry points and no single --help.

        An aid may be a module or a package -- `figure_layout` is a
        package, split by what each part needs -- so every source file
        under it is checked, not just its `__init__.py`. A `__main__.py`
        inside the package would be the same defect wearing a different
        filename.
        """
        for source in _aid_sources(module):
            assert not _MAIN_BLOCK.search(source.read_text(encoding="utf-8")), source

    @pytest.mark.parametrize("module", AID_MODULES)
    def test_running_an_aid_module_directly_does_nothing(self, module):
        """The observable half of the assertion above.

        The two shapes fail differently and both are correct. A module
        imports and exits 0 in silence. A *package* cannot be run with
        `-m` at all -- Python refuses it outright, exit 1, because there
        is no `__main__.py` -- which serves this invariant more strongly
        than the silent version does: the trap the docstring above calls
        "silent and harmless" is not even reachable.
        """
        result = _run("-m", f"chitragupta.review.{module}")

        assert result.stdout == ""
        if (REPO_ROOT / "chitragupta" / "review" / module).is_dir():
            assert result.returncode == 1
            assert "cannot be directly executed" in result.stderr
        else:
            assert result.returncode == 0

    def test_the_enrichment_layer_keeps_the_same_shape(self):
        """Not this layer, but the same invariant, and the precedent this
        layer's design was taken from: `--stages` is the only way to run
        an enrichment stage."""
        for module in ["docling_parse", "embed_index", "topic_model"]:
            source = (REPO_ROOT / "chitragupta" / "enrich" / f"{module}.py").read_text(
                encoding="utf-8"
            )
            assert not _MAIN_BLOCK.search(source), module


class TestTheExitCodeContractSurvivesTheDispatch:
    """The aids' own contract, unchanged by being dispatched to: `0` on
    every successful run, findings or not; `1` for a draft the layer will
    not read; `2` for a malformed invocation. A dispatcher that swallowed
    or remapped argparse's exit 2 would show up here."""

    def test_a_draft_outside_content_exits_one(self, tmp_path):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("# draft\n")
        result = _run("-m", "chitragupta.review", "provenance", str(outside))
        assert result.returncode == 1

    def test_a_missing_draft_exits_one(self):
        result = _run("-m", "chitragupta.review", "provenance", "content/drafts/nope.md")
        assert result.returncode == 1

    def test_a_missing_required_flag_exits_two(self):
        """`coverage` without --query: argparse's own error, reached
        through the subparser rather than a top-level parser."""
        result = _run("-m", "chitragupta.review", "coverage", "content/drafts/x.md")
        assert result.returncode == 2
        assert "--query" in result.stderr

    def test_an_out_of_range_flag_value_exits_two(self):
        result = _run(
            "-m", "chitragupta.review", "verbatim", "scan", "content/drafts/x.md", "--gap", "-1"
        )
        assert result.returncode == 2

    def test_recheck_without_a_baseline_exits_two(self):
        """`--baseline` is required: there is nothing to compare against
        without one, and defaulting to the report's usual path would
        silently compare against whatever happened to be lying there."""
        result = _run("-m", "chitragupta.review", "verbatim", "recheck", "content/drafts/x.md")
        assert result.returncode == 2
        assert "--baseline" in result.stderr

    def test_recheck_on_a_draft_outside_content_exits_one(self):
        result = _run(
            "-m",
            "chitragupta.review",
            "verbatim",
            "recheck",
            "README.md",
            "--baseline",
            "whatever.json",
        )
        assert result.returncode == 1

    def test_recheck_is_listed_as_a_verbatim_mode(self):
        result = _run("-m", "chitragupta.review", "verbatim", "--help")
        assert result.returncode == 0
        assert "recheck" in result.stdout
