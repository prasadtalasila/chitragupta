"""Zotero collection labels: parsing, matching, and the three places they
are read (#195).

The feature rests on one factual claim, and it is worth stating where the
tests can be read: **Zotero's own BibTeX exporter drops collection
membership.** Nothing here can be exercised by a plain Zotero export, only
by a Better BibTeX one with JabRef fields enabled, which writes JabRef's
`groups` field. So the case that matters most is not any of the matching
rules below -- it is that a library *without* that field keeps working
exactly as it did, which is why the no-field cases are tested at every
layer rather than only at the parser.
"""

import json
import sqlite3

import pytest

from chitragupta import bib_collections, config, ledger, retrieval

from tests.conftest import make_reference


class TestParse:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, ()),
            ("", ()),
            ("   ", ()),
            ("Modelling", ("Modelling",)),
            ("A, B", ("A", "B")),
            ("Digital twins > Modelling", ("Digital twins > Modelling",)),
            ("Digital twins>Modelling", ("Digital twins > Modelling",)),
            ("  Digital twins   >   Modelling  ", ("Digital twins > Modelling",)),
            ("A > > B", ("A > B",)),
            ("A >", ("A",)),
            ("A, A", ("A",)),
            ("A, , B", ("A", "B")),
        ],
    )
    def test_normalisation(self, value, expected):
        assert bib_collections.parse(value) == expected

    def test_order_is_preserved(self):
        """The ledger writes this as JSON, so a stable order is what keeps
        a re-sync of an unchanged entry from rewriting the row."""
        assert bib_collections.parse("Z, A, M") == ("Z", "A", "M")


class TestMatches:
    @pytest.mark.parametrize(
        "wanted,expected",
        [
            ("Digital twins", True),  # the parent selects the subtree
            ("digital TWINS", True),  # a label typed in a GUI, not a token
            ("Digital twins > Modelling", True),
            ("Digital twins>Modelling", True),
            ("Modelling", False),  # a subcollection is not a top-level one
            ("Digital", False),  # not a substring match
            ("Digital twins > Mod", False),  # nor within a segment
            ("", False),
            (">", False),
        ],
    )
    def test_against_one_nested_path(self, wanted, expected):
        assert bib_collections.matches(("Digital twins > Modelling",), wanted) is expected

    def test_a_sibling_with_a_shared_prefix_is_not_selected(self):
        """The reason matching is per-segment rather than `startswith`."""
        assert bib_collections.matches(("Modelling notes",), "Modelling") is False

    def test_no_collections_matches_nothing(self):
        assert bib_collections.matches((), "Anything") is False


class TestNames:
    def test_ancestors_are_implied(self):
        """Only the leaf path is stored, but a user may filter on a parent,
        so listing what they can filter on has to expand them back out."""
        assert bib_collections.names({"a": ("X > Y > Z",)}) == ["X", "X > Y", "X > Y > Z"]

    def test_paths_are_deduplicated_across_items(self):
        assert bib_collections.names({"a": ("X > Y",), "b": ("X > Z",), "c": ("X",)}) == [
            "X",
            "X > Y",
            "X > Z",
        ]

    def test_a_corpus_with_none_lists_none(self):
        assert bib_collections.names({"a": (), "b": ()}) == []


class TestTheBibField:
    def test_the_field_name_is_configurable(self, monkeypatch):
        """A user whose exporter writes them elsewhere should not have to
        patch the parser to be read."""
        from chitragupta import bib_reader

        monkeypatch.setattr(config, "BIB_COLLECTIONS_FIELD", "keywords")
        entry = {
            "ID": "k_2024",
            "ENTRYTYPE": "article",
            "title": "T",
            "keywords": "Shelf > Sub",
            "groups": "Ignored",
        }
        assert bib_collections.parse(entry.get(bib_reader.config.BIB_COLLECTIONS_FIELD)) == (
            "Shelf > Sub",
        )


class TestTheLedgerColumn:
    @pytest.fixture(autouse=True)
    def _rows_by_name(self, ledger_con):
        """`ledger.connect()` leaves the default tuple row factory in
        place; `all_items` sets `sqlite3.Row` per query. These tests query
        directly, so they have to ask for it themselves."""
        ledger_con.row_factory = sqlite3.Row
        yield
        ledger_con.row_factory = None

    def test_a_reference_with_collections_round_trips(self, ledger_con):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a_2024", collections=("X > Y",))
        )
        row = ledger_con.execute("SELECT * FROM items WHERE citekey = 'a_2024'").fetchone()
        assert json.loads(row["collections"]) == ["X > Y"]
        assert bib_collections.of_row(row) == ("X > Y",)

    def test_no_collections_is_stored_as_null_not_an_empty_array(self, ledger_con):
        """Most libraries have no such field at all. NULL is what a
        pre-migration row already holds, and writing "[]" into every row
        instead would churn the ledger for no reader's benefit."""
        ledger.upsert_reference(ledger_con, make_reference(citekey="b_2024"))
        row = ledger_con.execute("SELECT * FROM items WHERE citekey = 'b_2024'").fetchone()
        assert row["collections"] is None
        assert bib_collections.of_row(row) == ()

    def test_an_update_rewrites_them(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="c_2024", collections=("Old",)))
        ledger.upsert_reference(ledger_con, make_reference(citekey="c_2024", collections=("New",)))
        row = ledger_con.execute("SELECT * FROM items WHERE citekey = 'c_2024'").fetchone()
        assert bib_collections.of_row(row) == ("New",)

    @pytest.mark.parametrize("stored", ["not json", "{}", '"a string"', "7"])
    def test_an_unreadable_value_narrows_a_filter_rather_than_raising(self, ledger_con, stored):
        """A ledger is not a place to raise from. A row written by a future
        version, or hand-edited, should cost a search some candidates
        rather than stop it."""
        ledger.upsert_reference(ledger_con, make_reference(citekey="d_2024"))
        ledger_con.execute("UPDATE items SET collections = ? WHERE citekey = 'd_2024'", (stored,))
        row = ledger_con.execute("SELECT * FROM items WHERE citekey = 'd_2024'").fetchone()
        assert bib_collections.of_row(row) == ()

    def test_a_tuple_row_reads_as_none_rather_than_raising(self, ledger_con):
        """`collections_of` is public, and the connection this project
        hands around does not set a row factory by default."""
        ledger.upsert_reference(ledger_con, make_reference(citekey="e_2024"))
        ledger_con.row_factory = None
        row = ledger_con.execute("SELECT * FROM items").fetchone()
        assert bib_collections.of_row(row) == ()

    def test_a_row_from_before_the_column_existed_reads_as_none(self):
        """`collections_of` is handed rows from `SELECT *` on a ledger that
        may predate the migration entirely."""
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE items (citekey TEXT)")
        con.execute("INSERT INTO items VALUES ('old_2019')")
        row = con.execute("SELECT * FROM items").fetchone()
        assert bib_collections.of_row(row) == ()
        con.close()


