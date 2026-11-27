import pytest

from chitragupta import registry
from tests.test_registry import MODEL_GLOSSARY, accept

BOOK_SPEC = """# Composable Twins

## Front matter {#front}

### Preface {#preface}

## Part I {#part-i}

### What a twin costs {#ch-cost}

## Appendices {#appendices}

### Installing the toolchain {#app-install}

## Back matter {#back}

### About the author {#about}

### Glossary {#glossary}
"""


@pytest.fixture
def book(signed_book):
    return signed_book


def test_a_hand_written_front_or_back_unit_needs_no_glossary(book):
    accept(book, "preface", "Why I wrote this.\n")
    accept(book, "about", "Who I am.\n")
    accept(book, "ch-cost", "The bill.\n")
    found = registry.findings(registry.build(book))
    assert ("glossary", "ch-cost has no ## Glossary in scope.md") in found
    assert not [message for _, message in found if message.startswith(("preface", "about"))]


def test_an_appendix_is_numbered_so_it_still_needs_one(book):
    accept(book, "app-install", "Install it.\n")
    found = registry.findings(registry.build(book))
    assert ("glossary", "app-install has no ## Glossary in scope.md") in found


def test_a_term_defined_in_unnumbered_matter_is_a_finding(book):
    accept(book, "preface", "Why I wrote this.\n", glossary=MODEL_GLOSSARY)
    found = registry.findings(registry.build(book))
    assert (
        "glossary",
        "preface is front or back matter, which LaTeX does not number, so a "
        "glossary definition's \\Cref to it prints no chapter: define "
        "`digital twin` in a numbered chapter or appendix",
    ) in found
