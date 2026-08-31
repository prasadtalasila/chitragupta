# C4: a numeral in prose is a claim too

Status: **planned, unbuilt, and the plan's own recommendation is to
defer.** Written 2026-08-31 for
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s C4, build order
item 2. The design below is complete and buildable; a measurement taken
after it was written found that it reports the complement of the case
C4 is commissioned for, and that neither it nor its inverse can be shown
to work on any corpus this project has. **Read "Why this plan
recommends against building itself" before building any of it.**

**Written for** the person building the eleventh review aid: which
magnitudes a draft states without anything relating them to a source.
It exists because three of its contracts are decisions an implementer
would otherwise have to invent, and a later reviewer would have no way
to tell a decision from an accident -- what counts as a numeral worth
reporting, what counts as a traceable origin, and which genres raise
findings at all. That is [plans/README.md](README.md)'s first test.

It also meets the second. The aid joins `review agenda` as a ninth
source, and the agenda's item-class table is an artefact
`agenda-reviser`, `docs/AUTO-IMPROVEMENT.md` and
`tests/test_review_agenda.py` all already depend on.

**Assumed:** `review.envelope()` / `review.write_json()` exist and every
aid emits `--json`. `chitragupta/sentences.py` is the shared splitter and
no new one is written. `chitragupta/review/_claims.py` owns
`claim_sentences`, and `chitragupta/review/_units.py` owns `genre_of`
and the per-genre policy tables, pinned against `dossier.GENRES`.

**Not covered here:** D5. (C5, the citekey union invariant, was also
named here until it shipped on 2026-08-31 as `review union`.) This aid
asks only whether a magnitude has an origin, never whether the origin
supports it -- that is `support`'s question, asked of claims rather than
of numbers.

## The measurement this plan rests on

Run before any code, the way
[plans/c1-uncited-prose-report.md](c1-uncited-prose-report.md)'s was,
and for the same reason: C4's roadmap entry says the false-positive rate
decides whether the aid is usable at all, and a rate is measured rather
than predicted.

**The corpus.** 27 real source drafts under `content/drafts/` -- the
four originals in `digital-twins-for-software-engineers/`, the 15-chapter
book, two book chapters in two revisions each, and the Danish chapter --
totalling **11,106 claim sentences** as `_claims.claim_sentences`
counts them.

`content/drafts/books/*.tex` were **excluded, and the reason is worth
recording**: those files are pandoc-citeproc *renders* sitting inside
`drafts/`, with their citations already resolved to bracket numbers and
their bibliographies emitted as `\bibitem[\citeproctext]{...}`.
`citation_gate.extract_citekeys` returns zero on every one of them. They
are not drafts, and measuring on them would have manufactured a citation
gap in all 15 chapters at once.

### The three readings

| Reading | Findings | Share of claim sentences |
| --- | ---: | ---: |
| **Naive** -- any sentence containing a digit | 5,280 | **48%** |
| **Broad** -- after every exclusion in Decision 2 | 2,918 | **26%** |
| **Narrow** -- magnitude-shaped only (Decision 1) | 391 | **3.5%** |

So this aid's difficulty is the same as C1's and sits in the same place:
what it declines to report. The naive reading takes half the prose in
the repository. **The broad reading is measured and rejected**, at a
quarter of it -- recorded here so nobody re-proposes it as the obvious
middle path. Only the narrow reading is a report somebody opens twice.

What each exclusion costs, by the number of sentences it fires on:

| Exclusion | Sentences |
| --- | ---: |
| Cross-reference (`Figure 3`, `§5.4`, `Step 2`, `Exercise 1`) | 2,807 |
| Year (`2044`, `the 2020s`) | 535 |
| Inline or displayed math (`$C = 16$`, `\(k\)`) | 307 |
| Clock time (`17:20`) | 77 |
| Version (`v4.3`, `release 4.0`, `ISO 23247`) | 47 |
| Day and month (`March 2024`, `14 June`) | 40 |
| ISO date (`2026-02-01`) | 8 |
| Code span (`` `port 8080` ``) | 3 |

Cross-references alone are 53% of the naive reading. That is the single
measurement behind Decision 2, and it is why "a numeral in prose" cannot
be the finding as the roadmap entry words it.

