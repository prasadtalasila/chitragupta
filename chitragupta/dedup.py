"""Near-duplicate citekey detection: flags likely repeat imports of the
same paper under two different citekeys.

Advisory only: never blocks a sync or removes anything. A shared DOI is
near-certain, a shared title only a heuristic (a real blog post and
webinar shared one title), so a person decides.
"""

import re
from collections import defaultdict

from chitragupta.bib_reader import Reference


def _normalize_title(title: str) -> str:
    text = re.sub(r"[{}]", "", title).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    normalized = " ".join(text.split())
    # "Untitled" is bib_reader's placeholder; treated as empty, or every
    # untitled entry would be flagged as a duplicate of every other.
    return "" if normalized == "untitled" else normalized


def _normalize_doi(doi: str) -> str:
    # Prefixes stripped from a DOI field; http and https forms must compare
    # equal. Nothing is fetched.
    text = doi.strip().lower()
    text = re.sub(r"^https?://doi\.org/", "", text)
    return text.removeprefix("doi:")


def find_duplicates(references: list[Reference]) -> list[list[Reference]]:
    """Groups references that share a normalized DOI or normalized title,
    spanning 2+ distinct citekeys. Same-key duplicates never reach here:
    `bib_reader.read_library` drops and reports them (#840).
    """
    by_doi: dict[str, list[Reference]] = defaultdict(list)
    by_title: dict[str, list[Reference]] = defaultdict(list)
    for ref in references:
        if ref.doi:
            by_doi[_normalize_doi(ref.doi)].append(ref)
        if ref.title:
            normalized_title = _normalize_title(ref.title)
            if normalized_title:
                by_title[normalized_title].append(ref)

    seen_groups: set[frozenset[str]] = set()
    groups: list[list[Reference]] = []
    for bucket in (by_doi, by_title):
        for refs in bucket.values():
            distinct = {r.citekey: r for r in refs}
            if len(distinct) < 2:
                continue
            group_key = frozenset(distinct)
            if group_key in seen_groups:
                continue
            seen_groups.add(group_key)
            groups.append(list(distinct.values()))
    return groups
