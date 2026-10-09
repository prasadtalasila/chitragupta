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
from tests.test_review_quotation import a_source
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


def a_payload(draft: Path, *findings: match.Finding, total: int = 20) -> dict:
    checked = match.Checked()
    checked.findings.extend(findings)
    checked.words_total = total
    return render.payload(draft, "cmd", checked, render.items(checked, DIGEST))


class TestLoadBaseline:
    def test_reads_a_digest_payload_back(self, tmp_path):
        data = a_payload(a_digest(DIGEST))
        path = tmp_path / "notes.digest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert recheck.load_baseline(path)["aid"] == "digest"

    def test_an_unreadable_path_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="Cannot read the baseline"):
            recheck.load_baseline(tmp_path / "missing.json")

    def test_non_json_is_refused(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSON"):
            recheck.load_baseline(path)

    def test_another_aids_payload_is_refused(self, tmp_path):
        path = tmp_path / "notes.agenda.json"
        path.write_text(json.dumps({"aid": "agenda", "items": [], "command": "x"}), encoding="utf-8")
        with pytest.raises(ValueError, match="not a digest payload"):
            recheck.load_baseline(path)


class TestCompare:
    def test_resolved_persisting_new_by_id_and_the_counts(self):
        draft = a_digest(DIGEST)
        gone = match.Finding("unquoted-text", 6, "Gone sentence.", (KEY,))
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        detail = {"page": 4, "share": 0.9, "missing": []}
        fresh = match.Finding("copy-mismatch", 9, "Fresh sentence.", (KEY,), detail)
        before = a_payload(draft, gone, stays)
        after = a_payload(draft, stays, fresh)
        result = recheck.compare(after, before)
        assert [i["detail"]["text"] for i in result["resolved"]] == ["Gone sentence."]
        assert [i["detail"]["text"] for i in result["persisting"]] == ["Stays sentence."]
        assert [i["detail"]["text"] for i in result["new"]] == ["Fresh sentence."]
        assert result["counts_before"]["unquoted-text"] == 2
        assert result["counts_after"] == {"unsupported-text": 0, "copy-mismatch": 1, "unquoted-text": 1}
        assert result["fell"] is False

    def test_fell_means_no_class_rose_one_fell_nothing_new_and_the_fraction_did_not_rise(self):
        draft = a_digest(DIGEST)
        gone = match.Finding("unquoted-text", 6, "Gone sentence.", (KEY,))
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        assert recheck.compare(a_payload(draft, stays), a_payload(draft, gone, stays))["fell"] is True
        assert recheck.compare(a_payload(draft, stays), a_payload(draft, stays))["fell"] is False
        # One item gone but the digest shrank more: the fraction rose.
        shrunk = a_payload(draft, stays, total=2)
        assert recheck.compare(shrunk, a_payload(draft, gone, stays))["fell"] is False

    def test_both_fractions_travel(self):
        draft = a_digest(DIGEST)
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        result = recheck.compare(a_payload(draft, stays, total=10), a_payload(draft, stays, total=20))
        assert (result["unsupported_before"], result["unsupported_after"]) == (0.1, 0.2)
        assert (result["copied_before"], result["copied_after"]) == (0.0, 0.0)


class TestRecheckOutput:
    def test_command_names_the_baseline_and_json(self):
        assert recheck.recheck_command("content/drafts/t/notes.md", "b.json") == (
            "python -m chitragupta.review digest content/drafts/t/notes.md --baseline b.json --json"
        )

    def test_payload_and_text_say_the_same_thing(self):
        draft = a_digest(DIGEST)
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        comparison = recheck.compare(a_payload(draft, stays), a_payload(draft, stays))
        data = recheck.recheck_payload(draft, "b.json", comparison)
        text = recheck.format_recheck("b.json", comparison)
        assert data["aid"] == "digest" and data["baseline"] == "b.json"
        assert data["fell"] is False and "fell: no" in text
        assert "baseline: b.json" in text
        assert "persisting: 1" in text and "resolved: 0" in text and "new: 0" in text
        assert "unquoted-text: 1 -> 1" in text
        assert "unsupported fraction: 0.1 -> 0.1" in text
        assert "copied fraction: 0.0 -> 0.0" in text


class TestRegistration:
    def test_digest_is_an_aid_with_a_module_and_a_label(self):
        assert review.AIDS["digest"] == "Verbatim digest"
        from chitragupta.review import _registry

        assert _registry.AIDS["digest"][0] is verbatim_digest

    def test_the_report_lands_under_the_ordinary_rule(self, isolated_config):
        draft = config.DRAFTS_DIR / "t" / "notes.md"
        assert review.report_path(draft, "digest") == config.REVIEW_DIR / "t" / "notes.digest.md"

    def test_agenda_does_not_read_it(self):
        from chitragupta.review.agenda import _sources

        assert "digest" not in _sources.AID_NAMES

    def test_the_moved_path_helpers_keep_their_names(self):
        from chitragupta.review import _paths

        assert review.require_reviewable is _paths.require_reviewable
        assert review.report_dir is _paths.report_dir


class TestRun:
    def test_files_md_and_json_and_prints_the_summary(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        assert review_main.main(["digest", str(draft), "--formats", "md"]) == 0
        out = capsys.readouterr().out
        md = config.REVIEW_DIR / "dt" / "notes.digest.md"
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        assert md.is_file() and js.is_file()
        assert str(md) in out and str(js) in out
        data = json.loads(js.read_text(encoding="utf-8"))
        assert data["command"] == f"python -m chitragupta.review digest {draft} --formats md"
        assert data["counts"]["unquoted-text"] == 2
        assert data["counts"]["unsupported-text"] == 2
        assert data["words_copied"] == 17 and data["words_flagged"] == 12
        assert data["unsupported_fraction"] == round(12 / data["words_total"], 3)
        assert "Unsupported fraction" in md.read_text(encoding="utf-8")

    def test_json_goes_to_stdout_and_the_summary_to_stderr(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        assert review_main.main(["digest", str(draft), "--json", "--formats", "md"]) == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out)["aid"] == "digest"
        assert "notes.digest.json" in captured.err

    def test_a_digest_with_no_prose_exits_zero(self, capsys):
        draft = a_digest("# Only a heading\n")
        assert review_main.main(["digest", str(draft), "--json", "--formats", "md"]) == 0
        assert json.loads(capsys.readouterr().out)["unsupported_fraction"] == 0.0

    def test_a_draft_outside_content_exits_one(self, tmp_path, capsys):
        outside = tmp_path / "notes.md"
        outside.write_text("x\n", encoding="utf-8")
        assert review_main.main(["digest", str(outside)]) == 1
        assert "content" in capsys.readouterr().err

    def test_a_missing_draft_exits_one(self, capsys):
        assert review_main.main(["digest", str(config.DRAFTS_DIR / "nope.md")]) == 1

    def test_a_bad_baseline_exits_two_before_reading_the_ledger(self, tmp_path, capsys, monkeypatch):
        draft = a_digest(DIGEST)
        bad = tmp_path / "notes.agenda.json"
        bad.write_text(json.dumps({"aid": "agenda", "items": []}), encoding="utf-8")
        monkeypatch.setattr(verbatim_digest, "build_report", lambda *_: pytest.fail("built a report"))
        assert review_main.main(["digest", str(draft), "--baseline", str(bad)]) == 2
        assert "not a digest payload" in capsys.readouterr().err

    def test_baseline_prints_the_comparison_and_refiles_the_report(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        # The repair: delete the closing thought.
        draft.write_text(DIGEST.replace("And a closing thought of mine.\n", ""), encoding="utf-8")
        assert review_main.main(["digest", str(draft), "--baseline", str(js), "--formats", "md"]) == 0
        out = capsys.readouterr().out
        assert "resolved: 2" in out and "new: 0" in out and "fell: yes" in out
        assert json.loads(js.read_text(encoding="utf-8"))["counts"]["unquoted-text"] == 1

    def test_baseline_with_json_prints_the_comparison_payload(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        capsys.readouterr()
        argv = ["digest", str(draft), "--baseline", str(js), "--json", "--formats", "md"]
        assert review_main.main(argv) == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["baseline"] == str(js) and data["fell"] is False
        assert data["command"].endswith("--json")
        assert "notes.digest.md" in captured.err

    def test_the_filed_command_is_the_bare_one_even_under_baseline(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        review_main.main(["digest", str(draft), "--baseline", str(js), "--formats", "md"])
        assert "--baseline" not in json.loads(js.read_text(encoding="utf-8"))["command"]

    def test_passages_are_looked_up_once_per_citekey(self, monkeypatch):
        from chitragupta import passages as passages_mod

        calls = []
        real = passages_mod.source_passages

        def counting(con, citekey):
            calls.append(citekey)
            return real(con, citekey)

        monkeypatch.setattr(verbatim_digest.passages, "source_passages", counting)
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        verbatim_digest.build_report(draft)
        assert calls == [KEY]

    def test_main_with_default_formats_files_the_bare_command(self, capsys):
        """`main()` is the standalone entry the entry-point tests do not
        reach, and the default `--formats` is the one branch of
        `_command` a run that names its formats never takes. Rendering
        `tex`/`pdf` needs pandoc; without it each is skipped with a
        warning, which is the documented behaviour, not a failure."""
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        assert verbatim_digest.main([str(draft)]) == 0
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        assert json.loads(js.read_text(encoding="utf-8"))["command"] == (
            f"python -m chitragupta.review digest {draft}"
        )
        assert "notes.digest.md" in capsys.readouterr().out

    def test_the_standalone_parser_carries_the_same_defaults(self):
        """`tests/test_review_entrypoint.py` already pins that every aid
        declares its flags on the subparser and has no `__main__` block;
        this only covers `build_parser(None)`, the shape `main()` uses."""
        parser = verbatim_digest.build_parser()
        args = parser.parse_args(["x.md"])
        assert (args.formats, args.json, args.baseline) == ("md,tex,pdf", False, None)