### Two of the three traceable origins do not exist

C4's entry names three: *"a `math.md` row, an adjacent citekey, a
`quote:` in `evidence.md`"*. Counted across all **22 dossiers** in
`content/dossiers/`, 21 of them reachable from the drafts measured
(the 22nd is a `_scratch` benchmark dossier):

| Named origin | Dossiers carrying it |
| --- | ---: |
| A `math.md` row | **0** |
| A `quote:` in `evidence.md` | **0** |
| An adjacent citekey | the only one that exists |

Every dossier has `README.md`, `scope.md`, `sections.md`, `steering.md`,
`retrieval.md`, `evidence.md`, `rejected.md` and `revisions.md`. **None
has a `math.md` at all** -- WRITING-STANDARDS.md §12's mapped form is
preferred for a new draft and no real draft has used it yet, so
`_math`'s whole universe is empty. The `quote:` finding is the one
`review quotation` already reports and already says out loud: A2's
contract makes a `quote:` a deliberate act, and nobody has performed it.

And the surviving origin is thin. Of the 391 magnitude sentences, **10**
carry a citekey in the sentence and **10** more carry one somewhere in
their block. Twenty of 391 -- five per cent.

### The fourth origin, built and falsified

`evidence.md` does carry real supporting passages -- a "Supporting
content" column quoting the source -- so a fourth construction suggests
itself and is not in the roadmap: **does the magnitude's numeral appear
in the dossier's kept evidence?** It matches 49% of the 391.

It does not survive its own control. Following `bench/`'s convention
that a script publishing a number must fabricate a difference and assert
it sees it, each magnitude's digits were shuffled -- producing a number
that is by construction *not* the one the draft states -- and the same
lookup run again:

| Token looked up in `evidence.md` | Matched |
| --- | ---: |
| The draft's real magnitude | 49% |
| **The same digits, shuffled** | **41%** |

An eight-point separation is a coin flip. `evidence.md` is long enough
and numeral-dense enough that almost any short numeric token appears
somewhere in it. **Bag-of-numerals matching against dossier prose
manufactures traceability**, and this table is here permanently so the
construction is not re-proposed as a cheap win.

### The genre split, sharper than C1's

Every draft in this repository that records a genre records
`textbook-chapter`. Under C1's genre policy that is the genre where
uncited prose is *ordinary*, and the measurement says magnitudes behave
the same way, only more so. The broad reading's survivors in the life-
cycle chapter are:

> The twin is at version 3.4. ... Ship as 3.5. ... Floor 0.031, ceiling
> 0.15. ... A budget of 0.03 would be a permanent alarm. ... A later
> reader who sees "shadow run: 8 weeks" with no explanation will shorten
> it.

Those are a fictional district-heating station invented to teach with.
There is no source for them and there should not be one; a report
demanding one is wrong about what a textbook chapter is.

The four originals, which is the only place the exceptional genres are
represented at all:

| Draft | Claims | Naive | Broad | Narrow | Narrow, uncited block |
| --- | ---: | ---: | ---: | ---: | ---: |
| `survey.md` | 55 | 26 | 26 | 1 | **0** |
| `deep-research.md` | 28 | 17 | 15 | 0 | **0** |
| `book-chapter.md` | 80 | 22 | 14 | 2 | 2 |
| `tutorial.md` | 38 | 10 | 9 | 2 | 2 |

**So the aid raises zero findings on every dossier-bearing draft in this
repository, and zero on the one survey.** That is stated as a limit
rather than sold as a result -- see the last section.

## Decision 1: the finding is a magnitude, not a numeral

The roadmap words the mechanism as *"report a prose line that contains a
numeral and no traceable origin"*. Taken literally that is the naive
reading, at 48% of the corpus. The measurement narrows it, and the
narrowing is the decision.

**A finding is a sentence stating a magnitude with no traceable
origin.** A magnitude is a numeral in one of four shapes:

| Shape | Example |
| --- | --- |
| A percentage | `rose 43%`, `about 85 per cent` |
| A quantity with a unit | `0.02 bar`, `1 Hz`, `128 MB`, `eight weeks` |
| A factor or multiplier | `3x faster`, `a 4-fold increase` |
| A money or scale word | `$2 million`, `40 thousand` |

