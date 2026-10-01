"""`chitragupta/scaffold_guard.py`: #891 gap 1 -- a `chitragupta/` or
`chitragupta.py` planted into a `chitragupta init`-scaffolded project
after scaffolding, imported by a skill's own `python -m
chitragupta.draft gate` (etc.) with no hook and no `safe_path.py` in
between.

`tests/test_config.py::TestScaffoldGuardIsWired` covers the one line
`chitragupta/config.py` adds to call this at import time; everything
about the decision itself is pinned here, against synthetic trees, the
same split `tests/test_safe_path.py` draws for the hook-side half of
#822.
"""

from pathlib import Path

import pytest

from chitragupta import scaffold_guard


class TestShadowed:
    def test_false_with_no_marker_at_all(self, tmp_path):
        """A plain, unmarked directory -- a checkout, or any directory
        `init` never touched -- is never flagged, whatever it contains."""
        root = tmp_path / "root"
        (root / "chitragupta").mkdir(parents=True)
        package = root / "chitragupta" / "config.py"
        package.write_text("", encoding="utf-8")
        assert scaffold_guard.shadowed(package, root) is False

    def test_false_when_marked_but_the_package_resolves_outside(self, tmp_path):
        """The ordinary, intended shape: `init` scaffolded this project,
        and the real install lives in site-packages, not under the
        project root."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        installed = tmp_path / "site-packages" / "chitragupta" / "config.py"
        installed.parent.mkdir(parents=True)
        installed.write_text("", encoding="utf-8")
        assert scaffold_guard.shadowed(installed, root) is False

    def test_true_when_marked_and_the_package_resolves_inside(self, tmp_path):
        """The attack shape: `init` marked this root as scaffolded (so it
        never shipped a `chitragupta/` of its own), and yet the module
        actually running lives under that very root -- the only way that
        happens is a `chitragupta/` or `chitragupta.py` planted there
        after scaffolding."""
        root = tmp_path / "root"
        (root / scaffold_guard.SCAFFOLD_MARKER).parent.mkdir(parents=True, exist_ok=True)
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = root / "chitragupta" / "config.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        assert scaffold_guard.shadowed(planted, root) is True

    def test_nested_planted_module_still_counts(self, tmp_path):
        """Not only `config.py` itself -- any module under the planted
        package resolves inside the root the same way."""
        root = tmp_path / "root"
        root.mkdir()
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = root / "chitragupta" / "review" / "verbatim_check" / "core.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        assert scaffold_guard.shadowed(planted, root) is True


class TestRefuseIfShadowed:
    def test_a_clean_tree_returns_quietly(self, tmp_path, capsys):
        root = tmp_path / "root"
        root.mkdir()
        package = tmp_path / "site-packages" / "chitragupta" / "config.py"
        package.parent.mkdir(parents=True)
        package.write_text("", encoding="utf-8")
        scaffold_guard.refuse_if_shadowed(package, root)  # does not raise
        assert capsys.readouterr().err == ""

    def test_a_shadowed_tree_exits_one_and_names_both_paths(self, tmp_path, capsys):
        root = tmp_path / "root"
        (root / scaffold_guard.SCAFFOLD_MARKER).parent.mkdir(parents=True, exist_ok=True)
        (root / scaffold_guard.SCAFFOLD_MARKER).write_text("", encoding="utf-8")
        planted = root / "chitragupta" / "config.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("", encoding="utf-8")
        with pytest.raises(SystemExit) as raised:
            scaffold_guard.refuse_if_shadowed(planted, root)
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
