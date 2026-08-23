# B2: multi-source synthesis, at the unit each genre can carry

Status: **built.** Written 2026-08-21, shipped in
[#341](https://github.com/prasadtalasila/chitragupta/pull/341) (6.17.0),
which closed
[#310](https://github.com/prasadtalasila/chitragupta/issues/310) --
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s B2, build order
item 6.

## What changed on the way

Per [plans/README.md](README.md): a plan that no longer matches what
shipped is worse than no plan. Nine differences, and the first is the
one a reader is most likely to trip over.

1. **Three modules, not two.** `synthesis.py` came out at 298 code
   lines against C2's 250, so the rendering split off into
   `_synthesis_render.py`. The plan predicted the cap would bite and
   planned one split; it needed two. The boundary is honest -- what the
   numbers *are* against how they read -- but it was found by the
   ratchet, not by design.
2. **The renderers take the findings list as an argument.** The first
   cut had `_synthesis_render` importing `synthesis` for `Report` and
   `findings()`, which is a cycle; it was papered over with a deferred
   import and a `pylint: disable`. Passing `found` in removes the cycle,
   the disable, and a second `findings()` computation per render.
3. **`_units.blocks` is public, and `citation_provenance` uses it.** The
   plan said `_paragraph_spans` would migrate. The first commit did not
   do it and wrote a third copy of the walk instead; the pre-push review
   caught that, and the second commit did the migration properly. The
   register entry shrank 459 -> 457.
4. **`dossier.GENRES` is new.** The genre-to-unit table needed something
   to be checked against, or a sixth genre would arrive as a silent
   fallback to the paragraph. `dossier init --genre`'s help string is
   now built from it rather than restating it.
5. **A unit raises at most one finding.** A single-source section has a
   run as long as it has paragraphs, so reporting `single_key_run`
   beside `single_source` said the same thing twice. The run finding is
   suppressed when spread is 1.
6. **`RUN_REPORTED_AT = 3`**, taken from `textbook-chapter-writer` step
   4's own "before reusing the same citekey a third time". Every
   section's run is reported whatever its length; the constant only
   decides which get their own line, so it is not a threshold anything
   is scored against.
7. **A phantom section, found and fixed.** Blank lines before the first
   heading opened a section on the blank line, so a draft starting with
   one reported an extra uncited unit. Not in the plan's test list; it
   is now the eleventh test.
8. **`§11` was appended, exactly as the plan required** -- verified
   against the callers that cite `WRITING-STANDARDS.md` sections by
   number, one of which is a test assertion.
9. **`mkdocs.yml` needed nothing**, as predicted: this aid has no
   dedicated doc page, so `docs/CLI.md` carries it like `coverage` and
   `verbatim`.

The tutorial question the plan left open under "Open, deliberately" was
closed before the build, on the human's instruction that the guarantee
is needed in every genre. It is recorded below as a settled decision --
"Why a tutorial's unit is the document" -- rather than as a doubt.

**Written for** whoever builds it. **Assumed:**
[docs/GENRE.md](../docs/GENRE.md) for what each genre owes its reader,
[docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md) for the dossier,
and the roadmap's Theme B preamble for why paragraph shape is an
anti-copying mechanism at all. **Not covered here:** that argument
itself, which is the roadmap's and is not restated; and B1, which
shipped as [#318](https://github.com/prasadtalasila/chitragupta/pull/318).

## The problem in one line

The roadmap and the issue both state the rule at **one** unit -- the
body paragraph -- and that unit is right for two of the five genres,
wrong for two, and impossible for one.

## The correction this plan makes

The issue conflates two things that separate cleanly:

- **the guarantee** -- prose required to fuse two or more sources cannot
  be a transcription of any one of them, because you cannot transcribe
  two sources simultaneously;
- **the unit it binds at** -- paragraph, section, or document.

The guarantee is universal. The unit is per-genre. A multi-source
*paragraph* is what a survey wants and what a textbook chapter finds
distracting; a tutorial cannot have one at all, because its body carries
no citations by design
(`tutorial-writer/SKILL.md`,
step 6 -- citing is confined to "Where to go next" and is optional even
there).

Reading B2 as paragraph-only forces a choice between applying a rule
where it damages the prose and exempting three genres from the
guarantee. Neither is necessary.

## The contract

| genre | unit | the rule |
| --- | --- | --- |
| `survey` | paragraph | a body paragraph cites two or more citekeys wherever the evidence set allows |
| `deep-research` | paragraph | same |
| `thesis-chapter` | paragraph | same |
| `textbook-chapter` | **section** | a section's citations span two or more citekeys **and do not arrive in blocks** -- its paragraphs are free to be single-source, its consecutive paragraphs are not free to be the same single source |
| `tutorial` | **document** | the lesson is not a walkthrough of one source's procedure; two or more distinct citekeys in "Where to go next" are the evidence that it is not |

In every genre, a single-source unit is a **deliberate choice the
drafter states**, not a default.

**The unit comes from the dossier.** `dossier init --genre` is required
(`_cli.py:48`) and `scope.md` records
`- genre: <one of the five>` on its own line
(`_create.py:65`). A review aid can
therefore resolve the unit without being told, exactly as
`style_check.language_of()` resolves the dialect
(`style_check.py:67-99`). A draft with
no dossier falls back to an explicit `--unit`, and the report says which
of the two it used.

**Declaring a single-source unit.** An inline marker adjacent to the
unit:

```markdown
<!-- single-source: Foo2019 is the only paper in the corpus covering X -->
```

```latex
% single-source: Foo2019 is the only paper in the corpus covering X
```

Invisible when rendered, visible to the report and to a human reading
the source. It carries no `@` sigil and no `\cite`, so
`citation_gate.extract_citekeys()` does not read it as a citation --
which is what stops the marker inflating the count it exists to explain.

**Two rules the marker needs, and the reason for each was measured, not
assumed.** `_paragraph_spans` splits on blank lines and joins the
non-blank lines of a block with a space, which gives a marker two
distinct ways to go wrong:

```python
>>> _paragraph_spans(["Body text [@Foo2019].", "<!-- single-source: ... -->"])
[(1, 2, 'Body text [@Foo2019]. <!-- single-source: ... -->')]
>>> _paragraph_spans(["<!-- single-source: ... -->", "", "Body [@Foo2019]."])
[(1, 1, '<!-- single-source: ... -->'), (3, 3, 'Body [@Foo2019].')]
```

So:

1. **The marker attaches to its unit with no blank line between them**
   -- above it or below it, but inside the same block. Separated by a
   blank line it becomes a *unit of its own*, counted as a
   zero-citation unit, and detached from the thing it explains.
2. **Markers are stripped before unit text is computed**, and a
   marker-only line is never a unit. Otherwise the marker joins the
   text that feeds `finding_id()`, and *declaring* a single-source unit
   would change that unit's identity -- the declared/undeclared split
   would churn every id it touched, which is exactly what R2 exists to
   prevent.

The report reads the marker from the raw lines of the span, then
measures the stripped text. `_units.py` owns both halves so the two
cannot drift.

## Decisions this plan settles

**Why a per-genre unit rather than a per-genre threshold.** Because a
threshold is a continuous score with a line drawn on it, and R3 forbids
one becoming the thing being optimised. The unit is a *label* -- it
changes what gets counted, never what counts as passing. There is no
target proportion in this design, per genre or otherwise, and adding one
later needs a separate argument.

**Why thesis chapters keep the paragraph.** They are RQ-driven and
citation-dense, and the related-work chapter is the single place in this
pipeline most exposed to transcription. Sub-dividing the genre by
section role -- background at paragraph, contribution at document --
was considered and rejected: it needs the report to classify sections,
which is either a heuristic that is sometimes wrong or a new dossier
field, and neither is worth it for a report that judges nothing. A
contribution section that runs single-source declares it with the
marker, which is the mechanism already being built.

**What stops paragraph-level copying when the unit is the section.**
This is the question the section unit has to answer, because the
guarantee it buys is weaker than the paragraph unit's and pretending
otherwise would be the whole design failing quietly.

A section unit as *spread alone* -- "cites two or more citekeys" -- is
**satisfiable by concatenation.** Three paragraphs of A, then three of
B, then three of C spans three sources and interleaves none of them, and
every one of those nine paragraphs remains a candidate transcription.
Spread is not fusion.

So the section unit is measured at two scales, not one:

1. **spread** -- distinct citekeys in the section, as above; and
2. **the longest run of consecutive paragraphs resting on the same
   single citekey**, within the section.

The second is what catches the block-structured section, and it makes an
existing rule observable rather than adding a new one:
`textbook-chapter-writer` step 4 already instructs *"before reusing the
same citekey a third time within one section, do one more `search()`
pass"*, and nothing has ever checked it. Both numbers are reported.
Neither is a threshold -- a run of four in a section where one paper
genuinely is the only source for a sustained point is legitimate, and
the marker declares it.

Two further mechanisms bind below the unit in **every** genre, and the
section unit leans on them by design rather than by omission:

- **A2's `claim:`/`quote:` split** (#320, shipped). Prose is written
  from `claim:` -- the drafter's own words, recorded when the evidence
  was judged, which is before any sentence of the draft existed.
  `quote:` is opt-in and usable only inside quotation marks with an
  attribution. Textbook chapters are in scope for this:
  `textbook-chapter-writer/SKILL.md:126-129` requires the same block and
  says explicitly it is "not a shortcut `support:` line".
- **`verbatim`**, a real net but a partial one -- genuine restatement is
  detected only where the embedding tier can run, so a clean scan is not
  a clean bill of health.

**One residual exposure, named rather than papered over.** Step 3 still
has the drafter read 500-character retrieval snippets directly
(`textbook-chapter-writer/SKILL.md:246`), so source wording is in
context even with A2 shipped. That is roadmap **A3**, extraction at
retrieval, and it is unbuilt. B2 cannot close it and does not claim to.

**Why a tutorial's unit is the document.** Not as an exemption, and not
as a weaker version of the rule -- as the place the guarantee actually
binds in this genre. A tutorial's body is original prose, verified to
run before it is presented, and the anti-transcription work there is
done by that originality and by `verbatim`. What a tutorial *can* be a
transcription of is a single source's procedure, end to end, and that
failure is invisible at every scale below the whole document. Two or
more distinct citekeys in "Where to go next" are evidence about the
lesson's derivation, which is the thing at risk. Mid-lesson citations
stay banned; the genre's own rule is not being relaxed to make room for
this one.

**Why a zero-citation unit is counted but is never a finding.** Most of
a textbook chapter and effectively all of a tutorial are original prose
with no citation, and that is the genre working correctly. Making
uncited prose a finding would bury the one thing this report is for.

**Why the marker lives in the draft, not in `sections.md`.** A section
has a stable name to key on; a paragraph does not, so a dossier-side
record would break on the first edit that reorders anything. The marker
also puts the drafter's reason where a human reviewer reads it.

**Why not `extract_citekeys_from_line`.** #310 names it as the
reusable extractor. Its own docstring says otherwise
(`citation_gate.py:121-151`): it is a
back-compat per-line wrapper with a known false positive on fenced code
and a known false negative on a `\citep` argument split across lines,
and it tells any new caller holding the whole document to use
`extract_citekeys()` instead. This report holds the whole document.
Note the correction on the issue so the next reader is not misled.

**Naming.** `synthesis`, matching the roadmap's own heading for this
theme. The judgement register belongs to the gate -- `audit`,
`reckoning`, `verdict`, `ruling` are unavailable however well they fit
([docs/AUTO-IMPROVEMENT-RATIONALE.md](../docs/AUTO-IMPROVEMENT-RATIONALE.md),
"Naming, and the register the review layer may not use") -- and `triage`
is separately retired
([docs/REJECTION.md](../docs/REJECTION.md)).

**Prior art.** OpenScholar's `src/instructions.py::prompts_w_references`
instructs this behaviour, and is quoted as evidence in the roadmap
rather than lifted. The wording here is ours; credit is
[INSPIRATION.md](../docs/INSPIRATION.md)'s. Its **citation mechanics are
not adapted**: upstream cites by positional index into a truncated list,
so reordering the list silently changes what every citation means. This
project has real citekeys and keeps using them.

## The report

`python -m chitragupta.review synthesis <draft>` -- a fourth review aid,
alongside `provenance`, `verbatim` and `coverage`. **Advisory, exit 0,
no lock**, like the other three.

Per unit: the distinct citekeys it cites, plus -- where the unit is the
section -- the longest run of consecutive paragraphs on a single same
citekey inside it. In summary: units citing zero,
one, and two-or-more; the proportion that are single-source; and that
proportion split into **declared** and **undeclared**. Without the
split, the rule's second half -- that a single-source unit is a stated
choice -- is unobservable, and the report merges a considered decision
with an unexamined one.

Findings are single-source units only, undeclared first, worst-first
thereafter. R2 identity is `sha256(f"{unit}\x00{text}")[:12]`,
position-free for the same reason
`citation_provenance.finding_id()` is: an identity built on line number
renames every remaining finding the moment an edit above it shifts.

The header prints the genre, the unit measured, and where the genre came
from (`scope.md`, `--unit`, or nothing). This is load-bearing, not
decoration: it is what stops a tutorial's report reading as "0%
multi-source paragraphs", a number that would be both true and
meaningless, since paragraphs were never the unit.

The report states on its face that **a thin corpus legitimately produces
single-source units, and that this counts but does not judge** -- and
that a human reads it, nothing acts on it unattended (R3).

## Files

| File | Change |
| --- | --- |
| `docs/WRITING-STANDARDS.md` | **owns** the rule and the genre-to-unit table, appended as **§11** -- see below |
| `.claude/skills/survey-writer/SKILL.md` | step 6: unit is the paragraph; point at the canonical statement |
| `.claude/skills/thesis-chapter-writer/SKILL.md` | step 5: same |
| `.claude/skills/deep-research/SKILL.md` | Phase 5: same, in the brief handed to the writer subagent |
| `.claude/agents/deep-research-writer.md` | writing standards: same |
| `.claude/skills/textbook-chapter-writer/SKILL.md` | step 4: sharpen the existing source-diversity paragraph into a stated *section* unit, and name the run rule its "third time" sentence already implies -- amend it, do not add a second competing rule beside it |
| `.claude/skills/tutorial-writer/SKILL.md` | step 6: document unit; mid-lesson citations stay banned |
| `chitragupta/review/_units.py` | **new.** `genre_of()`, the genre-to-unit table, the splitters, marker detection |
| `chitragupta/review/synthesis.py` | **new.** compute, render, `--json`, CLI -- `citation_coverage.py`'s shape |
| `chitragupta/review/__init__.py` | register in `AIDS` |
| `chitragupta/review/__main__.py` | register in `AIDS`; the import-time drift guard enforces parity |
| `chitragupta/review/citation_provenance.py` | migrate `_paragraph_spans` to `_units.py` |
| `AGENTS.md`, `docs/CLI.md`, `README.md`, `docs/ARCHITECTURE.md` | R10's sweep -- see below |

**Append the standard as §11, do not insert it.** That file's sections
are numbered 1--10 and are cited *by number* from outside it -- §2, §8,
§9 and §10 each have at least one caller in `chitragupta/`, `docs/` or
`tests/`, and one of them is a test assertion
(`tests/test_style_assets_match_the_standard.py:35`). Inserting a
section anywhere but the end renumbers those silently, and reddens the
suite at best. §11 goes after §10 Figures and before "Sources and
attribution", which is unnumbered.

**Two modules, decided up front rather than discovered.** C2 caps a new
module at 250 code lines and admits no new offenders
(`tests/test_code_standards_scan.py:39,78`).
`citation_coverage.py` sits at exactly 250 for an aid of this shape, so a
fourth aid does not fit in one file. `_units.py` takes the part that is
genuinely shared.

**`verbatim_check.py` is left alone.** It has its own paragraph splitter
and already builds per-paragraph citekey sets
(`verbatim_check.py:314-330,402`),
so a third copy of that logic is real duplication -- but it is 1880 code
lines and frozen in the legacy register, and migrating it is a churn
risk out of proportion to the gain. `citation_provenance` migrates
because it is the smaller and better-tested of the two, and the move
shrinks a file already on that register.

**The two aids are not expected to agree on paragraph boundaries, and
that is not a bug.** `synthesis` owns its units through `_units.py`;
`verbatim` keeps its own splitter for its own purposes. Say so in
`synthesis`'s module docstring, so the first person to lay two reports
side by side and find a different paragraph count files nothing.

## The R10 sweep

Registration in both `AIDS` tables is machine-enforced: the drift guard
at `review/__main__.py:47-62` raises
at import if they disagree, and
`tests/test_review_entrypoint.py` exercises it.

Nothing else is. Roughly ten prose sites state "three aids" as a literal
fact and are found only by reading -- `docs/CLI.md:129,997`,
`README.md:87-88,194`, `docs/ARCHITECTURE.md:335-337,530`,
`docs/LADDERS.md:461,603`, `docs/CONFIG.md:140`,
`docs/CODE-STANDARDS.md:456`, `docs/PLAGIARISM-DESIGN.md:390`,
`docs/INSPIRATION.md:94`, and the four review modules' own docstrings.
Enumerated here so they are swept rather than rediscovered, in the same
spirit as the twelve places the roadmap counted for the
never-automatic wording.

`mkdocs.yml` needs an entry only if this aid gets a dedicated doc page
as `citation_provenance` did. It does not: `docs/CLI.md` carries it,
like `coverage` and `verbatim`.

## Tests

Failing first, per the TDD rule, and to the 100% bar:

1. Each of the five genres resolves its unit from `scope.md`.
2. A draft with no dossier falls back to `--unit`, and the report names
   the fallback as its source.
3. A paragraph citing inside a table, a list item, and a footnote --
   the block cases `citation_provenance._claim_spans` already handles.
4. A declared single-source unit, in Markdown and in LaTeX, lands in the
   declared count and not the undeclared one.
5. A marker naming a citekey without an `@` does not itself register as
   a citation -- including a marker inside a fenced code block, which
   must not be read as a declaration at all.
6. A marker separated from its unit by a blank line is **not** treated
   as that unit's declaration, and the report says why rather than
   silently ignoring it.
7. A **stale declaration** -- a marker on a unit that cites two keys --
   leaves the unit counted as multi-source. The marker is a statement
   about intent; the citekeys are the measurement, and the measurement
   wins.
8. A unit's `finding_id` is unchanged by adding, editing or removing its
   marker.
9. A **block-structured section** -- three paragraphs on A, then three
   on B -- reports its spread as 2 and its longest single-key run as 3.
   The spread number alone must not make it look like a fused section.
   Its interleaved counterpart, same citekeys, reports a run of 1.
10. A run is broken by a zero-citation paragraph and by a multi-source
    paragraph, and is counted per section, never across a heading.
11. A zero-citation unit is counted and is not a finding.
12. Byte-identical output over two runs, `.md` and `--json`.
13. Exit 0 on a draft where every unit is single-source and undeclared.

## Done when

A survey drafted after this lands has body paragraphs that close on
several citekeys at once; a textbook chapter has sections that span
sources *and interleave them*, rather than sections that meet the rule
by running one paper out before starting the next; a tutorial's report
says "unit: document" and reads as a fact rather than a failure; and
every single-source unit in any of them is either declared or visible in
a count someone reads.