This is the class the roadmap's own justification is about -- *"a draft
may state 'throughput rose 43%' with a perfectly real citation beside
it"* -- and it is the class where inventing the number is dangerous. A
bare integer in running prose (`the three properties`, `two of the four
rungs`) is not reported, and that is a deliberate loss of recall bought
for a 7x reduction in volume.

**Not chosen: the broad reading with `block_cites` as volume control.**
C1 solved its volume problem that way and it does not transfer. C1's
broad reading yields 30 findings on a survey; C4's yields 2,918 across
the corpus, of which 2,088 sit in blocks citing nothing, so the flag
sorts nothing. The narrowing has to happen in what counts as a finding.

## Decision 2: the exclusions, each one measured

A numeral is not a magnitude, and raises no finding, when it is:

| Excluded | Why, from the measurement |
| --- | --- |
| **A cross-reference** -- `Figure 3`, `Table 2`, `§5.4`, `Step 2`, `Chapter 11`, `Exercise 1`, `Objective 3` | 2,807 sentences, 53% of the naive reading. The draft pointing at its own furniture, and the number is the renderer's to assign -- `_claims`' own `figureref`/`tableref`/`equationref` handling already says the pipeline does not guess it |
| **A year, a date, a clock time, a version** | 707 sentences across five shapes. WRITING-STANDARDS.md §12 already rules on this in as many words: *"Dates, versions and timestamps are not math."* The rule is cited, not invented |
| **An inline or displayed math span** -- `$C = 16$`, `\(k\)`, `\[...\]` | 307 sentences. A quantity written as mathematics has been declared one by §12, and a symbol legend is not a claim about the world |
| **A code span** -- `` `port 8080` `` | 3 sentences, and §12 is explicit that backticks are for field names, endpoints, filenames and literal values. A literal value is traceable to the system, not to a paper |
| **A list enumerator the splitter left attached** -- `(a)`, `1.` | Splitter artefact, the same class as C1's heading finding |

Everything `_claims.claim_sentences` already excludes is excluded here
for free -- the reference list, headings, captions, table header rows,
comment-only blocks, fenced code. **That is the whole reason this aid
imports `_claims` rather than walking the draft itself**, and it is the
share C1 already paid for.

Two things the measurement tempted us to add and that are deliberately
absent:

- **No "approximately" or hedge detection.** `about 85%` is exactly as
  much a stated magnitude as `85%`, and a keyword list of hedges would
  be invented rather than measured.
- **No numeral-in-dossier matching**, for the reason the falsified
  fourth origin above records. It would suppress roughly half of all
  findings on evidence that is 8 points from noise.

## Decision 3: two origins are implemented, one of them empty today

Stated as one decision because the alternative -- implement only what
has a live universe -- is the tempting one and is wrong.

**Origin 1, a `math.md` row for the magnitude's exact span.** Checked
first, because it is the stronger of the two: §12's mapped form makes
the span itself the key, so a row is the drafter stating that this exact
quantity is a mapped one, which is a narrower and more deliberate act
than citing a paper in the vicinity of a number.

**Origin 2, a citekey in the same sentence.** `block_cites` is carried
on every finding as C1 carries it -- a magnitude in a paragraph that
cites something is a different read from one in a paragraph that cites
nothing -- but it does not suppress the finding, for C1's own reason: a
paragraph with one citation at the end and four unrelated numbers before
it is exactly the failure this aid is for.

**Origin 1 is built despite having no live universe**, and that is the
decision rather than an oversight. Zero of the 22 dossiers carry a
`math.md`, so on every draft in this repository the path is dead code
covered only by a fixture. It is built anyway for three reasons: §12
*prefers* the mapped form for a new draft, so the universe is empty by
adoption lag rather than by design; the aid would otherwise report a
correctly-mapped quantity as unsourced, which is a false positive in the
exact class this aid exists to keep rare; and retrofitting the stronger
origin later means re-deciding the precedence order after findings have
already been filed under the weaker one.

