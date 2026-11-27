import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = REPO_ROOT / "chitragupta"


def _imported_modules(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _modules(root: Path) -> list[Path]:
    found = sorted(root.rglob("*.py"))
    assert found, f"no Python modules under {root}"
    return found


def test_no_module_outside_enrich_imports_a_private_enrich_module():
    enrich = PACKAGE / "enrich"
    offenders = sorted(
        f"{path.relative_to(REPO_ROOT)}: {name}"
        for path in _modules(PACKAGE)
        if enrich not in path.parents
        for name in _imported_modules(path)
        if name.startswith("chitragupta.enrich.") and name.split(".")[2].startswith("_")
    )
    assert not offenders, (
        "a module outside chitragupta/enrich/ imports one of its private modules; "
        f"reach it through a public name instead: {offenders}"
    )


def test_discover_does_not_import_the_drafting_layers_references():
    offenders = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in _modules(PACKAGE / "discover")
        if "chitragupta.references" in _imported_modules(path)
    )
    assert not offenders, (
        "discover is a corpus-layer command; format entries through "
        f"chitragupta.reference_entries, not chitragupta.references: {offenders}"
    )
