"""Does seeding with corpus-extracted keywords, alongside the author's
own `content/topics.toml` phrases, produce more meaningful matches than
`content/topics.toml` alone?

Runs `chitragupta/enrich/topic_seeding.py`'s own `assign()` three times
over the same document embeddings -- one arm per phrase set (topics
only, keywords only, both combined) -- and reports, per arm:

- **coverage**: share of the corpus at least one phrase in the arm
  reaches. The plain question a seed list answers badly when it is too
  short or too far from the corpus's own vocabulary.
- **redundancy**: mean pairwise Jaccard similarity between phrases' match
  sets (phrases with zero matches excluded, not counted as a
  maximally-dissimilar 0.0 pair). High redundancy means several phrases
  are five wordings of the same cluster rather than five different ones
  -- more phrases without more topic.
- **keyword_only_coverage** (combined arm only): share of the corpus
  reached by a keyword phrase in the combined run that no topics.toml
  phrase, in that same run, also reaches. This is the number the
  question in the title actually reduces to -- everything else is
  context for reading it.

Needs `content/keywords.toml` already written (`bench/extract_keywords.py`
does that) plus the "enrich" Poetry group and a synced corpus, the same
as `bench/bench_topic_depth.py`. Reuses the document-vector cache the
same way.

    CONTENT_DIR=/path/to/content .venv-full/bin/python \\
        bench/bench_keyword_seed_topics.py --tag 2026-09-03-keywords
"""

import argparse
import itertools
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta import config, seed_topics  # noqa: E402
from chitragupta.enrich import corpus, doc_vectors, embed_index, topic_seeding  # noqa: E402


def _dedup(*phrase_lists) -> tuple:
    """Case-insensitive union of one or more phrase lists, first
    spelling wins, order preserved -- the same rule
    `chitragupta/seed_topics.py:load()` applies within one file, extended
    here to combining two."""
    seen: set[str] = set()
    merged: list[str] = []
    for phrases in phrase_lists:
        for phrase in phrases:
            key = phrase.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(phrase)
    return tuple(merged)


def _coverage(assignment: dict, n_docs: int) -> float:
    """Share of the corpus at least one phrase in this assignment
    reaches. `0.0` for `n_docs == 0` rather than a division error: an
    empty corpus is covered by nothing, which is the true answer, not an
    undefined one."""
    if not n_docs:
        return 0.0
    matched = {match["citekey"] for topic in assignment["topics"] for match in topic["matches"]}
    return len(matched) / n_docs


def _redundancy(assignment: dict) -> "float | None":
    """Mean pairwise Jaccard similarity between phrases' match sets,
    over phrases that matched at least one document.

    `None` for fewer than two live phrases: redundancy is a relation
    between phrases, and reporting `0.0` for "there was nothing to
    compare" would read identically to "compared, and found no overlap"
    -- the same distinction `bench_topic_depth.py`'s `_summarize_labels`
    draws for an all-outlier fit.
    """
    live_sets = [
        {match["citekey"] for match in topic["matches"]}
        for topic in assignment["topics"]
        if topic["matches"]
    ]
    if len(live_sets) < 2:
        return None
    scores = []
    for left, right in itertools.combinations(live_sets, 2):
        union = len(left | right)
        scores.append(len(left & right) / union if union else 0.0)
    return sum(scores) / len(scores)


def _keyword_only_coverage(combined: dict, keyword_phrases: tuple, n_docs: int) -> float:
    """Share of the corpus reached by a keyword phrase in `combined`
    that no topics.toml phrase, in that same run, also reaches.

    Computed from one combined assignment rather than diffed from two
    separate ones, deliberately: comparing a keyword-only run's coverage
    against a topics-only run's coverage cannot tell "new territory"
    apart from "the same territory, reached by a differently-worded
    phrase" -- only asking, within one run, which papers only a keyword
    phrase names, answers the question this benchmark exists for.
    """
    if not n_docs:
        return 0.0
    keyword_set = {phrase.casefold() for phrase in keyword_phrases}
    from_keywords: set[str] = set()
    from_topics: set[str] = set()
    for topic in combined["topics"]:
        bucket = from_keywords if topic["phrase"].casefold() in keyword_set else from_topics
        bucket.update(match["citekey"] for match in topic["matches"])
    return len(from_keywords - from_topics) / n_docs