**The third origin the roadmap names is not built.** A `quote:` in
`evidence.md` has no universe *and* no adoption path -- A2's contract
makes one a deliberate act nobody has performed, which `review
quotation` already reports about itself. Adding an unreachable branch
for it would be untestable except by fixture and would buy nothing §12's
mapped form does not already buy. The roadmap named three origins; this
plan builds two and says why the third is declined.

**The report's header states what it could check against**, per
[docs/REVIEW.md](../docs/REVIEW.md)'s rule that a finding absent because
the check could not run must not read as a finding absent because there
was nothing to find: how many `math.md` rows were available, and that
`quote:` matching is not implemented. On every draft here the first
number is `0`.

## Decision 4: the genre decides whether a magnitude needs an origin

A new table, `_units.MAGNITUDE_CLAIM`, beside `UNITS` and
`UNCITED_PROSE`, pinned against `dossier.GENRES` exactly as those are:

| Genre | An unsourced magnitude is | Findings raised |
| --- | --- | --- |
| `survey`, `thesis-chapter`, `deep-research` | exceptional | yes, one per magnitude |
| `textbook-chapter`, `tutorial` | ordinary | none. The counts are still reported |
| unrecorded | exceptional, and the report says the genre was not recorded | yes |

**Not a reuse of `UNCITED_PROSE`.** The two tables have the same shape
and the same values today, and they answer different questions that
should stay independently revisable: C1's is about citations, this one
about magnitudes. A tutorial pinning `python 3.11` and a textbook
inventing `0.031 bar` are both ordinary now, but a later decision that a
tutorial's version numbers *do* need an origin should not silently
change what C1 reports. `_units.py`'s own test already pins each table
against `dossier.GENRES` separately, so a sixth genre still cannot
arrive as a silent fallback.

`--genre`, with `choices=sorted(dossier.GENRES)`, overrides it, which is
how somebody runs the strict reading over a textbook chapter on purpose.
The unrecorded fallback is the strict reading, matching
`_units.FALLBACK_STANDING`: silence reads as clean.

## Decision 5: the name is `magnitudes`

`python -m chitragupta.review magnitudes <draft>` ->
`content/review/<topic>/<stem>.magnitudes.md`.

Not `numerals`, though that is the roadmap's word, because Decision 1
narrows the finding away from it: an aid called `numerals` that ignores
`the three properties` and `Figure 3` is misnamed, and a
`survey.numerals.md` found on disk months later would be read as a
promise the report does not keep. `magnitudes` is exactly what it
reports.

Blocked by the roadmap's constraint 5 and clear of it: not `audit`,
`verdict`, `reckoning`, `ruling` or `triage` -- the judgement register
belongs to the gate. Checked for collision against `_math.py`,
`style_equations.py` and `chitragupta/config.py`; neither `magnitude`
nor `numeral` is a term of art in any of them.

**This file keeps the roadmap's word and the aid does not**, which is
deliberate and worth one sentence so it does not read as drift.
[plans/README.md](README.md) names a plan for the roadmap item it
implements, not for what that item turns out to be called, so
`c4-numeral-as-claim.md` is correct and stays. Until C4's roadmap
section is deleted, someone searching the roadmap for "numeral" will
land on a plan about magnitudes; the sentence replacing the roadmap's
"none of the three has a plan" should name both words, so the trail
holds from either end.

## Decision 6: identity, and the agenda class

`finding_id` is `sha256(sentence)[:12]`, position-free, matching every
other aid. Editing an unrelated paragraph renames nothing; adding a
citekey to the sentence makes the finding disappear, which is what R2
asks "this finding is gone" to mean; adding one to the block flips
`block_cites` and keeps the id, because the finding is still true.

The agenda gains one class, **`uncited-magnitude`**, and it is
**surfaced, never `unattended`**. `agenda-reviser` may not repair it,
for the reason `docs/AUTO-IMPROVEMENT.md`'s table already gives for
`uncited-claim`: the fix is evidence or deletion, and a reviser
rewording the sentence would make the number *look* sourced without
sourcing it. Its rank sits beside `uncited-claim` in `CLASSES`, after
`claim-support` and before `uncited-source`.

