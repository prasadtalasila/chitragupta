"""Figure bitmaps and the citation string for each one: referencing the
crops `_docling_crops` wrote from the .md, and building the per-figure
record `<stem>.figures.json` publishes.

Split from `chitragupta/enrich/docling_parse.py` (#441). Self-contained:
takes a `CorpusDoc` and Docling's own document object, never anything
from `docling_parse.py` itself, so the dependency runs one way -- and it
now depends on `_docling_crops` in the same direction, which is why the
whole images-on write lives here rather than in the caller's branch.

Until #600 this module *rewrote* references Docling itself had written,
as absolute paths, after `save_as_markdown` materialised every bitmap it
had been holding. Docling is no longer asked for the bitmaps at all, so
there are no absolute paths to repair: the references are written from
names that were relative to begin with.
"""

import json
import logging
import re
from pathlib import Path

from chitragupta import config, logging_setup
from chitragupta.enrich._docling_crops import write_picture_crops
from chitragupta.enrich.corpus import CorpusDoc

logger = logging.getLogger("chitragupta.enrich.docling_parse")

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

# The marker `export_to_markdown()` leaves where a picture sits. Same
# shape as embed_text.strip_image_refs' own pattern, and anchored per
# line for the same reason: a placeholder is always a line of its own,
# and matching mid-line would rewrite prose that merely mentions one.
_IMAGE_PLACEHOLDER_RE = re.compile(r"^[ \t]*<!--\s*image\s*-->[ \t]*$", re.MULTILINE)


def _inject_image_refs(md_path: Path, names: list) -> list:
    """Point each `<!-- image -->` placeholder at the PNG written for it,
    and return the names that ended up in the markdown.

    `export_to_markdown()` leaves one placeholder per picture, in
    document order, because `_docling_crops` deliberately never asks
    docling to produce the bitmaps (#600) -- so the references are
    written here rather than rewritten afterwards. `names` comes
    straight from `write_picture_crops` and is already relative to this
    .md's own directory, which is what keeps `content/docling/` movable
    as a unit; there is no absolute path to repair any more, and none of
    the platform-specific separator trouble that came with one.

    A `None` name keeps its placeholder: a picture docling gave no
    provenance for, or one whose render failed, has no file to point at.
    `embed_text.strip_image_refs` already removes both forms.

    **A count disagreement drops every name** rather than pairing a
    figure with someone else's image, which is the same trade
    `_figure_records` makes on the same suspicion. The counts come from
    two different docling surfaces -- `len(dl_doc.pictures)` and the
    placeholders `export_to_markdown()` emitted -- so they agreeing is
    an assumption about the library, not an invariant of this code.
    """
    text = md_path.read_text(encoding="utf-8")
    placeholders = list(_IMAGE_PLACEHOLDER_RE.finditer(text))
    if len(placeholders) != len(names):
        logging_setup.say(
            logger,
            f"  WARNING {md_path.name} has {len(placeholders)} image placeholder(s) for "
            f"{len(names)} picture(s) -- leaving them unreferenced rather than risk "
            "pointing a figure at another figure's image.",
            level=logging.WARNING,
        )
        return [None] * len(names)

    # Right to left, so each replacement leaves the earlier matches'
    # offsets untouched.
    for match, name in reversed(list(zip(placeholders, names))):
        if name is not None:
            text = f"{text[: match.start()]}![Image]({name}){text[match.end() :]}"
    md_path.write_text(text, encoding="utf-8")
    return list(names)


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


def write_figure_outputs(doc: CorpusDoc, dl_doc, md_path: Path, figures_path: Path) -> None:
    """Everything the images-on setting adds to a parse: the crops, the
    references to them in the .md the caller has already written, and the
    `<stem>.figures.json` index.

    Here rather than in `docling_parse._write_parse_outputs` because all
    three steps are about figures and none is about parsing -- and
    because the ordering between them matters (crops first, so their
    names exist to reference; references before the index, so the index
    records what the markdown actually points at), which is easier to
    keep right in one place than spread across a caller's branch.

    Never writes the markdown *body*: `save_as_markdown` is what
    materialises every bitmap docling has been holding, which is the
    whole of #600, and it re-decodes any file an `ImageRef` points at, so
    it cannot be used even to reference crops already on disk.
    """
    image_names = _inject_image_refs(
        md_path,
        write_picture_crops(
            doc.pdf_path,
            dl_doc,
            md_path.parent / f"{md_path.stem}_artifacts",
            config.DOCLING_IMAGE_SCALE,
        ),
    )
    figures_path.write_text(
        json.dumps(_figure_records(doc, dl_doc, image_names), indent=2), encoding="utf-8"
    )
