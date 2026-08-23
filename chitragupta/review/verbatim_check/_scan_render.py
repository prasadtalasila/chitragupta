"""The Markdown report `scan --write` files: standing preamble prose plus
the findings, grouped into severity buckets.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

from pathlib import Path

from chitragupta import config, review
from chitragupta.review.verbatim_check._scan import (
    BUCKET_ORDER,
    _bucket,
    _bucket_title,
    _flags,
    _matched_note,
    _not_run_lines,
    _page_range,
    _tier_note,
)


def _how_to_read(not_run: list[dict]) -> list[str]:
    """The report's standing preamble: what a finding is, what the two
    flags mean, what each tier can and cannot see.

    Extracted out of `render_scan_markdown` (which was already over
    CODE-STANDARDS.md's C1 limit at 27 statements before tier 3 added to
    it) so the assembly of a report and the prose inside it are not the
    same function. It takes `not_run` because the last paragraph is the
    one thing here that is not standing text: what a clean scan does
    *not* rule out depends on which tiers actually ran.
    """
    return [
        "## How to read this",
        "",
        "Every run of at least `--min-run` words this draft shares with **any**",
        "parsed source in the corpus, cited or not. Sharing wording is not by",
        "itself misconduct -- a defined term, a standard's name and a correctly",
        "quoted sentence all show up here -- so each finding is a place to look,",
        "not a charge.",
        "",
        "Two flags narrow the reading:",
        "",
        "- **UNCITED SOURCE** -- the paragraph the run sits in does not cite the",
        "  source it matched. That is the finding `overlap` structurally cannot",
        "  make, and the one most worth reading first.",
        "- **quoted** -- the run touches quote delimiters, so it is most likely",
        "  a deliberate quotation. A run is usually wider than the quotation",
        "  inside it -- it can open in the draft's own framing prose -- so this",
        "  reads as overlap, not containment.",
        "",
        "Each finding names its `tier`: **exact** is a verbatim run; **skip-gram**",
        "is a tolerant stemmed-subsequence match that also catches a passage",
        "with a handful of words substituted. A skip-gram finding's word count",
        "is `matched words / span`: how many words the tier actually matched,",
        "out of the raw width of text those matches span -- the two can differ",
        "a lot, since a skip-gram window can stretch across stopwords and",
        "opposite-family words that were not themselves matched.",
        "",
        "**embedding** is the third tier: a sentence-level alignment between a",
        "section of this draft and the sources its dossier records that section",
        "as written from. It matches meaning rather than wording, so it is the",
        "only tier that can see a genuine restatement -- and the only one whose",
        "findings are not reproducible from the draft and the corpus alone,",
        "since the vectors change with `[enrich].embedding_model`. Its `score`",
        "is that alignment's strength, not a probability and not comparable to",
        "anything the other two report; a passage a deterministic tier already",
        "flagged is left to that tier rather than reported twice.",
        "",
        "Findings below are grouped most-damning-first: long runs, then short",
        "ones, then quoted runs -- but a quoted run only drops into the last",
        "group when it also cites the source it matched. A quoted run from an",
        "uncited source is still grouped by length (on matched words, not raw",
        "span), not buried under `quoted`.",
        "",
        "The allowlist bullet above names a per-host, gitignored file",
        "(`content/verbatim_allowlist.toml`, see docs/PLAGIARISM.md) of",
        "boilerplate this host's owner has decided never to flag -- a run is",
        "only dropped when what's left after discounting the allowlisted text",
        "would no longer clear `--min-run` on its own, so a real lift that",
        "merely contains a defined term still shows up below.",
        "",
    ] + _completeness_paragraph(not_run)


def _completeness_paragraph(not_run: list[dict]) -> list[str]:
    """What this particular scan does not rule out.

    Two different sentences, because "the paraphrase tier ran and found
    nothing here" and "the paraphrase tier never ran" are two different
    states of knowledge and only one of them is about the draft.
    `tests/test_skill_verbatim_scan_step.py` holds every skill's run
    of this scan to the same standard -- say what it cannot see -- and
    this is where the report itself keeps that promise.
    """
    if not_run:
        return (
            [
                "**A clean run is not a clean bill of health**, and this run was",
                "not complete. Two deterministic tiers checked this draft -- exact",
                "runs, and skip-gram matches tolerant of a substituted word -- and",
                "a genuine restatement, reworded well past a word swap, is",
                "invisible to both by construction. The tier that can see one did",
                "not run here:",
                "",
            ]
            + [f"- {line}" for line in _not_run_lines(not_run)]
            + [
                "",
                "So this report is silently incomplete rather than wrong. See",
                "docs/PLAGIARISM.md.",
                "",
            ]
        )
    return [
        "**A clean run is not a clean bill of health.** This draft has been",
        "checked against all three tiers, but they do not cover the same",
        "ground: the two deterministic ones see wording, and the embedding",
        "tier sees meaning only within each section's own recorded sources.",
        "Reuse from a source a section's dossier does not record is outside",
        "what any of the three can find by restatement alone. See",
        "docs/PLAGIARISM.md.",
        "",
    ]


def render_scan_markdown(
    draft: str | Path,
    findings: list[dict],
    min_run: int,
    limit: int | None,
    command: str,
    suppressed: int = 0,
    not_run: list[dict] | None = None,
) -> str:
    """The same findings as a Markdown report, for `--write`.

    Kept beside `format_scan` rather than replacing it: stdout is read in
    a terminal mid-review and wants no syntax, while a file kept for
    months is read next to the same draft's provenance and coverage
    reports and should look like them.

    `command` is built once, by `scan_command`, and handed to both this
    function and `scan_payload` -- so the Markdown header and the JSON
    envelope cannot disagree about what produced them.
    """
    allowlist_path = config.VERBATIM_ALLOWLIST_PATH
    if not allowlist_path.exists():
        allowlist_line = f"- Allowlist: none configured (`{allowlist_path}` not found)"
    else:
        allowlist_line = f"- Allowlist: `{allowlist_path}` ({suppressed} finding(s) suppressed)"

    lines = review.header(Path(draft), "verbatim", command)
    lines = lines[:-1] + [allowlist_line, ""]
    lines += _how_to_read(not_run or []) + ["## Findings", ""]

    if not findings:
        lines += [
            f"No verbatim run of {min_run} words or more was found anywhere in the draft.",
            "",
        ]
        return "\n".join(lines)

    lines += [f"{len(findings)} run(s), grouped most-damning-first.", ""]
    if limit is not None:
        lines += [
            f"This report was capped at `--limit {limit}` finding(s), taken from",
            "the longest-first list *before* grouping into the buckets below --",
            "a bucket may look emptier here than an uncapped scan would show, or",
            "be absent entirely, because its findings were cut before grouping.",
            "",
        ]

    return "\n".join(lines + _bucketed_lines(findings))


def _bucketed_lines(findings: list[dict]) -> list[str]:
    """The findings themselves, grouped into `BUCKET_ORDER`'s severity
    sections.

    Extracted out of `render_scan_markdown` for the reason
    `_exact_findings_from_groups` was extracted out of its own caller:
    this double loop's nesting was counting against a function that is
    otherwise a straight-line assembly of a document, and that function
    was over CODE-STANDARDS.md's C1 limit before this tier added to it.
    """
    buckets = {key: [] for key in BUCKET_ORDER}
    for f in findings:
        buckets[_bucket(f)].append(f)

    lines = []
    for key in BUCKET_ORDER:
        bucket_findings = buckets[key]
        if not bucket_findings:
            continue
        lines += [f"### {_bucket_title(key)}", ""]
        for f in bucket_findings:
            flags = _flags(f)
            flag_text = f" -- **{', '.join(flags)}**" if flags else ""
            lines += [
                f"#### {f['span_words']} words{_matched_note(f)} -- `{f['citekey']}` "
                f"{_page_range(f)} ({_tier_note(f)}){flag_text}",
                "",
                f"> {f['fragment']}",
                "",
                f"In context: {f['context']}...",
                "",
            ]
    return lines
