"""Figure bitmaps and the citation string for each one: rewriting
Docling's absolute image references to relative ones, and building the
per-figure record `<stem>.figures.json` publishes.

Split from `chitragupta/enrich/docling_parse.py` (#441). Self-contained:
takes a `CorpusDoc` and Docling's own document object, never anything
from `docling_parse.py` itself, so the dependency runs one way.
"""

import re
from pathlib import Path

from chitragupta.enrich.corpus import CorpusDoc

# Leading "Figure 3." / "Fig. 1.1" / "Table 2:" in a caption -- the
# paper's *own* numbering, which is the only trustworthy source for it.
# Docling's picture order can't stand in: publisher logos and licence
# badges are pictures too (3 of the first 3 on a real MDPI paper), so
# the Nth picture is routinely not the paper's Figure N.
#
# The number has to be captured whole. Chapter-scoped numbering ("Fig.
# 1.1" ... "Fig. 1.4", the convention in every edited book chapter in
# this corpus) and sub-figures ("Figure 2a") are both common, and
# matching only the leading integer collapses all four of that chapter's
# distinct figures onto a single "Fig 1" -- a citation that points at
# the wrong picture, which is worse than declining to number it.
_CAPTION_LABEL_RE = re.compile(
    r"^\s*(Figure|Fig\.?|Table|Scheme)\s*(\d+(?:\.\d+)*[a-z]?)\b", re.IGNORECASE
)

_IMAGE_REF_RE = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")


def _relativise_image_refs(md_path: Path) -> list[str]:
    """Rewrite the .md's image references to be relative to the .md, and
    return them in document order.

    Docling's `save_as_markdown` writes *absolute* paths, which bakes this
    host's directory layout into every file -- moving `content/docling/`,
    or generating it in a container and reading it elsewhere, breaks all
    of them. Relative refs keep the .md and its `_artifacts/` directory
    movable as a unit.

    The returned names are also what `_figure_records` records for each
    picture: the document's own `pic.image.uri` is a `data:` URI carrying
    the whole PNG base64-encoded, and `save_as_markdown` does not rewrite
    it, so the markdown is the only place the written filename appears.
    """
    text = md_path.read_text(encoding="utf-8")
    base = md_path.parent
    names: list[str] = []

    def rewrite(match) -> str:
        target = match.group(2)
        path = Path(target)
        if path.is_absolute():
            try:
                # as_posix(), not str(): a Markdown image reference is a
                # URL-ish path and must use forward slashes. On Windows
                # str() yields "dir\image.png", which is not a valid
                # reference anywhere -- including on the Windows box that
                # produced it -- and would make content/docling/ readable
                # only on the platform it was generated on.
                target = path.relative_to(base).as_posix()
            except ValueError:
                # Somewhere outside the .md's own tree -- leave it alone
                # rather than emit a fragile chain of `../`.
                pass
        names.append(target)
        return match.group(1) + target + match.group(3)

    md_path.write_text(_IMAGE_REF_RE.sub(rewrite, text), encoding="utf-8")
    return names


def _figure_records(doc: CorpusDoc, dl_doc, image_names: list[str] | None = None) -> list[dict]:
    """One record per extracted picture: where it sits in the source, and
    the exact string to cite it by.

    Deliberately produces a *textual* citation, never an instruction to
    reproduce the image -- see DEVELOPER.md's "Figures and copyright".
    A figure whose caption carries no number is cited by page, rather
    than by a number this module would otherwise have to invent.

    `image_names` pairs positionally with `dl_doc.pictures` (both are in
    document order). A count mismatch means that assumption broke, so
    every record drops the filename rather than risk pointing a figure at
    someone else's image.
    """
    if image_names is not None and len(image_names) != len(dl_doc.pictures):
        image_names = None
    records = []
    for index, pic in enumerate(dl_doc.pictures):
        caption = (pic.caption_text(dl_doc) or "").strip()
        page = pic.prov[0].page_no if pic.prov else None
        records.append(
            {
                "page": page,
                "caption": caption or None,
                "cite": _figure_cite(doc.citekey, caption, page),
                "image": image_names[index] if image_names else None,
            }
        )
    return records


def _figure_cite(citekey: str, caption: str, page: "int | None") -> str:
    """The exact string a draft cites one figure by.

    A numbered caption is cited by its own number; an unnumbered one by
    page; a figure with neither is named as unplaced rather than given a
    number this module would otherwise have to invent.
    """
    ref = f"[@{citekey}]"
    label_match = _CAPTION_LABEL_RE.match(caption)
    if label_match:
        kind = label_match.group(1).rstrip(".")
        # "Fig"/"Fig." -> "Figure", so the citation reads the way a
        # reader would write it, rather than echoing the source's
        # abbreviation into the middle of a sentence.
        kind = "Figure" if kind.lower().startswith("fig") else kind.capitalize()
        return f"{kind} {label_match.group(2)} of {ref}" + (f", p.{page}" if page else "")
    if page:
        return f"the figure on p.{page} of {ref}"
    return f"an unplaced figure in {ref}"
