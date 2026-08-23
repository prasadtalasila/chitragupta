"""Compares the three documented drop-in embedding models
(docs/CONFIG.md "Choosing an embedding model") against tier-3 overlap
detection's existing capability and recall harnesses.

Drives bench_overlap_embed.py and bench_paraphrase_hunt.py unmodified,
once per candidate model, via the EMBEDDING_MODEL environment variable
-- the same override every config.py setting already supports. Neither
script is touched: this is an orchestrator, not a fork.

SPECTER2 does not appear here. It cannot: the four graded-ladder rungs
this arm scores all restate the *same* paper's *same* claim at
different paraphrase distances, and a paper-level title+abstract vector
is identical across all four by construction -- there is nothing for it
to discriminate with. See the design spec's Arm A section.

    .venv-full/bin/python bench/bench_embed_model_compare.py \\
        --tag 2026-08-16-model-compare
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

# The three models docs/CONFIG.md documents as safe, symmetric drop-ins
# for embed_index.py's un-prefixed encode() call. Order matters only for
# the printed table, not for correctness -- code default first, then the
# two others in the order docs/CONFIG.md lists them.
CANDIDATES = (
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
    "sentence-transformers/multi-qa-mpnet-base-dot-v1",
)

DRAFTS_DIR = "content/drafts/books/digital-twins-for-software-engineers"

# The already-labelled ground truth bench_paraphrase_hunt.py's
# 2026-08-15 run produced. Copied per model into that model's own tagged
# results directory before --crosscheck runs, since crosscheck() writes
# tiers back into whatever labels.json its --tag resolves to -- reusing
# one shared file across three models would have each overwrite the last.
ORGANIC_LABELS = BENCH_DIR / "results" / "2026-08-15-organic-paraphrase-hunt" / "labels.json"


def model_slug(model):
    return model.rsplit("/", maxsplit=1)[-1]


def self_check():
    """CANDIDATES really are the three docs/CONFIG.md documents, and the
    organic ground truth this arm depends on is really on disk.

    Without this, a typo'd model string would run a real (expensive)
    embed against a model nobody meant to benchmark, and a missing
    ORGANIC_LABELS would fail deep inside a subprocess call with a
    message that does not say why.
    """
    assert len(CANDIDATES) == 3, f"expected 3 candidates, got {len(CANDIDATES)}"
    assert "all-MiniLM-L6-v2" in CANDIDATES[0], "code default should be listed first"
    assert len(set(CANDIDATES)) == 3, "a candidate is listed twice"
    assert ORGANIC_LABELS.exists(), (
        f"no {ORGANIC_LABELS} -- run bench_paraphrase_hunt.py --extract/--crosscheck "
        "first, or restore it from git"
    )


def _venv_python():
    """Path to the `enrich` Poetry group interpreter (chromadb,
    sentence-transformers, torch).

    Prefers this checkout's own `.venv-full`, matching every other bench
    script's documented `.venv-full/bin/python bench/...` invocation. On
    this host, though, a freshly created worktree does not carry its own
    multi-GB venv -- `.venv-full` lives once, in the checkout the
    worktree branched from -- so this falls back to that checkout,
    located the same way git itself finds it (`--git-common-dir`), rather
    than a hardcoded sibling path that would break on a different host
    layout."""
    local = REPO / ".venv-full" / "bin" / "python"
    if local.exists():
        return str(local)
    common_dir = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    shared = (REPO / common_dir).resolve().parent / ".venv-full" / "bin" / "python"
    if shared.exists():
        return str(shared)
    raise RuntimeError(
        f"no .venv-full/bin/python at {local} or {shared} -- "
        "run `poetry install --with enrich` in one of those checkouts"
    )


def _run(cmd, env_extra=None):
    """One subprocess call, with EMBEDDING_MODEL (or nothing) layered
    onto this process's own environment -- never a bare os.environ
    replacement, which would drop PATH and silently break every
    .venv-full/bin/python call downstream of it."""
    import os

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"{' '.join(cmd)} exited {result.returncode}")
    return result


def run_model(model, tag, out_dir):
    """Builds `model`'s Chroma collection if it isn't already current,
    scans the fixture and the real book with it, and cross-checks
    against the organic ground truth. Returns the three JSON payloads
    this model produced.

    Each step shells out to the real command a human would run --
    bench_overlap_embed.py and bench_paraphrase_hunt.py are never
    imported, only invoked -- so this script measures exactly what
    `bench/README.md` tells a person to run, not an approximation of it.
    """
    slug = model_slug(model)
    py = _venv_python()
    env = {"EMBEDDING_MODEL": model}

    # DRAFTS_DIR is relative ("content/drafts/books/..."), and
    # bench_overlap_embed.py/bench_paraphrase_hunt.py resolve --drafts as
    # a literal filesystem path, not through config.py -- so it only
    # finds the real restored book when made absolute against
    # config.CONTENT_DIR (config.toml's `[content] dir`, per-host and
    # possibly outside this checkout), not against this checkout's own
    # (mostly empty) content/ directory.
    from chitragupta import config  # noqa: PLC0415 -- deferred so self_check() alone stays import-light

    drafts_dir = str(config.CONTENT_DIR.parent / DRAFTS_DIR)

    print(f"\n=== {model} ===", flush=True)
    print("  building/confirming the Chroma collection ...", flush=True)
    _run([py, "-m", "chitragupta.enrich", "--stages", "embed"], env_extra=env)

    model_tag = f"{tag}-{slug}"
    print("  running the capability + precision arms ...", flush=True)
    _run(
        [
            py,
            "bench/bench_overlap_embed.py",
            "--fixture",
            "--drafts",
            drafts_dir,
            "--tag",
            model_tag,
        ],
        env_extra=env,
    )

    model_out = BENCH_DIR / "results" / model_tag
    capability = json.loads((model_out / "embed_capability.json").read_text(encoding="utf-8"))
    precision = json.loads((model_out / "embed_precision.json").read_text(encoding="utf-8"))

    organic_tag = f"{model_tag}-organic"
    organic_out = BENCH_DIR / "results" / organic_tag
    organic_out.mkdir(parents=True, exist_ok=True)
    organic_labels_copy = organic_out / "labels.json"
    organic_labels_copy.write_text(ORGANIC_LABELS.read_text(encoding="utf-8"), encoding="utf-8")

    print("  cross-checking against the 22 organic close-paraphrase pairs ...", flush=True)
    _run(
        [
            py,
            "bench/bench_paraphrase_hunt.py",
            "--crosscheck",
            "--drafts",
            drafts_dir,
            "--tag",
            organic_tag,
            "--embed-record",
            str(model_out / "embed_precision.json"),
        ]
    )

    organic = json.loads(organic_labels_copy.read_text(encoding="utf-8"))
    caught_by_embedding = sum(
        1
        for row in organic["candidates"]
        if row["judgment"] == "paraphrase" and "embedding" in row["tiers"]
    )
    total_paraphrase = sum(1 for row in organic["candidates"] if row["judgment"] == "paraphrase")

    return {
        "model": model,
        "grades_caught": {row["grade"]: row["tiers"] for row in capability["grades"]},
        "embedding_findings": precision["embedding_findings"],
        "organic_recall": f"{caught_by_embedding}/{total_paraphrase}",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--tag",
        required=True,
        help="names bench/results/<tag>/ for this run's comparison table "
        "(per-model results also land under bench/results/<tag>-<model-slug>/)",
    )
    args = ap.parse_args(argv)

    self_check()
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = [run_model(model, args.tag, out_dir) for model in CANDIDATES]

    print(f"\n{'model':40}  {'embedding findings':>19}  organic recall  grades caught")
    for row in rows:
        caught = sum(1 for tiers in row["grades_caught"].values() if tiers)
        print(
            f"{row['model']:40}  {row['embedding_findings']:>19}  "
            f"{row['organic_recall']:>14}  {caught}/4"
        )

    record = out_dir / "comparison.json"
    record.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nRecord: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
