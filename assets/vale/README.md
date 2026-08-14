# The vendored prose style

What `python -m src.draft style` checks a draft against. Read by
`src/style_check.py`; not meant to be run with a bare `vale`, which would
enable all three dialect rules at once and report every draft as wrong in
two directions.

## Provenance

- **Vale**, <https://vale.sh>, [errata-ai/vale](https://github.com/errata-ai/vale),
  MIT. Pinned to **v3.9.1**; `scripts/install_full_pipeline.sh` fetches
  that exact release and verifies it against a recorded sha256.
- **The rules in `styles/chitragupta/` are original to this repository.**
  No third-party Vale style package is vendored, adapted or copied --
  not Google's, not Microsoft's, not `write-good`'s. Each rule implements
  a numbered section of [docs/WRITING-STANDARDS.md](../../docs/WRITING-STANDARDS.md)
  and names it in the finding's message, so a reader can always get from a
  finding back to the rule it came from.

Vendored rather than fetched with `vale sync`, for the reason
[assets/csl/README.md](../csl/README.md) gives about `ieee.csl`: a style
downloaded at run time is not the style that was reviewed, and a check
whose rules differ between two clones is not a check.

## The rules

| File | Implements | Level |
|---|---|---|
| `DefectMarkers.yml` | §2 -- obviously, simply, of course, clearly, easy | warning |
| `Just.yml` | §2 -- "just", separately | suggestion |
| `DialectGB.yml` | §8 -- en-US spellings in an en-GB draft | warning |
| `DialectUS.yml` | §8 -- en-GB spellings in an en-US draft | warning |
| `DialectIN.yml` | §8 -- Oxford `-ize` in an en-IN draft | warning |
| `Acronyms.yml` | §2 -- expansion at first use | suggestion |

`Just.yml` is separate from the other five markers because
[§9](../../docs/WRITING-STANDARDS.md) says it is: the adverb ("just add
the flag") is a defect marker and the adjective ("a just outcome") is not,
and no string match separates them. It is reported for a human eye and
never auto-fixed, which is what the lower level encodes.

**The dialect rules are mutually exclusive.** `src/style_check.py` enables
exactly one set per draft, chosen from the `language:` line in the draft's
dossier `scope.md`, using Vale's `--filter`. A draft with no recorded
dialect gets none of them and is told so.

`en-IN` is not an alias for `en-GB`. British English accepts both `-ise`
and Oxford `-ize`, so `DialectGB` cannot flag `-ize` without reporting
correct prose; Indian English prefers `-ise`, and `DialectIN` is that one
extra check layered on `DialectGB`.

## Word pairs deliberately left out

The dialect lists are tuned for precision, not coverage. A prose check
with false positives is one people learn to ignore, and this one cannot
compel anything -- it is advisory by design
([docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md), "Layer 4"), so its
only asset is being believed.

Omitted because **no string match can decide them**:

| Pair | Why |
|---|---|
| `licence` / `license` | part of speech: en-GB uses `licence` for the noun and `license` for the verb |
| `practice` / `practise` | same, in the same direction |
| `program` / `programme` | domain: en-GB uses `program` for software and `programme` for a broadcast or a plan |
| `meter` / `metre` | meaning: in en-GB a `meter` measures and a `metre` is a unit |
| `disc` / `disk` | domain, and inconsistent even within en-GB |

Omitted because they are **not instances of the suffix at all**, and a
naive `-ise`/`-ize` rule gets every one of them wrong:

- Always `-ise`, in every dialect: *advertise, advise, arise, chastise,
  comprise, compromise, despise, devise, disguise, enterprise, excise,
  exercise, franchise, improvise, incise, merchandise, revise, supervise,
  surmise, surprise, televise*.
- Always `-ize`: *capsize, prize, size*.
- `-yse` in en-GB even under Oxford spelling: *analyse, catalyse,
  paralyse* -- so they are listed explicitly rather than left to a suffix.
- The doubled `l` runs **both** ways: en-GB *travelled* but *fulfil*;
  en-US *traveled* but *fulfill*.

## Two things about the config that are not obvious

**`[formats] tex = md` is load-bearing.** LaTeX is not one of Vale's
native markup formats. Without that mapping a `.tex` fragment is scanned
as plain text, `BlockIgnores` is silently not applied, and every word
inside a `verbatim` block is reported. `thesis-chapter-writer` emits
`.tex`, so this line is what makes one of the eight drafting skills
checkable at all.

**`BlockIgnores` is split on commas**, so no regex in it may contain one.
`\n{2,}` has to be written `\n\n+`; the first form fails to parse and
Vale refuses to run.

## Re-fetching or upgrading Vale

```bash
VALE_VERSION=3.9.1
curl -sLo vale.tar.gz \
  "https://github.com/errata-ai/vale/releases/download/v${VALE_VERSION}/vale_${VALE_VERSION}_Linux_64-bit.tar.gz"
sha256sum vale.tar.gz   # must match the pin in scripts/install_full_pipeline.sh
```

On an upgrade, re-run the checks over the shipped drafts and compare
against `bench/results/` before moving the pin: a Vale release can change
how a format is scoped, and the exemptions above are the part most likely
to move under you.
