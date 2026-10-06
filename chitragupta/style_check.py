"""Prose conformance for a draft, checked against docs/WRITING-STANDARDS.md.

`python -m chitragupta.draft style <draft>` reports where a draft departs from the
rules that document marks decidable in its §9 -- the defect markers of §2,
the recorded dialect of §8, and an acronym never expanded at first use --
and says nothing about the rules it marks a judgement. Vale does that
matching, against the style vendored at assets/vale/; this module decides
*which* rules apply to *this* draft and turns the result into a report.
One finding is not Vale's: `chitragupta.style_acronym_drift` checks the draft's
own recorded glossary against the current acronym vocabulary in plain
Python, because that vocabulary lives in a per-host file Vale cannot
read.

**Advisory, and it exits 0 whatever it finds.** Not a gate, and not a
gate under a flag either. The reason is docs/ARCHITECTURE.md's "Layer 4":
`chitragupta.draft gate` is measured against the ledger, which is ground truth, so
an absolute verdict is available; this is measured against a `language:`
line someone typed into scope.md, which can be wrong, stale, or
deliberately overridden -- so blocking on it would refuse a correct draft
on a bad target. DEVELOPER-AGENTS.md bars promoting any new check into a
gate beside chitragupta/citation_gate.py, and this is the check that rule was
written for.

**Tier 1 with an optional binary**, exactly like `chitragupta.draft render`: the
Python here imports nothing outside the standard library and runs on the
bare system interpreter, and the `vale` binary is probed for and reported
missing rather than assumed. A host without it loses this report and keeps
everything else, which is the same bargain render makes with pandoc.

Three behaviours worth knowing before reading the code, each learned from
running this over a real 178,000-word book rather than chosen up front:

- **The dialect rules are mutually exclusive, and selected per draft.**
  assets/vale/ ships DialectGB, DialectUS and DialectIN; enabling all
  three at once makes every draft wrong in two directions. `--filter`
  picks one, which leaves the vendored config byte-identical to what was
  reviewed -- appending a second `[*.{md,tex}]` section to a copy does
  not work, because Vale treats the later section as an override and
  silently drops `BasedOnStyles`, reporting nothing at all.
- **Findings are collapsed per (rule, match).** The book uses "AI" 45
  times without ever expanding it; that is one thing to fix, not 45. The
  count travels with the finding so nothing is hidden.
- **A draft whose dialect is unrecorded gets no dialect rules**, and is
  told so. `scope.md` ships `language:` as "not settled", and every
  dossier written before 5.12.0 has no such line at all -- guessing en-US
  for those would report a preference nobody chose.
"""

import json

# `_run` is the one patch point for this module's external launches
# (#854), in the shape `render_output._pandoc._run_pandoc` set: a test
# fakes it here and so fakes this module's subprocess and nobody
# else's. Patching the global `subprocess.run` reached every launch in
# the process.
from subprocess import run as _run
from pathlib import Path
from typing import Any

from chitragupta import config, install, programs
from chitragupta.style_language import resolve_language, rule_filter
from chitragupta.style_report import report
from chitragupta.style_rules import PYTHON_CHECKS, with_repair


class MissingBinary(RuntimeError):
    """Vale is not on PATH. Named for render_output's exception of the
    same shape, and handled the same way: reported to the caller as a
    warning, never raised past the CLI."""


def _vale_argv(vale: str, draft: Path, language: str | None) -> list[str]:
    return [
        vale,
        f"--config={config.VALE_CONFIG_PATH}",
        "--output=JSON",
        "--no-exit",  # findings are not this command's exit code; see the docstring
        f"--filter={rule_filter(language)}",
        # Resolved rather than passed as the caller typed it: the process
        # below runs with cwd=config.PROJECT_ROOT so vale can find the
        # vendored config, but a relative draft path is relative to the
        # *caller's* cwd -- from anywhere else, vale fails to find the
        # file while every Python-side check (resolved against the real
        # cwd) still passes, and that mismatch is exactly the "could not
        # run" this function exists to catch (#495).
        str(Path(draft).resolve()),
    ]


def run_vale(draft: Path, language: str | None) -> list[dict]:
    """Vale's findings for `draft`, flattened out of its per-file JSON."""
    vale = programs.resolve_program("vale")
    if vale is None:
        raise MissingBinary(
            "vale is not on PATH, so no prose check ran. Install it with "
            f"{install.remedy('os-deps')}, or see "
            "assets/vale/README.md for the pinned version. The draft is "
            "unaffected -- this check is advisory."
        )
    result = _run(
        _vale_argv(vale, draft, language),
        capture_output=True,
        text=True,
        check=False,
        cwd=config.PROJECT_ROOT,
    )
    # `--no-exit` keeps a nonzero exit reserved for vale itself failing to
    # run -- a missing file, a broken filter, a malformed config -- rather
    # than for findings. Those failures write to stderr and leave stdout
    # empty, which `json.loads(result.stdout or "{}")` below would
    # otherwise read as "{}": a clean run indistinguishable from a run
    # that never happened (#495). Checked before the parse, not folded
    # into the except below, because empty-and-nonzero is vale refusing
    # to run at all, not vale producing output this module can't read.
    if result.returncode != 0 and not result.stdout.strip():
        raise MissingBinary(
            f"vale exited {result.returncode} without checking the draft "
            f"({result.stderr.strip() or 'no stderr output'}). The draft is "
            "unaffected -- this check is advisory."
        )
    # Vale prints `{}` for a clean run and a JSON object keyed by path
    # otherwise. A parse failure is a broken vendored config rather than a
    # broken draft, so it is raised at the caller rather than swallowed
    # into an empty -- and therefore reassuring -- finding list.
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MissingBinary(
            f"vale produced output this command could not read ({exc}). "
            f"Check {config.VALE_CONFIG_PATH}.\n{result.stderr}"
        ) from exc
    return [finding for findings in payload.values() for finding in findings]


