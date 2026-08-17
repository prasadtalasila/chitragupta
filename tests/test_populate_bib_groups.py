"""`scripts/populate_bib_groups.py`: filling a `groups` field a plain Zotero
export never wrote.

The script is the one place in this repository that reads `zotero.sqlite`
directly instead of an export, and docs/EXPORT-ZOTERO-GROUPS.md carries the
warning about why that is a last resort. These tests exist mainly so the
warning is the *only* thing wrong with it: the matching rules, the splice
and the statistics are pinned here so a future edit cannot quietly change
what lands in the `groups` field.

The Zotero schema is rebuilt in memory rather than read from
`papers/zotero.sqlite`, for two reasons. A real library is not a fixture
anyone else can run, and -- more to the point -- the interesting cases
(a DOI hidden in `extra`, a title that only matches after LaTeX is
decoded, one bib entry hitting two duplicate Zotero items) are all easier
to state as three rows than to find in 644 real ones.

The end-to-end check against the real library is a smoke test run by hand,
recorded in the PR, not here.
"""

import sqlite3
from contextlib import closing

import pytest

from scripts import populate_bib_groups as pbg


@pytest.fixture
def make_db():
    """Builds throwaway Zotero-shaped databases, and closes them afterwards.

    A factory rather than a plain helper so that the connections have an
    owner: most call sites build one inline inside the call under test and
    have nowhere to hold a handle, and an unclosed sqlite connection
    raises a ResourceWarning when it is eventually collected. The fixture
    closes whatever it handed out, however the test ended.

    The factory takes (itemID, fieldName, value) triples, then
    (collectionID, collectionName) pairs, then (collectionID, itemID)
    pairs. Field IDs and value IDs are assigned here because nothing in
    the script cares what they are -- only that the three-way join
    reaches the value.
    """
    created = []

    def build(items=(), collections=(), memberships=()):
        con = sqlite3.connect(":memory:")
        created.append(con)
        con.executescript("""
            create table fieldsCombined (fieldID integer, fieldName text);
            create table itemDataValues (valueID integer, value);
            create table itemData (itemID integer, fieldID integer, valueID integer);
            create table collections (collectionID integer, collectionName text);
            create table collectionItems (collectionID integer, itemID integer);
        """)
        field_ids = {}
        for row_id, (item_id, field_name, value) in enumerate(items, start=1):
            field_id = field_ids.setdefault(field_name, len(field_ids) + 1)
            con.execute("insert into fieldsCombined values (?, ?)",
                        (field_id, field_name))
            con.execute("insert into itemDataValues values (?, ?)", (row_id, value))
            con.execute("insert into itemData values (?, ?, ?)",
                        (item_id, field_id, row_id))
        con.executemany("insert into collections values (?, ?)", collections)
        con.executemany("insert into collectionItems values (?, ?)", memberships)
        return con

    yield build
    for con in created:
        con.close()


def bib(body, key="smith2020", entry_type="article"):
    """One entry in the tab-indented layout Zotero's BibTeX translator writes."""
    return "@%s{%s,\n%s\n}\n" % (entry_type, key, body)


class TestStripDoi:
    """DOIs arrive with trailing punctuation when they were scraped out of prose."""

    @pytest.mark.parametrize("raw,expected", [
        ("10.1234/ABC", "10.1234/abc"),
        ("  10.1234/abc  ", "10.1234/abc"),
        ("10.1234/abc.", "10.1234/abc"),
        ("10.1234/abc),", "10.1234/abc"),
        ("10.1234/abc]", "10.1234/abc"),
        ("10.1234/abc>", "10.1234/abc"),
    ])
    def test_punctuation_and_case_are_normalised(self, raw, expected):
        assert pbg.strip_doi(raw) == expected


class TestNormaliseTitle:
    """Titles are compared across two encodings: BibTeX's and Zotero's.

    Zotero stores a title as plain Unicode. BibTeX brace-protects
    capitals and escapes accents, so the two never match as written --
    every case here is a pair that must collapse to one string.
    """

    def test_brace_protection_is_dropped(self):
        assert pbg.normalise_title("The {OMG} {Standard}") == "the omg standard"

    def test_whitespace_is_collapsed_and_case_folded(self):
        assert pbg.normalise_title("  A   Long\n\tTitle ") == "a long title"

    def test_an_empty_title_normalises_to_empty(self):
        assert pbg.normalise_title("") == ""


