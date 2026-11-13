"""Tests for `python -m chitragupta.draft diff`: the change report and the
redline, tied together.

Run through `draft.main`, the route a person and a reviser both take, so
the dispatch and the `[error]` lines are what is tested. The PDF path is
tested with `render` and `redline` faked -- no pandoc, TeX or latexdiff
runs here; the real end to end is a slow test of its own.
"""

import json
from pathlib import Path

import pytest

from chitragupta import config, dossier, draft, programs, render_output
from chitragupta.dossier import _draft_fingerprint, _versions
from chitragupta.draft_diff import _cli, _redline
from tests.conftest import add_citable, content_draft

_OLD = (
    "# Twins\n\n"
    "## Background\n\nDigital twins mirror physical assets [@sample_dt_overview_2024].\n\n"
    "## Synchronisation\n\nClocks drift between the twin and the asset.\n"
)
_NEW = _OLD.replace(
    "Clocks drift between the twin and the asset.",
    "Clocks drift between the twin and its asset, and must be resynchronised "
    "[@sample_dt_sync_2023].",
)


def _draft(text=_OLD, name="survey.md"):
    path = content_draft(config, f"drafts/dt/{name}")
    path.write_text(text, encoding="utf-8")
    return path


def _review_dir():
    return config.REVIEW_DIR / "dt"


def _seed(con):
    for key in ("sample_dt_overview_2024", "sample_dt_sync_2023"):
        add_citable(con, key)
    con.commit()


def _snapshotted(con, *, label=""):
    """A draft with one snapshot of `_OLD`, then edited to `_NEW`."""
    _seed(con)
    path = _draft()
    if label:
        _versions.take(path, trigger="manual", label=label)
    else:
        _versions.take(path, trigger="mark-revision", revision_label="tighten sync")
    path.write_text(_NEW, encoding="utf-8")
    return path


def _diff(*argv):
    return draft.main(["diff", *map(str, argv)])


def test_diff_is_a_draft_verb():
    assert "diff" in draft.VERBS
    assert draft.VERBS["diff"][0].main is _cli.main


def test_diff_against_latest_writes_report(isolated_config, ledger_con, capsys):
    path = _snapshotted(ledger_con)

    assert _diff(path) == 0

    out = capsys.readouterr().out
    assert out.startswith("# Changes since 001 · tighten sync · ")
    assert "sample_dt_sync_2023" in out
    report = (_review_dir() / "survey.diff.md").read_text(encoding="utf-8")
    assert out.startswith(report)
    data = json.loads((_review_dir() / "survey.diff.json").read_text(encoding="utf-8"))
    assert data["has_changes"] is True
    assert data["citekeys_added"] == [{"key": "sample_dt_sync_2023", "section": "Synchronisation"}]
    assert not (_review_dir() / "survey.diff.pdf").exists()


def test_diff_attaches_the_revision_log_since_the_baseline(isolated_config, ledger_con, capsys):
    path = _snapshotted(ledger_con)
    revisions = dossier.dossier_dir(path) / dossier.REVISIONS_MD
    snap_date = _versions.latest(path).taken_at[:10]
    revisions.write_text(
        f"# Revisions\n\n## {snap_date} -- tighten sync\n\nSections: Synchronisation\n",
        encoding="utf-8",
    )

    assert _diff(path, "--json") == 0

    data = json.loads(capsys.readouterr().out)
    changed = [s for s in data["sections"] if s["title"] == "Synchronisation"]
    assert changed[0]["log"] == [f"{snap_date} tighten sync"]
    assert data["unlogged"] == []


def test_diff_flags_hand_edits(isolated_config, ledger_con, capsys):
    _seed(ledger_con)
    path = _draft()
    dossier.init(path, "survey")
    _draft_fingerprint.stamp(path)
    _versions.take(path, trigger="mark-revision")
    path.write_text(_NEW, encoding="utf-8")

    assert _diff(path, "--json") == 0

    assert json.loads(capsys.readouterr().out)["hand_edits"] is True


