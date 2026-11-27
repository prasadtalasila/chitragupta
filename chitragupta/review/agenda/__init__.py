"""One ranked, deduplicated worklist merged across the other eight review
aids, `style_check.py`'s prose findings, the dossier's drift report, and
its recorded-but-uncited citekeys.

    python -m chitragupta.review agenda <draft>

Deterministic, stdlib-only, no LLM, no lock, exits 0 whatever it finds.
The bare mode reads, never invokes: the aids' optional `.json` files
(`_sources.py`) from earlier runs, plus `style_check.check()`,
`dossier.drift()` and `recorded_but_uncited()` called in-process, since
they leave no artefact. No dossier still yields an agenda, with the
absence named. It writes its own report, and `--accept` its record
(`_accept.py`); neither touches the draft.

`--baseline <previous .json>` is the one exception: it re-runs the aids
at `--formats md`, then reports `resolved`/`persisting`/`new`
(`_refresh.py`, `_recheck.py`; Decision 6 of `plans/f3-agenda-reviser.md`).
Refreshing is what makes the comparison honest: pre-edit `.json` reports
a finding resolved that is not, silently. Coverage's `--query` comes from
the draft's own `retrieval.md` rows, skipping mode `revision`.
"""

import argparse
import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, dossier, review
from chitragupta.review import _emit
from chitragupta.review.agenda import (
    _accept,
    _dedup,
    _items,
    _order,
    _recheck,
    _refresh,
    _render,
    _sources,
    _stale,
)
from chitragupta.help_format import ClickParser

# A backstop against a miscounting bug in the agenda-reviser loop, not a
# cost control (plans/f-auto-improvement-adoption.md, Decision 2); naming
# it wrong is how it gets mistaken for a budget.
PASS_BOUND = 3


@dataclass
class Agenda:
    draft: Path
    sources: _sources.Sources
    items: list = field(default_factory=list)
    # Stale items, reported and never repaired (R12, `_stale.py`); off
    # `items`, since a reviser could act on one there.
    stale: list = field(default_factory=list)
    # Accepted items (`_accept.py`), kept so the report lists them beside
    # what they silence and `--accept` of an accepted id says so.
    suppressed: list = field(default_factory=list)

    @property
    def objective_class_count(self) -> int:
        """The count a future re-run loop watches: unattended items only.

        Three classes: `missing-citekey`, verbatim-run's `"short"` bucket,
        and `prose` (issue 421) less `repair="review"` findings (issue 836).
        Spelled out because the loop terminates on it, so a stale
        description is the costliest comment here. An aid `--baseline`
        failed to refresh contributes nothing (#837).
        """
        skipped = _sources.unverified_classes(self.sources.not_refreshed())
        return sum(1 for item in self.items if item.unattended and item.cls not in skipped)


def build_agenda(
    draft: Path,
    refreshed: "dict[str, bool | None] | None" = None,
    errors: "dict[str, str] | None" = None,
) -> Agenda:
    """Collect the sources, extract one item per finding, merge, order,
    refuse what the draft no longer says, then set aside accepted items.

    Both filters run last, once over the ordered list: `_dedup.merge` sees
    every item, and nothing is re-ordered.
    """
    # Refusal before acceptance: otherwise a refused finding's record would
    # read `suppressed: true`, claiming a judgement honoured for an item
    # never raised (docs/AUTO-IMPROVEMENT.md section 5). Disjoint today
    # (`_stale` refuses only span-bearing classes, none `ACCEPTABLE`);
    # `TestStaleAndAcceptedDoNotOverlap` pins that.
    sources = _sources.collect(draft, refreshed, errors)
    text = draft.read_text(encoding="utf-8")
    sections = dossier.sections(text)
    items = _items.all_items(sources, sections)
    items, stale = _stale.partition(text, _order.sort(_dedup.merge(items)))
    items, suppressed = _accept.partition(items, sources.accepted)
    return Agenda(draft, sources, items=items, stale=stale, suppressed=suppressed)


