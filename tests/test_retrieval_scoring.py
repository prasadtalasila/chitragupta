import math

import pytest

from chitragupta import _abstract, config, ledger, passages, retrieval, retrieval_scoring

from tests.conftest import make_reference, parsed_text, plant_sidecar

ABSTRACT = (
    "This paper studies greenhouse humidity control in a commercial incubator, and "
    "reports a controller that holds the setpoint within half a degree across a full "
    "growing season. We describe the instrumentation, the calibration procedure and "
    "the two failure modes we observed in the field, and we release the logged data "
    "so that the result can be checked independently by other groups."
)
BODY = "The incubator was installed in a glasshouse and ran unattended for six months.\n"


def abstract_records(abstract: str = ABSTRACT):
    return [
        {"text": "An Incubator Study", "label": "title", "page": 1},
        {"text": "Abstract", "label": "section_header", "page": 1},
        {"text": abstract, "label": "text", "page": 1},
        {"text": "1 Introduction", "label": "section_header", "page": 1},
        {"text": BODY.strip(), "label": "text", "page": 1},
    ]


def as_passages(records: "list[dict] | None" = None):
    return [
        passages.Passage(page=rec["page"], words=set(), text=rec["text"], label=rec["label"])
        for rec in (abstract_records() if records is None else records)
    ]


def seeded(con, citekey="a2024", title="An Incubator Study", text=None):
    path = parsed_text(citekey, text if text is not None else f"{ABSTRACT}\n{BODY}")
    ledger.upsert_reference(con, make_reference(citekey=citekey, title=title))
    ledger.mark_parsed(con, citekey, path)
    return path


def weights(monkeypatch, **overrides):
    pinned = dict.fromkeys(retrieval_scoring.FIELDS, 1.0)
    pinned.update(overrides)
    monkeypatch.setattr(config, "RETRIEVAL_FIELD_WEIGHTS", pinned)


class TestTheFieldListDrivesTheSeam:
    def test_every_field_has_a_configured_weight(self):
        assert set(config.RETRIEVAL_FIELD_WEIGHTS) == set(retrieval_scoring.FIELDS)

    def test_title_and_abstract_are_the_fields_that_ship(self):
        assert retrieval_scoring.FIELDS == ("title", "abstract")


class TestDefaultsShipInert:
    def test_every_weight_defaults_to_one(self):
        assert set(config.RETRIEVAL_FIELD_WEIGHTS.values()) == {1.0}

    def test_weights_of_one_produce_no_deltas(self, monkeypatch):
        weights(monkeypatch)
        assert retrieval_scoring.field_deltas() == []


class TestWeightedFreq:
    def test_a_weight_of_one_is_the_plain_frequency(self, monkeypatch):
        weights(monkeypatch)
        entry = {"term_freqs": {"twin": 7}, "field_freqs": {"title": {"twin": 2}}}
        assert retrieval_scoring.weighted_freq(entry, "twin", []) == 7

    def test_a_weight_above_one_adds_the_field_count_once(self, monkeypatch):
        weights(monkeypatch, title=3.0)
        entry = {"term_freqs": {"twin": 7}, "field_freqs": {"title": {"twin": 2}}}
        got = retrieval_scoring.weighted_freq(entry, "twin", retrieval_scoring.field_deltas())
        assert got == pytest.approx(7 + 2 * 2)

    def test_an_entry_with_no_field_freqs_scores_unweighted(self, monkeypatch):
        weights(monkeypatch, title=5.0)
        entry = {"term_freqs": {"twin": 4}}
        got = retrieval_scoring.weighted_freq(entry, "twin", retrieval_scoring.field_deltas())
        assert got == 4

    def test_a_term_absent_from_the_document_scores_zero(self, monkeypatch):
        weights(monkeypatch, title=3.0)
        entry = {"term_freqs": {}, "field_freqs": {"title": {}}}
        got = retrieval_scoring.weighted_freq(entry, "absent", retrieval_scoring.field_deltas())
        assert got == 0

    def test_the_frequency_is_clamped_at_zero(self, monkeypatch):
        weights(monkeypatch, title=0.0)
        entry = {"term_freqs": {"twin": 1}, "field_freqs": {"title": {"twin": 3}}}
        got = retrieval_scoring.weighted_freq(entry, "twin", retrieval_scoring.field_deltas())
        assert got == 0.0


