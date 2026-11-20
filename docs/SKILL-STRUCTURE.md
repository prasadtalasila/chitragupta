# 🧱 Skill structure

Status: **reference.**

**Written for** anyone reading or changing a genre skill who wants the
shape of all six before opening one. **Assumed:**
[GENRE.md](GENRE.md). The skill files and the references they cite are
the source of truth; this page names the file that holds each part.

Six skills write a new draft: `survey-writer`,
`thesis-chapter-writer`, `textbook-chapter-writer`, `tutorial-writer`,
`deep-research` and `review-digest`. `figure-drawer` draws the figures
they hand it, and the revisers (`draft-reviser`, `corpus-reviser`,
`agenda-reviser`) change a draft once it exists. A genre skill is never
re-run to change its own output.

## 🗂 Four layers

A genre skill is spread across four layers, each read only when a step
points at it, so a skill's standing text is its steps and a procedure
every genre shares is written once.

| Layer | Where | What it holds |
| --- | --- | --- |
| The skill | `.claude/skills/<genre>/SKILL.md` | The numbered steps, each closing on a "Done when..." line |
| The genre reference | `.claude/skills/<genre>/references/<genre>.md` | The reasoning behind the steps, in numbered sections a step cites as "read §N" when it needs one |
| The shared references | `.claude/skills-common/references/` | What every genre does the same way (listed below) |
| The writing standards | [WRITING-STANDARDS.md](WRITING-STANDARDS.md) and `docs/writing-standards/` | The prose rules: core, element and genre files |

The shared references are:

- `genre-steps.md` §1-7: the frame described below, from the read-only
  corpus to stamping and handing over.
- `critique.md`: the repair loop against the evidence packet.
- `render-and-references.md`: the References section, the render, and
  the evidence sidecar.
- `prose-check.md` and `verbatim-scan.md`: reading and reporting the two
  review aids.
- `mathematical-prose.md`, `collection-scoping.md`,
  `digest-copying.md`, and, for the revisers and the book track,
  `figures-tables-equations.md` and `book-steps.md`.

## 🔁 The frame every genre shares

The genres differ between retrieval and drafting. The frame around that
is the same in all six.

### Before drafting

1. **The corpus is read-only.** No skill runs `corpus sync` or
   `enrich`. Each checks `python -m chitragupta.corpus ledger` first;
   the next section's table says what an empty ledger means per genre.
2. **Collection scoping**, except in `deep-research`, which always
   searches the whole corpus so that its perspectives can disagree.
3. **Open the dossier.** `draft dossier init <draft> --genre <genre>`
   creates `scope.md`: reader, scope, glossary and `language:`.
4. **Retrieve and record.** A passing `outline.md` supplies declared
   queries (`--origin declared`); otherwise the skill over-fetches with
   `retrieve search ... --k 15 --log`. Every candidate lands in
   `evidence.md` (`relevance:`, `claim:`, optionally `quote:`) or in
   `rejected.md`, and `dossier check-evidence` confirms it.

### After drafting

1. **Critique against the evidence packet.** Up to five places where
   the prose outruns, omits or drifts from a kept `claim:`, then at
   most three repairs, each logged in `revisions.md`.
2. **Gate, then references.** `python -m chitragupta.draft gate` must
   report `OK` before the user sees anything.
3. **Render** tex, pdf and md, and the evidence sidecar where the genre
   wants one.
4. **Review aids, never conditions of presenting.** `draft style` is
   the prose check; `dossier sections --write` then `review verbatim
   scan` look for source wording. `steering.md` records what the user
   said in chat.
5. **Stamp and present.** `dossier stamp`, then hand over. Any later
   change goes through `draft-reviser`.

## 🎭 Where the genres differ

