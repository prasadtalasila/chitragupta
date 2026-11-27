import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = REPO_ROOT / "tests" / "webapp" / "hypergeometric_cases.js"


def cases() -> list:
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
    assert len(cases()) >= 10


def test_every_case_still_matches_scipy():
    hypergeom = pytest.importorskip("scipy.stats").hypergeom
    for case in cases():
        expected = float(hypergeom.sf(case["k"] - 1, case["docs"], case["a"], case["b"]))
        assert case["p"] == pytest.approx(expected, rel=1e-12), case


def test_the_table_covers_the_gate_s_own_extremes():
    ps = [case["p"] for case in cases()]
    assert max(ps) == 1
    assert min(ps) < 1e-10


def test_the_stage_and_the_table_agree_on_a_real_pair():
    pytest.importorskip("scipy.stats")
    from chitragupta.enrich import topic_graph

    members = {"digital twin": {"dt2021", "dt2022"}, "machine learning": {"dt2022", "ml1", "ml2"}}
    assert topic_graph.overlap_edges(members, n_docs=4, p_value=0.01) == []
    assert any(c["k"] == 1 and c["docs"] == 4 and c["p"] == 1 for c in cases())
