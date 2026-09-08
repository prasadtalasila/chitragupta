"""Remove an `evidence.md` block for a citekey the draft no longer
cites -- #701's sub-defect 2, the removal primitive that did not exist.

Every comparable repair in this pipeline has a command:
`dossier sections --citekeys --write` for a stale section row,
`python -m chitragupta.draft references` for the reference list. This
one was a free-form `Edit` offered by `draft-reviser` in prose, so it
could not be re-run, verified or diffed, and `revisions.md` was the
only trace it had happened.

**Dry run by default.** `recorded - cited` cannot distinguish "the user
cut this citation" from "a candidate was transcribed into `evidence.md`
and never cited at all". The first wants the block gone; the second
wants it exactly where it is. Deleting recorded evidence unattended
would trade a cosmetic staleness for a real loss, so `--apply` is
opt-in and a person reads the report first. That is also why there is
no `--all`-style force: the confirmation *is* the feature.

**`evidence.md` only.** `sections.md` already has a writer that derives
the whole table from the draft (`_sections._sections_citekeys`), so a
stale row there self-heals on the next `--write` and a second writer
would only be a way for the two to disagree. `rejected.md` is never
touched, and never can be: `recorded_but_uncited` does not read it, so
nothing this module iterates can name a declined paper -- an invariant
by construction rather than by a guard (`_citekeys.CITED_FILES` draws
the same line for `drift()`).
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

    Returns the bool first and the message second **because the caller
    branches on the bool**. An earlier shape returned only the message
    and tested it for `"would remove"`, which makes rewording a string
    silently break the deletion with no test failing -- the exact
    "tested against the shape it was blind to" hazard
    DEVELOPER-AGENTS.md names. The message is presentation only.

    Four refusals rather than one, because a command whose whole design
    rests on a person confirming it has to say what it declined and
    why: "still cited" is the one a script most needs to hear, and
    "recorded only in sections.md" is the one with another command as
    its answer.

    `recorded` is every citekey either `CITED_FILES` mentions, and it
    is what separates the first two refusals. Inferring "not recorded"
    from the absence of an `evidence.md` span instead would report a
    cited, `sections.md`-only citekey as unrecorded -- false, and
    exactly the sort of message a person then acts on.
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

    Deletes by **line span**, never by matching the text
    `evidence_blocks` reconstructs -- see `evidence_block_spans` for the
    three ordinary file shapes that break a substring match, one of
    which (CRLF) breaks it for every block in the file.
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
        # `newline=""` on both halves, which is what actually preserves
        # the file's line endings -- and the bare `read_text` this used
        # first does not. Universal-newline mode translates CRLF to
        # `\n` on the way in, so `keepends` faithfully keeps an ending
        # that has already been rewritten, and pruning one block from a
        # CRLF dossier silently converted the whole file to LF. Caught
        # by a smoke test's `od`, not by the unit test, which did its
        # own join over raw lines and so never exercised this path.
        #
        # Via `open()` rather than `read_text(newline=...)`: that
        # keyword reached `Path.read_text` only in 3.13, while this
        # project supports 3.12 (`pyproject.toml`'s `python`), so the
        # tidier spelling passes locally and `TypeError`s in CI. Note
        # `write_text` *has* taken it since 3.10 -- the asymmetry is
        # the trap, and matching both to `open()` is what removes it.
        #
        # Line *counts* agree between the two modes -- `splitlines`
        # splits on `\r\n`, `\n` and a lone `\r` alike -- so the spans
        # `_parse_evidence` computed under universal newlines index
        # this list correctly.
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
    # Exit 1 only when a *named* citekey was refused, so a script that
    # asked for a specific key hears about it. A bare run that found
    # nothing to do is a clean state, not a failure.
    refused = [key for key, message in report.items() if message not in ("removed", "would remove")]
    return 1 if refused else 0
