"""Score the discover resolution ladder against a hand-written gold set.

Legacy AutoRAG's methodology (arXiv is silent; the archived 1.x docs are
the source) pointed at one corpus: a small set of hand-labelled queries
with the topics and citekeys they *should* reach, re-run after every
knob change, so `[discover].min_similarity`, the fuzzy cutoff and the
fusion shape are tuned by measurement rather than by feel. The gold
file is yours to write -- `assets/style/topic_gold.toml.example` is the
template -- because hand-writing ~40 queries for your own corpus is
cheaper and more trustworthy than generating them.

    [[query]]
    phrase = "how do digital twins synchronise state"
    topics = ["digital twin"]            # expected topics, any order
    citekeys = ["kritzinger_digital_2018"]  # optional: papers the top
                                            # topic should contain

Reports, per resolution rung and overall: hit@1, recall@5, MRR and
NDCG@5 for query->topic, and member-recall for topic->paper. Read-only:
it resolves against the artefacts on disk and writes nothing unless
`--out` names a file.

    python bench/topic_discovery_eval.py
    python bench/topic_discovery_eval.py --gold content/topic_gold.toml \\
        --out bench/results/gold.json

What `self_check()` cannot see: a gold file whose expectations are
themselves wrong, and any change in how the enrich stages *build* the
artefacts -- this script measures resolution over what is on disk, not
the pipeline that produced it.
"""

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# chitragupta imports stay inside the functions that resolve queries:
# importing chitragupta.config resolves PROJECT_ROOT from the cwd, and
# the metric helpers plus self_check() must work -- and be testable --
# without a project directory existing at all.


def recall_at(ranked: list, expected: set, k: int) -> float:
    if not expected:
        return 0.0
    return len(set(ranked[:k]) & expected) / len(expected)


def mrr(ranked: list, expected: set) -> float:
    for position, label in enumerate(ranked, start=1):
        if label in expected:
            return 1.0 / position
    return 0.0


def ndcg_at(ranked: list, expected: set, k: int) -> float:
    """Binary-relevance NDCG: gains discounted by log2(rank+1), against
    the ideal ordering of the same expectations."""
    gain = sum(
        1.0 / math.log2(position + 1)
        for position, label in enumerate(ranked[:k], start=1)
        if label in expected
    )
    ideal = sum(1.0 / math.log2(position + 1) for position in range(1, min(len(expected), k) + 1))
    return gain / ideal if ideal else 0.0


def score_query(record: dict, graph: dict, topic_set: dict, terms: dict) -> dict:
    from chitragupta.discover import _data, _resolve

    resolution = _resolve.resolve(record["phrase"], graph, topic_set, terms)
    return score_resolution(record, resolution.ranked, resolution.via, _data.members_of(topic_set))


def score_resolution(record: dict, ranked: list, via: str, members_by_label: dict) -> dict:
    """One gold row scored. An **empty** expected-topics list is a real
    expectation -- "this phrase should resolve to *no* topic" -- so it is
    credited when the ladder fell through to search and debited when a
    topic was claimed, rather than scoring an unwinnable zero. The
    ranked metrics are meaningless for it and are omitted (the
    aggregation skips absent keys)."""
    expected = set(record.get("topics", []))
    if not expected:
        return {
            "phrase": record["phrase"],
            "via": via,
            "hit_at_1": 1.0 if via == "search" else 0.0,
        }
    row = {
        "phrase": record["phrase"],
        "via": via,
        "hit_at_1": 1.0 if ranked and ranked[0] in expected else 0.0,
        "recall_at_5": recall_at(ranked, expected, 5),
        "mrr": mrr(ranked, expected),
        "ndcg_at_5": ndcg_at(ranked, expected, 5),
    }
    wanted_citekeys = set(record.get("citekeys", []))
    if wanted_citekeys and ranked:
        members = {m["citekey"] for m in members_by_label.get(ranked[0], [])}
        row["member_recall"] = len(members & wanted_citekeys) / len(wanted_citekeys)
    return row


def aggregate(rows: list) -> dict:
    """Means per metric, overall and grouped by the rung that resolved
    each query -- the per-rung split is what makes a knob's effect
    legible, since a floor change moves queries *between* rungs."""
    metrics = ("hit_at_1", "recall_at_5", "mrr", "ndcg_at_5", "member_recall")

    def means(group: list) -> dict:
        out = {"n": len(group)}
        for metric in metrics:
            values = [row[metric] for row in group if metric in row]
            if values:
                out[metric] = sum(values) / len(values)
        return out

    by_via: dict = {}
    for row in rows:
        by_via.setdefault(row["via"], []).append(row)
    return {
        "overall": means(rows),
        "by_rung": {via: means(group) for via, group in sorted(by_via.items())},
    }


def report(summary: dict) -> str:
    lines = []
    for scope, values in [("overall", summary["overall"]), *summary["by_rung"].items()]:
        cells = "  ".join(
            f"{metric}={value:.3f}" if metric != "n" else f"n={value}"
            for metric, value in values.items()
        )
        lines.append(f"{scope:<10} {cells}")
    return "\n".join(lines)


def self_check() -> None:
    """Fabricate a difference the aggregation must see: the same ranking
    scored against the right expectation and a wrong one must not tie --
    a comparison that reads those as equal would print a stable-looking
    zero over a broken metric, which is the bench failure mode."""
    ranked = ["alpha", "beta"]
    right = {"alpha"}
    wrong = {"gamma"}
    assert mrr(ranked, right) == 1.0 and mrr(ranked, wrong) == 0.0
    assert recall_at(ranked, right, 5) > recall_at(ranked, wrong, 5)
    assert ndcg_at(ranked, right, 5) > ndcg_at(ranked, wrong, 5)
    good = aggregate(
        [{"via": "exact", "hit_at_1": 1.0, "recall_at_5": 1.0, "mrr": 1.0, "ndcg_at_5": 1.0}]
    )
    bad = aggregate(
        [{"via": "exact", "hit_at_1": 0.0, "recall_at_5": 0.0, "mrr": 0.0, "ndcg_at_5": 0.0}]
    )
    assert good["overall"]["mrr"] > bad["overall"]["mrr"]
    # An empty expectation must be winnable and losable: a correct
    # fall-through to search scores, a claimed topic does not.
    none_expected = {"phrase": "q", "topics": []}
    fell_through = score_resolution(none_expected, [], "search", {})
    claimed = score_resolution(none_expected, ["alpha"], "hybrid", {})
    assert fell_through["hit_at_1"] > claimed["hit_at_1"]
    assert "mrr" not in fell_through


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gold", default=None, help="gold TOML (default: content/topic_gold.toml)")
    parser.add_argument("--out", default=None, help="also write the summary as JSON here")
    args = parser.parse_args()
    self_check()

    # Imported after self_check() and inside main(), like every bench
    # script: config resolves PROJECT_ROOT from the cwd at import time.
    from chitragupta import config
    from chitragupta.discover import _data

    gold_path = Path(args.gold) if args.gold else config.CONTENT_DIR / "topic_gold.toml"
    if not gold_path.exists():
        print(f"No gold set at {gold_path}. Start from assets/style/topic_gold.toml.example.")
        return 1
    records = tomllib.loads(gold_path.read_text(encoding="utf-8")).get("query", [])
    if not records:
        print(f"{gold_path} holds no [[query]] records.")
        return 1

    graph = _data.load_graph()
    topic_set = _data.load_topic_set()
    terms = _data.top_terms(topic_set)
    rows = [score_query(record, graph, topic_set, terms) for record in records]
    summary = aggregate(rows)
    print(report(summary))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
        print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
