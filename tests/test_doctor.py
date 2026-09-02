"""`chitragupta doctor`: probes the environment and reports -- never
installs, never exits non-zero (SOUL.md's aid-not-gate rule)."""

import importlib.metadata
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


class TestCheckEnrichExtra:
    def test_importable_is_ok(self, monkeypatch):
        monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: object())
        assert "[ok]" in doctor._check_enrich_extra()

    def test_not_importable_names_the_extra(self, monkeypatch):
        monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: None)
        result = doctor._check_enrich_extra()
        assert "[missing]" in result
        assert "'chitragupta-cli[enrich]'" in result
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
