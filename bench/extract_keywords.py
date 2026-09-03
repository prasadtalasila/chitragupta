"""Corpus-wide keyword phrases, extracted from the papers' own parsed
text rather than written by hand -- the other half of a seed list.

`content/topics.toml`/`content/seed_topics.toml` holds phrases an author
already had in mind (a field's vocabulary, a Zotero collection name).
This script instead asks the corpus what it talks about: TF-IDF over
every document's parsed text (the same `doc_vectors.corpus_texts()` the
topic model and seed-topic matcher both read), ranked by summed weight
across the corpus, with the author's own seed phrases excluded so this
never just re-proposes what `--exclude` already names. The result is
`content/keywords.toml`, written in the exact `topics = [...]` shape
`chitragupta/seed_topics.py:load()` reads, so it can be pointed at like
any other seed file -- see `bench/bench_keyword_seed_topics.py`, which is
the actual question this script exists to feed: does seeding with these
too, alongside the hand-written list, produce more meaningful matches?

Lists to the terminal by default and touches no file; pass `--write` to
also save the TOML, so sweeping `--top` to find where coverage plateaus
(`bench/RESULTS.md`'s 2026-09-03 entry) never clobbers a real
`content/keywords.toml` by accident.

Needs the "enrich" Poetry group and a synced corpus with parsed text, the
same as `bench/bench_topic_depth.py`.

    CONTENT_DIR=/path/to/content .venv-full/bin/python \\
        bench/extract_keywords.py --top 40

    CONTENT_DIR=/path/to/content .venv-full/bin/python \\
        bench/extract_keywords.py --top 40 --write
"""

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta import config, seed_topics  # noqa: E402
from chitragupta.enrich import corpus, doc_vectors  # noqa: E402
from chitragupta.enrich.topic_labels import stop_words  # noqa: E402

# `CITATION_NOISE` (topic_labels.py) catches bibliography scaffolding
# that appears mid-sentence -- "et al", a DOI fragment. What it does not
# catch is reference-*list* scaffolding, which is where TF-IDF over full
# text (rather than BERTopic's per-topic c-TF-IDF, computed after
# clustering has already grouped the papers that share a publisher)
# first meets it: measured on this corpus, "refhub"/"elsevier" and a bare
# "2023"/"2024" ranked in the top 40 before this set existed, one
# citation-manager artefact and two calendar years, neither a keyword
# for anything the papers are about.
REFERENCE_LIST_NOISE = frozenset({"refhub", "elsevier", "decoded", "sect", "springer", "wiley"})


def _is_year_like(term: str) -> bool:
    """True for a term that is nothing but digits and spaces -- "2023",
    "10 1016" -- which TF-IDF ranks by frequency same as any other term,
    but which names a publication date or a DOI fragment, not a subject.
    A term with any letter in it (`"3d"`, `"mqtt v5"`) is not year-like
    and is left alone."""
    return bool(term) and term.replace(" ", "").isdigit()


def _is_noisy(term: str, exclude: "set[str]") -> bool:
    """True if `term` should never reach `content/keywords.toml`: it (or
    the term were it split on whitespace) is already a known seed
    phrase, a reference-list artefact, or an all-digit token.

    Checked word-by-word rather than on the whole term alone because the
    vectorizer's `ngram_range=(1, 3)` means a two-gram can pair one real
    word with one noise word -- "formula decoded" and "refhub elsevier"
    both ranked in the top 40 on this corpus before this word-by-word
    check existed, `decoded` and `refhub`/`elsevier` each individually
    caught by the checks below but the bigram they formed was not.
    """
    words = term.split()
    if term.casefold() in exclude:
        return True
    if any(word in REFERENCE_LIST_NOISE for word in words):
        return True
    return _is_year_like(term)


def _top_terms(matrix, vocabulary: "list[str]", top: int, exclude: "set[str]") -> "list[str]":
    """The `top` vocabulary terms by summed TF-IDF weight across every
    document, skipping any term `_is_noisy` rules out: already in
    `exclude` (case-folded), a reference-list artefact, or an all-digit
    term.

    Factored out of `main()` so `self_check()` can fabricate a tiny
    matrix and vocabulary instead of fitting `TfidfVectorizer` on real
    corpus text. Ties break on the term itself, for the same reason
    `topic_seeding.assign()` breaks ties on citekey: a ranking that
    reorders itself between runs on tied scores is not one a person
    curating `content/keywords.toml` by re-running this script can trust.
    """
    import numpy as np

    # `np.asarray(...).ravel()` rather than the sparse-only `.A1`: this
    # reads a real (sparse) TF-IDF matrix from `main()` and a plain dense
    # array from `self_check()` alike, with the same line of code.
    scores = np.asarray(matrix.sum(axis=0)).ravel()
    ranked = sorted(range(len(vocabulary)), key=lambda i: (-scores[i], vocabulary[i]))
    picked = []
    for index in ranked:
        term = vocabulary[index]
        if _is_noisy(term, exclude):
            continue
        picked.append(term)
        if len(picked) == top:
            break
    return picked


