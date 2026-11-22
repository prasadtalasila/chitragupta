"""Collection membership: slug paths, the name table, and the places
they are read.

chitragupta-importer writes each entry's collections as slug paths in
`cg-collections` and one `@comment{cg-collections v1 ...}` table mapping
each slug path to the collection's own name. A library written any other
way carries no collections, and every command keeps working without them,
which is why the no-collections cases are tested at every layer.
"""

import json
import sqlite3

import pytest

from chitragupta import bib_collections, ledger, ledger_cli, retrieval, retrieval_cache
from chitragupta.bib_collections import (
    AmbiguousCollection,
    UnknownCollection,
    display_paths,
    is_slug_path,
    matches,
    parse,
    resolve,
)

from tests.conftest import make_reference

DEPTH_FOUR = {
    "digital-twins": "Digital Twins",
    "digital-twins.platforms": "Platforms",
    "digital-twins.platforms.cloud": "Cloud",
    "digital-twins.platforms.cloud.public": "Public",
}


class TestSlugPath:
    @pytest.mark.parametrize(
        "value", ["a", "industry-5-0", "digital-twin.use-cases.medical-1", "a1.b2.c3"]
    )
    def test_valid(self, value):
        assert is_slug_path(value)

    @pytest.mark.parametrize(
        "value", ["", "A", "a..b", ".a", "a.", "a b", "a/b", "a--b", "-a", "a-", "a > b"]
    )
    def test_invalid(self, value):
        assert not is_slug_path(value)


class TestParse:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, ()),
            ("", ()),
            ("   ", ()),
            ("a", ("a",)),
            ("digital-twin.dt-platforms, a.b , Bad Path", ("digital-twin.dt-platforms", "a.b")),
            ("a, a", ("a",)),
            ("a, , b", ("a", "b")),
        ],
    )
    def test_reads_slug_paths_and_drops_invalid(self, value, expected):
        assert parse(value) == expected

    def test_order_is_preserved(self):
        """The ledger writes this as JSON, so a stable order is what keeps
        a re-sync of an unchanged entry from rewriting the row."""
        assert parse("z, a, m") == ("z", "a", "m")


class TestMatches:
    @pytest.mark.parametrize(
        "wanted,expected",
        [
            ("a", True),
            ("a.b", True),
            ("a.b.c", True),
            ("a.bc", False),
            ("b", False),
            ("a.b.c.d", False),
            ("", False),
        ],
    )
    def test_is_subtree_per_segment(self, wanted, expected):
        assert matches(("a.b.c",), wanted) is expected

    def test_a_sibling_with_a_shared_prefix_is_not_selected(self):
        assert matches(("a.bc",), "a.b") is False

    def test_no_collections_matches_nothing(self):
        assert matches((), "a") is False


class TestDisplayPaths:
    def test_any_depth(self):
        shown = display_paths(DEPTH_FOUR, ["digital-twins.platforms.cloud.public"])
        assert shown["digital-twins.platforms.cloud.public"] == (
            "Digital Twins / Platforms / Cloud / Public"
        )
        assert shown["digital-twins.platforms"] == "Digital Twins / Platforms"

    def test_ancestors_are_implied_without_a_table(self):
        assert display_paths({}, ["x.y.z"]) == {"x": "x", "x.y": "x / y", "x.y.z": "x / y / z"}

    def test_a_missing_row_falls_back_to_its_segment(self):
        assert display_paths({"a": "A"}, ["a.b"])["a.b"] == "A / b"

    def test_a_table_row_with_no_papers_is_listed(self):
        assert display_paths({"a": "A", "a.c": "C"}, ["a"]) == {"a": "A", "a.c": "A / C"}

    def test_nothing_known(self):
        assert display_paths({}, []) == {}


