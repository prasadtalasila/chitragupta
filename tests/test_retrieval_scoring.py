"""chitragupta/retrieval_scoring.py: Okapi BM25, and the field weights
that tilt it toward a paper's title and abstract (#762).

The identity property is what most of this file is about. A field weight
of 1.0 must reproduce the unweighted ranking *exactly*, not merely
closely, because that is what lets the weights ship inert and lets every
measurement have a real baseline. It is structural rather than numeric --
`field_deltas` returns nothing when every weight is 1.0, so the weighted
frequency is the plain one by construction -- and the tests below pin it
at both ends: the delta list, and the score.
"""

import json
import math

import pytest

from chitragupta import _abstract, config, ledger, passages, retrieval, retrieval_scoring

from tests.conftest import make_reference

ABSTRACT = (
    "This paper studies greenhouse humidity control in a commercial incubator, and "
    "reports a controller that holds the setpoint within half a degree across a full "
    "growing season. We describe the instrumentation, the calibration procedure and "
    "the two failure modes we observed in the field, and we release the logged data "
    "so that the result can be checked independently by other groups."
)
BODY = "The incubator was installed in a glasshouse and ran unattended for six months.\n"


def parsed_file(text: str, citekey: str = "a2024"):
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PARSED_DIR / f"{citekey}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def corpus_sidecar(records: list[dict], citekey: str = "a2024"):
    """A rung-2 (corpus layer) passage sidecar -- the only rung BM25 reads."""
    path = config.PARSED_DIR / f"{citekey}.passages.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def abstract_records(abstract: str = ABSTRACT):
    return [
        {"text": "An Incubator Study", "label": "title", "page": 1},
        {"text": "Abstract", "label": "section_header", "page": 1},
        {"text": abstract, "label": "text", "page": 1},
        {"text": "1 Introduction", "label": "section_header", "page": 1},
        {"text": BODY.strip(), "label": "text", "page": 1},
    ]


def as_passages(records: "list[dict] | None" = None):
    """`records` as `Passage` objects, the shape the sidecar readers
    return. Built here rather than round-tripped through a file, because
    the tests that use it are about what `_abstract` does with passages,
    not about which rung produced them."""
    return [
        passages.Passage(page=rec["page"], words=set(), text=rec["text"], label=rec["label"])
        for rec in (abstract_records() if records is None else records)
    ]


def seeded(con, citekey="a2024", title="An Incubator Study", text=None):
    path = parsed_file(text if text is not None else f"{ABSTRACT}\n{BODY}", citekey)
    ledger.upsert_reference(con, make_reference(citekey=citekey, title=title))
    ledger.mark_parsed(con, citekey, path)
    return path


def weights(monkeypatch, **overrides):
    """Pin every field's weight, so a test states the whole vector rather
    than inheriting whatever the measured defaults become."""
    pinned = dict.fromkeys(retrieval_scoring.FIELDS, 1.0)
    pinned.update(overrides)
    monkeypatch.setattr(config, "RETRIEVAL_FIELD_WEIGHTS", pinned)


class TestTheFieldListDrivesTheSeam:
    def test_every_field_has_a_configured_weight(self):
        """A field with no weight would raise in `field_deltas`, so this
        is what says the two lists are one list. Issue #770 asked for two
        more and got neither: `caption` has no sidecar label to read and
        `table` measured a loss on both ground truths."""
        assert set(config.RETRIEVAL_FIELD_WEIGHTS) == set(retrieval_scoring.FIELDS)

    def test_title_and_abstract_are_the_fields_that_ship(self):
        assert retrieval_scoring.FIELDS == ("title", "abstract")


