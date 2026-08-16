""".claude/hooks/citation_gate_hook.py: the PostToolUse hook that
mechanically enforces AGENTS.md's citation gate on every Write/Edit under
content/drafts/ (PR #5). This has zero repo-tracked tests of its own --
its three behavioral fixes (path resolution against the hook's own fixed
location rather than cwd, is_relative_to containment instead of substring
matching, and a malformed-stdin guard) were previously only verified with
ad-hoc pipe-tests during that PR's review cycle.

The hook derives repo_root from its own on-disk location
(Path(__file__).resolve().parent.parent.parent), not from
config.CONTENT_DIR. Any test that needs a real gated file therefore gives
the hook a repo root of its own: `hook_repo` copies the hook script into
a tmp_path `.claude/hooks/`, so its self-location lands there, and the
draft goes under that same root's `content/drafts/`. A copy rather than a
symlink, because `Path(__file__).resolve()` would follow a symlink
straight back to the real checkout.

That also keeps `content/drafts/` and the ledger in one isolated tree,
which matters since 3.17.0: `citation_gate` refuses a draft resolving
outside `CONTENT_DIR`, so a draft in the real repo checked against a
tmp_path ledger would be rejected for its location rather than judged on
its citekeys. Pointing both at the same tmp_path is what keeps the two
consistent -- as they always are in production, where both derive from
the same repo root.

The hook's own subprocess.run call for `python -m src.draft gate`
doesn't pass env=, so it inherits whatever env this test process hands to
the hook subprocess -- used here for CONTENT_DIR, and for a PYTHONPATH
that lets the child import this checkout's real `src` while running from
the temp root.
"""

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from src import ledger

from tests.conftest import make_reference

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "citation_gate_hook.py"


def run_hook(stdin_text: str, env: dict | None = None, cwd: Path | None = None,
             hook: Path | None = None):
    return subprocess.run(
        [sys.executable, str(hook or HOOK_PATH)],
        input=stdin_text,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def payload(file_path) -> str:
    return json.dumps({"tool_input": {"file_path": str(file_path)}})


def _IS_COVERAGE_BOOTSTRAP(name: str) -> bool:
    """Whether an env var would make a child process start its own coverage.

    Stripped from the hook's environment because the hook runs
    `python -m src.draft gate` with `cwd` set to *its* repo root --
    the temp one, under this fixture. Coverage started there finds no
    config file, so it records statement-only data while the parent
    records branch data, and the run dies at combine time with
    "Can't combine statement coverage data with branch data" *after*
    every test has passed.

    Whether it happens at all depends on the pytest-cov version and on
    what `python` resolves to: pytest-cov 6.x ships a `.pth` that
    instruments every subprocess, 7.x does not, and the hook spawns a
    literal `python` rather than `sys.executable`, so a venv on PATH
    (what `poetry run` gives CI) is instrumented while a bare system
    interpreter is not. Stripping these makes every combination behave
    the same. Nothing is lost: the in-process tests already cover
    `src/citation_gate.py` fully, which is why the total is 100% on a
    host where these children were never measured.
    """
    return name.startswith("COV_CORE") or name in (
        "COVERAGE_PROCESS_START", "COVERAGE_FILE", "COVERAGE_RCFILE",
    )


class HookRepo:
    """A throwaway repo root the hook can call its own.

    `root/.claude/hooks/citation_gate_hook.py` is a real copy of the hook,
    so the hook's own `Path(__file__).resolve().parent.parent.parent`
    lands on `root` and it gates `root/content/drafts/`. `src` is not
    copied -- the child process reaches this checkout's real code through
    PYTHONPATH, so these tests exercise the actual gate rather than a
    stale copy of it.
    """

    def __init__(self, root: Path, cfg):
        self.root = root
        self.hook = root / ".claude" / "hooks" / "citation_gate_hook.py"
        self.hook.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOOK_PATH, self.hook)
        # The helper too, or the copy cannot `import draft_target`: a hook
        # is run by absolute path, so Python puts *its* directory first on
        # sys.path, and that directory is this temporary one.
        shutil.copy2(HOOK_PATH.parent / "draft_target.py",
                     self.hook.parent / "draft_target.py")
        self.drafts = root / "content" / "drafts"
        self.drafts.mkdir(parents=True, exist_ok=True)
        self.env = {
            **{k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)},
            "CONTENT_DIR": str(cfg.CONTENT_DIR),
            "PYTHONPATH": str(REPO_ROOT),
        }

    def draft(self, suffix: str = ".md") -> Path:
        return self.drafts / f"hook_test_{uuid.uuid4().hex}{suffix}"

    def run(self, file_path, cwd: Path | None = None):
        return run_hook(
            payload(file_path), env=self.env, cwd=cwd or self.root, hook=self.hook
        )


@pytest.fixture
def hook_repo(isolated_config, tmp_path):
    # tmp_path itself, so the hook's content/drafts/ and isolated_config's
    # CONTENT_DIR are the same tree -- which is what the gate now requires.
    return HookRepo(tmp_path, isolated_config)


