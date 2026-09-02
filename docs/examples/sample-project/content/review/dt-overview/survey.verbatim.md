# Verbatim scan: content/drafts/dt-overview/survey.md

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/survey.md`
- Command: `python -m chitragupta.review verbatim scan content/drafts/dt-overview/survey.md --min-run 8 --gap 1 --write`
- chitragupta 6.61.7
- Allowlist: none configured (`content/verbatim_allowlist.toml` not found)

## How to read this

Every run of at least `--min-run` words this draft shares with **any**
parsed source in the corpus, cited or not. Sharing wording is not by
itself misconduct -- a defined term, a standard's name and a correctly
quoted sentence all show up here -- so each finding is a place to look,
not a charge.

Two flags narrow the reading:

- **UNCITED SOURCE** -- the paragraph the run sits in does not cite the
  source it matched. That is the finding `overlap` structurally cannot
  make, and the one most worth reading first.
- **quoted** -- the run touches quote delimiters, so it is most likely
  a deliberate quotation. A run is usually wider than the quotation
  inside it -- it can open in the draft's own framing prose -- so this
  reads as overlap, not containment.

Each finding names its `tier`: **exact** is a verbatim run; **skip-gram**
is a tolerant stemmed-subsequence match that also catches a passage
with a handful of words substituted. A skip-gram finding's word count
is `matched words / span`: how many words the tier actually matched,
out of the raw width of text those matches span -- the two can differ
a lot, since a skip-gram window can stretch across stopwords and
opposite-family words that were not themselves matched.

**embedding** is the third tier: a sentence-level alignment between a
section of this draft and the sources its dossier records that section
as written from. It matches meaning rather than wording, so it is the
only tier that can see a genuine restatement -- and the only one whose
findings are not reproducible from the draft and the corpus alone,
since the vectors change with `[enrich].embedding_model`. Its `score`
is that alignment's strength, not a probability and not comparable to
anything the other two report; a passage a deterministic tier already
flagged is left to that tier rather than reported twice.

Findings below are grouped most-damning-first: long runs, then short
ones, then quoted runs -- but a quoted run only drops into the last
group when it also cites the source it matched. A quoted run from an
uncited source is still grouped by length (on matched words, not raw
span), not buried under `quoted`.

The allowlist bullet above names a per-host, gitignored file
(`content/verbatim_allowlist.toml`, see docs/PLAGIARISM.md) of
boilerplate this host's owner has decided never to flag -- a run is
only dropped when what's left after discounting the allowlisted text
would no longer clear `--min-run` on its own, so a real lift that
merely contains a defined term still shows up below.

**A clean run is not a clean bill of health.** This draft has been
checked against all three tiers, but they do not cover the same
ground: the two deterministic ones see wording, and the embedding
tier sees meaning only within each section's own recorded sources.
Reuse from a source a section's dossier does not record is outside
what any of the three can find by restatement alone. See
docs/PLAGIARISM.md.

## Findings

11 run(s), grouped most-damning-first.

### Short runs

#### 17 words, 8 matched -- `sample_dt_sync_2023` p.1 (tier=skip-gram)

> across nine simulated production cells event driven synchronisation reduced transmitted volume by 71 percent against one second

In context: threshold push and event driven flows across nine simulated production cells event driven synchronisation reduced transmitted volume by 71 percent against one second polling while holding worst case staleness...

#### 15 words, 6 matched -- `sample_dt_overview_2024` p.1 (tier=skip-gram)

> synthetic survey of forty deployments twenty eight systems described as twins were by this definition

In context: strictly keeps expectations honest in one synthetic survey of forty deployments twenty eight systems described as twins were by this definition shadows this survey groups the sample...

#### 13 words, 5 matched -- `sample_dt_factory_2022` p.1 (tier=skip-gram)

> showing supervisors agreeing with the twin in over ninety five percent of cases

In context: accuracy but a published override log showing supervisors agreeing with the twin in over ninety five percent of cases both failures it records were silent...

#### 13 words -- `sample_dt_overview_2024` p.1 (tier=exact)

> a digital model exchanges data with its physical counterpart only through manual steps

In context: here begins by fixing that vocabulary a digital model exchanges data with its physical counterpart only through manual steps a digital shadow adds an automatic...

#### 13 words -- `sample_dt_overview_2024` p.1 (tier=exact)

> synthetic survey of forty deployments twenty eight systems described as twins were by

In context: strictly keeps expectations honest in one synthetic survey of forty deployments twenty eight systems described as twins were by this definition shadows this survey groups...

#### 13 words -- `sample_dt_sync_2023` p.1 (tier=exact)

> a twin that knows it is stale must say so on every read

In context: much as technical marking staleness explicitly a twin that knows it is stale must say so on every read roughly halved operator mistrust incidents in...

#### 11 words -- `sample_std_interop_2021` p.1 (tier=exact)

> twin pilots rarely die of modelling problems they die of integration

In context: model 4 integrating with everything else twin pilots rarely die of modelling problems they die of integration interoperability requires agreement at three layers...

#### 10 words -- `sample_std_interop_2021` p.1 (tier=exact)

> integrated a new asset in a median of six days

In context: named owners sites that maintained one integrated a new asset in a median of six days against seven weeks where semantics were...

#### 9 words -- `sample_dt_sync_2023` p.1 (tier=exact)

> twin is only as trustworthy as its last synchronisation

In context: 2 keeping the twin true a twin is only as trustworthy as its last synchronisation comparing periodic pull threshold push and...

#### 9 words -- `sample_dt_sync_2023` p.1 (tier=exact)

> reduced transmitted volume by 71 percent against one second

In context: simulated production cells event driven synchronisation reduced transmitted volume by 71 percent against one second polling while holding worst case staleness...

#### 9 words -- `sample_dt_sync_2023` p.1 (tier=exact)

> both during slow thermal drift that never crossed its

In context: study s two worst staleness excursions both during slow thermal drift that never crossed its configured delta trust is behavioural as...
