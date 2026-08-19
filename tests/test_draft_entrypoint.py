"""chitragupta/draft.py: the drafting layer's single entry point.

What each command *computes* is covered in their own test
files (tests/test_citation_gate.py, tests/test_dossier.py,
tests/test_retrieval.py, tests/test_references.py,
tests/test_render_output.py). This file pins only the dispatch, and the
invariant the dispatch exists to serve: **one entry point per layer, one
level deep**, the same shape `python -m chitragupta.corpus sync` and `python -m
chitragupta.review <aid>` already give their layers.

Modeled closely on tests/test_review_entrypoint.py, which pinned the same
invariant for the review layer first and caught the two-level form
(`python -m chitragupta.review.verbatim_check`) before it shipped.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import draft as entrypoint

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every module the dispatcher forwards to, keyed by the verb chitragupta/draft.py
# uses for it.
BACKING_MODULES = {
    "gate": "citation_gate",
    "dossier": "dossier",
    "retrieve": "retrieval",
    "references": "references",
    "render": "render_output",
    "style": "style_check",
    "spec": "spec",
    "unit": "unit",
    "registry": "registry",
}

# A real top-level entry-point block, anchored at column 0 -- not the
# string wherever it appears. Same reasoning as test_review_entrypoint.py:
# a substring check can be fooled by a comment discussing
# `if __name__ == "__main__":` in prose.
_MAIN_BLOCK = re.compile(r'^if __name__ == ["\']__main__["\']:', re.MULTILINE)


def _run(*argv):
    return subprocess.run(
        [sys.executable, *argv],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )


class TestTheVerbsAreTheDraftingCommands:
    def test_the_verb_set_is_exactly_the_backing_modules(self):
        assert set(entrypoint.VERBS) == set(BACKING_MODULES)

    @pytest.mark.parametrize("verb", sorted(BACKING_MODULES))
    def test_every_verb_is_reachable_and_declares_its_own_flags(self, verb):
        """--help rather than a run: this pins that the verb's own parser
        (or, for `gate`, its own usage text) was wired in, without
        needing a corpus."""
        result = _run("-m", "chitragupta.draft", verb, "--help")
        assert result.returncode == 0
        assert f"chitragupta.draft {verb}" in result.stdout

    def test_no_verb_prints_the_layers_usage_and_exits_zero(self):
        """"Tell me how to use this" is not an error -- the same rule
        each of the commands already applies to a missing mode."""
        result = _run("-m", "chitragupta.draft")
        assert result.returncode == 0
        for verb in BACKING_MODULES:
            assert verb in result.stdout

    def test_an_unknown_verb_is_a_usage_error(self):
        result = _run("-m", "chitragupta.draft", "bogus")
        assert result.returncode == 2
        assert "invalid choice: 'bogus'" in result.stderr


class TestTheCommandSurfaceStaysOneLevelDeep:
    """The invariant this file exists for. See docs/ARCHITECTURE.md."""

    @pytest.mark.parametrize("module", sorted(BACKING_MODULES.values()))
    def test_a_backing_module_has_no_main_block(self, module):
        """`python -m src.<module>` must not become a second,
        undocumented way in. Without a __main__ block it imports the
        module and exits 0 having done nothing -- which is a trap, but a
        silent and harmless one, and the same one `chitragupta/enrich/`'s and
        `chitragupta/review/`'s submodules carry by design. With one, the layer
        would have one entry point per module and no single --help.

        `dossier` is a package since #219, not a flat file -- the
        equivalent property for a package is no `__main__.py` inside it,
        which `python -m` would run in the flat modules' place.
        """
        as_package = REPO_ROOT / "chitragupta" / module / "__init__.py"
        if as_package.is_file():
            assert not (REPO_ROOT / "chitragupta" / module / "__main__.py").is_file()
            return
        source = (REPO_ROOT / "chitragupta" / f"{module}.py").read_text(encoding="utf-8")
        assert not _MAIN_BLOCK.search(source)

    @pytest.mark.parametrize("module", sorted(BACKING_MODULES.values()))
    def test_running_a_backing_module_directly_does_nothing(self, module):
        """The observable half of the assertion above.

        A package without `__main__.py` can't reach this silently:
        Python's own `-m` machinery refuses to run it at all, exit 1
        with a message on stderr rather than exit 0 with empty stdout.
        Still nothing a drafting-layer command does -- checked here,
        not assumed, the same as the flat-module case below it.
        """
        result = _run("-m", f"chitragupta.{module}")
        if (REPO_ROOT / "chitragupta" / module / "__init__.py").is_file():
            assert result.returncode == 1
            assert "cannot be directly executed" in result.stderr
            assert result.stdout == ""
            return
        assert result.returncode == 0
        assert result.stdout == ""


class TestTheExitCodeContractSurvivesTheDispatch:
    """Each command's own contract, unchanged by being dispatched to. `0`
    on success, `1` on a refusal the command already reported gracefully
    (outside content/, missing ledger, missing dossier), `2` for a
    malformed invocation. A dispatcher that swallowed or remapped
    argparse's exit 2, or that mis-forwarded argv so a flag landed on the
    wrong parser, would show up here."""

    def test_gate_on_a_draft_outside_content_exits_one(self, tmp_path):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("# draft\n")
        result = _run("-m", "chitragupta.draft", "gate", str(outside))
        assert result.returncode == 1

    def test_gate_with_no_files_exits_two(self):
        result = _run("-m", "chitragupta.draft", "gate")
        assert result.returncode == 2

    def test_references_on_a_draft_outside_content_exits_one(self, tmp_path):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("# draft\n")
        result = _run("-m", "chitragupta.draft", "references", str(outside))
        assert result.returncode == 1

    def test_references_with_no_input_exits_two(self):
        result = _run("-m", "chitragupta.draft", "references")
        assert result.returncode == 2
        assert "input" in result.stderr

    def test_render_on_a_draft_outside_content_exits_one(self, tmp_path):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("# draft\n")
        result = _run("-m", "chitragupta.draft", "render", str(outside))
        assert result.returncode == 1

    def test_render_with_no_input_exits_two(self):
        result = _run("-m", "chitragupta.draft", "render")
        assert result.returncode == 2
        assert "input" in result.stderr

    def test_dossier_status_on_a_nonexistent_draft_exits_one(self):
        result = _run("-m", "chitragupta.draft", "dossier", "status", "content/drafts/does-not-exist-nope.md")
        assert result.returncode == 1

    def test_dossier_init_without_required_genre_exits_two(self, tmp_path):
        draft = tmp_path / "x.md"
        draft.write_text("# draft\n")
        result = _run("-m", "chitragupta.draft", "dossier", "init", str(draft))
        assert result.returncode == 2
        assert "--genre" in result.stderr

    def test_retrieve_search_without_required_query_exits_two(self):
        result = _run("-m", "chitragupta.draft", "retrieve", "search")
        assert result.returncode == 2
        assert "query" in result.stderr