class TestResolve:
    def test_slug_path_any_depth(self):
        assert resolve("digital-twins.platforms.cloud", DEPTH_FOUR, []) == (
            "digital-twins.platforms.cloud"
        )

    def test_slug_path_is_casefolded(self):
        assert resolve(" Digital-Twins ", DEPTH_FOUR, []) == "digital-twins"

    def test_slug_path_known_only_from_an_entry(self):
        assert resolve("x.y", {}, ["x.y.z"]) == "x.y"

    def test_display_path_with_loose_spacing(self):
        assert resolve("digital twins/ platforms /CLOUD", DEPTH_FOUR, []) == (
            "digital-twins.platforms.cloud"
        )

    def test_a_name_containing_a_slash_is_never_split(self):
        names = {"net": "Networking", "net.tcp-ip": "TCP/IP"}
        assert resolve(" networking/TCP/IP ", names, []) == "net.tcp-ip"

    def test_a_single_segment_display_name(self):
        assert resolve("Medical", {"med": "Medical"}, []) == "med"

    def test_ambiguous_siblings_list_both(self):
        names = {"u": "Use Cases", "u.medical": "Medical", "u.medical-1": "Medical"}
        with pytest.raises(AmbiguousCollection) as e:
            resolve("Use Cases/Medical", names, [])
        assert e.value.slugs == ["u.medical", "u.medical-1"]
        assert e.value.wanted == "Use Cases/Medical"

    def test_unknown_flags_old_syntax(self):
        with pytest.raises(UnknownCollection) as e:
            resolve("Digital twins > Modelling", {}, [])
        assert e.value.old_syntax is True
        assert e.value.wanted == "Digital twins > Modelling"

    def test_unknown_slug(self):
        with pytest.raises(UnknownCollection) as e:
            resolve("a.nope", {"a": "A"}, [])
        assert e.value.old_syntax is False

    def test_empty_is_unknown(self):
        with pytest.raises(UnknownCollection):
            resolve("  ", {"a": "A"}, [])


class TestReport:
    @staticmethod
    def rows(spec):
        return [
            {"citekey": key, "collections": json.dumps(list(paths)) if paths else None}
            for key, paths in spec
        ]

    def test_columns_and_counts_include_descendants_and_empty_rows(self):
        lines = bib_collections.report(
            self.rows([("k1", ["a.b"]), ("k2", ["a"]), ("k3", [])]),
            {"a": "Alpha", "a.b": "Beta", "a.c": "Gamma"},
        )
        assert [line.split() for line in lines[:3]] == [
            ["a", "Alpha", "2"],
            ["a.b", "Alpha", "/", "Beta", "1"],
            ["a.c", "Alpha", "/", "Gamma", "0"],
        ]
        assert lines[-1] == "  3 collection(s)."

    def test_a_paper_in_two_branches_counts_once_per_ancestor(self):
        lines = bib_collections.report(self.rows([("k1", ["a.b", "a.c"])]), {})
        assert lines[0].split() == ["a", "a", "1"]

    def test_columns_line_up(self):
        lines = bib_collections.report(self.rows([("k1", ["a.long-name"])]), {})
        assert lines[0].index("a ") == lines[1].index("a.long-name")
        assert len({line.rstrip().rfind(" ") for line in lines[:2]}) == 1

    def test_nothing_recorded_points_at_the_importer(self):
        lines = bib_collections.report(self.rows([("k1", [])]), {})
        assert lines[0] == "No collections recorded."
        assert "chitragupta-importer" in lines[1]


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
        ledger.upsert_reference(ledger_con, make_reference(citekey="a_2024", collections=("x.y",)))
        row = ledger_con.execute("SELECT * FROM items WHERE citekey = 'a_2024'").fetchone()
        assert json.loads(row["collections"]) == ["x.y"]
        assert bib_collections.of_row(row) == ("x.y",)

    def test_no_collections_is_stored_as_null_not_an_empty_array(self, ledger_con):
        """Most libraries have no such field at all. NULL is what a
        pre-migration row already holds, and writing "[]" into every row
        instead would churn the ledger for no reader's benefit."""
        ledger.upsert_reference(ledger_con, make_reference(citekey="b_2024"))
        row = ledger_con.execute("SELECT * FROM items WHERE citekey = 'b_2024'").fetchone()
        assert row["collections"] is None
        assert bib_collections.of_row(row) == ()

    def test_an_update_rewrites_them(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="c_2024", collections=("old",)))
        ledger.upsert_reference(ledger_con, make_reference(citekey="c_2024", collections=("new",)))
        row = ledger_con.execute("SELECT * FROM items WHERE citekey = 'c_2024'").fetchone()
        assert bib_collections.of_row(row) == ("new",)

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
            ("in_sub_2024", ("digital-twins.modelling",)),
            ("in_other_2024", ("reading-list",)),
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
        retrieval_cache._load_cache.cache_clear() if hasattr(
            retrieval_cache._load_cache, "cache_clear"
        ) else None
        return isolated_config

    def test_unfiltered_search_returns_everything(self, corpus):
        found = retrieval.search("modelling", k=10)
        assert {r.citekey for r in found} == {"in_sub_2024", "in_other_2024", "uncollected_2024"}

    def test_a_parent_collection_selects_the_subtree(self, corpus):
        found = retrieval.search("modelling", k=10, collection="digital-twins")
        assert {r.citekey for r in found} == {"in_sub_2024"}

    def test_an_unknown_collection_returns_nothing(self, corpus):
        assert retrieval.search("modelling", k=10, collection="nonexistent") == []

    def test_an_item_with_no_collections_is_excluded_by_any_filter(self, corpus):
        found = retrieval.search("modelling", k=10, collection="reading-list")
        assert "uncollected_2024" not in {r.citekey for r in found}

    def test_scores_do_not_change_when_a_filter_is_applied(self, corpus):
        """Scoring stays corpus-wide on purpose: narrowing the index would
        change every IDF, so the same query would rank differently
        depending on the filter, and the cached index could not be shared."""
        unfiltered = {r.citekey: r.score for r in retrieval.search("modelling", k=10)}
        filtered = retrieval.search("modelling", k=10, collection="digital-twins")
        assert filtered[0].score == unfiltered["in_sub_2024"]


