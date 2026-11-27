"""Figure bitmaps rendered one at a time from the PDF, rather than held
until the parse ends.

Docling holds every crop (as PIL *and* base64) until `save_as_markdown`,
so peak memory scaled with figure count: +8.95 GiB on one 99-page deck,
and a failure on docling_core's 20 MiB image guard at scale 6.0 (#600,
#585). The boxes are free, so this renders each from the PDF with
pypdfium2 and releases it: +0.02 GiB at 1.70x the speed, with crops
matching docling's (docs/PERFORMANCE.md). Handing `save_as_markdown` an
`ImageRef` with a file `uri` does not work: it decodes the file back.
"""

import logging
import shutil
from pathlib import Path

from chitragupta import logging_setup

logger = logging.getLogger("chitragupta.enrich.docling_parse")

# Zero-padded picture index, so the directory sorts in document order;
# not docling's sha256 name, since the whole bitmap is never held.
# `<stem>.figures.json` is the index, so names need only be stable.
_PICTURE_NAME = "picture_{index:06d}.png"


def crop_insets(bbox, page_width: float, page_height: float) -> tuple:
    """A docling bounding box as pdfium's `(left, bottom, right, top)`
    insets, measured inward from each page edge.

    Uses docling's own `to_bottom_left_origin`: TOPLEFT boxes exist, and
    re-deriving the rule would yield plausibly-sized crops of the wrong
    region that no test catches. A bbox without the method (any test
    double) is read as BOTTOMLEFT.
    """
    if hasattr(bbox, "to_bottom_left_origin"):
        bbox = bbox.to_bottom_left_origin(page_height)
    return (bbox.l, bbox.b, page_width - bbox.r, page_height - bbox.t)


def _render_one(page, bbox, scale: float, target: Path) -> None:
    """Render one box and write it, holding nothing afterwards.

    Explicit `close()`: `to_pil()` views pdfium's C buffer, and `del`
    alone cost +2.11 GiB on the #600 deck.
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
    provenance, so each page is opened once.

    `junk` is filtered before grouping, so a page of only logos is never
    opened (and the caller is at the 25-statement ceiling).
    """
    grouped: dict = {}
    for index, picture in enumerate(dl_doc.pictures):
        if junk and index in junk:
            continue
        if picture.prov:
            prov = picture.prov[0]
            grouped.setdefault(prov.page_no, []).append((index, prov.bbox))
    return grouped


def _clear_artifacts_dir(artifacts_dir: Path) -> None:
    """Drop a document's previous crops before writing this run's.

    Crops are named by index, so a re-parse with fewer pictures would
    leave stale ones (as with `passages.clear_sidecar`); clearing up front
    also makes a zero-picture re-parse land on "no artifacts". Only
    `FileNotFoundError` is ignored: a stale crop set is the failure this
    prevents.
    """
    try:
        shutil.rmtree(artifacts_dir)
    except FileNotFoundError:
        pass


def _open_pdf(pdf_path, num_pictures: int) -> "object | None":
    """The pdfium handle to crop from, or None with a warning logged."""
    import pypdfium2

    try:
        return pypdfium2.PdfDocument(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 -- the figures, not the parse
        # docling read this file fine, so a `PdfiumError` means the two
        # parsers disagree, not that the document is bad: keep the text.
        logging_setup.say(
            logger,
            f"  WARNING pypdfium2 could not open {pdf_path} to crop "
            f"{num_pictures} figure(s) from ({exc}) -- the parse itself "
            "succeeded and its text is kept; the figures are indexed without images.",
            level=logging.WARNING,
        )
        return None


def write_picture_crops(
    pdf_path, dl_doc, artifacts_dir: Path, scale: float, junk: "set | None" = None
) -> list:
    """Write one PNG per picture and return their names, in picture order.

    Always as long as `dl_doc.pictures`, with `None` where no image was
    written (no provenance, a failed render, or junk, #653):
    `_figure_records` pairs by index, so a shortened list would point
    figures at their neighbours' images. Names are relative to the .md,
    keeping `content/docling/` movable. A render failure is logged, not
    raised, so a successful parse isn't discarded (unlike #600).
    """
    names: list = [None] * len(dl_doc.pictures)
    _clear_artifacts_dir(artifacts_dir)
    grouped = _pictures_by_page(dl_doc, junk)
    if not grouped:
        return names

    pdf = _open_pdf(pdf_path, len(dl_doc.pictures))
    if pdf is None:
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
