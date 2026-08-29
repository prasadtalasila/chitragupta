"""`--for-draft`'s scope resolution: the citekey set, the stages that
refuse to be narrowed, and the corpus filter itself.

Split from `chitragupta/enrich/__main__.py` (#441): everything here
answers a question about the file the user named, before the pipeline
lock is taken -- `resolve_scope` runs entirely off the ledger and the
draft's own text, and `scope_corpus` only narrows a list already handed
to it. Neither reaches into a running stage or the lock `__main__.py`
holds while stages execute.

`scope_corpus` takes its reporting function (`_say`) as a parameter
rather than importing it back from `__main__.py`, the same shape
`chitragupta/retrieval_cache.py` uses for its tokenizer: `__main__.py`
is a flat module executed as `__main__` under `python -m
chitragupta.enrich`, so a plain import back from it would hit the same
circular-import trap `chitragupta/retrieval.py`'s split ran into --
avoided here by never creating the cycle in the first place.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from chitragupta import citation_gate, config

# The stages --for-draft refuses to run, rather than running over a
# subset. Each writes one whole-corpus artefact whose partial form is
# indistinguishable from its complete one: `embed` upserts into a Chroma
# collection that records no completeness marker, and four skills branch
# on nothing more than "does content/chroma/ exist" before searching it,
# so a collection holding a draft's eleven papers would answer as if it
# held the corpus; `bertopic` overwrites content/topics.json outright, so
# a scoped run replaces a corpus-wide topic model with an eleven-document
# one; `seed-topics` overwrites content/topic_seeds.json the same way, and
# its whole value is telling an author which of their papers no seed
# phrase describes -- an answer computed over eleven of them is not a
# smaller version of that answer, it is a wrong one. Allowing any of the
# three would mean inventing that marker, which is a larger change than
# this filter and belongs to its own issue.
#
# This is a tier and not a ladder, in docs/LADDERS.md's vocabulary: the
# run stops and names what it cannot give you, rather than quietly
# substituting the whole corpus (an hour of work nobody asked for) or a
# fraction of it (an index that lies about its coverage).
SCOPE_REFUSED = ("embed", "bertopic", "seed-topics", "converge")

# The stages that read the corpus at all -- every stage there is, since
# 4.0.0 removed the two per-draft passthroughs. Kept as its own name
# rather than folded into STAGE_ORDER because it answers a different
# question: an empty scope is only a reason to stop if some stage was
# going to use it, and SCOPE_REFUSED says which stages refuse to have a
# scope narrowed rather than which read one.
CORPUS_STAGES = ("docling", "embed", "bertopic", "seed-topics", "converge")

# 3, not 2: argparse already exits 2 for a usage error it detects
# itself, and runlock.EXIT_ALREADY_RUNNING is 2 as well. A wrapper needs
# to tell "you asked for something incoherent" apart from "someone else
# holds the lock, try later", because only the second is worth retrying.
EXIT_BAD_SCOPE = 3


def draft_citekeys(path: Path) -> set[str]:
    """Every citekey `path` cites, as the docling stage's scope.

    citation_gate.extract_citekeys() rather than a regex of this
    script's own, for two reasons: it is the same reader the hard gate
    uses, so a scoped run covers exactly the papers the gate will check
    the draft against, and it is whole-document rather than per-line, so
    a `\\citep{a,\\n b}` wrapped across lines contributes both keys
    (extract_citekeys_from_line would contribute neither).

    Returns a set: a draft cites the same paper many times, and the
    caller wants the papers, not the citations.
    """
    return {key for _, key in citation_gate.extract_citekeys(path.read_text(encoding="utf-8"))}


def resolve_scope(args, selected) -> "tuple[set[str] | None, int | None]":
    """--for-draft's citekey set, or the exit code refusing it.

    Returns (scope, None) on success and (None, EXIT_BAD_SCOPE) on any
    refusal, so main() has one place to bail. All of it runs before the
    lock: every answer here is a property of the file the user named,
    answerable without the ledger, so there is no reason to make a
    concurrent sync wait for it.
    """
    # Refused against the stages the user *typed*, not against the
    # default: a bare --for-draft selects docling alone in
    # _selected_stages and never reaches this branch, so the only way
    # here is having asked for a scoped embed or bertopic in so many
    # words.
    refused = sorted(selected & set(SCOPE_REFUSED))
    if refused:
        print(
            f"  --for-draft cannot scope {' or '.join(refused)}: "
            f"{'they each build' if len(refused) > 1 else 'it builds'} one whole-corpus "
            "artefact, and a partial one is indistinguishable from a complete one. Run "
            "them as separate commands:\n"
            f"      python -m chitragupta.enrich --for-draft {args.for_draft} --stages docling\n"
            f"      python -m chitragupta.enrich --stages {','.join(refused)}"
        )
        return None, EXIT_BAD_SCOPE

    draft_path = Path(args.for_draft)
    try:
        scope = draft_citekeys(draft_path)
    except OSError as exc:
        print(f"  cannot read --for-draft {draft_path}: {exc}")
        return None, EXIT_BAD_SCOPE
    except UnicodeDecodeError as exc:
        # A separate branch because it is a separate failure:
        # UnicodeDecodeError is a ValueError, so the clause above
        # does not catch it, and the fix is different enough to be
        # worth naming. Not read with errors="replace" instead --
        # a replacement character lands in the middle of whatever
        # citekey the bad byte was part of, and the run would then
        # scope itself to a quietly wrong set of papers rather than
        # stopping.
        print(
            f"  cannot read --for-draft {draft_path} as UTF-8: {exc}\n"
            "      Every draft this pipeline writes is UTF-8, so this one came from "
            "somewhere else -- re-save it in that encoding."
        )
        return None, EXIT_BAD_SCOPE
    if not scope:
        print(
            f"  no citations found in {draft_path} -- nothing to scope the run to. "
            "Drop --for-draft to enrich the whole corpus."
        )
        return None, EXIT_BAD_SCOPE
    return scope, None


def scope_corpus(docs, scope, args, selected, say: Callable[..., None]) -> tuple[list, int | None]:
    """The corpus narrowed to --for-draft's citekeys, with the losses named.

    The filter sits here rather than inside build_corpus(): that
    function's whole contract is "every ledger item", the full SELECT is
    microseconds next to any stage, and keeping the unfiltered list in
    hand is what lets the count below say what was left out instead of
    only what was kept.

    `say` is `__main__.py`'s own `_say` (module docstring explains why
    it is a parameter rather than an import).

    Returns (docs, None), or (docs, EXIT_BAD_SCOPE) when a corpus stage
    was asked to run over nothing.
    """
    total = len(docs)
    docs = [doc for doc in docs if doc.citekey in scope]
    say(
        f"Corpus: {len(docs)} of {total} doc(s) from {config.BIB_FILE_PATH} "
        f"-- scoped to {args.for_draft}"
    )

    # Named, not just counted. A citekey a draft cites and the
    # ledger has never heard of is normally the hard gate's business
    # and cannot reach a passing draft -- but a draft written before
    # a re-export, or against a corpus that has since moved, has
    # them, and silently enriching the remainder would report a
    # smaller number with nothing to explain it.
    unknown = sorted(scope - {doc.citekey for doc in docs})
    if unknown:
        say(
            f"  {len(unknown)} cited citekey(s) are not in the ledger and cannot be "
            f"enriched: {', '.join(unknown)}",
            level=logging.WARNING,
        )
    if not docs and selected & set(CORPUS_STAGES):
        say(
            "  nothing to enrich -- re-export your bibliography and run "
            "`python -m chitragupta.corpus sync` first.",
            level=logging.WARNING,
        )
        return docs, EXIT_BAD_SCOPE
    return docs, None
