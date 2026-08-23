"""chitragupta/enrich/topic_converge.py: the join of the two topic answers.

The property under test throughout: **the human's name wins**. An
emergent topic close enough to a phrase the author wrote is renamed by
it, not listed beside it -- which is what "seeds are a starting point"
has to mean once it reaches an artefact.
"""

import json

import pytest

from chitragupta import config
from chitragupta.enrich import topic_converge


class TestConverge:
    def test_a_close_topic_takes_the_seed_phrase(self, isolated_config):
        named = topic_converge.converge(
            {0: [1.0, 0.0]}, {"digital twin": [1.0, 0.05]}, min_similarity=0.4
        )
        assert named == {0: "digital twin"}

    def test_a_distant_topic_keeps_its_own_identity(self, isolated_config):
        assert (
            topic_converge.converge(
                {0: [1.0, 0.0]}, {"digital twin": [0.0, 1.0]}, min_similarity=0.4
            )
            == {}
        )

    def test_the_closest_of_several_seeds_wins(self, isolated_config):
        named = topic_converge.converge(
            {0: [1.0, 0.0]}, {"far": [1.0, 0.9], "near": [1.0, 0.05]}, min_similarity=0.4
        )
        assert named == {0: "near"}

    def test_a_tie_breaks_on_the_phrase_so_runs_are_diffable(self, isolated_config):
        """Two seeds equidistant from one cluster would otherwise resolve
        by dict order, and a topic set whose names shuffle between runs is
        one nobody can diff."""
        forward = topic_converge.converge(
            {0: [1.0, 0.0]}, {"alpha": [1.0, 0.0], "zulu": [1.0, 0.0]}, min_similarity=0.4
        )
        reverse = topic_converge.converge(
            {0: [1.0, 0.0]}, {"zulu": [1.0, 0.0], "alpha": [1.0, 0.0]}, min_similarity=0.4
        )
        # Which of the two wins is arbitrary; that both input orders agree
        # is the property. Sorting ascending on the phrase makes it "alpha".
        assert forward == reverse == {0: "alpha"}

    def test_a_phrase_names_only_its_closest_topic(self, isolated_config):
        """Built the other way first, and the real corpus refuted it: on a
        digital-twins corpus, letting every close cluster take the phrase
        produced eight topics called `digital twin` and three called `dt
        architecture` -- nineteen seed-named topics from nine phrases,
        none distinguishable from its namesakes. A label that does not
        distinguish is not a label."""
        named = topic_converge.converge(
            {0: [1.0, 0.0], 1: [1.0, 0.3]}, {"platform": [1.0, 0.05]}, min_similarity=0.4
        )
        assert named == {0: "platform"}

    def test_the_losing_topic_keeps_its_own_identity(self, isolated_config):
        """Not lost, just not renamed: it stays emergent with its derived
        label and its own members."""
        named = topic_converge.converge(
            {0: [1.0, 0.0], 1: [1.0, 0.3]}, {"platform": [1.0, 0.05]}, min_similarity=0.4
        )
        assert 1 not in named

    def test_two_phrases_can_name_two_topics(self, isolated_config):
        """One phrase per topic is a pairing, not a cap of one overall."""
        named = topic_converge.converge(
            {0: [1.0, 0.0], 1: [0.0, 1.0]},
            {"alpha": [1.0, 0.05], "beta": [0.05, 1.0]},
            min_similarity=0.4,
        )
        assert named == {0: "alpha", 1: "beta"}

    def test_the_threshold_defaults_to_config(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "TOPIC_CONVERGE_SIMILARITY", 0.99)
        assert topic_converge.converge({0: [1.0, 0.3]}, {"x": [1.0, 0.0]}) == {}


MEMBERSHIPS = {"a_2020": {"0": 0.8, "1": 0.5}, "b_2021": {"0": 0.6}, "c_2022": {"1": 0.7}}
CITEKEYS = ["a_2020", "b_2021", "c_2022", "d_2023"]


