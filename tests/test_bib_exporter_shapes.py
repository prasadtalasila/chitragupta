"""What real reference managers write into bibliography.bib, read the
way `bib_reader` must read it (#964, folding in #956 and #965).

Three things the exporters do that the reader got wrong:

- **Escaped delimiters in `file`.** Zotero and Better BibTeX escape the
  drive colon and every backslash of a Windows path
  (`C\\:\\\\Users\\\\me\\\\x.pdf`), and a `;` that is part of a file name
  (`a\\;b.pdf`). Splitting on bare `:`/`;` rebuilt `C\\:\\Users\\me\\x.pdf`,
  which exists nowhere, so every Windows entry was "no PDF" and sync
  exited 3; and `\\;` crashed bibtexparser's LaTeX decoder outright.
- **BibTeX inside a field value.** An abstract or `note` quoting an
  entry, wrapped so that `@article{` starts a line, was counted as an
  entry, giving a phantom drop that exits 3 and blocks `--remove-stale`.
- **A second bib parser.** The verbatim aid matched `@\\w+\\{key,` and
  `file = \\{...\\},` with its own regexes; `test_bib_reader_is_the_only_bib_parser`
  is the scan that keeps it from coming back.
"""

import re
import sys
from pathlib import Path

import pytest

from chitragupta import bib_escapes, bib_integrity, bib_reader, ledger, ledger_paths

ROOT = Path(__file__).resolve().parent.parent


class TestSplitUnescaped:
    @pytest.mark.parametrize(
        ("value", "sep", "expected"),
        [
            ("a:b:c", ":", ["a", "b", "c"]),
            (r"a\:b:c", ":", [r"a\:b", "c"]),
            # An escaped backslash does not escape what follows it.
            (r"a\\:b", ":", [r"a\\", "b"]),
            (r"x\;y.pdf:t;z", ";", [r"x\;y.pdf:t", "z"]),
            ("", ":", [""]),
            # A trailing lone backslash is kept rather than lost.
            ("a\\", ":", ["a\\"]),
        ],
    )
    def test_splits_only_on_an_unescaped_separator(self, value, sep, expected):
        assert bib_escapes.split_unescaped(value, sep) == expected

    @pytest.mark.parametrize(
        ("raw", "plain"),
        [
            (r"C\:\\Users\\me\\x.pdf", r"C:\Users\me\x.pdf"),
            (r"a\;b.pdf", "a;b.pdf"),
            ("/home/me/x.pdf", "/home/me/x.pdf"),
            # Only the three escapes the exporters write are undone.
            (r"\n\x", r"\n\x"),
        ],
    )
    def test_unescape_undoes_exactly_the_exporters_escapes(self, raw, plain):
        assert bib_escapes.unescape(raw) == plain


class TestAttachments:
    """`bib_escapes.attachments`: the `file` field as `(path, mime)`
    pairs, one per attachment, in the order the exporter wrote them."""

    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            pytest.param(
                r"Full Text PDF:C\:\\Users\\me\\Zotero\\storage\\AB12\\x.pdf:application/pdf",
                [(r"C:\Users\me\Zotero\storage\AB12\x.pdf", "application/pdf")],
                id="zotero-windows",
            ),
            pytest.param(
                "Full Text:/home/me/Zotero/storage/AB12/x.pdf:application/pdf",
                [("/home/me/Zotero/storage/AB12/x.pdf", "application/pdf")],
                id="zotero-posix",
            ),
            pytest.param(
                r"Smith - 2024.pdf:pdfs/21/Smith - 2024.pdf:application/pdf;"
                r"Snapshot:pdfs/21/snap.html:text/html",
                [
                    ("pdfs/21/Smith - 2024.pdf", "application/pdf"),
                    ("pdfs/21/snap.html", "text/html"),
                ],
                id="better-bibtex-two-attachments",
            ),
            pytest.param(":pdfs/j.pdf:PDF", [("pdfs/j.pdf", "PDF")], id="jabref-triple"),
            pytest.param(
                r":C\:/Users/me/j.pdf:PDF", [("C:/Users/me/j.pdf", "PDF")], id="jabref-windows"
            ),
            pytest.param(
                ":a.pdf:pdf;:b.pdf:pdf",
                [("a.pdf", "pdf"), ("b.pdf", "pdf")],
                id="mendeley-semicolon-list",
            ),
            pytest.param(
                r"A:pdfs/a\;b.pdf:application/pdf",
                [("pdfs/a;b.pdf", "application/pdf")],
                id="literal-semicolon-in-path",
            ),
            # An unescaped drive colon, as a hand edit writes it, still
            # rejoins: only the first and last parts are not the path.
            pytest.param(
                r"D:C:\x.pdf:application/pdf",
                [(r"C:\x.pdf", "application/pdf")],
                id="unescaped-drive-colon",
            ),
            pytest.param("just-a-filename.pdf", [None], id="not-three-parts"),
        ],
    )
    def test_real_exporter_shapes(self, field, expected):
        assert bib_escapes.attachments(field) == expected


