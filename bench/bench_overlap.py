"""Wall-clock cost of `src/review/verbatim_check.py`'s `overlap` and `scan`
modes (src/overlap_index.py, #110/#111), against a real draft and a
real corpus.

Unlike `bench_drift.py`, this never copies the ledger: `src/overlap_index.py`
opens it through a read-only URI (`sqlite3.connect(f"file:...?mode=ro")`),
never `ledger.connect()` (a write connection that runs migrations), so
timing a scan against this host's own `content/ledger.sqlite` in place is
safe -- there is nothing here for a migration to touch. `OVERLAP_DIR` is
still redirected to a throwaway directory, so a run never writes the
host's real `content/overlap/` cache.

Measures the ongoing-relevant comparison: N invocations of `overlap` (one
per citekey the draft cites -- what a reviewer running the old workflow by
hand does today) versus one `scan` call, cold and warm corpus index. It
does not reproduce the historical pdftotext-subprocess baseline `overlap`
had before #110 -- that code no longer exists on `main`; reproduce it by
checking out the commit before #110 merged (18f9f4b2) and timing
`cmd_overlap` from `src/review/verbatim_check.py` there instead.

    python3 bench/bench_overlap.py --draft path/to/draft.md
    python3 bench/bench_overlap.py --draft path/to/draft.md --out bench/results/<date>-overlap/overlap.json

Stdlib only, like the module it measures -- runs under bare `python`.
"""

import argparse
import json
import shutil
import sys
import tempfile
import time
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src import citation_gate, config  # noqa: E402


def _timed(fn, *a, **kw):
    buf = StringIO()
    start = time.perf_counter()
    with redirect_stdout(buf):
        fn(*a, **kw)
    return time.perf_counter() - start, buf.getvalue()


def run(draft: Path) -> dict:
    from src.review import verbatim_check as vc

    citekeys = sorted({key for _, key in citation_gate.extract_citekeys(draft.read_text())})
    if not citekeys:
        print(f"{draft} cites no one -- nothing to compare overlap against.", file=sys.stderr)
        return {"citekeys": [], "draft": str(draft)}

    # First pass builds each cited document's .fpr cache (cold); the
    # per-document cache then persists on disk exactly as it would across
    # real invocations of this review aid, so the second pass is the
    # representative, steady-state number -- discard the first.
    for citekey in citekeys:
        _timed(vc.cmd_overlap, str(draft), citekey, 8)
    overlap_warm = 0.0
    for citekey in citekeys:
        elapsed, _ = _timed(vc.cmd_overlap, str(draft), citekey, 8)
        overlap_warm += elapsed

    scan_cold, cold_out = _timed(vc.cmd_scan, str(draft))
    scan_warm, warm_out = _timed(vc.cmd_scan, str(draft))
    findings = warm_out.count("tier=exact")

    return {
        "draft": str(draft),
        "citekeys": citekeys,
        "overlap_n_invocations_warm_s": overlap_warm,
        "scan_cold_s": scan_cold,
        "scan_warm_s": scan_warm,
        "scan_findings": findings,
    }


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--draft", required=True, help="Markdown draft to scan")
    parser.add_argument("--out", help="Write the raw result JSON here")
    args = parser.parse_args(argv)

    draft = Path(args.draft)
    if not draft.is_file():
        print(f"No draft at {draft}", file=sys.stderr)
        return 1
    if not config.LEDGER_PATH.exists():
        print(f"No ledger at {config.LEDGER_PATH} -- run `python -m src.corpus sync` first.", file=sys.stderr)
        return 1

    root = Path(tempfile.mkdtemp(prefix="bench-overlap-"))
    original_overlap_dir = config.OVERLAP_DIR
    config.OVERLAP_DIR = root / "overlap"
    try:
        result = run(draft)
    finally:
        config.OVERLAP_DIR = original_overlap_dir
        shutil.rmtree(root, ignore_errors=True)

    if not result["citekeys"]:
        return 1

    n = len(result["citekeys"])
    print(f"draft: {draft}  ({n} cited source(s))\n")
    print(f"  {n}x overlap (warm cache):      {result['overlap_n_invocations_warm_s']:7.3f}s")
    print(f"  1x scan, cold corpus index:      {result['scan_cold_s']:7.3f}s")
    print(f"  1x scan, warm corpus index:      {result['scan_warm_s']:7.3f}s")
    print(f"  scan findings (warm run): {result['scan_findings']}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
