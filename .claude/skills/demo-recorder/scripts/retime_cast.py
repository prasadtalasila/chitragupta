#!/usr/bin/env python3
"""Retime an asciinema v2 `.cast`: speed one span up, stretch the tail.

The span runs from the first output event containing START to the first
one after it containing END -- tour.sh's `# N. ...` headings, so
`--start "# 1." --end "# 2."` is the `pip install` scroll. Inside it,
time runs `--speed-up` times faster; after it, `--tail` times slower
(below 1, faster); before it, nothing moves. Event payloads are copied
unchanged, and so is the header, except that a recorded
`idle_time_limit` is scaled by the tail factor: players and agg cap
every gap at it, which would undo a stretch.

Stdlib-only, so it runs with bare `python3`.

Usage:
    retime_cast.py IN.cast OUT.cast --start MARKER --end MARKER
        [--speed-up FACTOR] [--tail FACTOR]
"""

import argparse
import json


def _positive(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = 0.0
    if value <= 0:
        raise argparse.ArgumentTypeError(f"{text!r} is not a positive number")
    return value


def _first(events, marker: str, after: float | None = None) -> float | None:
    """The time of the first output event holding `marker`, later than
    `after` when one is given."""
    for ts, kind, data in events:
        if kind == "o" and marker in data and (after is None or ts > after):
            return ts
    return None


def retime(events, start: str, end: str, speed_up: float = 1.0, tail: float = 1.0) -> list:
    """`events` (`[time, type, data]` triples) with new times."""
    t0 = _first(events, start)
    if t0 is None:
        raise SystemExit(f"start marker {start!r} not found")
    t1 = _first(events, end, after=t0)
    if t1 is None:
        raise SystemExit(f"end marker {end!r} not found after {start!r}")
    new_t1 = t0 + (t1 - t0) / speed_up

    def moved(ts: float) -> float:
        if ts <= t0:
            return ts
        if ts <= t1:
            return t0 + (ts - t0) / speed_up
        return new_t1 + (ts - t1) * tail

    return [[round(moved(ts), 6), kind, data] for ts, kind, data in events]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--speed-up", type=_positive, default=1.0)
    parser.add_argument("--tail", type=_positive, default=1.0)
    args = parser.parse_args(argv)

    with open(args.source, encoding="utf-8") as f:
        header_line, *lines = f.read().splitlines()
    header = json.loads(header_line)
    if "idle_time_limit" in header:
        header["idle_time_limit"] *= args.tail
    events = [json.loads(line) for line in lines if line.strip()]
    out = retime(events, args.start, args.end, args.speed_up, args.tail)
    with open(args.target, "w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        f.writelines(json.dumps(ev) + "\n" for ev in out)
    print(f"{args.target}: {events[-1][0]:.2f}s -> {out[-1][0]:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
