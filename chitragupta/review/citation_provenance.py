"""Citation provenance report: for each citation in a draft, what in the
cited source supports it, and where.

`citation_gate` answers "is this citekey real?" -- exactly, as a hard
gate. This answers the question that comes next and can't be answered
exactly: *does the cited paper actually say this?* A claim that drifted
away from its source during drafting passes the gate cleanly, because
the citekey is real; only reading the source catches it.

One of the five commands in the **review layer**, beside
citation_coverage.py, verbatim_check.py and synthesis.py -- run by hand on
a finished draft, never automatically, never a gate, and never holding
the write lock. chitragupta/review/__init__.py owns what the five have in common: where
the report goes (`content/review/`, mirroring the draft's path) and what
its header looks like.

Not a gate, and for a concrete reason. Matching is lexical, so it cannot separate "the source
doesn't say this" from "the source says it in words I didn't recognise".
A check that blocked on that distinction would train people to work
around it, which is exactly the corrosion citation_gate avoids by only
ever asserting something it can verify exactly.

Passages come from `chitragupta/passages.py`, which owns the sidecar -> pages ->
`pdftotext` ladder and the rule that a source with no reading order
reports a page rather than a quotation. This module scores claims
against whatever that ladder hands back; it no longer decides where the
text comes from.

Stdlib only (sqlite3/re), like citation_gate.py and references.py --
runs with bare `python`, no venv.

Usage:
    python -m chitragupta.review provenance content/drafts/<slug>.md
    python -m chitragupta.review provenance <draft.md> --formats md,tex,pdf
"""

import argparse
import hashlib
import json
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import citation_gate, config, ledger, review, sentences
from chitragupta.passages import Passage, distinctive, source_passages
from chitragupta.review import _blocks


@dataclass
class Finding:
    line: int
    citekey: str
    claim: str
    score: float
    passage: Passage | None = None
    note: str | None = None


@dataclass
class Report:
    draft: Path
    findings: list[Finding] = field(default_factory=list)
    unreadable: dict[str, str] = field(default_factory=dict)


def claims(draft_text: str) -> list[tuple[int, str, str]]:
    """(line number, citekey, the text carrying it) for every citation.

    That text is whatever unit actually makes a claim where the citation
    sits: the citing **sentence** in prose, the citing **row** in a table,
    the citing **item** in a list, the **heading** itself when the
    citation is in one. It is never the raw line the citekey sits on, and
    never a whole paragraph.

    Both of those were tried. Reading the *line* fails because every draft
    this project produces is hard-wrapped, so a sentence spans three or
    four lines and the citation lands on whichever one happens to hold it
    -- yielding fragments like "." or ", or equivalently as combinations
    of", which score against nothing. Reading the whole *paragraph* fails
    the other way: a paragraph citing three papers scores identically
    against all three, telling a reviewer nothing about which citation is
    the weak one.

    So the unit is the block (`_blocks.spans`), then the sentence within it
    (`_sentence_around`). That matters because a table or a list is one
    blank-line paragraph containing no sentence boundary at all: reading
    it whole quoted the entire table back as the claim, once per citekey
    in it, and scored every row against the whole table's vocabulary --
    the same identical-claims failure one level up. Blocks are recognised
    in Markdown and in LaTeX, since every genre skill exports `.tex` and
    `.pdf` beside the `.md`. Ordinary prose is unaffected: it is one
    block, read exactly as before.
    """
    lines = draft_text.splitlines()
    spans = _blocks.spans(lines)
    out = []
    for line_no, citekey in citation_gate.extract_citekeys(draft_text):
        block = next(
            (text for start, end, text in spans if start <= line_no <= end),
            lines[line_no - 1] if 0 < line_no <= len(lines) else "",
        )
        out.append((line_no, citekey, _sentence_around(block, citekey)))
    return out


_CITE_MARKUP = re.compile(r"\[@[^\]]+\]|\\cite[tp]?\{[^}]*\}")


