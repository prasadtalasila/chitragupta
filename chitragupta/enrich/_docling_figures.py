"""Figure bitmaps and the citation string for each one: referencing the
crops `_docling_crops` wrote from the .md, and building the per-figure
record `<stem>.figures.json` publishes.
"""

import json
import logging
import re
from pathlib import Path

from chitragupta import config, logging_setup
from chitragupta.enrich._docling_crops import write_picture_crops
from chitragupta.enrich.corpus import CorpusDoc

logger = logging.getLogger("chitragupta.enrich.docling_parse")

# Leading "Figure 3." / "Fig. 1.1" / "Table 2:": the paper's *own*
# numbering is the only trustworthy source (logos are pictures too, so
# the Nth picture is not Figure N). Captured whole: chapter-scoped
# numbers and sub-figures are common, and the leading integer alone
# would cite the wrong picture.
_CAPTION_LABEL_RE = re.compile(
    r"^\s*(Figure|Fig\.?|Table|Scheme)\s*(\d+(?:\.\d+)*[a-z]?)\b", re.IGNORECASE
)

# Below this on *either* side, a caption-less picture is not a figure.
# In page points, so editing `docling_image_scale` doesn't reclassify the
# corpus (200px at scale 6.0, about half an inch). A conjunction, not a
# size threshold: over 8,769 crops, 6.4% were small captioned figures and
# 11.8% large uncaptioned ones; the 38.5% small uncaptioned dropped here
# are ORCID icons, journal badges and glyphs.
_MIN_FIGURE_POINTS = 33.0

# The `export_to_markdown()` picture placeholder, anchored per line like
# embed_text.strip_image_refs, so prose mentioning one is not rewritten.
_IMAGE_PLACEHOLDER_RE = re.compile(r"^[ \t]*<!--\s*image\s*-->[ \t]*$", re.MULTILINE)


def _inject_image_refs(md_path: Path, names: list) -> list:
    """Point each `<!-- image -->` placeholder at the PNG written for it,
    and return the names that ended up in the markdown.

    A `None` name keeps its placeholder. **A count disagreement drops
    every name** rather than pair a figure with another's image: the two
    counts come from different docling surfaces, so agreement is an
    assumption about the library.
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

    # Right to left, so earlier matches' offsets stay valid.
    for match, name in reversed(list(zip(placeholders, names))):
        if name is not None:
            text = f"{text[: match.start()]}![Image]({name}){text[match.end() :]}"
    md_path.write_text(text, encoding="utf-8")
    return list(names)


def _bbox_of(pic) -> "tuple | None":
    """`(l, t, r, b)` for a picture docling gave provenance for, else
    `None`.
    """
    if not pic.prov:
        return None
    bbox = pic.prov[0].bbox
    return (bbox.l, bbox.t, bbox.r, bbox.b)


def junk_picture_indices(dl_doc) -> set:
    """Indices of the pictures that are not figures: caption-less *and*
    under `_MIN_FIGURE_POINTS` on either side.

    Computed once, so crops and records cannot disagree. A picture with
    no provenance is never junk: it stays in the index as "unplaced".
    """
    junk = set()
    for index, pic in enumerate(dl_doc.pictures):
        if (pic.caption_text(dl_doc) or "").strip():
            continue
        bbox = _bbox_of(pic)
        if bbox is None:
            continue
        left, top, right, bottom = bbox
        if abs(right - left) < _MIN_FIGURE_POINTS or abs(top - bottom) < _MIN_FIGURE_POINTS:
            junk.add(index)
    return junk


def _figure_records(
    doc: CorpusDoc, dl_doc, image_names: "list[str] | None" = None, junk: "set | None" = None
) -> list[dict]:
    """One record per extracted picture: where it sits in the source, and
    the exact string to cite it by.

    A *textual* citation, never an instruction to reproduce the image
    (DEVELOPER.md's "Figures and copyright"). `image_names` pairs by index
    with `dl_doc.pictures`; on a count mismatch every record drops the
    filename. `junk` (#653) is filtered here, at emission, never by
    compacting `image_names`, which would misalign every later figure.
    """
    if image_names is not None and len(image_names) != len(dl_doc.pictures):
        image_names = None
    records = []
    for index, pic in enumerate(dl_doc.pictures):
        if junk and index in junk:
            continue
        caption = (pic.caption_text(dl_doc) or "").strip()
        page = pic.prov[0].page_no if pic.prov else None
        bbox = _bbox_of(pic)
        records.append(
            {
                "page": page,
                "caption": caption or None,
                "cite": _figure_cite(doc.citekey, caption, page),
                "image": image_names[index] if image_names else None,
                # Page points only, not pixels: pdfium's inset-based size
                # differs by 1-2px, and pixels are derivable as bbox x
                # [enrich].docling_image_scale.
                "bbox": list(bbox) if bbox else None,
            }
        )
    return records


def _figure_cite(citekey: str, caption: str, page: "int | None") -> str:
    """The exact string a draft cites one figure by.

    Never a number this module would have to invent: unnumbered captions
    are cited by page, and a figure with neither is named as unplaced.
    """
    ref = f"[@{citekey}]"
    label_match = _CAPTION_LABEL_RE.match(caption)
    if label_match:
        kind = label_match.group(1).rstrip(".")
        # "Fig"/"Fig." -> "Figure", as a reader would write it.
        kind = "Figure" if kind.lower().startswith("fig") else kind.capitalize()
        return f"{kind} {label_match.group(2)} of {ref}" + (f", p.{page}" if page else "")
    if page:
        return f"the figure on p.{page} of {ref}"
    return f"an unplaced figure in {ref}"


def write_figure_outputs(doc: CorpusDoc, dl_doc, md_path: Path, figures_path: Path) -> None:
    """Everything the images-on setting adds to a parse: the crops, the
    references to them in the .md the caller has already written, and the
    `<stem>.figures.json` index, in that order.

    Never writes the markdown *body*: `save_as_markdown` materialises
    every bitmap (#600) and re-decodes any `ImageRef` file.
    """
    # Once, and shared: neither crop nor record is written for junk.
    junk = junk_picture_indices(dl_doc)
    image_names = _inject_image_refs(
        md_path,
        write_picture_crops(
            doc.pdf_path,
            dl_doc,
            md_path.parent / f"{md_path.stem}_artifacts",
            config.DOCLING_IMAGE_SCALE,
            junk,
        ),
    )
    figures_path.write_text(
        json.dumps(_figure_records(doc, dl_doc, image_names, junk), indent=2), encoding="utf-8"
    )