def _command(draft_path: Path, as_json: bool) -> str:
    parts = ["python", "-m", "chitragupta.review", "agenda", str(draft_path)]
    if as_json:
        parts += ["--json"]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, hung off the subparser `__main__` created."""
    if parser is None:
        parser = ClickParser(
            description="One ranked, deduplicated worklist merged across every other aid.",
        )
    parser.add_argument("draft", help="Markdown draft to check")
    _emit.add_formats(parser)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the worklist as JSON instead of just the "
        "written-files summary. The .json sibling is filed beside the "
        "Markdown report either way.",
    )
    parser.add_argument(
        "--accept",
        action="append",
        metavar="ID",
        help="Record this agenda item id as considered and accepted, so "
        "it stays off the worklist while the finding's identity is "
        "unchanged. Repeatable. Only claim-support, uncited-claim and "
        "unsupported-claim may be accepted; an edit to the accepted span "
        "brings the item back, the id being a hash of that span.",
    )
    parser.add_argument(
        "--baseline",
        help="Re-run the eight aids and compare the result against a "
        "previously written agenda .json, reporting resolved/persisting/"
        "new items and the objective count before and after. This is the "
        "only mode that runs another aid -- the bare command never does "
        "-- and it costs seconds rather than milliseconds.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def _file_report(draft_path: Path, args, refreshed=None, errors=None) -> tuple[dict, dict]:
    """Build the agenda for `draft_path` and file its `.md` (plus any
    renders) and `.json`, returning `(payload, written)`. Identical in both
    modes; it is what the next run reads as a baseline.
    """
    agenda = build_agenda(draft_path, refreshed, errors)
    command = _command(draft_path, args.json)
    body = _render.render_markdown(agenda, command)
    written = review.write(draft_path, "agenda", body, _emit.formats(args))
    payload = _render.agenda_payload(agenda, command)
    written["json"] = review.write_json(draft_path, "agenda", payload)
    return payload, written


def _print_recheck(draft_path: Path, args, payload: dict, baseline: dict, written: dict) -> None:
    """`--baseline`'s stdout, in place of the plain worklist; under
    `--json` the payload alone is on stdout.
    """
    # Suppressed ids come off the report just filed: without them an
    # accepted item would read as resolved. A failed refresh unverifies that
    # aid's items on either side (#837); only this run's failures print.
    suppressed_ids = {row["id"] for row in payload["accepted"] if row["suppressed"]}
    failed, errors = _recheck.not_refreshed(payload), _recheck.refresh_errors(payload)
    unverified = {*failed, *_recheck.not_refreshed(baseline)}
    resolved, persisting, appeared, accepted, before, after = _recheck.compare(
        payload["items"], baseline["items"], suppressed_ids, unverified
    )
    groups, counts = (resolved, persisting, appeared, accepted), (before, after)
    if args.json:
        recheck = _recheck.recheck_payload(
            draft_path, args.baseline, groups, counts, failed, errors
        )
        print(json.dumps(recheck, indent=2))
        review.print_written(written, stream=sys.stderr)
    else:
        print(_recheck.format_recheck(args.baseline, groups, counts, failed, errors))
        review.print_written(written)


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments.

    The `.md`+`.json` are filed unconditionally (no `--write`): R9 needs a
    baseline artefact. `--json` only decides stdout. Under `--baseline`,
    three orderings are load-bearing:

    - The baseline loads first: a bad one is a usage error not worth ~21 s
      of aid runs, and it is usually `<stem>.agenda.json`, the very file
      this run overwrites.
    - The ledger is checked next, before any refresh or filing (#893).
    - The filed report records the bare command, since it is the next
      run's baseline; the `--baseline` spelling goes in the stdout payload.

    A bad baseline or a refused `--accept` prints to stderr and returns 2.
    """
    # `--accept` applies before any refresh: the ids were read off the
    # pre-refresh report, and filing after makes the report agree with it.
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    baseline = None
    if args.baseline:
        try:
            baseline = _recheck.load_baseline(args.baseline)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        # A bad baseline keeps exit 2 even with no ledger. The bare mode
        # runs no aid, so a missing corpus is only a header note.
        refusal = _refresh.ledger_refusal()
        if refusal is not None:
            return refusal

    if args.accept:
        refusal = _accept.apply(draft_path, build_agenda(draft_path), args)
        if refusal is not None:
            return refusal

    refreshed, errors = _refresh.refresh_aids(draft_path) if baseline is not None else (None, None)
    payload, written = _file_report(draft_path, args, refreshed, errors)

    if baseline is not None:
        _print_recheck(draft_path, args, payload, baseline, written)
    else:
        _emit.announce(payload, written, as_json=args.json)
    return 0
