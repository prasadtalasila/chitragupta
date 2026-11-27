import subprocess
from pathlib import Path

import pytest

from chitragupta import config

REPO_ROOT = Path(__file__).resolve().parent.parent

TRACKED = (
    "content/drafts/digital-twins-for-software-engineers",
    "content/rendered/digital-twins-for-software-engineers",
)

EXCEPTION_PARENTS = {path.rsplit("/", 1)[0] for path in TRACKED}


def _ignored(relative_path: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", relative_path],
            check=False,
        ).returncode
        == 0
    )


def _content_paths() -> list[str]:
    found = set()
    for value in vars(config).values():
        if isinstance(value, Path) and value != config.CONTENT_DIR:
            try:
                found.add(f"content/{value.relative_to(config.CONTENT_DIR).as_posix()}")
            except ValueError:
                continue
    return sorted(found)


def test_the_scan_found_the_paths_it_is_meant_to_check():
    paths = _content_paths()
    assert len(paths) >= 10, paths
    assert "content/drafts" in paths and "content/specs" in paths


@pytest.mark.parametrize("relative_path", _content_paths())
def test_every_content_artefact_path_is_ignored(relative_path):
    checked = (
        f"{relative_path}/some-other-topic/draft.md"
        if relative_path in EXCEPTION_PARENTS
        else relative_path
    )
    assert _ignored(checked), (
        f"{checked} is not gitignored, so everything the pipeline writes "
        "there shows up as untracked -- and is one `git add -A` from being "
        "committed as somebody's per-host data. See .gitignore's content/ block."
    )


def test_a_directory_nobody_has_invented_yet_is_ignored_too():
    assert _ignored("content/some-artefact-directory-from-the-future/file.json")


@pytest.mark.parametrize("relative_path", TRACKED)
def test_the_worked_examples_stay_visible(relative_path):
    assert not _ignored(relative_path), (
        f"{relative_path} is ignored, so the one worked example a fresh clone "
        "can read has stopped being visible to git."
    )
