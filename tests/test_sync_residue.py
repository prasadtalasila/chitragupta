"""chitragupta/sync_residue.py: what else still names a citekey that
`sync --remove-stale` is about to drop (issue #763).

Report, never repair -- so alongside the counts, these tests assert that
every artefact is byte-identical afterwards.
"""

import json

import pytest

from chitragupta import chroma_paging, overlap_chroma, sync_residue


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_text(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


@pytest.fixture
def residue_corpus(isolated_config):
    """One stale citekey (`smith_gone_2020`) with residue in all five
    artefact classes, and a lookalike (`smith_gone_2020b`) that must
    never be mistaken for it."""
    cfg = isolated_config
    write_text(cfg.OVERLAP_DIR / "docs" / "smith_gone_2020.fpr", "x")
    write_text(cfg.OVERLAP_DIR / "docs" / "smith_gone_2020.skipgram.fpr", "x")
    write_json(cfg.OVERLAP_DIR / "index.json", {"citekeys": ["smith_gone_2020", "kept_2021"]})
    write_json(
        cfg.TOPIC_GRAPH_PATH,
        {
            "edges_overlap": [
                {"shared": ["smith_gone_2020", "kept_2021"]},
                {"shared": ["kept_2021"]},
            ],
            "edges_withheld": [{"shared": ["smith_gone_2020"]}],
            "edges_semantic": [{"bridge": ["kept_2021", "smith_gone_2020"]}],
        },
    )
    # Membership is keyed by citekey in both files, so `smith_gone_2020b`
    # sitting in `uncovered` is the reverse of the prefix trap: scanning
    # the shorter key must not pick the longer one up either.
    write_json(
        cfg.TOPIC_SET_PATH,
        {
            "topics": [
                {
                    "label": "twins",
                    "members": [
                        {"citekey": "smith_gone_2020", "score": 0.9},
                        {"citekey": "kept_2021", "score": 0.8},
                    ],
                },
                {"label": "models", "members": [{"citekey": "smith_gone_2020", "score": 0.7}]},
            ],
            "uncovered": ["smith_gone_2020b"],
        },
    )
    write_json(
        cfg.TOPICS_PATH,
        {
            "assignments": {"smith_gone_2020": 40, "kept_2021": 12},
            "memberships": {"smith_gone_2020": {"40": 0.95}},
        },
    )
    write_text(
        cfg.DOSSIERS_DIR / "dt" / "survey" / "evidence.md",
        "## `smith_gone_2020`\n\nTranscribed evidence.\n\n## `smith_gone_2020b`\n\nOther.\n",
    )
    write_text(
        cfg.DOSSIERS_DIR / "dt" / "survey" / "sections.md",
        "| Section | Citekeys |\n| --- | --- |\n| Intro | @smith_gone_2020 |\n",
    )
    return cfg


class FakeCollection:
    """Stands in for a chroma collection: one `get` that pages."""

    def __init__(self, rows):
        self.rows = rows

    def get(self, where=None, include=None, limit=None, offset=0):
        wanted = set(where["citekey"]["$in"])
        matched = [row for row in self.rows if row["citekey"] in wanted]
        page = matched[offset : offset + limit]
        return {"ids": [f"{row['citekey']}::0" for row in page], "metadatas": page}


def use_fake_chroma(monkeypatch, cfg, rows):
    cfg.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: (object(), object()))
    monkeypatch.setattr(overlap_chroma, "built_collection", lambda _module: FakeCollection(rows))


