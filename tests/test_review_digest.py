"""chitragupta/review/verbatim_digest.py and its render/recheck halves:
the eleventh review aid, over a verbatim digest.

A digest is private study text written mostly in the sources' own words
(discussion #991). The aid leads with the unsupported fraction, lists
every sentence that is not verified source text as a `[surfaced]` item
in the agenda's own line format, and under `--baseline` says whether a
repair pass made the fraction fall. Advisory like the other ten: exit 0
whatever it finds, no lock, no draft blocked.
"""

import json
from pathlib import Path

import pytest

from chitragupta import config, ledger, review
from chitragupta.review import __main__ as review_main
from chitragupta.review import _digest_match as match
from chitragupta.review import _digest_recheck as recheck
from chitragupta.review import _digest_render as render
from chitragupta.review import verbatim_digest
from chitragupta.review._digest_runs import Run
from tests.test_review_units import draft_at

KEY = "shao_analysis_2023"
SOURCE = (
    "Layered twins separate the physical entity from its models. "
    "Each layer exposes one interface to the next."
)


@pytest.fixture(autouse=True)
def _a_synced_ledger(isolated_config):
    """An empty, current ledger: the aid reads read-only (#843) and a
    missing one is refused, so every test has to say it synced."""
    ledger.connect().close()


def a_source(citekey: str, *records: tuple[int, str]) -> Path:
    """A rung-2 passage sidecar: reading-ordered text with a page each."""
    path = config.PARSED_DIR / f"{citekey}.passages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([{"text": t, "page": p, "label": "text"} for p, t in records]),
        encoding="utf-8",
    )
    return path


def a_digest(body: str, name: str = "notes.md") -> Path:
    draft = draft_at(name)
    draft.write_text(body, encoding="utf-8")
    return draft


DIGEST = (
    "# Layered twins\n\n"
    "## Layers\n\n"
    f"Layered twins separate the physical entity from its models. [@{KEY}, p. 4]\n"
    "My own bridge sentence about pelicans.\n"
    f"Each layer exposes one interface to the next. [@{KEY}, p. 4]\n"
    "And a closing thought of mine.\n"
)


def a_checked() -> match.Checked:
    checked = match.Checked()
    run = Run(
        5,
        ("Layered twins separate the physical entity from its models.",),
        (KEY,),
        f"[@{KEY}, p. 4]",
        (4, 4),
    )
    checked.spans.append(match.Span(5, (KEY,), run.text, "exact", (4,), (4, 4), None))
    bridge = "My own bridge sentence about pelicans."
    closing = "And a closing thought of mine."
    unsupported = {"support_score": 0.0, "page": None}
    checked.findings.append(match.Finding("unquoted-text", 6, bridge, (KEY,)))
    checked.findings.append(match.Finding("unsupported-text", 6, bridge, (KEY,), unsupported))
    checked.findings.append(match.Finding("unquoted-text", 8, closing, ()))
    checked.findings.append(match.Finding("unsupported-text", 8, closing, (), unsupported))
    checked.words_total = 25
    return checked


class TestItems:
    def test_one_item_per_finding_worst_class_first_then_by_line(self):
        rows = render.items(a_checked(), DIGEST)
        assert [(r["class"], r["line"]) for r in rows] == [
            ("unsupported-text", 6),
            ("unsupported-text", 8),
            ("unquoted-text", 6),
            ("unquoted-text", 8),
        ]
        assert all(r["disposition"] == "surfaced" for r in rows)
        assert rows[0]["section"] == "Layers"
        assert rows[0]["citekeys"] == [KEY]
        assert rows[1]["citekeys"] == []

    def test_ids_are_twelve_hex_characters_and_stable_across_runs(self):
        first = [r["id"] for r in render.items(a_checked(), DIGEST)]
        second = [r["id"] for r in render.items(a_checked(), DIGEST)]
        assert first == second
        assert all(len(i) == 12 and int(i, 16) >= 0 for i in first)
        assert len(set(first)) == 4

    def test_a_copy_mismatch_summary_names_the_missing_words(self):
        checked = match.Checked()
        sentence = "Layered twins separate the physical entity from its blueprints."
        detail = {"page": 4, "share": 0.9, "missing": ["blueprints"]}
        checked.findings.append(match.Finding("copy-mismatch", 5, sentence, (KEY,), detail))
        (row,) = render.items(checked, DIGEST)
        assert "missing: blueprints" in row["summary"]
        assert "p. 4" in row["summary"]

    def test_a_long_sentence_is_excerpted_on_the_line_and_whole_in_detail(self):
        checked = match.Checked()
        long = "Word " * 40
        checked.findings.append(match.Finding("unquoted-text", 5, long.strip(), ()))
        (row,) = render.items(checked, DIGEST)
        assert row["summary"].count("Word") < 40 and row["summary"].count("...") == 1
        assert row["detail"]["text"] == long.strip()


