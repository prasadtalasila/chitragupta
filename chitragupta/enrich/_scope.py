"""`--for-draft`'s scope resolution: the citekey set, the stages that
refuse to be narrowed, and the corpus filter itself.

Runs before the pipeline lock is taken. `scope_corpus` takes `_say` as a
parameter, because importing back from `__main__.py` (run as
`__main__`) would create a circular import.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from chitragupta import citation_gate, config

# The stages --for-draft refuses to run over a subset: each writes one
# whole-corpus artefact whose partial form is indistinguishable from the
# complete one (`embed` has no completeness marker and skills only check
# that content/chroma/ exists; `bertopic` and `seed-topics` overwrite
# their files, and seeds over eleven papers give a wrong answer, not a
# smaller one). A tier, not a ladder (docs/LADDERS.md): stop and say so.
SCOPE_REFUSED = (
    "embed",
    "bertopic",
    "extract-keywords",
    "seed-topics",
    "converge",
    "topic-graph",
)

# The stages that read the corpus at all (every stage, since 4.0.0). Its
# own name: an empty scope stops the run only if some stage would use it.
CORPUS_STAGES = (
    "docling",
    "embed",
    "bertopic",
    "extract-keywords",
    "seed-topics",
    "converge",
    "topic-graph",
)

# 3, not 2: argparse and runlock.EXIT_ALREADY_RUNNING use 2, and only
# "someone holds the lock" is worth retrying.
EXIT_BAD_SCOPE = 3


def draft_citekeys(path: Path) -> set[str]:
    """Every citekey `path` cites, as the docling stage's scope.

    citation_gate.extract_citekeys(), the hard gate's own reader, so the
    scope is exactly what the gate checks; whole-document, so a
    `\\citep{a,\\n b}` wrapped across lines contributes both keys.
    """
    return {
        key for _, key in citation_gate.extract_citekeys_for(path, path.read_text(encoding="utf-8"))
    }


def resolve_scope(args, selected) -> "tuple[set[str] | None, int | None]":
    """--for-draft's citekey set, or the exit code refusing it.

    Returns (scope, None) or (None, EXIT_BAD_SCOPE). Runs before the
    lock: it depends only on the named file, so a sync need not wait.
    """
    # Refused against the stages the user *typed*: a bare --for-draft
    # selects docling alone and never reaches this branch.
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
        # Separate: UnicodeDecodeError escapes the clause above, and
        # errors="replace" would silently scope to wrong citekeys.
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

    Filtered here, not in build_corpus() ("every ledger item"), so the
    count can say what was left out. Returns (docs, None), or (docs,
    EXIT_BAD_SCOPE) when a corpus stage was asked to run over nothing.
    """
    total = len(docs)
    docs = [doc for doc in docs if doc.citekey in scope]
    say(
        f"Corpus: {len(docs)} of {total} doc(s) from {config.BIB_FILE_PATH} "
        f"-- scoped to {args.for_draft}"
    )

    # Named, not just counted: a draft predating a re-export can cite
    # keys the ledger lacks, and a silently smaller count explains nothing.
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
