"""What a topic is called, as distinct from which papers are in it.

BERTopic names a topic from the terms its c-TF-IDF finds most
distinguishing. Left to its defaults on this corpus that produced names
like `0_the_and_of_to` -- function words, because nothing configured a
stop-word list -- and, once those were removed, names like
`werner kritzinger, fraunhofer austria`, which is a person and their
institution rather than a subject.

Both are labelling failures and neither is a clustering failure. The
papers under that topic genuinely are a topic: they survey the
digital-twin/shadow/model taxonomy, and they mention its author because
they are discussing his work. Measured, `kritzinger` appears in 101 of
497 documents and 55 still contain it after the bibliography is removed,
so this cannot be fixed by dropping back matter -- the name is in the
prose, and the prose is the topic.

Asta's *Topic Extraction and Document-Topic Linking in Scientific and
Domain-Specific Corpora* names the remedy as a best practice: "use domain
term recognition as a backbone for both topics and labels", so that a
label is chosen from terms the domain actually uses rather than from
whatever is frequent. A person's name is not a domain term.

**The name list is the corpus's own bibliography, not a gazetteer.**
Every author of every paper in `content/ledger.sqlite` is a person this
corpus is likely to name in prose, and no other list is needed or
trustworthy: a general name list would be both too large (removing
ordinary words that happen to be somebody's surname somewhere) and too
small (missing the field's own authors, who are exactly the ones
discussed). The ledger's `bib_fields` column is the sanctioned reader for
this -- `chitragupta/references.py` uses the same source, and nothing
here parses `bibliography.bib`.

The cost, measured rather than assumed: of 1,277 distinct surnames in
this corpus's bibliography, five are also ordinary English words
(`black`, `brown`, `can`, `park`, `wood`) and are removed from the label
vocabulary along with the rest. In a corpus about digital twins that is
a price worth paying, and `[enrich].topic_exclude_author_names` turns it
off for a corpus where it is not.

**What the name list cannot reach.** It holds the authors of papers *in*
the corpus, so it catches the ones most discussed -- `kritzinger` is
excluded, and that was the top-ranked bad label. It does not catch a
person cited by these papers whose own work is not in the library:
measured, `drath` and `kockmann` both survive for exactly that reason.
Widening it would mean parsing names out of reference lists, which is
guessing at a person from prose; the bibliography is the one place a name
is asserted rather than inferred.

Note what this does **not** touch: the clustering. Topics are formed from
document embeddings, which never see this list. Only the words a topic is
described by change.
"""

import json
import re
from collections.abc import Iterator
from typing import Any

from chitragupta import config, ledger

# `Kritzinger, Werner` and `Werner Kritzinger` both occur in real .bib
# files, sometimes in one file. Splitting on BibTeX's own " and " first
# and then on the comma is what handles both without guessing.
AUTHOR_SEPARATOR = re.compile(r"\s+and\s+", re.IGNORECASE)
NOT_NAME_CHARS = re.compile(r"[^a-zA-Z\- ]")

# Citation and URL scaffolding, which survives `content_text()` because
# it appears mid-sentence rather than on lines of its own. Measured: it
# named two of this corpus's twenty largest topics -- `et al` and a DOI
# fragment -- before this list existed. Deliberately short, and only
# words that carry no subject in any field: `figure` and `table` are not
# here, because "table" is a real term in a database paper.
CITATION_NOISE = frozenset({
    "et", "al", "etc", "ie", "eg", "cf", "ibid",
    "doi", "http", "https", "www", "com", "org", "arxiv", "isbn",
})

# Two characters is an initial, not a name: dropping `J` and `de` keeps
# the exclusion list from swallowing tokens that carry no person in them.
MIN_NAME_LENGTH = 3


def _tokens(person: str) -> Iterator[str]:
    """The name-like words in one BibTeX author entry, lowercased.

    Yields given names and surname alike. A first name is no more a
    domain term than a surname in a technical corpus, and excluding only
    surnames would leave `werner` free to label a topic.
    """
    person = NOT_NAME_CHARS.sub(" ", person.strip().strip("{}"))
    for part in person.replace(",", " ").split():
        token = part.strip("-").lower()
        if len(token) >= MIN_NAME_LENGTH:
            yield token


def author_names(con=None) -> frozenset:
    """Every author name in the corpus's own bibliography, as lowercase
    tokens.

    Returns an empty set when the ledger holds no `bib_fields` at all,
    which is the honest answer for a corpus synced before that column
    existed -- and leaves labelling exactly as it was rather than
    degrading it.
    """
    con = ledger.connect() if con is None else con
    names = set()
    for (fields,) in con.execute(
            "SELECT bib_fields FROM items WHERE bib_fields IS NOT NULL"):
        try:
            author = (json.loads(fields) or {}).get("author") or ""
        except (TypeError, ValueError):
            continue
        for person in AUTHOR_SEPARATOR.split(author):
            names.update(_tokens(person))
    return frozenset(names)


def stop_words(con=None) -> list:
    """English function words, plus this corpus's own author names.

    One list rather than two passes because that is the seam
    `CountVectorizer` offers: `stop_words` drops tokens *before* n-grams
    are assembled, so excluding `werner` and `kritzinger` also prevents
    the bigram `werner kritzinger` from ever forming. Filtering finished
    labels instead would have to catch every n-gram the pair can appear
    in.
    """
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    names = author_names(con) if config.TOPIC_EXCLUDE_AUTHOR_NAMES else frozenset()
    return sorted(ENGLISH_STOP_WORDS | CITATION_NOISE | names)


def vectorizer(con=None) -> Any:
    """The `vectorizer_model` BERTopic should build its labels from.

    `ngram_range=(1, 2)` because the terms that name a topic in this
    corpus are largely two words -- `digital twin`, `mqtt v5`,
    `structural health monitoring` -- and a unigram-only vocabulary
    describes them with halves.

    `min_df=2` drops terms appearing in a single document: a label true of
    one paper does not describe the topic it sits in, and on a corpus this
    size the tail of such terms is long.
    """
    from sklearn.feature_extraction.text import CountVectorizer

    return CountVectorizer(stop_words=stop_words(con), ngram_range=(1, 2), min_df=2)
