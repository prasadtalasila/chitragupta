"""No message chitragupta prints the path `scripts/install_full_pipeline.sh`
(#1022 item 3).

A `chitragupta init` project has no `scripts/` (docs/PACKAGING.md), so a
remedy naming it sends the reader to a file they do not have.
`chitragupta install <stage>` runs the same script from either shape
(`chitragupta.install.remedy`). install.py is exempt: it is the module
that runs the script. Docstrings and comments are not messages and stay
free to explain where a stage lives.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "chitragupta"
EXEMPT = {PACKAGE / "install.py"}


def _docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                yield first.value


def test_no_printed_string_names_the_install_script():
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path in EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {id(node) for node in _docstrings(tree)}
        offenders += [
            f"{path.relative_to(PACKAGE.parent)}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and "scripts/install_full_pipeline.sh" in node.value
        ]
    assert offenders == []


SKILL_TREES = (".claude/skills", ".agents/skills", ".opencode/skills")


def test_no_skill_sends_a_drafting_reader_to_the_install_script():
    # The skills are scaffolded into a `chitragupta init` project too,
    # which has no scripts/ to run (#1022 review).
    root = PACKAGE.parent
    offenders = [
        f"{path.relative_to(root)}"
        for tree in SKILL_TREES
        for path in sorted((root / tree).rglob("*.md"))
        if "scripts/install_full_pipeline.sh" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
