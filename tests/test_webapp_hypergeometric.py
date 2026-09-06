"""The one number the browser recomputes, pinned from the Python side.

`assets/webapp/absence.js` explains a *withheld* overlap edge -- two
topics that share a paper with no edge between them -- by recomputing
the same hypergeometric tail `enrich/topic_graph.py` used to withhold
it. Two runtimes, one arithmetic: a browser-side p-value that disagreed
with the stage that drew the edges would be worse than showing none.

`tests/webapp/hypergeometric_cases.js` is the contract between them. It
is data, not code: this module asserts every row still matches scipy,
and the node suite asserts the JavaScript matches the same rows. Neither
side can drift without one of the two suites saying so, and neither
suite needs the other's runtime installed.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = REPO_ROOT / "tests" / "webapp" / "hypergeometric_cases.js"


def cases() -> list:
    """The rows of the shared table, read out of the JavaScript file.

    A regex rather than a JS parser: the file is written by hand in one
    fixed shape, and the non-vacuity assertion below is what stops a
    silently-empty match from making every test here pass.
    """
    text = CASES_PATH.read_text(encoding="utf-8")
    rows = re.findall(
        r"\{\s*k:\s*([\d.]+),\s*docs:\s*([\d.]+),\s*a:\s*([\d.]+),"
        r"\s*b:\s*([\d.]+),\s*p:\s*([\d.eE+-]+)\s*\}",
        text,
    )
    return [
        {"k": int(k), "docs": int(docs), "a": int(a), "b": int(b), "p": float(p)}
        for k, docs, a, b, p in rows
    ]


def test_the_table_is_read_at_all():
    """Non-vacuity: a regex that matched nothing would make every
    assertion below pass over an empty list."""
    assert len(cases()) >= 10


def test_every_case_still_matches_scipy():
    hypergeom = pytest.importorskip("scipy.stats").hypergeom
    for case in cases():
        expected = float(hypergeom.sf(case["k"] - 1, case["docs"], case["a"], case["b"]))
        assert case["p"] == pytest.approx(expected, rel=1e-12), case


def test_the_table_covers_the_gate_s_own_extremes():
    """The two readings the feature exists to tell apart: an overlap
    that is exactly what chance predicts (p = 1), and one that could not
    plausibly be chance."""
    ps = [case["p"] for case in cases()]
    assert max(ps) == 1
    assert min(ps) < 1e-10


def test_the_stage_and_the_table_agree_on_a_real_pair():
    """Not the tail alone: the same call the stage makes, through the
    stage's own function, on the corpus sizes from its documented worked
    example (two topics of size 2 and 3 sharing one paper in a 4-paper
    corpus -- p = 1.0, and the edge is withheld)."""
    pytest.importorskip("scipy.stats")
    from chitragupta.enrich import topic_graph

    members = {"digital twin": {"dt2021", "dt2022"}, "machine learning": {"dt2022", "ml1", "ml2"}}
    assert topic_graph.overlap_edges(members, n_docs=4, p_value=0.01) == []
    assert any(c["k"] == 1 and c["docs"] == 4 and c["p"] == 1 for c in cases())
