"""Figure bitmaps rendered one at a time from the PDF, rather than held
until the parse ends.

Docling's own figure extraction keeps every crop on the document -- as a
PIL bitmap *and* as a base64 `data:` URI, so roughly 2.3x the PNG bytes
per picture -- and writes them only when `save_as_markdown` runs on the
last line of `_write_parse_outputs`. Peak memory therefore scaled with
how many figures a document has, not with what was being worked on:
**+8.95 GiB on one 99-page slide deck**, and at
`docling_image_scale = 6.0` it reached 74.31 GiB and then failed
outright on docling_core's own 20 MiB decoded-image guard (#600, #585).

Docling reports each picture's page and bounding box whether or not it
was asked to produce the bitmap, so the boxes are free. This module
takes them, renders each one from the PDF with pypdfium2, writes it, and
releases it before touching the next -- which drops the figure term to
**+0.02 GiB on the same deck, at 1.70x the speed**, because docling
renders a whole page at `images_scale` to crop from and this renders
only the box. docs/PERFORMANCE.md has the full table.

The crops are docling's crops: mean absolute channel difference 4.41/255
across paired figures, sizes within 2px, aspect ratios within 0.4% --
anti-aliasing and inset rounding, not geometry.

Deliberately not attempted: handing `save_as_markdown` an `ImageRef`
carrying a file `uri`. It calls `item.get_image()` -> `image.pil_image`,
which reads and decodes the file back, re-materialising exactly what
this avoids. `_docling_figures._inject_image_refs` writes the references
instead.
"""

import logging
from pathlib import Path

from chitragupta import logging_setup

logger = logging.getLogger("chitragupta.enrich.docling_parse")

# Written beside the .md in `<stem>_artifacts/`, indexed by the
# picture's position in `dl_doc.pictures`. Zero-padded so the directory
# sorts in document order, and *not* docling's
# `image_<index>_<sha256>.png`: the digest was of bitmap bytes docling
# held and this module never has all of at once. Nothing parses these
# names -- `<stem>.figures.json` is the index -- so the only requirement
# is that they are stable and unique per document.
_PICTURE_NAME = "picture_{index:06d}.png"


def crop_insets(bbox, page_width: float, page_height: float) -> tuple:
    """A docling bounding box as pdfium's `(left, bottom, right, top)`
    insets, measured inward from each page edge.

    The two libraries disagree about where y starts: docling's
    `CoordOrigin` is usually BOTTOMLEFT, but TOPLEFT boxes exist and
    measure downward from the top instead. Confusing them yields a
    plausibly-*sized* crop of the wrong region, which no count or
    file-size assertion would catch.

    So the conversion is docling's own `to_bottom_left_origin`, not
    arithmetic here. Re-deriving it would mean owning a second, subtly
    different copy of a rule that belongs upstream -- and this only has
    to be wrong once to mislocate a figure in a way a reader discovers
    and this suite does not. A bbox without the method (any test double)
    is read as BOTTOMLEFT, docling's default.
    """
    if hasattr(bbox, "to_bottom_left_origin"):
        bbox = bbox.to_bottom_left_origin(page_height)
    return (bbox.l, bbox.b, page_width - bbox.r, page_height - bbox.t)


def _render_one(page, bbox, scale: float, target: Path) -> None:
    """Render one box and write it, holding nothing afterwards.

    `close()` on both the bitmap and the PIL view, rather than letting
    them fall out of scope: `to_pil()` is a view onto pdfium's buffer, so
    dropping the Python names leaves the C allocation to whenever the GC
    runs. Measured during #600's benchmark -- relying on `del` alone cost
    +2.11 GiB on the deck against +0.02 GiB with explicit closes, which
    is the same accumulation this module exists to remove, merely one
    layer down.
    """
    width, height = page.get_size()
    bitmap = page.render(scale=scale, crop=crop_insets(bbox, width, height))
    image = bitmap.to_pil()
    try:
        image.save(target)
    finally:
        image.close()
        bitmap.close()


def _pictures_by_page(dl_doc, junk: "set | None" = None) -> dict:
    """{page_no: [(index, bbox), ...]} for every picture that has
    provenance, keyed so each page is opened once however many pictures
    sit on it -- a slide routinely carries tens.

    `junk` (from `_docling_figures.junk_picture_indices`) is filtered out
    here rather than in the caller, for two reasons. The caller sits at
    docs/CODE-STANDARDS.md's 25-statement ceiling exactly, so it has no
    room for a branch; and dropping a picture *before* the grouping means
    a page carrying nothing but logos is never opened at all, where
    filtering later would still pay to open and close it.
    """
    grouped: dict = {}
    for index, picture in enumerate(dl_doc.pictures):
        if junk and index in junk:
            continue
        if picture.prov:
            prov = picture.prov[0]
            grouped.setdefault(prov.page_no, []).append((index, prov.bbox))
    return grouped


def write_picture_crops(
    pdf_path, dl_doc, artifacts_dir: Path, scale: float, junk: "set | None" = None
) -> list:
    """Write one PNG per picture and return their names, in picture order.

    The returned list is always as long as `dl_doc.pictures`, with `None`
    wherever no image was written -- a picture docling gave no provenance
    for, one whose render failed, or (since #653) one `junk` names as not
    a figure at all. That positional correspondence is load-bearing:
    `_figure_records` pairs these against `dl_doc.pictures` by index, so a
    shortened list would point every later figure at its neighbour's
    image. A junk picture therefore keeps its slot and simply has no file
    in it, exactly like the other two cases -- the record is dropped where
    records are emitted, not here.

    Names are relative to the .md's own directory (`<stem>_artifacts/x.png`),
    which is what keeps `content/docling/` movable as a unit -- the same
    property `_relativise_image_refs` used to restore after docling wrote
    absolute paths.

    A picture that cannot be rendered is logged and skipped rather than
    raised: by the time this runs the document's text and every other
    figure are already correct, and failing here would discard a parse
    that succeeded. That is the same trade docling_core's decoded-size
    guard got wrong in #600, where 74 GiB of work was thrown away at the
    end.
    """
    names: list = [None] * len(dl_doc.pictures)
    grouped = _pictures_by_page(dl_doc, junk)
    if not grouped:
        return names

    import pypdfium2

    try:
        pdf = pypdfium2.PdfDocument(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 -- the figures, not the parse
        # docling and pdfium are different parsers, and this is the one
        # point where that matters: docling has already read this file
        # successfully, so a `PdfiumError` here means the two disagree
        # about it, not that the document is bad. The text and passages
        # are written by now and are worth keeping.
        logging_setup.say(
            logger,
            f"  WARNING pypdfium2 could not open {pdf_path} to crop "
            f"{len(dl_doc.pictures)} figure(s) from ({exc}) -- the parse itself "
            "succeeded and its text is kept; the figures are indexed without images.",
            level=logging.WARNING,
        )
        return names

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    try:
        for page_no in sorted(grouped):
            try:
                page = pdf[page_no - 1]
            except Exception as exc:  # noqa: BLE001 -- one page, not the parse
                logging_setup.say(
                    logger,
                    f"  WARNING could not open page {page_no} of {pdf_path} to crop "
                    f"{len(grouped[page_no])} figure(s) from ({exc}) -- their captions "
                    "are still indexed, without an image.",
                    level=logging.WARNING,
                )
                continue
            try:
                for index, bbox in grouped[page_no]:
                    filename = _PICTURE_NAME.format(index=index)
                    _render_one(page, bbox, scale, artifacts_dir / filename)
                    names[index] = f"{artifacts_dir.name}/{filename}"
            finally:
                page.close()
    finally:
        pdf.close()
    return names
