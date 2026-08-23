"""Return-type annotation coverage under `chitragupta/`, enforced as a ratchet.

[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md)'s build order item 3 --
"type annotations and a checker" -- is what this file closes the cheap
half of. #355 annotated every `def` under `chitragupta/` that was missing a
return type (55 of 813, found by the same `ast`-walk this file runs), and
this is the check that stops the count going back up. The other half of
item 3, a real type checker such as `mypy`, is declined rather than
deferred: CODE-STANDARDS.md already calls it "worth having and its own
project, not a step in this one", and nothing here reopens that question.

Same shape as `tests/test_code_standards_scan.py`'s C1/C2 ratchet, and for
the same reason: today's offenders are frozen in a register that may only
shrink, so a rule that failed on day one would be a rule someone switches
off. The difference is what "today" already looked like by the time this
file was written -- #355 closed every offender in the same change that
added the check, so the register below starts, and is meant to stay,
empty. That is not a weaker check: `LEGACY_LONG_FUNCTIONS` is exactly this
shape for `chitragupta/sync.py::run` and `chitragupta/dossier.py`, both
resolved and both still enforced.
"""

import ast

from test_code_standards_scan import _python_files, _relative

ANNOTATION_ROOTS = ("chitragupta",)

# Every gap #355 found and fixed. Starts empty, and stays that way unless a
# future `def` genuinely cannot carry a return annotation -- add it here,
# with a comment saying why, rather than leaving the scan red.
LEGACY_UNANNOTATED_DEFS = set()


def _definitions(node, prefix):
    """`(qualified_name, is_missing_a_return_annotation)` for every function
    under `node`.

    Mirrors `test_code_standards_scan.functions()`'s walk exactly --
    nested and method definitions qualified the same way, conditionally
    defined functions still found -- because the two checks must agree on
    what a "def" is. They diverge only in what each records about it: a
    statement count there, whether `returns` is `None` here.
    """
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
    """Every function in `source` as `(qualified_name, is_missing_a_return_annotation)`."""
    return list(_definitions(ast.parse(source), ""))


def _unannotated_names(source):
    """The qualified name of every function in `source` with no return annotation."""
    return {name for name, missing in functions(source) if missing}


def unannotated_defs(roots):
    """`{path::qualified_name}` for every `chitragupta/` function with no return annotation."""
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
        "register:" + "".join(f"\n  {name}" for name in new)
        + "\n\nAdd a return annotation, or -- if it genuinely cannot carry one -- "
        "say why in the PR and add it to LEGACY_UNANNOTATED_DEFS in this file. "
        "See docs/CODE-STANDARDS.md's build order item 3."
    )


def test_the_register_holds_no_entry_that_is_already_fixed():
    """The ratchet's other half. Without it a function annotated later would
    keep its licence to lose that annotation again, silently, forever."""
    fixed = _fixed_offenders(unannotated_defs(ANNOTATION_ROOTS), LEGACY_UNANNOTATED_DEFS)
    assert not fixed, (
        "These now carry a return annotation -- delete them from "
        "LEGACY_UNANNOTATED_DEFS:" + "".join(f"\n  {name}" for name in fixed)
    )


def test_the_scan_reaches_the_source_tree():
    """Non-vacuity: a glob that silently matched nothing would make the
    test above pass for the wrong reason, forever."""
    scanned = {_relative(path) for path in _python_files(ANNOTATION_ROOTS)}
    assert "chitragupta/config.py" in scanned
    # A nested module, the specific thing the glob has to get right --
    # `**/*.py` degraded to `*.py` would still find config.py while
    # silently dropping every module enrich/ and review/ hold, which is
    # where most of #355's 55 gaps were.
    assert "chitragupta/enrich/docling_parse.py" in scanned
    assert "chitragupta/review/verbatim_check.py" in scanned


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
    source = (
        "def outer():\n"
        "    def inner() -> None:\n"
        "        pass\n"
        "    return inner\n"
    )
    assert dict(functions(source)) == {"outer": True, "outer.inner": False}


def test_a_method_is_qualified_by_its_class():
    source = "class C:\n    def m(self) -> None:\n        pass\n"
    assert dict(functions(source)) == {"C.m": False}


def test_a_function_defined_inside_a_conditional_keeps_its_enclosing_scope():
    """`if`/`try`/`with` are not scopes, so they must not extend the
    qualified name -- but they must still be descended into, or the
    function inside is invisible to the scan."""
    source = (
        "class A:\n"
        "    if True:\n"
        "        def m(self) -> None:\n"
        "            pass\n"
    )
    assert dict(functions(source)) == {"A.m": False}


def test_a_new_offender_is_reported_and_a_registered_one_is_not():
    found = {"a.py::f", "b.py::g"}
    assert _new_offenders(found, {"b.py::g"}) == ["a.py::f"]
    assert _fixed_offenders(found, {"b.py::g"}) == []


def test_a_registered_offender_that_no_longer_offends_is_reported():
    assert _fixed_offenders({"a.py::f"}, {"a.py::f", "b.py::g"}) == ["b.py::g"]
