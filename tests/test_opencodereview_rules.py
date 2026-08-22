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
per-host (`npm i -g @alibaba-group/open-code-review@1.9.9`), absent on
CI, and a test that self-skips when it is missing would be green on the
one host that never has it. Everything below is stdlib, so it runs
everywhere the rest of the suite does.
"""

import glob
import json
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
RULE_PATH = REPO_ROOT / ".opencodereview" / "rule.json"

# The only two keys OCR's unmarshaller reads from an entry, established
# against open-code-review v1.9.9 by feeding it a wrong-typed value and
# reading which Go struct field it named (`ProjectRuleEntry.rules.path of
# type string`). This is the tripwire for a schema rename in a later OCR
# release: the next person bumping the pinned version above should read a
# red test here as the feature working, not as a bug in this file, and
# re-probe before assuming these two names still hold.
ENTRY_FIELDS = ("path", "rule")

# Extensions OCR will actually open. It reviews only what it recognises as
# code and drops the rest *before* rules are consulted, reporting
# `exclude_reason: unsupported_ext` in `ocr delegate preview --format json`.
# This *is* that command's answer, transcribed rather than shelled out to
# at test time (see "Deliberately does not invoke `ocr`" above): run
# against open-code-review v1.9.9, .py, .json, .yml/.yaml, .sh and .toml
# came back reviewable; .md, .txt, .rst and .cfg came back excluded. A
# later OCR release can widen or narrow this set silently; re-probe on
# upgrade rather than assuming it still holds.
#
# This is the list that matters, and it is not the list `ocr rules check`
# answers from -- that command is a rule *lookup* and will happily resolve
# a rule for a file OCR would never review. An earlier revision of the rule
# file carried two Markdown rules that passed every check here and could
# not fire.
REVIEWABLE_EXTENSIONS = {".py", ".json", ".json5", ".yml", ".yaml", ".sh", ".toml"}


def _rules():
    return json.loads(RULE_PATH.read_text(encoding="utf-8"))


def _matches(pattern):
    """Repo-relative POSIX paths in the working tree matching one OCR glob.

    `as_posix()` rather than what `glob` returns: on the Windows CI leg it
    yields `src\\sync.py`, which never equals the `chitragupta/sync.py` the
    assertions below name -- and OCR's own globs are POSIX-spelled
    regardless of host. Caught by that leg after passing on Linux, which
    is the same asymmetry `tests/test_code_standards_scan.py` pins
    `encoding="utf-8"` for.
    """
    return [
        Path(match).as_posix()
        for match in glob.glob(pattern, root_dir=str(REPO_ROOT), recursive=True)
    ]


def test_the_rule_file_is_valid_json_with_the_two_top_level_keys():
    data = _rules()
    assert isinstance(data["rules"], list)
    assert data["rules"]
    assert isinstance(data["exclude"], list)
    assert data["exclude"]


def test_every_entry_carries_exactly_the_fields_ocr_reads():
    for entry in _rules()["rules"]:
        for field in ENTRY_FIELDS:
            problem = (
                f"entry {entry.get('name', entry)!r} is missing a usable "
                f"{field!r}. OCR reads only {ENTRY_FIELDS} and ignores "
                "everything else without complaining, so a typo here "
                "disables the rule rather than failing."
            )
            assert isinstance(entry.get(field), str), problem
            assert entry[field], problem


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


def test_the_globs_reach_every_tree_a_rule_claims():
    """Non-vacuity for this test itself.

    `test_no_rule_glob_matches_nothing` passes vacuously if `rules` is
    ever emptied, and passes for the wrong reason if every glob is a
    broad `**` that matches something regardless. Naming one file per
    tree is what pins it -- and the test tree is named because bringing
    `tests/` into scope is why this file was added.

    Every path here is a file OCR will actually review. A Markdown file
    would be the wrong thing to assert: see `REVIEWABLE_EXTENSIONS`.
    """
    covered = {path for entry in _rules()["rules"] for path in _matches(entry["path"])}
    for wanted in ("chitragupta/sync.py", "tests/conftest.py", "scripts/release.py",
                   "scripts/install_full_pipeline.sh", "bench/repro_check.py",
                   ".github/workflows/ci.yml"):
        assert wanted in covered, f"no rule covers {wanted}"


def test_no_rule_targets_an_extension_ocr_will_not_review():
    """The failure the Markdown rules were: a rule that cannot ever fire.

    OCR drops an unsupported extension before rules are consulted, so
    such a rule resolves cleanly under `ocr rules check`, reviews
    nothing, and reports no error -- while implying this repository's
    prose is covered. Worse than having no rule at all.

    Only globs that *name* an extension are checked. A directory sweep
    like `.github/**` legitimately matches both `ci.yml` (reviewed) and a
    Markdown template (not), and is not making a claim about either.
    """
    unreviewable = [
        entry["path"]
        for entry in _rules()["rules"]
        if (suffix := PurePosixPath(entry["path"]).suffix)
        and suffix not in REVIEWABLE_EXTENSIONS
    ]
    assert not unreviewable, (
        "these rules target extensions OCR reports as `unsupported_ext` and "
        f"never opens, so they can never fire: {unreviewable}. Verify with "
        "`ocr delegate preview --format json`, not `ocr rules check`."
    )


def test_every_rule_matches_at_least_one_file_ocr_will_actually_open():
    """The reachability claim itself, per rule rather than pooled.

    The two tests above are necessary but not sufficient together:
    `test_the_globs_reach_every_tree_a_rule_claims` pools all five globs
    before checking six hardcoded paths, so it cannot say *which* rule
    covers a directory sweep like `scripts/**` or `.github/**`, and
    `test_no_rule_targets_an_extension_ocr_will_not_review` only inspects
    globs that literally name a suffix, so it says nothing about those
    same two sweeps. Neither, alone or together, asserts "this specific
    rule matches a reviewable file" for every entry -- which is the actual
    claim `.opencodereview/rule.json` makes by existing. This test reads
    `REVIEWABLE_EXTENSIONS`, i.e. `ocr delegate preview --format json`'s
    own answer on the pinned v1.9.9 binary, never `ocr rules check`.
    """
    unreachable = [
        entry["path"]
        for entry in _rules()["rules"]
        if not any(
            PurePosixPath(match).suffix in REVIEWABLE_EXTENSIONS
            for match in _matches(entry["path"])
        )
    ]
    assert not unreachable, (
        "these rules match no file OCR will actually open, so they can "
        f"never fire despite passing `ocr rules check`: {unreachable}"
    )


def test_the_source_rule_states_the_citekey_invariant():
    """The one rule that may never be dropped from the review.

    CLAUDE.md and SOUL.md make fabricated citekeys the failure this whole
    project exists to prevent. A reviewer that does not know to look for
    one is worse than no reviewer, because it reports clean.
    """
    src_rule = next(e for e in _rules()["rules"] if e["path"] == "chitragupta/**/*.py")
    assert "citekey" in src_rule["rule"]
    assert "bib_reader" in src_rule["rule"]


def test_the_users_own_work_is_excluded():
    """`content/` is the user's drafts and corpus, `papers/` their personal
    bibliography export. Neither is this repository's code, and shipping
    either to a third-party LLM endpoint because a review tool swept the
    directory is the one thing this file must not allow.

    Only those two are pinned. The rest of `exclude` is housekeeping --
    build output, lockfiles, vendored CSL -- and a future maintainer
    dropping one of those is making a choice, not causing a defect.
    """
    excluded = set(_rules()["exclude"])
    for tree in ("content/**", "papers/**"):
        assert tree in excluded, (
            f"{tree} must stay excluded: it is the user's own work, not "
            "this repository's code."
        )
