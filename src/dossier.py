"""The working state that produced a draft, kept on disk so a later
session can revise it without re-running the drafting pipeline.

`citation_gate`, `references`, `render_output` and `citation_provenance`
all operate statelessly on a draft *file*: hand any of them a draft from
last month and they work. The drafting layer is the only stateful part
of this pipeline, and until this module none of that state was written
down -- it lived in one chat session and died with it. So "shorten
section 3" cost a full re-run: retrieve, score every candidate again,
re-cluster, rewrite. This module is the missing half, and
docs/DRAFT-ITERATION.md is the argument for why it is shaped this way.

**One dossier per draft, mirroring the draft's own path.** A dossier
directory is `content/dossiers/` plus the draft's path relative to
`content/drafts/`, minus the suffix:

    content/drafts/dt-for-engineers/survey.md
    -> content/dossiers/dt-for-engineers/survey/

That rule is mechanical, needs no registry to map one to the other, and
handles both layouts this repo actually contains -- the flat
`content/drafts/<slug>.md` the genre skills describe, and the
`content/drafts/<topic>/<genre>.md` the shipped example content uses.

**Markdown, not JSON.** Everything a dossier holds is read by a model or
a human, both of which read Markdown natively; nothing here is a data
structure some other module consumes. Markdown also means a restored
tarball is legible on its own a year later, without this code.

**Several files, not one**, because a revision should load only what it
needs: the scope and the section map are small and always relevant, the
rejected-candidate list is the largest and is only needed when a change
opens a sub-theme up for re-searching, and `retrieval.md` is written by
the tooling and read by nobody until someone asks what a run cost.

Deliberately *not* a gate and not a lock-taker. Nothing here blocks a
draft, and nothing here writes to the corpus layer -- the ledger is only
ever opened read-only, and only to answer "has the corpus moved since
this draft was written?". A dossier that is missing, stale or
hand-edited degrades the next revision's efficiency; it can never make a
draft wrong.

That is why `status()` reports rather than raising: a missing ledger, a
missing draft, an unparsable fingerprint and a hand-edited file all come
back as something to print. The one thing its *CLI* treats as an error is
a dossier that does not exist at all -- `_cmd_status` exits 1 there,
because "there is nothing to report yet, run `init`" is an actionable
condition a script should be able to branch on, unlike "this dossier
exists and the corpus has moved".

`status --all` extends the same posture across every dossier at once:
which drafts cite a citekey the ledger has since lost, and which new
papers this draft's own recorded queries would have surfaced. It always
exits 0 -- drift is the normal state of a live corpus -- and, like
everything else here, it writes nothing: see `_ephemeral_index` for why
`src.retrieval.search()` cannot be used to do the matching.

Stdlib only (re/sqlite3/tarfile/hashlib), like citation_gate.py,
references.py and citation_provenance.py -- runs with bare `python`, no
venv, on a machine where the corpus was never built.

Usage:
    python -m src.draft dossier init content/drafts/<name>.md --genre survey
    python -m src.draft dossier status content/drafts/<name>.md
    python -m src.draft dossier status --all [--json]
    python -m src.draft dossier sections content/drafts/<name>.md
    python -m src.draft dossier brief content/drafts/<name>.md --section "2. Failure modes"
    python -m src.draft dossier acronyms-suggest content/drafts/<name>.md
    python -m src.draft dossier list
    python -m src.draft dossier export [<name> ...] [--out FILE] [--with-rendered]
    python -m src.draft dossier restore <archive.tar.gz> [--force]
"""

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tarfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath

from src import acronyms, citation_gate, config, review

# One constant per dossier filename, because each recurs across this
# module -- as FILES keys, template keys, path joins and report lookups
# -- and a filename spelled at every use site is a rename that misses
# one. All seven are named, not only the ones repeated often enough for
# a duplicated-literal check to notice: a dict keyed by five constants
# and two bare strings would read as if the two were different in kind.
SCOPE_MD = "scope.md"
EVIDENCE_MD = "evidence.md"
REJECTED_MD = "rejected.md"
SECTIONS_MD = "sections.md"
STEERING_MD = "steering.md"
REVISIONS_MD = "revisions.md"
RETRIEVAL_MD = "retrieval.md"

# The files a dossier holds, in the order `init` writes them and `status`
# reports them. The value is how `status` counts entries in that file --
# see `_count`, and the "counts are advisory" note there.
FILES: dict[str, str] = {
    SCOPE_MD: "prose",
    EVIDENCE_MD: "blocks",
    REJECTED_MD: "rows",
    SECTIONS_MD: "rows",
    STEERING_MD: "prose",
    REVISIONS_MD: "prose",
    RETRIEVAL_MD: "rows",
}

# Top-level directories a bundle may contain, and the only ones `restore`
# will unpack. A whitelist rather than a blocklist: an archive member
# naming anything else is refused outright, so a hand-edited or
# hostile tarball cannot write outside the directories this module owns.
#
# Every root `bundle_members` can emit has to be here, or `export` and
# `restore` stop being a round trip -- and because `_checked_members`
# refuses the *whole* archive rather than skipping a member, the failure
# would be a bundle that cannot be restored at all rather than one
# missing a file.
ARCHIVE_ROOTS = ("drafts", "dossiers", "rendered", "review")


class DossierError(Exception):
    """A path that isn't a draft, or an archive that isn't safe to unpack."""


# --------------------------------------------------------------------------
# Locating a dossier
# --------------------------------------------------------------------------


def dossier_dir(draft: Path) -> Path:
    """Where `draft`'s dossier lives.

    Raises rather than guessing if the draft isn't under
    `content/drafts/`: the mirroring rule is the only thing tying the two
    together, and a dossier written somewhere unmirrored would be found
    by nothing later. That refusal is this module's policy;
    `config.mirrored_dir` holds only the shared rule, and answers `None`
    so each caller can decide.

    One shape difference from the other three consumers of that rule: a
    dossier is a *directory per draft*, not per topic, so the draft's own
    name is appended. `content/drafts/dt/survey.md` gets
    `content/dossiers/dt/survey/`, which is what lets two drafts in one
    topic directory keep separate dossiers.
    """
    mirrored = config.mirrored_dir(draft, config.DRAFTS_DIR, config.DOSSIERS_DIR)
    if mirrored is None:
        raise DossierError(
            f"{draft} is not under {config.DRAFTS_DIR}. A dossier mirrors its "
            "draft's path, so the draft has to live where the genre skills "
            "save it."
        )
    target = mirrored / Path(draft).stem
    # The draft's own path can't get out -- `mirrored_dir` resolves both
    # sides before subtracting them, so no argument carries a `..` or a
    # symlink's spelling past it. What can is the target side: a topic
    # directory under content/dossiers/ that is itself a symlink out of
    # the tree. `render_output._output_dir` and
    # `citation_provenance.write_report` both check their own mirrored
    # result for exactly this; this is the third consumer of that rule and
    # was the one that didn't.
    if not config.resolves_inside(target, config.DOSSIERS_DIR):
        raise DossierError(
            f"{target} resolves to {target.resolve()}, outside "
            f"{config.DOSSIERS_DIR.resolve()}. A dossier is only useful where "
            "the rest of the pipeline looks for it, and a copy of content/ is "
            "meant to be the whole record of the work -- remove the symlink on "
            "the topic directory, or point [content].dir (config.toml) at the "
            "tree you are really working in."
        )
    return target


def draft_name(draft: Path) -> str:
    """The draft's path relative to `content/drafts/`, suffix dropped --
    the name `export` matches against and `list` prints."""
    resolved = Path(draft).resolve()
    try:
        relative = resolved.relative_to(config.DRAFTS_DIR.resolve())
    except ValueError:
        return Path(draft).stem
    return relative.with_suffix("").as_posix()


def find_draft(dossier: Path) -> Path | None:
    """The draft a dossier belongs to, if it is still on disk.

    The inverse of `dossier_dir`, except that the suffix was dropped on
    the way in -- so this looks for any suffix a genre skill emits
    (`.md` from four of them, `.tex` from thesis-chapter-writer).
    """
    try:
        relative = dossier.resolve().relative_to(config.DOSSIERS_DIR.resolve())
    except ValueError:
        return None
    for suffix in (".md", ".tex"):
        candidate = config.DRAFTS_DIR / relative.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None


def all_dossiers() -> list[Path]:
    """Every dossier directory, nearest-first by name."""
    if not config.DOSSIERS_DIR.is_dir():
        return []
    found = {
        path.parent
        for path in config.DOSSIERS_DIR.rglob("*.md")
        if path.name in FILES
    }
    return sorted(found)


# --------------------------------------------------------------------------
# The corpus fingerprint
# --------------------------------------------------------------------------


def _corpus_rows() -> list[sqlite3.Row] | None:
    """Every ledger item, or None if there is no readable ledger.

    Opened read-only and with `timeout=0`, exactly as `src.ledger`'s own
    CLI does and for the same reason: this is an inspection, and it must
    not take a write lock, run a migration, or block behind a sync that
    happens to be mid-run. `src.ledger.connect()` would do all three --
    it mkdirs `content/`, executes the schema and runs migrations -- so
    nothing here goes through it, and `src.retrieval.search()`, which
    does, is off limits for the same reason (see `_ephemeral_index`).

    Three columns rather than one because the drift scan needs the same
    fields `src.retrieval` indexes on: `title` and `parsed_path` are what
    a BM25 entry is built from, and `title` is also what makes a reported
    candidate legible without a second lookup.
    """
    if not config.LEDGER_PATH.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{config.LEDGER_PATH}?mode=ro", uri=True, timeout=0)
    except sqlite3.Error:
        return None
    try:
        con.row_factory = sqlite3.Row
        return con.execute("SELECT citekey, title, parsed_path FROM items").fetchall()
    except sqlite3.DatabaseError:
        return None
    finally:
        con.close()


def known_citekeys() -> set[str] | None:
    """Every citekey in the ledger, or None if there is no readable one.

    None (rather than an empty set) distinguishes "no corpus on this
    machine" from "a corpus with nothing in it" -- `status` says
    different things about those two.
    """
    rows = _corpus_rows()
    return None if rows is None else {row["citekey"] for row in rows}


def digest(citekeys: set[str]) -> str:
    """A short, order-independent fingerprint of a set of citekeys.

    Twelve hex characters, which is plenty to answer the only question
    asked of it -- "is this the same corpus the draft was written
    against?" -- and short enough to sit on one line of `scope.md`
    without looking like something a reader has to parse.
    """
    joined = "\n".join(sorted(citekeys))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


# `- corpus: 501 citekeys, digest `a1b2c3d4e5f6`` in scope.md. Written by
# `init`, read by `status`, and safe to be absent -- a hand-written
# dossier that never recorded one just loses the drift check.
_CORPUS_LINE = re.compile(
    r"^-\s*corpus:\s*(\d+)\s+citekeys?,\s*digest\s*`?([0-9a-f]+)`?", re.MULTILINE
)


