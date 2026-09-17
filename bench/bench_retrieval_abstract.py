"""Four ways of letting a paper's abstract choose which *passages* the
drafting layer is shown (#772's neighbourhood), scored on both BM25
ground truths.

`[retrieval].weight_abstract` (#762) is the one mechanism this repository
has for using an abstract in retrieval, and it is measured to do nothing:
recall unchanged at every weight on the live-logged arm, a monotone loss
on the self-retrieval one, with the field populated for 318 of 642 items
so it is not a coverage artefact (bench/RESULTS.md, 2026-09-15). That arm
weights an abstract's terms inside a *document*'s bag of words, where a
173-word abstract is 3% of a 5,500-token document and BM25's saturation
has already flattened most of what it added.

The passage unit (#769) is where the question is live again, and it is a
different question. There the ranked object is one paragraph, so an
abstract can act on *selection* rather than on a document's score:
deciding which paragraphs of which papers a drafting skill is handed.
Field weights are inert there by construction -- a passage entry carries
no `field_freqs` -- so none of the arms below is reachable by turning a
`[retrieval]` dial, and all four are new mechanisms rather than settings.

**The four arms, and what each one believes.**

- `prior` -- the paper's abstract score is fused into every one of its
  passages' scores, min-max normalized within the query's own pool and
  convex-combined at `lambda` (the calibration `bench_retrieval_fusion.py`
  documents, reused rather than re-invented). Believes the passage unit
  gave up too much: it dropped the document-level pooling that made a
  diffusely-argued paper findable, and an abstract is the cheapest way to
  put a little of it back.
- `shortlist` -- abstracts rank the papers, the top `N` become the only
  papers whose passages may be returned. Believes the abstract is a good
  *filter* and a poor *scorer*: it says what a paper is about, and the
  paragraph should still be chosen on its own words.
- `centrality` -- a passage is lifted by how much of its own vocabulary
  its own abstract shares, independent of the query. Believes a paragraph
  that restates the paper's thesis is better evidence than one down a
  side-alley, and that the abstract is the only query-independent
  statement of that thesis the corpus already has.
- `exclude-abstract` -- passages that are themselves part of the abstract
  are dropped from the results. Believes the opposite of all three: that
  an abstract is a *summary*, and handing a drafting skill the summary
  when it asked for evidence is the failure, not the feature.

The first three can only help recall by pooling, which is what #769
deliberately stopped doing; the fourth can only cost it. Running all four
is what makes the answer an answer rather than a preference.

**Scored by collapsing to citekeys**, like every other passage row here
(`bench_retrieval_passage.py`'s docstring has the argument): both ground
truths judge papers, so a passage arm has to say which paper it found
before recall@5 means anything. `exclude-abstract` is therefore measured
on two things it can move -- the ranking, and how often an abstract
passage was being returned at all.

**One BM25 pass per query, not one per arm.** Every arm is a transform of
the same two score dicts (passages, abstracts), so they are computed once
and re-ranked thirteen ways. A 48,887-entry passage index at ~0.24s a
query makes the naive shape an hour where this is two minutes.

Stdlib only, no GPU, no venv beyond what the ground truths need.

    CONFIG_PATH=<config> python3 bench/bench_retrieval_abstract.py \\
        --tag 2026-09-17-abstract-passage-selection \\
        --live-dossiers content/backup/<date>-content/dossiers/books/<book>
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(BENCH_DIR))

from chitragupta import (  # noqa: E402
    _abstract,
    ledger,
    passages,
    retrieval,
    retrieval_cache,
    retrieval_passages,
    retrieval_passages_cache,
    retrieval_scoring,
)
from bench_retrieval_compare import K_REPORT, ndcg_at_k, recall_at_k  # noqa: E402
from bench_retrieval_passage import _ground_truths, _key, _pin_parser_settings, _relevant  # noqa: E402

# One arm at a time, geometric rather than fine -- the question is "does
# this mechanism help at all", not "what is its optimum", and a fine grid
# over a few hundred queries reads noise (bench/RESULTS.md's "Power,
# stated plainly").
PRIOR_LAMBDAS = (0.1, 0.25, 0.5, 0.75)
SHORTLIST_SIZES = (10, 25, 50, 100)
# Extended past 1.0 after the first run peaked *at* 1.0: a maximum
# sitting on a grid boundary is not a maximum, it is an unswept
# direction, and reporting it as one is how a bench publishes the
# edge of its own table as a finding.
CENTRALITY_MUS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)


def abstract_index(items):
    """One BM25 entry per item whose sidecar yields an abstract.

    Deliberately a *separate* index rather than a field on the document
    one. A field weight adds an abstract's counts to a document already
    5,500 tokens long and lets BM25 normalize by that length, which is
    exactly the mechanism #762 measured as inert. Here the abstract is
    the whole document: `avgdl` is ~177 words, so a two-term match in a
    173-word abstract saturates where the same match in a full paper does
    not. Whatever these arms measure, they are not re-measuring #762.
    """
    index = {}
    for item in items:
        found = passages.corpus_passages(item["citekey"])
        text = _abstract.extract_from(found) if found else None
        if not text:
            continue
        tokens = list(retrieval._tokenize(text))
        if not tokens:
            continue
        freqs = {}
        for token in tokens:
            freqs[token] = freqs.get(token, 0) + 1
        index[item["citekey"]] = {"term_freqs": freqs, "length": len(tokens)}
    return index


def abstract_spans(items):
    """`{citekey: {passage_index, ...}}` -- which passages are the
    abstract's own text.

    Matched on text rather than on a label, because there is no
    `abstract` label to match: Docling's `DocItemLabel` has no such
    member, which `_abstract.py`'s docstring names as the first thing a
    reader assumes and the reason its openers are matched on their words.
    `extract_from` joins its body with single spaces, so a passage that
    contributed to it appears verbatim inside it.
    """
    spans = {}
    for item in items:
        citekey = item["citekey"]
        found = passages.corpus_passages(citekey)
        text = _abstract.extract_from(found) if found else None
        if not text:
            continue
        spans[citekey] = {
            i for i, p in enumerate(found) if p.text and _is_abstract_text(p.text, text)
        }
    return spans


def _is_abstract_text(passage_text, abstract):
    """Whether `passage_text` is one of the paragraphs `abstract` was
    built from.

    Whole-string containment alone under-counts, and the miss is
    systematic rather than rare: `_abstract._opener` strips the literal
    `Abstract` marker off the first paragraph before it goes into the
    body (`_INLINE.sub`), so the one passage most certain to be abstract
    text is the one that fails an exact match. The tail is checked as
    well for that reason -- a marker is only ever a prefix. 60 characters
    is long enough not to collide across a 4,600-word document and short
    enough to survive the shortest genuine opener measured here.
    """
    stripped = passage_text.strip()
    if len(stripped) <= 40:
        return False
    return stripped in abstract or stripped[-60:] in abstract


def _normalized(scores):
    """`scores` min-max normalized into [0, 1] within this query's own
    pool -- `bench_retrieval_fusion.convex_fuse`'s calibration, which is
    the house convention for combining two BM25 routes whose raw scores
    are on different scales (different `N`, different `avgdl`, different
    IDF). Reproduced rather than imported because that function also
    inverts a dense *distance*, which no arm here has."""
    if not scores:
        return {}
    top = max(scores.values()) or 1.0
    return {key: value / top for key, value in scores.items()}


def rank_baseline(passage_scores, _abstract_scores, _spans):
    return sorted(passage_scores.items(), key=lambda kv: (-kv[1], kv[0]))


def rank_prior(passage_scores, abstract_scores, lam):
    """Every passage lifted by its own paper's abstract score."""
    p_norm = _normalized(passage_scores)
    a_norm = _normalized(abstract_scores)
    fused = {
        key: (1 - lam) * value + lam * a_norm.get(key[0], 0.0) for key, value in p_norm.items()
    }
    return sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))


