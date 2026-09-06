"""The rating instrument for claim support -- built, unlabelled, on purpose.

`bench/RESULTS.md`'s 2026-08-27 entry read 40 findings from the two ends
of the score distribution and reported a qualitative pattern. It says in
its own standing row that no labelled separation statistic was produced,
and the paper's Evaluation section repeats that the aid's precision is
unknown. #610 (B9) says what would close it, and the protocol it names --
from Isik & Guleryuzlu 2026, the roadmap's H12 -- is not the one that
entry used:

- a **stratified** sample, equal n per score quintile, at least 30 per
  stratum, rather than the two ends;
- **three raters**, not one;
- raters **blind to the score**, and the presentation order
  **randomised**, so the score cannot leak through position;
- Fleiss' kappa, pairwise Cohen's kappa, Spearman rho between score and
  majority label, and the separation statistic.

**This script builds that instrument and stops.** It writes a
rater-facing sheet with the scores withheld, a key that maps the shuffled
ids back to their findings, and an empty `ratings.json` per rater. It
computes no statistic and publishes no number, because there is nothing
to compute one from: the labels do not exist, and a machine that produced
them would be scoring the aid against itself. That is the whole argument
#610 makes against an LLM-as-judge here, and it applies to this script's
author too.

Once three humans have filled their `ratings.json`, `--score` reports the
four statistics above. Until then it says what is missing and exits
nonzero.

Reuses `bench_claim_support.py`'s `_population()` for the findings, so
the sample is drawn from exactly the pool that script scores, and the ids
are the ones its own `labels.json` would use.

Needs the "enrich" Poetry group (the entailment model), a synced corpus
and the four real drafts.

    CHITRAGUPTA_PROJECT=. .venv-full/bin/python \\
        bench/bench_claim_support_labelling.py --build \\
        --drafts content/drafts/digital-twins-for-software-engineers \\
        --tag 2026-09-04-claim-support-labelling
"""

import argparse
import itertools
import json
import random
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(BENCH_DIR))

import bench_claim_support as support  # noqa: E402

STRATA = 5
PER_STRATUM = 30
RATERS = ("rater-a", "rater-b", "rater-c")
JUDGMENTS = ("supported", "unsupported", "unclear")


def quintiles(pool: list) -> list:
    """`pool` split into `STRATA` equal-count bands by score, lowest band
    first.

    Equal *count*, not equal score width: the scores are not uniformly
    distributed, and equal-width bands would put almost every finding in
    one band and leave the others below the 30 the protocol requires.
    """
    ordered = sorted(pool, key=lambda row: row["score"])
    size = len(ordered) / STRATA if ordered else 0
    return [ordered[int(round(i * size)) : int(round((i + 1) * size))] for i in range(STRATA)]


def draw_sample(pool: list, per_stratum: int, seed: int) -> list:
    """`per_stratum` findings from each quintile, or the whole quintile
    when it holds fewer -- reported either way, never silently topped up
    from a neighbouring band, which would stop the sample being
    stratified at all."""
    rng = random.Random(seed)
    drawn = []
    for index, band in enumerate(quintiles(pool)):
        chosen = band if len(band) <= per_stratum else rng.sample(band, per_stratum)
        for row in chosen:
            drawn.append({**row, "stratum": index})
    return drawn


def shuffled_order(sample: list, seed: int) -> list:
    """The presentation order, randomised across strata.

    Randomised *across* strata rather than within them: a rater shown
    all thirty low-scoring findings together would infer the score from
    the run of similar material, which is exactly the leak blinding is
    supposed to close.
    """
    order = list(range(len(sample)))
    random.Random(seed + 1).shuffle(order)
    return order


def fleiss_kappa(ratings: list) -> "float | None":
    """Fleiss' kappa over `[[count per category] per item]`.

    None when every rater gave every item the same category: agreement
    is total, chance agreement is also total, and the ratio is 0/0.
    Reporting 1.0 there would claim a measured agreement that the data
    cannot distinguish from a rater who pressed one key throughout.
    """
    if not ratings:
        return None
    n_raters = sum(ratings[0])
    if n_raters < 2:
        return None
    items = len(ratings)
    proportions = [
        sum(row[category] for row in ratings) / (items * n_raters)
        for category in range(len(ratings[0]))
    ]
    observed = (
        sum(
            (sum(count * (count - 1) for count in row) / (n_raters * (n_raters - 1)))
            for row in ratings
        )
        / items
    )
    expected = sum(p * p for p in proportions)
    if expected == 1.0:
        return None
    return round((observed - expected) / (1 - expected), 4)


