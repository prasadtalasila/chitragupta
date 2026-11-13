"""Tests for chitragupta/dossier/_versions.py, the snapshot store.

A snapshot is what a later `draft diff` compares against, and nothing
else keeps the earlier text: `content/` is outside git on purpose. So
the weight here is on the two ways a snapshot can be wrong without
anyone noticing -- missing a figure the draft names, or being taken
under a number or label that `--against` would resolve to the wrong
one.
"""

import json

import pytest

from chitragupta import config
from chitragupta.dossier import dossier_dir
from chitragupta.dossier import _versions
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