def rank_shortlist(passage_scores, abstract_scores, size):
    """Passages restricted to the top-`size` papers by abstract score.

    A paper with no abstract cannot be shortlisted and so cannot be
    returned. That is the arm's real cost rather than an implementation
    detail -- 318 of 642 items have one — and it is why the record below
    carries `reachable`, the share of each ground truth's own correct
    answers that any shortlist arm could still find.
    """
    shortlist = {
        citekey
        for citekey, _ in sorted(abstract_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:size]
    }
    kept = {key: value for key, value in passage_scores.items() if key[0] in shortlist}
    return sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))


def rank_centrality(passage_scores, overlap, mu):
    """Query-independent lift by a passage's overlap with its own
    abstract. Multiplicative rather than additive: it is a statement
    about a passage's standing within its paper, and adding it would let
    a high-centrality passage of an irrelevant paper outrank a
    query-matching one."""
    lifted = {
        key: value * (1.0 + mu * overlap.get(key, 0.0)) for key, value in passage_scores.items()
    }
    return sorted(lifted.items(), key=lambda kv: (-kv[1], kv[0]))


def rank_excluding_abstract(passage_scores, _abstract_scores, spans):
    kept = {
        key: value
        for key, value in passage_scores.items()
        if key[1] not in spans.get(key[0], frozenset())
    }
    return sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))


