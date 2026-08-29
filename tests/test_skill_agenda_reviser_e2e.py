"""End-to-end proof of the `agenda-reviser` repair loop's machinery --
driven the way the skill drives it: `agenda --json` for a baseline (no
`--write` flag exists on this aid -- the report files unconditionally),
a scripted edit shaped like the skill's own `Edit` call, then `agenda
--baseline ... --json` to decide accept, revert or persist.

Nine tests, matching `plans/f3-agenda-reviser.md`'s "PR 2's tests, to the
100% bar" section: the issue's original five, plus three this plan adds
(cross-class coupling, the `missing-citekey` repair shape, and
`pass_bound` read from the payload rather than a literal).

Own module rather than a class in tests/test_feature_workflows.py (see
that file's TestOverlapRemediationEndToEnd for the narrower loop this
one supersedes): that file already covers a different loop end to end,
and one shared loop belongs in one file read on its own, the same
reasoning tests/test_skill_verbatim_scan_step.py and
tests/test_skill_pregate_feedback_step.py already follow.

**Two mechanics this suite exists to pin, discovered writing it rather
than assumed from the spec:**

`missing-citekey` is detected off the dossier's own record of what it
cites (`evidence.md`/`sections.md` via `dossier._citekeys.cited_citekeys`),
not off the draft's live `[@citekey]` markers -- so a repair that only
edits the draft text leaves the item unresolved on the next agenda. The
fixture's repair helper updates both.

`--baseline`'s target path is also what every `agenda` call refiles on
exit, a failed attempt included. A second attempt that reuses the same
path without an intervening bare (`agenda --json`, no `--baseline`)
refile after a revert compares against the first attempt's inflated
count rather than the pass's real starting point -- silently reporting a
retry as progress it never made. `_retry_agenda` below re-files before
every attempt after the first for exactly this reason.
"""

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
    "A DT tracks the physical asset across its life [@twin_ref_2024].\n\n"
    "## Monitoring\n\nSensors report drift on a fixed schedule.\n"
)


def _run_agenda(draft, *extra):
    """`review agenda <draft> --json`, plus whatever extra flags the
    caller passes, run in-process and parsed. Mirrors this repo's own
    `chitragupta/review/agenda/__init__.py::main` contract: exit 0
    always, JSON on stdout when `--json` is passed. No `--write` flag
    exists on this aid -- the `.md`/`.json` report files unconditionally
    on every run, unlike `verbatim scan`."""
    argv = [str(draft), "--json", *extra]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = agenda.main(argv)
    assert exit_code == 0, buf.getvalue()
    return json.loads(buf.getvalue())


@pytest.fixture
def draft(isolated_config):
    """`content/drafts/agenda-reviser-e2e.md`, carrying three findings in
    three different classes, all computed live so no other aid's `.json`
    has to be pre-seeded on disk:

    - `A DT tracks...` -- an unexpanded acronym, `prose`, unattended
      (`chitragupta.style_check` runs live on every agenda build).
    - `[@twin_ref_2024]` -- cited while the paper existed, then the
      paper is dropped from the corpus -- `missing-citekey`, unattended
      (`dossier.drift`, computed live from the dossier's own files).
    - `twin_candidate_2025` -- a second paper that matches the draft's
      recorded retrieval query but is never cited -- `candidate`,
      surfaced, also drift-based and live.
    """
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
        "# Kept evidence\n\n## `twin_ref_2024`\n\nHow a DT tracks the asset.\n"
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
    """The unattended `missing-citekey` repair: drop the marker from the
    draft *and* drop the citekey from the dossier's own record, since
    `missing-citekey` is detected off the latter, not the former."""
    draft.write_text(
        draft.read_text(encoding="utf-8").replace(" [@twin_ref_2024]", ""),
        encoding="utf-8",
    )
    target = dossier.dossier_dir(draft)
    (target / "evidence.md").write_text("# Kept evidence\n")
    (target / "sections.md").write_text(
        "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
        "| Deployment | (none) |\n"
    )


def _retry_agenda(draft, path, attempt_texts):
    """One item's R7 loop, up to `len(attempt_texts)` attempts: apply
    each candidate edit over the *original* draft, `--baseline` against
    `path`, and revert if `objective_delta` is positive. Between a
    revert and the next attempt, re-files `path` with a bare `agenda`
    call against the true reverted draft first -- see the module
    docstring for why that refile is load-bearing rather than
    defensive. Returns the list of deltas observed, one per attempt
    made (stops early on a non-positive delta, i.e. an accepted repair).
    """
    deltas = []
    for attempt_text in attempt_texts:
        draft.write_text(ORIGINAL.replace("Sensors report", attempt_text), encoding="utf-8")
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

    draft.write_text(
        ORIGINAL.replace("A DT tracks", "A Digital Twin (DT) tracks"),
        encoding="utf-8",
    )
    comparison = _run_agenda(draft, "--baseline", str(path))

    assert prose_item["id"] in [i["id"] for i in comparison["resolved"]]
    assert comparison["objective_delta"] < 0


