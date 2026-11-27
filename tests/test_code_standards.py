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
        assert scan.REGISTER_PATH == REPO_ROOT / "code-standards-register.toml"
        assert scan.REGISTER_PATH.is_file()

    def test_it_parses_into_two_name_to_count_maps(self, scan):
        c1, c2 = scan.register()
        assert all(isinstance(v, int) for v in c1.values())
        assert all(isinstance(v, int) for v in c2.values())

    def test_the_count_is_a_value_not_a_comment(self, scan):
        c1, _ = scan.register()
        assert c1["tests/test_release.py::make_repo"] > scan.MAX_STATEMENTS


class TestScanningNamedPaths:
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
        registered = REPO_ROOT / "chitragupta" / "sync.py"
        assert registered.is_file()
        assert [f for f in scan.findings([registered]) if f["rule"] == "C2"] == []

    def test_a_non_python_path_is_skipped(self, scan, tmp_path):
        path = tmp_path / "notes.md"
        path.write_text("# not python\n", encoding="utf-8")
        assert scan.findings([path]) == []

    def test_a_missing_path_is_skipped_rather_than_raising(self, scan, tmp_path):
        assert scan.findings([tmp_path / "gone.py"]) == []

    def test_a_file_that_will_not_parse_is_skipped(self, scan, tmp_path):
        path = tmp_path / "m.py"
        path.write_text("def f(:\n", encoding="utf-8")
        assert scan.findings([path]) == []


class TestTheWholeTreeScan:
    def test_no_argument_scans_the_registered_roots(self, scan):
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


class TestTheCliInProcess:
    def test_a_clean_tree_says_so(self, scan, capsys):
        assert scan.main([]) == 0
        assert "no findings" in capsys.readouterr().out.lower()

    def test_json_emits_a_findings_list(self, scan, capsys):
        assert scan.main(["--json"]) == 0
        assert json.loads(capsys.readouterr().out)["findings"] == []

    def test_a_crossing_is_named_in_the_text_form(self, scan, tmp_path, capsys):
        path = tmp_path / "m.py"
        path.write_text("\n".join(f"x{i} = {i}" for i in range(300)), encoding="utf-8")
        assert scan.main([str(path)]) == 0
        assert "C2" in capsys.readouterr().out

    def test_each_rule_names_its_own_unit(self, scan):
        text = scan.format_findings(
            [
                {"rule": "C1", "name": "f", "count": 30, "limit": 25},
                {"rule": "C2", "name": "m.py", "count": 300, "limit": 250},
            ]
        )
        assert "C1  f  30 statements (limit 25)" in text
        assert "C2  m.py  300 code lines (limit 250)" in text
