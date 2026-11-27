import sys

import pytest

from chitragupta import (
    ledger,
    reference_entries,
    references,
    references_ieee,
    references_renumber,
    references_section,
)

from tests.conftest import content_draft, make_reference, run_python


class TestUsedCitekeys:
    def test_dedupes_and_keeps_first_appearance_order(self):
        text = "[@zebra2024] and \\citep{apple2024} and [@zebra2024] again"
        assert references.used_citekeys(text) == ["zebra2024", "apple2024"]

    def test_no_citations(self):
        assert references.used_citekeys("just prose") == []

    def test_a_commented_out_latex_citation_is_not_used(self):
        text = "\\citep{zebra2024}\n% Dropped: \\citep{apple2024}\n"
        assert references.used_citekeys(text, latex=True) == ["zebra2024"]
        assert references.used_citekeys("30% [@apple2024]") == ["apple2024"]

    def test_ignores_a_citekey_inside_a_code_span(self):
        assert references.used_citekeys("[1] A Paper, 2024. `ghost2024`") == []


class TestHasSection:
    @pytest.mark.parametrize(
        "heading",
        [
            "## References",
            "# References",
            "###### References",
            "## 6. References",
            "## 6) References",
            "## references",
        ],
    )
    def test_matches_various_heading_styles(self, heading):
        assert references_section.has_section(f"Some text\n\n{heading}\n\nmore\n")

    def test_no_match_for_unrelated_heading(self):
        assert not references_section.has_section("## Introduction\n\nSome text.\n")

    def test_no_match_for_references_mentioned_in_prose(self):
        assert not references_section.has_section("See the references cited above.\n")

    def test_no_match_for_a_heading_inside_a_code_fence(self):
        draft = "# Lesson\n\n```markdown\n## References\n- an example\n```\n\nMore lesson.\n"
        assert not references_section.has_section(draft)

    def test_finds_a_real_heading_after_a_code_fence(self):
        draft = "# Lesson\n\n```markdown\n## References\n```\n\n## References\n\n[1] X. `k`\n"
        lines = draft.splitlines(keepends=True)
        assert lines[references_section.section_start(lines)].strip() == "## References"

    def test_no_match_for_a_bibliography_heading_inside_a_code_fence(self):
        draft = "# Lesson\n\n```markdown\n## Bibliography\n- an example\n```\n\nMore lesson.\n"
        assert not references_section.has_section(draft)

    def test_a_title_does_not_run_onto_the_next_line(self):
        assert not references_section.has_section("# D\n\n## 6.\nReferences\n")

    @pytest.mark.parametrize(
        "heading",
        [
            "## References",
            "# References",
            "###### References",
            "## 6. References",
            "## 6) References",
            "## 1.14 References",
            "### 12.14 References",
            "## 1.2.3.4 References",
            "## Bibliography",
            "## Works cited",
            "## Works Cited",
            "## 7. Bibliography",
            "## A. References",
            "## IV. Works cited",
        ],
    )
    def test_matches_bare_and_numbered_headings(self, heading):
        assert references_section.has_section(f"# Draft\n\n{heading}\n\n[1] X. `k`\n")

    @pytest.mark.parametrize(
        "heading",
        [
            "## Introduction",
            "## 3.5 The published reference architectures",
            "## Further References",
            "## References and notes",
            "## Reference",
            "## Bibliographic notes",
            "## Further reading",
            "## See. References",
            "####### References",
        ],
    )
    def test_does_not_match_a_heading_that_is_not_the_bibliography(self, heading):
        assert not references_section.has_section(f"# Draft\n\n{heading}\n\nProse.\n")


