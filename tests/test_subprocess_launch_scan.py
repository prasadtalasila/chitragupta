"""Every launch of the package under test goes through `run_python` (#867).

A test that runs `python -m chitragupta...` in a child imports whichever
chitragupta that child finds first. With the repository root as cwd that
is this checkout, because `-m` puts the cwd on sys.path; with any other
cwd it is whatever is installed, or nothing. One helper in conftest sets
PYTHONPATH explicitly instead, and this scan is what keeps a new test
from going back to launching the interpreter itself -- a launch that
happens to work from the repository root gives no sign it depends on it.

What counts as a launch of the package: a `subprocess` call (however
`subprocess` or its `run` was imported) whose argv -- a list or tuple
literal, or a name bound to one in the same scope -- begins with an
interpreter (`sys.executable`, a name or attribute with `python` in it,
`shutil.which("python3")`) and carries `-m chitragupta...`, a `-c`
program, or a `*argv` that could be either. Module- and class-level
launches count as well as those in functions. Hook scripts and
`scripts/*.py` launched by path are not the package and are not matched;
nor are git, node or kpsewhich. An argv assembled any other way -- by
concatenation, or in another function -- is not seen.
"""

import ast
import os
from pathlib import Path

from tests.conftest import REPO_ROOT, run_python

TESTS = Path(__file__).resolve().parent

_WHERE = "import chitragupta, os; print(os.path.dirname(os.path.dirname(chitragupta.__file__)))"


class TestRunPython:
    def test_a_child_outside_the_repository_imports_this_checkout(self, system_python, tmp_path):
        """The seam #867 names. A bare interpreter, a minimal environment
        and a cwd that is not the repository root: nothing but the
        helper's PYTHONPATH can find chitragupta, and it must find this
        one rather than none."""
        env = {"PATH": os.environ.get("PATH", "")}
        result = run_python("-c", _WHERE, python=system_python, cwd=tmp_path, env=env)
        assert result.returncode == 0, result.stderr
        assert Path(result.stdout.strip()) == REPO_ROOT

    def test_a_callers_own_pythonpath_stays_ahead_of_the_checkout(self, tmp_path):
        """tests/test_tokens.py imports an edited copy of the package from
        tmp_path; prepending the checkout would test the original.

        The copy sits in `lib/`, not in the cwd: `-c` puts the cwd first
        on sys.path, ahead of PYTHONPATH, so a copy there would win
        whatever order the helper chose and the test could not fail."""
        lib = tmp_path / "lib"
        (lib / "chitragupta").mkdir(parents=True)
        (lib / "chitragupta" / "__init__.py").write_text("", encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(lib)}
        result = run_python("-c", _WHERE, cwd=tmp_path, env=env)
        assert result.returncode == 0, result.stderr
        assert Path(result.stdout.strip()) == lib

    def test_coverage_follows_the_child_only_from_the_root(self, tmp_path):
        """From any other cwd a child's coverage finds no config, records
        statement-only data, and kills the session at combine time after
        every test passed -- which is what this helper's first version
        did to a full run."""
        probe = "import os; print(sorted(k for k in os.environ if k.startswith('COV_CORE')))"
        # A datafile of its own, so the root-side child's data never
        # reaches the parent's combine.
        datafile = str(tmp_path / ".coverage")
        env = {**os.environ, "COV_CORE_SOURCE": ":", "COV_CORE_DATAFILE": datafile}
        elsewhere = run_python("-c", probe, cwd=tmp_path, env=env)
        at_root = run_python("-c", probe, env=env)
        assert elsewhere.stdout.strip() == "[]"
        assert "COV_CORE_SOURCE" in at_root.stdout


# `path::function` -> why that launch must control the child's import
# path itself, which is the one thing run_python exists to take away.
EXEMPT = {
    "test_citation_gate_hook.py::test_interpreter_that_cannot_import_chitragupta_is_named_as_the_fault": (
        "Probes whether a bare interpreter can import chitragupta *without* "
        "this checkout on its path; run_python would put it there and make "
        "the probe pass for the wrong reason."
    ),
}

_LAUNCHERS = {"run", "Popen", "call", "check_call", "check_output"}


