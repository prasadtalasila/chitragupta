"""Tests for chitragupta/dossier/ (#219 split it out of one chitragupta/dossier.py).

Three things carry most of the weight here, because they are the three
that can lose someone's work or waste the tokens the module exists to
save:

- the mirroring rule (`content/drafts/x/y.md` <-> `content/dossiers/x/y/`),
  since nothing else ties a draft to its dossier;
- outline extraction, since a wrong line range hands a reviser a slice
  that cuts a section in half -- and the shipped example tutorial is
  mostly fenced code full of `#` comments;
- restore, the one destructive operation, which must refuse an unsafe
  archive outright and must not write at all without --force.
"""

import tarfile
import tomllib
from pathlib import Path

import pytest

from chitragupta import acronyms, config, dossier
from chitragupta.dossier import (
    _acronyms,
    _archive,
    _brief,
    _citekeys,
    _create,
    _drift,
    _evidence_check,
    _retrieval,
    _sections,
    _status,
)


@pytest.fixture
def draft(isolated_config):
    """A draft where a genre skill would save one, in the nested layout
    the shipped example content uses."""
    path = config.DRAFTS_DIR / "dt-for-engineers" / "survey.md"
    path.parent.mkdir(parents=True)
    path.write_text("# A survey\n\n## 1. First\n\ntext\n\n## 2. Second\n\nmore\n")
    return path


def _seed_ledger(citekeys):
    """A ledger holding just these citekeys.

    Inserted with raw SQL rather than through `upsert_reference`, which
    takes a `bib_reader.Reference` and so would drag bibtexparser into a
    module that is deliberately stdlib-only.
    """
    from chitragupta import ledger

    con = ledger.connect()
    try:
        con.executemany(
            "INSERT INTO items (citekey, status, last_synced) VALUES (?, 'parsed', '2026-01-01')",
            [(key,) for key in citekeys],
        )
        con.commit()
    finally:
        con.close()


class TestDossierDir:
    def test_mirrors_a_nested_draft_path(self, draft):
        assert dossier.dossier_dir(draft) == config.DOSSIERS_DIR / "dt-for-engineers" / "survey"

    def test_mirrors_a_flat_draft_path(self, isolated_config):
        config.DRAFTS_DIR.mkdir(parents=True)
        flat = config.DRAFTS_DIR / "survey.md"
        flat.write_text("# x\n")
        assert dossier.dossier_dir(flat) == config.DOSSIERS_DIR / "survey"

    def test_a_tex_draft_mirrors_the_same_way(self, isolated_config):
        config.DRAFTS_DIR.mkdir(parents=True)
        tex = config.DRAFTS_DIR / "thesis.tex"
        tex.write_text("\\section{x}\n")
        assert dossier.dossier_dir(tex) == config.DOSSIERS_DIR / "thesis"

    def test_a_draft_outside_the_drafts_dir_is_refused(self, isolated_config, tmp_path):
        stray = tmp_path / "elsewhere.md"
        stray.write_text("# x\n")
        with pytest.raises(dossier.DossierError, match="not under"):
            dossier.dossier_dir(stray)

    def test_a_dossier_dir_that_escapes_the_content_tree_is_refused(
        self, isolated_config, tmp_path
    ):
        """A symlinked topic directory under `content/dossiers/` must not
        become a licence to write outside `content/`.

        `relative` is computed from resolved paths, so no *argument* can
        smuggle a `..` past this -- the way out is configuration or a
        symlink on the target side, which is why the check is on the
        result rather than on the input. `render_output._output_dir` and
        `citation_provenance.write_report` already made it; this was the
        one consumer of the shared mirroring rule that didn't, so a
        dossier could be written where nothing else in the pipeline looks
        and no backup of `content/` would carry it.
        """
        config.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        config.DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        (config.DOSSIERS_DIR / "topic").symlink_to(outside)

        draft = config.DRAFTS_DIR / "topic" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# x\n")

        with pytest.raises(dossier.DossierError, match="outside"):
            dossier.dossier_dir(draft)

    def test_find_draft_is_the_inverse(self, draft):
        assert dossier.find_draft(dossier.dossier_dir(draft)) == draft

    def test_find_draft_returns_none_when_the_draft_is_gone(self, draft):
        target = dossier.dossier_dir(draft)
        draft.unlink()
        assert dossier.find_draft(target) is None

    def test_find_draft_finds_a_tex_draft(self, isolated_config):
        config.DRAFTS_DIR.mkdir(parents=True)
        tex = config.DRAFTS_DIR / "thesis.tex"
        tex.write_text("\\section{x}\n")
        assert dossier.find_draft(config.DOSSIERS_DIR / "thesis") == tex

    def test_draft_name_is_the_path_under_drafts_without_a_suffix(self, draft):
        assert dossier.draft_name(draft) == "dt-for-engineers/survey"


class TestSections:
    def test_line_ranges_run_to_the_next_heading(self):
        outline = dossier.sections("# Title\n\nintro\n\n## One\n\na\n\n## Two\n\nb\n")
        assert [(s.title, s.start, s.end) for s in outline] == [
            ("Title", 1, 4),
            ("One", 5, 8),
            ("Two", 9, 11),
        ]

    def test_the_last_section_runs_to_the_end_of_the_file(self):
        (last,) = dossier.sections("## Only\n\na\nb\nc\n")
        assert (last.start, last.end, last.lines) == (1, 5, 5)

    def test_heading_levels_are_recorded(self):
        outline = dossier.sections("# A\n## B\n### C\n")
        assert [s.level for s in outline] == [1, 2, 3]

    def test_a_hash_comment_inside_a_fenced_block_is_not_a_heading(self):
        text = (
            "# Tutorial\n\n```bash\n# Step 1: make the folder\nmkdir pot\n```\n\n## Real heading\n"
        )
        assert [s.title for s in dossier.sections(text)] == ["Tutorial", "Real heading"]

    def test_a_tilde_fence_is_tracked_too(self):
        text = "# T\n\n~~~python\n# not a heading\n~~~\n\n## Real\n"
        assert [s.title for s in dossier.sections(text)] == ["T", "Real"]

    def test_latex_sectioning_commands_are_recognised(self):
        text = "\\chapter{Ch}\ntext\n\\section{Sec}\nmore\n\\subsection{Sub}\n"
        outline = dossier.sections(text)
        assert [(s.title, s.level) for s in outline] == [
            ("Ch", 1),
            ("Sec", 2),
            ("Sub", 3),
        ]

    def test_a_latex_title_containing_braces_keeps_its_whole_title(self):
        (only,) = dossier.sections("\\section{The \\emph{twin} problem}\n")
        assert only.title == "The \\emph{twin} problem"

    def test_a_trailing_label_is_not_swallowed_into_the_title(self):
        (only,) = dossier.sections("\\section{Architecture}\\label{sec:arch}\n")
        assert only.title == "Architecture"

    def test_an_unterminated_latex_title_still_yields_a_section(self):
        (only,) = dossier.sections("\\section{A title that wraps\n")
        assert only.title == "A title that wraps"

    def test_a_section_command_inside_verbatim_is_not_a_heading(self):
        text = (
            "\\section{Real}\n"
            "\\begin{lstlisting}\n"
            "\\section{Not real}\n"
            "\\end{lstlisting}\n"
            "\\section{Also real}\n"
        )
        assert [s.title for s in dossier.sections(text)] == ["Real", "Also real"]

    def test_a_closing_hash_run_is_stripped_from_the_title(self):
        (only,) = dossier.sections("## Balanced ##\n")
        assert only.title == "Balanced"

    def test_a_draft_with_no_headings_yields_nothing(self):
        assert dossier.sections("just prose\nover two lines\n") == []

    def test_the_shipped_example_tutorial_outlines_cleanly(self):
        """Regression guard against the fence bug on real content: the
        example tutorial is mostly shell and Python whose comments start
        with `#`."""
        example = (
            config.PROJECT_ROOT / "content/drafts/digital-twins-for-software-engineers/tutorial.md"
        )
        if not example.is_file():  # pragma: no cover - example content is optional
            pytest.skip("example content not present in this checkout")
        titles = [s.title for s in dossier.sections(example.read_text())]
        assert titles[0] == "Build a Digital Twin for a Potted Plant"
        assert "Step 1: Create the project folder" in titles
        assert not any(t.startswith("!") or t.startswith("/") for t in titles)


class TestInit:
    def test_writes_every_dossier_file(self, draft):
        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        assert {p.name for p in target.iterdir()} == {"README.md", *dossier.FILES}

    def test_is_idempotent_and_does_not_clobber_filled_in_files(self, draft):
        dossier.init(draft, "survey")
        evidence = dossier.dossier_dir(draft) / "evidence.md"
        evidence.write_text("# Kept evidence\n\n## `talasila_composable_2025`\n")
        written = dossier.init(draft, "survey")
        assert written == []
        assert "talasila_composable_2025" in evidence.read_text()

    def test_replaces_only_a_deleted_file(self, draft):
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "steering.md").unlink()
        written = dossier.init(draft, "survey")
        assert [p.name for p in written] == ["steering.md"]

    def test_records_the_corpus_fingerprint(self, draft):
        _seed_ledger(["a_one_2020", "b_two_2021"])
        dossier.init(draft, "survey")
        recorded = dossier.recorded_corpus(dossier.dossier_dir(draft))
        assert recorded == (2, dossier.digest({"a_one_2020", "b_two_2021"}))

    def test_says_so_when_there_is_no_ledger_to_fingerprint(self, draft):
        dossier.init(draft, "survey")
        scope = (dossier.dossier_dir(draft) / "scope.md").read_text()
        assert "not recorded" in scope
        assert dossier.recorded_corpus(dossier.dossier_dir(draft)) is None

    def test_the_genre_reaches_the_dossier(self, draft):
        dossier.init(draft, "thesis-chapter")
        assert "genre: thesis-chapter" in (dossier.dossier_dir(draft) / "scope.md").read_text()

    def test_scope_carries_a_language_line_marked_unsettled(self, draft):
        """The dialect field #104 adds, and the fact that `init` cannot know it.

        A placeholder that looked like a value would be worse than no
        field: `draft-reviser` reads `scope.md` before every edit and
        would apply an en-US default nobody chose. So the line ships
        saying it is not settled, the same way the corpus fingerprint
        says "not recorded" rather than inventing a digest.
        """
        dossier.init(draft, "survey")
        scope = (dossier.dossier_dir(draft) / "scope.md").read_text()
        assert "- language: not settled" in scope
        assert "en-GB" in scope


def _write_glossary(draft, body):
    """Replace the shipped `## Glossary` placeholder with real bullets.

    Shared by TestGlossaryTerms and TestSuggestAcronyms.
    """
    scope = dossier.dossier_dir(draft) / "scope.md"
    placeholder = (
        "## Glossary\n\n"
        "<!-- Each recurring term with the one definition the whole "
        "draft uses. -->\n"
    )
    text = scope.read_text()
    assert placeholder in text
    scope.write_text(text.replace(placeholder, f"## Glossary\n\n{body}\n"))


class TestGlossaryTerms:
    """`## Glossary`'s `- **Term** -- definition` bullets, read back out.

    The shape is the one #190's resolving comment found a real 15-chapter
    book already converged on with no schema in force -- a forgiving
    parser, not a schema, so a hand-typed line that doesn't match is
    skipped rather than an error (docs/DRAFT-ITERATION.md's "degrades to
    unavailable" policy).
    """

    def test_returns_empty_dict_without_a_dossier(self, draft):
        assert _citekeys.glossary_terms(draft) == {}

    def test_the_shipped_placeholder_has_no_terms(self, draft):
        dossier.init(draft, "survey")
        assert _citekeys.glossary_terms(draft) == {}

    def test_returns_empty_when_scope_has_no_glossary_heading_at_all(self, draft):
        dossier.init(draft, "survey")
        scope = dossier.dossier_dir(draft) / "scope.md"
        scope.write_text(scope.read_text().replace("## Glossary", "## Not a glossary"))
        assert _citekeys.glossary_terms(draft) == {}

    def test_a_bullet_with_no_definition_text_is_skipped(self, draft):
        dossier.init(draft, "survey")
        _write_glossary(
            draft,
            "- **DTaaS** --\n- **FMU** -- Functional Mock-up Unit.",
        )
        assert _citekeys.glossary_terms(draft) == {"FMU": "Functional Mock-up Unit."}

    def test_parses_a_single_bullet(self, draft):
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")
        assert _citekeys.glossary_terms(draft) == {"DTaaS": "Digital Twin as a Service."}

    def test_parses_several_bullets(self, draft):
        dossier.init(draft, "survey")
        _write_glossary(
            draft,
            "- **DTaaS** -- Digital Twin as a Service.\n"
            "- **FMU** -- Functional Mock-up Unit, the packaging format "
            "co-simulation tools exchange.",
        )
        terms = _citekeys.glossary_terms(draft)
        assert terms["DTaaS"] == "Digital Twin as a Service."
        assert terms["FMU"].startswith("Functional Mock-up Unit")

    def test_a_definition_can_run_to_several_lines(self, draft):
        dossier.init(draft, "survey")
        _write_glossary(
            draft,
            "- **Twin state** -- the digital object's current best\n"
            "  estimate of the physical twin's condition. *Estimate*, not\n"
            "  *reading*: it may include quantities no sensor measures.",
        )
        terms = _citekeys.glossary_terms(draft)
        assert terms["Twin state"].startswith("the digital object's current best")
        assert "*Estimate*, not" in terms["Twin state"]

    def test_a_hand_typed_line_that_does_not_match_is_skipped_not_an_error(self, draft):
        dossier.init(draft, "survey")
        _write_glossary(draft, "DTaaS: Digital Twin as a Service (no bullet)")
        assert _citekeys.glossary_terms(draft) == {}

    def test_stops_at_the_next_heading(self, draft):
        # ## Glossary is the last section _scope() writes, so appending
        # a further heading is what exercises the "don't read past
        # Glossary" branch.
        dossier.init(draft, "survey")
        scope = dossier.dossier_dir(draft) / "scope.md"
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")
        scope.write_text(
            scope.read_text() + "\n## Not glossary\n\n- **Not a term** -- should not appear.\n"
        )
        assert _citekeys.glossary_terms(draft) == {"DTaaS": "Digital Twin as a Service."}


