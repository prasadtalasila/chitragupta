"""How often an unchanged skill would fail `--compare`, from measured runs.

For each (harness, skill), both arms of a comparison are drawn from the
same measured Tier 2 runs, with replacement, `--runs` an arm, and judged
by `skill_commands.judge`, the rule `--compare` applies. Since both arms
come from one skill, every FAIL is a false fail. Whole runs are drawn,
so a run that derails takes all its commands with it, which is how the
local harnesses fail. Every draw is enumerated, not sampled: with 3 to 6
runs a skill that is at most 6**3 * 6**3 pairs, so the rate is exact for
those runs and needs no seed.

`--model commands` draws each command, the gate and the timeout row
independently instead, each at its measured rate, `--trials` times with
a fixed seed. It ignores that a derailed run loses its commands
together, so it overstates the rate wherever runs fail whole; it is
here because the 2026-11-13 estimate on #1210 was read off it, and a new
rate is only comparable with an old one under the same model.

    python bench/simulate_false_fail.py FILE... [--runs 3] [--model runs|commands]
        [--trials 20000] [--json OUT]

Each FILE is a `tier2.json` (a JSON list of runs). A (harness, skill) in
more than one FILE is taken from the last FILE that has it, so list the
oldest first: an older baseline, then each skill's newer rows.

Prints, per harness, each skill's false-fail and inconclusive rate, and
for each skill the false-fail rate over all three harnesses: the chance
that at least one harness fails it, the harnesses drawn independently.
`bench/` sits outside the test suite and its coverage, so `self_check()`
runs on every invocation (bench/README.md).
"""

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

from skill_commands import (
    FAIL,
    GATE,
    INCONCLUSIVE,
    _counts,
    judge,
    measured,
    usable,
)


def latest_groups(paths: list) -> dict:
    """{(harness, skill): rows}, each group from the last file holding it."""
    groups: dict = {}
    for path in paths:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
        found: dict = {}
        for row in rows:
            found.setdefault((row["harness"], row["skill"]), []).append(row)
        groups.update(found)
    return groups


def rates(rows: list, runs: int) -> "tuple[float, float]":
    """The (fail, inconclusive) rate of an unchanged skill whose runs are
    `rows`, over every pair of `runs`-run arms drawn from them."""
    arms = list(itertools.product(range(len(rows)), repeat=runs))
    fail = inconclusive = 0
    for before in arms:
        for after in arms:
            verdict, _ = judge([rows[i] for i in before], [rows[i] for i in after])
            fail += verdict == FAIL
            inconclusive += verdict == INCONCLUSIVE
    total = len(arms) ** 2
    return fail / total, inconclusive / total


def command_rates(rows: list, runs: int, trials: int, seed: int) -> "tuple[float, float]":
    """`rates()` under the independent model: each key of a synthetic run
    is drawn on its own, at the share of measured runs it held."""
    good = usable(rows)
    if not good:
        return 0.0, 1.0
    counts = _counts(good)
    shares = {key: n / len(good) for key, n in counts.items()}
    kept = measured(rows)
    clock = sum(r.get("exit") in ("timeout", "error") for r in kept) / max(len(kept), 1)
    expected = list(dict.fromkeys(k for r in good for k in r.get("expected", [])))
    rng = random.Random(seed)

    def draw() -> dict:
        if rng.random() < clock:
            return {"exit": "timeout", "expected": expected}
        ran = [
            k for k, p in shares.items() if k != GATE and not k.startswith("(") and rng.random() < p
        ]
        forbidden = [
            k[len("(forbidden) ") :]
            for k, p in shares.items()
            if k.startswith("(forbidden) ") and rng.random() < p
        ]
        gate = 0 if rng.random() < shares[GATE] else 1
        return {
            "exit": 0,
            "gate": gate,
            "expected": expected,
            "ran_all": ran,
            "forbidden_ran": forbidden,
        }

    fail = inconclusive = 0
    for _ in range(trials):
        verdict, _ = judge([draw() for _ in range(runs)], [draw() for _ in range(runs)])
        fail += verdict == FAIL
        inconclusive += verdict == INCONCLUSIVE
    return fail / trials, inconclusive / trials


