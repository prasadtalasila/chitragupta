# Implementation plans

Status: **convention.** Written 2026-08-20.

Working documents for individual roadmap items --
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md) says *what* would
be built and in what order; a file here says *how* one item gets built,
for the person about to build it.

**This directory is not in the release archive.**
`scripts/release.py` lists `plans` in `EXCLUDE_TOP_LEVEL`, alongside
`tests/` and `bench/`, and the comment there says why: someone unzipping
a release to work on the pipeline needs `DEVELOPER-AGENTS.md` and the
roadmap, not the half-finished plan behind one merged PR.

It *is* built into the documentation site, because it is prose and the
roadmap links to it -- `mkdocs.yml`'s `exclude_docs` covers code,
per-host data and agent instructions, none of which this is. Two
distributions, two answers; that is not an inconsistency.

It is also the one prose directory here that is **allowed to go
stale**, which is the opposite of the contract every document under
`docs/` is held to.

## When a plan is worth writing

Most roadmap items do not need one. Each roadmap entry already carries
what it is, why, which files it touches, its size and its dependencies
-- for a mechanical change that *is* the plan, and restating it here
produces two documents that must agree.

Write a plan when at least one is true:

- **The design is genuinely underdetermined.** An implementer would
  otherwise have to invent a contract -- a file format, a field's
  meaning, a threshold -- and a later reviewer would have no way to tell
  a decision from an accident.
- **It changes an artefact other work already depends on**, such as the
  dossier's shape, where a migration question exists for material
  already on disk.
- **It spans layers**, so the [ARCHITECTURE.md](../docs/ARCHITECTURE.md)
  boundary it must not cross is worth stating before code exists.

Do *not* write one for a change that is one mechanical edit repeated, a
docs-only change, or anything whose whole design fits in its roadmap
entry.

## Shape

Follow the repository's documentation idiom rather than any tool's
default: a `Status:` line, then **Written for** / **Assumed** / **Not
covered here**, then the plan. `docs/AUTO-IMPROVEMENT.md` is the model
-- it is a specification of unbuilt work and reads like one.

Name a file for the roadmap item it implements: `<item-id>-<slug>.md`,
e.g. `a2-claim-quote-split.md`.

Record the outcome. When the work merges, add a line at the top saying
which PR closed it and what changed on the way. A plan that no longer
matches what shipped is worse than no plan, and this is the cheapest
guard against that.

## What lives here, and what does not

| | Where |
|---|---|
| What to build, and in what order | [docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md) |
| How one item gets built | here |
| Why the architecture is what it is | [docs/DESIGN.md](../docs/DESIGN.md), [SOUL.md](../SOUL.md) |
| A draft's own outline and evidence | `content/specs/`, `content/dossiers/` -- **product artefacts, unrelated to this directory** |

That last row is why this directory is `plans/` and not `specs/`: a
"spec" is already a thing this pipeline writes for a *book*
(`chitragupta/spec/`, `config.SPECS_DIR`), and reusing the word for a
developer document would collide with a product concept.