class TestReadLibraryResolvesEscapedFields:
    def test_a_literal_semicolon_in_a_path_resolves(self, isolated_config):
        """The `\\;` that crashed bibtexparser's LaTeX decoder for the
        whole file now names the PDF it means."""
        bib_dir = isolated_config.BIB_FILE_PATH.parent
        (bib_dir / "a;b.pdf").write_bytes(b"%PDF-1.4")
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{semi_2024,\n  title = {T},\n  file = {A:a\\;b.pdf:application/pdf},\n}\n",
            encoding="utf-8",
        )
        (reference,) = bib_reader.read_library().references
        assert reference.pdf_resolution == bib_reader.PDF_RESOLVED
        assert Path(reference.pdf_path).name == "a;b.pdf"

    def test_a_file_field_without_latex_markup_is_kept_as_written(self, isolated_config):
        """Every Zotero and Better BibTeX export: the exporters' own
        escapes reach `bib_escapes` untouched, and the other fields are
        still decoded as before."""
        isolated_config.BIB_FILE_PATH.write_text(
            '@article{k_2024,\n  title = {M{\\"o}bius},\n'
            "  file = {A:C\\:\\\\x\\;y.pdf:application/pdf},\n}\n",
            encoding="utf-8",
        )
        (reference,) = bib_reader.read_library().references
        assert reference.title == "Möbius"
        assert reference.fields["file"] == "A:C\\:\\\\x\\;y.pdf:application/pdf"

    def test_a_mendeley_latex_escaped_path_is_still_decoded(self, isolated_config):
        """Mendeley writes the field as LaTeX: an underscore is `{\\_}`
        and an umlaut `{\\"u}`. Decoding it is what made such a path
        resolve before #964, so a field holding LaTeX markup is still
        decoded."""
        bib_dir = isolated_config.BIB_FILE_PATH.parent
        (bib_dir / "Smith_Müller.pdf").write_bytes(b"%PDF-1.4")
        isolated_config.BIB_FILE_PATH.write_text(
            '@article{m_2024,\n  title = {T},\n  file = {:Smith{\\_}M{\\"u}ller.pdf:pdf},\n}\n',
            encoding="utf-8",
        )
        (reference,) = bib_reader.read_library().references
        assert reference.pdf_resolution == bib_reader.PDF_RESOLVED
        assert Path(reference.pdf_path).name == "Smith_Müller.pdf"

    def test_latex_markup_the_decoder_cannot_read_is_kept_raw(self, isolated_config):
        """Markup and a `\\;` together: the decoder raises on the `\\;`,
        and that must cost the field its decoding, not the read its life."""
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{both_2024,\n  title = {T},\n  file = {:a{\\_}b\\;c.pdf:pdf},\n}\n",
            encoding="utf-8",
        )
        (reference,) = bib_reader.read_library().references
        assert reference.fields["file"] == ":a{\\_}b\\;c.pdf:pdf"

    @pytest.mark.skipif(
        sys.platform != "win32", reason="a drive-letter path is absolute only on Windows"
    )
    def test_an_escaped_windows_path_resolves_on_windows(self, isolated_config):
        bib_dir = isolated_config.BIB_FILE_PATH.parent
        pdf = bib_dir / "x.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        escaped = str(pdf).replace("\\", "\\\\").replace(":", "\\:")
        isolated_config.BIB_FILE_PATH.write_text(
            f"@article{{w_2024,\n  title = {{T}},\n  file = {{F:{escaped}:application/pdf}},\n}}\n",
            encoding="utf-8",
        )
        (reference,) = bib_reader.read_library().references
        assert reference.pdf_resolution == bib_reader.PDF_RESOLVED


