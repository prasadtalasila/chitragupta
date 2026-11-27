"""How a document's raw text is fetched, cleaned, and split for an embedder.

Independent of Chroma or any model; `doc_vectors.py` needs only this
half. Re-exported from `embed_index.py`, so `embed_index.get_text` etc.
keep working.
"""

import hashlib
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from chitragupta import config, programs
from chitragupta.citekey_safety import citekey_path
from chitragupta.enrich.corpus import CorpusDoc

logger = logging.getLogger("chitragupta.enrich")


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def strip_image_refs(markdown: str) -> str:
    """Drop Docling's image markers from text on its way to the embedder.

    Both a `<!-- image -->` placeholder and a real `![Image](...png)`
    reference (one document can carry both since #600, plus older
    `image_<index>_<64 hex>.png` names). A path is worse than nothing:
    chunk_text() splits on whitespace, so it displaces real text. Captions
    are separate text items, so they survive and get embedded.
    """
    without_refs = re.sub(r"^[ \t]*!\[[^\]]*\]\([^)]*\)[ \t]*$", "", markdown, flags=re.MULTILINE)
    without_placeholders = re.sub(
        r"^[ \t]*<!--\s*image\s*-->[ \t]*$", "", without_refs, flags=re.MULTILINE
    )
    # Collapse the blank runs left behind, so no false paragraph gaps.
    return re.sub(r"\n{3,}", "\n\n", without_placeholders)


def get_text(doc: CorpusDoc) -> str | None:
    """Best available text for a doc: Docling output > existing parsed text
    > on-the-fly pdftotext. Doesn't require the Docling stage to have run."""
    docling_path = citekey_path(config.DOCLING_DIR, doc.citekey, ".md")
    if docling_path.exists():
        return strip_image_refs(docling_path.read_text(encoding="utf-8"))
    if doc.text_path and Path(doc.text_path).exists():
        return Path(doc.text_path).read_text(encoding="utf-8")
    if doc.pdf_path:
        # mkstemp with the descriptor closed at once, not a
        # NamedTemporaryFile `with` block: on Windows an open handle locks
        # the file, so pdftotext writing to it fails with PermissionError.
        fd, tmp_name = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            subprocess.run(
                [programs.require_program("pdftotext"), "-layout", doc.pdf_path, tmp_name],
                check=True,
                capture_output=True,
                # The sync backend's bound (#824): one hanging PDF used to
                # wedge the whole embed run.
                timeout=config.PARSER_DOCUMENT_TIMEOUT,
            )
            return Path(tmp_name).read_text(encoding="utf-8", errors="ignore")
        except subprocess.TimeoutExpired:
            # No text rather than a crash: reported as nothing to embed.
            return None
        except (subprocess.CalledProcessError, OSError) as exc:
            # Likewise an encrypted/corrupt PDF or no pdftotext (#978):
            # raising here failed every topic stage together.
            logger.warning("no text for %s: pdftotext failed (%s)", doc.citekey, exc)
            return None
        finally:
            os.unlink(tmp_name)
    return None


def chunk_text(text: str, chunk_words: int = 200, overlap_words: int = 40) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = chunk_words - overlap_words
    return [" ".join(words[i : i + chunk_words]) for i in range(0, len(words), step)]
