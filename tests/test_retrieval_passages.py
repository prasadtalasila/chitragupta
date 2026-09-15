"""chitragupta/retrieval_passages.py: BM25 whose unit is a paragraph
rather than a whole document (#769).

The properties these pin are the ones the document-level path gets for
free and this one has to earn: a source cannot take over the result set
(there is a cap, where `retrieval.search` needs none), the text handed
back is the text that scored (where `retrieval.search` chooses a window
afterwards by an unrelated rule), and a short dense passage cannot
outrank a real paragraph on length normalization alone.
"""

import json

import pytest

from chitragupta import (
    config,
    ledger,
    passages,
    retrieval,
    retrieval_passages,
    retrieval_passages_cache,
)

from tests.conftest import make_reference

# Long enough to clear MIN_PASSAGE_TOKENS (20 after tokenizing) so a test
# that is not about the floor does not trip over it.
FILLER = " ".join(f"substrate{i}" for i in range(30))


def paragraph(text: str, page: int = 1, label: str = "text") -> dict:
    return {"text": text, "label": label, "page": page}


def seeded(con, citekey: str, records: list[dict], title: str = "An Incubator Study", **fields):
    """A ledger row whose corpus-layer sidecar holds `records`.

    The flattened `.txt` is written too, and deliberately does not hold
    the passage text: nothing on this path reads it, and a test that let
    it agree could not tell the two apart.
    """
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PARSED_DIR / f"{citekey}.txt"
    path.write_text("flattened text nothing here reads\n", encoding="utf-8")
    (config.PARSED_DIR / f"{citekey}.passages.json").write_text(
        json.dumps(records), encoding="utf-8"
    )
    ledger.upsert_reference(con, make_reference(citekey=citekey, title=title, **fields))
    ledger.mark_parsed(con, citekey, path)
    return path


class TestTheUnitIsAPassage:
    def test_a_hit_carries_its_citekey_reading_position_and_page(self, ledger_con):
        seeded(
            ledger_con,
            "a2024",
            [
                paragraph(f"an unrelated opening {FILLER}", page=1),
                paragraph(f"greenhouse humidity is regulated by the incubator {FILLER}", page=7),
            ],
        )

        found = retrieval_passages.search_passages("greenhouse humidity incubator")

        assert [(r.citekey, r.passage_index, r.page) for r in found.results] == [("a2024", 1, 7)]

    def test_the_text_returned_is_the_passage_that_scored(self, ledger_con):
        # The whole point of the unit change: `retrieval.search` picks a
        # 500-character window *after* ranking, by a different rule. Here
        # what is shown is the object that won.
        body = f"greenhouse humidity is regulated by the incubator {FILLER}"
        seeded(ledger_con, "a2024", [paragraph("an unrelated opening"), paragraph(body)])

        found = retrieval_passages.search_passages("greenhouse humidity")

        assert found.results[0].text == body

    def test_a_query_that_tokenizes_to_nothing_returns_no_results(self, ledger_con):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])

        assert retrieval_passages.search_passages("why is it?").results == []

    def test_the_documents_title_rides_along_from_the_ledger(self, ledger_con):
        seeded(
            ledger_con,
            "a2024",
            [paragraph(f"greenhouse humidity {FILLER}")],
            title="Regulating An Incubator",
        )

        assert retrieval_passages.search_passages("greenhouse").results[0].title == (
            "Regulating An Incubator"
        )

    def test_the_label_rides_along_so_a_caller_can_tell_a_table_from_prose(self, ledger_con):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}", label="table")])

        assert retrieval_passages.search_passages("greenhouse").results[0].label == "table"


