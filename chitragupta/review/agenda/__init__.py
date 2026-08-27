"""One ranked, deduplicated worklist merged across the other seven review
aids, `style_check.py`'s prose findings, and the dossier's drift report.

    python -m chitragupta.review agenda <draft>
        merge everything else in the layer already knows about this
        draft into one ordered list of items.

The eighth aid in `review.AIDS` (`chitragupta/review/__init__.py`) and in
`chitragupta/review/__main__.py`'s own `AIDS` -- see that file for the
`RuntimeError`-at-import-time check tying the two together.
Deterministic, stdlib-only, no LLM, takes no lock, exits 0 whatever it
finds, exactly like the other eight.

**Reads, never invokes -- in the bare mode, which is the one every
caller but `--baseline` uses.** The seven review aids' `.json` files
(`_sources.py`), each optional and read from wherever an earlier
`--json`/`--write` run left them -- `review agenda <draft>` never runs an
aid live, and stays the free, read-only command docs/CLI.md and
docs/AUTO-IMPROVEMENT.md describe. `style_check.check()` and
`dossier.drift()` have no on-disk artefact, so those two are called
in-process instead. A draft with no dossier still produces an agenda,
with no `missing-citekey`/`candidate` items and the absence named in the
header -- the same "optional input, missing" pattern every aid already
uses, not a refusal.

**`--baseline` is the one exception, and it is scoped to that flag.**
`review agenda <draft> --baseline <a previous agenda .json>` re-runs the
seven aids at `--formats md` first, then rebuilds and reports
`resolved`/`persisting`/`new` against the baseline -- `_recheck.py`, and
Decision 6 of `plans/f3-agenda-reviser.md` for why the R4 cycle became
one deterministic command rather than prose in seven skills. Refreshing
is what makes the comparison mean anything: reading pre-edit `.json`
reports a finding resolved that is not, and it does so silently. That
mode also owns the `--query` source `coverage` needs, which is
`f-auto-improvement-adoption.md`'s Q5 answer -- the draft's own
`retrieval.md` rows, skipping mode `revision`.
"""

import argparse
import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, dossier, review
from chitragupta.review.agenda import _dedup, _items, _order, _recheck, _render, _sources

# plans/f-auto-improvement-adoption.md's Decision 2: a backstop against a
# miscounting bug in the future agenda-reviser re-run loop, not a cost
# control -- naming it wrong is how it later gets mistaken for a budget.
# Defined here because this is where the thing it bounds (an invocation's
# objective-class item count, `Agenda.objective_class_count`) is computed;
# nothing in this module loops on it yet.
PASS_BOUND = 3


@dataclass
class Agenda:
    draft: Path
    sources: _sources.Sources
    items: list = field(default_factory=list)

    @property
    def objective_class_count(self) -> int:
        """The count a future re-run loop watches: unattended items only.

        Three classes contribute -- `missing-citekey`, verbatim-run's
        `"short"` bucket, and `prose`, which joined them in issue 421.
        The list is spelled out rather than left as "whatever is
        flagged" because this is the number the loop terminates on: a
        description of it that has gone stale is the most expensive
        comment in this module.
        """
        return sum(1 for item in self.items if item.unattended)


def build_agenda(draft: Path) -> Agenda:
    """Everything this aid does, as data: collect the eight sources,
    extract one item per finding, merge, then order."""
    sources = _sources.collect(draft)
    sections = dossier.sections(draft.read_text(encoding="utf-8"))
    items = _items.all_items(sources, sections)
    items = _order.sort(_dedup.merge(items))
    return Agenda(draft=draft, sources=sources, items=items)


