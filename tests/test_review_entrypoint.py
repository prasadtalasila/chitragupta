import importlib
import re
from pathlib import Path

import pytest

from chitragupta import review
from chitragupta.review import __main__ as entrypoint
from chitragupta.review import _registry
from tests.conftest import run_python

REPO_ROOT = Path(__file__).resolve().parent.parent

AID_MODULES = [
    "citation_provenance",
    "citation_coverage",
    "verbatim_check",
    "synthesis",
    "figure_layout",
    "agenda",
]

_MAIN_BLOCK = re.compile(r'^if __name__ == ["\']__main__["\']:', re.MULTILINE)


def _aid_sources(module: str) -> list[Path]:
    base = REPO_ROOT / "chitragupta" / "review" / module
    return sorted(base.glob("*.py")) if base.is_dir() else [base.with_suffix(".py")]


class TestTheSubcommandsAreTheAids:
    def test_a_drifted_subcommand_set_is_refused_at_import(self, monkeypatch):
        monkeypatch.setitem(review.AIDS, "invented", "Not a real aid")
        try:
            with pytest.raises(RuntimeError, match="drifted apart"):
                importlib.reload(_registry)
        finally:
            monkeypatch.undo()
            importlib.reload(_registry)

    @pytest.mark.parametrize("aid", ["provenance", "verbatim", "coverage"])
    def test_every_aid_is_reachable_and_declares_its_own_flags(self, aid):
        result = run_python("-m", "chitragupta.review", aid, "--help")
        assert result.returncode == 0
        assert f"Usage: python -m chitragupta.review {aid}" in result.stdout

    def test_no_aid_prints_the_layers_usage_and_exits_zero(self):
        result = run_python("-m", "chitragupta.review")
        assert result.returncode == 0
        assert "provenance" in result.stdout
        assert "verbatim" in result.stdout
        assert "coverage" in result.stdout

    def test_no_aid_in_process_prints_the_usage_too(self, capsys):
        assert entrypoint.main([]) == 0
        out = capsys.readouterr().out
        for aid in ("provenance", "verbatim", "coverage"):
            assert aid in out

    def test_an_unknown_aid_is_a_usage_error(self):
        result = run_python("-m", "chitragupta.review", "bogus")
        assert result.returncode == 2
        assert "invalid choice: 'bogus'" in result.stderr


class TestTheCommandSurfaceStaysOneLevelDeep:
    @pytest.mark.parametrize("module", AID_MODULES)
    def test_an_aid_module_has_no_main_block(self, module):
        for source in _aid_sources(module):
            assert not _MAIN_BLOCK.search(source.read_text(encoding="utf-8")), source

    @pytest.mark.parametrize("module", AID_MODULES)
    def test_running_an_aid_module_directly_does_nothing(self, module):
        result = run_python("-m", f"chitragupta.review.{module}")

        assert result.stdout == ""
        if (REPO_ROOT / "chitragupta" / "review" / module).is_dir():
            assert result.returncode == 1
            assert "cannot be directly executed" in result.stderr
        else:
            assert result.returncode == 0

    def test_the_enrichment_layer_keeps_the_same_shape(self):
        for module in ["docling_parse", "embed_index", "topic_model"]:
            source = (REPO_ROOT / "chitragupta" / "enrich" / f"{module}.py").read_text(
                encoding="utf-8"
            )
            assert not _MAIN_BLOCK.search(source), module


class TestTheExitCodeContractSurvivesTheDispatch:
    def test_a_draft_outside_content_exits_one(self, tmp_path):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("# draft\n")
        result = run_python("-m", "chitragupta.review", "provenance", str(outside))
        assert result.returncode == 1

    def test_a_missing_draft_exits_one(self):
        result = run_python("-m", "chitragupta.review", "provenance", "content/drafts/nope.md")
        assert result.returncode == 1

    def test_a_missing_required_flag_exits_two(self):
        result = run_python("-m", "chitragupta.review", "coverage", "content/drafts/x.md")
        assert result.returncode == 2
        assert "--query" in result.stderr

    def test_an_out_of_range_flag_value_exits_two(self):
        result = run_python(
            "-m", "chitragupta.review", "verbatim", "scan", "content/drafts/x.md", "--gap", "-1"
        )
        assert result.returncode == 2

    def test_recheck_without_a_baseline_exits_two(self):
        result = run_python(
            "-m", "chitragupta.review", "verbatim", "recheck", "content/drafts/x.md"
        )
        assert result.returncode == 2
        assert "--baseline" in result.stderr

    def test_recheck_on_a_draft_outside_content_exits_one(self):
        result = run_python(
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
        result = run_python("-m", "chitragupta.review", "verbatim", "--help")
        assert result.returncode == 0
        assert "recheck" in result.stdout
