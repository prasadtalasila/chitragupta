"""chitragupta/enrich/keyword_extract.py: each paper's own declared
Keywords:/Index Terms line, extracted into content/keywords.toml.

Pure text processing throughout -- no model, no fake embeddings. The
constants asserted here (a 200-line detection window, a 300-character
line truncation, a 60-character phrase cap) are not invented by the
tests: bench/RESULTS.md's 2026-09-03c entry measured them on this
project's own corpus, and plans/604-declared-keyword-seeding.md carries
them as the contract.
"""

import tomllib

import pytest

from chitragupta import seed_topics
from chitragupta.enrich import keyword_extract
from chitragupta.enrich.corpus import CorpusDoc


def make_docs(tmp_path, texts: dict):
    docs = []
    for citekey, text in texts.items():
        path = tmp_path / f"{citekey}.txt"
        path.write_text(text, encoding="utf-8")
        docs.append(CorpusDoc(citekey=citekey, title=citekey, pdf_path=None, text_path=str(path)))
    return docs


class TestDeclaredPhrases:
    def test_comma_separated_keywords_line(self):
        text = "Title\n\nAbstract prose.\nKeywords: Digital Twin, Predictive Maintenance\nBody."
        assert keyword_extract.declared_phrases(text) == (
            "digital twin",
            "predictive maintenance",
        )

    def test_index_terms_marker_with_ieee_em_dash(self):
        text = "Index Terms—Federated Learning, Edge Computing\n"
        assert keyword_extract.declared_phrases(text) == ("federated learning", "edge computing")

    def test_middle_dot_beats_comma_when_both_present(self):
        """Separator priority is the line's own, best first: a middle dot
        is only ever a deliberate separator, while a comma can sit inside
        one phrase ('modeling, simulation and control')."""
        text = "Keywords: modeling, simulation · digital twin\n"
        assert keyword_extract.declared_phrases(text) == ("modeling, simulation", "digital twin")

    def test_pipe_and_semicolon_separators(self):
        assert keyword_extract.declared_phrases("Keywords: a | b\n") == ("a", "b")
        assert keyword_extract.declared_phrases("Keywords: a; b\n") == ("a", "b")

    def test_fallback_splits_at_lower_to_upper_word_boundary(self):
        """No separator at all -- Docling flattened the punctuation out.
        The fallback is lossy by design: 'Digital Twin' splits apart,
        which bench/RESULTS.md 2026-09-03c measured and accepted rather
        than silently dropping 27% of detected declarations."""
        text = "Keywords: Digital Twin Internet of Things\n"
        assert keyword_extract.declared_phrases(text) == (
            "digital",
            "twin",
            "internet of",
            "things",
        )

    def test_markdown_decoration_around_the_marker(self):
        text = "## **Keywords:** cloud computing, fog computing\n"
        assert keyword_extract.declared_phrases(text) == ("cloud computing", "fog computing")

    def test_marker_must_open_the_line(self):
        text = "The keywords: digital twin, iot\nwere chosen by the authors.\n"
        assert keyword_extract.declared_phrases(text) == ()

    def test_no_declaration_returns_empty(self):
        assert keyword_extract.declared_phrases("Title\n\nJust prose.\n") == ()

    def test_declaration_past_the_window_is_ignored(self):
        """A References entry titled 'Keywords in ...' sits far down the
        document; the 200-line window is what keeps it out."""
        text = "\n" * 200 + "Keywords: digital twin\n"
        assert keyword_extract.declared_phrases(text) == ()

    def test_declaration_on_the_window_boundary_is_found(self):
        text = "\n" * 199 + "Keywords: digital twin\n"
        assert keyword_extract.declared_phrases(text) == ("digital twin",)

    def test_first_declaration_wins(self):
        text = "Keywords: first\nKeywords: second\n"
        assert keyword_extract.declared_phrases(text) == ("first",)

    def test_line_truncated_before_splitting(self):
        """Docling occasionally flattens a whole PDF column -- the
        declaration, affiliations, the abstract -- into one line. Only
        the first 300 characters after the marker are split."""
        text = "Keywords: aaa, bbb, " + "c" * 300 + ", ddd\n"
        phrases = keyword_extract.declared_phrases(text)
        assert phrases[:2] == ("aaa", "bbb")
        assert "ddd" not in phrases

    def test_overlong_phrase_is_dropped(self):
        long_phrase = "x" * 61
        text = f"Keywords: short, {long_phrase}\n"
        assert keyword_extract.declared_phrases(text) == ("short",)

    def test_phrases_are_lowercased_and_whitespace_collapsed(self):
        text = "Keywords: Digital   Twin (DT); INDUSTRY 4.0\n"
        assert keyword_extract.declared_phrases(text) == ("digital twin (dt)", "industry 4.0")

    def test_empty_fragments_are_dropped(self):
        text = "Keywords: a,, b, \n"
        assert keyword_extract.declared_phrases(text) == ("a", "b")

    def test_marker_with_no_payload_yields_nothing(self):
        assert keyword_extract.declared_phrases("Keywords:\nBody.\n") == ()


