"""The enrichment layer: Docling -> sentence-transformers/Chroma ->
BERTopic, over the same corpus `python -m src.corpus sync` maintains.

Everything in here needs pyproject.toml's "enrich" Poetry group
(`poetry install --with enrich`), installed in a venv (PEP 668 blocks
system pip on the host this was built on). The stdlib-only corpus and
drafting layers in src/ (sync, retrieval, citation_gate) do not depend on
anything here and keep working regardless -- which is the point: this
layer is optional, and its absence costs recall, never correctness.

It extends the *corpus* layer rather than the drafting one. Nothing here
is generative, no genre skill runs it, and every artefact it writes
(content/docling/, content/chroma/, content/topics.json) is a deeper
reading of the same papers -- which is also why src/enrich/__main__.py takes
the same write lock as sync.

`src/render_output.py` is deliberately not here. It is the drafting
layer's publish step, needs no package from this group, and runs on the
bare system python3 -- what a module costs to install is a different
axis from which layer it belongs to.
"""
