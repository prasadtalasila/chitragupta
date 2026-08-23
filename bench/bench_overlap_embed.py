"""What the embedding tier (#134/#164) actually catches, measured two
ways -- and, unlike the other overlap benches, needing a GPU-class
dependency stack to run at all.

**Not a threshold sweep, and it cannot be one.** `bench_overlap_gate.py`
sweeps T because tier-1 findings have a threshold-to-gate mapping to
sweep; `bench_overlap_skipgram.py` sweeps stride because tier 2's
capability is a function of substitution density. Tier 3 can never gate
(`content/chroma/` is namespaced per `[enrich].embedding_model`, so a
finding is not reproducible across a config edit) and it does not
threshold: `overlap_embed.report` ranks and caps per section, because a
cutoff provably cannot separate paraphrase from topic in this corpus.
So both arms below ask "was the planted/known passage reported", not
"what does precision do as T moves".

**Capability arm** (`--fixture`): scans
`bench/fixtures/graded-paraphrase-of-singh-offload-2022.md`, in which one
real claim from one real corpus paper appears four times at four
distances from the original -- verbatim, substituted in place, lightly
edited, genuinely restated -- each in its own section and each citing the
source. Reports which grades each tier caught. This is the measurement
that says what tier 3 adds: tiers 1 and 2 fall off this ladder partway
down and tier 3 should not.

**Precision arm** (`--drafts`): scans real drafts, isolates
`tier == "embedding"` findings and reports agreement with hand labels,
the same shape and the same `KEPT_FIELDS` discipline as
`bench_overlap_skipgram.py`'s precision arm -- no `fragment`, `context`
or `draft_text` in a committed result, since those are draft and source
prose.

**What it needs that the other overlap benches do not.** They are stdlib
only and run anywhere. This one needs the `enrich` Poetry group
(`chromadb`, `sentence-transformers`, and torch under them), a built
`content/chroma/`, Docling passage sidecars for the cited sources, and a
dossier for every draft scanned. Any of those missing and tier 3 reports
itself unavailable rather than running -- which the arms below print
rather than swallow, because a zero from an unavailable tier and a zero
from a tier that found nothing are not the same number.

    .venv/bin/python bench/bench_overlap_embed.py --fixture

    .venv/bin/python bench/bench_overlap_embed.py --tag 2026-08-15-embed \\
        --drafts content/drafts/books/digital-twins-for-software-engineers
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import config, dossier, overlap_embed  # noqa: E402

# Same recorded-field discipline as bench_overlap_gate.py and
# bench_overlap_skipgram.py, plus `score`, which is this tier's own
# published field and the thing a ranking is ranked by.
KEPT_FIELDS = (
    "id",
    "citekey",
    "page",
    "end_page",
    "tier",
    "span_words",
    "matched_words",
    "line",
    "cites_source",
    "quoted",
    "severity",
    "score",
)

FIXTURE = BENCH_DIR / "fixtures" / "graded-paraphrase-of-singh-offload-2022.md"

# The fixture's section headings, in the order the grades run, paired
# with the citekey each restates. A grade is "caught" when some tier
# reports a finding against that citekey inside that section.
GRADES = (
    ("Verbatim: the offload argument as its source states it", "singh_offload_2022"),
    ("Word substitution: the same sentence, words swapped in place", "singh_offload_2022"),
    ("Light paraphrase: the same order, a few words moved and added", "singh_offload_2022"),
    ("Genuine restatement: the same claim, rebuilt", "singh_offload_2022"),
)


def _section_lines(text):
    """`{title: (first line, last line)}` for the fixture's headings,
    from the repo's one outline parser rather than a second one."""
    return {s.title: (s.start, s.end) for s in dossier.sections(text)}


def _staged(fixture):
    """The fixture copied under `content/drafts/`, with a dossier beside
    it -- what tier 3 requires before it will run at all.

    Copied rather than scanned in place, and this is the honest cost of
    the tier's own design: it scopes each section to the citekeys that
    section's `sections.md` records, so a draft with no dossier is one it
    reports itself unavailable for. `bench/fixtures/` has no dossier and
    should not grow one; a temporary staging copy under the configured
    content directory is what lets the fixture stay a fixture.
    """
    staged = config.DRAFTS_DIR / "bench-embed" / fixture.name
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture, staged)
    target = dossier.dossier_dir(staged)
    target.mkdir(parents=True, exist_ok=True)
    (target / dossier.SECTIONS_MD).write_text(
        dossier.sections_markdown(staged.read_text(encoding="utf-8")), encoding="utf-8"
    )
    return staged, (staged.parent, target.parent)


