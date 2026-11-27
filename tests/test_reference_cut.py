import json

import pytest

from chitragupta import (
    _reference_cut,
    config,
    ledger,
    passages,
    retrieval,
    retrieval_cache,
    retrieval_cli,
)

from tests.conftest import make_reference, parsed_text, plant_sidecar

BODY = "this chapter measures greenhouse humidity with an incubator\n\n"
REFS = "References\n\nSmith 2020. Blockchain consensus for supply chains.\n"


def refs_sidecar(header: str = "References", citekey: str = "a2024"):
    return plant_sidecar(
        citekey,
        [
            {"text": BODY.strip(), "label": "text", "page": 1},
            {"text": header, "label": "section_header", "page": 2},
        ],
        docling=False,
    )


def seeded(con, text: str, citekey: str = "a2024", title: str = "An Incubator Study"):
    path = parsed_text(citekey, text)
    ledger.upsert_reference(con, make_reference(citekey=citekey, title=title))
    ledger.mark_parsed(con, citekey, path)
    return path


class TestStripReferences:
    def test_text_from_the_header_onward_is_dropped(self, isolated_config):
        path = parsed_text("a2024", BODY + REFS)
        refs_sidecar()

        assert _reference_cut.strip_references(BODY + REFS, str(path)) == BODY

    def test_a_document_with_no_reference_header_is_unchanged(self, isolated_config):
        path = parsed_text("a2024", BODY)
        plant_sidecar("a2024", [{"text": BODY.strip(), "label": "text", "page": 1}], docling=False)

        assert _reference_cut.strip_references(BODY, str(path)) == BODY

    def test_no_sidecar_leaves_the_text_unchanged(self, isolated_config):
        path = parsed_text("a2024", BODY + REFS)

        assert _reference_cut.strip_references(BODY + REFS, str(path)) == BODY + REFS

    def test_a_corrupt_sidecar_leaves_the_text_unchanged(self, isolated_config):
        path = parsed_text("a2024", BODY + REFS)
        (config.PARSED_DIR / "a2024.passages.json").write_text("{not valid json", encoding="utf-8")

        assert _reference_cut.strip_references(BODY + REFS, str(path)) == BODY + REFS

    def test_the_last_matching_header_is_the_cut_point(self, isolated_config):
        text = BODY + REFS + "chapter two on calibration\n\n" + REFS
        path = parsed_text("a2024", text)
        plant_sidecar(
            "a2024",
            [
                {"text": BODY.strip(), "label": "text", "page": 1},
                {"text": "References", "label": "section_header", "page": 2},
                {"text": "chapter two on calibration", "label": "text", "page": 3},
                {"text": "References", "label": "section_header", "page": 4},
            ],
            docling=False,
        )

        assert _reference_cut.strip_references(text, str(path)) == (
            BODY + REFS + "chapter two on calibration\n\n"
        )

    @pytest.mark.parametrize(
        "header", ["REFERENCES", "Bibliography", "7 REFERENCES", "References:"]
    )
    def test_the_header_spellings_this_corpus_actually_uses(self, isolated_config, header):
        text = BODY + header + "\n\nSmith 2020.\n"
        path = parsed_text("a2024", text)
        refs_sidecar(header)

        assert _reference_cut.strip_references(text, str(path)) == BODY

    def test_a_heading_that_merely_starts_with_the_word_is_not_a_cut_point(self, isolated_config):
        text = BODY + "Reference architecture\n\nthe layered view of an incubator\n"
        path = parsed_text("a2024", text)
        refs_sidecar("Reference architecture")

        assert _reference_cut.strip_references(text, str(path)) == text

    def test_a_reference_marker_that_is_not_a_section_header_is_not_a_cut_point(
        self, isolated_config
    ):
        text = BODY + "References\n\nsee the incubator's own manual\n"
        path = parsed_text("a2024", text)
        plant_sidecar(
            "a2024",
            [
                {"text": BODY.strip(), "label": "text", "page": 1},
                {"text": "References", "label": "caption", "page": 2},
            ],
            docling=False,
        )

        assert _reference_cut.strip_references(text, str(path)) == text

    def test_a_header_the_flattened_text_does_not_contain_leaves_it_unchanged(
        self, isolated_config
    ):
        path = parsed_text("a2024", BODY)
        refs_sidecar()

        assert _reference_cut.strip_references(BODY, str(path)) == BODY

    def test_an_item_with_no_parsed_path_is_unchanged(self, isolated_config):
        assert _reference_cut.strip_references(BODY + REFS, None) == BODY + REFS


