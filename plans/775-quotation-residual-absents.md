# 🔍 Normalise away the false absents in `misquoted`, then decide acceptance (#775)

Status: **built.** Written 2026-09-17, implementing issue #775. PR number
to be recorded here when it lands.

Issue #775 asked one question in two halves, in a deliberate order:
narrow the `misquoted` class until an `absent` verdict means one thing,
**then** decide whether such a finding may ever be accepted (suppressed
from the review agenda). This file records what the measurement found,
the arm that shipped, the arm that was declined, and the answer to the
acceptance half -- which is **no**.

## 🧭 Why the order was the point

An `absent` verdict from `chitragupta/review/_quotation_match.py` is
either a correct quotation the matcher could not align, or a quotation
that is not in the source. The second is the one failure
[SOUL.md](../SOUL.md) exists to prevent. Granting acceptance over a class
containing both lets one keystroke bury a fabricated quotation
permanently -- so the class had to be narrowed before the question could
honestly be asked.

The discriminator a reader reaches for first is closed off.
`Checked.near_miss_score` is already computed and already carried in the
agenda item's `detail`, and an "accept below *X*" rule would sort the
class in one line. R3 bars a continuous score from being the thing
optimised, and `_quotation_match.py` says so in the module that owns the
number. So the work had to be **structural**: name a thing that is
legitimately not verbatim, remove it from both sides, and keep the
comparison exact.

## 📊 The corpus, and why it is 206 spans and not 189

[plans/c3-quotation-integrity.md](c3-quotation-integrity.md) measured 189
spans extracted from the `content/backup/chitragupta-6.20.7/` dossiers.
**That backup no longer exists on this host.** Rather than quote a figure
that cannot be rebuilt, #775 re-ran c3's own extraction rule -- verbatim,
including its crudeness -- over the backup that is here:

| | c3's measurement | #775's re-run |
| --- | --- | --- |
| Source | `content/backup/chitragupta-6.20.7/` | `content/backup/20260901-content/` |
| `evidence.md` files carrying spans | 14 | 19 |
| Spans / distinct citekeys | 189 / 87 | 206 / 93 |
| Confirmed in the cited source | 156 (82.5%) | 166 (80.6%) |
| `absent` | 33 (17.5%) | 40 (19.4%) |
| `unverifiable` | 0 | 0 |

The two found-rates sitting within two points of each other is the
evidence that the extractor reproduces c3's rule faithfully and the
difference is the corpus, not the method.

**c3's caveat carries over unchanged and matters more than the delta.**
The extraction attributes each span to the nearest preceding citekey in
its block, which is a heuristic. So 40/206 is an **upper bound on the
absent rate, not C3's false-positive rate** -- and the residual breakdown
below shows several spans that are plainly mis-attributions rather than
findings.

**Rebuilding it**, in the same three steps c3 published, because a
measurement that cannot be re-run is a claim rather than a result:

1. **Extract.** For each `evidence.md` under the backup's `dossiers/`,
   join hard wraps within each bullet or paragraph, find citekeys as
   `` `([a-z][a-z0-9_.-]*_[a-z0-9-]+_\d{4}[a-z0-9-]*)` ``, find spans as
   `["“]([^"“”]{20,600})["”]`, and attribute each span to the citekey
   matching nearest before it in the same block.
2. **Load sources.** `content/docling/<citekey>.passages.json`, else
   `content/parsed/<citekey>.passages.json`, else `<citekey>.txt` split on
   form feeds -- `passages.source_passages`'s own ladder. All 206
   resolved to rung 1 or 2, so `unverifiable` fired zero times again.
3. **Run `_quotation_match.locate`** over the quotable passages, and
   count the tier it returns.

Done with a throwaway script rather than a `bench/` entry, the same
choice c3 made and for the same reason: the recipe above is the durable
artefact, and a script that needs a vanished backup is not.

## ✅ The arm that shipped: an elision at either end of the quote

`fragments` splits a quote on `...`, `…` and any `[...]` group, and
`locate` then required **two** surviving fragments. An elision at the
*start* or *end* of a quote leaves exactly one, so `locate` returned
`None` before the elided tiers ever ran -- and `fragments`' own docstring
asserted the opposite, that "fewer than two means there was nothing to
elide". It is a bug in a stated invariant rather than a new heuristic,
which is what lets it satisfy the issue's "exact matching only" bar.

The two measured cases, both correct quotations reported `absent`:

```text
quote:  "For data-driven models, the topic is [unresolved]."
source: "...for data-driven models the topic is still being debated..."
         (viceconti_position_2024 -- 128 flattened characters, verbatim)

quote:  "...developed for a specific purpose which generally [changes]."
source: "...developed for a specific purpose which generally entails the
         monitoring, analysis, simulation or optimization..."
         (mertens_continuous_2024 -- 207 flattened characters, verbatim)
```

In both, the drafter substituted their own word in brackets at the end of
the quotation -- which is precisely what the elision contract already
promises to cut out and align around. Written the other way up,
`"... CN is the connection"`, it is the leading fragment that is empty.

**The guard keeps its other half.** One fragment is enough *only when the
quote carried an elision marker*. A quote with no marker at all also
produces one fragment -- the whole quote -- and it must stay `absent`:
those characters already failed the exact tiers above, and rerunning them
would relabel the same miss as `elided`.

**Measured: 40 residual absents to 38, 2 recovered, 0 lost.**

