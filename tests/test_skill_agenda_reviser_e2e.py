import contextlib
import io
import json

import pytest

from chitragupta import citation_gate, config, dossier
from chitragupta.review import agenda
from tests.conftest import content_draft
from tests.test_feature_workflows import _add_paper, _drop_paper

STEM = "agenda-reviser-e2e"

ORIGINAL = (
    "# Deployment\n\n"
    "A system tracks the physical asset across its life [@twin_ref_2024].\n\n"
    "<!-- figure: figures/deployment-diagram -->\n\n"
    "## Monitoring\n\nSensors report drift on a fixed schedule.\n"
)

REPAIRED_FIGURE = (
    "# Deployment\n\n"
    "As <!-- figureref: deployment-diagram --> shows, a system tracks the "
    "physical asset across its life [@twin_ref_2024].\n\n"
    "<!-- figure: figures/deployment-diagram -->\n"
    "The deployment topology.\n\n"
    "## Monitoring\n\nSensors report drift on a fixed schedule.\n"
)


def _run_agenda(draft, *extra):
    argv = [str(draft), "--json", *extra]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = agenda.main(argv)
    assert exit_code == 0, buf.getvalue()
    return json.loads(buf.getvalue())


def _new_figure(marker_id):
    return f"\n\n<!-- figure: figures/{marker_id} -->\n"


@pytest.fixture
def draft(isolated_config):
    _add_paper(
        "twin_ref_2024",
        "Digital twin tracking",
        "Digital twin tracking body text for engineering asset monitoring over time.",
    )
    _add_paper(
        "twin_candidate_2025",
        "Digital twin candidate paper",
        "Digital twin candidate paper body text about engineering asset monitoring over time.",
    )

    draft = content_draft(isolated_config, f"drafts/{STEM}.md")
    draft.write_text(ORIGINAL, encoding="utf-8")

    dossier.init(draft, "survey")
    target = dossier.dossier_dir(draft)
    (target / "evidence.md").write_text(
        "# Kept evidence\n\n## `twin_ref_2024`\n\nHow the system tracks the asset.\n\n"
        "## `twin_candidate_2025`\n\nKept, but never worked into the draft.\n"
    )
    (target / "sections.md").write_text(
        "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
        "| Deployment | `twin_ref_2024` |\n"
    )
    dossier.log_retrieval(draft, "search", "digital twin tracking", 15, 15, 2400)
    assert citation_gate.run([str(draft)]) == 0, "the draft starts sound"

    _drop_paper("twin_ref_2024")
    return draft


def _baseline(draft):
    payload = _run_agenda(draft)
    path = config.REVIEW_DIR / f"{STEM}.agenda.json"
    assert path.is_file()
    return path, payload


def _decite(draft):
    draft.write_text(
        draft.read_text(encoding="utf-8").replace(" [@twin_ref_2024]", ""),
        encoding="utf-8",
    )
    target = dossier.dossier_dir(draft)
    (target / "evidence.md").write_text(
        "# Kept evidence\n\n## `twin_candidate_2025`\n\nKept, but never worked into the draft.\n"
    )
    (target / "sections.md").write_text(
        "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
        "| Deployment | (none) |\n"
    )


def _retry_agenda(draft, path, marker_ids):
    deltas = []
    for marker_id in marker_ids:
        draft.write_text(ORIGINAL + _new_figure(marker_id), encoding="utf-8")
        comparison = _run_agenda(draft, "--baseline", str(path))
        deltas.append(comparison["objective_delta"])
        if comparison["objective_delta"] <= 0:
            break
        draft.write_text(ORIGINAL, encoding="utf-8")
        _run_agenda(draft)
    return deltas


def test_repairing_one_unattended_item_falls_the_objective_count(draft):
    path, before = _baseline(draft)
    prose_item = next(i for i in before["items"] if i["class"] == "prose")

    draft.write_text(REPAIRED_FIGURE, encoding="utf-8")
    comparison = _run_agenda(draft, "--baseline", str(path))

    assert prose_item["id"] in [i["id"] for i in comparison["resolved"]]
    assert comparison["objective_delta"] < 0


