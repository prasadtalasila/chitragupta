"""`chitragupta/programs.py`: a launched program comes from PATH, never cwd (#974).

The class this closes is program resolution that can pick up the current
directory. On Windows `shutil.which` prepends `.` to the search, and
`CreateProcess`, which `subprocess.run([name, ...])` uses, searches the
current directory before PATH; on any host a relative or empty PATH
entry does the same. Either way a `python.exe` planted in a cloned
project ran with the user's privileges. The unit cases below plant
programs in a temporary cwd; the scan at the bottom enumerates every
launch in the package and the hooks, so a new one that hands
`subprocess.run` a bare name fails here rather than in a review.
"""

import ast
import os
import stat
import sys
from pathlib import Path

import pytest

from chitragupta import programs

from tests.test_subprocess_launch_scan import _subprocess_names

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every spelling a Windows lookup tries for `python` (PATHEXT), plus the
# bare one a POSIX lookup tries.
_PLANTED = ("python", "python.exe", "python.bat", "python.cmd")


def _executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def planted(tmp_path, monkeypatch):
    """A cwd holding every spelling of `python`, and a PATH that names the
    cwd both ways a relative entry can: `.` and an empty entry."""
    project = tmp_path / "project"
    project.mkdir()
    for name in _PLANTED:
        _executable(project / name)
    monkeypatch.chdir(project)
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", os.environ.get("PATH", "")]))
    return project


class TestResolveProgram:
    def test_a_program_planted_in_cwd_is_never_the_answer(self, planted):
        found = programs.resolve_program("python")
        assert found is None or not Path(found).resolve().is_relative_to(planted)

    def test_the_planted_shape_is_what_shutil_which_returns(self, planted):
        """The guard is tested against the shape it was blind to: the
        plain lookup this replaced does pick the planted file."""
        import shutil  # pylint: disable=import-outside-toplevel

        assert Path(shutil.which("python")).resolve().is_relative_to(planted)

    def test_an_absolute_path_entry_is_searched(self, tmp_path, monkeypatch):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        tool = _executable(bin_dir / ("tool.exe" if sys.platform == "win32" else "tool"))
        monkeypatch.setenv("PATH", str(bin_dir))
        found = programs.resolve_program("tool")
        assert found is not None
        assert Path(found) == tool
        assert Path(found).is_absolute()

    def test_windows_looks_for_the_exe_createprocess_would_run(self, monkeypatch):
        """Not the first PATHEXT match: a `.bat` would run through
        cmd.exe, which re-parses the arguments."""
        monkeypatch.setattr(programs.sys, "platform", "win32")
        monkeypatch.setenv("PATH", os.path.abspath(os.sep))
        searched = []
        monkeypatch.setattr(programs.shutil, "which", lambda cmd: searched.append(cmd))
        programs.resolve_program("pdftotext")
        programs.resolve_program("python3.12")
        root = os.path.abspath(os.sep)
        assert searched == [
            os.path.join(root, "pdftotext.exe"),
            os.path.join(root, "python3.12"),
        ]

    def test_a_relative_entry_naming_another_directory_is_skipped(self, tmp_path, monkeypatch):
        (tmp_path / "bin").mkdir()
        _executable(tmp_path / "bin" / "tool")
        _executable(tmp_path / "bin" / "tool.bat")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", "bin")
        assert programs.resolve_program("tool") is None

    def test_a_program_on_no_path_entry_is_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATH", str(tmp_path))
        assert programs.resolve_program("no-such-program-anywhere") is None

    def test_an_unset_path_falls_back_to_the_default(self, monkeypatch):
        monkeypatch.delenv("PATH", raising=False)
        searched = []
        monkeypatch.setattr(programs.shutil, "which", lambda cmd: searched.append(cmd))
        programs.resolve_program("tool")
        expected = [d for d in os.defpath.split(os.pathsep) if os.path.isabs(d)]
        suffix = ".exe" if sys.platform == "win32" else ""
        assert searched == [os.path.join(d, "tool" + suffix) for d in expected]


class TestRequireProgram:
    def test_a_found_program_is_its_absolute_path(self, monkeypatch):
        monkeypatch.setattr(programs, "resolve_program", lambda name: f"/usr/bin/{name}")
        assert programs.require_program("pdftotext") == "/usr/bin/pdftotext"

    def test_a_missing_program_raises_what_subprocess_would_have(self, monkeypatch):
        """FileNotFoundError, as `subprocess.run(["pdftotext", ...])`
        raises for a missing program, so every caller's existing
        `except OSError` keeps its meaning."""
        monkeypatch.setattr(programs, "resolve_program", lambda name: None)
        with pytest.raises(FileNotFoundError, match="pdftotext"):
            programs.require_program("pdftotext")


# --- The scan: no launch in the package or the hooks takes a bare name ----

_RESOLVERS = {"resolve_program", "require_program"}
_LAUNCHERS = {"run", "Popen", "call", "check_call", "check_output"}


