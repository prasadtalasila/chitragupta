"""docs/ARCHITECTURE.md's "Layer 4: the review layer" section, held to
`chitragupta/review/__init__.py`'s `AIDS` rather than to a reader's
memory (#345).

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
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
    6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
}

_SECTION_HEADING = "## Layer 4: the review layer"


@pytest.fixture(scope="module")
def section() -> str:
    """The Layer 4 section's own text, heading to next `## `.

    Sliced rather than read whole so that an unrelated "three" elsewhere
    in the document -- and there are many -- can never satisfy or break
    an assertion here.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    start = text.index(_SECTION_HEADING)
    following = re.search(r"^## ", text[start + len(_SECTION_HEADING):], re.MULTILINE)
    end = start + len(_SECTION_HEADING) + following.start() if following else len(text)
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
        assert text.count(_SECTION_HEADING) == 1

    def test_there_are_aids_to_check(self):
        assert len(review.AIDS) >= 3

    def test_the_section_names_the_review_command(self, section):
        assert "chitragupta.review" in section


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
            word for size, word in _NUMBER_WORDS.items()
            if size != len(review.AIDS) and f"{word} aids" in section
        ]
        assert not stale, f"Layer 4 says '{current} aids' and also {stale} -- one is wrong."


class TestEveryAidIsDocumented:
    @pytest.mark.parametrize("aid", sorted(review.AIDS))
    def test_the_table_names_it(self, section, aid):
        assert f"chitragupta.review {aid}" in section, (
            f"docs/ARCHITECTURE.md's Layer 4 table has no row invoking "
            f"`chitragupta.review {aid}`. It landed in AIDS without reaching this "
            "section -- exactly the drift #345 was filed for."
        )

    @pytest.mark.parametrize("aid", sorted(review.AIDS))
    def test_the_output_contract_names_its_report(self, section, aid):
        # The report filename, not the command: #341 updated this block
        # and not the table, so the two are checked independently rather
        # than one standing in for the other.
        assert f"survey.{aid}.md" in section, (
            f"Layer 4's output-contract block does not show `survey.{aid}.md`. "
            "Every aid writes one, mirroring the draft's path."
        )
