"""The quotation report's two printed forms -- stdout, and the Markdown
that `--write` files under `content/review/` -- and its JSON payload,
with the `finding_id` both the payload and `quotation.findings()` key on.

Absent findings lead: they answer the reader's one question. Confirmed
and unverifiable counts still print, since "nineteen checked, all clean"
and "nineteen not checked" differ; the `- Universe:` line says whether
there was a dossier and a quote to check at all (#838).
"""

import hashlib

from chitragupta import review

_NOT_A_VERDICT = (
    "A span reported absent is evidence for a human judgement, never proof "
    "of a fabrication: it may equally be a quotation this parse of the "
    "source cannot represent."
)


def _tally(report) -> list[str]:
    return [
        f"- Quotes checked: {len(report.checked)}",
        f"- Confirmed in the cited source: {len(report.of('found'))}",
        f"- Absent from the cited source: {len(report.of('absent'))}",
        f"- Not checkable from this parse: {len(report.of('unverifiable'))}",
    ]


def which(index: int, of: int) -> str:
    """The ` (quote N of M)` suffix for a block with several quotes, so two
    quotes from one source never print as one line (#1174)."""
    return f" (quote {index} of {of})" if of > 1 else ""


def _key(checked) -> str:
    return f"`{checked.citekey}`{which(checked.index, checked.of)}"


def _where(checked) -> str:
    """The page or pages a confirmed span sits on, and how it matched."""
    pages = ", ".join(f"p.{page}" for page in checked.pages) or "page unknown"
    return f"{pages} ({checked.tier})"


def _near(checked) -> str:
    if checked.near_miss_page is None:
        return "its words appear on no page of this source"
    return (
        f"its distinctive words concentrate on p.{checked.near_miss_page} "
        f"({checked.near_miss_score:.0%})"
    )


def _finding_lines(report) -> list[str]:
    out = []
    for checked in sorted(report.of("absent"), key=lambda c: (c.near_miss_score, c.citekey)):
        out += [
            f"### {_key(checked)}",
            "",
            f"> {checked.quote}",
            "",
            f"Not found verbatim; {_near(checked)}.",
            "",
        ]
    return out


def _confirmed_lines(report) -> list[str]:
    return [f"- {_key(c)} -- {_where(c)}" for c in report.of("found")]


def _skipped_lines(report) -> list[str]:
    return [f"- {_key(c)} -- {c.reason}" for c in report.of("unverifiable")]


_EMPTY = {
    "no-dossier": [
        "No dossier for this draft, so there is nothing to check.",
        "",
        "A draft outside `content/drafts/`, or one no genre skill wrote a "
        "dossier for, has no `quote:` to read. It is not a clean bill of health.",
    ],
    "no-quotes": [
        "No `quote:` in this draft's dossier, so there is nothing to check.",
        "",
        "That is the expected answer for a dossier written before A2's "
        "`claim:`/`quote:` contract, and for any genre that captures no "
        "deliberate quotation. It is not a clean bill of health.",
    ],
}


def _clean(report) -> list[str]:
    """The no-absent-span paragraph, which must not claim an unchecked
    quote was found."""
    skipped = len(report.of("unverifiable"))
    if not skipped:
        return ["Every checked quote was found in its cited source."]
    return [
        f"None was absent; {len(report.of('found'))} found, "
        f"{skipped} could not be checked from this parse."
    ]


def _body(report, found) -> list[str]:
    """Everything below the header, shared by both printed forms. The
    universe line leads, so `grep '^- Universe:'` tells #838's three
    zero-findings cases apart."""
    universe = f"- Universe: `{report.universe}`"
    if report.universe in _EMPTY:
        return [universe, ""] + _EMPTY[report.universe]
    out = [universe] + _tally(report) + ["", _NOT_A_VERDICT, ""]
    if found:
        out += ["## Absent from the source they cite", ""] + _finding_lines(report)
    else:
        out += ["## No absent span", ""] + _clean(report) + [""]
    for title, lines in (
        ("Confirmed", _confirmed_lines(report)),
        ("Not checkable from this parse", _skipped_lines(report)),
    ):
        if lines:
            out += [f"## {title}", ""] + lines + [""]
    return out


def format_report(report, found) -> str:
    return "\n".join([f"Quotation integrity: {report.draft}", ""] + _body(report, found)).rstrip()


def render_markdown(report, command: str, found) -> str:
    header = review.header(report.draft, "quotation", command)
    return "\n".join(header + _body(report, found)) + "\n"


def finding_id(citekey: str, quote: str) -> str:
    """A finding's name, stable across runs and position-free.

    Keyed on (citekey, quote), the pair whose truth is in question: any
    quote edit, a typo fix included, is a new unchecked assertion, and
    keying on the citekey alone would let a repaired quote read as resolved
    (R2).
    """
    return hashlib.sha256(f"{citekey}\n{quote}".encode()).hexdigest()[:12]


def quotation_payload(report, command: str, found: list[dict]) -> dict:
    """The same verdicts the report prints, as data. Every checked quote
    appears, with its tier, and `universe` separates "no dossier", "no
    quote" and "checked" when all have zero findings (#838).
    """
    payload = review.envelope(report.draft, "quotation", command)
    payload.update(
        {
            "universe": report.universe,
            "quotes_total": len(report.checked),
            "found": len(report.of("found")),
            "absent": len(report.of("absent")),
            "unverifiable": len(report.of("unverifiable")),
            "quotes": [
                {
                    "id": finding_id(c.citekey, c.quote),
                    "citekey": c.citekey,
                    "verdict": c.verdict,
                    "tier": c.tier,
                    "pages": c.pages,
                    "reason": c.reason,
                    "index": c.index,
                    "of": c.of,
                }
                for c in report.checked
            ],
            "findings": found,
        }
    )
    return payload
