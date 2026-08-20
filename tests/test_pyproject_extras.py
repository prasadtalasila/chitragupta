"""pyproject.toml's `[tool.poetry.extras]` and the Poetry group each
mirrors (#265) -- two lists that must agree, because they are declared
in two unrelated places for a Poetry limitation, not by choice: a group
dependency never reaches a built wheel's metadata, so `pip install
chitragupta-cli[enrich]` needs its own, duplicate declaration under
`[tool.poetry.dependencies]` (`optional = true`) to work at all. Without
this test the two can drift silently -- a version bumped in one and not
the other ships a `pip install`-only user a different resolution than a
`poetry install --with` one gets, from the same source tree.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Every extra this package declares, and the Poetry group it has to
# mirror. Adding a fourth of either without the other fails
# test_every_declared_extra_has_a_matching_group below.
EXTRA_TO_GROUP = {"enrich": "enrich", "dev": "dev", "docs": "docs"}


def _poetry_table() -> dict:
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)["tool"]["poetry"]


class TestExtrasMirrorGroups:
    def test_every_declared_extra_has_a_matching_group(self):
        poetry = _poetry_table()
        assert set(poetry["extras"]) == set(EXTRA_TO_GROUP)

    def test_an_extras_package_list_matches_its_groups_exactly(self):
        poetry = _poetry_table()
        for extra, group in EXTRA_TO_GROUP.items():
            group_names = set(poetry["group"][group]["dependencies"])
            assert set(poetry["extras"][extra]) == group_names, extra

    def test_an_extras_package_is_declared_optional_in_main_dependencies(self):
        poetry = _poetry_table()
        main_deps = poetry["dependencies"]
        for names in poetry["extras"].values():
            for name in names:
                assert main_deps[name]["optional"] is True, name

    def test_the_version_constraint_matches_the_groups_exactly(self):
        """The drift this test exists to catch: a constraint bumped in
        one of the two declarations and not the other."""
        poetry = _poetry_table()
        main_deps = poetry["dependencies"]
        for extra, group in EXTRA_TO_GROUP.items():
            group_deps = poetry["group"][group]["dependencies"]
            for name in poetry["extras"][extra]:
                assert main_deps[name]["version"] == group_deps[name], name
