"""What a paper's figures are, for a drafting session that wants to
consider one -- `python -m chitragupta.draft figures <citekey>`.

Retrieval reads only parsed text, and a bitmap cannot be text, so figure
indexes had no reader. **Consider, never replicate:** this returns a
caption, page, citation string and path as a reading aid; a source
figure is never put in a draft (docs/CONFIG.md, `docling_images`).
#627's rejection of vision captioning bound the corpus layer, not this.

`content/docling/` is read as a path, never through `chitragupta.enrich`,
which would drag the optional stack into drafting; a test asserts the
import stays absent.
"""

import json
import sys

from chitragupta import config, ledger
from chitragupta.citekey_safety import citekey_path
from chitragupta.progname import prog_for
from chitragupta.help_format import ClickParser

# Names the stage: a full `python -m chitragupta.enrich` is a much longer
# answer to "why can't I see the figures".
_NOT_ENRICHED = (
    "no figure index for {citekey} -- the enrichment layer's docling stage "
    "has not run for it. `python -m chitragupta.enrich --stages docling` "
    "writes one (and needs [enrich].docling_images on)."
)


class FigureIndexError(ValueError):
    """A figure index names an image outside `content/docling/`.

    Raised, not skipped or rewritten (issue 875): a tampered index once
    offered any host file as a figure. Refusing says the index is not
    what enrich wrote; the remedy is re-running the docling stage.
    """


def _image_path(name: str, citekey: str) -> str:
    """`name` joined under `content/docling/`, once it is certain it
    lands there.

    Where it lands is the rule, not its shape (real names have two
    components). Resolution errors and symlink loops are refusals.
    """
    path = config.DOCLING_DIR / name
    try:
        inside = config.resolves_inside(path, config.DOCLING_DIR)
    except (OSError, ValueError):
        inside = False
    if not inside:
        raise FigureIndexError(
            f"{citekey}.figures.json names the image {name!r}, which lands outside "
            f"{config.DOCLING_DIR}. The index is not what the enrichment layer "
            f"wrote; re-run `python -m chitragupta.enrich --stages docling` for "
            f"{citekey} rather than trusting it."
        )
    return str(path)


def figures(citekey: str) -> "tuple[list | None, str | None]":
    """`(records, None)` for a citekey whose figure index exists, or
    `(None, reason)` for one whose does not.

    "No figures" (`[]`) and "not enriched yet" ask different things of
    the reader, so they stay distinct. Raises `KeyError` for a citekey not
    in the ledger, and `FigureIndexError` for an untrustworthy index.
    Each record gains `image_path`, since the stored name is relative to
    the `.md`'s directory.
    """
    with ledger.reading() as con:
        row = con.execute("SELECT title FROM items WHERE citekey = ?", (citekey,)).fetchone()
    if row is None:
        raise KeyError(f"{citekey} is not in the ledger")

    index = citekey_path(config.DOCLING_DIR, citekey, ".figures.json")
    if not index.exists():
        return None, _NOT_ENRICHED.format(citekey=citekey)

    records = json.loads(index.read_text(encoding="utf-8"))
    for record in records:
        name = record.get("image")
        record["image_path"] = _image_path(name, citekey) if name else None
    return records, None


def _print_human(citekey: str, records: list) -> None:
    """One block per figure, the citation string first: it belongs in a
    draft, the image path does not."""
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
    parser = ClickParser(
        prog=f"{prog_for('draft')} figures",
        description=(
            "The figures of one synced paper: caption, page, the string to cite each by, "
            "and the crop to look at. A reading aid: a draft never reproduces a source "
            "figure, except a verbatim digest, which may place the crop beside the run "
            "it belongs to (docs/VERBATIM-DIGEST.md)."
        ),
    )
    parser.add_argument("citekey")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    try:
        records, reason = figures(args.citekey)
    except KeyError as exc:
        # A caller error, not a fact about the corpus.
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except FigureIndexError as exc:
        # Nothing on stdout: `--json` must not get a half-trusted list.
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"citekey": args.citekey, "figures": records, "reason": reason}, indent=2))
    elif reason:
        print(reason)
    else:
        _print_human(args.citekey, records)
    # Zero either way: "not enriched" and "no figures" are true answers;
    # read-only lookups never fail a caller for what the corpus contains.
    return 0


# No `__main__` block: `python -m chitragupta.draft figures` is the entry
# (docs/ARCHITECTURE.md; tests/test_draft_entrypoint.py).
