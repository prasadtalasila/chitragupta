"""The vendored style and docs/WRITING-STANDARDS.md must name the same words.

§2 states the defect markers in prose, §9 restates them in a table, and
`assets/vale/styles/chitragupta/` encodes them for a machine. Three copies
of one list, which is exactly the drift 5.12.0 removed elsewhere by moving
HOUSE-STYLE.md's triage into §9 "so the two cannot drift into disagreeing
about the same rule."

Prose agreement is not enforceable by asking people to remember, and this
repository's standing answer to that is a pin rather than a policy --
tests/test_skill_verbatim_scan_step.py and test_code_standards_scan.py's
register both exist for the same reason. §2 remains the normative source;
this makes a divergence a failing build rather than a silent one.

A text scan, deliberately: what the rules *match* is Vale's business and
is covered by the bench entry. This pins only that the two lists agree.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STANDARD = REPO_ROOT / "docs" / "WRITING-STANDARDS.md"
STYLES = REPO_ROOT / "assets" / "vale" / "styles" / "chitragupta"


def markers_in_the_standard() -> set[str]:
    """The words §2 names, read out of its own sentence.

    Parsed rather than restated here, so this test cannot drift from the
    document in the very way it exists to prevent.
    """
    text = STANDARD.read_text(encoding="utf-8")
    sentence = re.search(r"Treat \*\*(.+?)\*\* as\s+defect markers", text, re.S)
    assert sentence, (
        "WRITING-STANDARDS.md §2 no longer states its marker list in the form this test reads"
    )
    return {word.lower() for word in re.findall(r'"([^"]+)"', sentence.group(1))}


def tokens_in(rule_file: str) -> set[str]:
    """The `tokens:` list of a Vale rule, without a YAML dependency --
    these files are ours and their shape is fixed by the tests below."""
    lines = (STYLES / rule_file).read_text(encoding="utf-8").splitlines()
    start = lines.index("tokens:")
    tokens = set()
    for line in lines[start + 1 :]:
        if not line.startswith("  - "):
            break
        tokens.add(line[4:].strip().lower())
    return tokens


def test_the_vendored_style_names_exactly_the_markers_the_standard_does():
    """The union of the two rule files, because "just" is deliberately
    split out: §9 says the adverb and the adjective are not separable by
    string match, so it is reported at a lower level and never auto-fixed.
    Splitting it must not lose it."""
    assert tokens_in("DefectMarkers.yml") | tokens_in("Just.yml") == markers_in_the_standard()


def test_just_is_the_one_that_is_split_out():
    assert tokens_in("Just.yml") == {"just"}
    assert "just" not in tokens_in("DefectMarkers.yml")


def test_every_rule_cites_the_section_it_implements():
    """A finding a reader cannot trace back to a rule in the standard is a
    finding they have no way to judge."""
    for rule in STYLES.glob("*.yml"):
        message = rule.read_text(encoding="utf-8")
        assert "WRITING-STANDARDS.md" in message, f"{rule.name} names no source section"


def test_the_dialect_rules_are_the_ones_style_check_knows_about():
    """assets/ and chitragupta/style_check.py's DIALECT_RULES are a pair: a rule
    file with no entry there is never enabled, and an entry with no file
    makes Vale fail to start."""
    from chitragupta import style_check  # noqa: PLC0415 -- kept local so the scan above stays import-free

    on_disk = {f"chitragupta.{rule.stem}" for rule in STYLES.glob("Dialect*.yml")}
    assert on_disk == set(style_check._ALL_DIALECT_RULES)


def test_no_block_ignore_contains_a_comma():
    """Vale splits BlockIgnores on commas, so a regex containing one --
    `\\n{2,}` is the natural way to write "a blank line" -- fails to parse
    and Vale refuses to run. Found the hard way; pinned so it stays found.
    """
    config = (REPO_ROOT / "assets" / "vale" / "vale.ini").read_text(encoding="utf-8")
    block = re.search(r"^BlockIgnores = (.+?)(?=\n[A-Z]|\n\n)", config, re.S | re.M)
    assert block
    for pattern in re.split(r",\s*\\?\n\s*", block.group(1)):
        assert "{" not in pattern or "," not in pattern.split("{", 1)[1].split("}", 1)[0]


def test_latex_is_mapped_to_a_markup_format():
    """Without `[formats] tex = md`, BlockIgnores is silently not applied
    to a .tex fragment and every word inside a verbatim block is reported.
    thesis-chapter-writer emits .tex, so this line is load-bearing."""
    config = (REPO_ROOT / "assets" / "vale" / "vale.ini").read_text(encoding="utf-8")
    assert re.search(r"^\[formats\]\s*\ntex = md", config, re.M)
