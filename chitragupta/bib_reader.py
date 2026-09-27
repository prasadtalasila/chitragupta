"""Reads the BibTeX-exported .bib file -- the source of truth for
citekeys and bibliographic metadata (project decision, 2026-07-28).

No auto-sync plugin is installed, so this file is a manual, point-in-time
export from your reference manager, not continuously auto-synced --
re-export it after adding papers, then re-run `python -m chitragupta.corpus sync`.
Whatever citekey BibTeX assigns in this file IS the citekey everywhere
downstream (the ledger, citation_gate, generated drafts); this module
never invents its own.

Needs `bibtexparser` (pyproject.toml's main dependency group, installed
via scripts/install_full_pipeline.sh) -- the one dependency the
otherwise stdlib-only corpus layer requires, because hand-rolling a
correct BibTeX parser (nested braces, LaTeX escapes, multi-line values)
is a worse bet than using a maintained library for something
citation-critical.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import bibtexparser

# v1 legacy API (BibTexParser/customization/bibtexparser.load|loads), not
# v2 -- a deliberate pin, not drift: see pyproject.toml's `bibtexparser =
# ">=1.4,<2.0"` line for the full rationale (v2 replaces this API with an
# incompatible one this module doesn't use). Don't migrate this import
# without reading that comment and relaxing the ceiling first.
from bibtexparser.bibdatabase import STANDARD_TYPES
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from chitragupta import bib_collections, bib_integrity, bib_names, config
from chitragupta.citekey_safety import citekey_problem

# Reference.pdf_resolution values -- *why* a PDF did or didn't resolve.
# Previously sync.py only ever saw a bare pdf_path of None and reported
# every one of these as one "no PDF attachment" bucket, which masked two
# very different problems: an item with only a non-PDF attachment saved
# (typically an HTML snapshot, but _resolve_pdf_path only actually checks
# for the *absence* of a pdf-mime entry, not the presence of a
# text/html one specifically -- invisible to retrieval/citation-gate the
# same as any other no-PDF item, but not surfaced as such) and an item
# whose PDF the bib file still points at, but which has since moved or
# been deleted (a silent data-loss failure, not a "never had a PDF" one).
PDF_RESOLVED = "resolved"
PDF_NO_FILE_FIELD = "no_file_field"
PDF_MALFORMED_FILE_FIELD = "malformed_file_field"
PDF_PATH_GONE = "pdf_path_gone"
PDF_NON_PDF_ATTACHMENT = "non_pdf_attachment"

# Issue 821. A `file` field is data someone else's tool wrote -- a
# reference manager, or a collaborator whose export you were sent -- and
# it may name any file on the host. One naming `/etc/passwd` or
# `~/.ssh/id_rsa` had that file parsed into `content/parsed/<citekey>.txt`
# by the next sync, indexed by retrieval, and quotable into a draft as
# corpus evidence. Confinement is the fix rather than sanitisation: the
# rule is "an attachment lives beside the bib file that claims it", not
# a list of spellings to strip.
#
# In PDF_LOST_REASONS below, so a run that refuses one exits nonzero.
# The commonest real outside path is a collaborator's absolute
# `/home/bob/Zotero/storage/...`, which before this reported as
# PDF_PATH_GONE and already exited 3; a refusal that quietly exited 0
# instead would make this *less* visible than the state it replaces,
# which is the exact defect #556 was filed for. It is a document the
# bib file promises and the corpus does not get, which is what that
# list means.
PDF_OUTSIDE_PAPERS = "pdf_outside_papers"

# The one reason in this set that `_resolve_pdf_path` never produces:
# a PDF that is on disk and that this host cannot read anyway
# (permissions, or a failing device). `chitragupta/sync_decide.py` is
# what sets it, from the `OSError` `ledger_upsert` hands back when the
# stat or the hash fails -- so it is only reachable once a run is
# already under way, which is why the bib-read-time resolver has no
# branch for it. It lives here rather than there because this is where
# a reader looks for the set of reasons the no-PDF breakdown can report,
# and a sixth one kept somewhere else would be found by nobody
# (issue #556).
PDF_UNREADABLE = "pdf_unreadable"

# The reasons that mean the corpus has a hole in it, as opposed to an
# item that never had a PDF on this host. `chitragupta/sync.py` gates its
# exit code on these and not on the whole no-PDF count: an entry with no
# attachment, an HTML-only snapshot and an unparseable `file` field are
# ordinary states of a bibliography, where a PDF this export claims and
# this host cannot produce is a document silently missing from the
# corpus (issue #556).
PDF_LOST_REASONS = (PDF_PATH_GONE, PDF_UNREADABLE, PDF_OUTSIDE_PAPERS)

# Dict order doubles as the fixed, deterministic order sync.py's
# no-PDF breakdown reports these in.
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


# What one read of the bib file yields. A result object rather than a bare
# list so that a further count about the read -- entries dropped or
# skipped, say -- is a new field here, not a new return shape every
# caller has to unpack.
#
# Issue 841 added the other two ways a read comes back short: entries
# bibtexparser dropped without raising (unbalanced braces), and citekeys
# skipped because they cannot be a filename. Either used to be a warning
# on stdout and nothing else, so `--remove-stale` pruned the row of a
# paper that was still in the library and the run exited 0.
@dataclass
class Library:
    references: list[Reference]
    duplicate_citekeys: tuple[str, ...] = ()
    dropped_entries: int = 0
    unfilenameable_citekeys: tuple[str, ...] = ()

    @property
    def seen_citekeys(self) -> set[str]:
        """Every citekey the bib file names that a sync must not treat as
        stale: the references, plus the skipped keys none was built for."""
        skipped = set(self.duplicate_citekeys) | set(self.unfilenameable_citekeys)
        return {r.citekey for r in self.references} | skipped

    @property
    def unread(self) -> dict[str, int]:
        """What the bib file holds that this read never saw, as
        `{description: count}`, nonzero only: entries bibtexparser
        dropped, and citekeys skipped as unusable filenames.

        Nonempty means a citekey missing from the references may be
        missing only from this read, so sync will not prune on it
        (issue 841). A shared citekey is not here: it is in
        `seen_citekeys`, so it cannot make another row look stale.
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
        return self.unread | shared


