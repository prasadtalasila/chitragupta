""".claude/hooks/patch_paths.py: the files an apply_patch envelope writes (#812, #900)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / ".claude" / "hooks"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "harness_payloads"


def load(name: str):
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


patch_paths = load("patch_paths")

PATCH = """*** Begin Patch
*** Add File: content/drafts/new.md
+A claim.
*** Update File: content/drafts/old.md
*** Move to: content/drafts/renamed.md
@@
-before
+after
*** Delete File: content/drafts/gone.md
*** Update File: content/drafts/new.md
@@
+again
*** End Patch
"""


def test_every_written_path_in_order_once():
    assert patch_paths.written_paths(PATCH) == [
        "content/drafts/new.md",
        "content/drafts/old.md",
        "content/drafts/renamed.md",
    ]


def test_a_deletion_is_not_a_write():
    text = "*** Begin Patch\n*** Delete File: content/drafts/gone.md\n*** End Patch\n"
    assert patch_paths.written_paths(text) == []


def test_text_with_no_envelope_is_not_a_patch():
    assert patch_paths.written_paths("ls content/drafts") == []


def test_crlf_line_endings_do_not_leak_into_the_path():
    text = PATCH.replace("\n", "\r\n")
    assert patch_paths.written_paths(text)[0] == "content/drafts/new.md"


def test_an_envelope_with_no_file_operation_is_unreadable():
    with pytest.raises(patch_paths.UnreadablePatch):
        patch_paths.written_paths("*** Begin Patch\n*** Frobnicate: x\n*** End Patch\n")


def test_a_header_quoted_in_a_body_line_is_not_read():
    # A `+` line that happens to quote a header is content, not an operation.
    text = "*** Begin Patch\n*** Add File: a.md\n+*** Add File: b.md\n*** End Patch\n"
    assert patch_paths.written_paths(text) == ["a.md"]


@pytest.mark.parametrize("fixture", ["codex_apply_patch.json", "codex_apply_patch_multi.json"])
def test_the_codex_payloads_parse(fixture):
    payload = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    paths = patch_paths.written_paths(payload["tool_input"]["command"])
    assert paths
    assert all(p.startswith("content/drafts/") for p in paths)


def test_the_opencode_patch_parses():
    args = json.loads((FIXTURES / "opencode_apply_patch_args.json").read_text(encoding="utf-8"))
    assert patch_paths.written_paths(args["patchText"]) == [
        "content/drafts/a.md",
        "content/drafts/b.md",
    ]