def test_a_repair_that_raises_the_count_is_not_accepted(draft):
    """A "repair" that fixes nothing and introduces a fresh, unexpanded
    acronym raises the total -- the accept condition (`objective_delta`
    not positive) fails, so a caller following R4 must revert rather
    than keep it."""
    path, before = _baseline(draft)

    draft.write_text(ORIGINAL.replace("Sensors report", "An IMU reports"), encoding="utf-8")
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
    """Not a property of the CLI (it has no attempt counter -- that
    discipline is the skill's own R7 loop). This proves the signal the
    skill relies on to know an attempt failed: two consecutive
    `--baseline` cycles against the pass's true starting point, each
    with a non-improving edit, both report `objective_delta > 0` -- the
    caller's cue to stop trying this item and escalate rather than a
    third signal from the CLI itself."""
    path, before = _baseline(draft)

    deltas = _retry_agenda(draft, path, ["An IMU reports", "A GPS unit reports"])

    assert len(deltas) == 2
    assert all(delta > 0 for delta in deltas)


def test_surfaced_items_are_never_among_the_unattended_worklist(draft):
    _, payload = _baseline(draft)
    surfaced = [i for i in payload["items"] if not i["unattended"]]
    assert any(i["class"] == "candidate" for i in surfaced)

    unattended = [i for i in payload["items"] if i["unattended"]]
    assert "candidate" not in {i["class"] for i in unattended}


def test_a_pass_that_keeps_falling_terminates_before_the_bound(draft):
    path, before = _baseline(draft)
    assert before["pass_bound"] == 3  # PASS_BOUND, read from the payload

    draft.write_text(
        ORIGINAL.replace("A DT tracks", "A Digital Twin (DT) tracks"),
        encoding="utf-8",
    )
    comparison = _run_agenda(draft, "--baseline", str(path))

    # One pass resolved the only prose finding; the count fell to 1
    # (missing-citekey remains), below pass_bound's 3 -- the loop's own
    # terminator (strictly falls) would stop here, before ever reaching
    # the backstop.
    assert comparison["objective_after"] < before["pass_bound"]
    assert comparison["objective_delta"] < 0


def test_a_pass_that_never_falls_stops_at_the_bound(draft):
    path, before = _baseline(draft)

    deltas = []
    for _ in range(before["pass_bound"]):
        draft.write_text(ORIGINAL.replace("Sensors report", "An IMU reports"), encoding="utf-8")
        comparison = _run_agenda(draft, "--baseline", str(path))
        deltas.append(comparison["objective_delta"])
        draft.write_text(ORIGINAL, encoding="utf-8")
        _run_agenda(draft)

    # Every attempt was non-improving -- the loop's terminator (count
    # strictly falls) never fires, so a caller following the skill's own
    # rule stops only because it hit pass_bound attempts, not because
    # progress was made.
    assert all(delta > 0 for delta in deltas)
    assert len(deltas) == before["pass_bound"]


def test_a_repair_in_one_class_that_raises_another_classs_count_reverts(draft):
    """Decision 4's cross-class coupling: repairing missing-citekey
    (-1) while the same edit introduces two fresh unexpanded acronyms
    (+2) nets positive even though the targeted item resolved -- R4
    reads the total, not the targeted item's own delta."""
    path, before = _baseline(draft)
    missing_item = next(i for i in before["items"] if i["class"] == "missing-citekey")

    _decite(draft)
    draft.write_text(
        draft.read_text(encoding="utf-8").replace(
            "Sensors report drift on a fixed schedule.",
            "An IMU reports GPS drift on a fixed schedule.",
        ),
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
    # The sentence survives -- it becomes an uncited-claim, a surfaced
    # class, on the next agenda rather than vanishing.
    assert "A DT tracks the physical asset across its life." in draft.read_text(encoding="utf-8")
    new_uncited_summaries = {
        i["summary"] for i in comparison["new"] if i["class"] == "uncited-claim"
    }
    assert "A DT tracks the physical asset across its life." in new_uncited_summaries


def test_pass_bound_is_read_from_the_payload_not_hardcoded(draft):
    """Not a test of the skill's own prose (that is
    tests/test_skill_verbatim_scan_step.py's style of check, not this
    module's) -- a test that the field this requirement depends on
    actually exists on the payload and is the same value the
    `PASS_BOUND` module constant carries, so a skill reading it gets the
    real backstop rather than a stale copy."""
    _, payload = _baseline(draft)
    assert payload["pass_bound"] == agenda.PASS_BOUND
    assert isinstance(payload["objective_class_count"], int)
