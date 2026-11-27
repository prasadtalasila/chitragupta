import sqlite3
import time

import pytest

from chitragupta import citation_gate, ledger

from tests.conftest import add_citable, content_draft, make_reference, run_python
from tests.ledger_faults import damage_past_the_header, leave_hot_journal


class TestExtractLatexCitations:
    @pytest.mark.parametrize(
        "cmd",
        [
            "cite",
            "citep",
            "citet",
            "parencite",
            "textcite",
            "autocite",
            "citeauthor",
            "citeyear",
            "citealp",
            "citealt",
            "footcite",
            "smartcite",
            "fullcite",
            "nocite",
            "citenum",
            "citeyearpar",
        ],
    )
    def test_all_recognized_commands(self, cmd):
        assert citation_gate.extract_citekeys_from_line(f"\\{cmd}{{smith2024}}") == ["smith2024"]

    @pytest.mark.parametrize("cmd", ["Citep", "Citet", "Textcite", "Parencite"])
    def test_capitalized_biblatex_forms(self, cmd):
        assert citation_gate.extract_citekeys_from_line(f"\\{cmd}{{smith2024}}") == ["smith2024"]

    def test_starred_variant(self):
        assert citation_gate.extract_citekeys_from_line("\\citep*{smith2024}") == ["smith2024"]

    def test_multiple_keys_comma_separated(self):
        assert citation_gate.extract_citekeys_from_line("\\cite{a2024,b2024}") == ["a2024", "b2024"]

    def test_multiple_keys_with_spaces(self):
        assert citation_gate.extract_citekeys_from_line("\\cite{a2024, b2024}") == [
            "a2024",
            "b2024",
        ]

    def test_optional_bracket_args_before_key(self):
        assert citation_gate.extract_citekeys_from_line("\\citep[see][p.\\ 5]{smith2024}") == [
            "smith2024"
        ]

    def test_biblatex_multicite_second_group_is_caught(self):
        assert citation_gate.extract_citekeys_from_line("\\cites{a2024}{b2024}") == [
            "a2024",
            "b2024",
        ]

    def test_multicite_with_pre_post_notes_per_key(self):
        assert citation_gate.extract_citekeys_from_line(
            "\\parencites[see][p.\\ 3]{a2024}[cf.][p.\\ 9]{b2024}"
        ) == ["a2024", "b2024"]

    def test_multicite_in_a_document_reports_the_right_line(self):
        text = "Prose first.\n\\cites{a2024}{b2024} close the argument.\n"
        assert citation_gate.extract_citekeys(text) == [(2, "a2024"), (2, "b2024")]

    def test_braces_inside_a_between_group_bracket_note_are_not_keys(self):
        assert citation_gate.extract_citekeys_from_line("\\cites{a2024}[\\emph{cf}]{b2024}") == [
            "a2024",
            "b2024",
        ]

    def test_a_prose_brace_group_after_whitespace_is_not_a_second_key(self):
        assert citation_gate.extract_citekeys_from_line("\\citep{a2024} {emphasised}") == ["a2024"]

    def test_unrelated_command_not_matched(self):
        assert citation_gate.extract_citekeys_from_line("\\section{Introduction}") == []

    def test_plain_text_no_match(self):
        assert citation_gate.extract_citekeys_from_line("Just some prose.") == []

    @pytest.mark.parametrize(
        "text",
        [
            "\\citep {smith2024}",
            "\\citep [see]{smith2024}",
            "\\citep *{smith2024}",
        ],
    )
    def test_whitespace_between_command_and_arguments(self, text):
        assert citation_gate.extract_citekeys_from_line(text) == ["smith2024"]


class TestLatexCiteRegexBacktracking:
    def test_bracket_run_without_a_key_group_completes_fast(self):
        text = "\\cite" + " [a]" * 64 + " x"
        start = time.perf_counter()
        assert citation_gate.extract_citekeys(text) == []
        assert time.perf_counter() - start < 2.0

    def test_paragraph_break_between_command_and_key_is_not_a_citation(self):
        assert citation_gate.extract_citekeys("\\citep\n\n{smith2024}\n") == []


