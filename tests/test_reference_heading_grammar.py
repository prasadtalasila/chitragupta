"""#951: three readers, one answer to "is this the bibliography?".

`references_section` (citeproc swap, verbatim masking, `draft references`),
`review/_claims` (uncited-prose report) and `style_typeset` (bare-URL
check) each used to restate which headings open a draft's reference
list, and disagreed: `## Bibliography` was the bibliography for two of
them and prose for the third. Each reader is asked through its public
behaviour, not its regex, so the test still holds if one of them stops
using a regex at all.
"""

import pytest

from chitragupta import references_section, style_typeset
from chitragupta.review import _claims
from tests.conftest import draft_with

URL = "https://github.com/INTO-CPS-Association/plant-controller"

HEADINGS = [
    ("## References", True),
    ("## Bibliography", True),
    ("## Works cited", True),
    ("## Works Cited", True),
    ("## REFERENCES", True),
    ("## 6. References", True),
    ("## 6) Bibliography", True),
    ("## 1.14 Works cited", True),
    ("## A. References", True),
    ("## IV. Bibliography", True),
    ("## Introduction", False),
    ("## References and notes", False),
    ("## Further References", False),
    ("## Reference", False),
    ("## Bibliographic notes", False),
    ("## See. References", False),
]


def section_reader(heading: str) -> bool:
    return references_section.has_section(f"# D\n\nProse.\n\n{heading}\n\nEntry.\n")


def claims_reader(heading: str) -> bool:
    sentences = _claims.claim_sentences(f"# D\n\nProse here.\n\n{heading}\n\nThe entry asserts.\n")
    return "The entry asserts." not in [s.text for s in sentences]


def typeset_reader(heading: str, tmp_path) -> bool:
    body = f"# D\n\nProse.\n\n{heading}\n\n[1] A. Author, {URL}\n"
    return style_typeset.findings(draft_with(body, tmp_path)) == []


@pytest.mark.parametrize(("heading", "is_bibliography"), HEADINGS)
def test_all_three_readers_agree(heading, is_bibliography, tmp_path):
    assert section_reader(heading) is is_bibliography
    assert claims_reader(heading) is is_bibliography
    assert typeset_reader(heading, tmp_path) is is_bibliography


def test_the_two_composing_readers_use_the_shared_title():
    # Composed from the one string, not merely agreeing with it today: a
    # copy that agrees now is the duplication #951 removed, waiting to drift.
    assert references_section.REFERENCE_TITLE in _claims.REFERENCE_TITLE.pattern
    assert references_section.REFERENCE_TITLE in style_typeset._REFERENCES_RE.pattern


def test_further_reading_is_the_typeset_check_s_exemption_alone(tmp_path):
    # A reading list is links by nature, so its URLs are not findings, but
    # it is not the reference list: the citeproc swap must not replace it.
    assert typeset_reader("## Further reading", tmp_path)
    assert not section_reader("## Further reading")
    assert not claims_reader("## Further reading")
