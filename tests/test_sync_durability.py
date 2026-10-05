"""Finished work survives an interruption, and one bad document fails
only itself (#961, folding in #962, #978 and #970).

Two properties, each tested over every path that has to hold it:

- **Durability.** A document whose parse finished is `parsed` in the
  ledger before anything else happens, on the serial path and on the
  pool path alike. Before #961 the pool path drained every future and
  only then wrote the ledger, so Ctrl+C or a pool failure left every
  finished `.txt` on disk with its row still `discovered`, and the next
  run parsed it again.
- **One boundary per document.** An exception no backend promised
  (`RuntimeError`, a pydantic error, a `UnicodeEncodeError`) is that
  document's recorded failure, never the batch's traceback.

The process-pool executor is not a parameter here. A real
`ProcessPoolExecutor` runs its work in a child interpreter where this
process's fakes do not exist (`tests/conftest.py::thread_executor`), and
the code under test, `sync_pool._drain_pool`, does not branch on which
executor it was handed.
"""

import subprocess
import time
from pathlib import Path

import pytest

from chitragupta import config, ledger, overlap_chroma, pdf_text, sync, sync_pool, sync_residue
from chitragupta.enrich import embed_text
from chitragupta.enrich.corpus import CorpusDoc
from tests.conftest import thread_executor

BIB = "".join(
    f"""
@article{{doc_{i}_2024,
  title = {{Paper {i}}},
  author = {{Author, A}},
  year = {{2024}},
  file = {{p{i}.pdf:p{i}.pdf:application/pdf}},
}}
"""
    for i in range(6)
)
CITEKEYS = [f"doc_{i}_2024" for i in range(6)]
BAD = "doc_3_2024"


@pytest.fixture(autouse=True)
def _pdftotext_present(monkeypatch):
    """As in `tests/test_sync.py`: extraction is faked, so the up-front
    backend probe must not depend on poppler being on this host."""
    monkeypatch.setattr(pdf_text, "is_available", lambda: True)


@pytest.fixture
def corpus(isolated_config):
    isolated_config.BIB_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    isolated_config.BIB_FILE_PATH.write_text(BIB, encoding="utf-8")
    for i in range(6):
        (isolated_config.BIB_FILE_PATH.parent / f"p{i}.pdf").write_bytes(b"%PDF" + b"x" * i)
    return isolated_config


@pytest.fixture(params=["serial", "thread_pool"])
def path(request, monkeypatch):
    """Both executors sync can run, by name. The pool is pdftotext's
    thread pool, so a fake parse needs no docling passages sidecar to
    count as finished on the next run."""
    if request.param == "thread_pool":
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        monkeypatch.setattr(sync_pool, "_executor_for", thread_executor)
    else:
        monkeypatch.setattr(config, "PARSER_WORKERS", 1)
    return request.param


def _finishing_first(path: str) -> list[str]:
    """The documents that finish before `BAD` is reached: the ones before
    it in bib order on the serial path, every other one in the pool."""
    if path == "serial":
        return CITEKEYS[: CITEKEYS.index(BAD)]
    return [c for c in CITEKEYS if c != BAD]


def _statuses() -> dict:
    con = ledger.connect()
    try:
        return {row["citekey"]: row["status"] for row in ledger.all_items(con)}
    finally:
        con.close()


def _parsed_count() -> int:
    return sum(1 for status in _statuses().values() if status == "parsed")


def _write_parse(citekey: str) -> Path:
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    out = config.PARSED_DIR / f"{citekey}.txt"
    out.write_text(f"extracted text for {citekey}", encoding="utf-8")
    return out


def _install(monkeypatch, document):
    """Route every document through `document(citekey)`, which returns the
    parse's path or raises, on both entry points: a run with one document
    left takes the serial path whatever `[parser].workers` says."""
    monkeypatch.setattr(pdf_text, "extract_text", lambda _pdf, citekey: document(citekey))

    def extract_one(job):
        _pdf, citekey, _threads = job
        try:
            return citekey, str(document(citekey)), None
        except pdf_text.ExtractionError as exc:
            return citekey, None, exc

    monkeypatch.setattr(pdf_text, "extract_one", extract_one)


