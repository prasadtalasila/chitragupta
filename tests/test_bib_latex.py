import json

import pytest

from chitragupta import bib_latex

V1_DECODINGS = [
    ('M{\\"u}ller', "Müller"),
    ("Jos\\'{e}", "José"),
    ("Fran\\c{c}ois", "François"),
    ('{\\AA}ngstr{\\"o}m', "Ångström"),
    ("\\'e", "é"),
    ("e\\'", "e"),
    ("105--107", "105--107"),
    ("Getting {Started} {\\textbar} {ADOxx}.org", "Getting Started \\textbar ADOxx.org"),
    ("C:\\\\Users{\\_}x", "C:\\\\Users_x"),
    ("A \\& B", "A & B"),
    ("{Digital} {Twins}", "Digital Twins"),
    ("Cafe\u0301", "Café"),
    ('Na\\"{\\i}ve', "Naïve"),
    ("\\ss{}", "ß"),
    ("$\\alpha$-test", "$α$-test"),
    ("plain text", "plain text"),
    ("\\o{}ster", "øster"),
    ("{\\'E}cole", "École"),
    ("\\v{S}koda", "Škoda"),
]


@pytest.mark.parametrize(("latex", "expected"), V1_DECODINGS)
def test_decodes_exactly_as_bibtexparser_1_did(latex, expected):
    assert bib_latex.latex_to_unicode(latex) == expected


def test_a_page_range_keeps_its_double_hyphen():
    assert bib_latex.latex_to_unicode("1--8") == "1--8"


def test_an_unknown_macro_survives_rather_than_vanishing():
    assert "\\textbar" in bib_latex.latex_to_unicode("A {\\textbar} B")


def test_the_result_is_nfc_normalised():
    decoded = bib_latex.latex_to_unicode("Cafe\u0301")
    assert decoded == "Caf\u00e9"
    assert len(decoded) == 4


def test_a_combining_accent_at_the_very_end_is_dropped():
    assert bib_latex.latex_to_unicode("abc\\'") == "abc"


def test_the_table_ships_with_its_licence_note_and_all_three_tables(tmp_path):
    table = json.loads(bib_latex.TABLE_PATH.read_text(encoding="utf-8"))
    assert "Francois Boulogne" in table["_source"]
    assert "BSD" in table["_source"]
    assert len(table["unicode_to_latex"]) == 2344
    assert len(table["unicode_to_crappy_latex1"]) == 199
    assert len(table["unicode_to_crappy_latex2"]) == 4
