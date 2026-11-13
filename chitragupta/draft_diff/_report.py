"""A change report written out: Markdown for a person, JSON for a reviser.

Neither form carries a timestamp of its own. The only date in a report
is the baseline's, part of its header, so writing the same comparison
twice gives the same bytes and a report diffs cleanly against the last.

The header is the one line `draft diff` also puts on the redline, so it
is built here once.
"""

from dataclasses import asdict

from chitragupta.draft_diff._compare import _LOGGED_KINDS, ChangeReport, FigureChange, SectionChange
from chitragupta.draft_diff._views import VersionView

_SEPARATOR = " · "

# U+2212, so "−1" reads as a count dropped, not a hyphenated word.
_MINUS = "−"


def header(report: ChangeReport) -> str:
    """`Changes since <ref> · <label> · <date> — review copy`, empty parts left out."""
    old = report.old
    since = _SEPARATOR.join(part for part in (old.ref, old.label, old.date) if part)
    return f"Changes since {since} — review copy"


def _words(count: int) -> str:
    return f"{count} word{'' if count == 1 else 's'}"


def _figures_summary(figures: list[FigureChange] | None) -> str:
    if figures is None:
        return "figures unknown"
    counts = {kind: sum(f.kind == kind for f in figures) for kind in ("added", "removed")}
    redrawn = sum(f.kind == "redrawn" for f in figures)
    extra = "".join(f", {n} {kind}" for kind, n in counts.items() if n)
    return f"figures {redrawn} redrawn{extra}"


def _summary(report: ChangeReport) -> str:
    touched = sum(c.kind != "unchanged" for c in report.sections)
    in_new = sum(c.kind != "removed" for c in report.sections)
    parts = (
        f"{_words(report.words_changed)} changed in {touched} of {in_new} sections",
        f"citekeys +{len(report.citekeys_added)} {_MINUS}{len(report.citekeys_dropped)}",
        _figures_summary(report.figures),
    )
    return _SEPARATOR.join(parts)


def _revision_log(report: ChangeReport) -> list[str]:
    lines = [f"- {entry}" for entry in report.log_entries] or ["No entries since the baseline."]
    if report.unmatched_log_sections:
        lines += ["", "Not matched to any heading: " + ", ".join(report.unmatched_log_sections)]
    return lines


# The kind leads each row: a title such as "3. Results" at the start of a
# list item would open a nested numbered list.
def _section_row(change: SectionChange) -> list[str]:
    # A moved section's words are unchanged, so a count of 0 says nothing.
    words = f" ({_words(change.words_changed)})" if change.words_changed else ""
    return [f"- {change.kind}: {change.title}{words}"] + [f"  - ↳ {log}" for log in change.log]


def _sections(report: ChangeReport) -> list[str]:
    rows = [
        line
        for change in report.sections
        if change.kind != "unchanged"
        for line in _section_row(change)
    ]
    unchanged = sum(c.kind == "unchanged" for c in report.sections)
    if unchanged:
        rows += ["", f"{unchanged} unchanged"]
    return rows


def _citekeys(report: ChangeReport) -> list[str]:
    lines = [f"- Added `{key}` in {section}" for key, section in report.citekeys_added]
    lines += [f"- Dropped `{key}`: {status}" for key, status in report.citekeys_dropped]
    return lines or ["No citekeys added or dropped."]


def _figure_row(change: FigureChange) -> str:
    if change.kind == "missing":
        return f"- `{change.name}`: missing in {change.side}"
    forms = f" ({change.forms})" if change.forms else ""
    return f"- `{change.name}`: {change.kind}{forms}"


def _figures(report: ChangeReport) -> list[str]:
    if report.figures is None:
        return ["Baseline figures unknown."]
    return [_figure_row(change) for change in report.figures] or ["No figures changed."]


def to_markdown(report: ChangeReport) -> str:
    """The report as one Markdown document, ending in a single newline."""
    blocks = [[f"# {header(report)}"]]
    if not report.has_changes:
        blocks.append(["No changes."])
    else:
        blocks.append([_summary(report)])
        if report.hand_edits:
            blocks.append(["Includes edits made outside any revision pass."])
        for title, body in (
            ("Revision log", _revision_log(report)),
            ("Sections", _sections(report)),
            ("Citekeys", _citekeys(report)),
            ("Figures", _figures(report)),
        ):
            blocks += [[f"## {title}"], body]
        # `report.unlogged`'s sections themselves, so each row names its kind.
        unlogged = [c for c in report.sections if c.kind in _LOGGED_KINDS and not c.log]
        if unlogged:
            blocks += [["## Needs a log entry"], [f"- {c.kind}: {c.title}" for c in unlogged]]
    return "\n\n".join("\n".join(block) for block in blocks) + "\n"


def _side(view: VersionView) -> dict:
    return {"ref": view.ref, "label": view.label, "date": view.date, "suffix": view.suffix}


def to_json(report: ChangeReport) -> dict:
    """The report as plain JSON-ready values; neither side's text is included."""
    figures = None if report.figures is None else [asdict(f) for f in report.figures]
    return {
        "header": header(report),
        "old": _side(report.old),
        "new": _side(report.new),
        "words_changed": report.words_changed,
        "has_changes": report.has_changes,
        "unlogged": report.unlogged,
        "sections": [asdict(change) for change in report.sections],
        "citekeys_added": [{"key": k, "section": s} for k, s in report.citekeys_added],
        "citekeys_dropped": [{"key": k, "status": s} for k, s in report.citekeys_dropped],
        "figures": figures,
        "log_entries": list(report.log_entries),
        "unmatched_log_sections": list(report.unmatched_log_sections),
        "hand_edits": report.hand_edits,
    }
