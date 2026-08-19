"""Retrieval ground truth for Arm B: 48 real (query, citekey) pairs,
recovered by joining bench_paraphrase_hunt.py's committed judgments back
onto their claim text.

The judgments (bench/results/2026-08-15-organic-paraphrase-hunt/labels.json)
are committed; the claim text they were judged from (pairs.json) is not
-- same "no draft/source prose in a committed result" discipline
bench_overlap_embed.py's KEPT_FIELDS already applies. Recovering it means
re-running bench_paraphrase_hunt.py --extract against the restored book,
then joining each labels.json row back to its pairs.json row by
(chapter, line, citekey).

All 48 rows are valid ground truth regardless of judgment -- "paraphrase"
vs "no-match" vs "no" describes how closely the claim restates the
source *passage*, which has no bearing on whether the citekey is the
paper that claim actually cites. It is, in every row.

**This script's own output is not committed either.** `ground_truth.json`'s
`query` field is the claim text itself -- the same drafted book prose
`pairs.json` carries and, for the reason given above, never commits. So
`ground_truth.json` is gitignored (see .gitignore's "no draft/source prose
in a committed result" entry) alongside `pairs.json`, and every downstream
task (Task 4 on) regenerates it locally via `build_ground_truth()` rather
than reading a committed copy. Only `labels.json` -- ids, chapters, lines,
citekeys, judgments, no claim text -- is committed, same as
bench_paraphrase_hunt.py's own convention.

    .venv-full/bin/python bench/bench_retrieval_ground_truth.py \\
        --drafts content/drafts/books/digital-twins-for-software-engineers \\
        --tag 2026-08-16-retrieval-ground-truth
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import config  # noqa: E402
import bench_paraphrase_hunt as hunt  # noqa: E402

LABELS_PATH = BENCH_DIR / "results" / "2026-08-15-organic-paraphrase-hunt" / "labels.json"


def build_ground_truth(drafts_dir, labels_path=LABELS_PATH):
    """Joins labels_path's judged rows to fresh claim text extracted from
    drafts_dir. Raises ValueError, naming every unresolved id, rather
    than silently returning a partial set -- a caller scoring retrieval
    quality against 40 of 48 rows without being told 8 went missing would
    read as a clean run."""
    labels = json.loads(labels_path.read_text(encoding="utf-8"))["candidates"]

    con = None  # extract() below owns its own ledger connection
    pairs_out = BENCH_DIR / "results" / "_ground_truth_extract_scratch"
    hunt.extract(drafts_dir, pairs_out)
    pairs = json.loads((pairs_out / "pairs.json").read_text(encoding="utf-8"))
    by_key = {(p["chapter"], p["line"], p["citekey"]): p["claim"] for p in pairs}

    rows, missing = [], []
    for row in labels:
        key = (row["chapter"], row["line"], row["citekey"])
        claim = by_key.get(key)
        if claim is None:
            missing.append(row["id"])
            continue
        rows.append({"chapter": row["chapter"], "line": row["line"],
                     "citekey": row["citekey"], "query": claim,
                     "judgment": row["judgment"]})

    if missing:
        raise ValueError(
            f"{len(missing)} of {len(labels)} labels.json row(s) did not resolve "
            f"against a fresh extraction: {', '.join(missing)}. The book restored "
            "from content/backup/ may not match the state labels.json was judged "
            "against -- do not proceed with a partial ground truth set."
        )
    return rows


def self_check():
    """labels.json really has 48 rows and really names real chapters --
    the two facts build_ground_truth() assumes before it ever restores
    or re-extracts anything."""
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))["candidates"]
    assert len(labels) == 48, f"expected 48 labelled rows, found {len(labels)}"
    assert all(row["chapter"].endswith(".md") for row in labels), (
        "a labels.json row's chapter field isn't a .md filename"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--drafts", required=True, help="directory of restored chapters")
    ap.add_argument("--tag", required=True, help="names bench/results/<tag>/")
    args = ap.parse_args(argv)

    self_check()
    if not config.LEDGER_PATH.exists():
        print(f"no ledger at {config.LEDGER_PATH} -- run `python -m chitragupta.corpus sync`",
              file=sys.stderr)
        return 1

    rows = build_ground_truth(args.drafts)
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "ground_truth.json"
    record.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"{len(rows)} ground-truth (query, citekey) pairs recovered")
    print(f"Record: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
