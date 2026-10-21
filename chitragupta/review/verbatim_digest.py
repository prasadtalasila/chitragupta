"""Verbatim digest report: how much of a digest is not the sources' own
words, and what every such sentence is (#991).

    python -m chitragupta.review digest <draft>
        split the digest into citation-terminated runs, find each in
        the source it cites, and list every sentence that is not
        verified source text. Leads with the unsupported fraction.

    python -m chitragupta.review digest <draft> --baseline <stem>.digest.json
        the same, then compare with an earlier run: resolved,
        persisting and new items, the counts and fractions before and
        after, and whether the unsupported text fell.

The eleventh aid in `review.AIDS`, and the first over a genre of its
own: a digest is private study text written mostly in the cited papers'
own words, with no quotation marks and a citation closing each copied
run (docs/VERBATIM-DIGEST.md). It is a draft like any other -- named
by the user, its genre recorded in its dossier's `scope.md` -- so its
report lands under the ordinary rule, `<stem>.digest.md` beside the
other aids' reports for the same draft. `_digest_runs.py` reads the
runs, `_digest_match.py` verifies them, `_digest_render.py` prints and
serialises, `_digest_recheck.py` compares. This file is the CLI.

**Not a gate, and advisory like the other ten.** Every finding is
`[surfaced]`: a person decides whether to cite, replace or delete.
Exits 0 whatever it finds. The digest is never a drafting source for any
other genre; `review verbatim scan` already catches its wording if it
reaches one.

**Needs the enriched corpus.** A run is matched against reading-ordered
passages only -- the Docling sidecar `chitragupta enrich --stages
docling` writes. A `pdftotext` parse has no reading order, and a run
copied from one can be a collage of two columns, which is the hazard
`review quotation` refuses to quote from and the reason this aid does
not fall back to page text: it reports the run as not checkable and
names the stage to run.

**Files its report unconditionally**, like `agenda` and for the same
reason: the `.json` is the next pass's `--baseline`. `--json` only
decides what prints to stdout.

Stdlib only, interpreter tier 1. Reads the ledger read-only (#843).
"""

import argparse
import shlex
import sys
from pathlib import Path

from chitragupta import config, ledger, passages, review
from chitragupta.review import _digest_match, _digest_recheck, _digest_render, _digest_runs, _emit

AID = "digest"


def build_report(draft: Path) -> tuple[_digest_match.Checked, list[dict]]:
    """Every run of `draft` checked, and the worklist rows for what failed.

    One ledger connection and one passage lookup per citekey for the
    whole run: a digest cites few papers many times.
    """
    text = draft.read_text(encoding="utf-8")
    checked = _digest_match.Checked()
    cache: dict[str, tuple[list, str | None]] = {}
    with ledger.reading() as con:

        def lookup(citekey: str) -> tuple[list, str | None]:
            if citekey not in cache:
                cache[citekey] = passages.source_passages(con, citekey)
            return cache[citekey]

        for run in _digest_runs.runs(text):
            _digest_match.check_run(run, lookup, checked)
    return checked, _digest_render.items(checked, text)


def _command(draft: Path, args: argparse.Namespace) -> str:
    """The bare invocation, which is what the filed `.json` records even
    under `--baseline`: that file is the *next* run's baseline, so its
    envelope has to name a command that regenerates a report."""
    parts = ["python", "-m", "chitragupta.review", "digest", str(draft)]
    if args.formats != "md,tex,pdf":
        parts += ["--formats", args.formats]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser(
            description="How much of a verbatim digest is not the sources' own words.",
        )
    parser.add_argument("draft", help="The digest to check, under content/drafts/")
    _emit.add_formats(parser)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the payload (or, with --baseline, the comparison) as JSON "
        "instead of the summary. The .json sibling is filed either way.",
    )
    parser.add_argument(
        "--baseline",
        help="Compare this run against a previously filed <stem>.digest.json: "
        "resolved, persisting and new items, counts and fractions before and "
        "after, and whether unsupported text fell.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def _file(draft: Path, args: argparse.Namespace) -> tuple[dict, dict]:
    checked, rows = build_report(draft)
    command = _command(draft, args)
    body = _digest_render.render_markdown(draft, command, checked, rows)
    written = review.write(draft, AID, body, _emit.formats(args))
    payload = _digest_render.payload(draft, command, checked, rows)
    written["json"] = review.write_json(draft, AID, payload)
    return payload, written


def run(args: argparse.Namespace) -> int:
    """The baseline is loaded before anything is computed: a bad one is a
    usage error (exit 2) and should cost nothing. The draft is checked
    first because a draft the layer will not read is exit 1, the same
    order `agenda` keeps."""
    try:
        draft = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1
    baseline = None
    if args.baseline:
        try:
            baseline = _digest_recheck.load_baseline(args.baseline)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
    payload, written = _file(draft, args)
    if baseline is None:
        _emit.announce(payload, written, as_json=args.json)
        return 0
    comparison = _digest_recheck.compare(payload, baseline)
    if args.json:
        recheck = _digest_recheck.recheck_payload(draft, args.baseline, comparison)
        _emit.announce(recheck, written, as_json=True)
    else:
        print(_digest_recheck.format_recheck(args.baseline, comparison))
        review.print_written(written)
    return 0