def _after_the_others_commit(path: str, failure: BaseException):
    """A document function that parses every document but `BAD`, which
    waits until `_finishing_first(path)` are `parsed` in the ledger and
    then raises `failure`.

    Waiting on the ledger rather than on the other workers is what makes
    the interleaving deterministic: it is exactly the state the fix has
    to produce. Bounded, so the pre-fix pool path, which never committed
    before the pool drained, raises after the bound instead of hanging."""
    expected = len(_finishing_first(path))

    def document(citekey: str) -> Path:
        if citekey != BAD:
            return _write_parse(citekey)
        deadline = time.monotonic() + 5.0
        while _parsed_count() < expected and time.monotonic() < deadline:
            time.sleep(0.01)
        raise failure

    return document


class TestFinishedWorkIsKept:
    def test_an_interrupt_keeps_every_document_that_finished(self, corpus, path, monkeypatch):
        _install(monkeypatch, _after_the_others_commit(path, KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            sync.run()

        statuses = _statuses()
        assert [c for c in CITEKEYS if statuses[c] == "parsed"] == _finishing_first(path)
        assert statuses[BAD] == "discovered"

    def test_the_next_run_parses_only_what_the_interrupt_left(self, corpus, path, monkeypatch):
        _install(monkeypatch, _after_the_others_commit(path, KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            sync.run()

        seen = []
        _install(monkeypatch, lambda c: seen.append(c) or _write_parse(c))
        assert sync.run() == 0
        assert sorted(seen) == [c for c in CITEKEYS if c not in _finishing_first(path)]


class TestOneBadDocumentFailsOnlyItself:
    @pytest.mark.parametrize(
        "failure",
        [RuntimeError("docling choked"), UnicodeEncodeError("utf-8", "x", 0, 1, "bad")],
        ids=["RuntimeError", "UnicodeEncodeError"],
    )
    def test_an_unexpected_exception_is_that_documents_failure(
        self, corpus, path, monkeypatch, failure
    ):
        """#962: only `ExtractionError`/`BackendUnavailable` were caught,
        so anything else aborted the batch and, on the pool path,
        discarded every collected result."""

        def document(citekey):
            if citekey == BAD:
                raise failure
            return _write_parse(citekey)

        _install(monkeypatch, document)
        assert sync.run() == 1

        statuses = _statuses()
        assert statuses[BAD] == "parse_failed"
        assert all(statuses[c] == "parsed" for c in CITEKEYS if c != BAD)

    def test_the_recorded_error_names_the_exception(self, corpus, path, monkeypatch):
        def document(citekey):
            if citekey == BAD:
                raise RuntimeError("docling choked")
            return _write_parse(citekey)

        _install(monkeypatch, document)
        sync.run()
        con = ledger.connect()
        try:
            row = con.execute(
                "SELECT parse_error, failure_kind FROM items WHERE citekey = ?", (BAD,)
            ).fetchone()
        finally:
            con.close()
        parse_error, failure_kind = row
        assert "RuntimeError" in parse_error
        assert "docling choked" in parse_error
        assert failure_kind == "deterministic"

    @pytest.mark.parametrize(
        "failure",
        [OSError(24, "Too many open files"), MemoryError()],
        ids=["OSError", "MemoryError"],
    )
    def test_a_failure_of_the_machine_is_retried_next_run(self, failure):
        """The #842 rule `write_failed` already applies: an `OSError` (a
        busy thread pool running out of descriptors) or a `MemoryError`
        is the machine, not the PDF, so the document comes back next run
        instead of being written off for good."""
        assert pdf_text.document_failure(failure).transient is True

    def test_anything_else_is_the_documents_own_failure(self):
        assert not getattr(pdf_text.document_failure(RuntimeError("x")), "transient", False)

    def test_the_pool_entry_point_returns_rather_than_raises(self, monkeypatch):
        """The boundary itself, below the fakes the tests above install:
        `extract_one` hands back an unexpected exception as the
        document's failure, and it survives pickling across a process
        boundary because it is an `ExtractionError` holding a string."""

        def explode(_pdf, _citekey, _threads=None):
            raise RuntimeError("docling choked")

        monkeypatch.setattr(pdf_text, "extract_text", explode)
        citekey, out_path, exc = pdf_text.extract_one(("x.pdf", "k_2024", None))
        assert (citekey, out_path) == ("k_2024", None)
        assert isinstance(exc, pdf_text.ExtractionError)
        assert not getattr(exc, "transient", False)

    def test_a_future_that_raises_is_charged_to_its_own_document(self, corpus, monkeypatch):
        """`future.result()` can still raise -- a result the worker
        could not pickle, or a stand-in `extract_one` -- and it used to
        escape `_drain_pool` and discard every result."""
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        monkeypatch.setattr(sync_pool, "_executor_for", thread_executor)

        def extract_one(job):
            _pdf, citekey, _threads = job
            if citekey == BAD:
                raise RuntimeError("worker result could not be pickled")
            return citekey, str(_write_parse(citekey)), None

        monkeypatch.setattr(pdf_text, "extract_one", extract_one)
        assert sync.run() == 1
        statuses = _statuses()
        assert statuses[BAD] == "parse_failed"
        assert all(statuses[c] == "parsed" for c in CITEKEYS if c != BAD)


@pytest.mark.usefixtures("programs_on_path")
class TestEnrichmentTextFallback:
    """#978: `embed_text.get_text` is reached for exactly the documents
    a parse already failed on, and every topic stage reads it."""

    @pytest.mark.parametrize(
        "failure",
        [
            subprocess.CalledProcessError(1, ["pdftotext"], stderr=b"Syntax Error"),
            FileNotFoundError("pdftotext"),
        ],
        ids=["corrupt-pdf", "no-pdftotext"],
    )
    def test_a_failing_pdftotext_is_no_text_not_a_crash(
        self, isolated_config, monkeypatch, tmp_path, caplog, failure
    ):
        seen = {}

        def fail(cmd, **_kwargs):
            seen["out"] = cmd[-1]
            raise failure

        monkeypatch.setattr(subprocess, "run", fail)
        doc = CorpusDoc(citekey="a2024", title="t", pdf_path=str(tmp_path / "a.pdf"))
        assert embed_text.get_text(doc) is None
        assert "a2024" in caplog.text
        assert not Path(seen["out"]).exists()


class TestStaleReportSurvivesItsArtefacts:
    """#970: `sync_residue` runs after every upsert has committed and
    before the stale list prints, so an exception there hid the one
    thing the person needed to see."""

    def test_an_unreadable_dossier_is_a_note(self, isolated_config, monkeypatch):
        evidence = isolated_config.DOSSIERS_DIR / "dt" / "survey" / "evidence.md"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("## `gone_2020`\n", encoding="utf-8")
        real_read_text = Path.read_text

        def unreadable(self, *args, **kwargs):
            if self == evidence:
                raise PermissionError(13, "Permission denied")
            return real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", unreadable)
        found, notes = sync_residue.scan(["gone_2020"])
        assert found == {"gone_2020": []}
        assert any(str(evidence) in note and "Permission denied" in note for note in notes)

    def test_a_chroma_error_is_a_note(self, isolated_config, monkeypatch):
        isolated_config.CHROMA_DIR.mkdir(parents=True)
        monkeypatch.setattr(overlap_chroma, "optional_stack", lambda: (object(), object()))

        def broken(_module):
            raise RuntimeError("no such table: collections")

        monkeypatch.setattr(overlap_chroma, "built_collection", broken)
        found, notes = sync_residue.scan(["gone_2020"])
        assert found == {"gone_2020": []}
        assert any("no such table: collections" in note for note in notes)
