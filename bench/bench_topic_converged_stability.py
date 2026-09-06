"""Does the *converged* topic set reproduce, or only the emergent one?

`bench_topic_depth.py --repeats` measures the stability of the emergent
clustering: fit HDBSCAN, refit it on a resample, score the agreement with
the adjusted Rand index. That number (0.14 for the settings hardcoded
until 6.9.0, 0.80 for the current ones) predates seeding entirely. What
ships today is a *converged* topic set -- emergent topics plus the ones a
seed phrase names, joined by `topic_converge.py` -- and nothing has ever
measured whether that survives a resample. #610 (B4) is that measurement.

Two arms per resample, from **one** pipeline run each, so they are
comparable:

- **emergent**, the assignment `run_topic_model()` returns. A genuine
  partition -- one topic per document -- so its ARI needs no
  interpretation. This is the control: it is the number
  `bench_topic_depth.py` already reports, re-derived here so the
  converged arm has something attributable to sit beside.
- **converged**, the assignment `content/topic_set.json` induces. This
  one is *not* a partition: a document may be a member of several
  topics, so a partition has to be chosen before ARI can be computed at
  all. This script takes each document's first listed topic and
  **reports the multi-membership share first**, because an ARI over a
  constructed partition means what it looks like only when few
  documents had a choice to construct.

The real stages do the work -- `run_topic_model`, `topic_seeding.run_stage`,
`topic_converge.run_stage` -- so this measures the shipped pipeline and
not a reimplementation of it. Their three output paths are redirected to
a throwaway directory for the duration, so the corpus's own
`topics.json`, `topic_seeds.json` and `topic_set.json` are read by
nothing here and written by nothing here.

Needs the "enrich" Poetry group and a synced corpus. Reuses
`content/topic_embed_cache.json` (deliberately not redirected -- it is a
cache keyed by document and model, so sharing it is free and correct).

    CHITRAGUPTA_PROJECT=. .venv-full/bin/python \\
        bench/bench_topic_converged_stability.py --tag 2026-09-04-converged-ari
"""

import argparse
import contextlib
import json
import random
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta import config  # noqa: E402
from chitragupta.enrich import corpus, stages, topic_converge, topic_model, topic_seeding  # noqa: E402

HOLDOUT = 0.10


@contextlib.contextmanager
def redirected_artefacts():
    """Point the three topic artefacts at a throwaway directory.

    All three, not one: `converge` *reads* `topics.json` and
    `topic_seeds.json` and writes `topic_set.json`, so redirecting only
    the write would have it join this run's clustering to the corpus's
    stored seeds. Verified against every `config.*_PATH` write in
    `topic_model.py`, `topic_seeding.py` and `topic_converge.py` -- there
    are exactly three.
    """
    scratch = Path(tempfile.mkdtemp(prefix="bench-converged-"))
    saved = (config.TOPICS_PATH, config.TOPIC_SEEDS_PATH, config.TOPIC_SET_PATH)
    config.TOPICS_PATH = scratch / "topics.json"
    config.TOPIC_SEEDS_PATH = scratch / "topic_seeds.json"
    config.TOPIC_SET_PATH = scratch / "topic_set.json"
    try:
        yield scratch
    finally:
        config.TOPICS_PATH, config.TOPIC_SEEDS_PATH, config.TOPIC_SET_PATH = saved


def primary_topics(topic_set: dict) -> dict:
    """`{citekey: label}` from a multi-membership topic set, taking each
    document's first listed topic.

    A choice, not a fact -- which is why `multi_membership_share()` is
    reported beside every number derived from it.
    """
    primary: dict = {}
    for topic in topic_set["topics"]:
        for member in topic["members"]:
            primary.setdefault(member["citekey"], topic["label"])
    return primary


def multi_membership_share(topic_set: dict) -> float:
    """Share of documents belonging to more than one topic -- how much of
    the partition above was constructed rather than observed."""
    counts: dict = {}
    for topic in topic_set["topics"]:
        for member in topic["members"]:
            counts[member["citekey"]] = counts.get(member["citekey"], 0) + 1
    if not counts:
        return 0.0
    return round(sum(1 for n in counts.values() if n > 1) / len(counts), 4)


def ari(baseline: dict, resampled: dict) -> "float | None":
    """Adjusted Rand index over the documents both assignments cover.

    None rather than 0.0 when fewer than two documents overlap: ARI is
    undefined there, and a 0.0 would read as "no agreement" when the
    truth is "nothing was compared".
    """
    from sklearn.metrics import adjusted_rand_score

    shared = sorted(set(baseline) & set(resampled))
    if len(shared) < 2:
        return None
    return round(
        adjusted_rand_score([baseline[c] for c in shared], [resampled[c] for c in shared]), 4
    )


