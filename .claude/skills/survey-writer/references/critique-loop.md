# The pre-gate critique loop

Read this at the critique step, before listing anything. The step that
sent you here says which path `<draft>` stands for and which tool makes
each edit. Paths here are from the project root. What decides whether
an edit is kept is the external count below, never your opinion of the
edit. The step that sent you is not done until steps 1 to 6 below have
run, and this loop is never a condition of presenting.

1. **Read what the corpus could not answer.** A sub-theme the corpus
   could not answer is a fourth kind of gap, and reading it costs one
   command. Before listing anything, where the dossier has an
   `outline.md`:

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
   every other repair in step 4 -- the 90% floor is what stops a cut
   becoming a rewrite that deletes its way to a lower count. Where there
   is no `outline.md` there is no declared list, so skip this and the
   report in step 5 rather than inventing either.

   Done when: you have read the `Outline:` block, or found no `outline.md`.

2. **List the gaps.** Read the dossier's `evidence.md` -- the
   `claim:`/`quote:` blocks recorded when each source was judged --
   against the draft's own prose, section by section. List, in priority
   order, up to five places where the prose claims more than its
   `claim:` line supports, omits a kept `claim:` the draft never used,
   or drifts from the wording `claim:` actually recorded. This is one
   inline judgement call, not a subagent dispatch and not a
   deterministic check -- nothing in this pipeline scores this
   automatically.

   Done when: the list is written down, or you have found nothing to put on it.

3. **Take the baseline**, before touching anything:

   ```bash
   python -m chitragupta.draft dossier sections <draft> --citekeys --write
   python -m chitragupta.review verbatim scan <draft> --write --json
   python -m chitragupta.draft style <draft> --json
   ```

   The first two are the same baseline discipline the agenda repair loop
   uses (uncapped, never `--limit`): they file
   `content/review/<topic>/<stem>.verbatim.json`, the file every edit in
   step 4 is rechecked against. The third's finding count -- not the
   file, `style` never writes one -- is the number you compare after each
   edit; note it down. Take all three fresh now rather than reusing
   anything on disk from an earlier run. If the scan's `tiers_not_run` is
   not empty, quote the reason: **genuine restatement is only detected
   where the embedding tier can run**, so the recheck in step 4 only ever
   compares what the tiers that did run can see. `style` reports only
   what WRITING-STANDARDS.md §9 marks decidable, and this loop -- like
   every other step -- is told to fix none of them: its count is a proxy
   for whether the edit introduced a new defect, not a work list to act
   on.

   Done when: all three have run fresh and you have noted the `style` count.

4. **Repair at most three items.** Work the top of your list, **at most
   three items, one edit each, no retry and no second critique pass**
   once the three are done or the list runs out first. If the list is
   empty there is nothing to repair. For each item:

   1. Keep the pre-edit text of the section you are about to touch.
   2. Make the edit inside that section only, with the tool the step
      that sent you names. Preserve the citekey; reword the claim to
      match what `claim:` says, or drop a sentence that overstates it.
      Never add a claim `evidence.md` does not already record, and never
      touch a `quote:` span -- a quotation is captured when the evidence
      is judged, never rewritten here.
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
      decidable and this loop is told to fix none of them -- is no higher
      than the count noted in step 3. Also check the edited section did
      not fall under 90% of its own pre-edit length -- a secondary sanity
      floor against a rewrite that deletes its way to a lower count,
      never itself a reason to accept one that the three checks above
      already failed.
   4. If any check fails, restore the pre-edit text you kept and move to
      the next item. Do not retry the same item.
   5. Log the attempt in the dossier's `revisions.md`: which gap, what
      you changed, and the outcome -- accepted or reverted. Never write
      any of this to `rejected.md`.

   Done when: three items have been tried, or the list ran out, and every attempt is in `revisions.md`.

5. **Say whether the declared queries are exhausted**, from the
   `Outline:` block you read in step 1 -- no second call. The declared
   list is exhausted when every query ran and none was reported
   `no evidence` or `not run`. Say so in one sentence, naming the ones
   that are not. This is a **real termination condition**, available
   because the corpus is closed and the declared list is finite, where
   an open-web tool has only a fixed round count. It bounds nothing
   above: the three-repair cap stands, and an unexhausted list never
   withholds a draft.

   Done when: you have said that sentence, or step 1 found no `outline.md`.

6. **Return to the step that sent you**, with: the list from step 2;
   each repair, kept or reverted; the `tiers_not_run` reason, if the
   scan gave one; and the sentence from step 5. If nothing on the list
   cleared the bar, or the list was empty, say so: the caller continues
   to the gate exactly as if this loop had not run -- the gate remains
   the only thing that blocks a draft, and this loop is never a
   condition of presenting.

   Done when: you are back at the step that sent you, with that result.
