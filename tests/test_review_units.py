"""chitragupta/review/_units.py: what a "unit" is, per genre, and how a
drafter declares that a single-source one was deliberate.

The unit is the scale the multi-source rule binds at, and it differs by
genre -- see plans/b2-multi-source-synthesis.md. These tests pin the
three things that get it wrong in practice: reading the genre out of a
dossier that may not exist, splitting a draft into units without
mistaking a declaration marker for prose, and counting a run of
consecutive paragraphs that all rest on the same single source.
"""

from pathlib import Path

import pytest

from chitragupta import config, dossier
from chitragupta.review import _units


def write_scope(draft: Path, genre: str) -> None:
    """Put one `- genre:` line into this draft's dossier scope.md."""
    scope_dir = dossier.dossier_dir(draft)
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / dossier.SCOPE_MD).write_text(
        f"# Scope\n\n- genre: {genre}\n- created: 2026-08-21\n", encoding="utf-8"
    )


def draft_at(name: str = "survey.md") -> Path:
    path = config.DRAFTS_DIR / "dt" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder\n", encoding="utf-8")
    return path


class TestGenreOf:
    def test_reads_the_genre_line_from_scope_md(self, isolated_config):
        draft = draft_at()
        write_scope(draft, "textbook-chapter")
        assert _units.genre_of(draft) == "textbook-chapter"

    def test_a_draft_with_no_dossier_has_no_genre(self, isolated_config):
        assert _units.genre_of(draft_at()) is None

    def test_a_scope_without_a_genre_line_has_no_genre(self, isolated_config):
        draft = draft_at()
        scope_dir = dossier.dossier_dir(draft)
        scope_dir.mkdir(parents=True, exist_ok=True)
        (scope_dir / dossier.SCOPE_MD).write_text("# Scope\n\n- language: en-GB\n",
                                                  encoding="utf-8")
        assert _units.genre_of(draft) is None

    def test_an_empty_genre_value_has_no_genre(self, isolated_config):
        draft = draft_at()
        scope_dir = dossier.dossier_dir(draft)
        scope_dir.mkdir(parents=True, exist_ok=True)
        (scope_dir / dossier.SCOPE_MD).write_text("# Scope\n\n- genre:\n", encoding="utf-8")
        assert _units.genre_of(draft) is None

    def test_a_draft_outside_content_has_no_genre(self, isolated_config, tmp_path):
        """dossier_dir raises for a path it cannot mirror; that is a
        missing genre, not a crash in a report that judges nothing."""
        assert _units.genre_of(tmp_path / "loose.md") is None


class TestResolveUnit:
    """Three sources, most specific first -- style_check.resolve_language's
    policy, because the report has to name where the unit came from."""

    def test_every_genre_resolves_its_own_unit(self, isolated_config):
        expected = {
            "survey": "paragraph",
            "thesis-chapter": "paragraph",
            "deep-research": "paragraph",
            "textbook-chapter": "section",
            "tutorial": "document",
        }
        for genre, kind in expected.items():
            draft = draft_at(f"{genre}.md")
            write_scope(draft, genre)
            assert _units.resolve_unit(draft) == (kind, "scope.md"), genre

    def test_the_table_covers_every_genre_dossier_init_accepts(self):
        """A genre `dossier init --genre` names but this table omits would
        silently fall back to the paragraph, which is wrong for two of
        the five."""
        assert set(_units.UNITS) == set(dossier.GENRES)

    def test_an_override_wins_over_the_dossier(self, isolated_config):
        draft = draft_at()
        write_scope(draft, "tutorial")
        assert _units.resolve_unit(draft, "section") == ("section", "--unit")

    def test_no_dossier_falls_back_and_says_so(self, isolated_config):
        assert _units.resolve_unit(draft_at()) == ("paragraph", "nothing")

    def test_an_unrecognised_genre_falls_back_and_says_so(self, isolated_config):
        """A hand-edited scope.md is not a reason to refuse to report."""
        draft = draft_at()
        write_scope(draft, "libretto")
        assert _units.resolve_unit(draft) == ("paragraph", "nothing")