def _is_interpreter(node) -> bool:
    """`sys.executable`, `python or sys.executable`, a name or attribute
    with `python` in it (`system_python`, `self.python`), or
    `shutil.which("python3")`."""
    if isinstance(node, ast.BoolOp):
        return any(_is_interpreter(value) for value in node.values)
    if isinstance(node, ast.Call):
        return any(isinstance(a, ast.Constant) and "python" in str(a.value) for a in node.args)
    if isinstance(node, ast.Attribute):
        is_sys = node.attr == "executable" and getattr(node.value, "id", None) == "sys"
        return is_sys or "python" in node.attr
    return isinstance(node, ast.Name) and "python" in node.id


def _launches_the_package(elements: list) -> bool:
    if not elements or not _is_interpreter(elements[0]):
        return False
    # `[python, *argv]` is a launcher that takes its flags from the caller;
    # `[python, str(script), *args]` runs a script by path, which is not
    # the package, so only a splat in the first argument position counts.
    if len(elements) > 1 and isinstance(elements[1], ast.Starred):
        return True
    for i, element in enumerate(elements[1:], start=1):
        value = element.value if isinstance(element, ast.Constant) else None
        if value == "-c" or str(value).startswith("-mchitragupta"):
            return True
        if value == "-m" and i + 1 < len(elements):
            target = elements[i + 1]
            # A module named by a variable or an f-string could be the
            # package, so only a literal naming something else is let go.
            if not isinstance(target, ast.Constant):
                return True
            return str(target.value).startswith("chitragupta")
    return False


def _subprocess_names(tree) -> "tuple[set, set]":
    """The names `subprocess` is reachable under in this module, and the
    launch functions imported from it bare (`from subprocess import run`)."""
    modules, functions = {"subprocess"}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name == "subprocess"}
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            functions |= {a.asname or a.name for a in node.names if a.name in _LAUNCHERS}
    return modules, functions


def _is_launch_call(node, modules, functions) -> bool:
    if not (isinstance(node, ast.Call) and node.args):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in functions
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _LAUNCHERS
        and getattr(func.value, "id", None) in modules
    )


def _argv_elements(arg, scope) -> "list | None":
    """The argv's elements: a list or tuple literal, or a name bound to
    one by an assignment in the same scope (`cmd = [...]; run(cmd)`)."""
    if isinstance(arg, (ast.List, ast.Tuple)):
        return arg.elts
    if isinstance(arg, ast.Name):
        for node in ast.walk(scope):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == arg.id for t in node.targets
            ):
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    return node.value.elts
    return None


def _scopes(tree):
    """(name, node) for the module and every function and class, each
    scope yielding only the statements directly its own."""
    yield "<module>", tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node


def direct_launches(source: str) -> "list[tuple[str, int]]":
    """(innermost enclosing function or class, line) of each package
    launch not made through run_python; `<module>` at module level."""
    tree = ast.parse(source)
    modules, functions = _subprocess_names(tree)
    found = {}
    for name, scope in _scopes(tree):
        for node in ast.walk(scope):
            if not _is_launch_call(node, modules, functions):
                continue
            elements = _argv_elements(node.args[0], scope)
            if elements is not None and _launches_the_package(elements):
                found[node.lineno] = name  # later, inner scopes overwrite outer ones
    return sorted(((name, line) for line, name in found.items()), key=lambda item: item[1])


def test_every_package_launch_goes_through_run_python():
    offenders = []
    for path in sorted(TESTS.glob("*.py")):
        if path.name == "conftest.py":  # run_python itself
            continue
        for function, line in direct_launches(path.read_text(encoding="utf-8")):
            if f"{path.name}::{function}" not in EXEMPT:
                offenders.append(f"{path.name}:{line} in {function}()")
    assert not offenders, (
        "launch the package through tests.conftest.run_python, which puts "
        "this checkout on the child's PYTHONPATH:\n  " + "\n  ".join(offenders)
    )


def test_every_exemption_still_names_a_direct_launch():
    """A register entry whose launch has gone is a hole a new one could
    reuse without anyone deciding it should."""
    for key in EXEMPT:
        filename, function = key.split("::")
        launches = direct_launches((TESTS / filename).read_text(encoding="utf-8"))
        assert function in {name for name, _line in launches}, f"stale exemption: {key}"


