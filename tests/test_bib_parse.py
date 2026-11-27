import logging

import pytest

from chitragupta import bib_parse

AWKWARD_BIB = r"""@string{myj = "My Journal"}
@STRING{Feb = {Febbraio}}
@string{both = myj # " and more"}
@preamble{"\newcommand{\noop}[1]{}"}
@comment{a comment block}

@ARTICLE{Upper2020,
  Title = {A {B} Title},
  AUTHOR = {M{\"u}ller, Hans and Jos\'{e} Garc\'{i}a},
  month = jan,
  journal = myj # " vol",
  note = "quoted {inner} value",
  year = 2020,
  volume = {},
  pages = {105--107},
  abstract = {  leading and trailing
  },
  keywords = both,
  url = {https://example.org/a_b%20c}
}

@inproceedings{dupfield_2021,
  title = {First},
  doi = {10.1/x},
  title = {Second},
  doi = {10.1/x}
}

@misc{samekey, title = {one}}
@book{samekey, title = {two}}

@misc{stub,
}
@software{sw_2022, title = {Software}}
@online{web_2023, title = {Online}}

@article(paren_2019,
  title = "Paren form",
  month = feb
)

@techreport{filefield_2024,
  title = {With a file},
  file = {:files/12/Smith{\_}2024.pdf:application/pdf}
}

@misc{zotero_2024,
  title = {Zotero file},
  file = {Full Text PDF:/home/u/Zotero/storage/AB\;CD/paper.pdf:application/pdf}
}
"""

EXPECTED = [
    {
        "url": "https://example.org/a_b%20c",
        "keywords": "My Journal and more",
        "abstract": "  leading and trailing\n",
        "pages": "105--107",
        "volume": "",
        "year": "2020",
        "note": "quoted inner value",
        "journal": "My Journal vol",
        "month": "January",
        "author": "Müller, Hans and José García",
        "title": "A B Title",
        "ENTRYTYPE": "article",
        "ID": "Upper2020",
    },
    {"doi": "10.1/x", "title": "First", "ENTRYTYPE": "inproceedings", "ID": "dupfield_2021"},
    {"title": "one", "ENTRYTYPE": "misc", "ID": "samekey"},
    {"title": "two", "ENTRYTYPE": "book", "ID": "samekey"},
    {"month": "Febbraio", "title": "Paren form", "ENTRYTYPE": "article", "ID": "paren_2019"},
    {
        "title": "With a file",
        "ENTRYTYPE": "techreport",
        "ID": "filefield_2024",
        "file": ":files/12/Smith_2024.pdf:application/pdf",
    },
    {
        "title": "Zotero file",
        "ENTRYTYPE": "misc",
        "ID": "zotero_2024",
        "file": "Full Text PDF:/home/u/Zotero/storage/AB\\;CD/paper.pdf:application/pdf",
    },
]


def _by_id(entries):
    return {(e["ID"], e["ENTRYTYPE"]): e for e in entries}


class TestMatchesBibtexparser1:
    def test_every_entry_and_value_is_what_1x_returned(self):
        assert bib_parse.parse_entries(AWKWARD_BIB) == EXPECTED

    def test_the_key_order_is_1xs_too(self):
        got = bib_parse.parse_entries(AWKWARD_BIB)
        assert [list(e) for e in got] == [list(e) for e in EXPECTED]


class TestValues:
    def _one(self, body, **strings):
        defs = "".join(f"@string{{{k} = {{{v}}}}}\n" for k, v in strings.items())
        (entry,) = bib_parse.parse_entries(defs + "@misc{k, " + body + "}\n")
        return entry

    def test_a_month_macro_expands_and_a_files_own_string_overrides_it(self):
        assert self._one("month = mar")["month"] == "March"
        assert self._one("month = mar", mar="Marzo")["month"] == "Marzo"

    def test_an_undefined_macro_is_kept_rather_than_ending_the_read(self):
        assert self._one("number = nosuchmacro")["number"] == "nosuchmacro"

    def test_a_hash_inside_braces_or_quotes_does_not_concatenate(self):
        assert self._one("title = {C# and F#}")["title"] == "C# and F#"
        assert self._one('title = "C# " # {rocks}')["title"] == "C# rocks"

    def test_one_trailing_newline_goes_and_indentation_after_a_newline_goes(self):
        assert self._one("abstract = {a\n}")["abstract"] == "a"
        assert self._one("abstract = {a\n\n}")["abstract"] == "a\n"
        assert self._one("abstract = {a\r\n}")["abstract"] == "a"
        assert self._one("abstract = {a \n   b}")["abstract"] == "a \nb"
        assert self._one("abstract = {a\n  b}")["abstract"] == "a\nb"

    def test_a_tab_is_expanded_by_column_as_pyparsing_did(self):
        assert self._one("title = {a\t}")["title"] == "a     "


class TestWhatIsSkipped:
    def test_a_non_standard_type_is_skipped_and_said(self, caplog):
        with caplog.at_level(logging.WARNING, logger="chitragupta.bib_parse"):
            entries = bib_parse.parse_entries("@software{s, title = {x}}\n")
        assert entries == []
        assert "Entry type software not standard. Not considered." in caplog.text

    def test_an_entry_with_no_fields_is_skipped(self):
        assert bib_parse.parse_entries("@misc{stub,\n}\n") == []

    def test_a_citekey_with_braces_is_refused_not_rewritten(self):
        text = "@phdthesis{Thesis_{X}, title = {Braced key}}\n@misc{ok, title = {T}}\n"
        assert [e["ID"] for e in bib_parse.parse_entries(text)] == ["ok"]


