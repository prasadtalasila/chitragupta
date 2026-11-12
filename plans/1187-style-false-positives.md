# 1187: style and verbatim findings an unattended repair must not touch

Status: **designed, unbuilt.** Written 2026-11-12, for
[issue 1187](https://github.com/prasadtalasila/chitragupta/issues/1187)
and its 2026-11-11 comment.

**Written for** whoever builds the fix. **It assumes**
[docs/AGENDA.md](../docs/AGENDA.md) for what `unattended` means,
`.claude/skills/agenda-reviser/SKILL.md` for who acts on it,
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §2, §8 and §9
for the rules involved, and [docs/PLAGIARISM.md](../docs/PLAGIARISM.md)
for the verbatim scan.

**Not covered here:** cleaning up an existing project's
`content/acronyms.toml` to the case rule in section 2. That is a commit
in the project that owns the file (for the digital-twins book, in
`chitragupta-drafts`), made after this ships. Nor is item 5 of the
comment, the job killed by a 60-second timeout while paused with
SIGSTOP: no such timeout exists in this repository (`timeout=60`
appears nowhere under `chitragupta/`, `scripts/` or `.claude/`; the
agenda refresh runs every aid in-process), so it came from the caller's
wrapper. It gets a comment on the issue, not code.

## The problem in one paragraph

`agenda-reviser` repairs every agenda item marked `unattended` without
asking. A `prose` item is unattended whenever its finding carries
`repair: "edit"` (`chitragupta/review/agenda/_items_findings.py:153`),
and every Vale rule except `Just` and a host-default dialect stamps
`"edit"` (`chitragupta/style_rules.py:with_repair`) without looking at
the match. A short verbatim run is unattended whenever its tier is not
`embedding` (`_items_findings.py:74`). The issue lists matches where
the "repair" is wrong: a difficulty grade, a correct lower-case
acronym expansion, a standard's official name, a LaTeX command, a
citekey, and an organisation's name copied from sources. The repairs
broke a grading scale across six chapters and capitalised common nouns
in some drafts but not others.

## The policy

Agreed with the user during design, and the test every change below
must pass:

1. **Suppress only what is declared.** A finding disappears only when a
   deterministic rule says the match is not prose (LaTeX syntax, a
   citekey, the exercise label) or when a project file names the term.
   An undeclared case is still reported, so a real mistake stays
   visible.
2. **A heuristic may only downgrade.** Where code has to guess (is this
   capitalised word a name?), the finding becomes `repair: "review"`,
   which the agenda surfaces to a person. The worst a wrong guess can
   do is ask an unnecessary question.
3. **Exceptions are dialect-agnostic and draft-agnostic.** A declared
   term applies to every draft in the project under every `language:`.

## 1. Project data

Two files under `content/`, both project data in the same sense as
`content/acronyms.toml`: an author's statement about the project,
meant to be versioned with it. That differs from
`content/verbatim_allowlist.toml`, which `config.py` documents as
per-host and gitignored.

### `content/acronyms.toml`: case becomes authoritative

No format change. One new meaning: **the case of an expansion is the
case a draft must use mid-sentence.** A capitalised value
(`UML = "Unified Modeling Language"`) is a proper name. A lower-case
value (`SCADA = "supervisory control and data acquisition"`) is a
common noun, which may only be capitalised at the start of a sentence
or a heading.

Why the file needs this: the real vocabulary in `chitragupta-drafts`
mixes all three cases, with proper names capitalised (`UML`, `ISO`,
`NASA`), common nouns also capitalised (`SCADA`, `ODE`, `RUL`), and
some common nouns in lower case (`PT = "physical twin"`). Nothing reads
case today. Retrieval lower-cases everything, `AcronymDrift` compares
case-insensitively, and Vale's `Acronyms` rule never reads the file.
The skills copy the value into drafts verbatim, so the file's
inconsistency becomes the drafts' inconsistency.

Touches: `assets/style/acronyms.toml.example` and
`assets/style/README.md` say so. `acronyms.suggest()` /
`dossier acronyms-suggest` keep the glossary's case but print one line
reminding the author that case is authoritative. The vendored floor
(`assets/style/acronyms.toml`) is already all proper names, so it stays
unchanged.

### `content/style_exceptions.toml`: new

```toml
# Exact terms no prose rule reports and the verbatim scan masks, in
# every draft of this project under every dialect. Acronym expansions
# in content/acronyms.toml are exceptions already; list only the rest.
terms = [
  "Unified Process",
]
```

- `config.STYLE_EXCEPTIONS_PATH = CONTENT_DIR / "style_exceptions.toml"`,
  fixed under `CONTENT_DIR` like `VERBATIM_ALLOWLIST_PATH`.
- Absent file: no terms. That is the normal state, and `chitragupta init`
  does not scaffold it.
- A present file that does not parse, cannot be read, has a key other
  than `terms`, or has a `terms` that is not a list of non-empty
  strings is an error. Follow `verbatim_check/_allowlist.py`'s
  precedent rather than `acronyms._load`'s skip-with-note: a broken
  exceptions file that silently loaded as empty would turn suppressed
  findings back into unattended edits, which is exactly the failure
  this issue is about.
- New module `chitragupta/style_exceptions.py`, with
  `terms() -> tuple[str, ...]` returning the file's terms plus every
  value of `acronyms.load_vocabulary()`, de-duplicated
  case-insensitively. It is the one source for both consumers below.

## 2. `draft style`

### House rules in `assets/vale/` (ship to everyone)

- **LaTeX syntax.** One more `TokenIgnores` entry in `vale.ini`, placed
  after the existing `\cite` entry. It matches an environment delimiter
  or a control-sequence name as a **single alternation**:
  `(\\(?:(?:begin|end)\{[^}]*\}|[A-Za-z]+\*?))`. It may not contain a
  literal comma (`assets/vale/README.md` explains the split). Only the
  command name is hidden, so `\emph{obviously}` is still flagged.
  Measured with Vale 3.26.0:
  - Today, `\centering`, `\begin{center}` and `\color{red}` produce
    `DialectGB` findings whose repair would break the LaTeX.
  - With this entry they produce none, while prose inside the
    environment and after it is still checked.
  - Two separate entries, one per shape, are **not** equivalent. That
    combination hid every finding in prose lines next to an ignored
    `\begin{…}` line. A fixture must keep the single-entry form from
    being "tidied" into two.
- **The exercise label.** A `TokenIgnores` entry for the bold label
  `\*\*Exercise \d+[^*]*\*\*` (no comma; the label's own comma sits
  inside `[^*]*`). Prose "easy" outside the label is still flagged.
  The label is written down as a convention in
  `.claude/skills/textbook-chapter-writer/SKILL.md` (where it says
  "Include a mix of difficulty") and in WRITING-STANDARDS §2:
  `**Exercise N (Objective M, easy|medium|hard).**`.
- **Lower-case acronym expansions.** `Acronyms.yml`'s `second:`
  becomes `(?:\b[A-Za-z][a-z]+[\s-]){1,5}\(([A-Z]{2,6})\)`, which
  accepts "supervisory control and data acquisition (SCADA)" and
  "megawatts (MW)". Whether that case is right is the next rule's
  question, not this one's. `acronyms._BODY_ACRONYM` keeps its
  capitalised shape: it proposes vocabulary entries, and widening it
  would propose every "word (ACRO)" in a draft.
- Fix `vale.ini`'s header comment while there. It says the command
  "copies this file to a temp location and appends one line", but
  `style_check._vale_argv` passes the shipped file and selects the
  dialect with `--filter`.

### Project terms: a Python filter over Vale's raw findings

`style_check.check` drops a raw Vale finding (before `collapse()`)
when its `Span` on its `Line` lies inside a case-insensitive occurrence
of a `style_exceptions.terms()` entry on that line of the draft. The
`chitragupta.Acronyms` rule is exempt from the filter, because a term
covering "Unified Modeling Language (UML)" must not hide an unexpanded
`UML` elsewhere.

Considered and rejected: a Vale vocabulary (`Vocab =` plus a generated
`accept.txt`). Measured, it gives the same result for `DialectGB`, but
Vale reads vocabularies only from under `StylesPath`, so it would mean
copying the shipped styles tree to a temp directory on every run, and
a user's `VALE_CONFIG_PATH` override would bypass it. The filter is
plain Python, works under an override, and is testable without Vale.

### `chitragupta.AcronymCase` (new Python rule, `repair: "review"`)

For each vocabulary acronym `A` with expansion `E`, find every
occurrence in the body (References section and code excluded, as
`acronyms.body_candidates` already does) of a phrase equal to `E`
case-insensitively, directly before `(A)`, whose case differs from `E`.
The one tolerated difference is a capitalised first letter where the
phrase starts a sentence, a line or a heading. One finding per
(acronym, matched text), with the vocabulary's spelling in the message.

It is `"review"`, not `"edit"`, because until a project's vocabulary
has been cleaned up the file can be the wrong side. The agenda
surfaces these findings instead of rewriting a draft to match a stale
entry. Registered in `style_rules.PYTHON_CHECKS` beside
`AcronymDrift`.

### `with_repair` becomes match-aware for dialect rules

A `DialectGB` / `DialectUS` / `DialectIN` finding whose `match` begins
with a capital letter is `"review"`. That covers a name nobody has
declared yet ("Modeling" in "Unified Modeling Language") and costs a
question for a sentence-initial "Color". Lower-case matches keep
today's rule (`"edit"` when the dialect came from `scope.md` or
`--language`). `_ALWAYS_REVIEW` is unchanged.

