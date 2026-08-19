"""src/render_output/_assets.py: local files copied beside the rendered output.

Split from one test module to mirror `src/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `src/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

from src import render_output
from tests.conftest import ASCII_FIGURE, MARKED_MD, MARKED_INPUT, TIKZ_FIGURE, figure_pair


class TestLocalImageRefs:
    def test_extracts_local_image_paths(self):
        text = "![alt one](figure-one.png)\n\nSome text ![alt two](sub/figure-two.svg \"a title\").\n"
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

        assert (dest_dir / "figures" / "fig1.tex").read_text() == "\\begin{tikzpicture}\\end{tikzpicture}\n"


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
