"""Every layer's one-line help, and its verbs', in one import-light table.

`chitragupta --help` prints a two-level tree of every layer and its verbs
(#1230). It cannot read that tree off the layers themselves:
`chitragupta/draft.py` imports every verb module when it loads, and
`enrich`'s imports are absent unless the optional group is installed, so
asking for help would cost hundreds of imports or fail outright. This
module is the one place each help line is written. The dispatchers read
it back for their own lists, which is what keeps the tree and the layers
from drifting apart.

Data only, standard library only, importing nothing from this package.
"""

# `{name: (one_line, {verb: help})}`, in the front door's dispatch order
# and each layer's own registration order, which is the order printed.
HELP: dict[str, tuple[str, dict[str, str]]] = {
    "corpus": (
        "bring the ledger up to date, or read what it recorded",
        {
            "sync": "bib file -> ledger -> PDF text: the deterministic corpus run",
            "ledger": "read-only view of what that run recorded -- takes no lock",
            "topics": "read-only view of which papers each seed topic matched -- takes no lock",
            "discover": (
                "resolve a phrase to a topic and walk its papers and neighbours -- takes no lock"
            ),
        },
    ),
    "draft": (
        "work on one draft -- gate it, cite it, render it",
        {
            "gate": "verify every citekey in a draft against the ledger",
            "dossier": (
                "the working state behind a draft: create it, inspect it, back it up, restore it"
            ),
            "retrieve": "BM25 retrieval over the synced corpus",
            "references": "an IEEE reference list built from a draft's own cited citekeys",
            "evidence": (
                "the evidence sidecar rendered beside a draft: each "
                "cited source and the spans its dossier marked quotable"
            ),
            "render": "render a Pandoc-markdown or LaTeX draft to tex/pdf/docx",
            "style": (
                "check a draft's prose against docs/WRITING-STANDARDS.md "
                "-- a review aid, never a gate"
            ),
            "spec": "the outline a book is generated from, and the human sign-off on it",
            "unit": "one section's generation contract, and the record of its acceptance",
            "registry": (
                "terminology, claims and cross-references over a book's "
                "accepted units -- a review aid, never a gate"
            ),
            "tldr": (
                "a one-paragraph summary per citekey, cached beside a "
                "fingerprint of its parsed text"
            ),
            "figures": "one paper's figures to look at while drafting -- never to reproduce",
            "diff": "what changed",
        },
    ),
    "review": (
        "eleven read-only aids over a finished draft; never a gate",
        {
            "provenance": "what in the source supports this claim?",
            "verbatim": "verbatim overlap with one source, or with the whole corpus",
            "coverage": "retrieval surfaced it -- did the draft cite it?",
            "synthesis": "how many sources does each unit of the draft rest on?",
            "figure": "what a TikZ figure's own geometry says about it",
            "uncited": "which sentences of the draft carry no citation?",
            "quotation": "is each quoted span really in the source it cites?",
            "agenda": "one ranked, deduplicated worklist across every other aid",
            "support": "does the cited source entail this claim?",
            "union": "does the assembly still carry every unit's citekeys?",
            "digest": "how much of a verbatim digest is not the sources' own words?",
        },
    ),
    "enrich": (
        "Docling -> embeddings/Chroma -> BERTopic -> topic graph: seven stages, whole corpus",
        {},
    ),
    "init": (
        "scaffold a project directory -- config.toml, .claude/, "
        "papers/, content/ and the prose docs",
        {},
    ),
    "doctor": (
        "probe and report: OS binaries, the enrich extra, torch vs. the GPU "
        "driver, a competing distribution, hook launchers, OpenCode skills, pdf fonts",
        {},
    ),
    "install": (
        "run the install_full_pipeline.sh stages a pip install "
        "cannot do itself -- os-deps, gpu-torch",
        {},
    ),
    "figure": (
        "start, check and look at one figure, and keep the house block current"
        " -- sync, check, new, look",
        {
            "sync": "stamp, refresh and report the block in figure files",
            "new": "start a figure from a layout's scaffold",
            "look": "see one figure as it will print",
            "check": "report every rule one figure file breaks",
        },
    ),
}


def verbs(name: str) -> dict[str, str]:
    """One layer's `{verb: help}`, empty for a command that has none."""
    return HELP[name][1]
