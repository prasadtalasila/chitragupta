"""chitragupta/enrich/doc_vectors.py's on-disk topic-embed cache.

Scoped to the #504 (M-24) fix -- degrading cleanly on a torn or
unreadable cache file -- rather than the whole module, which the rest
of the enrichment suite (test_enrich_topic_model.py,
test_enrich_topic_seeding.py) already exercises indirectly through
document_embeddings().
"""

import os

from chitragupta.enrich import doc_vectors


class TestLoadEmbedCacheDegradesCleanly:
    def test_missing_cache_file_is_empty(self, isolated_config):
        assert doc_vectors._load_embed_cache() == {}

    def test_corrupt_json_is_treated_as_empty(self, isolated_config):
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        isolated_config.TOPIC_EMBED_CACHE_PATH.write_text("{not valid json", encoding="utf-8")
        assert doc_vectors._load_embed_cache() == {}

    def test_non_dict_top_level_is_treated_as_empty(self, isolated_config):
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        isolated_config.TOPIC_EMBED_CACHE_PATH.write_text("[1, 2, 3]", encoding="utf-8")
        assert doc_vectors._load_embed_cache() == {}

    def test_a_valid_cache_round_trips(self, isolated_config):
        cache = {"a2024": {"hash": "x", "model": "m", "method": "v", "embedding": [1.0]}}
        doc_vectors._save_embed_cache(cache)
        assert doc_vectors._load_embed_cache() == cache


class TestSaveEmbedCacheIsAtomic:
    def test_no_tmp_file_survives_a_successful_save(self, isolated_config):
        doc_vectors._save_embed_cache({"a2024": {"hash": "x"}})
        leftovers = list(isolated_config.CONTENT_DIR.glob("*.tmp"))
        assert leftovers == []

    def test_a_write_that_dies_mid_save_leaves_the_previous_cache_intact(
        self, isolated_config, monkeypatch
    ):
        doc_vectors._save_embed_cache({"a2024": {"hash": "old"}})

        def dying_replace(*a, **kw):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", dying_replace)
        try:
            doc_vectors._save_embed_cache({"a2024": {"hash": "new"}})
        except OSError:
            pass

        assert doc_vectors._load_embed_cache() == {"a2024": {"hash": "old"}}
