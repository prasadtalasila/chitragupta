"""What the skip-gram tier (#133) actually catches, measured two ways.

`docs/PLAGIARISM.md`'s tier-2 entry and discussion #115 both call for
"start advisory, promote with evidence" -- this is that evidence, styled
on `bench_overlap_gate.py`'s two-part shape (a self-contained synthetic
capability check, plus a real-corpus precision measurement), because a
tier that catches synthetic word-swaps but drowns in false positives on
real prose is not evidence for anything.

**Capability arm** (always runs, needs no corpus): sweeps a source
sentence against every-Nth-word synonym swaps at a range
of strides and reports, for each, whether the skip-gram tier catches it
-- the same property `tests/test_overlap_skipgram.py::TestGradedParaphraseDetection`
pins, run here as a sweep instead of four fixed cases. Confirms the tier
does what discussion #115 designed it to do before spending any time on
the harder question below.

**Precision arm** (`--drafts`, needs a synced corpus): the tier-2
analogue of `bench_overlap_gate.py` -- scans real drafts, isolates
`tier == "skip-gram"` findings (dropping anything the exact tier already
covers, same as `scan_findings` itself does), and reports agreement with
hand labels the same way. This is the arm that answers "is tier 2 worth
trusting", and it is the one #162's own benchmark could not run, because
tier 2 did not exist yet.

**What this does not measure.** Embedding-level paraphrase (tier 3,
#134, unbuilt) -- restatement in genuinely new sentence structure, not a
word-for-word swap. A clean run on both arms here is not evidence
against that failure mode; see docs/PLAGIARISM.md.

    python3 bench/bench_overlap_skipgram.py --capability

    python3 bench/bench_overlap_skipgram.py --tag 2026-08-13-skipgram \\
        --drafts content/drafts/books/digital-twins-for-software-engineers
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from src import config, overlap_skipgram  # noqa: E402

# Same recorded-field discipline as bench_overlap_gate.py: no `fragment`,
# `context` or `draft_text` -- copyrighted source/draft prose -- since
# `bench/results/` is committed.
KEPT_FIELDS = (
    "id", "citekey", "page", "end_page", "tier", "span_words",
    "matched_words", "line", "cites_source", "quoted", "severity",
)

CAPABILITY_SOURCE = (
    "the validation of a digital twin requires continuous comparison "
    "against measurements taken from the physical asset every single "
    "time an engineer wants a trustworthy answer about the system"
).split()

# Even strides only: an odd stride does not keep every substitution on
# one original-index parity, so a miss there would not test the
# family-split design -- it would just be noise. See
# src/overlap_skipgram.py's module docstring.
CAPABILITY_STRIDES = (2, 4, 6, 8, 10, 12, 14)


def _swap_every_nth_word(words, stride):
    edited = list(words)
    for i in range(stride - 1, len(edited), stride):
        edited[i] = f"X{i}"
    return edited


def capability_sweep():
    """Detection rate at each stride in `CAPABILITY_STRIDES` -- no
    corpus, no ledger, pure function of `overlap_skipgram.skipgram_postings`.
    """
    n = overlap_skipgram.DEFAULT_N
    source_hashes = {h for h, _s, _e in overlap_skipgram.skipgram_postings(CAPABILITY_SOURCE, n)}
    rows = []
    for stride in CAPABILITY_STRIDES:
        edited = _swap_every_nth_word(CAPABILITY_SOURCE, stride)
        edited_postings = overlap_skipgram.skipgram_postings(edited, n)
        caught = any(h in source_hashes for h, _s, _e in edited_postings)
        rows.append({"stride": stride, "caught": caught})
    return rows


def self_check():
    """Prove the sweep can see a miss before trusting a clean sweep --
    the same guard `bench_overlap_gate.py` runs, adapted: a stride of 1
    (every word swapped) must never be caught, since neither family
    survives it, and the real `CAPABILITY_STRIDES` sweep must not read
    as "caught everything" for a reason that has nothing to do with the
    tier actually working.
    """
    n = overlap_skipgram.DEFAULT_N
    source_hashes = {h for h, _s, _e in overlap_skipgram.skipgram_postings(CAPABILITY_SOURCE, n)}
    every_word_swapped = _swap_every_nth_word(CAPABILITY_SOURCE, 1)
    edited_postings = overlap_skipgram.skipgram_postings(every_word_swapped, n)
    assert not any(h in source_hashes for h, _s, _e in edited_postings), (
        "the capability sweep reported a catch with every word replaced -- "
        "it is not measuring what it claims to"
    )
    assert capability_sweep(), "the capability sweep produced no rows at all"


def eligible(finding):
    """Skip-gram findings only, and only ones already surviving
    `scan_findings`' own exact-tier dedup (see that function's
    docstring) -- this script isolates what tier 2 uniquely contributes,
    not what it redundantly re-finds."""
    return finding["tier"] == "skip-gram"


def scan_all(drafts):
    from src.review import verbatim_check as vc

    out = []
    total_suppressed = 0
    for draft in drafts:
        found, _, suppressed, _ = vc.scan_findings(str(draft))
        total_suppressed += suppressed
        for f in found:
            if not eligible(f):
                continue
            record = {k: vc.published(f)[k] for k in KEPT_FIELDS}
            record["draft"] = draft.name
            out.append(record)
    return out, total_suppressed


def integrity_complaints(drafts, findings, labels):
    out = []
    if not drafts:
        out.append("no drafts matched -- every count below is zero for that reason alone")
    missing = [f["id"] for f in findings if f["id"] not in labels]
    if missing:
        out.append(f"{len(missing)} of {len(findings)} skip-gram finding(s) are unlabelled "
                   f"(e.g. {', '.join(missing[:3])})")
    if labels:
        stale = [i for i in labels if i not in {f["id"] for f in findings}]
        if stale:
            out.append(f"{len(stale)} label(s) match no current finding (e.g. "
                       f"{', '.join(stale[:3])}) -- stale corpus or re-parse")
    return out


def precision_run(drafts_dir, labels_path, out_dir):
    if not config.LEDGER_PATH.exists():
        print(f"no ledger at {config.LEDGER_PATH} -- run `python -m src.corpus sync` first",
              file=sys.stderr)
        return 1
    drafts = sorted(p for p in Path(drafts_dir).glob("*.md") if p.name[0].isdigit())
    if not drafts:
        print(f"no numbered chapters under {drafts_dir}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    labels_file = Path(labels_path) if labels_path else out_dir / "labels.json"
    labels = json.loads(labels_file.read_text())["labels"] if labels_file.exists() else {}

    print(f"  scanning {len(drafts)} draft(s) for skip-gram findings ...", flush=True)
    findings, suppressed = scan_all(drafts)
    complaints = integrity_complaints(drafts, findings, labels)

    tp = sum(1 for f in findings if labels.get(f["id"], {}).get("label") == "tp")
    fp = sum(1 for f in findings if labels.get(f["id"], {}).get("label") == "fp")
    payload = {
        "drafts": [d.name for d in drafts],
        "skipgram_findings": len(findings),
        "labelled_tp": tp,
        "labelled_fp": fp,
        "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "allowlist_suppressed": suppressed,
        "integrity_complaints": complaints,
        "findings": sorted(findings, key=lambda f: (-f["span_words"], f["draft"], f["id"])),
    }
    record = out_dir / "skipgram_precision.json"
    record.write_text(json.dumps(payload, indent=1))

    for complaint in complaints:
        print(f"\n  WARNING {complaint}")
    print(f"\nskip-gram findings: {len(findings)}  tp: {tp}  fp: {fp}  "
          f"precision: {payload['precision']}")
    print(f"Record: {record}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--drafts", default=None,
                    help="directory of drafts to scan for the precision arm "
                         "(*.md, chapters first). Needs a synced corpus.")
    ap.add_argument("--tag", default=None,
                    help="names bench/results/<tag>/ for the precision arm's output "
                         "(path components are stripped: only the final name is used)")
    ap.add_argument("--labels", default=None,
                    help="hand-authored ground truth for the precision arm "
                         "(default: bench/results/<tag>/labels.json)")
    args = ap.parse_args(argv)

    self_check()

    rows = capability_sweep()
    print(f"{'stride':>6} {'caught':>7}")
    for r in rows:
        print(f"{r['stride']:>6} {'yes' if r['caught'] else 'NO':>7}")
    missed = [r["stride"] for r in rows if not r["caught"]]
    if missed:
        print(f"\nnot caught at stride(s): {missed}")

    if args.tag:
        out_dir = BENCH_DIR / "results" / Path(args.tag).name
        out_dir.mkdir(parents=True, exist_ok=True)
        record = out_dir / "skipgram_capability.json"
        record.write_text(json.dumps({
            "source_words": len(CAPABILITY_SOURCE),
            "n": overlap_skipgram.DEFAULT_N,
            "strides": rows,
        }, indent=1))
        print(f"Record: {record}")

    if not args.drafts:
        return 0
    if not args.tag:
        print("--tag is required with --drafts", file=sys.stderr)
        return 2
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    return precision_run(args.drafts, args.labels, out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
