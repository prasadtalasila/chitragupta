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

import shutil
import sys
from pathlib import Path

import pytest

from chitragupta import scaffold_guard

from tests.conftest import run_python

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestScaffoldedAncestor:
    def test_none_when_no_ancestor_is_even_named_chitragupta(self, tmp_path):
        """The walk finds nothing to check at all: `package_file` itself
        is not under a directory named `chitragupta` -- not a shape any
        real caller produces (every caller here passes a module's own
        `__file__` from inside the package), but the loop must still
        terminate and answer `None` rather than loop forever or raise."""
        stray = tmp_path / "somewhere" / "else.py"
        stray.parent.mkdir(parents=True)
        stray.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(stray) is None

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

    def test_a_project_local_venv_install_is_not_flagged(self, tmp_path):
        """#891 review, round 3: a real regression an unbounded
        walk-every-ancestor version of this check had.
        `<root>/.venv/lib/pythonX.Y/site-packages/chitragupta/config.py`
        is a properly installed package that happens to sit several
        directories under a marked `<root>` -- not planted at
        `<root>/chitragupta/` directly. The package's immediate parent is
        named `site-packages`, an install-directory name, so this must
        stay silent regardless of the marker several levels above."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        installed = (
            root
            / ".venv-full"
            / "lib"
            / "python3.12"
            / "site-packages"
            / "chitragupta"
            / "config.py"
        )
        installed.parent.mkdir(parents=True)
        installed.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(installed) is None

    def test_a_debian_dist_packages_install_is_not_flagged(self, tmp_path):
        """The other mainstream install-directory name (system Python on
        a Debian-family host), same reasoning as `site-packages` above."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        installed = root / "usr" / "lib" / "python3" / "dist-packages" / "chitragupta" / "config.py"
        installed.parent.mkdir(parents=True)
        installed.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(installed) is None

    def test_a_plant_in_a_project_subdirectory_is_still_caught(self, tmp_path):
        """#891 review, round 8: the real bug the round-3 fix (checking
        only the one directory immediately above the package) left open.
        docs/CONFIG.md's project-root discovery walks up for `config.toml`
        from wherever a command runs, so `python -m chitragupta.draft
        gate` from `<root>/content/` is a supported shape, not an
        exotic one -- and a `chitragupta/` planted at
        `<root>/content/chitragupta/` has an immediate parent (`content/`)
        that is not an install-directory name, so the walk continues
        upward and still finds `<root>`'s marker. Reproduced live before
        the fix: the old one-level-only check returned `None` here."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = root / "content" / "chitragupta" / "config.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(planted) == root

    def test_a_plant_several_subdirectories_deep_is_still_caught(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = root / "content" / "drafts" / "some-topic" / "chitragupta" / "config.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        assert scaffold_guard.scaffolded_ancestor(planted) == root


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
        assert str(planted.absolute()) in err
        assert str(root) in err
        assert "scaffolded" in err

    @pytest.mark.skipif(
        sys.platform == "win32", reason="symlinks need elevated privileges on Windows"
    )
    def test_the_fatal_message_names_the_planted_entry_not_a_symlinks_target(
        self, tmp_path, capsys
    ):
        """#891 review: `package_file.resolve()` would have named
        `vendor/config.py` here -- the symlink's target, not the planted
        entry actually sitting under the scaffolded root -- pointing a
        reader's "remove it" at the wrong path entirely."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        real = tmp_path / "vendor" / "chitragupta"
        real.mkdir(parents=True)
        (real / "config.py").write_text("", encoding="utf-8")
        linked = root / "chitragupta"
        linked.symlink_to(real, target_is_directory=True)
        planted = linked / "config.py"
        with pytest.raises(SystemExit):
            scaffold_guard.refuse_if_shadowed(planted)
        err = capsys.readouterr().err
        assert str(planted.absolute()) in err
        assert str((real / "config.py").resolve()) not in err


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need elevated privileges on Windows")
class TestScaffoldedAncestorThroughASymlink:
    """#891 review: a symlinked package directory must still be checked
    at the lexical path Python's import actually selected, not wherever
    the link resolves to."""

    def test_a_symlinked_package_under_a_marked_root_is_still_caught(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        real = tmp_path / "vendor" / "chitragupta"
        real.mkdir(parents=True)
        (real / "config.py").write_text("", encoding="utf-8")
        linked = root / "chitragupta"
        linked.symlink_to(real, target_is_directory=True)
        # Python imports through the top-level, marked entry -- the
        # symlink itself -- so that is the path handed to the check.
        assert scaffold_guard.scaffolded_ancestor(linked / "config.py") == root

    def test_a_symlinked_package_outside_any_marked_root_is_not_flagged(self, tmp_path):
        real = tmp_path / "vendor" / "chitragupta"
        real.mkdir(parents=True)
        (real / "config.py").write_text("", encoding="utf-8")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        linked = elsewhere / "chitragupta"
        linked.symlink_to(real, target_is_directory=True)
        assert scaffold_guard.scaffolded_ancestor(linked / "config.py") is None


class TestUnsafeMarkerReason:
    def test_none_for_a_path_with_nothing_there(self, tmp_path):
        assert scaffold_guard.unsafe_marker_reason(tmp_path / "new-marker") is None

    def test_none_for_an_existing_regular_file(self, tmp_path):
        marker = tmp_path / "marker"
        marker.write_text("", encoding="utf-8")
        assert scaffold_guard.unsafe_marker_reason(marker) is None

    def test_a_directory_is_unsafe(self, tmp_path):
        marker = tmp_path / "marker"
        marker.mkdir()
        reason = scaffold_guard.unsafe_marker_reason(marker)
        assert reason is not None
        assert "not a regular file" in reason

    @pytest.mark.skipif(
        sys.platform == "win32", reason="symlinks need elevated privileges on Windows"
    )
    def test_a_dangling_symlink_is_unsafe(self, tmp_path):
        marker = tmp_path / "marker"
        marker.symlink_to(tmp_path / "nowhere")
        reason = scaffold_guard.unsafe_marker_reason(marker)
        assert reason is not None
        assert "symlink" in reason

    @pytest.mark.skipif(
        sys.platform == "win32", reason="symlinks need elevated privileges on Windows"
    )
    def test_a_symlink_to_a_real_file_is_still_unsafe(self, tmp_path):
        target = tmp_path / "real-file"
        target.write_text("", encoding="utf-8")
        marker = tmp_path / "marker"
        marker.symlink_to(target)
        reason = scaffold_guard.unsafe_marker_reason(marker)
        assert reason is not None
        assert "symlink" in reason


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
        result = run_python("-m", "chitragupta.corpus", "ledger", cwd=planted_checkout)
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
        result = run_python("-m", "chitragupta.corpus", "ledger", cwd=root)
        assert "[fatal]" not in result.stderr

    def test_a_planted_real_copy_in_a_subdirectory_still_refuses(self, planted_checkout):
        """#891 review, round 8: the real subdirectory-plant bug, proven
        end to end through the real, installed `config.py` -- not only
        through `scaffolded_ancestor()` directly (see
        `TestScaffoldedAncestor::test_a_plant_in_a_project_subdirectory_is_still_caught`).
        Moves the planted copy from the project root to `content/`,
        matching docs/CONFIG.md's supported "run from any subdirectory"
        shape, and runs from there instead of from the project root."""
        subdir = planted_checkout / "content"
        subdir.mkdir()
        shutil.move(str(planted_checkout / "chitragupta"), str(subdir / "chitragupta"))
        result = run_python("-m", "chitragupta.corpus", "ledger", cwd=subdir)
        assert result.returncode == 1
        assert "[fatal]" in result.stderr
        assert "scaffolded" in result.stderr
