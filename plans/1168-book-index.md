# 1168: a back-of-book index built from the glossary

Status: **designed, being built.** Reviewed twice by a second model
(Fable); its corrections to id stability, parent keys, the hyperref
encap, input discovery, the C2 split and the pass count are folded in.
[issue 1168](https://github.com/prasadtalasila/chitragupta/issues/1168).

**Written for** whoever builds or reviews #1168. **It assumes**
[docs/WRITE-A-BOOK.md](../docs/WRITE-A-BOOK.md) for the book track,
[docs/book/back-matter.md](../docs/book/back-matter.md) for the
generated pages, `.claude/skills/book-assembler/SKILL.md` for the
assembly steps, and [tb-10-book-glossary.md](tb-10-book-glossary.md) for
the glossary and List of Symbols this builds on.

**Not covered here:** heading-based locators, page ranges
(`|(` ... `|)`), and statistical term extraction. The issue's
"Alternatives considered" table records why each was set aside; the
user's decisions on the issue are not reopened here.

## Decisions taken with the user

| Question | Decision |
| --- | --- |
| Term sources | Glossary terms; symbols only beside their linked term. No corpus vocabulary (`seed_topics.toml`, `keywords.toml`) |
| Locator policy | Defining chapter always, bold; any other chapter at its first occurrence if the term occurs there at least `min_mentions` times (default 2) |
| Position | Last, after the bibliography |
| Rebuild | Every assembly |
| `index.toml` edited after sign-off | No re-sign-off |
| Editing | Hand edit; findings print the TOML that fixes them; no CLI |
| Report | `content/specs/<book>/registries/index.md` and `index.json` |
| Optional | Only when the outline has `### Index {#index}`; `spec init` writes it |
| Docs | `docs/book/book-index.md`, with the data-flow diagram explained |
| Split | One PR |
| Architecture | Approach B below |

## Architecture: the filter places ids, Python finishes the index

```text
scope.md glossaries ─┐
math.md ## Symbols ──┼─► registry build --index ─► rendered/<book>/index-terms.json
specs/<book>/index.toml ┘        (validates; exit 1 on bad toml)
                                              │
<unit>.md ─► render --fragment --index-terms ─┤─► <unit>.tex   (\index{t017} …)
                (Lua: match, count, place)    └─► <unit>.index.json  (sidecar: counts, casing)

book.tex ─► lualatex ─► bibtexu ─► lualatex ─► lualatex ─► book.idx
                                                 │
            registry index book.idx ◄────────────┘  (Python: ids → sort@printed, see/parents,
                 │                                    quoting; runs upmendex -s .ist)
                 ├─► book.ind ─► lualatex ─► book.pdf
                 └─► specs/<book>/registries/index.md + index.json  (report)
```

Why this split: matching must run on pandoc's AST (only it can skip
code, maths and citations), but capitalisation and the report need the
whole book, which one filter call never sees. Putting an opaque ASCII
id in `\index{}` removes LaTeX escaping from the problem entirely (the
key may sit inside a tokenised `\footnote{}` argument), keeps a single
matcher (Lua), and puts every presentation decision in Python, under
the 100% coverage rule.

## Contracts

### `content/specs/<book>/index.toml` (author, optional)

Tables: `settings` (`min_mentions` int >= 1, default 2; `sort` `"word"`
or `"letter"`; `letter_headings` bool; `skip_sections` list, default
`["Exercises", "Solutions"]`), `variants`, `restrict`, `always`,
`print`, `parent`, `parent_only`, `see`, `see_also`, `drop.terms`,
`add.terms`. Keys name terms by `term_key()`. `assets/book/index.toml`
is the commented sample; only `[settings]` is live in it.

Refusals (`build --index` exits 1, lists every problem, writes
nothing): unknown table or key; wrong type; `min_mentions < 1`; a term
in neither the glossary nor `[add]`; an `[add]` term already in the
glossary; a spelling claimed by two terms; an `[always]` chapter that
is not an accepted unit; a `[see]` source that is an indexed term
(Chicago 15.16); a `[see]`/`[see_also]` target that is not a term; a
`[parent]` child that is unknown or dropped.

### `content/rendered/<book>/index-terms.json` (generated)

```json
{"min_mentions": 2, "skip_sections": ["Exercises", "Solutions"],
 "terms": {"t017": {"key": "digital twin",
                    "spellings": ["digital twin"],
                    "defined_in": ["01-why-anyone-pays-for-a-digital-twin"],
                    "always": [],
                    "glossary": "Digital twin", "symbols": [],
                    "print": null, "parents": []}},
 "see": {"DT": "t017"}, "see_also": {}, "parent_only": [],
 "sort": "word", "letter_headings": false}
```