def collapse(findings: list[dict]) -> list[dict]:
    """One entry per (rule, matched text), carrying the first line it
    appears on and how many times it appears.

    Measured reason: a book chapter that never expands "AI" produces 45
    identical findings, and a report of 337 lines where 55 are distinct is
    one nobody reads to the end. The count is kept rather than dropped so
    that "once, in passing" and "throughout" stay distinguishable.
    """
    collapsed: dict[tuple[str, str], dict] = {}
    for finding in sorted(findings, key=lambda f: (f.get("Line", 0), f.get("Check", ""))):
        key = (finding.get("Check", ""), finding.get("Match", ""))
        if key in collapsed:
            collapsed[key]["count"] += 1
            continue
        collapsed[key] = {
            "rule": key[0],
            "match": key[1],
            "line": finding.get("Line", 0),
            "message": finding.get("Message", ""),
            "severity": finding.get("Severity", ""),
            "count": 1,
        }
    return sorted(collapsed.values(), key=lambda f: (-f["count"], f["line"]))


def propose_language(draft: Path) -> tuple[str, dict[str, int]] | None:
    """Which dialect `draft` reads as, measured by checking it both ways.

    Only ever a suggestion, and only computed when nobody has declared
    one. docs/HOUSE-STYLE.md's rule is that the machine proposes and the
    human accepts -- so this prints a command to run and writes nothing.
    Measured on a real book: 5 findings as en-GB against 400 as en-US, so
    at document length the signal is not subtle.

    None when the two are too close to call, which is the honest answer
    for a short draft with no dialect-bearing words in it at all.
    """
    # Dialect findings only. Every other rule fires identically whichever
    # dialect is assumed, so counting them in would add the same number to
    # both sides and bury the signal under the noise -- measured on one
    # chapter, 18 against 31 rather than the true 0 against 26.
    counts = {
        tag: sum(
            1 for f in run_vale(draft, tag) if f.get("Check", "").startswith("chitragupta.Dialect")
        )
        for tag in ("en-GB", "en-US")
    }
    best, worst = sorted(counts, key=lambda tag: counts[tag])
    if counts[best] == counts[worst]:
        return None
    return best, counts


def check(draft: Path, override: str | None = None, propose: bool = True) -> dict:
    """Everything one draft's report is built from, as data.

    `propose=False` skips `propose_language` (two extra Vale runs)
    entirely -- for a caller that never reads `proposed_language`, such
    as the review agenda's `_read_style` (#495), those runs cost the
    same two subprocess launches for nothing every single time it reads
    the `prose` class."""
    # The Python-side findings are computed first and survive a missing
    # Vale. They used to be appended to `run_vale`'s result, so the
    # `MissingBinary` it raises took the glossary and table findings down
    # with it -- a host that never ran the `os-deps` install stage lost
    # two checks that never needed the binary. The absence is reported as
    # `vale_error` rather than raised, because a report naming what did
    # not run is this module's whole header discipline.
    language, source = resolve_language(draft, override)
    findings = [found for rule in PYTHON_CHECKS for found in rule(draft)]
    vale_error, proposal = None, None
    try:
        findings = with_repair(collapse(run_vale(draft, language)), source) + findings
    except MissingBinary as exc:
        vale_error = str(exc)
    # Not attempted without Vale: the proposal is measured *by* running
    # it both ways, so on a host without it there is nothing to measure.
    proposed = (
        propose_language(draft) if propose and language is None and vale_error is None else None
    )
    if proposed:
        proposal = {"language": proposed[0], "findings_by_language": proposed[1]}
    return {
        "draft": str(draft),
        "language": language,
        "language_source": source,
        "findings": findings,
        "proposed_language": proposal,
        "vale_error": vale_error,
    }


def build_parser() -> Any:
    import argparse  # local, so importing this module stays cheap for the hook

    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft style",
        description="Check a draft's prose against docs/WRITING-STANDARDS.md. "
        "A review aid: it exits 0 whatever it finds.",
    )
    parser.add_argument("draft", nargs="+", help="draft(s) under content/")
    parser.add_argument(
        "--language",
        metavar="TAG",
        help="check against this dialect for this run only, "
        "ahead of scope.md and config.toml; writes nothing",
    )
    parser.add_argument(
        "--json", action="store_true", help="machine-readable findings, for a hook or an agenda"
    )
    return parser


def main(argv=None) -> int:
    """Always 0. The one exception is a usage error, which argparse owns
    and which is a mistake by the caller rather than a finding about the
    draft."""
    args = build_parser().parse_args(argv)
    payloads, warnings = [], []
    for name in args.draft:
        draft = Path(name)
        try:
            payloads.append(check(draft, args.language))
        except OSError as exc:
            warnings.append(f"{draft}: {exc}")
    # Once, not once per draft: the binary will not appear between two of
    # them, and repeating an identical warning is noise. Every draft is
    # still checked, because the findings Vale does not produce do not
    # depend on it.
    warnings += sorted({payload["vale_error"] for payload in payloads} - {None})
    if args.json:
        print(
            json.dumps(
                {"notice": "Review aid, not a gate.", "drafts": payloads, "warnings": warnings},
                indent=2,
            )
        )
    else:
        for payload in payloads:
            print("\n".join(report(Path(payload["draft"]), payload)))
        for warning in warnings:
            print(f"WARNING: {warning}")
    return 0
