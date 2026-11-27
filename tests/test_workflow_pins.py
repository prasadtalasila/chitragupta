from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS / "ci.yml"
DOCS_WORKFLOW = WORKFLOWS / "docs.yml"
RELEASE_WORKFLOW = WORKFLOWS / "release.yml"


def _workflow(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc


def _push_filters(workflow: Path) -> "set[str] | None":
    on = _workflow(workflow).get("on")
    if on == "push" or (isinstance(on, list) and "push" in on):
        return set()
    if not isinstance(on, dict) or "push" not in on:
        return None
    return set(on["push"] or {})


def _restore_keys_steps(path: Path) -> list[tuple[str, str]]:
    return [
        (job, step.get("name", step.get("uses", "?")))
        for job, spec in _workflow(path)["jobs"].items()
        for step in spec.get("steps", [])
        if "restore-keys" in (step.get("with") or {})
    ]


class TestTheWorkflowsKeepTheirOwnRules:
    def test_no_workflow_mixes_a_branch_filter_with_a_tag_filter(self):
        for workflow in (CI_WORKFLOW, DOCS_WORKFLOW):
            filters = _push_filters(workflow)
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


class TestOnlyMajorAndMinorVersionsAreReleased:
    def test_only_a_tag_ending_in_dot_zero_starts_a_run(self):
        push = _workflow(RELEASE_WORKFLOW)["on"]["push"]
        assert push == {"tags": ["v[0-9]+.[0-9]+.0"]}

    def test_the_release_job_refuses_any_other_tag(self):
        release = _workflow(RELEASE_WORKFLOW)["jobs"]["release"]
        assert release["if"] == "endsWith(github.ref_name, '.0')"

    def test_pypi_is_reached_only_through_the_release_job(self):
        publish = _workflow(RELEASE_WORKFLOW)["jobs"]["publish-pypi"]
        assert publish["needs"] == "release"
        assert "if" not in publish
