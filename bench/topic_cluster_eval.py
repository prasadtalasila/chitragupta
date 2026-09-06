"""What the app's MCL inflation default is worth, scored against
hand-written groupings (#689).

`assets/webapp/families.js` clusters each edge family separately at an
inflation the reader can drag, and the slider opens at 2.0. Nothing said
why 2.0. MCL is famously sensitive to exactly that parameter --
`docs/TOPIC-DISCOVERY-GRAPH.md` §5.2 says so -- so a default nobody has
measured is a default nobody can move safely: raise it and the reader
gets more, smaller clusters; lower it and the corpus melts into one, and
the disagreement grid changes shape either way.

`docs/TOPIC-DISCOVERY-GRAPH.md` §9 names the fix and the precedent: add
"these topics belong together" groupings to `content/topic_gold.toml`
and the inflation stops being a feel, exactly as the gold queries did
for `[discover].min_similarity`. `assets/style/topic_gold.toml.example`
is the template; the `[[group]]` records are yours to write, because
naming a handful of groupings for your own corpus is cheaper and more
trustworthy than generating them.

    [[group]]
    name = "co-simulation"
    topics = ["fmi", "co-simulation", "model exchange"]

**The partition scored is the one the reader is shown.** This script does
not implement MCL: it drives `assets/webapp/families.js` through `node`,
the same module `node --test tests/webapp/families.test.js` exercises. A
Python re-implementation would be a second version of the numbers in the
browser, free to disagree with it -- the exact hazard that module's own
docstring cites when it declines cytoscape's `markovClustering`.

Scoring is **pairwise, over the gold-covered topics only**. Grouping gold
is deliberately partial: a handful of groupings over a corpus of 131
topics, silent about the rest. So the universe is the topics some gold
group names, and within it every pair is a trial -- same gold group and
same cluster is a tp, same cluster but different gold groups an fp, same
gold group but different clusters an fn. Adjusted Rand would want a
complete reference partition, which grouping gold is not.

Per family, never fused: one score over a merged graph is the fusion the
design refuses, and the two families answer different questions.

    python bench/topic_cluster_eval.py
    python bench/topic_cluster_eval.py --gold content/topic_gold.toml \\
        --out bench/results/cluster.json

Read-only: it reads `content/topic_graph.json` and the gold file, and
writes only where `--out` names a file.

What `self_check()` cannot see: a gold file whose groupings are
themselves wrong, and whether `families.js` clusters *well* -- this
scores the partition it produces, not the algorithm's fitness for the
job.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FAMILIES_JS = REPO / "assets" / "webapp" / "families.js"
INDEX_HTML = REPO / "assets" / "webapp" / "index.html"
FAMILIES = ("overlap", "semantic")

# The slider's own range, in tenths, so the sweep spans exactly what a
# reader can select and nothing they cannot. Every other position, not
# every one: MCL over 131 topics is O(n^3) per iteration and the reader's
# step of 0.1 doubles the run for a resolution the score does not have.
# `report()` prints the step rather than leaving the gaps to be noticed,
# because a swept range that quietly skipped half of itself would read
# as an exhaustive answer.
STEP_TENTHS = 2
SLIDER_RE = re.compile(r'<input id="inflation"[^>]*\bmin="(\d+)"[^>]*\bmax="(\d+)"')
DEFAULT_RE = re.compile(r'<input id="inflation"[^>]*\bvalue="(\d+)"')

# One clustering per family per inflation, in one node process: the
# module is loaded once and the payload crosses the boundary once.
DRIVER = """
const fam = require(process.argv[1]);
let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  const req = JSON.parse(raw);
  const out = req.inflations.map((inflation) => {
    const row = { inflation: inflation };
    req.families.forEach((family) => {
      row[family] = fam.cluster(req.data, family, inflation).clusterOf;
    });
    return row;
  });
  process.stdout.write(JSON.stringify(out));
});
"""


def slider_sweep(html: str) -> tuple:
    """(the inflations the slider offers, the one it opens at), read off
    the shipped control rather than restated here -- a sweep that no
    longer covers the reader's range would measure the wrong thing, and
    silently."""
    span = SLIDER_RE.search(html)
    opens = DEFAULT_RE.search(html)
    if not span or not opens:
        raise ValueError(
            "assets/webapp/index.html no longer states the inflation slider "
            "in the shape this script reads (min/max/value on #inflation)"
        )
    low, high = int(span.group(1)), int(span.group(2))
    sweep = [tenths / 10 for tenths in range(low, high + 1, STEP_TENTHS)]
    # The default may not fall on the sampled grid -- it must be scored
    # whether or not it does, since it is the row the reader came for.
    opens_at = int(opens.group(1)) / 10
    return sorted(set(sweep) | {opens_at}), opens_at


def gold_universe(groups: list) -> dict:
    """Topic -> the gold group naming it. A topic in two groups is a gold
    file that contradicts itself, and saying so beats scoring it."""
    universe = {}
    for group in groups:
        for topic in group["topics"]:
            if topic in universe:
                raise ValueError(
                    f"gold topic {topic!r} is in two groups "
                    f"({universe[topic]!r} and {group['name']!r})"
                )
            universe[topic] = group["name"]
    return universe


def score(universe: dict, cluster_of: dict) -> dict:
    """Pairwise precision / recall / F1 over the gold-covered topics.

    `missing` is not a rounding detail: a gold label that names no topic
    in the graph scores nothing at all, and reported as a zero it would
    read as a partition that failed rather than a gold file that has
    drifted past a re-run of the stages.
    """
    present = [topic for topic in universe if topic in cluster_of]
    tp = fp = fn = 0
    for a, b in combinations(sorted(present), 2):
        same_gold = universe[a] == universe[b]
        same_cluster = cluster_of[a] == cluster_of[b]
        tp += same_gold and same_cluster
        fp += same_cluster and not same_gold
        fn += same_gold and not same_cluster
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "scored_topics": len(present),
        "missing": sorted(set(universe) - set(present)),
        # Both counts, because one of them alone misleads: `compared` is
        # every pair in the universe (the trials), `gold_pairs` only the
        # same-group ones (what recall is out of). Reporting tp+fp+fn as
        # "pairs" read as the first and was the second minus the true
        # negatives, which is neither.
        "compared": len(present) * (len(present) - 1) // 2,
        "gold_pairs": tp + fn,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "clusters": len(set(cluster_of.values())),
    }


def _f1(precision, recall):
    """None when there was nothing to score, 0.0 when there was and the
    partition got none of it. The distinction is the whole point: a gold
    file whose groups are all singletons has no pairs, and reporting that
    as 0.0 would be indistinguishable from a partition that put every
    gold pair in a different cluster. Guarding on falsiness rather than
    on None collapsed the two back together -- a precision of exactly 0.0
    read as "nothing to score" -- so a real zero disappeared from the
    sweep, and `best()` skipped the row instead of ranking it last."""
    if precision is None or recall is None:
        return None
    if not precision + recall:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def cluster_sweep(data: dict, inflations: list) -> list:
    """`families.js`'s own clustering, once per family per inflation."""
    request = json.dumps({"data": data, "inflations": inflations, "families": list(FAMILIES)})
    done = subprocess.run(
        ["node", "-e", DRIVER, str(FAMILIES_JS)],
        input=request,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        raise RuntimeError(f"node failed clustering: {done.stderr.strip()[:400]}")
    return json.loads(done.stdout)


def rows_for(universe: dict, sweep: list) -> dict:
    return {
        family: [{"inflation": row["inflation"], **score(universe, row[family])} for row in sweep]
        for family in FAMILIES
    }


def best(rows: list) -> dict:
    """The highest-F1 row, ties going to the lower inflation -- the
    default's own direction, so a tie never reads as an argument to
    move."""
    scored = [row for row in rows if row["f1"] is not None]
    return min(scored, key=lambda row: (-row["f1"], row["inflation"])) if scored else {}


def evaluate(gold_path: Path, graph: dict, html: str) -> tuple:
    """(the sweep per family, the shipped default). Every way the two
    input files can fail to say what this script reads raises
    `ValueError` with the reason, so `main()` has one thing to report
    rather than a traceback per shape."""
    groups = tomllib.loads(gold_path.read_text(encoding="utf-8")).get("group", [])
    if not groups:
        raise ValueError(
            f"{gold_path} holds no [[group]] records; "
            "see assets/style/topic_gold.toml.example for the shape."
        )
    inflations, shipped = slider_sweep(html)
    return rows_for(gold_universe(groups), cluster_sweep(graph, inflations)), shipped


def report(by_family: dict, shipped: float) -> str:
    sampled = sorted({row["inflation"] for rows in by_family.values() for row in rows})
    lines = [
        f"inflation swept {sampled[0]:.1f}-{sampled[-1]:.1f} (the slider's own range) "
        f"in steps of {STEP_TENTHS / 10:.1f}, {len(sampled)} settings scored per family"
    ]
    for family, rows in by_family.items():
        topics = rows[0]["scored_topics"]
        lines.append(
            f"\n{family}: {topics} gold {'topic' if topics == 1 else 'topics'} scored, "
            f"{rows[0]['compared']} pairs compared, "
            f"{rows[0]['gold_pairs']} of them same-group"
        )
        if rows[0]["missing"]:
            lines.append(f"  gold topics not in the graph: {', '.join(rows[0]['missing'])}")
        lines.append("  inflation  clusters  precision  recall     f1")
        for row in rows:
            mark = " <- shipped default" if row["inflation"] == shipped else ""
            lines.append(
                f"  {row['inflation']:>9.1f}  {row['clusters']:>8}  "
                f"{_cell(row['precision'])}  {_cell(row['recall'])}  {_cell(row['f1'])}{mark}"
            )
        top = best(rows)
        if not top:
            lines.append("  no pair in this family scored: the gold groups share no cluster")
            continue
        here = next(row for row in rows if row["inflation"] == shipped)
        lines.append(
            f"  best f1 {top['f1']:.3f} at inflation {top['inflation']:.1f}; "
            f"shipped default {shipped:.1f} scores {_cell(here['f1']).strip()}"
        )
    return "\n".join(lines)


def _cell(value) -> str:
    return f"{value:>9.3f}" if value is not None else f"{'--':>9}"


def self_check() -> None:
    """Fabricate a difference and assert the score sees it. Nothing in
    the test suite covers `bench/` (see bench/README.md), so this runs on
    every invocation instead."""
    universe = gold_universe(
        [{"name": "g1", "topics": ["a", "b"]}, {"name": "g2", "topics": ["c", "d"]}]
    )
    perfect = score(universe, {"a": "x", "b": "x", "c": "y", "d": "y"})
    shuffled = score(universe, {"a": "x", "b": "y", "c": "x", "d": "y"})
    assert perfect["f1"] == 1.0, perfect
    assert shuffled["f1"] is None or shuffled["f1"] < perfect["f1"], shuffled
    # One cluster for everything wins recall and must lose precision --
    # the collapse a too-low inflation produces, which an F1 that only
    # tracked recall would report as the best setting available.
    melted = score(universe, {"a": "x", "b": "x", "c": "x", "d": "x"})
    assert melted["recall"] == 1.0 and melted["precision"] < 1.0, melted
    # A gold group of one topic contributes no pair, and no-pairs must
    # not read as a perfect score.
    lone = score(gold_universe([{"name": "g", "topics": ["a"]}]), {"a": "x"})
    assert lone["gold_pairs"] == 0 and lone["f1"] is None, lone
    # The two counts are not the same number, and swapping them would
    # misreport the sweep rather than fail it: four topics in two groups
    # are six pairs compared, two of them same-group.
    assert (perfect["compared"], perfect["gold_pairs"]) == (6, 2), perfect
    # A partition that gets every gold pair wrong scores 0.0, not None:
    # a real zero must be rankable, and must not read as the no-pairs
    # case above.
    wrong = score(universe, {"a": "x", "b": "y", "c": "y", "d": "x"})
    assert wrong["tp"] == 0 and wrong["f1"] == 0.0, wrong
    # A gold topic the graph does not have is reported, not scored.
    drifted = score(universe, {"a": "x", "b": "x", "c": "y"})
    assert drifted["missing"] == ["d"], drifted
    # Ties go to the lower inflation, so a tie is never an argument to move.
    assert best([{"inflation": 3.0, "f1": 0.5}, {"inflation": 1.5, "f1": 0.5}])["inflation"] == 1.5


def _missing(gold_path: Path) -> str:
    """What is absent, named. A script here reports a missing input
    rather than a zero that looks like a measurement (bench/README.md)."""
    if not shutil.which("node"):
        return "node is not on PATH, and the partition scored is families.js's own."
    if not gold_path.exists():
        return f"No gold set at {gold_path}. Start from assets/style/topic_gold.toml.example."
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gold", default=None, help="gold file (default: content/topic_gold.toml)")
    ap.add_argument("--out", default=None, help="write the full sweep as JSON to this path")
    args = ap.parse_args(argv)

    self_check()

    # Imported after self_check() and inside main(), like every bench
    # script: config resolves PROJECT_ROOT from the cwd at import time.
    from chitragupta import config
    from chitragupta.discover import _data

    gold_path = Path(args.gold) if args.gold else config.CONTENT_DIR / "topic_gold.toml"
    absent = _missing(gold_path)
    if absent:
        print(absent)
        return 1
    try:
        by_family, shipped = evaluate(
            gold_path, _data.load_graph(), INDEX_HTML.read_text(encoding="utf-8")
        )
    except ValueError as exc:
        print(exc)
        return 1
    print(report(by_family, shipped))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"shipped_default": shipped, "families": by_family}, indent=2),
            encoding="utf-8",
        )
        print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
