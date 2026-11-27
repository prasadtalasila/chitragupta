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
    secret = tmp_path_factory.mktemp("elsewhere") / "id_rsa.txt"
    secret.write_text(SECRET, encoding="utf-8")
    return secret


def insert(con, citekey: str, *, parsed_path=None, pdf_path=None, status="parsed"):
    con.execute(
        "INSERT INTO items (citekey, title, status, parsed_path, pdf_path, pdf_hash, "
        "last_synced) VALUES (?, ?, ?, ?, ?, 'abc123', '2026-01-01')",
        (citekey, f"Paper {citekey}", status, parsed_path, pdf_path),
    )
    con.commit()


RELATIVE_TEXT = "the relocated corpus text"


@pytest.fixture
def relative_row(isolated_config):
    isolated_config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    (isolated_config.PARSED_DIR / "rel2024.txt").write_text(RELATIVE_TEXT, encoding="utf-8")
    with ledger.connection() as con:
        insert(con, "rel2024", parsed_path="rel2024.txt")
    return isolated_config


class TestRelativeRowsAreRead:
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
    def test_a_path_inside_the_root_comes_back(self, tmp_path):
        inside = tmp_path / "a.txt"
        assert config.confined_path(inside, tmp_path) == inside

    def test_a_path_outside_the_root_is_refused(self, tmp_path):
        assert config.confined_path(tmp_path.parent / "a.txt", tmp_path) is None

    def test_a_dot_dot_escape_is_refused(self, tmp_path):
        assert config.confined_path(tmp_path / ".." / "a.txt", tmp_path) is None

    @pytest.mark.parametrize("empty", [None, ""])
    def test_nothing_there_is_not_a_refusal(self, empty, tmp_path, capsys):
        assert config.confined_path(empty, tmp_path) is None
        assert capsys.readouterr().err == ""

    def test_a_refusal_names_the_path_and_the_root(self, tmp_path, capsys):
        config.confined_path("/etc/passwd", tmp_path)
        err = capsys.readouterr().err
        assert "/etc/passwd" in err
        assert str(tmp_path) in err

    def test_a_symlink_out_of_the_root_is_refused(self, tmp_path):
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

    def test_a_symlink_loop_lands_nowhere_on_every_python(self, tmp_path):
        first, second = tmp_path / "loop_a.txt", tmp_path / "loop_b.txt"
        try:
            first.symlink_to(second)
            second.symlink_to(first)
        except OSError:  # Windows without developer mode
            pytest.skip("this host cannot create a symlink")
        assert config.resolves_inside(first, tmp_path) is False
        assert config.confined_path(first, tmp_path) is None

    def test_a_value_the_platform_cannot_resolve_is_refused_not_raised(self, tmp_path):
        assert config.confined_path("a\x00b.txt", tmp_path) is None

    def test_a_drive_relative_or_backslashed_name_stays_inside(self, tmp_path):
        for spelling in ("C:x.txt", "a\\b.txt", "sub/c.txt"):
            resolved = config.confined_path(tmp_path / spelling, tmp_path)
            assert resolved is None or config.resolves_inside(resolved, tmp_path)


class TestLedgerParsedPathIsConfined:
    def test_retrieval_does_not_index_an_outside_file(self, isolated_config, outside_file):
        config.PARSED_DIR.mkdir(parents=True)
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file))
        assert retrieval.search("brahmastra") == []

    def test_the_index_fingerprint_does_not_stat_an_outside_file(
        self, isolated_config, outside_file
    ):
        assert retrieval_cache._parsed_file_stat(str(outside_file)) == (False, 0, 0)

    def test_an_index_built_before_the_fix_stops_serving_the_leak(
        self, isolated_config, outside_file, monkeypatch
    ):
        config.PARSED_DIR.mkdir(parents=True)
        with ledger.connection() as con:
            insert(con, "leaky2024", parsed_path=str(outside_file))
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
        assert ledger_upsert._parse_outputs_present("leaky2024", str(outside_file)) is False

    def test_a_real_parsed_file_is_still_read(self, isolated_config):
        config.PARSED_DIR.mkdir(parents=True)
        parsed = config.PARSED_DIR / "good2024.txt"
        parsed.write_text("digital twin brahmastra prose", encoding="utf-8")
        with ledger.connection() as con:
            insert(con, "good2024", parsed_path=str(parsed))
        assert [r.citekey for r in retrieval.search("brahmastra")] == ["good2024"]


class TestLedgerPdfPathIsConfined:
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
        statted = []
        monkeypatch.setattr(bib_reader.Path, "is_file", lambda self: statted.append(self) or True)
        bib_dir = tmp_path / "papers"
        bib_dir.mkdir()
        field = "Private:/etc/passwd:application/pdf"
        assert bib_reader._resolve_pdf_path(field, bib_dir)[0] is None
        assert statted == []

    def test_outside_beats_the_gone_reason(self, tmp_path):
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
        outside = tmp_path_factory.mktemp("outside") / "private.pdf"
        outside.write_bytes(b"%PDF-1.4")
        ledger_con.execute(
            "INSERT INTO items (citekey, title, status, pdf_path, last_synced)"
            " VALUES ('leaky2024', 'T', 'discovered', ?, '2026-01-01')",
            (str(outside),),
        )
        ledger_con.commit()
        assert verbatim_corpus.pdf_path("leaky2024") is None