class TestSuggestAcronyms:
    """suggest_acronyms() proposes; it never writes anything -- #190's
    own rule, restated in docs/HOUSE-STYLE.md: this class of feature
    proposes and the human accepts.

    The acronym-shape and already-in-vocabulary matching itself is
    `acronyms.suggest()`, tested directly in
    tests/test_acronyms.py::TestSuggest -- these tests only cover this
    module's own part: turning a draft path into the merged
    glossary-and-body-prose dict `acronyms.suggest()` needs, and the CLI
    wrapper around it. `acronyms.body_candidates()`'s own extraction
    rules (references excluded, hard-wraps reflowed) are tested directly
    in tests/test_acronyms.py::TestBodyCandidates.
    """

    def test_returns_empty_without_a_dossier(self, draft):
        assert _acronyms.suggest_acronyms(draft) == {}

    def test_delegates_to_acronyms_suggest_with_this_drafts_glossary(self, draft, monkeypatch):
        monkeypatch.setattr(
            acronyms,
            "load_vocabulary",
            lambda: {"PDF": "Portable Document Format"},
        )
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")
        assert _acronyms.suggest_acronyms(draft) == {"DTaaS": "Digital Twin as a Service."}

    def test_finds_a_candidate_only_present_in_the_drafts_own_prose(self, draft, monkeypatch):
        # The real gap this closes: DTP/DTI/DTA are defined inline in
        # the real book's chapter 2 but glossaried nowhere at all.
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        dossier.init(draft, "survey")
        draft.write_text(
            draft.read_text(encoding="utf-8")
            + "\nThe **Digital Twin Prototype (DTP)** is introduced here.\n",
            encoding="utf-8",
        )
        assert _acronyms.suggest_acronyms(draft) == {"DTP": "Digital Twin Prototype"}

    def test_the_glossary_wins_over_conflicting_body_prose(self, draft, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **Digital twin (DT)** -- the deliberate record.")
        draft.write_text(
            draft.read_text(encoding="utf-8")
            + "\nSome prose calls it the Digital Twin System (DT) instead.\n",
            encoding="utf-8",
        )
        assert _acronyms.suggest_acronyms(draft) == {"DT": "Digital twin"}

    def test_cli_reports_no_new_acronyms(self, draft, capsys, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        dossier.init(draft, "survey")
        assert dossier.main(["acronyms-suggest", str(draft)]) == 0
        assert "No new acronyms" in capsys.readouterr().out

    def test_cli_prints_a_suggestion_and_writes_nothing(self, draft, capsys, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")
        vendored = config.shipped("assets", "style", "acronyms.toml")
        vocab_before = vendored.read_text()

        assert dossier.main(["acronyms-suggest", str(draft)]) == 0

        out = capsys.readouterr().out
        assert "DTaaS" in out
        assert "Digital Twin as a Service" in out
        assert vendored.read_text() == vocab_before


class TestApplySuggestions:
    """apply_suggestions()/`--apply` -- the one path in this feature that
    writes. Guarded against the one way that write can go wrong: with
    `[style].acronyms` unset, `config.ACRONYMS_PATH` *is*
    `config.ACRONYMS_DEFAULT_PATH`, the vendored, git-tracked file, and
    writing there would commit one user's domain vocabulary into what
    every clone shares (#190)."""

    def test_refuses_to_write_when_the_user_path_is_unset(self, draft, tmp_path, monkeypatch):
        # The "unset" condition -- ACRONYMS_PATH is ACRONYMS_DEFAULT_PATH --
        # is established here, in tmp_path, rather than assumed of the
        # host's own config.toml: isolated_config does not patch either
        # constant (they are read once at import time), so a host that
        # followed docs/CONFIG.md and set [style].acronyms would otherwise
        # make this test assert something false about its own machine.
        vendored = tmp_path / "vendored.toml"
        monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
        monkeypatch.setattr(config, "ACRONYMS_PATH", vendored)
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")

        with pytest.raises(_acronyms.NoUserAcronymsFile):
            _acronyms.apply_suggestions(draft)

    def test_cli_apply_refuses_and_writes_nothing_when_unset(
        self, draft, tmp_path, capsys, monkeypatch
    ):
        # Same reason as the test above: without pinning both constants to
        # the same tmp_path file, a host with [style].acronyms set would
        # take the *write* branch instead and mutate that host's real
        # content/acronyms.toml as a side effect of running this suite.
        vendored = tmp_path / "vendored.toml"
        vendored.write_text('PDF = "Portable Document Format"\n', encoding="utf-8")
        monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
        monkeypatch.setattr(config, "ACRONYMS_PATH", vendored)
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")
        vocab_before = vendored.read_text(encoding="utf-8")

        assert dossier.main(["acronyms-suggest", str(draft), "--apply"]) == 0

        out = capsys.readouterr().out
        assert "[style].acronyms is not set" in out
        assert vendored.read_text(encoding="utf-8") == vocab_before

    def test_creates_the_user_file_and_writes_new_candidates(self, draft, tmp_path, monkeypatch):
        user_path = tmp_path / "content" / "acronyms.toml"
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        monkeypatch.setattr(config, "ACRONYMS_PATH", user_path)
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")

        written = _acronyms.apply_suggestions(draft)

        assert written == {"DTaaS": "Digital Twin as a Service."}
        assert user_path.is_file()
        assert 'DTaaS = "Digital Twin as a Service."' in user_path.read_text()

    def test_appends_without_duplicating_an_existing_entry(self, draft, tmp_path, monkeypatch):
        user_path = tmp_path / "content" / "acronyms.toml"
        user_path.parent.mkdir(parents=True, exist_ok=True)
        user_path.write_text('FMU = "Functional Mock-up Unit"\n', encoding="utf-8")
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"FMU": "Functional Mock-up Unit"})
        monkeypatch.setattr(config, "ACRONYMS_PATH", user_path)
        dossier.init(draft, "survey")
        _write_glossary(
            draft,
            "- **FMU** -- Functional Mock-up Unit.\n- **DTaaS** -- Digital Twin as a Service.",
        )

        written = _acronyms.apply_suggestions(draft)

        assert written == {"DTaaS": "Digital Twin as a Service."}
        text = user_path.read_text()
        assert text.count("FMU") == 1
        assert 'DTaaS = "Digital Twin as a Service."' in text

    def test_a_second_apply_with_nothing_new_writes_nothing(self, draft, tmp_path, monkeypatch):
        user_path = tmp_path / "content" / "acronyms.toml"
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        monkeypatch.setattr(config, "ACRONYMS_PATH", user_path)
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")
        _acronyms.apply_suggestions(draft)
        monkeypatch.setattr(
            acronyms, "load_vocabulary", lambda: {"DTaaS": "Digital Twin as a Service."}
        )
        text_after_first_apply = user_path.read_text()

        written = _acronyms.apply_suggestions(draft)

        assert written == {}
        assert user_path.read_text() == text_after_first_apply

    def test_cli_apply_reports_nothing_new_when_the_user_path_is_set(
        self, draft, tmp_path, capsys, monkeypatch
    ):
        user_path = tmp_path / "content" / "acronyms.toml"
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        monkeypatch.setattr(config, "ACRONYMS_PATH", user_path)
        dossier.init(draft, "survey")

        assert dossier.main(["acronyms-suggest", str(draft), "--apply"]) == 0

        assert "No new acronyms" in capsys.readouterr().out
        assert not user_path.exists()

    def test_escapes_a_quote_or_backslash_in_the_expansion(self, draft, tmp_path, monkeypatch):
        """A written entry must round-trip through tomllib -- apply_suggestions
        checks this itself, but only a definition containing the two
        characters a TOML basic string cannot hold unescaped actually
        exercises the escaping, rather than just its line coverage."""
        user_path = tmp_path / "content" / "acronyms.toml"
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        monkeypatch.setattr(config, "ACRONYMS_PATH", user_path)
        dossier.init(draft, "survey")
        _write_glossary(draft, r'- **JIT** -- the "just-in-time" pattern, C:\path style.')

        written = _acronyms.apply_suggestions(draft)

        expected = 'the "just-in-time" pattern, C:\\path style.'
        assert written == {"JIT": expected}
        with user_path.open("rb") as handle:
            assert tomllib.load(handle) == {"JIT": expected}

    def test_cli_apply_reports_what_it_wrote(self, draft, tmp_path, capsys, monkeypatch):
        user_path = tmp_path / "content" / "acronyms.toml"
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        monkeypatch.setattr(config, "ACRONYMS_PATH", user_path)
        dossier.init(draft, "survey")
        _write_glossary(draft, "- **DTaaS** -- Digital Twin as a Service.")

        assert dossier.main(["acronyms-suggest", str(draft), "--apply"]) == 0

        out = capsys.readouterr().out
        assert "Wrote 1 new entry" in out
        assert "DTaaS" in out


class TestKnownCitekeys:
    def test_returns_none_without_a_ledger(self, isolated_config):
        assert dossier.known_citekeys() is None

    def test_returns_none_for_a_ledger_that_is_not_a_database(self, isolated_config):
        config.LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.LEDGER_PATH.write_text("not sqlite")
        assert dossier.known_citekeys() is None

    def test_an_empty_ledger_is_a_set_not_none(self, isolated_config):
        _seed_ledger([])
        assert dossier.known_citekeys() == set()

    def test_the_digest_ignores_insertion_order(self):
        assert dossier.digest({"b", "a"}) == dossier.digest({"a", "b"})


class TestStatus:
    def test_reports_a_missing_dossier_without_raising(self, draft):
        report = _status.status(draft)
        assert report.files
        assert not any(f.present for f in report.files)

    def test_counts_entries_per_file(self, draft):
        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        (target / "evidence.md").write_text(
            "# Kept evidence\n\n## `a_one_2020`\n\n- relevance: x\n\n## `b_two_2021`\n\n- relevance: y\n"
        )
        (target / "rejected.md").write_text(
            "# Rejected\n\n| citekey | query | why |\n|---|---|---|\n"
            "| `c_three_2022` | q | off-topic |\n"
        )
        by_name = {f.name: f for f in _status.status(draft).files}
        assert by_name["evidence.md"].entries == 2
        assert by_name["rejected.md"].entries == 1

    def test_a_prose_file_reports_filled_in_rather_than_a_count(self, draft, capsys):
        """A count is information for the list-shaped files and noise for
        the prose ones -- "scope.md: 40 entries" is a number dressed up."""
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "steering.md").write_text(
            "# Steering\n\n## 2026-08-06 -- shorter\n\nCut the platform section.\n"
        )
        dossier.main(["status", str(draft)])
        out = capsys.readouterr().out
        assert "steering.md   filled in" in out
        assert "steering.md   2 entries" not in out

    def test_a_skeleton_file_counts_as_empty(self, draft):
        dossier.init(draft, "survey")
        by_name = {f.name: f for f in _status.status(draft).files}
        assert by_name["evidence.md"].entries == 0
        assert by_name["rejected.md"].entries == 0
        assert by_name["steering.md"].entries == 0

    def test_the_outline_comes_back_with_the_status(self, draft):
        dossier.init(draft, "survey")
        assert [s.title for s in _status.status(draft).outline] == [
            "A survey",
            "1. First",
            "2. Second",
        ]

    def test_drift_is_flagged_when_the_corpus_moves(self, draft):
        _seed_ledger(["a_one_2020"])
        dossier.init(draft, "survey")
        _seed_ledger(["b_two_2021"])
        report = _status.status(draft)
        assert report.drifted
        assert report.recorded[0] == 1
        assert report.current[0] == 2

    def test_an_unchanged_corpus_does_not_drift(self, draft):
        _seed_ledger(["a_one_2020"])
        dossier.init(draft, "survey")
        assert not _status.status(draft).drifted

    def test_citekeys_nowhere_in_the_dossier_are_named(self, draft):
        _seed_ledger(["a_one_2020", "b_two_2021"])
        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        (target / "evidence.md").write_text("# Kept\n\n## `a_one_2020`\n")
        assert _status.status(draft).unconsidered == {"b_two_2021"}

    def test_a_rejected_citekey_counts_as_considered(self, draft):
        _seed_ledger(["a_one_2020", "b_two_2021"])
        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        (target / "rejected.md").write_text(
            "| citekey | query | why |\n|---|---|---|\n| `b_two_2021` | q | off-topic |\n"
        )
        assert "b_two_2021" not in _status.status(draft).unconsidered

    def test_backticked_prose_is_not_mistaken_for_a_citekey(self, draft):
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "evidence.md").write_text(
            "# Kept\n\nRun `status` with `--force` on `content`.\n"
        )
        assert _citekeys.cited_citekeys(dossier.dossier_dir(draft)) == set()

    def test_a_separator_is_what_distinguishes_a_citekey_from_prose(self, draft):
        """Pins the rule `_CITEKEY_TOKEN`'s comment states: a letter start
        plus at least one separator-then-alphanumeric segment."""
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "evidence.md").write_text(
            "# Kept\n\n"
            "Real: `talasila_composable_2025`, `zech_digital-twins-as--service_2024`.\n"
            "Prose: `status`, `--force`, `content`, `md`.\n"
        )
        assert _citekeys.cited_citekeys(dossier.dossier_dir(draft)) == {
            "talasila_composable_2025",
            "zech_digital-twins-as--service_2024",
        }

    def test_drift_is_unavailable_rather_than_fatal_without_a_ledger(self, draft):
        dossier.init(draft, "survey")
        report = _status.status(draft)
        assert report.current is None
        assert not report.drifted

    def test_accepts_the_dossier_directory_as_well_as_the_draft(self, draft):
        dossier.init(draft, "survey")
        report = _status.status(dossier.dossier_dir(draft))
        assert report.draft == draft

    def test_reports_a_dossier_that_outlived_its_draft(self, draft):
        dossier.init(draft, "survey")
        draft.unlink()
        report = _status.status(dossier.dossier_dir(draft))
        assert report.draft is None
        assert report.outline == []


class TestList:
    def test_finds_every_dossier(self, draft, isolated_config):
        other = config.DRAFTS_DIR / "other.md"
        other.write_text("# other\n")
        dossier.init(draft, "survey")
        dossier.init(other, "tutorial")
        assert dossier.all_dossiers() == [
            config.DOSSIERS_DIR / "dt-for-engineers" / "survey",
            config.DOSSIERS_DIR / "other",
        ]

    def test_no_dossiers_directory_is_not_an_error(self, isolated_config):
        assert dossier.all_dossiers() == []


