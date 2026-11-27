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
