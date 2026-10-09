"""The review layer's shared spine: where a report goes, and what it looks like.

Eleven commands make up the review layer -- `chitragupta/review/citation_provenance.py`,
`chitragupta/review/citation_coverage.py`, `chitragupta/review/verbatim_check/`,
`chitragupta/review/synthesis.py`, `chitragupta/review/figure_layout/`,
`chitragupta/review/uncited_prose.py`, `chitragupta/review/quotation.py`,
`chitragupta/review/agenda/`, `chitragupta/review/claim_support.py`,
`chitragupta/review/citekey_union.py` and
`chitragupta/review/verbatim_digest.py`. Each reads a draft -- plus
the corpus, or in `figure_layout`'s case the figures the draft references, in
`uncited_prose`'s case nothing else at all, in `citekey_union`'s case the
acceptance records the book's units were accepted under, or in `agenda`'s
case the other seven aids' own reports -- and produces evidence for a human
judgement. None gates, none blocks a draft, none takes the write lock,
and all eleven are interpreter tier 1. docs/ARCHITECTURE.md's "Layer 4:
the review layer" is the definition; this module is what makes the
eleven obey one output contract instead of eleven.

**One directory, mirroring the draft's path**, the same rule
`content/rendered/` and `content/dossiers/` already follow:

    content/drafts/<topic>/survey.md
      -> content/review/<topic>/survey.provenance.md   (+ .tex/.pdf)
         content/review/<topic>/survey.verbatim.md     (+ .tex/.pdf)
         content/review/<topic>/survey.coverage.md     (+ .tex/.pdf)
         content/review/<topic>/survey.synthesis.md    (+ .tex/.pdf)
         content/review/<topic>/survey.figure.md       (+ .tex/.pdf)
         content/review/<topic>/survey.uncited.md      (+ .tex/.pdf)
         content/review/<topic>/survey.quotation.md    (+ .tex/.pdf)
         content/review/<topic>/survey.agenda.md       (+ .tex/.pdf)
         content/review/<topic>/survey.support.md      (+ .tex/.pdf)
         content/review/<book>/book.union.md           (+ .tex/.pdf)
         content/review/<topic>/survey.digest.md       (+ .tex/.pdf)

so a draft, its dossier, its renders and its review artefacts are all
findable from the draft's own path. The `.tex`/`.pdf` land *beside* the
`.md` rather than in `content/rendered/`, which is the drafting layer's
publish output and not somewhere a review artefact belongs; `write()`
gets that by passing `output_dir` to `render_output.render`.

**A machine-readable sibling beside the Markdown.** `write_json()` files
`<stem>.<aid>.json` in that same directory, and `envelope()` gives it the
provenance `header()` gives the Markdown. It is an additional
serialisation of the findings the report already prints -- never a second
computation -- so that a caller consuming them programmatically does not
have to regex the printed form back into data (issue #127). A *sibling*,
not one of `write()`'s formats: `tex` and `pdf` are renders of the
Markdown through `chitragupta/render_output.py`, and this is not a render of
anything. All eleven aids emit one now -- `verbatim scan` since #127,
`provenance` and `coverage` since #309, and `synthesis`, `figure`,
`uncited`, `quotation`, `agenda`, `support`, `union` and `digest` from the
day each landed -- which is why `agenda` itself can read each of the other seven
aids' JSON as optional rather than required.

**No timestamp in a report.** The reason to write one at all is that it
becomes reviewable later and diffable across revisions, and a wall-clock
line in the header defeats the diff -- two runs over an unchanged draft
and corpus produce byte-identical Markdown. What the header does carry
is the draft, the exact command including its flags (a coverage report
means nothing without its `--query` values), and the version.

**Every report opens with a banner saying it is not a verdict.** The
docs say so too, but a file found on disk months later is exactly the
case the docs cannot reach.

Stdlib-only, and imports `render_output` lazily so the md-only path
doesn't pay for it -- same tier as the eleven commands it serves.
"""

import json
import sys
import tomllib
from pathlib import Path
from typing import TextIO

from chitragupta import config
from chitragupta.review._paths import report_dir, require_reviewable

# One place per aid, so a caller cannot invent a report kind by
# typo. The value is the suffix that goes between the draft's stem and
# the extension: content/review/<topic>/survey.provenance.md.
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

# Deliberately names its sources rather than linking to them: this text
# is copied into a file whose depth under content/review/ varies with the
# draft's topic path, so any relative link would be right for one report
# and broken for the next.
BANNER = (
    "> **Review aid, not a gate.** This report is evidence for a human "
    "judgement, never a verdict. A driver may read it back; no draft is "
    "blocked by what it says. See SOUL.md, and "
    'docs/ARCHITECTURE.md\'s "Layer 4: the review layer".'
)