class TestReadFields:
    """Reading is delegated to bibtexparser, which is the point of the module.

    Each case here is something the hand-rolled regex parser this replaced
    got wrong or could not see at all.
    """

    def test_an_accent_decodes_to_the_character_zotero_stores(self):
        # The regex version stripped the accent (`\'{e}` -> `e`), so an
        # accented title never matched Zotero's `é` and fell through to
        # "unmatched". This is the case that motivated the rewrite.
        fields = pbg.read_fields(bib("\t" + r"title = {Caf\'{e} Design},"))
        assert pbg.normalise_title(fields["smith2020"]["title"]) == "café design"

    def test_a_value_spanning_lines_is_joined(self):
        fields = pbg.read_fields(bib("\ttitle = {A Title\n\t\tacross lines},"))
        assert pbg.normalise_title(fields["smith2020"]["title"]) == "a title across lines"

    def test_a_nested_brace_does_not_end_the_value(self):
        fields = pbg.read_fields(bib("\ttitle = {The {OMG} Spec},\n\turl = {http://x/a},"))
        assert fields["smith2020"]["url"] == "http://x/a"

    def test_field_names_are_lowercased(self):
        fields = pbg.read_fields(bib("\tDOI = {10.1234/a},"))
        assert fields["smith2020"]["doi"] == "10.1234/a"


class TestScanEntries:
    """The splice needs byte offsets, which the parser does not report."""

    def test_the_close_position_is_the_entrys_own_closing_brace(self):
        text = bib("\ttitle = {X},")
        [(key, close_pos)] = pbg.scan_entries(text)
        assert key == "smith2020"
        assert text[close_pos] == "}"
        assert text[close_pos:] == "}\n"

    def test_a_brace_inside_a_value_is_not_mistaken_for_the_end(self):
        text = bib("\ttitle = {The {OMG} {Spec}},")
        [(_, close_pos)] = pbg.scan_entries(text)
        assert text[close_pos:] == "}\n"

    def test_entries_are_returned_in_file_order(self):
        text = bib("\ttitle = {A},", key="a") + bib("\ttitle = {B},", key="b")
        assert [key for key, _ in pbg.scan_entries(text)] == ["a", "b"]

    def test_an_unbalanced_entry_is_reported_rather_than_truncating_output(self):
        # Silently dropping the tail of a bibliography is the one failure
        # this script must not have, so this raises rather than returning
        # what it managed to parse.
        with pytest.raises(ValueError, match="unbalanced"):
            pbg.scan_entries("@article{broken,\n\ttitle = {X},\n")


class TestBuildIndexes:
    def test_a_doi_is_found_in_its_own_field(self, make_db):
        indexes = pbg.build_indexes(make_db(items=[(1, "DOI", "10.1234/abc")]))
        assert indexes.doi["10.1234/abc"] == {1}

    def test_a_doi_buried_in_extra_is_found_too(self, make_db):
        # Older conferencePaper records have no DOI field and stash it in
        # `extra`; scanning every field value is the only way to see it.
        indexes = pbg.build_indexes(make_db(
            items=[(7, "extra", "PMID: 99\nDOI: 10.1234/xyz")]))
        assert indexes.doi["10.1234/xyz"] == {7}

    def test_a_non_text_field_value_is_skipped_not_crashed_on(self, make_db):
        # itemDataValues.value is untyped in Zotero's schema and a numeric
        # year arrives as an int; DOI_RE cannot run on that.
        indexes = pbg.build_indexes(make_db(items=[(1, "date", 2020)]))
        assert not indexes.doi

    def test_duplicate_items_sharing_a_doi_both_land_under_it(self, make_db):
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a"), (2, "DOI", "10.1234/A")]))
        assert indexes.doi["10.1234/a"] == {1, 2}

    def test_url_is_indexed_exactly_but_stripped(self, make_db):
        indexes = pbg.build_indexes(make_db(items=[(3, "url", "  http://x/a ")]))
        assert indexes.url["http://x/a"] == {3}

    def test_title_is_indexed_normalised(self, make_db):
        indexes = pbg.build_indexes(make_db(items=[(4, "title", "The  OMG Spec")]))
        assert indexes.title["the omg spec"] == {4}

    def test_collections_are_the_leaf_name_only(self, make_db):
        # Zotero nests collections, but Better BibTeX writes only the leaf
        # name and this script matches that convention deliberately.
        indexes = pbg.build_indexes(make_db(
            collections=[(10, "Digital Twin"), (11, "Theoretical Concepts")],
            memberships=[(11, 5)]))
        assert indexes.collections[5] == {"Theoretical Concepts"}

    def test_an_item_in_no_collection_is_absent_rather_than_empty(self, make_db):
        indexes = pbg.build_indexes(make_db(items=[(1, "DOI", "10.1234/a")]))
        assert 1 not in indexes.collections