class TestTheDetectorSeesTheShapesItWasWrittenFor:
    """Fed the real pre-#867 launches, verbatim, so a detector that
    reports clean is shown not to be blind."""

    def test_the_entrypoint_modules_run_helper(self):
        old = (
            "def _run(*argv):\n"
            "    return subprocess.run(\n"
            "        [sys.executable, *argv],\n"
            "        cwd=str(REPO_ROOT),\n"
            "        capture_output=True,\n"
            "        text=True,\n"
            "    )\n"
        )
        assert direct_launches(old) == [("_run", 2)]

    def test_a_dash_m_launch_and_a_system_python_one(self):
        old = (
            "def test_a(self):\n"
            '    subprocess.run([sys.executable, "-m", "chitragupta.corpus", "sync", "--help"])\n'
            "def test_b(self, system_python):\n"
            '    subprocess.run([system_python, "-m", "chitragupta.draft", "gate", str(d)])\n'
            "def test_c(self, layer):\n"
            '    subprocess.run([sys.executable, "-m", f"chitragupta.{layer}", "--help"])\n'
        )
        assert [name for name, _line in direct_launches(old)] == ["test_a", "test_b", "test_c"]

    def test_a_dash_c_program(self):
        old = 'def test_d(self):\n    subprocess.run([sys.executable, "-c", program], env=env)\n'
        assert direct_launches(old) == [("test_d", 2)]

    def test_what_is_not_the_package_is_left_alone(self):
        source = (
            "def test_e(self):\n"
            '    subprocess.run(["git", "init", "-q", "."])\n'
            "    subprocess.run([sys.executable, str(self.hook)])\n"
            '    subprocess.run(["kpsewhich", "tikz.sty"])\n'
            '    subprocess.run([sys.executable, "-m", "pip", "--version"])\n'
            '    run_python("-m", "chitragupta.corpus", "sync", "--help")\n'
            # tests/test_code_standards.py: a script by path, then its args.
            '    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "x.py"), *args])\n'
        )
        assert direct_launches(source) == []

    def test_a_module_named_by_a_variable(self):
        """tests/test_cli_help_is_short.py's shape: the target is only
        known at run time, so it has to be assumed to be the package."""
        old = (
            "def _help(module_path):\n"
            '    return subprocess.run([sys.executable, "-m", module_path, "--help"])\n'
        )
        assert direct_launches(old) == [("_help", 2)]

    def test_an_argv_bound_to_a_name_first(self):
        old = (
            "def test_f(self):\n"
            '    cmd = [sys.executable, "-m", "chitragupta.draft", "gate"]\n'
            "    subprocess.run(cmd, capture_output=True)\n"
        )
        assert direct_launches(old) == [("test_f", 3)]

    def test_a_tuple_argv_and_a_fused_dash_m(self):
        old = 'def test_g(self):\n    subprocess.run((sys.executable, "-mchitragupta.corpus"))\n'
        assert direct_launches(old) == [("test_g", 2)]

    def test_an_aliased_module_or_a_bare_imported_run(self):
        old = (
            "import subprocess as sp\n"
            "from subprocess import run\n"
            "def test_h(self):\n"
            '    sp.run([sys.executable, "-m", "chitragupta.corpus"])\n'
            '    run([sys.executable, "-m", "chitragupta.review"])\n'
        )
        assert direct_launches(old) == [("test_h", 4), ("test_h", 5)]

    def test_an_interpreter_found_by_which_or_held_on_self(self):
        old = (
            "class TestI:\n"
            "    def test_i(self):\n"
            '        subprocess.run([shutil.which("python3"), "-m", "chitragupta"])\n'
            '        subprocess.run([self.python, "-c", "import chitragupta"])\n'
        )
        assert direct_launches(old) == [("test_i", 3), ("test_i", 4)]

    def test_a_launch_outside_any_function(self):
        old = 'PROBE = subprocess.run([sys.executable, "-c", "import chitragupta"])\n'
        assert direct_launches(old) == [("<module>", 1)]
