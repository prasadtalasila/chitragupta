"""Tests that assert against un-versioned, per-host data -- the general
rule 4.1 fixed twice by hand and never taught to a detector, until #358.

`config.toml` and `papers/bibliography.bib` are gitignored and differ on
every machine; CI's `config.toml` is always `config.toml.example`, copied
fresh (`test_ci_creates_config_toml_from_the_tracked_example` pins that
step). A test whose truth depends on either file passes or fails on
whose checkout it is, invisibly to CI -- what
`tests/test_config.py::test_parser_ocr_defaults_off` and
`TestRealBibliographySmoke` (`tests/test_feature_workflows.py`) hit
before being fixed by hand (see their git history).

`tests/unversioned_data_scan.py` (split out to keep both files under 250
lines) implements two distinct risky reads, treated differently:

**Ambient config-selection reads** (`config.CONFIG_PATH`,
`importlib.reload(config)`) are risky only while nothing pins *which*
file the reload consults. Pinning `CONFIG_PATH` to a `tmp_path`-rooted
file -- directly, or via a same-module `@pytest.fixture` -- makes the
read deterministic and exempt, no register entry needed. An env-var
override on top of the TOML is also safe regardless of the pin; that
reasoning lives in `TestModuleReloadWithEnvOverrides._empty_config_toml`.

**Reads no CONFIG_PATH pin makes safe** get no exemption: a hardcoded
`config.PROJECT_ROOT / "papers" / "bibliography.bib"` join (never goes
through `_get()`) and `Path.home()` (a different per-host root) are
*always* flagged. `tests/conftest.py::real_bibliography_path()` lets
`TestRealBibliographySmoke`, which genuinely wants the real file, call a
named helper instead -- keeping it off the register below.

**The register** (`unversioned_data_scan.REGISTER`) is a ratchet, same
idiom as `test_code_standards_scan.py`'s: deliberate exceptions, each
with a stated reason, that only shrinks. One entry, `TestRealConfigToml`,
keyed at class granularity (no `.method`) because its docstring's claim
-- "constants as actually computed ... at real import time" -- is about
the whole class, not the one method that constructs the bib path.
"""

import ast
from pathlib import Path

from tests import unversioned_data_scan as scan


def test_no_new_test_reads_unversioned_data_outside_the_register():
    found = scan.unversioned_reads(scan.python_test_files())
    assert not found, (
        "Tests reading un-versioned, per-host data (config.toml / "
        "papers/bibliography.bib) with no pin and no register entry:"
        + "".join(f"\n  {name} -- {reason}" for name, reason in sorted(found.items()))
        + "\n\nPin CONFIG_PATH to a tmp_path file (see "
        "TestModuleReloadWithEnvOverrides._empty_config_toml), route a real-file "
        "read through tests/conftest.py::real_bibliography_path(), or -- if "
        "genuinely deliberate -- add it to REGISTER in tests/unversioned_data_scan.py "
        "and say why."
    )


def test_the_register_names_only_classes_and_paths_that_still_exist():
    """A register key is `Class` (the whole class), `Class.method`, or a
    bare `function` -- the three shapes the module docstring and
    `unversioned_reads()`'s lookup both promise."""
    for key in scan.REGISTER:
        path, qualified = key.split("::")
        assert (scan.REPO_ROOT / path).exists(), f"register entry for a file that no longer exists: {key}"
        tree = ast.parse((scan.REPO_ROOT / path).read_text(encoding="utf-8"))
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
    for path in scan.python_test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fixtures = scan.fixture_defs(tree)
        rel = path.relative_to(scan.REPO_ROOT).as_posix()
        for qualified, class_name, func_node in scan.test_functions(tree):
            if scan.offense_reason(func_node, fixtures):
                still_offends.add(f"{rel}::{qualified}")
                if class_name:
                    still_offends.add(f"{rel}::{class_name}")
    fixed = sorted(key for key in scan.REGISTER if key not in still_offends)
    assert not fixed, f"these no longer offend -- delete from REGISTER: {fixed}"


def test_ci_creates_config_toml_from_the_tracked_example():
    """The reason 4.1's first bug (config.toml read unpinned) never showed
    up in CI: CI's config.toml is always the tracked example, copied
    fresh, never a developer's own edited file. If this step is ever
    removed, every "CI can't see this" claim above stops being true."""
    ci_yml = (scan.REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "cp config.toml.example config.toml" in ci_yml


def test_the_scan_reaches_the_source_tree():
    scanned = {p.name for p in scan.python_test_files()}
    assert "test_config.py" in scanned
    assert "test_feature_workflows.py" in scanned
    assert "test_unversioned_data_scan.py" in scanned
    assert "unversioned_data_scan.py" in scanned


def test_this_scanner_obeys_its_own_statement_limit():
    """The check that would be embarrassing to fail -- see
    test_code_standards_scan.py's twin of this test. Covers both halves
    of the split: this file and the library it imports."""
    import tests.test_code_standards_scan as code_standards_scan

    over = []
    for path in (Path(__file__), scan.REPO_ROOT / "tests" / "unversioned_data_scan.py"):
        source = path.read_text(encoding="utf-8")
        over += [
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
    _, _, func_node = next(scan.test_functions(tree))
    return scan.offense_reason(func_node, fixtures or scan.fixture_defs(tree))


def test_the_original_parser_ocr_bug_is_flagged():
    assert _snippet_offense(_Snippets.ORIGINAL_PARSER_OCR_BUG)


def test_the_original_bib_smoke_bug_is_flagged():
    assert _snippet_offense(_Snippets.ORIGINAL_BIB_SMOKE_BUG)


def test_a_reload_pinned_to_tmp_path_is_not_flagged():
    assert _snippet_offense(_Snippets.PINNED_RELOAD) is None


def test_a_pin_factored_into_a_same_module_fixture_is_still_honoured():
    tree = ast.parse(_Snippets.PINNED_VIA_FIXTURE)
    fixtures = scan.fixture_defs(tree)
    _, _, func_node = next(
        (q, c, n) for q, c, n in scan.test_functions(tree) if q.endswith("test_bib_file_env_override")
    )
    assert scan.offense_reason(func_node, fixtures) is None


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
