"""`chitragupta/bib_parse.py`: bibtexparser 2 read into bibtexparser 1.x's
entry dicts.

`EXPECTED` below is what bibtexparser 1.4.4 returned for `AWKWARD_BIB`
(through `bib_reader`'s old customization), recorded before 1.x left the
lock, so these tests keep checking 1.x's behaviour after it is gone.
The file is built to hit every rule the module docstring lists. The same
comparison was run on 2,365 references from three real reference-manager
exports and differed on none.
"""

import logging

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
        """Reverse file order, then ENTRYTYPE and ID, then `file` last.
        The dicts become `Reference.fields`, which is stored, so order is
        part of the output."""
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
        """1.x raised `UndefinedString` here and the whole sync died with
        a traceback; one stray macro in an export is not worth that."""
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
        """`{a<TAB>}` was `a` and five spaces under 1.x: the tab sits at
        column 19 of `@misc{k, title = {a`, and the next stop is 24."""
        assert self._one("title = {a\t}")["title"] == "a     "


class TestWhatIsSkipped:
    def test_a_non_standard_type_is_skipped_and_said(self, caplog):
        """Issue 888: skipped by design, and logged in 1.x's words."""
        with caplog.at_level(logging.WARNING, logger="chitragupta.bib_parse"):
            entries = bib_parse.parse_entries("@software{s, title = {x}}\n")
        assert entries == []
        assert "Entry type software not standard. Not considered." in caplog.text

    def test_an_entry_with_no_fields_is_skipped(self):
        """`bib_integrity.block_has_fields` does not count such a stub as
        an entry either, so the two still agree."""
        assert bib_parse.parse_entries("@misc{stub,\n}\n") == []

    def test_a_citekey_with_braces_is_refused_not_rewritten(self):
        """1.x decoded `Thesis_{X}` into the citekey `Thesis_X` -- a key
        the bib file does not contain. 2.x refuses the block instead, so
        `bib_integrity.dropped_entries` counts and warns about it."""
        text = "@phdthesis{Thesis_{X}, title = {Braced key}}\n@misc{ok, title = {T}}\n"
        assert [e["ID"] for e in bib_parse.parse_entries(text)] == ["ok"]


class TestDuplicates:
    def test_both_entries_under_one_citekey_come_back(self):
        """`bib_integrity.duplicated_citekeys` refuses both, and can only
        do that if it sees both (issue 840)."""
        got = bib_parse.parse_entries("@misc{k, title = {one}}\n@book{k, title = {two}}\n")
        assert [(e["ID"], e["title"]) for e in got] == [("k", "one"), ("k", "two")]

    def test_the_first_of_two_same_named_fields_wins(self):
        got = bib_parse.parse_entries("@misc{k, doi = {first}, DOI = {second}}\n")
        assert got[0]["doi"] == "first"


class TestTheFileField:
    def test_a_zotero_path_is_left_raw(self):
        """#964: decoding `\\;` raised TypeError and ended the read."""
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
