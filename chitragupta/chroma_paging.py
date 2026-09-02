"""Reading a whole Chroma collection without asking SQLite for too much.

A Chroma `get` is answered by its SQLite backend in two steps: find the
matching rows, then re-fetch them with an `IN (?, ?, ...)` list holding
**one bound variable per returned row**. Past SQLite's
`SQLITE_MAX_VARIABLE_NUMBER` -- 32766 since 3.32 -- the statement is
rejected outright, and the caller gets `(code: 1) too many SQL variables`
rather than a short result. So the ceiling is on how many rows a `get`
may *return*, not on how many arguments the caller passes: a call naming
no ids at all still trips it, once the collection is big enough.

That is issue #581. `chitragupta/enrich/embed_index.py`'s orphan prune
read the whole collection in one `get`, so `chitragupta corpus enrich`
died at the end of every run on a corpus past 32766 chunks -- measured on
a real one at 41050, after all the embedding work was already done and
with no orphans to remove. `chitragupta/overlap_chroma.py`'s
`absent_citekeys` had the same shape, reachable by a draft citing enough
sources.

A separate module, and not a private helper inside either caller, for two
reasons. The page size is a rule about SQLite that both of them have to
agree on, and a copy in each is how two call sites start disagreeing
about what is safe -- the same argument that already has `overlap_chroma`
asking `embed_index` for the collection name rather than recomputing it.
And it belongs to neither layer: it imports nothing, takes the collection
as an argument, and so is readable by tier 3 of the overlap scan without
the `enrich` Poetry group installed, the property
`chitragupta/overlap_chroma.py`'s docstring exists to protect.
"""

__all__ = ["PAGE_SIZE", "all_rows"]

# Well under the 32766 ceiling rather than at it: the limit is measured
# in bound variables and this is measured in rows, and the two are only
# equal for as long as a row costs exactly one variable -- a fact about
# Chroma's current query shape, not a promise it makes.
PAGE_SIZE = 10_000


def all_rows(collection, **criteria) -> dict:
    """Every `(id, metadata)` pair in `collection` matching `criteria`,
    fetched a page at a time.

    `criteria` is passed to `collection.get` unchanged -- `where`,
    `include`, whatever the caller needs -- with `limit` and `offset`
    added. Returns `{"ids": [...], "metadatas": [...]}`, positionally
    aligned, which is all either caller reads; `documents` and
    `embeddings` are deliberately not accumulated, since holding a whole
    corpus of chunk text in memory is the other way to make a large
    collection fail.

    **The caller must finish reading before it deletes anything.** Both
    callers here compute a whole list and then act on it, and that is not
    incidental: `offset` counts surviving rows, so deleting inside the
    loop shifts every later row left past the offset and silently skips
    exactly as many as were removed -- and for the prune those skipped
    rows are the orphans the loop is looking for.
    """
    ids: list[str] = []
    metadatas: list[dict] = []
    offset = 0
    while True:
        page = collection.get(**criteria, limit=PAGE_SIZE, offset=offset)
        if not page["ids"]:
            return {"ids": ids, "metadatas": metadatas}
        ids += page["ids"]
        metadatas += page["metadatas"]
        # By what came back, not by what was asked for. chromadb 1.5.9
        # answers with a full page until the last one, so the two agree
        # today -- but nothing in its contract promises that, and a
        # backend that returns 2 rows to a request for 3 is not saying it
        # has run out. Advancing by `PAGE_SIZE` there steps over exactly
        # the rows it withheld, and hands the caller a partial collection
        # it has no way to notice (Copilot, #583).
        offset += len(page["ids"])
