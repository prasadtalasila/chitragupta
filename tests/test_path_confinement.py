"""Issue 821: a path handed to this pipeline as *data* -- read back out
of the ledger's `parsed_path`/`pdf_path`, or read out of a bib entry's
`file` field -- names a host file, and every consumer used to open
whichever one it named.

The threat is not hypothetical arithmetic: `content/ledger.sqlite` is a
plain, gitignored sqlite file under a shared `content/` tree, and a
`.bib` export is assembled by a reference manager and passed between
collaborators. Either one pointing at `~/.ssh/id_rsa` put that file's
bytes into the corpus as a paper's parsed text, where `search` ranked
it and a genre skill would quote it into a draft as evidence.

These tests are grouped by the layer that must refuse, not by module,
because the point of the fix is that no layer trusts the one above it.
"""

import os
from pathlib import Path

import pytest

from chitragupta import (
    bib_reader,
    config,
    ledger,
    ledger_upsert,
    overlap_index_ledger,
    passages,
    retrieval,
    retrieval_cache,
    tldr,
)
from chitragupta.discover import _overview
from chitragupta.enrich import corpus as enrich_corpus
from chitragupta.review.verbatim_check import _corpus as verbatim_corpus

SECRET = "brahmastra ssh private key material"


@pytest.fixture
def outside_file(tmp_path_factory):
    """A host file the corpus has no business reading.

    `tmp_path_factory`, not `tmp_path`: `isolated_config` puts both
    roots that matter -- `content/parsed/` and the bib file's own
    directory -- under the test's own `tmp_path`, so a "secret" written
    there would be inside the corpus and prove nothing."""
    secret = tmp_path_factory.mktemp("elsewhere") / "id_rsa.txt"
    secret.write_text(SECRET, encoding="utf-8")
    return secret


def insert(con, citekey: str, *, parsed_path=None, pdf_path=None, status="parsed"):
    """One ledger row, written the way an older release -- or a hand
    edit of the sqlite file -- leaves one: the columns say whatever they
    say, and nothing validated them on the way in."""
    con.execute(
        "INSERT INTO items (citekey, title, status, parsed_path, pdf_path, pdf_hash, "
        "last_synced) VALUES (?, ?, ?, ?, ?, 'abc123', '2026-01-01')",
        (citekey, f"Paper {citekey}", status, parsed_path, pdf_path),
    )
    con.commit()


RELATIVE_TEXT = "the relocated corpus text"


@pytest.fixture
def relative_row(isolated_config):
    """A row as #966 writes it: names relative to their roots."""
    isolated_config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    (isolated_config.PARSED_DIR / "rel2024.txt").write_text(RELATIVE_TEXT, encoding="utf-8")
    with ledger.connection() as con:
        insert(con, "rel2024", parsed_path="rel2024.txt")
    return isolated_config