class TestTheLedgerCLI:
    """`--collections` and `--collection`, the read-only half of #195."""

    @pytest.fixture
    def corpus(self, isolated_config, ledger_con):
        for citekey, collections in (
            ("shelved_2024", ("digital-twins.modelling",)),
            ("elsewhere_2024", ("reading-list",)),
            ("bare_2024", ()),
        ):
            ledger.upsert_reference(
                ledger_con, make_reference(citekey=citekey, collections=collections)
            )
        ledger_con.commit()
        return isolated_config

    def test_collections_lists_every_path_with_its_ancestors(self, corpus, capsys):
        assert ledger_cli.main(["--collections"]) == 0
        rows = [line.split() for line in capsys.readouterr().out.splitlines()]
        assert ["digital-twins", "digital-twins", "1"] in rows
        assert ["digital-twins.modelling", "digital-twins", "/", "modelling", "1"] in rows
        assert ["reading-list", "reading-list", "1"] in rows
        assert ["3", "collection(s)."] in rows

    def test_collections_on_a_corpus_without_any_explains_why(
        self, isolated_config, ledger_con, capsys
    ):
        """The likeliest cause of an empty list is the export, not the
        library, so the empty case is guidance rather than a result."""
        ledger.upsert_reference(ledger_con, make_reference(citekey="none_2024"))
        ledger_con.commit()
        assert ledger_cli.main(["--collections"]) == 0
        out = capsys.readouterr().out
        assert "No collections recorded." in out
        assert "chitragupta-importer" in out

    def test_collection_filters_the_listing_and_includes_the_subtree(self, corpus, capsys):
        assert ledger_cli.main(["--collection", "digital-twins"]) == 0
        out = capsys.readouterr().out
        assert "shelved_2024" in out
        assert "elsewhere_2024" not in out
        assert "bare_2024" not in out

    def test_an_empty_collection_says_so_rather_than_naming_a_status(self, corpus, capsys):
        """`--list` reports "no items with status None" when empty, which
        would be a confusing thing to print at someone who asked about a
        collection."""
        assert ledger_cli.main(["--collection", "nonexistent"]) == 0
        assert "No items in collection 'nonexistent'." in capsys.readouterr().out
