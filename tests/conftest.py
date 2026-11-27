import json
import multiprocessing
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


from chitragupta import config, ledger, programs
from tests import content_guard


# A dependency's sys.path entry can shadow stdlib for every later spawn child;
# test_runlock spawns directly, so sanitise once here.
def pytest_sessionstart(session):
    from chitragupta import pdf_text

    pdf_text.drop_stdlib_shadowing_path_entries()
    content_guard.record(session, config.CONTENT_DIR)


def pytest_sessionfinish(session):
    content_guard.verify(session)


# Pinned: config.toml is per-host and read at import, so a developer's own
# values would fail tests that CI never sees fail.
@pytest.fixture(autouse=True)
def _pin_parser_settings(monkeypatch):
    monkeypatch.setattr(config, "PARSER", "pdftotext")
    monkeypatch.setattr(config, "PARSER_OCR", False)
    monkeypatch.setattr(config, "PARSER_FORMULAS", False)
    monkeypatch.setattr(config, "PARSER_WORKERS", 1)


@pytest.fixture(autouse=True)
def _fresh_retrieval_memos():
    from chitragupta import retrieval_cache, retrieval_spelling

    retrieval_cache._READ_ONLY_MEMO.clear()
    retrieval_spelling._MEMO.clear()


# Stubbed at ensure_running, not prestart_pool, so the decision logic still
# runs; guarded because Windows resolves to spawn and never reaches it.
@pytest.fixture(autouse=True)
def _no_real_forkserver(monkeypatch):
    if "forkserver" not in multiprocessing.get_all_start_methods():
        return
    from multiprocessing import forkserver

    monkeypatch.setattr(forkserver, "ensure_running", lambda: None)


# pytest.fail, not ImportError: the ladder catches ImportError and degrades to
# lexical, so a refusal test would pass on it. Real models are a ~420 MB
# download on CI (#861); opt out with @pytest.mark.real_resolver_loaders.
@pytest.fixture(autouse=True)
def _no_real_resolver_models(request, monkeypatch):
    monkeypatch.setattr("chitragupta.discover._resolve._FAILED", {})
    if request.node.get_closest_marker("real_resolver_loaders"):
        return

    def refuse():
        pytest.fail(
            "reached the real resolver model: monkeypatch _resolve._load_model "
            "and _resolve._load_reranker with a fake",
            pytrace=False,
        )

    monkeypatch.setattr("chitragupta.discover._resolve._load_model", refuse)
    monkeypatch.setattr("chitragupta.discover._resolve._load_reranker", refuse)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"

    under_content = {
        "CONTENT_DIR": "",
        "PARSED_DIR": "parsed",
        "LEDGER_PATH": "ledger.sqlite",
        "REVIEW_DIR": "review",
        "DRAFTS_DIR": "drafts",
        "DOSSIERS_DIR": "dossiers",
        "SPECS_DIR": "specs",
        "TLDR_DIR": "tldr",
        "RETRIEVAL_INDEX_PATH": "retrieval_index.json",
        "RETRIEVAL_PASSAGE_INDEX_PATH": "retrieval_passage_index.json",
        "OVERLAP_DIR": "overlap",
        "VERBATIM_ALLOWLIST_PATH": "verbatim_allowlist.toml",
        "STYLE_EXCEPTIONS_PATH": "style_exceptions.toml",
        "PIPELINE_LOCK_PATH": "pipeline.lock.db",
        "DOCLING_DIR": "docling",
        "DOCLING_CACHE_PATH": "docling_cache.json",
        "CHROMA_DIR": "chroma",
        "TOPICS_PATH": "topics.json",
        "TOPIC_EMBED_CACHE_PATH": "topic_embed_cache.json",
        "SEED_TOPICS_PATH": "seed_topics.toml",
        "KEYWORDS_PATH": "keywords.toml",
        "TOPIC_SEEDS_PATH": "topic_seeds.json",
        "TOPIC_SET_PATH": "topic_set.json",
        "TOPIC_GRAPH_PATH": "topic_graph.json",
        "RENDERED_DIR": "rendered",
    }
    for name, relative in under_content.items():
        monkeypatch.setattr(config, name, content_dir / relative if relative else content_dir)

    monkeypatch.setattr(config, "BIB_FILE_PATH", tmp_path / "bibliography.bib")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    for name, value in {
        "DOCLING_IMAGES": False,
        "DOCLING_IMAGE_SCALE": 2.0,
        "DOCLING_FORMULAS": False,
    }.items():
        monkeypatch.setattr(config, name, value)
    # 0.5, above the shipped 0.15, so a test can place a vector below the floor.
    monkeypatch.setattr(config, "SEED_TOPIC_MIN_SIMILARITY", 0.5)
    monkeypatch.setattr(config, "SEED_TOPIC_MAX_PAPERS", 25)
    monkeypatch.setattr(config, "KEYWORD_TOP_N", 40)
    monkeypatch.setattr(config, "KEYWORD_MIN_DF", 2)
    monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 3)
    monkeypatch.setattr(config, "TOPIC_MIN_CLUSTER_SIZE", 3)
    monkeypatch.setattr(config, "TOPIC_MIN_SAMPLES", 2)
    monkeypatch.setattr(config, "TOPIC_NEIGHBORS", 5)
    monkeypatch.setattr(config, "TOPIC_DISTRIBUTION", True)
    monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_RATIO", 0.5)
    monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_MAX", 8)
    monkeypatch.setattr(config, "TOPIC_EXCLUDE_AUTHOR_NAMES", True)
    monkeypatch.setattr(config, "TOPIC_CONVERGE_SIMILARITY", 0.45)
    monkeypatch.setattr(config, "PROVENANCE_WEAK_SCORE", 0.20)
    monkeypatch.setattr(config, "PROVENANCE_GOOD_SCORE", 0.50)
    return config


