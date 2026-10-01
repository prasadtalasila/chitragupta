"""`chitragupta/scaffold_guard.py`: #891 gap 1 -- a `chitragupta/`
planted into a `chitragupta init`-scaffolded project after scaffolding,
imported by a skill's own `python -m chitragupta.draft gate` (etc.) with
no hook and no `safe_path.py` in between.

The unit tests drive `scaffolded_ancestor` with an explicit
`search_path`, standing in for `sys.path`, and with config.py's own
`discover_project_root` as the project finder, exactly as config.py
passes it. Every project root carries a `config.toml`, as every real
scaffold and checkout does. `TestWiredIntoConfig` is the end-to-end half:
a real subprocess running this checkout's own `config.py` as the planted
copy, so dropping the call from config.py fails here even though every
unit test would still pass.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

from chitragupta import config, scaffold_guard

from tests.conftest import run_python

REPO_ROOT = Path(__file__).resolve().parent.parent


def find(start):
    """config.py's own finder, with CHITRAGUPTA_PROJECT ignored."""
    return config.discover_project_root(cwd=start, environ={})


def project(path: Path, *, marked: bool = True) -> Path:
    """A project root: a `config.toml`, and the marker if `init` wrote it."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.toml").write_text("", encoding="utf-8")
    if marked:
        (path / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
    return path


def package(parent: Path, module: str = "config.py") -> Path:
    """A `chitragupta/` under `parent`, returning one module file in it."""
    path = parent / "chitragupta" / module
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def ancestor(path: Path, search_path, environ=None) -> "Path | None":
    return scaffold_guard.scaffolded_ancestor(path, find, [str(p) for p in search_path], environ)


class TestAPlantRunFromItsOwnDirectoryIsCaught:
    """Condition 1 holds: the copy was imported from `sys.path[0]`."""

    def test_at_the_project_root(self, tmp_path):
        root = project(tmp_path / "root")
        assert ancestor(package(root), [root]) == root.resolve()

    def test_any_module_of_it(self, tmp_path):
        root = project(tmp_path / "root")
        assert ancestor(package(root, "review/agenda/_render.py"), [root]) == root.resolve()

    def test_in_a_project_subdirectory(self, tmp_path):
        """#891 review: docs/CONFIG.md supports running from anywhere in
        the project, and an earlier version, checking only the directory
        directly above the package, missed this one."""
        root = project(tmp_path / "root")
        content = root / "content"
        assert ancestor(package(content), [content]) == root.resolve()

    def test_several_subdirectories_deep(self, tmp_path):
        root = project(tmp_path / "root")
        deep = root / "content" / "drafts" / "topic"
        assert ancestor(package(deep), [deep]) == root.resolve()

    def test_when_sys_path_names_the_current_directory_as_empty(self, tmp_path, monkeypatch):
        """`python -c` and the REPL put `''` first, meaning cwd."""
        root = project(tmp_path / "root")
        monkeypatch.chdir(root)
        assert ancestor(package(root), [""]) == root.resolve()

    def test_whatever_chitragupta_project_says(self, tmp_path, monkeypatch):
        """#891 review: the data-root override must not move the check."""
        root = project(tmp_path / "root")
        monkeypatch.setenv("CHITRAGUPTA_PROJECT", str(project(tmp_path / "other", marked=False)))
        assert ancestor(package(root), [root]) == root.resolve()


