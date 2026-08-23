"""`docs/TECHNICAL-DEBT.md` may not describe register entries that are no
longer there.

[Build order](../docs/CODE-STANDARDS.md#build-order) item 4 asks for a
doc-drift detector and is justified by one incident: `docs/DESIGN.md`
claiming "Three layers" against four, found by reading. TECHNICAL-DEBT.md's
own intro names a second and more specific shape -- its C1/C2 register
*counts* drifted to 26/13 against a real 10/11 until #228 caught it while
doing unrelated work. A reconciliation pass on 2026-08-18 found that same
shape twice more in one sitting: `chitragupta/sync.py::run` was split and delisted
in #178 on 2026-08-14, the day *after* this document was written, and its
"What to take first" list still named it as the second-highest-priority
open item four days later.

Every one of those is the same claim: **prose asserting something about
the current contents or size of `tests/test_code_standards_scan.py`'s
`LEGACY_LONG_FUNCTIONS`/`LEGACY_LONG_FILES`.** That claim has a
machine-readable source of truth, so it can be made binary. This file
makes it binary and nothing else.

## What this deliberately does not check, and why

**Not "every `chitragupta/*.py` token in the document."** That reading is
unimplementable and would be wrong if it were not: 3.2 named
`_executor_for` and 3.8 named `connect()` -- both were real debts,
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

import ast
import re
from pathlib import Path

import pytest

from test_code_standards_scan import LEGACY_LONG_FILES, LEGACY_LONG_FUNCTIONS

REPO_ROOT = Path(__file__).resolve().parent.parent
DEBT_DOC = REPO_ROOT / "docs" / "TECHNICAL-DEBT.md"
CODE_STANDARDS_DOC = REPO_ROOT / "docs" / "CODE-STANDARDS.md"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"
BENCH_README = REPO_ROOT / "bench" / "README.md"

# A register entry as the document writes one: `chitragupta/sync.py::run` for a
# C1 function, `chitragupta/dossier.py` for a C2 module, always in a code span.
_ENTRY_RE = re.compile(r"`(chitragupta/[\w./-]+\.py(?:::\w+)?)`")

# The two resolved-marker shapes, normalised by the 2026-08-18 pass so
# this has two to parse rather than free prose.
#
# A subsection's *heading* may keep describing the historical,
# pre-fix state -- `chitragupta/dossier.py`'s does, and `chitragupta/sync.py::run`'s does
# too -- because both are kept as the record of what a split was measured
# against. So the marker to read is the body's first non-blank line, never
# the heading text.
_RESOLVED_BODY_RE = re.compile(r"^\*\*Resolved\b")


# Headings carry an emoji prefix (`## 🧱 Tier 1: ...`), which sits between
# the `## ` this splits on and the text being matched. Stripped as "a
# leading run of non-ASCII plus its space" rather than as today's emoji,
# so changing which emoji a heading wears is a docs edit, not a test edit.
_HEADING_EMOJI_RE = re.compile(r"^[^\x00-\x7F]+\s+")


def _section(text: str, heading_prefix: str) -> str:
    """The `## `-level section starting with `heading_prefix`, to the next."""
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    matching = [p for p in parts if _HEADING_EMOJI_RE.sub("", p).startswith(heading_prefix)]
    assert len(matching) == 1, f"expected exactly one '## {heading_prefix}' section"
    return matching[0]


def _subject(text: str) -> str | None:
    """The *first* register entry named in `text`, or None.

    First rather than all, because what is being read is one claim about
    one entry, and everything after it is prose about that claim. Both
    resolved items in "What to take first" close with "See the
    `chitragupta/sync.py::run` subsection above" -- a cross-reference, not a
    second claim -- and an open item could as easily say "unlike
    `chitragupta/config.py`, which is fine". Scoring those against the register
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


@pytest.fixture(name="code_standards_doc")
def _code_standards_doc():
    return CODE_STANDARDS_DOC.read_text(encoding="utf-8")


