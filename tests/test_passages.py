import json
import subprocess
import sys
import types

import pytest

from chitragupta import _atomic_write, config, ledger, passages
from tests.conftest import add_item, plant_sidecar


class TestDistinctive:
    def test_drops_stopwords_and_short_words(self, isolated_config):
        assert passages.distinctive("The cat is on a mat") == {"cat", "mat"}

    def test_is_case_insensitive(self, isolated_config):
        assert passages.distinctive("Digital TWIN") == passages.distinctive("digital twin")


class TestQuotable:
    def test_a_passage_with_text_is_quotable(self, isolated_config):
        assert passages.Passage(page=1, words={"a"}, text="Real paragraph.").quotable

    def test_a_passage_without_text_is_not(self, isolated_config):
        assert not passages.Passage(page=1, words={"a"}).quotable


class TestSourcePassages:
    def test_prefers_the_docling_sidecar(self, isolated_config):
        add_item("a_2024", parsed_text="page one\fpage two")
        plant_sidecar(
            "a_2024", [{"text": "A real reading-ordered paragraph.", "label": "text", "page": 4}]
        )
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()

        assert reason is None
        assert len(found) == 1
        assert found[0].quotable
        assert found[0].page == 4
        assert found[0].label == "text"

    def test_falls_back_to_form_feed_pages_and_refuses_to_quote(self, isolated_config):
        add_item("a_2024", parsed_text="first page text\fsecond page text")
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()

        assert reason is None
        assert len(found) == 2
        assert [p.page for p in found] == [1, 2]
        assert not any(p.quotable for p in found), (
            "page-level passages must never be quoted -- column splicing "
            "makes any excerpt a two-argument collage"
        )

    def test_a_traversal_citekey_never_reaches_the_filesystem(self, isolated_config):
        outside = (config.DOCLING_DIR / ".." / ".." / "private.passages.json").resolve()
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text(
            json.dumps([{"text": "Contents that must stay unread.", "label": "text", "page": 1}]),
            encoding="utf-8",
        )
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "../../private")
        finally:
            con.close()
        assert found == []
        assert "unsafe" in reason

    def test_unknown_citekey_reports_why(self, isolated_config):
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "ghost_2024")
        finally:
            con.close()
        assert found == []
        assert reason == "not found in the corpus"

    def test_a_key_that_left_the_corpus_is_not_read_from_its_sidecar(self, isolated_config):
        plant_sidecar("gone_2024", [{"text": "Left behind.", "label": "text", "page": 1}])
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "gone_2024")
        finally:
            con.close()
        assert found == []
        assert reason == "not found in the corpus"

    @pytest.mark.parametrize("docling", [True, False])
    def test_a_row_that_stopped_being_parsed_yields_no_passages(self, isolated_config, docling):
        add_item("a_2024", parsed_text="old page one\fold page two")
        plant_sidecar(
            "a_2024", [{"text": "Old wording.", "label": "text", "page": 1}], docling=docling
        )
        con = ledger.connect()
        try:
            ledger.mark_parse_failed(con, "a_2024", "boom")
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert found == []
        assert reason == "status is parse_failed -- no current parsed text"

    def test_no_parsed_text_and_no_pdf_reports_why(self, isolated_config):
        add_item("a_2024")
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert found == []
        assert "no readable PDF" in reason

    def test_corrupt_sidecar_falls_through_instead_of_raising(self, isolated_config):
        add_item("a_2024", parsed_text="page one\fpage two")
        config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
        (config.DOCLING_DIR / "a_2024.passages.json").write_text("{not json")
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert reason is None
        assert len(found) == 2  # fell back to pages

    def test_blank_pages_are_dropped(self, isolated_config):
        add_item("a_2024", parsed_text="first page\f   \fthird page")
        con = ledger.connect()
        try:
            found, _ = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert [p.page for p in found] == [1, 3], (
            "page numbers stay tied to the source's own pagination"
        )