class TestExport:
    def test_bundles_the_draft_and_its_dossier(self, draft):
        dossier.init(draft, "survey")
        names = {name for _, name in _archive.bundle_members([], with_rendered=False)}
        assert "drafts/dt-for-engineers/survey.md" in names
        assert "dossiers/dt-for-engineers/survey/scope.md" in names

    def test_rendered_output_is_opt_in(self, draft):
        config.RENDERED_DIR.mkdir(parents=True)
        (config.RENDERED_DIR / "survey.pdf").write_bytes(b"%PDF")
        assert not any(
            name.startswith("rendered/")
            for _, name in _archive.bundle_members([], with_rendered=False)
        )
        assert any(
            name.startswith("rendered/")
            for _, name in _archive.bundle_members([], with_rendered=True)
        )

    def test_a_name_selects_the_rendered_output_of_a_nested_draft(self, draft):
        # Rendering mirrors the draft's own path (chitragupta/render_output.py's
        # _output_dir), which is what makes this match: while every format
        # wrote flat, `export dt-for-engineers --with-rendered` produced a
        # bundle with no PDFs in it and said nothing about it.
        rendered = config.RENDERED_DIR / "dt-for-engineers"
        rendered.mkdir(parents=True)
        (rendered / "survey.pdf").write_bytes(b"%PDF")
        names = {
            name for _, name in _archive.bundle_members(["dt-for-engineers"], with_rendered=True)
        }
        assert "rendered/dt-for-engineers/survey.pdf" in names

    def test_a_name_selects_a_drafts_evidence_sidecar(self, draft):
        # `survey.evidence.pdf` reduces to `dt-for-engineers/survey.evidence`
        # under _matches' with_suffix(""), which does not equal the draft
        # name `dt-for-engineers/survey` -- so without the aid-suffix
        # strip this file is silently absent from an archive whose whole
        # purpose is to be the complete record. Exactly the problem
        # `survey.provenance.md` had first.
        rendered = config.RENDERED_DIR / "dt-for-engineers"
        rendered.mkdir(parents=True)
        (rendered / "survey.evidence.pdf").write_bytes(b"%PDF")
        (rendered / "survey.evidence.md").write_text("# Evidence\n")
        names = {
            name
            for _, name in _archive.bundle_members(["dt-for-engineers/survey"], with_rendered=True)
        }
        assert "rendered/dt-for-engineers/survey.evidence.pdf" in names
        assert "rendered/dt-for-engineers/survey.evidence.md" in names

    def test_a_rendered_draft_whose_stem_merely_contains_a_dot_still_matches_itself(self, draft):
        # The strip is exactly `.evidence`, not "one more suffix": a draft
        # named `survey.v2.md` renders to `survey.v2.pdf` and must go on
        # matching `dt-for-engineers/survey.v2`, not be double-stripped to
        # `dt-for-engineers/survey`.
        rendered = config.RENDERED_DIR / "dt-for-engineers"
        rendered.mkdir(parents=True)
        (rendered / "survey.v2.pdf").write_bytes(b"%PDF")
        names = {
            name
            for _, name in _archive.bundle_members(
                ["dt-for-engineers/survey.v2"], with_rendered=True
            )
        }
        assert "rendered/dt-for-engineers/survey.v2.pdf" in names

    def test_a_name_selects_one_topic_directory(self, draft, isolated_config):
        other = config.DRAFTS_DIR / "unrelated.md"
        other.write_text("# other\n")
        dossier.init(draft, "survey")
        dossier.init(other, "tutorial")
        names = {
            name for _, name in _archive.bundle_members(["dt-for-engineers"], with_rendered=False)
        }
        assert "drafts/dt-for-engineers/survey.md" in names
        assert "dossiers/dt-for-engineers/survey/scope.md" in names
        assert not any("unrelated" in name for name in names)

    def test_a_name_can_be_a_single_flat_draft(self, isolated_config):
        config.DRAFTS_DIR.mkdir(parents=True)
        (config.DRAFTS_DIR / "survey.md").write_text("# s\n")
        (config.DRAFTS_DIR / "tutorial.md").write_text("# t\n")
        names = {name for _, name in _archive.bundle_members(["survey"], with_rendered=False)}
        assert names == {"drafts/survey.md"}

    def _review_reports(self, topic="dt-for-engineers"):
        directory = config.REVIEW_DIR / topic
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "survey.provenance.md").write_text("# p\n")
        (directory / "survey.verbatim.md").write_text("# v\n")
        (directory / "survey.provenance.pdf").write_bytes(b"%PDF")
        return directory

    def test_review_reports_are_bundled_by_default(self, draft):
        """The review layer gave its reports a mirrored path so a draft's
        evidence is findable from the draft. A bundle that dropped them
        would falsify that quietly."""
        self._review_reports()
        names = {name for _, name in _archive.bundle_members([], with_rendered=False)}
        assert "review/dt-for-engineers/survey.provenance.md" in names
        assert "review/dt-for-engineers/survey.verbatim.md" in names

    def test_their_renders_are_opt_in_like_every_other_pdf(self, draft):
        """--with-rendered gates PDFs, not text -- so the .md reports
        ship by default and their renders ride with the rest."""
        self._review_reports()
        default = {name for _, name in _archive.bundle_members([], with_rendered=False)}
        opted_in = {name for _, name in _archive.bundle_members([], with_rendered=True)}
        assert "review/dt-for-engineers/survey.provenance.pdf" not in default
        assert "review/dt-for-engineers/survey.provenance.pdf" in opted_in

    def test_a_versioned_draft_name_survives_the_aid_suffix_strip(self, isolated_config):
        """`survey.v2.md` matches as `survey.v2`, so its reports have to
        as well. Stripping two suffixes blindly would take them down to
        `survey` and quietly leave them out of the bundle."""
        config.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        (config.DRAFTS_DIR / "survey.v2.md").write_text("# s\n")
        config.REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        (config.REVIEW_DIR / "survey.v2.provenance.md").write_text("# p\n")

        names = {name for _, name in _archive.bundle_members(["survey.v2"], with_rendered=False)}

        assert names == {"drafts/survey.v2.md", "review/survey.v2.provenance.md"}

    def test_a_file_in_review_that_is_not_a_report_is_still_matched_by_topic(
        self, draft, isolated_config
    ):
        """Not everything under `content/review/` is `<stem>.<aid>.<ext>`.
        `render_output._copy_local_images` copies a report's images in
        beside it, so the aid-suffix strip has to leave a name it does not
        recognise alone rather than mangling it -- the file is still that
        topic's, and a bundle that dropped it would leave a `.tex` that no
        longer compiles."""
        directory = self._review_reports()
        (directory / "figure.png").write_bytes(b"\x89PNG")

        names = {
            name for _, name in _archive.bundle_members(["dt-for-engineers"], with_rendered=True)
        }

        assert "review/dt-for-engineers/figure.png" in names

    def test_a_name_selects_one_drafts_reports(self, draft, isolated_config):
        """A report's name carries the aid as well as the draft's stem
        (`survey.provenance.md`), so matching has to strip both suffixes
        to see the draft named `dt-for-engineers/survey`."""
        self._review_reports()
        self._review_reports(topic="unrelated-topic")
        names = {
            name
            for _, name in _archive.bundle_members(["dt-for-engineers/survey"], with_rendered=False)
        }
        assert "review/dt-for-engineers/survey.provenance.md" in names
        assert not any("unrelated-topic" in name for name in names)

    def test_exporting_nothing_is_an_error_rather_than_an_empty_archive(self, isolated_config):
        with pytest.raises(dossier.DossierError, match="Nothing to export"):
            _archive.export([], Path("out.tar.gz"))

    def test_writes_an_archive(self, draft, tmp_path):
        dossier.init(draft, "survey")
        out, count = _archive.export([], tmp_path / "bundle.tar.gz")
        assert out.is_file()
        assert count >= 2
        with tarfile.open(out) as tar:
            assert "drafts/dt-for-engineers/survey.md" in tar.getnames()


class TestRestore:
    @pytest.fixture
    def bundle(self, draft, tmp_path):
        dossier.init(draft, "survey")
        out, _ = _archive.export([], tmp_path / "bundle.tar.gz")
        return out

    def test_is_a_dry_run_by_default(self, bundle, draft):
        draft.unlink()
        plan = _archive.restore(bundle)
        assert not plan.performed
        assert not draft.exists()
        assert draft in plan.new

    def test_force_writes_the_files_back(self, bundle, draft):
        target = dossier.dossier_dir(draft)
        draft.unlink()
        (target / "scope.md").unlink()
        plan = _archive.restore(bundle, force=True)
        assert plan.performed
        assert draft.is_file()
        assert (target / "scope.md").is_file()

    def test_a_bundle_carrying_review_reports_round_trips(self, draft, tmp_path):
        """`bundle_members` gained a `review/` root; `ARCHIVE_ROOTS` is the
        allowlist `restore` checks members against, and `_checked_members`
        refuses the *whole* archive on an unlisted root. Miss one and
        export/restore stops being a round trip -- not by dropping a file,
        but by producing a bundle that cannot be restored at all."""
        dossier.init(draft, "survey")
        report = config.REVIEW_DIR / "dt-for-engineers" / "survey.provenance.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# provenance\n")

        out, _ = _archive.export([], tmp_path / "bundle.tar.gz")
        report.unlink()

        plan = _archive.restore(out, force=True)

        assert plan.performed
        assert report.is_file()
        assert report.read_text() == "# provenance\n"

    def test_reports_which_files_it_would_overwrite(self, bundle, draft):
        plan = _archive.restore(bundle)
        assert draft in plan.overwrite
        assert not plan.new

    def test_round_trips_content_exactly(self, bundle, draft):
        original = draft.read_text()
        draft.write_text("# clobbered\n")
        _archive.restore(bundle, force=True)
        assert draft.read_text() == original

    def test_a_path_too_long_for_a_tar_header_round_trips(self, isolated_config, tmp_path):
        """`_checked_members` refuses anything that isn't a regular file or
        directory, which raises the question of whether the extended
        headers tar uses for a >100-character path survive that check.

        They do, and not by luck: Python's `tarfile` consumes GNU longname
        (`L`/`K`) and PAX (`x`/`g`) header blocks while reading and folds
        them into the member they describe, so `getmembers()` only ever
        yields the real entry. Pinned here rather than argued, because the
        failure it would cause -- `export` producing a bundle its own
        `restore` refuses -- is exactly the kind a backup tool must not
        have.
        """
        deep = config.DRAFTS_DIR / ("topic-" + "x" * 90) / ("sub-" + "y" * 90)
        deep.mkdir(parents=True)
        draft = deep / ("survey-" + "z" * 80 + ".md")
        draft.write_text("# A survey with an inconveniently long path\n")
        assert len(str(draft.relative_to(config.DRAFTS_DIR))) > 100

        dossier.init(draft, "survey")
        archive, _ = _archive.export([], tmp_path / "long.tar.gz")

        draft.unlink()
        plan = _archive.restore(archive, force=True)
        assert plan.performed
        assert draft.is_file()
        assert draft.read_text() == "# A survey with an inconveniently long path\n"
        assert (dossier.dossier_dir(draft) / "scope.md").is_file()

    def _archive_containing(self, tmp_path, name, payload=b"x"):
        archive = tmp_path / "hostile.tar.gz"
        member = tmp_path / "payload"
        member.write_bytes(payload)
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(member, arcname=name)
        return archive

    def test_refuses_a_member_that_escapes_the_content_directory(self, isolated_config, tmp_path):
        archive = self._archive_containing(tmp_path, "drafts/../../../etc/passwd")
        with pytest.raises(dossier.DossierError, match="escapes"):
            _archive.restore(archive, force=True)

    def test_refuses_an_absolute_member(self, isolated_config, tmp_path):
        archive = tmp_path / "abs.tar.gz"
        payload = tmp_path / "payload"
        payload.write_bytes(b"x")
        with tarfile.open(archive, "w:gz") as tar:
            info = tar.gettarinfo(payload, arcname="/etc/passwd")
            with payload.open("rb") as handle:
                tar.addfile(info, handle)
        with pytest.raises(dossier.DossierError, match="escapes|not under"):
            _archive.restore(archive, force=True)

    def test_refuses_a_member_outside_the_three_known_directories(self, isolated_config, tmp_path):
        archive = self._archive_containing(tmp_path, "ledger.sqlite")
        with pytest.raises(dossier.DossierError, match="not under"):
            _archive.restore(archive, force=True)

    def test_refuses_a_symlink_member(self, isolated_config, tmp_path):
        archive = tmp_path / "link.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo("drafts/evil.md")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
        with pytest.raises(dossier.DossierError, match="not a regular file"):
            _archive.restore(archive, force=True)

    def test_an_unsafe_member_blocks_the_whole_archive(self, isolated_config, tmp_path):
        archive = tmp_path / "mixed.tar.gz"
        good = tmp_path / "good.md"
        good.write_text("# fine\n")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(good, arcname="drafts/good.md")
            tar.add(good, arcname="../escape.md")
        with pytest.raises(dossier.DossierError):
            _archive.restore(archive, force=True)
        assert not (config.DRAFTS_DIR / "good.md").exists()


class TestCli:
    def test_init_then_status_then_sections(self, draft, capsys):
        assert dossier.main(["init", str(draft), "--genre", "survey"]) == 0
        assert dossier.main(["status", str(draft)]) == 0
        assert dossier.main(["sections", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "scope.md" in out
        assert "1. First" in out

    def test_status_without_a_dossier_exits_nonzero_with_the_fix(self, draft, capsys):
        assert dossier.main(["status", str(draft)]) == 1
        assert "init" in capsys.readouterr().out

    def test_status_without_a_ledger_still_exits_zero(self, draft, capsys):
        """The two "missing" cases are deliberately different exit codes,
        and docs/CLI.md documents the difference: no dossier is actionable
        ("run init"), no ledger just means one section of the report is
        unavailable. A machine with no corpus built must still be able to
        see what it has."""
        dossier.init(draft, "survey")
        assert dossier.main(["status", str(draft)]) == 0
        assert "unavailable" in capsys.readouterr().out

    def test_sections_on_a_missing_draft_exits_nonzero(self, isolated_config, capsys):
        assert dossier.main(["sections", "content/drafts/nope.md"]) == 1
        assert "No such draft" in capsys.readouterr().err

    def test_list_with_nothing_to_list(self, isolated_config, capsys):
        assert dossier.main(["list"]) == 0
        assert "No dossiers" in capsys.readouterr().out

    def test_export_then_restore_round_trip(self, draft, tmp_path, capsys):
        dossier.main(["init", str(draft), "--genre", "survey"])
        archive = tmp_path / "b.tar.gz"
        assert dossier.main(["export", "--out", str(archive)]) == 0
        draft.unlink()
        assert dossier.main(["restore", str(archive)]) == 0
        assert not draft.exists(), "a dry run must not write"
        assert "Would restore" in capsys.readouterr().out
        assert dossier.main(["restore", str(archive), "--force"]) == 0
        assert draft.is_file()

    def test_export_with_nothing_to_export_exits_nonzero(self, isolated_config, capsys):
        assert dossier.main(["export"]) == 1
        assert "Nothing to export" in capsys.readouterr().err

    def test_restore_of_a_missing_archive_exits_nonzero(self, isolated_config, capsys):
        assert dossier.main(["restore", "nope.tar.gz"]) == 1
        assert "No such archive" in capsys.readouterr().err

    def test_init_on_a_draft_outside_drafts_reports_the_rule(
        self, isolated_config, tmp_path, capsys
    ):
        stray = tmp_path / "stray.md"
        stray.write_text("# x\n")
        assert dossier.main(["init", str(stray), "--genre", "survey"]) == 1
        assert "not under" in capsys.readouterr().err


class TestRetrievalLog:
    def test_appends_a_row_and_totals_it(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 2400)
        dossier.log_retrieval(draft, "evidence", "digital twin", 1, 3, 2100)
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (2, 4500)

    def test_creates_the_file_for_a_dossier_that_predates_it(self, draft):
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "retrieval.md").unlink()
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (1, 100)

    def test_creates_the_dossier_when_a_skill_logs_before_init(self, draft):
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        assert (dossier.dossier_dir(draft) / "retrieval.md").is_file()

    def test_logging_before_init_leaves_init_free_to_write_the_rest(self, draft):
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        written = {path.name for path in dossier.init(draft, "survey")}
        assert "retrieval.md" not in written
        assert "scope.md" in written
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (1, 100)

    def test_a_pipe_in_the_query_does_not_break_the_row(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "twin | shadow", 15, 15, 100)
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (1, 100)

    def test_a_hand_edited_row_is_skipped_rather_than_fatal(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        path = dossier.dossier_dir(draft) / "retrieval.md"
        path.write_text(path.read_text() + "| 2026-08-06 | search | q | 15 | 15 | lots |\n")
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (1, 100)

    def test_no_log_means_no_cost(self, draft):
        dossier.init(draft, "survey")
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (0, 0)

    def test_status_reports_the_measured_cost(self, draft, capsys):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 2400)
        dossier.main(["status", str(draft)])
        out = capsys.readouterr().out
        assert "1 call(s) returned 2,400 characters" in out

    def test_status_says_nothing_about_retrieval_when_nothing_was_logged(self, draft, capsys):
        dossier.init(draft, "survey")
        dossier.main(["status", str(draft)])
        assert "call(s) returned" not in capsys.readouterr().out

    def test_a_stale_existence_check_cannot_truncate_another_writers_row(self, draft, monkeypatch):
        """Two writers reaching this function at once both see the file
        as absent; the one that loses the create must not destroy the
        winner's row.

        The window is real -- `--log` is a flag on the retrieval CLI, and
        a skill that dispatched parallel subagents could hand it to all
        of them. It is reproduced here by making the second call's
        existence check stale, which is exactly what the loser of the
        race observes, rather than by racing real processes and hoping
        the interleaving lands.
        """
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "retrieval.md").unlink()
        dossier.log_retrieval(draft, "search", "first", 15, 15, 100)

        # A nested context, not monkeypatch.undo(): undo() would also
        # revert `isolated_config`'s patches, which share this fixture.
        with monkeypatch.context() as stale:
            stale.setattr(Path, "exists", lambda self: False)
            dossier.log_retrieval(draft, "search", "second", 15, 15, 200)

        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (2, 300)

    def test_a_row_appended_while_the_file_is_being_created_is_not_overwritten(
        self, draft, monkeypatch
    ):
        """The narrower race inside the create itself.

        Making the file exist and filling it in are two steps, and a
        second writer can append between them -- it finds the file
        already there, so it skips creation and appends to what is still
        an empty file. If the creating writer then writes the template
        from offset 0, it writes straight over that row.

        Reproduced by injecting a second writer at the moment
        `retrieval.md` is first opened for writing, rather than by racing
        real processes: the window is microseconds wide and process
        startup dwarfs it, so eight concurrent processes hit it
        essentially never and prove nothing.
        """
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "retrieval.md"
        path.unlink()

        real_open, injected = Path.open, []

        def racing_open(self, mode="r", *args, **kwargs):
            handle = real_open(self, mode, *args, **kwargs)
            if self.name == "retrieval.md" and "r" not in mode and not injected:
                injected.append(True)
                with real_open(self, "a", encoding="utf-8") as other:
                    other.write("| 2026-08-08 | search | loser | 15 | 15 | 200 |\n")
            return handle

        with monkeypatch.context() as racing:
            racing.setattr(Path, "open", racing_open)
            dossier.log_retrieval(draft, "search", "winner", 15, 15, 100)

        assert injected, "the interleaving never happened, so nothing was tested"
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (2, 300)

    def test_status_flags_a_run_that_searched_and_recorded_nothing(self, draft, capsys):
        """The signature of a run that closed without transcribing what
        it found. Nothing else reports it: the packets are gone, and the
        draft itself looks finished."""
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 2400)
        dossier.main(["status", str(draft)])
        out = capsys.readouterr().out
        assert "searched and recorded nothing it found" in out

    def test_status_does_not_flag_a_dossier_that_recorded_what_it_found(self, draft, capsys):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 2400)
        evidence = dossier.dossier_dir(draft) / "evidence.md"
        evidence.write_text(evidence.read_text() + "\n## ferko_architecting_2022\n")
        dossier.main(["status", str(draft)])
        out = capsys.readouterr().out
        assert "1 kept, 0 rejected" in out
        assert "searched and recorded nothing" not in out

    def test_a_newline_in_the_query_does_not_split_the_row(self, draft):
        """`retrieval_cost` reads rows positionally, so a query carrying a
        newline would not error -- it would quietly become two rows, one
        of which parses and one of which doesn't."""
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin\narchitecture", 15, 15, 100)
        text = (dossier.dossier_dir(draft) / "retrieval.md").read_text()
        assert "digital twin architecture" in text
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (1, 100)

    def test_tabs_and_carriage_returns_are_flattened_too(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "twin\tshadow\r\nmodel", 15, 15, 100)
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (1, 100)

    def test_a_scoped_call_records_its_collection(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100, collection="Digital twins")
        text = (dossier.dossier_dir(draft) / "retrieval.md").read_text()
        assert "| Digital twins |" in text

    def test_a_row_written_before_the_collection_column_still_parses(self, draft):
        """A six-cell row -- what every `retrieval.md` on disk before #254
        looks like -- must keep costing exactly what it always has."""
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "retrieval.md"
        path.write_text(path.read_text() + "| 2026-01-01 | search | q | 15 | 15 | 100 |\n")
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (1, 100)


