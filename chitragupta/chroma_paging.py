"""Reading a whole Chroma collection without asking SQLite for too much.

Chroma's SQLite backend re-fetches matches with one bound variable per
*returned* row, so a `get` returning more than 32766 rows fails with
"too many SQL variables", even with no ids passed (#581: enrich died at
the end of every run on a 41050-chunk corpus). One module, so both
callers agree on the page size; it imports nothing, so tier 3 can use it
without the `enrich` extra.
"""

__all__ = ["PAGE_SIZE", "all_rows"]

# Well under the ceiling: a row costs one variable only in Chroma's
# current query shape, which it does not promise.
PAGE_SIZE = 10_000


def all_rows(collection, **criteria) -> dict:
    """Every `(id, metadata)` pair in `collection` matching `criteria`,
    fetched a page at a time.

    Returns `{"ids", "metadatas"}` only: accumulating documents or
    embeddings is the other way to fail on a large collection.

    **Finish reading before deleting anything:** `offset` counts surviving
    rows, so deleting inside the loop skips exactly the rows removed.
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
        # Advance by what came back: a short page does not mean the end,
        # and stepping by PAGE_SIZE would skip withheld rows (#583).
        offset += len(page["ids"])
