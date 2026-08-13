"""What an `overlap_gate` would block, and how much of it would be wrong
(#130), measured over a real book against the corpus it was written from.

#130 asks whether a long verbatim run should block a draft the way
`python -m src.draft gate` blocks an unresolvable citekey, and forbids
guessing the threshold: it is to be "tuned against real reports". This
measures the report. For every candidate span threshold T it counts what
the predicate below would block, and -- against hand-labelled ground
truth -- how much of that is genuine reuse rather than a canonical
definition every paper in the field quotes.

    tier in {"exact", "skip-gram"} and span_words >= T
        and not (quoted and cites_source)

Two arms, because References masking turned out to dominate the answer.
`verbatim_check._mask_for_scan` blanks the draft's own bibliography
before scanning, since two documents citing the same paper share its
title and venue verbatim -- but `references.section_start` matched only
single-level heading numbers, so a book numbering its headings per
chapter ("## 1.14 References") was never masked at all. The unmasked arm
reproduces that, by making `section_start` return None. It is not a
hypothetical: it is what this benchmark measured before the pattern was
fixed, and the gap between the arms is the strongest number here.

**What this does not measure.** Paraphrase: the exact tier cannot see it,
so a low finding count is not a clean bill of health -- it is the
headline caveat of docs/PLAGIARISM.md and it applies to every number
below. Nor does it measure whether a blocked draft is *fixable*: the
`long` runs it counts are exactly the class `overlap-reviser` refuses to
rewrite unattended, referring the paraphrase-or-quote choice to a person.
Nor recall against reuse the corpus does not contain -- every true
positive here is reuse from one of 497 parsed documents.

Labels are an input, not an output: `--labels` is hand-authored, keyed by
the position-free finding `id`, and carries no verbatim text. Nothing
this script writes carries `fragment`, `context` or `draft_text` either,
because `bench/results/` is committed and those fields are extracts of
copyrighted PDFs.

    python3 bench/bench_overlap_gate.py --tag 2026-08-13-overlap-gate \\
        --drafts content/drafts/books/digital-twins-for-software-engineers

Needs a synced corpus (`python -m src.corpus sync`) and pays one cold
corpus-index build on first run; every run after that is warm.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from src import config, references  # noqa: E402

# Below the report-bucket boundary a run is not "long" in any sense the
# project already uses, and no candidate gate threshold sits there -- so
# the sweep starts here and the labelling only ever had to cover this
# population. The cost is that this benchmark cannot answer "should the
# gate fire lower than LONG_RUN_WORDS"; that is stated, not implied.
SWEEP_FLOOR = 15

# Recorded per finding. Deliberately not _PAYLOAD_FIELDS: `fragment`,
# `context` and `draft_text` are verbatim source and draft prose, and
# this file is committed.
KEPT_FIELDS = (
    "id", "citekey", "page", "end_page", "tier", "span_words",
    "matched_words", "line", "cites_source", "quoted", "severity",
)


def eligible(finding):
    """Whether the predicate under test could ever block on `finding`.

    The tier clause is trivially true today -- `scan` labels everything
    `exact` and no skip-gram tier is built -- but it is written out
    because it is the half of #130's predicate that decides what the
    gate *cannot* see, and a reader checking the numbers against the
    issue should find it here rather than infer it.

    The quoted-and-cited exemption mirrors `_bucket`'s own demotion: a
    properly quoted, properly attributed block quote is scholarship, and
    a gate that blocks it is wrong by construction.
    """
    if finding["tier"] not in {"exact", "skip-gram"}:
        return False
    return not (finding["quoted"] and finding["cites_source"])


def sweep(findings, labels, thresholds):
    """What the gate blocks at each T, and how much of it is mislabelled.

    `missed_tp` is the half a precision number alone hides: raising T
    always improves precision, and the only thing that argues against
    raising it forever is the genuine reuse that stops being caught.
    """
    gateable = [f for f in findings if eligible(f)]
    total_tp = sum(1 for f in gateable if labels.get(f["id"], {}).get("label") == "tp")
    rows = []
    for t in thresholds:
        blocked = [f for f in gateable if f["span_words"] >= t]
        tp = [f for f in blocked if labels.get(f["id"], {}).get("label") == "tp"]
        fp = [f for f in blocked if labels.get(f["id"], {}).get("label") == "fp"]
        unlabelled = len(blocked) - len(tp) - len(fp)
        cross = [f for f in blocked if f["end_page"] > f["page"]]
        cross_fp = [f for f in cross if labels.get(f["id"], {}).get("label") == "fp"]
        rows.append({
            "threshold": t,
            "blocked": len(blocked),
            "tp": len(tp),
            "fp": len(fp),
            "unlabelled": unlabelled,
            # None, not 0.0 or 1.0: at a threshold nothing reaches there
            # is no precision to report, and either number would read as
            # a measurement.
            "precision": round(len(tp) / len(blocked), 4) if blocked else None,
            "missed_tp": total_tp - len(tp),
            "blocked_cross_page": len(cross),
            "fp_cross_page": len(cross_fp),
            "drafts_blocked": len({f["draft"] for f in blocked}),
        })
    return rows


def scan_all(drafts, references_masked, allowlist=None):
    """Every finding in `drafts`, tagged with the draft it came from.

    `verbatim_check` is imported here rather than at module scope
    because the unmasked arm patches `references.section_start`, which
    `_mask_for_scan` resolves through the module object at call time --
    the patch has to be in place before the first scan, not before the
    first import, but keeping the import local makes the ordering
    obvious rather than incidental.

    `allowlist` is redirected the same way, and for the same reason:
    `_load_allowlist_phrases` reads `config.VERBATIM_ALLOWLIST_PATH` per
    call. Pointing it at a file under `bench/results/` rather than at
    `content/verbatim_allowlist.toml` keeps the arm reproducible off this
    host -- the real allowlist is per-host and gitignored, so an arm that
    depended on it would measure whatever the operator happened to have.
    """
    from src.review import verbatim_check as vc

    original_section = references.section_start
    original_allowlist = config.VERBATIM_ALLOWLIST_PATH
    if not references_masked:
        references.section_start = lambda lines: None
    # A Path that does not exist is how `_load_allowlist_phrases` spells
    # "no suppressions", so the no-allowlist arms need no special case.
    config.VERBATIM_ALLOWLIST_PATH = Path(allowlist) if allowlist else Path("/nonexistent")
    try:
        out = []
        total_suppressed = 0
        for draft in drafts:
            found, _, suppressed = vc.scan_findings(str(draft))
            total_suppressed += suppressed
            for f in found:
                record = {k: vc.published(f)[k] for k in KEPT_FIELDS}
                record["draft"] = draft.name
                out.append(record)
        if total_suppressed:
            print(f"    {total_suppressed} finding(s) allowlist-suppressed")
        return out, total_suppressed
    finally:
        references.section_start = original_section
        config.VERBATIM_ALLOWLIST_PATH = original_allowlist


def self_check():
    """Prove the predicate and the sweep can see a difference first.

    The failure this guards is the one this whole benchmark is exposed
    to: every count below can be zero because nothing was found, or zero
    because nothing was *looked at*, and the two print identically. A
    sweep over an empty findings list reports 0 blocked and 0 false
    positives at every threshold -- which reads exactly like a gate with
    a perfect false-positive rate.

    `bench/` sits outside CI's coverage targets (--cov=src --cov=scripts)
    and outside the clean-code ratchet, so nothing in the test suite will
    catch a regression here. This runs on every invocation instead.
    """
    quoted_cited = {"id": "a", "tier": "exact", "span_words": 99,
                    "quoted": True, "cites_source": True}
    quoted_uncited = {"id": "b", "tier": "exact", "span_words": 99,
                      "quoted": True, "cites_source": False}
    assert not eligible(quoted_cited), "a quoted, cited block quote must never block"
    # The case the predicate is easy to get wrong, and the one this
    # book actually contains: a blockquote citing the work that first
    # stated a definition still reads as UNCITED against every other
    # corpus paper quoting the same definition. `_bucket` keeps it in
    # `long` deliberately, so the gate must be able to reach it.
    assert eligible(quoted_uncited), "a quoted but uncited run must stay reachable"
    assert eligible({"id": "c", "tier": "exact", "span_words": 20,
                     "quoted": False, "cites_source": False})
    assert not eligible({"id": "d", "tier": "embedding", "span_words": 99,
                         "quoted": False, "cites_source": False}), (
        "only deterministic tiers may gate (docs/PLAGIARISM.md)")

    findings = [
        {"id": "t", "tier": "exact", "span_words": 30, "quoted": False,
         "cites_source": False, "page": 1, "end_page": 1, "draft": "x.md"},
        {"id": "f", "tier": "exact", "span_words": 16, "quoted": False,
         "cites_source": False, "page": 1, "end_page": 2, "draft": "x.md"},
    ]
    labels = {"t": {"label": "tp"}, "f": {"label": "fp"}}
    rows = {r["threshold"]: r for r in sweep(findings, labels, [16, 20, 40])}
    assert rows[16]["blocked"] == 2 and rows[16]["precision"] == 0.5
    assert rows[16]["fp_cross_page"] == 1, "cross-page split not counted"
    assert rows[20]["blocked"] == 1 and rows[20]["precision"] == 1.0
    assert rows[20]["missed_tp"] == 0, "a caught true positive counted as missed"
    # Raising T past everything must show the cost, not a clean sheet.
    assert rows[40]["blocked"] == 0 and rows[40]["precision"] is None
    assert rows[40]["missed_tp"] == 1, "a threshold above every finding hides its cost"


def integrity_complaints(drafts, arms, labels):
    """Everything that would make the tables below a lie, in one place.

    Each of these produces a row of zeros indistinguishable from a good
    result -- an empty corpus index, an empty draft set, or a sweep over
    findings nobody labelled all report a gate that blocks nothing and
    is wrong about nothing.
    """
    out = []
    if not drafts:
        out.append("no drafts matched -- every count below is zero for that reason alone")
    masked = arms.get("references-masked", [])
    if not masked:
        out.append("the masked arm found nothing at all -- an empty corpus index and a "
                   "clean book are indistinguishable here; check the ledger's "
                   "parsed_path values resolve on this host")
    gateable = [f for f in masked if eligible(f) and f["span_words"] >= SWEEP_FLOOR]
    missing = [f["id"] for f in gateable if f["id"] not in labels]
    if missing:
        out.append(f"{len(missing)} of {len(gateable)} gateable finding(s) are unlabelled "
                   f"(e.g. {', '.join(missing[:3])}) -- they are counted as blocked but "
                   f"score in neither tp nor fp, so precision is not evidence")
    if labels:
        stale = [i for i in labels if i not in {f["id"] for f in masked}]
        if stale:
            out.append(f"{len(stale)} label(s) match no current finding (e.g. "
                       f"{', '.join(stale[:3])}) -- the labels file is for a different "
                       f"corpus or a re-parse moved the fragments its ids are built from")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--drafts", required=True,
                    help="directory of drafts to scan (*.md, chapters first)")
    ap.add_argument("--tag", required=True,
                    help="names the output directory, bench/results/<tag>/. Passed in "
                         "rather than derived from the clock, so a re-run over an "
                         "unchanged corpus reproduces the same record byte for byte.")
    ap.add_argument("--labels", default=None,
                    help="hand-authored ground truth, keyed by finding id "
                         "(default: <out>/labels.json)")
    ap.add_argument("--allowlist", default=None,
                    help="a boilerplate allowlist to measure a third arm against "
                         "(default: <out>/candidate_allowlist.toml, if present)")
    ap.add_argument("--out", default=None,
                    help="output directory (default: bench/results/<tag>)")
    args = ap.parse_args(argv)

    self_check()

    if not config.LEDGER_PATH.exists():
        print(f"no ledger at {config.LEDGER_PATH} -- run `python -m src.corpus sync` first",
              file=sys.stderr)
        return 1
    drafts = sorted(p for p in Path(args.drafts).glob("*.md") if p.name[0].isdigit())
    if not drafts:
        print(f"no numbered chapters under {args.drafts}", file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else BENCH_DIR / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    labels_path = Path(args.labels) if args.labels else out_dir / "labels.json"
    labels = json.loads(labels_path.read_text())["labels"] if labels_path.exists() else {}

    allowlist = Path(args.allowlist) if args.allowlist else out_dir / "candidate_allowlist.toml"
    plan = [("references-masked", True, None),
            ("references-unmasked", False, None)]
    if allowlist.exists():
        plan.append(("references-masked+allowlist", True, allowlist))

    arms, suppressed_by_arm = {}, {}
    for arm, masked, allow in plan:
        print(f"  scanning {len(drafts)} draft(s), {arm} ...", flush=True)
        arms[arm], suppressed_by_arm[arm] = scan_all(drafts, masked, allow)
        longs = [f for f in arms[arm] if f["span_words"] >= SWEEP_FLOOR]
        print(f"    {len(arms[arm])} finding(s), {len(longs)} at or above "
              f"{SWEEP_FLOOR} words")

    findings = arms["references-masked"]
    spans = [f["span_words"] for f in findings if eligible(f)]
    thresholds = list(range(SWEEP_FLOOR, (max(spans) if spans else SWEEP_FLOOR) + 2))
    rows = sweep(findings, labels, thresholds)
    complaints = integrity_complaints(drafts, arms, labels)

    payload = {
        "drafts": [d.name for d in drafts],
        "corpus_documents": len(set(f["citekey"] for f in findings)),
        "parser_backend": config.PARSER,
        "allowlist_present": config.VERBATIM_ALLOWLIST_PATH.exists(),
        "sweep_floor": SWEEP_FLOOR,
        "labels_source": str(labels_path.name),
        "allowlist_source": allowlist.name if allowlist.exists() else None,
        "integrity_complaints": complaints,
        "arms": {
            arm: {
                "findings": len(items),
                "long_bucket": sum(1 for f in items if f["span_words"] >= SWEEP_FLOOR),
                "gateable_long": sum(1 for f in items
                                     if eligible(f) and f["span_words"] >= SWEEP_FLOOR),
                "allowlist_suppressed": suppressed_by_arm[arm],
            } for arm, items in arms.items()
        },
        "sweep": rows,
        "findings": sorted(findings, key=lambda f: (-f["span_words"], f["draft"], f["id"])),
    }
    record = out_dir / "overlap_gate.json"
    record.write_text(json.dumps(payload, indent=1))

    for complaint in complaints:
        print(f"\n  WARNING {complaint}")

    print(f"\n{'arm':<30} {'findings':>9} {'>=15w':>7} {'gateable':>9} {'suppressed':>11}")
    for arm, stats in payload["arms"].items():
        print(f"{arm:<30} {stats['findings']:>9} {stats['long_bucket']:>7} "
              f"{stats['gateable_long']:>9} {stats['allowlist_suppressed']:>11}")

    print(f"\n{'T':>4} {'blocked':>8} {'tp':>4} {'fp':>4} {'unlab':>6} "
          f"{'precision':>10} {'missed_tp':>10} {'drafts':>7}")
    for r in rows:
        prec = "-" if r["precision"] is None else f"{r['precision']:.2f}"
        print(f"{r['threshold']:>4} {r['blocked']:>8} {r['tp']:>4} {r['fp']:>4} "
              f"{r['unlabelled']:>6} {prec:>10} {r['missed_tp']:>10} "
              f"{r['drafts_blocked']:>7}")
    print(f"\nRecord: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
