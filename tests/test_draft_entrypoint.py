import re
from pathlib import Path

import pytest

from chitragupta import draft as entrypoint
from tests.conftest import run_python

REPO_ROOT = Path(__file__).resolve().parent.parent

BACKING_MODULES = {
    "gate": "citation_gate",
    "dossier": "dossier",
    "retrieve": "retrieval",
    "references": "references",
    "evidence": "evidence_appendix",
    "render": "render_output",
    "style": "style_check",
    "spec": "spec",
    "unit": "unit",
    "registry": "registry",
    "tldr": "tldr",
    "figures": "draft_figures",
    "diff": "draft_diff",
}

_MAIN_BLOCK = re.compile(r'^if __name__ == ["\']__main__["\']:', re.MULTILINE)


class TestTheVerbsAreTheDraftingCommands:
    def test_the_verb_set_is_exactly_the_backing_modules(self):
        assert set(entrypoint.VERBS) == set(BACKING_MODULES)

    @pytest.mark.parametrize("verb", sorted(BACKING_MODULES))
    def test_every_verb_is_reachable_and_declares_its_own_flags(self, verb):
        result = run_python("-m", "chitragupta.draft", verb, "--help")
        assert result.returncode == 0
        assert f"chitragupta.draft {verb}" in result.stdout

    def test_no_verb_prints_the_layers_usage_and_exits_zero(self):
        result = run_python("-m", "chitragupta.draft")
        assert result.returncode == 0
        for verb in BACKING_MODULES:
            assert verb in result.stdout

    def test_no_verb_in_process_prints_the_usage_too(self, capsys):
        assert entrypoint.main([]) == 0
        out = capsys.readouterr().out
        for verb in BACKING_MODULES:
            assert verb in out

    def test_an_unknown_verb_is_a_usage_error(self):
        result = run_python("-m", "chitragupta.draft", "bogus")
        assert result.returncode == 2
        assert "invalid choice: 'bogus'" in result.stderr


class TestTheCommandSurfaceStaysOneLevelDeep:
    @pytest.mark.parametrize("module", sorted(BACKING_MODULES.values()))
    def test_a_backing_module_has_no_main_block(self, module):
        as_package = REPO_ROOT / "chitragupta" / module / "__init__.py"
        if as_package.is_file():
            assert not (REPO_ROOT / "chitragupta" / module / "__main__.py").is_file()
            return
        source = (REPO_ROOT / "chitragupta" / f"{module}.py").read_text(encoding="utf-8")
        assert not _MAIN_BLOCK.search(source)

    @pytest.mark.parametrize("module", sorted(BACKING_MODULES.values()))
    def test_running_a_backing_module_directly_does_nothing(self, module):
        result = run_python("-m", f"chitragupta.{module}")
        if (REPO_ROOT / "chitragupta" / module / "__init__.py").is_file():
            assert result.returncode == 1
            assert "cannot be directly executed" in result.stderr
            assert result.stdout == ""
            return
        assert result.returncode == 0
        assert result.stdout == ""


class TestTheExitCodeContractSurvivesTheDispatch:
    def test_gate_on_a_draft_outside_content_exits_one(self, tmp_path):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("# draft\n")
        result = run_python("-m", "chitragupta.draft", "gate", str(outside))
        assert result.returncode == 1

    def test_gate_with_no_files_exits_two(self):
        result = run_python("-m", "chitragupta.draft", "gate")
        assert result.returncode == 2

    def test_references_on_a_draft_outside_content_exits_one(self, tmp_path):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("# draft\n")
        result = run_python("-m", "chitragupta.draft", "references", str(outside))
        assert result.returncode == 1

    def test_references_with_no_input_exits_two(self):
        result = run_python("-m", "chitragupta.draft", "references")
        assert result.returncode == 2
        assert "input" in result.stderr

    def test_render_on_a_draft_outside_content_exits_one(self, tmp_path):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("# draft\n")
        result = run_python("-m", "chitragupta.draft", "render", str(outside))
        assert result.returncode == 1

    def test_render_with_no_input_exits_two(self):
        result = run_python("-m", "chitragupta.draft", "render")
        assert result.returncode == 2
        assert "input" in result.stderr

    def test_dossier_status_on_a_nonexistent_draft_exits_one(self):
        result = run_python(
            "-m", "chitragupta.draft", "dossier", "status", "content/drafts/does-not-exist-nope.md"
        )
        assert result.returncode == 1

    def test_dossier_init_without_required_genre_exits_two(self, tmp_path):
        draft = tmp_path / "x.md"
        draft.write_text("# draft\n")
        result = run_python("-m", "chitragupta.draft", "dossier", "init", str(draft))
        assert result.returncode == 2
        assert "--genre" in result.stderr

    def test_retrieve_search_without_required_query_exits_two(self):
        result = run_python("-m", "chitragupta.draft", "retrieve", "search")
        assert result.returncode == 2
        assert "query" in result.stderr


class TestHelpIsOneCommandPerLine:
    def test_help_lists_one_command_per_line(self, monkeypatch, capsys):
        monkeypatch.setenv("COLUMNS", "80")
        monkeypatch.setattr("sys.argv", ["chitragupta"])
        with pytest.raises(SystemExit) as excinfo:
            entrypoint.main(["--help"])
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        for verb in entrypoint.VERBS:
            assert f"\n  {verb} " in out
        assert " / " not in out
        assert out.endswith("Run 'chitragupta draft COMMAND --help' for a command's flags.\n")

    def test_diff_row_says_what_it_compares_and_is_not_cut(self, monkeypatch, capsys):
        monkeypatch.setenv("COLUMNS", "80")
        monkeypatch.setattr("sys.argv", ["chitragupta"])
        with pytest.raises(SystemExit) as excinfo:
            entrypoint.main(["--help"])
        assert excinfo.value.code == 0
        (row,) = [
            line for line in capsys.readouterr().out.splitlines() if line.startswith("  diff ")
        ]
        assert "since a snapshot" in row
        assert not row.endswith("...")

    def test_verbs_and_help_index_agree(self):
        from chitragupta import command_help

        assert {verb: text for verb, (_, text) in entrypoint.VERBS.items()} == (
            command_help.verbs("draft")
        )


_THIRD_PARTY = (
    "print(sorted({m.split('.')[0] for m in sys.modules}"
    " - set(sys.stdlib_module_names) - {'chitragupta', '__main__'}))"
)


def test_gate_adds_only_the_stdlib_help_modules():
    gate = run_python(
        "-c",
        "import runpy, sys\n"
        "sys.argv = ['x', 'gate', '--help']\n"
        "try:\n    runpy.run_module('chitragupta.draft', run_name='__main__')\n"
        "except SystemExit:\n    pass\n"
        f"{_THIRD_PARTY}\n"
        "print('chitragupta.help_format' in sys.modules)",
    )
    baseline = run_python("-c", f"import sys\n{_THIRD_PARTY}")
    *_, third_party, loaded_help = gate.stdout.splitlines()
    assert third_party == baseline.stdout.strip()
    assert loaded_help == "True"
