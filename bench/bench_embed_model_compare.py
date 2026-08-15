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


if __name__ == "__main__":
    self_check()
    print("self_check() passed")