## 3. Verbatim scan

In `chitragupta/review/verbatim_check/_masking.py`:

- **LaTeX cites.** `_tokenize_draft` passes `latex=True` to
  `extract_citekeys_from_line` for a `.tex` draft and blanks
  `\cite…[…]{…}` commands, as `_CITE_MARKER_RE` already does for
  `[@…]`. Today a `.tex` draft's cite commands become words, and
  `cites_source` can be false for a run that cites its source.
- **Bare citekeys.** Any token equal to a citekey in the corpus is
  blanked, so a reference-list line or prose mention can no longer
  form a run. Rewording cannot repair a citekey.
- **Project terms.** Every `style_exceptions.terms()` phrase is masked
  the way allowlist phrases are (`_exact.py`'s
  `span_words - sum(mask) < min_run`), so a run must be `min_run`
  words *beyond* the names in it. Cost: masking every acronym
  expansion makes the scan slightly less sensitive around those words.
  This was accepted during design.
- **Name-heavy runs are surfaced, not suppressed.** A run gains
  `"names": true` when at least half of its words start with a capital
  letter and are not sentence-initial. In
  `_items_findings.py`, a verbatim item is unattended only when it is
  `short`, not `embedding`, and not `names`. An undeclared organisation
  name copied from sources reaches a person instead of being
  reworded.

