import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / ".claude" / "hooks"


@pytest.fixture
def sp():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location("safe_path", HOOKS / "safe_path.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolving_to(monkeypatch, sp, origin):
    spec = None if origin is False else SimpleNamespace(origin=origin)
    monkeypatch.setattr(sp.importlib.util, "find_spec", lambda name: spec)


class TestInstalledElsewhere:
    def test_a_package_outside_the_project_is_an_install(self, sp, monkeypatch, tmp_path):
        resolving_to(monkeypatch, sp, str(REPO_ROOT / "chitragupta" / "__init__.py"))
        assert sp.installed_elsewhere(tmp_path) is True

    def test_a_package_inside_the_project_is_a_checkout(self, sp, monkeypatch, tmp_path):
        resolving_to(monkeypatch, sp, str(tmp_path / "chitragupta" / "__init__.py"))
        assert sp.installed_elsewhere(tmp_path) is False

    def test_no_package_at_all_is_left_as_a_checkout(self, sp, monkeypatch, tmp_path):
        resolving_to(monkeypatch, sp, False)
        assert sp.installed_elsewhere(tmp_path) is False

    def test_a_namespace_package_has_no_origin_to_judge(self, sp, monkeypatch, tmp_path):
        resolving_to(monkeypatch, sp, None)
        assert sp.installed_elsewhere(tmp_path) is False

    def test_the_default_root_is_the_hooks_own_project(self, sp, monkeypatch):
        resolving_to(monkeypatch, sp, str(REPO_ROOT / "chitragupta" / "__init__.py"))
        assert sp.REPO_ROOT == REPO_ROOT
        assert sp.installed_elsewhere() is False


class TestChildEnv:
    def test_an_install_gets_safe_path(self, sp, monkeypatch, tmp_path):
        monkeypatch.setattr(sp, "installed_elsewhere", lambda root: True)
        env = sp.child_env(tmp_path, {"KEEP": "me"})
        assert env == {"KEEP": "me", "PYTHONSAFEPATH": "1"}

    def test_a_checkout_is_left_as_it_was(self, sp, monkeypatch, tmp_path):
        monkeypatch.setattr(sp, "installed_elsewhere", lambda root: False)
        assert sp.child_env(tmp_path, {"KEEP": "me"}) == {"KEEP": "me"}

    def test_the_default_base_is_this_process_environment(self, sp, monkeypatch, tmp_path):
        monkeypatch.setattr(sp, "installed_elsewhere", lambda root: False)
        monkeypatch.setenv("SAFE_PATH_PROBE", "inherited")
        assert sp.child_env(tmp_path)["SAFE_PATH_PROBE"] == "inherited"

    def test_the_base_passed_in_is_not_mutated(self, sp, monkeypatch, tmp_path):
        monkeypatch.setattr(sp, "installed_elsewhere", lambda root: True)
        base = {"KEEP": "me"}
        sp.child_env(tmp_path, base)
        assert base == {"KEEP": "me"}
