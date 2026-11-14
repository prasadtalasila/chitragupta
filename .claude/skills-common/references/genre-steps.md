# Genre steps: what every drafting genre does the same way

Read a section of this file when the step that sent you here cites it;
each section opens with when it applies. Paths here are from the project
root. The commands themselves are in the step, never here: this file
holds what they are for and how to judge what they return.

## 1. The corpus is read-only

Read this once, before the first retrieval of a run.

What the run reads, and never regenerates:

- `content/ledger.sqlite`: per-citekey status, written by the corpus
  sync.
- `papers/bibliography.bib` (gitignored, one per host): the source of
  truth for citekeys and their metadata. The sync reads it; nothing
  regenerates it.
- `content/parsed/<citekey>.txt`: the text extracted from each PDF.
- `chitragupta/retrieval.py`, behind the retrieval commands the step
  names. A search returns a citekey, a title, a score and a
  500-character snippet per candidate; the evidence command reads more
  of one document when a snippet is not enough to judge it.

Every retrieval call logs to the draft, which records the call's size in
the dossier's `retrieval.md`. That is what makes the cost of a run
measurable instead of estimated, so no call goes unlogged.

The ranker is keyword overlap, not embeddings, unless
`chitragupta/enrich/embed_index.py` has been built for this corpus. A
high score means the query's words are in the document, not that the
document supports your claim. That is why every candidate is judged
before it counts (§5).

**Read-only means read-only.** The corpus sync and every
`chitragupta/enrich/*` build stage belong to the corpus layer: both take
the pipeline's write lock, and either can run for tens of minutes (a
first full-corpus parse, or building the embedding index). They are the
user's to run, not yours. If a semantic index would help and none
exists, say so and use the keyword search; do not build one.

**An empty ledger stops the run.** If the ledger reports no items, or
none with status `parsed`, say so plainly, naming what you checked and
what you found, and stop there. Do not draft around it, do not sync, and
do not cite.

## 2. What the dossier is for

Read this before opening the dossier, and again whenever you wonder
whether something is worth recording.

The draft is only half of what a run produces. The other half is the
judgment behind it: the reader, the scope, the glossary, which
candidates were kept and **which were turned down and why**. It belongs
on disk, not in the conversation. Without it the next revision has to
re-retrieve and re-score the whole topic to change one paragraph.

`chitragupta/dossier/` owns that state, in Markdown, one directory per
draft at `content/dossiers/<the draft's path, minus its suffix>/`.
Create it before you search and fill it in as you go, not at the end,
when what you rejected has already fallen out of your context.
`docs/DRAFT-ITERATION.md` is the full design.

**The section map is derived, never written by hand.** `sections.md`
joins each heading's line range to the citekeys cited inside it, so a
later revision can tell which section owns a citation without reading
the draft. It is regenerated from the draft, so a problem it reports is
fixed in the draft, not in the table.

**Steering belongs there too.** When the user shapes a draft in chat
("don't lead with tooling", "shorter", "drop the adoption angle"), the
instruction is invisible in the prose and has nowhere else to live. A
revision that does not know about it will undo it, so it goes into
`steering.md`, dated.

## 3. Opening the dossier

Read this before creating the dossier: it covers everything the creation
step decides, so it can be followed on its own.

**Name the reader and the scope first.** Settle who the draft is for and
what it will and won't cover, and write the scope statement into the
draft's opening, including what is deliberately excluded, so a reader
can tell an omission from an oversight (`docs/WRITING-STANDARDS.md` §1
and §3).

**Settle the slug with the user before creating anything.** It is a
path under `content/drafts/`, and it may contain directories. A draft
for the `books/software-engineering` book is
`content/drafts/books/software-engineering/<genre>.<ext>`; a topic that
will hold more than one genre wants `content/drafts/<topic>/<genre>.<ext>`,
so they sit together. A flat `content/drafts/<slug>.<ext>` is the
default when neither applies. Ask rather than guess: the dossier
(`content/dossiers/<slug>/`) and every render
(`content/rendered/<the draft's own directory>/`) mirror whatever you
pick, so moving the draft later means moving both. A draft that may
gain a figure wants a topic directory from the start, because figures
under a flat draft land in `content/drafts/figures/`, shared with every
other flat draft.

**Fill in `scope.md` while you decide it**: **Reader**, **Covers**,
**Does not cover** and **Glossary**.

**Settle the dialect in the same breath** and write it to `scope.md`'s
`language:` line, which ships unset. A draft for an IEEE submission is
`en-US`, and one for a European funder is usually `en-GB`. A draft whose
dialect nobody chose silently gets the model's own
(`docs/WRITING-STANDARDS.md` §8).

**Read the acronym vocabulary**: the vendored floor at
`assets/style/acronyms.toml`, plus the user's own file if
`[style].acronyms` in `config.toml` points at one. Use its recorded
expansion at an acronym's first use rather than inventing one.

**Creating the dossier stamps the corpus fingerprint**, which is what
lets a later revision tell whether the ledger has moved since.

