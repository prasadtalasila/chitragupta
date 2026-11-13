"""Tests for chitragupta/dossier/_versions.py, the snapshot store.

A snapshot is what a later `draft diff` compares against, and nothing
else keeps the earlier text: `content/` is outside git on purpose. So
the weight here is on the two ways a snapshot can be wrong without
anyone noticing -- missing a figure the draft names, or being taken
under a number or label that `--against` would resolve to the wrong
one.
"""

import json
import shutil

import pytest

from chitragupta import config, dossier
from chitragupta.dossier import dossier_dir
from chitragupta.dossier import _retrieval, _versions
from chitragupta.dossier._versions import VersionError

_MD_DRAFT = "# A survey\n\n## 1. First\n\ntext\n\n<!-- figure: figures/estimator-loop -->\n"


def _draft(name="survey.md", text=_MD_DRAFT):
    path = config.DRAFTS_DIR / "dt" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _figure(draft, base, forms=(".tex", ".txt")):
    for suffix in forms:
        path = draft.parent / f"{base}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{base}{suffix} body\n", encoding="utf-8")


def _versions_dir(draft):
    return dossier_dir(draft) / _versions.VERSIONS_DIR


def test_first_snapshot_is_001_and_holds_draft_figures_and_manifest(isolated_config):
    draft = _draft()
    _figure(draft, "figures/estimator-loop")

    snap = _versions.take(draft, trigger="mark-revision", revision_label="pass 1")

    assert snap.number == 1 and snap.ref == "001"
    assert snap.path == _versions_dir(draft) / "001"
    assert snap.source.read_bytes() == draft.read_bytes()
    figures = snap.path / "figures"
    assert (figures / "estimator-loop.tex").read_text() == "figures/estimator-loop.tex body\n"
    assert (figures / "estimator-loop.txt").read_text() == "figures/estimator-loop.txt body\n"
    manifest = json.loads((snap.path / "snapshot.json").read_text())
    # Every field but `path`, which is where the manifest sits and so is
    # never written into it: an absolute path would not survive
    # `dossier export` onto another machine.
    assert set(manifest) == {
        "number",
        "label",
        "taken_at",
        "trigger",
        "revision_label",
        "fingerprint",
        "draft_name",
    }
    assert manifest["trigger"] == "mark-revision"
    assert manifest["revision_label"] == "pass 1"
    assert manifest["draft_name"] == "survey.md"
    assert manifest["label"] == ""


def test_only_figures_the_draft_names_are_copied(isolated_config):
    draft = _draft()
    _figure(draft, "figures/estimator-loop")
    _figure(draft, "figures/unused")

    snap = _versions.take(draft, trigger="mark-revision")

    assert sorted(p.name for p in (snap.path / "figures").iterdir()) == [
        "estimator-loop.tex",
        "estimator-loop.txt",
    ]


def test_a_named_figure_with_no_files_is_skipped_silently(isolated_config):
    draft = _draft()

    snap = _versions.take(draft, trigger="mark-revision")

    assert snap.source.is_file()
    assert not (snap.path / "figures").exists()


def test_mark_revision_snapshot_is_skipped_when_unchanged(isolated_config):
    draft = _draft()
    assert _versions.take(draft, trigger="mark-revision") is not None

    assert _versions.take(draft, trigger="mark-revision") is None
    assert [p.name for p in _versions_dir(draft).iterdir()] == ["001"]


def test_mark_revision_snapshot_is_taken_after_an_edit(isolated_config):
    draft = _draft()
    _versions.take(draft, trigger="mark-revision")
    draft.write_text(_MD_DRAFT + "\nmore\n", encoding="utf-8")

    assert _versions.take(draft, trigger="mark-revision").ref == "002"


def test_manual_snapshot_is_taken_even_when_unchanged(isolated_config):
    draft = _draft()
    _versions.take(draft, trigger="mark-revision")

    snap = _versions.take(draft, trigger="manual", label="milestone")

    assert snap is not None and snap.number == 2
    assert snap.trigger == "manual"