**Where it is least evidenced**, published the way `SLIVER` is rather
than guarded by a second constant R3 would bar tuning: both recovered
survivors were long (128 and 207 flattened characters). The corpus holds
no quote whose lone survivor sits near `SLIVER = 8`, so an 8-character
fragment carrying a whole quote's verdict is **untested rather than shown
safe**. If a later corpus produces one, this is the sentence to revisit.

## ❌ The arm that was declined: the abbreviation gloss

The obvious next candidate, and the one a later reader will reach for, so
it is recorded rather than dropped.

Academic prose glosses an abbreviation on first use -- *"the users of a
Digital Twin (DT) to gain the most value"* -- and a drafter quoting that
sentence may drop the `(DT)`. Flattened, the source carries a bare `dt`
inside the span and a correct quotation reads as fabricated. That is
structurally the same shape as the inline `[30]` reference marker that
`strip_markers` already handles, so: strip a parenthesised capitalised
abbreviation of 2-6 letters from the *source* before flattening.

**It loses more than it recovers.** Over the same 206 spans:

| Arm | Confirmed | Absent | Recovered | Lost |
| --- | --- | --- | --- | --- |
| Shipped matcher | 166 | 40 | -- | -- |
| + elision at either end | **168** | **38** | 2 | **0** |
| + abbreviation gloss | 155 | 51 | 1 | 12 |
| Both | 157 | 49 | 3 | 12 |

The reason is the direction of the human behaviour, and the measurement
is what showed it: a drafter quoting a glossed sentence **usually keeps
the gloss**. Twelve quotations in this corpus carry `(DT)`, `(ODE)`,
`(DES)`, `(OOD)` and their kind verbatim, and stripping the source side
breaks every one of them.

Declined, not deferred. The lesson generalises past this arm: a
normalisation applied to one side only is safe when the removed text is
something a human *never* types (a line-break hyphen) and unsafe when it
is something a human *may* type. `[30]` is the first kind; `(DT)` is the
second.

## 🧱 What the 38 residuals actually are

The issue's first success criterion, and the thing that makes the
acceptance answer decidable. Classified structurally -- by how much of
the flattened quote can be found as a prefix anywhere in the source --
rather than by a similarity score:

| Class | Count | What it is |
| --- | --- | --- |
| `short-phrase` (under 8 words) | 15 | The extraction rule collecting the book's own scare-quoted phrases -- `"explain it to a sponsor"`, `"which do you believe?"`, `"returns in Chapter 13"`. Never a `quote:` field. Not findings, and not the aid's fault |
| `nowhere-in-source` (under 20 characters match) | 18 | Essentially none of the quote is in the paper. At this extraction rule's fidelity these are mostly mis-attributions -- `worden_artificial_2023` matches 7 of 229 characters, `gomes_sensing_2024` 5 of 71 |
| `diverges-midway` | 5 | A real, long prefix matches and then the text differs. **This is the class C3 exists for** |

The five in the last row are worth naming, since they are the ones a
human should be reading:

- `ali_modeling_2024` -- 81 of 107 characters, then the source reads
  `...feasible40and...`: an unbracketed superscript reference marker the
  Docling parse flattened into the sentence. A *parse* artefact, not a
  drafting one, and not reachable without stripping bare digits from the
  source, which would eat every number a quotation legitimately carries.
- `rasheed_digital_2020` (twice) -- the source reads `highdelity` where
  the quote reads `highfidelity`: the parse dropped an `fi` ligature
  outright. Recovering it needs fuzzy matching, which R3 bars.
- `stadtmann_diagnostic_2024` -- the drafter elided
  `"the asset is monitored through measurements"` **without marking it**,
  and shortened `"a fault diagnosis"` to `"diagnosis"`.
- `bohlbro_visualisation_2024` -- the dropped `(DT)` gloss above.

So after the fourth normalisation, three of the five remaining real
divergences are defects in the *parse* rather than in the draft, and two
are genuine unmarked edits by the drafter. Neither group is a
fabrication, on this corpus -- but neither is distinguishable from one by
any rule available here, which is the finding that decides the second
half.

## ⚖️ The acceptance answer: no

Recorded in full in [docs/AUTO-IMPROVEMENT.md](../docs/AUTO-IMPROVEMENT.md),
which is the document that owns the acceptable-class list, and summarised
here because this is where the evidence is:

1. **The conflation is reduced, not removed.** 5 of the 38 residuals are
   a real prefix followed by a real divergence, and nothing here
   separates an unmarked drafter edit from a fabrication. A class still
   containing those is not a class to let one keystroke silence.
2. **The identity asymmetry is untouched.** `misquoted_items` keys on the
   quote text from `evidence.md`, so a finding that becomes newly true
   under a re-parse, a replaced PDF or a `corpus sync` leaves the id
   byte-identical and the acceptance holding. Fixing it means folding the
   parsed source's fingerprint into the identity -- a new mechanism, which
   #767 explicitly declined to add.
3. **It buys nothing measurable today.** No dossier in this corpus uses
   the `quote:`/`claim:`/`support:` contract, so the class's universe is
   empty on every real draft. The issue names closing this half unmerged
   as a legitimate outcome, and the measurement gives no reason to
   overrule that.

Success criterion 5 -- *"if acceptance is granted, the item identity
covers the parsed source"* -- is therefore **moot rather than skipped**,
and is recorded that way instead of left ambiguous.

## 📝 Record the outcome

Per [plans/README.md](README.md), replace the status line with the PR
that closed it when this merges.
