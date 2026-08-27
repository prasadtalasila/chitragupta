#!/usr/bin/env python3
"""C1 and C2, scanned: function statements and module code lines.

[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md) states the two rules
and owns the reasoning; `code-standards-register.toml` holds today's
offenders; `tests/test_code_standards_scan.py` is what *enforces* them
and is still the authority. This module is the scan those three share,
and adding it changed no rule.

**Why it is here rather than in the test that used to define it**
(issue 431). `docs/HOOKS.md` requires a hook adapter to hold "no logic
anyone could want to run by hand", so the edit-time hook needs a
hand-runnable command underneath it. `tests/` is in
`scripts/release.py`'s `EXCLUDE_TOP_LEVEL` and `scripts/` is not, so a
shipped hook importing the rules from a test module would have worked in
this checkout and been broken in every release.

**Why `scripts/` and not `chitragupta/`.** Every other check a hook
shells out to is `python -m chitragupta.draft <verb>`, and this one
deliberately is not: `DEVELOPER-AGENTS.md` places developer tooling
here, `docs/ARCHITECTURE.md`'s artefact graph has no node for a
code-standards scan, and putting it in the package would ship a
developer tool inside what a drafting user installs. The rule that
matters -- the adapter holds no logic -- is kept; `docs/HOOKS.md` names
this exception the way it already names `hook_launchers.py`'s.

**Advisory, and it says so by exiting 0.** A crossing found here is a
report, not a verdict: the register's escape hatch is part of the
standard (`docs/CODE-STANDARDS.md`), and `docs/TECHNICAL-DEBT.md` is
emphatic that nothing goes red for an unpaid debt. The ratchet test is
what fails a build.

Stdlib only (ast, tomllib, argparse, json), like `release.py` and
`check_version_bump.py` beside it -- it runs under a bare `python3`.

Usage:
    python3 scripts/code_standards.py [PATH ...] [--json]
"""

import argparse
import ast
import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MAX_STATEMENTS = 25
MAX_CODE_LINES = 250

# C1 covers the tests, C2 does not -- see CODE-STANDARDS.md. In short: the
# tests already hold C1, so including them locks in a bar that is met; a
# test module's *length* tracks the surface of the module under test
# rather than a count of responsibilities, so C2 would push tests into new
# files for no reason other than the cap. `bench/` is out of scope for
# both, as the parser measurement harness.
STATEMENT_ROOTS = ("chitragupta", "scripts", "tests")
CODE_LINE_ROOTS = ("chitragupta", "scripts")

REGISTER_PATH = REPO_ROOT / "code-standards-register.toml"


def register() -> "tuple[dict, dict]":
    """`({function: statements}, {module: code_lines})` as recorded.

    Read from TOML rather than from a Python literal so that this module
    and the test can share one copy -- see the module docstring for why
    the copy could not live under `tests/`. The counts are real values
    rather than trailing comments because `tomllib` discards comments,
    which would have made the number invisible to every consumer this
    file exists to serve.
    """
    data = tomllib.loads(REGISTER_PATH.read_text(encoding="utf-8"))
    return (
        {entry["name"]: entry["statements"] for entry in data["c1"]},
        {entry["name"]: entry["code_lines"] for entry in data["c2"]},
    )


def statement_count(node) -> int:
    """Statements in a function body, not descending into nested definitions.

    A nested `def` is reached by `functions()` in its own right and checked
    on its own account, so counting its body here too would charge it to
    both and make an inner helper look like a way to fail its parent. The
    nested `def` or `class` statement itself still counts as one statement
    of the parent, which is correct -- declaring it is something the parent
    does.

    Stopping the descent is what makes that true at any depth. An earlier
    version subtracted a set of nested nodes from the walk instead, which
    got a nested *class* wrong: its methods were themselves nested
    definitions, so they survived the subtraction and were charged to the
    enclosing function. The parent's count then moved when a method was
    added to a class it merely declared.
    """
    count = 0
    pending = list(ast.iter_child_nodes(node))
    while pending:
        child = pending.pop()
        if isinstance(child, ast.stmt):
            count += 1
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        pending.extend(ast.iter_child_nodes(child))
    return count


