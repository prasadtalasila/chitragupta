"""What does one review pass cost, at the current version, over all ten aids?

`docs/PERFORMANCE.md` prices nine aids over five real drafts, measured
2026-08-27 at 6.53. Two things have happened since: #538 and #548 changed
what `verbatim`'s tier 3 does, R4 was rewritten around an identity-based
accept test, and `union` -- the tenth aid -- has never been timed at all.
That table says so itself ("priced properly when there is a real
assembled book to price it against"). #610 (B11) is that re-timing, with
`union` included and a real assembled book to run it against.

Deliberately the **same five drafts** as the 2026-08-27 run, named by
path rather than picked by size, so the two tables are comparable row by
row. They span 1,258 to 18,061 words, two without a dossier and three
with -- the split that matters, because `verbatim`'s tier 3 is off
without one.

Every aid is timed through its **real CLI**, one subprocess per
measurement, at `--formats md`. That includes the interpreter start and
every model load the aid does, because that is what a person waiting for
a review pass actually waits for. A per-aid median over `--repeats`
runs, since a single timing on a shared host is noise.

Needs the "enrich" Poetry group, a synced corpus, `content/chroma/` and
the drafts' own dossiers -- the same five things `verbatim` tier 3 needs.
Aids that cannot run report their exit status rather than a time.

    CHITRAGUPTA_PROJECT=. .venv-full/bin/python \\
        bench/bench_review_cost.py --tag 2026-09-04-review-cost
"""

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta import config  # noqa: E402

# The 2026-08-27 five, in the order that table lists them. Relative to
# CONTENT_DIR so a differently-rooted project still resolves them.
DRAFTS = (
    "drafts/digital-twins-for-software-engineers/deep-research.md",
    "drafts/digital-twins-for-software-engineers/survey.md",
    "drafts/book-chapters/digital-twin-platforms/digital-twin-platforms.md",
    "drafts/books/digital-twins-for-software-engineers/03-anatomy-of-a-twin.md",
    "drafts/books/digital-twins-for-software-engineers/07-should-you-trust-the-twin.md",
)
# The nine per-draft aids, in the column order docs/PERFORMANCE.md uses.
# `union` is not among them: it takes an assembled document, not a draft,
# and is timed separately below.
DRAFT_AIDS = (
    "provenance",
    "verbatim",
    "coverage",
    "synthesis",
    "figure",
    "uncited",
    "quotation",
    "agenda",
    "support",
)
ASSEMBLIES = ("drafts/books/digital-twins-for-software-engineers/book.tex",)

# Two aids do not take a bare draft path. `verbatim` dispatches on a
# mode, and `scan` -- the whole-draft, whole-corpus scan -- is the one
# the 2026-08-27 table's `verbatim` column prices. `coverage` requires at
# least one retrieval query; a single fixed query is used for every row
# so the column is internally comparable, at the cost of not being
# comparable to a run that used a draft's own dossier queries.
COVERAGE_QUERY = "digital twin"
AID_ARGV = {
    "verbatim": (lambda draft: ["verbatim", "scan", str(draft)]),
    "coverage": (lambda draft: ["coverage", str(draft), "--query", COVERAGE_QUERY]),
}


def median_ms(samples: list) -> "float | None":
    """Median of the timings that succeeded, in milliseconds.

    Median rather than mean because a shared host produces occasional
    outliers an order of magnitude out, and one of those would move a
    mean far enough to change which aid the table names as dominant.
    """
    usable = [s for s in samples if s is not None]
    return round(statistics.median(usable), 1) if usable else None


def word_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").split())


def has_dossier(draft: Path) -> bool:
    """Whether this draft has the dossier `verbatim`'s tier 3 needs --
    the column docs/PERFORMANCE.md prints beside the word count, because
    it and not draft length is what moves the row total."""
    relative = draft.relative_to(config.CONTENT_DIR / "drafts")
    return (config.CONTENT_DIR / "dossiers" / relative.with_suffix("")).is_dir()


def time_aid(aid: str, draft: Path, repeats: int) -> dict:
    """One aid over one draft, `repeats` times, through the real CLI."""
    samples, failures = [], []
    for _ in range(repeats):
        started = time.perf_counter()
        argv = AID_ARGV.get(aid, lambda d: [aid, str(d)])(draft)
        completed = subprocess.run(
            [sys.executable, "-m", "chitragupta.review", *argv, "--formats", "md"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO),
        )
        elapsed = (time.perf_counter() - started) * 1000
        if completed.returncode == 0:
            samples.append(elapsed)
        else:
            # A nonzero exit is recorded, never averaged in: an aid that
            # refused in 200ms would otherwise read as the cheapest one
            # in the table.
            failures.append({"returncode": completed.returncode, "stderr": completed.stderr[-300:]})
    return {"aid": aid, "ms": median_ms(samples), "runs": len(samples), "failures": failures}


def self_check() -> None:
    """Fabricate a difference the aggregation must see.

    The failure this guards is the one that would quietly invert the
    table's conclusion: counting a *refusal* as a fast run. A refused
    aid contributes no sample, so its cell must be None -- not 0.0, and
    not the median of the runs that did work if none did.
    """
    assert median_ms([100.0, 300.0, 200.0]) == 200.0, median_ms([100.0, 300.0, 200.0])
    # One wild outlier must not move the median the way it moves a mean.
    assert median_ms([100.0, 110.0, 9000.0]) == 110.0, median_ms([100.0, 110.0, 9000.0])
    assert median_ms([]) is None, "an aid that never ran must report no time at all"
    assert median_ms([None, None]) is None, "refusals are not timings"


def _print_table(rows: list) -> None:
    header = f"{'words':>6} {'dossier':>7} " + " ".join(f"{a[:9]:>9}" for a in DRAFT_AIDS)
    print("\n" + header + f" {'all nine':>9}")
    for row in rows:
        cells = " ".join(
            f"{('-' if row['aids'][a]['ms'] is None else int(row['aids'][a]['ms'])):>9}"
            for a in DRAFT_AIDS
        )
        total = sum(row["aids"][a]["ms"] or 0 for a in DRAFT_AIDS)
        print(f"{row['words']:>6} {'yes' if row['dossier'] else 'no':>7} {cells} {int(total):>9}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    parser.add_argument("--repeats", type=int, default=3, help="runs per cell (default: 3)")
    args = parser.parse_args(argv)
    self_check()

    rows = []
    for relative in DRAFTS:
        draft = config.CONTENT_DIR / relative
        if not draft.exists():
            print(f"skipping {relative}: not present in this content directory")
            continue
        row = {
            "draft": relative,
            "words": word_count(draft),
            "dossier": has_dossier(draft),
            "aids": {},
        }
        for aid in DRAFT_AIDS:
            row["aids"][aid] = time_aid(aid, draft, args.repeats)
            cell = row["aids"][aid]
            print(f"  {relative.split('/')[-1]:34} {aid:11} {cell['ms']}ms", flush=True)
        rows.append(row)
    _print_table(rows)

    union_rows = []
    for relative in ASSEMBLIES:
        assembly = config.CONTENT_DIR / relative
        if not assembly.exists():
            print(f"\nunion: no assembled document at {relative}; not timed")
            continue
        timing = time_aid("union", assembly, args.repeats)
        union_rows.append({"assembly": relative, **timing})
        print(f"\nunion over {relative}: {timing['ms']}ms ({timing['runs']} clean runs)")

    out_dir = REPO / "bench" / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"repeats": args.repeats, "drafts": rows, "union": union_rows}
    (out_dir / "review_cost.json").write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"\nwrote {out_dir / 'review_cost.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