class TestRevisionMarker:
    """`mark_revision` and `retrieval_cost_by_revision`.

    `retrieval.md` rows carry only a date, so two revisions logged on the
    same day are otherwise indistinguishable -- that is the gap this
    machinery closes, and it is the thing worth testing directly rather
    than through `status`'s printed text.
    """

    def test_calls_before_any_marker_are_the_initial_draft_segment(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert segments == [_retrieval.RevisionCost("initial draft", 1, 100)]

    def test_a_marker_starts_a_new_segment(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q1", 15, 15, 100)
        _retrieval.mark_revision(draft, "shorten intro")
        dossier.log_retrieval(draft, "search", "q2", 15, 15, 200)
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert segments == [
            _retrieval.RevisionCost("initial draft", 1, 100),
            _retrieval.RevisionCost("shorten intro", 1, 200),
        ]

    def test_same_day_revisions_are_kept_separate(self, draft):
        """The whole point: a bare date column can't tell these apart,
        but two markers can, regardless of what `date.today()` writes."""
        dossier.init(draft, "survey")
        _retrieval.mark_revision(draft, "morning pass")
        dossier.log_retrieval(draft, "search", "q1", 15, 15, 100)
        _retrieval.mark_revision(draft, "afternoon pass")
        dossier.log_retrieval(draft, "search", "q2", 15, 15, 200)
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert [s.label for s in segments] == ["morning pass", "afternoon pass"]
        assert [s.chars for s in segments] == [100, 200]

    def test_an_unlabelled_marker_is_numbered_by_order(self, draft):
        dossier.init(draft, "survey")
        _retrieval.mark_revision(draft)
        dossier.log_retrieval(draft, "search", "q1", 15, 15, 100)
        _retrieval.mark_revision(draft)
        dossier.log_retrieval(draft, "search", "q2", 15, 15, 200)
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert [s.label for s in segments] == ["revision 1", "revision 2"]

    def test_a_revision_that_logged_nothing_is_dropped_not_zeroed(self, draft):
        """`mark-revision` costs nothing to call even when draft-reviser
        step 4 decides no search is needed -- that must not show up as a
        reported zero-cost revision cluttering the breakdown."""
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q1", 15, 15, 100)
        _retrieval.mark_revision(draft, "no search needed")
        _retrieval.mark_revision(draft, "this one searched")
        dossier.log_retrieval(draft, "search", "q2", 15, 15, 200)
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert [s.label for s in segments] == ["initial draft", "this one searched"]

    def test_marker_numbering_stays_stable_across_a_dropped_revision(self, draft):
        """The second *displayed* segment is still called "revision 2",
        not "revision 1" renumbered after the empty one between them was
        dropped -- numbering tracks marker order, not display order."""
        dossier.init(draft, "survey")
        _retrieval.mark_revision(draft)
        dossier.log_retrieval(draft, "search", "q1", 15, 15, 100)
        _retrieval.mark_revision(draft)  # logged nothing, dropped below
        _retrieval.mark_revision(draft)
        dossier.log_retrieval(draft, "search", "q2", 15, 15, 200)
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert [s.label for s in segments] == ["revision 1", "revision 3"]

    def test_no_markers_at_all_is_one_initial_draft_segment(self, draft):
        """A dossier revised before this existed, or without
        draft-reviser's loop calling it -- must not error and must not
        silently drop the only retrieval this draft has."""
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        dossier.log_retrieval(draft, "evidence", "q", 1, 3, 50)
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert segments == [_retrieval.RevisionCost("initial draft", 2, 150)]

    def test_a_trailing_marker_with_nothing_after_it_is_dropped(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        _retrieval.mark_revision(draft, "just started")
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert [s.label for s in segments] == ["initial draft"]

    def test_marker_rows_are_excluded_from_retrieval_cost(self, draft):
        """A marker records zero retrieval work by construction; counting
        it as a call would inflate the aggregate by one per revision."""
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        _retrieval.mark_revision(draft, "pass two")
        assert dossier.retrieval_cost(dossier.dossier_dir(draft)) == (1, 100)

    def test_creates_the_dossier_when_called_before_init(self, draft):
        _retrieval.mark_revision(draft, "early")
        assert (dossier.dossier_dir(draft) / "retrieval.md").is_file()

    def test_a_pipe_in_the_label_does_not_break_the_row(self, draft):
        """Escaped the same way `log_retrieval` escapes a query -- the
        row must still parse to six cells and split into its own
        segment, not merge with the next one -- and unescaped back on
        the way out, so `dossier status` prints what the user wrote
        rather than the markdown-safe form."""
        dossier.init(draft, "survey")
        _retrieval.mark_revision(draft, "shorten | tighten")
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        assert len(segments) == 1
        assert segments[0].label == "shorten | tighten"

    def test_status_prints_the_breakdown_once_there_is_more_than_one_segment(self, draft, capsys):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q1", 15, 15, 100)
        _retrieval.mark_revision(draft, "shorten intro")
        dossier.log_retrieval(draft, "search", "q2", 15, 15, 200)
        dossier.main(["status", str(draft)])
        out = capsys.readouterr().out
        assert "by revision:" in out
        assert "initial draft" in out
        assert "shorten intro" in out
        assert "1 call(s), 100 characters" in out
        assert "1 call(s), 200 characters" in out

    def test_status_omits_the_breakdown_with_only_one_segment(self, draft, capsys):
        """One segment would just repeat the total line under a
        different label -- not worth the extra output."""
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q", 15, 15, 100)
        dossier.main(["status", str(draft)])
        out = capsys.readouterr().out
        assert "by revision:" not in out

    def test_cli_mark_revision_writes_a_row(self, draft, capsys):
        dossier.init(draft, "survey")
        assert dossier.main(["mark-revision", str(draft), "--label", "cli pass"]) == 0
        segments = _retrieval.retrieval_cost_by_revision(dossier.dossier_dir(draft))
        # No calls logged yet, so the marker alone produces no segment --
        # confirmed via the row itself instead.
        assert segments == []
        text = (dossier.dossier_dir(draft) / "retrieval.md").read_text()
        assert "| revision | cli pass | 0 | 0 | 0 |" in text
        assert "cli pass" in capsys.readouterr().out

    def test_status_lifetime_totals_match_retrieval_cost(self, draft):
        """`status()` derives its lifetime totals from
        `retrieval_cost_by_revision`'s segments rather than parsing
        `retrieval.md` a second time via `retrieval_cost` -- this pins
        the two to agree regardless of which one changes first."""
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "q1", 15, 15, 100)
        _retrieval.mark_revision(draft, "shorten intro")
        dossier.log_retrieval(draft, "search", "q2", 15, 15, 200)
        _retrieval.mark_revision(draft, "no search needed")  # empty, dropped

        report = _status.status(draft)
        calls, chars = dossier.retrieval_cost(dossier.dossier_dir(draft))
        assert (report.retrieval_calls, report.retrieval_chars) == (calls, chars) == (2, 300)


# ---------------------------------------------------------------------
# Corpus drift across every dossier (`status --all`)
# ---------------------------------------------------------------------


def _seed_corpus(entries):
    """A ledger holding these citekeys, each with a real parsed text file.

    `_seed_ledger` above is enough for the fingerprint tests, which only
    need citekeys to exist. Query matching needs the text those citekeys
    rank against, so this writes `content/parsed/<citekey>.txt` and points
    the ledger's `parsed_path` at it -- the same shape `sync` produces.

    An entry is `(citekey, title, body)`, or `(citekey, title, body,
    collections)` for a drift-scoping test that needs a citekey inside or
    outside a Zotero collection -- `collections` a tuple of paths, stored
    the same way `chitragupta.ledger` stores them (JSON, or NULL for none).
    """
    import json

    from chitragupta import ledger

    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    con = ledger.connect()
    try:
        for entry in entries:
            citekey, title, body = entry[:3]
            collections = entry[3] if len(entry) > 3 else ()
            parsed = config.PARSED_DIR / f"{citekey}.txt"
            parsed.write_text(body, encoding="utf-8")
            con.execute(
                "INSERT INTO items (citekey, title, parsed_path, status, last_synced, "
                "collections) VALUES (?, ?, ?, 'parsed', '2026-01-01', ?)",
                (
                    citekey,
                    title,
                    str(parsed),
                    json.dumps(list(collections)) if collections else None,
                ),
            )
        con.commit()
    finally:
        con.close()


@pytest.fixture
def grounded(draft):
    """A dossier that cites one paper, rejected another, and logged the
    query that found them -- the state every drift finding is computed
    against."""
    dossier.init(draft, "survey")
    target = dossier.dossier_dir(draft)
    (target / "evidence.md").write_text(
        "# Kept evidence\n\n## `kept_paper_2024`\n\nWhy it was kept.\n"
    )
    (target / "rejected.md").write_text(
        "# Rejected candidates\n\n| citekey | query that surfaced it | why rejected |\n"
        "|---|---|---|\n| `turned_down_2023` | digital twin | off topic |\n"
    )
    (target / "sections.md").write_text(
        "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
        "| 1. First | `kept_paper_2024` |\n"
    )
    dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 2400)
    return target


class TestRecordedQueries:
    def test_reads_the_queries_out_of_retrieval_md(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 100)
        dossier.log_retrieval(draft, "evidence", "co-simulation", 2, 2, 100)
        assert _retrieval.recorded_queries(dossier.dossier_dir(draft)) == [
            "digital twin",
            "co-simulation",
        ]

    def test_a_repeated_query_is_reported_once_in_first_seen_order(self, draft):
        dossier.init(draft, "survey")
        for query in ("twin", "shadow", "twin"):
            dossier.log_retrieval(draft, "search", query, 5, 5, 100)
        assert _retrieval.recorded_queries(dossier.dossier_dir(draft)) == ["twin", "shadow"]

    def test_an_escaped_pipe_is_restored(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "twin | shadow", 5, 5, 100)
        assert _retrieval.recorded_queries(dossier.dossier_dir(draft)) == ["twin | shadow"]

    def test_a_hand_edited_row_that_does_not_parse_is_skipped(self, draft):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "retrieval.md"
        with path.open("a", encoding="utf-8") as handle:
            handle.write("| 2026-01-01 | search | only three cells |\n")
        dossier.log_retrieval(draft, "search", "real query", 5, 5, 100)
        assert _retrieval.recorded_queries(dossier.dossier_dir(draft)) == ["real query"]

    def test_an_empty_query_cell_is_not_a_query(self, draft):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "retrieval.md"
        with path.open("a", encoding="utf-8") as handle:
            handle.write("| 2026-01-01 | search |  | 5 | 5 | 100 |\n")
        assert _retrieval.recorded_queries(dossier.dossier_dir(draft)) == []

    def test_no_retrieval_file_means_no_queries(self, draft):
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "retrieval.md").unlink()
        assert _retrieval.recorded_queries(dossier.dossier_dir(draft)) == []

    def test_a_revision_label_is_never_reported_as_a_query(self, draft):
        """A marker's third cell holds `mark_revision`'s `--label` text,
        not a query -- without this exclusion it would be ranked against
        the corpus as if someone had searched for it (both here and in
        every caller: corpus-reviser's sub-theme list, `status --all`'s
        candidate matching)."""
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 100)
        _retrieval.mark_revision(draft, "shorten the introduction")
        dossier.log_retrieval(draft, "search", "co-simulation", 2, 2, 100)
        assert _retrieval.recorded_queries(dossier.dossier_dir(draft)) == [
            "digital twin",
            "co-simulation",
        ]

    def test_an_unlabelled_revision_marker_contributes_no_empty_query(self, draft):
        dossier.init(draft, "survey")
        _retrieval.mark_revision(draft)
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 100)
        assert _retrieval.recorded_queries(dossier.dossier_dir(draft)) == ["digital twin"]


