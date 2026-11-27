"""`overlap` and `locate`: the two CLI modes nothing else shares."""

import re
from pathlib import Path

from chitragupta import overlap_index
from chitragupta.review.verbatim_check._corpus import norm, pages, sentences_citing


def _gram_hit_runs(draft_hashes: list[int], grams: dict[int, int]) -> list[list[tuple[int, int]]]:
    """Consecutive-index runs of `draft_hashes` entries present in `grams`,
    as `[(index, posting), ...]` runs -- broken wherever a hash is absent.
    """
    run: list[tuple[int, int]] = []
    runs: list[list[tuple[int, int]]] = []
    for j, gh in enumerate(draft_hashes):
        if gh in grams:
            run.append((j, grams[gh]))
        else:
            if run:
                runs.append(run)
            run = []
    if run:
        runs.append(run)
    return runs


def cmd_overlap(draft: str | Path, citekey: str, n: int = 8) -> None:
    """Verbatim word-n-gram overlap between `draft`'s paragraphs citing
    `citekey` and that source's ledger-parsed text, fingerprinted and
    cached by chitragupta/overlap_index.py.

    The ledger's parsed text, not `pdftotext`: the text every other reader
    sees, and the only text a `docling` corpus has.
    """
    item = overlap_index.ledger_item(citekey)
    if item is None:
        print(f"no source text for {citekey}")
        return
    pdf_hash, parsed_path = item
    grams = overlap_index.grams_for_citekey(citekey, pdf_hash, parsed_path, n)
    hits = []
    for s in sentences_citing(draft, citekey):
        # A space, not "" (#516/m-53): deleting the marker welds its
        # neighbours into one token and can drop a run below the floor.
        w = norm(re.sub(r"\[@[^\]]+\]", " ", s))
        draft_hashes = overlap_index.gram_hashes(w, n)
        for r in _gram_hit_runs(draft_hashes, grams):
            start = r[0][0]
            length = r[-1][0] + n - start
            hits.append((length, r[0][1], " ".join(w[start : start + length]), s[:80]))
    hits.sort(reverse=True)
    if not hits:
        print(f"{citekey}: no verbatim run of >= {n} words found")
    for length, pg, frag, ctx in hits[:25]:
        print(f"  [{length} words, pdf p.{pg}] {frag}\n      in: {ctx}...")


def cmd_locate(citekey: str, *phrases: str) -> None:
    src_pages = pages(citekey)
    print(f"{citekey}: {len(src_pages)} pdf pages")
    for phrase in phrases:
        keys = [w for w in norm(phrase) if len(w) > 3]
        best = []
        for i, pg in enumerate(src_pages, 1):
            w = set(norm(pg))
            score = sum(1 for k in keys if k in w)
            best.append((score / max(len(keys), 1), i))
        best.sort(reverse=True)
        top = ", ".join(f"p.{i} ({s:.0%})" for s, i in best[:4])
        print(f"  {phrase!r}\n      -> {top}")
