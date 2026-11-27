import re
from pathlib import Path

import pytest

from test_code_standards_scan import LEGACY_LONG_FILES, LEGACY_LONG_FUNCTIONS

REPO_ROOT = Path(__file__).resolve().parent.parent
DEBT_DOC = REPO_ROOT / "docs" / "TECHNICAL-DEBT.md"

_ENTRY_RE = re.compile(r"`(chitragupta/[\w./-]+\.py(?:::\w+)?)`")

_RESOLVED_BODY_RE = re.compile(r"^\*\*Resolved\b")


_HEADING_EMOJI_RE = re.compile(r"^[^\x00-\x7F]+\s+")


def _section(text: str, heading_prefix: str) -> str:
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    matching = [p for p in parts if _HEADING_EMOJI_RE.sub("", p).startswith(heading_prefix)]
    assert len(matching) == 1, f"expected exactly one '## {heading_prefix}' section"
    return matching[0]


def _subject(text: str) -> str | None:
    match = _ENTRY_RE.search(text)
    return match.group(1) if match else None


def _tier_one_claims(text: str) -> list[tuple[str, bool]]:
    claims = []
    for block in re.split(r"^### ", _section(text, "Tier 1"), flags=re.MULTILINE)[1:]:
        heading, _, body = block.partition("\n")
        entry = _subject(heading)
        if entry is None:
            continue
        first_line = next((ln for ln in body.splitlines() if ln.strip()), "")
        claims.append((entry, bool(_RESOLVED_BODY_RE.match(first_line))))
    return claims


def _take_first_claims(text: str) -> list[tuple[str, bool]]:
    claims = []
    section = _section(text, "What to take first")
    for item in re.split(r"^\d+\. ", section, flags=re.MULTILINE)[1:]:
        entry = _subject(item) if "[Tier 1]" in item else None
        if entry is None:
            continue
        claims.append((entry, item.startswith("~~") and "**Done**" in item))
    return claims


def _all_claims(text: str) -> list[tuple[str, bool]]:
    return _tier_one_claims(text) + _take_first_claims(text)


def _missing_from_register(text: str, functions: set, files: set) -> list[str]:
    out = []
    for entry, resolved in _all_claims(text):
        if resolved:
            continue
        register = functions if "::" in entry else files
        if entry not in register:
            out.append(entry)
    return out


_SIZES_RE = re.compile(r"\*\*(\d+) functions\*\* over C1 .*?\*\*(\d+) modules?\*\* over C2")


def _stated_sizes(text: str) -> tuple[int, int]:
    match = _SIZES_RE.search(" ".join(text.split()))
    assert match, (
        "docs/TECHNICAL-DEBT.md no longer states its register sizes in the "
        "shape this test reads ('**N functions** over C1 ... **M modules** "
        "over C2'). Rewording it is fine; teach this pattern the new shape "
        "in the same change, or the check silently stops running."
    )
    return int(match.group(1)), int(match.group(2))


@pytest.fixture(name="debt_doc")
def _debt_doc():
    return DEBT_DOC.read_text(encoding="utf-8")


class TestTheDocumentDescribesTheRegisterCorrectly:
    def test_no_entry_named_as_open_has_left_its_register(self, debt_doc):
        missing = _missing_from_register(debt_doc, LEGACY_LONG_FUNCTIONS, LEGACY_LONG_FILES)
        assert not missing, (
            "docs/TECHNICAL-DEBT.md names these as currently-open register debt, "
            "but tests/test_code_standards_scan.py no longer lists them:"
            + "".join(f"\n  {name}" for name in missing)
            + "\n\nThe register is the authority. If the debt was paid, mark the "
            "entry resolved -- '**Resolved' as the first line of its Tier 1 "
            "subsection body, or '~~...~~ **Done**' for a 'What to take first' "
            "item -- rather than deleting the section, which the document keeps "
            "as the record of what a split was measured against."
        )

    def test_the_stated_register_sizes_match_the_registers(self, debt_doc):
        stated = _stated_sizes(debt_doc)
        actual = (len(LEGACY_LONG_FUNCTIONS), len(LEGACY_LONG_FILES))
        assert stated == actual, (
            "docs/TECHNICAL-DEBT.md's Tier 1 intro states "
            f"{stated[0]} functions over C1 and {stated[1]} modules over C2. "
            f"The registers hold {actual[0]} and {actual[1]}. This is the exact "
            "drift #228 found at 26/13 against a real 10/11."
        )


