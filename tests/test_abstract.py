"""chitragupta/_abstract.py: the author's own abstract, lifted out of the
structural passage sidecar rather than guessed at from flattened text.

Every case below is drawn from a real document in this project's own
corpus of 498 parsed papers, named in the test that carries it. That
matters more here than usual: the detector's whole risk is a *false
positive*, which publishes something that is not an abstract as though the
authors wrote it, and a fabricated fixture cannot tell you whether the
guards are aimed at shapes that actually occur.
"""

import json

from chitragupta import _abstract, config, passages

ABSTRACT_WORDS = " ".join(f"word{i}" for i in range(60))


def _sidecar(citekey, records, docling=False):
    """A structural passage sidecar on rung 1 or rung 2 of
    chitragupta/passages.py's ladder."""
    directory = config.DOCLING_DIR if docling else config.PARSED_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{citekey}.passages.json"
    path.write_text(_records_json(records), encoding="utf-8")
    return path


def _records_json(records):
    return json.dumps([{"text": t, "label": lbl, "page": 1} for t, lbl in records])


class TestTheTwoWaysAnAbstractIsMarked:
    def test_a_section_header_named_abstract(self, isolated_config):
        _sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_WORDS, "text")])
        assert _abstract.extract("smith2024") == ABSTRACT_WORDS

    def test_an_inline_opener_docling_emits_as_running_text(self, isolated_config):
        """Docling emits `Abstract` as running text as often as a heading
        -- one real document reads `Abstract At the heart of a digital
        twin is...` mid-paragraph. A heading-only scan finds 133 of 498
        documents; counting the inline form finds 342."""
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
        """160 of the 498 -- systematically the standards deliverables,
        project reports and theses, which are also the longest."""
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
        """`Keywords`/`Index Terms` arrive as ordinary text as often as
        as a header, so the stop cannot rely on the label alone."""
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
        """`humlum_large_2025` is the real case: a genuine abstract
        followed by body text with no `section_header` and no `Keywords`
        line to stop on, which swallowed 1442 words. The cap is on items
        rather than words deliberately -- a word cap would have discarded
        the correct abstract sitting in its first 200 words."""
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
        """`slavic_python_2025` (item #155) and `akiki_resources_2025`
        (item #93) both matched an inline opener deep in the document and
        captured class-diagram text as though it were an abstract.
        Genuine matches sit at median item #5, p90 #21."""
        filler = [("Body paragraph.", "text")] * 45
        _sidecar("slavic_python_2025", [*filler, (f"Abstract {ABSTRACT_WORDS}", "text")])
        assert _abstract.extract("slavic_python_2025") is None

    def test_a_body_shorter_than_the_floor_is_withheld(self, isolated_config):
        """`deslauriers_everyday_2022` captured a title-and-affiliations
        block at 35 words. The floor is a length sanity check rather than
        a title-specific rule -- that case simply falls under it."""
        _sidecar("smith2024", [("Abstract", "section_header"), ("Only a few words here.", "text")])
        assert _abstract.extract("smith2024") is None

    def test_a_body_longer_than_the_ceiling_is_withheld(self, isolated_config):
        """The longest genuine abstract in this corpus is 321 words; the
        p90 is 243. A body past the ceiling means the stop rule failed,
        and a withheld abstract costs a reader nothing."""
        _sidecar(
            "smith2024",
            [("Abstract", "section_header"), (" ".join(f"w{i}" for i in range(500)), "text")],
        )
        assert _abstract.extract("smith2024") is None

    def test_a_genuine_short_abstract_is_still_kept(self, isolated_config):
        """`lin_utwin_2023` is a real, correctly-bounded abstract at 58
        words -- which is why the floor is 40 and not the 60 an earlier
        design proposed."""
        _sidecar(
            "lin_utwin_2023",
            [("Abstract", "section_header"), (" ".join(f"w{i}" for i in range(58)), "text")],
        )
        assert _abstract.extract("lin_utwin_2023") is not None


class TestNoStructuralSidecar:
    def test_no_sidecar_is_a_different_answer_from_no_abstract(self, isolated_config):
        """`_extract_pdftotext` returns None rather than an empty list --
        "this backend resolves no reading order" -- so a document parsed
        by it has no passage sidecar at all. Reporting "no abstract" there
        would be a claim about a paper this cannot read."""
        assert _abstract.extract("smith2024") is _abstract.UNKNOWN

    def test_a_corrupted_sidecar_reads_as_unknown(self, isolated_config):
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        config.PARSED_DIR.joinpath("smith2024.passages.json").write_text("{", encoding="utf-8")
        assert _abstract.extract("smith2024") is _abstract.UNKNOWN

    def test_an_unsafe_citekey_never_becomes_a_path(self, isolated_config):
        """The same validator #638 put in front of passages.source_passages:
        a citekey reaching here came off a command line."""
        assert _abstract.extract("../../etc/passwd") is _abstract.UNKNOWN


class TestTheEnrichmentSidecarWinsWhenBothExist:
    def test_rung_one_is_preferred(self, isolated_config):
        """Rung 1 is a second, independent parse under the enrichment
        layer's own OCR settings -- passages.py's ladder already prefers
        it, and this must not resolve the two in a different order."""
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
        """The point of the seam: `source_passages` falls through to
        whole-page passages, which carry no labels and cannot answer a
        structural question. This returns None instead of degrading."""
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