@pytest.fixture
def ledger_con(isolated_config):
    con = ledger.connect()
    yield con
    con.close()


def content_draft(cfg, name: str) -> Path:
    path = cfg.CONTENT_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def parsed_text(citekey: str, text: str) -> Path:
    path = parsed_file(citekey)
    path.write_text(text, encoding="utf-8")
    return path


def parsed_file(citekey: str) -> Path:
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    return config.PARSED_DIR / f"{citekey}.txt"


def real_bibliography_path() -> Path:
    return config.PROJECT_ROOT / "papers" / "bibliography.bib"


def make_reference(citekey="smith_example_2024", **overrides):
    from chitragupta.bib_reader import Reference

    fields = dict(
        citekey=citekey,
        item_type="article",
        title="An Example Paper",
        authors=[("Jane", "Smith")],
        year="2024",
        doi=None,
        url=None,
        fields={},
        pdf_path=None,
    )
    fields.update(overrides)
    return Reference(**fields)


@pytest.fixture
def make_ref():
    return make_reference


def add_item(citekey, parsed_text=None, pdf_path=None, title="T"):
    parsed_path = None
    if parsed_text is not None:
        path = parsed_file(citekey)
        path.write_text(parsed_text, encoding="utf-8")
        parsed_path = str(path)
    con = ledger.connect()
    try:
        con.execute(
            "INSERT OR REPLACE INTO items"
            " (citekey, title, status, parsed_path, pdf_path, last_synced)"
            " VALUES (?, ?, 'parsed', ?, ?, '2026-01-01')",
            (citekey, title, parsed_path, pdf_path),
        )
        con.commit()
    finally:
        con.close()


def add_citable(con, citekey, **overrides):
    ledger.upsert_reference(con, make_reference(citekey=citekey, **overrides))
    ledger.mark_parsed(con, citekey, parsed_file(citekey))


def plant_sidecar(citekey, records, *, docling=True) -> Path:
    directory = config.DOCLING_DIR if docling else config.PARSED_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{citekey}.passages.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def add_parsed_item(ledger_con, tmp_path, citekey, text, pdf_bytes=b"%PDF-1.4 dummy"):
    pdf = tmp_path / f"{citekey}.pdf"
    pdf.write_bytes(pdf_bytes)
    parsed = parsed_text(citekey, text)
    ledger.upsert_reference(ledger_con, make_reference(citekey=citekey, pdf_path=str(pdf)))
    ledger.mark_parsed(ledger_con, citekey, parsed)
    return parsed


def make_docs(tmp_path, texts: dict):
    from chitragupta.enrich.corpus import CorpusDoc

    docs = []
    for citekey, text in texts.items():
        path = tmp_path / f"{citekey}.txt"
        path.write_text(text, encoding="utf-8")
        docs.append(CorpusDoc(citekey=citekey, title=citekey, pdf_path=None, text_path=str(path)))
    return docs


def draft_with(body: str, tmp_path: Path) -> Path:
    path = tmp_path / "survey.md"
    path.write_text(body, encoding="utf-8")
    return path


def retrieval_cost(target):
    from chitragupta.dossier import _retrieval

    segments = _retrieval.retrieval_cost_by_revision(target)
    return sum(s.calls for s in segments), sum(s.chars for s in segments)