class TestAnInstallOrACheckoutIsNotCaught:
    def test_a_checkout_has_no_marker(self, tmp_path):
        root = project(tmp_path / "checkout", marked=False)
        assert ancestor(package(root), [root]) is None

    def test_a_venv_inside_the_marked_project(self, tmp_path):
        """#891 review: imported from site-packages, not from cwd."""
        root = project(tmp_path / "root")
        site = root / ".venv-full" / "lib" / "python3.12" / "site-packages"
        assert ancestor(package(site), [root, site]) is None

    def test_an_editable_install_whose_checkout_is_inside_the_marked_project(self, tmp_path):
        """#891 review, reproduced: a vendored checkout under the project,
        reached through an editable install's `.pth` entry."""
        root = project(tmp_path / "root")
        source = root / "tools" / "chitragupta-src"
        assert ancestor(package(source), [root, source]) is None

    def test_running_from_inside_that_editable_checkout(self, tmp_path):
        """Condition 2: the `.pth` entry also puts it later on the path --
        isolated from the real environment's own `PYTHONPATH` with an
        explicit, empty `environ`, since this models a `.pth`-sourced
        duplicate, not a `PYTHONPATH`-sourced one (see the two
        `..._but_only_via_pythonpath` tests below for that distinction)."""
        root = project(tmp_path / "root")
        source = root / "tools" / "chitragupta-src"
        assert ancestor(package(source), [source, root / "lib", source], environ={}) is None

    def test_a_pythonpath_dot_does_not_disable_the_guard(self, tmp_path, monkeypatch):
        """#891 review: `PYTHONPATH=.` (a common shell/direnv habit) used
        to satisfy condition 2 and turn the check off for a plant sitting
        in plain sight. `.` is relative to this *process's* cwd, so the
        test chdirs into `root` first, matching what a real `-m` child
        run from there would see. Reproduced live before the fix: no
        refusal."""
        root = project(tmp_path / "root")
        planted = package(root)
        monkeypatch.chdir(root)
        environ = {"PYTHONPATH": "."}
        assert ancestor(planted, [root, root], environ=environ) == root.resolve()

    def test_a_pythonpath_naming_the_import_root_directly_does_not_disable_it(self, tmp_path):
        root = project(tmp_path / "root")
        planted = package(root)
        environ = {"PYTHONPATH": str(root)}
        assert ancestor(planted, [root, root], environ=environ) == root.resolve()

    def test_an_editable_checkout_reached_only_through_pythonpath_is_still_caught(self, tmp_path):
        """The accepted cost the suggested fix names: an *unconfigured*
        checkout (no config.toml of its own yet) put on the path only via
        PYTHONPATH, under a marked root, and run from inside itself, is
        refused rather than exempted -- condition 3 would have exempted a
        properly configured one regardless."""
        root = project(tmp_path / "root")
        source = root / "tools" / "chitragupta-src"
        source.mkdir(parents=True)
        planted = package(source)
        environ = {"PYTHONPATH": str(source)}
        assert ancestor(planted, [source, source], environ=environ) == root.resolve()

    def test_a_checkout_inside_a_marked_directory(self, tmp_path):
        """#891 review: `chitragupta init ~` must not block every checkout
        below it. The checkout's own config.toml is its project, unmarked."""
        home = project(tmp_path / "home")
        checkout = project(home / "code" / "chitragupta", marked=False)
        assert ancestor(package(checkout), [checkout]) is None

    def test_a_target_install_inside_the_marked_project(self, tmp_path):
        root = project(tmp_path / "root")
        vendor = root / "vendor"
        assert ancestor(package(vendor), [root, vendor]) is None

    def test_no_project_at_all(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "PACKAGE_ROOT", tmp_path / "nowhere" / "chitragupta")
        loose = tmp_path / "loose"
        assert ancestor(package(loose), [loose]) is None

    def test_no_chitragupta_directory_above_the_file(self, tmp_path):
        stray = tmp_path / "somewhere" / "else.py"
        stray.parent.mkdir(parents=True)
        stray.write_text("", encoding="utf-8")
        assert ancestor(stray, [stray.parent]) is None

    def test_an_empty_search_path(self, tmp_path):
        root = project(tmp_path / "root")
        assert ancestor(package(root), []) is None

    def test_sys_path_is_the_default(self, tmp_path, monkeypatch):
        root = project(tmp_path / "root")
        monkeypatch.setattr(sys, "path", [str(root)])
        assert scaffold_guard.scaffolded_ancestor(package(root), find) == root.resolve()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need elevated privileges on Windows")
class TestASymlinkedPackage:
    """#891 review: judged at the path Python imported, not the target."""

    def test_linked_under_a_marked_root_is_caught(self, tmp_path):
        root = project(tmp_path / "root")
        real = package(tmp_path / "vendor").parent
        (root / "chitragupta").symlink_to(real, target_is_directory=True)
        assert ancestor(root / "chitragupta" / "config.py", [root]) == root.resolve()

    def test_linked_under_an_unmarked_root_is_not(self, tmp_path):
        root = project(tmp_path / "root", marked=False)
        real = package(tmp_path / "vendor").parent
        (root / "chitragupta").symlink_to(real, target_is_directory=True)
        assert ancestor(root / "chitragupta" / "config.py", [root]) is None