class TestReferenceCutIndex:
    def body(self, text: str, label: str = "text"):
        return passages.Passage(page=1, words=set(), text=text, label=label)

    def test_the_index_of_the_last_reference_header_is_returned(self):
        found = [self.body("a"), self.body("References", "section_header"), self.body("Smith 2020")]

        assert _reference_cut.reference_cut_index(found) == 1

    def test_the_last_header_wins_when_a_book_has_one_per_chapter(self):
        found = [
            self.body("chapter one"),
            self.body("References", "section_header"),
            self.body("chapter two"),
            self.body("References", "section_header"),
            self.body("Smith 2020"),
        ]

        assert _reference_cut.reference_cut_index(found) == 3

    def test_a_document_with_no_reference_header_returns_none(self):
        found = [self.body("a"), self.body("Method", "section_header")]

        assert _reference_cut.reference_cut_index(found) is None

    def test_a_heading_that_merely_starts_with_the_word_is_not_a_cut_point(self):
        found = [self.body("a"), self.body("Reference architecture", "section_header")]

        assert _reference_cut.reference_cut_index(found) is None

    def test_the_same_word_under_another_label_is_not_a_cut_point(self):
        found = [self.body("a"), self.body("References", "caption")]

        assert _reference_cut.reference_cut_index(found) is None

    def test_a_numbered_header_is_a_cut_point(self):
        found = [self.body("a"), self.body("7 REFERENCES", "section_header")]

        assert _reference_cut.reference_cut_index(found) == 1


class TestReferencesAreNotIndexed:
    def test_a_query_matching_only_the_bibliography_finds_nothing(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()

        assert retrieval.search("blockchain") == []

    def test_the_same_query_still_finds_it_without_a_sidecar(self, ledger_con):
        seeded(ledger_con, BODY + REFS)

        assert [r.citekey for r in retrieval.search("blockchain")] == ["a2024"]

    def test_the_body_is_still_found(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()

        assert [r.citekey for r in retrieval.search("incubator")] == ["a2024"]

    def test_the_indexed_length_reflects_the_cut(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()
        row = ledger.all_items(ledger_con)[0]

        entry = retrieval._tokenize_item(row)
        assert "blockchain" not in entry["term_freqs"]
        assert entry["length"] == len(retrieval._tokenize(f"{row['title']}\n{BODY}"))

    def test_a_snippet_cannot_be_drawn_from_a_reference_list(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()

        results = retrieval.search("incubator")
        assert "Smith 2020" not in results[0].snippet

    def test_evidence_windows_stop_at_the_bibliography(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()

        windows = retrieval_cli.evidence("a2024", "blockchain consensus")
        assert windows == []

    def test_the_enrichment_layers_sidecar_does_not_change_what_is_indexed(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
        (config.DOCLING_DIR / "a2024.passages.json").write_text(
            json.dumps(
                [
                    {"text": BODY.strip(), "label": "text", "page": 1},
                    {"text": "References", "label": "section_header", "page": 2},
                ]
            ),
            encoding="utf-8",
        )

        assert [r.citekey for r in retrieval.search("blockchain")] == ["a2024"]


class TestCacheMigration:
    def test_an_index_cached_before_the_cut_is_not_reused(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_INDEX_PATH.write_text(
            json.dumps(
                {
                    "version": 1,
                    "items": {
                        "a2024": {
                            "fingerprint": None,
                            "length": 20,
                            "term_freqs": {"blockchain": 3},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        retrieval_cache._forget_cache()

        assert retrieval.search("blockchain") == []