class TestScan:
    def test_every_artefact_class_is_counted(self, residue_corpus, monkeypatch):
        use_fake_chroma(
            monkeypatch,
            residue_corpus,
            [{"citekey": "smith_gone_2020"}, {"citekey": "smith_gone_2020"}],
        )
        found, notes = sync_residue.scan(["smith_gone_2020"])

        assert notes == []
        counts = {hit.artefact: hit.count for hit in found["smith_gone_2020"]}
        assert counts == {
            sync_residue.OVERLAP: 3,
            sync_residue.TOPIC_GRAPH: 3,
            sync_residue.TOPIC_MEMBERSHIP: 4,
            sync_residue.DOSSIERS: 2,
            sync_residue.CHROMA: 2,
        }

    def test_a_citekey_with_no_residue_is_present_with_an_empty_list(self, residue_corpus):
        found, notes = sync_residue.scan(["never_seen_1999"])
        assert found == {"never_seen_1999": []}
        assert notes == []

    def test_a_longer_citekey_is_not_matched_as_a_prefix(self, residue_corpus):
        # Exact strings only -- upstream's fuzzy matcher was deliberately
        # not copied, so `smith_gone_2020` must not answer for
        # `smith_gone_2020b`, which is a different paper.
        found, _notes = sync_residue.scan(["smith_gone_2020b"])
        hits = {hit.artefact: hit.count for hit in found["smith_gone_2020b"]}
        # The membership hit is its own `uncovered` entry, not the two
        # `smith_gone_2020` memberships sitting beside it.
        assert hits == {sync_residue.TOPIC_MEMBERSHIP: 1, sync_residue.DOSSIERS: 1}

    def test_absent_artefacts_scan_clean(self, isolated_config):
        found, notes = sync_residue.scan(["anything_2000"])
        assert found == {"anything_2000": []}
        assert notes == []

    def test_the_skipgram_index_is_named_as_itself(self, isolated_config):
        # Not as `index.json`: the two tiers are built independently, so
        # reporting the wrong one would send a reader to a path that need
        # not exist at all.
        write_json(isolated_config.OVERLAP_DIR / "skipgram_index.json", {"citekeys": ["only_2001"]})
        found, _notes = sync_residue.scan(["only_2001"])
        assert [hit.where for hit in found["only_2001"]] == [
            (str(isolated_config.OVERLAP_DIR / "skipgram_index.json"),)
        ]

    def test_a_citekey_in_both_indexes_is_counted_twice(self, isolated_config):
        write_json(isolated_config.OVERLAP_DIR / "index.json", {"citekeys": ["both_2004"]})
        write_json(isolated_config.OVERLAP_DIR / "skipgram_index.json", {"citekeys": ["both_2004"]})
        found, _notes = sync_residue.scan(["both_2004"])
        (hit,) = found["both_2004"]
        assert hit.count == 2
        assert hit.where == (
            str(isolated_config.OVERLAP_DIR / "index.json"),
            str(isolated_config.OVERLAP_DIR / "skipgram_index.json"),
        )

    def test_topic_membership_names_each_file_and_its_own_count(self, residue_corpus):
        # Two memberships in topic_set.json (one per topic), and two in
        # topics.json (`assignments` and `memberships` each key by
        # citekey) -- reported per file, the way dossier mentions are.
        found, _notes = sync_residue.scan(["smith_gone_2020"])
        (hit,) = [
            hit for hit in found["smith_gone_2020"] if hit.artefact == sync_residue.TOPIC_MEMBERSHIP
        ]
        assert hit.unit == "membership"
        assert hit.where == (
            f"{residue_corpus.TOPIC_SET_PATH} (2)",
            f"{residue_corpus.TOPICS_PATH} (2)",
        )

    def test_a_citekey_only_in_topics_json_is_still_found(self, isolated_config):
        # topic_set.json need not exist for topics.json to be scanned;
        # the two are written by different stages.
        write_json(isolated_config.TOPICS_PATH, {"assignments": {"lone_2003": 7}})
        found, _notes = sync_residue.scan(["lone_2003"])
        (hit,) = found["lone_2003"]
        assert (hit.artefact, hit.count) == (sync_residue.TOPIC_MEMBERSHIP, 1)
        assert hit.where == (f"{isolated_config.TOPICS_PATH} (1)",)

    def test_a_member_carrying_no_citekey_is_ignored_rather_than_raising(self, isolated_config):
        # A malformed member reports zero, not a KeyError: this module
        # runs immediately before a destructive prompt.
        write_json(
            isolated_config.TOPIC_SET_PATH,
            {"topics": [{"label": "x", "members": [{"score": 0.5}]}]},
        )
        found, notes = sync_residue.scan(["anything_2000"])
        assert (found, notes) == ({"anything_2000": []}, [])

    def test_dossier_mentions_name_the_file_and_the_count(self, residue_corpus):
        found, _notes = sync_residue.scan(["smith_gone_2020"])
        (dossier_hit,) = [
            hit for hit in found["smith_gone_2020"] if hit.artefact == sync_residue.DOSSIERS
        ]
        assert dossier_hit.where == (
            f"{residue_corpus.DOSSIERS_DIR / 'dt' / 'survey' / 'evidence.md'} (1)",
            f"{residue_corpus.DOSSIERS_DIR / 'dt' / 'survey' / 'sections.md'} (1)",
        )


