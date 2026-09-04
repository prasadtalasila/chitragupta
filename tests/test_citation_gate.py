"""chitragupta/citation_gate.py: the hard invariant (AGENTS.md) -- a citekey may
only be used if it's actually in the ledger. This is the single most
important module in the repo to test thoroughly."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from chitragupta import citation_gate, ledger

from tests.conftest import content_draft, make_reference


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
            # These were silently missed by an earlier, enumerated version of
            # the regex: ordered alternation tried "cite" first, matched as a
            # prefix of e.g. "citealp", then failed to find the "{" that must
            # immediately follow and never backed off to try the longer
            # alternatives -- a false negative on the invariant this gate
            # exists to enforce (a fabricated key in one of these read as "0
            # citations" instead of "unresolved"). Regression coverage for
            # that fix, not just the already-working subset above.
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
        """biblatex's sentence-start capitalized commands (\\Citep, \\Textcite,
        ...) -- same false-negative class as test_all_recognized_commands."""
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
        # \cites{a}{b} takes one {key} group per citation. Capturing only
        # the first group let a fabricated second key read as "0 citations"
        # instead of unresolved -- the false-negative class this regex
        # exists to close.
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
        # A note between two multicite groups may itself contain braces
        # (\emph{cf}); reading them as a {key} group would invent a
        # citekey and block a sound draft.
        assert citation_gate.extract_citekeys_from_line("\\cites{a2024}[\\emph{cf}]{b2024}") == [
            "a2024",
            "b2024",
        ]

    def test_a_prose_brace_group_after_whitespace_is_not_a_second_key(self):
        # Trailing groups are consumed only when directly adjacent --
        # biblatex multicites are written adjacent, while `\citep{a} {x}`
        # is a citation followed by an ordinary prose brace group, and
        # swallowing that would invent a citekey and block a sound draft.
        assert citation_gate.extract_citekeys_from_line("\\citep{a2024} {emphasised}") == ["a2024"]

    def test_unrelated_command_not_matched(self):
        assert citation_gate.extract_citekeys_from_line("\\section{Introduction}") == []

    def test_plain_text_no_match(self):
        assert citation_gate.extract_citekeys_from_line("Just some prose.") == []

    @pytest.mark.parametrize(
        "text",
        [
            # TeX itself skips whitespace between a control word and its
            # arguments -- \citep {key} is valid and equivalent to
            # \citep{key}. Without \s* in the regex, any of these silently
            # missed a real (or fabricated) citekey -- same false-negative
            # class as test_all_recognized_commands above. Cases where the
            # whitespace itself contains a newline (\citep\n{key}) are covered
            # separately in TestExtractCitekeysWholeDocument, since a per-line
            # caller like citation_coverage.py never hands this wrapper a
            # string spanning two real lines in the first place.
            "\\citep {smith2024}",
            "\\citep [see]{smith2024}",
            "\\citep *{smith2024}",
        ],
    )
    def test_whitespace_between_command_and_arguments(self, text):
        assert citation_gate.extract_citekeys_from_line(text) == ["smith2024"]


class TestLatexCiteRegexBacktracking:
    """The gate must survive attacker-shaped input in linear time (#635).

    The pre-fix _WS (`[ \\t]*\\n?[ \\t]*`) was internally ambiguous -- a
    space run could split between its two `[ \\t]*` atoms every possible
    way -- and _LATEX_CITE_RE chained it around the star and each option
    group, so a `\\cite` followed by whitespace-separated `[...]` groups
    and *no* `{...}` made the engine explore ~2^N partitions before
    failing. ~160 bytes hung the gate past the hook's 30 s timeout, and a
    timed-out PostToolUse hook does not block -- the one way a fabricated
    citekey could land ungated."""

    def test_bracket_run_without_a_key_group_completes_fast(self):
        # 64 units took effectively forever pre-fix (22 already took ~5 s);
        # linear matching clears it in well under a second even on a slow
        # host, so the bound is a regression tripwire, not a benchmark.
        text = "\\cite" + " [a]" * 64 + " x"
        start = time.perf_counter()
        assert citation_gate.extract_citekeys(text) == []
        assert time.perf_counter() - start < 2.0

    def test_paragraph_break_between_command_and_key_is_not_a_citation(self):
        # The module comment promises at most a single newline between a
        # command and its argument (a blank line is a TeX paragraph break,
        # which ends the command). The ambiguous _WS chain accidentally
        # accepted up to three; the unambiguous form makes the documented
        # boundary real, so pin it.
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
        # Pandoc's own grammar allows a key to begin with a digit or an
        # underscore; requiring a letter made such a citation invisible to
        # the gate (read as 0 citations) while pandoc still rendered it.
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
        # LaTeX's \makeatletter ... \@ifundefined{...}{}{} ... \makeatother
        # idiom (pandoc's own rendered .tex templates use this) would
        # otherwise misread \@ifundefined as a citation -- found via a
        # retro-sweep of pandoc-rendered output, and load-bearing now that
        # thesis-chapter-writer's .tex drafts are hook-gated (see
        # .claude/hooks/citation_gate_hook.py).
        assert citation_gate.extract_citekeys_from_line(r"\@ifundefined{foo}{}{}") == []
        line = r"\makeatletter\@ifundefined{xetex}{}{}\makeatother"
        assert citation_gate.extract_citekeys_from_line(line) == []


class TestExtractCitekeysWholeDocument:
    """extract_citekeys(text) -- the whole-document scan that
    extract_citekeys_from_line() (tested above) delegates to for a single
    line. Covers what a per-line scan structurally cannot: a citation
    argument wrapped across multiple lines."""

    def test_wrapped_citep_is_caught(self):
        text = "See \\citep{real_key,\n       fabricated_key} for details.\n"
        keys = [key for _, key in citation_gate.extract_citekeys(text)]
        assert sorted(keys) == ["fabricated_key", "real_key"]

    def test_document_where_every_citation_is_wrapped_and_fabricated(self):
        # Regression for the exact bug found in review: a per-line scan
        # matches on neither line of a wrapped \citep{...}, so a document
        # citing nothing but fabricated, wrapped keys used to report "0
        # citations, all verified" (exit 0).
        text = "\\citealp{totally_made_up_key,\n          another_fake} shown here.\n"
        keys = [key for _, key in citation_gate.extract_citekeys(text)]
        assert sorted(keys) == ["another_fake", "totally_made_up_key"]

    def test_line_number_points_at_match_start(self):
        text = "line one\nline two \\citep{smith2024}\nline three\n"
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_whitespace_including_newline_between_command_and_brace(self):
        # TeX skips whitespace -- including a newline -- between a control
        # word and its argument, so \citep on one line and {key} on the
        # next is valid source and equivalent to \citep{key}. Only the
        # whole-document scan can catch this: citation_coverage.py's
        # per-line caller (extract_citekeys_from_line) would see "\citep"
        # and "{key}" as two separate, independently-unmatchable strings,
        # since splitlines() has already severed them before either one
        # reaches the wrapper.
        text = "See \\citep\n{smith2024} for details.\n"
        assert citation_gate.extract_citekeys(text) == [(1, "smith2024")]

    def test_results_are_in_document_order_not_regex_pass_order(self):
        # LaTeX and Pandoc citations are matched in two separate passes;
        # results must still come out in the order they actually appear in
        # the document (not "every LaTeX match, then every Pandoc match"),
        # or a FAIL report lists an out-of-order citekey, making it harder
        # to locate by reading top-to-bottom.
        text = "[@later_pandoc]\nprose\n\\citep{earlier_latex}\nmore\n[@even_later]\n"
        assert citation_gate.extract_citekeys(text) == [
            (1, "later_pandoc"),
            (3, "earlier_latex"),
            (5, "even_later"),
        ]


class TestCodeAndVerbatimExclusion:
    """The teaching genres' whole job is worked code examples, and code
    routinely contains @-tokens (Python's @dataclass, @property) or
    cite-shaped strings that aren't citations. With the PostToolUse hook
    (.claude/hooks/citation_gate_hook.py) treating a FAIL as blocking, a
    false positive here would push the agent to delete valid teaching
    code instead of a real fabricated citation."""

    def test_python_decorator_in_fenced_code_is_not_a_citation(self):
        text = "```python\n@dataclass\nclass Foo:\n    pass\n```\n"
        assert citation_gate.extract_citekeys(text) == []

    def test_inline_code_span_is_not_a_citation(self):
        assert citation_gate.extract_citekeys("use the `@override` annotation") == []
        assert citation_gate.extract_citekeys("run `npm install @scoped/pkg`") == []

    def test_whitespace_tolerance_does_not_bridge_a_blanked_verbatim_block(self):
        # _blank_code blanks a verbatim block's contents to spaces but keeps
        # its newlines, and a verbatim block is always >=2 lines. If the
        # cite regex's whitespace tolerance (added for \citep\n{key}, see
        # TestExtractCitekeysWholeDocument) were unbounded (\s*) instead of
        # capped at one newline, it could bridge straight across the
        # blanked-out block and read an unrelated \nocite ... {group} on
        # either side of it as one fake citation -- a false positive that
        # would push the blocking PostToolUse hook to reject a draft on
        # invented grounds.
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
        # ~~~ is the other CommonMark fence dialect; leaving it unblanked
        # made an in-code @dataclass read as a citation, a FAIL that
        # pushes the blocking hook to mangle valid teaching code.
        text = "~~~python\n@dataclass\nclass Foo:\n    pass\n~~~\n"
        assert citation_gate.extract_citekeys(text) == []

    def test_stray_fence_marker_in_prose_does_not_shift_pairing(self):
        # A fence opener is a line-start construct. Pairing every ```
        # token in document order let one prose mention of ``` shift the
        # pairing: the prose after it (citations included) was blanked and
        # the next real code block's interior was exposed.
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
        # CommonMark: a backtick fence's info string may not contain a
        # backtick, so a line-start ``` code ``` span is a paragraph, not
        # an opener. Treating it as one would blank the whole rest of the
        # document -- every later citation reading as 0 citations.
        text = "``` bash -c ``` runs a command.\nGrounded claim [@smith2024].\n"
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_tab_indented_marker_is_not_a_fence(self):
        # A tab indents by four columns in CommonMark, so a tab-indented
        # ``` line is indented code, not a fence opener.
        text = "\t```\nGrounded claim [@smith2024].\n"
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_indented_marker_is_not_a_fence(self):
        # Four or more spaces of indent is indented code, not a fence
        # opener (CommonMark); treating it as one would blank the prose
        # that follows.
        text = "    ```\nGrounded claim [@smith2024].\n"
        assert citation_gate.extract_citekeys(text) == [(2, "smith2024")]

    def test_unclosed_fence_blanks_to_end_of_document(self):
        # CommonMark runs an unclosed fence to the end of the document; an
        # @-token after one is still code, not a citation.
        text = "```python\n@dataclass\nclass Foo: pass\n"
        assert citation_gate.extract_citekeys(text) == []


class TestLatexBlanking:
    """In LaTeX a backtick is an open-quote character, not code markup.

    Applying Markdown's inline-code and fence blanking to `.tex` input
    let the span between two quoted phrases on one line read as "inline
    code" -- blanking a real `\\citep{...}` between them, so a fabricated
    citekey passed the gate as 0 citations. LaTeX mode must blank only
    LaTeX's own verbatim environments."""

    def test_double_backtick_quotes_do_not_eat_a_citation(self):
        text = "The ``digital twin'' approach \\citep{fabricated2024} extends the ``model'' view.\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "fabricated2024")]

    def test_single_backtick_quotes_do_not_eat_a_citation(self):
        text = "The `digital twin' approach \\citep{smith2024} is `neat'.\n"
        assert citation_gate.extract_citekeys(text, latex=True) == [(1, "smith2024")]

    def test_fence_blanking_is_off_in_latex_mode(self):
        # Three backticks in LaTeX are quotes (`` then `), not a fence;
        # fence blanking across two such runs would eat the prose between.
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


class TestCheckDocument:
    def test_reports_unknown_with_correct_line_numbers(self, tmp_path):
        path = tmp_path / "draft.md"
        path.write_text("Line one [@known2024].\nLine two [@unknown2024].\n")
        result = citation_gate.check_document(path, known_citekeys={"known2024"})

        assert result.total_citations == 2
        assert result.unknown == [(2, "unknown2024")]
        assert result.ok is False

    def test_all_known_is_ok(self, tmp_path):
        path = tmp_path / "draft.md"
        path.write_text("[@a2024] and [@b2024]\n")
        result = citation_gate.check_document(path, known_citekeys={"a2024", "b2024"})
        assert result.ok is True
        assert result.total_citations == 2

    def test_no_citations_is_ok_with_zero_total(self, tmp_path):
        path = tmp_path / "draft.md"
        path.write_text("Just prose, no citations at all.\n")
        result = citation_gate.check_document(path, known_citekeys=set())
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
        ledger.upsert_reference(con, make_reference(citekey="smith2024"))
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
        ledger.upsert_reference(con, make_reference(citekey="smith2024"))
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


class TestDeadLauncherWarning:
    """The gate is the one caller in the chain that can report a hook
    launcher which cannot start.

    Neither hook can: the gate hook cannot report its own failure to spawn,
    and `session_start_hook.py` -- written to report it -- is launched by
    the same interpreter name, so it is missing on exactly the host where
    the gate is (#197). This command runs on an interpreter that has
    demonstrably started, and every genre skill runs it.
    """

    @staticmethod
    def draft(cfg) -> str:
        """A draft that passes, against a ledger with something in it -- so
        the only thing that can reach stderr is the launcher warning."""
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith2024"))
        con.close()
        path = content_draft(cfg, "draft.md")
        path.write_text("A claim [@smith2024].\n", encoding="utf-8")
        return str(path)

    def test_a_dead_launcher_is_warned_about_without_changing_the_verdict(
        self, isolated_config, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            citation_gate.hook_launchers,
            "faults",
            lambda: ["`python` is not on PATH, so a hook cannot start."],
        )
        rc = citation_gate.run([self.draft(isolated_config)])
        captured = capsys.readouterr()

        assert rc == 0
        assert "OK" in captured.out
        assert "`python` is not on PATH" in captured.err
        assert "docs/HOOKS.md" in captured.err
        assert "WARNING" not in captured.out, "the verdict stream stays the verdict"

    def test_a_sound_launcher_says_nothing(self, isolated_config, monkeypatch, capsys):
        monkeypatch.setattr(citation_gate.hook_launchers, "faults", list)
        assert citation_gate.run([self.draft(isolated_config)]) == 0
        assert capsys.readouterr().err == ""


class TestCliEntrypoint:
    def test_no_args_prints_usage_and_exits_2(self, isolated_config):
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta.draft", "gate"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "usage:" in result.stderr

    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help_prints_usage_and_exits_0(self, isolated_config, flag):
        """This took a filename before, so `--help` died with a
        FileNotFoundError traceback -- on the one tool every genre skill
        and the write hook invoke, i.e. the first one anyone tries it on.
        Help goes to stdout and exits 0; the no-args *error* keeps
        stderr and exit 2."""
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta.draft", "gate", flag],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout
        assert "Traceback" not in result.stderr

    def test_runs_with_bare_system_python3_no_bibtexparser(
        self, system_python, isolated_config, tmp_path
    ):
        """AGENTS.md's hard requirement: citation_gate must run with the
        bare system interpreter, no bibtexparser/venv needed."""
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith2024"))
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("[@smith2024]\n")

        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [system_python, "-m", "chitragupta.draft", "gate", str(draft)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "CONTENT_DIR": str(isolated_config.CONTENT_DIR)},
        )
        assert "bibtexparser" not in (result.stderr or "").lower()
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout


class TestInputsAreConfinedToContent:
    """Every tier-1 tool reads only under content/, so that one directory
    is the whole record of the work -- see chitragupta/config.py's
    require_inside_content."""

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
        # run() reports on every path it is given; a refusal is one more
        # per-document result, not an abort.
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="a_2024"))
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
        # content/drafts/ is where the genre skills save one, but the rule
        # is "under content/" -- a scratch note or a content/review/ report
        # is checked the same way.
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="a_2024"))
        con.close()
        scratch = isolated_config.CONTENT_DIR / "scratch" / "notes.md"
        scratch.parent.mkdir(parents=True)
        scratch.write_text("A claim [@a_2024].\n")

        assert citation_gate.run([str(scratch)]) == 0
        assert "OK" in capsys.readouterr().out