class TestRelativeRowsAreRead:
    """Every reader must find the file a relative row names (#966).
    Opened raw, `rel2024.txt` resolves against the process cwd."""

    def test_overview(self, relative_row, monkeypatch, tmp_path_factory):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        assert _overview._parsed_texts(["rel2024"]) == {"rel2024": RELATIVE_TEXT}

    def test_overlap_ledger_returns_an_openable_path(
        self, relative_row, monkeypatch, tmp_path_factory
    ):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        _hash, path = overlap_index_ledger.ledger_item("rel2024")
        assert Path(path).read_text(encoding="utf-8") == RELATIVE_TEXT
        ((_ck, _h, listed),) = overlap_index_ledger._ledger_items()
        assert Path(listed).read_text(encoding="utf-8") == RELATIVE_TEXT

    def test_outputs_present(self, relative_row, monkeypatch, tmp_path_factory):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        assert ledger_upsert._parse_outputs_present("rel2024", "rel2024.txt")

    def test_tldr_fingerprint(self, relative_row, monkeypatch, tmp_path_factory):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        with ledger.reading() as con:
            assert tldr._fingerprint(con, "rel2024")

    def test_retrieval_indexes_the_text(self, relative_row, monkeypatch, tmp_path_factory):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        assert [r.citekey for r in retrieval.search("relocated")] == ["rel2024"]

    def test_the_index_fingerprint_stats_the_file(
        self, relative_row, monkeypatch, tmp_path_factory
    ):
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        present, size, _mtime = retrieval_cache._parsed_file_stat("rel2024.txt")
        assert present and size == len(RELATIVE_TEXT)

    def test_passages_reads_the_parsed_text(self, relative_row, monkeypatch, tmp_path_factory):
        (relative_row.PARSED_DIR / "rel2024.txt").write_text(
            "one two\fthree four", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        with ledger.reading() as con:
            found, why = passages.source_passages(con, "rel2024")
        assert why is None and [p.page for p in found] == [1, 2]

    def test_passages_hands_pdftotext_the_resolved_pdf(
        self, relative_row, monkeypatch, tmp_path_factory
    ):
        pdf = relative_row.BIB_FILE_PATH.parent / "paper.pdf"
        pdf.write_bytes(b"%PDF")
        with ledger.connection() as con:
            insert(con, "pdf2024", pdf_path="paper.pdf")
        ran = []
        monkeypatch.setattr(passages, "_from_pdf", lambda *a: ran.append(a[0]) or ([], "ran"))
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        with ledger.reading() as con:
            passages.source_passages(con, "pdf2024")
        assert ran == [str(pdf.resolve())]

    def test_the_enrichment_corpus_carries_absolute_paths(
        self, relative_row, monkeypatch, tmp_path_factory
    ):
        pdf = relative_row.BIB_FILE_PATH.parent / "paper.pdf"
        pdf.write_bytes(b"%PDF")
        with ledger.connection() as con:
            insert(con, "pdf2024", pdf_path="paper.pdf")
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
        doc = next(d for d in enrich_corpus.build_corpus() if d.citekey == "pdf2024")
        assert doc.pdf_path == str(pdf.resolve())

    def test_enrich_reuses_a_relative_corpus_parse(
        self, relative_row, monkeypatch, tmp_path_factory
    ):
        """`_docling_reuse` opens `CorpusDoc.text_path` and stats
        `.pdf_path` directly, so both must come back absolute (#966)."""
        from chitragupta.enrich import _docling_reuse

        pdf = relative_row.BIB_FILE_PATH.parent / "rel2024.pdf"
        pdf.write_bytes(b"%PDF")
        os.utime(pdf, ns=(1, 1))  # older than the parse, so reuse is allowed
        with ledger.connection() as con:
            con.execute("UPDATE items SET pdf_path = 'rel2024.pdf' WHERE citekey = 'rel2024'")
            con.commit()
        passages.sidecar_path("rel2024").write_text("[]", encoding="utf-8")
        monkeypatch.setattr(config, "DOCLING_IMAGES", False)
        monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))

        (doc,) = [d for d in enrich_corpus.build_corpus() if d.citekey == "rel2024"]
        assert Path(doc.text_path).is_absolute() and Path(doc.pdf_path).is_absolute()
        assert _docling_reuse._corpus_parse_available(doc)


class TestConfinedPath:
    """The one helper, beside `resolves_inside` it is built on."""

    def test_a_path_inside_the_root_comes_back(self, tmp_path):
        inside = tmp_path / "a.txt"
        assert config.confined_path(inside, tmp_path) == inside

    def test_a_path_outside_the_root_is_refused(self, tmp_path):
        assert config.confined_path(tmp_path.parent / "a.txt", tmp_path) is None

    def test_a_dot_dot_escape_is_refused(self, tmp_path):
        assert config.confined_path(tmp_path / ".." / "a.txt", tmp_path) is None

    @pytest.mark.parametrize("empty", [None, ""])
    def test_nothing_there_is_not_a_refusal(self, empty, tmp_path, capsys):
        """The routine case -- a row with no parsed text yet -- answers
        `None` like a refusal does, but must not be reported as one, or
        every unparsed row in the corpus prints a warning."""
        assert config.confined_path(empty, tmp_path) is None
        assert capsys.readouterr().err == ""

    def test_a_refusal_names_the_path_and_the_root(self, tmp_path, capsys):
        config.confined_path("/etc/passwd", tmp_path)
        err = capsys.readouterr().err
        assert "/etc/passwd" in err
        assert str(tmp_path) in err

    def test_a_symlink_out_of_the_root_is_refused(self, tmp_path):
        """The case a spelling check cannot see, and the one that
        matters on a shared `content/`: the name is inside the root and
        the bytes are not."""
        outside = tmp_path / "outside.txt"
        outside.write_text(SECRET, encoding="utf-8")
        root = tmp_path / "root"
        root.mkdir()
        link = root / "inside.txt"
        try:
            link.symlink_to(outside)
        except OSError:  # Windows without developer mode
            pytest.skip("this host cannot create a symlink")
        assert config.confined_path(link, root) is None

    def test_a_value_the_platform_cannot_resolve_is_refused_not_raised(self, tmp_path):
        """A NUL byte raises `ValueError` out of `resolve()` rather than
        answering False, and a name Windows rejects raises `OSError`.
        Both are refusals; neither may reach the caller as a crash."""
        assert config.confined_path("a\x00b.txt", tmp_path) is None

    def test_a_drive_relative_or_backslashed_name_stays_inside(self, tmp_path):
        """`C:x` and `a\\b` are one relative name on POSIX and two very
        different things on Windows. Whatever the platform makes of
        them, the answer asserted here is the only one that matters:
        nothing outside the root comes back."""
        for spelling in ("C:x.txt", "a\\b.txt", "sub/c.txt"):
            resolved = config.confined_path(tmp_path / spelling, tmp_path)
            assert resolved is None or config.resolves_inside(resolved, tmp_path)