class TestBuild:
    def test_a_named_topic_carries_the_phrase_and_its_provenance(self, isolated_config):
        got = topic_converge.build(MEMBERSHIPS, CITEKEYS, {0: "digital twin"}, {"topics": []})
        named = [t for t in got["topics"] if t["topic_id"] == 0][0]
        assert named["label"] == "digital twin"
        assert named["provenance"] == "seed"

    def test_an_unnamed_topic_keeps_a_derived_label(self, isolated_config):
        got = topic_converge.build(MEMBERSHIPS, CITEKEYS, {}, {"topics": []})
        assert {t["label"] for t in got["topics"]} == {"topic-0", "topic-1"}
        assert all(t["provenance"] == "emergent" for t in got["topics"])

    def test_a_paper_appears_under_every_topic_it_is_about(self, isolated_config):
        """The many-to-many view, not the single assignment -- which is
        the whole reason `memberships` exists."""
        got = topic_converge.build(MEMBERSHIPS, CITEKEYS, {}, {"topics": []})
        under = {t["topic_id"]: [m["citekey"] for m in t["members"]] for t in got["topics"]}
        assert under[0] == ["a_2020", "b_2021"]
        assert "a_2020" in under[1]

    def test_members_are_ranked_best_first(self, isolated_config):
        got = topic_converge.build(MEMBERSHIPS, CITEKEYS, {}, {"topics": []})
        under_zero = [t for t in got["topics"] if t["topic_id"] == 0][0]
        assert [m["score"] for m in under_zero["members"]] == [0.8, 0.6]
        assert [m["citekey"] for m in under_zero["members"]] == ["a_2020", "b_2021"]

    def test_a_seed_that_named_nothing_still_appears(self, isolated_config):
        """The useful case, not a leftover: the author named something the
        clustering did not separate out, and an empty topic_id is the
        signal that the corpus does not organise the way they assumed."""
        report = {
            "topics": [{"phrase": "fidelity", "matches": [{"citekey": "d_2023", "score": 0.5}]}]
        }
        got = topic_converge.build(MEMBERSHIPS, CITEKEYS, {}, report)
        orphan = [t for t in got["topics"] if t["label"] == "fidelity"][0]
        assert orphan["topic_id"] is None
        assert orphan["provenance"] == "seed"

    def test_a_seed_that_named_a_topic_is_not_listed_twice(self, isolated_config):
        report = {"topics": [{"phrase": "digital twin", "matches": []}]}
        got = topic_converge.build(MEMBERSHIPS, CITEKEYS, {0: "digital twin"}, report)
        assert sum(1 for t in got["topics"] if t["label"] == "digital twin") == 1

    def test_uncovered_names_the_papers_no_topic_reached(self, isolated_config):
        """The one number an author planning a draft actually wants."""
        got = topic_converge.build(MEMBERSHIPS, CITEKEYS, {}, {"topics": []})
        assert got["uncovered"] == ["d_2023"]

    def test_the_counts_distinguish_named_from_discovered(self, isolated_config):
        got = topic_converge.build(MEMBERSHIPS, CITEKEYS, {0: "digital twin"}, {"topics": []})
        assert got["n_seed_named"] == 1
        assert got["n_emergent"] == 1


class TestRunStage:
    def test_it_refuses_to_cluster_on_your_behalf(self, isolated_config):
        """This stage's contract is that it re-runs nothing. A stage that
        silently did an hour of GPU work would be a different stage
        wearing this one's name."""
        with pytest.raises(ValueError, match="Run the bertopic stage first"):
            topic_converge.run_topic_converge([], ())

    def test_the_stage_wrapper_skips_rather_than_failing(self, isolated_config):
        """A `--stages converge` before bertopic is a sequencing mistake,
        not a broken corpus."""
        result = topic_converge.run_stage([], ())
        assert result["status"] == "skipped"
        assert "bertopic first" in result["detail"]["reason"]

    def test_the_stage_reports_both_kinds_of_topic(self, isolated_config, monkeypatch):
        isolated_config.TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.TOPICS_PATH.write_text(json.dumps({"assignments": {}}), encoding="utf-8")
        monkeypatch.setattr(
            topic_converge,
            "run_topic_converge",
            lambda docs, phrases: {
                "n_docs": 3,
                "n_seed_named": 1,
                "n_emergent": 2,
                "uncovered": ["x"],
            },
        )
        detail = topic_converge.run_stage([], ())["detail"]
        assert detail == {"n_docs": 3, "seed_named": 1, "emergent": 2, "uncovered": 1}