class TestRecordedQueriesWithCollection:
    """`recorded_queries`'s sibling (#254): pairs each query with the
    collection its call actually ran against, so a caller can honour the
    scope instead of losing it the way `recorded_queries` alone does."""

    def test_an_unscoped_call_pairs_with_an_empty_collection(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 100)
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == [
            ("digital twin", ""),
        ]

    def test_a_scoped_call_pairs_with_its_collection(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(
            draft, "search", "digital twin", 15, 15, 100, collection="Digital twins"
        )
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == [
            ("digital twin", "Digital twins"),
        ]

    def test_the_same_query_scoped_and_unscoped_are_two_distinct_pairs(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "twin", 15, 15, 100)
        dossier.log_retrieval(draft, "search", "twin", 15, 15, 100, collection="Digital twins")
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == [
            ("twin", ""),
            ("twin", "Digital twins"),
        ]

    def test_a_repeated_scoped_pair_is_reported_once(self, draft):
        dossier.init(draft, "survey")
        for _ in range(2):
            dossier.log_retrieval(draft, "search", "twin", 15, 15, 100, collection="Digital twins")
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == [
            ("twin", "Digital twins"),
        ]

    def test_a_row_written_before_the_collection_column_pairs_with_empty(self, draft):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "retrieval.md"
        path.write_text(path.read_text() + "| 2026-01-01 | search | old query | 15 | 15 | 100 |\n")
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == [
            ("old query", ""),
        ]

    def test_a_revision_marker_contributes_no_pair(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 100)
        _retrieval.mark_revision(draft, "shorten the introduction")
        dossier.log_retrieval(draft, "search", "co-simulation", 2, 2, 100)
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == [
            ("digital twin", ""),
            ("co-simulation", ""),
        ]

    def test_no_retrieval_file_means_no_pairs(self, draft):
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "retrieval.md").unlink()
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == []

    def test_an_empty_query_cell_contributes_no_pair(self, draft):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "retrieval.md"
        with path.open("a", encoding="utf-8") as handle:
            handle.write("| 2026-01-01 | search |  | 5 | 5 | 100 | Digital twins |\n")
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == []


class TestSectionCitekeys:
    def test_maps_a_citekey_to_the_sections_citing_it(self, grounded):
        (grounded / "sections.md").write_text(
            "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
            "| 1. First | `a_one_2024`, `b_two_2024` |\n"
            "| 2. Second | `b_two_2024` |\n"
        )
        assert _citekeys.section_citekeys(grounded) == {
            "a_one_2024": ["1. First"],
            "b_two_2024": ["1. First", "2. Second"],
        }

    def test_a_missing_sections_file_maps_nothing(self, draft):
        assert _citekeys.section_citekeys(dossier.dossier_dir(draft)) == {}

    def test_a_row_with_no_citekeys_contributes_nothing(self, grounded):
        (grounded / "sections.md").write_text(
            "# Sections\n\n| section | citekeys |\n|---|---|\n| 1. First | none yet |\n"
        )
        assert _citekeys.section_citekeys(grounded) == {}

    def test_the_at_form_a_draft_uses_is_read_too(self, grounded):
        """`@key` as well as `` `key` ``.

        The templates show neither, and the skills wrote `sections.md`
        the way a draft cites -- so the shipped example dossier is all
        `@key`, and reading only the backticked form silently lost every
        section mapping it had.
        """
        (grounded / "sections.md").write_text(
            "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
            "| 1. First | @a_one_2024, @b_two_2024 |\n"
            "| 2. Second | `b_two_2024` |\n"
        )
        assert _citekeys.section_citekeys(grounded) == {
            "a_one_2024": ["1. First"],
            "b_two_2024": ["1. First", "2. Second"],
        }

    def test_an_at_word_with_no_separator_is_not_a_citekey(self, grounded):
        """The separator requirement is what keeps prose out, and it has
        to keep doing so now that a bare `@` opens a match."""
        (grounded / "sections.md").write_text(
            "# Sections\n\n| section | citekeys |\n|---|---|\n| 1. First | ask @someone, see @2 |\n"
        )
        assert _citekeys.section_citekeys(grounded) == {}


class TestDrift:
    def test_a_cited_key_that_left_the_ledger_is_reported_with_its_sections(self, grounded):
        _seed_corpus([("other_paper_2025", "Other", "unrelated text")])
        report = _drift.drift(grounded)
        assert report.missing == {"kept_paper_2024": ["1. First"]}

    def test_a_rejected_key_leaving_the_ledger_is_not_a_finding(self, grounded):
        _seed_corpus([("kept_paper_2024", "Kept", "text")])
        report = _drift.drift(grounded)
        assert report.missing == {}

    def test_a_new_paper_matching_a_recorded_query_is_a_candidate(self, grounded):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin architecture"),
                ("fresh_twin_2026", "A fresh twin paper", "digital twin co-simulation study"),
                ("unrelated_2026", "Baking bread", "sourdough starter hydration"),
            ]
        )
        report = _drift.drift(grounded)
        assert [c.citekey for c in report.candidates] == ["fresh_twin_2026"]
        assert report.candidates[0].queries == ["digital twin"]

    def test_a_paper_already_rejected_is_never_offered_again(self, grounded):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("turned_down_2023", "Turned down", "digital twin everywhere"),
            ]
        )
        report = _drift.drift(grounded)
        assert [c.citekey for c in report.candidates] == []

    def test_the_candidate_carries_why_it_was_reachable(self, grounded):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("fresh_twin_2026", "Fresh", "digital twin"),
            ]
        )
        report = _drift.drift(grounded)
        assert report.candidates[0].title == "Fresh"

    def test_no_ledger_reports_unavailable_rather_than_raising(self, grounded):
        report = _drift.drift(grounded)
        assert report.corpus_available is False
        assert report.missing == {}
        assert report.candidates == []

    def test_no_recorded_fingerprint_still_reports_missing_citations(self, grounded):
        """The fingerprint answers "did the corpus move"; a cited key
        vanishing is a finding whether or not the dossier recorded one."""
        (grounded / "scope.md").write_text("# Scope\n\n- genre: survey\n")
        _seed_corpus([("other_paper_2025", "Other", "text")])
        report = _drift.drift(grounded)
        assert report.recorded is None
        assert report.missing == {"kept_paper_2024": ["1. First"]}

    def test_an_empty_dossier_directory_is_reported_not_refused(self, draft):
        target = dossier.dossier_dir(draft)
        target.mkdir(parents=True)
        _seed_corpus([("any_paper_2025", "Any", "text")])
        report = _drift.drift(target)
        assert report.missing == {}
        assert report.candidates == []

    def test_a_dossier_whose_draft_is_gone_is_still_reported(self, grounded, draft):
        draft.unlink()
        _seed_corpus([("kept_paper_2024", "Kept", "text")])
        report = _drift.drift(grounded)
        assert report.draft is None


class TestDriftCollectionScoping:
    """#254: a query scoped with `--collection` must rank candidates over
    that shelf only, not the whole corpus -- the false-drift bug a
    collection-scoped draft hit once #229 made scoping reachable."""

    def test_a_scoped_query_does_not_surface_a_candidate_outside_its_collection(self, draft):
        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        dossier.log_retrieval(
            draft, "search", "digital twin", 15, 15, 100, collection="Digital twins"
        )
        _seed_corpus(
            [
                ("in_shelf_2024", "In shelf", "digital twin architecture", ("Digital twins",)),
                (
                    "outside_shelf_2025",
                    "Outside shelf",
                    "digital twin simulation",
                    ("Other shelf",),
                ),
            ]
        )
        report = _drift.drift(target)
        assert [c.citekey for c in report.candidates] == ["in_shelf_2024"]

    def test_a_subcollection_still_matches_its_parent(self, draft):
        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        dossier.log_retrieval(
            draft, "search", "digital twin", 15, 15, 100, collection="Digital twins"
        )
        _seed_corpus(
            [
                (
                    "nested_2024",
                    "Nested",
                    "digital twin architecture",
                    ("Digital twins > Modelling",),
                ),
            ]
        )
        report = _drift.drift(target)
        assert [c.citekey for c in report.candidates] == ["nested_2024"]

    def test_an_unscoped_query_still_ranks_over_the_whole_corpus(self, draft):
        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 100)
        _seed_corpus(
            [
                ("in_shelf_2024", "In shelf", "digital twin architecture", ("Digital twins",)),
                (
                    "outside_shelf_2025",
                    "Outside shelf",
                    "digital twin simulation",
                    ("Other shelf",),
                ),
            ]
        )
        report = _drift.drift(target)
        assert {c.citekey for c in report.candidates} == {
            "in_shelf_2024",
            "outside_shelf_2025",
        }

    def test_a_row_predating_the_collection_column_behaves_as_corpus_wide(self, draft):
        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        path = target / "retrieval.md"
        path.write_text(
            path.read_text() + "| 2026-01-01 | search | digital twin | 15 | 15 | 100 |\n"
        )
        _seed_corpus(
            [
                ("in_shelf_2024", "In shelf", "digital twin architecture", ("Digital twins",)),
                (
                    "outside_shelf_2025",
                    "Outside shelf",
                    "digital twin simulation",
                    ("Other shelf",),
                ),
            ]
        )
        report = _drift.drift(target)
        assert {c.citekey for c in report.candidates} == {
            "in_shelf_2024",
            "outside_shelf_2025",
        }


class TestEphemeralIndex:
    """The drift scan must leave the corpus layer exactly as it found it.

    `chitragupta.retrieval.search()` cannot be called here: it goes through
    `ledger.connect()`, which creates `content/`, executes the schema and
    runs migrations, and through `_load_index`, which rewrites
    `retrieval_index.json` whenever a fingerprint moved -- both of which a
    read-only report must not do.
    """

    def test_no_retrieval_index_is_written(self, grounded):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("fresh_twin_2026", "Fresh", "digital twin"),
            ]
        )
        _drift.drift(grounded)
        assert not config.RETRIEVAL_INDEX_PATH.exists()

    def test_an_existing_retrieval_index_is_left_byte_for_byte(self, grounded):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("fresh_twin_2026", "Fresh", "digital twin"),
            ]
        )
        config.RETRIEVAL_INDEX_PATH.write_text('{"version": 1, "items": {}}')
        before = config.RETRIEVAL_INDEX_PATH.read_bytes()
        _drift.drift(grounded)
        assert config.RETRIEVAL_INDEX_PATH.read_bytes() == before

    def test_a_warm_cache_entry_is_reused_rather_than_re_tokenized(self, grounded):
        """Seeding the on-disk cache with a *wrong* term count for a paper
        proves the cache was read: the match can only come from the cache,
        since the parsed text says something else entirely."""
        _seed_corpus([("cached_paper_2026", "Cached", "sourdough starter")])
        from chitragupta import retrieval_cache

        con = __import__("sqlite3").connect(config.LEDGER_PATH)
        con.row_factory = __import__("sqlite3").Row
        (row,) = con.execute("SELECT * FROM items").fetchall()
        fingerprint = retrieval_cache._fingerprint(row)
        con.close()
        config.RETRIEVAL_INDEX_PATH.write_text(
            __import__("json").dumps(
                {
                    "version": 1,
                    "items": {
                        "cached_paper_2026": {
                            "fingerprint": fingerprint,
                            "length": 2,
                            "term_freqs": {"digital": 1, "twin": 1},
                        }
                    },
                }
            )
        )
        report = _drift.drift(grounded)
        assert [c.citekey for c in report.candidates] == ["cached_paper_2026"]

    def test_a_stale_cache_entry_is_re_tokenized_in_memory(self, grounded):
        _seed_corpus([("fresh_twin_2026", "Fresh", "digital twin")])
        config.RETRIEVAL_INDEX_PATH.write_text(
            __import__("json").dumps(
                {
                    "version": 1,
                    "items": {
                        "fresh_twin_2026": {
                            "fingerprint": ["stale"],
                            "length": 2,
                            "term_freqs": {"sourdough": 1},
                        }
                    },
                }
            )
        )
        report = _drift.drift(grounded)
        assert [c.citekey for c in report.candidates] == ["fresh_twin_2026"]

    def test_the_ledger_is_never_created_by_a_scan(self, grounded):
        _drift.drift(grounded)
        assert not config.LEDGER_PATH.exists()


class TestDriftAll:
    def test_reports_every_dossier(self, isolated_config):
        for name in ("alpha", "beta"):
            path = config.DRAFTS_DIR / f"{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# x\n")
            dossier.init(path, "survey")
        _seed_corpus([("any_paper_2025", "Any", "text")])
        assert [r.name for r in dossier.drift_all()] == ["alpha", "beta"]

    def test_no_dossiers_is_an_empty_report_not_an_error(self, isolated_config):
        assert dossier.drift_all() == []

    def test_the_ledger_is_read_once_for_the_whole_sweep(self, isolated_config, monkeypatch):
        """Per-dossier ledger reads made `--all` cost O(dossiers) full
        table scans plus one corpus tokenization each."""
        for name in ("alpha", "beta", "gamma"):
            path = config.DRAFTS_DIR / f"{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# x\n")
            dossier.init(path, "survey")
            dossier.log_retrieval(path, "search", "digital twin", 5, 5, 100)
        _seed_corpus([("fresh_twin_2026", "Fresh", "digital twin")])

        calls = []
        # Patched on _drift, not on dossier: drift_all() calls _corpus_rows()
        # through _drift.py's own `from chitragupta.dossier import _corpus_rows`,
        # which is its own name binding to the same function object --
        # patching chitragupta.dossier's copy doesn't reach it (#219).
        real = _drift._corpus_rows
        monkeypatch.setattr(_drift, "_corpus_rows", lambda: calls.append(1) or real())
        dossier.drift_all()
        assert len(calls) == 1