class TestLedgerParsedPathIsConfined:
    """`parsed_path` read back out of a row nothing validated."""

    def test_retrieval_does_not_index_an_outside_file(self, isolated_config, outside_file):
        config.PARSED_DIR.mkdir(parents=True)
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file))
        assert retrieval.search("brahmastra") == []

    def test_the_index_fingerprint_does_not_stat_an_outside_file(
        self, isolated_config, outside_file
    ):
        """Fixing only the read leaves the leak cached: the fingerprint
        matched, so `_full_text` was never called again."""
        assert retrieval_cache._parsed_file_stat(str(outside_file)) == (False, 0, 0)

    def test_an_index_built_before_the_fix_stops_serving_the_leak(
        self, isolated_config, outside_file, monkeypatch
    ):
        """The upgrade path, which a check at the read alone does not
        cover: `content/retrieval_index.json` survives an upgrade, and
        an entry written while the row was still trusted holds the
        leaked tokens outright. It keeps being served unless the
        *fingerprint* also moves -- which is why `_parsed_file_stat` is
        confined too, and not merely `_full_text`."""
        config.PARSED_DIR.mkdir(parents=True)
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file))
        # A scoped context, not `monkeypatch.undo()`: undo also reverted
        # `isolated_config`, so the second search ran against the real
        # checkout's content/ -- and, while readers still opened the
        # ledger through the writer, created a ledger there (#843).
        with monkeypatch.context() as scoped:
            scoped.setattr(config, "confined_path", lambda value, root: Path(value or "."))
            assert [r.citekey for r in retrieval.search("brahmastra")] == ["leaky2024"]
            assert config.RETRIEVAL_INDEX_PATH.exists()
        retrieval_cache._forget_cache()
        assert retrieval.search("brahmastra") == []

    def test_passages_quotes_nothing_from_an_outside_file(self, isolated_config, outside_file):
        config.PARSED_DIR.mkdir(parents=True)
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file))
            found, why = passages.source_passages(con, "leaky2024")
        assert found == []
        assert why is not None

    def test_tldr_refuses_to_fingerprint_an_outside_file(self, isolated_config, outside_file):
        config.PARSED_DIR.mkdir(parents=True)
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file))
            with pytest.raises(tldr.TldrError):
                tldr._fingerprint(con, "leaky2024")

    def test_the_overlap_index_skips_an_outside_file(self, isolated_config, outside_file):
        config.PARSED_DIR.mkdir(parents=True)
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file))
        assert overlap_index_ledger.ledger_item("leaky2024") is None
        assert overlap_index_ledger._ledger_items() == []

    def test_discover_reads_no_outside_file(self, isolated_config, outside_file):
        config.PARSED_DIR.mkdir(parents=True)
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file))
        assert _overview._parsed_texts(["leaky2024"]) == {}

    def test_the_enrichment_corpus_carries_no_outside_path(self, isolated_config, outside_file):
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file), pdf_path=str(outside_file))
        doc = enrich_corpus.build_corpus()[0]
        assert doc.text_path is None
        assert doc.pdf_path is None

    def test_sync_treats_an_outside_parse_as_no_parse(self, isolated_config, outside_file):
        """A row claiming to be parsed at a path outside the corpus has
        no parse this pipeline will read, so the next sync must re-parse
        it rather than skip it as already done."""
        assert ledger_upsert._parse_outputs_present("leaky2024", str(outside_file)) is False

    def test_a_real_parsed_file_is_still_read(self, isolated_config):
        """The other half of the bargain: confinement that also refuses
        the corpus is not a fix. This is the shape every real row has."""
        config.PARSED_DIR.mkdir(parents=True)
        parsed = config.PARSED_DIR / "good2024.txt"
        parsed.write_text("digital twin brahmastra prose", encoding="utf-8")
        with ledger.connection() as con:
            insert(con, "good2024", parsed_path=str(parsed))
        assert [r.citekey for r in retrieval.search("brahmastra")] == ["good2024"]