class TestPassageRecords:
    @staticmethod
    def _item(text, label="text", page=1, bbox=None):
        prov = types.SimpleNamespace(page_no=page, bbox=bbox)
        return types.SimpleNamespace(text=text, label=label, prov=[prov])

    def test_keeps_prose_with_its_page(self, isolated_config):
        doc = types.SimpleNamespace(texts=[self._item("A real paragraph.", page=4)])
        assert passages.passage_records(doc) == [
            {"text": "A real paragraph.", "label": "text", "page": 4}
        ]

    def test_drops_labels_that_are_not_prose(self, isolated_config):
        doc = types.SimpleNamespace(
            texts=[
                self._item("Journal of Things, Vol 3", label="page_header"),
                self._item("Real prose.", label="text"),
                self._item("Figure 1. A diagram.", label="caption"),
            ]
        )
        assert [r["text"] for r in passages.passage_records(doc)] == ["Real prose."]

    def test_accepts_a_dotted_enum_label(self, isolated_config):
        doc = types.SimpleNamespace(texts=[self._item("Prose.", label="DocItemLabel.TEXT")])
        assert [r["label"] for r in passages.passage_records(doc)] == ["text"]

    def test_drops_empty_text(self, isolated_config):
        doc = types.SimpleNamespace(texts=[self._item("   "), self._item("Kept.")])
        assert [r["text"] for r in passages.passage_records(doc)] == ["Kept."]

    def test_carries_the_bounding_box_when_there_is_one(self, isolated_config):
        bbox = types.SimpleNamespace(l=1.0, t=2.0, r=3.0, b=4.0)
        doc = types.SimpleNamespace(texts=[self._item("Prose.", bbox=bbox)])
        assert passages.passage_records(doc)[0]["bbox"] == [1.0, 2.0, 3.0, 4.0]

    def test_a_document_with_no_texts_yields_nothing(self, isolated_config):
        assert passages.passage_records(types.SimpleNamespace()) == []


class TestTableAndFormulaRecords:
    @staticmethod
    def _table(markdown, caption="", page=2, bbox=None):
        prov = types.SimpleNamespace(page_no=page, bbox=bbox)
        return types.SimpleNamespace(
            export_to_markdown=lambda doc: markdown,
            caption_text=lambda doc: caption,
            prov=[prov],
        )

    def test_a_table_becomes_a_record_with_its_page(self, isolated_config):
        doc = types.SimpleNamespace(
            texts=[],
            tables=[self._table("| a | b |\n| 1 | 2 |", caption="Table 1. Results.", page=5)],
        )
        assert passages.passage_records(doc) == [
            {"text": "Table 1. Results.\n| a | b |\n| 1 | 2 |", "label": "table", "page": 5}
        ]

    def test_a_caption_already_in_the_export_is_not_repeated(self, isolated_config):
        doc = types.SimpleNamespace(
            texts=[],
            tables=[self._table("Table 1. Results.\n| a | b |", caption="Table 1. Results.")],
        )
        assert [r["text"] for r in passages.passage_records(doc)] == [
            "Table 1. Results.\n| a | b |"
        ]

    def test_a_captionless_table_is_just_its_cells(self, isolated_config):
        doc = types.SimpleNamespace(texts=[], tables=[self._table("| a |", caption="")])
        assert [r["text"] for r in passages.passage_records(doc)] == ["| a |"]

    def test_an_empty_table_export_contributes_nothing(self, isolated_config):
        doc = types.SimpleNamespace(texts=[], tables=[self._table("   ")])
        assert passages.passage_records(doc) == []

    def test_a_table_carries_its_bounding_box(self, isolated_config):
        bbox = types.SimpleNamespace(l=1.0, t=2.0, r=3.0, b=4.0)
        doc = types.SimpleNamespace(texts=[], tables=[self._table("| a |", bbox=bbox)])
        assert passages.passage_records(doc)[0]["bbox"] == [1.0, 2.0, 3.0, 4.0]

    def test_a_document_without_tables_attr_is_fine(self, isolated_config):
        doc = types.SimpleNamespace(texts=[TestPassageRecords._item("Prose.")])
        assert [r["label"] for r in passages.passage_records(doc)] == ["text"]

    def test_a_decoded_formula_is_kept(self, isolated_config):
        doc = types.SimpleNamespace(
            texts=[TestPassageRecords._item("T(t) = T_0 e^{-kt}", label="formula", page=3)]
        )
        assert passages.passage_records(doc) == [
            {"text": "T(t) = T_0 e^{-kt}", "label": "formula", "page": 3}
        ]

    def test_an_undecoded_formula_contributes_nothing(self, isolated_config):
        doc = types.SimpleNamespace(texts=[TestPassageRecords._item("", label="formula")])
        assert passages.passage_records(doc) == []

    def test_a_table_record_reads_back_as_a_quotable_passage(self, isolated_config):
        plant_sidecar("smith_2024", [{"text": "| a | b |", "label": "table", "page": 9}])
        add_item("smith_2024", parsed_text="page one\fpage two")
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "smith_2024")
        finally:
            con.close()
        assert reason is None
        assert [(p.page, p.label, p.quotable) for p in found] == [(9, "table", True)]


