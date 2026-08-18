# Book-scale drafting: the outline, the units, and the registries

Status: **being built.** The spec artefact below exists and is usable
today; the rest of the track is named here so a reader can see what each
piece is for, with the issue that builds it. This document grows one
section per landed piece rather than describing the whole design as if it
shipped.

**Written for** someone drafting a document larger than a chapter with
this pipeline, and for whoever builds the next piece of the track. It
assumes [AGENTS.md](../AGENTS.md) for the drafting layer and
[ARCHITECTURE.md](ARCHITECTURE.md) for the four layers.

## Table of contents

- [The constraint everything here answers](#the-constraint-everything-here-answers)
- [The spec artefact, and its sign-off](#the-spec-artefact-and-its-sign-off)
- [Why an id is required on every heading](#why-an-id-is-required-on-every-heading)
- [Why sign-off is a sibling file](#why-sign-off-is-a-sibling-file)
- [What `status`'s exit code is, and is not](#what-statuss-exit-code-is-and-is-not)
- [The rest of the track](#the-rest-of-the-track)

## The constraint everything here answers

> A book does not fit in a context window, and generation quality
> degrades long before the limit.

So cross-chapter consistency cannot live in a model's memory of an
earlier call. It has to live in explicit on-disk artefacts, injected as
relevant excerpts into each unit's generation, and checked
deterministically afterwards. That is the same two-plane discipline as
the rest of the project: the artefacts are written by deterministic
passes, never by an LLM writing to the corpus plane.

Two human sign-offs, and no more: **the outline** and **the finished
book**. No automated check verifies that an argument is good -- only that
it is grounded, consistent and complete. Everything between the two
sign-offs is mechanical.

## The spec artefact, and its sign-off

`python -m src.draft spec` (`src/spec.py`) owns one Markdown file per
book and a sign-off record beside it:

```text
content/drafts/twins/           the book's units, once they are drafted
  -> content/specs/twins/spec.md      the outline, edited by a human
     content/specs/twins/signoff.md   written by `spec sign`
```

That mirroring is the rule `content/dossiers/`, `content/rendered/` and
`content/review/` already follow, read one level up: those mirror a
single *draft*, so they carry the draft's parent directory. A book is a
*directory* of drafts, so its own path is what carries over.

The outline is four heading levels, and no more:

| Markdown | Is | Generates |
|---|---|---|
| `# Title` | the book | -- |
| `## Part {#part-i}` | a part | -- |
| `### Chapter {#ch-1}` | a chapter | -- |
| `#### Section {#sec-1}` | a **section** | one unit of prose |

The section is the generation unit (#137), which is why nothing sits
below it: a level deeper would be a unit nothing generates. Text beneath
a heading is that unit's **brief** -- what it must establish, and what it
leaves to another unit. Text before the first heading belongs to no unit
and is never handed to a generator; it is the preamble for whoever opens
the file.

Planned top-down, generated bottom-up. `spec show --unit <id>` prints one
unit's slice -- its title, its kind, the part and chapter above it, its
brief, and whether the outline is signed off -- and that slice is what a
genre skill generates from, instead of inventing structure per
invocation.

[CLI.md](CLI.md#python--m-srcdraft-spec) has the flags.

## Why an id is required on every heading

Every part, chapter and section carries an explicit `{#some-id}`, and a
heading without one is a parse problem rather than something the parser
guesses at.

A derived id -- slugified from the heading text, say -- changes the
moment someone rewords the heading, and every unit already written
against the old spelling silently becomes an orphan. At chapter scale a
person notices; across 300 pages nobody does. The same ids are what the
cross-reference graph (#138) will resolve against, so they have to
outlive an edit to the words around them.

`spec show`, `spec sign` and `spec status` all refuse a spec that does
not parse, and print **every** problem rather than the first: someone
fixing an outline wants the whole list, not one round trip per missing
id.

## Why sign-off is a sibling file

`spec sign` records a twelve-hex digest of `spec.md` -- the same shape as
the dossier's corpus fingerprint, and for the same reason: enough to
answer "is this the same document?", short enough to sit on one line.

It goes in `signoff.md` rather than into `spec.md` itself because writing
the digest into the file would change the file it just measured, and no
later read could ever match. The digest covers `spec.md` alone, so
`spec status` can tell three states apart:

| State | Exit | Means |
|---|---|---|
| signed off at digest `x` | 0 | the approved outline is the one on disk |
| not signed off | 1 | nobody has approved this outline yet |
| changed since sign-off | 1 | approved at one digest, now another |

`signoff.md` carries **no timestamp**, the same rule the review layer's
reports follow: two sign-offs of an unchanged outline produce
byte-identical files, so "did this change?" is a diff. *When* it was
approved is not a question any check asks; *what* was approved is.

## What `status`'s exit code is, and is not

`spec status` exits non-zero on an outline that is unsigned or has
drifted. That is not a new gate, and the distinction matters enough to
state rather than leave to a reader.

[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" draws the line by **what a
check is measured against**: the citation gate is measured against the
ledger, which is ground truth, while a check measured against a recorded
preference reports and never blocks, however mechanical its answer.
`spec status` is measured against neither. It reads back a record of a
*person's decision* -- did a human approve this outline? -- and reports
it. It judges no draft's content, refuses no write, and blocks no draft:
`python -m src.draft gate` remains the only gate in this project, and
`.claude/hooks/citation_gate_hook.py` remains the only automatic refusal.

What the exit code buys is that a genre skill can ask the question
without parsing prose. What a skill does with the answer -- stop and ask
the human to approve the outline first -- is the human gate itself, not a
machine outranking anybody.

## The rest of the track

Named here so the shape is visible; each lands with its own section in
this document.

- **Section-sized generation units** (#137) -- an explicit contract per
  unit: spec slice + registry excerpts + retrieved chunks in, draft +
  citations + claims out. Content-hashed so an unchanged unit costs
  nothing to re-run, and independently regenerable, which is what makes
  "regenerate one section fifty times while 200 pages sit untouched"
  cheap.
- **Consistency registries** (#138) -- terminology/notation, a claim
  register, and a cross-reference graph, each written by a deterministic
  post-pass over accepted units and injected as excerpts into later ones.
- **LaTeX book assembly** (#139) -- parts, chapters and front matter
  composed from accepted, gate-passed units, as a genre skill:
  conventions as data, not code.
