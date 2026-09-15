"""BM25 whose unit is a paragraph rather than a whole document (#769).

`chitragupta/retrieval.py` ranks one bag of words per source and then,
*after* the top-k is decided, hunts that source's text for a 500-character
window scored by a different rule entirely -- how many distinct query
terms fall inside it. So the evidence a drafting skill is shown was
chosen by a criterion that had no part in deciding the source was worth
showing, and it is a character window rather than a paragraph: cut
wherever 500 characters land, carrying no page number.

This module closes that gap by making the ranked object and the displayed
object the same thing. What ranks is a real reading-ordered paragraph out
of the corpus layer's passage sidecar; what comes back is that paragraph,
verbatim, with the page a reader can turn to. `chitragupta/passages.py`'s
own docstring has named this as the unbuilt consumer its seam was
extracted for since before this existed.

It is an *alternative* unit, not a replacement. "Did this paper argue X?"
is genuinely a whole-document question, and `retrieval.search` is
unchanged -- same signature, same scores, same snippets. The caller
chooses (`retrieve search --unit passage`).

Scores from the two units are not comparable and must never be sorted
into one list: `N`, every document frequency and `avgdl` are computed over
passages here and over documents there, so the numbers are on different
scales by construction.

#762's field weights are *inert* on this unit, and that is right rather
than missed. A passage entry carries no `field_freqs`, so
`retrieval_scoring.weighted_freq` returns the plain frequency however
`[retrieval].weight_title`/`weight_abstract` are set. Title and abstract
are properties of a document, and this unit's whole premise is that the
paragraph is the thing being scored -- weighting one paragraph because
the *paper* has a matching title would reintroduce exactly the pooling
this exists to drop. Worth knowing before raising a weight and wondering
why only one unit moved; docs/CONFIG.md says so too.

Stdlib only, like everything else on the tier-1 path: no venv, no model,
no `rank_bm25`. `chitragupta/enrich/embed_index.py` also ranks
sub-document units, and needs both a venv and a model download to do it.
"""

# One source can no longer be trusted to take one result slot, which is
# the other consequence of the smaller unit. `retrieval.search` is
# one-per-citekey by construction -- its scores dict is keyed by citekey
# -- so its docstring can say a cap "would be a no-op here". A
# well-matched paper has as many passages as it has paragraphs, so this
# needs the cap that docstring anticipated: `config.MAX_PASSAGES_PER_SOURCE`.
#
# Why there is no over-fetch multiplier beside it, which is the obvious
# thing to look for after reading `embed_index.search`: that path caps a
# list Chroma already truncated, so without over-fetching, dropping a
# dominant paper's excess chunks shortens the result instead of promoting
# another paper's chunk into it -- the failure #305 existed to fix.
# Nothing truncates here. `bm25_scores` returns every passage that scored
# above zero, so `_capped` walks the fully ranked list and takes the first
# k that fit, which is what an unbounded over-fetch would buy.
#
# Both said as comments rather than in the docstring above because
# docs/CODE-STANDARDS.md's C2 counts docstring lines, and this module
# already paid that limit once: the cache half is
# chitragupta/retrieval_passages_cache.py for exactly that reason.

from dataclasses import dataclass

from chitragupta import (
    bib_collections,
    config,
    ledger,
    passages,
    retrieval_passages_cache,
    retrieval_scoring,
)
from chitragupta.retrieval import _query_terms


@dataclass
class PassageResult:
    """One ranked paragraph. `text` is verbatim and quotable: it comes
    from a rung-2 sidecar, so it is a real reading-ordered paragraph
    rather than a window cut out of flattened text."""

    citekey: str
    title: str
    score: float
    text: str
    page: int | None
    passage_index: int
    label: str | None