| Genre | Output | Citations | Empty ledger | What only this genre does |
| --- | --- | --- | --- | --- |
| `survey-writer` | `.md`, `[@key]` | Dense | Stop | A comparison table and a gap analysis are required; step 2a puts retrieval for each sub-theme behind its own subagent; sidecar in pdf and md |
| `thesis-chapter-writer` | `.tex` fragment, `\citep`/`\citet`, no preamble | Dense | Stop | Pins the research question at step 1; writes `provenance.json`; no References section; md and pdf previews only; always reads `mathematical-prose.md` |
| `textbook-chapter-writer` | `.md` | Optional, sparse | Ask | 3-5 learning objectives, scope and prerequisites, motivation, worked examples faded to posed ones, exercises labelled `(Objective M, easy/medium/hard)`, a closing summary tied to the objectives |
| `tutorial-writer` | `.md` | Only in "Where to go next", no `quote:` lines | Ask | A task analysis first; imperative steps with real values; step 8 runs every command and records a `## Verified environment` in `scope.md`; no sidecar |
| `deep-research` | `.md` | Dense, whole corpus | Stop | Seven phases with quick, standard and deep presets; parallel interviewer, writer and peer-reviewer subagents; a contradiction map, a synthesis briefing and a peer-review scorecard; only the main run writes the dossier |
| `review-digest` | `.md` | Copied runs closed by `[@key, p. N]` | Stop | Follows `survey-writer`'s steps; the drafter's own sentences close on `[see @a; @b]`; `<!-- own: why -->` declares a paragraph the drafter's; `review digest` replaces the verbatim scan; never a deliverable |

## ✍ The writing standards

[WRITING-STANDARDS.md](WRITING-STANDARDS.md) is the core, from the
audience to dialect. The element files carry the rest:

| File | Section | Holds |
| --- | --- | --- |
| [figures.md](writing-standards/figures.md) | §10 | Original figures only, the two-file pair, captions |
| [mathematics.md](writing-standards/mathematics.md) | §12 | Mapped symbols, `math.md`, which equations get a number |
| [tables.md](writing-standards/tables.md) | §13 | Caption, id, and the sentence that reads the table |
| [page.md](writing-standards/page.md) | §14 | What has to fit the page |

Each genre file under
[writing-standards/genres/](writing-standards/genres/README.md) says
what that genre owes its reader, how often it uses figures and
mathematics, and what its reread checks. Where two sources of guidance
disagree, the citekey invariant wins, then the venue, then the writing
standards.

§11's synthesis unit should close on two or more citekeys, or carry
`<!-- single-source: why -->` (`% single-source:` in LaTeX). The unit is
the paragraph in a survey, a thesis chapter and a deep-research report;
the section in a textbook chapter; and the whole document in a tutorial.

## 📐 Figures, tables and equations

A genre skill decides **whether** a figure is warranted, and absence is
the default. `figure-drawer` owns **how** it is drawn, from choosing a
layout under `.claude/skills/figure-drawer/references/layouts/` and the
`assets/tikz/` scaffold to checking the ASCII twin
([FIGURE-DRAWER.md](FIGURE-DRAWER.md)). How often each genre draws:

| Genre | Figures |
| --- | --- |
| Tutorial | The genre most free to use them |
| Textbook chapter | Common, each one earned |
| Thesis chapter | Occasional |
| Survey | The rarest of the genres that draw |
| Deep research | None, by design |
| Digest | Only the sources' own; nothing drawn |

Every genre that draws repeats the core rules in its figure step, so they
hold even when `figure-drawer` is never loaded. A figure is a pair:
`figures/<name>.tex` in TikZ and `figures/<name>.txt` in 7-bit ASCII of
about 70 columns. If `kpsewhich tikz.sty` finds nothing, the ASCII goes
inline instead. Neither file holds a citekey, since the gate does not
follow `\input`, and nothing is redrawn from a source (§10). The caption
lives in the draft, and nobody writes "Figure N" by hand.

Tables (§13) and displayed equations (§12) carry id and reference
markers the same way, and the thesis chapter uses real LaTeX floats and
`\label`s instead. Only a chosen few equations are numbered. The
textbook chapter carries the most mathematics, the tutorial the least,
and `deep-research` numbers equations only once the parallel writers'
sections are reconciled.
