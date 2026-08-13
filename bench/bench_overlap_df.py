"""Whether a gram's corpus **document frequency** separates the false
positives #130 measured from genuine reuse -- groundwork for #133/#134.

`bench_overlap_gate.py` measured what an `overlap_gate` would block over
a real book and found precision 0.00 at every threshold: all 16 findings
at or above 15 words are false positives, and 13 of them are only
suppressible today by hand, through #128's per-host allowlist. Its own
label vocabulary says why in one line -- `third-party-echo`: "the draft
can only cite one source for a definition that many corpus papers
reproduce, so every other one reports as UNCITED SOURCE".

"Many corpus papers reproduce it" is a *measurable* property, and this
repository already stores it. `overlap_index.postings_for_gram` returns
every `(citekey, page, position)` posting for a gram, so the count of
**distinct citekeys** in those postings is that gram's document
frequency. No model, no new artefact, no new index: DF is a projection of
the index #110 already built.

This benchmark asks whether DF discriminates, and it needs two arms to
answer that, because the book supplies only one side of the question:

- **The book arm** is 15 chapters against the 497-document corpus they
  were written from, joined to `bench/results/2026-08-13-overlap-gate/
  labels.json`. Every label there is `fp`, so this arm can measure how
  much DF *suppresses* and is structurally incapable of measuring what it
  destroys.
- **The control arm** is `bench/fixtures/cloud-computing-for-digital-
  twins-planted-reuse.md`, whose planted paragraph is verbatim from
  `aguzzi_cloud_2020`, a paper the draft never cites (bench/RESULTS.md
  documents the plant). That is the true positive the book does not
  contain, and the only thing that stops a suppression rule from being
  scored on its ability to suppress everything.

A rule that suppresses the book's findings and keeps the fixture's is
doing the thing #128's allowlist does by hand. A rule that suppresses
both is a gate that has been talked out of firing.

**The statistic is the median DF over a run's 8-grams**, not the minimum,
and that choice is load-bearing rather than cosmetic. Two artefacts put
spurious zeroes and ones into the profile: a gap-merged run
(`scan_findings`' `--gap`) contains draft grams that are in no source at
all, and a run spanning a source page break reconstructs across the join
(#131), so the window straddling it matches nothing. Both drag a minimum
to 0 or 1 while every other gram in the run sits at 4. A median absorbs
both; a minimum reports the artefact.

**Read the grams off `fragment`, never off `draft_text`.** They are not
the same string: `fragment` is the normalised, space-joined word stream
the index is keyed on, and `draft_text` is the draft as written --
newlines, hyphenation and all. Hashing `draft_text` yields a profile of
all-zero DF that looks exactly like "this run appears in no corpus paper"
for a run that demonstrably matched one. The exact tier matches the same
word sequence on both sides, so `fragment` is the run.

**DF is corpus-state-dependent, and that is the finding's main caveat.**
`index.json`'s key is a sha256 over every document's own change-detection
key, so adding a paper or re-parsing one moves every DF in this table. A
suppression built on it is deterministic *given a corpus state*, which is
a weaker guarantee than `src.draft gate`'s and the same shape as #128's
per-host allowlist. The corpus key is recorded in the output for exactly
that reason. #130 is where that trade is priced, not here.

Nothing this script writes carries `fragment`, `context` or `draft_text`:
`bench/results/` is committed and those fields are extracts of
copyrighted PDFs. DF profiles are counts, so they are safe to record.

    python3 bench/bench_overlap_df.py --tag 2026-08-13-overlap-df \\
        --drafts content/drafts/books/digital-twins-for-software-engineers

Needs a synced corpus (`python -m src.corpus sync`) and pays one cold
corpus-index build on first run; every run after that is warm.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from src import config, overlap_index  # noqa: E402

# The same floor as bench_overlap_gate.py, and for the same reason: the
# hand labels this arm joins to were only ever authored at or above it,
# so a lower floor here would report unlabelled findings as if the
# labelling had considered and passed on them.
SWEEP_FLOOR = 15

# The planted-reuse control. Its 18-word run from `aguzzi_cloud_2020` is
# the only genuine uncredited reuse either arm contains.
CONTROL_FIXTURE = BENCH_DIR / "fixtures" / "cloud-computing-for-digital-twins-planted-reuse.md"

# Candidate suppression thresholds. D = 1 is degenerate -- every matched
# gram is in at least one paper by construction -- and is swept anyway so
# the table shows the degenerate end rather than starting after it.
THRESHOLDS = (1, 2, 3, 4, 5, 6)

# Recorded per finding: identity, size, and the DF profile. Deliberately
# not the payload's text fields (see the module docstring).
KEPT_FIELDS = (
    "id", "citekey", "page", "end_page", "tier", "span_words",
    "matched_words", "line", "cites_source", "quoted", "severity",
)


def df_profile(index, fragment):
    """The document frequency of every 8-gram in `fragment`.

    DF is `len({citekey for citekey, _, _ in postings})` -- distinct
    *documents*, not postings. A paper that repeats its own sentence
    twice contributes one, which is what "how much of the field says
    this" means; counting postings would let one verbose source imitate
    a field-wide consensus.
    """
    grams = overlap_index.gram_hashes(fragment.split(), index.n)
    return [
        len({citekey for citekey, _, _ in overlap_index.postings_for_gram(index, gram)})
        for gram in grams
    ]


def summarise(profile):
    """`(grams, min, median, max)` for one run, or zeroes for a run too
    short to hold a single n-gram.

    A run shorter than `n` produces no grams at all. That cannot happen
    at this benchmark's floor of 15 words, but it is the shape the
    control arm hits if someone lowers it, and returning zeroes keeps the
    table printable instead of raising inside a statistics call.
    """
    if not profile:
        return {"grams": 0, "min_df": 0, "median_df": 0, "max_df": 0}
    return {
        "grams": len(profile),
        "min_df": min(profile),
        "median_df": int(statistics.median(profile)),
        "max_df": max(profile),
    }


def eligible(finding):
    """Whether #130's predicate could ever block on `finding`.

    Copied in shape from `bench_overlap_gate.py::eligible` rather than
    imported, because the two benchmarks are independently re-runnable
    records and a shared helper would let a later edit to one silently
    restate what the other measured.
    """
    if finding["tier"] not in {"exact", "skip-gram"}:
        return False
    return not (finding["quoted"] and finding["cites_source"])


def scan_arm(index, drafts):
    """Every finding at or above `SWEEP_FLOOR` in `drafts`, with its DF
    profile attached.

    References masking is left at its default -- on. The unmasked arm is
    `bench_overlap_gate.py`'s business; repeating it here would measure
    a bibliography's shared titles, where DF is trivially high and says
    nothing about prose.
    """
    from src.review import verbatim_check as vc

    out = []
    for draft in drafts:
        found, _, _ = vc.scan_findings(str(draft))
        for finding in found:
            payload = vc.published(finding)
            if payload["span_words"] < SWEEP_FLOOR:
                continue
            record = {field: payload[field] for field in KEPT_FIELDS}
            record["draft"] = draft.name
            record.update(summarise(df_profile(index, payload["fragment"])))
            out.append(record)
    return out


def sweep(book, control, labels, thresholds):
    """What `median_df >= D` suppresses in each arm.

    Both counts matter and neither is meaningful alone. `fp_suppressed`
    is the win: hand-allowlisted boilerplate removed mechanically.
    `tp_suppressed` is the cost, and it can only be counted because the
    control arm exists -- over the book alone every row would report a
    perfect rule, since the book contains no genuine reuse to lose.
    """
    gateable = [f for f in book if eligible(f)]
    control_gateable = [f for f in control if eligible(f) and not f["cites_source"]]
    rows = []
    for threshold in thresholds:
        hit = [f for f in gateable if f["median_df"] >= threshold]
        fps = [f for f in hit if labels.get(f["id"], {}).get("label") == "fp"]
        lost = [f for f in control_gateable if f["median_df"] >= threshold]
        rows.append({
            "threshold": threshold,
            "suppressed": len(hit),
            "fp_suppressed": len(fps),
            "unlabelled_suppressed": len(hit) - len(fps),
            "remaining": len(gateable) - len(hit),
            "control_findings": len(control_gateable),
            "tp_suppressed": len(lost),
        })
    return rows


def by_class(book, labels):
    """DF medians grouped by the hand-authored finding class.

    The classes are `bench_overlap_gate.py`'s, and this is the table that
    says whether DF is measuring what the labeller was seeing by eye or
    something else that happens to correlate with it.
    """
    groups = {}
    for finding in book:
        label = labels.get(finding["id"], {})
        groups.setdefault(label.get("class", "unlabelled"), []).append(finding["median_df"])
    return {
        name: {
            "findings": len(medians),
            "median_df_min": min(medians),
            "median_df_max": max(medians),
        }
        for name, medians in sorted(groups.items())
    }


def self_check():
    """Prove the profile and the sweep can see a difference first.

    The same guard `bench_overlap_gate.py::self_check` exists for, with
    one addition specific to this benchmark: a `fragment`/`draft_text`
    mix-up (see the module docstring) produces an all-zero profile, and
    an all-zero profile suppresses nothing at every threshold -- which
    prints identically to "DF found no boilerplate". The median assertion
    below is what tells those two apart.
    """
    assert summarise([4, 4, 0, 4])["median_df"] == 4, "median must absorb a gap artefact"
    assert summarise([])["grams"] == 0, "a run shorter than n has no grams"
    boilerplate = {"id": "a", "tier": "exact", "quoted": False,
                   "cites_source": False, "median_df": 4}
    reuse = {"id": "b", "tier": "exact", "quoted": False,
             "cites_source": False, "median_df": 1}
    rows = sweep([boilerplate, reuse], [reuse], {"a": {"label": "fp"}}, (2,))
    assert rows[0]["fp_suppressed"] == 1, "a median-4 run must suppress at D=2"
    assert rows[0]["tp_suppressed"] == 0, "a median-1 run must survive D=2"
    assert rows[0]["remaining"] == 1, "the surviving run must still be counted"


def print_arm(name, findings):
    """One line per finding, sorted by the statistic under test."""
    print(f"\n{name}: {len(findings)} finding(s) at or above {SWEEP_FLOOR} words")
    print(f"  {'id':14}{'draft':26}{'words':>6}{'grams':>6}{'min':>5}{'med':>5}{'max':>5}")
    for finding in sorted(findings, key=lambda f: -f["median_df"]):
        print(f"  {finding['id'][:12]:14}{finding['draft'][:24]:26}"
              f"{finding['span_words']:>6}{finding['grams']:>6}"
              f"{finding['min_df']:>5}{finding['median_df']:>5}{finding['max_df']:>5}")


def print_sweep(rows):
    """The suppression table, both arms on one line per threshold."""
    print(f"\n{'D':>3}{'suppressed':>12}{'fp':>5}{'unlab':>7}{'remaining':>11}"
          f"{'tp_lost':>9}{'of_tp':>7}")
    for row in rows:
        print(f"{row['threshold']:>3}{row['suppressed']:>12}{row['fp_suppressed']:>5}"
              f"{row['unlabelled_suppressed']:>7}{row['remaining']:>11}"
              f"{row['tp_suppressed']:>9}{row['control_findings']:>7}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--drafts", required=True,
                        help="directory of drafts to scan (*.md)")
    parser.add_argument("--tag", required=True,
                        help="names the output directory, bench/results/<tag>/. "
                             "Passed in rather than derived from the clock, so a "
                             "re-run over an unchanged corpus reproduces the same "
                             "record byte for byte.")
    parser.add_argument("--labels",
                        default="bench/results/2026-08-13-overlap-gate/labels.json",
                        help="hand-authored ground truth, keyed by finding id. "
                             "Shared with bench_overlap_gate.py rather than "
                             "duplicated: the same findings, the same labels.")
    parser.add_argument("--control", default=str(CONTROL_FIXTURE),
                        help="the planted-reuse fixture supplying the true positive")
    parser.add_argument("--out", help="output directory (default: bench/results/<tag>)")
    return parser.parse_args()


def main():
    args = parse_args()
    self_check()

    out_dir = Path(args.out) if args.out else BENCH_DIR / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    # `p.name[0].isdigit()` is bench_overlap_gate.py's own selector, and
    # matching it is what makes the two records comparable: a table of
    # contents is a list of chapter titles, and scanning it measures the
    # book against itself rather than against the corpus.
    drafts = sorted(p for p in Path(args.drafts).glob("*.md") if p.name[0].isdigit())
    if not drafts:
        sys.exit(f"no numbered chapters under {args.drafts}")
    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))["labels"]

    print("  building the corpus index ...")
    index = overlap_index.build_corpus_index()
    header = json.loads(
        (Path(config.OVERLAP_DIR) / "index.json").read_text(encoding="utf-8")
    )
    print(f"    {len(index.citekeys)} document(s), {len(index.grams)} distinct gram(s)")

    print(f"  scanning {len(drafts)} draft(s) ...")
    book = scan_arm(index, drafts)
    print("  scanning the control fixture ...")
    control = scan_arm(index, [Path(args.control)])

    print_arm("book", book)
    print_arm("control (planted reuse)", control)
    rows = sweep(book, control, labels, THRESHOLDS)
    print_sweep(rows)

    unlabelled = [f["id"] for f in book if f["id"] not in labels]
    if unlabelled:
        print(f"\n  {len(unlabelled)} finding(s) carry no label -- the corpus has "
              f"moved since labels.json was authored, and every count above is "
              f"scored against a partial ground truth.")

    record = {
        "about": __doc__.split("\n\n")[0].replace("\n", " "),
        "corpus": {
            "documents": len(index.citekeys),
            "grams": len(index.grams),
            "corpus_key": header["key"],
            "tokenizer_version": header["tokenizer_version"],
            "n": index.n,
        },
        "sweep_floor": SWEEP_FLOOR,
        "statistic": "median document frequency over a run's n-grams",
        "book": book,
        "control": control,
        "sweep": rows,
        "by_class": by_class(book, labels),
        "unlabelled": unlabelled,
    }
    path = out_dir / "overlap_df.json"
    path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"\nRecord: {path}")


if __name__ == "__main__":
    main()