@dataclass
class PassageSearch:
    """`results`, plus how many parsed sources this path could not reach.

    A citekey parsed by `pdftotext` leaves no sidecar, so it is not ranked
    low here -- it is absent from the index entirely. Falling back to a
    document-level score for those would put two incomparable numbers in
    one ranking (see the module docstring), so the gap is reported rather
    than papered over, and a caller that wants it said out loud can.
    """

    results: list[PassageResult]
    without_sidecar: int


def _capped(ranked: list, k: int) -> list:
    """The first `k` of `ranked` in which no citekey appears more than
    `config.MAX_PASSAGES_PER_SOURCE` times.

    Applied to the whole ranked list rather than to a truncated pool,
    which is why no over-fetch multiplier is needed -- see the comment at
    the top of this module. Because the list is already sorted, the
    passages a source keeps are its highest-scoring ones rather than
    whichever the loop reached first.
    """
    limit = config.MAX_PASSAGES_PER_SOURCE
    seen: dict[str, int] = {}
    kept = []
    for key, score in ranked:
        citekey = key[0]
        if seen.get(citekey, 0) >= limit:
            continue
        seen[citekey] = seen.get(citekey, 0) + 1
        kept.append((key, score))
        if len(kept) == k:
            break
    return kept


def _results(ranked: list, by_citekey: dict) -> list[PassageResult]:
    """The ranked keys resolved back to their passages.

    Re-reads each winner's sidecar rather than carrying prose through the
    index, which holds term counts only: the same trade the document path
    makes for its snippets, for the same reason -- a cache of every
    paragraph's text is the corpus a second time over, and only k of them
    are ever needed.

    That re-read is a *second* read of a file the index was built from, so
    a hit whose position no longer resolves is dropped rather than raised
    on. The fingerprint closes the ordinary window -- a rewritten sidecar
    changes size or mtime, so its entry is rebuilt before anything is
    ranked -- but it cannot close the one inside this call, where a
    re-parse lands between the ranking and this loop. A shrunk sidecar
    would then index out of range, and a search dying with a bare
    IndexError is a worse answer than a search returning the hits that are
    still there.
    """
    found = []
    for (citekey, i), score in ranked:
        current = passages.corpus_passages(citekey) or []
        if i >= len(current):
            continue
        passage = current[i]
        found.append(
            PassageResult(
                citekey=citekey,
                title=by_citekey[citekey]["title"],
                score=score,
                text=passage.text,
                page=passage.page,
                passage_index=i,
                label=passage.label,
            )
        )
    return found


def search_passages(query: str, k: int = 5, collection: str | None = None) -> PassageSearch:
    """Rank the corpus's paragraphs by BM25 relevance to `query`.

    `collection` restricts the result to items in that Zotero collection
    or one beneath it, filtered on the *ranking* rather than the index --
    exactly as `retrieval.search` does it, and for the same two reasons:
    narrowing the index would change every IDF, so a query would score
    differently depending on the filter, and one cache could not serve
    both.

    There is no `snippet_chars`. The text returned is the paragraph that
    scored, at its own length; choosing a window is what this unit exists
    not to do.

    Deterministic. Ties break on `(citekey, passage_index)`, and the cap
    keeps the highest-scoring passages rather than whichever iteration
    reached first -- both necessary rather than tidy, since per-process
    string hashing makes anything reading a `set`'s order a different
    answer run to run (`retrieval._windows`' docstring has the history).
    """
    terms = _query_terms(query)
    if not terms:
        return PassageSearch([], 0)

    with ledger.connection() as con:
        items = ledger.all_items(con)

    index, without_sidecar = retrieval_passages_cache.load_index(items)
    scores = retrieval_scoring.bm25_scores(index, terms)
    by_citekey = {item["citekey"]: item for item in items}
    if collection is not None:
        scores = {
            key: score
            for key, score in scores.items()
            if bib_collections.matches(bib_collections.of_row(by_citekey[key[0]]), collection)
        }
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return PassageSearch(_results(_capped(ranked, k), by_citekey), without_sidecar)