def _described(*counts) -> dict[str, int]:
    """`(singular, plural, what, n)` rows as `{"<n's noun> <what>": n}`, zeros dropped."""
    return {f"{one if n == 1 else many} {what}": n for one, many, what, n in counts if n}


def listed(problems: dict[str, int]) -> str:
    """`Library.unread`/`integrity_problems` as one clause for a message."""
    return ", ".join(f"{n} {what}" for what, n in problems.items())


def _parse_authors(author_field: str) -> list[tuple[str, str]]:
    # bibtexparser preserves an author field's original line wrapping, so
    # a separator split across a line break (`... Doe\n  and Jane Smith`)
    # is whitespace, not the literal " and " a naive split() requires --
    # missing it silently collapses two authors into one mangled name.
    # A zero-width split on "and" (matched only, never consumed) so any
    # whitespace before and after -- one space, a wrapped newline, a
    # stray double space -- stays attached to its neighbouring segment
    # and is trimmed by the per-name strip() below, the same as before.
    authors = []
    for name in re.split(r"(?<=\s)and(?=\s)", author_field):
        name = name.strip()
        if not name:
            continue
        authors.append(bib_names.split_name(name))
    return authors


def _attachment_pdf(attachment: str, bib_dir: Path) -> "tuple[bool, Path | None]":
    """One `Desc:path:mimetype` segment, as `(did it parse at all, the
    pdf-mime path it names)`.

    Split out of `_resolve_pdf_path` when issue 821's confinement pushed
    that function past the 25-statement limit. The split falls here
    because the two halves answer different questions: this one is
    about the *field's* shape -- a convention of the export tool, and
    the reason a path is rejoined with `:` rather than taken as
    `parts[1]` -- and the caller is about which of several attachments
    the corpus will actually accept.

    `None` for the path covers both "not three colon-separated parts"
    and "parsed, but not a PDF"; the boolean is what tells those apart,
    and the caller needs both to pick between its two no-PDF reasons.
    """
    parts = attachment.split(":")
    if len(parts) < 3:
        return False, None
    if "pdf" not in parts[-1].lower():
        return True, None
    path = Path(":".join(parts[1:-1]))
    return True, path if path.is_absolute() else bib_dir / path