class TestSectionEnd:
    def test_runs_to_the_next_heading_of_any_level(self):
        draft = "## References\n\n[1] X. `k`\n\n## Appendix\n\nmore\n"
        lines = draft.splitlines(keepends=True)
        start = references_section.section_start(lines)
        end = references_section.section_end(lines, start)
        assert lines[start:end] == ["## References\n", "\n", "[1] X. `k`\n", "\n"]
        assert lines[end] == "## Appendix\n"

    def test_a_deeper_heading_still_ends_the_section(self):
        draft = "## References\n\n[1] X. `k`\n\n### Acknowledgments\n\nthanks\n"
        lines = draft.splitlines(keepends=True)
        start = references_section.section_start(lines)
        end = references_section.section_end(lines, start)
        assert lines[end] == "### Acknowledgments\n"

    def test_runs_to_end_of_file_when_nothing_follows(self):
        draft = "## References\n\n[1] X. `k`\n"
        lines = draft.splitlines(keepends=True)
        start = references_section.section_start(lines)
        end = references_section.section_end(lines, start)
        assert end == len(lines)

    def test_a_heading_inside_a_code_fence_does_not_end_the_section(self):
        draft = "## References\n\n[1] X. `k`\n\n```markdown\n## Appendix\n```\n\nstill references\n"
        lines = draft.splitlines(keepends=True)
        start = references_section.section_start(lines)
        end = references_section.section_end(lines, start)
        assert end == len(lines)


class TestFormatEntry:
    def test_article_is_quoted_inside_an_italic_journal(self):
        entry = references_ieee.format_entry(
            "k",
            "A Study",
            "2024",
            {"author": "Doe, Jane", "journal": "J. Things", "volume": "2", "pages": "1--9"},
        )
        assert entry == 'J. Doe, "A Study," *J. Things*, vol. 2, pp. 1–9, 2024.'

    def test_work_with_no_container_is_italic_and_unquoted(self):
        entry = references_ieee.format_entry(
            "k", "A Whole Book", "2020", {"author": "Doe, Jane", "publisher": "MIT Press"}
        )
        assert entry == "J. Doe, *A Whole Book*, MIT Press, 2020."

    def test_proceedings_paper_gets_in_prefix(self):
        entry = references_ieee.format_entry(
            "k", "A Paper", "2021", {"author": "Doe, Jane", "booktitle": "Proc. Conf."}
        )
        assert "in *Proc. Conf.*" in entry

    @pytest.mark.parametrize(
        "author,expected",
        [
            ("Doe, Jane", "J. Doe"),
            ("Jane Doe", "J. Doe"),
            ("Doe, Jane Mary", "J. M. Doe"),
            ("Smith, Jean-Paul", "J.-P. Smith"),
            ("A, X and B, Y", "X. A and Y. B"),
            ("A, X and B, Y and C, Z", "X. A, Y. B, and Z. C"),
            ("{IEEE Standards Association}", "IEEE Standards Association"),
        ],
    )
    def test_author_lists(self, author, expected):
        assert references_ieee.format_entry(
            "k", "T", "2024", {"author": author, "journal": "J"}
        ).startswith(expected + ",")

    def test_more_than_six_authors_collapses_to_et_al(self):
        author = " and ".join(f"Last{i}, First{i}" for i in range(7))
        entry = references_ieee.format_entry("k", "T", "2024", {"author": author, "journal": "J"})
        assert entry.startswith("F. Last0 et al.,")

    def test_bibtex_and_others_truncation_renders_as_et_al(self):
        entry = references_ieee.format_entry(
            "k", "T", "2024", {"author": "Doe, Jane and others", "journal": "J"}
        )
        assert entry.startswith("J. Doe et al.,")

    def test_author_separator_split_across_a_wrapped_line(self):
        entry = references_ieee.format_entry(
            "k", "T", "2024", {"author": "Smith, Jane\n  and Doe, John", "journal": "J"}
        )
        assert entry.startswith("J. Smith and J. Doe,")

    def test_page_range_with_a_single_hyphen_gets_an_en_dash(self):
        entry = references_ieee.format_entry("k", "T", "2024", {"journal": "J", "pages": "1-10"})
        assert "pp. 1–10," in entry

    def test_title_ending_in_an_abbreviation_keeps_its_period(self):
        entry = references_ieee.format_entry("k", "A Report on the U.S.", "2024", {})
        assert "*A Report on the U.S.*" in entry

    def test_title_ending_in_an_ordinary_period_has_it_stripped(self):
        entry = references_ieee.format_entry("k", "A Study.", "2024", {})
        assert "*A Study*" in entry

    def test_booktitle_wins_over_journal_for_a_dual_field_entry(self):
        entry = references_ieee.format_entry(
            "k", "A Chapter", "2024", {"journal": "J. Stray", "booktitle": "Proc. Conf."}
        )
        assert "in *Proc. Conf.*" in entry
        assert "J. Stray" not in entry

    def test_editor_is_used_when_there_is_no_author(self):
        entry = references_ieee.format_entry(
            "k", "A Volume", "2015", {"editor": "Ed, One", "publisher": "Springer"}
        )
        assert entry.startswith("O. Ed, Eds.,")

    def test_single_page_uses_p_not_pp(self):
        assert "p. 7," in references_ieee.format_entry(
            "k", "T", "2024", {"journal": "J", "pages": "7"}
        )

    def test_markdown_emphasis_in_a_value_is_escaped(self):
        entry = references_ieee.format_entry("k", "The C_str_ and A*B Problem", "2024", {})
        assert r"C\_str\_" in entry
        assert r"A\*B" in entry

    def test_entry_with_nothing_but_a_citekey_still_renders(self):
        assert references_ieee.format_entry("k", "", "", {}) == "k."