class TestTheCapOnPassagesPerSource:
    def dominant(self, con):
        """One paper with five matching paragraphs, one with a sixth."""
        seeded(
            con,
            "loud2024",
            [paragraph(f"greenhouse humidity paragraph {i} {FILLER}") for i in range(5)],
        )
        seeded(con, "quiet2024", [paragraph(f"greenhouse humidity alone {FILLER}")])

    def test_no_citekey_exceeds_the_configured_cap(self, ledger_con, monkeypatch):
        monkeypatch.setattr(config, "MAX_PASSAGES_PER_SOURCE", 2)
        self.dominant(ledger_con)

        found = retrieval_passages.search_passages("greenhouse humidity", k=5)

        assert sum(1 for r in found.results if r.citekey == "loud2024") == 2

    def test_capping_promotes_another_source_rather_than_shortening_the_list(
        self, ledger_con, monkeypatch
    ):
        # The failure #305 existed to fix, asserted on this path: a cap
        # that merely dropped the excess would return 2 results here, not
        # 3, and the quiet paper would never appear.
        monkeypatch.setattr(config, "MAX_PASSAGES_PER_SOURCE", 2)
        self.dominant(ledger_con)

        found = retrieval_passages.search_passages("greenhouse humidity", k=3)

        assert len(found.results) == 3
        assert "quiet2024" in {r.citekey for r in found.results}

    def test_a_cap_of_one_gives_one_passage_per_source(self, ledger_con, monkeypatch):
        monkeypatch.setattr(config, "MAX_PASSAGES_PER_SOURCE", 1)
        self.dominant(ledger_con)

        found = retrieval_passages.search_passages("greenhouse humidity", k=5)

        assert len(found.results) == len({r.citekey for r in found.results})

    def test_the_cap_keeps_the_best_scoring_passages_not_the_first_seen(
        self, ledger_con, monkeypatch
    ):
        monkeypatch.setattr(config, "MAX_PASSAGES_PER_SOURCE", 1)
        seeded(
            ledger_con,
            "a2024",
            [
                paragraph(f"greenhouse alone {FILLER}"),
                paragraph(f"greenhouse humidity incubator together {FILLER}"),
            ],
        )

        found = retrieval_passages.search_passages("greenhouse humidity incubator")

        assert found.results[0].passage_index == 1


class TestWhatIsNotIndexed:
    def test_a_passage_at_or_after_the_reference_header_is_not_indexed(self, ledger_con):
        # The same boundary `_reference_cut` already cuts the document
        # index on, read as a position rather than re-derived -- and the
        # case that matters here is the one the issue got backwards: a
        # bibliography entry is short and dense, so BM25's length
        # normalization would rank it *above* a real paragraph.
        seeded(
            ledger_con,
            "a2024",
            [
                paragraph(f"the incubator study body {FILLER}"),
                paragraph("References", label="section_header"),
                paragraph(f"Smith 2020. Greenhouse humidity in supply chains. {FILLER}"),
            ],
        )

        assert retrieval_passages.search_passages("greenhouse humidity").results == []

    def test_a_section_header_is_not_indexed_even_before_the_references(self, ledger_con):
        # A three-word heading whose text *is* the query is the highest
        # scoring object in any BM25 index that admits it, and it is
        # evidence of nothing.
        seeded(
            ledger_con,
            "a2024",
            [
                paragraph("Greenhouse Humidity", label="section_header"),
                paragraph(f"the incubator regulates it {FILLER}", label="text"),
            ],
        )

        assert retrieval_passages.search_passages("greenhouse humidity").results == []

    def test_a_passage_under_the_token_floor_is_not_indexed(self, ledger_con, monkeypatch):
        monkeypatch.setattr(config, "MIN_PASSAGE_TOKENS", 10)
        seeded(ledger_con, "a2024", [paragraph("greenhouse humidity incubator")])

        assert retrieval_passages.search_passages("greenhouse humidity").results == []

    def test_lowering_the_floor_admits_it_again(self, ledger_con, monkeypatch):
        monkeypatch.setattr(config, "MIN_PASSAGE_TOKENS", 1)
        seeded(ledger_con, "a2024", [paragraph("greenhouse humidity incubator")])

        assert len(retrieval_passages.search_passages("greenhouse humidity").results) == 1

    def test_an_item_whose_status_is_not_parsed_is_not_indexed(self, ledger_con):
        # Same guard #490 added to the document path: a reparse failure
        # leaves parsed_path -- and the sidecar beside it -- naming text a
        # superseded PDF produced.
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        ledger.mark_parse_failed(ledger_con, "a2024", "boom")

        assert retrieval_passages.search_passages("greenhouse humidity").results == []

    def test_a_hit_whose_position_no_longer_resolves_is_dropped_not_raised(
        self, ledger_con, monkeypatch
    ):
        # The index and the text come from two separate reads of the same
        # sidecar. The fingerprint closes the ordinary window, but not one
        # inside a single call -- a re-parse landing between the ranking
        # and the text lookup would index out of range, and a search dying
        # with a bare IndexError is worse than one short hit.
        seeded(
            ledger_con,
            "a2024",
            [paragraph(f"greenhouse humidity {i} {FILLER}") for i in range(3)],
        )
        real = passages.corpus_passages
        calls = []

        def shrinking(citekey):
            found = real(citekey)
            # Intact for the index build, truncated by the time the winners
            # are resolved.
            calls.append(citekey)
            return found if len(calls) == 1 else found[:1]

        monkeypatch.setattr(passages, "corpus_passages", shrinking)
        retrieval_passages_cache._forget_cache()

        found = retrieval_passages.search_passages("greenhouse humidity", k=3)

        assert [r.passage_index for r in found.results] == [0]


