import json
import multiprocessing
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


from chitragupta import config, ledger
from tests import content_guard


def pytest_sessionstart(session):
    """Keep spawned children importable for the whole session.

    A dependency imported by one test can leave a sys.path entry that
    shadows the standard library for every `spawn` child created
    afterwards -- see pdf_text.drop_stdlib_shadowing_path_entries. The
    production path sanitises before building a pool; the cross-process
    tests in tests/test_runlock.py spawn directly, so the session does it
    once here as well.
    """
    from chitragupta import pdf_text

    pdf_text.drop_stdlib_shadowing_path_entries()
    content_guard.record(session, config.CONTENT_DIR)


def pytest_sessionfinish(session):
    """Fail a session that wrote into the real content/ -- see
    tests/content_guard.py for why the effect is checked, not the code."""
    content_guard.verify(session)


@pytest.fixture(autouse=True)
def _pin_parser_settings(monkeypatch):
    """Pin the parser settings the suite assumes, instead of inheriting
    whatever this developer happens to have in config.toml.

    Since v1.0.0 config.toml is gitignored per-host data, so every
    developer's differs -- and `chitragupta.config` reads it at import time.
    Without this, a checkout with `backend = "docling"` fails nine tests
    that assert on pdftotext's messages, for no reason connected to the
    code under test. That is a confusing failure to hand someone, and it
    is CI-invisible: CI copies the unedited example, so it never sees it.

    Tests that care about a different backend monkeypatch these
    afterwards -- monkeypatch is last-write-wins within a test.
    """
    monkeypatch.setattr(config, "PARSER", "pdftotext")
    monkeypatch.setattr(config, "PARSER_OCR", False)
    # Pinned for the same reason as PARSER_OCR above, and it was missed
    # when [parser].formulas arrived in #651: without it, a test that
    # asserts the *default* is off passes or fails according to whether
    # the host running it happens to have turned the key on in its own
    # config.toml. CI copies config.toml.example and so never saw it.
    monkeypatch.setattr(config, "PARSER_FORMULAS", False)
    monkeypatch.setattr(config, "PARSER_WORKERS", 1)