class TestFormatNumbers:
    @pytest.mark.parametrize(
        "numbers,expected",
        [
            ([1], "[1]"),
            ([1, 2], "[1], [2]"),
            ([3, 4, 5], "[3]–[5]"),
            ([3, 4, 5, 6], "[3]–[6]"),
            ([1, 3, 4, 5, 7], "[1], [3]–[5], [7]"),
            ([5, 3, 4, 3], "[3]–[5]"),
            ([9, 1], "[1], [9]"),
        ],
    )
    def test_ieee_contraction_rules(self, numbers, expected):
        assert references_renumber._format_numbers(numbers) == expected


class TestRenumber:
    NUMBERS = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "g": 7}

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Claim [@a].", "Claim [1]."),
            ("Pair [@a; @b].", "Pair [1], [2]."),
            ("Run [@c; @d; @e].", "Run [3]–[5]."),
            ("Mixed [@a; @c; @d; @e; @g].", "Mixed [1], [3]–[5], [7]."),
            ("Suppressed [-@a].", "Suppressed [1]."),
            ("Bare @a here.", "Bare [1] here."),
            ("Locator [see @a, p. 33].", "Locator [see [1], p. 33]."),
            ("Locator [@a, p. 33].", "Locator [1, p. 33]."),
            ("Spaces [ @a ; @b ].", "Spaces [1], [2]."),
        ],
    )
    def test_marker_forms(self, text, expected):
        assert references.renumber(text, self.NUMBERS) == expected

    def test_a_group_holding_a_punctuated_key_renumbers_whole(self):
        assert references.renumber("[@smith:2020]", {"smith:2020": 1}) == "[1]"

    def test_a_locator_group_holding_a_punctuated_key_renumbers_whole(self):
        assert references.renumber("[@doe.2020, p. 33]", {"doe.2020": 4}) == "[4, p. 33]"

    @pytest.mark.parametrize(
        "text,numbers,expected",
        [
            ("[@3dprinting_2020]", {"3dprinting_2020": 2}, "[2]"),
            ("[@_internal2020]", {"_internal2020": 2}, "[2]"),
            ("[@3dprinting_2020; @a]", {"3dprinting_2020": 2, "a": 1}, "[1], [2]"),
        ],
    )
    def test_a_group_holding_a_digit_or_underscore_first_key_renumbers_whole(
        self, text, numbers, expected
    ):
        assert references.renumber(text, numbers) == expected

    def test_a_locator_group_holding_a_digit_first_key_renumbers_whole(self):
        assert references.renumber("[@3dprinting_2020, p. 33]", {"3dprinting_2020": 2}) == (
            "[2, p. 33]"
        )

    def test_a_digit_first_key_beside_an_unnumbered_punctuated_one(self):
        assert references.renumber(
            "[@3dprinting_2020] [@smith:2020]", {"3dprinting_2020": 2, "smith": 1}
        ) == ("[2] [@smith:2020]")

    def test_a_key_with_no_number_is_left_alone(self):
        assert references.renumber("Unknown [@zzz].", self.NUMBERS) == "Unknown [@zzz]."

    def test_a_bare_key_with_no_number_is_left_alone(self):
        assert references.renumber("Bare @zzz here.", self.NUMBERS) == "Bare @zzz here."

    def test_an_email_address_is_not_a_citation(self):
        numbers = dict(self.NUMBERS, gmail=9, example=8)
        text = "Write to <prasad.talasila@gmail.com> or name@example.com about [@a]."
        assert (
            references.renumber(text, numbers)
            == "Write to <prasad.talasila@gmail.com> or name@example.com about [1]."
        )

    def test_renumbers_exactly_what_the_gate_counts(self):
        text = "A [@a]. B [-@b]. C @c. Code `[@d]`. Mail x@e.com."
        numbers = {k: i for i, k in enumerate("abcde", start=1)}
        out = references.renumber(text, numbers)
        assert out.count("[") - out.count("`[") == len(references.used_citekeys(text))

    def test_a_group_is_left_alone_if_any_key_is_unnumbered(self):
        assert references.renumber("[@a; @zzz]", self.NUMBERS) == "[@a; @zzz]"

    def test_a_locator_group_is_left_alone_if_the_key_is_unnumbered(self):
        assert references.renumber("[@zzz, p. 33]", self.NUMBERS) == "[@zzz, p. 33]"

    def test_a_citation_inside_a_code_fence_is_untouched(self):
        text = "Write:\n\n```markdown\n[@a]\n```\n\nReal [@b].\n"
        assert (
            references.renumber(text, self.NUMBERS)
            == "Write:\n\n```markdown\n[@a]\n```\n\nReal [2].\n"
        )

    def test_a_citation_inside_an_inline_code_span_is_untouched(self):
        assert (
            references.renumber("Use `[@a]` for this. Real [@b].", self.NUMBERS)
            == "Use `[@a]` for this. Real [2]."
        )

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("[@{brace.one}] and @{brace_two}.", "[1] and [2]."),
            ("[@plain; @{brace.one}]", "[1], [3]"),
            ("[@{brace.one}, p. 3]", "[1, p. 3]"),
            ("[@müller_2020] and pre-@plain", "[4] and pre-[3]"),
            ("(@ex) An example.\n\nSee @ex and [@ex].", "(@ex) An example.\n\nSee @ex and [5]."),
        ],
    )
    def test_the_gates_own_citations_renumber(self, text, expected):
        numbers = {"brace.one": 1, "brace_two": 2, "plain": 3, "müller_2020": 4, "ex": 5}
        assert references.renumber(text, numbers) == expected

    def test_a_comment_inside_a_group_is_kept(self):
        assert references.renumber("[@a <!-- n --> ]", self.NUMBERS) == "[[1] <!-- n --> ]"

    def test_a_locator_carrying_a_code_span_keeps_it_verbatim(self):
        assert (
            references.renumber("See [@a, see `x`] for the flag.", self.NUMBERS)
            == "See [1, see `x`] for the flag."
        )


