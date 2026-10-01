"""`scripts/check_local.sh` must run what `ci.yml`'s `lint` job runs (#865).

The point of the script is that a green local run predicts a green CI
run, and that only holds while the two lists are the same list. Before
it, DEVELOPER-AGENTS.md's checklist named seven of the lint job's
commands and missed `check_version_bump.py`, `shellcheck`, `actionlint`,
the webapp and OpenCode node tests and the Vale exemptions check -- four
red CI runs in one session came from exactly that gap. A hand-kept list
drifts the same way the prose one did, so this file reads both sides
and compares them, step by step and in order.

The script states each step in one of three shapes, one per line and
starting at column 0, and
this test is what gives the shapes their meaning:

- `run "<step name>" <command>` -- CI's `run:` text, byte for byte
  after whitespace is collapsed. `off_main` in front of the command is
  the local spelling of CI's `if: github.event_name == 'pull_request'`.
- `need "<step name>" <tool>[==<pin>|@<pin>] ...` -- an install step.
  CI installs into a throwaway runner; locally that would write into the
  contributor's own environment, so the script checks the tool is on
  PATH instead (`py:<package>` is checked by import). Its pins and CI's
  must be the same set, so a bumped pin or a new package in `ci.yml`
  reddens here too.
- `instead "<step name>" <command>` -- a step whose CI form would do
  harm locally (overwrite a per-host `config.toml`, make a full clone
  shallow). Reserved for those two steps, each pinned at its CI command
  in `_INSTEAD_STEPS`; the script carries the reason.

Parsed with a real YAML loader, not by indentation: #866 is moving the
existing workflow pins the same way.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SCRIPT = REPO_ROOT / "scripts" / "check_local.sh"

_STEP_LINE_RE = re.compile(r'^(run|need|instead) "([^"]+)" (.+)$')
_PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)(?:==|@)(\S+)$")

# Actions that provision the runner the script is already standing in.
# Any other `uses:` step would be a check the script cannot run, so it
# fails here rather than being skipped as "not a run: step".
_PROVISIONING_ACTIONS = ("actions/checkout@", "actions/setup-python@", "actions/setup-node@")

# The only steps allowed the `instead` escape hatch, each with the CI
# command it stands in for -- so neither a script line marked `instead`
# to quiet a check, nor a change to what CI does in these two steps,
# passes unnoticed.
_INSTEAD_STEPS = {
    "Create config.toml from the tracked example": "cp config.toml.example config.toml",
    "Fetch main and tags for the version check": (
        'git fetch --quiet --depth=1 origin "+refs/heads/main:refs/remotes/origin/main" '
        '"+refs/tags/*:refs/tags/*"'
    ),
}

# What a `need` step's CI command must be: an install, never a check.
_INSTALL_PREFIXES = (
    "python -m pip install ",
    "npm install -g ",
    "bash scripts/install_full_pipeline.sh ",
)

_PULL_REQUEST_ONLY = "github.event_name == 'pull_request'"

# A key outside these changes what a step does (`env:`,
# `working-directory:`, `continue-on-error:`) in a way the script's line
# cannot show, so it has to be taught here before it can be pinned.
_STEP_KEYS = {"name", "run", "if", "shell"}


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _unpinnable_steps(steps: list[dict]) -> list[str]:
    """Lint-job steps whose behaviour the script's line cannot match."""
    problems = []
    for step in steps:
        label = step.get("name") or step.get("uses")
        if "uses" in step:
            if not step["uses"].startswith(_PROVISIONING_ACTIONS):
                problems.append(f"{label!r}: an action the script cannot run locally")
        elif set(step) - _STEP_KEYS or step.get("shell", "bash") != "bash":
            problems.append(f"{label!r}: keys this test does not pin: {sorted(step)}")
    return problems


def _script_steps(script_text: str) -> list[tuple[str, str, str]]:
    """(verb, step name, rest of line) for every step the script states.
    Unstripped on purpose: a step is a line at column 0, so the helper
    functions' own indented calls to `run` are not mistaken for steps."""
    found = []
    for line in script_text.splitlines():
        match = _STEP_LINE_RE.match(line)
        if match:
            found.append(match.groups())
    return found


def _divergences(workflow_text: str, script_text: str) -> list[str]:
    """Every way the script and CI's lint job disagree; empty when they
    are the same list."""
    steps = yaml.safe_load(workflow_text)["jobs"]["lint"]["steps"]
    problems = _unpinnable_steps(steps)
    ci_steps = [step for step in steps if "run" in step]
    local_steps = _script_steps(script_text)
    ci_names = [step["name"] for step in ci_steps]
    local_names = [name for _, name, _ in local_steps]
    if ci_names != local_names:
        return [*problems, f"step names differ:\n  ci.yml: {ci_names}\n  script: {local_names}"]
    for ci, (verb, name, rest) in zip(ci_steps, local_steps):
        problems.extend(_step_divergences(ci, verb, name, rest))
    return problems


def _need_divergences(name: str, ci_run: str, rest: str) -> list[str]:
    """A `need` stands in for an install, and checks exactly CI's pins --
    both directions, so a package CI adds reaches the script too. `py:`
    marks a Python package the script checks by import, not on PATH."""
    if not ci_run.startswith(_INSTALL_PREFIXES):
        return [f"{name!r}: `need` stands in for an install, but ci.yml runs `{ci_run}`"]
    script_pins = {spec.removeprefix("py:") for spec in rest.split() if "==" in spec or "@" in spec}
    ci_pins = {token for token in ci_run.split() if _PIN_RE.match(token)}
    if script_pins != ci_pins:
        return [f"{name!r}: script checks {sorted(script_pins)}, ci.yml installs {sorted(ci_pins)}"]
    return []