class TestRefuseIfShadowed:
    def test_a_clean_tree_returns_quietly(self, tmp_path, capsys):
        root = project(tmp_path / "checkout", marked=False)
        scaffold_guard.refuse_if_shadowed(package(root), find, [str(root)])
        assert capsys.readouterr().err == ""

    def test_a_plant_exits_one_and_names_both_paths(self, tmp_path, capsys):
        root = project(tmp_path / "root")
        planted = package(root)
        with pytest.raises(SystemExit) as raised:
            scaffold_guard.refuse_if_shadowed(planted, find, [str(root)])
        assert raised.value.code == 1
        err = capsys.readouterr().err
        assert str(planted.absolute()) in err
        assert str(root.resolve()) in err

    @pytest.mark.skipif(
        sys.platform == "win32", reason="symlinks need elevated privileges on Windows"
    )
    def test_the_message_names_the_planted_entry_not_the_links_target(self, tmp_path, capsys):
        """#891 review: naming the target would point "remove it" at the
        wrong path."""
        root = project(tmp_path / "root")
        real = package(tmp_path / "vendor")
        (root / "chitragupta").symlink_to(real.parent, target_is_directory=True)
        planted = root / "chitragupta" / "config.py"
        with pytest.raises(SystemExit):
            scaffold_guard.refuse_if_shadowed(planted, find, [str(root)])
        err = capsys.readouterr().err
        assert str(planted.absolute()) in err
        assert str(real.resolve()) not in err


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
        assert "not a regular file" in scaffold_guard.unsafe_marker_reason(marker)

    @pytest.mark.skipif(
        sys.platform == "win32", reason="symlinks need elevated privileges on Windows"
    )
    def test_a_dangling_symlink_is_unsafe(self, tmp_path):
        marker = tmp_path / "marker"
        marker.symlink_to(tmp_path / "nowhere")
        assert "symlink" in scaffold_guard.unsafe_marker_reason(marker)

    @pytest.mark.skipif(
        sys.platform == "win32", reason="symlinks need elevated privileges on Windows"
    )
    def test_a_symlink_to_a_real_file_is_still_unsafe(self, tmp_path):
        target = tmp_path / "real-file"
        target.write_text("", encoding="utf-8")
        marker = tmp_path / "marker"
        marker.symlink_to(target)
        assert "symlink" in scaffold_guard.unsafe_marker_reason(marker)


class TestWiredIntoConfig:
    """End to end: a real subprocess runs this checkout's own config.py as
    the planted copy, through `run_python` -- whose appended PYTHONPATH
    cannot outrank `-m`'s `sys.path[0]`, so the copy at cwd is the one
    imported."""

    @staticmethod
    def plant(parent: Path) -> None:
        shutil.copytree(REPO_ROOT / "chitragupta", parent / "chitragupta")

    def test_a_planted_copy_refuses(self, tmp_path):
        root = project(tmp_path / "project")
        self.plant(root)
        result = run_python("-m", "chitragupta.corpus", "ledger", cwd=root)
        assert result.returncode == 1
        assert "[fatal]" in result.stderr

    def test_a_planted_copy_in_a_subdirectory_refuses(self, tmp_path):
        root = project(tmp_path / "project")
        content = root / "content"
        content.mkdir()
        self.plant(content)
        result = run_python("-m", "chitragupta.corpus", "ledger", cwd=content)
        assert result.returncode == 1
        assert "[fatal]" in result.stderr

    def test_the_same_tree_without_the_marker_is_not_refused(self, tmp_path):
        root = project(tmp_path / "project", marked=False)
        self.plant(root)
        result = run_python("-m", "chitragupta.corpus", "ledger", cwd=root)
        assert "[fatal]" not in result.stderr

    def test_a_target_style_install_reached_through_pythonpath_is_not_refused(self, tmp_path):
        """#891 review, reproduced end to end: the package reached through
        PYTHONPATH from a directory other than cwd -- a `--target` install
        -- run from the project root."""
        root = project(tmp_path / "project")
        source = root / "tools" / "chitragupta-src"
        source.mkdir(parents=True)
        self.plant(source)
        env = {**os.environ, "PYTHONPATH": str(source)}
        result = run_python("-m", "chitragupta.corpus", "ledger", cwd=root, env=env)
        assert "[fatal]" not in result.stderr

    def test_pythonpath_dot_does_not_disable_the_guard(self, tmp_path):
        """#891 review: `PYTHONPATH=.` (a common shell/direnv habit) used
        to satisfy condition 2 and turn this check off entirely for a
        plant sitting directly at the project root -- reproduced live
        before the fix: no refusal at all with this env var set."""
        root = project(tmp_path / "project")
        self.plant(root)
        env = {**os.environ, "PYTHONPATH": "."}
        result = run_python("-m", "chitragupta.corpus", "ledger", cwd=root, env=env)
        assert result.returncode == 1
        assert "[fatal]" in result.stderr
