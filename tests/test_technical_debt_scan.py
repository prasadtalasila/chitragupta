"""`docs/TECHNICAL-DEBT.md` may not describe register entries that are no
longer there.

[Build order](../docs/CODE-STANDARDS.md#build-order) item 4 asks for a
doc-drift detector and is justified by one incident: `docs/DESIGN.md`
claiming "Three layers" against four, found by reading. TECHNICAL-DEBT.md's
own intro names a second and more specific shape -- its C1/C2 register
*counts* drifted to 26/13 against a real 10/11 until #228 caught it while
doing unrelated work. A reconciliation pass on 2026-08-18 found that same
shape twice more in one sitting: `src/sync.py::run` was split and delisted
in #178 on 2026-08-14, the day *after* this document was written, and its
"What to take first" list still named it as the second-highest-priority
open item four days later.

Every one of those is the same claim: **prose asserting something about
the current contents or size of `tests/test_code_standards_scan.py`'s
`LEGACY_LONG_FUNCTIONS`/`LEGACY_LONG_FILES`.** That claim has a
machine-readable source of truth, so it can be made binary. This file
makes it binary and nothing else.

## What this deliberately does not check, and why

**Not "every `src/*.py` token in the document."** That reading is
unimplementable and would be wrong if it were not: 3.2 names
`_executor_for` and 3.8 names `connect()`, both real open debts that are
legitimately *not* on C1/C2 and never claimed to be. The issue's own
phrasing is "the register **it claims to belong to**", so the scope here
is the two places where the document makes that claim -- a Tier 1
subsection heading, and a `[Tier 1]`-tagged item in "What to take first".

**Not free-standing factual claims.** `docs/DESIGN.md`'s layer count and
Tier 3.1's call-site count have no register behind them, so there is
nothing to check them against, and
[R3](../docs/AUTO-IMPROVEMENT.md#the-requirements) is exactly why no
general prose-accuracy score is attempted instead. Those stay a human
reconciliation pass's job.

**Not this document's status as a non-gate.** It says of itself that it
"is **not** a gate and gains no test". That is about the *debt* not
failing a build -- an entry here going unpaid must never turn red. This
test cannot fail on unpaid debt; it fails only when the document
*describes* the register wrongly, which is a factual error in prose, not
an outstanding cost.
"""

import re
from pathlib import Path

import pytest

from test_code_standards_scan import LEGACY_LONG_FILES, LEGACY_LONG_FUNCTIONS

REPO_ROOT = Path(__file__).resolve().parent.parent
DEBT_DOC = REPO_ROOT / "docs" / "TECHNICAL-DEBT.md"

# A register entry as the document writes one: `src/sync.py::run` for a
# C1 function, `src/dossier.py` for a C2 module, always in a code span.
_ENTRY_RE = re.compile(r"`(src/[\w./-]+\.py(?:::\w+)?)`")

# The two resolved-marker shapes, normalised by the 2026-08-18 pass so
# this has two to parse rather than free prose.
#
# A subsection's *heading* may keep describing the historical,
# pre-fix state -- `src/dossier.py`'s does, and `src/sync.py::run`'s does
# too -- because both are kept as the record of what a split was measured
# against. So the marker to read is the body's first non-blank line, never
# the heading text.
_RESOLVED_BODY_RE = re.compile(r"^\*\*Resolved\b")


def _section(text: str, heading_prefix: str) -> str:
    """The `## `-level section starting with `heading_prefix`, to the next."""
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    matching = [p for p in parts if p.startswith(heading_prefix)]
    assert len(matching) == 1, f"expected exactly one '## {heading_prefix}' section"
    return matching[0]


def _subject(text: str) -> str | None:
    """The *first* register entry named in `text`, or None.

    First rather than all, because what is being read is one claim about
    one entry, and everything after it is prose about that claim. Both
    resolved items in "What to take first" close with "See the
    `src/sync.py::run` subsection above" -- a cross-reference, not a
    second claim -- and an open item could as easily say "unlike
    `src/config.py`, which is fine". Scoring those against the register
    would report a module as drifted debt for being mentioned.
    """
    match = _ENTRY_RE.search(text)
    return match.group(1) if match else None


def _tier_one_claims(text: str) -> list[tuple[str, bool]]:
    """`(entry, is_resolved)` for every Tier 1 subsection heading."""
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
    """`(entry, is_resolved)` for every `[Tier 1]` item in "What to take
    first".

    Its resolved shape is the other one: the item *wrapped* in `~~...~~`
    and followed by `**Done**`.

    All three of those conditions are load-bearing. `**Done**` alone
    would match a sentence merely mentioning another item. A
    strikethrough anywhere in the item is not enough either, because
    that is also how the list marks *part* of an item done -- item 4
    strikes out its own measurement while the item itself stayed open
    for a while, so reading a mid-item `~~` as "resolved" would let
    exactly the drift this file exists for through, wearing the marker
    of a fix. Hence `startswith`, not `in`.
    """
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
    """Entries named as *open* debt that their register no longer holds.

    `::` decides which register a name claims to belong to -- a function
    is C1's, a bare module path is C2's -- which is the document's own
    notation, not one invented here.
    """
    out = []
    for entry, resolved in _all_claims(text):
        if resolved:
            continue
        register = functions if "::" in entry else files
        if entry not in register:
            out.append(entry)
    return out


