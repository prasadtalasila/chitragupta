"""`chitragupta/scaffold_guard.py`: #891 gap 1 -- a `chitragupta/`
planted into a `chitragupta init`-scaffolded project after scaffolding,
imported by a skill's own `python -m chitragupta.draft gate` (etc.) with
no hook and no `safe_path.py` in between.

`TestWiredIntoConfig` below is the end-to-end case Copilot review (928)
named by exact test path: a subprocess running the real, installed
`chitragupta/config.py` -- not a mock of it -- against a planted copy of
this checkout's own package, proving `config.py` actually calls
`scaffold_guard.refuse_if_shadowed` at the choke point every `python -m
chitragupta.<layer> ...` invocation passes through, and that removing
that one call would be caught here rather than only by the unit tests
below, which exercise `scaffold_guard` in isolation.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import scaffold_guard

from tests.conftest import _IS_COVERAGE_BOOTSTRAP

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestScaffoldedAncestor:
    def test_none_with_no_marker_anywhere(self, tmp_path):
        """A plain, unmarked directory -- a checkout, or any directory
        `init` never touched -- is never flagged, whatever it contains."""
        root = tmp_path / "root"
        (root / "chitragupta").mkdir(parents=True)
        package = root / "chitragupta" / "config.py"
        package.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(package) is None

    def test_none_when_marked_but_the_package_resolves_outside(self, tmp_path):
        """The ordinary, intended shape: `init` scaffolded this project,
        and the real install lives in site-packages, not under the
        project root."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        installed = tmp_path / "site-packages" / "chitragupta" / "config.py"
        installed.parent.mkdir(parents=True)
        installed.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(installed) is None

    def test_the_marked_root_when_the_package_resolves_inside(self, tmp_path):
        """The attack shape: `init` marked this root as scaffolded (so it
        never shipped a `chitragupta/` of its own), and yet the module
        actually running lives under that very root -- the only way that
        happens is a `chitragupta/` planted there after scaffolding."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = root / "chitragupta" / "config.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(planted) == root

    def test_nested_planted_module_still_counts(self, tmp_path):
        """Not only `config.py` itself -- any module under the planted
        package resolves inside the root the same way."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = root / "chitragupta" / "review" / "verbatim_check" / "core.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(planted) == root

    def test_a_chitragupta_project_data_root_env_var_does_not_blind_it(self, tmp_path, monkeypatch):
        """#891 review: this must not consult `config.PROJECT_ROOT` or
        `CHITRAGUPTA_PROJECT` at all -- a user who points their data at
        one directory while running from inside a *different*, marked,
        shadowed one must not have that override hide the plant. Walking
        up from `package_file` alone, as this does, never looks at the
        env var in the first place."""
        shadowed_root = tmp_path / "shadowed"
        shadowed_root.mkdir()
        (shadowed_root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = shadowed_root / "chitragupta" / "config.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        monkeypatch.setenv("CHITRAGUPTA_PROJECT", str(tmp_path / "elsewhere"))
        assert scaffold_guard.scaffolded_ancestor(planted) == shadowed_root


class TestShadowed:
    def test_false_when_no_ancestor_is_marked(self, tmp_path):
        package = tmp_path / "chitragupta" / "config.py"
        package.parent.mkdir(parents=True)
        package.write_text("", encoding="utf-8")
        assert scaffold_guard.shadowed(package) is False

    def test_true_when_an_ancestor_is_marked(self, tmp_path):
        (tmp_path / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        package = tmp_path / "chitragupta" / "config.py"
        package.parent.mkdir(parents=True)
        package.write_text("", encoding="utf-8")
        assert scaffold_guard.shadowed(package) is True


class TestRefuseIfShadowed:
    def test_a_clean_tree_returns_quietly(self, tmp_path, capsys):
        package = tmp_path / "site-packages" / "chitragupta" / "config.py"
        package.parent.mkdir(parents=True)
        package.write_text("", encoding="utf-8")
        scaffold_guard.refuse_if_shadowed(package)  # does not raise
        assert capsys.readouterr().err == ""

    def test_a_shadowed_tree_exits_one_and_names_both_paths(self, tmp_path, capsys):
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = root / "chitragupta" / "config.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        with pytest.raises(SystemExit) as raised:
            scaffold_guard.refuse_if_shadowed(planted)
        assert raised.value.code == 1
        err = capsys.readouterr().err
        assert str(planted.resolve()) in err
        assert str(root) in err
        assert "scaffolded" in err


def test_marker_literal_matches_init_pys_own_copy():
    """`chitragupta/init.py` duplicates this literal rather than
    importing it (see both modules' docstrings for why); this is the
    test that keeps the two from drifting apart silently."""
    import chitragupta.init as init  # pylint: disable=import-outside-toplevel

    assert scaffold_guard.SCAFFOLD_MARKER == init.SCAFFOLD_MARKER


@pytest.mark.skipif(sys.platform == "win32", reason="chmod/exec-bit semantics differ")
class TestWiredIntoConfig:
    """End to end, through a real subprocess running this checkout's own
    (fixed) `chitragupta/config.py` -- not a mock of it -- as the planted
    copy. Proves `config.py` actually calls
    `scaffold_guard.refuse_if_shadowed` at import time; a refactor that
    dropped that one call would fail this test while every unit test
    above, which only exercises `scaffold_guard` directly, kept passing.
    """

    @pytest.fixture
    def planted_checkout(self, tmp_path):
        """A real copy of this checkout's `chitragupta/` package, planted
        into a project `init` marked as scaffolded."""
        root = tmp_path / "project"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        shutil.copytree(REPO_ROOT / "chitragupta", root / "chitragupta")
        return root

    def test_a_planted_real_copy_refuses(self, planted_checkout):
        result = _run_corpus_ledger(planted_checkout)
        assert result.returncode == 1
        assert "[fatal]" in result.stderr
        assert "scaffolded" in result.stderr

    def test_the_same_tree_without_the_marker_runs_normally(self, tmp_path):
        """Not the marker alone, nor the copied package alone -- the
        combination. A checkout-shaped tree (no marker) must behave like
        any other checkout: no refusal, whatever error the (deliberately
        unconfigured) corpus layer reports instead."""
        root = tmp_path / "project"
        root.mkdir()
        shutil.copytree(REPO_ROOT / "chitragupta", root / "chitragupta")
        result = _run_corpus_ledger(root)
        assert "[fatal]" not in result.stderr
        assert result.returncode != 1 or "scaffolded" not in result.stderr


def _run_corpus_ledger(cwd: Path):
    """`python -m chitragupta.corpus ledger` from `cwd`, with no
    `PYTHONPATH` -- `-m` already puts `cwd` first on `sys.path`
    regardless, so the copied `chitragupta/` there is what resolves,
    exactly as a skill's real invocation would find a planted one. No
    `-S`: the real corpus layer's own third-party imports (bibtexparser)
    still need the real venv's site-packages for the "runs normally"
    control case below to mean anything. Not routed through
    `tests.conftest.run_python`, which always appends this checkout to
    `PYTHONPATH` and would make the child see the real, un-shadowed
    package instead of the planted one under test -- see this file's
    `EXEMPT` entry in `tests/test_subprocess_launch_scan.py`. Coverage
    bootstrap variables are stripped for the same reason
    `tests.conftest.run_python` strips them from any cwd that is not the
    repository root: a child without this checkout's own `pyproject.toml`
    on its path records statement-only coverage, which kills the combine
    step after every test has already passed.
    """
    env = {
        k: v for k, v in os.environ.items() if k != "PYTHONPATH" and not _IS_COVERAGE_BOOTSTRAP(k)
    }
    return subprocess.run(
        [sys.executable, "-m", "chitragupta.corpus", "ledger"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
