"""The OpenCodeReview project rule file stays valid, and keeps reaching the tree.

`.opencodereview/rule.json` tells OCR (`ocr review`, `ocr scan`) which
review rules apply to which paths in this repository, in place of its
generic built-in Python rule. DEVELOPER-AGENTS.md's "Reviewing before you
push" says to run it.

Two things make it worth a test rather than trusting the file:

**A rule whose glob matches nothing fails open, not closed.** OCR falls
back to its built-in rule for any file no project entry matches, and says
so only if someone runs `ocr rules check` on that exact path. So renaming
a directory -- or writing `test/**` for `tests/**` -- silently returns
the whole tree to generic review while every command still exits 0. That
is the same non-vacuity argument `test_code_standards_scan.py` makes for
its own glob, and it is the main reason this file exists.

**The schema is undocumented.** The published docs URL 404s, so the two
fields OCR actually reads (`path` and `rule`) were established by probing
the binary's unmarshaller. Anything else in an entry -- `name`, the
`_comment` block -- is silently ignored. A future edit that adds
`"paths"` or `"pattern"` in good faith would parse cleanly, match
nothing, and disable that rule. Pinning the field names is what turns
that into a failure.

Deliberately does **not** invoke `ocr`: it is a developer tool installed
per-host (`npm i -g @alibaba-group/open-code-review`), absent on CI, and
a test that self-skips when it is missing would be green on the one host
that never has it. Everything below is stdlib, so it runs everywhere the
rest of the suite does.
"""

import glob
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULE_PATH = REPO_ROOT / ".opencodereview" / "rule.json"

# The only two keys OCR's unmarshaller reads from an entry, established by
# feeding it a wrong-typed value and reading which Go struct field it named
# (`ProjectRuleEntry.rules.path of type string`). Kept here so a rename in
# a future OCR release shows up as this test failing rather than as every
# rule silently ceasing to match.
ENTRY_FIELDS = ("path", "rule")


def _rules():
    return json.loads(RULE_PATH.read_text(encoding="utf-8"))


def _matches(pattern):
    """Paths in the working tree matching one OCR path glob."""
    return glob.glob(pattern, root_dir=str(REPO_ROOT), recursive=True)


def test_the_rule_file_is_valid_json_with_the_two_top_level_keys():
    data = _rules()
    assert isinstance(data["rules"], list) and data["rules"]
    assert isinstance(data["exclude"], list) and data["exclude"]


def test_every_entry_carries_exactly_the_fields_ocr_reads():
    for entry in _rules()["rules"]:
        for field in ENTRY_FIELDS:
            assert isinstance(entry.get(field), str) and entry[field], (
                f"entry {entry.get('name', entry)!r} is missing a usable "
                f"{field!r}. OCR reads only {ENTRY_FIELDS} and ignores "
                "everything else without complaining, so a typo here "
                "disables the rule rather than failing."
            )


def test_no_rule_glob_matches_nothing():
    """The failure this file exists for: an orphaned glob is invisible."""
    orphaned = [
        entry["path"] for entry in _rules()["rules"] if not _matches(entry["path"])
    ]
    assert not orphaned, (
        "these .opencodereview/rule.json path globs match no file in the "
        f"working tree, so OCR reviews those files with its generic built-in "
        f"rule instead: {orphaned}"
    )


def test_the_globs_reach_both_the_source_and_the_test_tree():
    """Non-vacuity for this test itself.

    `test_no_rule_glob_matches_nothing` passes vacuously if `rules` is
    ever emptied, and passes for the wrong reason if every glob is a
    broad `**` that matches something regardless. Naming one file per
    tree that must be covered is what pins it -- and the test tree is
    named because bringing `tests/` into scope is why this file was added.
    """
    covered = {path for entry in _rules()["rules"] for path in _matches(entry["path"])}
    for wanted in ("src/sync.py", "tests/conftest.py", "scripts/release.py",
                   "bench/repro_check.py", "docs/CODE-STANDARDS.md",
                   "DEVELOPER-AGENTS.md"):
        assert wanted in covered, f"no rule covers {wanted}"


def test_the_source_rule_states_the_citekey_invariant():
    """The one rule that may never be dropped from the review.

    CLAUDE.md and SOUL.md make fabricated citekeys the failure this whole
    project exists to prevent. A reviewer that does not know to look for
    one is worse than no reviewer, because it reports clean.
    """
    src_rule = next(e for e in _rules()["rules"] if e["path"] == "src/**/*.py")
    assert "citekey" in src_rule["rule"]
    assert "bib_reader" in src_rule["rule"]


def test_per_host_and_generated_trees_are_excluded():
    """`content/` is the user's own work and `papers/` is their personal
    bibliography export -- neither is this repository's code, and sending
    either to a third-party LLM endpoint for review is not something a
    review tool should do by default."""
    excluded = set(_rules()["exclude"])
    for tree in ("content/**", "papers/**", "site/**"):
        assert tree in excluded