class TestMarkers:
    def test_a_markdown_marker_declares_its_unit(self, isolated_config):
        text = "Body text [@Foo2019].\n<!-- single-source: only Foo covers X -->\n"
        (unit,) = _units.units(text, "paragraph")
        assert unit.declared == "only Foo covers X"

    def test_a_latex_marker_declares_its_unit(self, isolated_config):
        text = "Body text \\citep{Foo2019}.\n% single-source: only Foo covers X\n"
        (unit,) = _units.units(text, "paragraph")
        assert unit.declared == "only Foo covers X"

    def test_a_marker_above_its_unit_also_declares_it(self, isolated_config):
        text = "<!-- single-source: only Foo covers X -->\nBody text [@Foo2019].\n"
        (unit,) = _units.units(text, "paragraph")
        assert unit.declared == "only Foo covers X"

    def test_a_marker_split_off_by_a_blank_line_declares_nothing(self, isolated_config):
        """It becomes its own block, which is why the standard requires it
        to touch the unit it explains."""
        text = "<!-- single-source: only Foo covers X -->\n\nBody text [@Foo2019].\n"
        units = _units.units(text, "paragraph")
        assert [u.declared for u in units] == [None]
        assert [u.citekeys for u in units] == [("Foo2019",)]

    def test_a_marker_only_block_is_not_a_unit(self, isolated_config):
        text = "<!-- single-source: stray -->\n\nBody [@Foo2019].\n"
        assert len(_units.units(text, "paragraph")) == 1

    def test_a_marker_inside_a_fenced_code_block_declares_nothing(self, isolated_config):
        text = (
            "Body text [@Foo2019].\n"
            "```\n"
            "<!-- single-source: this is sample code, not a declaration -->\n"
            "```\n"
        )
        (unit,) = _units.units(text, "paragraph")
        assert unit.declared is None

    def test_the_marker_is_stripped_from_the_units_text(self, isolated_config):
        """Otherwise declaring a unit changes the text that names it, and
        every finding id churns the moment someone explains one."""
        plain = "Body text [@Foo2019].\n"
        declared = "Body text [@Foo2019].\n<!-- single-source: because -->\n"
        assert _units.units(plain, "paragraph")[0].text == \
            _units.units(declared, "paragraph")[0].text

    def test_a_marker_naming_a_citekey_is_not_itself_a_citation(self, isolated_config):
        text = "Body text [@Foo2019].\n<!-- single-source: Bar2020 does not cover X -->\n"
        (unit,) = _units.units(text, "paragraph")
        assert unit.citekeys == ("Foo2019",)


class TestParagraphUnits:
    def test_each_blank_line_separated_block_is_a_unit(self, isolated_config):
        text = "One [@A].\n\nTwo [@B].\n\nThree [@C].\n"
        assert [u.citekeys for u in _units.units(text, "paragraph")] == \
            [("A",), ("B",), ("C",)]

    def test_citekeys_are_distinct_and_sorted(self, isolated_config):
        text = "Fuses [@Beta] and [@Alpha] and [@Beta] again.\n"
        (unit,) = _units.units(text, "paragraph")
        assert unit.citekeys == ("Alpha", "Beta")

    def test_a_citation_in_a_table_row_counts(self, isolated_config):
        text = "| Approach | Source |\n|---|---|\n| One | [@A] |\n| Two | [@B] |\n"
        (unit,) = _units.units(text, "paragraph")
        assert unit.citekeys == ("A", "B")

    def test_a_citation_in_a_list_item_counts(self, isolated_config):
        text = "- first [@A]\n- second [@B]\n"
        (unit,) = _units.units(text, "paragraph")
        assert unit.citekeys == ("A", "B")

    def test_a_citation_in_a_footnote_counts(self, isolated_config):
        text = "Body text.\n\n[^1]: A footnote citing [@A].\n"
        assert ("A",) in [u.citekeys for u in _units.units(text, "paragraph")]

    def test_a_unit_carries_the_line_it_starts_on(self, isolated_config):
        text = "One [@A].\n\nTwo [@B].\n"
        assert [u.line for u in _units.units(text, "paragraph")] == [1, 3]

    def test_a_paragraph_unit_has_no_run(self, isolated_config):
        """The run is a property of a section's internal shape; a
        paragraph has no inside to be block-structured."""
        (unit,) = _units.units("One [@A].\n", "paragraph")
        assert unit.longest_run == 0


