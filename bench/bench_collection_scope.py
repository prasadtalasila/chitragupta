"""What `--collection` (#195, src/bib_collections.py) buys a drafting run:
the same chapter written once against the whole corpus (Arm F) and once
against a curated shelf (Arm C), from the same pre-registered queries at
the same `--k`/`--chars`.

Parameterised, so one script serves every run of this design. The first
run of it (`bench/results/2026-08-18-collection-scope/`, `DT Platforms`,
a platforms chapter) hard-coded its own paths; this version takes them as
arguments so the `Lifecycle` replication and any later one share code
rather than a copy. That first run's script existed only as an
uncommitted file in the main working tree -- if you are landing this,
check you are not creating a duplicate of it.

Six things, each read from a different source because each is
trustworthy for a different reason:

- **Retrieval payload** (`retrieval.md` in each dossier) -- deterministic,
  and the only figure that is purely the feature's own cost. No session
  transcript involved.
- **Surfaced / selected / rejected** -- BM25 is deterministic over a fixed
  ledger, so replaying each dossier's own logged queries (with and
  without the collection filter, at the logged `--k`) reconstructs
  exactly what each arm's `search()` calls returned. This only holds
  because the ledger was not synced between drafting and this replay.
  `--hashes` checks that precondition instead of assuming it.
- **Index cost** -- `search()` scores corpus-wide and filters the ranking,
  so the cache is shared by construction. Checked by comparing the
  `content/retrieval_index.json` hashes recorded before Arm F, between
  the arms and after Arm C, rather than by re-reading the docstring.
- **Words** -- `wc -w` equivalent over each draft's body, excluding the
  generated References section. This is the denominator the first run
  lacked: without it, "Arm C used fewer output tokens" cannot be
  separated from "Arm C wrote a shorter chapter".
- **Tokens** -- read from the session transcript JSONL, windowed by the
  timestamps in `hashes.jsonl` (which are the arm boundaries, recorded
  as the arms ran) rather than by hand. The model in force is read per
  window, so a mid-arm `/model` switch is reported rather than silently
  netted out.
- **Draft-vs-draft overlap** -- shared word runs between the two arms'
  drafts. A clearly-labelled extra, not the headline: the headline
  overlap figure is each arm's scan against the *corpus*, which is what
  `src.review verbatim` measures.

    python bench/bench_collection_scope.py \\
        --topic book-chapters/digital-twin-life-cycle-considerations \\
        --arm-c digital-twin-life-cycle-considerations \\
        --arm-f digital-twin-life-cycle-considerations-full-corpus \\
        --collection Lifecycle \\
        --out bench/results/2026-08-18-collection-scope-lifecycle/measurements.json

Stdlib only -- runs under bare `python`, no venv, no lock.
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src import bib_collections, config, ledger, retrieval  # noqa: E402
from src.dossier._retrieval import _retrieval_rows  # noqa: E402

CITEKEY_RE = re.compile(r"\[@([a-zA-Z0-9_:-]+)\]")
REFERENCES_RE = re.compile(r"^#{1,3} (?:\d+\.\s*)?References\s*$", re.MULTILINE)
WORD_RUN = 8


def _body(draft_path):
    """The draft minus its generated References section.

    References are produced by `src.draft references` from the gated
    citekeys, so counting them as drafted words would credit each arm for
    its own bibliography -- and the whole-corpus arm has a longer one
    precisely because it cited more, which would flatter it twice.
    """
    text = draft_path.read_text(encoding="utf-8")
    match = REFERENCES_RE.search(text)
    return text[:match.start()] if match else text


def _cited_citekeys(draft_path):
    return set(CITEKEY_RE.findall(_body(draft_path)))


def _word_count(draft_path):
    return len(_body(draft_path).split())


def _replay_queries(dossier, collection):
    """query -> sorted citekeys `search()` returns today, at the query's
    own logged `--k`. `retrieval.md` records a result *count*, never the
    identities -- this replay is what makes "surfaced" answerable at all
    after the fact, and it is sound only over an unmoved ledger.
    """
    out = {}
    for row in _retrieval_rows(dossier):
        _date, mode, query, k, _results, _chars = row
        if mode != "search":
            continue
        found = retrieval.search(query, k=int(k), collection=collection)
        out[query] = sorted(r.citekey for r in found)
    return out


def _collection_size(collection):
    """How many ledger items the filter can reach, through
    `bib_collections.matches` rather than a tally of exact path strings:
    matching is prefix-by-segment, so a subcollection folds in and a
    string tally would undercount the denominator.
    """
    if collection is None:
        return None
    con = ledger.connect()
    try:
        return sum(1 for row in ledger.all_items(con)
                   if bib_collections.matches(bib_collections.of_row(row), collection))
    finally:
        con.close()


def _hash_check(hashes_path):
    """Whether the index and the ledger moved across the three
    checkpoints. If either did, the replay above is not reconstructing
    what the arms saw, and every surfaced-set figure here is void.
    """
    if not hashes_path or not hashes_path.is_file():
        return {"checked": False,
                "note": "no hashes.jsonl given -- the replay's precondition is unverified"}
    lines = hashes_path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    index_hashes = {r["retrieval_index"]["md5"] for r in rows}
    ledger_hashes = {r["ledger"]["md5"] for r in rows}
    return {
        "checked": True,
        "checkpoints": [r["point"] for r in rows],
        "index_unchanged": len(index_hashes) == 1,
        "ledger_unchanged": len(ledger_hashes) == 1,
        "index_md5": sorted(index_hashes),
        "ledger_md5": sorted(ledger_hashes),
        "index_bytes": sorted({r["retrieval_index"]["bytes"] for r in rows}),
        "replay_sound": len(index_hashes) == 1 and len(ledger_hashes) == 1,
    }


def _verbatim_summary(path):
    if not path.is_file():
        return {"ran": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    findings = data.get("findings", [])
    by_tier = {}
    for f in findings:
        by_tier[f["tier"]] = by_tier.get(f["tier"], 0) + 1
    not_run = data.get("tiers_not_run", [])
    return {
        "ran": True,
        "findings": len(findings),
        "by_tier": by_tier,
        "longest_run_words": max((f.get("span_words", 0) for f in findings), default=0),
        "tiers_not_run": [t["tier"] if isinstance(t, dict) else t for t in not_run],
    }


def _shared_runs(path_a, path_b, n=WORD_RUN):
    """Word runs of length >= n that appear in both drafts.

    A deliberately crude measure, and labelled as such in the output: it
    is here only to put a number on confound 1 (one session wrote both
    chapters), not to stand in for the corpus scan. Runs are normalised
    to lowercase words with punctuation stripped, so it will over-report
    shared boilerplate like table headers.
    """
    def grams(path):
        words = re.findall(r"[a-z0-9]+", _body(path).lower())
        return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}, words

    a_grams, a_words = grams(path_a)
    b_grams, _ = grams(path_b)
    shared = a_grams & b_grams
    # Longest shared run, by greedily extending each shared n-gram in A.
    longest = 0
    if shared:
        i = 0
        while i < len(a_words) - n + 1:
            if tuple(a_words[i:i + n]) in shared:
                j = i
                while j < len(a_words) - n + 1 and tuple(a_words[j:j + n]) in shared:
                    j += 1
                longest = max(longest, (j - i) + n - 1)
                i = j
            else:
                i += 1
    return {
        "measure": f"shared word runs of >= {n} words, lowercased, punctuation stripped",
        "caveat": "crude by design -- over-reports shared table headers and the "
                  "pre-registered section titles, which are identical by construction. "
                  "Not a substitute for the per-arm corpus scan.",
        "shared_ngrams": len(shared),
        "arm_f_ngrams": len(a_grams),
        "arm_c_ngrams": len(b_grams),
        "jaccard": round(len(shared) / len(a_grams | b_grams), 4) if (a_grams or b_grams) else None,
        "longest_shared_run_words": longest,
    }


def _pool_usage(session_file, start, end):
    """Turns and tokens for assistant entries timestamped in [start, end).

    Dedups on requestId -- streaming writes an entry more than once
    (docs/TOKENS.md) -- and records every distinct model seen, so a
    mid-window `/model` switch shows up instead of being averaged away.
    """
    seen = set()
    turns = tokens_in = tokens_out = 0
    models = {}
    if not session_file or not session_file.is_file():
        return {"turns": 0, "input_tokens": 0, "output_tokens": 0,
                "note": "transcript not found"}
    with session_file.open(encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            ts = entry.get("timestamp")
            if not ts or not start <= ts < end:
                continue
            message = entry.get("message") or {}
            usage = message.get("usage")
            rid = entry.get("requestId")
            if not usage or rid in seen:
                continue
            seen.add(rid)
            turns += 1
            tokens_in += (usage.get("input_tokens", 0)
                          + usage.get("cache_read_input_tokens", 0)
                          + usage.get("cache_creation_input_tokens", 0))
            tokens_out += usage.get("output_tokens", 0)
            model = message.get("model")
            if model:
                models[model] = models.get(model, 0) + 1
    return {"turns": turns, "input_tokens": tokens_in, "output_tokens": tokens_out,
            "models": models}


def _boundaries(hashes_path, session_file):
    """Arm boundaries, taken from the hash checkpoints rather than from
    hand-recorded times: each checkpoint was written at the boundary it
    names, so the two cannot drift apart.
    """
    lines = hashes_path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    at = {r["point"]: r["utc"] for r in rows}
    first = None
    if session_file and session_file.is_file():
        with session_file.open(encoding="utf-8") as f:
            for line in f:
                try:
                    ts = json.loads(line).get("timestamp")
                except ValueError:
                    continue
                if ts:
                    first = ts
                    break
    return {
        "session_start": first or at["before-arm-F"],
        "arm_f_start": at["before-arm-F"],
        "arm_f_end": at["between-arms"],
        "arm_c_end": at["after-arm-C"],
    }


def run(args):
    drafts = config.CONTENT_DIR / "drafts" / args.topic
    dossiers = config.CONTENT_DIR / "dossiers" / args.topic
    review = config.CONTENT_DIR / "review" / args.topic

    arm_f = {"draft": drafts / f"{args.arm_f}.md", "dossier": dossiers / args.arm_f,
             "verbatim": review / f"{args.arm_f}.verbatim.json", "collection": None}
    arm_c = {"draft": drafts / f"{args.arm_c}.md", "dossier": dossiers / args.arm_c,
             "verbatim": review / f"{args.arm_c}.verbatim.json", "collection": args.collection}

    cited_f = _cited_citekeys(arm_f["draft"])
    cited_c = _cited_citekeys(arm_c["draft"])

    replay_f = _replay_queries(arm_f["dossier"], None)
    replay_c = _replay_queries(arm_c["dossier"], args.collection)
    surfaced_f = set().union(*replay_f.values()) if replay_f else set()
    surfaced_c = set().union(*replay_c.values()) if replay_c else set()

    chars_f = sum(int(r[5]) for r in _retrieval_rows(arm_f["dossier"]) if r[1] == "search")
    chars_c = sum(int(r[5]) for r in _retrieval_rows(arm_c["dossier"]) if r[1] == "search")

    size_c = _collection_size(args.collection)
    words_f = _word_count(arm_f["draft"])
    words_c = _word_count(arm_c["draft"])

    def ratios(cited, surfaced, extra=None):
        out = {
            "surfaced_distinct_citekeys": len(surfaced),
            "cited": len(cited),
            "rejected": len(surfaced) - len(cited & surfaced),
            "selection_ratio": round(len(cited) / len(surfaced), 4) if surfaced else None,
            "rejection_ratio": round(1 - len(cited) / len(surfaced), 4) if surfaced else None,
        }
        out.update(extra or {})
        return out

    result = {
        "preregistration": args.preregistration,
        "collection": args.collection,
        "retrieval_payload": {
            "arm_f_chars": chars_f,
            "arm_c_chars": chars_c,
            "arm_f_queries": len(replay_f),
            "arm_c_queries": len(replay_c),
            "chars_delta_pct": round(100 * (chars_c - chars_f) / chars_f, 2) if chars_f else None,
            "note": "near-parity is the expected result, not a null one: at a fixed "
                    "--k the filter still returns k results, drawn from a smaller "
                    "pool. The filter changes WHICH papers arrive, not how many "
                    "characters do.",
        },
        "words": {
            "arm_f_words": words_f,
            "arm_c_words": words_c,
            "note": "body only; the generated References section is excluded from both.",
        },
        "surfaced_selected_rejected": {
            "arm_f": ratios(cited_f, surfaced_f),
            "arm_c": ratios(cited_c, surfaced_c, {
                "collection_size": size_c,
                "collection_coverage": round(len(surfaced_c) / size_c, 4) if size_c else None,
                "caveat": "surfaced is capped at collection_size by construction, so "
                          "arm_c's selection_ratio has a denominator that cannot grow. "
                          "Compare ratios, never raw surfaced counts.",
            }),
        },
        "common_papers": {
            "cited_in_both": sorted(cited_f & cited_c),
            "cited_only_in_f": sorted(cited_f - cited_c),
            "cited_only_in_c": sorted(cited_c - cited_f),
            "surfaced_in_both": sorted(surfaced_f & surfaced_c),
            "surfaced_in_both_count": len(surfaced_f & surfaced_c),
            "surfaced_only_in_c_count": len(surfaced_c - surfaced_f),
            "surfaced_only_in_c": sorted(surfaced_c - surfaced_f),
        },
        "index_cost": _hash_check(args.hashes),
        "verbatim_overlap": {
            "arm_f": _verbatim_summary(arm_f["verbatim"]),
            "arm_c": _verbatim_summary(arm_c["verbatim"]),
            "draft_vs_draft": _shared_runs(arm_f["draft"], arm_c["draft"]),
        },
    }

    if args.session and args.hashes and args.hashes.is_file():
        b = _boundaries(args.hashes, args.session)
        windows = {
            "setup (orientation + preregistration, shared)":
                _pool_usage(args.session, b["session_start"], b["arm_f_start"]),
            "arm F -- total (retrieval + first draft + rewrite + pipeline)":
                _pool_usage(args.session, b["arm_f_start"], b["arm_f_end"]),
            "arm C -- total (retrieval + draft + pipeline)":
                _pool_usage(args.session, b["arm_f_end"], b["arm_c_end"]),
        }
        if args.steering_at:
            windows["arm F -- before the steering (retrieval + first draft)"] = \
                _pool_usage(args.session, b["arm_f_start"], args.steering_at)
            windows["arm F -- after the steering (rewrite + pipeline, QUARANTINED)"] = \
                _pool_usage(args.session, args.steering_at, b["arm_f_end"])
        result["boundaries"] = b
        result["tokens"] = windows
        drafted_f = words_f + (args.arm_f_discarded_words or 0)
        per_k = {}
        arm_f_total = windows["arm F -- total (retrieval + first draft + rewrite + pipeline)"]
        arm_c_total = windows["arm C -- total (retrieval + draft + pipeline)"]
        if drafted_f:
            per_k["arm_f_output_tokens_per_1k_words"] = round(
                1000 * arm_f_total["output_tokens"] / drafted_f, 1)
        if words_c:
            per_k["arm_c_output_tokens_per_1k_words"] = round(
                1000 * arm_c_total["output_tokens"] / words_c, 1)
        per_k["arm_f_words_drafted_total"] = drafted_f
        per_k["arm_c_words_drafted_total"] = words_c
        per_k["note"] = ("Count each word an arm actually emitted, once. Where an arm "
                         "redrafted, the overwritten passes are not on disk and are "
                         "passed in via --arm-f-discarded-words; a pass that was written "
                         "once and then patched in place is counted once, not once per "
                         "assembly it appears in. Both windows also contain non-drafting "
                         "output -- gate, references, renders, style, verbatim -- so this "
                         "is an upper bound on the cost of drafting 1,000 words, not a "
                         "clean measure of it.")
        result["tokens_per_1k_words"] = per_k
        result["tokens_note"] = (
            "Windowed by the hash checkpoints, which were written at the arm "
            "boundaries themselves. Input tokens are dominated by cache reads of "
            "the other arm's context and are NOT a fair arm-to-arm comparison; "
            "output tokens and turns are. Arm C ran second and therefore carried "
            "Arm F's whole context, so any Arm C saving is a lower bound. The "
            "'models' map in each window is there so a mid-arm /model switch is "
            "visible rather than averaged away."
        )
    return result


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--topic", required=True,
                        help="Path under content/drafts/, e.g. "
                             "book-chapters/digital-twin-life-cycle-considerations")
    parser.add_argument("--arm-f", required=True, help="Whole-corpus draft stem")
    parser.add_argument("--arm-c", required=True, help="Collection-scoped draft stem")
    parser.add_argument("--collection", required=True, help="Zotero collection name")
    parser.add_argument("--preregistration", default=None,
                        help="Path to this run's preregistration.md, recorded in the output")
    parser.add_argument("--hashes", type=Path, default=None,
                        help="hashes.jsonl from the three checkpoints. Supplies the arm "
                             "boundaries and checks the replay's precondition.")
    parser.add_argument("--session", type=Path, default=None,
                        help="Session transcript JSONL for the token accounting")
    parser.add_argument("--steering-at", default=None,
                        help="ISO timestamp of a mid-arm-F steering change, to split "
                             "and quarantine the rewrite it caused")
    parser.add_argument("--arm-f-discarded-words", type=int, default=0,
                        help="Word count of an Arm F draft that was written and then "
                             "overwritten, for the per-1k-words normalisation")
    parser.add_argument("--out", type=Path, help="Write JSON here as well as stdout")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    result = run(args)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