class TestStatusAllCLI:
    def test_exits_zero_and_names_the_findings(self, grounded, capsys):
        _seed_corpus(
            [
                ("other_paper_2025", "Other", "text"),
                ("fresh_twin_2026", "A fresh twin", "digital twin co-simulation"),
            ]
        )
        assert dossier.main(["status", "--all"]) == 0
        out = capsys.readouterr().out
        assert "kept_paper_2024" in out  # cited, now gone
        assert "fresh_twin_2026" in out  # new, matches a logged query
        assert "1. First" in out  # the section to edit

    def test_exits_zero_with_no_dossiers_at_all(self, isolated_config, capsys):
        assert dossier.main(["status", "--all"]) == 0
        assert "No dossiers" in capsys.readouterr().out

    def test_exits_zero_with_no_ledger(self, grounded, capsys):
        assert dossier.main(["status", "--all"]) == 0
        assert "unavailable" in capsys.readouterr().out

    def test_an_uncheckable_dossier_is_not_reported_as_current(self, grounded, capsys):
        """No findings is not the same as nothing to find. Calling an
        unchecked dossier current is the one way this could mislead."""
        assert dossier.main(["status", "--all"]) == 0
        out = capsys.readouterr().out
        assert "could not be checked" in out
        assert "drift is unknown" in out
        assert "Every dossier is current" not in out

    def test_a_mixed_sweep_reports_both_the_drift_and_the_unknown(self, grounded, capsys):
        """One dossier under a readable ledger, one that predates it --
        the summary has to carry both facts, not just the louder one."""
        stray = config.DOSSIERS_DIR / "orphan"
        stray.mkdir(parents=True)
        (stray / "scope.md").write_text("# Scope\n")
        _seed_corpus([("other_paper_2025", "Other", "text")])
        assert dossier.main(["status", "--all"]) == 0
        out = capsys.readouterr().out
        assert "have drifted" in out
        assert "could not be checked" not in out

    def test_a_clean_dossier_says_so(self, grounded, capsys):
        _seed_corpus([("kept_paper_2024", "Kept", "sourdough bread")])
        assert dossier.main(["status", "--all"]) == 0
        assert "no drift" in capsys.readouterr().out.lower()

    def test_json_is_machine_readable_for_the_reviser(self, grounded, capsys):
        _seed_corpus(
            [
                ("other_paper_2025", "Other", "text"),
                ("fresh_twin_2026", "A fresh twin", "digital twin co-simulation"),
            ]
        )
        assert dossier.main(["status", "--all", "--json"]) == 0
        payload = __import__("json").loads(capsys.readouterr().out)
        (entry,) = payload["dossiers"]
        assert entry["missing"] == {"kept_paper_2024": ["1. First"]}
        assert entry["candidates"][0]["citekey"] == "fresh_twin_2026"
        assert entry["candidates"][0]["queries"] == ["digital twin"]

    def test_json_for_one_draft_has_the_same_shape(self, grounded, draft, capsys):
        _seed_corpus([("fresh_twin_2026", "Fresh", "digital twin")])
        assert dossier.main(["status", str(draft), "--json"]) == 0
        payload = __import__("json").loads(capsys.readouterr().out)
        assert len(payload["dossiers"]) == 1

    def test_json_reports_a_missing_dossier_rather_than_exiting_1(self, draft, capsys):
        """`--json` returns before the `is_dir()` check the text path
        exits 1 on, so a draft with no dossier still produces an envelope
        and a 0. `draft-reviser` therefore has to branch on the payload
        rather than the status code -- pinned so the contract cannot
        change under it silently."""
        _seed_corpus([("fresh_twin_2026", "Fresh", "digital twin")])
        assert dossier.main(["status", str(draft), "--json"]) == 0
        (entry,) = __import__("json").loads(capsys.readouterr().out)["dossiers"]
        assert entry["missing"] == {}
        assert entry["candidates"] == []
        assert entry["recorded"] is None, "nothing on disk recorded a fingerprint"

    def test_a_draft_and_all_together_is_refused(self, draft, capsys):
        assert dossier.main(["status", str(draft), "--all"]) == 2
        assert "not both" in capsys.readouterr().err

    def test_neither_a_draft_nor_all_is_refused(self, isolated_config, capsys):
        assert dossier.main(["status"]) == 2
        assert "--all" in capsys.readouterr().err

    def test_a_dossier_whose_draft_is_gone_is_flagged(self, grounded, draft, capsys):
        draft.unlink()
        _seed_corpus([("kept_paper_2024", "Kept", "text")])
        dossier.main(["status", "--all"])
        assert "draft missing" in capsys.readouterr().out

    def test_the_candidate_list_is_capped_with_a_visible_remainder(self, grounded, capsys):
        _seed_corpus(
            [("kept_paper_2024", "Kept", "digital twin")]
            + [(f"fresh_{n}_2026", f"Fresh {n}", "digital twin study") for n in range(12)]
        )
        dossier.main(["status", "--all"])
        assert "more" in capsys.readouterr().out

    def test_a_missing_citekey_list_is_capped_too(self, grounded, capsys):
        (grounded / "sections.md").write_text(
            "# Sections\n\n| section | citekeys |\n|---|---|\n"
            + "".join(f"| S{n} | `gone_{n}_2024` |\n" for n in range(12))
        )
        _seed_corpus([("survivor_2026", "Survivor", "sourdough")])
        dossier.main(["status", "--all"])
        out = capsys.readouterr().out
        # 12 from sections.md, plus `kept_paper_2024` from evidence.md --
        # a citekey counts as cited from either file.
        assert "13 cited citekey(s) no longer in the ledger" in out
        assert "... and 3 more" in out

    def test_missing_citations_are_reported_without_any_candidates(self, grounded, capsys):
        """The two findings are independent: a draft can cite a paper that
        left without the corpus having gained anything it would want."""
        _seed_corpus([("survivor_2026", "Survivor", "sourdough bread")])
        dossier.main(["status", "--all"])
        out = capsys.readouterr().out
        assert "no longer in the ledger" in out
        assert "new candidate(s)" not in out


class TestDriftEdges:
    def test_a_sections_row_with_the_wrong_cell_count_is_skipped(self, grounded):
        (grounded / "sections.md").write_text(
            "# Sections\n\n| section | citekeys |\n|---|---|\n"
            "| 1. First | `kept_paper_2024` | stray fourth cell |\n"
            "| 2. Second | `also_kept_2024` |\n"
        )
        assert _citekeys.section_citekeys(grounded) == {"also_kept_2024": ["2. Second"]}

    def test_a_query_of_nothing_but_stopwords_ranks_nothing(self, grounded):
        """`_tokenize` drops stopwords, so "the and of" reduces to no terms
        at all -- scoring it would rank the whole corpus by an empty query."""
        (grounded / "retrieval.md").write_text(
            "# Retrieval calls\n\n| date | mode | query | asked | results | chars |\n"
            "|---|---|---|---|---|---|\n| 2026-01-01 | search | the and of | 5 | 5 | 100 |\n"
        )
        _seed_corpus([("kept_paper_2024", "Kept", "digital twin")])
        assert _drift.drift(grounded).candidates == []

    def test_a_dossier_outside_the_dossiers_dir_falls_back_to_its_name(self, tmp_path):
        assert dossier.dossier_name(tmp_path / "stray-dossier") == "stray-dossier"


class TestRejectedReasons:
    def test_maps_a_citekey_to_why_it_was_turned_down(self, grounded):
        assert _citekeys.rejected_reasons(grounded) == {"turned_down_2023": "off topic"}

    def test_a_row_with_the_wrong_cell_count_is_skipped(self, grounded):
        (grounded / "rejected.md").write_text(
            "# Rejected\n\n| citekey | query | why |\n|---|---|---|\n"
            "| `broken_2023` | q |\n| `good_2023` | q | a real reason |\n"
        )
        assert _citekeys.rejected_reasons(grounded) == {"good_2023": "a real reason"}

    def test_a_row_naming_no_citekey_contributes_nothing(self, grounded):
        (grounded / "rejected.md").write_text(
            "# Rejected\n\n| citekey | query | why |\n|---|---|---|\n| none yet | q | r |\n"
        )
        assert _citekeys.rejected_reasons(grounded) == {}

    def test_a_missing_file_maps_nothing(self, draft):
        assert _citekeys.rejected_reasons(dossier.dossier_dir(draft)) == {}


class TestReconsider:
    """A paper this draft already read and declined, which its queries
    still reach. Not drift -- it was declined against a corpus that
    contained it -- but the reason is what a re-grounding pass needs in
    order to decide whether the decision still holds."""

    def test_a_still_matching_rejection_is_offered_back_with_its_reason(self, grounded):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("turned_down_2023", "Turned down", "digital twin everywhere"),
            ]
        )
        (entry,) = _drift.drift(grounded).reconsider
        assert (entry.citekey, entry.reason) == ("turned_down_2023", "off topic")
        assert entry.queries == ["digital twin"]

    def test_a_rejection_the_queries_no_longer_reach_is_not_offered(self, grounded):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("turned_down_2023", "Turned down", "sourdough starter hydration"),
            ]
        )
        assert _drift.drift(grounded).reconsider == []

    def test_it_never_duplicates_a_candidate(self, grounded):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("turned_down_2023", "Turned down", "digital twin"),
                ("fresh_twin_2026", "Fresh", "digital twin"),
            ]
        )
        report = _drift.drift(grounded)
        assert [c.citekey for c in report.candidates] == ["fresh_twin_2026"]
        assert [r.citekey for r in report.reconsider] == ["turned_down_2023"]

    def test_a_cited_paper_is_never_offered_for_reconsideration(self, grounded):
        (grounded / "rejected.md").write_text(
            "# Rejected\n\n| citekey | query | why |\n|---|---|---|\n"
            "| `kept_paper_2024` | digital twin | a stale row, since kept |\n"
        )
        _seed_corpus([("kept_paper_2024", "Kept", "digital twin")])
        assert _drift.drift(grounded).reconsider == []

    def test_it_does_not_by_itself_make_a_dossier_drifted(self, grounded, capsys):
        """A rejection that still matches is true on every sweep forever.
        Counting it as drift would mark every dossier that ever declined a
        paper permanently stale, which is the signal this command exists
        to give."""
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("turned_down_2023", "Turned down", "digital twin"),
            ]
        )
        report = _drift.drift(grounded)
        assert report.reconsider
        assert report.clean
        assert dossier.main(["status", "--all"]) == 0
        out = capsys.readouterr().out
        assert "no drift" in out
        assert "turned_down_2023" not in out

    def test_it_is_printed_once_the_dossier_is_already_drifting(self, grounded, capsys):
        _seed_corpus(
            [
                ("turned_down_2023", "Turned down", "digital twin"),
                ("fresh_twin_2026", "Fresh", "digital twin"),
            ]
        )
        dossier.main(["status", "--all"])
        out = capsys.readouterr().out
        assert "turned_down_2023" in out
        assert "off topic" in out

    def test_json_always_carries_it_for_the_reviser(self, grounded, capsys):
        _seed_corpus(
            [
                ("kept_paper_2024", "Kept", "digital twin"),
                ("turned_down_2023", "Turned down", "digital twin"),
            ]
        )
        dossier.main(["status", "--all", "--json"])
        (entry,) = __import__("json").loads(capsys.readouterr().out)["dossiers"]
        assert entry["reconsider"] == [
            {
                "citekey": "turned_down_2023",
                "title": "Turned down",
                "queries": ["digital twin"],
                "reason": "off topic",
            }
        ]

    def test_the_reconsider_list_is_capped_with_a_visible_remainder(self, grounded, capsys):
        (grounded / "rejected.md").write_text(
            "# Rejected\n\n| citekey | query | why |\n|---|---|---|\n"
            + "".join(f"| `old_{n}_2023` | digital twin | thin |\n" for n in range(12))
        )
        _seed_corpus(
            [("fresh_twin_2026", "Fresh", "digital twin")]
            + [(f"old_{n}_2023", f"Old {n}", "digital twin study") for n in range(12)]
        )
        dossier.main(["status", "--all"])
        out = capsys.readouterr().out
        assert "12 previously rejected paper(s)" in out
        assert "... and 2 more" in out

    def test_the_trailer_does_not_contradict_the_reconsider_list(self, grounded, capsys):
        """ "nothing here was turned down before" is false the moment a
        reconsider list is on screen."""
        _seed_corpus(
            [
                ("turned_down_2023", "Turned down", "digital twin"),
                ("fresh_twin_2026", "Fresh", "digital twin"),
            ]
        )
        dossier.main(["status", "--all"])
        out = capsys.readouterr().out
        assert "turned down before" not in out
        assert "the reconsider list is" in out


# ---------------------------------------------------------------------
# The reporting CLI's own output
#
# `status`, `list`, `sections` and `restore` are read by a human deciding
# what to do next, and most of what they print is a branch: a dossier
# whose draft is gone, a file that was never created, a corpus that moved
# by more than fits on a screen. Those branches were reachable only
# through `main()`, so they went unexercised while the functions beneath
# them were fully covered -- which is the shape of gap that lets a report
# say something untrue without any test noticing.
# ---------------------------------------------------------------------


class TestPathsOutsideTheContentTree:
    def test_draft_name_of_a_draft_outside_drafts_falls_back_to_its_stem(
        self, isolated_config, tmp_path
    ):
        stray = tmp_path / "elsewhere.md"
        assert dossier.draft_name(stray) == "elsewhere"

    def test_find_draft_of_a_dossier_outside_dossiers_finds_nothing(
        self, isolated_config, tmp_path
    ):
        assert dossier.find_draft(tmp_path / "not-a-dossier") is None


class TestUnreadableLedger:
    def test_a_ledger_that_cannot_be_opened_reports_unavailable(self, isolated_config, monkeypatch):
        """`exists()` is not `openable()`. A directory where the ledger
        should be is the cheap way to prove the difference, and the scan
        has to survive it rather than raise into a report."""
        fake = config.CONTENT_DIR / "ledger.sqlite"
        fake.mkdir(parents=True)
        monkeypatch.setattr(config, "LEDGER_PATH", fake)
        assert dossier._corpus_rows() is None
        assert dossier.known_citekeys() is None


class TestInitCLI:
    def test_a_second_init_says_the_dossier_is_already_complete(self, draft, capsys):
        dossier.init(draft, "survey")
        assert dossier.main(["init", str(draft), "--genre", "survey"]) == 0
        assert "already complete" in capsys.readouterr().out

    def test_with_a_ledger_present_it_does_not_warn_about_drift_checks(self, draft, capsys):
        _seed_ledger(["talasila_composable_2025"])
        assert dossier.main(["init", str(draft), "--genre", "survey"]) == 0
        out = capsys.readouterr().out
        assert "created scope.md" in out
        assert "No ledger" not in out


