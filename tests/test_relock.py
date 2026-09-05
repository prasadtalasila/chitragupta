"""`scripts/relock.py`: regenerating `poetry.lock` via uv's resolution.

The script exists because `poetry lock --regenerate` does not finish on
this dependency set -- see `docs/UV-MIGRATION.md` for the measurements.
It edits two tracked files (`pyproject.toml` and `poetry.lock`) and
restores them on failure, so the tests that matter most here are the
restore ones: a half-pinned `pyproject.toml` left behind by an
interrupted run reads as a hand edit weeks later, which is exactly the
kind of thing nobody traces back to a script.

Nothing in this module runs `uv` or `poetry` for real. Both are
subprocesses whose behaviour the script only reads through a return
code, and a test that shelled out to them would be measuring the
network.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def relock():
    spec = importlib.util.spec_from_file_location("relock", REPO_ROOT / "scripts" / "relock.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(relock, tmp_path, monkeypatch):
    """A throwaway pyproject.toml/poetry.lock pair the script may edit.

    Pointed at `tmp_path` rather than the repository's own files: every
    write test below would otherwise rewrite the lock this project
    ships, and a failing assertion would leave it rewritten.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "\n".join(
            [
                "[tool.poetry]",
                'name = "x"',
                "[tool.poetry.dependencies]",
                'python = ">=3.12,<3.15"',
                'bibtexparser = ">=1.4,<2.0"',
                'pinned-thing = "0.1.5"',
                'optional-thing = {version = ">=2.0,<3.0", optional = true}',
                "[tool.poetry.group.dev.dependencies]",
                'pytest = ">=9.0,<10.0"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    lock = tmp_path / "poetry.lock"
    lock.write_bytes(b"original lock\n")
    monkeypatch.setattr(relock, "PYPROJECT", pyproject)
    monkeypatch.setattr(relock, "LOCK", lock)
    return pyproject, lock


class TestDeclaredRequirements:
    def test_every_group_is_collected_and_python_is_not(self, relock, project):
        requirements = relock._declared_requirements()
        assert "bibtexparser>=1.4,<2.0" in requirements
        assert "pytest>=9.0,<10.0" in requirements, "the dev group has to be included"
        assert "optional-thing>=2.0,<3.0" in requirements
        assert not any(r.startswith("python") for r in requirements)

    def test_a_bare_pin_becomes_a_pep508_equality(self, relock, project):
        """The mkdocs-same-dir case, and the one that actually bit.

        `pinned-thing = "0.1.5"` passed through unchanged produces
        `pinned-thing0.1.5`, which uv reports as a package that does not
        exist -- a confusing error a long way from its cause.
        """
        assert "pinned-thing==0.1.5" in relock._declared_requirements()


class TestPep508:
    @pytest.mark.parametrize(
        ("declared", "expected"),
        [(">=1.4,<2.0", ">=1.4,<2.0"), ("0.1.5", "==0.1.5"), ("*", ""), ("!=1.2", "!=1.2")],
    )
    def test_the_forms_this_project_uses(self, relock, declared, expected):
        assert relock._pep508("thing", declared) == expected

    def test_an_untranslatable_form_refuses_rather_than_guessing(self, relock):
        """A caret is *guessable* -- `^1.2` is `>=1.2,<2.0` -- and
        guessing is the wrong move: a mistranslation resolves to a
        plausible wrong version and lands in the lock silently."""
        with pytest.raises(SystemExit) as excinfo:
            relock._pep508("thing", "^1.2")
        assert "does not translate" in str(excinfo.value)


class TestPin:
    def test_both_declaration_shapes_are_rewritten(self, relock, project):
        pyproject, _ = project
        pinned = relock._pin(
            pyproject.read_text(encoding="utf-8"),
            {"bibtexparser": "1.4.4", "optional-thing": "2.5.0"},
        )
        assert 'bibtexparser = "1.4.4"' in pinned
        assert 'optional-thing = {version = "2.5.0", optional = true}' in pinned

    def test_an_inline_table_keeps_its_other_keys(self, relock):
        """`{version = "...", optional = true}` is not the only shape an
        inline table takes -- `markers`, `python` and `source` all belong
        there too, and rebuilding the line from the name would drop
        them."""
        line = 'thing = {version = ">=1.0,<2.0", optional = true, markers = "sys_platform == \'linux\'"}'
        assert relock._pin_line("thing", line, "1.5.0") == (
            'thing = {version = "1.5.0", optional = true, markers = "sys_platform == \'linux\'"}'
        )

    def test_a_declaration_with_no_recognisable_version_refuses(self, relock):
        """Silently skipping it would leave the package unpinned, Poetry
        would search it again, and the script would look like it worked
        while doing the one thing it exists to avoid."""
        with pytest.raises(SystemExit) as excinfo:
            relock._pin_line("thing", 'thing = { git = "https://example.invalid" }', "1.5.0")
        assert "cannot pin thing" in str(excinfo.value)

    def test_comments_and_unknown_lines_survive(self, relock):
        """The comments are most of what `pyproject.toml` is worth here,
        and the pinned file is written back over the real one."""
        text = '# bibtexparser = "9.9.9" is a comment, not a declaration\nname = "x"\n'
        assert relock._pin(text, {"bibtexparser": "1.4.4"}) == text


class TestResolveWithUv:
    def test_versions_are_read_back_out_of_uv_output(self, relock, monkeypatch):
        def fake_run(command, **_kwargs):
            Path(command[command.index("-o") + 1]).write_text(
                "torch==2.14.0\n  # a comment\nscipy==1.18.1  # via torch\n", encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(relock, "_run", fake_run)
        assert relock._resolve_with_uv("uv", ["torch"]) == {
            "torch": "2.14.0",
            "scipy": "1.18.1",
        }

    def test_an_unresolvable_set_exits_with_uvs_own_message(self, relock, monkeypatch):
        monkeypatch.setattr(
            relock,
            "_run",
            lambda command, **_k: subprocess.CompletedProcess(command, 1, "", "conflict here"),
        )
        with pytest.raises(SystemExit) as excinfo:
            relock._resolve_with_uv("uv", ["torch"])
        assert "conflict here" in str(excinfo.value)


class TestTool:
    def test_a_missing_tool_says_how_to_install_it(self, relock, monkeypatch):
        monkeypatch.setattr(relock.shutil, "which", lambda _name: None)
        with pytest.raises(SystemExit) as excinfo:
            relock._tool("uv")
        assert "pip install uv" in str(excinfo.value)

    def test_a_present_tool_is_returned(self, relock, monkeypatch):
        monkeypatch.setattr(relock.shutil, "which", lambda _name: "/usr/bin/uv")
        assert relock._tool("uv") == "/usr/bin/uv"


class TestRegenerate:
    def test_the_lock_is_written_and_pyproject_restored(self, relock, project, monkeypatch):
        pyproject, lock = project
        original = pyproject.read_text(encoding="utf-8")
        seen = []

        def fake_lock(_poetry, step):
            seen.append((step, pyproject.read_text(encoding="utf-8")))
            lock.write_bytes(b"new lock\n")
            return 1.0

        monkeypatch.setattr(relock, "_poetry_lock", fake_lock)
        relock._regenerate("poetry", {"bibtexparser": "1.4.4"})

        assert pyproject.read_text(encoding="utf-8") == original, "must be put back verbatim"
        assert lock.read_bytes() == b"new lock\n"
        assert 'bibtexparser = "1.4.4"' in seen[0][1], "the first pass locks against pins"
        assert seen[1][1] == original, "the second locks against the real constraints"

    def test_a_failure_restores_both_files(self, relock, project, monkeypatch):
        pyproject, lock = project
        original = pyproject.read_text(encoding="utf-8")

        def boom(_poetry, _step):
            raise RuntimeError("poetry fell over")

        monkeypatch.setattr(relock, "_poetry_lock", boom)
        with pytest.raises(RuntimeError):
            relock._regenerate("poetry", {"bibtexparser": "1.4.4"})
        assert pyproject.read_text(encoding="utf-8") == original
        assert lock.read_bytes() == b"original lock\n", "the previous lock comes back"

    def test_an_interrupt_restores_too(self, relock, project, monkeypatch):
        """KeyboardInterrupt is not an Exception, and `except Exception`
        would let Ctrl-C leave a pinned pyproject.toml behind -- the one
        failure mode that later looks like somebody's hand edit."""
        pyproject, _ = project
        original = pyproject.read_text(encoding="utf-8")

        def interrupted(_poetry, _step):
            raise KeyboardInterrupt

        monkeypatch.setattr(relock, "_poetry_lock", interrupted)
        with pytest.raises(KeyboardInterrupt):
            relock._regenerate("poetry", {"bibtexparser": "1.4.4"})
        assert pyproject.read_text(encoding="utf-8") == original

    def test_a_missing_previous_lock_is_not_recreated(self, relock, project, monkeypatch):
        """`unlink(missing_ok=True)` plus a None guard: a run that starts
        with no lock and fails should not leave an empty one behind."""
        pyproject, lock = project
        lock.unlink()
        monkeypatch.setattr(
            relock, "_poetry_lock", lambda _p, _s: (_ for _ in ()).throw(RuntimeError("x"))
        )
        with pytest.raises(RuntimeError):
            relock._regenerate("poetry", {})
        assert not lock.exists()


class TestPoetryLock:
    def test_a_failing_lock_names_the_step(self, relock, monkeypatch):
        monkeypatch.setattr(
            relock,
            "_run",
            lambda command, **_k: subprocess.CompletedProcess(command, 1, "", "lock blew up"),
        )
        with pytest.raises(SystemExit) as excinfo:
            relock._poetry_lock("poetry", "the pinned pass")
        assert "the pinned pass" in str(excinfo.value)
        assert "lock blew up" in str(excinfo.value)

    def test_a_successful_lock_returns_its_duration(self, relock, monkeypatch):
        monkeypatch.setattr(
            relock, "_run", lambda command, **_k: subprocess.CompletedProcess(command, 0, "", "")
        )
        assert relock._poetry_lock("poetry", "a pass") >= 0.0


class TestMain:
    def test_check_writes_nothing(self, relock, project, monkeypatch, capsys):
        pyproject, lock = project
        monkeypatch.setattr(relock, "_tool", lambda _name: "/usr/bin/uv")
        monkeypatch.setattr(relock, "_resolve_with_uv", lambda _uv, _r: {"bibtexparser": "1.4.4"})
        assert relock.main(["--check"]) == 0
        assert lock.read_bytes() == b"original lock\n"
        assert "bibtexparser==1.4.4" in capsys.readouterr().out
        assert 'bibtexparser = ">=1.4,<2.0"' in pyproject.read_text(encoding="utf-8")

    def test_a_full_run_regenerates(self, relock, project, monkeypatch, capsys):
        _, lock = project
        monkeypatch.setattr(relock, "_tool", lambda _name: "/usr/bin/" + _name)
        monkeypatch.setattr(relock, "_resolve_with_uv", lambda _uv, _r: {"bibtexparser": "1.4.4"})
        monkeypatch.setattr(
            relock, "_poetry_lock", lambda _p, _s: lock.write_bytes(b"regenerated\n") or 1.0
        )
        assert relock.main([]) == 0
        assert lock.read_bytes() == b"regenerated\n"
        assert "done" in capsys.readouterr().out

    def test_the_run_command_shells_out_from_the_repo_root(self, relock):
        """`_run` is the one place a real subprocess is configured, and
        `cwd` is what makes `poetry lock` act on this project rather than
        on wherever the caller happened to be."""
        result = relock._run(["python3", "-c", "import os; print(os.getcwd())"])
        assert result.stdout.strip() == str(relock.REPO_ROOT)
