"""chitragupta/retrieval_text.py: the text BM25 indexes for an item, and
where it stops.

The cut is structural -- a `section_header` passage in the corpus layer's
sidecar whose text reads `references`/`bibliography`/`works cited`, and
everything from the last such header onward. Docling has no `reference`
label, so the header's *position* is the whole signal, which is what most
of these cases are about: what counts as a header, which one wins when
there are several, and what happens at each of the three ways the lookup
can come up empty.
"""

import json

import pytest

from chitragupta import config, ledger, passages, retrieval, retrieval_cli, retrieval_text

from tests.conftest import make_reference


def write_sidecar(citekey, records):
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    passages.sidecar_path(citekey).write_text(json.dumps(records), encoding="utf-8")


def header(text):
    return {"label": "section_header", "text": text, "page": 1}


def prose(text):
    return {"label": "text", "text": text, "page": 1}


class TestReferenceHeading:
    """What the pattern accepts as a section calling itself a
    bibliography. Matched against a *header's own text*, never a line of
    body prose, which is what lets the leading number of a numbered
    heading through without letting a sentence through."""

    @pytest.mark.parametrize(
        "text",
        [
            "References",
            "REFERENCES",
            "references",
            "Reference",
            "Bibliography",
            "Works Cited",
            "works  cited",
            "5. References",
            "5 References",
            "References:",
        ],
    )
    def test_accepts(self, text):
        assert retrieval_text._REFERENCE_HEADING.fullmatch(text)

    @pytest.mark.parametrize(
        "text",
        [
            "References and Further Reading",
            "The references are listed below",
            "Referenced Architectures",
            "Bibliography of the author",
            "",
        ],
    )
    def test_refuses(self, text):
        assert not retrieval_text._REFERENCE_HEADING.fullmatch(text)


class TestReferenceHeader:
    def test_no_sidecar_is_no_header(self, isolated_config):
        assert retrieval_text._reference_header("a2024") is None

    def test_unreadable_sidecar_is_no_header(self, isolated_config):
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        passages.sidecar_path("a2024").write_text("{not json", encoding="utf-8")
        assert retrieval_text._reference_header("a2024") is None

    def test_a_sidecar_that_is_not_a_list_is_no_header(self, isolated_config):
        write_sidecar("a2024", {"label": "section_header", "text": "References"})
        assert retrieval_text._reference_header("a2024") is None

    def test_a_non_dict_record_is_skipped(self, isolated_config):
        write_sidecar("a2024", ["not a record", header("References")])
        assert retrieval_text._reference_header("a2024") == "References"

    def test_a_non_string_text_is_skipped(self, isolated_config):
        write_sidecar("a2024", [{"label": "section_header", "text": 7}, header("References")])
        assert retrieval_text._reference_header("a2024") == "References"

    def test_a_reference_worded_body_passage_is_not_a_header(self, isolated_config):
        """The label carries the decision, not the words: a paragraph that
        happens to read "References" is not a section header."""
        write_sidecar("a2024", [prose("References")])
        assert retrieval_text._reference_header("a2024") is None

    def test_no_reference_header_among_real_ones(self, isolated_config):
        write_sidecar("a2024", [header("Introduction"), header("Method")])
        assert retrieval_text._reference_header("a2024") is None

    def test_the_last_matching_header_wins(self, isolated_config):
        """An appendix can restate the word, and a paper with per-chapter
        bibliographies has several. The last one is the one that opens the
        span this module cuts."""
        write_sidecar("a2024", [header("References"), header("Appendix"), header("Bibliography")])
        assert retrieval_text._reference_header("a2024") == "Bibliography"

    def test_strips_surrounding_whitespace(self, isolated_config):
        write_sidecar("a2024", [header("  References  ")])
        assert retrieval_text._reference_header("a2024") == "References"


class TestCutOffset:
    def test_finds_a_bare_heading_line(self):
        body = "Intro text\nReferences\n[1] Someone.\n"
        assert retrieval_text._cut_offset(body, "references") == len("Intro text\n")

    def test_tolerates_a_markdown_heading_mark(self):
        body = "Intro text\n## References\n[1] Someone.\n"
        assert retrieval_text._cut_offset(body, "references") == len("Intro text\n")

    def test_refuses_an_occurrence_inside_a_sentence(self):
        """The reason this is line-anchored rather than an `rfind`: a
        sentence naming the word would otherwise truncate the document at
        its own prose."""
        body = "We list our References in the appendix below.\nMore body text.\n"
        assert retrieval_text._cut_offset(body, "references") is None

    def test_the_last_matching_line_wins(self):
        body = "References\nbody\nReferences\n[1] Someone.\n"
        assert retrieval_text._cut_offset(body, "references") == len("References\nbody\n")

    def test_a_header_absent_from_the_body_is_none(self):
        assert retrieval_text._cut_offset("nothing like it here\n", "references") is None


