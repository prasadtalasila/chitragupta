"""How often does each connector rule (#1054) fire, and on what -- before
its thresholds are fixed?

The v3 plan (`plans/fig-xii-figure-drawer-v3.md`, 2c) says to bench the
connector rules over the scaffolds, the exemplars and the drafted figures
first, because a rule that fires on sound figures teaches an author to
allow it rather than read it. This runs `figure check` exactly as the
command does, one compile per figure, and reports:

- per rule, how many findings and on which files, with the scaffolds and
  exemplars apart (#1050, 1e, is what clears those);
- for `c2-tag-clearance`, the gap from every tag on a connector to its
  line, measured both ways: by the tag's node box and by its text box,
  which is the measurement the rule ships with and the reason it does;
- the connectors found, the lines not between two nodes, and every rule
  listed as not measured, with why.

It reads figures and writes nothing but its `--json` record. Needs
`lualatex` and `tikz.sty`, like `figure check` itself.

    .venv-full/bin/python bench/bench_connector_rules.py \\
        --drafts content/drafts --json bench/results/<tag>/connector_rules.json
"""

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from chitragupta.figure import _check  # noqa: E402
from chitragupta.figure._connectors import (  # noqa: E402
    LABEL_PREFIX,
    MM,
    connectors,
    segment_box_gap,
    segments,
)
from chitragupta.review.figure_layout import Drawn, DrawnLine, DrawnNode  # noqa: E402

SCAFFOLDS = REPO_ROOT / "assets" / "tikz"
# The connector rules, and node-overlap, which #1054 widened to every
# node the probe drew.
MEASURED = (*_check.CONNECTOR, "node-overlap")


def figure_files(drafts: Path) -> list[tuple[str, Path, str]]:
    """`(kind, path, label)`: every draft figure, scaffold and exemplar.
    The label is relative (to `--drafts`, or to the repository), so the
    committed record names no one's home directory."""
    found = [
        ("draft", path, f"drafts/{path.relative_to(drafts)}")
        for path in sorted(drafts.rglob("figures/*.tex"))
    ]
    house = [path for path in sorted(SCAFFOLDS.glob("*.tex")) if path.name != "cg-figstyle.tex"]
    found += [("scaffold", path, str(path.relative_to(REPO_ROOT))) for path in house]
    found += [
        ("exemplar", path, str(path.relative_to(REPO_ROOT)))
        for path in sorted((SCAFFOLDS / "exemplars").glob("*.tex"))
    ]
    return found


def tag_gaps(drawn: Drawn) -> list[tuple[float, float | None]]:
    """`(node-box gap, text-box gap)` in mm for every tag on a connector."""
    gaps = []
    for con in connectors(drawn)[0]:
        pieces = segments(con.line.points)
        for name in con.line.labels:
            node = drawn.nodes.get(name)
            if node is None or not name.startswith(LABEL_PREFIX):
                continue
            by_box = min(segment_box_gap(p, q, node.box) for p, q in pieces) / MM
            by_text = (
                min(segment_box_gap(p, q, node.text_box) for p, q in pieces) / MM
                if node.text_box
                else None
            )
            gaps.append((by_box, by_text))
    return gaps


def measure_one(item: tuple[str, Path, str]) -> dict:
    kind, path, label = item
    result = _check.check(path, _check.DEFAULT_WIDTH_PT)
    drawn = result.figure.drawn
    return {
        "kind": kind,
        "file": label,
        "findings": [
            [f.rule, f.target, f.measurement] for f in result.findings if f.rule in MEASURED
        ],
        "not_measured": [[r, why] for r, why in result.not_measured if r in _check.CONNECTOR],
        "connectors": len(connectors(drawn)[0]) if drawn else None,
        "loose": result.loose_lines,
        "tag_gaps": tag_gaps(drawn) if drawn else [],
    }


