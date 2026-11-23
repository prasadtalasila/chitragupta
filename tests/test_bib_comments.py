"""The `@comment` tab tables chitragupta-importer writes at the top of a bib.

Two blocks use this shape, `cg-collections` (slug path, name) and
`cg-renames` (old citekey, new citekey). The reading rule is the owner's
(plans/1211-cg-collections-and-renames.md, D5): fields 1 and 2 of each
row whatever the version, further fields ignored, a row whose key is not
valid skipped, and the version reported so a caller can flag it.
"""

from chitragupta import bib_collections
from chitragupta.bib_comments import KNOWN_VERSION, comment_blocks, read_tables

TABLE = "cg-collections"


class TestCommentBlocks:
    def test_tabs_survive(self):
        """bibtexparser 1.x expands tabs in comments, which is why this
        module reads the raw text at all."""
        raw = "@comment{cg-collections v1\na\tA\n}\n@article{k, title={T}}\n"
        assert comment_blocks(raw) == ["cg-collections v1\na\tA\n"]

    def test_escaped_braces_do_not_end_the_block(self):
        raw = "@comment{cg-collections v1\na\tSet \\{x\\}\nb\tB\n}"
        assert comment_blocks(raw) == ["cg-collections v1\na\tSet \\{x\\}\nb\tB\n"]

    def test_nested_braces_are_matched(self):
        assert comment_blocks("@Comment{x {y} z}") == ["x {y} z"]

    def test_case_and_spacing_of_the_keyword(self):
        assert comment_blocks("@COMMENT {x}") == ["x"]

    def test_an_unterminated_block_is_dropped(self):
        assert comment_blocks("@comment{cg-collections v1\na\tA\n") == []

    def test_no_blocks(self):
        assert comment_blocks("@article{k, title={T}}") == []


class TestReadTables:
    def test_v1_rows(self):
        t = read_tables(["cg-collections v1\na\tA\na.b\tB\n"], TABLE, bib_collections.is_slug_path)
        assert (t.version, t.rows, t.skipped) == ("v1", (("a", "A"), ("a.b", "B")), ())

    def test_no_block_of_that_name(self):
        assert read_tables(["jabref-meta: x;"], TABLE, bib_collections.is_slug_path) is None

    def test_a_name_that_only_starts_the_same_is_another_block(self):
        assert read_tables(["cg-collections-extra v1\na\tA"], TABLE, str.isalpha) is None

    def test_tolerant_of_extra_fields_and_unknown_version(self):
        t = read_tables(
            ["cg-collections v2\na\tA\tK7Q2\nBad Row\tX\n"], TABLE, bib_collections.is_slug_path
        )
        assert (t.version, t.rows, t.skipped) == ("v2", (("a", "A"),), ("Bad Row\tX",))

    def test_blank_lines_and_an_empty_block_are_ignored(self):
        t = read_tables(
            ["", "cg-collections v1\n\na\tA\n  \n"], TABLE, bib_collections.is_slug_path
        )
        assert (t.rows, t.skipped) == ((("a", "A"),), ())

    def test_a_row_without_a_tab_is_skipped(self):
        t = read_tables(["cg-collections v1\nlonely\n"], TABLE, bib_collections.is_slug_path)
        assert (t.rows, t.skipped) == ((), ("lonely",))

    def test_braces_are_unescaped_and_names_stripped(self):
        t = read_tables(
            ["cg-collections v1\na\t Set \\{x\\} \n"], TABLE, bib_collections.is_slug_path
        )
        assert t.rows == (("a", "Set {x}"),)

    def test_a_missing_version_is_not_the_known_one(self):
        t = read_tables(["cg-collections\na\tA\n"], TABLE, bib_collections.is_slug_path)
        assert t.version == "" and t.version != KNOWN_VERSION

    def test_two_blocks_merge_and_the_first_row_wins(self):
        t = read_tables(
            ["cg-collections v1\na\tFirst\n", "cg-collections v1\na\tSecond\nb\tB\n"],
            TABLE,
            bib_collections.is_slug_path,
        )
        assert t.rows == (("a", "First"), ("b", "B"))

    def test_any_unknown_version_among_blocks_is_reported(self):
        t = read_tables(
            ["cg-collections v1\na\tA\n", "cg-collections v3\nb\tB\n"],
            TABLE,
            bib_collections.is_slug_path,
        )
        assert t.version == "v3"