class TestMatchItemIds:
    """Match order is DOI, then URL, then title -- first hit wins."""

    @pytest.fixture
    def indexes(self, make_db):
        return pbg.build_indexes(make_db(items=[
            (1, "DOI", "10.1234/a"),
            (2, "url", "http://x/b"),
            (3, "title", "A Plain Title"),
        ]))

    def test_doi_wins_when_present(self, indexes):
        fields = {"doi": "10.1234/A", "url": "http://x/b", "title": "A Plain Title"}
        assert pbg.match_item_ids(fields, indexes) == ({1}, "doi")

    def test_url_is_used_when_the_doi_does_not_hit(self, indexes):
        fields = {"doi": "10.9999/miss", "url": "http://x/b"}
        assert pbg.match_item_ids(fields, indexes) == ({2}, "url")

    def test_title_is_the_last_resort(self, indexes):
        assert pbg.match_item_ids({"title": "a plain  title"}, indexes) == ({3}, "title")

    def test_url_is_used_when_there_is_no_doi_field_at_all(self, indexes):
        assert pbg.match_item_ids({"url": "http://x/b"}, indexes) == ({2}, "url")

    def test_title_is_used_when_there_is_no_url_field_at_all(self, indexes):
        assert pbg.match_item_ids({"title": "A Plain Title"}, indexes) == ({3}, "title")

    def test_an_entry_matching_nothing_reports_no_method(self, indexes):
        fields = {"doi": "10.9999/x", "url": "http://nope", "title": "Nothing Like It"}
        assert pbg.match_item_ids(fields, indexes) == (None, None)

    def test_an_entry_with_no_usable_field_reports_no_method(self, indexes):
        assert pbg.match_item_ids({"note": "x"}, indexes) == (None, None)


class TestEscapeGroupName:
    def test_a_comma_would_split_the_field_so_becomes_a_semicolon(self):
        assert pbg.escape_group_name("A, B") == "A; B"

    def test_an_ordinary_name_is_untouched(self):
        assert pbg.escape_group_name("Digital Twin") == "Digital Twin"


class TestPopulate:
    """The splice: what lands in the file, and where."""

    def test_a_matched_entry_gains_a_groups_field_before_its_closing_brace(self, make_db):
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a")],
            collections=[(10, "Digital Twin")], memberships=[(10, 1)]))
        text = bib("\tdoi = {10.1234/a},")
        out, _ = pbg.populate(text, indexes)
        assert out == "@article{smith2020,\n\tdoi = {10.1234/a},\n\tgroups = {Digital Twin},\n}\n"

    def test_several_collections_are_sorted_and_comma_joined(self, make_db):
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a")],
            collections=[(10, "Standards"), (11, "Digital Twin")],
            memberships=[(10, 1), (11, 1)]))
        out, _ = pbg.populate(bib("\tdoi = {10.1234/a},"), indexes)
        assert "\tgroups = {Digital Twin,Standards},\n" in out

    def test_duplicate_zotero_items_union_their_collections(self, make_db):
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a"), (2, "DOI", "10.1234/a")],
            collections=[(10, "Standards"), (11, "Digital Twin")],
            memberships=[(10, 1), (11, 2)]))
        out, stats = pbg.populate(bib("\tdoi = {10.1234/a},"), indexes)
        assert "\tgroups = {Digital Twin,Standards},\n" in out
        assert stats["matched_multiple_items"] == 1

    def test_an_entry_that_already_has_groups_is_left_alone(self, make_db):
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a")],
            collections=[(10, "Other")], memberships=[(10, 1)]))
        text = bib("\tdoi = {10.1234/a},\n\tgroups = {Kept},")
        out, stats = pbg.populate(text, indexes)
        assert out == text
        assert stats["already_had_groups"] == 1

    def test_an_unmatched_entry_is_counted_and_left_alone(self, make_db):
        indexes = pbg.build_indexes(make_db(items=[(1, "DOI", "10.1234/a")]))
        text = bib("\tdoi = {10.9999/nope},")
        out, stats = pbg.populate(text, indexes)
        assert out == text
        assert stats["unmatched"] == 1

    def test_a_matched_item_filed_nowhere_is_counted_separately(self, make_db):
        # Not a failure: the item exists, it is just in no collection.
        indexes = pbg.build_indexes(make_db(items=[(1, "DOI", "10.1234/a")]))
        out, stats = pbg.populate(bib("\tdoi = {10.1234/a},"), indexes)
        assert "groups" not in out
        assert stats["matched_no_collection_via_doi"] == 1

    def test_text_between_and_after_entries_is_preserved_verbatim(self, make_db):
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a")],
            collections=[(10, "G")], memberships=[(10, 1)]))
        text = "% a comment\n" + bib("\tdoi = {10.1234/a},") + "\n% trailing\n"
        out, _ = pbg.populate(text, indexes)
        assert out.startswith("% a comment\n")
        assert out.endswith("\n% trailing\n")

    def test_two_matched_entries_are_both_spliced_in_order(self, make_db):
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a"), (2, "DOI", "10.1234/b")],
            collections=[(10, "First"), (11, "Second")],
            memberships=[(10, 1), (11, 2)]))
        text = bib("\tdoi = {10.1234/a},", key="a") + bib("\tdoi = {10.1234/b},", key="b")
        out, _ = pbg.populate(text, indexes)
        assert out.index("First") < out.index("Second")
        assert out.count("groups = {") == 2

    def test_a_block_bibtexparser_does_not_return_as_an_entry_is_skipped(self, make_db):
        # @comment blocks carry no fields to match on. The scan sees them
        # and the parser does not, so the splice must tolerate the gap
        # rather than mis-aligning every entry after it.
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a")],
            collections=[(10, "G")], memberships=[(10, 1)]))
        text = "@comment{jabref-meta,\n}\n" + bib("\tdoi = {10.1234/a},")
        out, stats = pbg.populate(text, indexes)
        assert out.count("groups = {") == 1
        assert out.startswith("@comment{jabref-meta,\n}\n")
        assert stats["no_fields"] == 1

    def test_every_block_lands_in_exactly_one_bucket(self, make_db):
        # The buckets are what the summary reports, so a block falling
        # through all of them would under-report the file silently. This
        # is the property that keeps `groups added + skipped == total`.
        indexes = pbg.build_indexes(make_db(
            items=[(1, "DOI", "10.1234/a"), (2, "DOI", "10.1234/b")],
            collections=[(10, "G")], memberships=[(10, 1)]))
        text = ("@comment{meta,\n}\n"
                + bib("\tdoi = {10.1234/a},", key="filed")
                + bib("\tdoi = {10.1234/b},", key="unfiled")
                + bib("\tdoi = {10.9999/nope},", key="missing")
                + bib("\tdoi = {10.1234/a},\n\tgroups = {Kept},", key="kept"))
        _, stats = pbg.populate(text, indexes)
        counted = sum(value for key, value in stats.items()
                      if key not in ("entries_total", "matched_multiple_items"))
        assert counted == stats["entries_total"] == 5


