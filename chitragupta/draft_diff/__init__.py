"""`draft diff`: what changed between two versions of one draft.

A version is a dossier snapshot, the live draft, or any file passed with
`--against`. Between two of them this package builds a change report --
sections added, removed, moved or changed, citekeys added and dropped,
figures redrawn -- and a redline of the prose. The output is a review
copy: never gated, never a deliverable, never a source.
"""

from chitragupta.draft_diff._cli import main

__all__ = ["main"]