def _collapsed(ranked, k=K_REPORT):
    """Top-`k` capped passages, as a de-duplicated ranked citekey list.

    `retrieval_passages._capped` is the shipped cap, imported rather than
    re-implemented: an arm that quietly let one paper take all five slots
    would beat the baseline on recall by a rule the product does not use.
    """
    seen, out = set(), []
    for (citekey, _i), _score in retrieval_passages._capped(ranked, k):
        if citekey not in seen:
            seen.add(citekey)
            out.append(citekey)
    return out


def _abstract_share(ranked, spans, k=K_REPORT):
    """Share of the top-`k` returned passages that are the abstract's own
    text -- what `exclude-abstract` is removing, measured on the arms
    that do not remove it."""
    top = retrieval_passages._capped(ranked, k)
    if not top:
        return 0.0
    hits = sum(1 for (citekey, i), _ in top if i in spans.get(citekey, frozenset()))
    return hits / len(top)


def per_query_scores(rows, index, a_index):
    """`(passage_scores, abstract_scores)` per query, computed once."""
    out = {}
    for row in rows:
        terms = retrieval_passages._query_terms(row["query"])
        if not terms:
            out[_key(row)] = ({}, {})
            continue
        out[_key(row)] = (
            retrieval_scoring.bm25_scores(index, terms),
            retrieval_scoring.bm25_scores(a_index, terms),
        )
    return out


def centrality_overlap(index, a_index_texts):
    """`{(citekey, i): share of this passage's distinct terms that its own
    abstract also uses}`. Computed from the index's own term counts, so
    it costs no second tokenization."""
    overlap = {}
    for key, entry in index.items():
        abstract_terms = a_index_texts.get(key[0])
        if not abstract_terms:
            continue
        terms = set(entry["term_freqs"])
        if not terms:
            continue
        overlap[key] = len(terms & abstract_terms) / len(terms)
    return overlap


def measure(rows, index, a_index, spans, overlap):
    """Every arm's row for one ground truth."""
    scored = per_query_scores(rows, index, a_index)
    a_terms = {citekey: set(entry["term_freqs"]) for citekey, entry in a_index.items()}
    del a_terms

    arms = [("passage baseline (as shipped)", rank_baseline, None)]
    arms += [(f"+ abstract prior, lambda={lam}", rank_prior, lam) for lam in PRIOR_LAMBDAS]
    arms += [(f"abstract shortlist, N={n}", rank_shortlist, n) for n in SHORTLIST_SIZES]
    arms += [(f"x abstract centrality, mu={mu}", rank_centrality, mu) for mu in CENTRALITY_MUS]
    arms += [("exclude abstract passages", rank_excluding_abstract, None)]

    out = []
    for name, fn, param in arms:
        recalls, ndcgs, shares = [], [], []
        for row in rows:
            passage_scores, abstract_scores = scored[_key(row)]
            if fn is rank_centrality:
                ranked = fn(passage_scores, overlap, param)
            elif param is None:
                ranked = fn(passage_scores, abstract_scores, spans)
            else:
                ranked = fn(passage_scores, abstract_scores, param)
            citekeys = _collapsed(ranked)
            recalls.append(recall_at_k(citekeys, _relevant(row), K_REPORT))
            ndcgs.append(ndcg_at_k(citekeys, _relevant(row), K_REPORT))
            shares.append(_abstract_share(ranked, spans))
        out.append(
            {
                "row": name,
                "queries": len(rows),
                "recall@5": round(sum(recalls) / len(recalls), 4),
                "ndcg@5": round(sum(ndcgs) / len(ndcgs), 4),
                "abstract_share@5": round(sum(shares) / len(shares), 4),
            }
        )
    return out


