"""`scripts/code_standards.py`: the C1/C2 scanner, and what reads it.

The scanner's *rules* are exercised by `tests/test_code_standards_scan.py`,
which is where they have always been tested and which now imports them
from here rather than defining them. This file covers what the extraction
added: the register file, the path-scoped scan a hook needs, and the CLI.

**Why the scanner moved at all** (issue 431): `docs/HOOKS.md` requires a
hook adapter to hold "no logic anyone could want to run by hand", so the
edit-time hook needs a hand-runnable command to shell out to. The rules
lived inside a test module, and `tests/` is in `scripts/release.py`'s
`EXCLUDE_TOP_LEVEL` -- a shipped hook reading them would have worked in a
checkout and been broken in every release.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def scan():
    spec = importlib.util.spec_from_file_location(
        "code_standards", REPO_ROOT / "scripts" / "code_standards.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheRegisterFile:
    def test_it_is_at_the_repository_root_so_it_ships(self, scan):
        """`tests/` is excluded from the release archive and the root is
        not, which is the whole reason this file exists rather than the
        two Python literals it replaced."""
        assert scan.REGISTER_PATH == REPO_ROOT / "code-standards-register.toml"
        assert scan.REGISTER_PATH.is_file()

    def test_it_parses_into_two_name_to_count_maps(self, scan):
        c1, c2 = scan.register()
        assert all(isinstance(v, int) for v in c1.values())
        assert all(isinstance(v, int) for v in c2.values())

    def test_the_count_is_a_value_not_a_comment(self, scan):
        """`tomllib` discards comments, so the trailing `# 32` the Python
        register carried could not survive the move. Promoting it to a
        real key is what keeps
        `test_every_registered_offender_records_its_current_count`
        able to read it."""
        c1, _ = scan.register()
        assert c1["tests/test_release.py::make_repo"] > scan.MAX_STATEMENTS


class TestScanningNamedPaths:
    """What the hook needs: one file at a time, not the whole tree."""

    def test_a_short_function_is_no_finding(self, scan, tmp_path):
        path = tmp_path / "m.py"
        path.write_text("def f():\n    return 1\n", encoding="utf-8")
        assert scan.findings([path]) == []

    def test_an_over_long_function_is_reported_with_its_count(self, scan, tmp_path):
        path = tmp_path / "m.py"
        body = "\n".join(f"    x{i} = {i}" for i in range(scan.MAX_STATEMENTS + 1))
        path.write_text(f"def f():\n{body}\n", encoding="utf-8")
        found = scan.findings([path])
        assert len(found) == 1
        assert found[0]["rule"] == "C1"
        assert found[0]["count"] == scan.MAX_STATEMENTS + 1
        assert found[0]["limit"] == scan.MAX_STATEMENTS
        assert found[0]["name"].endswith("::f")

    def test_an_over_long_module_is_reported(self, scan, tmp_path):
        path = tmp_path / "m.py"
        path.write_text("\n".join(f"x{i} = {i}" for i in range(scan.MAX_CODE_LINES + 1)), "utf-8")
        assert [f["rule"] for f in scan.findings([path])] == ["C2"]

    def test_a_registered_offender_is_silent(self, scan):
        """The register is what stops the hook reporting the twenty debts
        it was told about on every edit -- noise indistinguishable from a
        real crossing, which is how an advisory check gets switched off."""
        registered = REPO_ROOT / "chitragupta" / "sync.py"
        assert registered.is_file()
        assert [f for f in scan.findings([registered]) if f["rule"] == "C2"] == []

    def test_a_non_python_path_is_skipped(self, scan, tmp_path):
        path = tmp_path / "notes.md"
        path.write_text("# not python\n", encoding="utf-8")
        assert scan.findings([path]) == []

    def test_a_missing_path_is_skipped_rather_than_raising(self, scan, tmp_path):
        """The hook hands over whatever the harness said was written; a
        file deleted between the write and the check is not an error."""
        assert scan.findings([tmp_path / "gone.py"]) == []

    def test_a_file_that_will_not_parse_is_skipped(self, scan, tmp_path):
        """Mid-edit source is the common case for a per-write hook, and a
        syntax error there is the author's business, not this scanner's."""
        path = tmp_path / "m.py"
        path.write_text("def f(:\n", encoding="utf-8")
        assert scan.findings([path]) == []


class TestTheWholeTreeScan:
    def test_no_argument_scans_the_registered_roots(self, scan):
        """The tree is clean by construction -- the ratchet test would be
        red otherwise -- so this asserts the scan reaches the tree and
        agrees with it, the same thing `test_the_scan_reaches_the_source_tree`
        does for the rules."""
        assert scan.findings(None) == []


class TestTheCli:
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "code_standards.py"), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_a_clean_tree_exits_zero_and_says_so(self):
        result = self._run()
        assert result.returncode == 0
        assert "no findings" in result.stdout.lower()

    def test_json_emits_a_findings_list(self):
        result = self._run("--json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["findings"] == []

    def test_a_crossing_is_reported_and_still_exits_zero(self, tmp_path):
        """Advisory, like the hook that calls it: `docs/HOOKS.md`'s rule
        puts C1/C2 on the fail-silent side, because the register's escape
        hatch is part of the standard. The ratchet test is what fails."""
        path = tmp_path / "m.py"
        path.write_text("\n".join(f"x{i} = {i}" for i in range(300)), encoding="utf-8")
        result = self._run(str(path))
        assert result.returncode == 0
        assert "C2" in result.stdout

    def test_json_carries_the_same_findings_the_text_form_names(self, tmp_path):
        path = tmp_path / "m.py"
        path.write_text("\n".join(f"x{i} = {i}" for i in range(300)), encoding="utf-8")
        payload = json.loads(self._run(str(path), "--json").stdout)
        assert [f["rule"] for f in payload["findings"]] == ["C2"]
        assert payload["findings"][0]["count"] == 300