ENTRY = "@article{{{key},\n  title = {{T}},\n  year = {{2024}},\n{extra}}}\n"
# Field text a reference manager really exports and wraps: BibTeX quoted
# inside an abstract or a note, with the `@` landing at a line start.
QUOTED = [
    "  note = {cite as\n@article{inner_2001, title={x}}},\n",
    "  abstract = {We write\n@misc(other_2002, title = {y})\nin our tool.},\n",
    "  annote = {\n@inproceedings{deep_2003,\n  title = {{Nested {braces}}},\n}\n},\n",
    "",
]


class TestEntriesInsideFieldValues:
    @pytest.mark.parametrize("extra", QUOTED, ids=["note", "abstract-paren", "annote-deep", "none"])
    def test_a_quoted_entry_is_not_counted(self, extra):
        text = ENTRY.format(key="real_2024", extra=extra)
        assert bib_integrity.count_raw_entries(text) == 1

    def test_the_count_matches_every_composition(self):
        """Every ordering of every quoted fragment across a run of real
        entries counts exactly the entries composed: the deterministic
        stand-in for a property test, since this project carries no
        hypothesis dependency."""
        for n in range(1, 5):
            for offset in range(len(QUOTED)):
                text = "\n".join(
                    ENTRY.format(key=f"k{i}_2024", extra=QUOTED[(i + offset) % len(QUOTED)])
                    for i in range(n)
                )
                assert bib_integrity.count_raw_entries(text) == n, (n, offset)

    def test_no_phantom_drop_reaches_the_library(self, isolated_config):
        isolated_config.BIB_FILE_PATH.write_text(
            ENTRY.format(key="real_2024", extra=QUOTED[0]), encoding="utf-8"
        )
        library = bib_reader.read_library()
        assert library.dropped_entries == 0
        assert library.unread == {}

    def test_an_entry_after_one_unbalanced_entry_is_still_counted(self):
        """Why the bound is depth one, not zero: after an entry missing
        its closing brace the depth never returns to zero, and a depth-0
        rule would stop counting every entry after it -- hiding the drop
        this count exists to show (`bib_integrity.block_has_fields`)."""
        text = (
            "@article{broken_2024,\n  title = {Unclosed,\n  year = {2024},\n}\n\n"
            + ENTRY.format(key="after_2024", extra="")
        )
        assert bib_integrity.count_raw_entries(text) == 2


class TestVerbatimReadsTheLedgersPdf:
    """#956: `verbatim locate`/`overlap` find a paper's PDF through the
    ledger row `sync` wrote with `bib_reader`, never by re-parsing the
    bib file -- so whatever bib_reader handles, they handle."""

    def test_a_shape_the_old_regex_missed_is_found(self, isolated_config, ledger_con):
        from chitragupta.review.verbatim_check import _corpus

        bib_dir = ledger_paths.pdf_root()
        pdf = bib_dir / "pdfs" / "x.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF-1.4")
        # `@article{ key ,` and an unbraced last `file` field: the two
        # shapes `bib_entry`'s regexes did not match.
        isolated_config.BIB_FILE_PATH.write_text(
            '@article{ spaced_2024 ,\n  title = {T},\n  file = "A:pdfs/x.pdf:application/pdf"\n}\n',
            encoding="utf-8",
        )
        ledger.upsert_reference(ledger_con, bib_reader.read_library().references[0])
        ledger_con.commit()
        assert _corpus.pdf_path("spaced_2024") == pdf.resolve()

    def test_a_missing_ledger_is_no_pdf_not_a_crash(self, isolated_config):
        from chitragupta.review.verbatim_check import _corpus

        assert _corpus.pdf_path("anything_2024") is None


def test_bib_reader_is_the_only_bib_parser():
    """The class test for #956: no module outside the bib reader's own
    compiles a pattern for an entry header or a `file` field."""
    allowed = {"bib_reader.py", "bib_integrity.py", "bib_escapes.py"}
    entry_or_file = re.compile(
        r"""re\.(?:compile|search|match|findall|finditer)\(\s*r?["']"""
        r"""[^"']*(?:@\\w\+|file\s*=|file = )"""
    )
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "chitragupta").rglob("*.py")
        if path.name not in allowed and entry_or_file.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