def test_a_repair_that_raises_the_count_is_not_accepted(draft):
    path, before = _baseline(draft)

    draft.write_text(ORIGINAL + _new_figure("monitoring-diagram"), encoding="utf-8")
    comparison = _run_agenda(draft, "--baseline", str(path))

    assert comparison["objective_delta"] > 0

    draft.write_text(ORIGINAL, encoding="utf-8")
    reverted = _run_agenda(draft, "--baseline", str(path))
    assert reverted["objective_delta"] < 0, (
        "the canonical baseline path was overwritten by the failed attempt above; "
        "comparing the true reverted draft against that inflated snapshot reports "
        "the revert itself as a fall -- false progress -- rather than the neutral "
        "no-op it actually is. Exactly the trap the module docstring names: a "
        "second attempt must re-file with a bare `agenda` call first, which is "
        "what `_retry_agenda` does and this direct call deliberately skips, to "
        "pin the trap rather than assume it"
    )


def test_two_failed_attempts_then_the_item_is_escalated(draft):
    path, before = _baseline(draft)

    deltas = _retry_agenda(draft, path, ["imu-diagram", "gps-diagram"])

    assert len(deltas) == 2
    assert all(delta > 0 for delta in deltas)


def test_surfaced_items_are_never_among_the_unattended_worklist(draft):
    _, payload = _baseline(draft)
    surfaced = [i for i in payload["items"] if not i["unattended"]]
    assert any(i["class"] == "recorded-but-uncited" for i in surfaced)

    unattended = [i for i in payload["items"] if i["unattended"]]
    assert "recorded-but-uncited" not in {i["class"] for i in unattended}


def test_a_pass_that_keeps_falling_terminates_before_the_bound(draft):
    path, before = _baseline(draft)
    assert before["pass_bound"] == 3  # PASS_BOUND, read from the payload

    draft.write_text(REPAIRED_FIGURE, encoding="utf-8")
    comparison = _run_agenda(draft, "--baseline", str(path))

    assert comparison["objective_after"] < before["pass_bound"]
    assert comparison["objective_delta"] < 0


def test_a_pass_that_never_falls_stops_at_the_bound(draft):
    path, before = _baseline(draft)

    deltas = []
    for _ in range(before["pass_bound"]):
        draft.write_text(ORIGINAL + _new_figure("imu-diagram"), encoding="utf-8")
        comparison = _run_agenda(draft, "--baseline", str(path))
        deltas.append(comparison["objective_delta"])
        draft.write_text(ORIGINAL, encoding="utf-8")
        _run_agenda(draft)

    assert all(delta > 0 for delta in deltas)
    assert len(deltas) == before["pass_bound"]


def test_a_repair_in_one_class_that_raises_another_classs_count_reverts(draft):
    path, before = _baseline(draft)
    missing_item = next(i for i in before["items"] if i["class"] == "missing-citekey")

    _decite(draft)
    draft.write_text(
        draft.read_text(encoding="utf-8") + _new_figure("imu-diagram") + _new_figure("gps-diagram"),
        encoding="utf-8",
    )
    comparison = _run_agenda(draft, "--baseline", str(path))

    assert missing_item["id"] in [i["id"] for i in comparison["resolved"]]
    assert comparison["objective_delta"] > 0


def test_missing_citekey_repair_removes_only_the_marker(draft):
    path, before = _baseline(draft)
    item = next(i for i in before["items"] if i["class"] == "missing-citekey")
    assert item["citekey"] == "twin_ref_2024"

    _decite(draft)
    comparison = _run_agenda(draft, "--baseline", str(path))

    assert item["id"] in [i["id"] for i in comparison["resolved"]]
    sentence = "A system tracks the physical asset across its life."
    assert sentence in draft.read_text(encoding="utf-8")
    new_uncited_summaries = {
        i["summary"] for i in comparison["new"] if i["class"] == "uncited-claim"
    }
    assert sentence in new_uncited_summaries


def test_pass_bound_is_read_from_the_payload_not_hardcoded(draft):
    _, payload = _baseline(draft)
    assert payload["pass_bound"] == agenda.PASS_BOUND
    assert isinstance(payload["objective_class_count"], int)
