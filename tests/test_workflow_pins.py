"""Structural rules about `.github/workflows/*.yml`, read with a YAML
loader rather than by indentation (#866).

A failure here means a workflow broke a rule its own header documents,
not that a document drifted -- that is `tests/test_docs_pins.py`. Both
rules are two of #512's four config findings, each turned into the check
that would have caught it.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS / "ci.yml"
DOCS_WORKFLOW = WORKFLOWS / "docs.yml"


def _workflow(path: Path) -> dict:
    """The parsed workflow. PyYAML follows YAML 1.1, where a bare `on`
    is the boolean True, so the trigger block arrives under that key; it
    is moved back to "on" here, once."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc


def _push_filters(workflow: Path) -> "set[str] | None":
    """The filter keys under a workflow's push trigger: **None** if it
    has no push trigger at all, an empty set if push is unfiltered.

    The caller tells those apart. Collapsing them is how a drift guard
    turns into a silent pass -- the exact defect class #509 was about.
    """
    on = _workflow(workflow).get("on")
    if on == "push" or (isinstance(on, list) and "push" in on):
        return set()
    if not isinstance(on, dict) or "push" not in on:
        return None
    return set(on["push"] or {})


def _restore_keys_steps(path: Path) -> list[tuple[str, str]]:
    """`(job, step)` for every step that passes `restore-keys`."""
    return [
        (job, step.get("name", step.get("uses", "?")))
        for job, spec in _workflow(path)["jobs"].items()
        for step in spec.get("steps", [])
        if "restore-keys" in (step.get("with") or {})
    ]


class TestTheWorkflowsKeepTheirOwnRules:
    def test_no_workflow_mixes_a_branch_filter_with_a_tag_filter(self):
        """m-84: under a `branches:`-filtered push trigger a tag push
        already matches nothing, so `tags-ignore` there does not narrow
        the trigger -- it re-enables builds for every tag the ignore list
        does not name. `ci.yml`'s own header documents the rule."""
        for workflow in (CI_WORKFLOW, DOCS_WORKFLOW):
            filters = _push_filters(workflow)
            # Both are known to filter their push trigger, so None or an
            # empty set means the trigger changed shape under this check,
            # not that there is nothing to check. Refused loudly rather
            # than passed over.
            assert filters, (
                f"{workflow.name} no longer has a filtered push trigger, so the "
                "branch/tag check below did not run. Do not delete this assertion."
            )
            if {"branches", "branches-ignore"} & filters:
                assert not {"tags", "tags-ignore"} & filters, (
                    f"{workflow.name}'s push trigger mixes a branch filter with a tag "
                    f"filter ({sorted(filters)}), which widens it rather than narrowing it."
                )

    def test_the_venv_cache_has_no_prefix_fallback(self):
        """m-87: `restore-keys` restored an older lock's venv, and
        `poetry install` without `--sync` never uninstalls -- so a package
        removed from the lock stayed importable, and on `main` was re-saved
        under the new lock's hash. CI would keep passing on an import a
        clean install cannot satisfy."""
        steps = _restore_keys_steps(CI_WORKFLOW)
        assert steps == [], (
            f"ci.yml restores a cache by key prefix again: {steps}. See #512/m-87 "
            "for why that carries a removed package forward forever."
        )


def _write(tmp_path: Path, on: str) -> Path:
    path = tmp_path / "w.yml"
    path.write_text(f"name: W\n{on}jobs: {{}}\n", encoding="utf-8")
    return path


class TestTheReadersThemselves:
    """The helpers both rules rest on, against the shapes YAML allows --
    so a rule is known to see a violation rather than assumed to."""

    def test_it_sees_a_mixed_filter(self, tmp_path):
        workflow = _write(
            tmp_path,
            "on:\n  push:\n    branches: [main]\n    tags-ignore:\n      - 'v*'\n"
            "  pull_request:\n    branches: [main]\n",
        )
        assert _push_filters(workflow) == {"branches", "tags-ignore"}

    @pytest.mark.parametrize(
        "block",
        [
            "  push:  # main only\n    branches: [main]\n",
            "  push: {branches: [main]}\n",
            "   push:\n     branches: [main]\n",
        ],
        ids=["trailing-comment", "inline-mapping", "different-indent"],
    )
    def test_a_reformatted_trigger_still_reads_correctly(self, tmp_path, block):
        """Each of these defeated the indentation reader this replaced,
        which could only report them as unreadable."""
        assert _push_filters(_write(tmp_path, f"on:\n{block}")) == {"branches"}

    @pytest.mark.parametrize(
        "on",
        ["on: push\n", "on: [push, pull_request]\n", "on:\n  push:\n"],
        ids=["scalar", "list", "null-body"],
    )
    def test_an_unfiltered_push_reads_as_empty_not_none(self, tmp_path, on):
        assert _push_filters(_write(tmp_path, on)) == set()

    def test_no_push_trigger_reads_as_none(self, tmp_path):
        assert _push_filters(_write(tmp_path, "on:\n  workflow_dispatch:\n")) is None

    def test_the_cache_rule_sees_a_restore_keys_step(self, tmp_path):
        path = tmp_path / "ci.yml"
        path.write_text(
            "on: push\njobs:\n  t:\n    steps:\n      - uses: actions/cache@v4\n"
            "        with:\n          key: k\n          restore-keys: k-\n",
            encoding="utf-8",
        )
        assert _restore_keys_steps(path) == [("t", "actions/cache@v4")]