# Every thread pool a test hands the code must come from here or go through
# track(): shutdown(wait=False) cannot kill a thread, so an unjoined job
# outlives the test and writes into the real content/ (#1226).
class ThreadPools:
    def __init__(self) -> None:
        self._pools: list = []

    def __call__(self, workers: int):
        from concurrent.futures import ThreadPoolExecutor

        return self.track(ThreadPoolExecutor(max_workers=workers))

    def track(self, pool):
        self._pools.append(pool)
        return pool

    def join_all(self) -> None:
        first_error = None
        for pool in self._pools:
            try:
                pool.shutdown(wait=True, cancel_futures=True)
            except Exception as exc:  # noqa: BLE001 -- re-raised below
                first_error = first_error or exc
        if first_error is not None:
            raise first_error


@pytest.fixture
def thread_executor(monkeypatch):
    pools = ThreadPools()
    yield pools
    pools.join_all()


HOOKS = Path(__file__).resolve().parent.parent / ".claude" / "hooks"


def load_hook(name: str):
    import importlib.util

    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _book_spec_of(request) -> str:
    text = getattr(request.module, "BOOK_SPEC", None)
    if text is None:
        pytest.fail(f"{request.module.__name__} requests a book but defines no BOOK_SPEC outline")
    return text


@pytest.fixture
def book_dir(isolated_config):
    return isolated_config.DRAFTS_DIR / "twins"


