"""Passage-unit BM25 against document-unit BM25, on both existing arms (#769).

`chitragupta/retrieval_passages.py` ranks the corpus layer's
reading-ordered paragraphs instead of whole documents. This scores that
change against the two ground truths every other retrieval row here is
scored on -- `bench_retrieval_keyword_selfretrieval.py`'s 256 keyword
queries and `bench_retrieval_live_logs.py`'s real drafting-session
queries -- plus three things neither of those can see.

**Both arms rank papers, so a passage row has to collapse to citekeys
before recall@k means anything.** `collapse_to_citekeys` already exists
in `bench_retrieval_compare.py` for the dense-chunk rows; it is imported,
not rewritten.

**Recall goes down, and that is the finding rather than a caveat.**
Measured 2026-09-15: 0.8086 -> 0.6914 on the keyword arm and
0.8646 -> 0.7812 on the live-logs arm. A document pools every paragraph's
evidence into one score; a passage stands alone, so a paper that argues
the query diffusely across ten paragraphs is beaten by one that says it
once, emphatically. Collapsing back to citekeys cannot recover what the
smaller unit never pooled. Anyone reading these rows for "is the passage
unit better" has the wrong question -- it is a different unit, and this
is what it costs.

**What it buys is what the collapse throws away**, and this script
measures three of them directly:

- *source diversity*: distinct citekeys in the top five, swept over the
  cap at 1/2/3. The document unit is 5 of 5 by construction, so read this
  as how much of that guarantee each cap setting *recovers* -- 3.72 of 5
  at the shipped cap of 3 -- not as a gain over it. The cap defends a
  property the smaller unit gave up; it cannot create one.
- *mid-sentence text*: the fraction of returned passages that begin or
  end mid-sentence. A document-unit snippet is a character window, so it
  is cut wherever 500 characters land; a passage is a whole paragraph.
  Measured the same way on both rather than asserted of either.
- *page availability*: the fraction of hits carrying a page a reader
  could turn to. Zero for the document unit, because flattening loses it.

And it sweeps `MIN_PASSAGE_TOKENS` at 1/10/20/40, which is where that
default came from rather than a number chosen and then defended.

    .venv-full/bin/python bench/bench_retrieval_passage.py \\
        --tag 2026-09-15-retrieval-passage
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import config, retrieval, retrieval_passages  # noqa: E402
from chitragupta import retrieval_passages_cache  # noqa: E402
from bench_retrieval_compare import (  # noqa: E402
    K_REPORT,
    collapse_to_citekeys,
    ndcg_at_k,
    recall_at_k,
)

CAPS = (1, 2, 3)
FLOORS = (1, 10, 20, 40)

# A passage "ends mid-sentence" if its last non-space character is not
# terminal punctuation, and "begins mid-sentence" if its first character
# is lower-case. Crude on purpose: it is applied identically to both
# units, so what it measures is the *difference*, and a rule that
# mis-scores a heading mis-scores it on both sides.
_ENDS_CLEAN = re.compile(r"[.!?][\"')\]]*$")


def _mid_sentence(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    return bool(stripped[0].islower()) or not _ENDS_CLEAN.search(stripped)


def _pin_parser_settings() -> None:
    """Pin everything that decides what is in the index.

    The host `config.toml` is a real project's, with its own
    `[parser]` and now its own `[retrieval]`. An arm that inherited them
    would measure whatever this host happens to be set to rather than the
    shipped defaults every published figure is quoted against.
    """
    config.MAX_PASSAGES_PER_SOURCE = 3
    config.MIN_PASSAGE_TOKENS = 20


def _document_row(rows):
    """Document-unit BM25: ranked citekeys and the snippet text per query."""
    ranked, texts, pages = {}, [], []
    for row in rows:
        found = retrieval.search(row["query"], k=K_REPORT)
        ranked[_key(row)] = [r.citekey for r in found]
        texts.extend(r.snippet for r in found)
        pages.extend([False] * len(found))
    return ranked, texts, pages


def _passage_row(rows, cap: int, floor: int):
    """Passage-unit BM25 at one (cap, floor), collapsed to citekeys."""
    config.MAX_PASSAGES_PER_SOURCE = cap
    config.MIN_PASSAGE_TOKENS = floor
    retrieval_passages_cache._forget_cache()
    ranked, texts, pages, diversity = {}, [], [], []
    for row in rows:
        found = retrieval_passages.search_passages(row["query"], k=K_REPORT)
        hits = found.results
        ranked[_key(row)] = collapse_to_citekeys([{"citekey": h.citekey} for h in hits])
        texts.extend(h.text for h in hits)
        pages.extend(h.page is not None for h in hits)
        diversity.append(len({h.citekey for h in hits}))
    return ranked, texts, pages, diversity


def _key(row):
    return (row.get("chapter", ""), row.get("query_index", 0), row["query"])


def _relevant(row):
    return set(row.get("citekeys") or [row["citekey"]])


def _score(rows, ranked):
    recalls = [recall_at_k(ranked[_key(r)], _relevant(r), K_REPORT) for r in rows]
    ndcgs = [ndcg_at_k(ranked[_key(r)], _relevant(r), K_REPORT) for r in rows]
    return {
        "queries": len(rows),
        "recall@5": round(sum(recalls) / len(recalls), 4) if recalls else 0.0,
        "ndcg@5": round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else 0.0,
    }


def _text_quality(texts, pages):
    if not texts:
        return {"hits": 0, "mid_sentence": 0.0, "with_page": 0.0, "mean_chars": 0}
    return {
        "hits": len(texts),
        "mid_sentence": round(sum(_mid_sentence(t) for t in texts) / len(texts), 4),
        "with_page": round(sum(pages) / len(pages), 4),
        "mean_chars": round(sum(len(t or "") for t in texts) / len(texts)),
    }


def measure_arm(name, rows):
    """Every row this script publishes for one ground-truth arm."""
    _pin_parser_settings()
    doc_ranked, doc_texts, doc_pages = _document_row(rows)
    out = {
        "arm": name,
        "document": {**_score(rows, doc_ranked), **_text_quality(doc_texts, doc_pages)},
        "passage_by_cap": {},
        "passage_by_floor": {},
    }
    for cap in CAPS:
        ranked, texts, pages, diversity = _passage_row(rows, cap, 20)
        out["passage_by_cap"][str(cap)] = {
            **_score(rows, ranked),
            **_text_quality(texts, pages),
            "mean_distinct_sources_in_top5": round(sum(diversity) / len(diversity), 3),
        }
    for floor in FLOORS:
        ranked, _texts, _pages, _diversity = _passage_row(rows, 3, floor)
        out["passage_by_floor"][str(floor)] = _score(rows, ranked)
    _pin_parser_settings()
    return out


def self_check():
    """Fabricate a difference each aggregation here is supposed to see,
    and assert it sees it.

    Three, one per published family of numbers, because each could
    silently read a real difference as none:

    `_score` must separate a ranking that found the answer from one that
    did not -- a recall aggregator that ignored `ranked` would report the
    same figure for both and every row in this script would be the
    document row wearing a different label.

    `_mid_sentence` is the evidence-quality claim, and it is the one most
    able to lie: if it returned a constant, the passage unit would score
    a flattering 0.0 that meant nothing. It must call a window cut
    mid-sentence dirty and a whole paragraph clean.

    `collapse_to_citekeys` must actually deduplicate, or the diversity
    figure -- the number the cap exists to move -- is just the hit count.
    """
    rows = [{"query": "greenhouse humidity", "citekey": "right_2024"}]
    hit = _score(rows, {_key(rows[0]): ["right_2024", "wrong_2024"]})
    miss = _score(rows, {_key(rows[0]): ["wrong_2024", "other_2024"]})
    assert hit["recall@5"] == 1.0 and miss["recall@5"] == 0.0, (
        "_score does not separate a ranking that found the answer from one that did not"
    )
    assert hit["ndcg@5"] > miss["ndcg@5"], "_score's nDCG does not move with rank position"

    assert _mid_sentence("regulated by the incubator, and the humidity"), (
        "_mid_sentence calls a window cut mid-sentence clean -- the evidence-quality "
        "figure would report every character window as a whole paragraph"
    )
    assert not _mid_sentence("The incubator regulates humidity."), (
        "_mid_sentence calls a whole paragraph dirty"
    )
    assert _mid_sentence("   "), "_mid_sentence accepts empty text as a clean passage"

    collapsed = collapse_to_citekeys([{"citekey": "a"}, {"citekey": "a"}, {"citekey": "b"}])
    assert collapsed == ["a", "b"], (
        f"collapse_to_citekeys does not deduplicate ({collapsed}) -- the diversity "
        "figure would be the hit count"
    )

    quality = _text_quality(["The incubator regulates humidity.", "cut mid"], [True, False])
    assert quality["mid_sentence"] == 0.5 and quality["with_page"] == 0.5, (
        "_text_quality does not average over its inputs"
    )


def _live_rows(dossiers):
    """The live-logs arm's ground truth, or None with a printed reason.

    Skipped rather than fatal, and the skip is printed rather than
    inferred from a missing row: the dossiers it reads are a restored
    book's, which is per-host data. On the host this was first run, the
    book had moved out of `content/` entirely and only a dated snapshot
    under `content/backup/` still had them -- hence `--live-dossiers`.
    """
    import bench_retrieval_live_logs as live

    if dossiers:
        live.BOOK_DOSSIERS = Path(dossiers)
    try:
        rows = live.build_live_ground_truth()
    except OSError as exc:
        print(f"  [skipped] live drafting logs: {exc}")
        return None
    if not rows:
        print(f"  [skipped] live drafting logs: no chapters with logs under {live.BOOK_DOSSIERS}")
        return None
    return rows


def _ground_truths(which, dossiers):
    """The two arms, imported rather than rebuilt."""
    arms = []
    if which in ("both", "keyword"):
        from bench_retrieval_keyword_selfretrieval import build_keyword_ground_truth

        arms.append(("keyword self-retrieval", build_keyword_ground_truth()))
    if which in ("both", "live"):
        rows = _live_rows(dossiers)
        if rows:
            arms.append(("live drafting logs", rows))
    return arms


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tag", help="names bench/results/<tag>/")
    ap.add_argument("--arm", choices=("both", "keyword", "live"), default="both")
    ap.add_argument(
        "--live-dossiers",
        metavar="DIR",
        help="Where the live-logs arm reads a restored book's dossiers. Defaults to "
        "bench_retrieval_live_logs.py's own path under content/dossiers/; point it at a "
        "content/backup/<date>-content/ snapshot when the book has moved out of content/",
    )
    args = ap.parse_args(argv)

    self_check()

    results = []
    for name, rows in _ground_truths(args.arm, args.live_dossiers):
        print(f"\n{name}: {len(rows)} queries")
        measured = measure_arm(name, rows)
        results.append(measured)
        doc = measured["document"]
        print(
            f"  document  recall@5 {doc['recall@5']}  nDCG@5 {doc['ndcg@5']}  "
            f"mid-sentence {doc['mid_sentence']}  with-page {doc['with_page']}"
        )
        for cap, row in measured["passage_by_cap"].items():
            print(
                f"  passage cap={cap}  recall@5 {row['recall@5']}  nDCG@5 {row['ndcg@5']}  "
                f"mid-sentence {row['mid_sentence']}  with-page {row['with_page']}  "
                f"sources/top5 {row['mean_distinct_sources_in_top5']}"
            )
        for floor, row in measured["passage_by_floor"].items():
            print(f"  passage floor={floor}  recall@5 {row['recall@5']}  nDCG@5 {row['ndcg@5']}")

    if args.tag:
        out_dir = BENCH_DIR / "results" / args.tag
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "passage_vs_document.json"
        path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