def _resolve_pdf_path(file_field: str, bib_dir: Path) -> tuple[str | None, str]:
    """The `file` field format in this project's bib export:
    `Desc:path:mimetype`, `;`-separated for multiple attachments (e.g. an
    HTML snapshot alongside the PDF) -- an export-tool convention, not
    part of the BibTeX standard itself.

    Returns (path, PDF_RESOLVED) on success, or (None, reason) where
    reason distinguishes *why*: PDF_PATH_GONE (a pdf-mime attachment was
    listed but its file no longer exists), PDF_NON_PDF_ATTACHMENT (every
    attachment parsed fine but none is pdf-mime -- typically an HTML
    snapshot saved instead of the PDF, but this only checks for the
    absence of a pdf-mime entry, not the presence of text/html
    specifically, so any other non-PDF mime lands here too), or
    PDF_MALFORMED_FILE_FIELD (not even one `;`-separated segment had the
    `Desc:path:mimetype` shape). If more than one attachment is present,
    a PDF path that's gone still wins over reporting a non-PDF attachment
    -- the presence of a pdf-mime entry is the more actionable signal (a
    paper this project's own bib once had a real PDF for, now missing)
    than "only ever had a non-PDF attachment".
    """
    saw_parseable_attachment = False
    saw_pdf_mime = False
    saw_outside = False
    for attachment in file_field.split(";"):
        parseable, path = _attachment_pdf(attachment, bib_dir)
        saw_parseable_attachment = saw_parseable_attachment or parseable
        if path is None:
            continue
        saw_pdf_mime = True
        # Confined before is_file(), not after: a refused path is not
        # probed for existence either, so the reason reported cannot
        # depend on -- or disclose -- what is actually at it.
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


# A citekey is not just an identifier here -- it is a *filename stem*.
# `content/parsed/<citekey>.txt`, its `.passages.json` sidecar, and the
# enrichment layer's `content/docling/<citekey>.md` are all built by
# interpolating it straight into a path, and nothing downstream rewrites
# it (deliberately: the bib file is the source of truth for citekeys).
# The validator itself lives in `chitragupta/citekey_safety.py` since
# #638 -- the review layer needs the same check on citekeys extracted
# from a *draft*, and cannot import this module's bibtexparser
# dependency -- re-exported from the imports at the top unchanged, so
# this stays the natural place to find it from the sync side.


def _unfilenameable_citekeys(entries, duplicated) -> tuple[str, ...]:
    """The citekeys that cannot be a filename, in bib order, each warned.

    Checked before anything else touches an entry: such a citekey would
    fail much later, inside a parse, as an OSError naming a path rather
    than the entry that produced it. Skipping the entry loses one paper
    and says so; letting it through risks writing outside content/. A
    duplicated key is already skipped and reported as that, so it is not
    counted twice.
    """
    skipped = []
    for entry in entries:
        key = entry["ID"]
        problem = citekey_problem(key)
        if problem is None or key in duplicated:
            continue
        skipped.append(key)
        print(
            f"  WARNING skipping citekey {key!r}: {problem}. "
            "It is used directly as a filename (content/parsed/<citekey>.txt "
            "and the enrichment layer's own outputs), and this project never "
            "rewrites a citekey -- the bib file is the source of truth. Rename "
            "it in your reference manager, re-export, and re-run sync."
        )
    return tuple(skipped)


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
        collections=bib_collections.parse(entry.get(config.BIB_COLLECTIONS_FIELD)),
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
    # Deliberately left at bibtexparser's default ignore_nonstandard_types=True:
    # an entry of a type outside STANDARD_TYPES (`@software`, `@online`,
    # `@dataset`, ...) is skipped, silently, and never synced. That is the
    # maintainer's stated intent (issue 888), not an oversight -- do not
    # "fix" it by passing False. What issue 888 fixed is the count below:
    # such an entry is ignored, not lost, so it is kept off the raw side of
    # the dropped-entry comparison and cannot exit 3 or block a prune.
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    bib_database = bibtexparser.loads(raw_text, parser=parser)

    name = config.BIB_FILE_PATH.name
    entries = bib_database.entries
    dropped = bib_integrity.dropped_entries(raw_text, len(entries), name, STANDARD_TYPES)
    duplicated = bib_integrity.duplicated_citekeys(entries, name)
    unfilenameable = _unfilenameable_citekeys(entries, duplicated)
    bib_dir = config.BIB_FILE_PATH.resolve().parent
    kept = [e for e in entries if e["ID"] not in duplicated and e["ID"] not in unfilenameable]
    return Library([_reference(e, bib_dir) for e in kept], duplicated, dropped, unfilenameable)