class TestDefaultsShipInert:
    def test_every_weight_defaults_to_one(self):
        """The measured default is 1.0 until a sweep says otherwise --
        see docs/RETRIEVAL.md. Shipping any other number without the
        figures behind it is the thing #762 exists to avoid."""
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
        """tf~ = tf_full + (w - 1) * tf_field. The title's 2 occurrences
        are already inside the full count of 7, so a weight of 3 adds
        them twice more rather than replacing anything."""
        weights(monkeypatch, title=3.0)
        entry = {"term_freqs": {"twin": 7}, "field_freqs": {"title": {"twin": 2}}}
        got = retrieval_scoring.weighted_freq(entry, "twin", retrieval_scoring.field_deltas())
        assert got == pytest.approx(7 + 2 * 2)

    def test_an_entry_with_no_field_freqs_scores_unweighted(self, monkeypatch):
        """`chitragupta/discover/_resolve.py` builds synthetic index
        entries by hand, with `term_freqs` and `length` and nothing else.
        They must keep ranking exactly as they do today whatever the
        weights say, or turning a weight up silently re-ranks the topic
        resolver too."""
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
        """A field's count comes from the passage sidecar and the full
        count from the flattened `.txt`, and the two normalize whitespace
        and hyphenation differently -- so a field can, for one term,
        count more than the whole document does. Below a weight of 1 that
        makes tf~ negative, which BM25 has no meaning for: the saturation
        curve would return a negative contribution and a document would
        be pushed *below* one that does not contain the term at all."""
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
        corpus_sidecar(abstract_records())
        row = ledger.all_items(ledger_con)[0]
        assert retrieval_scoring.field_texts(row)["abstract"] == ABSTRACT

    def test_no_sidecar_means_no_abstract_field(self, ledger_con):
        """The `pdftotext` backend writes no passage sidecar, and it is
        the shipped default. The abstract weight is then inert rather
        than an error -- there is nothing to weight, which is a fact
        about the parse and not a failure."""
        seeded(ledger_con)
        row = ledger.all_items(ledger_con)[0]
        assert "abstract" not in retrieval_scoring.field_texts(row)

    def test_a_sidecar_with_no_detectable_abstract_yields_no_field(self, ledger_con):
        seeded(ledger_con)
        corpus_sidecar([{"text": BODY.strip(), "label": "text", "page": 1}])
        row = ledger.all_items(ledger_con)[0]
        assert "abstract" not in retrieval_scoring.field_texts(row)

    def test_the_enrichment_sidecar_is_not_read(self, ledger_con, monkeypatch):
        """chitragupta/retrieval.py promises that running the enrichment
        layer's Docling stage does not change what BM25 ranks. Rung 1 is
        that layer's sidecar, and `passages.structural_passages` prefers
        it -- so reading the abstract through the ordinary ladder would
        break the promise, and `retrieval_cache._fingerprint` would not
        notice, because nothing in it stats a file the corpus layer never
        writes. #772 proposes reversing this deliberately; until then the
        rung-2 read is the contract.

        Rung 1 is simulated by patching `structural_passages` rather than
        by writing `content/docling/`, so the test fails loudly if the
        implementation ever reaches for the ladder -- writing the file
        would leave it passing for a reader who also happened to have no
        enrichment run on disk."""
        seeded(ledger_con)
        monkeypatch.setattr(passages, "structural_passages", lambda citekey: as_passages())
        row = ledger.all_items(ledger_con)[0]
        assert "abstract" not in retrieval_scoring.field_texts(row)


class TestFieldFreqs:
    def test_a_field_whose_text_tokenizes_to_nothing_is_omitted(self, ledger_con):
        """A title of only stopwords and short words leaves no tokens.
        The field is then absent rather than present-and-empty, so
        `weighted_freq` adds nothing for it -- the same shape as a paper
        with no abstract, and one case rather than two."""
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
        """What the clamp above defends against, asserted on real text
        rather than a hand-built entry: the title's tokens are part of
        `_full_text`, so every field count sits inside the full count."""
        seeded(ledger_con, title="Greenhouse Humidity In A Greenhouse")
        corpus_sidecar(abstract_records())
        row = ledger.all_items(ledger_con)[0]
        entry = retrieval._tokenize_item(row)

        for counts in entry["field_freqs"].values():
            for term, count in counts.items():
                assert count <= entry["term_freqs"].get(term, 0)


