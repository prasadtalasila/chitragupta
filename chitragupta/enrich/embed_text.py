"""How a document's raw text is fetched, cleaned, and split for an embedder.

Split out of `chitragupta/enrich/embed_index.py` when a #503/#504 fix pushed
that module past docs/CODE-STANDARDS.md's 250-line ceiling. The boundary
is real, not arithmetic: everything here answers "what text does this
document offer an embedder", independent of Chroma or any particular
model -- `chitragupta/enrich/doc_vectors.py` needs exactly this half without
the collection-management half, which is why it already called these
functions through `embed_index` rather than duplicating them. Re-exported
from `embed_index.py` (imported there, not just used) so every existing
`embed_index.hash_text`/`.get_text`/`.chunk_text`/`.strip_image_refs`
call -- inside and outside this package -- keeps working unchanged.
"""

import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path

from chitragupta import config
from chitragupta.enrich.corpus import CorpusDoc


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def strip_image_refs(markdown: str) -> str:
    """Drop Docling's image markers from text on its way to the embedder.

    Two forms, depending on config.DOCLING_IMAGES: a bare `<!-- image -->`
    placeholder, or a real `![Image](<stem>_artifacts/image_000000_<64 hex
    chars>.png)` reference. Neither carries meaning an embedding can use,
    and the second is worse than the first: chunk_text() splits on
    whitespace, so a ~100-character path hashes down to a single "word"
    that displaces real text from a 200-word chunk.

    Captions survive deliberately -- Docling emits them as their own
    text items ("Figure 3. Sensor placement..."), not as the image's alt
    text, so they're real prose about the figure and worth embedding.
    """
    without_refs = re.sub(r"^[ \t]*!\[[^\]]*\]\([^)]*\)[ \t]*$", "", markdown, flags=re.MULTILINE)
    without_placeholders = re.sub(
        r"^[ \t]*<!--\s*image\s*-->[ \t]*$", "", without_refs, flags=re.MULTILINE
    )
    # Collapse the blank runs those deletions leave behind, so chunking
    # doesn't see paragraph gaps where a figure used to sit.
    return re.sub(r"\n{3,}", "\n\n", without_placeholders)


def get_text(doc: CorpusDoc) -> str | None:
    """Best available text for a doc: Docling output > existing parsed text
    > on-the-fly pdftotext. Doesn't require the Docling stage to have run."""
    docling_path = config.DOCLING_DIR / f"{doc.citekey}.md"
    if docling_path.exists():
        return strip_image_refs(docling_path.read_text(encoding="utf-8"))
    if doc.text_path and Path(doc.text_path).exists():
        return Path(doc.text_path).read_text(encoding="utf-8")
    if doc.pdf_path:
        # mkstemp with the descriptor closed at once, and a manual unlink
        # in finally -- deliberately *not* a NamedTemporaryFile `with`
        # block wrapped around the subprocess call. On Windows an open
        # handle keeps the file exclusively locked, and pdftotext writing
        # to that same path while Python still holds it open fails with
        # PermissionError -- POSIX allows a second open of the same path,
        # which is why this only surfaced on this repo's Windows CI leg.
        # Only the *name* is wanted here, so the descriptor is closed
        # before anything else happens; any construct that held the file
        # open across the run() below would reintroduce exactly the lock
        # this close is here to release.
        fd, tmp_name = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            subprocess.run(
                ["pdftotext", "-layout", doc.pdf_path, tmp_name],
                check=True,
                capture_output=True,
            )
            return Path(tmp_name).read_text(encoding="utf-8", errors="ignore")
        finally:
            os.unlink(tmp_name)
    return None


def chunk_text(text: str, chunk_words: int = 200, overlap_words: int = 40) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = chunk_words - overlap_words
    return [" ".join(words[i : i + chunk_words]) for i in range(0, len(words), step)]