## Shape of the change

- `chitragupta/review/magnitudes.py` -- the aid -- and
  `chitragupta/review/_magnitudes_render.py` -- the text and Markdown
  renderers. **Split from the start**, as C1's plan insists and for its
  reason: `uncited_prose.py` is 205 code lines *with* its renderer
  already split out. The renderers take the findings list as an
  argument rather than importing the aid back.
- The shape table from Decision 1 lives in `magnitudes.py`, not in
  `_claims.py`. `_claims` answers "which sentences carry a claim", which
  C1 and C2 both want; "which of them state a magnitude" is this aid's
  question alone, and `_claims.py` at 134 code lines should not grow a
  second contract.
- `_units.MAGNITUDE_CLAIM`, seven lines with its docstring.
  **`_units.py` is at 223 of the 250-line cap**, so this fits with
  roughly 20 lines of headroom and the commentary justifying it belongs
  in this plan rather than in that module's docstring.
- Registration in **both** `review.AIDS` and `__main__.AIDS`;
  `review/__main__.py` raises `RuntimeError` when they disagree.
- Advisory: exit 0 whatever it finds, no lock, no second meaning for
  `python -m chitragupta.draft gate`.
- `--json` from the start, through `review.envelope()` /
  `review.write_json()`, with no timestamp. Prints by default and writes
  only under `--write`, like every aid except `provenance` and `agenda`.

### One split is owed before the agenda class lands

**`chitragupta/review/agenda/_items_findings.py` is at 243 code lines
against the 250 cap**, and `code-standards-register.toml` carries no
exemption for it. Measured, that is 17 lines of header and seven
builders:

| Builder | Code lines |
| --- | ---: |
| `prose_items` | 51 |
| `claim_support_items` | 37 |
| `unsupported_claim_items` | 31 |
| `misquoted_items` | 31 |
| `verbatim_run_items` | 29 |
| `uncited_source_items` | 24 |
| `uncited_claim_items` | 23 |

`uncited_magnitude_items` will sit at 23 to 24 -- it is shaped like
`uncited_claim_items`, the builder it ranks beside -- which lands the
module at **267, seventeen over**. So a split is not optional.

**Move `prose_items` to `chitragupta/review/agenda/_items_prose.py`.**
Not an arbitrary cut to get under the number: it is the one builder
whose source is `StyleSource` rather than `AidSource`, because it comes
from the drafting layer's prose check rather than from a review aid --
a boundary the type signatures already draw and that
`agenda/_sources.py` already treats separately. That leaves
`_items_findings.py` at **192**, with 58 lines of headroom, and the new
module at roughly 66.

**It rides along in this PR rather than going first.** C1's precedent is
the same move -- `_claims.py` was split out of `uncited_prose.py` within
C1's own PR -- and `DEVELOPER-AGENTS.md` has no rule sending a
mechanical split to its own PR. The reason to keep it here is that the
ratchet reddens the suite the moment the class is added, so a separate
prerequisite PR would exist only to make this one green. If a reviewer
disagrees, splitting it out costs one extra PR and a new row above C4 in
the build order.

## The documentation sweep

Wider than R10's four files, and none of it is caught by a checker
except where noted. Grep rather than working from this list.

**The literal aid count.** Counted 2026-08-31, after C5 shipped as
`review union`: `review.AIDS` has **ten** entries, so this aid would
make eleven.

- `chitragupta/review/__init__.py`'s docstring -- "Ten commands make up
  the review layer", its module enumeration, its output-contract
  example, and "all ten are interpreter tier 1".
- `chitragupta/review/__main__.py`'s docstring and `DESCRIPTION`.
- **"One of the seven commands in the review layer"** -- the opening
  line of `citation_provenance.py`, `citation_coverage.py`,
  `synthesis.py`, `uncited_prose.py` and `quotation.py`, and "One of the
  seven aids" in `verbatim_check/__init__.py` and
  `figure_layout/__init__.py`. **All seven are stale by three**, and
  getting worse: they read "seven" against a real count of ten, having
  been missed by each of the last three aids to ship. That is the
  measured cost of a count duplicated rather than derived, and it is
  worth fixing whether or not this aid is ever built.
