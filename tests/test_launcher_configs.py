"""chitragupta/launcher_configs.py: dead-launcher faults across every harness's config (#812)."""

import json

from chitragupta import launcher_configs


def write(root, rel, program):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    hooks = {"PostToolUse": [{"hooks": [{"type": "command", "command": f"{program} x.py"}]}]}
    path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def test_only_configs_that_exist_are_read(tmp_path):
    write(tmp_path, ".codex/hooks.json", "python")
    assert launcher_configs.present(tmp_path) == [tmp_path / ".codex" / "hooks.json"]


def test_both_configs_are_read_in_order(tmp_path):
    write(tmp_path, ".codex/hooks.json", "python")
    write(tmp_path, ".claude/settings.json", "python")
    assert [p.parent.name for p in launcher_configs.present(tmp_path)] == [".claude", ".codex"]


def test_a_dead_codex_launcher_is_named_with_its_config(tmp_path):
    write(tmp_path, ".codex/hooks.json", "no-such-interpreter-812")
    faults = launcher_configs.faults(tmp_path)
    assert len(faults) == 1
    assert faults[0].startswith(".codex/hooks.json: ")
    assert "no-such-interpreter-812" in faults[0]


def test_the_same_fault_twice_is_reported_once(tmp_path, monkeypatch):
    write(tmp_path, ".codex/hooks.json", "python")
    monkeypatch.setattr(launcher_configs.hook_launchers, "faults", lambda path: ["a", "a"])
    assert launcher_configs.faults(tmp_path) == [".codex/hooks.json: a"]


def test_no_configs_means_no_faults(tmp_path):
    assert launcher_configs.faults(tmp_path) == []
