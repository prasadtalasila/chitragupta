import glob
import json
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
RULE_PATH = REPO_ROOT / ".opencodereview" / "rule.json"

ENTRY_FIELDS = ("path", "rule")

REVIEWABLE_EXTENSIONS = {".py", ".json", ".json5", ".yml", ".yaml", ".sh", ".toml"}


def _rules():
    return json.loads(RULE_PATH.read_text(encoding="utf-8"))


def _matches(pattern):
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
    orphaned = [entry["path"] for entry in _rules()["rules"] if not _matches(entry["path"])]
    assert not orphaned, (
        "these .opencodereview/rule.json path globs match no file in the "
        f"working tree, so OCR reviews those files with its generic built-in "
        f"rule instead: {orphaned}"
    )


def test_the_globs_reach_every_tree_a_rule_claims():
    covered = {path for entry in _rules()["rules"] for path in _matches(entry["path"])}
    for wanted in (
        "chitragupta/sync.py",
        "tests/conftest.py",
        "scripts/release.py",
        "scripts/install_full_pipeline.sh",
        "bench/repro_check.py",
        ".github/workflows/ci.yml",
    ):
        assert wanted in covered, f"no rule covers {wanted}"


def test_no_rule_targets_an_extension_ocr_will_not_review():
    unreviewable = [
        entry["path"]
        for entry in _rules()["rules"]
        if (suffix := PurePosixPath(entry["path"]).suffix) and suffix not in REVIEWABLE_EXTENSIONS
    ]
    assert not unreviewable, (
        "these rules target extensions OCR reports as `unsupported_ext` and "
        f"never opens, so they can never fire: {unreviewable}. Verify with "
        "`ocr delegate preview --format json`, not `ocr rules check`."
    )


def test_every_rule_matches_at_least_one_file_ocr_will_actually_open():
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
    src_rule = next(e for e in _rules()["rules"] if e["path"] == "chitragupta/**/*.py")
    assert "citekey" in src_rule["rule"]
    assert "bib_reader" in src_rule["rule"]


def test_the_users_own_work_is_excluded():
    excluded = set(_rules()["exclude"])
    for tree in ("content/**", "papers/**"):
        assert tree in excluded, (
            f"{tree} must stay excluded: it is the user's own work, not this repository's code."
        )
