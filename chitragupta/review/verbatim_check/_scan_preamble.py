"""The verbatim report's standing preamble: how to read a finding, what
each tier can and cannot see, and what this particular scan does not rule
out.

Split out of `_scan_render.py` when that module crossed
CODE-STANDARDS.md's C2 line limit -- along the seam that module's own
docstring already named, "standing preamble prose plus the findings".
Everything here is text a reader sees before the first finding and none
of it depends on what was found, with the single exception
`_completeness_paragraph` documents: which tiers ran.
"""

from chitragupta.review.verbatim_check._scan_notes import _not_run_lines


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
        "**Where a finding shows two blocks, `Draft:` and `Source:`, the two are",
        "not the same wording** -- had they been, the exact tier would have",
        "caught it and the tier that did report it would have stood aside. Read",
        "them against each other, using the markup:",
        "",
        "- **Bold** on either side -- a word that side has and the other does",
        "  not: substituted, or added by the draft.",
        "- ~~Struck through~~, source side only -- a word the source has that",
        "  the draft dropped.",
        "- Unmarked -- the wording the two actually share. That is the overlap,",
        "  and it is left bare so it is the one thing on the line the eye finds",
        "  without looking.",
        "",
        "The draft side is normalized (lowercased, punctuation dropped) because",
        "that is the stream the tiers compare; the source side is its own text as",
        "parsed. So do not read a difference in capitals or apostrophes as a",
        "finding -- the comparison behind the markup is run on normalized words on",
        "both sides, and marks none of that.",
        "",
        "An **exact** finding shows one unmarked block instead of two: the tier",
        "only fires where the wording is identical, so there is no second side to",
        "show and nothing to mark.",
        "",
        "An **embedding** finding's word count says `aligned`, not `matched`: it",
        "is the width of the aligned sentences, not a count of words the two",
        "sides share. A long `aligned` count with a low `score` is a weak",
        "alignment over a long sentence, not a long lift.",
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

    Three different sentences, because "the paraphrase tier ran and
    found nothing here", "the paraphrase tier never ran", and "the
    paraphrase tier ran but not against everything this draft cites"
    are three different states of knowledge and only one of them is a
    clean bill of health. `tests/test_skill_verbatim_scan_step.py` holds
    every skill's run of this scan to the same standard -- say what it
    cannot see -- and this is where the report itself keeps that
    promise. Entries carry `"partial": True` when the tier ran and
    still contributed findings but skipped part of what it should have
    covered (#499) -- absent, not merely omitted, that key means the
    tier that could see one did not run at all.
    """
    absent = [entry for entry in not_run if not entry.get("partial")]
    partial = [entry for entry in not_run if entry.get("partial")]
    if absent:
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
            + [f"- {line}" for line in _not_run_lines(absent)]
            + [
                "",
                "So this report is silently incomplete rather than wrong. See",
                "docs/PLAGIARISM.md.",
                "",
            ]
        )
    if partial:
        return (
            [
                "**A clean run is not a clean bill of health**, and this run was",
                "not complete. The embedding tier -- the only one that can see a",
                "genuine restatement -- ran and the findings below are real, but it",
                "did not run against everything this draft cites:",
                "",
            ]
            + [f"- {line}" for line in _not_run_lines(partial)]
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
