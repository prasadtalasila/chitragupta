#!/usr/bin/env bash
# Rebuild this sample project's machine state from its committed inputs.
# Run from this directory, with chitragupta installed (the topic stages
# need the enrich extra: pip install 'chitragupta-cli[enrich]').
#
# The committed artefacts -- drafts, dossiers, reviews, renders, specs,
# the topic map -- were produced by the real pipeline against exactly
# these inputs; this script recreates the uncommitted substrate (ledger,
# parsed text, embeddings, topic artefacts) they were derived from. The
# optional Docling parse (content/docling/) is deliberately not run
# here: nothing committed depends on it, and it is the slowest stage --
# add `docling` to --stages if you want it.
set -euo pipefail
python -m chitragupta.corpus sync
python -m chitragupta.enrich --stages embed,bertopic,seed-topics,converge,topic-graph
python -m chitragupta.corpus discover