class TestDocumentUnits:
    def test_the_whole_draft_is_one_unit(self, isolated_config):
        text = "# Lesson\n\nSteps.\n\n## Where to go next\n\nSee [@A] and [@B].\n"
        (unit,) = _units.units(text, "document")
        assert unit.citekeys == ("A", "B")
        assert unit.line == 1

    def test_an_uncited_draft_is_still_one_unit(self, isolated_config):
        (unit,) = _units.units("# Lesson\n\nNo citations at all.\n", "document")
        assert unit.citekeys == ()


class TestSectionUnits:
    def test_a_markdown_heading_opens_a_section(self, isolated_config):
        text = "## One\n\nText [@A].\n\n## Two\n\nText [@B].\n"
        assert [u.citekeys for u in _units.units(text, "section")] == [("A",), ("B",)]

    def test_a_latex_heading_opens_a_section(self, isolated_config):
        text = ("\\section{One}\n\nText \\citep{A}.\n\n"
                "\\section{Two}\n\nText \\citep{B}.\n")
        assert [u.citekeys for u in _units.units(text, "section")] == [("A",), ("B",)]

    def test_prose_before_the_first_heading_is_its_own_section(self, isolated_config):
        text = "Preamble [@A].\n\n## One\n\nText [@B].\n"
        assert [u.citekeys for u in _units.units(text, "section")] == [("A",), ("B",)]

    def test_blank_lines_before_the_first_heading_open_no_section(self, isolated_config):
        """Otherwise a draft that happens to start with a blank line
        reports one more unit than it has, and that unit cites nothing."""
        assert [u.line for u in _units.units("\n\n## One\n\nText [@A].\n", "section")] \
            == [3]

    def test_a_draft_with_no_headings_is_one_section(self, isolated_config):
        text = "One [@A].\n\nTwo [@B].\n"
        assert [u.citekeys for u in _units.units(text, "section")] == [("A", "B")]


class TestTheLongestSingleKeyRun:
    """A section spanning two sources by running one paper out before
    starting the next satisfies spread and fuses nothing. The run is what
    tells the two apart."""

    def test_a_block_structured_section_reports_its_run(self, isolated_config):
        text = ("## S\n\nOne [@A].\n\nTwo [@A].\n\nThree [@A].\n\n"
                "Four [@B].\n\nFive [@B].\n\nSix [@B].\n")
        (unit,) = _units.units(text, "section")
        assert unit.citekeys == ("A", "B")
        assert unit.longest_run == 3

    def test_its_interleaved_counterpart_reports_a_run_of_one(self, isolated_config):
        text = ("## S\n\nOne [@A].\n\nTwo [@B].\n\nThree [@A].\n\n"
                "Four [@B].\n\nFive [@A].\n\nSix [@B].\n")
        (unit,) = _units.units(text, "section")
        assert unit.citekeys == ("A", "B")
        assert unit.longest_run == 1

    def test_a_multi_source_paragraph_breaks_a_run(self, isolated_config):
        text = "## S\n\nOne [@A].\n\nTwo [@A] and [@B].\n\nThree [@A].\n"
        (unit,) = _units.units(text, "section")
        assert unit.longest_run == 1

    def test_a_zero_citation_paragraph_breaks_a_run(self, isolated_config):
        text = "## S\n\nOne [@A].\n\nOriginal prose, no citation.\n\nThree [@A].\n"
        (unit,) = _units.units(text, "section")
        assert unit.longest_run == 1

    def test_a_run_is_not_counted_across_a_heading(self, isolated_config):
        text = "## One\n\nText [@A].\n\n## Two\n\nText [@A].\n"
        assert [u.longest_run for u in _units.units(text, "section")] == [1, 1]

    def test_an_uncited_section_has_no_run(self, isolated_config):
        (unit,) = _units.units("## S\n\nOriginal prose.\n", "section")
        assert unit.longest_run == 0


class TestAnEmptyDraft:
    """Not a hypothetical: a draft file that exists but has not been
    written to yet is what a genre skill leaves behind between steps."""

    def test_has_no_paragraph_units(self, isolated_config):
        assert _units.units("", "paragraph") == []

    def test_has_no_section_units(self, isolated_config):
        assert _units.units("", "section") == []

    def test_is_still_one_document_unit(self, isolated_config):
        (unit,) = _units.units("", "document")
        assert unit.citekeys == ()


class TestAnUnknownKind:
    def test_is_refused(self, isolated_config):
        with pytest.raises(ValueError, match="Unknown unit kind"):
            _units.units("Text.\n", "chapter")
