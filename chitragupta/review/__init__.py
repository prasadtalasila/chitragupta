"""The review layer's shared spine: where a report goes, and what it looks like.

Three commands make up the review layer -- `chitragupta/review/citation_provenance.py`,
`chitragupta/review/citation_coverage.py` and `chitragupta/review/verbatim_check.py`. Each reads a
draft plus the corpus and produces evidence for a human judgement. None
gates, none runs automatically, none takes the write lock, and all three
are interpreter tier 1. docs/ARCHITECTURE.md's "Layer 4: the review
layer" is the definition; this module is what makes the three obey one
output contract instead of three.

**One directory, mirroring the draft's path**, the same rule
`content/rendered/` and `content/dossiers/` already follow:

    content/drafts/<topic>/survey.md
      -> content/review/<topic>/survey.provenance.md   (+ .tex/.pdf)
         content/review/<topic>/survey.verbatim.md     (+ .tex/.pdf)
         content/review/<topic>/survey.coverage.md     (+ .tex/.pdf)

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
anything. `verbatim` is so far the only aid that emits one; the other two
follow in their own issues, which is why docs/AUTO-IMPROVEMENT.md's
`agenda` reads each aid's JSON as optional.

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
doesn't pay for it -- same tier as the three commands it serves.
"""

import json
import sys
import tomllib
from pathlib import Path
from typing import TextIO

from chitragupta import config

# One place per aid, so a caller cannot invent a fourth report kind by
# typo. The value is the suffix that goes between the draft's stem and
# the extension: content/review/<topic>/survey.provenance.md.
AIDS = {
    "provenance": "Citation provenance",
    "verbatim": "Verbatim scan",
    "coverage": "Citation coverage",
}

# Deliberately names its sources rather than linking to them: this text
# is copied into a file whose depth under content/review/ varies with the
# draft's topic path, so any relative link would be right for one report
# and broken for the next.
BANNER = (
    "> **Review aid, not a gate.** This report is evidence for a human "
    "judgement, never a verdict. Nothing in this pipeline reads it back, and "
    "no draft is blocked by what it says. See SOUL.md, and "
    "docs/ARCHITECTURE.md's \"Layer 4: the review layer\"."
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


def require_reviewable(draft: Path, what: str = "draft") -> Path:
    """Returns `draft`, having refused it if it is missing or outside `content/`.

    The layer's input contract in one place. The containment half is the
    tier-1 rule 3.17.0 set for `citation_gate`, `references` and
    `render_output` and did not then apply to the three review aids --
    everything this pipeline touches lives under `content/`, so that one
    directory is the whole record of the work. The existence half is here
    so all three commands fail the same way on a mistyped path, instead
    of one returning 1 and two raising `FileNotFoundError`.
    """
    path = config.require_inside_content(Path(draft), what)
    if not path.is_file():
        raise FileNotFoundError(f"No such {what}: {draft}")
    return path


def report_dir(draft: Path) -> Path:
    """Where `draft`'s review reports go: `config.REVIEW_DIR` with the
    draft's own place under `config.DRAFTS_DIR` mirrored into it.

    Falls back to a flat `REVIEW_DIR` for a draft that is under
    `content/` but not under `content/drafts/`, matching
    `render_output._output_dir`'s policy rather than
    `dossier.dossier_dir`'s raise: a review aid that refuses to run is a
    worse answer than one that writes flat, and unlike a dossier, nothing
    later goes looking for the report by its mirrored path.
    """
    for label, directory in (("review", config.REVIEW_DIR), ("drafts", config.DRAFTS_DIR)):
        if not config.resolves_inside(directory, config.CONTENT_DIR):
            raise config.OutsideContentDir(
                f"{directory} resolves to {directory.resolve()}, outside the content "
                f"directory {config.CONTENT_DIR.resolve()}. A review report mirrors "
                f"the draft's path from content/drafts/ into content/review/, so a "
                f"'{label}' that points out of the content directory has no mirror to "
                "compute and would write where nothing else in this pipeline looks. "
                "Move it back, or point [content].dir (config.toml) at wherever it "
                "really lives."
            )

    mirrored = config.mirrored_dir(draft, config.DRAFTS_DIR, config.REVIEW_DIR)
    if mirrored is None:
        return config.REVIEW_DIR
    if not config.resolves_inside(mirrored, config.REVIEW_DIR):
        raise config.OutsideContentDir(
            f"{mirrored} resolves to {mirrored.resolve()}, outside "
            f"{config.REVIEW_DIR.resolve()}. A draft's own path is never a reason to "
            "write outside the content directory -- remove the symlink, or review a "
            "draft from a topic directory that isn't one."
        )
    return mirrored


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
    needs pandoc/pdflatex on PATH, so a missing binary is reported and
    skipped rather than failing the whole run, matching how every other
    stage in this project treats an absent optional tool.
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

    for fmt in remaining:
        try:
            written[fmt] = render_output.render(
                str(md_path), fmt, output_dir=md_path.parent
            )
        except render_output.MissingBinary as exc:
            print(f"  WARNING: skipped {fmt} -- {exc}", file=sys.stderr)
        except render_output.OutsideContentDir as exc:
            # A layout fault rather than this report's fault: content/review
            # resolves out of the content directory, so render_output has
            # nowhere it is willing to write. The md report above is already
            # written and unaffected, so degrade the same way as the two
            # causes above rather than taking the whole run out, which is
            # also how render_output.py's own CLI reports it.
            print(f"  WARNING: skipped {fmt} -- {exc}", file=sys.stderr)
        except subprocess.CalledProcessError as exc:
            # A quoted excerpt can carry characters straight from the
            # source PDF (e.g. circled digits) that pdflatex's default
            # fonts can't set -- a real rendering failure, not a bug in
            # this report. render_output.py's own CLI already treats this
            # as warn-and-continue rather than a crash; do the same here
            # so one unrenderable format doesn't take out the md/tex
            # formats that did succeed.
            print(f"  WARNING: skipped {fmt} -- pandoc failed: {exc.stderr or exc}",
                  file=sys.stderr)
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
