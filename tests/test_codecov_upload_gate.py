import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
CODECOV = REPO_ROOT / "codecov.yml"


def matrix_legs() -> list[str]:
    listed = re.search(r"^\s*os:\s*\[([^\]]+)\]", CI.read_text(encoding="utf-8"), re.M)
    assert listed, "ci.yml no longer declares its matrix as `os: [...]` on one line"
    return [leg.strip() for leg in listed.group(1).split(",") if leg.strip()]


def after_n_builds() -> int:
    assert CODECOV.exists(), (
        "codecov.yml is missing: without it Codecov scores a commit on whichever "
        "of the matrix legs' uploads it has processed first"
    )
    gate = re.search(r"^\s*after_n_builds:\s*(\d+)\s*$", CODECOV.read_text(encoding="utf-8"), re.M)
    assert gate, "codecov.yml no longer sets after_n_builds"
    return int(gate.group(1))


def upload_steps() -> list[Path]:
    workflows = sorted(WORKFLOWS.glob("*.yml"))
    assert workflows, f"no workflow files under {WORKFLOWS}"
    found = []
    for path in workflows:
        uses = re.findall(
            r"^\s*uses:\s*codecov/codecov-action@", path.read_text(encoding="utf-8"), re.M
        )
        found.extend([path] * len(uses))
    return found


def test_the_gate_matches_the_number_of_uploads_a_run_makes():
    assert after_n_builds() == len(matrix_legs())


def test_ci_yml_holds_the_only_codecov_upload_in_the_repository():
    assert upload_steps() == [CI]


def test_both_legs_upload_rather_than_one_being_skipped():
    step = re.search(
        r"^      - name: Upload coverage to Codecov\n(.*?)(?=^      - name: |\Z)",
        CI.read_text(encoding="utf-8"),
        re.M | re.S,
    )
    assert step, "ci.yml no longer has a step named `Upload coverage to Codecov`"
    guard = re.search(r"^\s*if:\s*(.+)$", step.group(1), re.M)
    assert guard, "the Codecov upload step no longer carries an `if:` guard"
    assert "runner.os" not in guard.group(1) and "matrix.os" not in guard.group(1)