@pytest.fixture(name="bench_readme")
def _bench_readme():
    return BENCH_README.read_text(encoding="utf-8")


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
    """Both checks above pass trivially on today's document, and since
    #294 they pass over *nothing*: the compaction moved all thirteen
    closed items into a one-row-each "Resolved" index, so Tier 1 has no
    subsections and "What to take first" has no `[Tier 1]` item left to
    read. `_all_claims` returns an empty list.

    That is the honest state of a register whose two named entries are
    both closed, and the parsers still have to work for the next one that
    opens. Three tests used to pin them against the real document -- that
    a Tier 1 heading, a `[Tier 1]` item, and both resolved markers were
    each still found. All three asserted the document carried claims it
    no longer carries, so they went with the sections; keeping them would
    have meant keeping a section purely to be parsed.

    What replaces them is the fixture suite below, which was always the
    stronger half: it pins that the parsers find a wrong claim and do not
    find a right one, against documents written here rather than against
    whatever the real one happens to say this month. The one thing a
    fixture cannot see -- the real document's section headings moving out
    from under `_section` -- is what the single test below covers.
    """

    def test_the_two_sections_the_parsers_read_are_still_there(self, debt_doc):
        """The shape check, and deliberately not a count.

        `_section` asserts there is exactly one `## Tier 1` and one `##
        What to take first`; renaming or duplicating either is the one
        way the parsers stop working that no fixture below can see, since
        the fixtures supply their own documents. Asserting *how many*
        claims the real document holds would be worse than useless: it is
        zero today, and the first person to open a legitimate Tier 1
        entry would meet a red suite telling them the document is wrong.
        """
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
    """Fixtures, because the real document is clean -- which is what the
    checks are for, and also what makes them impossible to trust without
    these."""

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
        """The shape item 4 of the real list actually has: one clause
        struck out and marked done inside an item that is not. Reading a
        mid-item `~~` as "resolved" would let the drift through wearing
        the marker of a fix, which is worse than not checking."""
        doc = _OPEN_ITEM_DOC.replace(
            "The largest module in the tree.",
            "~~1605 code lines.~~ **Done**, measured -- but not yet split.",
        )
        assert _missing_from_register(doc, *_REGISTERS) == ["chitragupta/gone.py"]

    def test_a_cross_reference_later_in_an_item_is_not_a_second_claim(self):
        """Both resolved items in the real list close with "See the
        `...` subsection", and an open one could as easily contrast
        itself with a module that is fine. Only the item's own subject --
        the first entry it names -- is held to the register."""
        doc = _OPEN_ITEM_DOC.replace(
            "The largest module in the tree.",
            "The largest module in the tree, unlike `chitragupta/absent.py`.",
        )
        assert _missing_from_register(doc, *_REGISTERS) == ["chitragupta/gone.py"]

    def test_a_take_first_item_not_tagged_tier_one_is_ignored(self):
        """3.3's `bench/` item is a real open debt that was never a
        register entry, and 3.2's `_executor_for` was another. An item
        naming a `chitragupta/` path without claiming C1/C2 membership
        must not be held to the register."""
        doc = _OPEN_ITEM_DOC.replace("[Tier 1]", "[3.2]")
        assert _missing_from_register(doc, *_REGISTERS) == []

    def test_a_stated_size_that_does_not_match_is_reported(self):
        assert _stated_sizes(_OPEN_HEADING_DOC) == (2, 1)
        assert _stated_sizes(_OPEN_HEADING_DOC) != (
            len(_REGISTERS[0]),
            len(_REGISTERS[1]),
        )

    def test_a_reworded_size_sentence_fails_loudly_rather_than_silently(self):
        """The failure mode a regex check has that a `len()` does not: if
        the sentence is rephrased past the pattern, the honest outcome is
        red, not a check that quietly stops running."""
        doc = _OPEN_HEADING_DOC.replace("**2 functions** over C1", "two functions over C1")
        with pytest.raises(AssertionError, match="no longer states its register sizes"):
            _stated_sizes(doc)


