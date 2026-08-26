"""The quotation report's two printed forms: stdout, and the Markdown
that `--write` files under `content/review/`.

Split from `chitragupta/review/quotation.py` for the reason
`_uncited_render.py` was split from `uncited_prose.py` -- the aid stays
under docs/CODE-STANDARDS.md's C2 cap, and the layout of a report is a
different thing to change from what the report decides.

**The absent findings lead.** A reader opening this has one question --
which of these quotations is not in the paper it names -- and the
confirmed spans are the answer to a different one. The confirmed and
unverifiable counts still print, because "nineteen checked, all clean"
and "nineteen not checked at all" are different reports and a bare
"no findings" cannot tell them apart.

Stdlib-only.
"""

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


def _body(report, found) -> list[str]:
    """Everything below the header, shared by both printed forms."""
    if not report.checked:
        return [
            "No `quote:` in this draft's dossier, so there is nothing to check.",
            "",
            "That is the expected answer for a dossier written before A2's "
            "`claim:`/`quote:` contract, and for any genre that captures no "
            "deliberate quotation. It is not a clean bill of health.",
        ]
    out = _tally(report) + ["", _NOT_A_VERDICT, ""]
    if found:
        out += ["## Absent from the source they cite", ""] + _finding_lines(report)
    else:
        out += ["## No absent span", "", "Every checked quote was found in its cited source.", ""]
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
