"""`chitragupta doctor`: probes the environment and reports -- never
installs, never exits non-zero (SOUL.md's aid-not-gate rule)."""

import importlib.metadata
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import chitragupta.doctor as doctor

REPO_ROOT = Path(__file__).resolve().parent.parent


class FakeEntryPoint(SimpleNamespace):
    group: str
    name: str


class FakeDistribution(SimpleNamespace):
    name: str
    entry_points: list


class TestCheckBinaries:
    def test_a_present_binary_is_ok(self, monkeypatch):
        monkeypatch.setattr(
            doctor.shutil, "which", lambda b: f"/usr/bin/{b}" if b == "pandoc" else None
        )
        lines = doctor._check_binaries()
        assert any(line.startswith("[ok] pandoc") for line in lines)

    def test_an_absent_binary_is_reported_missing(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda b: None)
        lines = doctor._check_binaries()
        assert all("[missing-binary]" in line for line in lines)
        assert len(lines) == len(doctor.BINARIES)


class TestCheckPdfFonts:
    """#996: every family chitragupta/pdf_fonts.py names, looked up the
    way LuaLaTeX will look it up."""

    def test_no_font_loader_is_one_missing_binary_line(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda b: None)
        lines = doctor._check_pdf_fonts()
        assert len(lines) == 1
        assert lines[0].startswith("[missing-binary] luaotfload-tool")
        assert "texlive-luatex" in lines[0]

    def test_each_family_is_reported_found_or_missing(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda b: f"/usr/bin/{b}")
        present = {"STIX Two Text", "Noto Serif"}

        def fake_run(cmd, **kwargs):
            name = cmd[1].removeprefix("--find=")
            # luaotfload-tool exits 0 either way; only the message differs.
            message = (
                f'luaotfload | resolve : Font "{name}" found!'
                if name in present
                else f'luaotfload | resolve : Cannot find "{name}" in index.'
            )
            return SimpleNamespace(returncode=0, stdout="", stderr=message)

        monkeypatch.setattr(doctor.subprocess, "run", fake_run)
        lines = doctor._check_pdf_fonts()
        assert len(lines) == len(doctor.pdf_fonts.all_families())
        assert "[ok] pdf font found: STIX Two Text" in lines
        assert "[ok] pdf font found: Noto Serif" in lines
        missing = [line for line in lines if line.startswith("[missing] pdf font")]
        assert len(missing) == len(lines) - 2
        assert all("install_full_pipeline.sh os-deps" in line for line in missing)


class TestCheckEnrichExtra:
    def test_importable_is_ok(self, monkeypatch):
        monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: object())
        assert "[ok]" in doctor._check_enrich_extra()

    def test_not_importable_names_the_command_that_fixes_it(self, monkeypatch):
        """Names `chitragupta install enrich`, not the pip line it used
        to print. `doctor` is most often read inside
        docker/Dockerfile.claude, where the CLI is all there is and the
        pip incantation was the one thing a user had to know that the
        tool would not do for them."""
        monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: None)
        result = doctor._check_enrich_extra()
        assert "[missing]" in result
        assert "chitragupta install enrich" in result
        assert "incomplete" not in result

    def test_a_partial_install_is_reported_and_names_what_is_missing(self, monkeypatch):
        """m-35 (#509): probing `sentence_transformers` alone reported the
        whole tier ok on a host that had it and nothing else, so `doctor`
        passed and the run failed at the first stage reaching for
        `docling` -- the opposite of what a preflight is for."""
        monkeypatch.setattr(
            doctor.importlib.util,
            "find_spec",
            lambda name: object() if name == "sentence_transformers" else None,
        )
        result = doctor._check_enrich_extra()
        assert "[missing]" in result
        assert "incomplete" in result
        assert "docling" in result
        assert "sentence_transformers" not in result

    def test_every_module_the_extra_installs_is_probed(self):
        """The list is `pyproject.toml`'s, read from it rather than
        restated here -- a package added to the extra and not to
        `ENRICH_MODULES` would otherwise go unprobed forever."""
        import tomllib

        data = tomllib.loads(REPO_ROOT.joinpath("pyproject.toml").read_text(encoding="utf-8"))
        declared = data["tool"]["poetry"]["extras"]["enrich"]
        assert [name.replace("-", "_") for name in declared] == list(doctor.ENRICH_MODULES)


class TestCheckGpuTorch:
    def test_no_gpu_is_ok(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda b: None)
        assert "[ok] no GPU detected" in doctor._check_gpu_torch()

    def test_gpu_present_but_torch_missing_is_skipped(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda b: "/usr/bin/nvidia-smi")
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("no torch")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        assert "[skipped]" in doctor._check_gpu_torch()

    def test_gpu_present_and_torch_sees_it_is_ok(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda b: "/usr/bin/nvidia-smi")
        fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True))
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            return fake_torch if name == "torch" else real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        assert "[ok] torch sees the GPU" in doctor._check_gpu_torch()

    def test_gpu_present_but_torch_cpu_only_names_the_fix(self, monkeypatch):
        monkeypatch.setattr(doctor.shutil, "which", lambda b: "/usr/bin/nvidia-smi")
        fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            return fake_torch if name == "torch" else real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        result = doctor._check_gpu_torch()
        assert "[gpu-mismatch]" in result
        assert "chitragupta install gpu-torch" in result


