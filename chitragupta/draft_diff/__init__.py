"""`draft diff`: what changed between two versions of one draft.

A version is a dossier snapshot, the live draft, or an `--against` file.
The output (change report and redline) is a review copy: never gated,
never a deliverable, never a source.
"""

from chitragupta.draft_diff._cli import main

__all__ = ["main"]