def test_diff_against_label_number_and_path(isolated_config, ledger_con, capsys):
    path = _snapshotted(ledger_con, label="sent to supervisor")

    assert _diff(path, "--against", "sent to supervisor") == 0
    assert "Changes since 001 · sent to supervisor" in capsys.readouterr().out

    assert _diff(path, "--against", "1") == 0
    assert "Changes since 001 · sent to supervisor" in capsys.readouterr().out

    other = config.CONTENT_DIR / "elsewhere" / "old.md"
    other.parent.mkdir(parents=True)
    other.write_text(_OLD, encoding="utf-8")

    assert _diff(path, "--against", other) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Changes since old.md — review copy")
    assert "Baseline figures unknown." in out


def test_diff_no_versions_exits_1_with_hint(isolated_config, capsys):
    path = _draft()

    assert _diff(path) == 1

    err = capsys.readouterr().err
    assert err.startswith("[error] ")
    assert "mark-revision" in err
    assert "--against <file>" in err
    assert len(err.strip().splitlines()) == 1


def test_diff_unknown_ref_lists_versions(isolated_config, capsys):
    path = _draft()
    _versions.take(path, trigger="manual", label="sent to supervisor")

    assert _diff(path, "--against", "camera ready") == 1

    err = capsys.readouterr().err
    assert err.startswith("[error] ")
    assert "001-sent-to-supervisor" in err


def test_diff_format_mismatch_refused(isolated_config, capsys):
    path = _draft()
    baseline = _draft("\\section{Twins}\n\nText.\n", name="survey.tex")

    assert _diff(path, "--against", baseline) == 1

    err = capsys.readouterr().err
    assert err == "[error] the baseline is .tex, the draft is .md; they cannot be compared\n"


@pytest.mark.parametrize("where", ["missing", "outside"])
def test_diff_refuses_a_draft_not_under_drafts(isolated_config, capsys, where):
    if where == "missing":
        path = config.DRAFTS_DIR / "dt" / "nope.md"
    else:
        path = config.CONTENT_DIR / "notes" / "survey.md"
        path.parent.mkdir(parents=True)
        path.write_text(_OLD, encoding="utf-8")

    assert _diff(path) == 1

    err = capsys.readouterr().err
    assert err.startswith("[error] ")
    assert str(path) in err


def test_diff_refuses_a_review_dir_outside_content(isolated_config, tmp_path, capsys):
    path = _draft()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    config.REVIEW_DIR.mkdir(parents=True)
    (config.REVIEW_DIR / "dt").symlink_to(outside, target_is_directory=True)
    _versions.take(path, trigger="manual", label="first")

    assert _diff(path) == 1

    assert capsys.readouterr().err.startswith("[error] ")
    assert not list(outside.iterdir())


def test_diff_json_flag_prints_json(isolated_config, ledger_con, capsys):
    path = _snapshotted(ledger_con)

    assert _diff(path, "--json") == 0

    data = json.loads(capsys.readouterr().out)
    assert data["header"].startswith("Changes since 001")
    assert data == json.loads((_review_dir() / "survey.diff.json").read_text(encoding="utf-8"))


def _fake_render(calls):
    def render(input_path, output_format, output_dir, defer_citations):
        calls.append((input_path, output_format, output_dir, defer_citations))
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        tex = out / "survey.tex"
        tex.write_text("\\documentclass{article}\n", encoding="utf-8")
        return tex

    return render


def test_diff_no_changes_exits_0_writes_no_pdf(isolated_config, ledger_con, monkeypatch, capsys):
    _seed(ledger_con)
    path = _draft()
    _versions.take(path, trigger="mark-revision")
    # A redline from an earlier run, of a state the draft no longer has.
    _review_dir().mkdir(parents=True)
    for stale in ("survey.diff.pdf", "survey.diff.tex"):
        (_review_dir() / stale).write_text("old", encoding="utf-8")
    calls = []
    monkeypatch.setattr(render_output, "render", _fake_render(calls))

    assert _diff(path, "--format", "pdf") == 0

    assert "No changes." in capsys.readouterr().out
    assert calls == []
    assert not (_review_dir() / "survey.diff.pdf").exists()
    assert not (_review_dir() / "survey.diff.tex").exists()
    assert (_review_dir() / "survey.diff.md").is_file()


