"""What query-side spelling correction (#1232) does on this corpus:
how often it picks the right word, what it costs, whether it moves real
queries, and whether it recovers the paper a typo lost.

Every arm runs the shipped code -- `retrieval.query_terms` and
`retrieval_spelling.correct` -- with `config.SPELLING_CORRECTION` flipped
in one process. Ranking goes through `retrieval_cache.read_only_index`
and `retrieval._bm25_scores`, as the drift report does, so this script
never writes the BM25 cache. Acronym expansion is held off in every arm,
so nothing but correction differs between them.

Four arms:

1. **Accuracy and cost.** Every 5+-letter, all-letter word of the logged
   queries that the corpus contains gets four synthetic typos (one
   deletion, adjacent swap, substitution and insertion, from
   `random.Random(1232)`). Each is corrected and scored right, wrong or
   none. Typos that are themselves corpus words (rule 1 leaves them
   alone) and typos under five letters stay in the denominator as their
   own buckets. Timed per word, which includes the ledger read and
   fingerprinting every `query_terms` call pays with correction on.
2. **Harm check.** Every logged `search`/`evidence` query, off and on. The
   logs hold no genuine typo, so this arm can only show harm: which
   queries gained a correction, and how their top five moved.
3. **Recovery.** The keyword self-retrieval set (a paper's own `keywords`
   field as the query, that paper as the answer), with one typo injected
   into one eligible word per query. Recall@1, recall@5 and MRR@5 off and
   on, overall and on the queries correction actually changed, beside the
   untouched queries' figures for reference.
4. **`--y-prev` prose.** Paragraphs of the project's own drafts, as
   `retrieve search --y-prev` would append them: how many corrections a
   round adds without a note.

Run from the repository, naming the project to measure:

    CHITRAGUPTA_PROJECT=/path/to/project \\
        python bench/bench_retrieval_spelling.py --tag <date>-spelling-correction
"""

import argparse
import json
import random
import re
import string
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import (  # noqa: E402
    config,
    dossier,
    ledger,
    retrieval,
    retrieval_cache,
    retrieval_spelling,
)
from chitragupta.dossier._retrieval_queries import _retrieval_rows  # noqa: E402
from chitragupta.ledger_citable import PARSED  # noqa: E402
from bench_retrieval_compare import recall_at_k, with_field_weights  # noqa: E402
from bench_retrieval_keyword_selfretrieval import build_keyword_ground_truth  # noqa: E402

K = 5
SEED = 1232


def typos(word: str, rng: random.Random) -> dict[str, str]:
    """One typo of each kind at a random interior position."""
    i = rng.randrange(1, len(word) - 1)
    letters = string.ascii_lowercase
    return {
        "delete": word[:i] + word[i + 1 :],
        "swap": word[:i] + word[i + 1] + word[i] + word[i + 2 :],
        "substitute": word[:i] + rng.choice(letters.replace(word[i], "")) + word[i + 1 :],
        "insert": word[:i] + rng.choice(letters) + word[i:],
    }


def eligible(word: str) -> bool:
    return len(word) >= retrieval_spelling.MIN_LENGTH and word.isalpha()


def ranked(index: dict, query: str) -> list[str]:
    scores = retrieval._bm25_scores(index, retrieval.query_terms(query)[0])
    return [c for c, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:K]]


def logged_queries() -> list[str]:
    """Every distinct `search`/`evidence` query any dossier logged."""
    queries = set()
    for path in dossier.all_dossiers():
        for row in _retrieval_rows(path):
            if row[1] in {"search", "evidence"} and row[2]:
                queries.add(row[2])
    return sorted(queries)