Ids are `"t" + sha1(term_key)[:8]`: stable across rebuilds, so a
chapter rendered before a term was added can never point an old id at a
different term. The file's own digest goes into every sidecar, and
`registry index` refuses a sidecar whose digest differs, or an accepted
unit with no sidecar ("re-render with --index-terms"): a stale or
unindexed chapter is a refused build, never a silently empty one.
Spellings are normalised by the filter's own token rule (hyphen splits,
lowercase), so `digital twin` already covers `digital-twin`. A term
with `[restrict]` has the restrict phrases as its spellings and not
its bare key. A glossary term whose text holds maths is left out unless
`[variants]` gives a plain spelling (reported). The filter reads only
`min_mentions`, `skip_sections` and each term's `spellings`,
`defined_in`, `always`.

### `<output-dir>/<unit>.index.json` (sidecar, one per rendered chapter)

```json
{"unit": "04-digital-twin-architecture", "terms_digest": "<sha256 of index-terms.json>",
 "terms": {"t017": {"count": 2, "indexed": true,
                    "midsentence": {"digital twin": 2}}}}
```

Sorted keys, no timestamp.

### `book.idx` rewrite

Input lines are `\indexentry{<id>|<encap>}{<page>}`; installed hyperref
writes `hyperpage` or `hyperxindexformat{\textbf}` (verified). The parser
is `\indexentry{(id)(\|[^}]*)?}{(page)}` and never names the macro: only
the key is replaced, the encap and page are copied verbatim. Output `book-index.idx`;
`book.idx` is not modified, so the step reruns safely. Every input
`registry index` needs sits beside `--idx` by convention: `index-terms.json`
and `<unit-id>.index.json` for each accepted unit (fragments render into
the book's rendered directory, SKILL.md step 4). Outline ids equal file
stems (`unit.draft_path`), and `render()` hands pandoc a temporary copy,
so the unit id reaches the filter through `--metadata`, as
`_unit_labels` passes its prefix. An id not in
`index-terms.json` is a stale build: exit 1, say to rebuild.

## Components

| File | Role |
| --- | --- |
| `chitragupta/registry/_index_terms.py` | load and validate `index.toml`; build the term table from `built`; write `index-terms.json` |
| `chitragupta/registry/_index_finish.py` | read `.idx` and sidecars; printed form, sort key, quoting, parents, see entries; write `book-index.idx` and `book.ist`; run `upmendex` |
| `chitragupta/registry/_index_report.py` | findings and the full table as `index.md` / `index.json` |
| `chitragupta/registry/_cli.py` | `build --index PATH`; `index BOOK --idx PATH` |
| `chitragupta/render_output/_index_terms.py` | the render-side argv, twin of `_unit_labels.py` |
| `chitragupta/render_output/_cli.py`, `_pandoc.py` | `--index-terms PATH`, refused without `--fragment` |
| `chitragupta/render_output/_markdown_to_latex.py` | forced split: `_pandoc.py` is at exactly 250 code lines (C2) and not on the register, so `markdown_to_latex` and its separators move out at their existing section boundary; the package re-export stays and `registry/_cli.py` imports the new home |
| `assets/pandoc/index_terms.lua` | match, count, place, write the sidecar |
| `assets/latex/chitragupta-index.ist` | `upmendex` style template |
| `assets/book/index.toml` | the sample |
| `chitragupta/spec/_matter.py`, `_scaffold.py`, `_cli.py` | `{#index}` in `GENERATED`; `spec init` writes the line and copies the sample |
| `chitragupta/doctor.py` | `upmendex` and `bibtexu` in `BINARIES` |
| `scripts/install_full_pipeline.sh` | comment the two packages; fail `os-deps` if `upmendex` or `imakeidx.sty` is missing |

Printed forms are converted to LaTeX by the same batched
`markdown_to_latex` the Glossary page uses (`_pages.render`), so the
index and the Glossary print a term identically; no second escaper.

### Printed form, sort key, quoting

- Casing: the majority mid-sentence surface form over all sidecars;
  a tie or none keeps the glossary's casing; `[print]` overrides.
- Leading *the/a/an*: dropped from the sort key, printed inverted
  ("four criteria, the").
- Symbols appended in parentheses, as the Glossary heading prints them.
- Sort key: `term_key()`, LaTeX removed, Greek names spelled out
  (`_pages._GREEK_NAMES`), article dropped.
- `upmendex` quoting: `"` before each of `! @ | "` in both parts.
- Parents: `parent-sort@parent-printed!child-sort@child-printed`, the
  parent's full `sort@printed` repeated on every child line (otherwise
  `upmendex` prints the parent twice; verified). A child that starts or
  ends with the parent's word drops it. Children also post at top level unless `parent_only`.
