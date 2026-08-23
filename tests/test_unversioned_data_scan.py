"""Tests that assert against un-versioned, per-host data -- the general
rule 4.1 fixed twice by hand and never taught to a detector, until #358.

`config.toml` and `papers/bibliography.bib` are gitignored, differ on
every machine, and CI never sees either -- CI's `config.toml` is always
`config.toml.example`, copied fresh (`test_ci_creates_config_toml_from_the_tracked_example`
below pins that step so this reasoning cannot go stale silently). A test
whose truth depends on either file therefore passes or fails on whose
checkout it is, invisibly to CI, which is exactly the failure class two
tests in this suite hit before being fixed by hand (see git history of
`tests/test_config.py::test_parser_ocr_defaults_off` and
`tests/test_feature_workflows.py::TestRealBibliographySmoke`).

Two distinct risky reads, not one, and they get different treatment:

**Ambient config-selection reads** -- `config.CONFIG_PATH` and
`importlib.reload(config)` -- are only risky when nothing pins *which*
file the reload consults. A test that pins `CONFIG_PATH` to a
`tmp_path`-rooted file (directly, or via a `@pytest.fixture` defined in
the same module) has made the read deterministic, so it is exempt without
needing a register entry. `chitragupta.config._get()` layers an env-var
override on top of the TOML for every value it computes, so a test that
also sets the matching env var is safe regardless -- but that reasoning
lives in `TestModuleReloadWithEnvOverrides._empty_config_toml`'s
docstring, not here, and every test in that class uses the fixture.

**Reads no CONFIG_PATH pin makes safe** get no exemption at all: a
direct, hardcoded construction of the real bib path
(`config.PROJECT_ROOT / "papers" / "bibliography.bib"`), which never goes
through `_get()`, and `Path.home()`, a per-host root CONFIG_PATH does not
touch. Both are *always* flagged where they appear in a test's own body.
`tests/conftest.py::real_bibliography_path()` exists so a test that
genuinely wants the real file -- `TestRealBibliographySmoke`, by design
-- calls a named, documented helper instead of writing the literal
inline, which is what keeps it off the register below.

**The register** is a ratchet, same idiom as
`tests/test_code_standards_scan.py`'s: a frozen list of the deliberate
exceptions, each with a stated reason, that only shrinks. It holds one
entry: `TestRealConfigToml`, keyed at class granularity (no `.method`
suffix) because its docstring's claim -- "constants as actually computed
... at real import time" -- is about the whole class, not the one method
that happens to construct the bib path literally.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Keyed `path::Class` (every test method in that class is exempt) or
# `path::Class.method` / `path::function` (only that one is). See the
# module docstring for why TestRealConfigToml is class-granularity.
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
    """True if `tmp_path` (the pytest fixture) appears anywhere in this
    expression -- the discriminator between a deliberately isolated read
    and an ambient one."""
    return any(
        isinstance(n, ast.Name) and n.id == "tmp_path" for n in ast.walk(node)
    )


def _tmp_path_aliases(func_node):
    """Local names assigned a `tmp_path`-derived value in this function,
    e.g. `empty_toml = tmp_path / "config.toml"`.

    One hop only -- `monkeypatch.setenv("CONFIG_PATH", str(empty_toml))`
    is the only indirection this suite's reload tests use, and a deeper
    chase would be solving a problem this codebase doesn't have yet.
    """
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
    """`monkeypatch.setenv("CONFIG_PATH", ...)` or
    `monkeypatch.setattr(config, "CONFIG_PATH", ...)`, with the value
    resolving to a `tmp_path`-rooted file, anywhere in this function's own
    body."""
    aliases = _tmp_path_aliases(func_node)
    for node in ast.walk(func_node):
        if _is_monkeypatch_call(node, "setenv") and _string_arg(node, 0) == "CONFIG_PATH":
            if _resolves_to_tmp_path(node.args[1], aliases):
                return True
        if _is_monkeypatch_call(node, "setattr") and _string_arg(node, 1) == "CONFIG_PATH":
            if _resolves_to_tmp_path(node.args[2], aliases):
                return True
    return False


def _fixture_defs(tree):
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
    pin factored out (as `_empty_config_toml` is) still counts."""
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
    constructed by hand rather than via `config.BIB_FILE_PATH`'s own
    env-var-aware lookup."""
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
    """CONFIG_PATH-driven reads -- safe once CONFIG_PATH itself is pinned
    to a tmp_path file, because everything they compute flows through
    that one file."""
    return any(
        _is_config_path_read(n) or _is_reload_config_call(n) for n in ast.walk(func_node)
    )


def _has_unconditional_trigger(func_node):
    """Reads no CONFIG_PATH pin makes safe: the real bib path constructed
    by hand (never goes through CONFIG_PATH/`_get()` at all), and
    `Path.home()` (a different per-host root CONFIG_PATH does not touch)."""
    return any(
        _is_bib_literal_join(n) or _is_home_call(n) for n in ast.walk(func_node)
    )


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


def _test_functions(tree):
    """`(qualified_name, class_name_or_None, FunctionDef)` for every
    `def test_*`/`async def test_*` in this module, one level of class
    nesting deep -- what this suite actually uses."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node.name, None, node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                    yield f"{node.name}.{child.name}", node.name, child