## 4. Following an `outline.md`

Read this when the dossier has an `outline.md` and it passes its check.

A human writes `outline.md` by hand, when the dossier is created or
later. Per section it holds a heading, a `brief:` and/or a `claim:`
block, and optional declared `queries:`.

**Run each section's declared queries verbatim**, in place of breaking
the topic into sub-themes yourself, logged with origin `declared`. Score
and record what they return exactly as §5 describes. A section whose
declared queries come up thin still gets §6's reformulation, logged with
origin `extended` instead. That distinction is what lets the dossier's
status report answer "did this draft follow its outline?" from
`retrieval.md` afterwards, so log it honestly rather than as `declared`.

**A `claim:` section is content to ground, not steer from.** The human's
prose there is rewritten, not preserved: find a citekey supporting each
assertion (the section's declared queries first, then the assertion's
own wording if those don't cover it, logged `extended`), write the
grounded sentence into the draft with its citation, and **drop, don't
ship, any sentence you can't ground**. Name what you dropped in your
final summary to the user. The uncited-claims review is the backstop
that catches anything that slips through regardless.

In a genre where citing is optional, a `claim:` block is a steer: write
toward it, and cite only where the evidence supports a sentence.

## 5. Judging a candidate and recording it

Read this before you record your first `evidence.md` block.

**Score every candidate yourself before it counts as evidence.** Read
the full snippet (500 characters, sized so you have enough to judge and
not just a title) and decide: does this actually support a claim about
the sub-theme, or did it only share vocabulary with the query? Keep only
the ones that pass. This is the discipline PaperQA2 calls "gather
evidence" (retrieve, then judge relevance, *then* write); the difference
here is that you judge inline rather than through a second API call.

**Read more of a document only to be more careful about something you
are about to cite**, never as a routine second pass over everything.
`docs/REJECTION.md` explains why the reverse, a cheap screen used to
reject faster, was tried and withdrawn: a wrong rejection is invisible,
unrecoverable, and then entrenched in `rejected.md`, which later
revisions are told to trust.

**Record both outcomes before you draft prose**, while the passages are
still in front of you:

- What survives goes into `evidence.md`: one ``## `citekey` `` block
  with a `relevance:` line (why it supports the claim), a `claim:` line
  (what the source establishes, in your own words) and, only when a
  quotation is genuinely warranted, a `quote:` line (the verbatim span).
  `claim:` is the only field you may draft prose from later; `quote:` is
  usable in the draft solely inside quotation marks with an attribution.
  Write `claim:` from what you now understand the source to say, not by
  lightly editing the passage still on screen: the two produce different
  sentences, and only the first is yours.
- What doesn't goes into `rejected.md`: one table row per candidate,
  with the citekey, the query that surfaced it, and a few words on why
  it was turned down ("shares vocabulary only", "wrong domain",
  "superseded by X").

The rejected list is the more valuable of the two and the easier to
skip. It is what stops the next revision retrieving and re-judging the
same twelve papers you just turned down, the single most expensive piece
of repeated work in this pipeline.

**The evidence self-check gives two kinds of warning.** `N blocks under
one citekey` means `evidence.md` has more than one block for that paper
and only the first is ever read: merge them. A reword warning, a
`claim:` that reads like its own `quote:` with the words moved, means
re-read whether that claim is really your own reading of the source. It
is not a cue to keep rewording until the warning stops.

## 6. Thin results and disagreement

Read this when a sub-theme comes back with little or nothing, or when
two kept sources disagree.

**A single query wording is not the ceiling.** If scoring leaves you
with little or nothing for a sub-theme, try synonyms, broader or
narrower terms, or an adjacent concept, and search again. Do this a few
times before concluding that thin coverage is real rather than a wording
problem. Only after genuine attempts report a sub-theme as thin, and
then say so explicitly, in the draft and to the user, rather than
padding it with uncited claims.

**Check for disagreement across sources before writing.** If two kept
pieces of evidence conflict on a claim, don't silently pick one side:
note the disagreement in the draft, saying which source says what.
Silently resolving a real contradiction is a worse failure than leaving
it visible.

## 7. Stamping and handing over

Read this at the last step, before you stamp the draft: it covers the
stamp and the hand-over, so it can be followed on its own.

**Stamp only when the text is final.** The stamp records the draft's own
fingerprint, the baseline a later hand edit is compared against when the
dossier's status is read. Nothing edits the draft's text after it, so it
is the last thing before presenting.

**Then present**: the draft, a one-paragraph summary of thin-coverage
areas and any unresolved cross-source disagreement, and the render
outcome (the paths of the files that rendered, or the warning a render
printed).

**Hand it over.** Tell the user where the dossier is, and that a change
to this draft goes through the revision skill the step names, not
another run of the genre skill: a revision reads the dossier, where a
fresh run would re-retrieve and re-judge everything and discard the
rejected list. `content/drafts/` and `content/dossiers/` are gitignored,
so the export the step names is how a draft and its working state get
backed up.
