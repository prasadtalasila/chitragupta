"""chitragupta/enrich/topic_labels.py: what a topic is called.

The distinction these tests exist to hold: this module changes *labels*
and never *clustering*. Topics are formed from document embeddings, which
never see the author-name list.
"""

import json

import pytest

from chitragupta import config, ledger
from chitragupta.enrich import topic_labels


def add_item(con, citekey, author=None, bib_fields=...):
    """One ledger row. `last_synced` is NOT NULL, so it is supplied here
    rather than left to the caller of every test below."""
    if bib_fields is ...:
        bib_fields = json.dumps({"author": author}) if author is not None else None
    con.execute("INSERT INTO items (citekey, item_type, title, status, last_synced, "
                "bib_fields) VALUES (?, 'article', 't', 'discovered', '2026-01-01', ?)",
                (citekey, bib_fields))
    con.commit()


class TestAuthorNames:
    def test_surname_and_given_name_both_excluded(self, ledger_con):
        """Excluding only surnames would leave `werner` free to label a
        topic, and `werner kritzinger` is the label that motivated this."""
        add_item(ledger_con, "a_2020", "Kritzinger, Werner")
        names = topic_labels.author_names(ledger_con)
        assert {"kritzinger", "werner"} <= names

    def test_both_bibtex_name_orders_are_read(self, ledger_con):
        """`Kritzinger, Werner` and `Werner Kritzinger` both occur in real
        .bib files, sometimes in the same file."""
        add_item(ledger_con, "a_2020", "Kritzinger, Werner")
        add_item(ledger_con, "b_2021", "Rainer Drath")
        names = topic_labels.author_names(ledger_con)
        assert {"kritzinger", "drath", "rainer"} <= names

    def test_multiple_authors_split_on_bibtex_and(self, ledger_con):
        add_item(ledger_con, "a_2020",
                 "Kapteyn, Michael G. and Knezevic, David J. and Willcox, Karen")
        names = topic_labels.author_names(ledger_con)
        assert {"kapteyn", "knezevic", "willcox", "karen"} <= names

    def test_initials_are_not_names(self, ledger_con):
        """`G.` and `J.` carry no person and would only shrink the label
        vocabulary."""
        add_item(ledger_con, "a_2020", "Kapteyn, Michael G.")
        assert "g" not in topic_labels.author_names(ledger_con)

    def test_braces_and_punctuation_do_not_survive(self, ledger_con):
        add_item(ledger_con, "a_2020", "{Van Der Berg}, Jan-Willem")
        names = topic_labels.author_names(ledger_con)
        assert "berg" in names
        assert not any("{" in n or "." in n for n in names)

    def test_a_ledger_with_no_bib_fields_yields_nothing(self, ledger_con):
        """The honest answer for a corpus synced before that column
        existed: leave labelling as it was rather than degrade it."""
        add_item(ledger_con, "a_2020", None)
        assert topic_labels.author_names(ledger_con) == frozenset()

    def test_malformed_bib_fields_are_skipped_not_fatal(self, ledger_con):
        add_item(ledger_con, "good_2020", "Kritzinger, Werner")
        add_item(ledger_con, "bad_2020", bib_fields="not json")
        assert "kritzinger" in topic_labels.author_names(ledger_con)

    def test_an_entry_with_no_author_is_skipped(self, ledger_con):
        add_item(ledger_con, "a_2020", bib_fields=json.dumps({"title": "x"}))
        assert topic_labels.author_names(ledger_con) == frozenset()


class TestStopWords:
    def test_function_words_and_author_names_are_one_list(self, ledger_con):
        """`CountVectorizer.stop_words` drops tokens *before* n-grams are
        assembled, so excluding both halves of a name also prevents the
        bigram from forming. Filtering finished labels instead would have
        to catch every n-gram the pair appears in."""
        add_item(ledger_con, "a_2020", "Kritzinger, Werner")
        words = set(topic_labels.stop_words(ledger_con))
        assert "the" in words
        assert "kritzinger" in words

    def test_domain_terms_survive(self, ledger_con):
        add_item(ledger_con, "a_2020", "Kritzinger, Werner")
        words = set(topic_labels.stop_words(ledger_con))
        for term in ("digital", "twin", "gitops", "mqtt", "monitoring"):
            assert term not in words

    def test_switching_it_off_keeps_only_function_words(self, ledger_con, monkeypatch):
        monkeypatch.setattr(config, "TOPIC_EXCLUDE_AUTHOR_NAMES", False)
        add_item(ledger_con, "a_2020", "Kritzinger, Werner")
        words = set(topic_labels.stop_words(ledger_con))
        assert "the" in words
        assert "kritzinger" not in words

    def test_the_list_is_sorted_so_runs_are_reproducible(self, ledger_con):
        """A set's iteration order is not stable across processes, and a
        vectorizer built from an unstable list is a topic model whose
        labels can move without its inputs moving."""
        add_item(ledger_con, "a_2020", "Kritzinger, Werner")
        words = topic_labels.stop_words(ledger_con)
        assert words == sorted(words)


class TestVectorizer:
    def test_it_reads_two_word_terms(self, ledger_con):
        """The terms that name a topic here are largely two words --
        `digital twin`, `mqtt v5` -- and a unigram vocabulary describes
        them with halves."""
        assert topic_labels.vectorizer(ledger_con).ngram_range == (1, 2)

    def test_single_document_terms_are_dropped(self, ledger_con):
        assert topic_labels.vectorizer(ledger_con).min_df == 2

    def test_it_excludes_the_corpus_own_authors(self, ledger_con):
        add_item(ledger_con, "a_2020", "Kritzinger, Werner")
        assert "kritzinger" in set(topic_labels.vectorizer(ledger_con).stop_words)

    def test_a_name_cannot_become_a_label(self, ledger_con):
        """End to end through sklearn, not just the configuration: the
        bigram must be absent from the fitted vocabulary."""
        add_item(ledger_con, "a_2020", "Kritzinger, Werner")
        vec = topic_labels.vectorizer(ledger_con)
        vec.fit(["werner kritzinger proposed a digital twin taxonomy",
                 "a digital twin taxonomy needs a digital twin definition"])
        vocabulary = set(vec.vocabulary_)
        assert "digital twin" in vocabulary
        assert not any("kritzinger" in term or "werner" in term for term in vocabulary)


class TestCitationNoise:
    """Scaffolding that survives `content_text()` because it appears
    mid-sentence. Measured: it named two of this corpus's twenty largest
    topics -- `et al` and a DOI fragment -- before this list existed."""

    def test_citation_scaffolding_cannot_label_a_topic(self, ledger_con):
        words = set(topic_labels.stop_words(ledger_con))
        assert {"et", "al", "doi", "www", "arxiv"} <= words

    def test_real_terms_that_look_like_scaffolding_survive(self, ledger_con):
        """`table` is a real term in a database paper and `figure` in a
        rendering one, so neither is on the list."""
        words = set(topic_labels.stop_words(ledger_con))
        for term in ("table", "figure", "section", "model"):
            assert term not in words

    def test_it_applies_even_with_author_exclusion_off(self, ledger_con, monkeypatch):
        """The two lists answer different questions: one is about this
        corpus's people, the other about every corpus's boilerplate."""
        monkeypatch.setattr(config, "TOPIC_EXCLUDE_AUTHOR_NAMES", False)
        assert "et" in set(topic_labels.stop_words(ledger_con))
