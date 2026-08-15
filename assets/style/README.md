# The vendored acronym vocabulary

`acronyms.toml` is the floor every draft starts from -- acronyms common
enough across this project's readership that expanding them would insult
the reader (`PDF`, `CPU`, `URL`, `API`, `HTML`). Read by
`src/acronyms.py::load_vocabulary()` at a genre skill's step 0, the same
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
copy it, edit it to your own field's vocabulary, and point the config
key at your copy.

## What this is not

Not a check. `assets/vale/styles/chitragupta/Acronyms.yml` is the rule
that *verifies* an acronym was expanded at first use and not
re-expanded later (#107) -- a Vale rule, unrelated code, untouched by
this file. This vocabulary is the *input* side: what a genre skill drafts
from, so the check downstream has less to find.