class FakeModel:
    """Encodes each phrase to the vector `VECTORS` names for it, so a test
    can place a seed at a chosen angle to a cluster."""

    VECTORS: dict = {}

    def encode(self, texts, show_progress_bar=False):
        import numpy as np

        return np.array([FakeModel.VECTORS[text] for text in texts])


class TestRunTopicConverge:
    """The whole join, driven through fakes: it must read the artefacts
    the earlier stages wrote and cluster nothing itself."""

    def prepare(self, cfg, monkeypatch, assignments, memberships, vectors):
        from chitragupta import seed_topics as seed_topics_module
        from chitragupta.enrich import doc_vectors, embed_index

        cfg.TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg.TOPICS_PATH.write_text(
            json.dumps({"assignments": assignments, "memberships": memberships}), encoding="utf-8"
        )
        monkeypatch.setattr(
            doc_vectors, "corpus_texts", lambda docs: {c: "text" for c in assignments}
        )
        monkeypatch.setattr(doc_vectors, "document_embeddings", lambda texts, model: vectors)
        monkeypatch.setattr(embed_index, "get_client_and_model", lambda: (None, FakeModel()))
        monkeypatch.setattr(seed_topics_module, "load_report", lambda: {"topics": []})

    def test_a_seed_renames_the_cluster_it_matches(self, isolated_config, monkeypatch):
        FakeModel.VECTORS = {"digital twin": [1.0, 0.0, 0.0]}
        self.prepare(
            isolated_config,
            monkeypatch,
            assignments={"a": 0, "b": 0, "c": 1, "d": 1},
            memberships={"a": {"0": 0.9}, "b": {"0": 0.8}, "c": {"1": 0.9}, "d": {"1": 0.8}},
            vectors={
                "a": [1.0, 0.0, 0.0],
                "b": [1.0, 0.1, 0.0],
                "c": [0.0, 0.0, 1.0],
                "d": [0.0, 0.1, 1.0],
            },
        )
        result = topic_converge.run_topic_converge([], ("digital twin",))
        labels = {t["label"] for t in result["topics"]}
        assert "digital twin" in labels
        assert result["n_seed_named"] == 1

    def test_it_writes_the_artefact(self, isolated_config, monkeypatch):
        FakeModel.VECTORS = {"digital twin": [1.0, 0.0, 0.0]}
        self.prepare(
            isolated_config,
            monkeypatch,
            assignments={"a": 0, "b": 0, "c": 1, "d": 1},
            memberships={"a": {"0": 0.9}, "b": {"0": 0.8}, "c": {"1": 0.9}, "d": {"1": 0.8}},
            vectors={
                "a": [1.0, 0.0, 0.0],
                "b": [1.0, 0.1, 0.0],
                "c": [0.0, 0.0, 1.0],
                "d": [0.0, 0.1, 1.0],
            },
        )
        result = topic_converge.run_topic_converge([], ("digital twin",))
        assert isolated_config.TOPIC_SET_PATH.exists()
        assert json.loads(isolated_config.TOPIC_SET_PATH.read_text(encoding="utf-8")) == result

    def test_with_no_seeds_every_topic_stays_emergent(self, isolated_config, monkeypatch):
        self.prepare(
            isolated_config,
            monkeypatch,
            assignments={"a": 0, "b": 0, "c": 1, "d": 1},
            memberships={"a": {"0": 0.9}, "b": {"0": 0.8}, "c": {"1": 0.9}, "d": {"1": 0.8}},
            vectors={
                "a": [1.0, 0.0, 0.0],
                "b": [1.0, 0.1, 0.0],
                "c": [0.0, 0.0, 1.0],
                "d": [0.0, 0.1, 1.0],
            },
        )
        result = topic_converge.run_topic_converge([], ())
        assert result["n_seed_named"] == 0
        assert result["n_emergent"] == 2