class TestNumberedMarkdown:
    def _seed(self, con):
        for key, title, year in [("b2024", "B Paper", "2024"), ("a2023", "A Paper", "2023")]:
            ledger.upsert_reference(
                con,
                make_reference(
                    citekey=key,
                    title=title,
                    year=year,
                    fields={"author": "Doe, Jane", "journal": "J. Things"},
                ),
            )

    def test_numbers_body_and_rebuilds_the_list_without_citekey_labels(self, ledger_con):
        self._seed(ledger_con)
        out = references.numbered_markdown("# T\n\nOne [@b2024]. Two [@a2023].\n", ledger_con)

        assert "One [1]. Two [2]." in out
        assert '[1] J. Doe, "B Paper," *J. Things*, 2024.' in out
        assert "`b2024`" not in out
        assert "[@" not in out

    def test_replaces_an_existing_section_and_keeps_its_heading(self, ledger_con):
        self._seed(ledger_con)
        draft = (
            "One [@b2024].\n\n## 6. References\n\n"
            '[1] J. Doe, "B Paper," *J. Things*, 2024. `b2024`\n'
        )
        out = references.numbered_markdown(draft, ledger_con)

        assert out.count("References") == 1
        assert "## 6. References" in out
        assert "`b2024`" not in out

    def test_replaces_a_bibliography_section_and_keeps_its_title(self, ledger_con):
        self._seed(ledger_con)
        draft = (
            "One [@b2024].\n\n## Bibliography\n\n"
            '[1] J. Doe, "B Paper," *J. Things*, 2024. `b2024`\n'
        )
        out = references.numbered_markdown(draft, ledger_con)

        assert "## Bibliography" in out
        assert "References" not in out
        assert out.count("[1] J. Doe") == 1

    def test_an_explicit_heading_overrides_the_drafts_own(self, ledger_con):
        self._seed(ledger_con)
        draft = "One [@b2024].\n\n## 6. References\n\n[1] old entry\n"
        out = references.numbered_markdown(draft, ledger_con, heading="Further reading")
        assert "## Further reading" in out
        assert "6. References" not in out

    def test_a_draft_with_no_citations_is_returned_unchanged(self, ledger_con):
        assert (
            references.numbered_markdown("# T\n\nJust prose.\n", ledger_con)
            == "# T\n\nJust prose.\n"
        )

    def test_an_uncited_draft_keeps_a_references_section_it_already_had(self, ledger_con):
        draft = "# T\n\nJust prose.\n\n## References\n\n- A hand-written pointer\n"
        assert references.numbered_markdown(draft, ledger_con) == draft

    def test_numbering_follows_first_appearance_not_the_ledger(self, ledger_con):
        self._seed(ledger_con)
        out = references.numbered_markdown("First [@a2023]. Then [@b2024].\n", ledger_con)
        assert "First [1]. Then [2]." in out
        assert out.index("A Paper") < out.index("B Paper")

    def test_content_after_an_existing_section_survives(self, ledger_con):
        self._seed(ledger_con)
        draft = "One [@b2024].\n\n## References\n\n[1] old entry\n\n## Appendix\n\nSupplementary.\n"
        out = references.numbered_markdown(draft, ledger_con)
        assert "## Appendix" in out
        assert "Supplementary." in out
        assert out.index("## References") < out.index("## Appendix")

    def test_a_citekey_cited_only_in_the_surviving_tail_is_still_numbered(self, ledger_con):
        self._seed(ledger_con)
        draft = (
            "Body cites [@b2024].\n\n## References\n\n[1] old\n\n"
            "## Appendix\n\nAlso cites [@a2023] here.\n"
        )
        out = references.numbered_markdown(draft, ledger_con)
        assert "[@" not in out
        assert "Body cites [1]." in out
        assert "Also cites [2] here." in out
        assert '[2] J. Doe, "A Paper," *J. Things*, 2023.' in out


