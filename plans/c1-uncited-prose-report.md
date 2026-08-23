# C1: the uncited-prose report

Status: **built.** Written 2026-08-22 and shipped the same day in 6.19.0,
closing [#311](https://github.com/prasadtalasila/chitragupta/issues/311)
-- [docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s C1, build
order item 7.

## What changed on the way

Per [plans/README.md](README.md): a plan that no longer matches what
shipped is worse than no plan. Four differences.

1. **Five modules, not two.** The plan named `uncited_prose.py` and
   `_uncited_render.py`. It came out at 253 code lines against C2's 250,
   so the exclusion policy split off into `_claims.py` -- which is the
   better boundary anyway, since C2 wants "which sentences carry a
   claim" without wanting this report. `_blocks.py` was planned; it made
   five with `_units.py`'s new table.
2. **`_blocks.text_of` now strips a blockquote's marker from every
   line**, not only the first. Found by running the aid on
   `deep-research.md`, whose method banner came back as "Method adapted
   from > hadufer/claude-storm". A list item's continuation lines carry
   no marker and a blockquote's do, so `count=1` was right for one and
   wrong for the other. `citation_provenance` shares the fix and is
   better for it -- a quoted claim is now quoted back without its `>`.
3. **The empty-sentence guard came out.** `claim_sentences` filtered
   whitespace-only sentences, which `sentences.split` cannot produce
   once the block is known non-empty. It cost a branch nothing could
   cover, which is how it was found.
4. **The LaTeX table header row was missed on the first pass.** Every
   other exclusion handled both markups; that one keyed on markdown's
   `|` row and separator alone, so a `thesis-chapter` -- which emits
   `.tex` *and* is one of the three genres where uncited prose is
   exceptional -- would have had its column names reported as a claim.
   The two markups mark the header from opposite sides, which is why
   one lookahead was not enough. Found in review, not by a test.
5. **The sweep was wider than the section below predicted**, and in one
   direction it did not predict at all: `docs/PACKAGING.md` counts the
   CLI's leaf commands in prose (`17 verbs and aids`, `41 invocable leaf
   commands`) and `tests/test_packaging_command_table.py` pins both
   against the live parsers. That test is the only part of the sweep a
   machine catches; the rest was grep.

**Written for** the person building the fifth review aid: which
sentences of a draft carry no citation at all. It exists because two of
its contracts -- what is *not* a finding, and which genres raise
findings at all -- are decisions an implementer would otherwise have to
invent, and a later reviewer would have no way to tell a decision from
an accident. That is [plans/README.md](README.md)'s first test.

**Assumed:** [#309](https://github.com/prasadtalasila/chitragupta/issues/309)
has landed, so `review.envelope()` / `review.write_json()` exist and
every aid already emits `--json`. `chitragupta/sentences.py` exists and
is the shared splitter. `chitragupta/review/_units.py` owns `genre_of`,
and `dossier.GENRES` is the list a per-genre table is pinned against.

**Not covered here:** C2 (does the cited source actually support the
sentence?) and C3 (does a quoted span appear at the cited page?). This
aid asks only whether a citation is present, never whether it is apt.

## What the roadmap asked for, and the one thing it can stop asking for

C1's entry says *"The sentence splitter is shared with the roadmap's C2,
so put it somewhere C2 can reuse it."* **That work is already done.**
`chitragupta/sentences.py` was split out of `citation_provenance` so
tier 3 of the overlap scan could share it, and its docstring already
states the invariant -- two aids must not each keep their own idea of
where a sentence ends. C1 imports it, C2 imports it, and no new splitter
is written. Delete that line from C1's expectations rather than building
against it.

The same applies one level up. `citation_provenance._claim_spans` and
`_block_text` already subdivide a paragraph into blocks -- a table row,
a list item, a heading -- in **both** Markdown and LaTeX, because every
genre skill exports `.tex` beside the `.md`. `citation_provenance`'s own
comment records that `verbatim_check._paragraphs` "is a third copy and
deliberately stays one"; a fourth is not on offer.

So the walk **moves** into `chitragupta/review/_blocks.py` and both aids
import it. Two alternatives were measured and rejected. Importing
`citation_provenance._claim_spans` from the new aid drags `ledger` and
`passages` in behind it, and this aid reads only the draft -- it needs no
corpus, no ledger and no sync, which is a property worth keeping. Moving
the walk into `_units.py` instead would take that module from 199 code
lines to roughly 265, over C2's 250 cap, so it would need its own split
first. A new module is the cheap answer, and it is the same move B2 made
when `_units.py` came out of `synthesis.py`. `citation_provenance`'s
size-register entry shrinks with it, from 457.

## The measurement this plan rests on

Run before any code, against the four real drafts in
`content/drafts/digital-twins-for-software-engineers/` on the 501-paper
corpus -- the same drafts the roadmap's own verbatim baseline uses.
The naive reading (every sentence carrying no citekey is a finding):

| Draft | Sentences | Uncited | Naive findings |
| --- | --- | --- | --- |
| `survey.md` | 112 | 87 | 78% of the draft |
| `book-chapter.md` | 103 | 98 | 95% of the draft |
| `deep-research.md` | 51 | 38 | 75% of the draft |
| `tutorial.md` | 48 | 47 | 98% of the draft |

So the aid's whole difficulty is in what it declines to report. A report
that flags four fifths of a survey is one nobody opens twice, and alarm
fatigue is the stated risk for this class. Everything below is what the
measurement said, not what seemed likely.

## Decision 1: the name is `uncited`

`python -m chitragupta.review uncited <draft>` ->
`content/review/<topic>/<stem>.uncited.md`.

Blocked by the roadmap's constraint 5: not `audit`, `verdict`,
`reckoning`, `ruling` or `triage` -- the judgement register belongs to
the gate. Two further candidates were considered and dropped:

- **`grounding`** collides with something load-bearing. *Re-grounding*
  is `draft-reviser`'s mode for repairing citations after a sync moved
  the corpus ([docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md)),
  and a `survey.grounding.md` on disk would be read as drift, which is a
  different question about the same prose.
- **`attribution`** is what OpenScholar calls its own posthoc citation
  pass, which C2's entry is explicit about not porting. Reusing the word
  would suggest we did.

`uncited` is the issue's own word and is exactly true. It sits close to
`coverage`'s `uncited_candidates`, and that is tolerable *because*
`coverage` never uses the bare word: its findings are always qualified
as candidates, on the corpus side of the boundary. This aid's are
qualified as sentences, on the prose side. Both docstrings say so.

## Decision 2: the finding is a sentence, and the block is an attribute

The issue is plain -- *"a sentence either carries a citation or does
not"* -- so a finding is one sentence and the check is binary.

What is **not** an exclusion: the enclosing block carrying a citation.
The obvious shortcut is to suppress every sentence in a paragraph that
cites something anywhere, on the theory that the citation binds the
paragraph. It would take the topic-sentence and transition problem out
at a stroke, and it is wrong: a paragraph with one citation at the end
and four unrelated assertions before it is exactly the failure this aid
is for, and the shortcut is blind to it.

So each finding carries `block_cites` -- whether any citation appears
anywhere in the block the sentence sits in. That is volume control for
the human (read the bare blocks first), a real per-sentence binary for
an agenda, and it costs no invented vocabulary of transition phrases.
Measured on `survey.md` after the exclusions below: 30 findings, 17 of
them in blocks citing nothing.

## Decision 3: the exclusions, each one measured

A sentence is not a claim, and raises no finding, when it is:

| Excluded | Why, from the measurement |
| --- | --- |
| **The reference list** -- everything from a heading titled `References` / `Bibliography` / `Works Cited` to the end of the draft | 40 of `survey.md`'s 87 naive findings. A bibliography entry is uncited prose by construction. The heading match must tolerate a section number: the real drafts write `## 7. References` |
| **Headings**, Markdown and LaTeX | Also a splitter artefact: `## 1. The connection is the twin` splits into `1.` and the title, so a heading costs two findings, not one |
| **Captions** -- `\caption{...}`, `![alt](...)`, and a block opening `Figure N.` / `Table N:` / `Listing N.` | Named in the issue |
| **The table header row** -- in Markdown the row above the `\|---\|` separator, in LaTeX the row below booktabs' `\toprule` | Column names, not a claim. The separator row itself already flattens to nothing through `_cells_prose`. An `\hline`-ruled table's header is **not** detected and is reported: `\hline` separates every row from every other, and the genre skills emit booktabs |
| **Comment-only blocks** -- `<!-- ... -->` and a LaTeX `%` line | Includes §11's `<!-- single-source: ... -->` marker, which must not be read as an uncited claim about the world |
| **Fenced code and LaTeX verbatim** | Already blanked by `citation_gate._blank_code`, which this aid calls first, like `_units.units` does |
| **Anything that flattens to nothing** | A bare `\item`, a `\begin{itemize}` -- the list scaffolding the issue names. `_block_text` already strips the markers; what is left is empty and is skipped |

Everything else is reported, and two things the measurement *tempted* us
to add are deliberately absent:

- **No topic-sentence or transition detection.** There is no honest
  deterministic test for one, and a keyword list of document deixis
  ("this section", "we now turn to") would be invented rather than
  measured. `block_cites` is the answer instead.
- **Table rows stay in.** `survey.md`'s comparison table attributes each
  row with a citekey in backticks, which is not a citation -- the gate
  cannot see it, and neither can this aid. Reporting those rows is
  correct, and `survey-writer` step 9 already says to attribute "in the
  prose or the comparison table, **where the gate can see the key**".
  Suppressing the rows would hide a real instance of the thing that step
  warns about.

## Decision 4: the genre decides whether uncited prose is a finding

This is the expensive one to get wrong, because it shapes the tests.

[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §11 records
that a tutorial's body "carries no citations at all, by design", and
`textbook-chapter-writer`'s own description says it is "not
citation-dense; most content is original worked examples and exercises".
The measurement agrees: after every exclusion above, `book-chapter.md`
still yields **81** findings -- learning objectives, worked arithmetic,
exercises -- and not one of them is actionable.

So a genre declares whether uncited prose is **exceptional** or
**ordinary**:

| Genre | Uncited prose is | Findings raised |
| --- | --- | --- |
| `survey`, `thesis-chapter`, `deep-research` | exceptional | yes, one per uncited sentence |
| `textbook-chapter`, `tutorial` | ordinary | none. The counts are still reported |
| unrecorded (no dossier, no `- genre:`) | exceptional | yes, and the report says the genre was not recorded |

This is `synthesis.single_source_pct`'s move one level down -- that
property excludes uncited units for the same reason, in the same two
genres, and says so. The counts are reported for every genre regardless,
because a textbook chapter whose *background* section cites nothing is
still worth a human's eye; what changes is whether a machine is handed a
finding about it.

The fallback for an unrecorded genre is the **strict** reading, matching
`_units.FALLBACK_KIND`'s reasoning: a report that judges nothing is more
useful reporting at the wrong scale *and saying so* than staying silent,
because silence reads as clean. `--genre` overrides it, with
`choices=sorted(dossier.GENRES)`, which is also how someone runs the
strict reading over a textbook chapter on purpose.

The table lives in `_units.py`, beside `UNITS`, because that module
already owns per-genre policy and `genre_of`, and is pinned against
`dossier.GENRES` the way `tests/test_review_units.py` already pins
`UNITS` -- so a sixth genre cannot arrive as a silent fallback.

## Decision 5: identity, and what an edit does to it

`finding_id` is `sha256(sentence)[:12]`, position-free, matching the
convention the other four aids use. Three consequences, all wanted:

- Editing an unrelated paragraph renames nothing.
- Adding a citation **to the sentence** makes the finding disappear,
  which is what "this finding is gone" should mean (R2).
- Adding a citation **to the block** flips `block_cites` and keeps the
  id. The finding is still true -- this sentence still carries no
  citation -- so it should not be renamed into a new one.

Two identical sentences in one draft collide into one id. That is
`synthesis`'s behaviour too, and it is the honest cost of being
position-free.

## Shape of the change

- `chitragupta/review/uncited_prose.py` -- the aid, and
  `chitragupta/review/_uncited_render.py` -- the text and Markdown
  renderers. **Split from the start, not after the ratchet bites.**
  `synthesis.py` is 280 lines *with* its renderer already split out;
  planning one module here would repeat B2's first mistake. The
  renderers take the findings list as an argument rather than importing
  the aid back, which is the cycle B2 hit.
- Registration in **both** `review.AIDS` and `__main__.AIDS`;
  `review/__main__.py` raises `RuntimeError` when they disagree.
- Advisory, like every aid: exit 0 whatever it finds, no lock, no second
  meaning for `python -m chitragupta.draft gate`
  ([docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10).
- `--json` from the start, through `review.envelope()` /
  `review.write_json()`, with no timestamp.

## The documentation sweep is wider than R10's four files

R10 names AGENTS.md, docs/CLI.md, the README tables and `mkdocs.yml`,
and the `mkdocs.yml` omission is the silent one -- missing nav is INFO,
not a `--strict` failure. But the literal word **four** is load-bearing
in more places than that, and no test catches any of them:

- `review/__init__.py`'s docstring ("Four commands make up the review
  layer"), its output-contract example, and its "All four aids emit one
  now".
- `review/__main__.py`'s docstring ("Four aids, run by hand") and its
  `DESCRIPTION` ("four read-only aids over a finished draft").
- "One of the four commands in the **review layer**" in each of the four
  existing aid docstrings.
- `docs/ARCHITECTURE.md`'s "Layer 4: the review layer".

Grep for it rather than working from this list; it was written by
reading, not by a checker.

## Tests, to the 100% line-and-branch bar

The issue names six, and the measurement adds two:

1. A cited sentence is not reported.
2. An uncited claim is.
3. Captions and headings are excluded -- and so are the reference list,
   the table header row and a comment-only block, one test each, because
   every exclusion branch has to be covered anyway.
4. Ids are stable across runs and unchanged by an unrelated edit.
5. Two runs are byte-identical.
6. Exit 0 either way.
7. `block_cites` is true for an uncited sentence in a citing paragraph
   and false in a bare one.
8. A `tutorial` and a `textbook-chapter` raise no findings and still
   report counts; an unrecorded genre raises them; `--genre` overrides.

Plus the standing pair every aid owes: the `AIDS` dicts agree, and the
per-genre table covers `dossier.GENRES` exactly.

## Record the outcome

Per [plans/README.md](README.md), when this merges, replace the status
line with the PR that closed it and add a "What changed on the way"
section. A plan that no longer matches what shipped is worse than no
plan.