class TestSourcesThisPathCannotReach:
    def test_an_item_with_no_sidecar_is_counted_rather_than_silently_absent(self, ledger_con):
        # A pdftotext parse writes no sidecar, so the source is not
        # ranked low here -- it is not present at all. That is a real
        # answer and has to be sayable.
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        path = config.PARSED_DIR / "nosidecar2024.txt"
        path.write_text(f"greenhouse humidity {FILLER}\n", encoding="utf-8")
        ledger.upsert_reference(ledger_con, make_reference(citekey="nosidecar2024"))
        ledger.mark_parsed(ledger_con, "nosidecar2024", path)

        found = retrieval_passages.search_passages("greenhouse humidity")

        assert found.results == []
        assert found.without_sidecar == 1

    def test_an_item_with_a_sidecar_is_not_counted(self, ledger_con):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])

        assert retrieval_passages.search_passages("greenhouse humidity").without_sidecar == 0

    def test_a_sidecar_whose_passages_all_fail_the_floor_is_not_counted(
        self, ledger_con, monkeypatch
    ):
        # It has a sidecar and is parsed fine; it just has nothing long
        # enough to rank. Reporting it as sidecar-less would send a reader
        # to re-parse a document with no parse problem.
        monkeypatch.setattr(config, "MIN_PASSAGE_TOKENS", 100)
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])

        found = retrieval_passages.search_passages("greenhouse humidity")

        assert found.results == []
        assert found.without_sidecar == 0

    def test_an_unparsed_item_is_not_counted_as_missing_a_sidecar(self, ledger_con):
        # It has no parsed text at all, so "no sidecar" is not what is
        # wrong with it and reporting it here would misattribute the gap.
        ledger.upsert_reference(ledger_con, make_reference(citekey="unparsed2024"))

        assert retrieval_passages.search_passages("greenhouse").without_sidecar == 0


class TestDeterminismAndOrdering:
    def test_ties_break_on_citekey_then_passage_index(self, ledger_con):
        # Two identical passages in two papers score identically, and
        # `set` iteration order is randomised per process -- so without an
        # explicit tie-break this is a different answer run to run.
        for citekey in ("b2024", "a2024"):
            seeded(ledger_con, citekey, [paragraph(f"greenhouse humidity {FILLER}")])

        found = retrieval_passages.search_passages("greenhouse humidity", k=2)

        assert [r.citekey for r in found.results] == ["a2024", "b2024"]

    def test_the_same_query_gives_the_same_answer_twice(self, ledger_con):
        seeded(
            ledger_con,
            "a2024",
            [paragraph(f"greenhouse humidity {i} {FILLER}") for i in range(4)],
        )

        first = retrieval_passages.search_passages("greenhouse humidity", k=3)
        second = retrieval_passages.search_passages("greenhouse humidity", k=3)

        assert [r.passage_index for r in first.results] == [r.passage_index for r in second.results]