class TestCompetingDistribution:
    def test_no_other_distribution_is_ok(self, monkeypatch):
        mine = FakeDistribution(
            name="chitragupta-cli",
            entry_points=[
                FakeEntryPoint(group="console_scripts", name="chitragupta"),
            ],
        )
        monkeypatch.setattr(importlib.metadata, "distributions", lambda: [mine])
        assert "[ok] no competing" in doctor._check_competing_distribution()

    def test_another_distribution_owning_chitragupta_is_a_collision(self, monkeypatch):
        mine = FakeDistribution(
            name="chitragupta-cli",
            entry_points=[
                FakeEntryPoint(group="console_scripts", name="chitragupta"),
            ],
        )
        theirs = FakeDistribution(
            name="chitragupta",
            entry_points=[
                FakeEntryPoint(group="console_scripts", name="chitragupta"),
            ],
        )
        monkeypatch.setattr(importlib.metadata, "distributions", lambda: [mine, theirs])
        result = doctor._check_competing_distribution()
        assert "[collision]" in result
        assert "chitragupta" in result

    def test_a_distribution_with_no_console_scripts_is_not_a_collision(self, monkeypatch):
        mine = FakeDistribution(name="chitragupta-cli", entry_points=[])
        unrelated = FakeDistribution(
            name="some-other-package",
            entry_points=[
                FakeEntryPoint(group="console_scripts", name="something-else"),
            ],
        )
        monkeypatch.setattr(importlib.metadata, "distributions", lambda: [mine, unrelated])
        assert "[ok] no competing" in doctor._check_competing_distribution()


class TestMain:
    def test_exits_zero_regardless_of_findings(self, monkeypatch, capsys):
        monkeypatch.setattr(doctor.shutil, "which", lambda b: None)
        monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: None)
        monkeypatch.setattr(importlib.metadata, "distributions", lambda: [])
        assert doctor.main([]) == 0
        out = capsys.readouterr().out
        assert "[missing-binary]" in out

    def test_help_exits_zero(self):
        with pytest.raises(SystemExit) as excinfo:
            doctor.main(["--help"])
        assert excinfo.value.code == 0

    def test_help_does_not_print_the_module_docstring(self):
        assert doctor.DESCRIPTION != doctor.__doc__
        assert "\n\n" not in doctor.DESCRIPTION


class TestCheckLaunchers:
    """#812: a dead launcher on any harness, by name, and never fatal."""

    @staticmethod
    def codex(root, program):
        (root / ".codex").mkdir()
        hooks = {"PostToolUse": [{"hooks": [{"type": "command", "command": f"{program} x.py"}]}]}
        (root / ".codex" / "hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")

    def test_a_project_with_sound_launchers_is_ok(self, tmp_path):
        assert doctor._check_launchers(tmp_path) == ["[ok] every hook launcher found can start"]

    def test_a_dead_codex_launcher_is_named(self, tmp_path):
        self.codex(tmp_path, "no-such-interpreter-812")
        lines = doctor._check_launchers(tmp_path)
        assert len(lines) == 1
        assert lines[0].startswith("[launcher] .codex/hooks.json: ")
        assert "no-such-interpreter-812" in lines[0]

    def test_an_opencode_project_without_the_plugin_is_named(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        lines = doctor._check_launchers(tmp_path)
        assert "OpenCode runs no citation gate" in lines[0]

    def test_an_opencode_project_with_the_plugin_is_ok(self, tmp_path):
        (tmp_path / ".opencode" / "plugins").mkdir(parents=True)
        (tmp_path / ".opencode" / "plugins" / "chitragupta-gate.js").write_text("//")
        assert doctor._check_launchers(tmp_path)[0].startswith("[ok]")

    def test_main_reports_it_and_still_exits_0(self, tmp_path, monkeypatch, capsys):
        self.codex(tmp_path, "no-such-interpreter-812")
        monkeypatch.chdir(tmp_path)
        assert doctor.main([]) == 0
        assert "[launcher] .codex/hooks.json" in capsys.readouterr().out


class TestCheckOpencodeSkills:
    """#900: OpenCode keys skills by name, so its deny list is what keeps it
    on its own copies."""

    @staticmethod
    def project(root, rules):
        (root / ".opencode" / "skills" / "survey-writer-opencode").mkdir(parents=True)
        if rules is not None:
            config = {"permission": {"skill": rules}}
            (root / ".opencode" / "opencode.json").write_text(json.dumps(config), encoding="utf-8")

    def test_no_opencode_skills_says_nothing(self, tmp_path):
        assert doctor._check_opencode_skills(tmp_path) == []

    def test_a_complete_deny_list_is_ok(self, tmp_path):
        self.project(tmp_path, {"*": "allow", "survey-writer": "deny"})
        assert doctor._check_opencode_skills(tmp_path)[0].startswith("[ok]")

    @pytest.mark.parametrize("rules", [None, {"*": "allow"}, "deny", {"survey-writer": "ask"}])
    def test_a_missing_or_partial_deny_list_is_named(self, tmp_path, rules):
        self.project(tmp_path, rules)
        (line,) = doctor._check_opencode_skills(tmp_path)
        assert line.startswith("[skills]")
        assert "survey-writer" in line

    def test_a_config_that_is_not_json_is_named(self, tmp_path):
        self.project(tmp_path, None)
        (tmp_path / ".opencode" / "opencode.json").write_text("{not json", encoding="utf-8")
        assert doctor._check_opencode_skills(tmp_path)[0].startswith("[skills]")