def _sentence_around(text: str, citekey: str) -> str:
    """The sentence within `text` containing `citekey`, citation markup
    stripped so the markers themselves don't score as content.

    The split itself is `chitragupta/sentences.py`'s, shared with tier 3 of the
    overlap scan (`chitragupta/overlap_embed.py`) -- see that module on why the
    two aids must not each keep their own idea of where a sentence ends.
    """
    for part in sentences.split(text):
        if citekey in part:
            return _tidy(part)
    return _tidy(text)


def _tidy(text: str) -> str:
    """Drop citation markup and close the gap it leaves behind.

    Removing `[@key]` from "processes [@key], or equivalently" otherwise
    leaves "processes , or equivalently" -- a space before the comma and
    a double space where the marker was. Small, but this text is quoted
    back to a reviewer, and the artefacts read as sloppiness in the
    *draft* rather than in this tool.
    """
    stripped = _CITE_MARKUP.sub("", text)
    # `\s++` (possessive, 3.11+): the backtracking `\s+` re-tries every
    # shorter run of a long whitespace stretch before giving up at each
    # scan position, which is quadratic on whitespace-heavy input (Sonar
    # S8786). Possessive changes no match -- whitespace then punctuation
    # is found identically -- only the wasted re-tries.
    stripped = re.sub(r"\s++([.,;:!?)])", r"\1", stripped)
    stripped = re.sub(r"\(\s+", "(", stripped)
    return re.sub(r"\s{2,}", " ", stripped).strip(" ,;:")


def score_claim(claim: str, passages: list[Passage]) -> tuple[float, Passage | None]:
    """Best lexical-overlap score over `passages`, and the passage that
    achieved it.

    Overlap rather than verbatim n-grams: a correct paraphrase keeps most
    of its content words while changing order and function words, so it
    scores well here and scores *zero* under the >=8-word exact runs that
    chitragupta/review/verbatim_check.py's `overlap` mode uses. That mode is looking
    for borrowed wording; this one is looking for support, and paraphrase
    is the normal case rather than the exception.
    """
    wanted = distinctive(claim)
    if not wanted or not passages:
        return 0.0, None
    best_score, best = 0.0, None
    for passage in passages:
        hits = len(wanted & passage.words)
        score = hits / len(wanted)
        if score > best_score:
            best_score, best = score, passage
    return best_score, best


def build_report(draft_path: Path) -> Report:
    text = draft_path.read_text(encoding="utf-8")
    # The path, not `.name`. It was the bare filename while every report
    # landed flat in one directory and the title was decoration; now that
    # reports mirror the draft's path, two drafts named `survey.md` in
    # different topics would produce headers that read identically -- the
    # exact confusion the mirroring exists to prevent, reintroduced inside
    # the file. It also makes the recorded command re-runnable, which
    # `survey.md` alone is not.
    report = Report(draft=Path(draft_path))
    with ledger.connection() as con:
        cache: dict[str, list[Passage]] = {}
        for line_no, citekey, claim in claims(text):
            if citekey not in cache:
                passages, reason = source_passages(con, citekey)
                cache[citekey] = passages
                if reason:
                    report.unreadable[citekey] = reason
            score, passage = score_claim(claim, cache[citekey])
            note = report.unreadable.get(citekey)
            report.findings.append(
                Finding(line=line_no, citekey=citekey, claim=claim,
                        score=score, passage=passage, note=note)
            )
    # Worst first: the report should open on what deserves attention,
    # not make a reviewer read forty entries to find three.
    report.findings.sort(key=lambda f: (f.score, f.line))
    return report


def _band(score: float) -> str:
    if score < config.PROVENANCE_WEAK_SCORE:
        return "no support found"
    if score < config.PROVENANCE_GOOD_SCORE:
        return "weak"
    return "supported"


