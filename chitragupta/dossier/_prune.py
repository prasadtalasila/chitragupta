"""Remove an `evidence.md` block for a citekey the draft no longer
cites (#701): a re-runnable, verifiable command instead of a free-form edit.

**Dry run by default.** `recorded - cited` cannot tell a cut citation
from a never-cited candidate that should stay, so `--apply` is opt-in
after a person reads the report, with no force flag.

**`evidence.md` only.** `sections.md` self-heals via its own derived
writer. `rejected.md` can never be touched: `recorded_but_uncited`
does not read it, an invariant by construction.
"""

import argparse
from pathlib import Path

from chitragupta.dossier import EVIDENCE_MD, dossier_dir, draft_relpath
from chitragupta.dossier._citekeys import (
    citekeys_by_section,
    duplicate_evidence_keys,
    evidence_block_spans,
)
from chitragupta.dossier._draft_fingerprint import recorded_but_uncited


def _verdict(
    key: str,
    orphaned: "dict[str, list[str]]",
    recorded: "set[str]",
    duplicates: "dict[str, int]",
) -> "tuple[bool, str]":
    """Whether `key` may be pruned, and why not when it may not.

    The caller branches on the bool, never on message text, so rewording
    cannot silently break deletion. Each refusal says why. `recorded`
    separates "still cited" from "not recorded": inferring it from a
    missing `evidence.md` span would misreport a `sections.md`-only key.
    """
    if key not in orphaned:
        if key in recorded:
            return False, "still cited -- not an orphan"
        return False, "not recorded in this dossier"
    if "evidence" not in orphaned[key]:
        return False, "recorded only in sections.md -- run `dossier sections --citekeys --write`"
    if key in duplicates:
        return False, (
            f"{duplicates[key]} blocks for this key -- resolve the duplicate by hand first"
        )
    return True, "prunable"


def _within(index: int, spans: "list[tuple[int, int]]") -> bool:
    return any(start <= index < end for start, end in spans)


def prune_evidence(draft: Path, citekeys: "set[str] | None", apply: bool) -> dict[str, str]:
    """Prune the named citekeys' `evidence.md` blocks, or every orphan
    when `citekeys` is None. Returns citekey -> what happened.

    Deletes by **line span**, never by matching reconstructed text (see
    `evidence_block_spans`).
    """
    target = dossier_dir(draft)
    orphaned = recorded_but_uncited(draft)
    spans = evidence_block_spans(target)
    duplicates = duplicate_evidence_keys(target)
    recorded = set(spans) | {key for keys in citekeys_by_section(target).values() for key in keys}
    wanted = citekeys if citekeys is not None else set(orphaned)

    report: dict[str, str] = {}
    doomed: list[tuple[int, int]] = []
    for key in sorted(wanted):
        prunable, message = _verdict(key, orphaned, recorded, duplicates)
        report[key] = ("removed" if apply else "would remove") if prunable else message
        if prunable:
            doomed.append(spans[key])

    if apply and doomed:
        path = target / EVIDENCE_MD
        # `newline=""` on both halves preserves line endings: universal
        # newlines silently converted a CRLF dossier to LF. Via `open()`
        # because `Path.read_text(newline=)` is 3.13+ and we support 3.12.
        # Line counts agree in both modes, so the spans still index.
        with path.open(encoding="utf-8", newline="") as handle:
            lines = handle.read().splitlines(keepends=True)
        kept = [line for index, line in enumerate(lines) if not _within(index, doomed)]
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("".join(kept))
    return report


def _cmd_prune(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    if not draft.is_file():
        print(f"No such draft: {args.draft}")
        return 1
    report = prune_evidence(draft, set(args.citekey) if args.citekey else None, args.apply)
    if not report:
        print(f"{draft_relpath(draft)}: nothing recorded-but-uncited to prune.")
        return 0
    for key, message in report.items():
        print(f"  `{key}`: {message}")
    if not args.apply:
        print("Dry run -- pass --apply to write.")
    # Exit 1 only when a *named* citekey was refused; a bare run with
    # nothing to do is clean.
    refused = [key for key, message in report.items() if message not in ("removed", "would remove")]
    return 1 if refused else 0
