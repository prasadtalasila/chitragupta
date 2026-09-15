"""chitragupta/render_output/_citeproc.py: preparing a draft and the bib for --citeproc.

Split from one test module to mirror `chitragupta/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `chitragupta/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

import pytest
from chitragupta import render_output


class TestSwapManualRefsForCiteproc:
    def test_keeps_the_heading_and_swaps_the_entries_for_the_anchor(self):
        text = "# Title\n\nA claim [@k].\n\n## References\n\n[1] A Paper, 2024. `k`\n"
        assert render_output._swap_manual_refs_for_citeproc(text) == (
            "# Title\n\nA claim [@k].\n\n## References\n\n::: {#refs}\n:::\n"
        )

    def test_preserves_a_draft_s_own_numbered_heading(self):
        # textbook-chapter-writer passes --heading "6. References" to match
        # its other headings; citeproc emits no heading of its own, so
        # dropping this one left the rendered bibliography untitled.
        text = "A claim [@k].\n\n## 6. References\n\n[1] A Paper, 2024. `k`\n"
        assert "## 6. References" in render_output._swap_manual_refs_for_citeproc(text)

    def test_preserves_the_heading_level(self):
        text = "A claim [@k].\n\n#### References\n\n[1] A Paper, 2024. `k`\n"
        assert "#### References" in render_output._swap_manual_refs_for_citeproc(text)

    def test_handles_a_heading_on_the_final_line_without_a_newline(self):
        text = "A claim [@k].\n\n## References"
        out = render_output._swap_manual_refs_for_citeproc(text)
        assert out.endswith("## References\n\n::: {#refs}\n:::\n")

    def test_leaves_a_draft_without_one_alone(self):
        text = "# Title\n\nA claim [@k].\n"
        assert render_output._swap_manual_refs_for_citeproc(text) == text

    def test_leaves_a_latex_fragment_alone(self):
        # thesis-chapter-writer's .tex fragment has no Markdown heading and
        # defers to the user's own thesis-wide bibliography.
        text = "A claim \\citep{k}.\n\n\\section{References}\n"
        assert render_output._swap_manual_refs_for_citeproc(text) == text

    def test_content_after_references_survives_in_the_pandoc_copy(self):
        # M-8: this used to drop everything from the heading to end of
        # file -- an appendix or acknowledgments after References vanished
        # from tex/pdf/docx output while the md path (references.apply)
        # kept it, so two renders of one draft disagreed.
        text = (
            "A claim [@k].\n\n"
            "## References\n\n[1] A Paper, 2024. `k`\n\n"
            "## Acknowledgments\n\nThanks to everyone.\n"
        )
        out = render_output._swap_manual_refs_for_citeproc(text)
        assert "## Acknowledgments" in out
        assert "Thanks to everyone." in out
        assert out.index("::: {#refs}") < out.index("## Acknowledgments")


class TestAliasFor:
    def test_replaces_double_hyphen(self):
        assert (
            render_output._alias_for("zech_digital-twins-as--service_2024")
            == "zech_digital-twins-as-x2d-service_2024"
        )

    @pytest.mark.parametrize(
        "citekey",
        [
            "zech_digital-twins-as--service_2024",
            # This project's own corpus has a 3-hyphen key. A single
            # replace("--", "-x2d-") leaves "state-x2d--art" -- still
            # truncating, so the citation resolves to nothing and the source
            # silently disappears from the rendered bibliography.
            "tygesen_state---art_2019",
            "a----b",
        ],
    )
    def test_alias_never_leaves_a_double_hyphen_behind(self, citekey):
        assert "--" not in render_output._alias_for(citekey)

    def test_no_double_hyphen_unchanged_value(self):
        # _alias_for always transforms; callers only invoke it for keys
        # already known to contain "--" (see _safe_render_inputs).
        assert render_output._alias_for("plain_key_2024") == "plain_key_2024"


class TestSanitizeForLatex:
    """Control characters and math-alphanumeric Unicode break pdflatex,
    not pandoc -- both surfaced via a quoted passage straight out of
    content/parsed/<citekey>.txt (#389)."""

    def test_a_nul_byte_is_stripped(self):
        assert render_output._sanitize_for_latex("been outlined in ISO 23,247 \x00") == (
            "been outlined in ISO 23,247 "
        )

    def test_other_c0_controls_are_stripped_but_whitespace_is_kept(self):
        assert render_output._sanitize_for_latex("a\x01b\tc\nd\re") == "ab\tc\nd\re"

    def test_math_italic_is_folded_to_its_ascii_letter(self):
        # U+1D461 MATHEMATICAL ITALIC SMALL T -- pdflatex's default font
        # has no glyph for it ("Unicode character \U0001d461 not set up").
        assert render_output._sanitize_for_latex("the \U0001d461 statistic") == "the t statistic"

    def test_ordinary_unicode_is_left_alone(self):
        text = "an em—dash, café, and an arrow →"
        assert render_output._sanitize_for_latex(text) == text

    def test_idempotent_on_already_clean_text(self):
        text = "Nothing unusual here.\n"
        assert render_output._sanitize_for_latex(text) == text


class TestSafeRenderInputs:
    def test_no_bad_keys_returns_original_paths(self, tmp_path):
        md = tmp_path / "in.md"
        md.write_text("Citing [@smith_2024].\n")
        bib = tmp_path / "bibliography.bib"
        bib.write_text("@article{smith_2024,\n  title={T},\n}\n")

        safe_md, safe_bib = render_output._safe_render_inputs(md, bib, tmp_path / "tmp")
        assert safe_md == md
        assert safe_bib == bib

    def test_a_nul_byte_in_the_draft_is_sanitized_in_the_safe_copy(self, tmp_path):
        # The draft's own file on disk is never touched -- only the temp
        # copy handed to pandoc, same as the other two fixups here.
        md = tmp_path / "in.md"
        md.write_text("Quoting ISO 23,247 \x00 verbatim.\n")
        bib = tmp_path / "bibliography.bib"
        bib.write_text("")
        tmp_dir = tmp_path / "tmp"
        tmp_dir.mkdir()

        safe_md, _ = render_output._safe_render_inputs(md, bib, tmp_dir)
        assert safe_md != md
        assert "\x00" not in safe_md.read_text()
        assert "\x00" in md.read_text()

    def test_double_hyphen_key_gets_aliased_in_both_files(self, tmp_path):
        md = tmp_path / "in.md"
        md.write_text("Citing [@zech_digital-twins-as--service_2024] here.\n")
        bib = tmp_path / "bibliography.bib"
        bib.write_text(
            "@article{zech_digital-twins-as--service_2024,\n  title={T},\n}\n"
            "@article{zech_digital-twins-as--service_2024-1,\n  title={T2},\n}\n"
        )
        tmp_dir = tmp_path / "tmp"
        tmp_dir.mkdir()

        safe_md, safe_bib = render_output._safe_render_inputs(md, bib, tmp_dir)
        assert safe_md != md
        assert safe_bib != bib

        md_text = safe_md.read_text()
        assert "zech_digital-twins-as-x2d-service_2024" in md_text
        assert "--service" not in md_text

        bib_text = safe_bib.read_text()
        assert "@article{zech_digital-twins-as-x2d-service_2024," in bib_text
        # The "-1" duplicate entry must be untouched, not also aliased.
        assert "@article{zech_digital-twins-as--service_2024-1," in bib_text


class TestDeferringCitationsToTheConsumingDocument:
    """A `--fragment` render emits `\\citep{...}` and no reference list: the
    document that `\\input`s it resolves every citation once, so one source
    carries one number across the whole book.

    Citeproc assigns numbers in the pass that builds the list, so the
    alternative -- resolve per unit, collect the lists at the back -- gives
    chapter 1 and chapter 2 each their own `[2]` for different papers, in a
    book that compiles cleanly. These pin the two text-level halves of
    moving the resolution rather than the list.
    """

    def test_the_references_section_goes_entirely_heading_and_all(self):
        """The difference from `_swap_manual_refs_for_citeproc`, which keeps
        the heading for citeproc's untitled bibliography to sit under. Here
        there is no bibliography to title, so a kept heading would be an
        empty `References` chapter in the assembled book."""
        text = "Body [@smith_2024].\n\n## References\n\n[1] Smith. `smith_2024`\n"

        out = render_output._citeproc.drop_manual_refs(text)

        assert "## References" not in out
        assert "[1] Smith" not in out
        assert "Body [@smith_2024]." in out

    def test_a_section_after_references_survives(self):
        """M-8, the same rule the swap obeys: an appendix introduced by its
        own heading after References is not part of it, and dropping to the
        end of the file would delete it from the book silently."""
        text = "Body.\n\n## References\n\n[1] Smith. `smith_2024`\n\n## Appendix\n\nKeep me.\n"

        out = render_output._citeproc.drop_manual_refs(text)

        assert "## Appendix" in out and "Keep me." in out
        assert "[1] Smith" not in out

    def test_a_draft_with_no_references_section_is_unchanged(self):
        text = "Body [@smith_2024].\n\n## Method\n\nProse.\n"

        assert render_output._citeproc.drop_manual_refs(text) == text

    def test_every_double_hyphen_key_in_the_bib_is_aliased_not_just_one_drafts(self):
        """The book's `.bib` is read by one `bibtex` pass over every
        chapter, but each chapter is rendered separately. Aliasing only the
        keys the draft in hand cites would let the last unit rendered decide
        the file's contents, and every other unit's `\\citep{...-x2d-...}`
        would resolve to nothing."""
        bib = (
            "@article{tygesen_state---art_2019, title={A}}\n"
            "@book{lim_state--art_2020, title={B}}\n"
            "@misc{plain_2021, title={C}}\n"
        )

        out = render_output._citeproc.aliased_bib_text(bib)

        assert "@article{tygesen_state-x2d-x2d-art_2019," in out
        assert "@book{lim_state-x2d-art_2020," in out
        assert "@misc{plain_2021," in out, "a key with no -- is left exactly as it was"

    def test_aliasing_a_bib_with_no_bad_key_changes_nothing(self):
        bib = "@article{smith_2024, title={A}}\n"

        assert render_output._citeproc.aliased_bib_text(bib) == bib

    def test_substituted_drops_the_references_section_for_a_fragment_only(self, tmp_path):
        """The drop rides on the one function that answers "what does the
        writer actually see", so there is no second place rewriting the
        same text. A standalone render keeps the section for
        `_swap_manual_refs_for_citeproc` to fill from citeproc."""
        draft = tmp_path / "unit.md"
        text = "Body [@a_2024].\n\n## References\n\n[1] A. `a_2024`\n"
        draft.write_text(text, encoding="utf-8")

        assert "## References" in render_output._substituted(text, draft, "tex", {})
        assert "## References" not in render_output._substituted(text, draft, "tex", {}, True)
