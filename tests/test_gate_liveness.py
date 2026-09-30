"""chitragupta/gate_liveness.py: notice an automatic gate that is not running (#812)."""

import json

import pytest

from chitragupta import gate_liveness
from tests.conftest import content_draft

HOOK_PATH = gate_liveness.Path(__file__).resolve().parent.parent / ".claude" / "hooks"


@pytest.fixture(autouse=True)
def no_launcher_faults(monkeypatch):
    # This checkout's own launchers are not what these tests are about.
    monkeypatch.setattr(gate_liveness.launcher_configs, "faults", lambda root: [])
    monkeypatch.delenv(gate_liveness.GATE_CALLER_ENV, raising=False)


def configure(root, rel=".codex/hooks.json"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hooks": {}}), encoding="utf-8")


def draft_in(cfg, text="x\n"):
    draft = content_draft(cfg, "drafts/a.md")
    draft.write_text(text, encoding="utf-8")
    return draft


def as_hook(monkeypatch, paths):
    monkeypatch.setenv(gate_liveness.GATE_CALLER_ENV, "hook")
    gate_liveness.observe([str(p) for p in paths])
    monkeypatch.delenv(gate_liveness.GATE_CALLER_ENV)


def records(cfg):
    return sorted((cfg.CONTENT_DIR / gate_liveness.RECORD_DIR).iterdir())


def test_a_hook_call_records_the_draft(isolated_config, monkeypatch):
    draft = draft_in(isolated_config)
    as_hook(monkeypatch, [draft])
    (record,) = records(isolated_config)
    assert record.name == gate_liveness._record_name("drafts/a.md")
    assert record.read_text("utf-8") == gate_liveness._digest(str(draft))


def test_two_hooks_on_different_drafts_keep_both_records(isolated_config, monkeypatch, capsys):
    # The race one shared file had: parallel subagents writing two drafts
    # at once, each hook reading and rewriting the record, one lost.
    configure(isolated_config.CONTENT_DIR.parent)
    first = draft_in(isolated_config)
    second = content_draft(isolated_config, "drafts/b.md")
    second.write_text("y\n", encoding="utf-8")
    as_hook(monkeypatch, [first])
    as_hook(monkeypatch, [second])
    gate_liveness.observe([str(first), str(second)])
    assert capsys.readouterr().err == ""


def test_a_hook_call_prints_nothing(isolated_config, monkeypatch, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    as_hook(monkeypatch, [draft_in(isolated_config)])
    assert capsys.readouterr().err == ""


def test_a_draft_no_hook_saw_warns(isolated_config, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    gate_liveness.observe([str(draft_in(isolated_config))])
    err = capsys.readouterr().err
    assert "no automatic gate has checked drafts/a.md" in err


def test_a_draft_the_hook_saw_is_quiet(isolated_config, monkeypatch, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    draft = draft_in(isolated_config)
    as_hook(monkeypatch, [draft])
    gate_liveness.observe([str(draft)])
    assert capsys.readouterr().err == ""


def test_an_edit_after_the_hook_warns_again(isolated_config, monkeypatch, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    draft = draft_in(isolated_config)
    as_hook(monkeypatch, [draft])
    draft.write_text("changed through a shell\n", encoding="utf-8")
    gate_liveness.observe([str(draft)])
    assert "no automatic gate has checked" in capsys.readouterr().err


def test_the_opencode_plugin_counts_as_a_configured_harness(isolated_config, capsys):
    root = isolated_config.CONTENT_DIR.parent
    configure(root, gate_liveness.PLUGIN)
    gate_liveness.observe([str(draft_in(isolated_config))])
    assert "no automatic gate has checked" in capsys.readouterr().err


def test_a_project_with_no_harness_configured_is_quiet(isolated_config, capsys):
    gate_liveness.observe([str(draft_in(isolated_config))])
    assert capsys.readouterr().err == ""


def test_a_stale_record_is_treated_as_unseen(isolated_config, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    draft = draft_in(isolated_config)
    record = (
        isolated_config.CONTENT_DIR
        / gate_liveness.RECORD_DIR
        / gate_liveness._record_name("drafts/a.md")
    )
    record.parent.mkdir(parents=True)
    record.write_text("not the digest of this text", encoding="utf-8")
    gate_liveness.observe([str(draft)])
    assert "no automatic gate has checked" in capsys.readouterr().err


def test_an_unreadable_draft_is_left_to_the_gate(isolated_config, monkeypatch, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    missing = isolated_config.CONTENT_DIR / "drafts" / "gone.md"
    as_hook(monkeypatch, [missing])
    gate_liveness.observe([str(missing)])
    assert capsys.readouterr().err == ""


def test_a_path_outside_content_is_keyed_by_its_full_path(isolated_config, tmp_path, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    outside = tmp_path / "elsewhere.md"
    outside.write_text("x\n", encoding="utf-8")
    gate_liveness.observe([str(outside)])
    assert outside.resolve().as_posix() in capsys.readouterr().err


def test_a_record_that_cannot_be_written_never_fails_the_gate(isolated_config, monkeypatch):
    draft = draft_in(isolated_config)
    # A plain file where the record directory should be: every write fails.
    (isolated_config.CONTENT_DIR / gate_liveness.RECORD_DIR).write_text("", encoding="utf-8")
    as_hook(monkeypatch, [draft])  # raises nothing


def test_a_dead_launcher_is_warned_about(isolated_config, monkeypatch, capsys):
    monkeypatch.setattr(gate_liveness.launcher_configs, "faults", lambda root: ["x: dead"])
    gate_liveness.observe([str(draft_in(isolated_config))])
    err = capsys.readouterr().err
    assert "WARNING: x: dead" in err
    assert "docs/HOOKS.md" in err


def test_the_hook_sets_the_variable_this_reads():
    # The hook must not import layer 1 at load time, so the name is written
    # twice; this is what keeps the two from drifting apart.
    text = (HOOK_PATH / "citation_gate_hook.py").read_text(encoding="utf-8")
    assert f'GATE_CALLER_ENV = "{gate_liveness.GATE_CALLER_ENV}"' in text