class TestPayload:
    def test_carries_the_envelope_the_fractions_and_the_counts(self):
        draft = a_digest(DIGEST)
        data = render.payload(draft, "cmd", a_checked(), render.items(a_checked(), DIGEST))
        assert data["aid"] == "digest" and data["draft"] == str(draft) and data["command"] == "cmd"
        assert data["notice"] == review.notice()
        assert data["words_total"] == 25 and data["words_copied"] == 9 and data["words_flagged"] == 12
        assert data["unsupported_fraction"] == 0.48
        assert data["copied_fraction"] == 0.36
        assert data["unverifiable_fraction"] == 0.0 and data["words_unverifiable"] == 0
        assert data["counts"] == {"unsupported-text": 2, "copy-mismatch": 0, "unquoted-text": 2}
        assert data["spans"] == [
            {
                "line": 5,
                "citekeys": [KEY],
                "text": "Layered twins separate the physical entity from its models.",
                "tier": "exact",
                "pages": [4],
                "cited": [4, 4],
                "note": None,
            }
        ]
        assert data["unverifiable"] == []
        assert len(data["items"]) == 4

    def test_is_json_serialisable(self):
        draft = a_digest(DIGEST)
        json.dumps(render.payload(draft, "cmd", a_checked(), render.items(a_checked(), DIGEST)))


class TestMarkdown:
    def test_opens_with_the_header_and_leads_with_the_unsupported_fraction(self):
        draft = a_digest(DIGEST)
        checked = a_checked()
        text = render.render_markdown(draft, "cmd", checked, render.items(checked, DIGEST))
        assert text.startswith(f"# Verbatim digest: {draft}\n")
        assert review.BANNER in text
        summary = text.index("## Summary")
        unsupported = text.index("- Unsupported fraction: 0.48 (12 of 25 words)")
        assert unsupported < text.index("- Copied fraction: 0.36 (9 of 25 words)")
        assert text.index("- Not checkable: 0.0 (0 of 25 words, 0 runs)") > summary
        assert "- unsupported-text: 2" in text

    def test_item_lines_use_the_agendas_format(self):
        checked = a_checked()
        rows = render.items(checked, DIGEST)
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, rows)
        assert f"- `{rows[0]['id']}` [surfaced] (Layers): {rows[0]['summary']}" in text

    def test_lists_copied_spans_and_unverifiable_runs(self):
        checked = a_checked()
        reason = f"{KEY}: no reading-ordered passages -- only page-level text"
        checked.unverifiable.append({"line": 9, "citekeys": [KEY], "words": 4, "reason": reason})
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, render.items(checked, DIGEST))
        assert "## Copied spans" in text and f"line 5, `{KEY}`, p. 4, exact" in text
        assert "## Not checkable" in text and "line 9" in text

    def test_a_clean_digest_says_so(self):
        checked = match.Checked()
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, [])
        assert "No findings." in text
        assert "- Unsupported fraction: 0.0 (0 of 0 words)" in text
        assert "None." in text

    def test_carries_no_date(self):
        import datetime

        text = render.render_markdown(a_digest(DIGEST), "cmd", match.Checked(), [])
        assert str(datetime.date.today().year) not in text.replace(review.version(), "")
