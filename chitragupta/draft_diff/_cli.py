"""`python -m chitragupta.draft diff`: the change report, then the redline.

The report is written to `content/review/<topic>/` before any PDF work
starts, so a missing latexdiff or a redline that will not compile still
leaves `<stem>.diff.md` and `<stem>.diff.json` behind. The review
directory is computed with the rule `review/_paths.report_dir` uses,
restated rather than imported: the drafting layer does not reach into
the review layer.

The output is a review copy (plans/draft-diff.md, decision 14): it is
never gated as a draft, never rendered as a deliverable, and never read
back as a source. Each side of the redline is still gated by `render()`,
unchanged.
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from chitragupta import citation_gate, config, ledger, render_output
from chitragupta.dossier import REVISIONS_MD, DossierError, dossier_dir
from chitragupta.dossier._versions import VersionError, resolve
from chitragupta.draft_diff import _redline
from chitragupta.draft_diff._compare import ChangeReport, compare
from chitragupta.draft_diff._report import to_json, to_markdown
from chitragupta.draft_diff._revlog import attach, entries, hand_edited
from chitragupta.draft_diff._sides import key_status, prepare
from chitragupta.draft_diff._views import VersionView, from_draft, from_file, from_snapshot
from chitragupta.render_output._gate import UngatedDraft
from chitragupta.render_output._math import MathMappingError

_STILL_CITABLE = "still citable"


class _Refused(ValueError):
    """A diff this command will not make; str() is the whole message."""


# Each said as one `[error]` line, the reaction a reviser already has to
# every other drafting-layer refusal. A pandoc failure and a refused math
# marker are render failures like `UngatedDraft`, raised by the same call.
_FAILURES = (
    _Refused,
    VersionError,
    DossierError,
    config.OutsideContentDir,
    UngatedDraft,
    MathMappingError,
    render_output.MissingBinary,
    _redline.RedlineFailed,
    subprocess.CalledProcessError,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft diff",
        description=(
            "What changed in a draft since a snapshot: a change report, "
            "and with --format pdf a redline. A review copy, never a deliverable."
        ),
    )
    parser.add_argument("draft", help="The draft, under content/drafts/")
    parser.add_argument(
        "--against",
        metavar="REF",
        help="A snapshot number, a snapshot label, or a file (default: the latest snapshot)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("md", "pdf"),
        default="md",
        help="md writes the report; pdf adds a redline PDF (default: md)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the report as JSON instead of Markdown"
    )
    return parser


def _review_dir(draft: Path) -> Path:
    """`content/review/<topic>/` for `draft`, which must be under `content/drafts/`."""
    if not draft.is_file():
        raise _Refused(f"No such draft: {draft}")
    mirrored = config.mirrored_dir(draft, config.DRAFTS_DIR, config.REVIEW_DIR)
    if mirrored is None:
        raise _Refused(
            f"{draft} is not under {config.DRAFTS_DIR}; a diff compares a draft "
            "with its own snapshots, which only a draft there has."
        )
    # The topic directory may be a symlink out of the tree.
    return config.require_inside_content(mirrored, "review directory")


def _baseline(draft: Path, ref: str | None) -> VersionView:
    """The version `ref` names; an existing file wins over a snapshot ref."""
    if ref is not None and Path(ref).is_file():
        return from_file(Path(ref))
    return from_snapshot(resolve(draft, ref))


def _key_status(draft: Path, old: VersionView, new: VersionView) -> Callable[[str], str]:
    """Each key's standing now, read from the ledger only if either side
    cites one -- the gate's own test, so a citation-free draft diffs
    before the first sync, as it renders."""
    if not any(citation_gate.extract_citekeys_for(draft, v.text) for v in (old, new)):
        # Never consulted: neither side has a key to ask about.
        return lambda key: _STILL_CITABLE
    with ledger.reading() as con:
        return key_status(con)


def _report(
    draft: Path, old: VersionView, new: VersionView
) -> "tuple[ChangeReport, Callable[[str], str]]":
    """The change report, with its log entries and hand-edit flag, and
    the key-status function it was built with."""
    status = _key_status(draft, old, new)
    report = compare(old, new, status)
    revisions = dossier_dir(draft) / REVISIONS_MD
    log = entries(revisions.read_text(encoding="utf-8")) if revisions.is_file() else []
    attach(report, log, old.date)
    report.hand_edits = hand_edited(draft)
    return report, status


def _write_report(report: ChangeReport, review_dir: Path, stem: str) -> None:
    # The stem is an existing draft's, so it names no other directory.
    name = f"{stem}.diff"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / f"{name}.md").write_text(to_markdown(report), encoding="utf-8")
    body = json.dumps(to_json(report), indent=2, ensure_ascii=False) + "\n"
    (review_dir / f"{name}.json").write_text(body, encoding="utf-8")
    # A redline from an earlier run shows an older state than this
    # report; it goes now, and only a redline built below replaces it.
    for suffix in (".pdf", ".tex"):
        (review_dir / f"{name}{suffix}").unlink(missing_ok=True)


def _redline_pdf(
    report: ChangeReport, status: Callable[[str], str], review_dir: Path, stem: str
) -> Path:
    name = f"{stem}.diff"
    work = review_dir / name
    # Exactly what the gate accepts, so the old side keeps every citation
    # the gate would pass and loses every one it would refuse.
    old_src, new_src = prepare(
        report.old, report.new, work, lambda key: status(key) == _STILL_CITABLE, stem
    )
    old_tex, new_tex = (
        render_output.render(
            str(src), output_format="tex", output_dir=work / side, defer_citations=True
        )
        for src, side in ((old_src, "old-tex"), (new_src, "new-tex"))
    )
    return _redline.redline(old_tex, new_tex, report, review_dir, stem)


def _diff(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    review_dir = _review_dir(draft)
    old, new = _baseline(draft, args.against), from_draft(draft)
    if old.suffix != new.suffix:
        raise _Refused(
            f"the baseline is {old.suffix}, the draft is {new.suffix}; they cannot be compared"
        )
    report, status = _report(draft, old, new)
    _write_report(report, review_dir, draft.stem)
    if args.json:
        print(json.dumps(to_json(report), indent=2, ensure_ascii=False))
    else:
        print(to_markdown(report), end="")
    if report.has_changes and args.output_format == "pdf":
        pdf = _redline_pdf(report, status, review_dir, draft.stem)
        # On stderr under --json, so what stdout carries still parses.
        print(pdf, file=sys.stderr if args.json else sys.stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Exit 0 when the report is written (including "No changes."), 1 on
    any refusal or failed redline, each as one `[error]` line; argparse's
    2 for a malformed invocation."""
    args = _build_parser().parse_args(argv)
    try:
        return _diff(args)
    except _FAILURES as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