class TestLedgerPdfPathIsConfined:
    """`pdf_path` is worse than a read: it is handed to `pdftotext`."""

    def test_passages_runs_no_pdftotext_on_an_outside_path(
        self, isolated_config, outside_file, monkeypatch
    ):
        ran = []
        monkeypatch.setattr(passages, "_from_pdf", lambda *a: ran.append(a) or ([], "ran"))
        config.PARSED_DIR.mkdir(parents=True)
        outside_pdf = outside_file.with_suffix(".pdf")
        outside_pdf.write_bytes(b"%PDF-1.4")
        with ledger.connection() as con:
            insert(con, "leaky2024", pdf_path=str(outside_pdf))
            passages.source_passages(con, "leaky2024")
        assert ran == []


class TestBibFileFieldIsConfined:
    """The write side. A `file` field is data someone else's tool wrote."""

    def test_an_absolute_path_outside_the_bib_directory_is_refused(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        pdf = outside / "private.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        bib_dir = tmp_path / "papers"
        bib_dir.mkdir()
        field = f"Private:{pdf}:application/pdf"
        assert bib_reader._resolve_pdf_path(field, bib_dir) == (
            None,
            bib_reader.PDF_OUTSIDE_PAPERS,
        )

    def test_a_dot_dot_escape_is_refused(self, tmp_path):
        outside = tmp_path / "private.pdf"
        outside.write_bytes(b"%PDF-1.4")
        bib_dir = tmp_path / "papers"
        bib_dir.mkdir()
        field = "Private:../private.pdf:application/pdf"
        assert bib_reader._resolve_pdf_path(field, bib_dir) == (
            None,
            bib_reader.PDF_OUTSIDE_PAPERS,
        )

    def test_the_outside_file_is_never_even_statted(self, tmp_path, monkeypatch):
        """Refused before `is_file()`, so a refused path is not probed
        for existence either -- the answer must not depend on, or
        disclose, what is actually there."""
        statted = []
        monkeypatch.setattr(bib_reader.Path, "is_file", lambda self: statted.append(self) or True)
        bib_dir = tmp_path / "papers"
        bib_dir.mkdir()
        field = "Private:/etc/passwd:application/pdf"
        assert bib_reader._resolve_pdf_path(field, bib_dir)[0] is None
        assert statted == []

    def test_outside_beats_the_gone_reason(self, tmp_path):
        """Two attachments, one outside and one merely missing: the
        refusal is the more actionable report, and the one a person can
        act on without guessing."""
        bib_dir = tmp_path / "papers"
        bib_dir.mkdir()
        field = "A:/elsewhere/a.pdf:application/pdf;B:missing.pdf:application/pdf"
        assert bib_reader._resolve_pdf_path(field, bib_dir) == (
            None,
            bib_reader.PDF_OUTSIDE_PAPERS,
        )

    def test_a_later_attachment_inside_the_bib_directory_still_resolves(self, tmp_path):
        bib_dir = tmp_path / "papers"
        bib_dir.mkdir()
        good = bib_dir / "files" / "good.pdf"
        good.parent.mkdir()
        good.write_bytes(b"%PDF-1.4")
        field = "A:/elsewhere/a.pdf:application/pdf;B:files/good.pdf:application/pdf"
        assert bib_reader._resolve_pdf_path(field, bib_dir) == (
            str(good),
            bib_reader.PDF_RESOLVED,
        )

    def test_the_new_reason_has_a_label_sync_can_print(self):
        assert bib_reader.PDF_OUTSIDE_PAPERS in bib_reader.PDF_RESOLUTION_LABELS

    def test_verbatim_locate_resolves_no_outside_pdf(
        self, isolated_config, tmp_path_factory, ledger_con
    ):
        """`review/verbatim_check/_corpus.py` hands the PDF it finds to
        `pdftotext`, so it needs the same confinement. It reads the
        ledger's `pdf_path` since #956 rather than re-parsing the `file`
        field, so the row is what is planted here: one naming a file
        outside the bib directory, as a hand-edited ledger could."""
        outside = tmp_path_factory.mktemp("outside") / "private.pdf"
        outside.write_bytes(b"%PDF-1.4")
        ledger_con.execute(
            "INSERT INTO items (citekey, title, status, pdf_path, last_synced)"
            " VALUES ('leaky2024', 'T', 'discovered', ?, '2026-01-01')",
            (str(outside),),
        )
        ledger_con.commit()
        assert verbatim_corpus.pdf_path("leaky2024") is None
