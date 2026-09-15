"""chitragupta/_reference_cut.py: a paper's own bibliography kept out of
what BM25 indexes and out of what it quotes back (#768)."""

import json

import pytest

from chitragupta import _reference_cut, config, ledger, retrieval, retrieval_cache, retrieval_cli

from tests.conftest import make_reference

BODY = "this chapter measures greenhouse humidity with an incubator\n\n"
REFS = "References\n\nSmith 2020. Blockchain consensus for supply chains.\n"


def parsed_file(text: str, citekey: str = "a2024"):
    """`text` written where the corpus layer would have parsed it to."""
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PARSED_DIR / f"{citekey}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def sidecar(records: list[dict], citekey: str = "a2024"):
    """A corpus-layer passage sidecar (rung 2) for `citekey`."""
    path = config.PARSED_DIR / f"{citekey}.passages.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def refs_sidecar(header: str = "References", citekey: str = "a2024"):
    return sidecar(
        [
            {"text": BODY.strip(), "label": "text", "page": 1},
            {"text": header, "label": "section_header", "page": 2},
        ],
        citekey=citekey,
    )


def seeded(con, text: str, citekey: str = "a2024", title: str = "An Incubator Study"):
    """A ledger row whose parsed text is `text`."""
    path = parsed_file(text, citekey)
    ledger.upsert_reference(con, make_reference(citekey=citekey, title=title))
    ledger.mark_parsed(con, citekey, path)
    return path


class TestStripReferences:
    def test_text_from_the_header_onward_is_dropped(self, isolated_config):
        path = parsed_file(BODY + REFS)
        refs_sidecar()

        assert _reference_cut.strip_references(BODY + REFS, str(path)) == BODY

    def test_a_document_with_no_reference_header_is_unchanged(self, isolated_config):
        path = parsed_file(BODY)
        sidecar([{"text": BODY.strip(), "label": "text", "page": 1}])

        assert _reference_cut.strip_references(BODY, str(path)) == BODY

    def test_no_sidecar_leaves_the_text_unchanged(self, isolated_config):
        # A `pdftotext` parse writes no sidecar, so there is no reading
        # order to cut on and the item keeps today's behaviour.
        path = parsed_file(BODY + REFS)

        assert _reference_cut.strip_references(BODY + REFS, str(path)) == BODY + REFS

    def test_a_corrupt_sidecar_leaves_the_text_unchanged(self, isolated_config):
        path = parsed_file(BODY + REFS)
        (config.PARSED_DIR / "a2024.passages.json").write_text("{not valid json", encoding="utf-8")

        assert _reference_cut.strip_references(BODY + REFS, str(path)) == BODY + REFS

    def test_the_last_matching_header_is_the_cut_point(self, isolated_config):
        # A per-chapter book has one bibliography per chapter. The rule is
        # the last of them to the end of the document, so an earlier
        # chapter's references stay indexed -- stated by a test rather
        # than left as an assumption about the corpus.
        text = BODY + REFS + "chapter two on calibration\n\n" + REFS
        path = parsed_file(text)
        sidecar(
            [
                {"text": BODY.strip(), "label": "text", "page": 1},
                {"text": "References", "label": "section_header", "page": 2},
                {"text": "chapter two on calibration", "label": "text", "page": 3},
                {"text": "References", "label": "section_header", "page": 4},
            ]
        )

        assert _reference_cut.strip_references(text, str(path)) == (
            BODY + REFS + "chapter two on calibration\n\n"
        )

    @pytest.mark.parametrize(
        "header", ["REFERENCES", "Bibliography", "7 REFERENCES", "References:"]
    )
    def test_the_header_spellings_this_corpus_actually_uses(self, isolated_config, header):
        text = BODY + header + "\n\nSmith 2020.\n"
        path = parsed_file(text)
        refs_sidecar(header)

        assert _reference_cut.strip_references(text, str(path)) == BODY

    def test_a_heading_that_merely_starts_with_the_word_is_not_a_cut_point(self, isolated_config):
        text = BODY + "Reference architecture\n\nthe layered view of an incubator\n"
        path = parsed_file(text)
        refs_sidecar("Reference architecture")

        assert _reference_cut.strip_references(text, str(path)) == text

    def test_a_reference_marker_that_is_not_a_section_header_is_not_a_cut_point(
        self, isolated_config
    ):
        # Position after a *heading* is what carries the signal. A
        # running-head or a caption reading "References" is not one.
        text = BODY + "References\n\nsee the incubator's own manual\n"
        path = parsed_file(text)
        sidecar(
            [
                {"text": BODY.strip(), "label": "text", "page": 1},
                {"text": "References", "label": "caption", "page": 2},
            ]
        )

        assert _reference_cut.strip_references(text, str(path)) == text

    def test_a_header_the_flattened_text_does_not_contain_leaves_it_unchanged(
        self, isolated_config
    ):
        # The sidecar and the .txt come from one parse, so this should not
        # happen -- but a hand-edited sidecar must not silently truncate a
        # document at position zero.
        path = parsed_file(BODY)
        refs_sidecar()

        assert _reference_cut.strip_references(BODY, str(path)) == BODY

    def test_an_item_with_no_parsed_path_is_unchanged(self, isolated_config):
        assert _reference_cut.strip_references(BODY + REFS, None) == BODY + REFS


class TestReferencesAreNotIndexed:
    def test_a_query_matching_only_the_bibliography_finds_nothing(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()

        assert retrieval.search("blockchain") == []

    def test_the_same_query_still_finds_it_without_a_sidecar(self, ledger_con):
        # The control for the case above: it is the cut that drops the
        # hit, not the fixture failing to contain the word.
        seeded(ledger_con, BODY + REFS)

        assert [r.citekey for r in retrieval.search("blockchain")] == ["a2024"]

    def test_the_body_is_still_found(self, ledger_con):
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()

        assert [r.citekey for r in retrieval.search("incubator")] == ["a2024"]

    def test_the_indexed_length_reflects_the_cut(self, ledger_con):
        # BM25 normalizes by document length, so a bibliography left in
        # the count penalises the paper that carries it even for a query
        # none of its references match.
        seeded(ledger_con, BODY + REFS)
        refs_sidecar()
        row = ledger.all_items(ledger_con)[0]

        entry = retrieval._tokenize_item(row)
        assert "blockchain" not in entry["term_freqs"]
        assert entry["length"] == len(retrieval._tokenize(f"{row['title']}\n{BODY}"))

    def test_a_snippet_cannot_be_drawn_from_a_reference_list(self, ledger_con):
        # The bibliography is the only place the query's term appears
        # *near*, so a snippet chosen from uncut text would show it.
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
        # chitragupta/retrieval.py's docstring promises that running the
        # enrichment layer's Docling stage does not change what BM25
        # ranks. Rung 1 (content/docling/) is that layer's own parse, so
        # this reads rung 2 alone -- and this test is what stops a later
        # refactor reaching for `passages.structural_passages`, which
        # tries rung 1 first.
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
        # Every entry written before #768 counted the bibliography's
        # tokens, and the parsed file's own stat -- which is what the
        # fingerprint carries -- has not moved. Only the schema version
        # says the entry is from a different indexing rule.
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