def _unstage(directories):
    """Remove what `_staged` created. A bench script writing into the
    configured content directory has to take it back out again: the next
    `dossier status --all` would otherwise report a draft nobody wrote,
    and `bench-embed` is not a topic.

    The dossier's *parent* (`content/dossiers/bench-embed/`), not the
    dossier itself -- `dossier_dir` appends the draft's own stem, so
    removing only that leaves the topic directory behind, which is the
    half a reader would still see."""
    for directory in directories:
        shutil.rmtree(directory, ignore_errors=True)


def capability_run(out_dir):
    """Which grades each tier caught, and which it did not."""
    from chitragupta.review import verbatim_check as vc

    staged, staged_dirs = _staged(FIXTURE)
    try:
        text = staged.read_text(encoding="utf-8")
        lines = _section_lines(text)
        findings, _min_run, _suppressed, not_run = vc.scan_findings(str(staged))
    finally:
        _unstage(staged_dirs)

    rows = []
    for title, citekey in GRADES:
        start, end = lines[title]
        tiers = sorted(
            {f["tier"] for f in findings if f["citekey"] == citekey and start <= f["line"] <= end}
        )
        rows.append({"grade": title.split(":")[0], "citekey": citekey, "tiers": tiers})

    print(
        f"  reporting cap: {overlap_embed.SECTION_LIMIT} alignment(s) per section, "
        f"shortlist {overlap_embed.SHORTLIST_SOURCES} source(s) per section"
    )
    print(f"{'grade':>20}  caught by")
    for row in rows:
        print(f"{row['grade']:>20}  {', '.join(row['tiers']) or 'NOTHING'}")
    for entry in not_run:
        print(f"\n  WARNING tier {entry['tier']} did not run: {entry['reason']}")

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        record = out_dir / "embed_capability.json"
        record.write_text(
            json.dumps(
                {
                    "fixture": FIXTURE.name,
                    "section_limit": overlap_embed.SECTION_LIMIT,
                    "shortlist_sources": overlap_embed.SHORTLIST_SOURCES,
                    "grades": rows,
                    "tiers_not_run": not_run,
                },
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"Record: {record}")
    return 0


def eligible(finding):
    """Embedding findings only. `scan_findings` has already dropped any
    that a deterministic tier's finding overlaps, so what is left is what
    tier 3 uniquely contributes."""
    return finding["tier"] == "embedding"


def scan_all(drafts):
    from chitragupta.review import verbatim_check as vc

    out = []
    total_suppressed = 0
    unavailable = []
    for draft in drafts:
        found, _, suppressed, not_run = vc.scan_findings(str(draft))
        total_suppressed += suppressed
        unavailable += [dict(entry, draft=draft.name) for entry in not_run]
        for f in found:
            if not eligible(f):
                continue
            record = {k: vc.published(f)[k] for k in KEPT_FIELDS}
            record["draft"] = draft.name
            out.append(record)
    return out, total_suppressed, unavailable


def integrity_complaints(drafts, findings, labels, unavailable):
    """Everything that would make a number below mean less than it looks.

    The unavailable check is this tier's own addition to the shape
    `bench_overlap_skipgram.py` established: a precision of `None` over
    zero findings reads identically whether the tier ran and found
    nothing or never ran, and only one of those is a measurement.
    """
    out = []
    if not drafts:
        out.append("no drafts matched -- every count below is zero for that reason alone")
    if unavailable:
        names = ", ".join(sorted({entry["draft"] for entry in unavailable})[:3])
        out.append(
            f"tier 3 did not run on {len(unavailable)} draft(s) (e.g. {names}) -- "
            f"first reason: {unavailable[0]['reason']}"
        )
    missing = [f["id"] for f in findings if f["id"] not in labels]
    if missing:
        out.append(
            f"{len(missing)} of {len(findings)} embedding finding(s) are unlabelled "
            f"(e.g. {', '.join(missing[:3])})"
        )
    if labels:
        stale = [i for i in labels if i not in {f["id"] for f in findings}]
        if stale:
            out.append(
                f"{len(stale)} label(s) match no current finding (e.g. "
                f"{', '.join(stale[:3])}) -- stale corpus or re-parse"
            )
    return out


def precision_run(drafts_dir, labels_path, out_dir):
    if not config.LEDGER_PATH.exists():
        print(
            f"no ledger at {config.LEDGER_PATH} -- run `python -m chitragupta.corpus sync` first",
            file=sys.stderr,
        )
        return 1
    drafts = sorted(p for p in Path(drafts_dir).glob("*.md") if p.name[0].isdigit())
    if not drafts:
        print(f"no numbered chapters under {drafts_dir}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    labels_file = Path(labels_path) if labels_path else out_dir / "labels.json"
    labels = (
        json.loads(labels_file.read_text(encoding="utf-8"))["labels"]
        if labels_file.exists()
        else {}
    )

    print(f"  scanning {len(drafts)} draft(s) for embedding findings ...", flush=True)
    findings, suppressed, unavailable = scan_all(drafts)
    complaints = integrity_complaints(drafts, findings, labels, unavailable)

    tp = sum(1 for f in findings if labels.get(f["id"], {}).get("label") == "tp")
    fp = sum(1 for f in findings if labels.get(f["id"], {}).get("label") == "fp")
    payload = {
        "drafts": [d.name for d in drafts],
        # The population this precision is over is already capped by the
        # tier itself, and a count that does not say so reads as "every
        # alignment in the book". Recorded rather than left implicit.
        "section_limit": overlap_embed.SECTION_LIMIT,
        "shortlist_sources": overlap_embed.SHORTLIST_SOURCES,
        "embedding_findings": len(findings),
        "labelled_tp": tp,
        "labelled_fp": fp,
        "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "allowlist_suppressed": suppressed,
        "tiers_not_run": unavailable,
        "integrity_complaints": complaints,
        "findings": sorted(findings, key=lambda f: (-(f["score"] or 0), f["draft"], f["id"])),
    }
    record = out_dir / "embed_precision.json"
    record.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    for complaint in complaints:
        print(f"\n  WARNING {complaint}")
    print(
        f"\nembedding findings: {len(findings)} (capped at "
        f"{overlap_embed.SECTION_LIMIT} per section)  tp: {tp}  fp: {fp}  "
        f"precision: {payload['precision']}"
    )
    print(f"Record: {record}")
    return 0


def self_check():
    """The fixture says what this script assumes it says.

    Every grade named in `GRADES` is a heading of the fixture, and the
    citekey each restates is cited in that section. Without this, a
    heading renamed in the fixture would silently make every grade
    "NOTHING" and read as a tier that catches nothing at all.
    """
    text = FIXTURE.read_text(encoding="utf-8")
    lines = _section_lines(text)
    body = text.splitlines()
    for title, citekey in GRADES:
        assert title in lines, f"the fixture has no section titled {title!r}"
        start, end = lines[title]
        assert any(citekey in line for line in body[start - 1 : end]), (
            f"the fixture's {title!r} section does not cite {citekey}"
        )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--fixture", action="store_true", help="run the capability arm over the graded fixture"
    )
    ap.add_argument(
        "--drafts",
        default=None,
        help="directory of drafts to scan for the precision arm "
        "(*.md, chapters first). Needs a synced corpus.",
    )
    ap.add_argument(
        "--tag",
        default=None,
        help="names bench/results/<tag>/ for output (path components "
        "are stripped: only the final name is used)",
    )
    ap.add_argument(
        "--labels",
        default=None,
        help="hand-authored ground truth for the precision arm "
        "(default: bench/results/<tag>/labels.json)",
    )
    args = ap.parse_args(argv)

    self_check()
    out_dir = BENCH_DIR / "results" / Path(args.tag).name if args.tag else None

    if args.fixture:
        capability_run(out_dir)

    if not args.drafts:
        return 0
    if not args.tag:
        print("--tag is required with --drafts", file=sys.stderr)
        return 2
    return precision_run(args.drafts, args.labels, out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