# --- #353: the other drift-prone claims the issue asked to pin --------
#
# Each is a "now" claim -- true of the tree today, re-measured rather
# than a frozen record of a past baseline -- the same shape
# `_stated_sizes` above already pins for the C1/C2 register sizes.
# `_regex_pin` is that shape made generic, so #348 (PACKAGING.md) and
# #345 (ARCHITECTURE.md) can reuse it instead of reinventing it. Two
# claims that were once pinned here no longer are, each for the same
# reason: the debt was closed outright rather than merely re-measured,
# so there is no longer a prose figure to drift. The noqa-marker count
# is #354's (adopted `ruff`, deleted the "inert markers" section --
# `RUF100` is now the mechanism that checks the suppressed set is the
# right one). The annotation ratio is #355's (annotated every gap,
# deleted the "Type annotations" section -- `tests/test_annotation_scan.py`
# ratchets the count directly against the tree instead). The bench
# self-check count moved rather than closed: #356 turned `bench/`'s
# exclusion into a stated decision and relocated the live count from
# `docs/TECHNICAL-DEBT.md` to `bench/README.md`'s self-check section --
# still a drift-prone claim, so it is still pinned here, just against
# the new document. A second, weaker prose pin for either remaining
# closed claim would be exactly the two-debt-lists problem the
# register warns against.


def _regex_pin(pattern: re.Pattern, text: str, what: str) -> tuple[str, ...]:
    """Search `pattern` in a whitespace-normalised copy of `text` and
    return its captured groups, failing loudly rather than returning
    nothing if the sentence has been reworded past the pattern -- the
    same guarantee `_stated_sizes` gives the register-size claim, made
    reusable for the claims below and for future documents."""
    match = pattern.search(" ".join(text.split()))
    assert match, (
        f"{what} no longer states this fact in the shape this test reads "
        f"({pattern.pattern!r}). Rewording it is fine; teach this pattern "
        "the new shape in the same change, or the check silently stops "
        "running."
    )
    return match.groups()


_LINT_TARGET_QUOTE_RE = re.compile(r"pylint --rcfile=\.pylintrc ([^`]+)`")

_COVERAGE_SOURCE_QUOTE_RE = re.compile(r"source = (\[[^\]]*\])")

_BENCH_SELF_CHECK_COUNT_RE = re.compile(r"(\d+) of the (\d+) scripts here")