class TestBodyBeforeReferences:
    def test_truncates_at_the_header(self, isolated_config):
        write_sidecar("a2024", [header("References")])
        body = "real body text\n## References\n[1] Someone Else. A Paper About Cats.\n"
        assert retrieval_text.body_before_references(body, "a2024") == "real body text\n"

    def test_unchanged_with_no_sidecar(self, isolated_config):
        body = "real body text\n## References\n[1] Someone Else.\n"
        assert retrieval_text.body_before_references(body, "a2024") == body

    def test_unchanged_with_no_reference_header(self, isolated_config):
        write_sidecar("a2024", [header("Introduction")])
        body = "real body text\n## References\n[1] Someone Else.\n"
        assert retrieval_text.body_before_references(body, "a2024") == body

    def test_unchanged_when_the_header_is_not_in_the_body(self, isolated_config):
        """The sidecar and the `.txt` are two serialisations of one parse,
        so they normally agree -- but the sidecar can outlive a hand-edited
        `.txt`, and indexing the document whole is the right cost for
        that."""
        write_sidecar("a2024", [header("References")])
        body = "real body text, and no heading line at all\n"
        assert retrieval_text.body_before_references(body, "a2024") == body


class TestFullText:
    def test_title_only_when_not_parsed(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="A Title"))
        row = ledger.all_items(ledger_con)[0]
        assert retrieval_text._full_text(row) == "A Title"

    def test_a_missing_parsed_file_is_not_an_error(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="A Title"))
        ledger.mark_parsed(ledger_con, "a2024", "content/parsed/gone.txt")
        row = ledger.all_items(ledger_con)[0]
        assert retrieval_text._full_text(row) == "A Title"

    def test_drops_the_reference_list(self, ledger_con, tmp_path):
        parsed = tmp_path / "a2024.txt"
        parsed.write_text("body about turbines\n## References\n[1] A Paper About Cats.\n")
        ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="A Title"))
        ledger.mark_parsed(ledger_con, "a2024", parsed)
        write_sidecar("a2024", [header("References")])
        row = ledger.all_items(ledger_con)[0]

        text = retrieval_text._full_text(row)
        assert "turbines" in text
        assert "Cats" not in text


class TestTheRankerStopsReadingBibliographies:
    """The behaviour the whole module exists for, at the level `search`
    actually reports."""

    def _seed(self, con, tmp_path, citekey, body, records=None):
        parsed = tmp_path / f"{citekey}.txt"
        parsed.write_text(body)
        ledger.upsert_reference(con, make_reference(citekey=citekey, title="Untitled"))
        ledger.mark_parsed(con, citekey, parsed)
        if records is not None:
            write_sidecar(citekey, records)

    def test_a_paper_that_only_cites_the_subject_no_longer_matches(self, ledger_con, tmp_path):
        self._seed(
            ledger_con,
            tmp_path,
            "cites_it",
            "this paper is about turbines\n## References\n[1] Groundwater Salinity Modelling.\n",
            [header("References")],
        )
        assert retrieval.search("groundwater salinity") == []

    def test_the_paper_actually_about_it_still_matches(self, ledger_con, tmp_path):
        self._seed(
            ledger_con,
            tmp_path,
            "about_it",
            "groundwater salinity is modelled here at length\n## References\n[1] Cats.\n",
            [header("References")],
        )
        hits = [r.citekey for r in retrieval.search("groundwater salinity")]
        assert hits == ["about_it"]

    def test_an_item_with_no_sidecar_is_indexed_whole(self, ledger_con, tmp_path):
        """The `pdftotext` backend writes no sidecar, and those items keep
        today's behaviour rather than being cut by a guess."""
        self._seed(
            ledger_con,
            tmp_path,
            "no_sidecar",
            "this paper is about turbines\nReferences\n[1] Groundwater Salinity Modelling.\n",
        )
        hits = [r.citekey for r in retrieval.search("groundwater salinity")]
        assert hits == ["no_sidecar"]

    def test_a_snippet_cannot_be_drawn_from_a_reference_list(self, ledger_con, tmp_path):
        self._seed(
            ledger_con,
            tmp_path,
            "a2024",
            "turbines everywhere in this body\n## References\n[1] Turbines In Passing.\n",
            [header("References")],
        )
        (result,) = retrieval.search("turbines")
        assert "In Passing" not in result.snippet

    def test_evidence_cannot_draw_a_window_from_one_either(self, ledger_con, tmp_path):
        """`evidence` transcribes into a dossier, so it is the caller a
        bibliography window would do the most damage to."""
        self._seed(
            ledger_con,
            tmp_path,
            "a2024",
            "turbines everywhere in this body\n## References\n[1] Turbines In Passing.\n",
            [header("References")],
        )
        windows = retrieval_cli.evidence("a2024", "turbines")
        assert not any("In Passing" in w for w in windows)
