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
  The setting-specific validators stay in `config.py`. The second PR
  moves the 26 `[enrich]`/`[discover]` knobs into `config_enrich.py`,
  which imports only `config_load`. The paths those stages write stay in
  `config.py`, because they are derived from `CONTENT_DIR` and moving them
  would save nothing: each moved line costs a re-export line. That move
  alone left `config.py` at 274 code lines. Folding `_get_start_method`
  and `_get_log_level`, which differed only in the case they folded to,
  into one `config_load._get_choice` brought it to 247 and delisted it. A
  star re-export would have been shorter, but `.pylintrc` sets
  `allow-wildcard-with-all=no` and the codebase has none. `config.py`
  reloads `config_enrich` when it is itself reloaded, because
  `importlib.reload(config)` does not re-run a module it only imports.
- **#849, review output.** Covers every aid that repeats the
  formats/write/print sequence, which by now is ten, not eight.
- **#850, aid registries.** One registry in code. The SVGs are re-rendered
  with mermaid-cli 11 and fingerprinted by a single manifest,
  `docs/diagrams/svg/sources.json`, which maps each diagram to its `.mmd`'s
  sha256. A stale SVG then fails with a message naming its source.
- **#851, caches.** Only the two retrieval caches share the new helper,
  `_json_cache.MemoisedJson`. The two enrich caches have no memo or stamp,
  so they are left alone. Each retrieval cache binds its old private names
  (`_load_cache`, `_save_cache`, `_forget_cache`) to the shared object's
  methods, so `dossier/_drift.py` and the tests keep calling them.
- **#852, style rules.** A tuple registry in `style_rules.py`, using the
  `repair` field #836 already added.
- **#853, enrich seams.** The reranker loader moves down into a public
  corpus-layer `chitragupta/reranker.py`, imported by both `discover` and
  `enrich`. `references.entries()` and `MissingCitekey` move down into
  `chitragupta/reference_entries.py`, so `discover` no longer imports the
  drafting layer; callers import it directly, with no re-export.
  `embed_index.search()` caches its client and model on
  `(CHROMA_DIR, EMBEDDING_MODEL)`, and it returns `[]` with a logged
  reason, creating nothing, when the index directory or the collection is
  absent. That read-side opening lives in `enrich/_index_reader.py`,
  because adding it to `embed_index.py` put the module at 268 code lines
  and `search()` at 26 statements, and this epic adds no register entry.
  The existence check is `overlap_chroma.existing_collection`, factored
  out of `built_collection` so there is one way to ask.
  `tests/test_layer_imports.py` pins both boundaries.
- **#854, seams and shims.** The `references._format_numbers` shim was
  already gone. `extract_citekeys_from_line` scans whatever string it is
  handed, so `_claims`, which passes whole blocks, never had the
  line-break false negative the issue feared. It switches to
  `extract_citekeys()` for an honest name, and a test pins the split
  citation. The launch seam is `from subprocess import run as _run` in
  each module. That replaces the `import subprocess` line instead of
  adding one, so the registered `style_check.py` does not grow.
