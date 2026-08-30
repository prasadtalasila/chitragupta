"""Find close-paraphrase candidates in a real drafted book, and check
which detection tiers fire on them.

This is a **recall** harness, and the only one here. `bench_overlap_gate.py`,
`bench_overlap_skipgram.py` and `bench_overlap_embed.py` all start from
what a tier *found* and ask how much of it is wrong. This one starts from
what a reader *finds by reading* and asks how much of it a tier saw. The
two questions have opposite failure modes and neither substitutes for the
other: a tier that reports nothing scores perfect precision.

## Why it exists

#134's implementation plan names
`bench/results/2026-08-14-organic-paraphrase-hunt/candidates.md` -- 59
hand-flagged close-paraphrase candidates -- as tier 3's primary
validation dataset. That file was never committed; the issue comment
says so at the time ("labels and raw results are local to this session"),
and it is not recoverable. A dataset that exists only in a session's
context is a dataset that has to be rebuilt from scratch every time
someone wants to check a claim made from it, which is the same failure
`bench/RESULTS.md` exists to prevent. So this script is the method,
written down: run it and the candidate list comes back.

## The method, and the one thing that would invalidate it

1. **Every citation's claim**, via `citation_provenance.claims()` -- the
   citing sentence, table row or list item, never the raw line.
2. **Passages of the cited source only.** The citekey already says which
   paper, so the only search is *within* that document. This is what
   keeps the dataset independent of tier 3: nothing here embeds anything,
   and a candidate enters the set because a reader judged it, not because
   a cosine ranked it. Building the candidate list with the same
   similarity the tier uses would make "tier 3 catches N% of candidates"
   a measurement of nothing.
3. **A shortlist, stated rather than silent.** Ranking by lexical support
   and reading the top of that ranking is a cap, and it is reported: the
   count read, the count shortlisted, and the count extracted.
4. **A human judgment per pair**, recorded with its reason in
   `labels.json`. This script does not classify; it prepares pairs for
   someone who will, and merges their judgments back.
5. **A cross-check** against every tier, at `(citekey, chapter)`
   granularity -- "did the scanner find *something* for that citekey in
   that chapter", which is the granularity #134's own hand read used.

**The bias to state whenever a number from this is quoted.** Step 2
retrieves within the right document by *lexical* overlap, so for a
genuine restatement -- the class tier 3 exists for -- the top passages
may not include the one actually restated, and the pair reads as "no
corresponding passage found" rather than as a candidate. That is a
false-negative bias pointing straight at the target class, so a
close-paraphrase count from this method is a **floor**, not an estimate.
The `no-match` judgment exists to keep that visible instead of silently
folding those pairs into "not a paraphrase".

    .venv/bin/python bench/bench_paraphrase_hunt.py --extract \\
        --drafts content/drafts/books/digital-twins-for-software-engineers \\
        --tag 2026-08-15-organic-paraphrase-hunt

    # ... judge the pairs it wrote, then:

    .venv/bin/python bench/bench_paraphrase_hunt.py --crosscheck \\
        --drafts content/drafts/books/digital-twins-for-software-engineers \\
        --tag 2026-08-15-organic-paraphrase-hunt
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import config, ledger, overlap_index, passages  # noqa: E402
from chitragupta.review import citation_provenance as cp  # noqa: E402

# Claims at or above this lexical support are shortlisted for reading.
# Not a threshold on anything published -- a reading order, and the cap
# is reported in the output rather than applied silently.
SHORTLIST_SUPPORT = 0.5

# Passages of the cited document offered per claim.
PASSAGES_PER_CLAIM = 5

# A claim shorter than this many alphabetic words is a pointer or a
# citekey enumeration ("and [@key] for a small-manufacturer case"), not a
# checkable assertion about the source.
MIN_CLAIM_WORDS = 12

_POINTER = re.compile(r"where to go next|further reading|see also|^\s*\[\d+\]", re.I)
_WORD = re.compile(r"[a-z]{3,}")
# Tokens a restatement usually keeps even when it rewrites everything
# around them, and which a bag-of-words score can miss.
_HARD = re.compile(r"\b\d[\d.,%]*\b|\b[A-Z]{2,}\b")


def is_pointer(claim):
    return bool(_POINTER.search(claim)) or len(_WORD.findall(claim.lower())) < MIN_CLAIM_WORDS


def extract(drafts_dir, out_dir):
    """Write one record per claim: the claim, and the passages of the
    source it cites that a reader should judge it against."""
    con = ledger.connect()
    cache, rows, skipped = {}, [], 0
    for chapter in sorted(Path(drafts_dir).glob("*.md")):
        if not chapter.name[0].isdigit():
            continue
        text = chapter.read_text(encoding="utf-8")
        for line, citekey, claim in cp.claims(text):
            if is_pointer(claim):
                skipped += 1
                continue
            if citekey not in cache:
                found, _reason = passages.source_passages(con, citekey)
                cache[citekey] = [p for p in found if p.text]
            source = cache[citekey]
            if not source:
                skipped += 1
                continue
            rows.append(_record(chapter, line, citekey, claim, source))

    shortlisted = [
        r for r in rows if r["lexical"] and r["lexical"][0]["score"] >= SHORTLIST_SUPPORT
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pairs.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"citations with a readable cited source: {len(rows)}")
    print(f"skipped as pointer or unreadable source: {skipped}")
    print(f"shortlisted at lexical support >= {SHORTLIST_SUPPORT}: {len(shortlisted)}")
    print("  -- the rest are not judged, and are not evidence of anything")
    print(f"Record: {out_dir / 'pairs.json'}")
    return 0


def _record(chapter, line, citekey, claim, source):
    scored = sorted(
        ((cp.score_claim(claim, [p])[0], p) for p in source), key=lambda pair: -pair[0]
    )[:PASSAGES_PER_CLAIM]
    hard = set(_HARD.findall(claim))
    token_hits = [
        p
        for p in source
        if hard & set(_HARD.findall(p.text)) and all(p is not other for _score, other in scored)
    ]
    return {
        "chapter": chapter.name,
        "line": line,
        "citekey": citekey,
        "claim": claim,
        "lexical": [
            {"score": round(s, 3), "page": p.page, "text": p.text} for s, p in scored if s > 0
        ],
        "token_hits": [{"page": p.page, "text": p.text} for p in token_hits[:3]],
    }


def lexical_findings(drafts_dir):
    """Tiers 1 and 2 per chapter, called directly.

    Not through `scan_findings`, deliberately: that would run tier 3 as
    well, re-embedding every shortlisted source for a third time to
    recover a population `bench_overlap_embed.py` has already recorded.
    """
    from chitragupta.review import verbatim_check as vc

    # The two tier functions live in private submodules and are not
    # re-exported by the package, so `vc._exact_tier_findings` raises
    # AttributeError -- import them from where they actually are.
    from chitragupta.review.verbatim_check._exact import _exact_tier_findings
    from chitragupta.review.verbatim_check._skipgram import _skipgram_tier_findings

    out = {}
    for chapter in sorted(Path(drafts_dir).glob("*.md")):
        if not chapter.name[0].isdigit():
            continue
        text = chapter.read_text(encoding="utf-8")
        words, paragraph_citekeys = vc._tokenize_draft(text)
        word_strs = [w.text for w in words]
        newlines = vc._newline_offsets(text)
        found = []
        for finder in (_exact_tier_findings, _skipgram_tier_findings):
            rows, _suppressed = finder(
                words, word_strs, paragraph_citekeys, newlines, text, overlap_index.DEFAULT_N, 1, []
            )
            found += rows
        out[chapter.name] = found
        print(f"  {chapter.name}: {len(found)} lexical finding(s)", flush=True)
    return out


def crosscheck(drafts_dir, out_dir, embed_record):
    """Merge the judgments with which tiers fired, and report."""
    labels_path = out_dir / "labels.json"
    if not labels_path.exists():
        print(f"no {labels_path} -- judge the pairs first", file=sys.stderr)
        return 1
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    embed = json.loads(Path(embed_record).read_text(encoding="utf-8"))["findings"]
    lexical = lexical_findings(drafts_dir)

    for row in payload["candidates"]:
        tiers = {
            f["tier"] for f in lexical.get(row["chapter"], []) if f["citekey"] == row["citekey"]
        }
        tiers |= {
            f["tier"]
            for f in embed
            if f["citekey"] == row["citekey"] and f["draft"] == row["chapter"]
        }
        row["tiers"] = sorted(tiers)

    para = [r for r in payload["candidates"] if r["judgment"] == "paraphrase"]
    by_tier = collections.Counter(", ".join(r["tiers"]) or "NOTHING" for r in para)
    payload["close_paraphrase_by_tier"] = dict(sorted(by_tier.items()))
    labels_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"\nclose-paraphrase candidates: {len(para)} of {len(payload['candidates'])} judged")
    for tiers, n in by_tier.most_common():
        print(f"  {n:2d}  caught by: {tiers}")
    print(f"Record: {labels_path}")
    return 0


def self_check():
    """A pointer really is filtered and a claim really is not.

    The published counts are a population and a share of it, and a filter
    that quietly matched everything would report a small, clean-looking
    dataset that meant nothing -- the failure `repro_check.py`'s own
    self-check exists for.
    """
    assert is_pointer("and [@singh_digital_2023] for a small-manufacturer case"), (
        "the pointer filter no longer catches a further-reading pointer"
    )
    assert not is_pointer(
        "A case study of a small-to-medium roll-to-roll label-printing manufacturer "
        "reports a deliberate strategy of protecting return on investment"
    ), "the pointer filter is swallowing checkable claims"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--extract", action="store_true", help="write the claim/passage pairs to judge")
    ap.add_argument(
        "--crosscheck", action="store_true", help="merge judgments with which tiers fired"
    )
    ap.add_argument("--drafts", required=True, help="directory of chapters")
    ap.add_argument(
        "--tag", required=True, help="names bench/results/<tag>/ (path components stripped)"
    )
    ap.add_argument(
        "--embed-record",
        default="bench/results/2026-08-15-embed/embed_precision.json",
        help="where the embedding tier's finding population was recorded",
    )
    args = ap.parse_args(argv)

    self_check()
    if not config.LEDGER_PATH.exists():
        print(
            f"no ledger at {config.LEDGER_PATH} -- run `python -m chitragupta.corpus sync`",
            file=sys.stderr,
        )
        return 1
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    if args.extract:
        return extract(args.drafts, out_dir)
    if args.crosscheck:
        return crosscheck(args.drafts, out_dir, args.embed_record)
    print("one of --extract or --crosscheck is required", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
