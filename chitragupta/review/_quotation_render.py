"""The quotation report's two printed forms -- stdout, and the Markdown
that `--write` files under `content/review/` -- and its JSON payload,
with the `finding_id` both the payload and `quotation.findings()` key on.

Split from `chitragupta/review/quotation.py` for the reason
`_uncited_render.py` was split from `uncited_prose.py` -- the aid stays
under docs/CODE-STANDARDS.md's C2 cap, and the layout of a report is a
different thing to change from what the report decides.

**The absent findings lead.** A reader opening this has one question --
which of these quotations is not in the paper it names -- and the
confirmed spans are the answer to a different one. The confirmed and
unverifiable counts still print, because "nineteen checked, all clean"
and "nineteen not checked at all" are different reports and a bare
"no findings" cannot tell them apart. The `- Universe:` line above them
is the other half (#838): it says whether there was a dossier, and a
quote in it, to check at all.

Stdlib-only.
"""

import hashlib

from chitragupta import review

_NOT_A_VERDICT = (
    "A span reported absent is evidence for a human judgement, never proof "
    "of a fabrication: it may equally be a quotation this parse of the "
    "source cannot represent."
)


def _tally(report) -> list[str]:
    """The three counts, always all three."""
    return [
        f"- Quotes checked: {len(report.checked)}",
        f"- Confirmed in the cited source: {len(report.of('found'))}",
        f"- Absent from the cited source: {len(report.of('absent'))}",
        f"- Not checkable from this parse: {len(report.of('unverifiable'))}",
    ]


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
            f"### `{checked.citekey}`",
            "",
            f"> {checked.quote}",
            "",
            f"Not found verbatim; {_near(checked)}.",
            "",
        ]
    return out


def _confirmed_lines(report) -> list[str]:
    return [f"- `{c.citekey}` -- {_where(c)}" for c in report.of("found")]


def _skipped_lines(report) -> list[str]:
    return [f"- `{c.citekey}` -- {c.reason}" for c in report.of("unverifiable")]


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
    """The no-absent-span paragraph, which must not claim a quote the
    parse could not check was found."""
    skipped = len(report.of("unverifiable"))
    if not skipped:
        return ["Every checked quote was found in its cited source."]
    return [
        f"None was absent; {len(report.of('found'))} found, "
        f"{skipped} could not be checked from this parse."
    ]


def _body(report, found) -> list[str]:
    """Everything below the header, shared by both printed forms. The
    universe line leads, so `grep '^- Universe:'` says which of #838's
    three zero-findings situations a report is."""
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
    """What a bare invocation prints."""
    return "\n".join([f"Quotation integrity: {report.draft}", ""] + _body(report, found)).rstrip()


def render_markdown(report, command: str, found) -> str:
    """The written report: the layer's standard header, then the body."""
    header = review.header(report.draft, "quotation", command)
    return "\n".join(header + _body(report, found)) + "\n"


def finding_id(citekey: str, quote: str) -> str:
    """A finding's name, stable across runs and position-free -- the same
    convention the other six aids' `finding_id` use.

    Keyed on the pair whose truth is in question, so both halves hold and
    both are wanted. Editing an unrelated block renames nothing, and
    re-attributing the quote or correcting it to the real span makes the
    finding disappear, which is what "this finding is gone" should mean
    (R2). And *any* edit to the quote text is a new finding by
    construction, a typo fix included: a changed span is a different
    assertion about the source and has not been checked. Keying on the
    citekey alone would let a repaired quote inherit its predecessor's
    identity and read, in a later comparison, as one that was resolved.
    """
    return hashlib.sha256(f"{citekey}\n{quote}".encode()).hexdigest()[:12]


def quotation_payload(report, command: str, found: list[dict]) -> dict:
    """The same verdicts the report prints, as data -- an additional
    serialisation, never a second computation.

    Every checked quote appears, not only the findings: the tier that
    confirmed a span is what tells a reader the check was contiguous
    rather than an ordered alignment around an ellipsis, and a count of
    what was skipped is what separates "seven checked, all clean" from
    "seven not checked at all". `universe` is what separates "no
    dossier", "no quote" and "checked" when all three have zero
    findings (#838).
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
                }
                for c in report.checked
            ],
            "findings": found,
        }
    )
    return payload