@pytest.fixture(autouse=True)
def _no_real_forkserver(monkeypatch):
    """Keep the suite from launching an actual forkserver process.

    `sync.run()` calls `pdf_text.prestart_pool()` before reading the
    bibliography, and any test that drives `run()` with the docling
    backend and more than one worker reaches it for real -- measured, 22
    times in tests/test_sync.py alone. Each one spawns a process whose
    whole job is to import torch and docling: hundreds of megabytes and
    seconds of CPU, in a unit-test suite that mocks docling precisely so
    it never has to pay that.

    Neutralised at `ensure_running` rather than at `prestart_pool`, so
    the decision logic under test still runs -- only the process launch
    is stubbed. The tests that assert *on* that launch patch this same
    name afterwards and read their own recorder; monkeypatch is
    last-write-wins within a test.

    Guarded because Windows has no forkserver module path worth
    importing -- there, `start_method()` resolves to spawn and
    `prestart_pool` returns before it would ever be reached.
    """
    if "forkserver" not in multiprocessing.get_all_start_methods():
        return
    from multiprocessing import forkserver

    monkeypatch.setattr(forkserver, "ensure_running", lambda: None)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point every chitragupta.config path constant at a throwaway tmp_path tree.

    chitragupta.config computes these once at import time as plain Path objects,
    not functions, and every consumer module does `from chitragupta import
    config` then reads `config.SOME_PATH` at call time -- so patching
    attributes on this one shared module object is visible everywhere,
    no importlib.reload needed. Each derived path (e.g. PARSED_DIR from
    CONTENT_DIR) is set independently here, since config.py itself only
    derives them once at import time -- patching just the parent
    wouldn't move an already-computed child.
    """
    content_dir = tmp_path / "content"

    # A table rather than a run of setattr calls, so that adding a path
    # to config.py costs one line here instead of pushing this fixture
    # past docs/CODE-STANDARDS.md's 25-statement limit -- which is what
    # happened when the seed-topic paths arrived. The relative names are
    # exactly what config.py derives from CONTENT_DIR, kept in the same
    # spelling so the two are diffable by eye.
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
    # Pinned rather than inherited from config.toml: DOCLING_IMAGES
    # participates in the Docling cache key, so a test asserting a
    # cache hit would otherwise pass or fail based on the repo's
    # current setting. Tests that care set it explicitly.
    # A table for the same statement-budget reason as `under_content`
    # above: all three participate in the Docling cache key, so a
    # cache-hit assertion must not depend on the repo's current setting.
    for name, value in {
        "DOCLING_IMAGES": False,
        "DOCLING_IMAGE_SCALE": 2.0,
        "DOCLING_FORMULAS": False,
    }.items():
        monkeypatch.setattr(config, name, value)
    # Pinned for the same reason: these decide which documents land under
    # a seed phrase and under a discovered topic, so a test asserting a
    # match would otherwise pass or fail on the developer's own
    # config.toml. The 0.5 floor is deliberately higher than the shipped
    # 0.15 so a test can place a vector below it without needing a
    # near-orthogonal pair to do it.
    monkeypatch.setattr(config, "SEED_TOPIC_MIN_SIMILARITY", 0.5)
    monkeypatch.setattr(config, "SEED_TOPIC_MAX_PAPERS", 25)
    # Pinned for the same reason as the two above: these decide which
    # extracted phrases reach content/keywords.toml, so a test asserting
    # the min-df or top-n arithmetic must not inherit a developer's own
    # config.toml tuning.
    monkeypatch.setattr(config, "KEYWORD_TOP_N", 40)
    monkeypatch.setattr(config, "KEYWORD_MIN_DF", 2)
    # Pinned so a developer's own config.toml can't change how many
    # chunks embed_index.search() admits per citekey out from under a
    # test that is asserting the cap's arithmetic, not its default.
    monkeypatch.setattr(config, "EMBED_MAX_PASSAGES_PER_SOURCE", 3)
    # Pinned to the values the scaling-arithmetic tests assert against,
    # so a developer tuning topic depth in their own config.toml does not
    # fail a suite that is checking the clamps rather than the defaults.
    monkeypatch.setattr(config, "TOPIC_MIN_CLUSTER_SIZE", 3)
    monkeypatch.setattr(config, "TOPIC_MIN_SAMPLES", 2)
    monkeypatch.setattr(config, "TOPIC_NEIGHBORS", 5)
    monkeypatch.setattr(config, "TOPIC_DISTRIBUTION", True)
    monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_RATIO", 0.5)
    monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_MAX", 8)
    monkeypatch.setattr(config, "TOPIC_EXCLUDE_AUTHOR_NAMES", True)
    monkeypatch.setattr(config, "TOPIC_CONVERGE_SIMILARITY", 0.45)
    # Pinned to the shipped defaults so a developer's own config.toml
    # can't change whether a fixed input text's score clears the "good"
    # band -- these two are read as incidental pass/fail scaffolding by
    # tests that are asserting claim-splitting logic, not the threshold.
    monkeypatch.setattr(config, "PROVENANCE_WEAK_SCORE", 0.20)
    monkeypatch.setattr(config, "PROVENANCE_GOOD_SCORE", 0.50)
    return config


@pytest.fixture
def ledger_con(isolated_config):
    con = ledger.connect()
    yield con
    con.close()


def content_draft(cfg, name: str) -> Path:
    """A draft path a tier-1 tool will accept: under `cfg.CONTENT_DIR`.

    Since 3.17.0 `citation_gate`, `references` and `render_output` all
    refuse a path that resolves outside the content directory, so a test
    draft has to live under one. Creates the parent, which
    `isolated_config` names but does not make.
    """
    path = cfg.CONTENT_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def parsed_text(citekey: str, text: str) -> Path:
    """Parsed text where a real parse puts it: `content/parsed/<citekey>.txt`.

    Since issue 821 every consumer refuses a ledger `parsed_path` that
    lands outside `config.PARSED_DIR`, so a fixture dropping the text
    in a bare `tmp_path` and pointing the row at it is no longer
    testing the shape a row actually has -- it is testing the one the
    pipeline now declines to read. Creates the directory, which
    `isolated_config` names but does not make.
    """
    path = parsed_file(citekey)
    path.write_text(text, encoding="utf-8")
    return path


def parsed_file(citekey: str) -> Path:
    """`content/parsed/<citekey>.txt`, with the directory made.

    The location half of `parsed_text` above, for a fixture that writes
    the file itself (or writes it twice, to prove a re-index).
    """
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    return config.PARSED_DIR / f"{citekey}.txt"


def real_bibliography_path() -> Path:
    """This repo's actual, gitignored `papers/bibliography.bib` -- real
    per-host data, for the one test class that deliberately smoke-tests
    against a maintainer's real export rather than a synthetic fixture
    (`TestRealBibliographySmoke`). Centralised here, rather than as a
    literal in each test, so `tests/test_unversioned_data_scan.py`'s scan
    for un-versioned-data reads can tell a named, documented accessor from
    a bare inline one -- the difference the scan actually cares about,
    per its own module docstring.
    """
    return config.PROJECT_ROOT / "papers" / "bibliography.bib"


def make_reference(citekey="smith_example_2024", **overrides):
    """A minimal chitragupta.bib_reader.Reference, for tests that don't need a
    real .bib file on disk."""
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
    """A `parsed` ledger row, optionally with its text on disk where a
    real parse puts it. One helper rather than the four module copies it
    replaced (#867), which differed only in whether they accepted a
    `pdf_path`; taking it always and storing NULL by default covers all
    four."""
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


def plant_sidecar(citekey, records, *, docling=True) -> Path:
    """A structural passage sidecar, `<citekey>.passages.json`, holding
    `records` as written.

    Rung 1 of chitragupta/passages.py's ladder (the Docling directory)
    by default, which is where three of the four copies this replaced
    wrote; `docling=False` is rung 2, beside the parsed text.
    """
    directory = config.DOCLING_DIR if docling else config.PARSED_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{citekey}.passages.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def add_parsed_item(ledger_con, tmp_path, citekey, text, pdf_bytes=b"%PDF-1.4 dummy"):
    """A ledger row with status='parsed', a real pdf_hash (from a
    throwaway PDF file, so upsert_reference actually computes one), and
    parsed_path pointing at real text on disk."""
    pdf = tmp_path / f"{citekey}.pdf"
    pdf.write_bytes(pdf_bytes)
    parsed = parsed_text(citekey, text)
    ledger.upsert_reference(ledger_con, make_reference(citekey=citekey, pdf_path=str(pdf)))
    ledger.mark_parsed(ledger_con, citekey, parsed)
    return parsed


def make_docs(tmp_path, texts: dict):
    """One CorpusDoc per `citekey -> text`, each text on disk under
    tmp_path: the enrichment corpus with no ledger behind it."""
    from chitragupta.enrich.corpus import CorpusDoc

    docs = []
    for citekey, text in texts.items():
        path = tmp_path / f"{citekey}.txt"
        path.write_text(text, encoding="utf-8")
        docs.append(CorpusDoc(citekey=citekey, title=citekey, pdf_path=None, text_path=str(path)))
    return docs


def draft_with(body: str, tmp_path: Path) -> Path:
    """`body` as `tmp_path/survey.md`, for the style checks, which read a
    draft from anywhere."""
    path = tmp_path / "survey.md"
    path.write_text(body, encoding="utf-8")
    return path


def retrieval_cost(target):
    """(calls, chars) over a whole `retrieval.md`, as the sum of its
    per-revision segments.

    `dossier.retrieval_cost` used to answer this directly and was deleted
    in #515: `_status` computes the lifetime figures this same way, and a
    second whole-file reader was surface nothing production called. These
    cases are about `log_retrieval`'s row format -- pipe escaping, a
    hand-edited row, a file created before `init` -- so they need *a*
    reader, and using the one production uses is the point.
    """
    from chitragupta.dossier import _retrieval

    segments = _retrieval.retrieval_cost_by_revision(target)
    return sum(s.calls for s in segments), sum(s.chars for s in segments)


def thread_executor(workers):
    """A real ProcessPoolExecutor would run parse_one in a child
    interpreter, where this process's sys.modules fakes don't exist -- the
    fake docling would silently not be used. Swapping the executor keeps
    the concurrency real while leaving the fakes visible."""
    from concurrent.futures import ThreadPoolExecutor

    return ThreadPoolExecutor(max_workers=workers)


HOOKS = Path(__file__).resolve().parent.parent / ".claude" / "hooks"


def load_hook(name: str):
    """A fresh module object for `.claude/hooks/<name>.py`, so one test's
    monkeypatching cannot leak.

    `.claude/hooks` goes on `sys.path` first because a hook is run by
    absolute path in production, which puts its own directory there --
    that is what makes `import draft_target` resolve with no path
    manipulation inside the hook. Loading by spec does not reproduce it,
    so the test harness has to.
    """
    import importlib.util

    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Books: the three shapes the book-track tests start from --------------
# A bare path, a path with its outline written, and that outline signed.
# The outline text is each module's own -- the chapters under test differ
# -- so `book` reads it from the requesting module's BOOK_SPEC rather than
# taking it as an argument a fixture cannot be given.


def _book_spec_of(request) -> str:
    """The requesting module's BOOK_SPEC, or a refusal that says so
    rather than an AttributeError on a module object."""
    text = getattr(request.module, "BOOK_SPEC", None)
    if text is None:
        pytest.fail(f"{request.module.__name__} requests a book but defines no BOOK_SPEC outline")
    return text


@pytest.fixture
def book_dir(isolated_config):
    """content/drafts/twins, not created: an outline is written before
    any prose, so a test of the outline starts from nothing."""
    return isolated_config.DRAFTS_DIR / "twins"


def write_book_spec(book_path: Path, text: str) -> Path:
    """`text` as `book_path`'s outline, with the book directory made."""
    from chitragupta import spec

    spec_file = spec.spec_path(book_path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(text, encoding="utf-8")
    book_path.mkdir(parents=True, exist_ok=True)
    return book_path


@pytest.fixture
def book(book_dir, request):
    """`book_dir` with the module's BOOK_SPEC written as its outline."""
    return write_book_spec(book_dir, _book_spec_of(request))


@pytest.fixture
def example_ledger(ledger_con):
    """A ledger holding the one reference the book tests' outlines and
    drafts cite, so a unit citing it can be accepted."""
    ledger.upsert_reference(ledger_con, make_reference(citekey="smith_example_2024"))
    ledger_con.commit()
    return ledger_con


@pytest.fixture
def signed_book(book_dir, example_ledger, request):
    """The module's BOOK_SPEC outline, signed, over `example_ledger`, so a
    unit can be accepted against it.

    Built from `book_dir` rather than from `book`: a module that renames
    this fixture to `book` for its own tests would otherwise make it
    request itself.
    """
    from chitragupta import spec

    write_book_spec(book_dir, _book_spec_of(request))
    spec.main(["sign", str(book_dir)])
    return book_dir


REPO_ROOT = Path(__file__).resolve().parent.parent


def _IS_COVERAGE_BOOTSTRAP(name: str) -> bool:
    """Whether an env var would make a child process start its own coverage.

    `run_python` strips these from any child it starts outside the
    repository root, and the hook tests strip them from the hook's
    environment, for the same reason. The hook runs
    `python -m chitragupta.draft gate` with `cwd` set to *its* repo root --
    a temporary one in those tests. Coverage started there finds no
    config file, so it records statement-only data while the parent
    records branch data, and the run dies at combine time with
    "Can't combine statement coverage data with branch data" *after*
    every test has passed.

    Whether it happens at all depends on the pytest-cov version and on
    what `python` resolves to: pytest-cov 6.x ships a `.pth` that
    instruments every subprocess, 7.x does not, and the hook spawns a
    literal `python` rather than `sys.executable`, so a venv on PATH
    (what `poetry run` gives CI) is instrumented while a bare system
    interpreter is not. Stripping these makes every combination behave
    the same. Nothing is lost: the in-process tests already cover
    `chitragupta/citation_gate.py` fully, which is why the total is 100% on a
    host where these children were never measured.
    """
    return name.startswith("COV_CORE") or name in (
        "COVERAGE_PROCESS_START",
        "COVERAGE_FILE",
        "COVERAGE_RCFILE",
    )


def run_python(*argv, python=None, cwd=None, env=None, **kwargs):
    """`python *argv` in a child process, with this checkout's
    chitragupta importable whatever the child's cwd (#867).

    Every launch of the package under test goes through here, which
    `tests/test_subprocess_launch_scan.py` holds to. Before, each launch
    imported whichever chitragupta the child found first: a `-m` child
    finds this one only because its cwd is the repository root and `-m`
    puts the cwd on sys.path, which stops being true the moment a test
    passes `cwd=tmp_path`.

    The checkout is *appended* to the caller's PYTHONPATH, never
    prepended, so a test that deliberately imports another copy of the
    package (tests/test_tokens.py edits one under tmp_path) still gets
    it. `env`, when given, is the child's whole environment, exactly as
    the caller wrote it: the `system_python` tests pass a minimal one on
    purpose. cwd stays the repository root by default because that is
    where the child finds this checkout's config.toml.

    Anywhere else, coverage's bootstrap variables are dropped: a child
    started from a cwd with no pyproject.toml measures statement-only and
    the session dies at combine time, after every test has passed (see
    `_IS_COVERAGE_BOOTSTRAP`). From the root the child is still measured.
    """
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
    """A python3 that can't import bibtexparser, to verify the documented
    invariant (AGENTS.md) that citation_gate.py/references.py/
    render_output.py run with the bare system interpreter, no venv
    required. A venv's python is typically just a symlink to the same
    system binary (`file` on it resolves identically to /usr/bin/python3),
    so comparing resolved paths can't tell them apart -- what actually
    differs is which pyvenv.cfg (if any) gets picked up based on the
    *invoked* path, which in turn determines whether bibtexparser is on
    sys.path. So check that directly instead.
    """
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


# --- Rendering: binary probes and figure fixtures -------------------------
# Shared by the eight tests/test_render_output*.py modules. Here rather
# than in each of them so the kpsewhich subprocess below runs once per
# session instead of eight times at import.
pandoc_available = shutil.which("pandoc") is not None
pdflatex_available = shutil.which("pdflatex") is not None
# tikz.sty is texlive-pictures (#222), a separate package from the ones
# scripts/install_full_pipeline.sh already installed for lmodern etc. --
# pdflatex being on PATH doesn't guarantee it, so this is its own probe
# rather than folded into pdflatex_available.
tikz_available = (
    shutil.which("kpsewhich") is not None
    and subprocess.run(["kpsewhich", "tikz.sty"], capture_output=True, check=False).returncode == 0
)
# poppler-utils, which `scripts/install_full_pipeline.sh os-deps` installs
# beside TeX Live but which is a different package from it. Its own probe
# for that reason, like tikz above: the one test that reads it measures
# where a caption actually wrapped on the page, which is a question no
# assertion over the `.tex` can answer.
pdftotext_available = shutil.which("pdftotext") is not None
# Whether this host can compile a TikZ figure at all: the two facts
# `render_output/_figures.py::_require_tikz()` checks. A skip, not a
# failure, because CI's Windows leg installs no `os-deps`. One marker for
# the three geometry modules that each used to probe for it themselves.
needs_tikz = pytest.mark.skipif(
    not (pdflatex_available and tikz_available), reason="needs pdflatex with tikz.sty"
)

# A figure is two forms -- a TikZ picture and the same diagram in
# WRITING-STANDARDS.md §10's plain ASCII -- and both are always files.
# A Markdown draft carries only the marker; a `.tex` draft keeps its TikZ
# inline (the fragment a real thesis `\input`s) and names its ASCII twin
# in a marker of its own. These are the two shapes that produces.
ASCII_FIGURE = (
    "  +-------+  read   +--------+\n"
    "  | model | ------> | solver |\n"
    "  +-------+         +--------+\n"
)
TIKZ_FIGURE = "\\begin{tikzpicture}\\draw[blue] (0,0) circle (1);\\end{tikzpicture}\n"
MARKED_MD = "Before.\n\n<!-- figure: figures/fig1 -->\n\nAfter.\n"
MARKED_INPUT = "Before.\n\n\\input{figures/fig1.tex}\n%figure: figures/fig1\n\nAfter.\n"

# Issue 411: a figure marker with its caption directly below it, no blank
# line between -- the adjacency that makes it a *captioned* figure, with a
# number and a `\ref`-able id, rather than the uncaptioned case above.
CAPTIONED_MD = "Before.\n\n<!-- figure: figures/fig1 -->\nOne reading path.\n\nAfter.\n"


def figure_pair(draft_dir, name="fig1"):
    """Both halves of a figure on disk, returning the draft's directory."""
    (draft_dir / "figures").mkdir(parents=True, exist_ok=True)
    (draft_dir / "figures" / f"{name}.tex").write_text(TIKZ_FIGURE)
    (draft_dir / "figures" / f"{name}.txt").write_text(ASCII_FIGURE)
    return draft_dir


# How long `read_under_a_held_write_lock` holds the ledger's EXCLUSIVE
# lock. Comfortably inside sqlite's 5s default busy timeout, so a reader
# that waits recovers with room to spare, and long enough that half of it
# is an unambiguous "this call blocked" on a loaded CI runner.
WRITE_LOCK_HOLD = 0.5


def read_under_a_held_write_lock(read, hold=WRITE_LOCK_HOLD):
    """Run `read` while another connection holds the ledger's EXCLUSIVE
    lock, release it after `hold` seconds, and return `(result, waited)`.

    Shared by every read-only ledger path that has to survive a writer's
    commit window -- `ledger_cli.main` (m-72), `dossier._corpus_rows` and
    `overlap_index_ledger._ledger_connect_ro` (issue #552). One helper
    rather than a copy of this thread dance in each of the three test
    modules, which is the duplication `docs/CODE-STANDARDS.md` calls the
    highest-value thing to catch.

    A real held lock rather than an assertion about the `timeout`
    argument, because the argument is not the claim; surviving the window
    is. The ledger has no `journal_mode = WAL`, so under the default
    rollback journal a reader really is locked out for the length of a
    commit.

    `waited` is what makes the returned result mean anything. A reader
    that did not reach its query until after the rollback would succeed
    without ever meeting a lock, and so would pass against the very
    `timeout=0` these tests exist to reject; it cannot have returned
    before the lock was released, so a call that took an appreciable
    fraction of `hold` is one that blocked and recovered. The reader
    signals just before it starts for the same reason.

    Anything `read` raises is re-raised here rather than swallowed, so
    the `timeout=0` case fails as the `sqlite3.OperationalError: database
    is locked` it actually is instead of as a missing dict key.
    """
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
        # `BaseException`, not `Exception`, and not swallowed either way:
        # anything that escapes here would kill the thread with `outcome`
        # half-filled, and the caller would then fail on a missing dict
        # key rather than on the real cause. `read()` is a CLI `main()`
        # in one of the three callers, so `SystemExit` is not far-fetched.
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
    """The PIL view `to_pil()` hands back, plus the `close()` that
    releases pdfium's buffer behind it."""

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
    """A recording pypdfium2 in `sys.modules`, yielding its call log.

    Faked rather than real for the same reason docling is: `_docling_crops`
    imports it lazily so the enrich extra stays optional, and a unit test
    must not need a real PDF on disk to render from.

    The log is the point. What `_docling_crops` has to get right is *when
    things are released* -- a version that produced every crop correctly
    and freed none of them would satisfy any output-only assertion while
    reproducing the bug it exists to fix (#600). Ordering is only
    checkable against a record of the calls.

    `test_enrich_real_libraries.py` pins the same surface against the
    pypdfium2 CI installs, so this cannot drift from the library
    unnoticed.
    """
    import importlib.machinery
    import sys
    import types

    log: list[str] = []
    module = types.ModuleType("pypdfium2")
    module.PdfDocument = lambda path: FakePdfiumDocument(path, log)
    module.__spec__ = importlib.machinery.ModuleSpec("pypdfium2", loader=None)
    monkeypatch.setitem(sys.modules, "pypdfium2", module)
    return log
