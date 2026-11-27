"""The enrichment layer: Docling -> sentence-transformers/Chroma ->
BERTopic, over the same corpus `python -m chitragupta.corpus sync` maintains.

Needs pyproject.toml's "enrich" extra. The stdlib-only corpus and drafting
layers do not depend on it: its absence costs recall, never correctness.
It extends the *corpus* layer (nothing here is generative), which is why
it takes the same write lock as sync. `chitragupta/render_output/` is the
drafting layer's publish step and deliberately not here.
"""
