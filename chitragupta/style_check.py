"""Prose conformance for a draft, checked against docs/WRITING-STANDARDS.md.

`python -m src.draft style <draft>` reports where a draft departs from the
rules that document marks decidable in its §9 -- the defect markers of §2,
the recorded dialect of §8, and an acronym never expanded at first use --
and says nothing about the rules it marks a judgement. Vale does that
matching, against the style vendored at assets/vale/; this module decides
*which* rules apply to *this* draft and turns the result into a report.
One finding is not Vale's: `src.style_acronym_drift` checks the draft's
own recorded glossary against the current acronym vocabulary in plain
Python, because that vocabulary lives in a per-host file Vale cannot
read.

**Advisory, and it exits 0 whatever it finds.** Not a gate, and not a
gate under a flag either. The reason is docs/ARCHITECTURE.md's "Layer 4":
`src.draft gate` is measured against the ledger, which is ground truth, so
an absolute verdict is available; this is measured against a `language:`
line someone typed into scope.md, which can be wrong, stale, or
deliberately overridden -- so blocking on it would refuse a correct draft
on a bad target. DEVELOPER-AGENTS.md bars promoting any new check into a
gate beside src/citation_gate.py, and this is the check that rule was
written for.

**Tier 1 with an optional binary**, exactly like `src.draft render`: the
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
import shutil
import subprocess
from pathlib import Path

from src import config, dossier
from src.style_acronym_drift import findings as acronym_drift_findings
from src.style_report import report
from src.style_rules import DIALECT_RULES, _ALL_DIALECT_RULES



class MissingBinary(RuntimeError):
    """Vale is not on PATH. Named for render_output's exception of the
    same shape, and handled the same way: reported to the caller as a
    warning, never raised past the CLI."""


def language_of(draft: Path) -> str | None:
    """The BCP-47 tag in this draft's dossier `scope.md`, or None.

    None covers three different situations that all want the same
    treatment -- no dossier, no `language:` line (every dossier written
    before 5.12.0), and the "not settled" placeholder `init` ships. Each
    means *nobody has chosen a dialect*, and the honest response to that
    is to skip the dialect rules and say so.
    """
    try:
        scope = dossier.dossier_dir(draft) / dossier.SCOPE_MD
    except Exception:  # pylint: disable=broad-except
        return None  # a draft outside content/ has no dossier path to compute
    if not scope.is_file():
        return None
    for line in scope.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("- language:"):
            continue
        value = stripped.split(":", 1)[1].strip()
        # "not settled -- a BCP-47 tag (`en-GB`, ...)" is the shipped
        # placeholder, and it *contains* real tags, so the whole value
        # cannot be trusted. Matched by prefix rather than by tag shape,
        # because "not" is itself three lowercase letters and passes for a
        # BCP-47 primary subtag.
        if value.lower().startswith("not settled"):
            return None
        tag = value.split()[0] if value else ""
        # Returned even when this style has no rules for it. "Recorded
        # fr-FR, nothing to check it with" and "nobody chose one" are
        # different states, and only the second is worth prompting about.
        return tag or None
    return None


def resolve_language(draft: Path, override: str | None = None) -> tuple[str | None, str]:
    """The dialect to check `draft` against, and where it came from.

    Three sources, most specific first, because that is the order in which
    someone's intent gets more specific: a flag typed for this run, the
    draft's own recorded property, then a standing preference for this
    machine. The source travels with the tag so the report can name it --
    a draft checked against a host-wide default must not look like a draft
    that declared one.
    """
    if override:
        return override, "--language"
    recorded = language_of(draft)
    if recorded:
        return recorded, "scope.md"
    if config.STYLE_LANGUAGE:
        return config.STYLE_LANGUAGE, "config.toml"
    return None, "nothing"


def rule_filter(language: str | None) -> str:
    """A Vale `--filter` expression keeping every rule except the dialect
    rules that do not apply to `language`.

    Expressed as exclusions rather than inclusions so that a rule added to
    assets/vale/ later is enabled by default: forgetting to list a new
    rule here would otherwise silently disable it, which is the failure
    mode that is invisible in a report of zero findings.
    """
    wanted = DIALECT_RULES.get(language or "", ())
    if isinstance(wanted, str):
        wanted = (wanted,)
    excluded = [rule for rule in _ALL_DIALECT_RULES if rule not in wanted]
    return " and ".join(f'.Name != "{rule}"' for rule in excluded)


def _vale_argv(draft: Path, language: str | None) -> list[str]:
    return [
        "vale",
        f"--config={config.VALE_CONFIG_PATH}",
        "--output=JSON",
        "--no-exit",  # findings are not this command's exit code; see the docstring
        f"--filter={rule_filter(language)}",
        str(draft),
    ]


def run_vale(draft: Path, language: str | None) -> list[dict]:
    """Vale's findings for `draft`, flattened out of its per-file JSON."""
    if shutil.which("vale") is None:
        raise MissingBinary(
            "vale is not on PATH, so no prose check ran. Install it with "
            "`bash scripts/install_full_pipeline.sh os-deps`, or see "
            "assets/vale/README.md for the pinned version. The draft is "
            "unaffected -- this check is advisory."
        )
    result = subprocess.run(
        _vale_argv(draft, language), capture_output=True, text=True, check=False,
        cwd=config.PROJECT_ROOT,
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
        tag: sum(1 for f in run_vale(draft, tag)
                 if f.get("Check", "").startswith("chitragupta.Dialect"))
        for tag in ("en-GB", "en-US")
    }
    best, worst = sorted(counts, key=lambda tag: counts[tag])
    if counts[best] == counts[worst]:
        return None
    return best, counts


def check(draft: Path, override: str | None = None) -> dict:
    """Everything one draft's report is built from, as data."""
    language, source = resolve_language(draft, override)
    findings = collapse(run_vale(draft, language)) + acronym_drift_findings(draft)
    proposal = None
    if language is None:
        proposed = propose_language(draft)
        if proposed:
            proposal = {"language": proposed[0], "findings_by_language": proposed[1]}
    return {"draft": str(draft), "language": language, "language_source": source,
            "findings": findings, "proposed_language": proposal}


def build_parser():
    import argparse  # local, so importing this module stays cheap for the hook

    parser = argparse.ArgumentParser(
        prog="python -m src.draft style",
        description="Check a draft's prose against docs/WRITING-STANDARDS.md. "
                    "A review aid: it exits 0 whatever it finds.",
    )
    parser.add_argument("draft", nargs="+", help="draft(s) under content/")
    parser.add_argument("--language", metavar="TAG",
                        help="check against this dialect for this run only, "
                             "ahead of scope.md and config.toml; writes nothing")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable findings, for a hook or an agenda")
    return parser


def main(argv=None):
    """Always 0. The one exception is a usage error, which argparse owns
    and which is a mistake by the caller rather than a finding about the
    draft."""
    args = build_parser().parse_args(argv)
    payloads, warnings = [], []
    for name in args.draft:
        draft = Path(name)
        try:
            payloads.append(check(draft, args.language))
        except MissingBinary as exc:
            warnings.append(str(exc))
            break  # the binary will not appear between two drafts
        except OSError as exc:
            warnings.append(f"{draft}: {exc}")
    if args.json:
        print(json.dumps({"notice": "Review aid, not a gate.",
                          "drafts": payloads, "warnings": warnings}, indent=2))
    else:
        for payload in payloads:
            print("\n".join(report(Path(payload["draft"]), payload)))
        for warning in warnings:
            print(f"WARNING: {warning}")
    return 0