class TestExtractPandocCitations:
    def test_bracketed_single_key(self):
        assert citation_gate.extract_citekeys_from_line("Some claim [@smith2024].") == ["smith2024"]

    def test_bracketed_multiple_keys(self):
        assert citation_gate.extract_citekeys_from_line("[@a2024; @b2024]") == ["a2024", "b2024"]

    def test_bare_at_key(self):
        assert citation_gate.extract_citekeys_from_line("As @smith2024 showed...") == ["smith2024"]

    def test_suppress_author_form(self):
        assert citation_gate.extract_citekeys_from_line("Smith (-@smith2024) showed...") == [
            "smith2024"
        ]

    def test_digit_start_key_is_caught(self):
        assert citation_gate.extract_citekeys_from_line("[@3dprinting_2020]") == ["3dprinting_2020"]

    def test_underscore_start_key_is_caught(self):
        assert citation_gate.extract_citekeys_from_line("As @_draft2020 argued...") == [
            "_draft2020"
        ]

    def test_key_with_hyphens_and_underscores(self):
        assert citation_gate.extract_citekeys_from_line("[@jacoby_open-source_2023]") == [
            "jacoby_open-source_2023"
        ]

    def test_key_with_double_hyphen(self):
        assert citation_gate.extract_citekeys_from_line(
            "[@zech_digital-twins-as--service_2024]"
        ) == ["zech_digital-twins-as--service_2024"]

    def test_internal_colon_is_part_of_the_key(self):
        assert citation_gate.extract_citekeys_from_line("see [@smith:2020]") == ["smith:2020"]

    def test_internal_dot_is_part_of_the_key(self):
        assert citation_gate.extract_citekeys_from_line("as @doe.2020 showed") == ["doe.2020"]

    def test_internal_plus_is_part_of_the_key(self):
        assert citation_gate.extract_citekeys_from_line("as @a+b showed") == ["a+b"]

    def test_sentence_final_punctuation_is_not_part_of_the_key(self):
        assert citation_gate.extract_citekeys_from_line("shown by @key.") == ["key"]

    def test_group_mixes_plain_and_punctuated_keys(self):
        assert citation_gate.extract_citekeys_from_line("[@a; @b:c]") == ["a", "b:c"]

    def test_email_address_not_mistaken_for_citation(self):
        assert (
            citation_gate.extract_citekeys_from_line("Contact us at name@example.com for details.")
            == []
        )

    def test_email_alongside_real_citation(self):
        line = "See [@smith2024] or email name@example.com."
        assert citation_gate.extract_citekeys_from_line(line) == ["smith2024"]

    def test_mixed_latex_and_pandoc_on_one_line(self):
        line = "As shown \\citep{a2024} and also [@b2024]."
        assert citation_gate.extract_citekeys_from_line(line) == ["a2024", "b2024"]

    def test_latex_internal_at_macro_not_mistaken_for_citation(self):
        assert citation_gate.extract_citekeys_from_line(r"\@ifundefined{foo}{}{}") == []
        line = r"\makeatletter\@ifundefined{xetex}{}{}\makeatother"
        assert citation_gate.extract_citekeys_from_line(line) == []


class TestExtractCitekeysWholeDocument:
    def test_wrapped_citep_is_caught(self):
        text = "See \\citep{real_key,\n       fabricated_key} for details.\n"
        keys = [key for _, key in citation_gate.extract_citekeys(text)]
        assert sorted(keys) == ["fabricated_key", "real_key"]

    def test_document_where_every_citation_is_wrapped_and_fabricated(self):
        text = "\\citealp{totally_made_up_key,\n          another_fake} shown here.\n"
        keys = [key for _, key in citation_gate.extract_citekeys(text)]
        assert sorted(keys) == ["another_fake", "totally_made_up_key"]

    def test_line_number_points_at_match_start(self):
        text = "line one\nline two \\citep{smith2024}\nline three\n"
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_whitespace_including_newline_between_command_and_brace(self):
        text = "See \\citep\n{smith2024} for details.\n"
        assert citation_gate.extract_citekeys(text) == [(1, "smith2024")]

    def test_results_are_in_document_order_not_regex_pass_order(self):
        text = "[@later_pandoc]\nprose\n\\citep{earlier_latex}\nmore\n[@even_later]\n"
        assert citation_gate.extract_citekeys(text) == [
            (1, "later_pandoc"),
            (3, "earlier_latex"),
            (5, "even_later"),
        ]


