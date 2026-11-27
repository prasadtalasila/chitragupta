import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STANDARD = REPO_ROOT / "docs" / "WRITING-STANDARDS.md"
STYLES = REPO_ROOT / "assets" / "vale" / "styles" / "chitragupta"


def markers_in_the_standard() -> set[str]:
    text = STANDARD.read_text(encoding="utf-8")
    sentence = re.search(r"Treat \*\*(.+?)\*\* as\s+defect markers", text, re.S)
    assert sentence, (
        "WRITING-STANDARDS.md §2 no longer states its marker list in the form this test reads"
    )
    return {word.lower() for word in re.findall(r'"([^"]+)"', sentence.group(1))}


def tokens_in(rule_file: str) -> set[str]:
    lines = (STYLES / rule_file).read_text(encoding="utf-8").splitlines()
    start = lines.index("tokens:")
    tokens = set()
    for line in lines[start + 1 :]:
        if not line.startswith("  - "):
            break
        tokens.add(line[4:].strip().lower())
    return tokens


def test_the_vendored_style_names_exactly_the_markers_the_standard_does():
    assert tokens_in("DefectMarkers.yml") | tokens_in("Just.yml") == markers_in_the_standard()


def test_just_is_the_one_that_is_split_out():
    assert tokens_in("Just.yml") == {"just"}
    assert "just" not in tokens_in("DefectMarkers.yml")


def test_every_rule_cites_the_section_it_implements():
    for rule in STYLES.glob("*.yml"):
        message = rule.read_text(encoding="utf-8")
        assert "WRITING-STANDARDS.md" in message, f"{rule.name} names no source section"


def test_the_dialect_rules_are_the_ones_style_check_knows_about():
    from chitragupta import style_rules

    on_disk = {f"chitragupta.{rule.stem}" for rule in STYLES.glob("Dialect*.yml")}
    assert on_disk == set(style_rules._ALL_DIALECT_RULES)


def test_no_block_ignore_contains_a_comma():
    config = (REPO_ROOT / "assets" / "vale" / "vale.ini").read_text(encoding="utf-8")
    block = re.search(r"^BlockIgnores = (.+?)(?=\n[A-Z]|\n\n)", config, re.S | re.M)
    assert block
    for pattern in re.split(r",\s*\\?\n\s*", block.group(1)):
        assert "{" not in pattern or "," not in pattern.split("{", 1)[1].split("}", 1)[0]


def test_latex_is_mapped_to_a_markup_format():
    config = (REPO_ROOT / "assets" / "vale" / "vale.ini").read_text(encoding="utf-8")
    assert re.search(r"^\[formats\]\s*\ntex = md", config, re.M)
