from chitragupta import _abstract, config, passages
from tests.conftest import plant_sidecar

ABSTRACT_WORDS = " ".join(f"word{i}" for i in range(60))


def _sidecar(citekey, records, docling=False):
    rows = [{"text": t, "label": lbl, "page": 1} for t, lbl in records]
    return plant_sidecar(citekey, rows, docling=docling)


class TestTheTwoWaysAnAbstractIsMarked:
    def test_a_section_header_named_abstract(self, isolated_config):
        _sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_WORDS, "text")])
        assert _abstract.extract("smith2024") == ABSTRACT_WORDS

    def test_an_inline_opener_docling_emits_as_running_text(self, isolated_config):
        _sidecar("smith2024", [(f"Abstract {ABSTRACT_WORDS}", "text")])
        assert _abstract.extract("smith2024") == ABSTRACT_WORDS

    def test_a_numbered_heading(self, isolated_config):
        _sidecar("smith2024", [("1. Abstract", "section_header"), (ABSTRACT_WORDS, "text")])
        assert _abstract.extract("smith2024") == ABSTRACT_WORDS

    def test_several_paragraphs_are_joined_in_reading_order(self, isolated_config):
        _sidecar(
            "smith2024",
            [
                ("Abstract", "section_header"),
                (ABSTRACT_WORDS, "text"),
                ("A second paragraph of the same abstract.", "text"),
            ],
        )
        assert _abstract.extract("smith2024").endswith("A second paragraph of the same abstract.")

    def test_a_document_with_no_abstract_at_all(self, isolated_config):
        _sidecar("smith2024", [("1 Introduction", "section_header"), (ABSTRACT_WORDS, "text")])
        assert _abstract.extract("smith2024") is None


class TestWhereTheBodyStops:
    def test_the_next_section_header_ends_it(self, isolated_config):
        _sidecar(
            "smith2024",
            [
                ("Abstract", "section_header"),
                (ABSTRACT_WORDS, "text"),
                ("1 Introduction", "section_header"),
                ("Body text that is not part of the abstract.", "text"),
            ],
        )
        assert "not part of the abstract" not in _abstract.extract("smith2024")

    def test_a_keywords_line_ends_it_even_unlabelled(self, isolated_config):
        _sidecar(
            "smith2024",
            [
                ("Abstract", "section_header"),
                (ABSTRACT_WORDS, "text"),
                ("Keywords: digital twin, simulation", "text"),
                ("More body text.", "text"),
            ],
        )
        result = _abstract.extract("smith2024")
        assert "Keywords" not in result and "More body text" not in result

    def test_an_unlabelled_introduction_ends_it(self, isolated_config):
        _sidecar(
            "smith2024",
            [
                ("Abstract", "section_header"),
                (ABSTRACT_WORDS, "text"),
                ("1. Introduction", "text"),
                ("More body text.", "text"),
            ],
        )
        assert "More body text" not in _abstract.extract("smith2024")

    def test_a_runaway_is_capped_by_item_count(self, isolated_config):
        paragraphs = [(f"Paragraph {i} " + ABSTRACT_WORDS, "text") for i in range(9)]
        _sidecar("humlum_large_2025", [("Abstract", "section_header"), *paragraphs])
        result = _abstract.extract("humlum_large_2025")
        assert result is not None
        assert "Paragraph 0" in result and "Paragraph 3" not in result

    def test_a_figure_caption_inside_the_abstract_is_skipped_not_terminal(self, isolated_config):
        _sidecar(
            "smith2024",
            [
                ("Abstract", "section_header"),
                ("Figure 1: a caption.", "caption"),
                (ABSTRACT_WORDS, "text"),
            ],
        )
        assert _abstract.extract("smith2024") == ABSTRACT_WORDS


class TestTheGuardsWithholdRatherThanTrim:
    def test_a_match_deep_in_reading_order_is_withheld(self, isolated_config):
        filler = [("Body paragraph.", "text")] * 45
        _sidecar("slavic_python_2025", [*filler, (f"Abstract {ABSTRACT_WORDS}", "text")])
        assert _abstract.extract("slavic_python_2025") is None

    def test_a_body_shorter_than_the_floor_is_withheld(self, isolated_config):
        _sidecar("smith2024", [("Abstract", "section_header"), ("Only a few words here.", "text")])
        assert _abstract.extract("smith2024") is None

    def test_a_body_longer_than_the_ceiling_is_withheld(self, isolated_config):
        _sidecar(
            "smith2024",
            [("Abstract", "section_header"), (" ".join(f"w{i}" for i in range(500)), "text")],
        )
        assert _abstract.extract("smith2024") is None

    def test_a_genuine_short_abstract_is_still_kept(self, isolated_config):
        _sidecar(
            "lin_utwin_2023",
            [("Abstract", "section_header"), (" ".join(f"w{i}" for i in range(58)), "text")],
        )
        assert _abstract.extract("lin_utwin_2023") is not None


class TestNoStructuralSidecar:
    def test_no_sidecar_is_a_different_answer_from_no_abstract(self, isolated_config):
        assert _abstract.extract("smith2024") is _abstract.UNKNOWN

    def test_a_corrupted_sidecar_reads_as_unknown(self, isolated_config):
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        config.PARSED_DIR.joinpath("smith2024.passages.json").write_text("{", encoding="utf-8")
        assert _abstract.extract("smith2024") is _abstract.UNKNOWN

    def test_an_unsafe_citekey_never_becomes_a_path(self, isolated_config):
        assert _abstract.extract("../../etc/passwd") is _abstract.UNKNOWN


class TestTheEnrichmentSidecarWinsWhenBothExist:
    def test_rung_one_is_preferred(self, isolated_config):
        _sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_WORDS, "text")])
        _sidecar(
            "smith2024",
            [("Abstract", "section_header"), ("Docling " + ABSTRACT_WORDS, "text")],
            docling=True,
        )
        assert _abstract.extract("smith2024").startswith("Docling")


class TestStructuralPassagesIsTheOneResolver:
    def test_it_reads_rung_two(self, isolated_config):
        _sidecar("smith2024", [("A paragraph.", "text")])
        found = passages.structural_passages("smith2024")
        assert [p.text for p in found] == ["A paragraph."]

    def test_it_does_not_fall_through_to_page_level(self, isolated_config, ledger_con):
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        config.PARSED_DIR.joinpath("smith2024.txt").write_text(
            "page one\fpage two", encoding="utf-8"
        )
        ledger_con.execute(
            "INSERT INTO items (citekey, title, status, parsed_path, last_synced)"
            " VALUES (?, 'T', 'parsed', ?, '2026-01-01')",
            ("smith2024", str(config.PARSED_DIR / "smith2024.txt")),
        )
        ledger_con.commit()

        found, reason = passages.source_passages(ledger_con, "smith2024")
        assert len(found) == 2 and reason is None
        assert passages.structural_passages("smith2024") is None

    def test_an_unsafe_citekey_is_refused(self, isolated_config):
        assert passages.structural_passages("../../etc/passwd") is None