def _ci_lint_target() -> str:
    """The path list `ci.yml`'s lint job actually passes to pylint, read
    from the workflow rather than typed -- the source of truth both
    dangling cross-references #353 fixed were checked against."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"run: pylint --rcfile=\.pylintrc (\S.*\S)\s*$", text, re.MULTILINE)
    assert match, "ci.yml no longer runs pylint in the shape this test reads"
    return match.group(1)


def _pyproject_coverage_source() -> list[str]:
    """`[tool.coverage.run].source`, read from `pyproject.toml` rather
    than typed."""
    text = PYPROJECT_TOML.read_text(encoding="utf-8")
    match = re.search(r"^source = (\[.*\])", text, re.MULTILINE)
    assert match, (
        "pyproject.toml no longer states [tool.coverage.run].source in the shape this test reads"
    )
    return ast.literal_eval(match.group(1))


def _bench_self_check_counts() -> tuple[int, int]:
    """(scripts with a self_check(), total bench/*.py scripts), mirroring
    `for f in bench/*.py; do grep -q "def self_check" $f || echo $f; done`."""
    paths = sorted((REPO_ROOT / "bench").glob("*.py"))
    with_check = sum(1 for p in paths if "def self_check" in p.read_text(encoding="utf-8"))
    return with_check, len(paths)


def _assert_lint_target_matches(doc_name: str, text: str, ci_target: str) -> None:
    """Every `pylint --rcfile=.pylintrc ...` quoted in `text` must name
    `ci_target` -- the check both dangling cross-references #353 fixed
    would have caught, and that catches the next rename too."""
    quoted = _LINT_TARGET_QUOTE_RE.findall(" ".join(text.split()))
    assert quoted, (
        f"{doc_name} no longer quotes the pylint invocation in the shape "
        "this test reads (`pylint --rcfile=.pylintrc ...`)"
    )
    assert all(target.strip() == ci_target for target in quoted), (
        f"{doc_name} quotes `pylint --rcfile=.pylintrc ...` with a target "
        f"that no longer matches ci.yml's `{ci_target}`. This is the "
        "dangling-reference shape #353 fixed twice already (.pylintrc's "
        "stale section number, docs/CODE-STANDARDS.md's stale `src`)."
    )


def _assert_coverage_source_matches(doc_name: str, text: str, pyproject_source: list[str]) -> None:
    quoted = _COVERAGE_SOURCE_QUOTE_RE.findall(text)
    assert quoted, (
        f"{doc_name} no longer quotes [tool.coverage.run].source in the "
        "shape this test reads (`source = [...]`)"
    )
    for raw in quoted:
        assert ast.literal_eval(raw) == pyproject_source, (
            f"{doc_name} quotes a coverage `source` list that no longer "
            f"matches pyproject.toml's {pyproject_source!r}."
        )


class TestTheOtherDriftProneClaimsArePinned:
    """Two of the four claims #353's own "What to build" list named are
    checked here (lint target, coverage source) -- the other two (the
    annotation ratio and the noqa marker count) are #355's and #354's
    now, not this file's. The bench self-check count, a third claim
    pinned here beyond #353's original four, is also checked here
    again, relocated by #356 from `docs/TECHNICAL-DEBT.md` to
    `bench/README.md`; see the comment above."""

    def test_the_quoted_lint_target_matches_ci_everywhere_it_appears(
        self, debt_doc, code_standards_doc
    ):
        ci_target = _ci_lint_target()
        _assert_lint_target_matches("docs/TECHNICAL-DEBT.md", debt_doc, ci_target)
        _assert_lint_target_matches("docs/CODE-STANDARDS.md", code_standards_doc, ci_target)

    def test_the_quoted_coverage_source_matches_pyproject(self, bench_readme):
        _assert_coverage_source_matches(
            "bench/README.md", bench_readme, _pyproject_coverage_source()
        )

    def test_the_bench_self_check_count_matches_the_tree(self, bench_readme):
        stated = tuple(
            int(n) for n in _regex_pin(_BENCH_SELF_CHECK_COUNT_RE, bench_readme, "bench/README.md")
        )
        assert stated == _bench_self_check_counts(), (
            "bench/README.md's self-check count no longer matches bench/*.py. "
            "Re-measure rather than editing the figure by hand."
        )


class TestTheNewPinsFailLoudlyWhenReworded:
    """The same guarantee
    `test_a_reworded_size_sentence_fails_loudly_rather_than_silently`
    pins for `_stated_sizes`, extended to the new patterns above: a pin
    that silently stops matching is worse than no pin."""

    def test_a_lint_target_no_longer_quoted_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer quotes the pylint invocation"):
            _assert_lint_target_matches(
                "the doc", "prose with no invocation quoted", "chitragupta scripts"
            )

    def test_a_lint_target_quoted_with_a_stale_value_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer matches ci.yml's"):
            _assert_lint_target_matches(
                "the doc", "`pylint --rcfile=.pylintrc src scripts`", "chitragupta scripts"
            )

    def test_a_coverage_source_no_longer_quoted_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer quotes"):
            _assert_coverage_source_matches(
                "the doc", "prose with no source list quoted", ["chitragupta"]
            )

    def test_a_coverage_source_quoted_with_a_stale_value_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer matches pyproject.toml's"):
            _assert_coverage_source_matches(
                "the doc", 'source = ["src", "scripts"]', ["chitragupta", "scripts"]
            )

    def test_a_reworded_bench_self_check_count_sentence_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer states this fact"):
            _regex_pin(
                _BENCH_SELF_CHECK_COUNT_RE, "20 scripts have one, out of 22 total.", "the doc"
            )