def test_label_becomes_a_slug_suffix(isolated_config):
    draft = _draft()
    _versions.take(draft, trigger="mark-revision")

    snap = _versions.take(draft, trigger="manual", label="Sent to supervisor")

    assert snap.path == _versions_dir(draft) / "002-sent-to-supervisor"
    assert snap.label == "Sent to supervisor"
    assert _versions.list_versions(draft)[1] == snap


@pytest.mark.parametrize("bad", ["", "  ", "123", "§ → ‽", "§4 →"])
def test_manual_label_refused(isolated_config, bad):
    draft = _draft()

    with pytest.raises(VersionError):
        _versions.take(draft, trigger="manual", label=bad)
    assert not _versions_dir(draft).exists()


def test_label_slug_folds_accents_and_collapses_runs():
    assert _versions.label_slug("  Café -- Draft #2!  ") == "cafe-draft-2"


def test_duplicate_label_refused(isolated_config):
    draft = _draft()
    _versions.take(draft, trigger="manual", label="Sent to supervisor")

    with pytest.raises(VersionError, match="sent-to-supervisor"):
        _versions.take(draft, trigger="manual", label="sent  TO supervisor")


def test_unknown_trigger_refused(isolated_config):
    with pytest.raises(VersionError, match="trigger"):
        _versions.take(_draft(), trigger="cron")


def test_resolve_by_number_label_and_latest(isolated_config):
    draft = _draft()
    _versions.take(draft, trigger="mark-revision")
    labelled = _versions.take(draft, trigger="manual", label="Sent to supervisor")
    draft.write_text(_MD_DRAFT + "\nmore\n", encoding="utf-8")
    newest = _versions.take(draft, trigger="mark-revision")

    assert _versions.resolve(draft, "2") == labelled
    assert _versions.resolve(draft, "002") == labelled
    assert _versions.resolve(draft, "sent-to-supervisor") == labelled
    assert _versions.resolve(draft, "Sent to supervisor") == labelled
    assert _versions.resolve(draft, None) == newest == _versions.latest(draft)
    assert [s.number for s in _versions.list_versions(draft)] == [1, 2, 3]


def test_resolve_unknown_lists_what_exists(isolated_config):
    draft = _draft()
    _versions.take(draft, trigger="mark-revision")
    _versions.take(draft, trigger="manual", label="Sent to supervisor")

    with pytest.raises(VersionError) as raised:
        _versions.resolve(draft, "7")
    assert "001" in str(raised.value)
    assert "sent-to-supervisor" in str(raised.value)


def test_resolve_with_no_versions_names_mark_revision_and_against(isolated_config):
    draft = _draft()

    assert _versions.latest(draft) is None
    assert _versions.list_versions(draft) == []
    with pytest.raises(VersionError) as raised:
        _versions.resolve(draft, None)
    assert "mark-revision" in str(raised.value)
    assert "--against <file>" in str(raised.value)


def test_unfinished_and_foreign_directories_are_not_versions(isolated_config):
    draft = _draft()
    _versions.take(draft, trigger="mark-revision")
    (_versions_dir(draft) / ".tmp-002").mkdir()
    (_versions_dir(draft) / "notes").mkdir()

    assert [s.ref for s in _versions.list_versions(draft)] == ["001"]


def test_tex_fragment_snapshot_copies_its_figures(isolated_config):
    text = "\\section{Intro}\n\n\\input{figures/x.tex}\n%figure: figures/x\n"
    draft = _draft("chapter.tex", text)
    _figure(draft, "figures/x")

    snap = _versions.take(draft, trigger="mark-revision")

    assert snap.source == snap.path / "chapter.tex"
    assert (snap.path / "figures" / "x.tex").is_file()
    assert (snap.path / "figures" / "x.txt").is_file()


