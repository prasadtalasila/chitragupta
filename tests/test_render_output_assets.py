"""chitragupta/render_output/_assets.py: local files copied beside the rendered output.

Split from one test module to mirror `chitragupta/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `chitragupta/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

from chitragupta import render_output
from tests.conftest import ASCII_FIGURE, MARKED_MD, TIKZ_FIGURE, figure_pair


class TestLocalImageRefs:
    def test_extracts_local_image_paths(self):
        text = '![alt one](figure-one.png)\n\nSome text ![alt two](sub/figure-two.svg "a title").\n'
        assert render_output._local_image_refs(text) == ["figure-one.png", "sub/figure-two.svg"]

    def test_skips_remote_urls_and_data_uris(self):
        text = (
            "![remote](https://example.com/figure.png)\n"
            "![inline](data:image/png;base64,AAAA)\n"
            "![local](figure.png)\n"
        )
        assert render_output._local_image_refs(text) == ["figure.png"]

    def test_no_images_returns_empty_list(self):
        assert render_output._local_image_refs("Just text, no images.\n") == []

    def test_a_bracketed_target_with_a_space_is_matched(self):
        # m-58: `[^)\s]+` never matched a path with a literal space at
        # all -- CommonMark's answer to that is wrapping the destination
        # in angle brackets, which this must also recognise.
        text = "![alt](<my figure.png>)\n"
        assert render_output._local_image_refs(text) == ["my figure.png"]

    def test_a_percent_encoded_space_is_unquoted(self):
        # m-58: pandoc/CommonMark's answer for an *unwrapped* destination
        # with a space is percent-encoding it -- the regex already
        # matches "my%20figure.png" as one token (no whitespace in it),
        # but it must be decoded before it's treated as a filesystem path
        # or it never resolves to the real file.
        text = "![alt](my%20figure.png)\n"
        assert render_output._local_image_refs(text) == ["my figure.png"]

    def test_a_bracketed_target_with_a_title_is_still_matched(self):
        text = '![alt](<my figure.png> "A title").\n'
        assert render_output._local_image_refs(text) == ["my figure.png"]


class TestCopyLocalImages:
    def test_copies_an_existing_local_image(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        (src_dir / "figure.png").write_bytes(b"fake png bytes")
        draft = src_dir / "draft.md"
        draft.write_text("![alt](figure.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert (dest_dir / "figure.png").read_bytes() == b"fake png bytes"

    def test_skips_a_reference_that_does_not_resolve_to_a_real_file(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        draft = src_dir / "draft.md"
        draft.write_text("![alt](does-not-exist.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)  # must not raise

        assert list(dest_dir.iterdir()) == []

    def test_skips_absolute_and_parent_escaping_paths(self, tmp_path):
        secret = tmp_path / "secret.png"
        secret.write_bytes(b"marker")
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        draft = src_dir / "draft.md"
        draft.write_text(f"![abs]({secret})\n\n![traversal](../secret.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert list(dest_dir.iterdir()) == []

    def test_copies_a_bracketed_target_with_a_space_in_its_name(self, tmp_path):
        # m-58: a genuinely realistic filename -- a screenshot or export
        # saved with its default, space-containing name -- was silently
        # never copied, so a `tex` output referencing it failed to
        # compile standalone.
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        (src_dir / "my figure.png").write_bytes(b"fake png bytes")
        draft = src_dir / "draft.md"
        draft.write_text("![alt](<my figure.png>)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert (dest_dir / "my figure.png").read_bytes() == b"fake png bytes"

    def test_copies_a_percent_encoded_target(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        (src_dir / "my figure.png").write_bytes(b"fake png bytes")
        draft = src_dir / "draft.md"
        draft.write_text("![alt](my%20figure.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert (dest_dir / "my figure.png").read_bytes() == b"fake png bytes"

    def test_creates_nested_destination_directories(self, tmp_path):
        src_dir = tmp_path / "drafts"
        (src_dir / "figures").mkdir(parents=True)
        (src_dir / "figures" / "figure.png").write_bytes(b"fake png bytes")
        draft = src_dir / "draft.md"
        draft.write_text("![alt](figures/figure.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert (dest_dir / "figures" / "figure.png").read_bytes() == b"fake png bytes"


class TestCopyLocalTexIncludes:
    def test_copies_an_existing_local_include(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        (src_dir / "fig1.tex").write_text("\\begin{tikzpicture}\\end{tikzpicture}\n")
        draft = src_dir / "draft.md"
        draft.write_text("\\input{fig1.tex}\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_tex_includes(draft, dest_dir)

        assert (dest_dir / "fig1.tex").read_text() == "\\begin{tikzpicture}\\end{tikzpicture}\n"

    def test_skips_a_reference_that_does_not_resolve_to_a_real_file(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        draft = src_dir / "draft.md"
        draft.write_text("\\input{does-not-exist.tex}\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_tex_includes(draft, dest_dir)  # must not raise

        assert list(dest_dir.iterdir()) == []

    def test_skips_absolute_and_parent_escaping_paths(self, tmp_path):
        secret = tmp_path / "secret.tex"
        secret.write_text("marker")
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        draft = src_dir / "draft.md"
        draft.write_text(f"\\input{{{secret}}}\n\n\\input{{../secret.tex}}\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_tex_includes(draft, dest_dir)

        assert list(dest_dir.iterdir()) == []

    def test_creates_nested_destination_directories(self, tmp_path):
        src_dir = tmp_path / "drafts"
        (src_dir / "figures").mkdir(parents=True)
        (src_dir / "figures" / "fig1.tex").write_text("\\begin{tikzpicture}\\end{tikzpicture}\n")
        draft = src_dir / "draft.md"
        draft.write_text("\\input{figures/fig1.tex}\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_tex_includes(draft, dest_dir)

        assert (
            dest_dir / "figures" / "fig1.tex"
        ).read_text() == "\\begin{tikzpicture}\\end{tikzpicture}\n"


class TestCopyLocalTexIncludesFollowsMarkers:
    def test_a_markdown_marker_gets_its_figure_copied(self, tmp_path):
        # Without this the standalone .tex in content/rendered/ emits an
        # \input for a file that was never copied beside it, and fails to
        # compile on its own -- the exact regression #226's own copy test
        # exists to catch, reintroduced through the marker path.
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        draft.write_text(MARKED_MD)
        dest = tmp_path / "rendered"
        dest.mkdir()

        render_output._copy_local_tex_includes(draft, dest)

        assert (dest / "figures" / "fig1.tex").read_text() == TIKZ_FIGURE


class TestRenderingIntoTheDraftsOwnDirectory:
    """`--output-dir <the draft's own directory>` is what a book assembly
    does: the fragments have to sit beside the `book.tex` that \\input-s
    them, which is the same directory the chapters live in. The asset copy
    then has the same file as source and destination, and `shutil.copy2`
    raises `SameFileError` -- so a 15-chapter book with figures failed
    every fragment conversion at once (2026-08-19)."""

    def test_a_figure_beside_the_draft_is_not_copied_onto_itself(self, tmp_path):
        draft_dir = tmp_path / "book"
        (draft_dir / "figures").mkdir(parents=True)
        (draft_dir / "figures" / "fig1.tex").write_text(TIKZ_FIGURE, encoding="utf-8")
        (draft_dir / "figures" / "fig1.txt").write_text(ASCII_FIGURE, encoding="utf-8")
        draft = draft_dir / "ch01.md"
        draft.write_text(MARKED_MD, encoding="utf-8")

        render_output._copy_local_assets(draft, draft_dir)

        assert (draft_dir / "figures" / "fig1.tex").read_text(encoding="utf-8") == TIKZ_FIGURE

    def test_an_image_beside_the_draft_is_not_copied_onto_itself(self, tmp_path):
        draft_dir = tmp_path / "book"
        (draft_dir / "img").mkdir(parents=True)
        (draft_dir / "img" / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        draft = draft_dir / "ch01.md"
        draft.write_text("![cover](img/cover.png)\n", encoding="utf-8")

        render_output._copy_local_assets(draft, draft_dir)

        assert (draft_dir / "img" / "cover.png").read_bytes() == b"\x89PNG\r\n\x1a\n"


class TestTheBookBibliographyBesideAFragment:
    """`bibtex` resolves `\\bibliography{...}` against the directory it runs
    in, which for a book is `content/rendered/<book>/`. A fragment's
    citations are deferred, so the `.bib` has to be there or every citation
    in the assembled book renders `[?]` with pdflatex still exiting 0.
    """

    def test_the_corpus_bib_lands_in_the_output_directory(self, isolated_config, tmp_path):
        isolated_config.BIB_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024, title={A}}\n", encoding="utf-8"
        )
        dest = tmp_path / "rendered" / "twins"

        render_output._assets._copy_book_bibliography(dest)

        written = dest / isolated_config.BIB_FILE_PATH.name
        assert written.is_file()
        assert "@article{smith_2024," in written.read_text(encoding="utf-8")

    def test_double_hyphen_keys_are_aliased_to_match_the_fragments(self, isolated_config, tmp_path):
        """The fragment carries `\\citep{..._state-x2d-x2d-art_...}`, so the
        copy has to agree or bibtex answers nothing -- the silent half of
        the `--` problem, since pdflatex reports it only as a warning."""
        isolated_config.BIB_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{tygesen_state---art_2019, title={A}}\n", encoding="utf-8"
        )
        dest = tmp_path / "rendered" / "twins"

        render_output._assets._copy_book_bibliography(dest)

        written = (dest / isolated_config.BIB_FILE_PATH.name).read_text(encoding="utf-8")
        assert "@article{tygesen_state-x2d-x2d-art_2019," in written

    def test_the_users_own_bib_is_never_modified(self, isolated_config, tmp_path):
        """`papers/bibliography.bib` is the human's export and the source of
        truth for every citekey in the project."""
        isolated_config.BIB_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        original = "@article{tygesen_state---art_2019, title={A}}\n"
        isolated_config.BIB_FILE_PATH.write_text(original, encoding="utf-8")

        render_output._assets._copy_book_bibliography(tmp_path / "out")

        assert isolated_config.BIB_FILE_PATH.read_text(encoding="utf-8") == original

    def test_a_project_with_no_bibliography_yet_is_not_an_error(self, isolated_config, tmp_path):
        """The render that produced the fragment would have failed on the
        missing file long before this, and a book with no citations has
        nothing for bibtex to answer either way."""
        dest = tmp_path / "out"

        render_output._assets._copy_book_bibliography(dest)

        assert not (dest / isolated_config.BIB_FILE_PATH.name).exists()

    def test_copy_local_assets_brings_the_bib_only_for_a_fragment(self, isolated_config, tmp_path):
        """A standalone render resolves its own citations, so a `.bib`
        beside it would be an unused file in the publish output. A fragment
        defers, so it is the one thing between its `\\citep{...}` and a
        resolved reference."""
        isolated_config.BIB_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.BIB_FILE_PATH.write_text("@article{a_2024, title={A}}\n", encoding="utf-8")
        draft = tmp_path / "unit.md"
        draft.write_text("Body [@a_2024].\n", encoding="utf-8")
        name = isolated_config.BIB_FILE_PATH.name

        standalone = tmp_path / "standalone"
        standalone.mkdir()
        render_output._copy_local_assets(draft, standalone)
        assert not (standalone / name).exists()

        fragment = tmp_path / "fragment"
        fragment.mkdir()
        render_output._copy_local_assets(draft, fragment, True)
        assert (fragment / name).is_file()