def _step_divergences(ci: dict, verb: str, name: str, rest: str) -> list[str]:
    ci_run = _collapse(ci["run"])
    if verb == "need":
        return _need_divergences(name, ci_run, rest)
    if verb == "instead":
        if _INSTEAD_STEPS.get(name) != ci_run:
            return [
                f"{name!r}: `instead` is reserved for {sorted(_INSTEAD_STEPS)} at their CI form"
            ]
        return []
    guarded = rest.startswith("off_main ")
    command = rest.removeprefix("off_main ") if guarded else rest
    problems = []
    if _collapse(command) != ci_run:
        problems.append(f"{name!r}: script runs `{command}`, ci.yml runs `{ci_run}`")
    if ci.get("if", _PULL_REQUEST_ONLY) != _PULL_REQUEST_ONLY:
        problems.append(f"{name!r}: no local form for ci.yml's `if: {ci['if']}`")
    elif guarded != ("if" in ci):
        problems.append(f"{name!r}: `off_main` must match ci.yml's `if:` ({ci.get('if')!r})")
    return problems


class TestTheScriptMatchesTheLintJob:
    def test_ci_lint_set_matches_local_script(self):
        problems = _divergences(
            CI_WORKFLOW.read_text(encoding="utf-8"), SCRIPT.read_text(encoding="utf-8")
        )
        assert not problems, (
            "scripts/check_local.sh no longer runs what ci.yml's lint job runs. "
            "Change both in the same commit:\n" + "\n".join(problems)
        )

    def test_the_script_states_at_least_one_step_of_each_shape(self):
        """A reworded step line would drop out of `_script_steps` silently
        and take its pin with it; the name comparison above would catch
        that, but only by accident of the lists being non-empty."""
        verbs = {verb for verb, _, _ in _script_steps(SCRIPT.read_text(encoding="utf-8"))}
        assert verbs == {"run", "need", "instead"}

    def test_the_script_is_under_shellchecks_glob(self):
        """`scripts/*.sh` is what the lint job's own shellcheck step reaches."""
        assert SCRIPT.parent.name == "scripts" and SCRIPT.suffix == ".sh"


_WORKFLOW = """
jobs:
  lint:
    steps:
      - uses: actions/checkout@v4
      - name: Install ruff
        run: python -m pip install ruff==0.16.4
      - name: Version check
        if: github.event_name == 'pull_request'
        run: python3 scripts/check_version_bump.py
      - name: ruff
        run: ruff check chitragupta scripts
      - name: Create config.toml from the tracked example
        run: cp config.toml.example config.toml
"""

_MATCHING_SCRIPT = """
need "Install ruff" ruff==0.16.4
run "Version check" off_main python3 scripts/check_version_bump.py
run "ruff" ruff check   chitragupta scripts
instead "Create config.toml from the tracked example" copy_config_if_absent
"""


class TestEachDriftShapeReddens:
    """A guard that reports "clean" fails silently, so each of the ways
    the two lists can part is fed in and must be reported."""

    def test_matching_lists_report_nothing(self):
        assert _divergences(_WORKFLOW, _MATCHING_SCRIPT) == []

    @pytest.mark.parametrize(
        ("old", "new", "expect"),
        [
            ("ruff check   chitragupta scripts", "ruff check chitragupta", "script runs"),
            ('run "ruff"', 'run "ruff lint"', "step names differ"),
            ("ruff==0.16.4", "ruff==0.16.3", "script checks"),
            ("off_main ", "", "must match ci.yml's `if:`"),
            ('run "ruff" ruff check   chitragupta scripts', 'instead "ruff" true', "reserved"),
            ('run "ruff" ruff check   chitragupta scripts', 'need "ruff" ruff', "stands in for"),
        ],
    )
    def test_a_script_side_change_is_reported(self, old, new, expect):
        assert expect in "\n".join(_divergences(_WORKFLOW, _MATCHING_SCRIPT.replace(old, new)))

    def test_a_new_ci_step_is_reported(self):
        workflow = _WORKFLOW + "      - name: shellcheck\n        run: shellcheck scripts/*.sh\n"
        assert "step names differ" in "\n".join(_divergences(workflow, _MATCHING_SCRIPT))

    @pytest.mark.parametrize(
        ("old", "new", "expect"),
        [
            ("ruff==0.16.4", "ruff==0.16.4 bibtexparser==1.4.4", "script checks"),
            ("cp config.toml.example", "cp -f config.toml.example", "reserved"),
            (
                "run: ruff check",
                "env: {X: 1}\n        run: ruff check",
                "keys this test does not pin",
            ),
            (
                "run: ruff check",
                "shell: pwsh\n        run: ruff check",
                "keys this test does not pin",
            ),
            ("'pull_request'", "'push'", "no local form"),
            ("actions/checkout@v4", "reviewdog/action-ruff@v1", "cannot run locally"),
        ],
    )
    def test_a_ci_side_change_is_reported(self, old, new, expect):
        workflow = _WORKFLOW.replace(old, new)
        assert expect in "\n".join(_divergences(workflow, _MATCHING_SCRIPT))

    def test_a_python_package_pin_is_matched_without_its_prefix(self):
        workflow = _WORKFLOW.replace("ruff==0.16.4", "ruff==0.16.4 bibtexparser==1.4.4")
        script = _MATCHING_SCRIPT.replace("ruff==0.16.4", "ruff==0.16.4 py:bibtexparser==1.4.4")
        assert _divergences(workflow, script) == []

    def test_reordered_ci_steps_are_reported(self):
        lines = _MATCHING_SCRIPT.strip().splitlines()
        reordered = "\n".join([lines[1], lines[0], *lines[2:]])
        assert "step names differ" in "\n".join(_divergences(_WORKFLOW, reordered))