def test_diff_pdf_renders_both_sides_and_redlines(isolated_config, ledger_con, monkeypatch, capsys):
    path = _snapshotted(ledger_con)
    calls, redlined = [], []
    monkeypatch.setattr(render_output, "render", _fake_render(calls))

    def fake_redline(old_tex, new_tex, report, out_dir, stem):
        redlined.append((old_tex, new_tex, out_dir, stem))
        pdf = out_dir / f"{stem}.diff.pdf"
        pdf.write_bytes(b"%PDF")
        return pdf

    monkeypatch.setattr(_redline, "redline", fake_redline)

    assert _diff(path, "--format", "pdf") == 0

    work = _review_dir() / "survey.diff"
    assert [(c[2], c[1], c[3]) for c in calls] == [
        (work / "old-tex", "tex", True),
        (work / "new-tex", "tex", True),
    ]
    assert calls[0][0] == str(work / "old" / "survey.md")
    assert calls[1][0] == str(work / "new" / "survey.md")
    assert redlined == [
        (work / "old-tex" / "survey.tex", work / "new-tex" / "survey.tex", _review_dir(), "survey")
    ]
    out = capsys.readouterr().out
    assert out.rstrip().endswith(str(_review_dir() / "survey.diff.pdf"))


def test_diff_pdf_withdraws_a_key_no_longer_citable(
    isolated_config, ledger_con, monkeypatch, capsys
):
    _seed(ledger_con)
    path = _draft(_OLD.replace("asset.\n", "asset [@sample_std_interop_2021].\n"))
    _versions.take(path, trigger="mark-revision")
    path.write_text(_NEW, encoding="utf-8")
    monkeypatch.setattr(render_output, "render", _fake_render([]))
    monkeypatch.setattr(
        _redline, "redline", lambda old, new, report, out_dir, stem: out_dir / "x.pdf"
    )

    assert _diff(path, "--format", "pdf") == 0

    old_side = (_review_dir() / "survey.diff" / "old" / "survey.md").read_text(encoding="utf-8")
    assert "(citation withdrawn)" in old_side
    assert "sample_std_interop_2021" not in old_side
    assert "no longer in the corpus" in capsys.readouterr().out


def test_diff_pdf_without_latexdiff_keeps_report_and_exits_1(
    isolated_config, ledger_con, monkeypatch, capsys
):
    path = _snapshotted(ledger_con)
    monkeypatch.setattr(render_output, "render", _fake_render([]))
    monkeypatch.setattr(programs, "resolve_program", lambda name: None)

    assert _diff(path, "--format", "pdf") == 1

    err = capsys.readouterr().err
    assert err.startswith("[error] ")
    assert "latexdiff" in err
    assert (_review_dir() / "survey.diff.md").is_file()
    assert (_review_dir() / "survey.diff.json").is_file()


def test_diff_pdf_reports_a_failed_redline(isolated_config, ledger_con, monkeypatch, capsys):
    path = _snapshotted(ledger_con)
    monkeypatch.setattr(render_output, "render", _fake_render([]))

    def fails(*args):
        raise _redline.RedlineFailed("The redline did not compile.")

    monkeypatch.setattr(_redline, "redline", fails)

    assert _diff(path, "--format", "pdf") == 1

    assert capsys.readouterr().err == "[error] The redline did not compile.\n"


def test_diff_pdf_refuses_a_draft_citing_an_uncitable_key(
    isolated_config, ledger_con, monkeypatch, capsys
):
    path = _snapshotted(ledger_con)
    path.write_text(_NEW + "\nSee [@sample_ml_anomaly_2023].\n", encoding="utf-8")
    # The real render, which gates each side before any pandoc runs.
    monkeypatch.setattr(_redline, "redline", lambda *args: pytest.fail("redline reached"))

    assert _diff(path, "--format", "pdf") == 1

    err = capsys.readouterr().err
    assert err.startswith("[error] ")
    assert "sample_ml_anomaly_2023" in err
    assert (_review_dir() / "survey.diff.md").is_file()


def test_diff_json_with_pdf_keeps_stdout_parseable(
    isolated_config, ledger_con, monkeypatch, capsys
):
    path = _snapshotted(ledger_con)
    monkeypatch.setattr(render_output, "render", _fake_render([]))
    monkeypatch.setattr(
        _redline, "redline", lambda old, new, report, out_dir, stem: out_dir / "survey.diff.pdf"
    )

    assert _diff(path, "--format", "pdf", "--json") == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out)["has_changes"] is True
    assert captured.err.strip() == str(_review_dir() / "survey.diff.pdf")
