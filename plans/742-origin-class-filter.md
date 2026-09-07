# Filtering the topic graph by origin (#742)

## The problem

Topic origin is visible and unusable. `chitragupta/discover/_app.py`
annotates each topic `seed` | `keyword` | `both` | `emergent` by reading
`content/seed_topics.toml` and `content/keywords.toml`, and the app
colours by it -- but nothing can be *filtered* on it, in the browser or
from the terminal. The other views cannot even see it: they read
`topic_set.json`'s `provenance`, which is `seed` | `emergent` only,
because `stages._seed_phrases()` unions the two TOML files before any
stage runs. That union is why `_app.py` reads the files itself, and why
the artefacts cannot answer the question.

## Why this needs a plan rather than a roadmap row

Two contracts are decided here and neither is mechanical: what
`--origins seed` means for a topic that is *also* a keyword, and where
the annotation lives now that four views want it. A later reviewer
would have no way to tell either decision from an accident.

## The decisions

### 1. `both` becomes `corroborated`

A topic the human named and the PDFs' extracted keywords also named is
one that two independent sources agree on. `both` names the set
operation; `corroborated` names the fact, which is what the reader is
looking at. The value is renamed everywhere it appears -- the app
payload, `ORIGIN_COLORS`/`ORIGIN_LABELS` in `assets/webapp/graph.js`,
the `--both` CSS variable, the legend, the docs and their tests.

Renaming a shipped payload field is cheap exactly here and nowhere
later: `data.js` is written fresh by every `--app` run and read only by
the app directory written beside it, so there is no stored artefact to
migrate and no second reader to keep in step. Doing it after a filter
ships would mean renaming a value users have typed on a command line.

### 2. The annotation moves to `_origin.py`

`_page.build_payload` is a pure renderer of the artefacts and stays
one -- pushing the TOML reads down into the join would make it read
files no stage wrote, and its docstring's promise that the page cannot
disagree with `--json` would stop being about the artefacts alone.

So the annotation becomes `chitragupta/discover/_origin.py`:
`annotate(payload)` (each topic gains `origin`), `parse(value)` (the
flag's vocabulary) and `keep(payload, origins)` (the filter).
`_app.build_app_payload` becomes a thin wrapper over `annotate`, and
the CLI applies `annotate` + `keep` at the view boundary. One
definition of origin, four callers.

### 3. Selection is a union of predicates

`--origins` takes a comma-separated subset of `seed`, `keyword`,
`corroborated`, `emergent`:

| `--origins ...` | shows |
| --- | --- |
| `seed` | pure-seed **and** corroborated -- a corroborated topic *is* seeded |
| `keyword` | pure-keyword **and** corroborated |
| `corroborated` | only the intersection |
| `emergent` | only what the topic model found on its own |

Set membership decides it: `corroborated` satisfies the seed predicate
and the keyword predicate, so either ticked class shows it. The
alternative -- `seed` meaning strictly-not-keyword -- would make
`--origins seed,keyword` and `--origins corroborated` overlap in a way
no reader can predict, and would hide hand-written topics from someone
who asked for hand-written topics.

That inclusiveness is the one misreadable thing here, so it is stated
in `--help`, not only in `docs/CLI.md`.

### 4. The flag filters the payload, not the presentation

`--origins` pre-filters for every view -- terminal list, `--json`,
`--html`, `--app`. One rule everywhere; an exported page or app
directory contains what it says it contains, and `--json` cannot
disagree with the canvas. Absent flag means all four classes and
byte-identical output to today, which is what keeps the diff
reviewable.

Refusals: an unknown value, or a selection that is empty, is a message
on stderr and exit 1 -- never a silently empty graph, by the rule every
other refusal in this module follows.

### 5. The app filters live, over what shipped

A checkbox per class in the header, all ticked on open. The filter
restricts the label universe, and every consumer of that universe moves
with it:

- the type-ahead (`candidatesFor`), or the app offers a topic that is
  not on the canvas and pinning it reaches a state `elementsFor` never
  sees;
- the hierarchy panel: a group whose members are all hidden is not
  drawn. The stored merge tree is still cut as stored -- recutting over
  a subset would invent a grouping no stage computed.

Stage-computed numbers stay corpus-wide: `edges_withheld` and the
absence verdict are the artefact's statements about the corpus, not
about the reader's current view, and rescaling them to a filtered
subset would publish a number no stage ever produced.

A class the export excluded has no topics in `data.js`. Its checkbox is
disabled and says which export excluded it, rather than doing nothing
when clicked -- the reader can tell "filtered out at export" from "this
corpus has none". Unticking the last enabled class is refused; an empty
canvas is not a view.

### 6. The two positional stored fields

`topic_graph.json` holds two fields indexed by *position* rather than by
name, and a filter that ignores them is silently wrong rather than
merely incomplete.

- **`communities`** is one cluster id per topic in `topics` order.
  Filtered in step with the topics, so each survivor keeps the id the
  stage gave it. A partly hidden cluster is still that topic's cluster,
  and nothing is re-clustered: a partition over a subset is a claim no
  stage made.
- **`paths`** stores next-hop indices into the edge lists, and a stored
  route may run *through* a topic the filter removed. Truncating the
  matrices would leave routes pointing at edges that are gone, and
  recomputing is not the reader's to do. So `--path` refuses to compose
  with a narrowing `--origins` (exit 2, argparse's usage code, as every
  other refused view combination here uses), and the field is dropped
  from a filtered `--app` export -- where the app falls back to walking
  in the browser exactly as it does for an older artefact.

In the app, where the checkboxes filter a corpus-wide payload rather
than the export doing it, the same two views stay corpus-wide and say
so: the disagreement grid keeps the stored partitions and lists only
pairs both of whose topics are on the canvas, and a path names every hop
with a line reporting that the route left the filter.

## Files

- `chitragupta/discover/_origin.py` (new): `annotate`, `parse`, `keep`.
- `chitragupta/discover/_app.py`: `build_app_payload` wraps `annotate`;
  `write_app` takes the selection.
- `chitragupta/discover/_page.py`, `_render.py`, `__init__.py`: the
  flag, its refusals, and the filter applied to each view.
- `assets/webapp/graph.js`, `app.js`, `index.html`, `style.css`: the
  rename, the checkboxes, the filtered universe.
- `tests/test_discover_origins.py` (new), plus `test_discover_app.py`,
  `test_discover_page.py`, `tests/webapp/graph.test.js`.
- `docs/CLI.md`, `docs/TOPIC-DISCOVERY.md`, the Discovery app tour.

## Not in scope

No stage recomputes anything: this is a reader-side filter over
artefacts `chitragupta enrich` already wrote.
