"""What a paper's figures are, for a drafting session that wants to
consider one -- `python -m chitragupta.draft figures <citekey>`.

**Why this exists at all.** `chitragupta/retrieval.py` indexes
`content/parsed/<citekey>.txt` and nothing else, so that file is the
whole of what a genre skill can read. Prose is in it; table cell text is
in it; decoded equations reach it too since #651, because a decoded
formula is LaTeX and LaTeX is text. A *bitmap* cannot be. Figures were
therefore the one modality with no route to the drafting stage rather
than a route that needed widening -- 8,769 crops and 497
`<stem>.figures.json` indexes existed on disk with no reader anywhere in
the repository.

**Consider, never replicate.** This hands back a caption, a page, a
citation string and a path. It is a *reading aid*: look at the figure to
ground a claim about what a paper shows, or to inform a diagram you are
drawing yourself. It is never an instruction to put someone else's image
in a draft. `docs/CONFIG.md`'s `docling_images` section states the
position -- having a paper in your library grants no right to reproduce
its figures -- and this implements it rather than revisiting it.

#627 measured and rejected vision captioning of figures because it would
have put generated text in the *corpus* layer, which may not call an LLM.
That does not bind this: a drafting-time reader writes nothing back, and
only the draft changes.

**The layer rule, in the direction that is easy to get wrong.**
AGENTS.md has the enrichment layer importing nothing from the drafting
or review layers. A drafting module importing `chitragupta.enrich` would
be the mirror-image violation, and would drag that layer's optional
dependencies into an ordinary drafting run. So `content/docling/` is read
here as a *path*, never through its writer -- exactly as
`chitragupta/passages.py`'s rung 1 already reads the passage sidecar
from the same directory. A test asserts the absence of that import,
because it is the kind of thing a later convenience edit adds without
noticing.
"""

import argparse
import json
import sys

from chitragupta import config, ledger
from chitragupta.progname import prog_for

# Said once, here, so the CLI and any other caller quote the same
# command. Naming the stage rather than the bare entry point matters: a
# full `python -m chitragupta.enrich` also runs embeddings and topic
# modelling, which is a much longer answer to "why can't I see the
# figures".
_NOT_ENRICHED = (
    "no figure index for {citekey} -- the enrichment layer's docling stage "
    "has not run for it. `python -m chitragupta.enrich --stages docling` "
    "writes one (and needs [enrich].docling_images on)."
)


def figures(citekey: str) -> "tuple[list | None, str | None]":
    """`(records, None)` for a citekey whose figure index exists, or
    `(None, reason)` for one whose does not.

    The two are deliberately different answers, and an empty list is the
    *first* of them: "this paper has no figures" and "nothing has looked
    at this paper yet" are only one word apart in English and nothing
    like each other in what they ask of the reader -- one is a fact about
    the paper, the other is a corpus-wide enrichment run they have not
    done. Collapsing both to `[]` would routinely send someone off to
    spend an hour on the wrong one.

    Raises `KeyError` for a citekey the ledger does not have, which is a
    third thing again -- almost always a typo, and the answer to it is
    never "run the enrichment layer".

    Each record gains `image_path`: the record stores a name relative to
    the `.md`'s own directory, which is what keeps `content/docling/`
    movable as a unit, and a caller handed that raw cannot open it
    without knowing so.
    """
    with ledger.connection() as con:
        row = con.execute("SELECT title FROM items WHERE citekey = ?", (citekey,)).fetchone()
    if row is None:
        raise KeyError(f"{citekey} is not in the ledger")

    index = config.DOCLING_DIR / f"{citekey}.figures.json"
    if not index.exists():
        return None, _NOT_ENRICHED.format(citekey=citekey)

    records = json.loads(index.read_text(encoding="utf-8"))
    for record in records:
        name = record.get("image")
        record["image_path"] = str(config.DOCLING_DIR / name) if name else None
    return records, None


def _print_human(citekey: str, records: list) -> None:
    """One block per figure. The citation string is printed first because
    it is the part that belongs in a draft -- the image path is the part
    that does not."""
    if not records:
        print(f"{citekey}: no figures recorded in its docling parse.")
        return
    print(f"{citekey}: {len(records)} figure(s).")
    for record in records:
        print(f"\n  {record['cite']}")
        if record.get("caption"):
            print(f"    caption: {record['caption']}")
        if record.get("image_path"):
            print(f"    image:   {record['image_path']}")


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        prog=f"{prog_for('draft')} figures",
        description=(
            "The figures of one synced paper: caption, page, the string to cite each by, "
            "and the crop to look at. A reading aid -- never reproduce a source figure "
            "in a draft."
        ),
    )
    parser.add_argument("citekey")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    try:
        records, reason = figures(args.citekey)
    except KeyError as exc:
        # Same shape as `retrieve evidence`'s refusal: named on stderr,
        # non-zero, because a citekey that does not exist is a caller
        # error and not a fact about the corpus.
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"citekey": args.citekey, "figures": records, "reason": reason}, indent=2))
    elif reason:
        print(reason)
    else:
        _print_human(args.citekey, records)
    # Zero either way once the citekey is real: "not enriched yet" and "no
    # figures" are both true answers about the corpus, and this layer's
    # read-only lookups never fail a caller for what the corpus contains.
    return 0


# Deliberately no `if __name__ == "__main__"` block. The drafting layer is
# one entry point one level deep -- `python -m chitragupta.draft figures`
# -- and no module beside `draft.py` carries one, so `python -m
# chitragupta.draft_figures` imports this and exits 0 without doing
# anything. docs/ARCHITECTURE.md states the invariant and
# tests/test_draft_entrypoint.py enforces it per module.