def arm_accuracy(queries: list[str], vocab: dict[str, int]) -> dict:
    words = sorted({w for q in queries for w in retrieval._query_terms(q) if eligible(w)})
    words = [w for w in words if w in vocab]
    rng = random.Random(SEED)
    buckets = {"right": 0, "wrong": 0, "none": 0, "typo is a corpus word": 0, "typo too short": 0}
    by_kind: dict[str, dict[str, int]] = {}
    times, wrong = [], []
    config.SPELLING_CORRECTION = True
    for word in words:
        for kind, typo in typos(word, rng).items():
            if typo in vocab:
                outcome = "typo is a corpus word"
            elif len(typo) < retrieval_spelling.MIN_LENGTH:
                outcome = "typo too short"
            else:
                start = time.perf_counter()
                found = retrieval_spelling.correct(
                    [typo], retrieval._tokenize_item, retrieval._INTERROGATIVES
                )
                times.append(time.perf_counter() - start)
                outcome = "none" if not found else "right" if found[0][1] == word else "wrong"
                if outcome == "wrong":
                    wrong.append(f"{word} -> {typo} -> {found[0][1]}")
            buckets[outcome] += 1
            by_kind.setdefault(kind, {}).setdefault(outcome, 0)
            by_kind[kind][outcome] += 1
    corrected = buckets["right"] + buckets["wrong"]
    times.sort()
    return {
        "words": len(words),
        "typos": sum(buckets.values()),
        "buckets": buckets,
        "by_kind": by_kind,
        "right_when_corrected": round(buckets["right"] / corrected, 4) if corrected else None,
        "fixed_of_all_typos": round(buckets["right"] / sum(buckets.values()), 4),
        "pool_size": sum(1 for n in vocab.values() if n >= retrieval_spelling.MIN_PAPERS),
        "ms_per_word_median": round(1000 * times[len(times) // 2], 2),
        "ms_per_word_p95": round(1000 * times[int(0.95 * len(times))], 2),
        "wrong_examples": wrong[:20],
    }


def arm_harm(index: dict, queries: list[str]) -> dict:
    moved = []
    for query in queries:
        config.SPELLING_CORRECTION = False
        off = ranked(index, query)
        config.SPELLING_CORRECTION = True
        added = [a for a in retrieval.query_terms(query)[1] if a.source == "spelling"]
        if added:
            moved.append(
                {
                    "query": query,
                    "added": [f"{a.typed} ~> {a.term}" for a in added],
                    "top5_off": off,
                    "top5_on": ranked(index, query),
                }
            )
    return {"queries": len(queries), "corrected": len(moved), "moved": moved}


def _figures(rows: list[dict], key: str) -> dict | None:
    if not rows:
        return None
    n = len(rows)
    return {
        "n": n,
        "recall@1": round(sum(r[key]["r1"] for r in rows) / n, 4),
        "recall@5": round(sum(r[key]["r5"] for r in rows) / n, 4),
        "mrr@5": round(sum(r[key]["rr"] for r in rows) / n, 4),
    }


def _score(top: list[str], answer: str) -> dict:
    rr = next((1 / i for i, c in enumerate(top, start=1) if c == answer), 0.0)
    return {"r1": recall_at_k(top, {answer}, 1), "r5": recall_at_k(top, {answer}, K), "rr": rr}


def arm_recovery(index: dict, vocab: dict[str, int]) -> dict:
    rng = random.Random(SEED)
    rows = []
    for truth in build_keyword_ground_truth():
        if truth["citekey"] not in index:
            continue
        words = [w for w in retrieval._query_terms(truth["query"]) if eligible(w) and w in vocab]
        if not words:
            continue
        word = rng.choice(words)
        options = [t for t in typos(word, rng).values() if t not in vocab]
        if not options:
            continue
        # As a whole token: `twin` must not land inside an earlier `twins`.
        pattern = rf"(?<![a-z0-9]){word}(?![a-z0-9])"
        query = re.sub(pattern, rng.choice(options), truth["query"].lower(), count=1)
        config.SPELLING_CORRECTION = False
        row = {"clean": _score(ranked(index, truth["query"]), truth["citekey"])}
        row["off"] = _score(ranked(index, query), truth["citekey"])
        config.SPELLING_CORRECTION = True
        row["on"] = _score(ranked(index, query), truth["citekey"])
        row["affected"] = any(a.source == "spelling" for a in retrieval.query_terms(query)[1])
        rows.append(row)
    affected = [r for r in rows if r["affected"]]
    return {
        "overall": {k: _figures(rows, k) for k in ("clean", "off", "on")},
        "affected": {k: _figures(affected, k) for k in ("clean", "off", "on")},
    }


def arm_y_prev(limit: int = 300) -> dict:
    """What `--y-prev` prose gains: `retrieve search --y-prev` appends up
    to 1500 characters of draft text to the query, and corrections in it
    reach no note. Paragraphs of this project's own drafts stand in for
    that text."""
    paragraphs = set()
    for path in sorted(config.DRAFTS_DIR.rglob("*")):
        if path.suffix in {".md", ".tex"} and path.is_file():
            for block in path.read_text(encoding="utf-8", errors="replace").split("\n\n"):
                if len(block) >= 200:
                    paragraphs.add(block[:1500])
    sample = sorted(paragraphs)
    sample = random.Random(SEED).sample(sample, min(limit, len(sample)))
    config.SPELLING_CORRECTION = True
    counts, examples = [], []
    for text in sample:
        found = retrieval_spelling.correct(
            retrieval._query_terms(text), retrieval._tokenize_item, retrieval._INTERROGATIVES
        )
        counts.append(len(found))
        examples += [f"{typed} ~> {term}" for typed, term in found]
    return {
        "paragraphs": len(counts),
        "with_a_correction": sum(1 for c in counts if c),
        "mean_corrections": round(sum(counts) / len(counts), 2) if counts else None,
        "max_corrections": max(counts, default=0),
        "examples": examples[:30],
    }


def build_times(rows: list) -> dict:
    """What a vocabulary costs to build, and what checking it costs.

    Each process with correction on builds it once. `no_cache_s` is a
    build with no BM25 cache file at all, every paper tokenized; a sync
    re-tokenizes only the papers whose entries it made stale.
    `warm_cache_s` is a build whose every entry the on-disk cache can
    serve, simulated in memory -- this script must not write the cache,
    and the host's may be stale (a re-parse rewrites the `.txt` files,
    and only the next `search` re-saves). It is that build plus the
    measured time to read the cache file. `check_ms` is what every
    corrected query pays once the vocabulary is built: a ledger read and
    a fingerprint of every parsed file, which is how a sync is noticed.
    """
    real = retrieval_cache._load_cache

    def timed(load) -> float:
        retrieval_cache._READ_ONLY_MEMO.clear()
        retrieval_spelling._MEMO.clear()
        retrieval_cache._load_cache = load
        start = time.perf_counter()
        retrieval_spelling.vocabulary(retrieval._tokenize_item)
        return time.perf_counter() - start

    no_cache = timed(dict)
    built = retrieval_cache._READ_ONLY_MEMO["index"]
    served = {
        row["citekey"]: {**built[row["citekey"]], "fingerprint": retrieval_cache._fingerprint(row)}
        for row in rows
    }
    warm = timed(lambda: served)
    retrieval_cache._load_cache = real
    start = time.perf_counter()
    retrieval_cache._CACHE.read_file()
    read_file = time.perf_counter() - start
    start = time.perf_counter()
    retrieval_spelling.vocabulary(retrieval._tokenize_item)
    check = time.perf_counter() - start
    return {
        "papers": len(rows),
        "no_cache_s": round(no_cache, 3),
        "warm_cache_s": round(warm + read_file, 3),
        "check_ms": round(1000 * check, 1),
    }


def self_check(index: dict, queries: list[str]) -> None:
    """Off must rank exactly on the typed terms, and the typo generator
    must be deterministic -- both before anything is published."""
    config.SPELLING_CORRECTION = False
    for query in queries[:50]:
        terms = retrieval._query_terms(query)
        bare = sorted(retrieval._bm25_scores(index, terms).items(), key=lambda kv: (-kv[1], kv[0]))
        assert ranked(index, query) == [c for c, _ in bare[:K]], query
    assert typos("structural", random.Random(SEED)) == typos("structural", random.Random(SEED))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="results/<tag>/ to write the record into")
    parser.add_argument("--self-check", action="store_true", help="Run the self-check and stop")
    args = parser.parse_args(argv)

    with_field_weights({})
    config.ACRONYM_EXPANSION = False
    with ledger.reading() as con:
        rows = [row for row in ledger.all_items(con) if row["status"] == PARSED]
    index = retrieval_cache.read_only_index(rows, retrieval._tokenize_item)
    queries = logged_queries()
    self_check(index, queries)
    if args.self_check:
        print("self-check passed")
        return 0
    if not args.tag:
        print("--tag is required", file=sys.stderr)
        return 2

    timing = build_times(rows)
    vocab = retrieval_spelling.vocabulary(retrieval._tokenize_item)
    record = {
        "corpus": {**timing, "vocabulary": len(vocab), "logged_queries": len(queries)},
        "accuracy": arm_accuracy(queries, vocab),
        "harm": arm_harm(index, queries),
        "recovery": arm_recovery(index, vocab),
        "y_prev": arm_y_prev(),
    }
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "spelling_correction.json"
    out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "harm"}, indent=1)[:4000])
    print(f"harm: {record['harm']['corrected']} of {record['harm']['queries']} queries corrected")
    print(f"\nRecord: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