def write_book_spec(book_path: Path, text: str) -> Path:
    from chitragupta import spec

    spec_file = spec.spec_path(book_path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(text, encoding="utf-8")
    book_path.mkdir(parents=True, exist_ok=True)
    return book_path


@pytest.fixture
def book(book_dir, request):
    return write_book_spec(book_dir, _book_spec_of(request))


@pytest.fixture
def example_ledger(ledger_con):
    add_citable(ledger_con, "smith_example_2024")
    return ledger_con


@pytest.fixture
def signed_book(book_dir, example_ledger, request):
    from chitragupta import spec

    write_book_spec(book_dir, _book_spec_of(request))
    spec.main(["sign", str(book_dir)])
    return book_dir


REPO_ROOT = Path(__file__).resolve().parent.parent


def _IS_COVERAGE_BOOTSTRAP(name: str) -> bool:
    return name.startswith("COV_CORE") or name in (
        "COVERAGE_PROCESS_START",
        "COVERAGE_FILE",
        "COVERAGE_RCFILE",
    )


def run_python(*argv, python=None, cwd=None, env=None, **kwargs):
    child_env = dict(os.environ if env is None else env)
    if Path(cwd or REPO_ROOT).resolve() != REPO_ROOT:
        child_env = {k: v for k, v in child_env.items() if not _IS_COVERAGE_BOOTSTRAP(k)}
    paths = [child_env.get("PYTHONPATH"), str(REPO_ROOT)]
    child_env["PYTHONPATH"] = os.pathsep.join(p for p in paths if p)
    return subprocess.run(
        [python or sys.executable, *argv],
        cwd=str(cwd or REPO_ROOT),
        env=child_env,
        capture_output=True,
        text=True,
        **kwargs,
    )


@pytest.fixture
def system_python():
    import subprocess

    candidates = []
    which_result = shutil.which("python3")
    if which_result:
        candidates.append(which_result)
    candidates += ["/usr/bin/python3", "/usr/local/bin/python3"]

    seen = set()
    for candidate in candidates:
        if candidate in seen or not Path(candidate).exists():
            continue
        seen.add(candidate)
        probe = subprocess.run(
            [candidate, "-c", "import bibtexparser"],
            capture_output=True,
        )
        if probe.returncode != 0:
            return candidate
    pytest.skip("no system python3 without bibtexparser found on this host")


@pytest.fixture
def programs_on_path(monkeypatch):
    monkeypatch.setattr(programs, "resolve_program", lambda name: f"/usr/bin/{name}")


pandoc_available = shutil.which("pandoc") is not None
pdflatex_available = shutil.which("pdflatex") is not None
lualatex_available = (
    shutil.which("lualatex") is not None
    and shutil.which("kpsewhich") is not None
    and subprocess.run(["kpsewhich", "luaotfload.sty"], capture_output=True, check=False).returncode
    == 0
)
tikz_available = (
    shutil.which("kpsewhich") is not None
    and subprocess.run(["kpsewhich", "tikz.sty"], capture_output=True, check=False).returncode == 0
)
pdftotext_available = shutil.which("pdftotext") is not None


def pdf_text(pdf) -> str:
    return subprocess.run(
        ["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout


def lualatex_book(directory) -> None:
    run = subprocess.run(
        ["lualatex", "-interaction=nonstopmode", "book.tex"],
        cwd=directory,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout[-3000:]


needs_tikz = pytest.mark.skipif(
    not (lualatex_available and tikz_available), reason="needs lualatex with tikz.sty"
)

ASCII_FIGURE = (
    "  +-------+  read   +--------+\n"
    "  | model | ------> | solver |\n"
    "  +-------+         +--------+\n"
)
TIKZ_FIGURE = "\\begin{tikzpicture}\\draw[blue] (0,0) circle (1);\\end{tikzpicture}\n"
MARKED_MD = "Before.\n\n<!-- figure: figures/fig1 -->\n\nAfter.\n"
MARKED_INPUT = "Before.\n\n\\input{figures/fig1.tex}\n%figure: figures/fig1\n\nAfter.\n"

CAPTIONED_MD = "Before.\n\n<!-- figure: figures/fig1 -->\nOne reading path.\n\nAfter.\n"


@pytest.fixture
def figures(tmp_path):
    directory = tmp_path / "drafts" / "topic" / "figures"
    directory.mkdir(parents=True)
    return directory


def figure_pair(draft_dir, name="fig1"):
    (draft_dir / "figures").mkdir(parents=True, exist_ok=True)
    (draft_dir / "figures" / f"{name}.tex").write_text(TIKZ_FIGURE)
    (draft_dir / "figures" / f"{name}.txt").write_text(ASCII_FIGURE)
    return draft_dir


WRITE_LOCK_HOLD = 0.5


def read_under_a_held_write_lock(read, hold=WRITE_LOCK_HOLD):
    import sqlite3
    import threading
    import time

    writer = sqlite3.connect(config.LEDGER_PATH, isolation_level=None)
    writer.execute("BEGIN EXCLUSIVE")
    entered = threading.Event()
    outcome = {}

    def run():
        entered.set()
        start = time.monotonic()
        try:
            outcome["result"] = read()
        except BaseException as exc:  # noqa: BLE001 -- re-raised by the caller
            outcome["error"] = exc
        outcome["waited"] = time.monotonic() - start

    reader = threading.Thread(target=run)
    try:
        reader.start()
        assert entered.wait(timeout=30)
        time.sleep(hold)
    finally:
        writer.execute("ROLLBACK")
        writer.close()
    reader.join(timeout=30)
    assert not reader.is_alive()
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"], outcome["waited"]


class FakePdfiumImage:
    def __init__(self, size, log):
        self.size = size
        self._log = log

    def save(self, path):
        Path(path).write_bytes(b"\x89PNG fake")

    def close(self):
        self._log.append("image.close")


class FakePdfiumBitmap:
    def __init__(self, size, log):
        self._size = size
        self._log = log

    def to_pil(self):
        return FakePdfiumImage(self._size, self._log)

    def close(self):
        self._log.append("bitmap.close")


class FakePdfiumPage:
    def __init__(self, index, log, size=(100.0, 100.0)):
        self._index = index
        self._log = log
        self._size = size

    def get_size(self):
        return self._size

    def render(self, scale=1.0, crop=(0, 0, 0, 0)):
        self._log.append(f"render page={self._index} scale={scale} crop={crop}")
        return FakePdfiumBitmap(
            (
                round((self._size[0] - crop[0] - crop[2]) * scale),
                round((self._size[1] - crop[1] - crop[3]) * scale),
            ),
            self._log,
        )

    def close(self):
        self._log.append(f"page.close page={self._index}")


class FakePdfiumDocument:
    def __init__(self, path, log, pages=8):
        self.path = path
        self._log = log
        self._pages = pages

    def __len__(self):
        return self._pages

    def __getitem__(self, index):
        self._log.append(f"page.open page={index}")
        return FakePdfiumPage(index, self._log)

    def close(self):
        self._log.append("pdf.close")


@pytest.fixture
def fake_pdfium(monkeypatch):
    import importlib.machinery
    import sys
    import types

    log: list[str] = []
    module = types.ModuleType("pypdfium2")
    module.PdfDocument = lambda path: FakePdfiumDocument(path, log)
    module.__spec__ = importlib.machinery.ModuleSpec("pypdfium2", loader=None)
    monkeypatch.setitem(sys.modules, "pypdfium2", module)
    return log


def fake(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path