def _python_test_files():
    return sorted((REPO_ROOT / "tests").glob("**/*.py"))


def unversioned_reads(paths):
    """`{"path::qualified_name": reason}` for every offender not covered
    by REGISTER."""
    found = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fixtures = _fixture_defs(tree)
        rel = _relative(path)
        for qualified, class_name, func_node in _test_functions(tree):
            if f"{rel}::{qualified}" in REGISTER or (class_name and f"{rel}::{class_name}" in REGISTER):
                continue
            reason = offense_reason(func_node, fixtures)
            if reason:
                found[f"{rel}::{qualified}"] = reason
    return found


def test_no_new_test_reads_unversioned_data_outside_the_register():
    found = unversioned_reads(_python_test_files())
    assert not found, (
        "Tests reading un-versioned, per-host data (config.toml / "
        "papers/bibliography.bib) with no pin and no register entry:"
        + "".join(f"\n  {name} -- {reason}" for name, reason in sorted(found.items()))
        + "\n\nPin CONFIG_PATH to a tmp_path file (see "
        "TestModuleReloadWithEnvOverrides._empty_config_toml), route a real-file "
        "read through tests/conftest.py::real_bibliography_path(), or -- if "
        "genuinely deliberate -- add it to REGISTER in this file and say why."
    )


