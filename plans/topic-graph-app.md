# The interactive topic-graph app (`corpus discover --app`)

## The problem

The topic graph had two presentations: terminal views and the `--html`
page -- one static file, topics on a circle, chords for edges. Legible
at tens of topics, but a reader cannot *work* it: there is no search,
no way to say "show me these three topics and what surrounds them", and
with the keyword-seeding arc (#604-#606) landed, a hand-written seed
phrase and a machine-extracted keyword render identically because
`topic_set.json` records both as provenance "seed" -- the union happens
in `stages._seed_phrases()` before any stage runs, so the artefacts
cannot tell them apart.

## The decision

One more pure renderer, `chitragupta/discover/_app.py`, behind a
`--app DIR` flag on `corpus discover`, writing a **directory**:

- Static interaction layer (`index.html`, `app.js`, `style.css`) copied
  verbatim from `assets/webapp/`, plus a vendored, pinned
  [cytoscape.js](https://js.cytoscape.org/) (`assets/webapp/vendor/`,
  committed for the reason `assets/csl/ieee.csl` is: the directory must
  work from `file://` with no network, forever).
- `data.js`, the one derived file: `_page.build_payload`'s join (same
  code, same drift refusal, `<` escaped the same way) with one field
  added per topic -- `origin`: `seed` | `keyword` | `both` | `emergent`,
  computed by reading `content/seed_topics.toml` and
  `content/keywords.toml` case-insensitively, matching
  `_seed_phrases()`'s own dedup rule. A seed topic in neither file (the
  files moved after the stages ran) degrades to `seed` rather than
  refusing: the artefact's provenance is still true.
- Data as a JS assignment, not JSON: `fetch()` of a local file is
  blocked under `file://`, and a plain script tag naming `data.js` as
  its source is not.

In the browser: type-ahead search over labels and top terms, multiple
selected topics as removable chips, the canvas filtered to the selected
topics plus their neighbours over both edge families, node colour by
origin and size by member count, papers as ledger-titled cards on node
click, shared/bridge papers on edge click.

## Alternatives considered

- **Growing the `--html` page.** The circle-and-chords page is a
  deliberate non-choice of force layout and stays; retrofitting a graph
  library, a search index and a filter model into one inline template
  would trade its "one file, no dependencies" contract for everything
  at once. Two views, two contracts.
- **Fetching cytoscape.js from a CDN.** Breaks the first time the
  reader is offline, and violates the project-wide rule that shipped
  pages never reference the network.
- **A serving application (Flask/HTTP).** Nothing here needs a server:
  the payload is finished at build time, so shipping a directory is
  strictly less machinery for the reader. The "thin python application"
  is the builder, not a daemon.
- **Recording origin in the artefacts instead.** Moving the annotation
  into `converge` would be truer, but it rewrites a shipped artefact
  schema for a presentation concern; the two TOML files are already the
  authoritative record of which phrase came from where.

## Verification

`tests/test_discover_app.py`: the directory is complete and the vendored
copy byte-identical, the data script round-trips and escapes `<`, every
origin case (seed/keyword/both/emergent/absent-files), drift and
missing-artefact refusals shared with the other views, the CLI contract
(`--json` composition, stderr refusals, unwritable target). Smoke-tested
against the synced sample project and rendered in headless Chromium:
three cytoscape canvases, zero console errors.
