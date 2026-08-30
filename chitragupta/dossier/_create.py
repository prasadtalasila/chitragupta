"""Everything `dossier init` writes: the seven per-dossier template
files and the logic that decides which of them are still missing.

Split out of chitragupta/dossier.py (#219).
"""

import argparse
from datetime import date
from pathlib import Path

from chitragupta import config
from chitragupta.dossier import (
    EVIDENCE_MD,
    OUTLINE_MD,
    REJECTED_MD,
    RETRIEVAL_MD,
    REVISIONS_MD,
    SCOPE_MD,
    SECTIONS_MD,
    STEERING_MD,
    _SECTIONS_TEMPLATE,
    digest,
    dossier_dir,
    draft_name,
    draft_relpath,
    known_citekeys,
)


def _readme(name: str, draft: Path, genre: str) -> str:
    return f"""# Dossier: {name}

The working state that produced `{draft_relpath(draft)}` -- what a later
session needs in order to revise it without re-running the drafting
pipeline. Genre: {genre}.

| File | What it holds |
|---|---|
| `scope.md` | reader, dialect, what the draft covers/excludes, glossary, corpus/draft digests |
| `evidence.md` | each citekey kept, why, and the supporting quote or paraphrase |
| `rejected.md` | candidates retrieved and turned down, with the reason |
| `sections.md` | section heading -> the citekeys cited under it |
| `steering.md` | what the user asked for in chat that the draft doesn't show |
| `revisions.md` | append-only log of what changed and why |
| `retrieval.md` | every retrieval call, its result size, and a `mark-revision` boundary per pass |

This directory is gitignored, like the draft it describes. Back it up and
restore it with:

    python -m chitragupta.draft dossier export {name}
    python -m chitragupta.draft dossier restore <archive.tar.gz> --force

A bundle carries drafts and dossiers, not the corpus: `content/ledger.sqlite`
is regenerable with `python -m chitragupta.corpus sync`, and `papers/bibliography.bib` is
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
- draft digest: not recorded (run `dossier stamp` once the draft is ready)

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

<!-- Appended by `python -m chitragupta.draft retrieve ... --log <draft>`, never by
     hand.

     `asked` is how much that call requested -- `--k` for search,
     `--windows` for evidence. `chars` is the size of the payload it
     handed back: the thing that then sits in the caller's context for
     the rest of the run. Together with evidence.md's and rejected.md's
     counts, this is what turns "retrieval is where the tokens go" from
     an estimate into a measurement for a particular draft.

     A row with mode `revision` is not a call: `python -m chitragupta.draft dossier
     mark-revision` writes one, at the start of each draft-reviser pass,
     so `dossier status` can total retrieval cost per revision instead of
     only as one lifetime figure -- the date column alone can't tell two
     same-day revisions apart.

     `collection` is the Zotero collection `--collection` scoped the call
     to, empty for a corpus-wide call -- which is also how every row
     written before this column existed reads, since an absent seventh
     cell is padded in the same way (#254). Without it, a scoped call and
     a corpus-wide one write byte-identical rows, and `dossier status`
     re-asks a scoped draft's queries against the whole corpus.

     `origin` is `declared` or `extended` (#455) -- whether the query came
     verbatim from outline.md or was added with `--origin extended`
     because a declared section came up thin. Empty for a call that named
     neither, padded in the same way for a row written before this column
     existed -- but unlike `collection`'s empty reading, that is not read
     as "declared": a pre-outline.md call was neither. Without this
     column, "did this draft follow the outline it declared?" has no
     evidence to answer from. -->

| date | mode | query | asked | results | chars | collection | origin |
|---|---|---|---|---|---|---|---|
"""


_OUTLINE_TEMPLATE = """<!-- Outline. Edited by hand before drafting. Per `##`-or-deeper heading:
     `brief:` (steering, never appears in the draft) and/or one or more
     `claim:` blocks (your own prose, rewritten -- every sentence that
     can't be grounded is reported rather than shipped), and an
     optional `queries:` list of the search terms to run verbatim
     instead of the skill inventing sub-themes. A section needs at
     least a brief or a claim; queries: is optional -- plenty of
     sections are pure framing prose with nothing to search for.

     Declared queries bind by default. `--origin extended` on the
     skill's own retrieval calls covers a section that came up thin,
     logged distinctly so `python -m chitragupta.draft dossier outline <draft>`
     can report whether the draft ran what this file declared.

     Before filling this in, run a broad search or two on the topic
     (`python -m chitragupta.draft retrieve search "<topic>"`) and skim
     what the corpus actually returns -- an outline written blind is one
     whose sections the corpus may not support.

     Example:

     ## Failure modes of co-simulation

     brief: Focus on timestep mismatch and solver divergence; skip
     FMI-specific tooling.

     queries:
     - failure modes co-simulation
     - timestep mismatch solver divergence
-->

"""


_TEMPLATES = {
    EVIDENCE_MD: _EVIDENCE_TEMPLATE,
    REJECTED_MD: _REJECTED_TEMPLATE,
    SECTIONS_MD: _SECTIONS_TEMPLATE,
    STEERING_MD: _STEERING_TEMPLATE,
    REVISIONS_MD: _REVISIONS_TEMPLATE,
    RETRIEVAL_MD: _RETRIEVAL_TEMPLATE,
}


def init(draft: Path, genre: str, outline: bool = False) -> list[Path]:
    """Create the dossier skeleton for `draft`. Returns what it wrote.

    Only ever creates missing files, so re-running it on a dossier that
    a skill has since filled in adds whatever is absent and touches
    nothing else. That matters because `init` is the one command a genre
    skill runs before it knows what it will find -- it must not be able
    to destroy the thing it exists to protect.

    `outline` is opt-in (#455): most dossiers have no `outline.md`, so it
    is not one of the seven files every dossier always gets -- see
    `OUTLINE_MD`'s own docstring for why that distinction matters to
    `status`. Stdlib-only and ledger-read-only like the rest of `init`:
    the broad-call survey a human runs before filling `outline.md` in is
    an ordinary `retrieve search`, not something this command runs for
    them -- `init` stays the one command a genre skill can call before it
    knows what it will find.
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
    if outline:
        contents[OUTLINE_MD] = _OUTLINE_TEMPLATE
    for name, body in contents.items():
        path = target / name
        if path.exists():
            continue
        path.write_text(body, encoding="utf-8")
        written.append(path)
    return written


def _cmd_init(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    written = init(draft, args.genre, outline=args.outline)
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
