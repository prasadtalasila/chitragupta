"""What a topic is called, as distinct from which papers are in it.

BERTopic's default c-TF-IDF labels here were function words and then an
author's name and institution: labelling failures, not clustering ones.
The name is in the prose, so dropping back matter can't fix it; the
remedy is labels drawn from domain terms, and a person's name is not one.

**The name list is the corpus's own bibliography, not a gazetteer**, read
through the ledger's `bib_fields` (as `chitragupta/references.py` does):
a general list would be too large and miss the field's own authors. It
costs five surnames that are ordinary English words;
`[enrich].topic_exclude_author_names` turns it off. It cannot reach
cited authors absent from the library; widening it would mean guessing
names from prose. The clustering itself never sees this list.
"""

import json
import re
from collections.abc import Iterator
from typing import Any

from chitragupta import config, ledger

# Both `Surname, Given` and `Given Surname` occur in real .bib files:
# split on BibTeX's " and " first, then on the comma.
AUTHOR_SEPARATOR = re.compile(r"\s+and\s+", re.IGNORECASE)
NOT_NAME_CHARS = re.compile(r"[^a-zA-Z\- ]")

# Citation and URL scaffolding that survives `content_text()` mid-sentence
# (`et al` and a DOI fragment once named large topics). Only words with no
# subject in any field: not `table`, a real database term.
CITATION_NOISE = frozenset(
    {
        "et",
        "al",
        "etc",
        "ie",
        "eg",
        "cf",
        "ibid",
        "doi",
        "http",
        "https",
        "www",
        "com",
        "org",
        "arxiv",
        "isbn",
    }
)

# Two characters is an initial or particle, not a name.
MIN_NAME_LENGTH = 3


def _tokens(person: str) -> Iterator[str]:
    """The name-like words in one BibTeX author entry, lowercased.

    Given names too: they are no more domain terms than surnames.
    """
    person = NOT_NAME_CHARS.sub(" ", person.strip().strip("{}"))
    for part in person.replace(",", " ").split():
        token = part.strip("-").lower()
        if len(token) >= MIN_NAME_LENGTH:
            yield token


def author_names(con=None) -> frozenset:
    """Every author name in the corpus's own bibliography, as lowercase
    tokens; empty when no row carries `bib_fields`, leaving labels as they
    were.
    """
    if con is not None:
        return _author_names_from(con)
    # Opened here, so closed here (#511/m-80).
    with ledger.reading() as owned:
        return _author_names_from(owned)


def _author_names_from(con) -> frozenset:
    names = set()
    for (fields,) in con.execute("SELECT bib_fields FROM items WHERE bib_fields IS NOT NULL"):
        try:
            author = (json.loads(fields) or {}).get("author") or ""
        except (TypeError, ValueError):
            continue
        for person in AUTHOR_SEPARATOR.split(author):
            names.update(_tokens(person))
    return frozenset(names)


def stop_words(con=None) -> list:
    """English function words, plus this corpus's own author names.

    `stop_words` drops tokens *before* n-grams form, so an author's given
    name and surname can never form a bigram label.
    """
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    names = author_names(con) if config.TOPIC_EXCLUDE_AUTHOR_NAMES else frozenset()
    return sorted(ENGLISH_STOP_WORDS | CITATION_NOISE | names)


def vectorizer(con=None) -> Any:
    """The `vectorizer_model` BERTopic should build its labels from.

    `ngram_range=(1, 2)`: topic terms here are largely two words.
    `min_df=2`: a term in one paper doesn't describe its topic.
    """
    from sklearn.feature_extraction.text import CountVectorizer

    return CountVectorizer(stop_words=stop_words(con), ngram_range=(1, 2), min_df=2)