def version() -> str:
    """The project version, for a report's header.

    Falls back to `"unknown"` rather than raising: a report that cannot
    name its version is still a useful report, and this is the only
    reason the review layer would ever read `pyproject.toml`.
    """
    try:
        with open(config.shipped("pyproject.toml"), "rb") as handle:
            return tomllib.load(handle)["tool"]["poetry"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


def report_path(draft: Path, aid: str, suffix: str = "md") -> Path:
    """`content/review/<topic>/<stem>.<aid>.<suffix>` for `draft`."""
    if aid not in AIDS:
        raise ValueError(f"Unknown review aid {aid!r}; expected one of {sorted(AIDS)}.")
    return report_dir(draft) / f"{Path(draft).stem}.{aid}.{suffix}"


def header(draft: Path, aid: str, command: str) -> list[str]:
    """The Markdown lines every report opens with: title, banner, and the
    provenance of the report itself -- draft, command, version.

    Deliberately no date; see the module docstring.
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
    """`BANNER` without its Markdown, for a payload that is read as data.

    Derived rather than restated, so the two cannot drift into saying
    different things about the same report.
    """
    return BANNER.removeprefix("> ").replace("**", "")


def envelope(draft: Path, aid: str, command: str) -> dict:
    """The provenance fields every aid's JSON payload opens with -- the
    data counterpart of `header()`, carrying the same facts: that this is
    not a verdict, which aid, which draft, the exact command including
    its flags, and the version.

    The notice leads, for the reason the module docstring gives about the
    Markdown banner: a file found on disk months later is exactly the
    case the docs cannot reach, and that is no less true of a file whose
    likeliest reader is an agent acting on it.

    Deliberately no date, for the reason the module docstring gives about
    the Markdown: two runs over an unchanged draft and corpus produce
    byte-identical JSON, so a payload kept beside a draft diffs cleanly
    across revisions instead of differing on every run.

    Returns a fresh dict each call, which the caller adds its own
    findings to -- the envelope names the run, not what the run found.
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

    Separate from `write()` rather than a fourth entry in its `formats`:
    everything in that list goes through `render_output.render`, which
    renders the Markdown into another *document* format. This is not a
    render of the report -- it is the findings the report was built from,
    serialised (see the module docstring).

    `indent=2` and a trailing newline: this file is read by a program but
    also diffed by a person and committed beside the draft it describes,
    the same way `dossier status --json` is formatted.
    """
    path = report_path(draft, aid, "json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write(draft: Path, aid: str, body: str, formats: list[str]) -> dict[str, Path]:
    """Writes `body` as `<stem>.<aid>.md` and renders the other `formats`
    beside it. Returns `{format: path}` for what succeeded.

    `md` is produced directly. `tex`/`pdf` go through
    `chitragupta/render_output.py`, the same path every genre draft uses -- it
    needs pandoc, and LuaLaTeX for pdf, so a missing binary is reported and
    skipped rather than failing the whole run, matching how every other
    stage in this project treats an absent optional tool. So is every
    other failure in `render_output._failures.RENDER_FAILURES`, the
    render gate's refusal among them.
    """
    md_path = report_path(draft, aid)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(body, encoding="utf-8")
    written = {"md": md_path}

    # `json` is dropped alongside `md`, not passed on to `render_output`:
    # it names the same path `write_json` files the payload at, and pandoc
    # accepts `json` as a real output format (its own document AST) -- so
    # routing it through would spend a subprocess writing something else
    # entirely over the payload, or under it, depending on which ran last.
    # Dropped rather than refused, because `--write` already files the
    # payload: a caller who names it here gets it either way.
    remaining = [fmt for fmt in formats if fmt not in ("md", "json")]
    if not remaining:
        return written

    # Imported here rather than at module top only to keep the import
    # cost off the md-only path; render_output is itself stdlib-only, so
    # there is no optional dependency to guard against.
    import subprocess

    from chitragupta import render_output
    from chitragupta.render_output._failures import RENDER_FAILURES

    for fmt in remaining:
        try:
            written[fmt] = render_output.render(str(md_path), fmt, output_dir=md_path.parent)
        except subprocess.CalledProcessError as exc:
            # A quoted excerpt can carry characters straight from the
            # source PDF (e.g. circled digits) that no font in the
            # render's chain can set -- a real rendering failure, not a bug in
            # this report. Its own branch only for pandoc's stderr.
            print(
                f"  WARNING: skipped {fmt} -- pandoc failed: {exc.stderr or exc}", file=sys.stderr
            )
        except RENDER_FAILURES as exc:
            # Every other way render() refuses: a missing binary, an
            # output dir outside content/, or the render gate refusing a
            # verbatim excerpt that quotes a `[@key]` the ledger lacks
            # (#949). The md report above is already written and
            # unaffected, and the caller files the `.json` the agenda reads
            # next, so one format is skipped rather than the run taken out
            # -- how render_output.py's own CLI reports each of these too.
            # The shared tuple rather than classes listed here, so a
            # failure render() gains later is caught without this
            # needing to know.
            print(f"  WARNING: skipped {fmt} -- {exc}", file=sys.stderr)
    return written


def print_written(written: dict[str, Path], stream: TextIO | None = None) -> None:
    """The one-line-per-format summary all three commands print.

    `json` is listed here too, so an aid that files the machine-readable
    sibling reports it the same way it reports the report itself -- a
    written file the caller isn't told about is one they will not know to
    look for.

    `stream` is how a caller whose stdout is itself machine-readable
    (`verbatim scan --json --write`) keeps this summary out of it: this
    is a note to a person, and it belongs on stderr whenever stdout has
    become a payload. Defaults to stdout, which is every other caller.
    """
    for fmt in ("md", "tex", "pdf", "json"):
        if fmt in written:
            print(f"  {fmt:4s} {written[fmt]}", file=stream or sys.stdout)