def _command(draft_path: Path, as_json: bool) -> str:
    parts = ["python", "-m", "chitragupta.review", "agenda", str(draft_path)]
    if as_json:
        parts += ["--json"]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags.

    `parser` is passed by `chitragupta/review/__main__.py`, which has
    already created the `agenda` subparser and needs the flags hung off
    *that* -- declared once, here, the same convention every other aid
    follows.
    """
    if parser is None:
        parser = argparse.ArgumentParser(
            description="One ranked, deduplicated worklist merged across every other aid.",
        )
    parser.add_argument("draft", help="Markdown draft to check")
    parser.add_argument(
        "--formats",
        default="md,tex,pdf",
        help="Additional formats to render beside the Markdown report "
        "(default: md,tex,pdf). The .md is always written -- it is the "
        "report; tex/pdf are renders of it, and need pandoc/pdflatex "
        "on PATH.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the worklist as JSON instead of just the "
        "written-files summary. The .json sibling is filed beside the "
        "Markdown report either way.",
    )
    parser.add_argument(
        "--baseline",
        help="Re-run the seven aids and compare the result against a "
        "previously written agenda .json, reporting resolved/persisting/"
        "new items and the objective count before and after. This is the "
        "only mode that runs another aid -- the bare command never does "
        "-- and it costs seconds rather than milliseconds.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def _file_report(draft_path: Path, args) -> tuple[dict, dict]:
    """Build the agenda for `draft_path` and file its `.md` (plus any
    renders) and `.json`, returning `(payload, written)`.

    Runs identically in both modes -- `--baseline` refreshes the inputs
    in front of this and compares behind it, but the report filed for the
    draft's *current* state is the same artefact either way, and is what
    the next run reads as a baseline.
    """
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    agenda = build_agenda(draft_path)
    command = _command(draft_path, args.json)
    body = _render.render_markdown(agenda, command)
    written = review.write(draft_path, "agenda", body, formats)
    payload = _render.agenda_payload(agenda, command)
    written["json"] = review.write_json(draft_path, "agenda", payload)
    return payload, written


def _print_recheck(draft_path: Path, args, payload: dict, baseline: dict, written: dict) -> None:
    """`--baseline`'s stdout, in place of the plain worklist.

    The comparison is what the caller asked for, so it is what gets
    printed; the agenda itself is still on disk either way. The
    stdout/stderr split is the bare path's, unchanged -- under `--json`
    the payload is the only thing on stdout, so `agenda --baseline ...
    --json > report.json` stays a valid JSON file.
    """
    resolved, persisting, appeared, before, after = _recheck.compare(
        payload["items"], baseline["items"]
    )
    groups, counts = (resolved, persisting, appeared), (before, after)
    if args.json:
        command = _recheck.recheck_command(draft_path, args.baseline)
        print(
            json.dumps(
                _recheck.recheck_payload(draft_path, args.baseline, groups, counts, command),
                indent=2,
            )
        )
        review.print_written(written, stream=sys.stderr)
    else:
        print(_recheck.format_recheck(args.baseline, groups, counts))
        review.print_written(written)


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments.

    The `.md`+`.json` are filed unconditionally -- there is no `--write`
    flag, matching AUTO-IMPROVEMENT.md's unconditional "Writes:" line and
    R9's need for a baseline artefact before a reviser pass runs.
    `--json` only decides what prints to stdout; the written-files
    summary moves to stderr under it, the same discipline `provenance
    --json` and `verbatim scan --json` already follow.

    `--baseline` adds a refresh in front and a comparison behind, and
    changes nothing between them. Two orderings in it are load-bearing:

    - **The baseline is loaded before anything is refreshed.** A bad one
      is a usage error, and paying ~21 s of aid runs before saying so
      would be gratuitous. It is also what makes the natural invocation
      safe -- the baseline a caller reaches for is usually
      `<stem>.agenda.json`, which is the very file this run overwrites.
    - **The filed report still records `_command`'s bare invocation**,
      not the `--baseline` one. That `.json` is the *next* run's
      baseline, so its envelope has to name a command that regenerates
      an agenda rather than a comparison against itself; the
      `--baseline` spelling belongs to the payload printed to stdout,
      which is where `_recheck.recheck_command` puts it.

    A `ValueError` from the load prints to stderr and returns 2, the
    usage-error code `verbatim_check.run` uses for its own refusals.
    """
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
        _recheck.refresh_aids(draft_path)

    payload, written = _file_report(draft_path, args)

    if baseline is not None:
        _print_recheck(draft_path, args, payload, baseline, written)
    elif args.json:
        print(json.dumps(payload, indent=2))
        review.print_written(written, stream=sys.stderr)
    else:
        review.print_written(written)
    return 0
