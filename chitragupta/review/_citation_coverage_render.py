"""How a citation-coverage report reads: the Markdown document and the
plain-text stdout form.

Takes `CoverageResult` as an argument from `citation_coverage.py` (#441)
and never imports it back, keeping the dependency one-way rather than a
cycle behind a deferred import.
"""

from chitragupta import review


def format_report(draft_path, queries: list[str], result) -> str:
    lines = [f"Citation coverage for {draft_path}", f"Queries: {queries}"]
    if result.corrections:
        lines.append("Spelling corrections:")
        lines += [f"  - {query}: {added}" for query, added in result.corrections.items()]

    if result.coverage_pct is None:
        lines.append("No candidates found for any query -- nothing to compare against.")
    else:
        lines.append(
            f"Coverage: {result.coverage_pct:.0f}% "
            f"({len(result.cited_candidates)}/{len(result.candidates)} retrieved candidates cited)"
        )
        if result.uncited_candidates:
            lines.append("Retrieved but not cited:")
            for key in sorted(result.uncited_candidates):
                lines.append(f"  - {key}: {result.candidates[key]}")

    if result.cited_outside_candidates:
        lines.append("Cited but not surfaced by these queries (not necessarily a problem):")
        for key in sorted(result.cited_outside_candidates):
            lines.append(f"  - {key}")

    return "\n".join(lines)


def render_markdown(draft_path, queries: list[str], k: int, result, command: str) -> str:
    """The same report as `format_report`, as Markdown: stdout wants no
    syntax, while a kept file should look like the other review reports.
    """
    lines = review.header(draft_path, "coverage", command)
    lines += [
        "## How to read this",
        "",
        "Each query below was run through the same retrieval this project's",
        "genre skills use. A candidate it surfaced that the draft never cites",
        "is either a source worth adding or a query that was too broad --",
        "this report does not know which, and does not guess.",
        "",
        "A citekey cited but not surfaced here is **not** a gap: it is almost",
        "always explained by a different query the skill ran. It is listed so",
        "the report cannot be misread as a complete picture of the draft's",
        "sources.",
        "",
        "## Queries",
        "",
    ]
    lines += [f"- `{query}`" for query in queries]
    lines += ["", f"Top {k} results per query.", ""]
    if result.corrections:
        lines += ["## Spelling corrections", ""]
        lines += [f"- `{query}`: {added}" for query, added in result.corrections.items()]
        lines.append("")
    lines += ["## Coverage", ""]

    if result.coverage_pct is None:
        lines += ["No candidates found for any query -- nothing to compare against.", ""]
    else:
        lines += [
            f"**{result.coverage_pct:.0f}%** -- {len(result.cited_candidates)} of "
            f"{len(result.candidates)} retrieved candidates are cited.",
            "",
        ]
        if result.uncited_candidates:
            lines += ["### Retrieved but not cited", ""]
            for key in sorted(result.uncited_candidates):
                lines.append(f"- `{key}` -- {result.candidates[key]}")
            lines.append("")

    if result.cited_outside_candidates:
        lines += [
            "### Cited but not surfaced by these queries",
            "",
            "Not necessarily a problem -- see above.",
            "",
        ]
        for key in sorted(result.cited_outside_candidates):
            lines.append(f"- `{key}`")
        lines.append("")

    return "\n".join(lines)