class TestFormatStats:
    def test_the_summary_names_the_total_and_each_bucket(self):
        lines = pbg.format_stats(
            {"entries_total": 3, "matched_via_doi": 2, "unmatched": 1})
        assert "entries total:            3" in lines
        assert any("matched_via_doi" in line and "2" in line for line in lines)

    def test_the_total_is_not_repeated_as_a_bucket_line(self):
        lines = pbg.format_stats({"entries_total": 3, "unmatched": 3})
        assert not any(line.startswith("entries_total") for line in lines)

    def test_only_matched_via_buckets_count_toward_the_added_total(self):
        # `matched_no_collection_via_doi` starts with "matched" but adds no
        # field, so a prefix test on "matched" would overcount.
        lines = pbg.format_stats({"entries_total": 2, "matched_via_doi": 1,
                                  "matched_no_collection_via_doi": 1})
        assert "groups field added to:    1 / 2 entries" in lines


class TestMain:
    @pytest.fixture
    def library(self, tmp_path, make_db):
        db_path = tmp_path / "zotero.sqlite"
        source = make_db(items=[(1, "DOI", "10.1234/a")],
                         collections=[(10, "Digital Twin")], memberships=[(10, 1)])
        source.commit()
        with closing(sqlite3.connect(db_path)) as on_disk:
            source.backup(on_disk)
        return db_path

    def test_it_writes_the_output_file_and_leaves_the_input_untouched(
            self, tmp_path, library, capsys):
        in_path = tmp_path / "in.bib"
        in_path.write_text(bib("\tdoi = {10.1234/a},"), encoding="utf-8")
        out_path = tmp_path / "out.bib"

        assert pbg.main([str(library), str(in_path), str(out_path)]) == 0

        assert "groups = {Digital Twin}" in out_path.read_text(encoding="utf-8")
        assert "groups" not in in_path.read_text(encoding="utf-8")
        assert "groups field added to:    1 / 1 entries" in capsys.readouterr().out

    def test_wrong_argument_count_exits_non_zero_with_a_usage_line(self, capsys):
        assert pbg.main(["only-one"]) == 2
        assert "usage:" in capsys.readouterr().err

    def test_the_database_is_opened_read_only(self, library):
        # The doc promises it is safe to run while Zotero is open. That
        # rests entirely on the mode=ro URI, so pin it: a writable open
        # would let a bug corrupt somebody's library.
        with closing(pbg.open_library(library)) as con:
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                con.execute("delete from collections")
