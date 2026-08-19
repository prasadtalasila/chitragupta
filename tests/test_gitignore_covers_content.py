"""Every artefact directory the pipeline writes under `content/` is
gitignored, and the two worked examples are not.

The enumerated `.gitignore` this replaces failed silently: `content/specs/`
landed in 5.34.0 and nothing noticed, so a whole book's outline, unit
records and registries showed up as untracked in every `git status` --
one `git add -A` from being committed as somebody's per-host data. A
blanket `content/*` cannot go stale that way, and this pins that it
stays blanket rather than drifting back to a list.

It derives the names from `src/config.py` rather than restating them, so
a new `config.SOMETHING_DIR` under `content/` is covered on the day it is
added, not on the day someone remembers this file.

Asked of `git check-ignore` rather than by parsing `.gitignore`: the
ordering rules for a negation inside an ignored directory are exactly
the part that is easy to get wrong (git never descends into an ignored
directory, so `!content/drafts/<topic>/` alone never fires), and only
git itself answers for them.
"""

import subprocess
from pathlib import Path

import pytest

from src import config

REPO_ROOT = Path(__file__).resolve().parent.parent

# The two trees kept tracked deliberately: one worked draft of each genre,
# and the renders that match it, so a fresh clone can see what this
# pipeline produces before it has a corpus.
TRACKED = (
    "content/drafts/digital-twins-for-software-engineers",
    "content/rendered/digital-twins-for-software-engineers",
)

# The two directories those live in cannot themselves be ignored -- git
# never descends into an ignored directory, so ignoring `content/drafts`
# would hide the exception inside it. What has to hold for them is one
# step down: every *other* topic under them is ignored.
EXCEPTION_PARENTS = {path.rsplit("/", 1)[0] for path in TRACKED}


def _ignored(relative_path: str) -> bool:
    """What git itself says about a path, which need not exist."""
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", relative_path],
        check=False,
    ).returncode == 0


def _content_paths() -> list[str]:
    """`content/<name>` for every path constant config.py derives from
    CONTENT_DIR -- the pipeline's own list of what it writes there."""
    found = set()
    for value in vars(config).values():
        if isinstance(value, Path) and value != config.CONTENT_DIR:
            try:
                found.add(f"content/{value.relative_to(config.CONTENT_DIR).as_posix()}")
            except ValueError:
                continue
    return sorted(found)


def test_the_scan_found_the_paths_it_is_meant_to_check():
    """Guards against the whole file passing vacuously if config.py ever
    stops exposing its paths as module-level `Path`s."""
    paths = _content_paths()
    assert len(paths) >= 10, paths
    assert "content/drafts" in paths and "content/specs" in paths


@pytest.mark.parametrize("relative_path", _content_paths())
def test_every_content_artefact_path_is_ignored(relative_path):
    # For the two directories holding a tracked example, the claim is
    # about what they contain rather than about them: any other topic
    # written there is per-host data like everything else.
    checked = (f"{relative_path}/some-other-topic/draft.md"
               if relative_path in EXCEPTION_PARENTS else relative_path)
    assert _ignored(checked), (
        f"{checked} is not gitignored, so everything the pipeline writes "
        "there shows up as untracked -- and is one `git add -A` from being "
        "committed as somebody's per-host data. See .gitignore's content/ block."
    )


def test_a_directory_nobody_has_invented_yet_is_ignored_too():
    """The point of the blanket rule: coverage that does not depend on
    anyone updating a list."""
    assert _ignored("content/some-artefact-directory-from-the-future/file.json")


@pytest.mark.parametrize("relative_path", TRACKED)
def test_the_worked_examples_stay_visible(relative_path):
    assert not _ignored(relative_path), (
        f"{relative_path} is ignored, so the one worked example a fresh clone "
        "can read has stopped being visible to git."
    )