def self_check() -> None:
    """Prove `_top_terms` ranks by summed weight, breaks ties
    alphabetically, drops an excluded term rather than counting it
    toward `top`, and drops a reference-list artefact and an all-digit
    term the same way -- the shapes a real TF-IDF fit would hide inside
    floating-point noise and alphabetical accident, or would rank
    straight into the output since nothing about a raw score
    distinguishes "refhub" or "2023" from a real keyword.

    `bench/` sits outside CI's coverage targets, so nothing in the test
    suite will ever catch a regression here. This runs on every
    invocation instead, and needs no real vectorizer fit.
    """
    import numpy as np

    assert _is_year_like("2023")
    assert _is_year_like("10 1016")
    assert not _is_year_like("3d"), "a term with a letter in it is not year-like"
    assert not _is_year_like(""), "an empty term is not year-like"

    # column sums: a=5, b=3, c=2, d=2 ("c" and "d" tie).
    matrix = np.array(
        [
            [3.0, 1.0, 0.0, 1.0],
            [2.0, 1.0, 1.0, 0.0],
            [0.0, 1.0, 1.0, 1.0],
        ]
    )
    vocabulary = ["a", "b", "c", "d"]

    picked = _top_terms(matrix, vocabulary, top=3, exclude=set())
    assert picked == ["a", "b", "c"], f"expected rank order with alpha tie-break, got {picked}"

    excluded = _top_terms(matrix, vocabulary, top=3, exclude={"b"})
    assert excluded == ["a", "c", "d"], f"excluded term must not consume a slot, got {excluded}"

    # "refhub" (a=5) outranks every real term below it; "2023" (b=3) is
    # the runner-up. Both must be skipped like an excluded term, not
    # counted toward `top`.
    noisy_vocabulary = ["refhub", "2023", "c", "d"]
    cleaned = _top_terms(matrix, noisy_vocabulary, top=2, exclude=set())
    assert cleaned == ["c", "d"], f"reference-list noise and years must be dropped, got {cleaned}"

    # "refhub elsevier" (a=5) is a bigram pairing two noise words; it
    # must be dropped the same as either word alone, not survive because
    # the two-word string itself is not in `REFERENCE_LIST_NOISE`.
    bigram_vocabulary = ["refhub elsevier", "2023", "c", "d"]
    bigram_cleaned = _top_terms(matrix, bigram_vocabulary, top=2, exclude=set())
    assert bigram_cleaned == ["c", "d"], f"a noise bigram must be dropped too, got {bigram_cleaned}"

    rendered = _render_toml(["edge", "digital twin"], Path("content/topics.toml"))
    body = rendered.splitlines()
    assert body[-4:] == ["topics = [", '    "digital twin",', '    "edge",', "]"], (
        f"expected a sorted, closed topics array, got {rendered!r}"
    )


def _render_toml(keywords: "list[str]", exclude_path: Path) -> str:
    """`content/keywords.toml`'s exact text, in the `topics = [...]` shape
    `chitragupta/seed_topics.py:load()` reads. Kept separate from
    `main()` so the sweep in `bench/RESULTS.md` can print candidates
    without ever touching disk -- `--write` is what commits to a file,
    printing is not."""
    lines = [
        "# Generated by bench/extract_keywords.py from the corpus's own parsed",
        "# PDF text (TF-IDF over every document, ranked by summed weight across",
        f"# the corpus), excluding every phrase already in {exclude_path}.",
        "# Not hand-curated -- see bench/bench_keyword_seed_topics.py for",
        "# whether seeding with this alongside the hand-written list helps.",
        "",
        "topics = [",
    ]
    for keyword in sorted(keywords):
        lines.append(f'    "{keyword}",')
    lines.append("]")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--top", type=int, default=40, help="how many keyword phrases to list")
    parser.add_argument(
        "--write",
        action="store_true",
        help="also write the TOML to --out (default: only list to the terminal)",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="default: content/keywords.toml (needs --write)"
    )
    parser.add_argument(
        "--exclude",
        type=Path,
        default=None,
        help="an existing seed-topics TOML whose phrases are never re-proposed "
        "as keywords (default: content/topics.toml)",
    )
    args = parser.parse_args(argv)
    self_check()

    out_path = args.out or (config.CONTENT_DIR / "keywords.toml")
    exclude_path = args.exclude or (config.CONTENT_DIR / "topics.toml")

    from sklearn.feature_extraction.text import TfidfVectorizer

    docs = corpus.build_corpus()
    doc_texts = doc_vectors.corpus_texts(docs)
    texts = list(doc_texts.values())
    if not texts:
        print("no parsed text to extract keywords from", flush=True)
        return 1

    exclude = {phrase.casefold() for phrase in seed_topics.load(exclude_path)}
    vectorizer = TfidfVectorizer(stop_words=stop_words(), ngram_range=(1, 3), min_df=3, max_df=0.6)
    matrix = vectorizer.fit_transform(texts)
    vocabulary = vectorizer.get_feature_names_out().tolist()
    keywords = _top_terms(matrix, vocabulary, args.top, exclude)

    print(f"{len(texts)} documents, {len(vocabulary)}-term vocabulary, excluding {exclude_path}")
    print(f"\n{len(keywords)} keyword phrases:")
    for keyword in sorted(keywords):
        print(f"  {keyword}")

    if args.write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_render_toml(keywords, exclude_path), encoding="utf-8")
        print(f"\nwrote {len(keywords)} keyword phrases to {out_path}")
    else:
        print(f"\nnot written -- pass --write to save to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
