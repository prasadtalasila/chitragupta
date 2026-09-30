"""chitragupta/_json_cache.py: the memoised, versioned JSON file both
retrieval caches keep their per-item stats in (#851).

The retrieval-specific halves -- what an item's fingerprint is, and how
an entry is rebuilt -- stay in `retrieval_cache.py` and
`retrieval_passages_cache.py` and are tested there. This file pins the
shared plumbing: the per-process memo, its stamp, the version check and
the atomic write.
"""

import json

from chitragupta._json_cache import MemoisedJson


def a_cache(tmp_path, version=1, name="index.json"):
    path = tmp_path / name
    return MemoisedJson(lambda: path, version), path


class TestLoad:
    def test_an_absent_file_is_an_empty_index(self, tmp_path):
        cache, _path = a_cache(tmp_path)
        assert cache.load() == {}

    def test_a_file_from_another_schema_version_is_ignored(self, tmp_path):
        cache, path = a_cache(tmp_path, version=2)
        path.write_text(json.dumps({"version": 1, "items": {"a": 1}}), encoding="utf-8")
        assert cache.load() == {}

    def test_unreadable_json_is_an_empty_index_not_a_crash(self, tmp_path):
        cache, path = a_cache(tmp_path)
        path.write_text("{not json", encoding="utf-8")
        assert cache.load() == {}

    def test_a_payload_whose_items_are_not_a_mapping_is_ignored(self, tmp_path):
        cache, path = a_cache(tmp_path)
        path.write_text(json.dumps({"version": 1, "items": ["a"]}), encoding="utf-8")
        assert cache.load() == {}

    def test_a_payload_that_is_not_an_object_is_ignored(self, tmp_path):
        cache, path = a_cache(tmp_path)
        path.write_text(json.dumps(["a"]), encoding="utf-8")
        assert cache.load() == {}


class TestTheMemo:
    def test_a_second_load_does_not_reread_the_file(self, tmp_path, monkeypatch):
        cache, _path = a_cache(tmp_path)
        cache.save({"a": 1})
        reads = []
        real = cache.read_file
        monkeypatch.setattr(cache, "read_file", lambda: reads.append(1) or real())
        cache.load()
        cache.load()
        assert reads == []

    def test_a_save_is_seen_by_the_next_load(self, tmp_path):
        cache, _path = a_cache(tmp_path)
        cache.save({"a": 1})
        assert cache.load() == {"a": 1}
        cache.save({"b": 2})
        assert cache.load() == {"b": 2}

    def test_a_rewrite_behind_its_back_is_picked_up_after_forget(self, tmp_path):
        cache, path = a_cache(tmp_path)
        cache.save({"a": 1})
        path.write_text(json.dumps({"version": 1, "items": {"c": 3}}), encoding="utf-8")
        cache.forget()
        assert cache.load() == {"c": 3}

    def test_the_path_is_part_of_the_stamp(self, tmp_path):
        """A path getter, not a path: the retrieval caches' paths are
        `config` attributes that move between test trees, and a memo
        keyed on size and mtime alone could carry one tree's index into
        another's."""
        where = {"path": tmp_path / "one.json"}
        cache = MemoisedJson(lambda: where["path"], 1)
        cache.save({"a": 1})
        first = cache.stamp()
        where["path"] = tmp_path / "two.json"
        assert cache.stamp() != first
        assert cache.load() == {}


class TestSave:
    def test_it_writes_the_version_and_creates_the_directory(self, tmp_path):
        cache, path = a_cache(tmp_path / "deeper", version=7)
        cache.save({"a": 1})
        assert json.loads(path.read_text(encoding="utf-8")) == {"version": 7, "items": {"a": 1}}

    def test_no_temp_file_is_left_behind(self, tmp_path):
        cache, path = a_cache(tmp_path)
        cache.save({"a": 1})
        assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]
