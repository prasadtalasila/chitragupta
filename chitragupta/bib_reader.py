"""Reads the BibTeX-exported .bib file -- the source of truth for
citekeys and bibliographic metadata (project decision, 2026-07-28).

The file is a manual export, re-exported after adding papers. Whatever
citekey it assigns IS the citekey everywhere downstream; this module
never invents its own. Needs `bibtexparser`, the corpus layer's one
dependency: hand-rolling a BibTeX parser is a worse bet for something
citation-critical.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import (
    bib_escapes,
    bib_integrity,
    bib_names,
    bib_parse,
    bib_tables,
    config,
    ledger_paths,
)

# Re-exported: callers and tests ask the bib reader whether a citekey is usable.
from chitragupta.citekey_safety import citekey_problem  # noqa: F401  # pylint: disable=unused-import

# Reference.pdf_resolution values: *why* a PDF did or did not resolve, so
# an HTML-only item and a PDF that has since moved (silent data loss) are
# not reported as one bucket.
PDF_RESOLVED = "resolved"
PDF_NO_FILE_FIELD = "no_file_field"
PDF_MALFORMED_FILE_FIELD = "malformed_file_field"
PDF_PATH_GONE = "pdf_path_gone"
PDF_NON_PDF_ATTACHMENT = "non_pdf_attachment"

# Issue 821: a `file` field is someone else's data and may name any host
# file (`~/.ssh/id_rsa` became quotable corpus evidence). Confinement to
# beside the bib file is the fix, not sanitising spellings. In
# PDF_LOST_REASONS, so a refusal exits nonzero rather than quieter than the
# PDF_PATH_GONE it replaces (#556).
PDF_OUTSIDE_PAPERS = "pdf_outside_papers"

# Set by `sync_decide` from the `OSError` ledger_upsert hands back, never
# by `_resolve_pdf_path`; kept here with the other reasons (#556).
PDF_UNREADABLE = "pdf_unreadable"

# Reasons that mean the corpus has a hole, which sync gates its exit code
# on; no attachment or an HTML-only snapshot is an ordinary state (#556).
PDF_LOST_REASONS = (PDF_PATH_GONE, PDF_UNREADABLE, PDF_OUTSIDE_PAPERS)

# Dict order is the order sync.py's no-PDF breakdown reports in.
PDF_RESOLUTION_LABELS = {
    PDF_NO_FILE_FIELD: "no file field in bib entry",
    PDF_PATH_GONE: "PDF path no longer exists on disk",
    PDF_UNREADABLE: "PDF is on disk but could not be read (permissions, or an I/O error)",
    PDF_NON_PDF_ATTACHMENT: "non-PDF attachment only (e.g. an HTML snapshot)",
    PDF_MALFORMED_FILE_FIELD: "malformed file field (couldn't parse mime/path)",
    PDF_OUTSIDE_PAPERS: "PDF path resolves outside the bib file's own directory",
}


@dataclass
class Reference:
    citekey: str
    item_type: str
    title: str
    authors: list[tuple[str, str]]  # (first, last)
    year: str
    doi: str | None
    url: str | None
    fields: dict[str, str] = field(default_factory=dict)
    collections: tuple[str, ...] = ()
    pdf_path: str | None = None
    pdf_resolution: str = PDF_NO_FILE_FIELD


# A result object, so another count about the read is a new field, not a
# new return shape. Issue 841: dropped entries and unfilenameable keys used
# to be stdout warnings only, so `--remove-stale` pruned live papers.
@dataclass
class Library:
    references: list[Reference]
    duplicate_citekeys: tuple[str, ...] = ()
    dropped_entries: int = 0
    unfilenameable_citekeys: tuple[str, ...] = ()
    # chitragupta-importer's @comment tables (chitragupta/bib_tables.py).
    tables: bib_tables.Tables = field(default_factory=bib_tables.Tables)

    @property
    def seen_citekeys(self) -> set[str]:
        """Every citekey the bib file names that a sync must not treat as
        stale: the references, plus the skipped keys none was built for."""
        skipped = set(self.duplicate_citekeys) | set(self.unfilenameable_citekeys)
        return {r.citekey for r in self.references} | skipped

    @property
    def unread(self) -> dict[str, int]:
        """What the bib file holds that this read never saw, as
        `{description: count}`, nonzero only.

        Nonempty means sync will not prune (issue 841). A shared citekey is
        in `seen_citekeys` instead, so it cannot make another row look stale.
        """
        return _described(
            ("entry", "entries", "dropped unparsed by bibtexparser", self.dropped_entries),
            (
                "citekey",
                "citekeys",
                "skipped as unusable as a filename",
                len(self.unfilenameable_citekeys),
            ),
        )

    @property
    def integrity_problems(self) -> dict[str, int]:
        """Everything this read could not sync, as `unread` plus shared
        citekeys; nonempty makes sync exit EXIT_BIB_INTEGRITY."""
        shared = _described(
            ("citekey", "citekeys", "shared by more than one entry", len(self.duplicate_citekeys))
        )
        return self.unread | shared | self.tables.problems()


def _described(*counts) -> dict[str, int]:
    """`(singular, plural, what, n)` rows as `{"<n's noun> <what>": n}`, zeros dropped."""
    return {f"{one if n == 1 else many} {what}": n for one, many, what, n in counts if n}


def listed(problems: dict[str, int]) -> str:
    """`Library.unread`/`integrity_problems` as one clause for a message."""
    return ", ".join(f"{n} {what}" for what, n in problems.items())


def _parse_authors(author_field: str) -> list[tuple[str, str]]:
    # Split on a zero-width "and" between whitespace: bibtexparser keeps
    # line wraps, and a naive " and " split merges wrapped authors.
    authors = []
    for name in re.split(r"(?<=\s)and(?=\s)", author_field):
        name = name.strip()
        if not name:
            continue
        authors.append(bib_names.split_name(name))
    return authors


def _attachment_pdf(
    attachment: "tuple[str, str] | None", bib_dir: Path
) -> "tuple[bool, Path | None]":
    """One `bib_escapes.attachments` entry, as `(did it parse at all, the
    pdf-mime path it names)`.

    `None` covers both malformed and non-PDF; the boolean tells them
    apart for the caller's two no-PDF reasons.
    """
    if attachment is None:
        return False, None
    raw_path, mimetype = attachment
    if "pdf" not in mimetype.lower():
        return True, None
    path = Path(raw_path)
    return True, path if path.is_absolute() else bib_dir / path


def _resolve_pdf_path(file_field: str, bib_dir: Path) -> tuple[str | None, str]:
    """Resolve the export's `file` field (`Desc:path:mimetype`,
    `;`-separated; an export-tool convention, not BibTeX).

    Returns (path, PDF_RESOLVED) or (None, reason). A gone pdf-mime path
    wins over a non-PDF attachment as the more actionable signal.
    """
    saw_parseable_attachment = False
    saw_pdf_mime = False
    saw_outside = False
    for attachment in bib_escapes.attachments(file_field):
        parseable, path = _attachment_pdf(attachment, bib_dir)
        saw_parseable_attachment = saw_parseable_attachment or parseable
        if path is None:
            continue
        saw_pdf_mime = True
        # Confined before is_file(), so the reason cannot disclose what is
        # actually at a refused path.
        confined = config.confined_path(path, bib_dir)
        if confined is None:
            saw_outside = True
        elif confined.is_file():
            return str(confined), PDF_RESOLVED
    if saw_outside:
        return None, PDF_OUTSIDE_PAPERS
    if saw_pdf_mime:
        return None, PDF_PATH_GONE
    if saw_parseable_attachment:
        return None, PDF_NON_PDF_ATTACHMENT
    return None, PDF_MALFORMED_FILE_FIELD


def _clean_title(title: str) -> str:
    return re.sub(r"[{}]", "", title)


# A citekey is a filename stem (`content/parsed/<citekey>.txt` and
# others), never rewritten downstream. Its validator lives in
# `chitragupta/citekey_safety.py` (#638) so the review layer can use it
# without bibtexparser; re-exported above.


def _reference(entry: dict, bib_dir: Path) -> Reference:
    """One parsed bib entry, with its PDF resolved, as a `Reference`."""
    if "file" in entry:
        pdf_path, pdf_resolution = _resolve_pdf_path(entry["file"], bib_dir)
    else:
        pdf_path, pdf_resolution = None, PDF_NO_FILE_FIELD
    return Reference(
        citekey=entry["ID"],
        item_type=entry.get("ENTRYTYPE", "misc"),
        title=_clean_title(entry.get("title", "Untitled")),
        authors=_parse_authors(entry.get("author", "")),
        year=entry.get("year", "n.d."),
        doi=entry.get("doi"),
        url=entry.get("url"),
        fields=entry,
        collections=bib_tables.collections(entry),
        pdf_path=pdf_path,
        pdf_resolution=pdf_resolution,
    )


def read_library() -> Library:
    if not config.BIB_FILE_PATH.exists():
        raise FileNotFoundError(
            f"No bib file at {config.BIB_FILE_PATH}. Export your reference "
            "manager's library to BibTeX at this path -- or point BIB_FILE / "
            "config.toml's [bib].path at wherever you keep it -- then re-run sync."
        )

    raw_text = config.BIB_FILE_PATH.read_text(encoding="utf-8", errors="replace")
    # Nonstandard types (`@software`, `@online`...) are skipped silently,
    # as bibtexparser 1.x did. Intended (issue 888) -- do not "fix" it; they
    # are kept out of the dropped-entry count, so they cannot exit 3.
    entries = bib_parse.parse_entries(raw_text)

    name = config.BIB_FILE_PATH.name
    dropped = bib_integrity.dropped_entries(raw_text, len(entries), name, bib_parse.STANDARD_TYPES)
    duplicated = bib_integrity.duplicated_citekeys(entries, name)
    unfilenameable = bib_integrity.unfilenameable_citekeys(entries, duplicated)
    bib_dir = ledger_paths.pdf_root()
    kept = [e for e in entries if e["ID"] not in duplicated and e["ID"] not in unfilenameable]
    tables = bib_tables.read(raw_text, entries, name)
    references = [_reference(e, bib_dir) for e in kept]
    return Library(references, duplicated, dropped, unfilenameable, tables)