class TestCorpusLayerSidecar:
    def test_is_used_when_the_enrichment_layer_has_not_run(self, isolated_config):
        add_item("smith_2024", parsed_text="page one\fpage two")
        passages.write_sidecar(
            "smith_2024",
            [
                {"text": "A reading-ordered paragraph.", "label": "text", "page": 7},
            ],
        )
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "smith_2024")
        finally:
            con.close()
        assert reason is None
        assert [(p.page, p.text, p.quotable) for p in found] == [
            (7, "A reading-ordered paragraph.", True)
        ]

    def test_the_enrichment_sidecar_still_wins_when_both_exist(self, isolated_config):
        add_item("smith_2024", parsed_text="page one\fpage two")
        plant_sidecar("smith_2024", [{"text": "From the enrichment layer.", "page": 1}])
        passages.write_sidecar("smith_2024", [{"text": "From the corpus layer.", "page": 1}])
        con = ledger.connect()
        try:
            found, _ = passages.source_passages(con, "smith_2024")
        finally:
            con.close()
        assert [p.text for p in found] == ["From the enrichment layer."]

    def test_a_corrupt_one_falls_through_to_the_page_rung(self, isolated_config):
        add_item("smith_2024", parsed_text="page one\fpage two")
        passages.sidecar_path("smith_2024").write_text("{ not json")
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "smith_2024")
        finally:
            con.close()
        assert reason is None
        assert [p.page for p in found] == [1, 2]
        assert not any(p.quotable for p in found)

    def test_clear_removes_it_and_tolerates_its_absence(self, isolated_config):
        passages.write_sidecar("smith_2024", [{"text": "Gone soon.", "page": 1}])
        assert passages.sidecar_path("smith_2024").exists()
        passages.clear_sidecar("smith_2024")
        assert not passages.sidecar_path("smith_2024").exists()
        passages.clear_sidecar("smith_2024")  # second call must not raise

    def test_lives_beside_the_parsed_text_not_in_the_enrichment_directory(self, isolated_config):
        assert passages.sidecar_path("k").parent == config.PARSED_DIR
        assert passages.sidecar_path("k") != config.DOCLING_DIR / "k.passages.json"

    def test_a_write_replaces_the_old_file_whole_and_leaves_no_temp(self, isolated_config):
        passages.write_sidecar("smith_2024", [{"text": "Old.", "page": 1}])
        passages.write_sidecar("smith_2024", [{"text": "New.", "page": 2}])
        assert json.loads(passages.sidecar_path("smith_2024").read_text()) == [
            {"text": "New.", "page": 2}
        ]
        assert [p.name for p in config.PARSED_DIR.iterdir()] == ["smith_2024.passages.json"]

    def test_a_failed_write_keeps_the_old_file_and_removes_its_temp(
        self, isolated_config, monkeypatch
    ):
        passages.write_sidecar("smith_2024", [{"text": "Old.", "page": 1}])

        def full_disk(src, dst):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(_atomic_write.os, "replace", full_disk)
        with pytest.raises(OSError, match="No space left"):
            passages.write_sidecar("smith_2024", [{"text": "New.", "page": 2}])
        assert json.loads(passages.sidecar_path("smith_2024").read_text())[0]["text"] == "Old."
        assert [p.name for p in config.PARSED_DIR.iterdir()] == ["smith_2024.passages.json"]

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            (None, "absent"),
            (b"[]", "ok"),  # a prose-less parse: present and settled
            (b'[{"text": "A paragraph."}]', "ok"),
            (b'[{"text": "A para', "unreadable"),
            (b'[{"text": "caf\xc3', "unreadable"),
            (b'{"text": "not a list"}', "unreadable"),
        ],
    )
    def test_state_tells_absent_from_unreadable(self, isolated_config, content, expected):
        path = passages.sidecar_path("smith_2024")
        if content is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        assert passages.sidecar_state(path) == expected

    def test_state_reports_an_unreadable_directory_entry(self, isolated_config):
        path = passages.sidecar_path("smith_2024")
        path.mkdir(parents=True)
        assert passages.sidecar_state(path) == "unreadable"


