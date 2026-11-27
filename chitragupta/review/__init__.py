"""The review layer's shared spine: where a report goes, and what it looks like.

Eleven review aids (citation_provenance, citation_coverage, verbatim_check,
synthesis, figure_layout, uncited_prose, quotation, agenda, claim_support,
citekey_union, verbatim_digest) each read a draft and produce evidence for
a human judgement. None gates, blocks or takes the write lock, and all are
interpreter tier 1. docs/ARCHITECTURE.md's "Layer 4: the review layer" is
the definition; this module gives the eleven one output contract.

Reports mirror the draft's path, `content/drafts/<topic>/survey.md` ->
`content/review/<topic>/survey.<aid>.md`, with `.tex`/`.pdf` beside the
`.md` rather than in `content/rendered/`, the drafting layer's publish
output. A `.json` sibling serialises the same findings, never a second
computation, so callers need not regex the Markdown (#127).

No timestamp in a report, so two runs over an unchanged draft diff
byte-identical. Every report opens with a not-a-verdict banner, because a
file found on disk months later is the case the docs cannot reach.
"""

import json
import sys
import tomllib
from pathlib import Path
from typing import TextIO

from chitragupta import _private_use, config
from chitragupta.review._paths import report_dir, require_reviewable

# Value is the suffix between the draft's stem and the extension
# (survey.provenance.md); one table, so no report kind is invented by typo.
AIDS = {
    "provenance": "Citation provenance",
    "verbatim": "Verbatim scan",
    "coverage": "Citation coverage",
    "synthesis": "Multi-source synthesis",
    "figure": "TikZ layout check",
    "uncited": "Uncited prose",
    "quotation": "Quotation integrity",
    "agenda": "Agenda",
    "support": "Claim support",
    "union": "Citekey union",
    "digest": "Verbatim digest",
}

# Names its sources rather than linking them: report depth under
# content/review/ varies, so a relative link would break.
BANNER = (
    "> **Review aid, not a gate.** This report is evidence for a human "
    "judgement, never a verdict. A driver may read it back; no draft is "
    "blocked by what it says. See SOUL.md, and "
    'docs/ARCHITECTURE.md\'s "Layer 4: the review layer".'
)


def version() -> str:
    """The project version, for a report's header; `"unknown"` rather than
    raising, since a report that cannot name its version is still useful.
    """
    try:
        with open(config.shipped("pyproject.toml"), "rb") as handle:
            return tomllib.load(handle)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


def report_path(draft: Path, aid: str, suffix: str = "md") -> Path:
    """`content/review/<topic>/<stem>.<aid>.<suffix>` for `draft`."""
    if aid not in AIDS:
        raise ValueError(f"Unknown review aid {aid!r}; expected one of {sorted(AIDS)}.")
    return report_dir(draft) / f"{Path(draft).stem}.{aid}.{suffix}"


def header(draft: Path, aid: str, command: str) -> list[str]:
    """The Markdown lines every report opens with: title, banner, draft,
    command, version. Deliberately no date (see the module docstring).
    """
    return [
        f"# {AIDS[aid]}: {draft}",
        "",
        BANNER,
        "",
        f"- Draft: `{draft}`",
        f"- Command: `{command}`",
        f"- chitragupta {version()}",
        "",
    ]


def notice() -> str:
    """`BANNER` without its Markdown, derived so the two cannot drift."""
    return BANNER.removeprefix("> ").replace("**", "")


def envelope(draft: Path, aid: str, command: str) -> dict:
    """The provenance fields every aid's JSON payload opens with, the data
    counterpart of `header()`. The notice leads and there is no date, for
    the module docstring's reasons. Returns a fresh dict for the caller's
    findings.
    """
    return {
        "notice": notice(),
        "aid": aid,
        "draft": str(draft),
        "command": command,
        "version": version(),
    }


def write_json(draft: Path, aid: str, payload: dict) -> Path:
    """Writes `payload` as `<stem>.<aid>.json` beside the Markdown report.

    Not one of `write()`'s formats: those are renders through
    `render_output`, and this is the findings themselves. `indent=2` and a
    trailing newline because it is also diffed and committed by a person.
    """
    path = report_path(draft, aid, "json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write(draft: Path, aid: str, body: str, formats: list[str]) -> dict[str, Path]:
    """Writes `body` as `<stem>.<aid>.md` and renders the other `formats`
    beside it. Returns `{format: path}` for what succeeded.

    A missing pandoc/LuaLaTeX, or any other failure in
    `render_output._failures.RENDER_FAILURES`, skips that format rather
    than failing the run.
    """
    md_path = report_path(draft, aid)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    # Before the .md, so the .tex/.pdf can set every character (#1125); the
    # .json, written separately, keeps the original.
    body, markers = _private_use.mark(body)
    if markers:
        print(_private_use.note(markers), file=sys.stderr)
    md_path.write_text(body, encoding="utf-8")
    written = {"md": md_path}

    # `json` is dropped, not passed to `render_output`: pandoc accepts `json`
    # as its own AST format and would overwrite the payload `write_json` files.
    remaining = [fmt for fmt in formats if fmt not in ("md", "json")]
    if not remaining:
        return written

    # Lazy, only to keep the import cost off the md-only path.
    import subprocess

    from chitragupta import render_output
    from chitragupta.render_output._failures import RENDER_FAILURES

    for fmt in remaining:
        try:
            written[fmt] = render_output.render(str(md_path), fmt, output_dir=md_path.parent)
        except subprocess.CalledProcessError as exc:
            # Source characters (e.g. circled digits) no font can set: a
            # real render failure, not a bug in this report.
            print(
                f"  WARNING: skipped {fmt} -- pandoc failed: {exc.stderr or exc}", file=sys.stderr
            )
        except RENDER_FAILURES as exc:
            # Every other render() refusal (missing binary, output dir
            # outside content/, render gate refusing an unknown `[@key]`,
            # #949): skip one format, since the .md and the agenda's .json
            # are already filed. The shared tuple catches future failures.
            print(f"  WARNING: skipped {fmt} -- {exc}", file=sys.stderr)
    return written


def print_written(written: dict[str, Path], stream: TextIO | None = None) -> None:
    """The one-line-per-format summary all three commands print, `json`
    included. `stream` lets a caller whose stdout is a payload
    (`verbatim scan --json --write`) send this note to stderr.
    """
    for fmt in ("md", "tex", "pdf", "json"):
        if fmt in written:
            print(f"  {fmt:4s} {written[fmt]}", file=stream or sys.stdout)