def run_pipeline(docs: list) -> dict:
    """One full emergent-plus-converged run over `docs`, through the real
    stages, with its artefacts redirected. Returns both assignments."""
    phrases = stages._seed_phrases()
    with redirected_artefacts():
        emergent = topic_model.run_topic_model(docs)
        topic_seeding.run_stage(docs, phrases)
        topic_converge.run_stage(docs, phrases)
        topic_set = json.loads(config.TOPIC_SET_PATH.read_text(encoding="utf-8"))
    return {
        "emergent": {k: str(v) for k, v in emergent["assignments"].items()},
        "converged": primary_topics(topic_set),
        "n_topics_emergent": len({v for v in emergent["assignments"].values() if v != -1}),
        "n_topics_converged": len(topic_set["topics"]),
        "multi_membership_share": multi_membership_share(topic_set),
    }


def self_check() -> None:
    """Fabricate a difference each aggregation must see.

    The trap specific to this script is the constructed partition: a
    `primary_topics` that silently let a later topic overwrite an
    earlier one would produce a *different* partition on every run, and
    the converged ARI would then measure dictionary ordering rather than
    clustering. So the fixture puts one document in two topics and pins
    which one wins.
    """
    topic_set = {
        "topics": [
            {"label": "alpha", "members": [{"citekey": "a"}, {"citekey": "shared"}]},
            {"label": "beta", "members": [{"citekey": "b"}, {"citekey": "shared"}]},
        ]
    }
    assert primary_topics(topic_set) == {"a": "alpha", "shared": "alpha", "b": "beta"}
    assert multi_membership_share(topic_set) == round(1 / 3, 4), multi_membership_share(topic_set)
    assert multi_membership_share({"topics": []}) == 0.0
    # An identical relabelling is perfect agreement; a shuffle is not.
    same = {"a": "x", "b": "x", "c": "y", "d": "y"}
    relabelled = {"a": "1", "b": "1", "c": "2", "d": "2"}
    assert ari(same, relabelled) == 1.0, ari(same, relabelled)
    split = {"a": "1", "b": "2", "c": "1", "d": "2"}
    assert ari(same, split) < 0.5, ari(same, split)
    assert ari({"a": "x"}, {"a": "x"}) is None, "one document compares nothing"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    parser.add_argument("--repeats", type=int, default=10, help="resamples (default: 10)")
    parser.add_argument("--seed", type=int, default=42, help="resample seed (default: 42)")
    args = parser.parse_args(argv)
    self_check()

    docs = corpus.build_corpus()
    print(f"{len(docs)} documents; fitting the baseline", flush=True)
    started = time.time()
    baseline = run_pipeline(docs)
    print(
        f"baseline: {baseline['n_topics_emergent']} emergent, "
        f"{baseline['n_topics_converged']} converged topics, "
        f"{baseline['multi_membership_share']:.1%} of documents in more than one "
        f"({time.time() - started:.0f}s)",
        flush=True,
    )

    rng = random.Random(args.seed)
    keep_n = int(round(len(docs) * (1 - HOLDOUT)))
    rows = []
    for i in range(args.repeats):
        kept = rng.sample(docs, keep_n)
        got = run_pipeline(kept)
        row = {
            "repeat": i,
            "emergent_ari": ari(baseline["emergent"], got["emergent"]),
            "converged_ari": ari(baseline["converged"], got["converged"]),
            "n_topics_emergent": got["n_topics_emergent"],
            "n_topics_converged": got["n_topics_converged"],
            "multi_membership_share": got["multi_membership_share"],
        }
        rows.append(row)
        print(
            f"  repeat {i}: emergent ARI {row['emergent_ari']}, "
            f"converged ARI {row['converged_ari']} "
            f"({row['n_topics_emergent']}/{row['n_topics_converged']} topics)",
            flush=True,
        )

    def mean(key):
        values = [r[key] for r in rows if r[key] is not None]
        return round(sum(values) / len(values), 4) if values else None

    summary = {
        "repeats": args.repeats,
        "holdout": HOLDOUT,
        "emergent_ari_mean": mean("emergent_ari"),
        "converged_ari_mean": mean("converged_ari"),
        "baseline_multi_membership_share": baseline["multi_membership_share"],
        "baseline_n_topics_emergent": baseline["n_topics_emergent"],
        "baseline_n_topics_converged": baseline["n_topics_converged"],
    }
    print(
        f"\nmean ARI over {args.repeats} resamples dropping {HOLDOUT:.0%}: "
        f"emergent {summary['emergent_ari_mean']}, "
        f"converged {summary['converged_ari_mean']}"
    )

    out_dir = REPO / "bench" / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "converged_ari.json").write_text(
        json.dumps({"summary": summary, "repeats": rows}, indent=2), "utf-8"
    )
    print(f"wrote {out_dir / 'converged_ari.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