- `[see]`/`[see_also]`: `|see{...}`/`|seealso{...}` entries, page taken
  from the target's first entry; a target with no locator drops the
  cross-reference (reported).

### The filter

Walks Para, Plain, list items, table cells, block quotes, Note blocks.
Not Header, Figure/Table captions, Code, CodeBlock, Math, RawInline,
RawBlock, Cite, Image. A heading whose text is in `skip_sections`
starts a skipped region until the next heading of the same or higher
level. Flattens each inline list into tokens (descending Emph, Strong,
SmallCaps, Span, Quoted, Link content) with a back-pointer to the
`Str`; tokens are lowercased with `pandoc.text.lower`, edge punctuation
and a possessive `'s`/`’s` stripped, split on `-` and `–`. Longest
spelling first at each position; the last word may add `s`/`es`;
matches never overlap. Pass 1 counts and records mid-sentence surface
forms (mid-sentence = not paragraph-initial and not after `.` `!` `?`).
Pass 2 places `\index{<id>}` (or `|textbf` in a defining chapter) after
the *top-level* inline that contains the first matched `Str` (never
inside a link or quote, so never inside a moving argument), when the
term qualifies in this chapter. `skip_sections` titles compare
case-insensitively. The `s`/`es` plural applies to the last word only.

### Report findings (advisory, never block)

`index.md`: the summary line, findings each with its fix, then the full
table (term, chapters with locators and counts, chapters below
`min_mentions`). `index.json`: the same data. Kinds:

| Kind | When | Fix printed |
| --- | --- | --- |
| `no-locator` | a term with no locator anywhere | `[variants]` or `[drop]` |
| `generic` | locators in at least 3/4 of the chapters (and at least 4 chapters) | `[drop]` or `[restrict]` |
| `below-threshold` | a chapter with 1..`min_mentions`-1 mentions, not indexed | `[always]` |
| `mixed-case` | more than one mid-sentence surface casing | `[print]` |
| `family` | three or more terms sharing a first or last word, with no parent | `[parent]` |
| `unused` | an `index.toml` entry that matched nothing | remove it |
| `not-indexable` | a glossary term holding maths with no plain variant | `[variants]` |
| `dangling-see` | a see target with no locator | fix or remove |

## Assembly

`book.tex`, only with `{#index}`: `\usepackage{imakeidx}` before
hyperref, `\makeindex[noautomatic,intoc]`; `\printindex` after the
bibliography under `\backmatter`. Build order:
`lualatex → bibtexu → lualatex → lualatex → registry index → lualatex`.
The `.idx` is read only after the third pass, once citations,
cross-references and the contents have settled the page breaks; the
index adds one pass (about a fifth of the ~86 s build). The skill
is at 19,771 of 20,000 bytes (#1091), so the three new command lines go
in `SKILL.md` with existing wording trimmed to fit, and the preamble,
`{#index}` row and rationale go in `references/latex-conventions.md`.

## Install

`upmendex` ships in `texlive-binaries`, `imakeidx.sty` in
`texlive-latex-extra` (`dpkg -S`, Ubuntu); both already in `os-deps`.
The script gains a comment naming the book index as their user, and a
post-install check that fails loudly when either is missing. A test pins
both package names in the script's `apt-get` line. CI's `docker-build`
runs `os-deps`, so the check runs there. `docs/WINDOWS.md` says how
MiKTeX provides `upmendex` (verified, not assumed).

## Build order (each step test-first)

1. `{#index}` reserved; `spec init` line and sample copy.
2. `_index_terms`: validation, term table, JSON, `build --index`.
3. Lua filter, render hook, `--index-terms`; pandoc-backed fixtures for
   line break, hyphen, partial emphasis, nested terms, footnote,
   skipped section (including a deeper heading inside it), caption,
   citation, possessive, restrict, SoftBreak inside a term, a match in
   Link and Quoted, and the sidecar write.
4. `_index_finish`: rewrite, printed form, sort, quoting, parents, see,
   `.ist`, `upmendex` (a fast test running the real `upmendex` on a
   hand-written `.idx`; `# pragma: no cover-windows`, not `slow`).
5. `_index_report` and `registry index`.
6. Slow end-to-end test: a two-chapter book through the full build,
   awkward keys in body and footnote, `book.ind` asserted.
7. `doctor` (widen `tests/test_doctor.py`'s binary fixture), install
   script check and its test.
8. Skill, references, docs (`book-index.md`, `back-matter.md`,
   `WRITE-A-BOOK.md`, `WRITING-PROCESS.md`, `CLI.md`, `WINDOWS.md`,
   `PACKAGING.md`, `README.md`).
9. Real-book check on the digital-twins book in a scratch directory;
   all local checks; MINOR bump.