class TestCodeAndVerbatimExclusion:
    def test_python_decorator_in_fenced_code_is_not_a_citation(self):
        text = "```python\n@dataclass\nclass Foo:\n    pass\n```\n"
        assert citation_gate.extract_citekeys(text) == []

    def test_inline_code_span_is_not_a_citation(self):
        assert citation_gate.extract_citekeys("use the `@override` annotation") == []
        assert citation_gate.extract_citekeys("run `npm install @scoped/pkg`") == []

    def test_whitespace_tolerance_does_not_bridge_a_blanked_verbatim_block(self):
        text = (
            "Refer to \\nocite\n\\begin{verbatim}\nanything\n\\end{verbatim}\n{\\bfseries note}\n"
        )
        assert citation_gate.extract_citekeys(text) == []

    def test_latex_verbatim_environment_is_not_scanned(self):
        text = "\\begin{verbatim}\n\\citep{fake_key}\n\\end{verbatim}\n"
        assert citation_gate.extract_citekeys(text) == []

    def test_real_citation_after_a_fenced_block_is_still_caught(self):
        text = "```python\n@dataclass\nclass Foo: pass\n```\nAs shown in [@smith2024].\n"
        assert citation_gate.extract_citekeys(text) == [(5, "smith2024")]

    def test_tilde_fenced_code_is_not_a_citation(self):
        text = "~~~python\n@dataclass\nclass Foo:\n    pass\n~~~\n"
        assert citation_gate.extract_citekeys(text) == []

    def test_stray_fence_marker_in_prose_does_not_shift_pairing(self):
        text = (
            "A fence opens with three backticks (```) on its own line.\n"
            "Grounded claim [@smith2024].\n"
            "```python\n"
            "@dataclass\n"
            "class Foo: pass\n"
            "```\n"
        )
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_inline_triple_backtick_span_is_not_a_fence_opener(self):
        text = "``` bash -c ``` runs a command.\nGrounded claim [@smith2024].\n"
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_tab_indented_marker_is_not_a_fence(self):
        text = "\t```\nGrounded claim [@smith2024].\n"
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_indented_marker_is_not_a_fence(self):
        text = "    ```\nGrounded claim [@smith2024].\n"
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_an_unclosed_fence_is_prose_as_pandoc_reads_it(self):
        text = "```python\n@dataclass\nclass Foo: pass\n\nSee [@fabricated_2026].\n"
        assert citation_gate.extract_citekeys(text) == [(2, "dataclass"), (5, "fabricated_2026")]


class TestFragments:
    def test_a_fragment_indented_under_its_lost_list_item_still_cites(self):
        assert citation_gate.extract_citekeys_from_line("    continued [@smith2024]") == [
            "smith2024"
        ]

    def test_a_fragment_keeps_latex_rules_when_asked(self):
        line = "The `twin' view \\citep{smith2024} is `neat'."
        assert citation_gate.extract_citekeys_from_line(line, latex=True) == ["smith2024"]