class TestMalformedStdinGuard:
    """Regression coverage for the fix that used to let a malformed
    PostToolUse payload crash the hook (json.JSONDecodeError/ValueError
    propagating uncaught) instead of failing open."""

    def test_invalid_json_does_not_crash(self):
        result = run_hook("not valid json {{{")
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert result.stderr == ""

    def test_empty_stdin_does_not_crash(self):
        result = run_hook("")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_json_that_is_not_an_object_does_not_crash(self):
        # Regression: json.load succeeds on valid-but-wrong-shaped JSON
        # (a bare array here), which the original guard's except clause
        # (JSONDecodeError/ValueError only) never caught -- the next line
        # then called .get() on a list and crashed with an uncaught
        # AttributeError instead of failing open.
        result = run_hook("[1, 2, 3]")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_tool_input_that_is_not_an_object_does_not_crash(self):
        # Same class of bug as above, one level deeper: "tool_input"
        # present but not itself an object.
        result = run_hook(json.dumps({"tool_input": "not-an-object"}))
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestIgnoredPayloads:
    def test_missing_file_path_is_ignored(self):
        result = run_hook(json.dumps({"tool_input": {}}))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_missing_tool_input_is_ignored(self):
        result = run_hook(json.dumps({}))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_path_outside_drafts_dir_is_ignored(self):
        # A real .md file, real absolute path -- outside content/drafts/
        # is the only thing that should exempt it.
        result = run_hook(payload(REPO_ROOT / "AGENTS.md"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_non_gated_extension_inside_drafts_dir_is_ignored(self, hook_repo):
        path = hook_repo.draft(suffix=".py")
        path.write_text("@dataclass\nclass Foo:\n    pass\n")
        result = hook_repo.run(path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestContainmentCheck:
    """Regression coverage for the is_relative_to fix -- containment must
    be checked against resolved path parts, not a "/content/drafts/"
    substring match (which a payload carrying a relative path would
    silently skip, and which a string like
    "/tmp/content/drafts/../../evil.md" could spoof)."""

    def test_dotdot_traversal_out_of_drafts_dir_is_rejected(self):
        traversal = REPO_ROOT / "content" / "drafts" / ".." / ".." / "AGENTS.md"
        result = run_hook(payload(traversal))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_lookalike_path_elsewhere_on_disk_is_rejected(self, tmp_path):
        # A path that contains the literal substring "content/drafts/"
        # but sits under a completely different directory tree -- a naive
        # string check (e.g. "content/drafts/" in str(path)) would wrongly
        # treat this as a gated draft; is_relative_to against the
        # *resolved* repo_root/content/drafts/ must reject it.
        decoy_file = tmp_path / "not_this_repo" / "content" / "drafts" / "evil.md"
        decoy_file.parent.mkdir(parents=True)
        decoy_file.write_text("[@fabricated_key_not_in_ledger]\n")

        result = run_hook(payload(decoy_file))
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestPathResolution:
    """Regression coverage for resolving repo_root from the hook's own
    fixed on-disk location rather than the target path or cwd -- a
    relative "content/drafts/<slug>.md" (no leading slash) must still be
    recognized and gated, invoked from any working directory."""

    def test_relative_path_is_resolved_and_gated_regardless_of_cwd(self, hook_repo, tmp_path):
        path = hook_repo.draft()
        path.write_text("No citations in this draft at all.\n")
        rel_path = path.relative_to(hook_repo.root)
        # cwd is deliberately somewhere else: the hook must resolve a
        # relative payload against its own location, not against cwd.
        elsewhere = tmp_path / "elsewhere-cwd"
        elsewhere.mkdir()
        result = hook_repo.run(rel_path, cwd=elsewhere)
        assert result.returncode == 0
        assert result.stdout.strip() == ""  # gate ran and passed -- not silently skipped


class TestGateEnforcement:
    """The actual point of the hook: a citation_gate FAIL must come back
    as a blocking decision with a reason naming the bad citekey; a PASS
    must produce no output at all (PostToolUse only acts on the
    "decision": "block" shape)."""

    def test_fabricated_citation_blocks_with_reason(self, hook_repo):
        path = hook_repo.draft()
        path.write_text("This claim cites [@totally_fabricated_key_2026].\n")
        result = hook_repo.run(path)

        assert result.returncode == 0  # the hook process itself always exits 0
        response = json.loads(result.stdout)
        assert response["decision"] == "block"
        assert "totally_fabricated_key_2026" in response["reason"]
        assert "Citation gate FAILED" in response["reason"]

    def test_verified_citation_does_not_block(self, hook_repo, ledger_con):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="smith_real_2024", title="A Real Paper")
        )
        path = hook_repo.draft()
        path.write_text("A real, grounded claim [@smith_real_2024].\n")
        result = hook_repo.run(path)

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_draft_with_no_citations_does_not_block(self, hook_repo):
        path = hook_repo.draft()
        path.write_text("Plain prose with no citations at all.\n")
        result = hook_repo.run(path)

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_tex_extension_is_also_gated(self, hook_repo):
        path = hook_repo.draft(suffix=".tex")
        path.write_text(r"This claim cites \citep{totally_fabricated_key_2026}." "\n")
        result = hook_repo.run(path)

        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert response["decision"] == "block"
        assert "totally_fabricated_key_2026" in response["reason"]
