# Critique against the evidence packet: the repair loop

Read this at the critique step, once you have the prioritised list
that step asks for. The step that sent you here says which path
`<draft>` stands for and which tool makes each edit. Paths here are
from the project root. What decides whether an edit is kept is the
external count below, never your opinion of the edit.

## A sub-theme the corpus could not answer

That is a fourth kind of gap, and reading it costs one command. Before
listing anything, where the dossier has an `outline.md`:

```bash
python -m chitragupta.draft dossier status <draft>
```

Its `Outline:` block reports each declared query as run, `no evidence`
(it ran and returned nothing) or `not run` (nobody issued it). Every
sentence resting on a `no evidence` sub-theme is ungrounded, and the
repair is to **cut the sentence, never to re-point it at whichever
citekey ranked nearest**. Against a closed, human-curated bibliography
an empty result set is information: it means the claim cannot be
grounded here. A re-pointed citation is invisible to the gate, because
that citekey is real. Cut inside the same accept-or-revert cycle as
every other repair below -- the 90% floor is what stops a cut becoming
a rewrite that deletes its way to a lower count. Where there is no
`outline.md` there is no declared list, so skip this and the closing
report below rather than inventing either.

## The baseline

Take it before touching anything:

```bash
python -m chitragupta.draft dossier sections <draft> --citekeys --write
python -m chitragupta.review verbatim scan <draft> --write --json
python -m chitragupta.draft style <draft> --json
```

The first two are the same baseline discipline the agenda repair loop
uses (uncapped, never `--limit`): they file
`content/review/<topic>/<stem>.verbatim.json`, the file every edit below
is rechecked against. The third's finding count -- not the file, `style`
never writes one -- is the number you compare after each edit; note it
down. Take all three fresh now rather than reusing anything on disk from
an earlier run. If the scan's `tiers_not_run` is not empty, quote the
reason: **genuine restatement is only detected where the embedding tier
can run**, so the recheck below only ever compares what the tiers that
did run can see. `style` reports only what WRITING-STANDARDS.md §9 marks
decidable, and this step -- like every other -- is told to fix none of
them: its count is a proxy for whether the edit introduced a new defect,
not a work list to act on.

## The repairs

Work the top of your list, **at most three items, one edit each, no
retry and no second critique pass** once the three are done or the list
runs out first. For each:

1. Keep the pre-edit text of the section you are about to touch.
2. Make the edit inside that section only, with the tool the step names.
   Preserve the citekey; reword the claim to match what `claim:` says,
   or drop a sentence that overstates it. Never add a claim
   `evidence.md` does not already record, and never touch a `quote:`
   span -- a quotation is captured when the evidence is judged, never
   rewritten here.
3. Check, all three required:

   ```bash
   python -m chitragupta.draft gate <draft>
   python -m chitragupta.review verbatim recheck <draft> \
       --baseline content/review/<topic>/<stem>.verbatim.json --json
   python -m chitragupta.draft style <draft> --json
   ```

   Accept the edit only if: the gate exits `OK`; the recheck's
   `objective_delta` is not positive; and the fresh `style` finding
   count -- read only as a number, since `style` reports what §9 marks
   decidable and this step is told to fix none of them -- is no higher
   than the count noted before editing. Also check the edited section
   did not fall under 90% of its own pre-edit length -- a secondary
   sanity floor against a rewrite that deletes its way to a lower
   count, never itself a reason to accept one that the three checks
   above already failed.
4. If any check fails, restore the text you kept in step 1 and move to
   the next item. Do not retry the same item.
5. Log the attempt in the dossier's `revisions.md`: which gap, what you
   changed, and the outcome -- accepted or reverted. Never write any of
   this to `rejected.md`.

## Then report exhaustion, and carry on

**Say whether the declared queries are exhausted**, from the `Outline:`
block you read before starting -- no second call. The declared list is
exhausted when every query ran and none was reported `no evidence` or
`not run`. Say so in one sentence, naming the ones that are not. This is
a **real termination condition**, available because the corpus is
closed and the declared list is finite, where an open-web tool has only
a fixed round count. It bounds nothing above: the three-repair cap
stands, and an unexhausted list never withholds a draft.

If nothing on the list clears the bar, or the list was empty, continue
to the gate exactly as if this step had not run -- the gate remains the
only thing that blocks a draft, and this step is never a condition of
presenting.
