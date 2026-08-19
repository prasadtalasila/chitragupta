"""`dossier status`: what a dossier holds, and whether the corpus has
moved since -- the report a person runs to find out what they have.

Split out of chitragupta/dossier.py (#219). Depends on `_drift` (for the
`--json` single-draft path) but never the reverse -- `status()` itself
never calls `drift()` (confirmed by reading it: they read overlapping
dossier state independently, joined only at the CLI layer).
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config
from chitragupta.dossier._citekeys import cited_citekeys
from chitragupta.dossier import (
    EVIDENCE_MD, FILES, REJECTED_MD, _resolve_dossier, digest, dossier_dir,
    draft_relpath, find_draft, known_citekeys, recorded_corpus,
)
from chitragupta.dossier._drift import drift, drift_all
from chitragupta.dossier._drift_report import _cmd_status_all
from chitragupta.dossier._retrieval import RevisionCost, retrieval_cost_by_revision
from chitragupta.dossier._sections import Section, sections

@dataclass
class FileStatus:
    name: str
    present: bool
    entries: int
    shape: str = "prose"


@dataclass
class Status:
    dossier: Path
    draft: Path | None
    files: list[FileStatus] = field(default_factory=list)
    outline: list[Section] = field(default_factory=list)
    recorded: tuple[int, str] | None = None
    current: tuple[int, str] | None = None
    unconsidered: set[str] = field(default_factory=set)
    retrieval_calls: int = 0
    retrieval_chars: int = 0
    revisions: list[RevisionCost] = field(default_factory=list)

    @property
    def drifted(self) -> bool:
        return bool(self.recorded and self.current and self.recorded[1] != self.current[1])


_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _count(text: str, shape: str) -> int:
    """How many entries a dossier file holds. Advisory, not exact.

    Nothing depends on the number being right -- `status` prints it so a
    reader can see at a glance whether a file was filled in or left as
    the skeleton, and a hand-edited dossier that counts a little wrong
    still revises fine.
    """
    body = _COMMENT.sub("", text)
    if shape == "blocks":
        return sum(1 for line in body.splitlines() if line.startswith("## "))
    if shape == "rows":
        return sum(
            1
            for line in body.splitlines()
            if line.lstrip().startswith("|") and not set(line) <= set("|-: \t")
        ) - 1  # the header row, which every template ships with
    return sum(
        1
        for line in body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def status(draft_or_dossier: Path) -> Status:
    """What this dossier holds, and whether the corpus has moved since.

    Never raises on a missing ledger or a missing dossier: this is the
    command someone runs to find out what they have, including on a
    machine where the corpus was never built and only a restored backup
    exists.
    """
    path = Path(draft_or_dossier)
    if path.is_dir():
        dossier, draft = path, find_draft(path)
    else:
        dossier, draft = dossier_dir(path), (path if path.is_file() else None)

    report = Status(dossier=dossier, draft=draft)
    for name, shape in FILES.items():
        file_path = dossier / name
        if file_path.is_file():
            entries = _count(file_path.read_text(encoding="utf-8"), shape)
            report.files.append(FileStatus(name, True, max(entries, 0), shape))
        else:
            report.files.append(FileStatus(name, False, 0, shape))

    if draft is not None:
        report.outline = sections(draft.read_text(encoding="utf-8"))
    # One parse of retrieval.md, not two: retrieval_cost_by_revision's
    # segments already exclude mark_revision's boundary rows the same
    # way retrieval_cost does, so the lifetime totals are just their sum
    # -- calling retrieval_cost here too would parse the same file twice
    # for numbers `_retrieval_rows` only needed to compute once.
    report.revisions = retrieval_cost_by_revision(dossier)
    report.retrieval_calls = sum(segment.calls for segment in report.revisions)
    report.retrieval_chars = sum(segment.chars for segment in report.revisions)

    report.recorded = recorded_corpus(dossier)
    corpus_keys = known_citekeys()
    if corpus_keys is not None:
        report.current = (len(corpus_keys), digest(corpus_keys))
        report.unconsidered = corpus_keys - cited_citekeys(dossier)
    return report


def _cmd_status(args: argparse.Namespace) -> int:
    if args.all and args.draft:
        print("[error] Give a draft path or --all, not both.", file=sys.stderr)
        return 2
    if not args.all and not args.draft:
        print("[error] Give a draft path, or --all for every dossier.", file=sys.stderr)
        return 2
    if args.all:
        return _cmd_status_all(drift_all(), args.json)
    if args.json:
        return _cmd_status_all([drift(_resolve_dossier(Path(args.draft)))], True)

    report = status(Path(args.draft))
    if not report.dossier.is_dir():
        print(f"No dossier at {draft_relpath(report.dossier)}.")
        print("Create one with `python -m chitragupta.draft dossier init "
              f"{args.draft} --genre <genre>`.")
        return 1

    print(f"Dossier: {draft_relpath(report.dossier)}")
    _print_status_files(report)
    _print_status_retrieval(report)
    print()
    _print_status_drift(report)
    return 0


def _print_status_files(report: Status) -> None:
    """The draft line and the per-file table."""
    if report.draft is not None:
        print(f"  draft         {draft_relpath(report.draft)} ({len(report.outline)} sections)")
    else:
        print("  draft         MISSING -- the dossier outlived its draft")
    for entry in report.files:
        # A count means something for the two files that are lists
        # (evidence blocks, rejected/section rows) and nothing for the
        # three that are prose -- "scope.md: 40 entries" would be a
        # number dressed up as information.
        if not entry.present:
            print(f"  {entry.name:<14}absent")
        elif not entry.entries:
            print(f"  {entry.name:<14}empty (skeleton only)")
        elif entry.shape == "prose":
            print(f"  {entry.name:<14}filled in")
        else:
            print(f"  {entry.name:<14}{entry.entries} entr{'y' if entry.entries == 1 else 'ies'}")


def _print_status_retrieval(report: Status) -> None:
    """The retrieval cost block, when this dossier logged any calls."""
    if not report.retrieval_calls:
        return
    kept = next((f.entries for f in report.files if f.name == EVIDENCE_MD), 0)
    rejected = next((f.entries for f in report.files if f.name == REJECTED_MD), 0)
    print(f"\nRetrieval: {report.retrieval_calls} call(s) returned "
          f"{report.retrieval_chars:,} characters")
    if kept or rejected:
        print(f"  {kept} kept, {rejected} rejected")
    else:
        # Searched, and recorded nothing it found. Reported rather
        # than blocked, like every other check outside the citation
        # gate: it costs a comparison of two numbers already on this
        # report, and nothing else in the pipeline can see it -- the
        # draft looks finished and the judgment behind it is gone.
        #
        # "no entries" rather than "empty": both counts are 0 for an
        # absent file too, and the per-file lines above already
        # distinguish `absent` from `empty (skeleton only)`. Calling
        # a missing file empty would contradict them.
        print("  but evidence.md and rejected.md hold no entries -- this run")
        print("  searched and recorded nothing it found, so a revision will")
        print("  have to re-retrieve and re-judge the same candidates.")

    # Only worth a breakdown once there's more than one segment --
    # with just one, it would repeat the total line above under a
    # different label. A dossier revised before `mark-revision`
    # existed has exactly one ("initial draft") for the same reason a
    # dossier with no revisions yet does: nothing split it.
    if len(report.revisions) > 1:
        print("  by revision:")
        for segment in report.revisions:
            print(f"    {segment.label:<24}{segment.calls} call(s), "
                  f"{segment.chars:,} characters")


def _print_status_drift(report: Status) -> None:
    """The corpus drift block: unavailable, unchanged, or changed with
    the unconsidered citekeys named."""
    if report.current is None:
        print(f"Corpus drift: unavailable -- no readable ledger at {config.LEDGER_PATH}.")
        return
    if report.recorded is None:
        print("Corpus drift: unavailable -- scope.md records no corpus fingerprint.")
        print(f"  now: {report.current[0]} citekeys, digest {report.current[1]}")
        return

    print("Corpus drift since this draft:")
    print(f"  recorded  {report.recorded[0]} citekeys, digest {report.recorded[1]}")
    print(f"  now       {report.current[0]} citekeys, digest {report.current[1]}")
    if not report.drifted:
        print("  unchanged -- the dossier's evidence is current.")
        return
    print(f"  CHANGED ({report.current[0] - report.recorded[0]:+d} citekeys)")
    if report.unconsidered:
        shown = sorted(report.unconsidered)[:10]
        print(f"\n  {len(report.unconsidered)} citekey(s) in the ledger appear nowhere in "
              "this dossier:")
        for citekey in shown:
            print(f"    {citekey}")
        if len(report.unconsidered) > len(shown):
            print(f"    ... and {len(report.unconsidered) - len(shown)} more")
        print("\n  Re-search only if the change you are making touches a sub-theme")
        print("  these could bear on. Drift is not itself a reason to redraft.")