class TestWriteNumbered:
    def test_writes_into_the_output_directory_and_leaves_the_draft_alone(
        self, isolated_config, tmp_path
    ):
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith2024", title="A Paper", year="2024")
        )
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        original = "Body [@smith2024].\n"
        draft.write_text(original)
        out_dir = tmp_path / "rendered"

        out_path = references.write_numbered(draft, out_dir)

        assert out_path == out_dir / "draft.md"
        assert "Body [1]." in out_path.read_text()
        assert draft.read_text() == original, "the gated source must not be rewritten"

    def test_a_text_override_is_numbered_instead_of_the_file_on_disk(
        self, isolated_config, tmp_path
    ):
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith2024", title="A Paper", year="2024")
        )
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("Unsubstituted [@smith2024].\n")
        out_dir = tmp_path / "rendered"

        out_path = references.write_numbered(draft, out_dir, text="Substituted [@smith2024].\n")

        assert "Substituted [1]." in out_path.read_text()


class TestBuildSection:
    def test_builds_formatted_entries_in_given_order(self, ledger_con):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="b2024", title="B Paper", year="2024")
        )
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="A Paper", year="2023")
        )

        section = references.build_section(["b2024", "a2024"], ledger_con)
        lines = section.splitlines()
        assert lines[0] == "## References"
        assert "[1] *B Paper*, 2024. `b2024`" in section
        assert "[2] *A Paper*, 2023. `a2024`" in section
        assert section.index("b2024") < section.index("a2024")

    def test_entry_uses_the_full_bib_fields_when_the_ledger_has_them(self, ledger_con):
        ledger.upsert_reference(
            ledger_con,
            make_reference(
                citekey="doe2024",
                title="Digital Twins as a Service",
                year="2024",
                fields={
                    "author": "Doe, Jane and Roe, Richard",
                    "journal": "IEEE Trans. Testing",
                    "volume": "3",
                    "number": "2",
                    "pages": "11--20",
                    "abstract": "Not part of a reference entry.",
                },
            ),
        )
        section = references.build_section(["doe2024"], ledger_con)
        assert (
            '[1] J. Doe and R. Roe, "Digital Twins as a Service," '
            "*IEEE Trans. Testing*, vol. 3, no. 2, pp. 11–20, 2024. `doe2024`"
        ) in section
        assert "abstract" not in section.lower()

    def test_entry_falls_back_to_title_and_year_without_bib_fields(self, ledger_con):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="bare2024", title="A Paper", year="2024")
        )
        ledger_con.execute("UPDATE items SET bib_fields = NULL WHERE citekey = 'bare2024'")
        section = references.build_section(["bare2024"], ledger_con)
        assert "[1] *A Paper*, 2024. `bare2024`" in section

    def test_entry_survives_unparseable_bib_fields(self, ledger_con):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="bad2024", title="A Paper", year="2024")
        )
        ledger_con.execute("UPDATE items SET bib_fields = 'not json' WHERE citekey = 'bad2024'")
        section = references.build_section(["bad2024"], ledger_con)
        assert "[1] *A Paper*, 2024. `bad2024`" in section

    def test_custom_heading(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a2024"))
        section = references.build_section(["a2024"], ledger_con, heading="6. References")
        assert section.startswith("## 6. References")

    def test_missing_citekey_raises_keyerror(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a2024"))
        with pytest.raises(KeyError, match="fabricated2024"):
            references.build_section(["a2024", "fabricated2024"], ledger_con)

    def test_missing_citekey_raises_the_dedicated_subclass(self, ledger_con):
        with pytest.raises(reference_entries.MissingCitekey):
            references.build_section(["fabricated2024"], ledger_con)


class TestApply:
    def test_a_hand_built_bibliography_is_replaced_not_followed_by_a_second_list(
        self, isolated_config
    ):
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith2024", title="A Paper", year="2024")
        )
        con.close()
        draft = content_draft(isolated_config, "tutorial.md")
        draft.write_text(
            "# Lesson\n\n## Where to go next\n\nA filter helps [@smith2024].\n\n"
            "## Bibliography\n\n[1] A Paper, 2024. `smith2024`\n"
        )
        references.apply(draft)

        text = draft.read_text()
        assert "## Bibliography" not in text
        assert text.count("## References") == 1
        assert text.count("[1] ") == 1

    def test_no_citekeys_returns_message_and_leaves_file_untouched(self, isolated_config, tmp_path):
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("Just prose, nothing cited.\n")
        result = references.apply(draft)
        assert "nothing to do" in result
        assert draft.read_text() == "Just prose, nothing cited.\n"

    def test_appends_section_when_none_exists(self, isolated_config, tmp_path):
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith2024", title="A Paper", year="2024")
        )
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("Body text citing [@smith2024].\n")
        result = references.apply(draft)

        text = draft.read_text()
        assert "wrote References section with 1 citekey(s)" in result
        assert "## References" in text
        assert "[1] *A Paper*, 2024. `smith2024`" in text
        assert text.index("Body text") < text.index("## References")

    def test_replaces_existing_section_idempotently(self, isolated_config, tmp_path):
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith2024", title="A Paper", year="2024")
        )
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("Body text citing [@smith2024].\n\n## References\n\n- stale entry\n")
        references.apply(draft)
        first_pass = draft.read_text()
        assert first_pass.count("## References") == 1
        assert "stale entry" not in first_pass

        references.apply(draft)
        second_pass = draft.read_text()
        assert second_pass.count("## References") == 1
        assert second_pass == first_pass

    def test_content_after_an_existing_section_survives(self, isolated_config, tmp_path):
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith2024", title="A Paper", year="2024")
        )
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "Body text citing [@smith2024].\n\n"
            "## References\n\n- stale entry\n\n"
            "## Appendix\n\nSupplementary material.\n"
        )
        references.apply(draft)

        text = draft.read_text()
        assert "## Appendix" in text
        assert "Supplementary material." in text
        assert text.index("## References") < text.index("## Appendix")


