"""What query-side acronym expansion (#789) does to retrieval on this
corpus -- recall *and* precision, over every ground truth this host can
build, plus a derived set that isolates the case the issue is about.

`chitragupta/retrieval_expansion.py` adds an acronym's expansion to a
query's terms when `[retrieval].acronym_expansion` is on, so that a query
saying `DT` can reach a paper that spells "digital twin" out and never
writes the abbreviation. Expansion *adds matches*, so it is the change
most likely to cost precision, and #789 asks for both numbers before any
default moves.

**Two arms per vocabulary -- off and on -- because the setting is a
switch.** It was a weight for one revision of this branch, and the sweep
that decided otherwise ran from this script: 0.25, 0.5 and 1.0 of the
weight a typed term carries, with full weight ahead on every figure it
moved (8 queries better against 2 worse, against 6/1 and 1/0 below it).
A dial whose only supported setting is its maximum is not a dial, so the
setting became boolean and the sub-weight arms left with it -- scoring
them now would need a weighted ranker `chitragupta/` no longer has, i.e.
a re-implementation, which is what every arm here is written to avoid.
Those figures are in `results/2026-09-17-acronym-expansion/
acronym_expansion_weight_sweep.json`, and RESULTS.md reads them out; they
are not reproducible from this script as it now stands, which is the
honest cost of having simplified what ships.

**The headline is a null result on the shipped vocabulary, and it is the
whole reason the feature ships off.** The vendored
`assets/style/acronyms.toml` is five general-computing entries (PDF, CPU,
URL, API, HTML). Zero of this host's 256 self-retrieval queries and zero
of its 96 live-logged queries contain one, so the vendored arms move
nothing -- not "a small gain", *nothing*, and `affected` is 0 rows rather
than a mean over rows where nothing happened. A number that cannot move
cannot support turning a default on.

**So the domain arm is a stand-in and is labelled as one.** The
vocabulary a user of this pipeline actually has is their own
`[style].acronyms` file, which is per-host data no measurement here can
stand in for. `DOMAIN_VOCABULARY` below is read off the real 15-chapter
digital-twin book's own glossary (`content/backup/20260901-content/
dossiers/books/digital-twins-for-software-engineers/*/scope.md`) -- eight
acronyms this project's own drafting actually defined. It is written into
this script as a literal, like every arm here and in
`bench_retrieval_token_floor.py`: a vocabulary derived at run time would
make a published figure depend on a per-host file that is free to change
under it. **Nothing in `chitragupta/` reads it** -- the shipped path
reads `acronyms.load_vocabulary()` and nothing else, which is the
argument #789 uses to prefer this vocabulary over #771's topic model.

**Three ground truths, because the two existing ones cannot see this.**
Both are built from text that spells the term out *and* abbreviates it:
an author keyword list reads "Digital twin (DT), DT modeling", and a
drafting session types "digital twin fidelity". Expansion adds nothing to
a query that already contains the expansion's words -- deliberately, so
a typed word is never demoted -- so both sets are near-inert even on the
domain vocabulary. The third set, `acronym-only`, is the self-retrieval
set with each expansion phrase rewritten to its acronym: same corpus,
same correct answer, and the query a reader who works in acronyms would
actually type. It is **derived, not observed**, and no figure from it
should be read as evidence about real queries -- it is evidence about the
mechanism, which is the thing the other two sets cannot supply.

**Why the unaffected rows are a real control here**, unlike in the token
floor entry. This is query-side only: no document is re-tokenized, no
`length` moves, and IDF is read from `term_freqs` alone, so a query that
gains no term cannot move by even a float. `self_check` pins that, and it
is what makes "the affected subset" the whole story rather than half of
it.

**Precision is rank quality, not precision@k**, for the reason the
stemming and token-floor entries give: the self-retrieval set has exactly
one relevant document per query, so precision@5 there is recall@5 / 5.
What expansion risks is junk *above* the right answer, which shows as
recall@1, MRR@5 and nDCG@5 moving differently from recall@5, and as the
mean document frequency of a query's terms rising -- "digital" and "twin"
are in far more documents of this corpus than "DT" is.

**Never touches `content/retrieval_index.json`.** The index is built in
memory and, unlike the token-floor arms, is shared by every arm here --
it is the same index in all of them, which is the property being
measured.

Stdlib-only, no GPU, reads this host's real corpus read-only:

    cp config.toml.example config.toml   # worktree only; gitignored data
    CONTENT_DIR=/workspace/content \\
      BIB_FILE=/workspace/papers/bibliography.bib \\
      BENCH_BOOK_DOSSIERS=/workspace/content/backup/20260901-content/dossiers/books/digital-twins-for-software-engineers \\
      .venv-full/bin/python bench/bench_retrieval_acronym_expansion.py --tag <tag>

`BENCH_BOOK_DOSSIERS` is what the live-logged set needs where the book
has left `content/dossiers/` (`bench_retrieval_live_logs.py`); without
it that set reports as unavailable by name rather than as a zero.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import (  # noqa: E402
    acronyms,
    config,
    ledger,
    retrieval,
    retrieval_expansion,
    retrieval_scoring,
)
from bench_retrieval_compare import ndcg_at_k, recall_at_k, with_field_weights  # noqa: E402
from bench_retrieval_keyword_selfretrieval import build_keyword_ground_truth  # noqa: E402
from bench_retrieval_live_logs import build_live_ground_truth  # noqa: E402

K_REPORT = 5

BASELINE = "expansion off (baseline, as shipped)"

# The vendored vocabulary, written out rather than read, so a published
# figure keeps naming the table it was computed from. `self_check`
# compares it against `assets/style/acronyms.toml` and fails if they have
# parted -- an edit to that file is a reason to re-measure, not a reason
# for this script to quietly measure something else.
VENDORED_VOCABULARY = {
    "PDF": "Portable Document Format",
    "CPU": "Central Processing Unit",
    "URL": "Uniform Resource Locator",
    "API": "Application Programming Interface",
    "HTML": "HyperText Markup Language",
}

# A stand-in for the per-host `[style].acronyms` file this project cannot
# ship, read off the real book's own glossary -- see the module docstring
# for the provenance and for why it is a literal. Every one of these is a
# term this project's own drafting defined in prose; none is invented for
# the benchmark, and none reaches `chitragupta/`.
DOMAIN_VOCABULARY = {
    "DT": "digital twin",
    "PT": "physical twin",
    "DM": "digital model",
    "DS": "digital shadow",
    "DES": "discrete-event simulation",
    "RTF": "real-time factor",
    "ROM": "reduced-order model",
    "UQ": "uncertainty quantification",
}

VOCABULARIES = {"vendored": VENDORED_VOCABULARY, "domain": DOMAIN_VOCABULARY}

ARMS = {BASELINE: None}
for _name, _vocabulary in VOCABULARIES.items():
    ARMS[f"{_name} vocabulary, expansion on"] = _vocabulary


def arm_expansion(query, vocabulary):
    """`(terms, added)` for one arm, through the shipped code path.

    The arm is the *configuration*, never a re-implementation: this pins
    `config.ACRONYM_EXPANSION` and `acronyms.load_vocabulary` and then
    calls `retrieval_expansion.expand` itself, so a change to the shipped
    expansion rule moves these figures instead of silently leaving them
    describing code that no longer runs. The query rule is
    `retrieval._query_terms`, not `_tokenize` -- the two differ on
    interrogatives, and measuring an arm through the document rule is a
    mistake this project has made before and caught in a fourth decimal.
    """
    terms = retrieval._query_terms(query)
    if vocabulary is None:
        return terms, []
    original_vocabulary, original_switch = acronyms.load_vocabulary, config.ACRONYM_EXPANSION
    acronyms.load_vocabulary = lambda: dict(vocabulary)
    config.ACRONYM_EXPANSION = True
    try:
        added = retrieval_expansion.expand(terms, retrieval._tokenize)
    finally:
        acronyms.load_vocabulary = original_vocabulary
        config.ACRONYM_EXPANSION = original_switch
    return terms, added


def build_index(items):
    """The per-document entry `retrieval._tokenize_item` produces, in
    memory, for the shipped tokenizer.

    One index for every arm, which is the point rather than an
    optimisation: expansion is query-side, so an arm that needed its own
    index would not be this feature. `field_freqs` is carried because
    `retrieval_scoring.weighted_freq` reads a missing one as "this
    document's title matched nothing"; the weights themselves are pinned
    to 1.0 in `main`.
    """
    index = {}
    for item in items:
        tokens = retrieval._tokenize(retrieval._full_text(item))
        index[item["citekey"]] = {
            "length": len(tokens),
            "term_freqs": dict(Counter(tokens)),
            "field_freqs": retrieval_scoring.field_freqs(item, retrieval._tokenize),
        }
    return index


def mrr(ranked_citekeys, relevant):
    """Reciprocal rank of the first relevant hit, 0.0 if none is ranked.

    Published as `mrr@5`: every caller passes a list already cut to
    `K_REPORT`, so a right answer at rank 9 scores 0.0 exactly as one
    never ranked does. Same definition as the token-floor entry's, so the
    two tables can be read against each other.
    """
    for position, citekey in enumerate(ranked_citekeys, start=1):
        if citekey in relevant:
            return 1.0 / position
    return 0.0


def mean_doc_frequency(index, terms):
    """Mean number of documents containing one of `terms`.

    The mechanism behind a precision loss rather than a symptom of it. An
    expansion trades a rare term for common ones -- "DT" appears in far
    fewer documents of this corpus than "digital" does -- so a rise here
    without a recall gain is what "the added words bought nothing and
    cost specificity" looks like before it shows up in a rank.
    """
    if not terms:
        return 0.0
    counts = [sum(1 for entry in index.values() if entry["term_freqs"].get(t)) for t in set(terms)]
    return sum(counts) / len(counts)


def _figures(rows):
    """The five published figures for a list of per-query records."""
    if not rows:
        return None
    n = len(rows)
    return {
        "n_queries": n,
        "recall@1": round(sum(r["recall@1"] for r in rows) / n, 4),
        f"recall@{K_REPORT}": round(sum(r["recall@k"] for r in rows) / n, 4),
        f"mrr@{K_REPORT}": round(sum(r["rr"] for r in rows) / n, 4),
        f"ndcg@{K_REPORT}": round(sum(r["ndcg"] for r in rows) / n, 4),
        "mean_query_term_df": round(sum(r["df"] for r in rows) / n, 1),
    }


def score_arm(label, index, ground_truth):
    """One arm's row, its ranking per query, and its per-query records.

    A ground-truth row is `{"key", "query", "relevant"}` -- `relevant` a
    set, so one scorer serves the self-retrieval set's single correct
    paper and the live-logged set's whole kept-citekey set.

    `affected` is computed here rather than passed in, because unlike a
    tokenizer change this one is visible directly: a row is affected when
    *this arm* added at least one term to it. The baseline's affected set
    is empty by construction, so its subset figures are `None` rather
    than a zero -- "no query could move" and "every query scored zero"
    are different findings.
    """
    vocabulary = ARMS[label]
    per_query, ranked_by_key, affected, added_terms = [], {}, set(), Counter()
    for row in ground_truth:
        terms, added = arm_expansion(row["query"], vocabulary)
        if added:
            affected.add(row["key"])
            added_terms.update(token for _acronym, token in added)
        scored_terms = terms + [token for _acronym, token in added]
        scores = retrieval_scoring.bm25_scores(index, scored_terms)
        ranked = [c for c, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]
        ranked = ranked[:K_REPORT]
        ranked_by_key[row["key"]] = ranked
        per_query.append(
            {
                "key": row["key"],
                "recall@1": recall_at_k(ranked, row["relevant"], 1),
                "recall@k": recall_at_k(ranked, row["relevant"], K_REPORT),
                "rr": mrr(ranked, row["relevant"]),
                "ndcg": ndcg_at_k(ranked, row["relevant"], K_REPORT),
                "df": mean_doc_frequency(index, scored_terms),
            }
        )
    row = {
        "row": label,
        **_figures(per_query),
        "queries_expanded": len(affected),
        "terms_added": sum(added_terms.values()),
        "most_added": [t for t, _ in added_terms.most_common(5)],
    }
    row["affected"] = _figures([r for r in per_query if r["key"] in affected])
    return row, ranked_by_key, per_query, affected


def per_query_movement(before, after, ground_truth, affected):
    """How many queries the arm helped, hurt and left alone, by the rank
    of their own correct answer.

    A mean can hide a swap -- four found and four lost reports as no
    movement -- and on a set where 9 rows of 256 can even move, the mean
    is almost all the unaffected rows. These counts are what it cannot
    say.

    Counted over the whole set *and* over `affected`, as the token-floor
    entry does, but with the opposite expectation: there, an unaffected
    query could still move because every document's length had changed;
    here it cannot move at all, and a `better`/`worse` outside `affected`
    means this script is measuring something other than what it claims.
    `self_check` asserts that, so the whole-set counts are a guard rather
    than a second result.
    """

    def split(rows):
        better, worse, same = [], [], 0
        for row in rows:
            before_rr = mrr(before.get(row["key"], []), row["relevant"])
            after_rr = mrr(after.get(row["key"], []), row["relevant"])
            if after_rr > before_rr:
                better.append(row["key"])
            elif after_rr < before_rr:
                worse.append(row["key"])
            else:
                same += 1
        return better, worse, same

    better, worse, same = split(ground_truth)
    sub_better, sub_worse, sub_same = split([r for r in ground_truth if r["key"] in affected])
    return {
        "better": [str(k) for k in better],
        "worse": [str(k) for k in worse],
        "unchanged": same,
        "expanded": len(affected),
        "affected_better": [str(k) for k in sub_better],
        "affected_worse": [str(k) for k in sub_worse],
        "affected_unchanged": sub_same,
    }


def self_retrieval_rows():
    """The author-keyword rows, in this script's row shape.

    Biased *against* expansion showing anything, which is the opposite of
    this set's bias in the token-floor entry and has to be read that way:
    a keyword list that contains an acronym almost always contains its
    expansion too ("Digital twin (DT), DT modeling"), and expansion never
    re-adds a word the query already has. The set is therefore a strong
    control -- if expansion hurts here, it hurts for free -- and a weak
    detector.
    """
    return [
        {"key": row["citekey"], "query": row["query"], "relevant": {row["citekey"]}}
        for row in build_keyword_ground_truth()
    ]


def live_logged_rows():
    """The real drafting-session queries, in this script's row shape.

    Neither query nor answer was produced by any tokenizer: a person
    typed the query into `search` while writing a chapter, and the
    relevant set is what that chapter kept. The one set here that is
    evidence about *use*, and the one that says how often a real query
    even contains an abbreviation.
    """
    return [
        {
            "key": f"{row['chapter']}#{row['query_index']}",
            "query": row["query"],
            "relevant": set(row["citekeys"]),
        }
        for row in build_live_ground_truth()
    ]


def acronymise(query, vocabulary=None):
    """`query` with every expansion phrase rewritten to its acronym.

    "Digital twin (DT), DT modeling, digital twin network" becomes
    "DT, DT modeling, DT network". Longest phrase first, so an entry
    whose expansion contains another's ("digital twin" inside nothing
    here, but "real-time factor" against a future "real-time") cannot be
    half-rewritten; the parenthetical is dropped first so the rewrite
    does not produce "DT (DT)".

    Case-insensitive on the phrase and exact on the words, because an
    author's keyword list capitalises inconsistently -- "Digital twin",
    "digital twin" and "Digital Twin" all appear in this corpus's
    `keywords` fields.
    """
    vocabulary = DOMAIN_VOCABULARY if vocabulary is None else vocabulary
    rewritten = query
    for acronym in vocabulary:
        rewritten = rewritten.replace(f"({acronym})", " ")
    for acronym, expansion in sorted(vocabulary.items(), key=lambda kv: -len(kv[1])):
        lowered = rewritten.lower()
        phrase = expansion.lower()
        start, pieces, cursor = lowered.find(phrase), [], 0
        while start != -1:
            pieces.append(rewritten[cursor:start] + acronym)
            cursor = start + len(phrase)
            start = lowered.find(phrase, cursor)
        if pieces:
            rewritten = "".join(pieces) + rewritten[cursor:]
    # Dropping "(DT)" leaves a space in front of the comma that followed
    # it, and the keyword sets are read by eye as well as tokenized.
    return " ".join(rewritten.split()).replace(" ,", ",").replace(" .", ".")


def acronym_only_rows():
    """The self-retrieval rows whose query names a domain expansion, with
    that expansion rewritten to its acronym.

    **Derived, not observed.** No person typed these. What they isolate is
    the one situation #789 is about and the observed sets cannot show: a
    query that carries the abbreviation *alone*, against a corpus whose
    papers mostly spell the term out. Read as evidence about the
    mechanism and its cost, never as evidence about real queries -- the
    live-logged set is the only one here that is that, and it is the set
    where nothing happens.

    Rows whose query is unchanged by the rewrite are dropped: they are
    the self-retrieval set again, already scored above, and keeping them
    would dilute every figure by the ratio of the two sets.
    """
    rows = []
    for row in build_keyword_ground_truth():
        rewritten = acronymise(row["query"])
        if rewritten != " ".join(row["query"].split()):
            rows.append(
                {
                    "key": row["citekey"],
                    "query": rewritten,
                    "relevant": {row["citekey"]},
                }
            )
    return rows


GROUND_TRUTHS = {
    "self-retrieval": self_retrieval_rows,
    "live-logged": live_logged_rows,
    "acronym-only (derived)": acronym_only_rows,
}


def self_check():
    """A fabricated difference this script's own comparison must see.

    Two papers: one that spells "digital twin" out and never writes the
    abbreviation, and a decoy about something else. The baseline must
    rank *nothing* for the query "DT" -- BM25 is exact match and no
    document here contains that string -- and every domain arm must rank
    the first paper first. A vendored arm must stay at the baseline, on
    this fixture as on the real corpus, since none of its five acronyms
    appears anywhere in it.

    What it cannot see: whether the real ground truths were built from
    the data they name. Those scripts carry their own self-checks, and
    re-running them against a fixture here would only prove a fixture
    parses.
    """
    assert mrr(["a", "b", "c"], {"b"}) == 0.5, "relevant at rank 2 is a reciprocal rank of 1/2"
    assert mrr(["a", "b"], {"z"}) == 0.0, "no relevant item anywhere must be 0, not an error"

    # The pinned vendored table is the shipped one. A drift here is a
    # reason to re-measure and re-pin, not a reason to keep publishing a
    # figure about a table that has changed underneath it.
    assert VENDORED_VOCABULARY == acronyms._load(config.ACRONYMS_DEFAULT_PATH), (
        "assets/style/acronyms.toml has changed since these figures were measured -- "
        "re-run this script and update VENDORED_VOCABULARY"
    )
    # The arm has to be the shipped rule and nothing else. `_query_terms`
    # drops interrogatives where `_tokenize` does not, and an arm built
    # on the wrong one measures a query nobody ran.
    terms, added = arm_expansion("what is DT fidelity", DOMAIN_VOCABULARY)
    assert terms == ["dt", "fidelity"], f"the arm is not using the shipped query rule: {terms}"
    assert added == [("dt", "digital"), ("dt", "twin")], f"the arm expanded nothing: {added}"
    assert arm_expansion("DT fidelity", None)[1] == [], "the baseline arm expanded something"
    # A query that already spells the term out gains nothing -- the
    # property that makes both observed ground truths near-inert, and the
    # reason the derived set exists.
    assert arm_expansion("digital twin DT", DOMAIN_VOCABULARY)[1] == [], (
        "a word the caller typed was added again, and would rank at the expansion weight"
    )

    assert acronymise("Digital twin (DT), digital twin network") == "DT, DT network", acronymise(
        "Digital twin (DT), digital twin network"
    )
    assert acronymise("soil moisture sensing") == "soil moisture sensing", (
        "a query naming no expansion must come back unchanged, so the derived set "
        "cannot silently inherit rows the rewrite did nothing to"
    )

    fake_items = [
        {
            "citekey": "spelled_2024",
            "title": "A digital twin of a greenhouse, digital twin calibration",
            "parsed_path": None,
            "status": "parsed",
        },
        {
            "citekey": "decoy_2024",
            "title": "unrelated work on soil moisture sensors",
            "parsed_path": None,
            "status": "parsed",
        },
    ]
    query = [
        {"key": "spelled_2024", "query": "DT", "relevant": {"spelled_2024"}},
        {"key": "decoy_query", "query": "soil moisture", "relevant": {"decoy_2024"}},
    ]
    index = build_index(fake_items)
    scored, movements = _score(index, query, "fixture", verbose=False)
    rows = {row["row"]: row for row in scored}
    assert rows[BASELINE][f"recall@{K_REPORT}"] == 0.5, (
        "the baseline found the paper that never writes 'DT', or missed the decoy's "
        "ordinary terms -- either way the 'before' arm is not the shipped ranker"
    )
    assert rows[BASELINE]["affected"] is None, "the baseline arm expanded a query"
    for label, vocabulary in ARMS.items():
        if label == BASELINE:
            continue
        expected = 1.0 if vocabulary is DOMAIN_VOCABULARY else 0.5
        assert rows[label][f"recall@{K_REPORT}"] == expected, (
            f"{label} scored {rows[label][f'recall@{K_REPORT}']} where {expected} was "
            f"the arm's whole claim"
        )
    for movement in movements:
        if "domain" in movement["arm"]:
            assert movement["affected_better"] == ["spelled_2024"], (
                f"per_query_movement did not see {movement['arm']}'s fabricated win: {movement}"
            )
        else:
            assert not movement["better"] and not movement["worse"], (
                f"a vendored arm moved a fixture containing none of its acronyms: {movement}"
            )
        # The control this feature gets and a tokenizer change does not:
        # no document was re-tokenized, so a query that gained no term
        # cannot move by even a float.
        assert set(movement["better"]) <= set(movement["affected_better"]), (
            f"{movement['arm']} moved a query it added no term to -- expansion is "
            f"query-side, so that is impossible unless the index differs per arm"
        )
        assert set(movement["worse"]) <= set(movement["affected_worse"]), (
            f"{movement['arm']} moved a query it added no term to: {movement}"
        )

    assert mean_doc_frequency(index, ["soil", "moisture"]) == 1.0, (
        "both terms sit in exactly one of the two fixture documents"
    )


def _score(index, ground_truth, name, verbose=True):
    """Every arm scored over one ground truth, plus each arm's movement
    against the baseline.

    `verbose=False` is for `self_check`, whose two-document fixture would
    otherwise print seven rows of ones and zeroes above the real run.
    """
    rows, movements, rankings, per_query, affected = [], [], {}, {}, {}
    for label in ARMS:
        row, ranked, records, keys = score_arm(label, index, ground_truth)
        row["ground_truth"] = name
        rows.append(row)
        rankings[label], per_query[label], affected[label] = ranked, records, keys
    for label in ARMS:
        if label == BASELINE:
            continue
        # The "before" on this arm's own affected rows, taken from the
        # baseline's records rather than re-scored, so it is the same
        # arithmetic the whole-set row was built from. `None` where the
        # arm expanded nothing at all, which is every vendored arm here.
        row = next(r for r in rows if r["row"] == label)
        row["baseline_affected"] = _figures(
            [r for r in per_query[BASELINE] if r["key"] in affected[label]]
        )
        movement = per_query_movement(
            rankings[BASELINE], rankings[label], ground_truth, affected[label]
        )
        movement.update(arm=label, ground_truth=name)
        movements.append(movement)
        if verbose:
            print(
                f"  {label}: {len(movement['better'])} better, "
                f"{len(movement['worse'])} worse, {movement['unchanged']} unchanged "
                f"over all {len(ground_truth)}; {movement['expanded']} query/ies "
                f"expanded, of which {len(movement['affected_better'])} better and "
                f"{len(movement['affected_worse'])} worse",
                flush=True,
            )
    if verbose:
        for row in rows:
            print(f"  {row}", flush=True)
    return rows, movements


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="results/<tag>/ to write the record into")
    parser.add_argument(
        "--only",
        choices=sorted(GROUND_TRUTHS),
        help="Score against one ground truth rather than all three. The "
        "live-logged set needs a book's dossiers on disk -- set "
        "BENCH_BOOK_DOSSIERS (bench_retrieval_live_logs.py) to a "
        "content/backup snapshot where the live ones have gone",
    )
    parser.add_argument("--self-check", action="store_true", help="Run the self-check and stop")
    args = parser.parse_args(argv)

    self_check()
    if args.self_check:
        print("self-check passed")
        return 0
    if not args.tag:
        print("--tag is required", file=sys.stderr)
        return 2

    # Every `[retrieval]` field weight pinned, not just read: an arm that
    # inherited this host's config.toml would measure whatever it happens
    # to say, which is the class of bug `repro_check.py` exists for. The
    # expansion switch is pinned per arm in `arm_expansion`, including for
    # the baseline, which this host's config.toml now turns on by default.
    with_field_weights({})
    config.ACRONYM_EXPANSION = False

    with ledger.connection() as con:
        items = ledger.all_items(con)
    print(f"building the index over {len(items)} ledger items...", flush=True)
    index = build_index(items)

    rows, movements = [], []
    for name in sorted(GROUND_TRUTHS):
        if args.only and name != args.only:
            continue
        try:
            ground_truth = GROUND_TRUTHS[name]()
        except OSError as exc:
            print(f"{name}: ground truth unavailable -- {exc}", file=sys.stderr)
            return 2
        if not ground_truth:
            print(
                f"{name}: no ground-truth rows -- check CONTENT_DIR, BIB_FILE and "
                "BENCH_BOOK_DOSSIERS",
                file=sys.stderr,
            )
            return 2
        print(f"\n{name}: {len(ground_truth)} queries", flush=True)
        set_rows, set_movements = _score(index, ground_truth, name)
        rows.extend(set_rows)
        movements.extend(set_movements)

    record = {
        "rows": rows,
        "movements": movements,
        "vocabularies": {name: dict(v) for name, v in VOCABULARIES.items()},
    }
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "acronym_expansion.json"
    out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"\nRecord: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
