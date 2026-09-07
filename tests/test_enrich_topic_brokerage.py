"""chitragupta/enrich/topic_brokerage.py: stored brokerage (#713).

The property under test: the builder's networkx numbers and the
browser's egoStats arithmetic are the same numbers --
tests/webapp/brokerage_cases.json is the contract, asserted from node
by tests/webapp/ego.test.js and from here by this module.
"""

import json
from pathlib import Path

from chitragupta.enrich import topic_brokerage

CASES_PATH = Path(__file__).resolve().parent / "webapp" / "brokerage_cases.json"


def cases() -> list:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def test_every_shared_case_matches():
    rows = cases()
    assert len(rows) >= 3  # non-vacuity
    for row in rows:
        analysis = topic_brokerage.brokerage(
            row["labels"], row["edges"]["overlap"], row["edges"]["semantic"]
        )
        assert analysis[row["ego"]] == row["expected"], row["name"]


def test_every_topic_gets_both_families():
    rows = cases()[0]
    analysis = topic_brokerage.brokerage(
        rows["labels"], rows["edges"]["overlap"], rows["edges"]["semantic"]
    )
    for label in rows["labels"]:
        assert set(analysis[label]) == {"overlap", "semantic"}


def test_an_isolated_topic_reads_as_nothing_not_nan():
    analysis = topic_brokerage.brokerage(["loner"], [], [])
    assert analysis["loner"]["overlap"] == {
        "degree": 0,
        "ego_density": None,
        "effective_size": 0,
        "constraint": None,
    }