def simulate(
    groups: dict, runs: int, model: str = "runs", trials: int = 20000, seed: int = 1210
) -> dict:
    """{harness: {skill: {"fail", "inconclusive", "runs"}}}."""
    out: dict = {}
    for (harness, skill), rows in sorted(groups.items()):
        if model == "runs":
            fail, inconclusive = rates(rows, runs)
        else:
            fail, inconclusive = command_rates(rows, runs, trials, seed)
        out.setdefault(harness, {})[skill] = {
            "fail": fail,
            "inconclusive": inconclusive,
            "runs": len(rows),
        }
    return out


def over_harnesses(result: dict, harnesses: list) -> dict:
    """{skill: chance at least one of `harnesses` fails it}, for the
    skills every one of them measured."""
    skills = set.intersection(*(set(result.get(h, {})) for h in harnesses))
    combined = {}
    for skill in sorted(skills):
        passes = 1.0
        for harness in harnesses:
            passes *= 1 - result[harness][skill]["fail"]
        combined[skill] = 1 - passes
    return combined


def report(result: dict) -> None:
    for harness, skills in result.items():
        print(f"\n{harness}")
        for skill, row in skills.items():
            print(
                f"  {skill:<26} false fail {row['fail']:6.1%}   "
                f"inconclusive {row['inconclusive']:6.1%}   ({row['runs']} runs)"
            )
        fails = [row["fail"] for row in skills.values()]
        print(f"  {'range over skills':<26} {min(fails):.1%} to {max(fails):.1%}")
    harnesses = list(result)
    if len(harnesses) > 1:
        combined = over_harnesses(result, harnesses)
        print(f"\nover {', '.join(harnesses)} (at least one fails)")
        for skill, rate in combined.items():
            print(f"  {skill:<26} {rate:6.1%}")
        if combined:
            print(
                f"  {'range over skills':<26} "
                f"{min(combined.values()):.1%} to {max(combined.values()):.1%}"
            )


def self_check() -> None:
    """Identical runs never fail; a command that ran in only some runs
    fails exactly when one arm drew only runs with it and the other only
    runs without it."""

    def row(ran):
        return {"harness": "h", "skill": "s", "exit": 0, "gate": 0, "expected": ["x"], "ran": ran}

    same = [row(["x"])] * 3
    assert rates(same, 3) == (0.0, 0.0), rates(same, 3)
    mixed = [row(["x"]), row(["x"]), row([])]
    fail, _ = rates(mixed, 3)
    want = (2 / 3) ** 3 * (1 / 3) ** 3
    assert abs(fail - want) < 1e-12, (fail, want)
    result = {"a": {"s": {"fail": 0.5}}, "b": {"s": {"fail": 0.5}, "t": {"fail": 1.0}}}
    assert over_harnesses(result, ["a", "b"]) == {"s": 0.75}, "only skills both measured"
    assert command_rates(same, 3, 200, 1)[0] == 0.0, "identical runs never fail"
    fail, _ = command_rates(mixed, 3, 20000, 1)
    assert abs(fail - want) < 0.01, (fail, want)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--runs", type=int, default=3, help="runs an arm (default 3)")
    parser.add_argument("--model", choices=("runs", "commands"), default="runs")
    parser.add_argument("--trials", type=int, default=20000, help="--model commands only")
    parser.add_argument("--json", type=Path, help="also write the rates here")
    args = parser.parse_args(argv)
    self_check()
    result = simulate(latest_groups(args.files), args.runs, args.model, args.trials)
    report(result)
    if args.json:
        harnesses = list(result)
        payload = {
            "runs": args.runs,
            "model": args.model,
            "trials": args.trials if args.model == "commands" else None,
            "files": [str(f) for f in args.files],
            "rates": result,
        }
        if len(harnesses) > 1:
            payload["over_harnesses"] = over_harnesses(result, harnesses)
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
