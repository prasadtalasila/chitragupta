# 1117/1118/1119: a citable key is a parsed one, and a cited key is a marker

Status: **built, in the pull request that closes all three issues
(v6.160.0).** Signed off by a Fable review with seven changes, folded in
below. Changed on the way: `search()` drops unparsed rows before the
BM25 index rather than after ranking, and the embedding search drops
hits the ledger holds as unparsed (both in section 3); the final review
added a bare key in `*emphasis*` and a `unit accept` refusal naming an
absent source beside an unparsed one. Written 2026-11-05, for
[issue 1117](https://github.com/prasadtalasila/chitragupta/issues/1117),
[issue 1118](https://github.com/prasadtalasila/chitragupta/issues/1118)
and [issue 1119](https://github.com/prasadtalasila/chitragupta/issues/1119),
fixed in one PR at the user's request.

**Written for** whoever builds the fix. **It assumes**
[SOUL.md](../SOUL.md) for the one invariant and why there is exactly one
gate, the module docstrings of `chitragupta/citation_gate.py`,
`chitragupta/dossier/_drift.py` and `chitragupta/style_typeset.py`, and
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §9.

**Not covered here:** an opt-in for citing an entry with no parsed PDF
(a web page, say). The user's call: no exception for now. Unparsed
entries simply never reach the drafting layer. Nor is flagging a
narrative `@key`: the user keeps it as it is.

## The defects

1. **#1118, the invariant is half-enforced.** CLAUDE.md, AGENTS.md and
   SOUL.md say a citekey must be in the `.bib` *and* parsed from a real
   PDF. `ledger.known_citekeys` returns every row, so the gate, render's
   pre-gate (`render_output/_gate.py`) and `unit accept`
   (`unit/_cli.py`) all pass a `no_pdf`, `discovered` or `parse_failed`
   key. Worse than the issue says: **retrieval offers those keys.**
   `retrieval.search()` indexes every row's title, so a `no_pdf` row
   comes back on a title match (probed: a lone `no_pdf` "Robotics web
   page" row is the hit for `robotics`). That is the likely route
   `noauthor_pulsate_nodate` took into a draft. `embed_index.search`'s
   docstring says the same about metadata-only entries in BM25.
2. **#1117, prose read as a citation.** `drift()` computes
   `missing = cited - corpus`, with `cited` from the loose backtick
   match over `evidence.md` and `sections.md`. `` `tutorial-writer` `` in
   the evidence preamble is then a "cited citekey no longer in the
   ledger".
3. **#1119, a bare key prints raw.** A ledger key written without `@`
   ("frameworks gil_survey_2024 evaluates") or in a code span
   (`` `obaidat_hubcap_2022` ``) passes the gate (it counts only
   citations) and `draft style` says nothing. Both come from the
   drafting agents: a paper wanted as a noun, written as its key, and
   the dossier's own `` `key` `` notation copied into prose to remark on
   the corpus.

## Measurement

Over `chitragupta-freja/content` (77 drafts, ledger 497 `parsed` + 145
`no_pdf`); `chitragupta-drafts` has no ledger of its own.

- **#1118:** 0 citations of an unparsed key. The stricter gate fails
  nothing on disk.
- **#1119:** a plain token match finds 786 bare keys; **785 are false
  positives** in two shapes, both of which the rule must skip:
  764 `` [n] entry `key` `` labels in the References section
  `references.build_section` writes (render strips that section), and
  keys inside `<!-- single-source: ... -->` comments. **One real hit:**
  `deep-research/digital-twin-platforms.md:316`, the issue's
  `` `obaidat_hubcap_2022` ``. A probe that passed `section_start` lines
  without line ends missed `## 12. References`; the locator is right,
  the probe was not.

## Design

### 1. `ledger`: one definition of citable

A new `chitragupta/ledger_citable.py` (`ledger.py` is at 247 of 250
code lines):

- `PARSED = "parsed"`.
- `citable_citekeys(con) -> set[str]`: `status = 'parsed'` rows.
- `unparsed_citekeys(con) -> dict[str, str]`: citekey -> status for
  every other row, so a refusal can say *why*.
- `known_citekeys` stays (every row) for what really wants every row:
  sync's own tests and the bare-key rule (an unparsed key printed raw is
  still a defect). Its docstring says it is not a citability test.

### 2. The gate and its two in-process callers

`citation_gate.check_text(path, text, citable: set[str], unparsed:
"Mapping[str, str] | None" = None)`, `check_document` likewise. The
parameter is renamed from `known_citekeys`, so the four keyword calls in
`tests/test_citation_gate.py` (570, 579, 590, 597) are edited with it.
`GateResult` gains `unparsed: dict[str, str]`, the status of each
unresolved key that has a row. `unknown` keeps every unresolved
`(line, key)`, so `ok` and every existing assertion stand.

`report()` prints, per unresolved key:

- no row: `@k not found in ledger -- not sourced from bib sync`
  (unchanged)
- a row: `@k is in the ledger but has no parsed PDF (status no_pdf) --
  attach its PDF in Zotero and run sync again`

`report()` moves to a new `chitragupta/citation_gate_report.py`
(`citation_gate.py` is at 249 of 250), imported back into
`citation_gate` so `citation_gate.report` keeps working for render and
`unit accept`.

`run()`: the empty-ledger warning fires when `citable` is empty; when
`unparsed` is not, it says the ledger holds no parsed source rather than
that it is empty. `render_output/_gate.py` and `unit/_cli.py` read the
same two sets; `unit accept`'s `_unknown_sources` refuses a contract
source that is not citable, with the same wording.

### 3. Retrieval never offers an unparsed key

- `retrieval.search()`: only `parsed` rows are indexed and ranked.
  (Built differently from this plan's first draft, which filtered the
  ranking after BM25 like `collection`: `retrieval.py` was at the cap,
  and `search` is the only writer of the BM25 cache, so filtering the
  rows before `_load_index` costs one line and keeps the cache and every
  IDF over the same set.) `search_iterative` and `discover` go through
  `search`.
- `retrieval_cli.evidence()`: an unparsed row raises `KeyError("k has no
  parsed PDF (status s), so it has no text and cannot be cited")`,
  printed by the existing `[error]` path. This inverts a pinned
  contract: `tests/test_retrieval.py`'s
  `test_a_citekey_with_no_parsed_text_is_not_an_error` and
  `test_parse_failed_status_does_not_serve_stale_parsed_text` (the
  `evidence` one) become refusal tests, and the `evidence` docstring
  line saying an unparsed key is not an error is rewritten.
- `enrich.embed_index.search()`: hits whose citekey the ledger holds
  as unparsed are dropped (`ledger_citable.unparsed_on_this_host`), since
  an index built before a status change still has their chunks.
  Dropping the known-unparsed rather than keeping only the citable is
  what lets a search with no ledger behave as before; the gate still
  refuses the key. Docstring paragraph on metadata-only entries
  rewritten.
- `retrieval_passages` already filters on status; unchanged.

### 4. The dossier's corpus is parsed rows

`dossier._corpus_rows()` selects `WHERE status = 'parsed'`. That makes
`dossier.known_citekeys()`, `Corpus`, the `scope.md` fingerprint,
`missing`, `unconsidered` and candidates all parsed-only.
`agenda`'s `missing-citekey` class reads `drift.missing`, so a row that
went `no_pdf` becomes an unattended de-cite there, which is right. A cited key
whose row stops being parsed is reported missing. **Every existing
dossier's recorded digest stops matching once**, a one-off drift the
release notes state.

### 5. #1117: only a declaration can go missing

In `drift()`:
`missing = (declared_citekeys(dossier) | sections.md keys) - corpus`,
where the `sections.md` keys are those `section_citekeys(dossier,
known)` already returns. The loose `cited` set stays for what it is
used for now: `mentioned` and the cited-beats-rejected tie in
`reconsider`.

**One accepted regression.** A key cited only in an `evidence.md` body,
under a heading that does not open with the key, is no longer reported
missing. Hand-written dossiers are a supported input, but that shape is
the very prose #1117 is about, and a key heading is the format every
skill writes. #506/M-28 still holds: `Doe2024` declared by a heading is
in `declared_citekeys`. A test pins the regression so it is not later
"repaired" back.

### 6. #1119: `chitragupta.BareCitekey`

New `chitragupta/style_bare_citekeys.py` with
`findings(draft: Path) -> list[dict]`, registered in
`style_rules.PYTHON_CHECKS`. Advisory like every style rule; the gate
is untouched (DEVELOPER-AGENTS.md bars a second gate).

- **Keys:** `ledger.known_citekeys` and `citable_citekeys`, read
  read-only; no ledger, or one that cannot be read, gives `[]`. Only
  keys with a digit, `_` or `:` are looked for: a pure-letter key
  (`smith`) is an ordinary word in prose.
- **Tokens** are `re.finditer` over `_pandoc_cites.PANDOC_KEY`, whole
  tokens only, so `doe_2024` is never found inside `doe_2024-1` or
  `smith` inside `smith:2024`; a token is kept when the character before
  it is not `@`, a word character or key punctuation and it equals a
  ledger key.
- **What is scanned, Markdown:** the References section blanked
  (`references_section.section_start`/`section_end` over
  `splitlines(keepends=True)`). Every citation blanked by its span:
  `_pandoc_cites.citations(...)` returns `(start, end, key)`, which
  covers `[@k]`, `@k`, `[-@k]` and braced `@{k}`; plus the
  `citation_gate._LATEX_CITE_RE` matches. Then:
  - *prose:* `citation_gate.markdown_prose(text)[0]` (code, comments,
    link targets, raw blocks already blanked), tokenised as above.
  - *code span:* an inline code span (from
    `_markdown_inert.non_prose_spans(text, code_only=True)`, one line)
    whose whole content is a ledger key. A fenced block is code, not a
    mention, and is skipped.
- **What is scanned, `.tex`:** `citation_gate._blank_code(text,
  latex=True)` (comments, verbatim) with `\cite`-family matches blanked.
  The token pattern accepts `\\?_`, and the lookup strips the
  backslashes from the matched token only; the text is never rewritten,
  so `line_of` on the blanked text gives the right line.
  `\texttt{key}` is the code-span case.
- **Findings,** one per occurrence, line-numbered:

  | Where | Key | `repair` | Message says |
  | --- | --- | --- | --- |
  | prose | parsed | `edit` | replace with `[@k]` (`\citep{k}` in `.tex`, the form `thesis-chapter-writer` writes), IEEE's numbered citation used as a noun: "In [@k], the authors..." |
  | prose | unparsed | `review` | it cannot be cited (no parsed PDF, status s); reword without it |
  | code span | any | `review` | a reader cannot resolve a key; a note about the corpus goes in the dossier's `revisions.md`; to cite it, write `[@k]` |

  `edit` is the agenda's unattended repair: `agenda-reviser` applies
  the message's replacement and keeps it only if `draft gate` passes.
- **No silencer.** A reader-facing draft has no legitimate bare key.

### 7. Stop writing them

- `AGENTS.md`: the invariant's rule line says *parsed*; one paragraph
  that a citation is always a marker (`[@k]`; as a noun, "In [@k], ...";
  never the bare key), and that a remark about the corpus belongs in
  the dossier's `revisions.md`, never in the draft. Every skill already
  reads AGENTS.md, and skills have size caps (#1106), so the rule goes
  there once.
- `docs/WRITING-STANDARDS.md`: a short §16 with the same rule, and a §9
  row for `BareCitekey`.
- `docs/AGENDA.md`'s `[unattended]` row names `BareCitekey`'s review
  cases beside `WideCodeLine`.

## Module sizes (C2: 250 code lines)

Measured with `scripts/code_standards.code_lines`: `citation_gate.py`
249, `retrieval.py` 248, `ledger.py` 247, `retrieval_cli.py` 245,
`embed_index.py` 243, `dossier/_drift.py` 233. The register may only
shrink, so the splits are decided above: `ledger_citable.py`,
`citation_gate_report.py`, and a merged filter in `search()`.
`retrieval_cli.py` has room for its two lines.

## Tasks (test-first; each test red before its code)

1. **ledger.** `tests/test_ledger.py`: `citable_citekeys` returns only
   the `parsed` row of a `parsed`/`no_pdf`/`discovered`/`parse_failed`
   set; `unparsed_citekeys` maps the other three to their statuses.
2. **gate.** `tests/test_citation_gate.py`:
   `test_a_no_pdf_key_fails_naming_its_status` (draft `[@k]`, row
   `no_pdf`; `run()` exits 1, output has `has no parsed PDF (status
   no_pdf)`); the same for `discovered` and `parse_failed` (parametrize);
   a missing key keeps its old line; `test_a_ledger_of_only_unparsed_rows_warns_no_parsed_source`.
   Render: `tests/test_render_output_gate.py`, where `gated_warnings`
   raises `UngatedDraft` for a `no_pdf` citation. Unit:
   `tests/test_unit.py`, where `unit accept` refuses a `no_pdf` source.
   Existing set-passing calls keep working; the four keyword calls are
   renamed.
3. **retrieval.** `tests/test_retrieval.py`:
   `test_search_never_returns_an_unparsed_row` (the probe above, plus a
   parsed row that must still come back with an unchanged score);
   `evidence` on a `no_pdf` or `parse_failed` key raises with the
   status (the two tests named in section 3 rewritten);
   `tests/test_enrich_embed_index.py`: a `parse_failed` hit is dropped.
4. **dossier.** `tests/test_dossier*.py`: the corpus digest and count
   are over parsed rows; a cited key whose row is `no_pdf` is in
   `missing`; the issue's `` `tutorial-writer` `` preamble reports
   nothing missing; a declared heading key and a `sections.md` key that
   left the ledger still do;
   `test_a_key_cited_only_in_an_evidence_body_is_not_missing` pins the
   accepted regression.
5. **BareCitekey.** `tests/test_style_bare_citekeys.py`: the issue's
   two lines (one `edit` at line 3 saying `[@gil_survey_2024]`-shaped,
   one `review` at line 5); negatives: a `` [n] entry `key` `` References
   section, a `<!-- single-source: only key ... -->` comment, `[@key]`,
   `@key`, `[-@key]`, a fenced block holding a key, a link target, a
   pure-letter key in prose; an unparsed key in prose is `review`; a
   `.tex` `gil\_survey\_2024` in prose and `\texttt{key}`; no ledger
   gives `[]`. Fixtures use the temp-ledger `make_reference` helper with
   keys of the shape the tests already use, never a key copied from a
   real `.bib`. Then register in `PYTHON_CHECKS`
   (`tests/test_style_check.py` enforces it).
6. **Docs and skills** (section 7), plus every doc the change makes
   false: `grep -rn "known_citekeys\|metadata-only\|findable" docs
   AGENTS.md chitragupta` and the `repair-missing-citekey.md` wording
   ("left the ledger" now also means "no longer parsed").
7. **Version** 6.160.0 in `pyproject.toml` (and wherever the release
   check reads it), the full local check list from DEVELOPER-AGENTS.md,
   then the PR.

Found on the way and left for its own issue: `passages._ledger_row`
reads `parsed_path` with no status guard (the #490 class).

## Review Focus

- A ledger of only unparsed rows: every citation fails, and the warning
  must not say "empty" (task 2).
- A row that goes `parsed` -> `parse_failed` on a re-sync: the gate,
  search and drift all stop treating it as citable at once (tasks 2-4).
- A key that is a prefix of another (`doe_2024` / `doe_2024-1`): the
  bare-key match must not report the shorter inside the longer (task 5).
- A `.tex` unit with `\_` escapes and `%` comments naming keys (task 5).
- The retrieval cache: filtering after BM25 must leave the cached index
  and every parsed row's score byte-identical (task 3).

## Version

MINOR, **6.160.0** (6.159.0 went to #1147, merged first): a new style
rule. The stricter gate is a bug fix
restoring the documented invariant, but the release notes say plainly
that a draft citing an unparsed key now fails and that every dossier
shows corpus drift once.