# "freezes **10 functions** over C1 (25 statements) and **11 modules**
# over C2 (250 code lines)" -- matched over whitespace-normalised text,
# because the sentence line-wraps and the wrap point moves with any edit.
_SIZES_RE = re.compile(r"\*\*(\d+) functions\*\* over C1 .*?\*\*(\d+) modules\*\* over C2")


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
    # encoding="utf-8" explicitly: without it read_text uses the locale
    # codec, which is cp1252 on CI's Windows leg, and this document is
    # full of em dashes.
    return DEBT_DOC.read_text(encoding="utf-8")


class TestTheDocumentDescribesTheRegisterCorrectly:
    """The two checks, against the real document."""

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
    """Both checks above pass trivially on today's document -- every Tier 1
    entry is resolved, so the membership check has nothing to look at.

    That is the normal state and not a problem, but it means a parser that
    quietly stopped matching anything (a reworded heading, a renumbered
    list) would look identical to a clean run, forever. These pin that the
    parser still finds the document's claims; the fixtures below pin that
    finding one wrong actually fails.
    """

    def test_the_tier_one_headings_are_still_parsed(self, debt_doc):
        assert _tier_one_claims(debt_doc), (
            "no register entry found in any Tier 1 subsection heading -- the "
            "headings were reworded, or the section was renamed"
        )

    def test_the_take_first_items_are_still_parsed(self, debt_doc):
        assert _take_first_claims(debt_doc), (
            "no register entry found in any '[Tier 1]' item of 'What to take "
            "first' -- the tag or the list numbering changed"
        )

    def test_the_two_resolved_shapes_are_both_still_in_use(self, debt_doc):
        """If nothing were marked resolved, `_missing_from_register` would
        be checking every entry and the suite would be red -- so this
        cannot fail silently. It is here to say which shape is load-bearing
        where, since the two parsers read different markers."""
        assert any(resolved for _, resolved in _tier_one_claims(debt_doc))
        assert any(resolved for _, resolved in _take_first_claims(debt_doc))


_OPEN_HEADING_DOC = """\
## Tier 1: the debt the ratchet already holds

Freezes **2 functions** over C1 (25 statements) and **1 modules** over C2
(250 code lines).

### `src/gone.py::vanished` -- 99 statements

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

1. **[Tier 1] `src/gone.py`.** The largest module in the tree.
"""

_RESOLVED_ITEM_DOC = _OPEN_ITEM_DOC.replace(
    "1. **[Tier 1] `src/gone.py`.** The largest module in the tree.",
    "1. ~~**[Tier 1] `src/gone.py`.** The largest module in the tree.~~ "
    "**Done**, in #1.",
)

_REGISTERS = ({"src/kept.py::held"}, {"src/kept.py"})


class TestTheChecksActuallyFire:
    """Fixtures, because the real document is clean -- which is what the
    checks are for, and also what makes them impossible to trust without
    these."""

    def test_an_open_heading_naming_a_delisted_function_is_reported(self):
        assert _missing_from_register(_OPEN_HEADING_DOC, *_REGISTERS) == [
            "src/gone.py::vanished"
        ]

    def test_the_same_heading_marked_resolved_is_not(self):
        assert _missing_from_register(_RESOLVED_HEADING_DOC, *_REGISTERS) == []

    def test_an_open_take_first_item_naming_a_delisted_module_is_reported(self):
        assert _missing_from_register(_OPEN_ITEM_DOC, *_REGISTERS) == ["src/gone.py"]

    def test_the_same_item_struck_through_and_done_is_not(self):
        assert _missing_from_register(_RESOLVED_ITEM_DOC, *_REGISTERS) == []

    def test_a_partly_struck_through_item_is_still_open(self):
        """The shape item 4 of the real list actually has: one clause
        struck out and marked done inside an item that is not. Reading a
        mid-item `~~` as "resolved" would let the drift through wearing
        the marker of a fix, which is worse than not checking."""
        doc = _OPEN_ITEM_DOC.replace(
            "The largest module in the tree.",
            "~~1605 code lines.~~ **Done**, measured -- but not yet split.",
        )
        assert _missing_from_register(doc, *_REGISTERS) == ["src/gone.py"]

    def test_a_cross_reference_later_in_an_item_is_not_a_second_claim(self):
        """Both resolved items in the real list close with "See the
        `...` subsection", and an open one could as easily contrast
        itself with a module that is fine. Only the item's own subject --
        the first entry it names -- is held to the register."""
        doc = _OPEN_ITEM_DOC.replace(
            "The largest module in the tree.",
            "The largest module in the tree, unlike `src/absent.py`.",
        )
        assert _missing_from_register(doc, *_REGISTERS) == ["src/gone.py"]

    def test_a_take_first_item_not_tagged_tier_one_is_ignored(self):
        """3.2's `_executor_for` and 3.8's `connect()` are real open debts
        that were never register entries. An item naming a `src/` path
        without claiming C1/C2 membership must not be held to the
        register."""
        doc = _OPEN_ITEM_DOC.replace("[Tier 1]", "[3.2]")
        assert _missing_from_register(doc, *_REGISTERS) == []

    def test_a_stated_size_that_does_not_match_is_reported(self):
        assert _stated_sizes(_OPEN_HEADING_DOC) == (2, 1)
        assert _stated_sizes(_OPEN_HEADING_DOC) != (
            len(_REGISTERS[0]), len(_REGISTERS[1]),
        )

    def test_a_reworded_size_sentence_fails_loudly_rather_than_silently(self):
        """The failure mode a regex check has that a `len()` does not: if
        the sentence is rephrased past the pattern, the honest outcome is
        red, not a check that quietly stops running."""
        doc = _OPEN_HEADING_DOC.replace("**2 functions** over C1", "two functions over C1")
        with pytest.raises(AssertionError, match="no longer states its register sizes"):
            _stated_sizes(doc)
