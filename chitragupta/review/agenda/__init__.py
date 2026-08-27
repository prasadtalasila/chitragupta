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

**Reads, never invokes.** The seven review aids' `.json` files
(`_sources.py`), each optional and read from wherever an earlier
`--json`/`--write` run left them -- this module never runs an aid live.
`style_check.check()` and `dossier.drift()` have no on-disk artefact, so
those two are called in-process instead. A draft with no dossier still
produces an agenda, with no `missing-citekey`/`candidate` items and the
absence named in the header -- the same "optional input, missing" pattern
every aid already uses, not a refusal.

**R4's re-run loop, and the `--query` source it needs for `coverage`,
belong to a future `agenda-reviser` (docs/AUTO-IMPROVEMENT.md step 5),
not to this module.** That plan's Q5 answer is recorded here so step 5
does not have to re-derive it: the re-run query source is the draft's own
`retrieval.md` rows, skipping mode `revision`. Nothing here implements
that loop.
"""

import argparse
import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, dossier, review
from chitragupta.review.agenda import _dedup, _items, _order, _render, _sources

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
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments.

    The `.md`+`.json` are filed unconditionally -- there is no `--write`
    flag, matching AUTO-IMPROVEMENT.md's unconditional "Writes:" line and
    R9's need for a baseline artefact before a future reviser pass runs.
    `--json` only decides what prints to stdout; the written-files
    summary moves to stderr under it, the same discipline `provenance
    --json` and `verbatim scan --json` already follow.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    agenda = build_agenda(draft_path)
    command = _command(draft_path, args.json)
    body = _render.render_markdown(agenda, command)
    written = review.write(draft_path, "agenda", body, formats)
    payload = _render.agenda_payload(agenda, command)
    written["json"] = review.write_json(draft_path, "agenda", payload)

    if args.json:
        print(json.dumps(payload, indent=2))
        review.print_written(written, stream=sys.stderr)
    else:
        review.print_written(written)
    return 0
