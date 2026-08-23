"""`codecov.yml`'s `after_n_builds` must equal the number of uploads a run makes.

Codecov computes a commit's `project` status from whatever sessions it has
processed *at that moment*. A matrix that uploads two partial reports --
which this one does, deliberately, because the Windows leg installs no
`os-deps` and so self-skips the render and pdf tests -- is only correct once
both have landed. Score it after one and the answer is the Windows leg
alone: ~99%, read as a regression on a branch that did not cause one.

That is not hypothetical. It happened on #199 and #204, and #199 is the
clean case: one attempt, no re-run, both legs logging `Upload queued for
processing complete`, and Codecov's own commit API reporting `sessions: 2`
and `coverage: 100.0` for that head SHA today. Nothing was lost. The status
was simply computed before the second session finished processing.

`codecov.notify.after_n_builds` is the gate for exactly that: hold the
notification until N uploads are in. Which makes N a number that has to
track the workflow, and a number nobody will remember to move -- add a
third matrix leg and the gate silently reverts to scoring two reports out
of three. So it is pinned here rather than asserted in a comment, the same
way tests/test_style_assets_match_the_standard.py pins two copies of one
list.

A text scan, and no YAML dependency: the Windows leg installs `python-deps`
only (bibtexparser), so PyYAML is not importable there, and these two files
are ours with a shape fixed by the tests below.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
CODECOV = REPO_ROOT / "codecov.yml"


def matrix_legs() -> list[str]:
    """The `test` job's operating systems, read out of ci.yml's own matrix."""
    listed = re.search(r"^\s*os:\s*\[([^\]]+)\]", CI.read_text(encoding="utf-8"), re.M)
    assert listed, "ci.yml no longer declares its matrix as `os: [...]` on one line"
    return [leg.strip() for leg in listed.group(1).split(",") if leg.strip()]


def after_n_builds() -> int:
    """The upload count `codecov.yml` holds the notification for."""
    assert CODECOV.exists(), (
        "codecov.yml is missing: without it Codecov scores a commit on whichever "
        "of the matrix legs' uploads it has processed first"
    )
    gate = re.search(r"^\s*after_n_builds:\s*(\d+)\s*$", CODECOV.read_text(encoding="utf-8"), re.M)
    assert gate, "codecov.yml no longer sets after_n_builds"
    return int(gate.group(1))


def upload_steps() -> list[Path]:
    """Every workflow file that uploads to Codecov, one entry per `uses:`.

    The gate counts *uploads*, not matrix legs; they coincide only while
    the single upload step lives in the single matrix job. This is what
    notices when that stops being true.
    """
    workflows = sorted(WORKFLOWS.glob("*.yml"))
    # A glob that matches nothing would make the assertion below pass for
    # the wrong reason forever -- the vacuous-scan trap the repo-walking
    # tests in test_code_standards_scan.py guard against the same way.
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
    """So that `after_n_builds == len(matrix_legs())` stays a sound derivation.

    A second upload anywhere -- another job in ci.yml, or docs.yml/release.yml
    growing one -- makes the matrix size the wrong number, and the symptom
    would be the silent one this whole file exists to stop.
    """
    assert upload_steps() == [CI]


def test_both_legs_upload_rather_than_one_being_skipped():
    """The upload step is guarded on `!cancelled()` and nothing else.

    Narrow it to one OS -- as the `Upload coverage.xml for the SonarQube
    job` step above it legitimately is -- and a run makes one upload while
    the gate still waits for two, which turns a wrong number into a status
    that never posts at all.
    """
    step = re.search(
        # `|\Z` so that making this the job's last step reports the guard it
        # actually broke, rather than "there is no such step" about a step
        # that is plainly still there.
        r"^      - name: Upload coverage to Codecov\n(.*?)(?=^      - name: |\Z)",
        CI.read_text(encoding="utf-8"),
        re.M | re.S,
    )
    assert step, "ci.yml no longer has a step named `Upload coverage to Codecov`"
    guard = re.search(r"^\s*if:\s*(.+)$", step.group(1), re.M)
    assert guard, "the Codecov upload step no longer carries an `if:` guard"
    assert "runner.os" not in guard.group(1) and "matrix.os" not in guard.group(1)