def recorded_corpus(dossier: Path) -> tuple[int, str] | None:
    """(citekey count, digest) as recorded in `scope.md` at draft time."""
    scope = dossier / SCOPE_MD
    if not scope.is_file():
        return None
    match = _CORPUS_LINE.search(scope.read_text(encoding="utf-8"))
    if not match:
        return None
    return int(match.group(1)), match.group(2)


# `- **Term** -- definition` bullets under a `## Glossary` heading in
# scope.md. A forgiving parser, not a schema: #190's resolving comment
# found a real 15-chapter book had already converged on this exact shape
# with no format rule in force, so this reads what a genre skill's step 0
# already writes by hand rather than imposing a new one. A line that
# doesn't match -- a human typed it differently -- is skipped, the same
# "degrades to unavailable rather than to an error" policy
# docs/DRAFT-ITERATION.md states for the rest of this file.
_GLOSSARY_HEADING = re.compile(r"^## Glossary\s*$", re.MULTILINE)
_NEXT_HEADING = re.compile(r"^## ", re.MULTILINE)
_GLOSSARY_TERM = re.compile(r"^-\s*\*\*(?P<term>[^*]+)\*\*\s*--\s*", re.MULTILINE)


def glossary_terms(draft: Path) -> dict[str, str]:
    """Recorded `term -> definition` pairs from the draft's `## Glossary`.

    `{}` if there's no dossier yet, no `## Glossary` heading, or no
    bullet in the recognised shape -- never an error.
    """
    scope = dossier_dir(draft) / SCOPE_MD
    if not scope.is_file():
        return {}
    text = scope.read_text(encoding="utf-8")
    heading = _GLOSSARY_HEADING.search(text)
    if not heading:
        return {}
    next_heading = _NEXT_HEADING.search(text, heading.end())
    body = text[heading.end():next_heading.start() if next_heading else len(text)]

    matches = list(_GLOSSARY_TERM.finditer(body))
    terms: dict[str, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        definition = body[match.end():end].strip()
        if definition:
            terms[match.group("term").strip()] = definition
    return terms


def _citekeys_in(dossier: Path, names: tuple[str, ...]) -> set[str]:
    found: set[str] = set()
    for name in names:
        path = dossier / name
        if path.is_file():
            found |= set(_citekeys(path.read_text(encoding="utf-8")))
    return found


# The files that mean "this draft *stands on* that paper", as opposed to
# "this draft *looked at* it". The split matters for drift: a citekey
# that leaves the ledger is a finding when the draft cites it and a
# non-event when the draft turned it down, and `MENTIONED_FILES` would
# report the second as the first.
CITED_FILES = (EVIDENCE_MD, SECTIONS_MD)
MENTIONED_FILES = (EVIDENCE_MD, REJECTED_MD, SECTIONS_MD)


def cited_citekeys(dossier: Path) -> set[str]:
    """Every citekey the dossier mentions, kept or rejected.

    Used to answer "which papers in the corpus were never considered for
    this draft?" -- a more actionable drift signal than a count, because
    it names what to go and look at. Matched loosely (any backticked
    token that looks like a BibTeX key) so that a hand-edited
    `evidence.md` still contributes.
    """
    return _citekeys_in(dossier, MENTIONED_FILES)


def rejected_reasons(dossier: Path) -> dict[str, str]:
    """citekey -> why `rejected.md` says this draft turned it down.

    The reason is the part that does not survive being reduced to a set.
    "Turned down because the corpus had nothing better" and "turned down
    because it is about a different field" age completely differently,
    and only the first is worth revisiting when the corpus grows -- so a
    re-grounding pass needs the sentence, not just the membership.
    """
    path = dossier / REJECTED_MD
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in _ROW_SPLIT.split(stripped.strip("|"))]
        if len(cells) != 3:
            continue
        for citekey in _citekeys(cells[0]):
            found[citekey] = cells[2]
    return found


def section_citekeys(dossier: Path) -> dict[str, list[str]]:
    """citekey -> the `sections.md` sections that cite it.

    The point is scope, not bookkeeping: a reviser handed "this citekey
    left the ledger" still has to find the prose that leans on it, and
    reading the whole draft to find out is the cost `sections` and this
    both exist to avoid. Absent or hand-mangled rows map nothing, like
    every other read here.
    """
    found: dict[str, list[str]] = {}
    for title, citekeys in citekeys_by_section(dossier).items():
        for citekey in citekeys:
            found.setdefault(citekey, []).append(title)
    return found


def citekeys_by_section(dossier: Path) -> dict[str, list[str]]:
    """section -> the citekeys `sections.md` assigns to it, in row order.

    The file has one parser, and this is it -- `section_citekeys` is this
    inverted. They answer different questions for different callers:
    that one is "who leans on this paper?", for a reviser holding a
    citekey that left the ledger; this one is "what is this section's
    evidence?", for a section writer about to be dispatched. Row order is
    kept because it is the order the run itself chose.

    A section whose citekey cell is empty maps to `[]` rather than being
    dropped. `deep-research` writes this file at outline time, before
    every section has evidence assigned, and "planned but empty" and
    "not a section at all" want opposite fixes -- one is a gap to fill,
    the other a typo in the section name.
    """
    path = dossier / SECTIONS_MD
    if not path.is_file():
        return {}
    found: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|-: \t"):
            continue
        # `\|` is markdown's literal pipe, and a heading containing one is
        # written that way (by hand or by `sections --citekeys`). Splitting
        # already skips it; unescaping here is the other half, so the
        # section name read back is the heading as it appears in the draft
        # rather than its escaped spelling -- which is what a caller then
        # matches against `sections()` output.
        cells = [cell.strip().replace(r"\|", "|")
                 for cell in _ROW_SPLIT.split(stripped.strip("|"))]
        if len(cells) != 2 or [cell.lower() for cell in cells] == ["section", "citekeys"]:
            continue
        found[cells[0]] = _citekeys(cells[1])
    return found


def evidence_blocks(dossier: Path) -> dict[str, str]:
    """citekey -> its whole `## `citekey`` block in `evidence.md`.

    What a dispatched subagent reads instead of being handed the same
    text pasted into its prompt. The block is returned verbatim, heading
    included, because what a genre skill puts under one varies (a
    `relevance:`/`support:` pair, a claim list, a quotation) and this
    module does not own that shape -- only the heading that addresses it.

    Keyed on the first citekey-shaped token in the heading, so
    ``## `smith_x_2024` -- kept for section 3`` is addressable as
    `smith_x_2024`, and so is ``## @smith_x_2024`` -- either delimiter,
    since `_citekeys` reads both. A heading carrying no citekey token at
    all falls back to its own text: a hand-written dossier is a supported
    input everywhere else here, and a block nobody can address is a block
    the next run re-retrieves.
    """
    path = dossier / EVIDENCE_MD
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    key: str | None = None
    body: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if key is not None:
                found[key] = "\n".join(body).rstrip() + "\n"
            heading = line[3:].strip()
            tokens = _citekeys(heading)
            key = tokens[0] if tokens else heading.strip("` ")
            body = [line]
            continue
        if key is not None:
            body.append(line)
    if key is not None:
        found[key] = "\n".join(body).rstrip() + "\n"
    return found


# A citekey as the dossier templates write one: inside backticks, starting
# with a letter, and carrying at least one run of `_`/`:`/`-` separators
# followed by more alphanumerics -- the shape BibTeX gives a key
# (`talasila_composable_2025`). Requiring a separator is what keeps
# ordinary backticked prose out: `status` and `content` have none, and
# `--force` also fails the letter start.
#
# The separator run is `+`, not a single character, because a real key in
# this project's own corpus is `zech_digital-twins-as--service_2024` --
# BibTeX collapses "as-a-service" into a doubled hyphen. Matching only one
# separator dropped it silently.
#
# Both delimiters, because the dossier is written by hand and by two
# different habits. No template shows an example row, so each file settled
# on whatever the skill filling it in reached for: `evidence.md` headings
# are backticked, while `sections.md` copies the form the draft cites with
# (`@key`). Reading only the backticked form lost every section mapping in
# the shipped example dossier, which is what made `missing` report a
# departed citekey with no sections to go and edit.
#
# A false *negative* is the worse failure, and always was: this set is
# subtracted from the ledger's citekeys to find what a dossier never
# considered, so a prose token that looks key-shaped (`draft-reviser`) is
# inert -- it is not in the ledger, so subtracting it changes nothing,
# while a missed real key gets reported as "never considered" when it was
# cited. False positives are no longer entirely free, though: since the
# drift report, this same set is also differenced the other way to find
# citekeys that have *left* the ledger, where an invented one would be
# reported as a broken citation that isn't. The separator requirement is
# what holds that line, and it is the *only* thing holding it: a match
# needs a letter start and at least one `_`/`:`/`-` run followed by more
# alphanumerics, so `@someone` and `@2` are not keys while
# `@noauthor_digital_nodate` is. Nothing here requires a trailing year --
# a real key in this corpus ends in `_nodate`.
_KEY = r"[A-Za-z][A-Za-z0-9]*(?:[_:-]+[A-Za-z0-9]+)+"
_CITEKEY_TOKEN = re.compile(rf"`({_KEY})`|@({_KEY})")


def _citekeys(text: str) -> list[str]:
    """Every citekey token in `text`, in either delimiter, in order."""
    return [backticked or at_form for backticked, at_form in _CITEKEY_TOKEN.findall(text)]


# --------------------------------------------------------------------------
# Section anchors
# --------------------------------------------------------------------------


@dataclass
class Section:
    title: str
    level: int
    start: int  # 1-indexed line of the heading itself
    end: int  # 1-indexed last line before the next heading

    @property
    def lines(self) -> int:
        return self.end - self.start + 1


# Headings for *outline extraction*: where does each section start and
# stop, so a revision can Read and Edit one section instead of the whole
# file. src/review/citation_provenance.py has a similar-looking pair of regexes
# doing a different job -- segmenting claim-bearing blocks for scoring --
# and the two are deliberately not shared: that module needs list items
# and table rows to be blocks, which would be noise in an outline.
# The whole rest of the line is captured and the optional ATX closing
# sequence (`## Title ##`) stripped in `sections()` instead of by a
# `(.*?)\s*#*\s*$` tail here: that tail's adjacent ambiguous quantifiers
# backtrack super-linearly on pathological input (Sonar S8786), and a
# plain-code strip is both linear and easier to confirm faithful.
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_TEX_HEADING = re.compile(r"^\s*\\(chapter|(?:sub){0,2}section|paragraph)\*?\{(.*)$")
_TEX_LEVELS = {
    "chapter": 1, "section": 2, "subsection": 3, "subsubsection": 4, "paragraph": 5,
}
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_VERBATIM_BEGIN = re.compile(r"\\begin\{(verbatim|lstlisting|minted|Verbatim)\*?\}")
_VERBATIM_END = re.compile(r"\\end\{(verbatim|lstlisting|minted|Verbatim)\*?\}")