class TestChromaBranches:
    def test_a_missing_chroma_dir_is_silent(self, isolated_config):
        hits, note = sync_residue._scan_chroma(["x_2000"])
        assert (hits, note) == ({}, None)

    def test_an_uninstalled_stack_is_reported_as_unscanned(self, isolated_config, monkeypatch):
        isolated_config.CHROMA_DIR.mkdir(parents=True)
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: None)
        hits, note = sync_residue._scan_chroma(["x_2000"])
        assert hits == {}
        assert "not scanned" in note

    def test_an_unbuilt_collection_is_not_an_unscanned_note(self, isolated_config, monkeypatch):
        isolated_config.CHROMA_DIR.mkdir(parents=True)
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: (object(), object()))
        monkeypatch.setattr(overlap_chroma, "built_collection", lambda _module: None)
        assert sync_residue._scan_chroma(["x_2000"]) == ({}, None)

    def test_a_collection_holding_no_matching_vector_reports_nothing(
        self, isolated_config, monkeypatch
    ):
        use_fake_chroma(monkeypatch, isolated_config, [{"citekey": "other_2002"}])
        hits, note = sync_residue._scan_chroma(["x_2000"])
        assert (hits, note) == ({}, None)

    def test_vectors_are_paged_rather_than_fetched_in_one_call(
        self, isolated_config, monkeypatch, residue_corpus
    ):
        monkeypatch.setattr(chroma_paging, "PAGE_SIZE", 1)
        use_fake_chroma(
            monkeypatch,
            residue_corpus,
            [{"citekey": "smith_gone_2020"} for _ in range(3)],
        )
        hits, _note = sync_residue._scan_chroma(["smith_gone_2020"])
        assert hits["smith_gone_2020"].count == 3


class TestReport:
    def test_nothing_is_printed_when_there_are_no_stale_citekeys(self, isolated_config, capsys):
        sync_residue.report([])
        assert capsys.readouterr().out == ""

    def test_it_groups_by_artefact_and_says_it_repaired_nothing(
        self, residue_corpus, monkeypatch, capsys
    ):
        use_fake_chroma(monkeypatch, residue_corpus, [{"citekey": "smith_gone_2020"}])
        sync_residue.report(["smith_gone_2020"])
        out = capsys.readouterr().out
        assert "still referenced by 5 artefact class(es)" in out
        assert "overlap index    3 file(s):" in out
        assert "topic graph      3 edge(s):" in out
        assert "topic membership 4 membership(s):" in out
        assert "dossiers         2 mention(s):" in out
        assert "chroma vectors   1 vector(s):" in out
        assert "Reported, not repaired" in out

    def test_no_residue_is_said_out_loud(self, residue_corpus, capsys):
        sync_residue.report(["never_seen_1999"])
        out = capsys.readouterr().out
        assert "never_seen_1999: no other artefact references it" in out
        assert "Reported, not repaired" in out

    def test_an_unscanned_class_is_noted(self, isolated_config, monkeypatch, capsys):
        isolated_config.CHROMA_DIR.mkdir(parents=True)
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: None)
        sync_residue.report(["x_2000"])
        assert "NOTE: chroma vectors:" in capsys.readouterr().out

    def test_it_modifies_no_artefact(self, residue_corpus, capsys):
        before = {
            path: path.read_bytes()
            for path in sorted(residue_corpus.CONTENT_DIR.rglob("*"))
            if path.is_file()
        }
        sync_residue.report(["smith_gone_2020"])
        capsys.readouterr()
        after = {
            path: path.read_bytes()
            for path in sorted(residue_corpus.CONTENT_DIR.rglob("*"))
            if path.is_file()
        }
        assert after == before
        assert not residue_corpus.CHROMA_DIR.exists()
