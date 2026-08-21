# The vendored acronym vocabulary

`acronyms.toml` is the floor every draft starts from -- acronyms common
enough across this project's readership that expanding them would insult
the reader (`PDF`, `CPU`, `URL`, `API`, `HTML`). Read by
`chitragupta/acronyms.py::load_vocabulary()` at a genre skill's step 0, the same
place the dialect is settled (`docs/WRITING-STANDARDS.md` §8).

## Provenance

Original to this repository, not fetched or adapted from any external
source -- there is no upstream "common acronyms" list to vendor the way
`assets/csl/ieee.csl` vendors IEEE's own CSL style. The five entries here
are the ones named in
[GitHub issue #190](https://github.com/prasadtalasila/chitragupta/issues/190).
Grow this list with a PR when a new acronym earns a place on the floor
every draft shares -- a term specific to one author's field belongs in
their own file instead (see below), not here.

## The user override

**Your domain vocabulary is your data, not this project's** -- the same
footing `papers/bibliography.bib` and `content/verbatim_allowlist.toml`
are on. Point `[style].acronyms` in `config.toml` at your own TOML file
(`SHORT = "Long form"` pairs, same shape as this file) and
`load_vocabulary()` merges it over the vendored floor above, your
definition winning if you redefine one of the five. It is never a
wholesale replacement: the vendored floor always loads, so a user file
that only adds `DTaaS = "Digital Twin as a Service"` still gets `PDF`,
`CPU`, `URL`, `API` and `HTML` for free.

`acronyms.toml.example` in this same directory is a starting point --
copy it to `content/acronyms.toml` (gitignored, per-host, the same
footing as `config.toml` itself -- not this directory, which is
version-controlled and ships with the project), edit your copy to your
own field's vocabulary, and point `[style].acronyms` at it. `python -m
chitragupta.draft dossier acronyms-suggest <draft> --apply` can write new
entries there for you, proposed from a draft's own glossary and its
prose; see `docs/CONFIG.md`.

## What this is not

Not a check, on its own -- but two checks now read it. Vale's
`assets/vale/styles/chitragupta/Acronyms.yml` *verifies* an acronym was
expanded at first use and not re-expanded later (#107), against the
draft's text and unaware this file exists. `chitragupta/style_acronym_drift.py`
is the other one: it compares a draft's own recorded glossary against
`load_vocabulary()`'s current merge of this file and the user's, and
reports when they've drifted apart. Neither check is this file's own
job -- this vocabulary is the *input* side, what a genre skill drafts
from, so both checks downstream have less to find.

## The seed-topic list

`topics.toml.example` is the other template here, and unlike
`acronyms.toml.example` it has no vendored floor beside it -- there is no
`topics.toml` in this directory and there should not be. An acronym like
`PDF` is common to every reader this project has; a topic is the one
thing that is never shared between two authors, so a default list would
be wrong for everybody rather than merely incomplete.

Copy it to `content/seed_topics.toml` (gitignored, per-host, the same
footing as `content/acronyms.toml`), write your own phrases, then match
them against the corpus with `chitragupta enrich --stages seed-topics`
and read the result with `chitragupta corpus topics`. If your Zotero
export carries collection labels, `chitragupta corpus ledger
--collections` prints the candidates worth pasting in. See
`docs/CONFIG.md` for `[enrich].seed_topic_min_similarity`, and
`chitragupta/seed_topics.py` for why the file is TOML.
