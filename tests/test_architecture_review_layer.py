import re
from pathlib import Path

import pytest

from chitragupta import review

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"

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
    11: "Eleven",
}

_SECTION_HEADING = "## Layer 4: the review layer"

_SECTION_HEADING_RE = re.compile(
    r"^## (?:[^\x00-\x7F]+ )?" + re.escape(_SECTION_HEADING.removeprefix("## ")),
    re.MULTILINE,
)

REVIEW_MD = REPO_ROOT / "docs" / "REVIEW.md"
REVIEW_TEXT = REVIEW_MD.read_text(encoding="utf-8")

_DEFAULT_STEM = "survey"
_EXAMPLE_STEM = {"union": "book"}


@pytest.fixture(scope="module")
def section() -> str:
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
    def test_the_heading_is_present_and_unique(self):
        text = ARCHITECTURE.read_text(encoding="utf-8")
        assert len(_SECTION_HEADING_RE.findall(text)) == 1

    def test_there_are_aids_to_check(self):
        assert len(review.AIDS) >= 3

    def test_the_section_is_about_the_review_layer(self, section):
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
        current = _NUMBER_WORDS[len(review.AIDS)]
        stale = [
            word
            for size, word in _NUMBER_WORDS.items()
            if size != len(review.AIDS) and f"{word} aids" in section
        ]
        assert not stale, f"Layer 4 says '{current} aids' and also {stale} -- one is wrong."


class TestEveryAidIsDocumented:
    @pytest.mark.parametrize("aid", sorted(review.AIDS))
    def test_review_md_explains_it(self, aid):
        assert f"review {aid}" in REVIEW_TEXT, (
            f"docs/REVIEW.md does not cover `review {aid}`. It landed in AIDS "
            "without reaching the page written for the person reading its "
            "output -- exactly the drift #345 was filed for."
        )

    @pytest.mark.parametrize("aid", sorted(review.AIDS))
    def test_the_output_contract_names_its_report(self, aid):
        stem = _EXAMPLE_STEM.get(aid, _DEFAULT_STEM)
        assert f"{stem}.{aid}.md" in REVIEW_TEXT, (
            f"docs/REVIEW.md's output-contract block does not show "
            f"`{stem}.{aid}.md`. Every aid writes one, mirroring its input's path."
        )


class TestArchitectureDefersRatherThanRestates:
    def test_it_points_at_the_review_page(self, section):
        assert "REVIEW.md" in section

    def test_it_does_not_re_list_every_aid(self, section):
        listed = [aid for aid in review.AIDS if f"chitragupta.review {aid}" in section]
        assert len(listed) < len(review.AIDS), (
            "docs/ARCHITECTURE.md's Layer 4 has started enumerating the aids "
            "again. That list lives in docs/REVIEW.md; two copies is how the "
            "count went stale in the first place."
        )