class Unfollowed(Exception):
    """An argv shape the scan cannot follow. Failing on it, rather than
    passing, keeps a new shape from being a way around the check."""


def _call_name(node) -> "str | None":
    func = node.func if isinstance(node, ast.Call) else None
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else None


def _launch_argv(node, modules, functions):
    """The argv a `subprocess` launch is given, positionally or as
    `args=`; None if `node` is not a launch."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    named = isinstance(func, ast.Name) and func.id in functions
    attribute = (
        isinstance(func, ast.Attribute)
        and func.attr in _LAUNCHERS
        and getattr(func.value, "id", None) in modules
    )
    if not (named or attribute):
        return None
    if node.args:
        return node.args[0]
    keyword = [k.value for k in node.keywords if k.arg == "args"]
    if not keyword:
        raise Unfollowed(ast.unparse(node))
    return keyword[0]


def _functions(tree) -> dict:
    return {
        n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _enclosing(tree, target):
    """The innermost function holding `target`, or the module."""
    inner = tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            child is target for child in ast.walk(node)
        ):
            if inner is tree or any(child is node for child in ast.walk(inner)):
                inner = node
    return inner


def _bindings(scope, name: str) -> list:
    """Values bound to `name` in `scope` by a plain `name = value`.

    Any other binding -- a `for` target, `with ... as`, `+=`, an
    annotation, a walrus, tuple unpacking, an import -- is a value the
    scan does not follow, so it raises rather than reading as none.
    """
    plain = [
        node.value
        for node in ast.walk(scope)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == name
    ]
    stores = [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store)
    ]
    imported = [
        alias
        for node in ast.walk(scope)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
        if (alias.asname or alias.name) == name
    ]
    if len(stores) > len(plain) or imported:
        raise Unfollowed(name)
    return plain


def _argv_lists(arg, scope, tree) -> list:
    """Every (list or tuple literal, the scope that built it) `arg` can
    be: itself, a name bound to one, or what a same-module function
    returns -- whose elements are then judged in *that* function."""
    if isinstance(arg, (ast.List, ast.Tuple)):
        return [(arg, scope)]
    if isinstance(arg, ast.Name) and _bindings(scope, arg.id):
        return [pair for v in _bindings(scope, arg.id) for pair in _argv_lists(v, scope, tree)]
    function = _functions(tree).get(_call_name(arg)) if isinstance(arg, ast.Call) else None
    if function is not None:
        returns = [n.value for n in ast.walk(function) if isinstance(n, ast.Return) and n.value]
        return [pair for r in returns for pair in _argv_lists(r, function, tree)]
    raise Unfollowed(ast.unparse(arg))


def _argument(call, function, name: str):
    """The expression `call` passes for `function`'s parameter `name`:
    positional, keyword, or the default. Splats and methods raise."""
    if any(isinstance(a, ast.Starred) for a in call.args) or any(
        k.arg is None for k in call.keywords
    ):
        raise Unfollowed(ast.unparse(call))
    if isinstance(call.func, ast.Attribute):
        raise Unfollowed(ast.unparse(call))  # a method's `self` shifts every index
    params = [a.arg for a in function.args.posonlyargs + function.args.args]
    if name in params and params.index(name) < len(call.args):
        return call.args[params.index(name)]
    keyword = [k.value for k in call.keywords if k.arg == name]
    if keyword:
        return keyword[0]
    defaults = dict(zip(reversed(params), reversed(function.args.defaults)))
    kw_defaults = dict(zip([a.arg for a in function.args.kwonlyargs], function.args.kw_defaults))
    default = defaults.get(name) or kw_defaults.get(name)
    if default is None:
        raise Unfollowed(ast.unparse(call))
    return default


def _is_resolved(node, scope, tree) -> bool:
    """`sys.executable`, a resolver's result, or a name holding one -- a
    local, or a parameter every same-module caller passes one for."""
    if isinstance(node, ast.Attribute):
        return node.attr == "executable" and getattr(node.value, "id", None) == "sys"
    if isinstance(node, ast.Call):
        return _call_name(node) in _RESOLVERS
    if not isinstance(node, ast.Name):
        return False
    if _bindings(scope, node.id):
        return all(_is_resolved(v, scope, tree) for v in _bindings(scope, node.id))
    args = getattr(scope, "args", None)
    params = [a.arg for a in (args.posonlyargs + args.args + args.kwonlyargs)] if args else []
    calls = [n for n in ast.walk(tree) if _call_name(n) == getattr(scope, "name", None)]
    if node.id not in params or not calls:
        raise Unfollowed(node.id)
    return all(_is_resolved(_argument(c, scope, node.id), _enclosing(tree, c), tree) for c in calls)


def bare_launches(source: str) -> "list[tuple[int, str]]":
    """(line, why) for each launch whose program is not resolved."""
    tree = ast.parse(source)
    modules, functions = _subprocess_names(tree)
    found = []
    for node in ast.walk(tree):
        try:
            argv = _launch_argv(node, modules, functions)
            if argv is None:
                continue
            for literal, built_in in _argv_lists(argv, _enclosing(tree, node), tree):
                first = literal.elts[0] if literal.elts else None
                if first is None or not _is_resolved(first, built_in, tree):
                    found.append((node.lineno, ast.unparse(first) if first else "[]"))
        except Unfollowed as exc:
            found.append((node.lineno, f"cannot follow {exc}"))
    return found


def _scanned() -> list:
    return sorted(
        [
            *(REPO_ROOT / "chitragupta").rglob("*.py"),
            *(REPO_ROOT / ".claude" / "hooks").rglob("*.py"),
        ]
    )


def test_no_launch_in_the_package_or_the_hooks_takes_a_bare_name():
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{line} {why}"
        for path in _scanned()
        for line, why in bare_launches(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "resolve the program with chitragupta.programs.resolve_program or "
        "require_program (or use sys.executable), so a binary planted in "
        "cwd is never what runs:\n  " + "\n  ".join(offenders)
    )


def test_the_scan_reaches_the_launches_it_is_about():
    """A scan that finds no launch at all passes for the wrong reason."""
    launches = 0
    for path in _scanned():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules, functions = _subprocess_names(tree)
        launches += sum(_launch_argv(n, modules, functions) is not None for n in ast.walk(tree))
    assert launches >= 15


class TestTheScanSeesTheShapesItWasWrittenFor:
    """Fed the real pre-#974 launches, so a scan reporting clean is shown
    not to be blind."""

    def test_a_bare_literal(self):
        old = 'def f(p):\n    subprocess.run(["pdftotext", "-layout", p, "-"])\n'
        assert bare_launches(old) == [(2, "'pdftotext'")]

    def test_an_argv_bound_to_a_name_first(self):
        old = (
            'def f():\n    command = ["bash", str(SCRIPT), "os-deps"]\n'
            "    subprocess.run(command)\n"
        )
        assert bare_launches(old) == [(3, "'bash'")]

    def test_an_argv_a_same_module_function_builds(self):
        """style_check's `_run(_vale_argv(draft, language))`."""
        old = (
            "from subprocess import run as _run\n"
            'def _vale_argv(d):\n    return ["vale", d]\n'
            "def run_vale(d):\n    _run(_vale_argv(d))\n"
        )
        assert bare_launches(old) == [(5, "'vale'")]

    def test_a_parameter_a_caller_fills_with_a_bare_name(self):
        """hook_launchers' `_import_fault(program, env)`."""
        old = (
            "def _import_fault(program):\n"
            '    subprocess.run([program, "-c", "import chitragupta"])\n'
            "def faults(program):\n    _import_fault(program)\n"
        )
        assert bare_launches(old) == [(2, "cannot follow program")]

    def test_what_is_resolved_is_left_alone(self):
        source = (
            "def f(p):\n"
            '    subprocess.run([sys.executable, "-m", "pip"])\n'
            '    subprocess.run([programs.require_program("pdftotext"), p])\n'
            '    smi = resolve_program("nvidia-smi")\n'
            '    subprocess.run([smi, "--list-gpus"])\n'
            "def _vale_argv(vale, d):\n    return [vale, d]\n"
            'def run_vale(d):\n    vale = resolve_program("vale")\n'
            "    subprocess.run(_vale_argv(vale, d))\n"
        )
        assert bare_launches(source) == []

    def test_an_argv_from_elsewhere_is_reported_not_passed(self):
        old = "def _run_pandoc(cmd, env):\n    subprocess.run(cmd, env=env)\n"
        assert bare_launches(old) == [(2, "cannot follow cmd")]

    def test_an_element_is_judged_where_its_list_was_built(self):
        """A resolved local of the same name at the launch site must not
        vouch for a bare one in the builder."""
        old = (
            'def _argv(d):\n    tool = "vale"\n    return [tool, d]\n'
            'def run(d):\n    tool = resolve_program("vale")\n    subprocess.run(_argv(d))\n'
        )
        assert bare_launches(old) == [(6, "tool")]

    def test_a_bare_name_passed_by_keyword_or_left_to_a_default(self):
        old = (
            'def f(program="bash"):\n    subprocess.run([program])\n'
            'def g():\n    f(program="python")\n    f()\n'
        )
        assert bare_launches(old) == [(2, "program")]

    def test_a_method_call_is_not_followed(self):
        old = (
            "class C:\n"
            "    def f(self, program):\n        subprocess.run([program])\n"
            '    def g(self):\n        self.f("bash")\n'
        )
        assert bare_launches(old) == [(3, "cannot follow self.f('bash')")]

    def test_an_argv_given_as_args_keyword(self):
        old = 'def f():\n    subprocess.run(args=["bash", "x"])\n'
        assert bare_launches(old) == [(2, "'bash'")]

    def test_a_name_rebound_other_than_by_plain_assignment(self):
        old = (
            "def f():\n"
            '    p = resolve_program("x")\n'
            '    for p in ("bash",):\n        subprocess.run([p])\n'
        )
        assert bare_launches(old) == [(4, "cannot follow p")]