## 4. Documentation

- WRITING-STANDARDS §2: the exercise label, and `easy` stays in the
  marker table (`tests/test_style_assets_match_the_standard.py` holds
  the token sets equal). §9: the case rule and `style_exceptions.toml`.
- `docs/CONFIG.md` (or wherever `content/` files are listed): the new
  file. `docs/PLAGIARISM.md`: the new masks and the `names` field.
- `.claude/skills/agenda-reviser/SKILL.md`, the `prose` row of the
  class table: add `AcronymCase`, and capitalised dialect matches, to
  the list of `"review"` findings.
- `.claude/skills/agenda-reviser/references/repair-missing-citekey.md`:
  correct the account of what is left after the repair. Removing the
  `[@key]` marker leaves a `recorded-but-uncited` item, and the
  `missing-citekey` item itself also persists while `evidence.md` or
  `sections.md` still holds the key. Both clear only when the author
  runs `dossier prune`. The reviser's report says so, naming the
  command, instead of calling the residue intended.

## 5. Tests

Real-Vale fixtures (`tests/fixtures/style/`, run by
`TestAgainstRealVale`). Each false positive from the issue is paired
with a control that must still be reported:

| Must not be reported (or must be `review`) | Must still be an `edit` |
| --- | --- |
| `**Exercise 1 (Objective 2, easy).**` | "This is easy." |
| "supervisory control and data acquisition (SCADA)" | "SCADA" never expanded |
| "Unified Modeling Language" with `UML` in the vocabulary | "modeling" alone, en-GB from `scope.md` |
| `\centering`, `\begin{center}` in `.tex` | `\emph{obviously}`, and prose inside the `center` environment |
| A term from `style_exceptions.toml` | The same misspelling outside the term |

Unit tests:

- the `style_exceptions` loader: absent, empty, each malformed case,
  and the merge with the vocabulary;
- the span filter, including the `Acronyms` exemption;
- `AcronymCase`: wrong case, sentence-start tolerance, a heading, the
  References exclusion;
- the match-aware `with_repair`;
- verbatim masking of LaTeX cites, bare citekeys and terms, and the
  `names` flag;
- the agenda's unattended mapping for `names` runs and `AcronymCase`.

## Order of work

1. `style_exceptions.py`, config and loader tests.
2. House Vale rules and fixtures.
3. Span filter, then `with_repair`, then `AcronymCase`.
4. Verbatim masks and the `names` flag, then the agenda mapping.
5. Docs and skill references; a comment on #1187 for item 5.
