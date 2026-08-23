"""Detector library for `test_unversioned_data_scan.py` (#358).

Split out from the test module so both stay under 250 lines -- the test
module's own docstring carries the full reasoning for what counts as a
risky read, what a pin looks like, and why the register holds one entry.
This file is the AST walk that reasoning compiles to.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Keyed `path::Class` (every test method in that class is exempt) or
# `path::Class.method` / `path::function` (only that one is). See
# test_unversioned_data_scan.py's module docstring for why
# TestRealConfigToml is class-granularity.
REGISTER = {
    "tests/test_config.py::TestRealConfigToml": (
        "Sanity-checks the constants config.py actually computed from this "
        "developer's real config.toml at import time -- the class's whole "
        "point, stated in its own docstring, and unlike 4.1's two original "
        "cases it never claims to test a default."
    ),
}


def _relative(path):
    return path.relative_to(REPO_ROOT).as_posix()


def _references_tmp_path(node):
    """True if the pytest `tmp_path` fixture appears anywhere in this
    expression -- the discriminator between an isolated read and an
    ambient one."""
    return any(isinstance(n, ast.Name) and n.id == "tmp_path" for n in ast.walk(node))


def _tmp_path_aliases(func_node):
    """Local names assigned a `tmp_path`-derived value, one hop deep --
    e.g. `empty_toml = tmp_path / "config.toml"`."""
    aliases = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign) and _references_tmp_path(node.value):
            aliases.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return aliases


def _resolves_to_tmp_path(value_node, aliases):
    """`value_node` is `tmp_path`, an alias of it, or `str()` of either."""
    if _references_tmp_path(value_node):
        return True
    if isinstance(value_node, ast.Name):
        return value_node.id in aliases
    if (
        isinstance(value_node, ast.Call)
        and isinstance(value_node.func, ast.Name)
        and value_node.func.id == "str"
        and len(value_node.args) == 1
    ):
        return _resolves_to_tmp_path(value_node.args[0], aliases)
    return False


def _is_monkeypatch_call(node, method):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "monkeypatch"
    )


def _string_arg(node, index):
    if len(node.args) > index and isinstance(node.args[index], ast.Constant):
        return node.args[index].value
    return None


def _pins_config_path_directly(func_node):
    """`monkeypatch.setenv("CONFIG_PATH", ...)` or `.setattr(config,
    "CONFIG_PATH", ...)`, value resolving to a `tmp_path` file, anywhere
    in this function's own body."""
    aliases = _tmp_path_aliases(func_node)
    for node in ast.walk(func_node):
        if _is_monkeypatch_call(node, "setenv") and _string_arg(node, 0) == "CONFIG_PATH":
            if _resolves_to_tmp_path(node.args[1], aliases):
                return True
        if _is_monkeypatch_call(node, "setattr") and _string_arg(node, 1) == "CONFIG_PATH":
            if _resolves_to_tmp_path(node.args[2], aliases):
                return True
    return False


def fixture_defs(tree):
    """`{name: FunctionDef}` for every `@pytest.fixture`-decorated
    function or method in this module."""
    defs = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr == "fixture":
                defs[node.name] = node
    return defs


def _requested_fixture_names(func_node):
    return [a.arg for a in func_node.args.args if a.arg != "self"]


def _pins_config_path(func_node, fixtures, seen=None):
    """Recurses into requested fixtures defined in the same module, so a
    pin factored into a fixture still counts."""
    seen = seen if seen is not None else set()
    if func_node.name in seen:
        return False
    seen.add(func_node.name)
    if _pins_config_path_directly(func_node):
        return True
    return any(
        name in fixtures and _pins_config_path(fixtures[name], fixtures, seen)
        for name in _requested_fixture_names(func_node)
    )


def _is_bib_literal_join(node):
    """`<expr> / "papers" / "bibliography.bib"` -- the real bib path,
    constructed by hand rather than via `config.BIB_FILE_PATH`."""
    return (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Div)
        and isinstance(node.right, ast.Constant)
        and node.right.value == "bibliography.bib"
        and isinstance(node.left, ast.BinOp)
        and isinstance(node.left.op, ast.Div)
        and isinstance(node.left.right, ast.Constant)
        and node.left.right.value == "papers"
    )


def _is_config_path_read(node):
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "CONFIG_PATH"
        and isinstance(node.value, ast.Name)
        and node.value.id == "config"
    )


def _is_reload_config_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "reload"
        and any(isinstance(a, ast.Name) and a.id == "config" for a in node.args)
    )


def _is_home_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "home"
        and not node.args
    )


def _has_ambient_config_trigger(func_node):
    """CONFIG_PATH-driven reads -- safe once CONFIG_PATH is pinned to a
    tmp_path file, since everything they compute flows through it."""
    return any(_is_config_path_read(n) or _is_reload_config_call(n) for n in ast.walk(func_node))


def _has_unconditional_trigger(func_node):
    """Reads no CONFIG_PATH pin makes safe: the real bib path built by
    hand, and `Path.home()` -- a different per-host root."""
    return any(_is_bib_literal_join(n) or _is_home_call(n) for n in ast.walk(func_node))


def _has_assert(func_node):
    return any(isinstance(n, ast.Assert) for n in ast.walk(func_node))


def offense_reason(func_node, fixtures):
    """Why this test function reads un-versioned data, or None."""
    if not _has_assert(func_node):
        return None
    if _has_unconditional_trigger(func_node):
        return "constructs the real papers/bibliography.bib path, or calls Path.home(), directly"
    if _has_ambient_config_trigger(func_node) and not _pins_config_path(func_node, fixtures):
        return "reads config.toml via an unpinned CONFIG_PATH (attribute or reload)"
    return None


def test_functions(tree):
    """`(qualified_name, class_name_or_None, FunctionDef)` for every
    `def test_*`/`async def test_*`, one level of class nesting deep."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            yield node.name, None, node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and child.name.startswith("test_"):
                    yield f"{node.name}.{child.name}", node.name, child


def python_test_files():
    return sorted((REPO_ROOT / "tests").glob("**/*.py"))


def unversioned_reads(paths):
    """`{"path::qualified_name": reason}` for every offender not covered
    by REGISTER."""
    found = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fixtures = fixture_defs(tree)
        rel = _relative(path)
        for qualified, class_name, func_node in test_functions(tree):
            if f"{rel}::{qualified}" in REGISTER or (
                class_name and f"{rel}::{class_name}" in REGISTER
            ):
                continue
            reason = offense_reason(func_node, fixtures)
            if reason:
                found[f"{rel}::{qualified}"] = reason
    return found
