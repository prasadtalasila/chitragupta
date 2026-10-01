"""No module-level helper or fixture body appears in two test modules (#867).

docs/CODE-STANDARDS.md names duplication the highest-value thing to catch,
and the rule covers tests. Before #867 the suite carried seven copies of
`book`, four of `_sidecar` and of `_add_item`, three of `_has_tikz` and a
dozen more pairs -- each one a place for a fix to land in one copy and
not the others, which is how `test_tldr.py`'s came to say it "mirrors"
another module's.

The comparison is on the AST of the body with its docstring dropped, so
a copy that only reworded its docstring is still a copy, and a one-line
body is not counted: `return book_dir` in two modules is a name, not a
duplicated procedure. A shared helper lives in tests/conftest.py, or
beside the helpers it builds on (`tests/test_review_units.py`'s
`a_draft`).

What it does not see, so a clean run is read for what it is: methods
and nested functions (only module-level `def`s are compared), a copy
that renamed a local variable (the comparison is exact), and one-line
bodies. A one-line launcher wrapper, the old `_run`, is
`tests/test_subprocess_launch_scan.py`'s to catch.
"""

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def _body_key(node: ast.FunctionDef) -> "str | None":
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if len(body) < 2:
        return None
    return ast.dump(ast.Module(body=body, type_ignores=[]))


def duplicates(sources: "dict[str, str]") -> "list[list[str]]":
    """Groups of `module::function` sharing one body across modules."""
    seen: "dict[str, list[str]]" = {}
    for module, source in sources.items():
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and (key := _body_key(node)):
                seen.setdefault(key, []).append(f"{module}::{node.name}")
    return [sorted(where) for where in seen.values() if len({w.split("::")[0] for w in where}) > 1]


def test_no_helper_body_is_defined_in_two_test_modules():
    sources = {p.name: p.read_text(encoding="utf-8") for p in sorted(TESTS.glob("*.py"))}
    found = duplicates(sources)
    assert not found, "move the shared body to tests/conftest.py and import it:\n  " + "\n  ".join(
        ", ".join(group) for group in found
    )


def test_the_detector_sees_a_pre_867_copy():
    """`_sidecar` as it stood in three modules, two of them verbatim and
    one with a docstring the others lacked."""
    body = (
        "def _sidecar(citekey, records):\n"
        "    config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)\n"
        '    (config.DOCLING_DIR / f"{citekey}.passages.json").write_text(json.dumps(records))\n'
    )
    documented = body.replace("records):\n", 'records):\n    """A sidecar."""\n', 1)
    assert duplicates({"a.py": body, "b.py": documented}) == [["a.py::_sidecar", "b.py::_sidecar"]]


def test_a_one_line_alias_is_not_a_copy():
    alias = "@pytest.fixture\ndef book(book_dir):\n    return book_dir\n"
    assert duplicates({"a.py": alias, "b.py": alias}) == []