def test_the_register_names_only_classes_and_paths_that_still_exist():
    """A register key is `Class` (the whole class), `Class.method`, or a
    bare `function` -- the three shapes the module docstring and
    `unversioned_reads()`'s lookup both promise."""
    for key in REGISTER:
        path, qualified = key.split("::")
        assert (REPO_ROOT / path).exists(), f"register entry for a file that no longer exists: {key}"
        tree = ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"))
        classes = {c.name: c for c in ast.iter_child_nodes(tree) if isinstance(c, ast.ClassDef)}
        methods = {
            f"{c}.{m.name}"
            for c, n in classes.items()
            for m in n.body
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        functions = {
            n.name for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        known = set(classes) | methods | functions
        assert qualified in known, f"register entry names no class, method or function in {path}: {key}"


def test_the_register_holds_no_entry_that_is_already_fixed():
    """The ratchet's other half: a class kept in the register after it
    stops tripping the scan would silently relicense the pattern."""
    still_offends = set()
    for path in _python_test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fixtures = _fixture_defs(tree)
        rel = _relative(path)
        for qualified, class_name, func_node in _test_functions(tree):
            if offense_reason(func_node, fixtures):
                still_offends.add(f"{rel}::{qualified}")
                if class_name:
                    still_offends.add(f"{rel}::{class_name}")
    fixed = sorted(key for key in REGISTER if key not in still_offends)
    assert not fixed, f"these no longer offend -- delete from REGISTER: {fixed}"


def test_ci_creates_config_toml_from_the_tracked_example():
    """The reason 4.1's first bug (config.toml read unpinned) never showed
    up in CI: CI's config.toml is always the tracked example, copied
    fresh, never a developer's own edited file. If this step is ever
    removed, every "CI can't see this" claim above stops being true."""
    ci_yml = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "cp config.toml.example config.toml" in ci_yml


def test_the_scan_reaches_the_source_tree():
    scanned = {p.name for p in _python_test_files()}
    assert "test_config.py" in scanned
    assert "test_feature_workflows.py" in scanned
    assert "test_unversioned_data_scan.py" in scanned


def test_this_scanner_obeys_its_own_statement_limit():
    """The check that would be embarrassing to fail -- see
    test_code_standards_scan.py's twin of this test."""
    import tests.test_code_standards_scan as code_standards_scan

    source = Path(__file__).read_text(encoding="utf-8")
    over = [
        name
        for name, count in code_standards_scan.functions(source)
        if count > code_standards_scan.MAX_STATEMENTS
    ]
    assert not over, over


class _Snippets:
    """Synthetic test-function source used by the unit tests below --
    reconstructions of the two fixed bugs (git history, pre-#161), plus
    the shapes that must NOT be flagged."""

    ORIGINAL_PARSER_OCR_BUG = '''
def test_parser_ocr_defaults_off(self, monkeypatch):
    monkeypatch.delenv("PARSER_OCR", raising=False)
    importlib.reload(config)
    assert config.PARSER_OCR is False
'''

    ORIGINAL_BIB_SMOKE_BUG = '''
def test_real_bib_file_parses_without_error(self, isolated_config, monkeypatch):
    real_bib = config.PROJECT_ROOT / "papers" / "bibliography.bib"
    monkeypatch.setattr(config, "BIB_FILE_PATH", real_bib)
    refs = bib_reader.read_library()
    assert len(refs) == 646
'''

    PINNED_RELOAD = '''
def test_parser_ocr_defaults_off(self, monkeypatch, tmp_path):
    empty_toml = tmp_path / "config.toml"
    empty_toml.write_text("", encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(empty_toml))
    monkeypatch.delenv("PARSER_OCR", raising=False)
    importlib.reload(config)
    assert config.PARSER_OCR is False
'''

    PINNED_VIA_FIXTURE = '''
class TestModuleReloadWithEnvOverrides:
    @pytest.fixture
    def _empty_config_toml(self, tmp_path, monkeypatch):
        empty_toml = tmp_path / "config.toml"
        empty_toml.write_text("", encoding="utf-8")
        monkeypatch.setenv("CONFIG_PATH", str(empty_toml))

    def test_bib_file_env_override(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("BIB_FILE", "/tmp/other.bib")
        importlib.reload(config)
        assert config.BIB_FILE_PATH == config.PROJECT_ROOT / "/tmp/other.bib"
'''

    HOME_CALL = '''
def test_something(self):
    p = Path.home()
    assert p.exists()
'''

    HOME_CALL_EVEN_IF_CONFIG_PATH_PINNED = '''
def test_something(self, monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "config.toml"))
    p = Path.home()
    assert p.exists()
'''

    READ_WITH_NO_ASSERT = '''
def test_reload_does_not_raise(self):
    importlib.reload(config)
'''

    BIB_LITERAL_EVEN_IF_PINNED = '''
def test_real_bib_smoke(self, isolated_config, monkeypatch):
    real_bib = config.PROJECT_ROOT / "papers" / "bibliography.bib"
    monkeypatch.setattr(config, "CONFIG_PATH", real_bib)
    refs = bib_reader.read_library()
    assert len(refs) == 2
'''


def _snippet_offense(source, fixtures=None):
    tree = ast.parse(source)
    _, _, func_node = next(_test_functions(tree))
    return offense_reason(func_node, fixtures or _fixture_defs(tree))


def test_the_original_parser_ocr_bug_is_flagged():
    assert _snippet_offense(_Snippets.ORIGINAL_PARSER_OCR_BUG)


def test_the_original_bib_smoke_bug_is_flagged():
    assert _snippet_offense(_Snippets.ORIGINAL_BIB_SMOKE_BUG)


def test_a_reload_pinned_to_tmp_path_is_not_flagged():
    assert _snippet_offense(_Snippets.PINNED_RELOAD) is None


def test_a_pin_factored_into_a_same_module_fixture_is_still_honoured():
    tree = ast.parse(_Snippets.PINNED_VIA_FIXTURE)
    fixtures = _fixture_defs(tree)
    _, _, func_node = next(
        (q, c, n) for q, c, n in _test_functions(tree) if q.endswith("test_bib_file_env_override")
    )
    assert offense_reason(func_node, fixtures) is None


def test_a_bare_home_call_is_flagged():
    assert _snippet_offense(_Snippets.HOME_CALL)


def test_a_read_with_no_assert_is_not_flagged():
    assert _snippet_offense(_Snippets.READ_WITH_NO_ASSERT) is None


def test_the_bib_literal_join_is_flagged_even_when_pinned():
    """The discriminator from the ambient-config triggers: pinning
    CONFIG_PATH does not make constructing the real bib path by hand
    safe, because that construction never goes through CONFIG_PATH at
    all."""
    assert _snippet_offense(_Snippets.BIB_LITERAL_EVEN_IF_PINNED)


def test_a_home_call_is_flagged_even_when_config_path_is_pinned():
    """Same discriminator as the bib literal: `Path.home()` is a
    different per-host root that pinning CONFIG_PATH does nothing to."""
    assert _snippet_offense(_Snippets.HOME_CALL_EVEN_IF_CONFIG_PATH_PINNED)