class TestLatexBlanking:
    def test_double_backtick_quotes_do_not_eat_a_citation(self):
        text = "The ``digital twin'' approach \\citep{fabricated2024} extends the ``model'' view.\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "fabricated2024")]

    def test_single_backtick_quotes_do_not_eat_a_citation(self):
        text = "The `digital twin' approach \\citep{smith2024} is `neat'.\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "smith2024")]

    def test_fence_blanking_is_off_in_latex_mode(self):
        text = "He said ```why''' twice.\nStill cited \\citep{smith2024}.\nAnd ```again'''.\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(2, "smith2024")]

    def test_latex_verbatim_is_still_blanked_in_latex_mode(self):
        text = "\\begin{verbatim}\n\\citep{fake_key}\n\\end{verbatim}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == []

    def test_markdown_mode_is_the_default_and_unchanged(self):
        assert citation_gate.extract_citekeys("use the `@override` annotation") == []

    def test_check_document_gates_a_tex_draft_through_latex_quoting(self, tmp_path):
        draft = tmp_path / "chapter.tex"
        draft.write_text(
            "The ``digital twin'' approach \\citep{fabricated2024} extends the ``model'' view.\n",
            encoding="utf-8",
        )
        result = citation_gate.check_document(draft, {"real2024"})
        assert result.total_citations == 1
        assert result.unknown == [(1, "fabricated2024")]

    def test_check_document_md_still_blanks_inline_code(self, tmp_path):
        draft = tmp_path / "chapter.md"
        draft.write_text("use the `@override` annotation\n", encoding="utf-8")
        result = citation_gate.check_document(draft, set())
        assert result.ok and result.total_citations == 0


class TestLatexCommentsAndVerb:
    def test_a_commented_out_citation_is_not_a_citation(self):
        assert citation_gate.extract_citekeys("% \\cite{commented}\n", latex=True) == []

    def test_a_comment_after_real_prose_on_the_same_line(self):
        text = "Cited \\citep{real2024}.  % was \\citep{dropped2024}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "real2024")]

    def test_a_comment_ends_at_the_line_it_is_on(self):
        text = "% \\cite{commented}\nStill cited \\citep{real2024}.\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(2, "real2024")]

    def test_a_commented_pandoc_key_is_inert_too(self):
        assert citation_gate.extract_citekeys("% see @commented2024\n", latex=True) == []

    def test_an_escaped_percent_does_not_start_a_comment(self):
        text = "\\citep[see 5\\% of]{real2024} and \\citep{second2024}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [
            (1, "real2024"),
            (1, "second2024"),
        ]

    def test_a_percent_after_a_line_break_is_a_comment(self):
        assert citation_gate.extract_citekeys("Row \\\\% \\cite{dead}\n", latex=True) == []

    def test_a_literal_percent_after_a_line_break_still_escapes(self):
        text = "Row \\\\\\% \\citep{real2024}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "real2024")]

    def test_verb_content_is_inert(self):
        assert citation_gate.extract_citekeys("\\verb|\\cite{x}|\n", latex=True) == []

    def test_verb_takes_an_arbitrary_delimiter(self):
        assert citation_gate.extract_citekeys("\\verb+\\cite{x}+\n", latex=True) == []

    def test_the_starred_verb_is_recognized(self):
        assert citation_gate.extract_citekeys("\\verb*|\\cite{x}|\n", latex=True) == []

    def test_verb_with_a_star_delimiter(self):
        assert citation_gate.extract_citekeys("\\verb**\\cite{x}*\n", latex=True) == []

    def test_a_delimiter_is_never_a_letter(self):
        text = "\\verbatiminput{sample.tex} \\citep{fabricated2024}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "fabricated2024")]

    def test_a_percent_inside_verb_does_not_comment_out_the_rest(self):
        text = "\\verb|50%| then \\citep{real2024}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "real2024")]

    def test_a_verb_inside_a_comment_is_still_commented_out(self):
        assert citation_gate.extract_citekeys("% \\verb|x| \\cite{dead}\n", latex=True) == []

    def test_an_unclosed_verb_leaves_the_line_alone(self):
        text = "\\verb|unclosed \\citep{fabricated2024}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "fabricated2024")]

    def test_markdown_mode_gains_no_comment_rule(self):
        assert citation_gate.extract_citekeys("50% done, see [@real2024]\n") == [(1, "real2024")]

    def test_a_run_of_unclosed_verbs_completes_fast(self):
        text = "".join(f"\\verb{chr(0x4E00 + i)}" for i in range(2000)) + " \\citep{real2024}"
        start = time.perf_counter()
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "real2024")]
        assert time.perf_counter() - start < 2.0

    def test_a_percent_inside_url_is_not_a_comment(self):
        text = "See \\url{http://x/a%20b} and \\citep{fabricated2024}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "fabricated2024")]

    def test_a_percent_inside_href_is_not_a_comment(self):
        text = "See \\href{http://x/a%20b}{the page}, \\citep{fabricated2024}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "fabricated2024")]

    def test_a_url_inside_a_comment_is_still_commented_out(self):
        text = "% \\url{http://x/a%20b} \\cite{dead}\n"
        assert citation_gate.extract_citekeys(text, latex=True) == []