- `README.md:81`, `docs/REVIEW.md:4`, `:46` and `:258` ("Nine of the ten
  aids are deterministic").
- **`docs/ARCHITECTURE.md:343` is stale on `main` today** -- "Seven of
  the nine answer questions of judgement" against a count of ten. Left
  alone here rather than corrected in passing, because the fix depends
  on whether `union` is a judgement aid or a decidable one, and that is
  C5's call to record rather than this plan's to guess.

**The agenda's "eight aids"** becomes nine: `AGENTS.md:206`,
`docs/REVIEW.md:147`, `.claude/skills/agenda-reviser/SKILL.md` (the
frontmatter description and line 233), and
`tests/test_review_agenda.py`'s module docstring and its `aid_stubs`
fixture ("Every one of the eight aids' `main` replaced by a recorder").

**Machine-checked, so these redden the suite rather than merely going
stale:**

| File | Test | What it pins |
| --- | --- | --- |
| `docs/FEATURES.md` | `tests/test_features_doc.py` | The literal string `"Ten advisory aids"`, derived from `len(review.AIDS)` -- three sites, lines 32, 306 and 389, all reading "nine" today |
| `docs/ARCHITECTURE.md`'s layer-4 section | `tests/test_architecture_review_layer.py` | The spelled-out count and the aid list, scoped to `## Layer 4: the review layer` alone |
| `docs/PACKAGING.md`'s leaf-command counts | `tests/test_packaging_command_table.py` | `17 verbs and aids` / `41 invocable leaf commands`, against the live parsers |
| `docs/diagrams/*.mmd` and `svg/*.svg` | `tests/test_diagrams_in_sync.py` | That each SVG matches its source |

Both `_NUMBER_WORDS` tables already carry `10: "Ten"`, so neither test
needs extending -- only the prose it reads.

Four diagrams name the aids and each needs its SVG re-rendered:
`00-main-workflow`, `extra-sequence`, `v3-artifacts`, `g1-corpus-led`.
`mmdc` needs `--no-sandbox` on this host, and an unchanged `.mmd` still
re-renders to a different width, so re-render only what changed.

**Also**: `docs/CLI.md`'s command reference, `mkdocs.yml` nav (missing
nav is INFO, not a `--strict` failure, which is what makes it the silent
one), `docs/AUTO-IMPROVEMENT.md`'s item-class table, and
`docs/REVIEW.md`'s cost table -- which needs a real measured column, not
an estimate.

And [FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md) itself: per
`plans/README.md`'s convention and the roadmap's own, C4's subsection
and its build-order row are **deleted**, not marked done.

## Tests, to the 100% line-and-branch bar

1. A magnitude with a citekey in the sentence is not reported; one
   without is.
2. Each exclusion in Decision 2 has its own test -- cross-reference,
   year, date, clock, version, math span, code span, enumerator --
   because every branch has to be covered anyway.
3. Each shape in Decision 1 is recognised: percentage, unit, factor,
   money. And a bare integer is *not* a finding.
4. A `math.md` row for the span traces the magnitude, and takes
   precedence over a citekey when both are present -- against a fixture
   dossier, which per Decision 3 is the only thing that will cover this
   path until a draft adopts §12's mapped form.
5. The header reports `0` available `math.md` rows when the dossier has
   none, and says so rather than omitting the line.
6. `block_cites` is true for an unsourced magnitude in a citing
   paragraph and false in a bare one, and does not suppress either.
7. `tutorial` and `textbook-chapter` raise no findings and still report
   counts; an unrecorded genre raises them and says the genre was not
   recorded; `--genre` overrides.
8. Ids are stable across runs, unchanged by an unrelated edit, and
   unchanged by a citation added to the block.
9. Two runs are byte-identical. Exit 0 either way.
10. The agenda emits `uncited-magnitude` with `unattended=False`, and
    ranks it where Decision 6 says.

Plus the standing pair every aid owes: the two `AIDS` dicts agree, and
`MAGNITUDE_CLAIM` covers `dossier.GENRES` exactly.

## What this aid cannot demonstrate on this corpus