def _definitions(node, prefix):
    """`(qualified_name, statement_count)` for every function under `node`.

    A class or an enclosing function extends the prefix; any other
    statement -- `if`, `try`, `with` -- leaves it alone, so a conditionally
    defined function is still found and still named for its real scope.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = prefix + child.name
            yield name, statement_count(child)
            yield from _definitions(child, name + ".")
        elif isinstance(child, ast.ClassDef):
            yield from _definitions(child, prefix + child.name + ".")
        else:
            yield from _definitions(child, prefix)


def functions(source: str) -> list:
    """Every function in `source` as `(qualified_name, statement_count)`.

    The caller prefixes the path. Nested and method definitions are
    yielded too -- each is a function someone has to read, and C1 is about
    reading.

    Qualified (`Class.method`, `outer.inner`), not the bare name, because
    the bare name is not unique within a file: `chitragupta/pdf_text.py`
    defined `__init__` twice, in `interrupt_guard` and `_AnnotatedStream`,
    before #361 split it into a package. `long_functions()` keys a dict on
    this, so a collision would drop one offender of a colliding pair --
    and, worse, would let a register entry for one `main` silently license
    a *different* `main` added to the same module later.
    """
    return list(_definitions(ast.parse(source), ""))


def code_lines(source: str) -> int:
    """Physical lines that are neither blank nor a whole-line comment.

    Deliberately counts docstrings, which are neither. Stripping them
    would need the rule to distinguish a module's prose header from a
    string constant, and the point of C2 is module size rather than a
    precise accounting of what fills it.
    """
    return sum(
        1 for line in source.splitlines() if line.strip() and not line.strip().startswith("#")
    )


def _python_files(roots) -> list:
    """Every `.py` file under `roots` in the working tree, path-sorted.

    The working tree, not `git ls-files`: an untracked scratch file under
    `chitragupta/` is scanned and can fail the suite. That is deliberate
    -- it is the state the code is actually in -- but it means a
    local-only failure naming a file you never committed is a stray file,
    not a bug here.

    `encoding="utf-8"` is passed on every read below. Without it
    `read_text()` uses the locale codec, which is cp1252 on the Windows CI
    leg, and these files are full of em dashes -- so the scan would die
    with a `UnicodeDecodeError` there while passing on Linux.
    """
    return sorted(path for root in roots for path in (REPO_ROOT / root).glob("**/*.py"))


def _relative(path: Path) -> str:
    """`path` as the register spells it, or as itself when it is outside
    the repository -- a hook is handed whatever was written, which in a
    scaffolded project or a temporary directory is not under this root."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def long_functions(roots) -> dict:
    """`{qualified_name: statement_count}` for everything over C1."""
    return _long_functions_in(_python_files(roots))


def long_files(roots) -> dict:
    """`{path: code_line_count}` for everything over C2."""
    return _long_files_in(_python_files(roots))


def _read(path: Path) -> "str | None":
    """`path`'s source, or None when there is nothing to scan.

    Absent and unparseable are one answer on purpose. A per-write hook is
    handed the path the harness says was written, and both states are
    ordinary there: a file deleted between the write and the check, and
    source caught mid-edit. Neither is this scanner's business, and
    neither may raise -- the caller is advisory.
    """
    if path.suffix != ".py" or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _long_functions_in(paths) -> dict:
    found = {}
    for path in paths:
        source = _read(path)
        if source is None:
            continue
        try:
            parsed = functions(source)
        except SyntaxError:
            continue
        for name, count in parsed:
            if count > MAX_STATEMENTS:
                found[f"{_relative(path)}::{name}"] = count
    return found


def _long_files_in(paths) -> dict:
    found = {}
    for path in paths:
        source = _read(path)
        if source is None:
            continue
        count = code_lines(source)
        if count > MAX_CODE_LINES:
            found[_relative(path)] = count
    return found


def findings(paths=None) -> list:
    """Every crossing in `paths` that the register does not already hold.

    `None` means the whole tree, at each rule's own roots -- the form the
    test and a bare CLI run use. A list of paths is the form the hook
    uses, and both rules are applied to all of them: scoping C2 away from
    `tests/` is a property of the *default* roots, not of a path someone
    named explicitly.

    Registered offenders are silent. Reporting them would fire on every
    edit to any of the twenty debts the register was written to record,
    which is noise indistinguishable from a real crossing -- and an
    advisory check that cries wolf is one people turn off.
    """
    c1_register, c2_register = register()
    if paths is None:
        c1, c2 = long_functions(STATEMENT_ROOTS), long_files(CODE_LINE_ROOTS)
    else:
        paths = [Path(p) for p in paths]
        c1, c2 = _long_functions_in(paths), _long_files_in(paths)
    found = [
        {"rule": "C1", "name": name, "count": count, "limit": MAX_STATEMENTS}
        for name, count in sorted(c1.items())
        if name not in c1_register
    ]
    found += [
        {"rule": "C2", "name": name, "count": count, "limit": MAX_CODE_LINES}
        for name, count in sorted(c2.items())
        if name not in c2_register
    ]
    return found


def format_findings(found: list) -> str:
    """The human form. One line per finding, and a sentence when there
    are none -- silence from a tool you ran by hand is indistinguishable
    from a tool that did not run."""
    if not found:
        return "no findings: nothing over C1 or C2 that the register does not hold."
    lines = []
    for finding in found:
        noun = "statements" if finding["rule"] == "C1" else "code lines"
        lines.append(
            f"{finding['rule']}  {finding['name']}  "
            f"{finding['count']} {noun} (limit {finding['limit']})"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    """Always exits 0. See the module docstring: this reports, and
    `tests/test_code_standards_scan.py` is what fails a build."""
    parser = argparse.ArgumentParser(
        prog="python3 scripts/code_standards.py",
        description="Report functions over C1 and modules over C2 that the register does not hold.",
    )
    parser.add_argument("paths", nargs="*", help="Files to check (default: the whole tree)")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON")
    args = parser.parse_args(argv)

    found = findings(args.paths or None)
    if args.json:
        print(json.dumps({"findings": found}, indent=2))
    else:
        print(format_findings(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