class TestFieldTexts:
    def test_the_title_comes_from_the_ledger_row(self, ledger_con):
        seeded(ledger_con, title="Greenhouse Humidity Control")
        row = ledger.all_items(ledger_con)[0]
        assert retrieval_scoring.field_texts(row)["title"] == "Greenhouse Humidity Control"

    def test_the_abstract_comes_from_the_corpus_sidecar(self, ledger_con):
        seeded(ledger_con)
        plant_sidecar("a2024", abstract_records(), docling=False)
        row = ledger.all_items(ledger_con)[0]
        assert retrieval_scoring.field_texts(row)["abstract"] == ABSTRACT

    def test_no_sidecar_means_no_abstract_field(self, ledger_con):
        seeded(ledger_con)
        row = ledger.all_items(ledger_con)[0]
        assert "abstract" not in retrieval_scoring.field_texts(row)

    def test_a_sidecar_with_no_detectable_abstract_yields_no_field(self, ledger_con):
        seeded(ledger_con)
        plant_sidecar("a2024", [{"text": BODY.strip(), "label": "text", "page": 1}], docling=False)
        row = ledger.all_items(ledger_con)[0]
        assert "abstract" not in retrieval_scoring.field_texts(row)

    def test_the_enrichment_sidecar_is_not_read(self, ledger_con, monkeypatch):
        seeded(ledger_con)
        monkeypatch.setattr(passages, "structural_passages", lambda citekey: as_passages())
        row = ledger.all_items(ledger_con)[0]
        assert "abstract" not in retrieval_scoring.field_texts(row)


class TestFieldFreqs:
    def test_a_field_whose_text_tokenizes_to_nothing_is_omitted(self, ledger_con):
        seeded(ledger_con, title="Of On In A")
        row = ledger.all_items(ledger_con)[0]
        assert "title" not in retrieval_scoring.field_freqs(row, retrieval._tokenize)

    def test_field_counts_are_per_field_not_pooled(self, ledger_con):
        seeded(ledger_con, title="Greenhouse Greenhouse Humidity")
        row = ledger.all_items(ledger_con)[0]
        counts = retrieval_scoring.field_freqs(row, retrieval._tokenize)
        assert counts["title"] == {"greenhouse": 2, "humidity": 1}


class TestTokenisingTheFieldsSeparatelyIsConsistent:
    def test_a_field_can_never_out_count_the_whole_document(self, ledger_con):
        seeded(ledger_con, title="Greenhouse Humidity In A Greenhouse")
        plant_sidecar("a2024", abstract_records(), docling=False)
        row = ledger.all_items(ledger_con)[0]
        entry = retrieval._tokenize_item(row)

        for counts in entry["field_freqs"].values():
            for term, count in counts.items():
                assert count <= entry["term_freqs"].get(term, 0)


class TestBm25ScoresAreUnchangedAtWeightOne:
    def test_the_ranking_is_identical_with_and_without_field_freqs(self, monkeypatch):
        weights(monkeypatch)
        plain = {"a": {"length": 10, "term_freqs": {"twin": 3}}}
        with_fields = {
            "a": {"length": 10, "term_freqs": {"twin": 3}, "field_freqs": {"title": {"twin": 3}}}
        }
        assert retrieval_scoring.bm25_scores(
            with_fields, ["twin"]
        ) == retrieval_scoring.bm25_scores(plain, ["twin"])

    def test_an_empty_index_scores_nothing(self):
        assert retrieval_scoring.bm25_scores({}, ["twin"]) == {}


class TestSearchHonoursTheWeights:
    def test_weighting_the_title_flips_the_paper_that_only_mentions_it(
        self, ledger_con, monkeypatch
    ):
        seeded(
            ledger_con,
            citekey="about2024",
            title="Greenhouse Humidity",
            text="an unrelated body about calibration procedure and instrumentation\n",
        )
        seeded(
            ledger_con,
            citekey="passing2024",
            title="Unrelated Paper",
            text="greenhouse humidity " * 12,
        )

        weights(monkeypatch)
        unweighted = [r.citekey for r in retrieval.search("greenhouse humidity")]
        weights(monkeypatch, title=8.0)
        weighted = [r.citekey for r in retrieval.search("greenhouse humidity")]

        assert unweighted[0] == "passing2024"
        assert weighted[0] == "about2024"

    def test_weight_one_reproduces_the_unweighted_scores_exactly(self, ledger_con, monkeypatch):
        seeded(ledger_con, citekey="a2024", title="Greenhouse Humidity Control")
        seeded(ledger_con, citekey="b2024", title="Humidity In Passing")
        plant_sidecar("a2024", abstract_records(), docling=False)

        weights(monkeypatch)
        weighted = [(r.citekey, r.score) for r in retrieval.search("humidity")]
        monkeypatch.setattr(
            retrieval_scoring, "weighted_freq", lambda e, t, d: e["term_freqs"].get(t, 0)
        )
        unweighted = [(r.citekey, r.score) for r in retrieval.search("humidity")]
        assert weighted == unweighted