class TestBm25ScoresAreUnchangedAtWeightOne:
    def test_the_ranking_is_identical_with_and_without_field_freqs(self, monkeypatch):
        """The baseline every measurement in docs/RETRIEVAL.md is read
        against. Two indexes over the same term frequencies, one carrying
        field counts and one not, must score bit-identically at 1.0."""
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
        """#762's own user story, end to end. `passing2024` says
        "greenhouse humidity" twelve times in its body and is not about
        it; `about2024` says it once, in its title. Unweighted, the
        passing mention wins on sheer term frequency -- which is the
        defect. The flip, not merely the weighted order, is the
        assertion: asserting only the second half would stay green if
        the fixture stopped exercising the defect at all."""
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
        """Not `approx`: the identity has to be exact, or every figure in
        docs/RETRIEVAL.md is read against a baseline that drifted."""
        seeded(ledger_con, citekey="a2024", title="Greenhouse Humidity Control")
        seeded(ledger_con, citekey="b2024", title="Humidity In Passing")
        corpus_sidecar(abstract_records(), citekey="a2024")

        weights(monkeypatch)
        weighted = [(r.citekey, r.score) for r in retrieval.search("humidity")]
        # The pre-#762 scorer, reproduced by removing the field seam
        # itself rather than by setting its weights to 1.0 -- so this
        # compares against code that never reads `field_freqs`, which is
        # what "reproduces current ranking" actually claims.
        monkeypatch.setattr(
            retrieval_scoring, "weighted_freq", lambda e, t, d: e["term_freqs"].get(t, 0)
        )
        unweighted = [(r.citekey, r.score) for r in retrieval.search("humidity")]
        assert weighted == unweighted


def bm25_as_shipped_before_788(index, terms, k1=1.5, b=0.75):
    """Okapi BM25 with the constants written in, as #788 found them.

    A second implementation rather than a call with the defaults pinned,
    for the reason `test_weight_one_reproduces_the_unweighted_scores_exactly`
    gives about the field seam: comparing `bm25_scores` against itself
    proves determinism, not that the shipped defaults reproduce the
    ranking the module had before the constants became configurable.
    This is that ranking, transcribed from the pre-#788 source.
    """
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
    """Pin both BM25 constants, so a test states the whole pair rather
    than inheriting whatever the measured defaults become -- the same
    reason `weights` above pins every field."""
    monkeypatch.setattr(config, "RETRIEVAL_K1", k1)
    monkeypatch.setattr(config, "RETRIEVAL_B", b)


class TestTheBm25ConstantsComeFromConfig:
    def test_the_shipped_defaults_reproduce_the_pre_788_scores_exactly(self, monkeypatch):
        """#788's own success criterion. Not `approx`: 1.5 and 0.75 have
        to be the ranking this module had when they were module
        constants, or the sweep in bench/RESULTS.md has no baseline."""
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
        """Read at call time, like `field_deltas` reads the weights --
        which is what lets bench/bench_retrieval_bm25_params.py sweep a
        grid in one process, and what would silently stop working if the
        pair were bound at import."""
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
        """`b = 0` is "do not normalize by length at all", the bottom of
        #788's `b` sweep. Two documents with the same term count and very
        different lengths must then tie exactly -- which is the property
        the sweep's `b` arm is moving, stated as behaviour rather than as
        a number."""
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
        """`k1 = 0` saturates immediately: `freq * (k1+1) / (freq + 0)`
        is 1 for every non-zero frequency, so nine mentions and one
        mention score identically. The top of the curve the `k1` arm
        sweeps, pinned as behaviour."""
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
        """`UNKNOWN` distinguishes "no sidecar" from "no abstract", and
        only `extract` can be in the first case -- `extract_from` has the
        passages by construction. Pushing the sentinel down would make
        every caller handle three cases where two will do."""
        found = as_passages([{"text": "nothing here", "label": "text", "page": 1}])
        assert _abstract.extract_from(found) is None

    def test_it_finds_the_same_abstract_extract_would(self):
        assert _abstract.extract_from(as_passages()) == ABSTRACT
