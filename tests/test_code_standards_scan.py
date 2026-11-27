# Enforces C1 (25 statements per function) and C2 (250 code lines per module)
# from docs/CODE-STANDARDS.md. Statements, not physical lines, so a size limit
# never rewards deleting a why-comment. A ratchet, not a wall: today's
# offenders are frozen in the register, and an entry that comes back under
# its threshold fails until it is deleted, so the register can only shrink.
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_scanner():
    spec = importlib.util.spec_from_file_location(
        "code_standards", REPO_ROOT / "scripts" / "code_standards.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scan = _load_scanner()

MAX_STATEMENTS = scan.MAX_STATEMENTS
MAX_CODE_LINES = scan.MAX_CODE_LINES
STATEMENT_ROOTS = scan.STATEMENT_ROOTS
CODE_LINE_ROOTS = scan.CODE_LINE_ROOTS

statement_count = scan.statement_count
functions = scan.functions
code_lines = scan.code_lines
long_functions = scan.long_functions
long_files = scan.long_files
_python_files = scan._python_files
_relative = scan._relative

_C1_COUNTS, _C2_COUNTS = scan.register()
LEGACY_LONG_FUNCTIONS = set(_C1_COUNTS)
LEGACY_LONG_FILES = set(_C2_COUNTS)


def _new_offenders(found, register):
    return sorted(set(found) - register)


def _fixed_offenders(found, register):
    return sorted(register - set(found))


def test_no_new_function_exceeds_the_statement_limit():
    found = long_functions(STATEMENT_ROOTS)
    new = _new_offenders(found, LEGACY_LONG_FUNCTIONS)
    assert not new, (
        "Functions over the "
        f"{MAX_STATEMENTS}-statement limit that are not in the register:"
        + "".join(f"\n  {name} -- {found[name]} statements" for name in new)
        + "\n\nSplit the function, or -- if it genuinely cannot be split -- say why "
        "in the PR and add it to LEGACY_LONG_FUNCTIONS in this file. Statements, "
        "not lines: comments are free, so this is about what the function does, "
        "not how well it is explained. See docs/CODE-STANDARDS.md."
    )


def test_no_new_module_exceeds_the_code_line_limit():
    found = long_files(CODE_LINE_ROOTS)
    new = _new_offenders(found, LEGACY_LONG_FILES)
    assert not new, (
        f"Modules over the {MAX_CODE_LINES}-code-line limit that are not in the "
        "register:"
        + "".join(f"\n  {name} -- {found[name]} code lines" for name in new)
        + "\n\nA module this long is usually holding more than one responsibility; "
        'see DEVELOPER-AGENTS.md\'s "Module boundaries". Blank lines and comments '
        "are not counted, so this is not a limit on explaining yourself. If the "
        "split is genuinely wrong, add it to LEGACY_LONG_FILES in this file and "
        "say why in the PR. See docs/CODE-STANDARDS.md."
    )


def test_the_function_register_holds_no_entry_that_is_already_fixed():
    fixed = _fixed_offenders(long_functions(STATEMENT_ROOTS), LEGACY_LONG_FUNCTIONS)
    assert not fixed, (
        "These are now within the limit -- delete them from "
        "LEGACY_LONG_FUNCTIONS:" + "".join(f"\n  {name}" for name in fixed)
    )


def test_the_file_register_holds_no_entry_that_is_already_fixed():
    fixed = _fixed_offenders(long_files(CODE_LINE_ROOTS), LEGACY_LONG_FILES)
    assert not fixed, (
        "These are now within the limit -- delete them from LEGACY_LONG_FILES:"
        + "".join(f"\n  {name}" for name in fixed)
    )


def test_the_scan_reaches_the_source_tree():
    scanned = {_relative(path) for path in _python_files(STATEMENT_ROOTS)}
    assert "chitragupta/sync.py" in scanned
    assert "scripts/release.py" in scanned
    assert "tests/test_code_standards_scan.py" in scanned
    assert "chitragupta/enrich/docling_parse.py" in scanned
    assert "chitragupta/review/citation_provenance.py" in scanned
    assert not any(name.startswith("bench/") for name in scanned)


def test_the_registers_name_only_paths_that_still_exist():
    paths = {name.split("::")[0] for name in LEGACY_LONG_FUNCTIONS} | LEGACY_LONG_FILES
    missing = sorted(name for name in paths if not (REPO_ROOT / name).exists())
    assert not missing, f"register entries for files that no longer exist: {missing}"


def _recorded_counts():
    return {**_C1_COUNTS, **_C2_COUNTS}


def test_every_registered_offender_records_its_current_count():
    counts = long_functions(STATEMENT_ROOTS) | long_files(CODE_LINE_ROOTS)
    recorded = _recorded_counts()
    assert set(recorded) == set(counts), (
        "the register comments and the registers themselves disagree about which entries exist"
    )
    drifted = {name: (was, counts[name]) for name, was in recorded.items() if was != counts[name]}
    assert not drifted, (
        "register entries whose recorded count is stale (recorded -> actual):"
        + "".join(f"\n  {n}: {w} -> {a}" for n, (w, a) in sorted(drifted.items()))
        + "\n\nUpdate the trailing comment to the current number. Ordering in the "
        "register is worst-first, so check whether the entry also needs moving."
    )


def test_the_registers_are_the_size_this_document_says():
    text = (REPO_ROOT / "docs" / "CODE-STANDARDS.md").read_text(encoding="utf-8")
    files = len(LEGACY_LONG_FILES)
    expected = (
        f"**{len(LEGACY_LONG_FUNCTIONS)}\nfunctions** and "
        f"**{files} module{'' if files == 1 else 's'}**"
    )
    assert " ".join(expected.split()) in " ".join(text.split()), (
        "docs/CODE-STANDARDS.md no longer states the register sizes correctly. "
        f"They are now {len(LEGACY_LONG_FUNCTIONS)} functions and "
        f"{len(LEGACY_LONG_FILES)} modules."
    )


def test_this_scanner_obeys_its_own_statement_limit():
    for path in (REPO_ROOT / "scripts" / "code_standards.py", Path(__file__)):
        source = path.read_text(encoding="utf-8")
        assert all(count <= MAX_STATEMENTS for _, count in functions(source)), path


def test_a_statement_is_counted_per_statement_not_per_line():
    terse = "def f():\n    a = 1\n    b = 2\n    return a + b\n"
    explained = (
        "def f():\n"
        + "    # why a is 1: "
        + "x" * 40
        + "\n" * 1
        + "    a = 1\n"
        + "    # why b is 2, at length:\n" * 30
        + "    b = 2\n"
        + "    return a + b\n"
    )
    assert functions(terse) == functions(explained) == [("f", 3)]
    assert len(explained.splitlines()) > 30


def test_a_nested_function_is_charged_to_itself_not_to_its_parent():
    source = (
        "def outer():\n"
        "    def inner():\n"
        "        a = 1\n"
        "        b = 2\n"
        "        return a + b\n"
        "    return inner\n"
    )
    assert dict(functions(source)) == {"outer": 2, "outer.inner": 3}


def test_the_methods_of_a_nested_class_are_not_charged_to_the_enclosing_function():
    source = (
        "def outer():\n"
        "    class C:\n"
        "        def m(self):\n"
        "            pass\n"
        "        def n(self):\n"
        "            pass\n"
        "    return C\n"
    )
    assert dict(functions(source)) == {"outer": 2, "outer.C.m": 1, "outer.C.n": 1}


def test_a_method_is_counted_and_not_charged_to_its_class_body():
    source = "class C:\n    def m(self):\n        a = 1\n        return a\n"
    assert dict(functions(source)) == {"C.m": 2}


def test_two_same_named_methods_in_one_module_stay_distinct():
    source = (
        "class A:\n"
        "    def __init__(self):\n"
        "        self.x = 1\n"
        "class B:\n"
        "    def __init__(self):\n"
        "        self.y = 1\n"
        "        self.z = 2\n"
    )
    assert dict(functions(source)) == {"A.__init__": 1, "B.__init__": 2}


def test_a_function_defined_inside_a_conditional_keeps_its_enclosing_scope():
    source = (
        "class A:\n    if True:\n        def m(self):\n            a = 1\n            return a\n"
    )
    assert dict(functions(source)) == {"A.m": 2}


def test_an_async_function_is_counted():
    assert functions("async def f():\n    a = 1\n    return a\n") == [("f", 2)]


def test_code_lines_ignores_blanks_and_whole_line_comments():
    source = "import os\n\n# a comment\n    # an indented comment\nx = 1\n"
    assert code_lines(source) == 2


def test_code_lines_counts_a_trailing_comment_on_a_real_line():
    assert code_lines("x = 1  # why x is 1\n") == 1


def test_a_new_offender_is_reported_and_a_registered_one_is_not():
    found = {"a.py::f": 40, "b.py::g": 30}
    assert _new_offenders(found, {"b.py::g"}) == ["a.py::f"]
    assert _fixed_offenders(found, {"b.py::g"}) == []


def test_a_registered_offender_that_no_longer_offends_is_reported():
    assert _fixed_offenders({"a.py::f": 40}, {"a.py::f", "b.py::g"}) == ["b.py::g"]
