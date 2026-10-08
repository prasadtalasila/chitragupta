# Re-grounding: R1 to R5

Read this once the skill has sent you here from a `dossier status --all`
report or a sync. Steps 5, 6 and 7 are the skill's own loop. Paths here
are from the project root.

## R1. Read the report as data

```bash
python -m chitragupta.draft dossier status content/drafts/<path> --json
```

Or take the payload from a `--all --json` sweep the user already has. The
envelope is always `{"dossiers": [...]}`, so a single draft comes back as
a one-element list: read `.dossiers[0]`, not a bare object.

## R2. Branch on the payload, never on the exit code

This command exits 0 almost unconditionally -- that is deliberate, so the
caller reads the contents rather than a status. Two cases to check before
anything else:

- **`corpus_available` is `false`.** The ledger could not be read, so
  every finding list is empty because the check never ran, not because
  there is nothing to find. Say what you checked, point the user at
  `python -m chitragupta.corpus sync`, and stop. Do not report the draft as current.
- **The dossier does not exist.** `--json` returns an almost-empty entry
  and still exits 0. Go to "When there is no dossier", bootstrap, and
  come back.

## R3. Act on the three lists -- they are not the same kind of thing

Flattening them into one list of "papers to look at" is the failure mode
this section exists to prevent.

**`missing` is a defect.** The draft stands on a paper the corpus no
longer has; `citation_gate` already disagrees with the draft. Always
actioned, whatever else the revision is about. Each entry maps a citekey
to the sections citing it, and `python -m chitragupta.draft dossier sections
content/drafts/<path>` turns those into line ranges, so the edit stays as
scoped as any other. Look for the replacement in this order, and stop at
the first that supports the claim:

1. `evidence.md` -- another paper you already kept may support it, at no
   retrieval cost at all.
2. The report's own `candidates` -- a paper that arrived matching the
   same query that once produced the broken citation is the likeliest
   replacement there is.
3. A fresh search -- here it *is* right, unlike the candidate path,
   because a claim left unsupported is genuinely new ground:

   ```bash
   python -m chitragupta.draft retrieve search "<the claim>" --k 15 --collection "<from scope.md>" --log content/drafts/<path>
   ```

If none of the three supports it, **remove the claim** and say so. Not a
reworded sentence that keeps the assertion and quietly drops the
citation. Never leave the citekey in place, and never replace it with a
key you have not seen in the ledger.

**`candidates` are a decision, not a defect.** New papers that this
dossier's own recorded queries reach. Pursue only the ones whose
`queries` touch the sub-theme actually in play; the rest are reported to
the user and left in the report for the next revision to weigh. Do not
work through the list.

For the ones you do pursue, go straight to the passage. The report
already carries the citekey, the title and the query that surfaced it, so
re-running `search` for that query pays for fifteen snippets to be handed
back the same fifteen citekeys:

```bash
python -m chitragupta.draft retrieve evidence "<the query from the report>" \
    --citekey <candidate> --log content/drafts/<path>
```

What the report lacks is text to judge on, and that is what `evidence` is
for. Keep `python -m chitragupta.draft retrieve search "<query>" --k 15 --log <draft>`
for the case where the revision opens ground the dossier never covered --
a query not already in `retrieval.md`, which by definition could not have
produced a candidate.

**`reconsider` is not re-judged.** These are papers the draft already
read and turned down, which its queries still reach. `rejected.md` has
already been subtracted from `candidates`; these are carried separately
*with the recorded reason* so you can weigh the reason without paying to
re-judge the paper. Report citekey, title and reason. Re-open one only
when the recorded reason no longer holds -- typically a scope change the
user agreed to in step 2. Re-judging these by default is precisely the
cost `rejected.md` exists to prevent (`docs/REJECTION.md`).

## R4. Edit, write back, and re-stamp

Step 5 unchanged. Step 6 unchanged except for two of its bullets, which
were written for a revision someone asked for:

- **`steering.md` -- usually nothing.** A re-grounding pass has no
  instruction to record; the corpus moved, the user did not steer.
  Append only if they actually said something here. Inventing a steering
  entry to fill the file is the same failure as inventing an evidence
  one.
- **`scope.md` -- the fingerprint line only.** The rule that the scope
  statement changes only by agreement is untouched; the corpus line
  below is bookkeeping, and is the one thing this mode always writes.

Then two things specific to this mode.

**Re-stamp the corpus fingerprint** in `scope.md`, after the gate passes,
from the report's `current` field -- it is the record that this draft was
re-grounded against that corpus:

```text
- corpus: 503 citekeys, digest `f6e5d4c3b2a1`
```

Rewrite the line; do not reshape it. Anything that no longer matches the
recorded form makes `recorded_corpus()` return nothing, and the dossier
silently downgrades to "records no corpus fingerprint" instead of
erroring.

**Append a `revisions.md` entry** naming this as a re-grounding: what was
swapped, what was dropped, what was added, and -- with the same weight --
which candidates were reported and *not* pursued. The Guardrails rule
about reporting what you didn't do binds hardest here, because the user
did not ask for this revision and cannot infer its edges.

## R5. The gate is the exit, not the report

Finish with step 7 and change nothing about it. `missing` is computed
from the dossier's own `evidence.md` and `sections.md`, not from the
draft body, so a citekey the draft cites that was never recorded in the
dossier will not appear in the report at all. `python -m
chitragupta.draft gate` is the check that reads the draft, and it is what
decides the draft is presentable. A clean drift report never does.

The loop's two riders still apply, and neither is a gate. A re-grounding
pass rewrites sentences around a swapped citation, which is new prose
whatever prompted it.

Expect the draft to keep showing candidates in the next sweep, and say
so. A query returns fifteen hits and a revision accepts one or two;
"still has candidates" is the normal state of a healthy draft. What
re-grounding promises is that the *missing* list is empty. Do not clear
the candidate list by writing unpursued papers into `rejected.md` -- a
rejection recorded from a title alone is a judgment you did not make, and
`rejected.md` is trusted permanently by every revision after this one.