def bm25_as_shipped_before_788(index, terms, k1=1.5, b=0.75):
    doc_count = len(index)
    avgdl = sum(entry["length"] for entry in index.values()) / doc_count
    term_set = set(terms)
    doc_freq = {
        t: sum(1 for entry in index.values() if entry["term_freqs"].get(t)) for t in term_set
    }
    idf = {t: math.log((doc_count - doc_freq[t] + 0.5) / (doc_freq[t] + 0.5) + 1) for t in term_set}
    scores = {}
    for citekey, entry in index.items():
        norm = 1 - b + b * (entry["length"] / avgdl if avgdl else 0)
        score = 0.0
        for t in term_set:
            freq = float(entry["term_freqs"].get(t, 0))
            if freq == 0:
                continue
            score += idf[t] * (freq * (k1 + 1)) / (freq + k1 * norm)
        if score > 0:
            scores[citekey] = score
    return scores


def constants(monkeypatch, k1=1.5, b=0.75):
    monkeypatch.setattr(config, "RETRIEVAL_K1", k1)
    monkeypatch.setattr(config, "RETRIEVAL_B", b)


class TestTheBm25ConstantsComeFromConfig:
    def test_the_shipped_defaults_reproduce_the_pre_788_scores_exactly(self, monkeypatch):
        weights(monkeypatch)
        constants(monkeypatch)
        index = {
            "long2024": {"length": 400, "term_freqs": {"twin": 9, "humidity": 2}},
            "short2024": {"length": 40, "term_freqs": {"twin": 2}},
            "unrelated2024": {"length": 120, "term_freqs": {"soil": 4}},
        }
        assert retrieval_scoring.bm25_scores(index, ["twin", "humidity"]) == (
            bm25_as_shipped_before_788(index, ["twin", "humidity"])
        )

    def test_the_scorer_reads_the_configured_constants_not_its_own(self, monkeypatch):
        weights(monkeypatch)
        index = {
            "long2024": {"length": 400, "term_freqs": {"twin": 9}},
            "short2024": {"length": 40, "term_freqs": {"twin": 2}},
        }
        constants(monkeypatch, k1=0.5, b=0.2)
        assert retrieval_scoring.bm25_scores(index, ["twin"]) == (
            bm25_as_shipped_before_788(index, ["twin"], k1=0.5, b=0.2)
        )

    def test_b_of_zero_scores_a_long_and_a_short_document_the_same(self, monkeypatch):
        weights(monkeypatch)
        index = {
            "long2024": {"length": 4000, "term_freqs": {"twin": 3}},
            "short2024": {"length": 40, "term_freqs": {"twin": 3}},
        }
        constants(monkeypatch, b=0.0)
        scores = retrieval_scoring.bm25_scores(index, ["twin"])
        assert scores["long2024"] == scores["short2024"]

        constants(monkeypatch, b=0.75)
        normalized = retrieval_scoring.bm25_scores(index, ["twin"])
        assert normalized["short2024"] > normalized["long2024"]

    def test_k1_of_zero_scores_presence_and_not_frequency(self, monkeypatch):
        weights(monkeypatch)
        index = {
            "many2024": {"length": 100, "term_freqs": {"twin": 9}},
            "once2024": {"length": 100, "term_freqs": {"twin": 1}},
        }
        constants(monkeypatch, k1=0.0)
        scores = retrieval_scoring.bm25_scores(index, ["twin"])
        assert scores["many2024"] == scores["once2024"]


class TestExtractFrom:
    def test_it_reports_no_abstract_rather_than_unknown(self):
        found = as_passages([{"text": "nothing here", "label": "text", "page": 1}])
        assert _abstract.extract_from(found) is None

    def test_it_finds_the_same_abstract_extract_would(self):
        assert _abstract.extract_from(as_passages()) == ABSTRACT