class TestMainCli:
    def test_success_prints_result_and_returns_0(
        self, isolated_config, tmp_path, capsys, monkeypatch
    ):
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith2024"))
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("[@smith2024]\n")

        monkeypatch.setattr(sys, "argv", ["references.py", str(draft)])
        rc = references.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert "wrote References section" in out

    def test_missing_citekey_prints_error_and_returns_1(
        self, isolated_config, ledger_con, tmp_path, capsys, monkeypatch
    ):
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("[@fabricated2024]\n")

        monkeypatch.setattr(sys, "argv", ["references.py", str(draft)])
        rc = references.main()
        err = capsys.readouterr().err
        assert rc == 1
        assert "[error]" in err
        assert "fabricated2024" in err

    def test_runs_with_bare_system_python3(self, system_python, isolated_config, tmp_path):
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith2024", title="A Paper", year="2024")
        )
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("Citing [@smith2024] here.\n")

        result = run_python(
            "-m",
            "chitragupta.draft",
            "references",
            str(draft),
            python=system_python,
            env={"PATH": "/usr/bin:/bin", "CONTENT_DIR": str(isolated_config.CONTENT_DIR)},
        )
        assert result.returncode == 0, result.stderr
        assert "wrote References section" in result.stdout


class TestInputsAreConfinedToContent:
    def test_a_draft_outside_the_content_directory_is_refused(self, isolated_config, tmp_path):
        loose = tmp_path / "loose.md"
        loose.write_text("A claim [@a_2024].\n")
        with pytest.raises(references.config.OutsideContentDir, match="outside the content"):
            references.apply(loose)

    def test_a_draft_anywhere_under_content_is_accepted(self, isolated_config):
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="a_2024", title="A Paper", year="2024"))
        con.close()
        scratch = isolated_config.CONTENT_DIR / "scratch" / "notes.md"
        scratch.parent.mkdir(parents=True)
        scratch.write_text("A claim [@a_2024].\n")

        references.apply(scratch)

        assert "a_2024" in scratch.read_text()

    def test_the_cli_reports_it_rather_than_raising(
        self, isolated_config, tmp_path, monkeypatch, capsys
    ):
        loose = tmp_path / "loose.md"
        loose.write_text("A claim [@a_2024].\n")
        monkeypatch.setattr(sys, "argv", ["references.py", str(loose)])

        rc = references.main()

        assert rc == 1
        assert "outside the content directory" in capsys.readouterr().err
