"""#950's class: a path-list environment variable joined with `:`.

`TEXINPUTS`, `PATH`, `PYTHONPATH` and their kin are separated by
`os.pathsep`, which is `;` on Windows. A literal `:` there splits a
drive-letter path in two (`C` and `\\Users\\...`), so the list names
nothing that exists and a pdf render with a figure include fails with
"File not found". Nothing under chitragupta/ or scripts/ may build the
value of such a variable with a literal `:`.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The variables whose value is a list of paths, by the names they end in.
PATH_LIST_SUFFIXES = ("PATH", "INPUTS")


def _is_path_list_key(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.upper().endswith(PATH_LIST_SUFFIXES)
    )


def _joins_with_a_colon(value: ast.expr) -> bool:
    """An f-string with a `:` in its literal text, or `":".join(...)`."""
    if isinstance(value, ast.JoinedStr):
        return any(isinstance(part, ast.Constant) and ":" in part.value for part in value.values)
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == "join"
        and isinstance(value.func.value, ast.Constant)
        and value.func.value.value == ":"
    )


def _offending_lines(source: str) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Dict):
            pairs = zip(node.keys, node.values)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript):
            pairs = [(node.targets[0].slice, node.value)]
        else:
            continue
        lines += [v.lineno for k, v in pairs if _is_path_list_key(k) and _joins_with_a_colon(v)]
    return lines


def test_the_scan_catches_the_spellings_it_was_written_for():
    assert _offending_lines('env = {"TEXINPUTS": f"{d}:"}') == [1]
    assert _offending_lines('env["PYTHONPATH"] = ":".join(paths)') == [1]
    assert _offending_lines('env = {"TEXINPUTS": f"{d}{os.pathsep}"}') == []
    # A Zotero `file` field is split on `:` too, but it is no env var.
    assert _offending_lines('path = Path(":".join(parts[1:-1]))') == []


def test_no_path_list_env_var_is_joined_with_a_colon():
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for top in ("chitragupta", "scripts")
        for path in sorted((ROOT / top).rglob("*.py"))
        for n in _offending_lines(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
