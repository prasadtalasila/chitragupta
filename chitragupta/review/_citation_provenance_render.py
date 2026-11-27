"""How a citation-provenance report reads and publishes: the Markdown
document, and the JSON payload the same findings serialise to.

Takes the report as an argument from `citation_provenance.py` (#441),
leaving `Finding` unannotated rather than importing it, so the dependency
stays one-way. `_band` lives here so both modules share one copy of the
three-way split through the import they already have.
"""

import hashlib
import shlex

from chitragupta import config, review
from chitragupta.passages import Passage


def _band(score: float) -> str:
    if score < config.PROVENANCE_WEAK_SCORE:
        return "no support found"
    if score < config.PROVENANCE_GOOD_SCORE:
        return "weak"
    return "supported"


def render_markdown(report) -> str:
    weak = config.PROVENANCE_WEAK_SCORE
    good = config.PROVENANCE_GOOD_SCORE
    lines = review.header(
        report.draft,
        "provenance",
        # shlex.join, so a draft path with a space reproduces as one argument.
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


def _summary_lines(report) -> list[str]:
    """The Summary band counts, plus unreadable sources if any."""
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
        lines += [
            "",
            "Findings for these show a score of 0 because there was "
            "nothing to compare against, not because the claim is "
            "unsupported.",
            "",
        ]
    return lines


def _finding_lines(finding) -> list[str]:
    lines = [
        f"#### Line {finding.line} -- `[@{finding.citekey}]` ({finding.score:.0%} match)",
        "",
        f"> {finding.claim}" if finding.claim else "> (no sentence text)",
        "",
    ]
    if finding.note:
        lines += [f"*Source unavailable: {finding.note}*", ""]
    elif finding.passage is None:
        lines += ["*No passage in the source matched any distinctive word from this sentence.*", ""]
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
    """A finding's name, stable across runs. Position-free, as
    `verbatim_check.finding_id`, so an edit above does not rename every
    later finding. An identical citekey/claim pair sharing an id is correct.
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


# Fields spelled out rather than `__dict__`, so an internal Finding field
# never silently joins the published contract (see
# `verbatim_check._PAYLOAD_FIELDS`).
def published(finding) -> dict:
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


def provenance_payload(report, command: str) -> dict:
    """The same findings `render_markdown` prints, as data: the envelope
    plus one object per finding, worst-first. A serialisation, never a
    second computation.
    """
    payload = review.envelope(report.draft, "provenance", command)
    payload.update(
        {
            "unreadable": report.unreadable,
            "findings": [published(finding) for finding in report.findings],
        }
    )
    return payload