def tally(rows: list[dict]) -> dict:
    """Per-rule counts, overall and on the scaffolds and exemplars."""
    fired = Counter(rule for row in rows for rule, _, _ in row["findings"])
    house = Counter(
        rule for row in rows if row["kind"] != "draft" for rule, _, _ in row["findings"]
    )
    files = {
        rule: sorted(
            {Path(row["file"]).name for row in rows for r, _, _ in row["findings"] if r == rule}
        )
        for rule in MEASURED
    }
    return {
        "figures": len(rows),
        "connectors": sum(row["connectors"] or 0 for row in rows),
        "loose": sum(row["loose"] or 0 for row in rows),
        "fired": {rule: fired[rule] for rule in MEASURED},
        "fired_on_house_figures": {rule: house[rule] for rule in MEASURED},
        "files": files,
        "not_measured": Counter(
            f"{Path(row['file']).name}: {why}"
            for row in rows
            for rule, why in row["not_measured"]
            if rule == "c1-orthogonal"
        ),
    }


def histogram(values: list[float]) -> dict[str, int]:
    bands = [("<0.1", 0.1), ("0.1-0.8", 0.8), ("0.8-3", 3.0), (">3", float("inf"))]
    counts = dict.fromkeys((name for name, _ in bands), 0)
    for value in values:
        counts[next(name for name, top in bands if value < top)] += 1
    return counts


def self_check() -> None:
    """The planted cases every number here depends on: each rule fires on
    its own defect and only there, `tally` counts what it is given, and
    the gap histogram bands a value where the rule's thresholds do."""
    a = DrawnNode("a", "rectangle", (0.0, 0.0, 40.0, 20.0), None)
    b = DrawnNode("b", "rectangle", (100.0, 60.0, 140.0, 80.0), None)
    tag = DrawnNode("cgu-1", "rectangle", (60.0, 30.0, 80.0, 40.0), (61.0, 31.0, 79.0, 39.0))
    diagonal = DrawnLine(1, ((40.0, 10.0), (100.0, 70.0)), False, False, False, ("cgu-1",))
    drawn = Drawn({"a": a, "b": b, "cgu-1": tag}, [diagonal])
    gaps = tag_gaps(drawn)
    assert len(gaps) == 1 and gaps[0][1] is not None and gaps[0][1] < gaps[0][0] + 1, gaps
    rows = [
        {
            "kind": "draft",
            "file": "x/one.tex",
            "findings": [["c1-orthogonal", "a->b", "m"]],
            "not_measured": [],
            "connectors": 1,
            "loose": 2,
            "tag_gaps": [],
        },
        {
            "kind": "scaffold",
            "file": "x/two.tex",
            "findings": [["c1-orthogonal", "a->b", "m"]],
            "not_measured": [["c1-orthogonal", "why"]],
            "connectors": 3,
            "loose": None,
            "tag_gaps": [],
        },
    ]
    counted = tally(rows)
    assert counted["fired"]["c1-orthogonal"] == 2 and counted["fired"]["c2-tag-clearance"] == 0
    assert counted["fired_on_house_figures"]["c1-orthogonal"] == 1
    assert (counted["connectors"], counted["loose"]) == (4, 2)
    assert counted["files"]["c1-orthogonal"] == ["one.tex", "two.tex"]
    assert histogram([0.0, 0.5, 0.8, 2.9, 3.0, 9.0]) == {
        "<0.1": 1,
        "0.1-0.8": 1,
        "0.8-3": 2,
        ">3": 2,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--drafts", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    self_check()
    items = figure_files(args.drafts.resolve())
    with ProcessPoolExecutor(args.workers) as pool:
        rows = list(pool.map(measure_one, items))
    summary = tally(rows)
    gaps = [g for row in rows for g in row["tag_gaps"]]
    summary["c2_gap_by_node_box_mm"] = histogram([box for box, _ in gaps])
    summary["c2_gap_by_text_box_mm"] = histogram([text for _, text in gaps if text is not None])
    summary["c2_tags_without_text_box"] = sum(1 for _, text in gaps if text is None)
    print(json.dumps(summary, indent=2, default=dict))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"summary": summary, "figures": rows}, indent=2, default=dict) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