class TestCheckDocument:
    def test_reports_unknown_with_correct_line_numbers(self, tmp_path):
        path = tmp_path / "draft.md"
        path.write_text("Line one [@known2024].\nLine two [@unknown2024].\n")
        result = citation_gate.check_document(path, citable={"known2024"})

        assert result.total_citations == 2
        assert result.unknown == [(2, "unknown2024")]
        assert result.ok is False

    def test_all_known_is_ok(self, tmp_path):
        path = tmp_path / "draft.md"
        path.write_text("[@a2024] and [@b2024]\n")
        result = citation_gate.check_document(path, citable={"a2024", "b2024"})
        assert result.ok is True
        assert result.total_citations == 2

    def test_a_ledger_key_that_is_only_a_prefix_fails(self, tmp_path):
        path = tmp_path / "draft.md"
        path.write_text("Claim [@smith:2020].\n")
        result = citation_gate.check_document(path, citable={"smith"})
        assert result.unknown == [(1, "smith:2020")]
        assert result.ok is False

    def test_no_citations_is_ok_with_zero_total(self, tmp_path):
        path = tmp_path / "draft.md"
        path.write_text("Just prose, no citations at all.\n")
        result = citation_gate.check_document(path, citable=set())
        assert result.ok is True
        assert result.total_citations == 0


class TestRun:
    def test_empty_ledger_warns_and_fails(self, isolated_config, tmp_path, capsys):
        ledger.connect().close()
        path = content_draft(isolated_config, "draft.md")
        path.write_text("[@smith2024]\n")

        rc = citation_gate.run([str(path)])
        captured = capsys.readouterr()

        assert rc == 1
        assert "WARNING: ledger is empty" in captured.err
        assert "FAIL" in captured.out
        assert "@smith2024 not found in ledger" in captured.out

    def test_known_citekey_passes(self, isolated_config, tmp_path, capsys):
        con = ledger.connect()
        add_citable(con, "smith2024")
        con.close()

        path = content_draft(isolated_config, "draft.md")
        path.write_text("[@smith2024]\n")
        rc = citation_gate.run([str(path)])
        out = capsys.readouterr().out

        assert rc == 0
        assert "OK" in out
        assert "1 citation(s), all verified" in out

    def test_multiple_files_mixed_result(self, isolated_config, tmp_path, capsys):
        con = ledger.connect()
        add_citable(con, "smith2024")
        con.close()

        good = content_draft(isolated_config, "good.md")
        good.write_text("[@smith2024]\n")
        bad = content_draft(isolated_config, "bad.md")
        bad.write_text("[@fabricated2024]\n")

        rc = citation_gate.run([str(good), str(bad)])
        out = capsys.readouterr().out

        assert rc == 1
        assert f"OK    {good}" in out
        assert f"FAIL  {bad}" in out