Stated plainly rather than discovered later, and the honest counterpart
to [C6's skip](../docs/FEATURE-ROADMAP.md#-c6-measure-the-refusal).

**It finds nothing here.** Under Decision 4's genre gate the aid raises
zero findings on all 21 dossier-bearing drafts, because every one of
them is a `textbook-chapter`, and zero on `survey.md`, whose single
magnitude sits in a citing block. The exceptional-genre sample in this
repository is one 55-sentence survey and one 28-sentence report,
neither with a dossier.

**That is not the same defect C6 had, and the difference is why this
ships.** C6's *ground truth constructions were falsified* -- removing a
shelf raised the retrieval score, so the negative set was not negative.
Nothing here is falsified. The one construction that was --
numeral-in-`evidence.md` -- is this plan's own invention, not the
roadmap's, and killing it narrows the aid rather than defeating it. What
the measurement establishes is a **false-positive rate**, which is the
exact quantity C4's roadmap entry says decides usability, and it comes
out at zero on real drafts. For an advisory aid whose named risk is
alarm fatigue, quiet is the pass condition.

What it does not establish is a **true-positive rate**, and no draft in
this repository can. That waits on a survey or thesis chapter that
states a magnitude, which is a corpus fact rather than a code one. The
roadmap entry anticipates exactly this: *"Ship it reporting what it
finds and let a real draft say whether the signal survives."*

**Two blind spots to name in the aid's own docstring**, so the first
person to run it does not read them as bugs:

- Pointed at `content/drafts/books/*.tex` -- pandoc-citeproc renders,
  not drafts -- it reports hundreds of findings, because
  `extract_citekeys` returns nothing on resolved bracket citations.
  `uncited` has the same blind spot today; it is a property of those
  files' location, not of either aid, and fixing it is neither one's
  job.
- A `\hline`-ruled table's header row reaches this aid as prose, for the
  reason `_claims.TEX_HEADER_RULE` already records.

## Why this plan recommends against building itself

Written after the decisions above, from a measurement taken to answer
"is this worth building?" It does not amend them -- they are what the
aid *would* be. It records why it should not be.

### 1. The aid reports the complement of its motivating case

C4's roadmap entry motivates the aid with one example:

> a draft may state "throughput rose 43%" with a perfectly real citation
> beside it and no check anywhere relates the number to the source

**Decision 3 marks that traced.** A citekey in the sentence is an
origin, so a magnitude with a real citation beside it and a fabricated
value raises no finding. What the aid reports is the *other* case -- a
magnitude with no citation at all.

That is a design inversion rather than a tuning question, and it is
independent of anything to do with this corpus: it would be just as
wrong on a repository full of surveys. Either the roadmap entry's
example is not what C4 is for, or Decision 3 is, and the entry is the
older and more considered of the two.

### 2. The genre gate never fires, and not by accident

Counted across `content/dossiers/` and both snapshots in
`content/backup/` -- **37 dossiers, and every one records
`textbook-chapter`.** No survey, thesis chapter or deep-research report
has ever been drafted in this project. Decision 4 raises findings only
in those three genres, so the aid's finding count on the project's
entire recorded history is **zero**, and would have been zero on any day
it had existed.

The two exceptional-genre drafts that exist at all are the genre-less
demos: `survey.md`, whose one magnitude is cited, and
`deep-research.md`, which states none. The base rate of the failure C4
guards against, over **11,106 claim sentences**, is **0 observed
instances**.

### 3. The inverse check was built, and cannot discriminate

If the aid should report the motivating case instead -- is the cited
magnitude's number actually in the cited source? -- that is buildable:
the corpus is parsed and `passages.source_passages` already serves the
text. It has a real, non-empty universe, which Decision 3's two origins
do not: **8 distinct sentences, 11 (sentence, citekey) pairs**, source
text available for every one.

All 11 numbers are present in the cited source. Then the same control
that falsified the fourth origin above:

| Token looked up in the cited source | Matched |
| --- | ---: |
| The draft's real magnitude | 11 of 11 |
| **The same digits, shuffled** | **9 of 11** |

`source_passages` returns whole-paper text -- **averaging 102,658
characters** over these eleven -- and a two- or three-digit token
appears somewhere in almost any paper. "100% found" means the check
cannot discriminate, not that nothing is fabricated. It is the
`evidence.md` failure again, one haystack larger.

Narrowing the haystack to the single passage `provenance` already
matches would discriminate, and is refused for a reason the review layer
has already published about itself:
[docs/REVIEW.md](../docs/REVIEW.md)'s third limit records that the
dominant failure in `support` was *"the passage-matching step handing
the scorer the wrong passage from an otherwise-relevant paper."* A
number absent from a wrongly-matched passage is a false accusation of
fabrication, and the measured base rate of real fabrications is zero.

**One defect this control exposed, recorded so the next measurement
avoids it.** The token lists above were initially polluted by the
citekeys themselves: `[@guo_life_2024]` contributes the token `2024` to
any scan that does not strip citation markers first. It did not move the
headline table -- re-measured with `[@...]` and `\citep{...}` stripped,
the magnitude count is **391 either way** -- because `is_magnitude`
keys on percent, unit, factor and money shapes that a citekey cannot
satisfy. It did inflate the source-lookup experiment, which makes that
result weaker than the table shows, not stronger. **Strip citation
markers before any numeral scan.**

### 4. What it costs, measured

`eb12a6c2`, the commit that shipped C1 -- the closest comparable aid --
touched **29 files for +1,645 / -203 lines**. C4 costs that plus what
C1 did not need: an agenda item class, the `_items_findings.py` split
above, four diagram re-renders with their SVGs, and the correction of
seven aid docstrings.

Against a measured benefit of zero findings, on a check that reports the
complement of its motivating case.

### The recommendation

**Defer C4, and say why in the roadmap in its own terms.** The grounds
are different from [C6's](../docs/FEATURE-ROADMAP.md#-c6-measure-the-refusal)
and the roadmap distinguishes its skips by reason, so this should not be
filed as "skipped by evidence" beside it. C6's *ground-truth
construction was falsified*: the shelf-holdout raised retrieval scores,
so the negative set was not negative. Nothing here is falsified. **C4 is
mis-specified** -- the finding it defines is the complement of the
finding it was commissioned for -- and separately unmeasurable on a
single-genre corpus.

Two things would revive it, and they are not the same thing:

- **A survey, thesis chapter or deep-research draft with a dossier**,
  which would give Decision 4's gate something to fire on and the base
  rate a chance to be non-zero. This is a drafting fact, not a code one.
- **A decision that the finding is the cited case**, which is a
  different aid from the one designed above: it would need a passage
  narrow enough to discriminate in, and REVIEW.md's third limit says
  the review layer does not currently have one it trusts.

Everything above the line stays as written. If either condition
changes, the exclusions, the genre table, the naming and the sweep are
all still right, and only Decision 3 has to be re-opened.

## One sentence this plan falsified on arrival

[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s build order
said, of D5, C4 and C5: *"**None of the three items still listed here
has one**, which is a statement about them rather than a gap."*

This file made that false. **The claim was right on its own terms and
was not simply deleted**: C4's entry did name its files, its size and
its dependency, and what put it over `plans/README.md`'s first test was
not the entry's thinness but three contracts it could not settle without
a measurement -- what counts as a numeral worth reporting, what counts
as a traceable origin, and which genres raise findings at all. Two of
the three came out contrary to what the entry predicted.

**Amended in the same PR that filed this plan.** The roadmap now says
two items remain and neither has a plan, and carries a paragraph on why
one plan here belongs to an item that was never built -- because a plan
records a decision, including a decision not to build. C4's own section
keeps its place and gains the deferral, the way C6's and D4's sections
keep theirs.

## Record the outcome

Per [plans/README.md](README.md), when this merges, replace the status
line with the PR that closed it and add a "What changed on the way"
section. A plan that no longer matches what shipped is worse than no
plan.

Two conventions this repository holds every PR to, noted because a
plan-shaped change is easy to think exempt from them: **every PR bumps
the version**, docs-only included, and the check runs first in `lint` so
a miss reads as a lint failure with no lint output. Check the tags
rather than `main` before picking the number -- two PRs choosing the same
version merge silently and lose the bump.