class TestTheScanIsNotVacuous:
    def test_the_two_sections_the_parsers_read_are_still_there(self, debt_doc):
        assert _section(debt_doc, "Tier 1")
        assert _section(debt_doc, "What to take first")


_OPEN_HEADING_DOC = """\
## Tier 1: the debt the ratchet already holds

Freezes **2 functions** over C1 (25 statements) and **1 modules** over C2
(250 code lines).

### `chitragupta/gone.py::vanished` -- 99 statements

Still the worst thing in the tree.

## What to take first

1. **[3.1] Something else.** Unrelated.
"""

_RESOLVED_HEADING_DOC = _OPEN_HEADING_DOC.replace(
    "Still the worst thing in the tree.",
    "**Resolved in #1.** Kept as the record of what the split measured.",
)

_OPEN_ITEM_DOC = """\
## Tier 1: the debt the ratchet already holds

Freezes **2 functions** over C1 (25 statements) and **1 modules** over C2
(250 code lines).

## What to take first

1. **[Tier 1] `chitragupta/gone.py`.** The largest module in the tree.
"""

_RESOLVED_ITEM_DOC = _OPEN_ITEM_DOC.replace(
    "1. **[Tier 1] `chitragupta/gone.py`.** The largest module in the tree.",
    "1. ~~**[Tier 1] `chitragupta/gone.py`.** The largest module in the tree.~~ **Done**, in #1.",
)

_REGISTERS = ({"chitragupta/kept.py::held"}, {"chitragupta/kept.py"})


class TestTheChecksActuallyFire:
    def test_an_open_heading_naming_a_delisted_function_is_reported(self):
        assert _missing_from_register(_OPEN_HEADING_DOC, *_REGISTERS) == [
            "chitragupta/gone.py::vanished"
        ]

    def test_the_same_heading_marked_resolved_is_not(self):
        assert _missing_from_register(_RESOLVED_HEADING_DOC, *_REGISTERS) == []

    def test_an_open_take_first_item_naming_a_delisted_module_is_reported(self):
        assert _missing_from_register(_OPEN_ITEM_DOC, *_REGISTERS) == ["chitragupta/gone.py"]

    def test_the_same_item_struck_through_and_done_is_not(self):
        assert _missing_from_register(_RESOLVED_ITEM_DOC, *_REGISTERS) == []

    def test_a_partly_struck_through_item_is_still_open(self):
        doc = _OPEN_ITEM_DOC.replace(
            "The largest module in the tree.",
            "~~1605 code lines.~~ **Done**, measured -- but not yet split.",
        )
        assert _missing_from_register(doc, *_REGISTERS) == ["chitragupta/gone.py"]

    def test_a_cross_reference_later_in_an_item_is_not_a_second_claim(self):
        doc = _OPEN_ITEM_DOC.replace(
            "The largest module in the tree.",
            "The largest module in the tree, unlike `chitragupta/absent.py`.",
        )
        assert _missing_from_register(doc, *_REGISTERS) == ["chitragupta/gone.py"]

    def test_a_take_first_item_not_tagged_tier_one_is_ignored(self):
        doc = _OPEN_ITEM_DOC.replace("[Tier 1]", "[3.2]")
        assert _missing_from_register(doc, *_REGISTERS) == []

    def test_a_stated_size_that_does_not_match_is_reported(self):
        assert _stated_sizes(_OPEN_HEADING_DOC) == (2, 1)
        assert _stated_sizes(_OPEN_HEADING_DOC) != (
            len(_REGISTERS[0]),
            len(_REGISTERS[1]),
        )

    def test_a_reworded_size_sentence_fails_loudly_rather_than_silently(self):
        doc = _OPEN_HEADING_DOC.replace("**2 functions** over C1", "two functions over C1")
        with pytest.raises(AssertionError, match="no longer states its register sizes"):
            _stated_sizes(doc)