class TestUnparsedRowsAreNotCitable:
    @pytest.mark.parametrize("status", ["no_pdf", "discovered", "parse_failed"])
    def test_an_unparsed_key_fails_naming_its_status(
        self, isolated_config, tmp_path, capsys, status
    ):
        con = ledger.connect()
        add_citable(con, "smith2024")
        con.execute("UPDATE items SET status = ? WHERE citekey = 'smith2024'", (status,))
        con.commit()
        con.close()
        path = content_draft(isolated_config, "draft.md")
        path.write_text("Intro.\n\nA web page describes the tool [@smith2024].\n")

        rc = citation_gate.run([str(path)])
        out = capsys.readouterr().out

        assert rc == 1
        assert (
            f"{path}:3: @smith2024 is in the ledger but has no parsed PDF (status {status})" in out
        )
        assert "not found in ledger" not in out

    def test_an_absent_key_keeps_its_own_message(self, isolated_config, capsys):
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith2024"))
        con.close()
        path = content_draft(isolated_config, "draft.md")
        path.write_text("[@smith2024] and [@fabricated2024]\n")

        assert citation_gate.run([str(path)]) == 1
        out = capsys.readouterr().out
        assert "@fabricated2024 not found in ledger -- not sourced from bib sync" in out
        assert "@smith2024 is in the ledger but has no parsed PDF (status no_pdf)" in out
        assert "2 unresolved citekey(s)" in out

    def test_a_ledger_of_only_unparsed_rows_warns_no_parsed_source(self, isolated_config, capsys):
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith2024"))
        con.close()
        path = content_draft(isolated_config, "draft.md")
        path.write_text("[@smith2024]\n")

        assert citation_gate.run([str(path)]) == 1
        err = capsys.readouterr().err
        assert "ledger holds no parsed source" in err
        assert "ledger is empty" not in err

    def test_check_text_records_the_status_of_an_unparsed_key(self, tmp_path):
        result = citation_gate.check_text(
            tmp_path / "d.md", "[@a2024] [@b2024]\n", {"a2024"}, {"b2024": "no_pdf"}
        )
        assert result.unknown == [(1, "b2024")]
        assert result.unparsed == {"b2024": "no_pdf"}


class TestLedgerItCannotRead:
    @staticmethod
    def _gate(cfg, text, capsys):
        path = content_draft(cfg, "drafts/draft.md")
        path.write_text(text)
        rc = citation_gate.run([str(path)])
        return rc, capsys.readouterr()

    @staticmethod
    def _assert_no_verdict(captured):
        assert captured.out == ""  # no OK or FAIL line to mistake for one
        assert captured.err.startswith(
            "ERROR: the citation gate could not read the ledger, so no citekey was checked."
        )
        assert "not a verdict on any draft (exit 3)" in captured.err

    def test_a_hot_journal_exits_3_with_its_cause(self, isolated_config, capsys):
        con = ledger.connect()
        add_citable(con, "smith2024")
        con.close()
        journal = leave_hot_journal(isolated_config.LEDGER_PATH)
        rc, captured = self._gate(isolated_config, "[@someFabricatedKey2099]\n", capsys)
        assert rc == 3
        self._assert_no_verdict(captured)
        assert journal.name in captured.err
        assert "chitragupta.corpus sync" in captured.err

    def test_a_ledger_needing_a_sync_exits_3_even_for_a_citation_free_draft(
        self, isolated_config, capsys
    ):
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(isolated_config.LEDGER_PATH)
        raw.execute("CREATE TABLE items (citekey TEXT PRIMARY KEY)")
        raw.close()
        rc, captured = self._gate(isolated_config, "No citations here.\n", capsys)
        assert rc == 3
        self._assert_no_verdict(captured)
        assert "predates this version's schema" in captured.err

    def test_a_ledger_damaged_past_its_header_exits_3(self, isolated_config, capsys):
        con = ledger.connect()
        add_citable(con, "smith2024")
        con.close()
        damage_past_the_header(isolated_config.LEDGER_PATH)
        rc, captured = self._gate(isolated_config, "[@smith2024]\n", capsys)
        assert rc == 3
        self._assert_no_verdict(captured)
        assert "damaged" in captured.err

    def test_the_usage_documents_exit_3(self):
        assert "3 = the ledger could not be read" in citation_gate.USAGE


