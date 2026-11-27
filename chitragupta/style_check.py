"""Prose conformance for a draft, checked against docs/WRITING-STANDARDS.md.

`python -m chitragupta.draft style <draft>` reports the rules §9 marks
decidable; Vale does the matching against assets/vale/, and this module
picks which rules apply and builds the report. Python-side checks (such
as `style_acronym_drift`) cover what Vale cannot read.

Advisory, exiting 0 whatever it finds, never a gate: it measures against
a typed `language:` line that can be wrong (docs/ARCHITECTURE.md "Layer
4"), and DEVELOPER-AGENTS.md bars a gate beside citation_gate.py. Tier 1
with an optional `vale` binary, reported missing rather than assumed.

Learned on a 178,000-word book: dialect rules are exclusive and picked
by `--filter` (a second config section makes Vale drop
`BasedOnStyles`); findings collapse per (rule, match) with a count; and
an unrecorded dialect gets no dialect rules, and is told so.
"""

import json
import sys

# The one patch point for this module's launches (#854), so a test fakes
# only this module's subprocess.
from subprocess import run as _run
from pathlib import Path
from typing import Any

from chitragupta import (
    citation_gate,
    config,
    install,
    programs,
    style_exceptions,
    style_latex,
    style_quotes,
    style_vendored,
)
from chitragupta.style_language import resolve_language, rule_filter
from chitragupta.style_report import report
from chitragupta.style_rules import PYTHON_CHECKS, with_repair
from chitragupta.progname import prog_for


class MissingBinary(RuntimeError):
    """Vale is not on PATH. Reported to the caller as a warning, as
    render_output does, never raised past the CLI."""


def _vale_argv(vale: str, draft: Path, language: str | None) -> list[str]:
    return [
        vale,
        f"--config={config.VALE_CONFIG_PATH}",
        "--output=JSON",
        "--no-exit",  # findings are not this command's exit code; see the docstring
        f"--filter={rule_filter(language)}",
        # Resolved: vale runs with cwd=config.PROJECT_ROOT to find its
        # config, so a caller-relative path would fail there while the
        # Python checks passed (#495). A `.tex` draft goes on stdin,
        # blanked, with its extension so `tex = md` still applies.
        "--ext=.tex" if citation_gate.is_latex(draft) else str(Path(draft).resolve()),
    ]


def run_vale(draft: Path, language: str | None) -> list[dict]:
    """Vale's findings for `draft`, flattened out of its per-file JSON.
    A `.tex` draft goes on stdin blanked by `style_latex.for_vale`."""
    vale = programs.resolve_program("vale")
    if vale is None:
        raise MissingBinary(
            "vale is not on PATH, so no prose check ran. Install it with "
            f"{install.remedy('os-deps')}, or see "
            "assets/vale/README.md for the pinned version. The draft is "
            "unaffected -- this check is advisory."
        )
    text = Path(draft).read_text(encoding="utf-8")
    result = _run(
        _vale_argv(vale, draft, language),
        input=style_latex.for_vale(text) if citation_gate.is_latex(draft) else None,
        capture_output=True,
        text=True,
        # Not the locale's codec, which could refuse non-ASCII text.
        encoding="utf-8",
        check=False,
        cwd=config.PROJECT_ROOT,
    )
    # `--no-exit` reserves a nonzero exit for vale failing to run, whose
    # empty stdout would otherwise parse as a clean "{}" (#495).
    if result.returncode != 0 and not result.stdout.strip():
        raise MissingBinary(
            f"vale exited {result.returncode} without checking the draft "
            f"({result.stderr.strip() or 'no stderr output'}). The draft is "
            "unaffected -- this check is advisory."
        )
    # A parse failure is a broken vendored config, raised rather than
    # turned into a reassuringly empty list.
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MissingBinary(
            f"vale produced output this command could not read ({exc}). "
            f"Check {config.VALE_CONFIG_PATH}.\n{result.stderr}"
        ) from exc
    flattened = [finding for findings in payload.values() for finding in findings]
    kept = style_quotes.drop_quoted(style_exceptions.drop_exempt(flattened, text), text)
    return style_vendored.reconcile(kept)


def collapse(findings: list[dict]) -> list[dict]:
    """One entry per (rule, matched text), carrying the first line it
    appears on and how many times it appears (a chapter never expanding
    "AI" gave 45 identical findings; the count keeps "throughout" visible).
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

    Only a suggestion when nobody declared one: it prints a command and
    writes nothing (docs/HOUSE-STYLE.md). None when too close to call.
    """
    # Dialect findings only: the rest fire identically either way and
    # would bury the signal.
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

    `propose=False` skips `propose_language`'s two extra Vale runs, for a
    caller such as the agenda's `_read_style` (#495)."""
    # Python-side findings first, so they survive a missing Vale, which is
    # reported as `vale_error` rather than raised.
    language, source = resolve_language(draft, override)
    findings = [found for rule in PYTHON_CHECKS for found in rule(draft)]
    vale_error, proposal = None, None
    try:
        findings = with_repair(collapse(run_vale(draft, language)), source) + findings
    except MissingBinary as exc:
        vale_error = str(exc)
    # Not attempted without Vale: the proposal is measured by running it.
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
    # Local, so importing this module stays cheap for the hook.
    from chitragupta.help_format import ClickParser

    parser = ClickParser(
        prog=f"{prog_for('draft')} style",
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
    """0 for any finding, with or without Vale. Usage errors exit 2,
    including a broken `style_exceptions.toml` (#1187): loading it as
    empty would silently re-raise every declared term."""
    args = build_parser().parse_args(argv)
    payloads, warnings = [], []
    for name in args.draft:
        draft = Path(name)
        try:
            payloads.append(check(draft, args.language))
        except OSError as exc:
            warnings.append(f"{draft}: {exc}")
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
    # Warned once, not per draft; every draft is still checked.
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