class TestDuplicates:
    def test_both_entries_under_one_citekey_come_back(self):
        got = bib_parse.parse_entries("@misc{k, title = {one}}\n@book{k, title = {two}}\n")
        assert [(e["ID"], e["title"]) for e in got] == [("k", "one"), ("k", "two")]

    def test_the_first_of_two_same_named_fields_wins(self):
        got = bib_parse.parse_entries("@misc{k, doi = {first}, DOI = {second}}\n")
        assert got[0]["doi"] == "first"


class TestTheFileField:
    def test_a_zotero_path_is_left_raw(self):
        got = _by_id(bib_parse.parse_entries(AWKWARD_BIB))[("zotero_2024", "misc")]
        assert "AB\\;CD" in got["file"]

    def test_a_mendeley_path_is_decoded(self):
        got = _by_id(bib_parse.parse_entries(AWKWARD_BIB))[("filefield_2024", "techreport")]
        assert got["file"] == ":files/12/Smith_2024.pdf:application/pdf"

    def test_a_file_field_whose_decode_fails_is_kept_raw(self, monkeypatch):
        def boom(_value):
            raise TypeError("combining() argument must be a unicode character")

        monkeypatch.setattr(bib_parse.bib_latex, "latex_to_unicode", boom)
        assert bib_parse._decoded_file("{\\x}") == "{\\x}"


IMPORTER_HEAD = (
    "@comment{cg-renames v1\n"
    "lehner_pattern_2023-1\tlehner_pattern_2023\n"
    "old_a_2020\told_b_2020\n"
    "old_b_2020\tkept_2020\n"
    "}\n\n"
    "@comment{cg-collections v1\n"
    "dt\tDigital Twin\n"
    "dt.at\tTwins @ Scale\n"
    "dt.fake\t@article\\{fake, title=\\{x\\}\\}\n"
    "}\n\n"
)


def _importer_entry(key, abstract):
    return (
        f"@article{{{key},\n\ttitle = {{T}},\n\tabstract = {{{abstract}}},\n"
        f"\tfile = {{Full Text PDF:files/{key}.pdf:application/pdf}},\n"
        "\tcg-collections = {dt, dt.at},\n}\n"
    )


class TestALineStartingWithAnAtSignInsideAValue:
    @pytest.mark.parametrize(
        "abstract",
        [
            "First line\n@article(see Smith, 2020)",
            "Code:\n@dataclass(frozen=True)",
            "Open\n@book( never closed",
            "Raw braces\n@misc{looks like an entry}",
            "Indented\n   @Test(expected=Error.class)",
        ],
    )
    def test_the_entry_survives_and_the_value_is_unchanged(self, abstract):
        text = IMPORTER_HEAD + _importer_entry("k1", abstract) + "\n" + _importer_entry("k2", "x")
        entries = bib_parse.parse_entries(text)
        assert [e["ID"] for e in entries] == ["k1", "k2"]
        expected = bib_parse.bib_latex.latex_to_unicode(abstract.replace("\n   ", "\n"))
        assert entries[0]["abstract"] == expected

    def test_an_unbalanced_entry_is_still_skipped_and_the_rest_kept(self):
        text = (
            "@article{a,\n\ttitle = {ok},\n}\n\n"
            "@article{b,\n\ttitle = {never closed,\n}\n\n"
            "@article{c,\n\ttitle = {fine},\n}\n\n"
            "@article{d,\n\ttitle = {fine too},\n}\n"
        )
        assert [e["ID"] for e in bib_parse.parse_entries(text)] == ["a", "c", "d"]

    def test_the_comment_tables_yield_no_entry_and_hide_none(self):
        text = IMPORTER_HEAD + _importer_entry("lehner_pattern_2023", "x")
        assert [e["ID"] for e in bib_parse.parse_entries(text)] == ["lehner_pattern_2023"]

    def test_a_private_use_character_already_in_the_file_comes_back_as_written(self):
        abstract = "has \ue000 in it\n@article(and a guarded line)"
        text = _importer_entry("k1", abstract) + "\n" + _importer_entry("k2", "x")
        entries = bib_parse.parse_entries(text)
        assert [e["ID"] for e in entries] == ["k1", "k2"]
        assert entries[0]["abstract"] == abstract


class TestAValueTheDecoderCannotRead:
    def test_is_kept_raw_rather_than_ending_the_read(self):
        text = (
            "@misc{k1,\n\ttitle = {T},\n\turl = {https://e.org/a\\;b},\n}\n\n"
            "@misc{k2,\n\ttitle = {Next},\n}\n"
        )
        entries = bib_parse.parse_entries(text)
        assert [e["ID"] for e in entries] == ["k1", "k2"]
        assert entries[0]["url"] == r"https://e.org/a\;b"


class TestABackslashBeforeABrace:
    @pytest.mark.parametrize("field", ["url", "doi"])
    def test_a_value_ending_in_a_backslash_keeps_its_entry(self, field):
        text = (
            f"@misc{{k1,\n\ttitle = {{T}},\n\t{field} = {{https://e.org/a\\}},\n}}\n\n"
            "@misc{k2,\n\ttitle = {Next},\n}\n"
        )
        entries = bib_parse.parse_entries(text)
        assert [e["ID"] for e in entries] == ["k1", "k2"]
        assert entries[0][field] == "https://e.org/a\\"

    def test_an_escaped_brace_inside_a_value_decodes_as_before(self):
        text = "@misc{k1,\n\ttitle = {Paired \\{X\\} name},\n}\n"
        (entry,) = bib_parse.parse_entries(text)
        assert entry["title"] == bib_parse.bib_latex.latex_to_unicode("Paired \\{X\\} name")