def reachable_share(rows, a_index):
    """Share of each ground truth's correct answers that has an abstract
    at all -- the ceiling every `shortlist` arm is measured against."""
    total = hit = 0
    for row in rows:
        for citekey in _relevant(row):
            total += 1
            hit += citekey in a_index
    return round(hit / total, 4) if total else 0.0


def rank_documents_full_text(doc_scores, _abstract_scores, _has_abstract):
    return [c for c, _ in sorted(doc_scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def rank_documents_abstract_only(_doc_scores, abstract_scores, _has_abstract):
    return [c for c, _ in sorted(abstract_scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def rank_documents_abstract_first(doc_scores, abstract_scores, has_abstract):
    """Papers with an abstract ranked by it, then every other paper ranked
    by full-text BM25 -- the two-tier shape that answers "what about the
    papers with no abstract" by demoting rather than dropping them.

    **It cannot change a top-5, and that is structural rather than
    measured.** The first tier is every paper that has an abstract -- 318
    of 642 on this corpus -- so the second tier begins at rank 319 and no
    `k` a caller would ask for reaches it. The rows below therefore tie
    `abstract-only` exactly, and a reader should not read that tie as
    "the fallback did not help": it was never consulted. Making it
    consultable means interleaving the two rankings by score, which needs
    the per-query calibration `_normalized` exists for -- the two BM25
    routes have different `N`, different `avgdl` and different IDF, so
    their raw scores are not comparable. That is a different arm, and an
    honest one to build; it is not this one.
    """
    ranked = [c for c, _ in sorted(abstract_scores.items(), key=lambda kv: (-kv[1], kv[0]))]
    rest = [
        c
        for c, _ in sorted(doc_scores.items(), key=lambda kv: (-kv[1], kv[0]))
        if c not in has_abstract
    ]
    return ranked + rest


DOCUMENT_RANKERS = (
    ("full-text BM25 (as shipped)", rank_documents_full_text),
    ("abstract-only BM25, no fallback", rank_documents_abstract_only),
    ("abstract-first, full-text fallback", rank_documents_abstract_first),
)


def document_ranker_rows(rows, doc_index, a_index):
    """Can an abstract *replace* full text as the paper ranker?

    A different question from the four passage arms above, and the one to
    ask before any of them: those modify a ranking, this substitutes for
    it. Reported over all queries and over the subset whose own correct
    answer has an abstract -- the second isolates "is an abstract a good
    enough representation of a paper" from "do enough papers have one",
    which the first confounds and which no single number can separate.
    """
    has_abstract = set(a_index)
    scored = {}
    for row in rows:
        terms = retrieval._query_terms(row["query"])
        scored[_key(row)] = (
            retrieval_scoring.bm25_scores(doc_index, terms),
            retrieval_scoring.bm25_scores(a_index, terms),
        )
    subset = [r for r in rows if any(c in has_abstract for c in _relevant(r))]
    out = []
    for label, queries in (("all queries", rows), ("answer has an abstract", subset)):
        for name, fn in DOCUMENT_RANKERS:
            recalls, ndcgs = [], []
            for row in queries:
                ranked = fn(*scored[_key(row)], has_abstract)
                recalls.append(recall_at_k(ranked, _relevant(row), K_REPORT))
                ndcgs.append(ndcg_at_k(ranked, _relevant(row), K_REPORT))
            out.append(
                {
                    "subset": label,
                    "row": name,
                    "queries": len(queries),
                    "recall@5": round(sum(recalls) / len(recalls), 4),
                    "ndcg@5": round(sum(ndcgs) / len(ndcgs), 4),
                }
            )
    return out


def self_check():
    """Fabricate a difference each arm must see, per bench/README.md.

    Four hand-built cases, one per mechanism, because an arm that silently
    does nothing publishes a row identical to the baseline -- and a table
    of thirteen rows that all tie reads as "the abstract does not help"
    when it means "the harness never applied it".
    """
    scores = {("a", 0): 1.0, ("b", 0): 0.9}
    abstracts = {"b": 10.0, "a": 1.0}

    ranked = rank_prior(scores, abstracts, 0.75)
    assert [key for key, _ in ranked][0] == ("b", 0), (
        f"a strong abstract must promote b above a at lambda=0.75: {ranked}"
    )
    assert [key for key, _ in rank_prior(scores, abstracts, 0.0)][0] == ("a", 0), (
        "lambda=0 must reproduce the baseline order exactly"
    )

    ranked = rank_shortlist(scores, abstracts, 1)
    assert [key for key, _ in ranked] == [("b", 0)], (
        f"a shortlist of 1 must drop every passage of the unlisted paper: {ranked}"
    )

    overlap = {("a", 0): 0.0, ("b", 0): 1.0}
    ranked = rank_centrality(scores, overlap, 1.0)
    assert [key for key, _ in ranked][0] == ("b", 0), (
        f"full abstract overlap must promote b at mu=1.0: {ranked}"
    )
    assert [key for key, _ in rank_centrality(scores, overlap, 0.0)][0] == ("a", 0), (
        "mu=0 must reproduce the baseline order exactly"
    )

    ranked = rank_excluding_abstract(scores, abstracts, {"a": {0}})
    assert [key for key, _ in ranked] == [("b", 0)], (
        f"an abstract passage must not survive the exclude arm: {ranked}"
    )

    assert _normalized({"x": 4.0, "y": 2.0}) == {"x": 1.0, "y": 0.5}, (
        "min-max normalization must map the pool maximum to 1.0"
    )

    # The document rankers, and in particular the claim the entry rests
    # on: the fallback tier is unreachable at any k below the size of the
    # first tier. Asserted rather than described, because "these two rows
    # tie" is exactly what a broken fallback also looks like.
    doc = {"has": 1.0, "none": 9.0}
    abstracts = {"has": 1.0}
    ranked = rank_documents_abstract_first(doc, abstracts, {"has"})
    assert ranked == ["has", "none"], (
        f"a paper with no abstract must sit below every paper with one, "
        f"however high its full-text score: {ranked}"
    )
    assert ranked[:1] == rank_documents_abstract_only(doc, abstracts, {"has"})[:1], (
        "within the first tier's length, abstract-first must equal abstract-only -- "
        "the tie the entry reports is this identity, not a null result"
    )
    assert rank_documents_full_text(doc, abstracts, {"has"}) == ["none", "has"], (
        "the full-text ranker must ignore abstracts entirely"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tag", help="names bench/results/<tag>/")
    ap.add_argument("--arm", choices=("both", "keyword", "live"), default="both")
    ap.add_argument("--live-dossiers", metavar="DIR", help="see bench_retrieval_passage.py")
    args = ap.parse_args(argv)

    self_check()
    if not args.tag:
        print("--tag is required", file=sys.stderr)
        return 2

    _pin_parser_settings()
    retrieval_passages_cache._forget_cache()
    with ledger.connection() as con:
        items = ledger.all_items(con)
    index, without_sidecar = retrieval_passages_cache.load_index(items)
    a_index = abstract_index(items)
    spans = abstract_spans(items)
    a_terms = {citekey: set(entry["term_freqs"]) for citekey, entry in a_index.items()}
    overlap = centrality_overlap(index, a_terms)
    print(
        f"{len(index)} passages ({without_sidecar} sources without a sidecar); "
        f"{len(a_index)} of {len(items)} items have an abstract; "
        f"{sum(len(s) for s in spans.values())} passages are abstract text",
        flush=True,
    )

    doc_index = retrieval_cache._load_index(items, retrieval._tokenize_item)

    record = {"arms": []}
    for name, rows in _ground_truths(args.arm, args.live_dossiers):
        print(f"\n{name}: {len(rows)} queries", flush=True)
        reach = reachable_share(rows, a_index)
        rankers = document_ranker_rows(rows, doc_index, a_index)
        print("\n  -- can an abstract replace full text as the paper ranker?")
        print(f"  {'subset':22} {'ranker':36} {'recall@5':>9} {'ndcg@5':>8}")
        for entry in rankers:
            print(
                f"  {entry['subset']:22} {entry['row']:36} "
                f"{entry['recall@5']:>9} {entry['ndcg@5']:>8}"
            )
        table = measure(rows, index, a_index, spans, overlap)
        print(f"  correct answers that have an abstract at all: {reach:.4f}")
        print(f"\n  {'row':38} {'recall@5':>9} {'ndcg@5':>8} {'abs@5':>7}")
        for entry in table:
            print(
                f"  {entry['row']:38} {entry['recall@5']:>9} "
                f"{entry['ndcg@5']:>8} {entry['abstract_share@5']:>7}"
            )
        record["arms"].append({"arm": name, "reachable": reach, "rankers": rankers, "rows": table})

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "abstract_passage_selection.json"
    path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"\nRecord: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