def self_check() -> None:
    """Fabricate a doc/phrase layout with a hand-computed answer for
    each metric, since none of the three touch the embedding model --
    `bench/` sits outside CI's coverage targets, so this is what catches
    a regression here instead."""
    assignment = {
        "topics": [
            {"phrase": "digital twin", "matches": [{"citekey": "a"}, {"citekey": "b"}]},
            {"phrase": "iot platform", "matches": [{"citekey": "b"}, {"citekey": "c"}]},
            {"phrase": "unicorn", "matches": []},
        ]
    }
    n_docs = 4  # a, b, c, d -- d is unmatched by design

    coverage = _coverage(assignment, n_docs)
    assert coverage == 0.75, f"3 of 4 docs matched, expected 0.75, got {coverage}"
    assert _coverage(assignment, 0) == 0.0, "an empty corpus must not raise"

    redundancy = _redundancy(assignment)
    # {a,b} vs {b,c}: intersection 1, union 3 -> 1/3. "unicorn" has no
    # matches and must be dropped, not scored as a disjoint 0.0 pair.
    assert redundancy == 1 / 3, f"expected the two live phrases' Jaccard 1/3, got {redundancy}"
    assert _redundancy({"topics": [assignment["topics"][0]]}) is None, (
        "redundancy needs at least two live phrases, must not divide by zero"
    )

    keyword_only = _keyword_only_coverage(assignment, ("iot platform",), n_docs)
    # "iot platform" reaches {b, c}; the only other live phrase,
    # "digital twin", reaches {a, b}; c is the one doc only the keyword
    # phrase reaches, so 1/4.
    assert keyword_only == 0.25, f"expected c alone -> 0.25, got {keyword_only}"

    merged = _dedup(("Digital Twin", "IoT"), ("digital twin", "edge"))
    assert merged == ("Digital Twin", "IoT", "edge"), (
        f"expected case-insensitive dedup keeping the first spelling, got {merged}"
    )


def _run_arm(doc_embeddings: dict, model, phrases: tuple) -> dict:
    phrase_vecs = model.encode(list(phrases), show_progress_bar=False)
    phrase_embeddings = {phrase: vec.tolist() for phrase, vec in zip(phrases, phrase_vecs)}
    return topic_seeding.assign(doc_embeddings, phrase_embeddings)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    parser.add_argument("--topics", type=Path, default=None, help="default: content/topics.toml")
    parser.add_argument(
        "--keywords", type=Path, default=None, help="default: content/keywords.toml"
    )
    args = parser.parse_args(argv)
    self_check()

    topics_path = args.topics or (config.CONTENT_DIR / "topics.toml")
    keywords_path = args.keywords or (config.CONTENT_DIR / "keywords.toml")
    topics = seed_topics.load(topics_path)
    keywords = seed_topics.load(keywords_path)
    if not topics or not keywords:
        print(
            f"need both {topics_path} and {keywords_path} populated with "
            f"phrases; got {len(topics)} topics, {len(keywords)} keywords",
            flush=True,
        )
        return 1

    docs = corpus.build_corpus()
    doc_texts = doc_vectors.corpus_texts(docs)
    _client, model = embed_index.get_client_and_model()
    doc_embeddings = doc_vectors.document_embeddings(doc_texts, model)
    n_docs = len(doc_embeddings)

    arms = {
        "topics_only": topics,
        "keywords_only": keywords,
        "combined": _dedup(topics, keywords),
    }
    rows: dict = {}
    print(f"{n_docs} documents\n", flush=True)
    print(f"{'arm':>13} | {'phrases':>7} {'coverage':>9} {'redundancy':>10}", flush=True)
    for name, phrases in arms.items():
        assignment = _run_arm(doc_embeddings, model, phrases)
        row = {
            "phrases": len(phrases),
            "coverage": _coverage(assignment, n_docs),
            "redundancy": _redundancy(assignment),
        }
        if name == "combined":
            row["keyword_only_coverage"] = _keyword_only_coverage(assignment, keywords, n_docs)
        rows[name] = row
        redundancy_str = "-" if row["redundancy"] is None else f"{row['redundancy']:.3f}"
        print(
            f"{name:>13} | {row['phrases']:>7} {row['coverage']:>9.1%} {redundancy_str:>10}",
            flush=True,
        )

    gain = rows["combined"]["coverage"] - rows["topics_only"]["coverage"]
    print(f"\ncombined coverage gain over topics-only: {gain:+.1%}")
    print(
        "of the corpus, share reached ONLY by a keyword phrase in the "
        f"combined run: {rows['combined']['keyword_only_coverage']:.1%}"
    )

    out = Path(__file__).resolve().parent / "results" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "keyword_seed_topics.json").write_text(
        json.dumps({"n_docs": n_docs, "arms": rows}, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {out / 'keyword_seed_topics.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