class TestAggregate:
    def test_min_df_drops_single_document_phrases(self):
        per_doc = {"a": ("shared", "only-a"), "b": ("shared", "only-b")}
        assert keyword_extract.aggregate(per_doc, min_df=2, top_n=40) == ["shared"]

    def test_counts_distinct_documents_not_occurrences(self):
        """One paper repeating a phrase never inflates it: 'twice' appears
        twice in one document and once in another (2 docs), while 'both'
        appears once in each of two documents (also 2) -- with top_n=1 the
        alphabetical tie-break proves neither outranked the other."""
        per_doc = {"a": ("twice", "twice", "both"), "b": ("twice", "both")}
        assert keyword_extract.aggregate(per_doc, min_df=2, top_n=1) == ["both"]

    def test_top_n_keeps_most_declared_phrases(self):
        per_doc = {
            "a": ("popular", "rare"),
            "b": ("popular", "rare"),
            "c": ("popular",),
        }
        assert keyword_extract.aggregate(per_doc, min_df=2, top_n=1) == ["popular"]

    def test_result_is_sorted_alphabetically(self):
        """Rank decides membership; the artifact itself is read by a
        person, so it is written in the order a person scans."""
        per_doc = {"a": ("zeta", "alpha"), "b": ("zeta", "alpha")}
        assert keyword_extract.aggregate(per_doc, min_df=2, top_n=40) == ["alpha", "zeta"]


class TestRunStage:
    def test_writes_keywords_toml_that_seed_topics_load_reads(self, isolated_config, tmp_path):
        docs = make_docs(
            tmp_path,
            {
                "a": "Keywords: digital twin, edge computing\n",
                "b": "Index Terms—digital twin\n",
            },
        )
        result = keyword_extract.run_stage(docs)
        assert result["status"] == "ok"
        # min_df=2 (the pinned default): only the phrase both papers
        # declared survives.
        assert seed_topics.load(isolated_config.KEYWORDS_PATH) == ("digital twin",)

    def test_detail_counts_documents_and_declarations(self, isolated_config, tmp_path):
        docs = make_docs(
            tmp_path,
            {
                "a": "Keywords: digital twin\n",
                "b": "Keywords: digital twin\n",
                "c": "No declaration here.\n",
            },
        )
        result = keyword_extract.run_stage(docs)
        assert result["detail"] == {
            "documents": 3,
            "with_declaration": 2,
            "phrases": 1,
            "path": str(isolated_config.KEYWORDS_PATH),
        }

    def test_no_declarations_is_ok_and_writes_an_empty_list(self, isolated_config, tmp_path):
        """Half this project's own corpus declares nothing; that is the
        ordinary state, not an error, and the artifact says so rather
        than going stale from a previous run."""
        docs = make_docs(tmp_path, {"a": "Just prose.\n"})
        result = keyword_extract.run_stage(docs)
        assert result["status"] == "ok"
        assert result["detail"]["with_declaration"] == 0
        with open(isolated_config.KEYWORDS_PATH, "rb") as handle:
            assert tomllib.load(handle) == {"topics": []}

    def test_regenerates_fresh_over_a_previous_run(self, isolated_config, tmp_path):
        """A generated artifact, not a curated one: whatever a previous
        run (or a misguided hand-edit) left there is replaced whole."""
        isolated_config.KEYWORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.KEYWORDS_PATH.write_text('topics = ["stale phrase"]', encoding="utf-8")
        docs = make_docs(
            tmp_path,
            {"a": "Keywords: fresh phrase\n", "b": "Keywords: fresh phrase\n"},
        )
        keyword_extract.run_stage(docs)
        assert seed_topics.load(isolated_config.KEYWORDS_PATH) == ("fresh phrase",)

    def test_skipped_when_no_document_has_text(self, isolated_config):
        docs = [CorpusDoc(citekey="a", title="a", pdf_path=None, text_path=None)]
        result = keyword_extract.run_stage(docs)
        assert result["status"] == "skipped"
        assert "no parsed document" in result["detail"]["reason"]
        assert not isolated_config.KEYWORDS_PATH.exists()

    def test_generated_header_names_the_promotion_path(self, isolated_config, tmp_path):
        """The file must tell its reader it is machine output -- the
        header is the one place a person about to hand-curate it will
        actually look."""
        docs = make_docs(tmp_path, {"a": "Keywords: iot\n", "b": "Keywords: iot\n"})
        keyword_extract.run_stage(docs)
        header = isolated_config.KEYWORDS_PATH.read_text(encoding="utf-8")
        assert header.startswith("#")
        assert "seed_topics.toml" in header

    def test_a_phrase_with_a_quote_survives_the_toml_round_trip(self, isolated_config, tmp_path):
        text = 'Keywords: so-called "smart" grid\n'
        docs = make_docs(tmp_path, {"a": text, "b": text})
        keyword_extract.run_stage(docs)
        assert seed_topics.load(isolated_config.KEYWORDS_PATH) == ('so-called "smart" grid',)

    def test_config_top_n_and_min_df_are_read(self, isolated_config, tmp_path, monkeypatch):
        monkeypatch.setattr(isolated_config, "KEYWORD_MIN_DF", 1)
        monkeypatch.setattr(isolated_config, "KEYWORD_TOP_N", 1)
        docs = make_docs(tmp_path, {"a": "Keywords: beta\n", "b": "Keywords: alpha, beta\n"})
        keyword_extract.run_stage(docs)
        # beta is declared by two documents, alpha by one; top_n=1 keeps
        # the higher count, proving rank (not alphabet) decides membership.
        assert seed_topics.load(isolated_config.KEYWORDS_PATH) == ("beta",)


class TestModuleHasNoEntryPoint:
    def test_import_alone_does_nothing(self):
        """Same invariant every stage module holds (docs/ARCHITECTURE.md):
        `python -m chitragupta.enrich` is the only entry point."""
        assert not hasattr(keyword_extract, "main")


@pytest.mark.parametrize(
    "marker",
    ["Keywords", "KEYWORDS", "Index Terms", "index terms", "Keywords:", "Index Terms —"],
)
def test_marker_spellings(marker):
    text = f"{marker} digital twin, iot\n"
    assert keyword_extract.declared_phrases(text) == ("digital twin", "iot")
