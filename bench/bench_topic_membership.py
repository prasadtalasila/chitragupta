"""Which mechanism can say a paper belongs to more than one topic.

`assignments` in content/topics.json gives each document exactly one
topic id, because that is all `fit_transform` returns. A corpus grouped
by hand does not work that way -- this project's own has 637 of 642
papers under 95 Zotero collections -- so something has to supply the
many-to-many view. Four candidates were measured before one was chosen,
and three failed for structural reasons rather than for want of tuning.

The column that decides it is **agreement**: a membership set that does
not contain the topic the clustering actually assigned is describing a
different clustering than the one it is printed beside. Two fields of one
artefact contradicting each other is worse than one field saying less.

    approximate_distribution  BERTopic's own, c-TF-IDF over token windows
    centroid-embed            cosine to cluster centroids, centred, in the
                              embedding space
    centroid-umap             the same, in the reduced space the
                              clustering actually happened in
    gaussian-mixture          soft by construction, over the reduced space
    hdbscan-soft              HDBSCAN's own all_points_membership_vectors

Needs the "enrich" Poetry group and a synced corpus. Reuses the cached
document vectors, so a warm content/topic_embed_cache.json makes this
minutes rather than tens of minutes.

    CONTENT_DIR=/path/to/content .venv-full/bin/python \\
        bench/bench_topic_membership.py --tag 2026-08-21-topic-membership
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta import config  # noqa: E402
from chitragupta.enrich import corpus, doc_vectors, embed_index, topic_model  # noqa: E402


def unit(matrix):
    import numpy as np

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


def score(name, weights, labels, columns, ratio=0.5):
    """Shape and agreement for one candidate mechanism.

    `agreement` is the share of non-outlier documents whose *assigned*
    topic appears in the membership set the mechanism produced for them,
    and `is_top` the share where it ranks first.

    `columns` gives the topic id each column of `weights` stands for, and
    is not always `sorted(set(labels))`: HDBSCAN's own soft clustering is
    indexed by *cluster* id, and BERTopic renumbers topics by size, so
    cluster 0 was topic 6 on the run this was written against. Passing the
    mapping in rather than assuming it is what keeps this comparison
    honest -- assuming it scored the winning mechanism at 1% agreement.
    """
    import numpy as np

    weights = np.clip(np.asarray(weights, dtype=float), 0, None)
    keep = (weights >= ratio * weights.max(axis=1, keepdims=True)) & (weights > 0)
    counts = keep.sum(axis=1)
    live = counts > 0
    total = weights.sum(axis=1)
    ok = total > 0
    top_share = np.divide(weights.max(axis=1), total, out=np.zeros(len(weights)), where=ok)
    ranked_top = np.array([columns[i] for i in weights.argmax(axis=1)])

    real = np.asarray(labels) != -1
    index = {topic_id: i for i, topic_id in enumerate(columns)}
    in_set = np.array([keep[row, index[labels[row]]]
                       if real[row] and labels[row] in index else False
                       for row in range(len(weights))])
    return {
        "mechanism": name,
        "topics_per_doc": float(counts[live].mean()) if live.any() else 0.0,
        "plural_share": float((counts > 1).mean()),
        "top_share": float(top_share[ok].mean()) if ok.any() else 0.0,
        "uniform_baseline": 1.0 / weights.shape[1],
        "agreement": float(in_set[real].sum() / max(real.sum(), 1)),
        "is_top": float((ranked_top[real] == np.asarray(labels)[real]).sum()
                        / max(real.sum(), 1)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    args = parser.parse_args(argv)

    import numpy as np
    from hdbscan import all_points_membership_vectors
    from sklearn.mixture import GaussianMixture

    docs = corpus.build_corpus()
    doc_texts = doc_vectors.corpus_texts(docs)
    _client, model = embed_index.get_client_and_model()
    vectors = doc_vectors.document_embeddings(doc_texts, model)
    citekeys = [c for c in doc_texts if c in vectors]
    embeddings = np.array([vectors[c] for c in citekeys])
    texts = [doc_texts[c] for c in citekeys]

    fitted, topics = topic_model._fit(texts, embeddings, model)  # noqa: SLF001
    labels = [int(t) for t in topics]
    ids = sorted(set(labels) - {-1})
    print(f"{len(citekeys)} documents, {len(ids)} topics, "
          f"{100 * labels.count(-1) / len(labels):.0f}% outliers\n", flush=True)

    assigned = np.asarray(labels)
    rows = []

    rows.append(score("approximate_distribution",
                      fitted.approximate_distribution(texts, min_similarity=0.0)[0],
                      labels, ids))

    centred = embeddings - embeddings.mean(axis=0)
    centroids = np.array([centred[assigned == t].mean(axis=0) for t in ids])
    rows.append(score("centroid-embed", unit(centred) @ unit(centroids).T, labels, ids))

    reduced = np.asarray(fitted.umap_model.embedding_)
    reduced_centroids = np.array([reduced[assigned == t].mean(axis=0) for t in ids])
    distance = np.linalg.norm(reduced[:, None, :] - reduced_centroids[None, :, :], axis=2)
    rows.append(score("centroid-umap", 1.0 / (1.0 + distance), labels, ids))

    mixture = GaussianMixture(n_components=len(ids), covariance_type="diag",
                              random_state=42).fit(reduced)
    rows.append(score("gaussian-mixture", mixture.predict_proba(reduced), labels, ids))

    # HDBSCAN's columns are its own cluster ids. The mapping onto
    # BERTopic's topic ids is recovered from the documents, each of which
    # carries both, exactly as chitragupta/enrich/topic_model.py does it.
    cluster_labels = [int(label) for label in fitted.hdbscan_model.labels_]
    cluster_columns = sorted(set(cluster_labels) - {-1})
    renumbered = {cluster: topic for cluster, topic in zip(cluster_labels, labels)}
    rows.append(score("hdbscan-soft",
                      np.atleast_2d(np.asarray(all_points_membership_vectors(
                          fitted.hdbscan_model))), labels,
                      [renumbered[c] for c in cluster_columns]))

    print(f"{'mechanism':26} {'topics/doc':>10} {'plural':>7} {'top-share':>10} "
          f"{'agreement':>10} {'is-top':>7}")
    for row in rows:
        print(f"{row['mechanism']:26} {row['topics_per_doc']:>10.2f} "
              f"{100 * row['plural_share']:>6.0f}% {row['top_share']:>10.2f} "
              f"{100 * row['agreement']:>9.0f}% {100 * row['is_top']:>6.0f}%")
    print(f"\nuniform top-share baseline: {rows[0]['uniform_baseline']:.2f} "
          f"-- a mechanism at that number is saying nothing")

    out = Path(__file__).resolve().parent / "results" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "membership.json").write_text(
        json.dumps({"n_docs": len(citekeys), "n_topics": len(ids),
                    "model": config.EMBEDDING_MODEL, "rows": rows}, indent=2),
        encoding="utf-8")
    print(f"wrote {out / 'membership.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