class TestSidecarRobustness:
    @pytest.mark.parametrize(
        "payload",
        [
            '{"not": "a list"}',
            "[]",
            '["not a dict"]',
            '[{"text": "   "}]',
            '[{"no_text_key": 1}]',
            '[{"text": 7}]',
        ],
    )
    def test_unusable_sidecar_shapes_fall_through_to_pages(self, isolated_config, payload):
        add_item("a_2024", parsed_text="page one\fpage two")
        config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
        (config.DOCLING_DIR / "a_2024.passages.json").write_text(payload)
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert reason is None
        assert [p.page for p in found] == [1, 2]

    def test_truncated_utf8_sidecar_falls_through_instead_of_raising(self, isolated_config):
        add_item("a_2024", parsed_text="page one\fpage two")
        config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
        (config.DOCLING_DIR / "a_2024.passages.json").write_bytes(
            b'[{"text": "Real paragraph ' + b"\xe2\x82"
        )
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert reason is None
        assert [p.page for p in found] == [1, 2]

    def test_mixed_sidecar_keeps_the_usable_records(self, isolated_config):
        add_item("a_2024", parsed_text="ignored\fignored")
        plant_sidecar("a_2024", ["junk", {"text": ""}, {"text": "Real paragraph here.", "page": 3}])
        con = ledger.connect()
        try:
            found, _ = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert len(found) == 1
        assert found[0].text == "Real paragraph here."

    @pytest.mark.parametrize("bad_page", ["seven", 3.5, 0, -2, True, None, [1]])
    def test_a_page_that_is_not_a_page_number_is_dropped(self, isolated_config, bad_page):
        add_item("a_2024", parsed_text="ignored\fignored")
        plant_sidecar("a_2024", [{"text": "Real paragraph.", "page": bad_page}])
        con = ledger.connect()
        try:
            found, _ = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert found[0].page is None
        assert found[0].quotable, "the text is still fine -- only the locator was junk"

    def test_a_real_page_number_survives(self, isolated_config):
        add_item("a_2024", parsed_text="ignored\fignored")
        plant_sidecar("a_2024", [{"text": "Real paragraph.", "page": 4}])
        con = ledger.connect()
        try:
            found, _ = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert found[0].page == 4

    def test_a_label_that_is_not_a_string_is_dropped(self, isolated_config):
        add_item("a_2024", parsed_text="ignored\fignored")
        plant_sidecar("a_2024", [{"text": "Real paragraph.", "label": 7}])
        con = ledger.connect()
        try:
            found, _ = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert found[0].label is None