class TestStatusCLIOutput:
    def test_a_dossier_that_outlived_its_draft_says_so(self, draft, capsys):
        dossier.init(draft, "survey")
        draft.unlink()
        assert dossier.main(["status", str(dossier.dossier_dir(draft))]) == 0
        assert "MISSING -- the dossier outlived its draft" in capsys.readouterr().out

    def test_a_file_that_was_never_created_reads_absent(self, draft, capsys):
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "steering.md").unlink()
        dossier.main(["status", str(draft)])
        assert "steering.md   absent" in capsys.readouterr().out.replace("  ", "  ")

    def test_the_kept_and_rejected_tally_appears_beside_the_retrieval_cost(
        self, grounded, draft, capsys
    ):
        dossier.main(["status", str(draft)])
        out = capsys.readouterr().out
        assert "1 call(s) returned" in out
        assert "1 kept, 1 rejected" in out

    def test_a_dossier_with_no_fingerprint_reports_the_current_corpus_instead(self, draft, capsys):
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "scope.md").write_text("# Scope\n\n- genre: survey\n")
        _seed_ledger(["a_paper_2024", "b_paper_2024"])
        assert dossier.main(["status", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "scope.md records no corpus fingerprint" in out
        assert "now: 2 citekeys" in out

    def test_an_unmoved_corpus_says_the_evidence_is_current(self, draft, capsys):
        _seed_ledger(["a_paper_2024"])
        dossier.init(draft, "survey")
        assert dossier.main(["status", str(draft)]) == 0
        assert "unchanged -- the dossier's evidence is current" in capsys.readouterr().out

    def test_a_moved_corpus_names_what_was_never_considered(self, draft, capsys):
        _seed_ledger(["a_paper_2024"])
        dossier.init(draft, "survey")
        _seed_ledger(["b_paper_2025", "c_paper_2025"])
        assert dossier.main(["status", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "CHANGED (+2 citekeys)" in out
        assert "b_paper_2025" in out
        assert "Drift is not itself a reason to redraft" in out

    def test_the_never_considered_list_is_capped_with_a_visible_remainder(self, draft, capsys):
        _seed_ledger(["a_paper_2024"])
        dossier.init(draft, "survey")
        _seed_ledger([f"new_{n}_paper_2025" for n in range(12)])
        dossier.main(["status", str(draft)])
        assert "... and 3 more" in capsys.readouterr().out


class TestSectionsCLIOutput:
    def test_a_draft_with_no_headings_says_so_and_exits_zero(self, isolated_config, capsys):
        config.DRAFTS_DIR.mkdir(parents=True)
        flat = config.DRAFTS_DIR / "prose.md"
        flat.write_text("just prose\nover two lines\n")
        assert dossier.main(["sections", str(flat)]) == 0
        assert "No headings in" in capsys.readouterr().out


class TestListCLIOutput:
    def test_it_names_every_dossier_and_flags_an_orphan(self, draft, capsys):
        dossier.init(draft, "survey")
        orphan = config.DRAFTS_DIR / "gone.md"
        orphan.write_text("# x\n")
        dossier.init(orphan, "survey")
        orphan.unlink()
        assert dossier.main(["list"]) == 0
        out = capsys.readouterr().out
        assert "dt-for-engineers/survey" in out
        assert "gone   (draft missing)" in out
        assert "2 dossier(s) under" in out


class TestRestoreCLIOutput:
    def test_an_archive_that_is_not_a_tarball_is_refused_without_a_traceback(
        self, isolated_config, tmp_path, capsys
    ):
        junk = tmp_path / "not-really.tar.gz"
        junk.write_bytes(b"this is not a gzip stream")
        assert dossier.main(["restore", str(junk)]) == 1
        assert "[error]" in capsys.readouterr().err

    def test_an_unsafe_member_is_refused_without_a_traceback(
        self, isolated_config, tmp_path, capsys
    ):
        archive = tmp_path / "hostile.tar.gz"
        payload = tmp_path / "payload.md"
        payload.write_text("x")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(payload, arcname="../escaped.md")
        assert dossier.main(["restore", str(archive)]) == 1
        assert "escapes the extraction directory" in capsys.readouterr().err

    def test_a_directory_member_is_carried_but_not_counted_as_a_file(
        self, isolated_config, tmp_path, capsys
    ):
        """`export` only ever adds files, but a hand-rolled or
        hand-edited bundle can carry directory entries, and the plan
        counts files -- an empty directory is not something to warn about
        overwriting."""
        archive = tmp_path / "with-dir.tar.gz"
        staging = tmp_path / "drafts"
        staging.mkdir()
        (staging / "one.md").write_text("# one\n")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(staging, arcname="drafts")
        assert dossier.main(["restore", str(archive)]) == 0
        out = capsys.readouterr().out
        assert "1 new file(s)" in out
        assert "Dry run" in out

    def test_the_overwrite_list_is_capped_with_a_visible_remainder(
        self, isolated_config, tmp_path, capsys
    ):
        config.DRAFTS_DIR.mkdir(parents=True)
        for n in range(12):
            (config.DRAFTS_DIR / f"draft{n}.md").write_text(f"# {n}\n")
        archive = tmp_path / "all.tar.gz"
        _archive.export([], archive)
        assert dossier.main(["restore", str(archive)]) == 0
        out = capsys.readouterr().out
        assert "12 existing file(s) would be OVERWRITTEN" in out
        assert "... and 2 more" in out

    def test_a_corpus_that_only_shrank_reports_drift_with_nothing_to_look_at(self, draft, capsys):
        """Drift is a digest comparison, so losing a paper moves it just
        as gaining one does -- but there is then nothing "never
        considered" to list, and the report must not print an empty
        heading."""
        _seed_ledger(["a_paper_2024", "b_paper_2024"])
        dossier.init(draft, "survey")
        (dossier.dossier_dir(draft) / "evidence.md").write_text(
            "# Kept evidence\n\n## `a_paper_2024`\n\nkept.\n\n## `b_paper_2024`\n\nkept.\n"
        )
        from chitragupta import ledger

        con = ledger.connect()
        con.execute("DELETE FROM items WHERE citekey = 'b_paper_2024'")
        con.commit()
        con.close()

        assert dossier.main(["status", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "CHANGED (-1 citekeys)" in out
        assert "appear nowhere in this dossier" not in out


# ---------------------------------------------------------------------
# Dispatching from the dossier (`brief`)
# ---------------------------------------------------------------------
#
# The reason these exist is a token bill rather than a correctness one.
# A skill that fans out to parallel section writers has to hand each one
# its source material, and pasting that material into the dispatch prompt
# spends it in the *output* pool -- the expensive direction. `brief` is
# what a dispatch prompt points at instead, so the tests that matter are
# the ones about resolving the right rows and about saying so loudly when
# there are none: a subagent handed a pointer to nothing writes an
# ungrounded section, and nothing downstream would report why.


def _fill_dossier(draft, evidence="", sections_rows=""):
    """A dossier whose evidence.md and sections.md hold real rows."""
    dossier.init(draft, "deep-research")
    target = dossier.dossier_dir(draft)
    if evidence:
        (target / "evidence.md").write_text(_create._EVIDENCE_TEMPLATE + evidence, encoding="utf-8")
    if sections_rows:
        (target / "sections.md").write_text(
            dossier._SECTIONS_TEMPLATE + sections_rows, encoding="utf-8"
        )
    return target


_TWO_BLOCKS = (
    "## `ferko_architecting_2022`\n\n"
    "- relevance: names the service layer this section is about\n"
    '- support: "a digital twin is composed of services"\n\n'
    "## `talasila_composable_2025`\n\n"
    "- relevance: the composition rule the section leans on\n"
    '- support: "twins compose from tool-agnostic parts"\n'
)


class TestEvidenceBlocks:
    def test_one_block_per_citekey_heading(self, draft):
        target = _fill_dossier(draft, evidence=_TWO_BLOCKS)
        blocks = _citekeys.evidence_blocks(target)
        assert list(blocks) == ["ferko_architecting_2022", "talasila_composable_2025"]
        assert "service layer" in blocks["ferko_architecting_2022"]
        assert "composition rule" not in blocks["ferko_architecting_2022"]

    def test_a_heading_that_carries_prose_still_keys_on_the_citekey(self, draft):
        target = _fill_dossier(
            draft, evidence="## `ferko_architecting_2022` -- kept for section 3\n\nbody\n"
        )
        assert "ferko_architecting_2022" in _citekeys.evidence_blocks(target)

    def test_a_heading_without_backticks_keys_on_its_text(self, draft):
        """A hand-written dossier is a supported input everywhere else
        here, and a block nobody can address is a block that gets
        re-retrieved."""
        target = _fill_dossier(draft, evidence="## ferko_architecting_2022\n\nbody\n")
        assert "ferko_architecting_2022" in _citekeys.evidence_blocks(target)

    def test_no_evidence_file_maps_nothing(self, draft):
        target = dossier.dossier_dir(draft)
        target.mkdir(parents=True)
        assert _citekeys.evidence_blocks(target) == {}


class TestCitekeysBySection:
    def test_reads_rows_in_order_and_skips_the_header(self, draft):
        target = _fill_dossier(
            draft,
            sections_rows=(
                "| 2. Failure modes | `ferko_architecting_2022`, `talasila_composable_2025` |\n"
                "| 3. Adoption | `zech_digital-twins-as--service_2024` |\n"
            ),
        )
        assert _citekeys.citekeys_by_section(target) == {
            "2. Failure modes": ["ferko_architecting_2022", "talasila_composable_2025"],
            "3. Adoption": ["zech_digital-twins-as--service_2024"],
        }

    def test_a_planned_section_with_no_citekeys_yet_is_still_a_section(self, draft):
        """Phase 4 writes the plan before Phase 5 dispatches, and a
        section it has not assigned evidence to must be reported as empty
        rather than as unknown -- the two want opposite fixes."""
        target = _fill_dossier(draft, sections_rows="| 4. Open questions |  |\n")
        assert _citekeys.citekeys_by_section(target) == {"4. Open questions": []}

    def test_no_sections_file_maps_nothing(self, draft):
        target = dossier.dossier_dir(draft)
        target.mkdir(parents=True)
        assert _citekeys.citekeys_by_section(target) == {}

    def test_a_hand_mangled_row_is_skipped_rather_than_fatal(self, draft):
        target = _fill_dossier(
            draft,
            sections_rows=(
                "| 2. Failure modes | `ferko_architecting_2022` |\n"
                "| 3. Adoption | `a_b_2024` | stray fourth cell |\n"
            ),
        )
        assert list(_citekeys.citekeys_by_section(target)) == ["2. Failure modes"]


class TestBrief:
    def test_resolves_the_citekeys_it_is_given_in_order(self, draft):
        target = _fill_dossier(draft, evidence=_TWO_BLOCKS)
        report = _brief.brief(
            target, citekeys=["talasila_composable_2025", "ferko_architecting_2022"]
        )
        assert [key for key, _ in report.blocks] == [
            "talasila_composable_2025",
            "ferko_architecting_2022",
        ]
        assert report.missing == []

    def test_a_citekey_with_no_block_is_reported_not_dropped(self, draft):
        target = _fill_dossier(draft, evidence=_TWO_BLOCKS)
        report = _brief.brief(target, citekeys=["ferko_architecting_2022", "never_seen_2020"])
        assert [key for key, _ in report.blocks] == ["ferko_architecting_2022"]
        assert report.missing == ["never_seen_2020"]

    def test_resolves_a_section_through_sections_md(self, draft):
        target = _fill_dossier(
            draft,
            evidence=_TWO_BLOCKS,
            sections_rows=(
                "| 2. Failure modes | `ferko_architecting_2022` |\n"
                "| 3. Adoption | `talasila_composable_2025` |\n"
            ),
        )
        report = _brief.brief(target, section="2. Failure modes")
        assert report.section == "2. Failure modes"
        assert [key for key, _ in report.blocks] == ["ferko_architecting_2022"]

    def test_a_section_matches_on_its_title_without_its_numbering(self, draft):
        target = _fill_dossier(
            draft,
            evidence=_TWO_BLOCKS,
            sections_rows=("| 2. Failure modes | `ferko_architecting_2022` |\n"),
        )
        report = _brief.brief(target, section="failure modes")
        assert report.section == "2. Failure modes"

    def test_an_ambiguous_section_matches_nothing_and_offers_the_candidates(self, draft):
        """Guessing between two sections would hand a writer someone
        else's evidence, which reads as a plausible section and is wrong."""
        target = _fill_dossier(
            draft,
            evidence=_TWO_BLOCKS,
            sections_rows=(
                "| 2. Failure modes in practice | `ferko_architecting_2022` |\n"
                "| 3. Failure modes in theory | `talasila_composable_2025` |\n"
            ),
        )
        report = _brief.brief(target, section="failure modes")
        assert report.section is None
        assert len(report.known_sections) == 2

    def test_a_section_and_citekeys_together_are_the_union_without_repeats(self, draft):
        target = _fill_dossier(
            draft,
            evidence=_TWO_BLOCKS,
            sections_rows=("| 2. Failure modes | `ferko_architecting_2022` |\n"),
        )
        report = _brief.brief(
            target,
            citekeys=["ferko_architecting_2022", "talasila_composable_2025"],
            section="2. Failure modes",
        )
        assert [key for key, _ in report.blocks] == [
            "ferko_architecting_2022",
            "talasila_composable_2025",
        ]

    def test_a_section_with_no_evidence_transcribed_resolves_to_nothing(self, draft):
        target = _fill_dossier(
            draft, sections_rows=("| 2. Failure modes | `ferko_architecting_2022` |\n")
        )
        report = _brief.brief(target, section="2. Failure modes")
        assert report.blocks == []
        assert report.missing == ["ferko_architecting_2022"]


class TestBriefCli:
    def test_prints_the_blocks_for_the_citekeys_asked_for(self, draft, capsys):
        _fill_dossier(draft, evidence=_TWO_BLOCKS)
        assert dossier.main(["brief", str(draft), "ferko_architecting_2022"]) == 0
        out = capsys.readouterr().out
        assert "service layer" in out
        assert "composition rule" not in out

    def test_check_reports_the_count_without_the_bodies(self, draft, capsys):
        """What the orchestrator runs before dispatching: it needs to know
        the rows are there, and reading them into its own context is the
        cost the whole mechanism exists to avoid."""
        _fill_dossier(draft, evidence=_TWO_BLOCKS)
        assert dossier.main(["brief", str(draft), "ferko_architecting_2022", "--check"]) == 0
        captured = capsys.readouterr()
        assert "1 of 1" in captured.err
        assert "service layer" not in captured.out + captured.err

    def test_the_dossier_directory_works_as_well_as_the_draft_path(self, draft, capsys):
        target = _fill_dossier(draft, evidence=_TWO_BLOCKS)
        assert dossier.main(["brief", str(target), "ferko_architecting_2022"]) == 0
        assert "service layer" in capsys.readouterr().out

    def test_a_section_is_resolved_and_named_in_the_header(self, draft, capsys):
        _fill_dossier(
            draft,
            evidence=_TWO_BLOCKS,
            sections_rows=("| 2. Failure modes | `ferko_architecting_2022` |\n"),
        )
        assert dossier.main(["brief", str(draft), "--section", "failure modes"]) == 0
        captured = capsys.readouterr()
        assert "2. Failure modes" in captured.err, "the header names the row it matched"
        assert "service layer" in captured.out, "stdout carries only the evidence"

    def test_an_unknown_section_exits_nonzero_and_lists_the_known_ones(self, draft, capsys):
        _fill_dossier(
            draft,
            evidence=_TWO_BLOCKS,
            sections_rows=("| 2. Failure modes | `ferko_architecting_2022` |\n"),
        )
        assert dossier.main(["brief", str(draft), "--section", "adoption"]) == 1
        err = capsys.readouterr().err
        assert "2. Failure modes" in err

    def test_an_unknown_section_with_no_plan_at_all_says_so(self, draft, capsys):
        _fill_dossier(draft, evidence=_TWO_BLOCKS)
        assert dossier.main(["brief", str(draft), "--section", "adoption"]) == 1
        assert "sections.md" in capsys.readouterr().err

    def test_nothing_transcribed_exits_nonzero_and_names_the_cause(self, draft, capsys):
        """The failure this makes loud. Before it, an orchestrator that
        skipped its transcription lost six packets and nothing said so."""
        _fill_dossier(draft)
        assert dossier.main(["brief", str(draft), "ferko_architecting_2022"]) == 1
        err = capsys.readouterr().err
        assert "ferko_architecting_2022" in err
        assert "evidence.md" in err

    def test_a_partial_result_still_prints_what_it_has_and_warns(self, draft, capsys):
        _fill_dossier(draft, evidence=_TWO_BLOCKS)
        assert (
            dossier.main(["brief", str(draft), "ferko_architecting_2022", "never_seen_2020"]) == 0
        )
        captured = capsys.readouterr()
        assert "service layer" in captured.out
        assert "never_seen_2020" in captured.err

    def test_no_selector_at_all_is_an_error_rather_than_the_whole_file(self, draft, capsys):
        """Defaulting to "print everything" would put the whole of
        evidence.md into the reader's context, which is what a caller
        reaching for `brief` is trying not to do."""
        _fill_dossier(draft, evidence=_TWO_BLOCKS)
        assert dossier.main(["brief", str(draft)]) == 1
        assert "--section" in capsys.readouterr().err

    def test_no_dossier_at_all_points_at_init(self, draft, capsys):
        assert dossier.main(["brief", str(draft), "a_b_2024"]) == 1
        assert "init" in capsys.readouterr().err

    def test_a_planned_section_with_no_evidence_assigned_says_which_gap(self, draft, capsys):
        """Distinct from a section name that matched nothing: this row
        exists, and it is Phase 4's plan that is incomplete."""
        _fill_dossier(draft, evidence=_TWO_BLOCKS, sections_rows="| 4. Open questions |  |\n")
        assert dossier.main(["brief", str(draft), "--section", "Open questions"]) == 1
        assert "planned but has no citekeys" in capsys.readouterr().err

    def test_a_mistyped_dossier_path_gets_the_mirroring_rule_not_init(
        self, isolated_config, capsys
    ):
        """`brief` takes either a draft path or a dossier directory, and
        the two wrong-path cases have to say different things. A draft
        with no dossier yet gets `init <that draft>`, which is the right
        command. A dossier path that resolves to nothing never reaches
        that suggestion -- `dossier_dir` refuses it first, because
        `init` would not accept it -- and says which rule was broken
        instead. `status` behaves the same way; this pins that they
        agree."""
        config.DRAFTS_DIR.mkdir(parents=True)
        assert dossier.main(["brief", "content/dossiers/nope", "a_b_2024"]) == 1
        err = capsys.readouterr().err
        assert "is not under" in err
        assert "init" not in err


class TestAttributeCitekeys:
    """Deriving `sections.md` from the draft (#89).

    The relation is mechanical -- heading line range x citekey line
    number -- and a `sections.md` that disagrees with the draft hands a
    reviser a wrong answer about which section owns a citation. So what
    is pinned here is the join itself, both syntaxes, and the two cases
    that have no obvious right answer: a key cited above every heading,
    and a heading containing the character the table is delimited by.
    """

    MD = (
        "Opening prose citing [@early_2020].\n"
        "\n"
        "# Title\n"
        "\n"
        "## 1. Background\n"
        "\n"
        "Claims [@a_one_2024] and [@b_two_2024; @a_one_2024].\n"
        "\n"
        "```python\n"
        "# Step 1: not a heading\n"
        'print("[@fenced_9999]")\n'
        "```\n"
        "\n"
        "## 2. Results\n"
        "\n"
        "More [@c_three_2022].\n"
    )

    def test_each_citekey_lands_in_the_section_that_cites_it(self):
        per_section, unattributed = _sections.attribute_citekeys(self.MD)
        assert [(section.title, keys) for section, keys in per_section] == [
            ("Title", []),
            ("1. Background", ["a_one_2024", "b_two_2024"]),
            ("2. Results", ["c_three_2022"]),
        ]
        assert unattributed == ["early_2020"]

    def test_a_key_cited_twice_in_one_section_appears_once(self):
        per_section, _ = _sections.attribute_citekeys(self.MD)
        background = dict((s.title, keys) for s, keys in per_section)["1. Background"]
        assert background.count("a_one_2024") == 1

    def test_a_citekey_inside_a_fence_is_not_attributed(self):
        """`sections()` already skips fenced code for line ranges, and
        `extract_citekeys` skips it for keys -- so a `[@key]` printed by
        the shipped example tutorial's own Python must not become
        evidence."""
        per_section, unattributed = _sections.attribute_citekeys(self.MD)
        every = [key for _, keys in per_section for key in keys] + unattributed
        assert "fenced_9999" not in every

    def test_the_latex_syntax_is_read_too(self):
        tex = (
            "\\section{Intro}\n"
            "A claim \\citep{a_one_2024} and \\citet{b_two_2024}.\n"
            "\\subsection{Detail}\n"
            "\\begin{verbatim}\n"
            "\\citep{verbatim_0000}\n"
            "\\end{verbatim}\n"
            "Another \\citep{a_one_2024}.\n"
        )
        per_section, unattributed = _sections.attribute_citekeys(tex)
        assert [(section.title, keys) for section, keys in per_section] == [
            ("Intro", ["a_one_2024", "b_two_2024"]),
            ("Detail", ["a_one_2024"]),
        ]
        assert unattributed == []

    def test_a_key_cited_twice_above_every_heading_is_reported_once(self):
        text = "Prose [@a_one_2024], and again [@a_one_2024].\n\n## 1. First\n\ntext\n"
        _, unattributed = _sections.attribute_citekeys(text)
        assert unattributed == ["a_one_2024"]

    def test_a_draft_with_no_headings_attributes_nothing(self):
        per_section, unattributed = _sections.attribute_citekeys("Just prose [@a_one_2024].\n")
        assert per_section == []
        assert unattributed == ["a_one_2024"]


class TestSectionsMarkdown:
    def test_it_writes_the_template_and_one_row_per_section(self):
        table = _sections.sections_markdown(TestAttributeCitekeys.MD)
        assert table.startswith("# Sections and their citekeys")
        assert "| section | citekeys |" in table
        assert "| 1. Background | `a_one_2024`, `b_two_2024` |" in table
        assert "| 2. Results | `c_three_2022` |" in table
        assert "| Title |  |" in table

    def test_it_round_trips_through_the_reader(self, tmp_path):
        """The file has one parser (`citekeys_by_section`), and this is
        the other end of it: what is derived here must read back as the
        same relation, or a reviser and a writer disagree."""
        (tmp_path / "sections.md").write_text(
            _sections.sections_markdown(TestAttributeCitekeys.MD), encoding="utf-8"
        )
        assert _citekeys.citekeys_by_section(tmp_path) == {
            "Title": [],
            "1. Background": ["a_one_2024", "b_two_2024"],
            "2. Results": ["c_three_2022"],
        }

    def test_a_pipe_in_a_heading_survives_the_round_trip(self, tmp_path):
        """A `|` in a heading would otherwise cut the row in two. It is
        escaped on the way out and unescaped on the way back, so the
        section name matches what `sections()` reports for the draft."""
        text = "## Results | caveats\n\nA claim [@a_one_2024].\n"
        (tmp_path / "sections.md").write_text(_sections.sections_markdown(text), encoding="utf-8")
        assert r"| Results \| caveats |" in (tmp_path / "sections.md").read_text()
        assert _citekeys.citekeys_by_section(tmp_path) == {
            "Results | caveats": ["a_one_2024"],
        }
        assert list(_citekeys.citekeys_by_section(tmp_path)) == [
            section.title for section in dossier.sections(text)
        ]


class TestSectionsCitekeysCli:
    def test_it_prints_the_table(self, draft, capsys):
        draft.write_text(TestAttributeCitekeys.MD)
        assert dossier.main(["sections", str(draft), "--citekeys"]) == 0
        out = capsys.readouterr()
        assert "| 1. Background | `a_one_2024`, `b_two_2024` |" in out.out
        assert "early_2020" in out.err, "an unattributed key must be said out loud"

    def test_write_fills_in_the_dossiers_own_file(self, draft, capsys):
        draft.write_text(TestAttributeCitekeys.MD)
        dossier.init(draft, "survey")
        assert dossier.main(["sections", str(draft), "--citekeys", "--write"]) == 0
        written = (dossier.dossier_dir(draft) / "sections.md").read_text()
        assert "| 2. Results | `c_three_2022` |" in written
        assert "sections.md" in capsys.readouterr().out

    def test_a_draft_citing_only_inside_sections_says_nothing_on_stderr(self, draft, capsys):
        draft.write_text("## 1. First\n\nA claim [@a_one_2024].\n")
        assert dossier.main(["sections", str(draft), "--citekeys"]) == 0
        assert capsys.readouterr().err == ""

    def test_write_without_a_dossier_is_refused(self, draft, capsys):
        draft.write_text(TestAttributeCitekeys.MD)
        assert dossier.main(["sections", str(draft), "--citekeys", "--write"]) == 1
        assert "init" in capsys.readouterr().err

    def test_write_needs_citekeys(self, draft, capsys):
        assert dossier.main(["sections", str(draft), "--write"]) == 1
        assert "--citekeys" in capsys.readouterr().err

    def test_a_draft_with_no_headings_is_an_error(self, draft, capsys):
        draft.write_text("Just prose.\n")
        assert dossier.main(["sections", str(draft), "--citekeys"]) == 1
        assert "No headings" in capsys.readouterr().err


# ---------------------------------------------------------------------
# A2 (#306): evidence.md's claim:/quote: split, and its self-check
# (chitragupta/dossier/_evidence_check.py, plans/a2-claim-quote-split.md).
#
# `evidence_blocks()` is unchanged by A2 -- it was already shape-agnostic
# (its own docstring says so) -- so the two round-trip tests below are
# characterization tests pinning that pre-existing coexistence guarantee,
# not TDD red-then-green: they pass before this module exists too. What
# is new is `_evidence_check`, tested below them.
# ---------------------------------------------------------------------


class TestEvidenceBlocksCoexistence:
    def test_a_new_shape_block_round_trips(self, draft):
        target = _fill_dossier(
            draft,
            evidence=(
                "## `talasila_realising_2024`\n\n"
                "- relevance: names the synchronization requirement\n"
                "- claim: a digital twin must stay synchronized with its physical "
                "counterpart to remain valid\n"
                '- quote: "a digital twin that drifts from its physical counterpart '
                'is no longer trustworthy"\n'
            ),
        )
        block = _citekeys.evidence_blocks(target)["talasila_realising_2024"]
        assert "claim:" in block
        assert "quote:" in block

    def test_a_legacy_support_only_block_still_round_trips(self, draft):
        target = _fill_dossier(draft, evidence=_TWO_BLOCKS)
        blocks = _citekeys.evidence_blocks(target)
        assert "support:" in blocks["ferko_architecting_2022"]


class TestOverlapScore:
    """chitragupta/dossier/_evidence_check.py::overlap_score -- the pure
    stemmed-bigram comparison the self-check is built on. Fixture pairs
    and their measured scores (n=2, this repo's own corpus tooling):

    - a quote reworded (clauses swapped, no new words) scores 0.5-0.75
    - a genuine restatement (same topic, different structure and words)
      scores ~0.08
    - a quote too short to form one bigram has nothing to compare

    n=2 rather than overlap_skipgram's own DEFAULT_N=5: a claim/quote
    pair is a sentence, not a document, and at n=5 a short pair never
    reaches one gram at all. n=2 was checked against these same fixtures
    before n=3 was ruled out: n=3 still separates the two long fixtures
    but collapses the short reworded one to 0.33, under a threshold that
    catches the long case -- n=2 is the one width that separates every
    fixture tried.
    """

    QUOTE = (
        "digital twins for software engineers require continuous "
        "synchronization between the physical system and its virtual "
        "counterpart to remain valid"
    )
    REWORDED = (
        "continuous synchronization between the physical system and its "
        "virtual counterpart is required for digital twins for software "
        "engineers to remain valid"
    )
    RESTATED = (
        "the paper argues that a digital twin only stays useful if it is "
        "kept in sync with the real system it mirrors"
    )

    def test_a_reworded_quote_scores_at_or_above_the_threshold(self):
        score = _evidence_check.overlap_score(self.REWORDED, self.QUOTE)
        assert score is not None
        assert score >= _evidence_check._OVERLAP_THRESHOLD

    def test_a_genuine_restatement_scores_below_the_threshold(self):
        score = _evidence_check.overlap_score(self.RESTATED, self.QUOTE)
        assert score is not None
        assert score < _evidence_check._OVERLAP_THRESHOLD

    def test_a_quote_shorter_than_one_bigram_has_nothing_to_compare(self):
        assert _evidence_check.overlap_score("the twins compose from parts", "twins") is None

    def test_a_short_quote_quantizes_to_whole_steps(self):
        # Two stemmed content words is exactly one bigram, so the only
        # scores possible are 0.0 and 1.0 -- never a fraction. A
        # one-clause quote is a realistic input, not an edge case to
        # special-case away.
        assert _evidence_check.overlap_score("the twins compose from parts", "twins compose") == 1.0
        assert _evidence_check.overlap_score("a reusable module design", "twins compose") == 0.0


_REWORDED_BLOCK = (
    "## `talasila_realising_2024`\n\n"
    f"- relevance: names the synchronization requirement\n"
    f"- claim: {TestOverlapScore.REWORDED}\n"
    f"- quote: {TestOverlapScore.QUOTE}\n"
)
_RESTATED_BLOCK = (
    "## `ferko_architecting_2022`\n\n"
    f"- relevance: names the synchronization requirement\n"
    f"- claim: {TestOverlapScore.RESTATED}\n"
    f"- quote: {TestOverlapScore.QUOTE}\n"
)
_LEGACY_SUPPORT_ONLY_BLOCK = (
    "## `talasila_composable_2025`\n\n"
    "- relevance: the composition rule the section leans on\n"
    '- support: "twins compose from tool-agnostic parts"\n'
)
_CLAIM_WITHOUT_QUOTE_BLOCK = (
    "## `smith_x_2024`\n\n- relevance: why this matters\n- claim: a claim with no quote recorded\n"
)


class TestRewordedClaims:
    def test_flags_a_reworded_quote(self, draft):
        target = _fill_dossier(draft, evidence=_REWORDED_BLOCK)
        assert "talasila_realising_2024" in _evidence_check.reworded_claims(target)

    def test_stays_silent_on_a_genuine_restatement(self, draft):
        target = _fill_dossier(draft, evidence=_RESTATED_BLOCK)
        assert _evidence_check.reworded_claims(target) == {}

    def test_a_legacy_support_only_block_has_nothing_to_check(self, draft):
        """No `claim:` field means nothing to compare it against -- the
        self-check only ever applies to a block the new contract wrote,
        per the plan's migration rule."""
        target = _fill_dossier(draft, evidence=_LEGACY_SUPPORT_ONLY_BLOCK)
        assert _evidence_check.reworded_claims(target) == {}

    def test_a_claim_with_no_recorded_quote_has_nothing_to_check(self, draft):
        target = _fill_dossier(draft, evidence=_CLAIM_WITHOUT_QUOTE_BLOCK)
        assert _evidence_check.reworded_claims(target) == {}

    def test_a_field_typed_with_no_value_is_dropped_not_recorded_empty(self, draft):
        """A blank `claim:` (nothing typed after the colon) is dropped
        rather than kept as an empty string that happens to be falsy --
        so a block with a blank claim: has nothing to compare its
        quote: against, the same as a block with no claim: line at all."""
        target = _fill_dossier(
            draft,
            evidence=(
                f"## `talasila_realising_2024`\n\n- claim:\n- quote: {TestOverlapScore.QUOTE}\n"
            ),
        )
        assert _evidence_check.reworded_claims(target) == {}

    def test_no_evidence_file_flags_nothing(self, draft):
        target = dossier.dossier_dir(draft)
        target.mkdir(parents=True)
        assert _evidence_check.reworded_claims(target) == {}


class TestCheckEvidenceCommand:
    def test_flags_a_reworded_quote_without_printing_a_score_by_default(self, draft, capsys):
        _fill_dossier(draft, evidence=_REWORDED_BLOCK)
        assert dossier.main(["check-evidence", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "talasila_realising_2024" in out
        assert "%" not in out, "no score by default -- nothing to optimise against (R3)"

    def test_the_score_flag_prints_the_number(self, draft, capsys):
        _fill_dossier(draft, evidence=_REWORDED_BLOCK)
        assert dossier.main(["check-evidence", str(draft), "--score"]) == 0
        assert "%" in capsys.readouterr().out

    def test_a_clean_dossier_says_so(self, draft, capsys):
        _fill_dossier(draft, evidence=_RESTATED_BLOCK)
        assert dossier.main(["check-evidence", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "ferko_architecting_2022" not in out
        assert "reworded" in out

    def test_missing_dossier_is_refused_not_crashed(self, draft, capsys):
        assert dossier.main(["check-evidence", str(draft)]) == 1
        assert "init" in capsys.readouterr().out
