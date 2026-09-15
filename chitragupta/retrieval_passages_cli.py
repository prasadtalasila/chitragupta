"""`retrieve search --unit passage`: printing a passage ranking (#769).

The same split `chitragupta/retrieval.py` and
`chitragupta/retrieval_cli.py` already have, one unit over: the library
is `chitragupta/retrieval_passages.py`, and this is what a terminal sees.
Its own module because `retrieval_cli.py` crossed
docs/CODE-STANDARDS.md's 250-line C2 limit when this was inside it -- a
split the change forced rather than one chosen, which is why it is in the
same PR.

`retrieval_cli.py` imports this lazily, inside `_run_search`, rather than
at the top of the file. Not the circular-import dance
`retrieval.py.__getattr__` documents -- nothing here is imported back --
but the same instinct about cost: `--unit document` is the default and
every genre skill's path, and it should not pay to import a ranker it
will not call.
"""

from chitragupta import retrieval_passages


def _print_passages(found) -> int:
    """One block per hit. Returns the payload size in characters.

    The page is printed where the document unit prints nothing, because
    it is the half of this unit a caller cannot get any other way: a
    `search` snippet is a character window cut out of flattened text, and
    no page survives the flattening. A passage with no recorded page
    falls back to its reading position, which is at least a stable
    handle on the same paragraph.
    """
    chars = 0
    for result in found.results:
        chars += len(result.text)
        where = f"p.{result.page}" if result.page else f"passage {result.passage_index}"
        print(f"\n{result.citekey}  (score {result.score:.1f}, {where})")
        print(f"  {result.title}")
        print(f"  {result.text}")
    return chars


def _note_unreachable_sources(count: int) -> None:
    """Say how many parsed sources this unit structurally cannot return.

    Not a remark about this query. A citekey whose parse left no passage
    sidecar is absent from the index entirely, however well it matches,
    so without this the result reads as "the corpus has nothing on that"
    when what happened is "a fifth of your corpus was never eligible".
    """
    if count:
        print(
            f"\n  [note] {count} parsed source(s) have no passage sidecar and "
            "cannot appear here at all. `--unit document` searches them; "
            '`[parser].backend = "docling"` plus a re-sync gives them one.'
        )


def run(args) -> "tuple[int, int]":
    """Print the passage ranking for `args`; return (results, chars)."""
    found = retrieval_passages.search_passages(args.query, k=args.k, collection=args.collection)
    if not found.results:
        print("No results.")
    chars = _print_passages(found)
    _note_unreachable_sources(found.without_sidecar)
    if found.results:
        print(
            "\n  Each hit is the paragraph that scored, verbatim -- judge it "
            "yourself. A high score means your words are in that paragraph, not "
            "that it supports your claim."
        )
    return len(found.results), chars