@pytest.mark.usefixtures("programs_on_path")
class TestPdfFallback:
    def test_parsed_text_without_page_breaks_falls_through_to_the_pdf(
        self, isolated_config, monkeypatch, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        add_item("a_2024", parsed_text="one continuous document, no form feeds", pdf_path=str(pdf))

        class FakeRun:
            stdout = "page one hysteresis\fpage two relay"

        monkeypatch.setattr(passages.subprocess, "run", lambda *a, **k: FakeRun())
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()

        assert reason is None
        assert [p.page for p in found] == [1, 2]

    def test_pdftotext_failure_is_reported_not_raised(self, isolated_config, monkeypatch, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        add_item("a_2024", parsed_text="no form feeds here", pdf_path=str(pdf))

        def boom(*a, **k):
            raise OSError("pdftotext not on PATH")

        monkeypatch.setattr(passages.subprocess, "run", boom)
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()

        assert [p.page for p in found] == [1]
        assert "feeds" in {word for p in found for word in p.words}
        assert reason is None

    def test_a_pdftotext_timeout_falls_back_like_any_other_failure(
        self, isolated_config, monkeypatch, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        add_item("a_2024", parsed_text="no form feeds here", pdf_path=str(pdf))
        monkeypatch.setattr(passages.config, "PARSER_DOCUMENT_TIMEOUT", 7.0)
        seen = {}

        def hang(*a, **k):
            seen.update(k)
            raise subprocess.TimeoutExpired(a[0], k["timeout"])

        monkeypatch.setattr(passages.subprocess, "run", hang)
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()

        assert seen["timeout"] == 7.0
        assert [p.page for p in found] == [1]
        assert reason is None

    def test_pdftotext_failure_with_nothing_held_is_reported(
        self, isolated_config, monkeypatch, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        add_item("a_2024", parsed_text=None, pdf_path=str(pdf))

        def boom(*a, **k):
            raise OSError("pdftotext not on PATH")

        monkeypatch.setattr(passages.subprocess, "run", boom)
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()

        assert found == []
        assert "pdftotext" in reason

    def test_an_empty_pdftotext_result_gets_a_reason(self, isolated_config, monkeypatch, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        add_item("a_2024", parsed_text=None, pdf_path=str(pdf))
        monkeypatch.setattr(
            passages.subprocess,
            "run",
            lambda *a, **k: types.SimpleNamespace(stdout="", returncode=0),
        )
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert found == []
        assert "no extractable text layer" in reason

    def test_an_empty_pdftotext_result_falls_back_to_the_held_page(
        self, isolated_config, monkeypatch, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        add_item("a_2024", parsed_text="no form feeds here", pdf_path=str(pdf))
        monkeypatch.setattr(
            passages.subprocess,
            "run",
            lambda *a, **k: types.SimpleNamespace(stdout="", returncode=0),
        )
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert [p.page for p in found] == [1]
        assert reason is None

    def test_no_pdf_at_all_still_returns_the_held_page(self, isolated_config):
        add_item("a_2024", parsed_text="no form feeds here", pdf_path=None)
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()
        assert [p.page for p in found] == [1]
        assert reason is None

    def test_undecodable_pdftotext_output_does_not_take_down_the_report(
        self, isolated_config, monkeypatch, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        add_item("a_2024", parsed_text="no form feeds here", pdf_path=str(pdf))

        real_run = subprocess.run
        emit = r"import sys; sys.stdout.buffer.write(b'first \xff\xfe page\fsecond page')"

        def fake_run(cmd, **kwargs):
            return real_run([sys.executable, "-c", emit], **kwargs)

        monkeypatch.setattr(passages.subprocess, "run", fake_run)
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()

        assert reason is None
        assert [p.page for p in found] == [1, 2]
        assert "first" in " ".join(found[0].words), (
            "the decodable text either side of the bad bytes is still there"
        )

    def test_missing_parsed_file_falls_through_to_the_pdf(
        self, isolated_config, monkeypatch, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        add_item("a_2024", parsed_text="page one\fpage two", pdf_path=str(pdf))
        config.PARSED_DIR.joinpath("a_2024.txt").unlink()

        class FakeRun:
            stdout = "from the pdf\fsecond page"

        monkeypatch.setattr(passages.subprocess, "run", lambda *a, **k: FakeRun())
        con = ledger.connect()
        try:
            found, reason = passages.source_passages(con, "a_2024")
        finally:
            con.close()

        assert reason is None
        assert [p.page for p in found] == [1, 2]


class TestSeamWithCitationProvenance:
    def test_citation_provenance_re_exports_the_ladder(self, isolated_config):
        from chitragupta.review import citation_provenance as cp

        assert cp.source_passages is passages.source_passages
        assert cp.Passage is passages.Passage
        assert cp.distinctive is passages.distinctive