def _braced(text: str) -> str:
    """The contents of a `{...}` group, given everything after the `{`.

    Brace-balanced rather than matched by regex, because both regex
    readings are wrong on titles this project actually produces: a lazy
    `.*?` stops at the first `}` and truncates `\\emph{twin}` mid-word, a
    greedy `.*` runs past the closing brace and swallows a trailing
    `\\label{...}`. A backslash escape is consumed as a pair so that a
    literal `\\{` in a title doesn't open a group.
    """
    depth, out, index = 1, [], 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            out.append(text[index:index + 2])
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(char)
        index += 1
    return "".join(out)


def _prose_lines(lines: list[str]):
    """(line number, line) for every line outside fenced code blocks and
    LaTeX verbatim environments -- the fence tracking `sections()`'s
    docstring says is not a nicety, shared so no caller re-derives it."""
    in_fence = False
    in_verbatim = False
    for number, line in enumerate(lines, 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if _VERBATIM_BEGIN.search(line):
            in_verbatim = True
        if _VERBATIM_END.search(line):
            in_verbatim = False
            continue
        if not in_fence and not in_verbatim:
            yield number, line


def sections(text: str) -> list[Section]:
    """The draft's outline: one `Section` per heading, with line ranges.

    Code is skipped first, which is not a nicety. `tutorial.md` in the
    shipped example content is mostly shell and Python, and a `# Step 1`
    comment inside a fenced block is indistinguishable from a Markdown
    heading to anything that doesn't track fences -- so an outline built
    without this reports sections that don't exist and hands a reviser
    line ranges that cut a code block in half.

    Markdown and LaTeX are both recognised, since thesis-chapter-writer
    emits `.tex` and the other four emit `.md`.
    """
    lines = text.splitlines()
    found: list[Section] = []

    for number, line in _prose_lines(lines):
        md = _MD_HEADING.match(line)
        if md:
            # Strip whitespace, then one closing-hash run, then the
            # whitespace preceding it -- the same shape the regex's old
            # `\s*#*\s*$` tail matched, so `## Title ##` and `## Title`
            # both yield "Title" while an interior `#` survives.
            title = md.group(2).strip().rstrip("#").rstrip()
            found.append(Section(title, len(md.group(1)), number, number))
            continue
        tex = _TEX_HEADING.match(line)
        if tex:
            found.append(Section(
                _braced(tex.group(2)).strip(),
                _TEX_LEVELS.get(tex.group(1), 2),
                number,
                number,
            ))

    for current, following in zip(found, found[1:]):
        current.end = following.start - 1
    if found:
        found[-1].end = len(lines)
    return found


def attribute_citekeys(text: str) -> tuple[list[tuple[Section, list[str]]], list[str]]:
    """(section, its citekeys) for every heading, plus the unattributed ones.

    The join key is the line number: `sections()` gives each heading a
    line range, `citation_gate.extract_citekeys()` gives every citekey the
    line it was cited on, and the intersection is the relation
    `sections.md` records. Both halves already handle the two syntaxes
    and skip code, so `.md` (`[@key]`) and `.tex` (`\\citep{key}`) need no
    separate treatment here.

    Duplicates collapse, keeping first-cited order -- the file answers
    "which section leans on this paper", and a key cited three times in
    one section is one answer, not three.

    A key cited before the first heading belongs to no section and is
    returned separately rather than dropped or forced into the first row.
    Attributing it to a section that does not contain it would be a wrong
    answer handed to a reviser, which is the failure this whole file
    exists to prevent.
    """
    outline = sections(text)
    per_section: list[tuple[Section, list[str]]] = [(section, []) for section in outline]
    unattributed: list[str] = []
    for line, citekey in citation_gate.extract_citekeys(text):
        for section, keys in per_section:
            if section.start <= line <= section.end:
                if citekey not in keys:
                    keys.append(citekey)
                break
        else:
            if citekey not in unattributed:
                unattributed.append(citekey)
    return per_section, unattributed


def sections_markdown(text: str) -> str:
    """The finished `sections.md` for a draft, header and all.

    Deterministic, so it can be regenerated rather than maintained: the
    template already says the file is "rebuildable from the draft", and
    this is that sentence made executable. A pipe in a heading is escaped
    rather than left to break the row -- `_ROW_SPLIT` reads `\\|` as
    literal, so the round trip through `citekeys_by_section()` returns
    the heading as written.
    """
    per_section, _ = attribute_citekeys(text)
    rows = "".join(
        f"| {section.title.replace('|', r'\|')} | "
        f"{', '.join(f'`{key}`' for key in keys)} |\n"
        for section, keys in per_section
    )
    return _SECTIONS_TEMPLATE + rows


# --------------------------------------------------------------------------
# Creating a dossier
# --------------------------------------------------------------------------


def _readme(name: str, draft: Path, genre: str) -> str:
    return f"""# Dossier: {name}

The working state that produced `{draft_relpath(draft)}` -- what a later
session needs in order to revise it without re-running the drafting
pipeline. Genre: {genre}.

| File | What it holds |
|---|---|
| `scope.md` | reader, dialect, what the draft covers and excludes, glossary, corpus fingerprint |
| `evidence.md` | each citekey kept, why, and the supporting quote or paraphrase |
| `rejected.md` | candidates retrieved and turned down, with the reason |
| `sections.md` | section heading -> the citekeys cited under it |
| `steering.md` | what the user asked for in chat that the draft doesn't show |
| `revisions.md` | append-only log of what changed and why |
| `retrieval.md` | every retrieval call and the size of what it returned, plus a `mark-revision` boundary per revision pass |

This directory is gitignored, like the draft it describes. Back it up and
restore it with:

    python -m src.draft dossier export {name}
    python -m src.draft dossier restore <archive.tar.gz> --force

A bundle carries drafts and dossiers, not the corpus: `content/ledger.sqlite`
is regenerable with `python -m src.corpus sync`, and `papers/bibliography.bib` is
your reference manager's export, which belongs in that tool's backup rather
than in a copy this pipeline keeps.

See `docs/DRAFT-ITERATION.md`.
"""


def _scope(draft: Path, genre: str, corpus: tuple[int, str] | None) -> str:
    # `language` ships unset rather than defaulting, and says so in the
    # value itself. `init` has no way to know the dialect -- it is settled
    # with the reader, one step later -- and `draft-reviser` reads this
    # file before every edit, so a plausible-looking `en-US` here would be
    # a preference nobody chose, silently applied to every future
    # revision. Same policy as `corpus_line` below, for the same reason:
    # an honest "not recorded" beats an invented value.
    corpus_line = (
        f"- corpus: {corpus[0]} citekeys, digest `{corpus[1]}`"
        if corpus
        else "- corpus: not recorded (no ledger on this machine when the dossier was created)"
    )
    return f"""# Scope

- genre: {genre}
- language: not settled -- a BCP-47 tag (`en-GB`, `en-IN`, `en-US`), \
settled with the reader; docs/WRITING-STANDARDS.md section 8
- draft: {draft_relpath(draft)}
- created: {date.today().isoformat()}
{corpus_line}

## Reader

<!-- One concrete sentence: who is this draft for, and what do they
     already know? Every later revision is judged against this. -->

## Covers

## Does not cover

<!-- Including any sub-theme the corpus turned out too thin to support,
     so a reader can tell an omission from an oversight. -->

## Glossary

<!-- Each recurring term with the one definition the whole draft uses. -->
"""


_EVIDENCE_TEMPLATE = """# Kept evidence

<!-- One block per citekey that survived relevance scoring. A citekey the
     draft cites should appear here; one that was retrieved and turned
     down belongs in rejected.md instead. -->

"""

_REJECTED_TEMPLATE = """# Rejected candidates

<!-- Retrieved, read, and turned down. Recording these is what stops the
     next revision re-searching and re-judging the same papers -- it is
     the single most expensive thing a fresh session repeats. -->

| citekey | query that surfaced it | why rejected |
|---|---|---|
"""

_SECTIONS_TEMPLATE = """# Sections and their citekeys

<!-- Rebuildable from the draft, and worth keeping anyway: a revision can
     see which section owns a citation without reading the draft. -->

| section | citekeys |
|---|---|
"""

_STEERING_TEMPLATE = """# Steering

<!-- What the user asked for in chat that the draft itself doesn't show:
     "don't lead with tooling", "shorter", "drop the adoption angle".
     This is the only part of a drafting session that has nowhere else to
     live. One dated entry per instruction. -->

"""

_REVISIONS_TEMPLATE = """# Revisions

<!-- Append-only, newest last. One entry per revision session: what
     changed, which sections, and why. -->

"""

_RETRIEVAL_TEMPLATE = """# Retrieval calls

<!-- Appended by `python -m src.draft retrieve ... --log <draft>`, never by
     hand.

     `asked` is how much that call requested -- `--k` for search,
     `--windows` for evidence. `chars` is the size of the payload it
     handed back: the thing that then sits in the caller's context for
     the rest of the run. Together with evidence.md's and rejected.md's
     counts, this is what turns "retrieval is where the tokens go" from
     an estimate into a measurement for a particular draft.

     A row with mode `revision` is not a call: `python -m src.draft dossier
     mark-revision` writes one, at the start of each draft-reviser pass,
     so `dossier status` can total retrieval cost per revision instead of
     only as one lifetime figure -- the date column alone can't tell two
     same-day revisions apart. -->

| date | mode | query | asked | results | chars |
|---|---|---|---|---|---|
"""

_TEMPLATES = {
    EVIDENCE_MD: _EVIDENCE_TEMPLATE,
    REJECTED_MD: _REJECTED_TEMPLATE,
    SECTIONS_MD: _SECTIONS_TEMPLATE,
    STEERING_MD: _STEERING_TEMPLATE,
    REVISIONS_MD: _REVISIONS_TEMPLATE,
    RETRIEVAL_MD: _RETRIEVAL_TEMPLATE,
}


def log_retrieval(
    draft: Path, mode: str, query: str, k: int, results: int, chars: int
) -> Path:
    """Append one retrieval call to the dossier's `retrieval.md`.

    Creates the file if the dossier exists but predates it, and creates
    the dossier directory if a skill logged before running `init` --
    losing a measurement because the skeleton wasn't there yet would be a
    silly way to fail, and this writes nothing a later `init` would
    clobber.

    The query is flattened onto one line before it is written. A pipe
    would split the row into extra cells and a newline would split it
    into two rows -- and `retrieval_cost` reads rows positionally, so
    either one turns a logged call into a silently miscounted one rather
    than a visible error. Whitespace is collapsed with `split()`, which
    covers newlines, tabs and carriage returns together.

    **Nothing here ever writes at an offset.** That matters because
    `--log` is a flag on the retrieval CLI and a skill dispatching
    parallel subagents could hand it to all of them, so two processes
    can reach this function at once. The file is opened once, in append
    mode, and the template is written only when that open finds it
    empty -- so both the template and the row go through `O_APPEND` and
    land at whatever the end of the file is *at the time of the write*.
    A writer can therefore never overwrite what another one put there.

    Two earlier shapes could, and both are worth naming because each
    looks correct:

    - `if not path.exists(): path.write_text(TEMPLATE)` truncates, and
      the check goes stale between the two calls.
    - Creating with mode `"x"` fixes that, but publishes an empty file
      and then writes the template to it from offset 0. A second writer
      that appends a row in between has it overwritten.

    What this does *not* promise: that the template is written exactly
    once. Two writers that both find the file empty both write one, so
    the file can carry a duplicate header. That is deliberately the
    failure left in, because it loses nothing -- `retrieval_cost` skips
    any row whose last cell isn't an integer, which both the header and
    its separator are -- and `_count`'s advisory total is one high.
    Buying exactly-once would need a lock or a link-into-place dance,
    for a file whose whole point is to be cheap. See the module
    docstring, and docs/TOKENS.md for why a lock is the wrong instrument
    here.

    Write atomicity is deliberately *not* claimed. Both writes go
    through one buffered handle and may well reach the filesystem as a
    single small write -- but that is an implementation detail of how
    the template's size compares to a buffer, not behaviour to rely on:
    buffered text I/O can flush at points of its own choosing, closing
    may still issue more than one write, and POSIX does not promise that
    a write to a regular file arrives unsplit. Nothing here depends on
    any of that. `retrieval_cost` skips
    any row it cannot parse, so a torn row costs that one measurement
    and leaves every other row intact -- while a row overwritten at an
    offset would have been silently gone. The guarantee this function
    makes is the weaker, sufficient one: no writer addresses a position,
    so no writer can destroy what another wrote.
    """
    target = dossier_dir(draft)
    target.mkdir(parents=True, exist_ok=True)
    path = target / RETRIEVAL_MD
    safe_query = " ".join(query.split()).replace("|", "\\|")
    row = f"| {date.today().isoformat()} | {mode} | {safe_query} | {k} | {results} | {chars} |\n"
    with path.open("a", encoding="utf-8") as handle:
        if not handle.tell():
            handle.write(_RETRIEVAL_TEMPLATE)
        handle.write(row)
    return path


# `log_retrieval`'s `mode` is always "search" or "evidence" -- the two
# `python -m src.draft retrieve` subcommands. "revision" can't collide with a
# real logged call; it exists only so `retrieval_cost_by_revision` has
# something to split on.
_REVISION_MARKER_MODE = "revision"


def mark_revision(draft: Path, label: str = "") -> Path:
    """Append a revision-boundary marker to the dossier's `retrieval.md`.

    `retrieval.md` rows otherwise carry only a date (`log_retrieval` writes
    `date.today()`), and two revisions on the same day are indistinguishable
    by it. `draft-reviser`'s loop calls this once per pass, before any
    retrieval, precisely so same-day revisions don't get silently merged
    into one figure -- see `retrieval_cost_by_revision`, the reader this
    writes for.

    Shares `log_retrieval`'s append-only, no-offset-write discipline (see
    that function's docstring for why), even though nothing calls this one
    concurrently -- one write path is one fewer thing to get right twice.
    A marker with `results` and `chars` both 0 costs nothing towards
    `retrieval_cost`'s totals; it is real data only to
    `retrieval_cost_by_revision`, which reads it as a boundary rather than
    a call.
    """
    target = dossier_dir(draft)
    target.mkdir(parents=True, exist_ok=True)
    path = target / RETRIEVAL_MD
    safe_label = " ".join(label.split()).replace("|", "\\|")
    row = f"| {date.today().isoformat()} | {_REVISION_MARKER_MODE} | {safe_label} | 0 | 0 | 0 |\n"
    with path.open("a", encoding="utf-8") as handle:
        if not handle.tell():
            handle.write(_RETRIEVAL_TEMPLATE)
        handle.write(row)
    return path


def _retrieval_rows(dossier: Path) -> list[list[str]]:
    """The parseable rows of `retrieval.md`, six cells each.

    An integer `chars` cell is what separates a logged call from the
    template's own header and separator rows, which otherwise parse to
    six cells like any other. Advisory like every other read here: a
    hand-edited row that doesn't parse is skipped rather than raising.
    """
    path = dossier / RETRIEVAL_MD
    if not path.is_file():
        return []
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        # Split on unescaped pipes only: `log_retrieval` writes a query
        # containing a pipe as `\|`, which is markdown's literal, and
        # splitting there would cut the row into seven cells.
        cells = [cell.strip() for cell in _ROW_SPLIT.split(line.strip().strip("|"))]
        if len(cells) != 6:
            continue
        try:
            int(cells[5])
        except ValueError:
            continue
        rows.append(cells)
    return rows


def retrieval_cost(dossier: Path) -> tuple[int, int]:
    """(calls, characters returned) recorded in `retrieval.md`.

    Excludes `mark_revision`'s boundary rows: they record zero retrieval
    work by construction (`results` and `chars` are always 0), but without
    filtering them out here each one would still count as a "call" that
    fetched nothing, inflating this total by one per revision session.
    """
    rows = [row for row in _retrieval_rows(dossier) if row[1] != _REVISION_MARKER_MODE]
    return len(rows), sum(int(row[5]) for row in rows)


@dataclass
class RevisionCost:
    label: str
    calls: int
    chars: int


def retrieval_cost_by_revision(dossier: Path) -> list[RevisionCost]:
    """`retrieval_cost`, split at each `mark_revision` boundary.

    Rows logged before the first marker -- which is every row on a dossier
    revised before this existed, or one revised without `draft-reviser`'s
    loop -- form a leading segment labelled `"initial draft"`. Each marker
    after that starts a new segment, labelled with the text passed to
    `mark_revision` or, if none was given, `"revision N"` counted by marker
    order (so numbering stays stable even if an earlier revision logged no
    calls and is dropped below).

    A segment with no calls is dropped rather than reported as a
    zero-cost revision -- `mark-revision` costs nothing to call even when
    `draft-reviser` step 4 decides no search is needed, and a list of
    revisions padded with real ones that did nothing would obscure the
    ones that did.
    """
    rows = _retrieval_rows(dossier)
    segments: list[RevisionCost] = []
    label = "initial draft"
    marker_index = 0
    calls = chars = 0
    for row in rows:
        if row[1] == _REVISION_MARKER_MODE:
            if calls or chars:
                segments.append(RevisionCost(label, calls, chars))
            marker_index += 1
            # `mark_revision` escapes a pipe in the label the same way
            # `log_retrieval` escapes one in a query, so the row parses;
            # unescape it back for display, same as `recorded_queries`
            # does for a query cell.
            label = row[2].replace("\\|", "|") or f"revision {marker_index}"
            calls = chars = 0
            continue
        calls += 1
        chars += int(row[5])
    if calls or chars:
        segments.append(RevisionCost(label, calls, chars))
    return segments


def recorded_queries(dossier: Path) -> list[str]:
    """The distinct queries this draft was retrieved with, first seen first.

    `retrieval.md` was written to measure what a run cost, and this is
    the second thing it turns out to be good for: it is the only record
    of *what this draft went looking for*, which is what makes "the
    corpus grew" answerable as "and here is the part of the growth this
    draft would have wanted". Deduplicated because a reformulated search
    logs the same query more than once, and running it twice would just
    report the same candidate twice.

    Skips `mark_revision`'s boundary rows. Their third cell holds the
    `--label` text, not a query -- without this exclusion a label like
    "shorten intro" would be ranked against the corpus as if someone had
    searched for it, both here and in every caller (`corpus-reviser`'s
    sub-theme list, `status --all`'s candidate matching).
    """
    seen: dict[str, None] = {}
    for cells in _retrieval_rows(dossier):
        if cells[1] == _REVISION_MARKER_MODE:
            continue
        # `log_retrieval` escapes a pipe on the way in; unescape it so the
        # query goes to the ranker as the caller actually typed it.
        query = cells[2].replace("\\|", "|").strip()
        if query:
            seen[query] = None
    return list(seen)


def draft_relpath(draft: Path) -> str:
    """`draft` relative to the repo root where possible, for display."""
    try:
        return Path(draft).resolve().relative_to(config.REPO_ROOT).as_posix()
    except ValueError:
        return str(draft)


def init(draft: Path, genre: str) -> list[Path]:
    """Create the dossier skeleton for `draft`. Returns what it wrote.

    Only ever creates missing files, so re-running it on a dossier that
    a skill has since filled in adds whatever is absent and touches
    nothing else. That matters because `init` is the one command a genre
    skill runs before it knows what it will find -- it must not be able
    to destroy the thing it exists to protect.
    """
    target = dossier_dir(draft)
    target.mkdir(parents=True, exist_ok=True)
    corpus_keys = known_citekeys()
    corpus = (len(corpus_keys), digest(corpus_keys)) if corpus_keys is not None else None

    written: list[Path] = []
    contents = {
        "README.md": _readme(draft_name(draft), draft, genre),
        SCOPE_MD: _scope(draft, genre, corpus),
        **_TEMPLATES,
    }
    for name, body in contents.items():
        path = target / name
        if path.exists():
            continue
        path.write_text(body, encoding="utf-8")
        written.append(path)
    return written


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------


@dataclass
class FileStatus:
    name: str
    present: bool
    entries: int
    shape: str = "prose"


@dataclass
class Status:
    dossier: Path
    draft: Path | None
    files: list[FileStatus] = field(default_factory=list)
    outline: list[Section] = field(default_factory=list)
    recorded: tuple[int, str] | None = None
    current: tuple[int, str] | None = None
    unconsidered: set[str] = field(default_factory=set)
    retrieval_calls: int = 0
    retrieval_chars: int = 0
    revisions: list[RevisionCost] = field(default_factory=list)

    @property
    def drifted(self) -> bool:
        return bool(self.recorded and self.current and self.recorded[1] != self.current[1])


_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ROW_SPLIT = re.compile(r"(?<!\\)\|")


def _count(text: str, shape: str) -> int:
    """How many entries a dossier file holds. Advisory, not exact.

    Nothing depends on the number being right -- `status` prints it so a
    reader can see at a glance whether a file was filled in or left as
    the skeleton, and a hand-edited dossier that counts a little wrong
    still revises fine.
    """
    body = _COMMENT.sub("", text)
    if shape == "blocks":
        return sum(1 for line in body.splitlines() if line.startswith("## "))
    if shape == "rows":
        return sum(
            1
            for line in body.splitlines()
            if line.lstrip().startswith("|") and not set(line) <= set("|-: \t")
        ) - 1  # the header row, which every template ships with
    return sum(
        1
        for line in body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _resolve_dossier(draft_or_dossier: Path) -> Path:
    """A dossier directory, given either it or the draft it belongs to."""
    path = Path(draft_or_dossier)
    return path if path.is_dir() else dossier_dir(path)


def status(draft_or_dossier: Path) -> Status:
    """What this dossier holds, and whether the corpus has moved since.

    Never raises on a missing ledger or a missing dossier: this is the
    command someone runs to find out what they have, including on a
    machine where the corpus was never built and only a restored backup
    exists.
    """
    path = Path(draft_or_dossier)
    if path.is_dir():
        dossier, draft = path, find_draft(path)
    else:
        dossier, draft = dossier_dir(path), (path if path.is_file() else None)

    report = Status(dossier=dossier, draft=draft)
    for name, shape in FILES.items():
        file_path = dossier / name
        if file_path.is_file():
            entries = _count(file_path.read_text(encoding="utf-8"), shape)
            report.files.append(FileStatus(name, True, max(entries, 0), shape))
        else:
            report.files.append(FileStatus(name, False, 0, shape))

    if draft is not None:
        report.outline = sections(draft.read_text(encoding="utf-8"))
    # One parse of retrieval.md, not two: retrieval_cost_by_revision's
    # segments already exclude mark_revision's boundary rows the same
    # way retrieval_cost does, so the lifetime totals are just their sum
    # -- calling retrieval_cost here too would parse the same file twice
    # for numbers `_retrieval_rows` only needed to compute once.
    report.revisions = retrieval_cost_by_revision(dossier)
    report.retrieval_calls = sum(segment.calls for segment in report.revisions)
    report.retrieval_chars = sum(segment.chars for segment in report.revisions)

    report.recorded = recorded_corpus(dossier)
    corpus_keys = known_citekeys()
    if corpus_keys is not None:
        report.current = (len(corpus_keys), digest(corpus_keys))
        report.unconsidered = corpus_keys - cited_citekeys(dossier)
    return report


# --------------------------------------------------------------------------
# Dispatching from the dossier
#
# `status` and `drift` read a dossier on behalf of a human. This reads it
# on behalf of a *subagent*, and the difference is what the shape is for.
#
# A skill that fans out -- `deep-research` Phase 5 dispatches one writer
# per section -- has to give each subagent the evidence its section
# stands on. Pasting that evidence into the dispatch prompt spends it in
# the output pool, which is the expensive direction (docs/TOKENS.md), and
# spends it once per subagent. Handing over a command instead moves the
# same text into the subagent's own one-shot context, where it is billed
# once and discarded with that context.
#
# This does not, and cannot, shrink what the *orchestrator* is already
# carrying: a context is append-only between compactions, so material
# already returned into it stays. What it removes is the re-emission --
# and, because the dossier outlives the run, the need to re-derive any of
# it after a compaction or in a later session.
# --------------------------------------------------------------------------


@dataclass
class Brief:
    """The evidence a dispatched subagent was asked for, and what of it
    the dossier could not supply."""

    dossier: Path
    section: str | None = None  # the sections.md row this matched, if asked by section
    blocks: list[tuple[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    known_sections: list[str] = field(default_factory=list)


def _normalised(title: str) -> str:
    return " ".join(title.split()).casefold()


def _match_section(wanted: str, known: dict[str, list[str]]) -> str | None:
    """The `sections.md` row `wanted` names, or None if it names no single
    one.

    Exact first (modulo case and runs of whitespace), then a unique
    substring either way, so a writer dispatched for "Failure modes"
    matches the row a skill numbered "2. Failure modes" without the
    caller having to know how it was numbered.

    An ambiguous name matches *nothing* rather than the first candidate.
    Guessing here hands a section writer another section's evidence,
    which is the one failure mode this whole path has to avoid: it comes
    back as a fluent, correctly-cited section about the wrong thing.
    """
    target = _normalised(wanted)
    for title in known:
        if _normalised(title) == target:
            return title
    partial = [
        title for title in known
        if target in _normalised(title) or _normalised(title) in target
    ]
    return partial[0] if len(partial) == 1 else None


def brief(
    dossier: Path,
    citekeys: "list[str] | tuple[str, ...]" = (),
    section: str | None = None,
) -> Brief:
    """The kept-evidence blocks for `citekeys`, for `section`, or for both.

    Reports rather than raises, like everything else here -- but the
    report distinguishes three things a caller has to tell apart: a
    citekey with a block (`blocks`), one asked for with no block
    (`missing`), and a section name that matches no row (`section` back
    as None, with `known_sections` filled in).

    `missing` is the load-bearing one. A citekey that was retrieved,
    kept, and then never transcribed exists nowhere once the run that
    found it ends, and until this the loss was silent: the draft looked
    finished and the judgment behind it was gone. A dispatch that reads
    from here turns that into a named citekey at the moment it matters.
    """
    known = citekeys_by_section(dossier)
    matched = _match_section(section, known) if section else None
    report = Brief(dossier=dossier, section=matched, known_sections=list(known))
    if section and matched is None:
        return report

    asked: list[str] = []
    for citekey in list(known.get(matched, [])) + list(citekeys):
        if citekey not in asked:
            asked.append(citekey)

    blocks = evidence_blocks(dossier)
    for citekey in asked:
        if citekey in blocks:
            report.blocks.append((citekey, blocks[citekey]))
        else:
            report.missing.append(citekey)
    return report


# --------------------------------------------------------------------------
# Drift
#
# `status <draft>` answers "did the corpus move under this one draft?".
# This answers the other half: which drafts on this machine have gone
# stale, and what specifically about each. Read-only, lock-free, and
# never fatal -- a missing ledger, a missing dossier file and an
# unparsable row are all things to report, not to fail on.
# --------------------------------------------------------------------------


# How deep to look down each recorded query's ranking. 15 matches
# `survey-writer`'s own `search(sub_theme, k=15)`: the report should
# surface a new paper if and only if the draft's original search would
# have put it in front of the writer, and a different number here would
# quietly mean something else by "would have been considered".
CANDIDATE_K = 15


def _ephemeral_index(rows: list[sqlite3.Row]) -> dict:
    """A BM25 term-frequency index built in memory and thrown away.

    `src.retrieval.search()` cannot be used here, for two reasons that
    are both about this being a *report*. It connects through
    `ledger.connect()`, which mkdirs `content/`, executes the schema and
    runs migrations -- a write connection, which is exactly what
    `_corpus_rows` avoids. And it goes through `retrieval._load_index`,
    which calls `_save_cache` whenever any document's fingerprint moved
    -- which, after the sync that caused the drift being reported, is
    guaranteed. Either one would make an inspection mutate the corpus
    layer it is inspecting.

    The index itself is not the problem, though: `_tokenize_item` and
    `_bm25_scores` are pure, and the only thing that persists in
    `retrieval` is the cache write between them. So this composes the
    same two halves and skips the middle -- seeding from the on-disk
    cache where a fingerprint still matches (`_load_cache` only reads),
    tokenizing the rest into memory, and never writing back. A warm cache
    makes this nearly free; a cold or absent one costs one tokenization
    of the corpus, paid once per scan and dropped when it returns.

    Imported lazily so that `import src.dossier` stays as cheap as the
    rest of the module -- and it stays stdlib-only either way, since
    `src.retrieval` is too.
    """
    from src import retrieval

    cached = retrieval._load_cache()
    index = {}
    for row in rows:
        entry = cached.get(row["citekey"])
        if isinstance(entry, dict) and entry.get("fingerprint") == retrieval._fingerprint(row):
            index[row["citekey"]] = entry
        else:
            index[row["citekey"]] = retrieval._tokenize_item(row)
    return index


class Corpus:
    """The ledger read once, plus the throwaway index built from it.

    Held as one object so that a sweep over every dossier pays for the
    table read and the tokenization once between them all, rather than
    once each. The index is built on first use, so a sweep over dossiers
    that logged no queries never builds one at all.
    """

    def __init__(self, rows: list[sqlite3.Row]):
        self.rows = rows
        self.citekeys = {row["citekey"] for row in rows}
        self.titles = {row["citekey"]: row["title"] or "" for row in rows}
        self._index: dict | None = None

    @property
    def index(self) -> dict:
        if self._index is None:
            self._index = _ephemeral_index(self.rows)
        return self._index

    def matches(self, queries: list[str], k: int = CANDIDATE_K) -> dict[str, list[str]]:
        """citekey -> the recorded queries whose top-k it would land in."""
        from src import retrieval

        hits: dict[str, list[str]] = {}
        for query in queries:
            terms = retrieval._tokenize(query)
            if not terms:
                continue
            scores = retrieval._bm25_scores(self.index, terms)
            # Ties broken by citekey so that two runs over an unchanged
            # corpus report the same candidates in the same order.
            ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
            for citekey, _score in ranked:
                hits.setdefault(citekey, []).append(query)
        return hits


@dataclass
class Candidate:
    """A paper in the ledger that this dossier has never weighed, which
    one of the dossier's own recorded queries would have surfaced."""
    citekey: str
    title: str
    queries: list[str]


@dataclass
class Reconsider:
    """A paper this draft read and declined, which its queries still
    reach -- carried with the reason it was declined."""
    citekey: str
    title: str
    queries: list[str]
    reason: str


@dataclass
class Drift:
    dossier: Path
    name: str
    draft: Path | None
    corpus_available: bool = False
    recorded: tuple[int, str] | None = None
    current: tuple[int, str] | None = None
    missing: dict[str, list[str]] = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)
    reconsider: list[Reconsider] = field(default_factory=list)
    unconsidered: int = 0

    @property
    def drifted(self) -> bool:
        return bool(self.recorded and self.current and self.recorded[1] != self.current[1])

    @property
    def clean(self) -> bool:
        # `reconsider` is deliberately not part of this. A rejection that
        # still matches its query was true before the corpus moved and
        # will be true on every sweep after it -- counting it as drift
        # would mark every dossier that ever declined a paper permanently
        # stale, which is exactly the signal this command exists to give.
        return not self.missing and not self.candidates

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "dossier": draft_relpath(self.dossier),
            "draft": draft_relpath(self.draft) if self.draft else None,
            "corpus_available": self.corpus_available,
            "recorded": list(self.recorded) if self.recorded else None,
            "current": list(self.current) if self.current else None,
            "drifted": self.drifted,
            "missing": self.missing,
            "candidates": [
                {"citekey": c.citekey, "title": c.title, "queries": c.queries}
                for c in self.candidates
            ],
            "reconsider": [
                {"citekey": r.citekey, "title": r.title,
                 "queries": r.queries, "reason": r.reason}
                for r in self.reconsider
            ],
            "unconsidered": self.unconsidered,
        }


def dossier_name(dossier: Path) -> str:
    """A dossier's path under `content/dossiers/` -- what `list` prints."""
    try:
        return dossier.resolve().relative_to(config.DOSSIERS_DIR.resolve()).as_posix()
    except ValueError:
        return dossier.name


def drift(dossier: Path, corpus: "Corpus | None" = None) -> Drift:
    """What has gone stale about one dossier since its draft was written.

    Two findings, and they are not the same kind of thing. A **missing**
    citekey is a defect: the draft cites a paper the corpus no longer
    has, and something has to be swapped or dropped. A **candidate** is
    an opportunity: a paper the corpus has gained that this draft's own
    recorded queries would have put in front of the writer. The first is
    work; the second is a decision, and drift is still not itself a
    reason to redraft.

    Pass `corpus` to share one ledger read and one index across a sweep;
    omit it and this reads the ledger for itself.
    """
    dossier = Path(dossier)
    if corpus is None:
        rows = _corpus_rows()
        corpus = Corpus(rows) if rows is not None else None

    report = Drift(
        dossier=dossier,
        name=dossier_name(dossier),
        draft=find_draft(dossier),
        recorded=recorded_corpus(dossier),
    )
    if corpus is None:
        return report

    report.corpus_available = True
    report.current = (len(corpus.citekeys), digest(corpus.citekeys))

    sections_citing = section_citekeys(dossier)
    cited = _citekeys_in(dossier, CITED_FILES)
    report.missing = {
        citekey: sections_citing.get(citekey, [])
        for citekey in sorted(cited - corpus.citekeys)
    }

    # Everything the dossier ever weighed -- rejections included, which is
    # the point. Re-offering a paper the draft already turned down as if
    # it were new would cost exactly the re-judging that `rejected.md`
    # exists to prevent.
    mentioned = cited_citekeys(dossier)
    report.unconsidered = len(corpus.citekeys - mentioned)

    declined = rejected_reasons(dossier)
    matched = sorted(corpus.matches(recorded_queries(dossier)).items())
    report.candidates = [
        Candidate(citekey, corpus.titles.get(citekey, ""), queries)
        for citekey, queries in matched
        if citekey not in mentioned
    ]
    # A declined paper its queries still reach, reported separately and
    # with the reason. `cited` wins the tie: a citekey that is both cited
    # and listed as rejected is a stale `rejected.md` row, not an open
    # question, and offering it back would send a reviser to re-decide
    # something the draft already acts on.
    report.reconsider = [
        Reconsider(citekey, corpus.titles.get(citekey, ""), queries, declined[citekey])
        for citekey, queries in matched
        if citekey in declined and citekey not in cited
    ]
    return report


def drift_all() -> list[Drift]:
    """One drift report per dossier on this machine, nearest-first."""
    rows = _corpus_rows()
    corpus = Corpus(rows) if rows is not None else None
    return [drift(path, corpus) for path in all_dossiers()]


# --------------------------------------------------------------------------
# Backup and restore
# --------------------------------------------------------------------------


def _matches(relative: PurePosixPath, names: list[str]) -> bool:
    if not names:
        return True
    text = relative.as_posix()
    stem = relative.with_suffix("").as_posix()
    return any(
        text == name or stem == name or text.startswith(f"{name}/") for name in names
    )


def _strip_aid_suffix(relative: PurePosixPath) -> PurePosixPath:
    """`survey.provenance.md` -> `survey`, for matching a review report
    against the draft it belongs to.

    Drops the format suffix, then the aid suffix -- and only if it really
    is one of `review.AIDS`, so a draft named `survey.v2.md` keeps its
    `.v2` and its reports go on matching `topic/survey.v2`.
    """
    stem = relative.with_suffix("")
    if stem.suffix.lstrip(".") in review.AIDS:
        return stem.with_suffix("")
    return stem


def bundle_members(names: list[str], with_rendered: bool) -> list[tuple[Path, str]]:
    """(file on disk, name inside the archive) for everything to back up.

    Archive names are relative to `content/`, not to the repo root, so a
    bundle restores correctly into a checkout whose `[content].dir`
    points somewhere else.

    `content/review/` is included by default, filtered to the `.md`
    reports and the `.json` payloads beside them. That is the line
    `--with-rendered` already draws -- it exists to gate PDFs, not text
    -- and a bundle that dropped the review reports would quietly falsify
    the property they were given a mirrored path for, namely that a
    draft's evidence is findable from the draft. The same holds for the
    payload: it is that evidence as data, and leaving it out of the
    bundle would mean a restored draft's findings were readable by a
    person and not by the tools written to consume them (#127). Their
    `.tex`/`.pdf` renders sit in the same tree and are gated with
    everything else heavy.
    """
    roots = [("drafts", config.DRAFTS_DIR), ("dossiers", config.DOSSIERS_DIR),
             ("review", config.REVIEW_DIR)]
    if with_rendered:
        roots.append(("rendered", config.RENDERED_DIR))

    members: list[tuple[Path, str]] = []
    for label, root in roots:
        if root.is_dir():
            members.extend(_root_members(label, root, names, with_rendered))
    return members


def _root_members(label: str, root: Path, names: list[str],
                  with_rendered: bool) -> list[tuple[Path, str]]:
    """The (file, archive name) pairs one content root contributes."""
    members = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if (label == "review" and not with_rendered
                and path.suffix.lower() not in (".md", ".json")):
            continue
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if _matches(_match_target(label, relative), names):
            members.append((path, f"{label}/{relative.as_posix()}"))
    return members


def _match_target(label: str, relative: PurePosixPath) -> PurePosixPath:
    """What one archive member's path is matched against a draft name as.

    A dossier lives one directory deeper than its draft, so
    match its parent: `dossiers/topic/survey/scope.md` belongs
    to the draft named `topic/survey`. A review report mirrors
    the draft's path exactly, so it needs no such adjustment --
    but its own name carries the aid (`survey.provenance.md`),
    so strip exactly that before matching against a draft named
    `topic/survey`. Exactly that, not "two suffixes": a draft
    named `survey.v2.md` would otherwise have its reports
    double-stripped to `survey` and stop matching the draft.
    """
    if label == "dossiers":
        return relative.parent
    if label == "review":
        return _strip_aid_suffix(relative)
    return relative


def export(names: list[str], out: Path, with_rendered: bool = False) -> tuple[Path, int]:
    """Write a gzipped tar of the named drafts, their dossiers and their
    review reports (`.md`; the renders need `--with-rendered`)."""
    members = bundle_members(names, with_rendered)
    if not members:
        raise DossierError(
            "Nothing to export"
            + (f" matching {', '.join(names)}" if names else f" under {config.CONTENT_DIR}")
            + "."
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as archive:
        for path, name in members:
            archive.add(path, arcname=name)
    return out, len(members)


def _checked_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    """Every member, having refused the whole archive if any is unsafe.

    Refusing wholesale rather than skipping the bad member: a partially
    extracted backup is worse than none, because it looks like it worked.
    `extractall(filter="data")` below repeats the traversal checks -- this
    is not redundant, it is the layer that can say *which* member was
    wrong and that only the three directories this module owns are
    writable.
    """
    checked: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        if not (member.isfile() or member.isdir()):
            raise DossierError(
                f"{member.name!r} is not a regular file or directory "
                "(a link or device node). Refusing the whole archive."
            )
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts:
            raise DossierError(
                f"{member.name!r} escapes the extraction directory. "
                "Refusing the whole archive."
            )
        if not name.parts or name.parts[0] not in ARCHIVE_ROOTS:
            raise DossierError(
                f"{member.name!r} is not under {'/, '.join(ARCHIVE_ROOTS)}/. "
                "Refusing the whole archive."
            )
        checked.append(member)
    return checked


@dataclass
class RestorePlan:
    archive: Path
    new: list[Path] = field(default_factory=list)
    overwrite: list[Path] = field(default_factory=list)
    performed: bool = False


def restore(archive: Path, force: bool = False) -> RestorePlan:
    """Unpack a bundle under `content/`. A dry run unless `force`.

    Reporting first is the default because restoring is the only
    destructive thing in this module, and the case it exists for --
    "I need last month's draft back" -- is exactly the case where the
    working copy might be something you'd rather not lose to a
    mistyped archive name.
    """
    plan = RestorePlan(archive=archive)
    with tarfile.open(archive, "r:gz") as tar:
        members = _checked_members(tar)
        for member in members:
            if not member.isfile():
                continue
            target = config.CONTENT_DIR / member.name
            (plan.overwrite if target.exists() else plan.new).append(target)
        if force:
            config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
            tar.extractall(config.CONTENT_DIR, members=members, filter="data")
            plan.performed = True
    return plan


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_init(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    written = init(draft, args.genre)
    target = dossier_dir(draft)
    if not written:
        print(f"Dossier already complete: {draft_relpath(target)}")
    else:
        print(f"Dossier: {draft_relpath(target)}")
        for path in written:
            print(f"  created {path.name}")
        if known_citekeys() is None:
            print(f"\n  No ledger at {config.LEDGER_PATH}, so no corpus fingerprint was")
            print("  recorded. Drift checks will be unavailable for this dossier.")
    return 0


def _cmd_mark_revision(args: argparse.Namespace) -> int:
    path = mark_revision(Path(args.draft), args.label)
    print(f"Marked a revision boundary in {draft_relpath(path)}"
          + (f" ({args.label!r})" if args.label else "") + ".")
    return 0


# How many findings of one kind to print before summarising the rest.
# A drift report is read to decide what to do next, not as a manifest;
# what it must never do is truncate silently, so the remainder is always
# counted out loud.
_SHOWN = 10


def _print_drift(report: Drift) -> None:
    marker = "" if report.draft else "   (draft missing)"
    if not report.corpus_available:
        print(f"  {report.name}{marker}\n    drift unavailable -- no readable ledger.")
        return
    if report.clean:
        moved = " (corpus moved, nothing this dossier relies on)" if report.drifted else ""
        print(f"  {report.name}{marker}\n    no drift{moved}.")
        return

    print(f"  {report.name}{marker}")
    if report.missing:
        _print_capped(
            f"    {len(report.missing)} cited citekey(s) no longer in the ledger:",
            list(report.missing.items()), _render_missing)
    if report.candidates:
        _print_capped(
            f"    {len(report.candidates)} new candidate(s) matching this "
            "dossier's recorded queries:",
            report.candidates, _render_candidate)
    # Only alongside a real finding. On its own this is true on every
    # sweep forever, so printing it unconditionally would bury the drift
    # it is meant to help act on.
    if report.reconsider:
        _print_capped(
            f"    {len(report.reconsider)} previously rejected paper(s) these "
            "queries still reach:",
            report.reconsider, _render_reconsider)


def _print_capped(header: str, items: list, render) -> None:
    """A listing capped at _SHOWN entries that always counts its
    remainder out loud -- the never-truncate-silently rule stated at
    _SHOWN's definition, in one place instead of three."""
    print(header)
    for item in items[:_SHOWN]:
        render(item)
    if len(items) > _SHOWN:
        print(f"      ... and {len(items) - _SHOWN} more")


def _render_missing(item) -> None:
    citekey, in_sections = item
    where = f"  cited in: {', '.join(in_sections)}" if in_sections else ""
    print(f"      {citekey}{where}")


def _render_candidate(candidate) -> None:
    title = f"  {candidate.title}" if candidate.title else ""
    print(f"      {candidate.citekey}{title}")
    print(f"        surfaced by: {'; '.join(candidate.queries)}")


def _render_reconsider(entry) -> None:
    title = f"  {entry.title}" if entry.title else ""
    print(f"      {entry.citekey}{title}")
    print(f"        rejected because: {entry.reason}")


def _cmd_status_all(reports: list[Drift], as_json: bool) -> int:
    if as_json:
        print(json.dumps({"dossiers": [r.as_dict() for r in reports]}, indent=2))
    elif not reports:
        print(f"No dossiers under {draft_relpath(config.DOSSIERS_DIR)}.")
    else:
        _print_drift_summary(reports)
    return 0


def _print_drift_summary(reports: list[Drift]) -> None:
    """The human-readable half of `status --all`: every dossier's drift,
    then the how-to-read-this coda. Split from `_cmd_status_all` so the
    command keeps one exit and one return -- this text report cannot fail,
    which is exactly why it returns nothing."""
    print(f"Corpus drift across {len(reports)} dossier(s):\n")
    for report in reports:
        _print_drift(report)
    stale = [r for r in reports if not r.clean]
    # A dossier with no readable ledger has no findings, which is not the
    # same as having none to find. Reporting it as current would be the
    # one way this command could actively mislead: "nothing to do here"
    # asserted about a check that never ran.
    unknown = [r for r in reports if not r.corpus_available]
    print()
    if unknown:
        print(f"  {len(unknown)} of {len(reports)} dossier(s) could not be checked: "
              f"no readable ledger at {config.LEDGER_PATH}.")
        print("  Run `python -m src.corpus sync` to build one; until then drift is unknown,")
        print("  not absent.")
    if not stale:
        if not unknown:
            print("  Every dossier is current against the corpus.")
        return
    print(f"  {len(stale)} of {len(reports)} dossier(s) have drifted.")
    print("  A missing citekey is a defect: the draft cites what the corpus no")
    print("  longer has. A candidate is a decision, not a defect -- re-search only")
    print("  if the change you are making touches a sub-theme it could bear on.")
    if any(r.reconsider for r in stale):
        print("  Candidates exclude everything in `rejected.md`; the reconsider list is")
        print("  the exception, shown with its reason so you can judge whether it holds.")
    else:
        print("  `rejected.md` was already subtracted, so nothing here was turned "
              "down before.")


def _cmd_status(args: argparse.Namespace) -> int:
    if args.all and args.draft:
        print("[error] Give a draft path or --all, not both.", file=sys.stderr)
        return 2
    if not args.all and not args.draft:
        print("[error] Give a draft path, or --all for every dossier.", file=sys.stderr)
        return 2
    if args.all:
        return _cmd_status_all(drift_all(), args.json)
    if args.json:
        return _cmd_status_all([drift(_resolve_dossier(Path(args.draft)))], True)

    report = status(Path(args.draft))
    if not report.dossier.is_dir():
        print(f"No dossier at {draft_relpath(report.dossier)}.")
        print(f"Create one with `python -m src.draft dossier init {args.draft} --genre <genre>`.")
        return 1

    print(f"Dossier: {draft_relpath(report.dossier)}")
    _print_status_files(report)
    _print_status_retrieval(report)
    print()
    _print_status_drift(report)
    return 0


def _print_status_files(report: Status) -> None:
    """The draft line and the per-file table."""
    if report.draft is not None:
        print(f"  draft         {draft_relpath(report.draft)} ({len(report.outline)} sections)")
    else:
        print("  draft         MISSING -- the dossier outlived its draft")
    for entry in report.files:
        # A count means something for the two files that are lists
        # (evidence blocks, rejected/section rows) and nothing for the
        # three that are prose -- "scope.md: 40 entries" would be a
        # number dressed up as information.
        if not entry.present:
            print(f"  {entry.name:<14}absent")
        elif not entry.entries:
            print(f"  {entry.name:<14}empty (skeleton only)")
        elif entry.shape == "prose":
            print(f"  {entry.name:<14}filled in")
        else:
            print(f"  {entry.name:<14}{entry.entries} entr{'y' if entry.entries == 1 else 'ies'}")


def _print_status_retrieval(report: Status) -> None:
    """The retrieval cost block, when this dossier logged any calls."""
    if not report.retrieval_calls:
        return
    kept = next((f.entries for f in report.files if f.name == EVIDENCE_MD), 0)
    rejected = next((f.entries for f in report.files if f.name == REJECTED_MD), 0)
    print(f"\nRetrieval: {report.retrieval_calls} call(s) returned "
          f"{report.retrieval_chars:,} characters")
    if kept or rejected:
        print(f"  {kept} kept, {rejected} rejected")
    else:
        # Searched, and recorded nothing it found. Reported rather
        # than blocked, like every other check outside the citation
        # gate: it costs a comparison of two numbers already on this
        # report, and nothing else in the pipeline can see it -- the
        # draft looks finished and the judgment behind it is gone.
        #
        # "no entries" rather than "empty": both counts are 0 for an
        # absent file too, and the per-file lines above already
        # distinguish `absent` from `empty (skeleton only)`. Calling
        # a missing file empty would contradict them.
        print("  but evidence.md and rejected.md hold no entries -- this run")
        print("  searched and recorded nothing it found, so a revision will")
        print("  have to re-retrieve and re-judge the same candidates.")

    # Only worth a breakdown once there's more than one segment --
    # with just one, it would repeat the total line above under a
    # different label. A dossier revised before `mark-revision`
    # existed has exactly one ("initial draft") for the same reason a
    # dossier with no revisions yet does: nothing split it.
    if len(report.revisions) > 1:
        print("  by revision:")
        for segment in report.revisions:
            print(f"    {segment.label:<24}{segment.calls} call(s), "
                  f"{segment.chars:,} characters")


def _print_status_drift(report: Status) -> None:
    """The corpus drift block: unavailable, unchanged, or changed with
    the unconsidered citekeys named."""
    if report.current is None:
        print(f"Corpus drift: unavailable -- no readable ledger at {config.LEDGER_PATH}.")
        return
    if report.recorded is None:
        print("Corpus drift: unavailable -- scope.md records no corpus fingerprint.")
        print(f"  now: {report.current[0]} citekeys, digest {report.current[1]}")
        return

    print("Corpus drift since this draft:")
    print(f"  recorded  {report.recorded[0]} citekeys, digest {report.recorded[1]}")
    print(f"  now       {report.current[0]} citekeys, digest {report.current[1]}")
    if not report.drifted:
        print("  unchanged -- the dossier's evidence is current.")
        return
    print(f"  CHANGED ({report.current[0] - report.recorded[0]:+d} citekeys)")
    if report.unconsidered:
        shown = sorted(report.unconsidered)[:10]
        print(f"\n  {len(report.unconsidered)} citekey(s) in the ledger appear nowhere in "
              "this dossier:")
        for citekey in shown:
            print(f"    {citekey}")
        if len(report.unconsidered) > len(shown):
            print(f"    ... and {len(report.unconsidered) - len(shown)} more")
        print("\n  Re-search only if the change you are making touches a sub-theme")
        print("  these could bear on. Drift is not itself a reason to redraft.")


def _cmd_sections(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    if not draft.is_file():
        print(f"No such draft: {draft}", file=sys.stderr)
        return 1
    if args.write and not args.citekeys:
        # Refused rather than assumed: the bare form prints an outline,
        # and writing that into sections.md would replace the citekey
        # relation with a heading list.
        print("--write needs --citekeys.", file=sys.stderr)
        return 1
    text = draft.read_text(encoding="utf-8")
    if args.citekeys:
        return _sections_citekeys(draft, text, args.write)
    outline = sections(text)
    if not outline:
        print(f"No headings in {draft_relpath(draft)}.")
        return 0
    print(f"{draft_relpath(draft)}")
    for section in outline:
        indent = "  " * (section.level - 1)
        span = f"{section.start}-{section.end}"
        print(f"  {span:>12}  ({section.lines:>4} lines)  {indent}{section.title}")
    print("\n  Read one section with offset=<start>, limit=<lines>; edit inside that")
    print("  range rather than rewriting the file.")
    return 0


def _sections_citekeys(draft: Path, text: str, write: bool) -> int:
    """`sections --citekeys`: the derived table, printed or written.

    Exit code 1 when the draft has no headings, because there is then no
    table to build and a caller that piped this somewhere should hear
    about it rather than write an empty file.
    """
    per_section, unattributed = attribute_citekeys(text)
    if not per_section:
        print(f"No headings in {draft_relpath(draft)}.", file=sys.stderr)
        return 1

    table = sections_markdown(text)
    if write:
        target = dossier_dir(draft) / SECTIONS_MD
        if not target.parent.is_dir():
            print(
                f"No dossier for {draft_relpath(draft)} -- run `init` first.",
                file=sys.stderr,
            )
            return 1
        target.write_text(table, encoding="utf-8")
        print(f"{target}: {len(per_section)} section(s) from {draft_relpath(draft)}")
    else:
        print(table, end="")

    if unattributed:
        # Said out loud rather than dropped: a citekey cited above the
        # first heading is real evidence the table cannot place, and a
        # reviser reading only the table would never learn it exists.
        print(
            "Cited before the first heading, so in no section: "
            + ", ".join(f"`{key}`" for key in unattributed),
            file=sys.stderr,
        )
    return 0


def _cmd_brief(args: argparse.Namespace) -> int:
    """Exit codes: 0 when it printed at least one block, 1 when it could
    not print any.

    A caller of this is a dispatch prompt, not a person, so "nothing
    here" has to be a status code rather than a paragraph -- a subagent
    that reads an empty brief and writes the section anyway produces
    exactly the ungrounded prose this project exists to prevent. Every
    diagnostic goes to stderr so that stdout is only ever the evidence.
    """
    if not args.citekeys and not args.section:
        print("Name at least one citekey, or a section with --section. "
              "`brief` selects rows; it deliberately won't dump the whole "
              "of evidence.md into a reader's context.", file=sys.stderr)
        return 1

    target = _resolve_dossier(Path(args.draft))
    if not target.is_dir():
        print(f"No dossier at {draft_relpath(target)}. Create one with "
              f"`python -m src.draft dossier init {args.draft} --genre <genre>`.",
              file=sys.stderr)
        return 1

    report = brief(target, args.citekeys, args.section)
    if args.section and report.section is None:
        _explain_unknown_section(args.section, target, report)
        return 1

    label = f"{dossier_name(target)}"
    if report.section:
        label += f" -- section {report.section!r}"
    asked = len(report.blocks) + len(report.missing)
    print(f"# Kept evidence: {label}", file=sys.stderr)
    print(f"#   {len(report.blocks)} of {asked} citekey(s) from "
          f"{draft_relpath(target / EVIDENCE_MD)}", file=sys.stderr)

    if not args.check:
        for _, block in report.blocks:
            print(f"\n{block}", end="")

    _warn_brief_gaps(report, asked)
    return 0 if report.blocks else 1


def _explain_unknown_section(section: str, target: Path, report: Brief) -> None:
    """stderr for a --section that matched nothing: what is there instead."""
    print(f"No section matching {section!r} in "
          f"{draft_relpath(target / SECTIONS_MD)}.", file=sys.stderr)
    if report.known_sections:
        print("  Sections it does hold:", file=sys.stderr)
        for title in report.known_sections:
            print(f"    {title}", file=sys.stderr)
    else:
        print("  sections.md holds no rows yet -- the run that dispatches by "
              "section writes the section -> citekey plan there first.",
              file=sys.stderr)


def _warn_brief_gaps(report: Brief, asked: int) -> None:
    """The two ungrounded-evidence warnings a brief can end with."""
    if report.missing:
        print(f"\n[warn] {len(report.missing)} citekey(s) have no block in "
              "evidence.md, so nothing here grounds them:", file=sys.stderr)
        for citekey in report.missing:
            print(f"    {citekey}", file=sys.stderr)
        print("  Either the run that found them never transcribed them -- in "
              "which case they are gone and have to be re-retrieved -- or they "
              "are misspelled here.", file=sys.stderr)
    elif not asked:
        # A row that exists and assigns nothing. Distinct from a name
        # that matched no row, and it wants the opposite fix: the plan
        # has a gap in it, rather than the caller having mistyped.
        print("\n[warn] That section is planned but has no citekeys assigned "
              "to it, so there is nothing to write from. Assign its evidence "
              "in sections.md, or don't dispatch a writer for it.",
              file=sys.stderr)


def _cmd_list(args: argparse.Namespace) -> int:
    found = all_dossiers()
    if not found:
        print(f"No dossiers under {config.DOSSIERS_DIR}.")
    else:
        for dossier in found:
            draft = find_draft(dossier)
            name = dossier.resolve().relative_to(config.DOSSIERS_DIR.resolve()).as_posix()
            marker = "" if draft else "   (draft missing)"
            print(f"  {name}{marker}")
        print(f"\n  {len(found)} dossier(s) under {draft_relpath(config.DOSSIERS_DIR)}.")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    if args.out:
        out = Path(args.out)
    else:
        label = "-".join(name.replace("/", "-") for name in args.names) or "all"
        out = Path(f"drafts-{label}-{date.today().isoformat()}.tar.gz")
    try:
        written, count = export(args.names, out, args.with_rendered)
    except DossierError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    size = written.stat().st_size
    print(f"  {written}  ({count} file(s), {size / 1024:.1f} KiB)")
    print("\n  Restore with:")
    print(f"    python -m src.draft dossier restore {written} --force")
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    archive = Path(args.archive)
    if not archive.is_file():
        print(f"No such archive: {archive}", file=sys.stderr)
        return 1
    try:
        plan = restore(archive, args.force)
    except (DossierError, tarfile.TarError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    verb = "Restored" if plan.performed else "Would restore"
    print(f"{verb} into {draft_relpath(config.CONTENT_DIR)}:")
    print(f"  {len(plan.new)} new file(s)")
    print(f"  {len(plan.overwrite)} existing file(s) "
          f"{'overwritten' if plan.performed else 'would be OVERWRITTEN'}")
    for path in plan.overwrite[:10]:
        print(f"    {draft_relpath(path)}")
    if len(plan.overwrite) > 10:
        print(f"    ... and {len(plan.overwrite) - 10} more")
    if not plan.performed:
        print("\n  Dry run. Re-run with --force to write:")
        print(f"    python -m src.draft dossier restore {archive} --force")
    return 0


# A BCP-47 tag's shape, not a list of the ones this repo can check. The
# dossier records what a human declared; `src.draft style` decides
# separately which declarations it has rules for, and says so when it has
# none. Validating against the checker's list here would stop someone
# recording a true fact about their draft merely because no rule exists
# for it yet.
_LANGUAGE_TAG = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")

_LANGUAGE_LINE = re.compile(r"^- language:.*$", re.MULTILINE)


def set_language(draft: Path, tag: str) -> Path:
    """Record `tag` as the draft's dialect in its dossier `scope.md`.

    Replaces the line if one is there -- including the "not settled"
    placeholder `init` ships -- and inserts it after `- genre:` if not,
    which is where the template puts it and where a reader looks. Every
    dossier written before 5.12.0 lacks the line entirely, so the insert
    path is the common one rather than the edge.
    """
    if not _LANGUAGE_TAG.match(tag):
        raise ValueError(
            f"{tag!r} is not a BCP-47 language tag. Expected a form like "
            "en-GB, en-US or en-IN."
        )
    scope = dossier_dir(draft) / SCOPE_MD
    if not scope.is_file():
        raise FileNotFoundError(
            f"No scope.md for {draft}. Run `python -m src.draft dossier init "
            f"{draft} --genre <genre>` first."
        )
    text = scope.read_text(encoding="utf-8")
    line = f"- language: {tag}"
    if _LANGUAGE_LINE.search(text):
        text = _LANGUAGE_LINE.sub(line, text, count=1)
    else:
        text = text.replace("- genre:", f"{line}\n- genre:", 1) \
            if "- genre:" in text else text.replace("# Scope\n", f"# Scope\n\n{line}\n", 1)
    scope.write_text(text, encoding="utf-8")
    return scope


def _cmd_set_language(args) -> int:
    try:
        scope = set_language(Path(args.draft), args.language)
    except (ValueError, FileNotFoundError, config.OutsideContentDir) as exc:
        print(f"  {exc}", file=sys.stderr)
        return 1
    print(f"  language: {args.language}  ->  {scope}")
    return 0


def suggest_acronyms(draft: Path) -> dict[str, str]:
    """Glossary terms that look like an acronym and aren't in the
    vocabulary yet -- candidates for the user's own acronyms file.

    Never writes anything. `python -m src.draft dossier acronyms-suggest`
    only prints these: #190's own rule is that this feature proposes and
    the human accepts, the same as every other vocabulary file this
    pipeline reads but never edits (papers/bibliography.bib,
    content/verbatim_allowlist.toml). The matching itself is
    `acronyms.suggest()` -- this is just glossary_terms() handed to it.
    """
    return acronyms.suggest(glossary_terms(draft))


def _cmd_acronyms_suggest(args) -> int:
    candidates = suggest_acronyms(Path(args.draft))
    if not candidates:
        print("  No new acronyms to suggest.")
        return 0
    print(
        "  New acronyms in this draft's glossary, not yet in your "
        "vocabulary. Nothing is written -- add what you want to your own "
        "[style].acronyms file:\n"
    )
    for term, definition in sorted(candidates.items()):
        print(f'  {term} = "{definition}"')
    return 0


_DRAFT_PATH_HELP = "Path to the draft under content/drafts/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.draft dossier",
        description="The working state behind a draft: create it, inspect it, "
                    "back it up, restore it. Stdlib only; never writes to the "
                    "corpus layer.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a dossier skeleton for a draft")
    p_init.add_argument("draft", help=_DRAFT_PATH_HELP)
    p_init.add_argument("--genre", required=True,
                        help="survey, thesis-chapter, textbook-chapter, tutorial, deep-research")
    p_init.set_defaults(func=_cmd_init)

    p_status = sub.add_parser("status", help="What a dossier holds, and corpus drift since")
    p_status.add_argument("draft", nargs="?",
                          help="Draft path, or the dossier directory itself")
    p_status.add_argument("--all", action="store_true",
                          help="One drift report over every dossier instead")
    p_status.add_argument("--json", action="store_true",
                          help="Machine-readable drift report (for draft-reviser)")
    p_status.set_defaults(func=_cmd_status)

    p_mark_revision = sub.add_parser(
        "mark-revision",
        help="Record a revision-session boundary, so retrieval cost totals per revision")
    p_mark_revision.add_argument("draft", help=_DRAFT_PATH_HELP)
    p_mark_revision.add_argument(
        "--label", default="",
        help="Short name for this revision (the date is already recorded)")
    p_mark_revision.set_defaults(func=_cmd_mark_revision)

    p_sections = sub.add_parser(
        "sections", help="Heading -> line range, for reading and editing one section")
    p_sections.add_argument("draft", help="Path to the draft")
    p_sections.add_argument(
        "--citekeys", action="store_true",
        help="Print the dossier's sections.md table -- heading -> the citekeys "
             "cited under it -- derived from the draft instead of by hand")
    p_sections.add_argument(
        "--write", action="store_true",
        help="With --citekeys: write the table to the dossier's sections.md")
    p_sections.set_defaults(func=_cmd_sections)

    p_brief = sub.add_parser(
        "brief", help="The kept evidence for one section, for a subagent to read")
    p_brief.add_argument("draft", help="Draft path, or the dossier directory itself")
    p_brief.add_argument("citekeys", nargs="*", help="Citekeys to print the blocks for")
    p_brief.add_argument("--section",
                         help="Take the citekeys from this sections.md row instead")
    p_brief.add_argument("--check", action="store_true",
                         help="Report what resolves without printing the blocks")
    p_brief.set_defaults(func=_cmd_brief)

    p_set_language = sub.add_parser(
        "set-language",
        help="Record the draft's dialect, so `src.draft style` can check it",
    )
    p_set_language.add_argument("draft", help=_DRAFT_PATH_HELP)
    p_set_language.add_argument("language", help="a BCP-47 tag: en-GB, en-US, en-IN")
    p_set_language.set_defaults(func=_cmd_set_language)

    p_suggest = sub.add_parser(
        "acronyms-suggest",
        help="Acronyms this draft's glossary defines that aren't in your vocabulary yet",
    )
    p_suggest.add_argument("draft", help=_DRAFT_PATH_HELP)
    p_suggest.set_defaults(func=_cmd_acronyms_suggest)

    p_list = sub.add_parser("list", help="Every dossier on this machine")
    p_list.set_defaults(func=_cmd_list)

    p_export = sub.add_parser("export", help="Back up drafts and dossiers to a tar.gz")
    p_export.add_argument("names", nargs="*",
                          help="Draft names to include (default: everything)")
    p_export.add_argument("--out", help="Archive path (default: drafts-<name>-<date>.tar.gz)")
    p_export.add_argument("--with-rendered", action="store_true",
                          help="Include content/rendered/, and the .tex/.pdf renders "
                               "of content/review/'s reports (large: PDFs)")
    p_export.set_defaults(func=_cmd_export)

    p_restore = sub.add_parser("restore", help="Unpack a bundle (dry run unless --force)")
    p_restore.add_argument("archive", help="Path to a tar.gz written by `export`")
    p_restore.add_argument("--force", action="store_true",
                           help="Actually write, overwriting what is already there")
    p_restore.set_defaults(func=_cmd_restore)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except DossierError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
