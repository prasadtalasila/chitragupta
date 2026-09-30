# Design and refactoring debt (epic #817)

Status: **building.** Written 2026-09-30.

**Written for** whoever picks up a sub-issue of #817 part-way through, or
reviews one of its PRs and wants to know which choices were decisions.

**Assumed:** each sub-issue's own text, and
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md)'s register rules. This
file records only where the implementation departs from, or settles
something the issues leave open.

**Not covered here:** the webapp findings, which sit under the webapp epic.

## Shape of the work

One PR per sub-issue (two for #848), done one at a time, each branched
from the latest `main`, each a PATCH release. None changes what the pipeline
does or how it is invoked, which is the PATCH rule in
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md). The order is #848 (two
PRs), then #854, #853, #851, #849, #850 and #852.

## Decisions, per sub-issue

- **#848, config.** The first PR moves the TOML load and the eight generic
  getters into `config_load.py`. `_toml` moves with them, because a getter
  reads it from its own module's globals. `tests/test_config.py` therefore
  patches `config_load._toml` instead of `config._toml`. That is the one
  test change beyond the register, and it is why the old header said the
  split could not be mechanical. `config.py` calls `config_load.load()` on
  every import, so `importlib.reload(config)` still re-reads the file.
  The setting-specific validators stay in `config.py`. No `_get_choice` is
  added. The second PR moves the `[enrich]`/`[discover]` settings out and
  delists `config.py`.
- **#849, review output.** Covers every aid that repeats the
  formats/write/print sequence, which by now is ten, not eight.
- **#850, aid registries.** One registry in code. The SVGs are re-rendered
  with mermaid-cli 11 and fingerprinted by a single manifest,
  `docs/diagrams/svg/sources.json`, which maps each diagram to its `.mmd`'s
  sha256. A stale SVG then fails with a message naming its source.
- **#851, caches.** Only the two retrieval caches share the new helper.
  The two enrich caches have no memo or stamp, so they are left alone.
- **#852, style rules.** A tuple registry in `style_rules.py`, using the
  `repair` field #836 already added.
- **#853, enrich seams.** The reranker loader moves down into a public
  corpus-layer `chitragupta/reranker.py`, imported by both `discover` and
  `enrich`. `references.entries()` and `MissingCitekey` move down into
  `chitragupta/reference_entries.py`, so `discover` no longer imports the
  drafting layer. `embed_index.search()` caches the client and model on
  their config values and uses `get_collection`.
- **#854, seams and shims.** The `references._format_numbers` shim is
  already gone. `_claims` switches to `extract_citekeys()`; the per-line
  wrapper stays for its per-line callers.
