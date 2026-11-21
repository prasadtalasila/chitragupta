# The vendored prose style

What `python -m chitragupta.draft style` checks a draft against. Read by
`chitragupta/style_check.py`; not meant to be run with a bare `vale`, which would
enable all three dialect rules at once and report every draft as wrong in
two directions.

## Provenance

- **Vale**, <https://vale.sh>, [vale-cli/vale](https://github.com/vale-cli/vale) (formerly errata-ai/vale),
  MIT. Pinned to **v3.26.0**; `scripts/install_full_pipeline.sh` fetches
  that exact release and verifies it against a recorded sha256.
- **The rules in `styles/chitragupta/` are original to this repository.**
  Each one implements a numbered section of
  [docs/WRITING-STANDARDS.md](../../docs/WRITING-STANDARDS.md) and names
  it in the finding's message, so a reader can always get from a finding
  back to the rule it came from. The phrase lists of the seven
  machine-prose rules (`BorrowedAuthority` to `Strawman` below) are
  drawn from [humanizer](https://github.com/blader/humanizer) v4.0.0,
  MIT, Copyright (c) 2025 Siqi Chen, whose licence is
  `styles/chitragupta/LICENSE-humanizer`; humanizer's patterns come from
  Wikipedia's "Signs of AI writing".
- **The rules in the other five directories are third-party**, copied
  byte-identical from pinned releases of four packages: see
  [Third-party rules](#third-party-rules) below.

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
| `Acronyms.yml` | §2 -- expansion at first use | suggestion |  <!-- see the exceptions note below -->
| `BorrowedAuthority.yml` | §4 -- an unnamed authority ("experts argue") | suggestion |
| `DeepSaying.yml` | §4 -- a saying that only sounds deep ("at its core") | suggestion |
| `Inflated.yml` | §4 -- importance claimed, not shown ("plays a pivotal role") | suggestion |
| `KnowledgeLimit.yml` | §7 -- a knowledge limit, then a guess ("based on available information") | suggestion |
| `PlainVerbs.yml` | §4 -- "serves as" or "stands as" where "is" will do | suggestion |
| `RunUp.yml` | §4 -- a run-up before the point ("here's the thing") | suggestion |
| `Strawman.yml` | §4 -- an answer to an objection nobody raised ("this is not to say") | suggestion |

`Just.yml` is separate from the other five markers because
[§9](../../docs/WRITING-STANDARDS.md) says it is: the adverb ("just add
the flag") is a defect marker and the adjective ("a just outcome") is not,
and no string match separates them. It is reported for a human eye and
never auto-fixed, which is what the lower level encodes.

The seven machine-prose rules are never auto-fixed either
(`chitragupta/style_rules.py`'s `_ALWAYS_REVIEW`): each repair is a
rewrite of the sentence around its claim. Their lists keep only phrases
with no ordinary use in a draft. humanizer's §14 ("associated with"),
§25 ("the table below compares") and most of §18 ("features",
"represents") are left out, because a survey or a textbook uses them
correctly all the time, and §13 has to give the table its reference
sentence. Phrases that `ai-tells.PromotionalPuffery` or
`Microsoft.Wordiness` already lists were removed from `Inflated.yml`,
so no two files carry the same phrase.

**The dialect rules are mutually exclusive.** `chitragupta/style_check.py` enables
exactly one set per draft, chosen from the `language:` line in the draft's
dossier `scope.md`, using Vale's `--filter`. A draft with no recorded
dialect gets none of them and is told so.

`en-IN` is not an alias for `en-GB`. British English accepts both `-ise`
and Oxford `-ize`, so `DialectGB` cannot flag `-ize` without reporting
correct prose; Indian English prefers `-ise`, and `DialectIN` is that one
extra check layered on `DialectGB`.

### The `Acronyms` exceptions, and why they are grouped

This rule was written against *drafts*, where the reader is an outsider
to the field and an unexpanded acronym is a real defect. Run over this
repository's own `docs/` it reported **536 findings across 96 tokens** --
which is why `.github/workflows/ci.yml` says a prose lint of this
repository "would fail today" and does not run one.

Almost none of them were the defect the rule is for. Two changes took it
to **91 findings across 23 tokens** without weakening it:

- **`vale.ini` ignores Markdown document names as tokens.** `AGENTS.md`,
  `CODE-STANDARDS.md` and `SOUL.md` are filenames, not prose, and were
  119 findings on their own. Ignored there rather than in this rule's
  exceptions, so a genuine `CODE` or `DESIGN` elsewhere still reports.
- **The exceptions list gained three labelled groups**: literal config
  and status values (`INFO`, `NEVER`, `FAILED`), bare document-name stems
  (`README`, `SKILL`), and the general computing vocabulary this
  document set's reader already knows (`CI`, `CLI`, `LLM`, `POSIX`).
  That last group is the same judgement `CPU`, `JSON` and `URL` were
  already exempt on.

What still reports is what the rule is for: domain jargon a reader would
plausibly look up -- `GROBID`, `TEI`, `CJK`, `UMAP`, `ONNX`, `SBERT`,
`IDF`, `TATR`, `CSL`, `BCP`, `CPS`, `DF`, `VLM` -- and the venue and
project names (`PAN`, `NAACL`, `OVAL`, `STORM`, `MOSS`, `BAAI`). Those 91
are a backlog to work through, not noise to suppress.

## Third-party rules

**32 rules from four packages**, each file copied byte-identical from the
release below and switched on by its own line in `vale.ini`, at
`suggestion` whatever level the package ships. A package is never named
in `BasedOnStyles`, so a file added beside these runs nowhere until it
gets a line. `VENDORED.sha256` records every file's hash, and
`tests/test_style_vendored.py` fails when a file, its `vale.ini` line,
its hash or its row in `chitragupta/style_vendored.py` disagree.

| Package | Release | Licence | Directory |
|---|---|---|---|
| [vale-cli/proselint](https://github.com/vale-cli/proselint) | v0.3.4 | BSD-3-Clause | `styles/proselint/` |
| [tbhb/vale-ai-tells](https://github.com/tbhb/vale-ai-tells) | v1.37.0 | MIT | `styles/ai-tells/` |
| [jdkato/journals](https://github.com/jdkato/journals) | v0.1.0 | MIT | `styles/Journals/`, and `styles/PLOS/` for one rule |
| [errata-ai/Microsoft](https://github.com/errata-ai/Microsoft) | v0.15.2 | MIT | `styles/Microsoft/` |

Each directory carries its package's `LICENSE` (and Journals' `NOTICE`).
proselint is pinned to v0.3.4, the release #1186 measured; v0.4.0
(2026-11-19) regenerates the rules from native proselint 0.16.0, whose
false positives #1186 recorded, and is a pin bump to measure first.

**Every finding is `review`**, so the review agenda never repairs one
unattended. Three rules were once meant to be the exception, and each
matches prose that is right as written: `ai-tells.SycophancyMarkers`
lists "absolutely" and "certainly" ("absolutely continuous", "almost
certainly holds"), `ai-tells.ClosingPleasantries` lists "If anything is
unclear", which a tutorial uses to point at a step, and
`proselint.Nonwords` swaps the noun "pettifogger" for a verb and offers
two meanings for some words.

**The section each rule implements is added to its message** by
`chitragupta/style_vendored.py` ("... (WRITING-STANDARDS.md §4)"), since
the packages' messages name none and the files are not edited.

| Rule | Catches | Section |
|---|---|---|
| `proselint.Cliches` | stock phrases ("a far cry") | §4 |
| `proselint.Hedging` | three fixed hedges ("so to speak"); a modal is never flagged | §4 |
| `proselint.Hyperbole` | repeated `!` or `?` | §4 |
| `proselint.Malapropisms` | a wrong word for the right one | §4 |
| `proselint.Needless` | a needless variant ("abolishment" for "abolition") | §4 |
| `proselint.Nonwords` | a non-word ("analyzation") | §4 |
| `proselint.Oxymorons` | "increasingly less" | §4 |
| `proselint.RASSyndrome` | a redundant acronym ("ATM machine") | §4 |
| `proselint.Skunked` | a disputed word ("decimate", "hopefully") | §4 |
| `proselint.Uncomparables` | a degree on an absolute ("very unique") | §4 |
| `proselint.Very` | "very" | §4 |
| `ai-tells.ClosingPleasantries` | a chatbot sign-off ("I hope this helps") | §4 |
| `ai-tells.ConclusionMarkers` | "In conclusion", "To sum up" | §4 |
| `ai-tells.ContrastiveFormulas` | "it's not just X; it's Y" | §4 |
| `ai-tells.NegatedPair` | "with no setup and no config" | §4 |
| `ai-tells.PromotionalPuffery` | sales language ("nestled in", "a testament to") | §4 |
| `ai-tells.PseudoCleft` | "What we found is that ..." | §4 |
| `ai-tells.StackedHedges` | "could potentially" | §4 |
| `ai-tells.SycophancyMarkers` | "Great question" | §4 |
| `Journals.EtAl` | "et. al" for "et al." | §4 |
| `Journals.Hype` | "novel", "groundbreaking" | §4 |
| `Journals.PValueCase` | `p` and `P` in one draft | §4 |
| `Journals.PValueZero` | "p = 0.000" for "p < 0.001" | §4 |
| `Journals.Placeholder` | `TODO`, `FIXME`, `[cite]`, `??` left in | §7 |
| `Journals.Prove` | "proves" of a result | §7 |
| `Journals.Significant` | "significant" with no statistic in the sentence | §7 |
| `Journals.UnitSpacing` | "5ms" for "5 ms" | §4 |
| `Journals.UnitSymbols` | "secs" for "s", "ml" for "mL" | §4 |
| `PLOS.PValues` | "p < 0.05" where the exact value belongs | §4 |
| `Microsoft.Plurals` | "file(s)" | §4 |
| `Microsoft.Uppercase` | several words in capitals; also fires on two acronyms side by side ("OPC UA"), which a person dismisses | §4 |
| `Microsoft.Wordiness` | "in order to" for "to" | §4 |

### Two rules, one phrase

The packages were written independently, and some phrases sit in two of
them: "at the end of the day" is both a cliché and a conclusion marker.
The files cannot be edited, so `chitragupta/style_vendored.py`'s
`SHADOWED_BY` drops the second finding when two rules report overlapping
words on one line. The winner is the more specific check, or the one
that says what to write instead.

| Dropped | When it overlaps | Example |
|---|---|---|
| `proselint.Cliches` | `ai-tells.ConclusionMarkers`, `Microsoft.Wordiness` | "at the end of the day", "this day and age" |
| `proselint.Needless` | `proselint.Nonwords` | "minimalize" |
| `proselint.Skunked` | `ai-tells.ClosingPleasantries` | "Hopefully this helps" |
| `proselint.Very` | `proselint.Uncomparables` | "very unique" |
| `Microsoft.Wordiness` | `ai-tells.ClosingPleasantries`, `ai-tells.ConclusionMarkers` | "let me know", "taking all of this into account" |
| `Journals.Prove` | `ai-tells.ClosingPleasantries` | "I hope this proves helpful" |
| `ai-tells.SycophancyMarkers` | `chitragupta.DefectMarkers`, `ai-tells.ClosingPleasantries` | "Of course", "happy to help" |
| `chitragupta.Strawman` | `ai-tells.ContrastiveFormulas` | "This isn't about speed; it's about trust" |

Overlaps that are two different checks keep both findings: an
unexpanded acronym inside a redundant one ("ATM machine"), a defect
marker inside a cliché ("easy as pie"), the case of a p-value and its
precision. `tests/test_style_vendored.py` feeds every phrase of every
rule file to Vale and fails on an overlap that is in neither list, so a
pin bump that adds one has to be decided before it merges.

### Left out, and why

Each package was measured over two real drafts (#1183, #1186) and the
choice recorded here; `bench/RESULTS.md` (2026-11-20) has this run.

| Left out | Why |
|---|---|
| `ai-tells.VerbTricolon` | 70 findings over the two drafts and the sample project, nearly all real three-item lists; §4 covers the forced triad in the drafting rules instead |
| `Microsoft.Adverbs` | 57 findings ("roughly", "deliberately", "separately"), field-blind, and it repeats `proselint.Very`, `ai-tells.StackedHedges` and `proselint.Skunked` |
| `proselint.Annotations` | `Journals.Placeholder` reports the same markers and more (`[cite]`, `??`) |
| `proselint.P-Value` | `Journals.PValueZero` reports the same "p = 0.000" with the correct repair |
| `proselint.Typography`, `Diacritical` | quotes and dashes are the typesetter's |
| `proselint.Archaisms` | reads the acronym "WoT" as an archaism |
| ai-tells' word lists, figurative verbs, `ColonUsage`, `DoubleHyphen`, `EmDashUsage` | field-blind ("granularity" as AI vocabulary), or fire on LaTeX's `--` and on proper nouns; they wait for calibration against example papers (#1181) |
| Journals' citation rules and its Nature, CONSORT, PRISMA and other layers | misfire on `\cite` and `[@key]`, or are biomedical |
| `Microsoft.Contractions`, `We`, `FirstPerson`, `SentenceLength`, `Passive`, `Headings` | a software-documentation house style; "we" and the passive are a field's choice (#1181) |
| Readability | an index is a trap ([HOUSE-STYLE.md](../../docs/HOUSE-STYLE.md)) |

**No heading rule is enabled.** Under `tex = md`, `\section{...}` is
not a Markdown heading, so a rule scoped to headings never sees a `.tex`
unit; none of the 32 is heading-scoped, and heading checks stay with
`chitragupta/style_headings.py`.

### Moving a pin

1. Copy the listed files from the new release over the old ones, and
   its `LICENSE`.
2. Regenerate `VENDORED.sha256` with the command in its header, and
   update the release and commit there and in the table above.
3. Run `tests/test_style_vendored.py`. A renamed or removed rule fails
   the tables; a new overlap fails the probe until it is added to
   `SHADOWED_BY` or recorded as two different checks.
4. Re-run the drafts in `bench/RESULTS.md`'s 2026-11-20 entry and
   compare.

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

## What is not obvious about the config

**A quotation inside a sentence is exempted after Vale runs**, by
`chitragupta/style_quotes.py`, not here. A block quotation is exempted
by `BlockIgnores` below, but a `TokenIgnores` pattern for `"..."`,
curly quotes or LaTeX's ``` ``...'' ``` has to span lines, and measured
on the bench drafts it lost three real findings outside any quote; it
also hid every expansion written inside a quotation from `Acronyms`,
which `style_quotes.py` leaves alone.

**A `.tex` draft reaches Vale with its LaTeX markup already blanked**, by
`chitragupta/style_latex.py`, and on stdin rather than as a file.
`TokenIgnores` below still lists citation commands, `$...$` and command
names, but on a real 8.7k-word thesis chapter those entries lost
findings in long paragraphs: with a defect marker planted on every prose
line, Vale reported 636 of 839, and with the same spans blanked to
spaces of equal width first, all 839. Two ``` ``...'' ``` in one paragraph
also read as a Markdown code span, hiding the words between them; each
``` `` ``` is handed over as `""`. A `.md` draft still goes to Vale as a file, and the
same probe found Markdown losing findings too (106 of 217 on a 15k-word
survey), which is not fixed yet.

**`TokenIgnores` also skips LaTeX command names and the exercise label**
(#1187). `\centering` and `\begin{center}` were read as prose, and
`center` as an en-US spelling. One alternation covers both forms and must
stay one entry: split in two, it hid every finding beside a `\begin`
line. The label `**Exercise N (Objective M, easy|medium|hard).**` is
ignored whole, so its grade is not read as the marker "easy"; "easy" in
running prose is still reported.

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
VALE_VERSION=3.26.0
curl -sLo vale.tar.gz \
  "https://github.com/vale-cli/vale/releases/download/v${VALE_VERSION}/vale_${VALE_VERSION}_Linux_64-bit.tar.gz"
sha256sum vale.tar.gz   # must match the pin in scripts/install_full_pipeline.sh
```

On an upgrade, re-run the checks over the shipped drafts and compare
against `bench/results/` before moving the pin: a Vale release can change
how a format is scoped, and the exemptions above are the part most likely
to move under you.
The last move, 3.9.1 to 3.26.0, is recorded in
`bench/RESULTS.md` (2026-11-10): no finding gained
or lost, seven more occurrences of existing ones, three placed better.
