import ast

from test_code_standards_scan import _python_files, _relative

ANNOTATION_ROOTS = ("chitragupta",)

LEGACY_UNANNOTATED_DEFS = set()


def _definitions(node, prefix):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = prefix + child.name
            yield name, child.returns is None
            yield from _definitions(child, name + ".")
        elif isinstance(child, ast.ClassDef):
            yield from _definitions(child, prefix + child.name + ".")
        else:
            yield from _definitions(child, prefix)


def functions(source):
    return list(_definitions(ast.parse(source), ""))


def _unannotated_names(source):
    return {name for name, missing in functions(source) if missing}


def unannotated_defs(roots):
    return {
        f"{_relative(path)}::{name}"
        for path in _python_files(roots)
        for name in _unannotated_names(path.read_text(encoding="utf-8"))
    }


def _new_offenders(found, register):
    return sorted(found - register)


def _fixed_offenders(found, register):
    return sorted(register - found)


def test_no_new_def_lacks_a_return_annotation():
    found = unannotated_defs(ANNOTATION_ROOTS)
    new = _new_offenders(found, LEGACY_UNANNOTATED_DEFS)
    assert not new, (
        "def's under chitragupta/ with no return annotation that are not in the "
        "register:"
        + "".join(f"\n  {name}" for name in new)
        + "\n\nAdd a return annotation, or -- if it genuinely cannot carry one -- "
        "say why in the PR and add it to LEGACY_UNANNOTATED_DEFS in this file. "
        "See docs/CODE-STANDARDS.md's build order item 4."
    )


def test_the_register_holds_no_entry_that_is_already_fixed():
    fixed = _fixed_offenders(unannotated_defs(ANNOTATION_ROOTS), LEGACY_UNANNOTATED_DEFS)
    assert not fixed, (
        "These now carry a return annotation -- delete them from "
        "LEGACY_UNANNOTATED_DEFS:" + "".join(f"\n  {name}" for name in fixed)
    )


def test_the_scan_reaches_the_source_tree():
    scanned = {_relative(path) for path in _python_files(ANNOTATION_ROOTS)}
    assert "chitragupta/config.py" in scanned
    assert "chitragupta/enrich/docling_parse.py" in scanned
    assert "chitragupta/review/citation_provenance.py" in scanned


def test_a_missing_return_annotation_is_detected():
    source = "def f():\n    return 1\n"
    assert functions(source) == [("f", True)]
    assert _unannotated_names(source) == {"f"}


def test_a_present_return_annotation_is_not_flagged():
    source = "def f() -> int:\n    return 1\n"
    assert functions(source) == [("f", False)]
    assert _unannotated_names(source) == set()


def test_an_async_function_is_checked_too():
    assert functions("async def f():\n    return 1\n") == [("f", True)]
    assert functions("async def f() -> int:\n    return 1\n") == [("f", False)]


def test_a_nested_function_is_qualified_and_checked_on_its_own_account():
    source = "def outer():\n    def inner() -> None:\n        pass\n    return inner\n"
    assert dict(functions(source)) == {"outer": True, "outer.inner": False}


def test_a_method_is_qualified_by_its_class():
    source = "class C:\n    def m(self) -> None:\n        pass\n"
    assert dict(functions(source)) == {"C.m": False}


def test_a_function_defined_inside_a_conditional_keeps_its_enclosing_scope():
    source = "class A:\n    if True:\n        def m(self) -> None:\n            pass\n"
    assert dict(functions(source)) == {"A.m": False}


def test_a_new_offender_is_reported_and_a_registered_one_is_not():
    found = {"a.py::f", "b.py::g"}
    assert _new_offenders(found, {"b.py::g"}) == ["a.py::f"]
    assert _fixed_offenders(found, {"b.py::g"}) == []


def test_a_registered_offender_that_no_longer_offends_is_reported():
    assert _fixed_offenders({"a.py::f"}, {"a.py::f", "b.py::g"}) == ["b.py::g"]