def cohen_kappa(first: list, second: list) -> "float | None":
    """Pairwise Cohen's kappa between two raters' category lists."""
    if not first or len(first) != len(second):
        return None
    categories = sorted(set(first) | set(second))
    observed = sum(1 for a, b in zip(first, second) if a == b) / len(first)
    expected = sum(
        (first.count(c) / len(first)) * (second.count(c) / len(second)) for c in categories
    )
    if expected == 1.0:
        return None
    return round((observed - expected) / (1 - expected), 4)


def spearman(scores: list, ranks: list) -> "float | None":
    """Spearman rho between the aid's score and the majority label's
    rank, on the tie-corrected Pearson-of-ranks definition."""
    if len(scores) < 2:
        return None
    try:
        return round(statistics.correlation(_ranked(scores), _ranked(ranks)), 4)
    except statistics.StatisticsError:
        return None


def _ranked(values: list) -> list:
    """Average ranks, ties shared -- what makes the correlation above
    Spearman's rather than Pearson's on raw values."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def self_check() -> None:
    """Fabricate the agreements each statistic must see.

    Perfect agreement across a mixed set is 1.0. The second fixture is
    the one that matters: three raters who split 1-2 on every item agree
    with each other 33% of the time, and a kappa that forgot to subtract
    chance agreement would publish that 0.33 as modest agreement. Chance
    agreement on that marginal distribution is 0.56, so the honest
    answer is **negative** -- worse than guessing. Pinning -0.5 rather
    than "some number below zero" is what makes the check catch a
    correction applied in the wrong direction as well as one omitted.
    """
    perfect = [[3, 0, 0], [0, 3, 0], [3, 0, 0], [0, 3, 0]]
    assert fleiss_kappa(perfect) == 1.0, fleiss_kappa(perfect)
    split = [[1, 2, 0], [1, 2, 0], [1, 2, 0], [1, 2, 0]]
    assert fleiss_kappa(split) == -0.5, fleiss_kappa(split)
    assert fleiss_kappa([[3, 0], [3, 0]]) is None, "unanimity on one category is not measurable"
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "b", "a", "b"], ["b", "a", "b", "a"]) == -1.0
    assert spearman([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    # A stratified draw must not top a short band up from its neighbour.
    pool = [{"score": i / 10} for i in range(10)]
    bands = quintiles(pool)
    assert [len(b) for b in bands] == [2, 2, 2, 2, 2], [len(b) for b in bands]
    drawn = draw_sample(pool, 1, seed=1)
    assert sorted(row["stratum"] for row in drawn) == [0, 1, 2, 3, 4], drawn


def _sheet(sample: list, order: list) -> str:
    """The rater-facing document. Carries the claim, the citekey and the
    matched passage -- and **not** the score, the stratum or the draft's
    position, which are what the rater must not see."""
    lines = [
        "# Claim-support rating sheet",
        "",
        "Read each item and judge whether the cited passage supports the",
        "claim. Record one of `supported`, `unsupported`, `unclear` per item",
        "in your own `ratings-<you>.json`. You are rating the *claim against",
        "the passage*, not the writing.",
        "",
        "The aid's score is deliberately absent, and the order is shuffled.",
        "Do not consult `key.json` -- it exists to join your ratings back",
        "afterwards, and reading it un-blinds the rating.",
        "",
    ]
    for position, index in enumerate(order):
        row = sample[index]
        lines += [
            f"## item {position}",
            "",
            f"**Claim.** {row['claim']}",
            "",
            f"**Cited source.** `{row['citekey']}`"
            + (f", page {row['page']}" if row.get("page") else ""),
            "",
            "**Matched passage.**",
            "",
            "> " + (row.get("passage") or "(no passage matched)").replace("\n", "\n> "),
            "",
        ]
    return "\n".join(lines)


def build(drafts_dir: Path, out_dir: Path, per_stratum: int, seed: int) -> dict:
    from chitragupta import entailment

    entailer = entailment.Entailer()
    # `_population` walks `bench_claim_support.DRAFT_NAMES`, the four
    # example reports. Those hold 71 scored findings between them --
    # fewer than B9's protocol needs for a *single* stratum, let alone
    # five. Pointing the same function at every chapter of a directory
    # is the one change that makes the sample size reachable, and it is
    # done by naming the files rather than by reimplementing the pool:
    # the ids, the scoring and the collision handling all stay
    # `bench_claim_support.py`'s.
    names = tuple(sorted(p.name for p in drafts_dir.glob("*.md")))
    if not names:
        raise SystemExit(f"no .md chapters under {drafts_dir}")
    saved = support.DRAFT_NAMES
    support.DRAFT_NAMES = names
    try:
        pool, per_draft, _unscoreable, missing, duplicates = support._population(
            drafts_dir, entailer
        )
    finally:
        support.DRAFT_NAMES = saved
    sample = draw_sample(pool, per_stratum, seed)
    order = shuffled_order(sample, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sheet.md").write_text(_sheet(sample, order), encoding="utf-8")
    (out_dir / "key.json").write_text(
        json.dumps(
            {
                "protocol": {
                    "strata": STRATA,
                    "per_stratum_target": per_stratum,
                    "raters": list(RATERS),
                    "judgments": list(JUDGMENTS),
                    "blind": "scores and strata withheld from sheet.md",
                    "order_seed": seed,
                },
                "items": [
                    {"position": position, **sample[index]} for position, index in enumerate(order)
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for rater in RATERS:
        path = out_dir / f"ratings-{rater}.json"
        if not path.exists():
            path.write_text(
                json.dumps(
                    {
                        "rater": rater,
                        "ratings": [
                            {"position": position, "judgment": None}
                            for position in range(len(sample))
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    return {
        "pool": len(pool),
        "sample": len(sample),
        "per_stratum": [sum(1 for r in sample if r["stratum"] == i) for i in range(STRATA)],
        "per_draft": {k: v[1] for k, v in per_draft.items()},
        "missing_drafts": missing,
        "id_collisions": duplicates,
    }


def score(out_dir: Path) -> int:
    """The four statistics, once three humans have filled their sheets."""
    key = json.loads((out_dir / "key.json").read_text(encoding="utf-8"))
    filled, empty = {}, []
    for rater in RATERS:
        path = out_dir / f"ratings-{rater}.json"
        rows = json.loads(path.read_text(encoding="utf-8"))["ratings"] if path.exists() else []
        judged = {r["position"]: r["judgment"] for r in rows if r.get("judgment")}
        if len(judged) < len(key["items"]):
            empty.append(f"{path.name}: {len(judged)}/{len(key['items'])} rated")
        filled[rater] = judged
    if empty:
        print("Not rated yet -- no statistic is computed or published:")
        for line in empty:
            print(f"  {line}")
        return 1

    positions = [item["position"] for item in key["items"]]
    counts = [
        [sum(1 for r in RATERS if filled[r][p] == judgment) for judgment in JUDGMENTS]
        for p in positions
    ]
    majority = [JUDGMENTS[row.index(max(row))] for row in counts]
    scores = [item["score"] for item in key["items"]]
    result = {
        "n_items": len(positions),
        "fleiss_kappa": fleiss_kappa(counts),
        "cohen_kappa": {
            f"{a}|{b}": cohen_kappa(
                [filled[a][p] for p in positions], [filled[b][p] for p in positions]
            )
            for a, b in itertools.combinations(RATERS, 2)
        },
        "spearman_score_vs_majority": spearman(
            scores, [JUDGMENTS.index(label) for label in majority]
        ),
        "median_score_supported": _median_for(scores, majority, "supported"),
        "median_score_unsupported": _median_for(scores, majority, "unsupported"),
    }
    (out_dir / "labelling.json").write_text(json.dumps(result, indent=2), "utf-8")
    print(json.dumps(result, indent=2))
    return 0


def _median_for(scores: list, majority: list, judgment: str) -> "float | None":
    chosen = [s for s, label in zip(scores, majority) if label == judgment]
    return round(statistics.median(chosen), 4) if chosen else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    parser.add_argument("--drafts", help="directory of drafts (required with --build)")
    parser.add_argument("--build", action="store_true", help="draw the sample and write the sheet")
    parser.add_argument("--score", action="store_true", help="score filled rating sheets")
    parser.add_argument("--per-stratum", type=int, default=PER_STRATUM)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    self_check()

    out_dir = REPO / "bench" / "results" / args.tag
    if args.score:
        return score(out_dir)
    if not args.build or not args.drafts:
        parser.error("give --build with --drafts, or --score")
    summary = build(Path(args.drafts), out_dir, args.per_stratum, args.seed)
    print(json.dumps(summary, indent=2))
    print(
        f"\nwrote {out_dir / 'sheet.md'}, {out_dir / 'key.json'} and one empty "
        f"ratings file per rater.\nNo statistic is computed until three humans "
        f"have filled them in; run --score then."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
