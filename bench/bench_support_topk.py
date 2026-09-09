"""What does capping `review support`'s premises per citation cost, and
what does it buy -- measured without human labels, over the real drafts?

Issue #693's remaining half. `claim_support._score_claim` sends the
entailment model one (passage, claim) pair per quotable passage of the
cited source, measured at 725-887 pairs per citation
(`docs/PERFORMANCE.md`), which is why `support` is ~97% of a nine-aid
pass on a draft with no dossier. #693 proposes pre-ranking premises
lexically and scoring only the top k. `chitragupta/config.py`'s
`SUPPORT_PREMISE_TOPK` is that mechanism, shipped off by default; this
script is what a person reads before turning it on.

## What it cannot measure, and what it measures instead

It cannot measure precision. Whether a capped score is *right* needs the
human ratings issue #757 tracks -- B9's instrument is committed and
unlabelled, and #693's cost half was gated on it. Nothing here
substitutes for that, and a reading of this script's output as "the cap
is safe" is a misreading: it is self-consistency against the uncapped
scorer, which can say a cap changes nothing and cannot say the uncapped
answer was correct.

What it measures is what a cap does *relative to today's scorer*, which
is enough to price k:

1. **Score delta.** `capped - uncapped`, per finding. Negative or zero
   by construction -- the capped premise set is a subset, so its `max`
   cannot exceed the full set's. The distribution is the headline: a cap
   whose worst delta is -0.002 has changed nothing a reader would act on.
2. **Reading-order agreement over the worst `WORST_N`.** This aid is
   *ranked, never banded* -- `claim_support.py` says so, and
   `agenda/_items_findings.py:claim_support_items` puts **every** scored
   finding on the agenda with no cutoff, worst-score-first. So there is
   no threshold for a finding to cross, and the aid's actual deliverable
   is the order a reviewer reads in. A cap that leaves the worst-N set
   intact has preserved the output; one that drops a claim out of it has
   changed which citation gets read first, which is the real harm.
3. **Argmax agreement.** Whether the same passage is reported as the
   claim's support. Secondary on purpose: with hundreds of near-duplicate
   premises per source, ties and near-ties shuffle the argmax while the
   score barely moves, so a low agreement here alongside a ~0 delta is a
   non-event rather than a finding.
4. **Pairs and seconds**, the thing being bought.

## Two measurement choices worth knowing before changing them

**In-process, not through the CLI.** Unlike `bench_review_cost.py`,
which times whole subprocesses because that is what a person waits for,
every arm here shares one loaded model. The model load is identical
across arms and would be most of a small draft's wall clock -- including
it would flatten exactly the difference being measured. The seconds
column is therefore *scoring* time and is not comparable to
`bench_review_cost.py`'s.

**k pinned per arm at the call site**, via `build_report`'s own `top_k`
parameter, never by mutating `config.SUPPORT_PREMISE_TOPK` mid-run. A
sweep that reached through the config would measure whatever the host's
`config.toml` says on every arm.

The premise universe is whatever the current sidecars hold, and #693's
whole finding is that a re-parse can move it 1.67x with the corpus
unchanged. The recorded pair count is what makes an entry comparable to
another date's; the corpus size alone is not.

    CHITRAGUPTA_PROJECT=. .venv-full/bin/python \\
        bench/bench_support_topk.py --tag 2026-09-09-support-topk
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from bench.bench_review_cost import DRAFTS, word_count  # noqa: E402
from chitragupta import config, entailment  # noqa: E402
from chitragupta.review import claim_support  # noqa: E402

# None must come first: it is the baseline every other arm is compared
# against, and it is also the most expensive, so a run that dies partway
# has still produced the number the rest are relative to.
ARMS = (None, 128, 64, 32, 16, 8)

# How deep the reading-order comparison goes. Twenty is the order of a
# review sitting rather than a tuned number -- a reviewer works down the
# worst-scoring end of the list, and a cap that reorders findings ranked
# 400th and 401st has not changed anyone's afternoon.
WORST_N = 20


class CountingEntailer:
    """The real entailer, plus a pair counter.

    Counted here rather than re-derived from the sidecars (which is what
    `bench_review_cost.entailment_pairs` does, correctly, for a run it
    cannot instrument) because this script *is* the caller: wrapping the
    seam records what the arm actually sent, so a cap that failed to
    apply shows up as an unchanged count rather than as a suspiciously
    equal set of scores.
    """

    def __init__(self, inner):
        self.inner = inner
        self.pairs = 0

    def score(self, pairs):
        pairs = list(pairs)
        self.pairs += len(pairs)
        return self.inner.score(pairs)


def arm(entailer, draft: Path, top_k) -> dict:
    """One draft at one k: the findings, the pairs sent, the seconds."""
    counter = CountingEntailer(entailer)
    started = time.perf_counter()
    report = claim_support.build_report(draft, counter, top_k)
    seconds = time.perf_counter() - started
    scored = {
        claim_support.finding_id(f.citekey, f.claim): {
            "score": f.score,
            "passage": None if f.passage is None else f.passage.text,
        }
        for f in report.findings
        if f.note is None
    }
    return {
        "top_k": top_k,
        "pairs": counter.pairs,
        "seconds": round(seconds, 2),
        "scored": scored,
    }


def worst(scored: dict, count: int) -> list:
    """The `count` worst-scoring finding ids, worst first -- the order
    `claim_support.findings` publishes and the agenda reads in. Tied
    scores break on the id so the comparison is not itself a source of
    disagreement."""
    return sorted(scored, key=lambda fid: (scored[fid]["score"], fid))[:count]


def compare(baseline: dict, capped: dict) -> dict:
    """What arm `capped` did to arm `baseline`'s output.

    Keyed on finding id and intersected: a finding present in one arm
    only cannot have a delta, and `missing` reports the count rather than
    silently dropping it. That case should not arise -- a cap changes
    which premises are scored, never which citations exist -- so a
    nonzero `missing` means something other than the cap moved.
    """
    shared = sorted(set(baseline) & set(capped))
    deltas = [capped[fid]["score"] - baseline[fid]["score"] for fid in shared]
    same_passage = sum(baseline[fid]["passage"] == capped[fid]["passage"] for fid in shared)
    base_worst, capped_worst = worst(baseline, WORST_N), worst(capped, WORST_N)
    return {
        "findings": len(shared),
        "missing": len(set(baseline) ^ set(capped)),
        "worst_delta": round(min(deltas), 4) if deltas else None,
        "median_delta": round(statistics.median(deltas), 4) if deltas else None,
        "unchanged_scores": sum(d == 0 for d in deltas),
        "argmax_agreement": round(same_passage / len(shared), 3) if shared else None,
        f"worst_{WORST_N}_kept": len(set(base_worst) & set(capped_worst)),
        f"worst_{WORST_N}_order_identical": base_worst == capped_worst,
    }


def self_check() -> None:
    """Fabricate the differences the comparison must see.

    Every arm's numbers come out of `compare`, so the failure that would
    quietly make this whole record decoration is a comparison that reads
    *identical* on inputs that differ. Three fabrications, one per column
    that could go blind, and all on synthetic findings -- no model, no
    corpus, no drafts.
    """
    base = {f"f{i}": {"score": i / 10, "passage": f"p{i}"} for i in range(10)}
    assert compare(base, base)["worst_delta"] == 0.0, (
        "a scorer compared to itself must show no delta"
    )
    assert compare(base, base)[f"worst_{WORST_N}_order_identical"], "self-comparison reordered"

    # A cap that lowered one score must be seen in the delta column, and
    # must not be averaged into invisibility: `worst_delta` is a min, so
    # one harmed finding among nine untouched ones still reports -0.5.
    lowered = dict(base, f9={"score": 0.4, "passage": "p9"})
    assert compare(base, lowered)["worst_delta"] == -0.5, compare(base, lowered)
    assert compare(base, lowered)["unchanged_scores"] == 9

    # The reading-order column is the one that matters, so it gets its
    # own fabrication: three findings, a worst-2 window, and a capped arm
    # that pushes the worst finding out of it. A set-overlap that counted
    # all three would report the order as preserved when it is not.
    small = {"a": {"score": 0.1, "passage": "x"}, "b": {"score": 0.5, "passage": "y"}}
    assert worst(small, 1) == ["a"], "the worst-scoring finding is not sorting first"
    assert worst(dict(small, a={"score": 0.9, "passage": "x"}), 1) == ["b"], (
        "a rescored finding did not move in the reading order, so this column "
        "cannot detect a cap that changes what a reviewer reads first"
    )

    # A passage swap at an unchanged score has to stay visible as its own
    # column: it is the difference this script deliberately calls a
    # non-event, and a reader can only discount it if it is reported.
    swapped = dict(base, f3={"score": 0.3, "passage": "other"})
    assert compare(base, swapped)["worst_delta"] == 0.0
    assert compare(base, swapped)["argmax_agreement"] == 0.9, compare(base, swapped)


def _print_row(draft: str, words: int, base: dict, arms: list) -> None:
    print(f"\n{draft}  ({words:,} words, {base['pairs']:,} pairs uncapped)")
    print(
        f"{'k':>5} {'pairs':>9} {'cut':>6} {'sec':>7} {'worst d':>8} {'argmax':>7} {'worst20':>8}"
    )
    for row in arms:
        cut = f"{base['pairs'] / row['pairs']:.1f}x" if row["pairs"] else "-"
        cmp = row["vs_uncapped"]
        print(
            f"{str(row['top_k']):>5} {row['pairs']:>9,} {cut:>6} {row['seconds']:>7.1f} "
            f"{str(cmp['worst_delta']):>8} {str(cmp['argmax_agreement']):>7} "
            f"{cmp[f'worst_{WORST_N}_kept']:>5}/{WORST_N}"
        )


def sweep(entailer, draft: Path) -> "list | None":
    """Every arm over one draft, baseline first. None when the draft has
    nothing for the entailer to score, which is not a result."""
    rows = []
    for top_k in ARMS:
        row = arm(entailer, draft, top_k)
        if not row["scored"]:
            print(f"skipping {draft.name}: no scored finding to compare")
            return None
        row["vs_uncapped"] = compare(rows[0]["scored"], row["scored"]) if rows else None
        rows.append(row)
    rows[0]["vs_uncapped"] = compare(rows[0]["scored"], rows[0]["scored"])
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    parser.add_argument(
        "--drafts",
        type=int,
        default=len(DRAFTS),
        help="how many of bench_review_cost.py's five drafts to sweep, "
        "smallest-first as listed there (default: all)",
    )
    args = parser.parse_args(argv)
    self_check()

    entailer, reason = entailment.open_entailer()
    if entailer is None:
        print(f"not run -- {reason}", file=sys.stderr)
        return 0

    results = []
    for relative in DRAFTS[: args.drafts]:
        draft = config.CONTENT_DIR / relative
        if not draft.exists():
            print(f"skipping {relative}: not present in this content directory")
            continue
        rows = sweep(entailer, draft)
        if rows is None:
            continue
        words = word_count(draft)
        _print_row(relative, words, rows[0], rows[1:])
        # The per-finding scores are dropped from what is written: they
        # are claim-keyed material out of the real drafts, the reason
        # bench_claim_support.py gitignores its own candidates.md.
        results.append(
            {
                "draft": relative,
                "words": words,
                "arms": [{k: v for k, v in row.items() if k != "scored"} for row in rows],
            }
        )

    out = REPO / "bench" / "results" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    written = out / "support_topk.json"
    written.write_text(
        json.dumps({"entailment_model": config.ENTAILMENT_MODEL, "drafts": results}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