class TestRetrievalFilter:
    """`search(..., collection=...)` -- #195's actual ask: a chapter on
    modelling retrieving only from the modelling shelf."""

    @pytest.fixture
    def corpus(self, isolated_config, ledger_con):
        for citekey, collections in (
            ("in_sub_2024", ("Digital twins > Modelling",)),
            ("in_other_2024", ("Reading list",)),
            ("uncollected_2024", ()),
        ):
            ref = make_reference(citekey=citekey, collections=collections)
            ledger.upsert_reference(ledger_con, ref)
            parsed = isolated_config.PARSED_DIR / f"{citekey}.txt"
            parsed.parent.mkdir(parents=True, exist_ok=True)
            parsed.write_text("digital twin modelling and simulation " * 20)
            ledger_con.execute(
                "UPDATE items SET parsed_path = ?, status = 'parsed' WHERE citekey = ?",
                (str(parsed), citekey),
            )
        ledger_con.commit()
        retrieval._load_cache.cache_clear() if hasattr(
            retrieval._load_cache, "cache_clear"
        ) else None
        return isolated_config

    def test_unfiltered_search_returns_everything(self, corpus):
        found = retrieval.search("modelling", k=10)
        assert {r.citekey for r in found} == {"in_sub_2024", "in_other_2024", "uncollected_2024"}

    def test_a_parent_collection_selects_the_subtree(self, corpus):
        found = retrieval.search("modelling", k=10, collection="Digital twins")
        assert {r.citekey for r in found} == {"in_sub_2024"}

    def test_an_unknown_collection_returns_nothing(self, corpus):
        assert retrieval.search("modelling", k=10, collection="Nonexistent") == []

    def test_an_item_with_no_collections_is_excluded_by_any_filter(self, corpus):
        found = retrieval.search("modelling", k=10, collection="Reading list")
        assert "uncollected_2024" not in {r.citekey for r in found}

    def test_scores_do_not_change_when_a_filter_is_applied(self, corpus):
        """Scoring stays corpus-wide on purpose: narrowing the index would
        change every IDF, so the same query would rank differently
        depending on the filter, and the cached index could not be shared."""
        unfiltered = {r.citekey: r.score for r in retrieval.search("modelling", k=10)}
        filtered = retrieval.search("modelling", k=10, collection="Digital twins")
        assert filtered[0].score == unfiltered["in_sub_2024"]


class TestTheLedgerCLI:
    """`--collections` and `--collection`, the read-only half of #195."""

    @pytest.fixture
    def corpus(self, isolated_config, ledger_con):
        for citekey, collections in (
            ("shelved_2024", ("Digital twins > Modelling",)),
            ("elsewhere_2024", ("Reading list",)),
            ("bare_2024", ()),
        ):
            ledger.upsert_reference(
                ledger_con, make_reference(citekey=citekey, collections=collections)
            )
        ledger_con.commit()
        return isolated_config

    def test_collections_lists_every_path_with_its_ancestors(self, corpus, capsys):
        assert ledger.main(["--collections"]) == 0
        out = capsys.readouterr().out
        assert "  Digital twins\n" in out
        assert "  Digital twins > Modelling\n" in out
        assert "  Reading list\n" in out
        assert "3 collection(s)." in out

    def test_collections_on_a_corpus_without_any_explains_why(
        self, isolated_config, ledger_con, capsys
    ):
        """The likeliest cause of an empty list is the export, not the
        library, so the empty case is guidance rather than a result."""
        ledger.upsert_reference(ledger_con, make_reference(citekey="none_2024"))
        ledger_con.commit()
        assert ledger.main(["--collections"]) == 0
        out = capsys.readouterr().out
        assert "No collections recorded." in out
        assert "Better BibTeX" in out

    def test_collection_filters_the_listing_and_includes_the_subtree(self, corpus, capsys):
        assert ledger.main(["--collection", "Digital twins"]) == 0
        out = capsys.readouterr().out
        assert "shelved_2024" in out
        assert "elsewhere_2024" not in out
        assert "bare_2024" not in out

    def test_an_empty_collection_says_so_rather_than_naming_a_status(self, corpus, capsys):
        """`--list` reports "no items with status None" when empty, which
        would be a confusing thing to print at someone who asked about a
        collection."""
        assert ledger.main(["--collection", "Nonexistent"]) == 0
        assert "No items in collection 'Nonexistent'." in capsys.readouterr().out
