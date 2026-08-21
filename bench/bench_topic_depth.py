"""How many topics the corpus divides into, at each clustering setting.

The measurement behind `[enrich].topic_min_cluster_size`,
`topic_min_samples` and `topic_neighbors`, and behind the claim that
their hardcoded predecessors were a *ceiling* rather than a default:
every parameter saturated at n_docs >= 20, so a 497-document corpus was
clustered with the settings written for a 20-document one and could not
yield more than ~13 topics however far it grew.

Reports, per setting: how many topics, what share of the corpus is left
in the outlier bucket, the median topic size, and -- with `--repeats` --
whether the same setting reproduces.

Two columns are worth watching. **outliers** *falls* as topics get finer,
which is what makes the coarse setting a defect rather than a preference.
**stability** answers the question Asta's survey says this family of
methods is usually not asked: "a model that looks good once can still be
unstable across runs or topic counts". It is the adjusted Rand index
between repeated fits of one setting, over the document-to-topic
assignment -- 1.0 means the two runs partition the corpus identically,
0.0 means no more agreement than chance.

The motivating case is in bench/RESULTS.md: one swept setting reported 13
topics at 27% outliers, then 5 at 12% after an unrelated preprocessing
change landed, with `random_state=42` throughout. Nothing was random; the
inputs moved. A stability column would not have caught that -- it is
measured within one corpus state -- but it says which settings are worth
trusting at all before that question even arises.

Needs the "enrich" Poetry group and a synced corpus with parsed text; it
drives the real UMAP/HDBSCAN stack. Reuses the document vectors
chitragupta/enrich/doc_vectors.py caches, so a warm
content/topic_embed_cache.json makes it minutes rather than tens of
minutes -- and a cold one pays a full corpus embed first.

    CONTENT_DIR=/path/to/content .venv-full/bin/python \\
        bench/bench_topic_depth.py --tag 2026-08-21-topic-depth
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta.enrich import corpus, doc_vectors, embed_index  # noqa: E402

# (n_neighbors, n_components, min_cluster_size, min_samples). min_samples
# None leaves HDBSCAN's own default, which is min_cluster_size.
GRID = [
    (15, 5, 10, None),   # the values hardcoded until 6.9.0
    (15, 5, 5, None),
    (15, 5, 3, None),
    (10, 5, 10, None),
    (10, 5, 5, None),
    (10, 5, 3, None),
    (10, 5, 3, 2),       # the 6.9.0 defaults
    (5, 5, 5, 3),
    (5, 5, 3, 2),
    (5, 10, 3, 2),
]


def fit_labels(reduced, min_cluster_size, min_samples):
    """One HDBSCAN fit's labels, and the fitted clusterer."""
    from hdbscan import HDBSCAN

    kwargs = dict(min_cluster_size=min_cluster_size, metric="euclidean",
                  cluster_selection_method="eom", prediction_data=True)
    if min_samples is not None:
        kwargs["min_samples"] = min_samples
    clusterer = HDBSCAN(**kwargs).fit(reduced)
    return [int(label) for label in clusterer.labels_], clusterer


def stability(reduced, min_cluster_size, min_samples, repeats):
    """Mean adjusted Rand index between repeated fits of one setting.

    Returns None for `repeats < 2`, which is "not asked" rather than
    "perfectly stable" -- the two must not print the same.

    HDBSCAN is deterministic given identical input, so a bare repeat
    would return 1.0 and measure nothing. Each repeat therefore re-fits
    on a bootstrap resample of the reduced space and scores agreement on
    the documents the two runs have in common, which is the resampling
    Asta's survey describes rather than a re-run of the same arithmetic.
    """
    import numpy as np
    from sklearn.metrics import adjusted_rand_score

    if repeats < 2:
        return None
    rng = np.random.default_rng(42)
    scores, baseline = [], fit_labels(reduced, min_cluster_size, min_samples)[0]
    for _ in range(repeats - 1):
        keep = rng.choice(len(reduced), size=int(0.9 * len(reduced)), replace=False)
        resampled = fit_labels(reduced[keep], min_cluster_size, min_samples)[0]
        scores.append(adjusted_rand_score([baseline[i] for i in keep], resampled))
    return float(np.mean(scores))