def test_figure_names_dedupes_in_order():
    md = "<!-- figure: figures/b -->\n<!-- figure: figures/a -->\n<!-- figure: figures/b -->\n"
    tex = "\\input{figures/c.tex}\n%figure: figures/c\n% figure: figures/d\n"

    assert _versions.figure_names(md, ".md") == ["figures/b", "figures/a"]
    assert _versions.figure_names(tex, ".tex") == ["figures/c", "figures/d"]


def test_mark_revision_takes_no_label(isolated_config):
    with pytest.raises(VersionError, match="revision_label"):
        _versions.take(_draft(), trigger="mark-revision", label="pass 1")


def test_a_corrupt_manifest_is_reported_not_skipped(isolated_config):
    draft = _draft()
    snap = _versions.take(draft, trigger="mark-revision")
    (snap.path / _versions.SNAPSHOT_JSON).write_text("{not json", encoding="utf-8")

    with pytest.raises(VersionError, match="not a snapshot manifest"):
        _versions.list_versions(draft)


def test_a_failed_write_leaves_no_version_behind(isolated_config, monkeypatch):
    draft = _draft()

    def fail(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(_versions, "_write", fail)
    with pytest.raises(OSError, match="disk full"):
        _versions.take(draft, trigger="mark-revision")
    assert list(_versions_dir(draft).iterdir()) == []


def test_mark_revision_takes_a_snapshot_with_its_label(isolated_config):
    draft = _draft()

    path = _retrieval.mark_revision(draft, "shorten §4")

    snap = _versions.latest(draft)
    assert snap.trigger == "mark-revision"
    assert snap.revision_label == "shorten §4" and snap.label == ""
    assert "| shorten §4 |" in path.read_text(encoding="utf-8")


def test_mark_revision_unchanged_draft_writes_row_but_no_snapshot(isolated_config):
    draft = _draft()
    _retrieval.mark_revision(draft, "pass 1")

    path = _retrieval.mark_revision(draft, "pass 2")

    assert [snap.ref for snap in _versions.list_versions(draft)] == ["001"]
    assert "| pass 2 |" in path.read_text(encoding="utf-8")


def test_mark_revision_on_a_missing_draft_writes_row_but_no_snapshot(isolated_config):
    draft = config.DRAFTS_DIR / "dt" / "nowhere.md"

    path = _retrieval.mark_revision(draft, "pass 1")

    assert "| pass 1 |" in path.read_text(encoding="utf-8")
    assert _versions.list_versions(draft) == []


def test_a_corrupt_snapshot_warns_but_still_marks_the_revision(isolated_config, capsys):
    """A broken manifest must not stop a revision pass: the boundary row
    is what retrieval cost accounting reads, and it does not need the
    snapshot to be right."""
    draft = _draft()
    snap = _versions.take(draft, trigger="mark-revision")
    (snap.path / _versions.SNAPSHOT_JSON).write_text("{not json", encoding="utf-8")

    path = _retrieval.mark_revision(draft, "pass 2")

    assert "| pass 2 |" in path.read_text(encoding="utf-8")
    err = capsys.readouterr().err
    assert err.startswith("[warning] ")
    assert "not a snapshot manifest" in err and err.rstrip().endswith("; no snapshot taken")


def test_snapshot_command_prints_ref_and_exits_0(isolated_config, capsys):
    draft = _draft()
    _versions.take(draft, trigger="mark-revision")

    assert dossier.main(["snapshot", str(draft), "--label", "sent to supervisor"]) == 0

    out = capsys.readouterr().out
    assert out.startswith("Snapshot 002-sent-to-supervisor of ")
    assert "survey.md" in out
    assert _versions.latest(draft).trigger == "manual"


@pytest.mark.parametrize("bad", ["2024", "!!!"])
def test_snapshot_command_bad_label_exits_1(isolated_config, capsys, bad):
    draft = _draft()

    assert dossier.main(["snapshot", str(draft), "--label", bad]) == 1

    assert capsys.readouterr().err.startswith("[error] ")
    assert _versions.list_versions(draft) == []


def test_snapshot_command_on_a_missing_draft_exits_1(isolated_config, capsys):
    missing = config.DRAFTS_DIR / "nowhere.md"

    assert dossier.main(["snapshot", str(missing), "--label", "x"]) == 1

    assert "No such draft" in capsys.readouterr().err


def test_versions_command_lists_and_json(isolated_config, capsys):
    draft = _draft()
    _retrieval.mark_revision(draft, "shorten §4")
    _versions.take(draft, trigger="manual", label="sent to supervisor")
    capsys.readouterr()

    assert dossier.main(["versions", str(draft)]) == 0
    lines = capsys.readouterr().out.splitlines()
    today = _versions.latest(draft).taken_at[:10]
    assert lines[0].split() == ["001", today, "mark-revision", '"shorten', '§4"']
    assert lines[1].split() == ["002", today, "manual", "sent", "to", "supervisor"]

    assert dossier.main(["versions", str(draft), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [entry["number"] for entry in listed] == [1, 2]
    assert listed[1]["label"] == "sent to supervisor"
    assert listed[1]["path"] == "dossiers/dt/survey/versions/002-sent-to-supervisor"
    assert set(listed[0]) == {
        "number",
        "label",
        "taken_at",
        "trigger",
        "revision_label",
        "fingerprint",
        "draft_name",
        "path",
    }


def test_versions_command_with_none_says_so(isolated_config, capsys):
    draft = _draft()

    assert dossier.main(["versions", str(draft)]) == 0
    assert "no snapshots yet" in capsys.readouterr().out
    assert dossier.main(["versions", str(draft), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_versions_command_on_a_corrupt_manifest_exits_1(isolated_config, capsys):
    draft = _draft()
    snap = _versions.take(draft, trigger="mark-revision")
    (snap.path / _versions.SNAPSHOT_JSON).write_text("{not json", encoding="utf-8")

    assert dossier.main(["versions", str(draft)]) == 1
    assert capsys.readouterr().err.startswith("[error] ")


def test_status_reports_versions_line(isolated_config, capsys):
    draft = _draft()
    dossier.init(draft, "survey")
    assert dossier.main(["status", str(draft)]) == 0
    assert "Versions: none yet" in capsys.readouterr().out

    _versions.take(draft, trigger="mark-revision")
    newest = _versions.take(draft, trigger="manual", label="milestone")
    assert dossier.main(["status", str(draft)]) == 0
    assert f"Versions: 2, latest 002 ({newest.taken_at[:10]})" in capsys.readouterr().out


def test_status_reports_an_unreadable_snapshot_without_failing(isolated_config, capsys):
    draft = _draft()
    dossier.init(draft, "survey")
    snap = _versions.take(draft, trigger="mark-revision")
    (snap.path / _versions.SNAPSHOT_JSON).write_text("{not json", encoding="utf-8")

    assert dossier.main(["status", str(draft)]) == 0
    assert "Versions: unreadable" in capsys.readouterr().out


def test_export_restore_round_trip_keeps_versions(isolated_config, tmp_path):
    draft = _draft()
    _figure(draft, "figures/estimator-loop")
    dossier.init(draft, "survey")
    first = _versions.take(draft, trigger="mark-revision", revision_label="pass 1")
    draft.write_text(_MD_DRAFT + "\nmore\n", encoding="utf-8")
    _versions.take(draft, trigger="manual", label="sent to supervisor")
    held = sorted(
        path.relative_to(_versions_dir(draft)).as_posix()
        for path in _versions_dir(draft).rglob("*")
    )
    archive, _ = dossier.export([], tmp_path / "bundle.tar.gz")
    shutil.rmtree(dossier_dir(draft))

    dossier.restore(archive, force=True)

    restored = sorted(
        path.relative_to(_versions_dir(draft)).as_posix()
        for path in _versions_dir(draft).rglob("*")
    )
    assert restored == held
    assert [snap.ref for snap in _versions.list_versions(draft)] == ["001", "002"]
    assert _versions.resolve(draft, "1").source.read_bytes() == first.source.read_bytes()
    assert _versions.resolve(draft, "sent to supervisor").label == "sent to supervisor"