def render_markdown(report: Report) -> str:
    weak = config.PROVENANCE_WEAK_SCORE
    good = config.PROVENANCE_GOOD_SCORE
    lines = review.header(
        report.draft, "provenance",
        # shlex.join, not an f-string: a draft path with a space in it
        # would otherwise be recorded as two arguments, so the header
        # would name an invocation that doesn't reproduce the report.
        # The other two review aids already quote theirs.
        shlex.join(["python", "-m", "chitragupta.review", "provenance", str(report.draft)]),
    ) + [
        "## How to read this",
        "",
        "Each entry pairs a citing sentence from the draft with the passage of",
        "the cited paper that best matches it, scored by how many of the",
        "sentence's distinctive words appear there. Entries are ordered",
        "**worst match first**, so the ones worth checking come first.",
        "",
        "This is a **review aid, not a gate**. A low score means *go look* --",
        "it does not mean the citation is wrong. A claim correctly paraphrased",
        "into different vocabulary scores low, and a claim that happens to",
        "share wording with its source scores high while misrepresenting it.",
        "The report tells you where to spend attention; it does not adjudicate.",
        "",
        f"Bands: **no support found** below {weak:.0%}, **weak** below "
        f"{good:.0%}, **supported** at or above {good:.0%}.",
        "",
        "**Scores are comparable within a source kind, not across them.** A",
        "quoted paragraph is a much smaller haystack than a whole page, so",
        "the same quality of support scores lower against a paragraph than",
        "against a page. On one real draft the identical citations banded as",
        "8 weak / 5 supported page-level and 12 weak / 1 supported once",
        "paragraphs were available -- the matches did not get worse, the",
        "denominator got smaller. Compare entries with each other, and treat",
        "the band as a rough reading order rather than a measurement.",
        "",
    ]

    if not report.findings:
        lines += ["No citations found in this draft.", ""]
        return "\n".join(lines)

    lines += _summary_lines(report)

    lines += ["## Findings", ""]
    current = None
    for finding in report.findings:
        band = _band(finding.score)
        if band != current:
            lines += [f"### {band.capitalize()}", ""]
            current = band
        lines += _finding_lines(finding)
    return "\n".join(lines)


def _summary_lines(report: Report) -> list[str]:
    """The Summary band counts, and the unreadable-sources section when
    there is one."""
    counts: dict[str, int] = {}
    for finding in report.findings:
        counts[_band(finding.score)] = counts.get(_band(finding.score), 0) + 1
    lines = ["## Summary", ""]
    for band in ("no support found", "weak", "supported"):
        if counts.get(band):
            lines.append(f"- {counts[band]} {band}")
    lines.append("")

    if report.unreadable:
        lines += ["## Sources that could not be read", ""]
        for citekey, reason in sorted(report.unreadable.items()):
            lines.append(f"- `{citekey}`: {reason}")
        lines += ["", "Findings for these show a score of 0 because there was "
                      "nothing to compare against, not because the claim is "
                      "unsupported.", ""]
    return lines


def _finding_lines(finding: Finding) -> list[str]:
    """One finding's body: the claim, then the best-match passage or the
    stated reason there is none."""
    lines = [
        f"#### Line {finding.line} -- `[@{finding.citekey}]` "
        f"({finding.score:.0%} match)",
        "",
        f"> {finding.claim}" if finding.claim else "> (no sentence text)",
        "",
    ]
    if finding.note:
        lines += [f"*Source unavailable: {finding.note}*", ""]
    elif finding.passage is None:
        lines += ["*No passage in the source matched any distinctive word "
                  "from this sentence.*", ""]
    elif finding.passage.quotable:
        page = f", p.{finding.passage.page}" if finding.passage.page else ""
        lines += [f"Best match in the source{page}:", ""]
        lines += [f"> {finding.passage.text}", ""]
    else:
        page = finding.passage.page
        lines += [
            f"Best match is on **page {page}** of the source. The text for "
            "this citekey has no reading order (see chitragupta/passages.py), "
            "so the page is reported without quoting from it.",
            "",
        ]
    return lines


def finding_id(citekey: str, claim: str) -> str:
    """A finding's name, stable across runs. Position-free (no `line`),
    the same convention `verbatim_check.finding_id` uses and for the same
    reason: an identity built on `line` would rename every remaining
    finding the moment an edit above it shifted line numbers, and nothing
    could then decide whether a given finding had survived a revision.

    Two identical citekey/claim pairs therefore share an id -- a draft
    citing the same source with the same sentence twice is the one case
    that collides, and that is the correct read rather than a bug.
    """
    digest = hashlib.sha256(f"{citekey}\x00{claim}".encode())
    return digest.hexdigest()[:12]


