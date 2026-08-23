"""The two documents that describe the review layer, held to
`chitragupta/review/__init__.py`'s `AIDS` rather than to a reader's
memory (#345).

**Which document owns what changed**, and this test moved with it.
`docs/REVIEW.md` now owns the enumeration -- one entry per aid, and the
output contract naming every report -- because that is reader-facing
material. `docs/ARCHITECTURE.md`'s Layer 4 keeps only the boundary: the
count, and what the layer may not do. So the per-aid checks below run
against REVIEW.md, and ARCHITECTURE.md is checked for the count and for
still pointing at REVIEW.md rather than re-listing them.

That section drifted twice without anyone noticing: `synthesis` landed in
#341 and `figure` in #344, and neither updated it. The drift was
*partial*, which is what made it worth pinning rather than just fixing --
#341 updated the output-contract block but not the count or the table, so
one section contradicted itself.

`AIDS` is the single source of truth for what the aids are. This module
checks the prose against it, in the same spirit as
tests/test_packaging_command_table.py: a hand-maintained document,
cross-checked against the live structure, so adding a sixth aid fails
here instead of leaving a stale "five" behind.

**Scoped to one section on purpose.** The word "three" appears seventeen
times in this file and almost all of them are unrelated -- the drafting
layer's three commands, the three verbatim detection tiers, the three
enrichment stages. A check that swept the whole document for a number
would be a check nobody could keep green, so everything here reads the
Layer 4 section and nothing else.
"""

import re
from pathlib import Path

import pytest

from chitragupta import review

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"

# The spelled-out numbers this section uses. A range rather than a single
# expected value so the failure message can say what the prose *should*
# read, and so this does not have to change when an aid is added.
_NUMBER_WORDS = {
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
}

_SECTION_HEADING = "## Layer 4: the review layer"

# Headings carry an emoji prefix (`## 🔍 Layer 4: ...`), so the heading is
# matched as `## ` + an optional run of non-ASCII + the text, rather than
# as one literal. Written as a pattern, not as today's emoji, so changing
# which emoji a heading wears is a docs edit and not a test edit.
_SECTION_HEADING_RE = re.compile(
    r"^## (?:[^\x00-\x7F]+ )?" + re.escape(_SECTION_HEADING.removeprefix("## ")),
    re.MULTILINE,
)

REVIEW_MD = REPO_ROOT / "docs" / "REVIEW.md"
REVIEW_TEXT = REVIEW_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def section() -> str:
    """The Layer 4 section's own text, heading to next `## `.

    Sliced rather than read whole so that an unrelated "three" elsewhere
    in the document -- and there are many -- can never satisfy or break
    an assertion here.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    match = _SECTION_HEADING_RE.search(text)
    assert match, f"no heading matching {_SECTION_HEADING!r} in ARCHITECTURE.md"
    start, after = match.start(), match.end()
    following = re.search(r"^## ", text[after:], re.MULTILINE)
    end = after + following.start() if following else len(text)
    body = text[start:end]
    assert len(body) > 500, "Layer 4 section came back suspiciously short -- did the heading move?"
    return body


class TestTheSectionIsNotVacuous:
    """Guards against the whole module passing for the wrong reason.

    A slice that silently came back empty, or an `AIDS` that lost its
    contents, would make every assertion below trivially true.
    """

    def test_the_heading_is_present_and_unique(self):
        text = ARCHITECTURE.read_text(encoding="utf-8")
        assert len(_SECTION_HEADING_RE.findall(text)) == 1

    def test_there_are_aids_to_check(self):
        assert len(review.AIDS) >= 3

    def test_the_section_is_about_the_review_layer(self, section):
        # Non-vacuity only: a slice that silently came back as the wrong
        # section would make every assertion below meaningless.
        assert "chitragupta/review/" in section and "review layer" in section

    def test_review_md_exists_and_has_content(self):
        assert len(REVIEW_TEXT) > 2000


class TestTheStatedCount:
    def test_it_matches_the_number_of_aids(self, section):
        expected = _NUMBER_WORDS[len(review.AIDS)]
        assert f"{expected} aids behind one command" in section, (
            f"docs/ARCHITECTURE.md's Layer 4 should open with "
            f"'{expected} aids behind one command' -- chitragupta/review/__init__.py's "
            f"AIDS has {len(review.AIDS)} entries ({', '.join(sorted(review.AIDS))})."
        )

    def test_no_stale_count_survives_alongside_it(self, section):
        """The failure #345 actually described: a section that updated one
        number and not another, contradicting itself.
        """
        current = _NUMBER_WORDS[len(review.AIDS)]
        stale = [
            word
            for size, word in _NUMBER_WORDS.items()
            if size != len(review.AIDS) and f"{word} aids" in section
        ]
        assert not stale, f"Layer 4 says '{current} aids' and also {stale} -- one is wrong."


class TestEveryAidIsDocumented:
    """Now against docs/REVIEW.md, which owns the enumeration."""

    @pytest.mark.parametrize("aid", sorted(review.AIDS))
    def test_review_md_explains_it(self, aid):
        assert f"review {aid}" in REVIEW_TEXT, (
            f"docs/REVIEW.md does not cover `review {aid}`. It landed in AIDS "
            "without reaching the page written for the person reading its "
            "output -- exactly the drift #345 was filed for."
        )

    @pytest.mark.parametrize("aid", sorted(review.AIDS))
    def test_the_output_contract_names_its_report(self, aid):
        # The report filename, not the command: #341 once updated one and
        # not the other, so the two are checked independently rather than
        # one standing in for the other.
        assert f"survey.{aid}.md" in REVIEW_TEXT, (
            f"docs/REVIEW.md's output-contract block does not show "
            f"`survey.{aid}.md`. Every aid writes one, mirroring the draft's path."
        )


class TestArchitectureDefersRatherThanRestates:
    """Layer 4 keeps the boundary and hands the detail to REVIEW.md.

    If it grows the per-aid table back, the two drift apart again -- which
    is the whole failure #345 recorded, one document over.
    """

    def test_it_points_at_the_review_page(self, section):
        assert "REVIEW.md" in section

    def test_it_does_not_re_list_every_aid(self, section):
        listed = [aid for aid in review.AIDS if f"chitragupta.review {aid}" in section]
        assert len(listed) < len(review.AIDS), (
            "docs/ARCHITECTURE.md's Layer 4 has started enumerating the aids "
            "again. That list lives in docs/REVIEW.md; two copies is how the "
            "count went stale in the first place."
        )