class TestTheCollectionFilter:
    def test_only_items_in_the_named_collection_are_returned(self, ledger_con):
        seeded(
            ledger_con,
            "in2024",
            [paragraph(f"greenhouse humidity {FILLER}")],
            collections=("Modelling",),
        )
        seeded(ledger_con, "out2024", [paragraph(f"greenhouse humidity {FILLER}")])

        found = retrieval_passages.search_passages("greenhouse humidity", collection="Modelling")

        assert [r.citekey for r in found.results] == ["in2024"]


class TestTheIndexCache:
    def test_a_second_search_reuses_the_cached_passage_stats(self, ledger_con, monkeypatch):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        retrieval_passages.search_passages("greenhouse")

        calls = []
        real = retrieval_passages_cache._passage_stats
        # The cache module, not this one: `load_index` binds the name in
        # its own namespace, so patching it on the caller reaches nothing.
        monkeypatch.setattr(
            retrieval_passages_cache,
            "_passage_stats",
            lambda *a: calls.append(1) or real(*a),
        )
        retrieval_passages.search_passages("humidity")

        assert calls == []

    def test_a_rewritten_sidecar_invalidates_the_entry(self, ledger_con):
        # The document index's fingerprint deliberately omits the sidecar,
        # because there the .txt is the source of truth and moves with it.
        # Here the sidecar *is* the source, so it has to be fingerprinted
        # or a restored/hand-written one is invisible.
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        retrieval_passages.search_passages("greenhouse")

        (config.PARSED_DIR / "a2024.passages.json").write_text(
            json.dumps([paragraph(f"blockchain consensus instead {FILLER}")]), encoding="utf-8"
        )
        retrieval_passages_cache._forget_cache()

        assert retrieval_passages.search_passages("greenhouse").results == []
        assert len(retrieval_passages.search_passages("blockchain consensus").results) == 1

    def test_changing_the_token_floor_invalidates_the_entry(self, ledger_con, monkeypatch):
        # The floor decides what is in the index, not just what is
        # returned, so a cache written under one value cannot be reused
        # under another.
        monkeypatch.setattr(config, "MIN_PASSAGE_TOKENS", 100)
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        assert retrieval_passages.search_passages("greenhouse").results == []

        monkeypatch.setattr(config, "MIN_PASSAGE_TOKENS", 1)
        retrieval_passages_cache._forget_cache()

        assert len(retrieval_passages.search_passages("greenhouse").results) == 1

    def test_a_corrupt_cache_file_is_rebuilt_rather_than_fatal(self, ledger_con):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        config.RETRIEVAL_PASSAGE_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_PASSAGE_INDEX_PATH.write_text("{not json", encoding="utf-8")
        retrieval_passages_cache._forget_cache()

        assert len(retrieval_passages.search_passages("greenhouse humidity").results) == 1

    @pytest.mark.parametrize(
        "payload",
        [
            '["a bare array"]',
            '{"version": 0, "items": {}}',
            '{"version": 1, "items": "not a dict"}',
        ],
    )
    def test_an_unexpected_cache_shape_is_a_miss_rather_than_a_crash(self, ledger_con, payload):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        config.RETRIEVAL_PASSAGE_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_PASSAGE_INDEX_PATH.write_text(payload, encoding="utf-8")
        retrieval_passages_cache._forget_cache()

        assert len(retrieval_passages.search_passages("greenhouse humidity").results) == 1

    def test_an_entry_of_the_wrong_shape_costs_a_retokenize_rather_than_a_crash(self, ledger_con):
        # #504/M-24 on the document path: a hand-edited entry with a
        # matching fingerprint but no usable payload used to be reused
        # as-is and crash the scorer.
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        retrieval_passages.search_passages("greenhouse")
        data = json.loads(config.RETRIEVAL_PASSAGE_INDEX_PATH.read_text(encoding="utf-8"))
        data["items"]["a2024"]["passages"] = "not a list"
        config.RETRIEVAL_PASSAGE_INDEX_PATH.write_text(json.dumps(data), encoding="utf-8")
        retrieval_passages_cache._forget_cache()

        assert len(retrieval_passages.search_passages("greenhouse humidity").results) == 1

    def test_a_dropped_citekey_is_removed_from_the_cache(self, ledger_con):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        retrieval_passages.search_passages("greenhouse")
        ledger_con.execute("DELETE FROM items WHERE citekey = ?", ("a2024",))
        ledger_con.commit()

        retrieval_passages.search_passages("greenhouse")
        data = json.loads(config.RETRIEVAL_PASSAGE_INDEX_PATH.read_text(encoding="utf-8"))

        assert data["items"] == {}