def _passage_payload(passage: Passage | None) -> dict | None:
    if passage is None:
        return None
    return {
        "page": passage.page,
        "quotable": passage.quotable,
        "text": passage.text if passage.quotable else None,
    }


# The finding fields the JSON payload publishes, spelled out rather than
# serialising the Finding dataclass's own `__dict__` -- see
# `verbatim_check._PAYLOAD_FIELDS` for why: `Finding` is this module's
# working representation, and a field added there for internal use should
# not silently become part of a published contract.
def published(finding: Finding) -> dict:
    return {
        "id": finding_id(finding.citekey, finding.claim),
        "line": finding.line,
        "citekey": finding.citekey,
        "claim": finding.claim,
        "score": finding.score,
        "band": _band(finding.score),
        "passage": _passage_payload(finding.passage),
        "note": finding.note,
    }


def provenance_payload(report: Report, command: str) -> dict:
    """The same findings `render_markdown` prints, as data: `review.envelope`'s
    provenance plus one object per finding, worst-first like the report.

    An additional serialisation of `report.findings`, never a second
    computation, so the printed and published forms cannot disagree about
    what was found.
    """
    payload = review.envelope(report.draft, "provenance", command)
    payload.update({
        "unreadable": report.unreadable,
        "findings": [published(finding) for finding in report.findings],
    })
    return payload


def _command(draft_path: Path, as_json: bool) -> str:
    """The invocation recorded in the JSON payload's envelope.

    `--formats` is left out, matching `citation_coverage._command`'s own
    exclusion: it selects renders *of* the report and changes nothing in
    the payload or the Markdown it describes.
    """
    parts = ["python", "-m", "chitragupta.review", "provenance", str(draft_path)]
    if as_json:
        parts += ["--json"]
    return shlex.join(parts)


def write_report(draft_path: Path, formats: list[str]) -> dict[str, Path]:
    """Writes the report and returns {format: path} for what succeeded.

    The report lands in `content/review/`, mirroring the draft's own
    place under `content/drafts/`, with its `.tex`/`.pdf` renders beside
    it -- `chitragupta/review/__init__.py` owns both the path and the degrade-on-missing-
    binary behaviour, shared with the other two review aids.
    """
    return review.write(
        draft_path, "provenance", render_markdown(build_report(draft_path)), formats
    )


def build_parser(parser=None):
    """This aid's flags.

    `parser` is passed by chitragupta/review/__main__.py, which has already
    created the `provenance` subparser and needs the flags hung off
    *that* -- so they are declared once, here, and the entry point never
    restates them.
    """
    if parser is None:
        parser = argparse.ArgumentParser(
            description="Report what in each cited source supports the claim citing it.",
        )
    parser.add_argument("draft", help="Markdown draft to check")
    parser.add_argument(
        "--formats", default="md,tex,pdf",
        help="Additional formats to render beside the Markdown report "
             "(default: md,tex,pdf). The .md is always written -- it is the "
             "report; tex/pdf are renders of it, and need pandoc/pdflatex "
             "on PATH.",
    )
    parser.add_argument("--json", action="store_true",
                        help="Print the findings as JSON instead of just the "
                             "written-files summary. The .json sibling is filed "
                             "beside the Markdown report either way.")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments.

    Split from main() so chitragupta/review/__main__.py can hand over the args it
    parsed with this module's own build_parser(), rather than re-slicing
    argv and parsing it twice.

    The `.json` sibling is filed unconditionally, matching the `.md`'s own
    always-write policy (this aid, unlike the other two, was never
    print-only) -- `--json` only decides what prints to stdout instead of
    the written-files summary. Under `--json` that summary moves to
    stderr, so `provenance --json > findings.json` stays a valid JSON
    file, the same discipline `verbatim scan --json` follows.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    report = build_report(draft_path)
    written = review.write(draft_path, "provenance", render_markdown(report), formats)
    payload = provenance_payload(report, _command(draft_path, args.json))
    written["json"] = review.write_json(draft_path, "provenance", payload)

    if args.json:
        print(json.dumps(payload, indent=2))
        review.print_written(written, stream=sys.stderr)
    else:
        review.print_written(written)
    return 0
