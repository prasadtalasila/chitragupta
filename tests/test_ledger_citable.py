"""chitragupta/ledger_citable.py: which ledger rows a draft may cite (#1118)."""

from chitragupta import ledger, ledger_citable

from tests.conftest import add_parsed_item, make_reference


def _seed_every_status(ledger_con, tmp_path):
    add_parsed_item(ledger_con, tmp_path, "parsed_a_2024", "some text")
    ledger.upsert_reference(ledger_con, make_reference(citekey="nopdf_b_2024"))
    add_parsed_item(ledger_con, tmp_path, "failed_c_2024", "old text")
    ledger.mark_parse_failed(ledger_con, "failed_c_2024", "corrupt pdf")
    pdf = tmp_path / "found.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    ledger.upsert_reference(ledger_con, make_reference(citekey="found_d_2024", pdf_path=str(pdf)))


class TestCitable:
    def test_only_a_parsed_row_is_citable(self, ledger_con, tmp_path):
        _seed_every_status(ledger_con, tmp_path)
        assert ledger_citable.citable_citekeys(ledger_con) == {"parsed_a_2024"}

    def test_every_other_row_maps_to_its_status(self, ledger_con, tmp_path):
        _seed_every_status(ledger_con, tmp_path)
        assert ledger_citable.unparsed_citekeys(ledger_con) == {
            "nopdf_b_2024": "no_pdf",
            "failed_c_2024": "parse_failed",
            "found_d_2024": "discovered",
        }

    def test_an_empty_ledger_has_nothing_either_way(self, ledger_con):
        assert ledger_citable.citable_citekeys(ledger_con) == set()
        assert ledger_citable.unparsed_citekeys(ledger_con) == {}
