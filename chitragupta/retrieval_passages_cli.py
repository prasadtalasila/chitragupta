"""`retrieve search --unit passage`: printing a passage ranking (#769).

The library is `chitragupta/retrieval_passages.py`. `retrieval_cli.py`
imports this lazily so the default `--unit document` path never pays to
import a ranker it will not call.
"""

from chitragupta import retrieval_passages


def _print_passages(found) -> int:
    """One block per hit. Returns the payload size in characters.

    The page is printed because a `search` snippet cannot carry one; a
    passage with no recorded page falls back to its reading position.
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

    A citekey with no passage sidecar is absent from the index, so without
    this the result reads as "the corpus has nothing on that".
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