class TestTheCli:
    """`retrieve search --unit passage`. A flag rather than a sibling
    subcommand deliberately: same question, two units -- and
    docs/PACKAGING.md's leaf-command count is test-enforced."""

    def test_the_default_unit_is_the_document_and_is_unchanged(self, ledger_con, capsys):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        (config.PARSED_DIR / "a2024.txt").write_text(
            f"greenhouse humidity {FILLER}\n", encoding="utf-8"
        )

        assert retrieval.main(["search", "greenhouse humidity"]) == 0
        assert "evidence --citekey" in capsys.readouterr().out

    def test_unit_passage_prints_the_paragraph_and_its_page(self, ledger_con, capsys):
        body = f"greenhouse humidity is regulated by the incubator {FILLER}"
        seeded(ledger_con, "a2024", [paragraph(body, page=7)])

        assert retrieval.main(["search", "greenhouse humidity", "--unit", "passage"]) == 0
        out = capsys.readouterr().out
        assert body in out
        assert "p.7" in out

    def test_a_passage_with_no_page_falls_back_to_its_reading_position(self, ledger_con, capsys):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}", page=None)])

        retrieval.main(["search", "greenhouse humidity", "--unit", "passage"])

        assert "passage 0" in capsys.readouterr().out

    def test_an_empty_passage_ranking_says_so(self, ledger_con, capsys):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])

        retrieval.main(["search", "blockchain consensus", "--unit", "passage"])

        assert "No results." in capsys.readouterr().out

    def test_sources_with_no_sidecar_are_named_rather_than_silently_absent(
        self, ledger_con, capsys
    ):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])
        path = config.PARSED_DIR / "nosidecar2024.txt"
        path.write_text("greenhouse humidity\n", encoding="utf-8")
        ledger.upsert_reference(ledger_con, make_reference(citekey="nosidecar2024"))
        ledger.mark_parsed(ledger_con, "nosidecar2024", path)

        retrieval.main(["search", "greenhouse humidity", "--unit", "passage"])

        assert "1 parsed source(s) have no passage sidecar" in capsys.readouterr().out

    def test_no_such_note_when_every_source_has_one(self, ledger_con, capsys):
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])

        retrieval.main(["search", "greenhouse humidity", "--unit", "passage"])

        assert "no passage sidecar" not in capsys.readouterr().out

    def test_y_prev_with_the_passage_unit_is_refused_rather_than_ignored(self, ledger_con, capsys):
        # It merges two rounds on citekey and caps back to --k, which the
        # passage unit changes the meaning of. Silently ignoring either
        # flag would be the worse answer.
        seeded(ledger_con, "a2024", [paragraph(f"greenhouse humidity {FILLER}")])

        code = retrieval.main(
            ["search", "greenhouse", "--unit", "passage", "--y-prev", "some prose"]
        )

        assert code == 1
        assert "document-unit only" in capsys.readouterr().err


class TestTheDocumentPathIsUntouched:
    def test_search_still_returns_one_result_per_citekey(self, ledger_con):

        seeded(
            ledger_con,
            "a2024",
            [paragraph(f"greenhouse humidity paragraph {i} {FILLER}") for i in range(5)],
        )
        # The document index reads the flattened .txt, which `seeded`
        # deliberately fills with something else -- so put the passage
        # text there too for this one comparison.
        (config.PARSED_DIR / "a2024.txt").write_text(
            "greenhouse humidity in the incubator\n", encoding="utf-8"
        )

        found = retrieval.search("greenhouse humidity")

        assert [r.citekey for r in found] == ["a2024"]
