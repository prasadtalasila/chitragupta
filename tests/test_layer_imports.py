"""Two layer boundaries, pinned by what the modules actually import (#853).

- **Only `chitragupta/enrich/` reaches an underscore-private enrich
  module.** `discover` imported `enrich._rerank` and called its private
  `_load_reranker`, so a rename inside the enrichment layer broke a corpus
  command. The shared loader now lives in the corpus-layer
  `chitragupta/reranker.py`, which both import.
- **`discover` does not import the drafting layer's `references`.** It
  only needs formatted entries, which `chitragupta/reference_entries.py`
  provides beneath both.

Read with `ast`, not by importing, so a module whose optional
dependencies are missing is still scanned.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = REPO_ROOT / "chitragupta"


def _imported_modules(path: Path) -> set[str]:
    """Every module name `path` imports, as a dotted name -- including a
    `from package import name`, which is recorded as `package.name` since
    that is how `from chitragupta.enrich import _rerank` reaches a module."""
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
    # Non-vacuous: a glob that matched nothing would pass every assertion.
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
