"""How often do the contrast and wording rules (#1055) fire, and on what?

The v3 plan's rules `k1-stroke`, `k2-text` and `w4-pictograph` are
objective, so a false positive costs an author an allow; `w1` to `w3`
are advisory, so a noisy one costs only attention. This runs `figure
check` exactly as the command does, one compile per figure, over the
drafted figures, the scaffolds and the exemplars, and reports:

- per rule, how many findings and on which files, with the scaffolds and
  exemplars apart (they must report no objective finding);
- for k1 and k2, the colour pairs behind the findings, most common
  first, which is what says whether the fix is the one rename the rule's
  documentation gives;
- every figure where k1 and k2 were not measured, with why.

It reads figures and writes nothing but its `--json` record. Needs
`lualatex` and `tikz.sty`, like `figure check` itself.

    .venv-full/bin/python bench/bench_contrast_wording.py \\
        --drafts content/drafts --json bench/results/<tag>/contrast_wording.json
"""

import argparse
import json
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bench.bench_connector_rules import figure_files  # noqa: E402
from chitragupta.figure import _check  # noqa: E402

OBJECTIVE = ("k1-stroke", "k2-text", "w4-pictograph")
ADVISORY = ("w1-case", "w2-tag", "w3-gloss")

# `text cgAccent on fill cgAccent!10: 3.42:1, needs 4.5:1` -> the pair,
# with the ground's owner dropped (`zone's fill x` reads as `fill x`).
_PAIR_RE = re.compile(r"^(?:border|line|text) (?P<colour>.+?) on (?:\S+'s )?(?P<ground>.+?): ")


def measure_one(item: tuple[str, Path, str]) -> dict:
    kind, path, label = item
    result = _check.check(path, _check.DEFAULT_WIDTH_PT)
    return {
        "kind": kind,
        "file": label,
        "findings": [
            [f.rule, f.target, f.measurement] for f in result.findings if f.rule in OBJECTIVE
        ],
        "advisory": [
            [f.rule, f.target, f.measurement] for f in result.advisory if f.rule in ADVISORY
        ],
        "not_measured": [[r, why] for r, why in result.not_measured if r == "k2-text"],
    }


def pair(rule: str, measurement: str) -> str | None:
    """`rule: colour on ground` for a k1 or k2 finding, else `None`."""
    match = _PAIR_RE.match(measurement)
    if rule not in ("k1-stroke", "k2-text") or match is None:
        return None
    return f"{rule}: {match.group('colour')} on {match.group('ground')}"


def tally(rows: list[dict]) -> dict:
    """Per-rule counts, overall and on the house figures, and the pairs."""
    reports = [(row, entry) for row in rows for entry in row["findings"] + row["advisory"]]
    fired = Counter(entry[0] for _, entry in reports)
    house = Counter(entry[0] for row, entry in reports if row["kind"] != "draft")
    files = {
        rule: len({row["file"] for row, entry in reports if entry[0] == rule})
        for rule in OBJECTIVE + ADVISORY
    }
    pairs = Counter(pair(entry[0], entry[2]) for _, entry in reports)
    pairs.pop(None, None)
    return {
        "figures": len(rows),
        "fired": {rule: fired[rule] for rule in OBJECTIVE + ADVISORY},
        "fired_on_house_figures": {rule: house[rule] for rule in OBJECTIVE + ADVISORY},
        "files": files,
        "pairs": dict(pairs.most_common()),
        "not_measured": Counter(why for row in rows for _, why in row["not_measured"]),
    }


def self_check() -> None:
    """The planted cases every number here depends on."""
    assert pair("k2-text", "text cgAccent on fill cgAccent!10: 3.42:1, needs 4.5:1") == (
        "k2-text: cgAccent on fill cgAccent!10"
    )
    assert pair("k1-stroke", "line cgAux on zone's fill cgAlt!6: 2.0:1, needs 3:1") == (
        "k1-stroke: cgAux on fill cgAlt!6"
    )
    assert pair("w4-pictograph", '"x" (U+2713) in the label') is None
    rows = [
        {
            "kind": "draft",
            "file": "x/one.tex",
            "findings": [["k2-text", "a", "text cgAux on white: 2.3:1, needs 4.5:1"]],
            "advisory": [["w1-case", '"a"', "m"]],
            "not_measured": [],
        },
        {
            "kind": "scaffold",
            "file": "x/two.tex",
            "findings": [["k2-text", "b", "text cgAux on white: 2.3:1, needs 4.5:1"]],
            "advisory": [],
            "not_measured": [["k2-text", "why"]],
        },
    ]
    counted = tally(rows)
    assert counted["fired"]["k2-text"] == 2 and counted["fired"]["w1-case"] == 1
    assert counted["fired_on_house_figures"] == {
        **dict.fromkeys(OBJECTIVE + ADVISORY, 0),
        "k2-text": 1,
    }
    assert counted["files"]["k2-text"] == 2
    assert counted["pairs"] == {"k2-text: cgAux on white": 2}
    assert counted["not_measured"] == {"why": 1}


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
    print(json.dumps(summary, indent=2, default=dict))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"summary": summary, "figures": rows}, indent=2, default=dict) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
