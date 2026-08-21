import multiprocessing
import shutil
import subprocess
from pathlib import Path

import pytest



from chitragupta import config, ledger

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
        "RETRIEVAL_INDEX_PATH": "retrieval_index.json",
        "OVERLAP_DIR": "overlap",
        "VERBATIM_ALLOWLIST_PATH": "verbatim_allowlist.toml",
        "PIPELINE_LOCK_PATH": "pipeline.lock.db",
        "DOCLING_DIR": "docling",
        "DOCLING_CACHE_PATH": "docling_cache.json",
        "CHROMA_DIR": "chroma",
        "TOPICS_PATH": "topics.json",
        "TOPIC_EMBED_CACHE_PATH": "topic_embed_cache.json",
        "SEED_TOPICS_PATH": "seed_topics.toml",
        "TOPIC_SEEDS_PATH": "topic_seeds.json",
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
    monkeypatch.setattr(config, "DOCLING_IMAGES", False)
    monkeypatch.setattr(config, "DOCLING_IMAGE_SCALE", 2.0)
    # Pinned for the same reason: these decide which documents land under
    # a seed phrase and under a discovered topic, so a test asserting a
    # match would otherwise pass or fail on the developer's own
    # config.toml. The 0.5 floor is deliberately higher than the shipped
    # 0.15 so a test can place a vector below it without needing a
    # near-orthogonal pair to do it.
    monkeypatch.setattr(config, "SEED_TOPIC_MIN_SIMILARITY", 0.5)
    monkeypatch.setattr(config, "SEED_TOPIC_MAX_PAPERS", 25)
    # Pinned to the values the scaling-arithmetic tests assert against,
    # so a developer tuning topic depth in their own config.toml does not
    # fail a suite that is checking the clamps rather than the defaults.
    monkeypatch.setattr(config, "TOPIC_MIN_CLUSTER_SIZE", 3)
    monkeypatch.setattr(config, "TOPIC_MIN_SAMPLES", 2)
    monkeypatch.setattr(config, "TOPIC_NEIGHBORS", 10)
    monkeypatch.setattr(config, "TOPIC_DISTRIBUTION", True)
    monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_RATIO", 0.5)
    monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_MAX", 3)
    monkeypatch.setattr(config, "TOPIC_EXCLUDE_AUTHOR_NAMES", True)
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
    and subprocess.run(
        ["kpsewhich", "tikz.sty"], capture_output=True, check=False
    ).returncode == 0
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


def figure_pair(draft_dir, name="fig1"):
    """Both halves of a figure on disk, returning the draft's directory."""
    (draft_dir / "figures").mkdir(parents=True, exist_ok=True)
    (draft_dir / "figures" / f"{name}.tex").write_text(TIKZ_FIGURE)
    (draft_dir / "figures" / f"{name}.txt").write_text(ASCII_FIGURE)
    return draft_dir
