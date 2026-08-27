"""Does claim-support checking's entailment score separate claims a human
reviewer would judge *supported* from claims a human reviewer would judge
*unsupported*, over the real drafted book -- or does it not, which is a
result too (#... "it does not separate supported from unsupported on this
corpus" is a result, not a failure to deliver)?

Mirrors `bench/bench_paraphrase_hunt.py`'s two-phase shape (`--extract`
then a human judges, then `--crosscheck`) and `bench/bench_overlap_embed.py`'s
`self_check()` convention (a script publishing a number must fabricate a
difference and assert it sees it) -- read both scripts in full before
changing this one; do not reinvent either convention.

## The method

1. **Self-check first, always.** `chitragupta/entailment.py`'s real
   cross-encoder, run over a fabricated entailed pair and a fabricated
   contradicted pair (`bench/fixtures/graded-claim-support.md` plus its two
   source fixtures under `bench/fixtures/graded-claim-support-sources/`),
   must score the entailed pair higher. This proves the scorer's plumbing
   works; it says nothing about whether the aid is useful on real content
   -- that is what `--extract`/`--crosscheck` measure. Skips, not fails,
   when the `enrich` extras are not installed.
2. **`--extract`**: runs `chitragupta.review.claim_support.build_report()`
   over the four real drafts named explicitly below (matching
   `chitragupta/review/_claims.py`'s own docstring precedent, not "the
   project's real drafts" as a placeholder), pools every scored finding,
   and writes the `CANDIDATES_PER_END` lowest-scored and highest-scored
   findings to `bench/results/<tag>/candidates.md` for a human to read and
   judge -- claim text, citekey and matched passage excerpt, quoted
   straight out of the real drafts and their real sources.
3. **A human judges `candidates.md`** and writes
   `bench/results/<tag>/labels.json` as
   `{"candidates": [{"id": ..., "judgment": "supported"|"unsupported"|"unclear",
   "reason": "..."}]}`, one entry per candidate id shown in `candidates.md`
   -- the same shape `bench_paraphrase_hunt.py`'s own `labels.json` uses.
   This step is not automated by this script and must never be simulated:
   judging "is this claim actually supported by its source" for a real
   citation in this project's real drafts is exactly the kind of call this
   whole feature exists to keep human.
4. **`--crosscheck`**: reads `labels.json` back, recomputes every finding's
   score fresh (a second `build_report()` pass, not a persisted population
   file -- see below), and reports whether the score's median separates
   `"supported"` from `"unsupported"`, plus any label that no longer
   matches a current finding. Writes `bench/results/<tag>/crosscheck.json`.
   Reports the real numbers, whatever they are.

**Why `candidates.md` carries no machine-readable sibling.**
`bench_paraphrase_hunt.py`'s `pairs.json` and `bench_retrieval_ground_truth.py`'s
`ground_truth.json` are both gitignored (`.gitignore`, next to
`bench/results/*/pairs.json`) because they carry claim text quoted straight
out of the drafted book. `candidates.md` is the same category -- claim text
plus a matched source excerpt -- so it is gitignored the same way and is
never committed; only this script, the fixtures, and (once a human has
judged) `labels.json` and `crosscheck.json` are. Regenerate it locally with
the `--extract` invocation below.

**Finding ids are pool-unique, not just `claim_support.finding_id`-unique.**
That function keys on `(citekey, claim)` alone, with no draft in it, so the
same sentence citing the same source in two of the four drafts would
collide. Every id in `candidates.md` and in the `--crosscheck` score map is
`f"{draft}#{finding_id}"` instead (numbered further on the rare exact
in-draft repeat), so a human's `labels.json` can always join back to
exactly one finding.

    .venv-full/bin/python bench/bench_claim_support.py --extract \\
        --drafts content/drafts/digital-twins-for-software-engineers \\
        --tag 2026-08-26-claim-support-measurement

    # judge candidates.md into labels.json, then:

    .venv-full/bin/python bench/bench_claim_support.py --crosscheck \\
        --drafts content/drafts/digital-twins-for-software-engineers \\
        --tag 2026-08-26-claim-support-measurement
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import config, entailment  # noqa: E402
from chitragupta.review import citation_provenance as cp  # noqa: E402
from chitragupta.review import claim_support  # noqa: E402

FIXTURE = BENCH_DIR / "fixtures" / "graded-claim-support.md"
FIXTURE_SOURCES = BENCH_DIR / "fixtures" / "graded-claim-support-sources"
ENTAILED_CASE = "fixture_entailed_case"
CONTRADICTED_CASE = "fixture_contradicted_case"

# The four real drafts, named explicitly -- see this module's docstring on
# why "the project's real drafts" would be the wrong way to say this.
DRAFT_NAMES = ("survey.md", "book-chapter.md", "tutorial.md", "deep-research.md")

# Findings shortlisted at each end of the ranked pool for a human to read
# and judge. Not a threshold on anything published -- a reading order, and
# the cap is stated in candidates.md rather than applied silently, the same
# discipline bench_paraphrase_hunt.py's SHORTLIST_SUPPORT states for its
# own cap.
CANDIDATES_PER_END = 20

INVOCATION = (
    ".venv-full/bin/python bench/bench_claim_support.py --extract "
    "--drafts content/drafts/digital-twins-for-software-engineers --tag <tag>"
)


def _fixture_source_text(citekey: str) -> str:
    """The one source passage
    `bench/fixtures/graded-claim-support-sources/<citekey>.passages.json`
    carries -- the same `{"text", "label", "page"}` shape
    `chitragupta/passages.py`'s `passage_records()` writes, read directly
    here rather than through that module's content-backed sidecar ladder:
    this fixture cites no citekey any real ledger or `content/` sidecar
    could resolve, by design (never smoke-test against real content)."""
    path = FIXTURE_SOURCES / f"{citekey}.passages.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    return records[0]["text"]


def self_check():
    """A fabricated entailed/contradicted pair, and the real entailer
    sees the difference.

    Two checks in one, matching `bench_overlap_embed.py`'s self_check (the
    fixture says what this script assumes it says) and
    `bench_paraphrase_hunt.py`'s (a filter/scorer really discriminates):
    first that the fixture still carries exactly the two citekeys this
    script keys on, then that `chitragupta/entailment.py`'s real
    cross-encoder -- not a fake -- scores the entailed pair higher than the
    contradicted one. This validates the scorer's plumbing, not the aid's
    usefulness on real content -- that is what `--extract` measures.

    Skips, rather than fails, when the enrich group is not installed in
    whatever venv runs this check -- the same gating
    `bench_overlap_embed.py`'s own `--fixture` arm uses, via
    `entailment.open_entailer()` rather than a raw import so the two
    scripts agree on what "installed" means.
    """
    text = FIXTURE.read_text(encoding="utf-8")
    claims = {citekey: claim for _line, citekey, claim in cp.claims(text)}
    for citekey in (ENTAILED_CASE, CONTRADICTED_CASE):
        assert citekey in claims, f"the fixture no longer cites {citekey}"

    entailer, reason = entailment.open_entailer()
    if entailer is None:
        print(f"self_check: skipped -- {reason}")
        return

    entailed_score, contradicted_score = entailer.score(
        [
            (_fixture_source_text(ENTAILED_CASE), claims[ENTAILED_CASE]),
            (_fixture_source_text(CONTRADICTED_CASE), claims[CONTRADICTED_CASE]),
        ]
    )
    assert entailed_score > contradicted_score, (
        f"the entailed pair ({entailed_score:.3f}) did not outscore the "
        f"contradicted pair ({contradicted_score:.3f}) -- the scorer's own "
        "plumbing is broken, not just this corpus's separation"
    )
    print(f"self_check: entailed={entailed_score:.3f} contradicted={contradicted_score:.3f} -- ok")


def _population(drafts_dir, entailer):
    """Every scored finding across the four named real drafts, tagged with
    the draft it came from and a pool-unique id. Called by both
    `--extract` (to build `candidates.md`) and `--crosscheck` (to get a
    fresh `{id: score}` map to join `labels.json` against) -- one
    computation, not two that could drift apart.
    """
    drafts_dir = Path(drafts_dir)
    pool = []
    per_draft = {}
    unscoreable = {}
    missing = []
    for name in DRAFT_NAMES:
        draft_path = drafts_dir / name
        if not draft_path.exists():
            missing.append(str(draft_path))
            continue
        report = claim_support.build_report(draft_path, entailer)
        scored = [f for f in report.findings if f.note is None]
        per_draft[name] = (len(report.findings), len(scored), dict(report.unscoreable))
        unscoreable.update(report.unscoreable)
        for f in scored:
            pool.append(
                {
                    "id": f"{name}#{claim_support.finding_id(f.citekey, f.claim)}",
                    "draft": name,
                    "line": f.line,
                    "citekey": f.citekey,
                    "claim": f.claim,
                    "score": f.score,
                    "page": f.passage.page if f.passage else None,
                    "passage": f.passage.text if f.passage else None,
                }
            )

    # Disambiguate any id collision -- the rare exact repeat of one
    # (citekey, claim) pair inside one draft -- so every pool entry has a
    # truly unique id a human's labels.json can key on. Reported, not
    # silent: candidates.md's own header states the dedupe count.
    counts = {}
    for row in pool:
        counts[row["id"]] = counts.get(row["id"], 0) + 1
    seen = {}
    duplicates = 0
    for row in pool:
        if counts[row["id"]] > 1:
            seen[row["id"]] = seen.get(row["id"], 0) + 1
            duplicates += 1
            row["id"] = f"{row['id']}-{seen[row['id']]}"

    return pool, per_draft, unscoreable, missing, duplicates


def _section(title, rows):
    out = [f"## {title}", ""]
    for row in rows:
        out.append(f"### {row['id']}  score={row['score']:.3f}  {row['draft']}:{row['line']}")
        out.append("")
        out.append(f"- citekey: `{row['citekey']}`")
        out.append(f"- claim: {row['claim']}")
        page = f" (p.{row['page']})" if row["page"] else ""
        out.append(f"- matched passage{page}: {row['passage']}")
        out.append("")
    return out


def _render_candidates(pool, per_draft, unscoreable, missing, duplicates):
    ordered = sorted(pool, key=lambda r: (r["score"], r["draft"], r["id"]))
    cap = min(CANDIDATES_PER_END, len(ordered))
    lowest = ordered[:cap]
    highest = list(reversed(ordered[-cap:])) if cap else []
    scores = sorted(r["score"] for r in pool)

    lines = [
        "# Claim-support candidates for human judgment",
        "",
        "Regenerate this file with:",
        "",
        f"    {INVOCATION}",
        "",
        f"Population: {len(pool)} scored finding(s) across {len(per_draft)} of "
        f"{len(DRAFT_NAMES)} named draft(s) ({', '.join(DRAFT_NAMES)}).",
    ]
    for name in DRAFT_NAMES:
        if name in per_draft:
            total, scored, unsc = per_draft[name]
            lines.append(
                f"  - {name}: {total} finding(s), {scored} scored, "
                f"{len(unsc)} citekey(s) unscoreable"
            )
        else:
            lines.append(f"  - {name}: MISSING (not found under --drafts)")
    if missing:
        lines.append(f"  - {len(missing)} named draft(s) not found: {', '.join(missing)}")
    if duplicates:
        lines.append(
            f"  - {duplicates} id collision(s) (same citekey+claim repeated inside one "
            "draft) disambiguated with a numeric suffix"
        )
    if unscoreable:
        lines.append("")
        lines.append("Unscoreable citekeys (no quotable source passage) and why:")
        for citekey, why in sorted(unscoreable.items()):
            lines.append(f"  - `{citekey}`: {why}")
    lines.append("")
    lines.append(
        f"Score range: {scores[0]:.3f} .. {scores[-1]:.3f}  median: {statistics.median(scores):.3f}"
    )
    lines.append(
        f"Shortlisted below: the {len(lowest)} lowest-scored and the {len(highest)} "
        f"highest-scored of the {len(pool)} above -- the rest are not judged here, and "
        "are not evidence of anything (same discipline as bench_paraphrase_hunt.py's own "
        "shortlist)."
    )
    if 2 * cap > len(pool):
        lines.append("The two lists below overlap: fewer scored findings exist than twice the cap.")
    lines.append("")
    lines.append(
        "Judge each candidate 'supported', 'unsupported' or 'unclear' against the matched "
        "passage shown -- not against general knowledge of the topic -- and record one "
        "entry per id in bench/results/<tag>/labels.json as:"
    )
    lines.append("")
    lines.append(
        '    {"candidates": [{"id": "<id>", "judgment": "supported"|"unsupported"|'
        '"unclear", "reason": "..."}]}'
    )
    lines.append("")
    lines.append("(no claim text needed there -- id is enough to join back to this file.)")
    lines.append("")

    lines += _section(
        f"{len(lowest)} lowest-scored -- candidate false negatives: does the source really "
        "not support this claim, or did retrieval just miss the right passage?",
        lowest,
    )
    lines += _section(
        f"{len(highest)} highest-scored -- candidate confirmations: does a high score mean "
        "real support, or just lexical/topical overlap?",
        highest,
    )
    return "\n".join(lines) + "\n"


def extract(drafts_dir, out_dir):
    entailer, reason = entailment.open_entailer()
    if entailer is None:
        print(f"extract: not run -- {reason}", file=sys.stderr)
        return 1
    if not config.LEDGER_PATH.exists():
        print(
            f"no ledger at {config.LEDGER_PATH} -- run `python -m chitragupta.corpus sync`",
            file=sys.stderr,
        )
        return 1

    print(f"  scoring {len(DRAFT_NAMES)} real draft(s) against their cited sources ...", flush=True)
    pool, per_draft, unscoreable, missing, duplicates = _population(drafts_dir, entailer)
    for name in DRAFT_NAMES:
        if name in per_draft:
            total, scored, unsc = per_draft[name]
            print(
                f"  {name}: {total} finding(s), {scored} scored, {len(unsc)} citekey(s) unscoreable"
            )
        else:
            print(f"  WARNING missing draft: {Path(drafts_dir) / name}", file=sys.stderr)
    if not pool:
        print("no scored findings across the named drafts -- nothing to shortlist", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = out_dir / "candidates.md"
    candidates_path.write_text(
        _render_candidates(pool, per_draft, unscoreable, missing, duplicates), encoding="utf-8"
    )

    scores = sorted(row["score"] for row in pool)
    cap = min(CANDIDATES_PER_END, len(pool))
    print(f"\npool: {len(pool)} scored finding(s) across {len(per_draft)} draft(s)")
    print(
        f"  score range: {scores[0]:.3f} .. {scores[-1]:.3f}  "
        f"median: {statistics.median(scores):.3f}"
    )
    print(f"  shortlisted: {cap} lowest + {cap} highest")
    if unscoreable:
        print(f"  {len(unscoreable)} citekey(s) unscoreable (no quotable source passage)")
    print(f"Record: {candidates_path}")
    return 0


def crosscheck(drafts_dir, out_dir):
    """Reads labels.json back, recomputes every finding's score fresh
    (rather than persisting a second machine-readable population file that
    would itself carry claim text and need candidates.md's own gitignore
    treatment), and reports whether the score's median separates
    "supported" from "unsupported" -- the real numbers, whatever they are.

    Not run by this task: this task builds and runs `self_check()` and
    `--extract` only. `labels.json` does not exist yet, and writing or
    simulating one is explicitly out of scope -- that judgment must stay
    human. This function exists so the next person can run it once a human
    has judged `candidates.md`.
    """
    labels_path = out_dir / "labels.json"
    if not labels_path.exists():
        print(
            f"no {labels_path} -- judge {out_dir / 'candidates.md'} into it first",
            file=sys.stderr,
        )
        return 1
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    labels = {row["id"]: row for row in payload.get("candidates", [])}

    entailer, reason = entailment.open_entailer()
    if entailer is None:
        print(f"crosscheck: not run -- {reason}", file=sys.stderr)
        return 1
    if not config.LEDGER_PATH.exists():
        print(
            f"no ledger at {config.LEDGER_PATH} -- run `python -m chitragupta.corpus sync`",
            file=sys.stderr,
        )
        return 1

    pool, _per_draft, _unscoreable, _missing, _duplicates = _population(drafts_dir, entailer)
    scores = {row["id"]: row["score"] for row in pool}

    # A label whose id matches no current finding is a stale corpus, draft
    # edit, or model swap between --extract and this run -- reported, not
    # silently dropped, the same complaint bench_overlap_embed.py's own
    # integrity_complaints() raises for its stale-label case.
    stale_labels = sorted(i for i in labels if i not in scores)
    unlabelled = sorted(i for i in scores if i not in labels)

    by_judgment = {}
    for finding_id, score in scores.items():
        row = labels.get(finding_id)
        if row is None:
            continue
        by_judgment.setdefault(row["judgment"], []).append(score)

    summary = {
        judgment: {
            "n": len(vals),
            "min": round(min(vals), 4),
            "median": round(statistics.median(vals), 4),
            "max": round(max(vals), 4),
        }
        for judgment, vals in sorted(by_judgment.items())
    }

    result = {
        "drafts": list(DRAFT_NAMES),
        "labelled": len(labels),
        "matched_to_a_current_finding": sum(len(v) for v in by_judgment.values()),
        "stale_labels": stale_labels,
        "unlabelled_candidates": len(unlabelled),
        "by_judgment": summary,
    }
    if "supported" in summary and "unsupported" in summary:
        result["supported_median_minus_unsupported_median"] = round(
            summary["supported"]["median"] - summary["unsupported"]["median"], 4
        )

    record = out_dir / "crosscheck.json"
    record.write_text(json.dumps(result, indent=1), encoding="utf-8")

    if stale_labels:
        print(
            f"\n  WARNING {len(stale_labels)} label(s) match no current finding "
            f"(e.g. {', '.join(stale_labels[:3])}) -- stale corpus, draft or model"
        )
    print(
        f"\nlabelled: {len(labels)}  "
        f"matched to a current finding: {result['matched_to_a_current_finding']}"
    )
    for judgment, stats in summary.items():
        print(
            f"  {judgment:>12}: n={stats['n']:3d}  min={stats['min']:.3f}  "
            f"median={stats['median']:.3f}  max={stats['max']:.3f}"
        )
    if "supported_median_minus_unsupported_median" in result:
        print(
            "  supported median - unsupported median = "
            f"{result['supported_median_minus_unsupported_median']:+.3f}"
        )
    print(f"Record: {record}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--extract", action="store_true", help="score the four real drafts and write candidates.md"
    )
    ap.add_argument(
        "--crosscheck",
        action="store_true",
        help="merge labels.json with a fresh score pass and report separation",
    )
    ap.add_argument(
        "--drafts",
        help="directory holding survey.md, book-chapter.md, tutorial.md, deep-research.md",
    )
    ap.add_argument(
        "--tag", required=True, help="names bench/results/<tag>/ (path components stripped)"
    )
    args = ap.parse_args(argv)

    self_check()
    out_dir = BENCH_DIR / "results" / Path(args.tag).name

    if args.extract:
        if not args.drafts:
            print("--drafts is required with --extract", file=sys.stderr)
            return 2
        return extract(args.drafts, out_dir)
    if args.crosscheck:
        if not args.drafts:
            print("--drafts is required with --crosscheck", file=sys.stderr)
            return 2
        return crosscheck(args.drafts, out_dir)
    print("one of --extract or --crosscheck is required", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