class TestDeadLauncherWarning:
    @staticmethod
    def draft(cfg) -> str:
        con = ledger.connect()
        add_citable(con, "smith2024")
        con.close()
        path = content_draft(cfg, "draft.md")
        path.write_text("A claim [@smith2024].\n", encoding="utf-8")
        return str(path)

    def test_a_dead_launcher_is_warned_about_without_changing_the_verdict(
        self, isolated_config, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            citation_gate.gate_liveness.launcher_configs,
            "faults",
            lambda root: [
                ".claude/settings.json: `python` is not on an absolute PATH entry, so a hook cannot start."
            ],
        )
        rc = citation_gate.run([self.draft(isolated_config)])
        captured = capsys.readouterr()

        assert rc == 0
        assert "OK" in captured.out
        assert "`python` is not on an absolute PATH entry" in captured.err
        assert "docs/HOOKS.md" in captured.err
        assert "WARNING" not in captured.out, "the verdict stream stays the verdict"

    def test_a_sound_launcher_says_nothing(self, isolated_config, monkeypatch, capsys):
        monkeypatch.setattr(citation_gate.gate_liveness.launcher_configs, "faults", lambda root: [])
        assert citation_gate.run([self.draft(isolated_config)]) == 0
        assert capsys.readouterr().err == ""


class TestCliEntrypoint:
    def test_no_args_prints_usage_and_exits_2(self, isolated_config):
        result = run_python("-m", "chitragupta.draft", "gate")
        assert result.returncode == 2
        assert "Usage:" in result.stderr

    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help_prints_usage_and_exits_0(self, isolated_config, flag):
        result = run_python("-m", "chitragupta.draft", "gate", flag)
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "Traceback" not in result.stderr

    def test_no_args_in_process_is_the_same_usage_error(self, isolated_config, capsys):
        assert citation_gate.main([]) == 2
        assert "Usage:" in capsys.readouterr().err

    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help_in_process_is_the_same_answer(self, isolated_config, capsys, flag):
        assert citation_gate.main([flag]) == 0
        assert "Usage:" in capsys.readouterr().out

    def test_gate_help_reads_like_click(self, isolated_config):
        out = run_python("-m", "chitragupta.draft", "gate", "--help").stdout
        assert out.startswith(
            "Usage: python -m chitragupta.draft gate [OPTIONS] FILE...\n\n  Fail if"
        )
        assert out.endswith("\nOptions:\n  -h, --help  Show this message and exit.\n")

    def test_runs_with_bare_system_python3_no_bibtexparser(
        self, system_python, isolated_config, tmp_path
    ):
        con = ledger.connect()
        add_citable(con, "smith2024")
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("[@smith2024]\n")

        result = run_python(
            "-m",
            "chitragupta.draft",
            "gate",
            str(draft),
            python=system_python,
            env={"PATH": "/usr/bin:/bin", "CONTENT_DIR": str(isolated_config.CONTENT_DIR)},
        )
        assert "bibtexparser" not in (result.stderr or "").lower()
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout


class TestInputsAreConfinedToContent:
    def test_a_draft_outside_the_content_directory_is_refused(
        self, isolated_config, tmp_path, capsys
    ):
        loose = tmp_path / "loose.md"
        loose.write_text("A claim [@a_2024].\n")

        rc = citation_gate.run([str(loose)])

        out = capsys.readouterr().out
        assert rc == 1
        assert "outside the content directory" in out
        assert str(loose) in out

    def test_one_bad_path_does_not_stop_the_others_being_checked(
        self, isolated_config, tmp_path, capsys
    ):
        con = ledger.connect()
        add_citable(con, "a_2024")
        con.close()
        good = isolated_config.CONTENT_DIR / "drafts" / "good.md"
        good.parent.mkdir(parents=True)
        good.write_text("A claim [@a_2024].\n")
        loose = tmp_path / "loose.md"
        loose.write_text("A claim [@a_2024].\n")

        rc = citation_gate.run([str(loose), str(good)])

        out = capsys.readouterr().out
        assert rc == 1
        assert "outside the content directory" in out
        assert f"OK    {good}" in out

    def test_a_draft_anywhere_under_content_is_accepted(self, isolated_config, capsys):
        con = ledger.connect()
        add_citable(con, "a_2024")
        con.close()
        scratch = isolated_config.CONTENT_DIR / "scratch" / "notes.md"
        scratch.parent.mkdir(parents=True)
        scratch.write_text("A claim [@a_2024].\n")

        assert citation_gate.run([str(scratch)]) == 0
        assert "OK" in capsys.readouterr().out