def measure(reduced, min_cluster_size, min_samples, repeats=1):
    import numpy as np
    from hdbscan import all_points_membership_vectors

    labels, clusterer = fit_labels(reduced, min_cluster_size, min_samples)
    ids = sorted(set(labels) - {-1})
    if not ids:
        return {"topics": 0, "outlier_share": 1.0, "median_size": 0,
                "topics_per_doc": 0.0, "stability": None}

    sizes = sorted(labels.count(topic_id) for topic_id in ids)
    soft = np.atleast_2d(np.asarray(all_points_membership_vectors(clusterer)))
    keep = (soft >= 0.5 * soft.max(axis=1, keepdims=True)) & (soft > 0)
    counts = keep.sum(axis=1)
    live = counts[counts > 0]
    return {
        "topics": len(ids),
        "outlier_share": labels.count(-1) / len(labels),
        "median_size": sizes[len(sizes) // 2],
        "topics_per_doc": float(live.mean()) if len(live) else 0.0,
        "stability": stability(reduced, min_cluster_size, min_samples, repeats),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    parser.add_argument("--repeats", type=int, default=1,
                        help="fit each setting this many times and report the "
                             "agreement between fits (adjusted Rand index)")
    args = parser.parse_args(argv)

    import numpy as np
    from umap import UMAP

    docs = corpus.build_corpus()
    doc_texts = doc_vectors.corpus_texts(docs)
    _client, model = embed_index.get_client_and_model()
    started = time.time()
    vectors = doc_vectors.document_embeddings(doc_texts, model)
    embed_seconds = time.time() - started
    citekeys = [c for c in doc_texts if c in vectors]
    embeddings = np.array([vectors[c] for c in citekeys])
    print(f"{len(citekeys)} documents, embedded in {embed_seconds:.0f}s "
          f"(0s means the cache was warm)", flush=True)

    rows = []
    # UMAP is the expensive half and depends only on (n_neighbors,
    # n_components), so it is fitted once per pair and reused across every
    # HDBSCAN setting underneath it.
    reductions = {}
    print(f"\n{'n_nbr':>5} {'n_cmp':>5} {'mcs':>4} {'ms':>4} | {'topics':>6} "
          f"{'outliers':>9} {'median':>7} {'topics/doc':>10}", flush=True)
    for n_neighbors, n_components, min_cluster_size, min_samples in GRID:
        key = (n_neighbors, n_components)
        if key not in reductions:
            reductions[key] = UMAP(n_neighbors=n_neighbors, n_components=n_components,
                                   min_dist=0.0, metric="cosine",
                                   random_state=42).fit_transform(embeddings)
        got = measure(reductions[key], min_cluster_size, min_samples,
                      args.repeats)
        rows.append(dict(n_neighbors=n_neighbors, n_components=n_components,
                         min_cluster_size=min_cluster_size, min_samples=min_samples, **got))
        stable = "-" if got["stability"] is None else f"{got['stability']:.2f}"
        print(f"{n_neighbors:>5} {n_components:>5} {min_cluster_size:>4} "
              f"{str(min_samples or '-'):>4} | {got['topics']:>6} "
              f"{100 * got['outlier_share']:>8.0f}% {got['median_size']:>7} "
              f"{got['topics_per_doc']:>10.2f} {stable:>10}", flush=True)

    out = Path(__file__).resolve().parent / "results" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "depth.json").write_text(
        json.dumps({"n_docs": len(citekeys), "repeats": args.repeats, "rows": rows},
                   indent=2), encoding="utf-8")
    print(f"\nwrote {out / 'depth.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
