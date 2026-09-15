# Book assembly: rendered layout, authored preamble, book-wide bibliography

Five threads, settled in discussion and verified against the code and the
host toolchain. Numbers below are measured, not estimated.

## Decisions taken

| # | Decision |
| --- | --- |
| 1 | ToC lists sections: `\setcounter{tocdepth}{1}` |
| 2 | Normalise the CSL/BST reference lists -- **it needs no code** (see D14) |
| 3 | `run()` catches `spec.SpecError` |
| 4 | Citation mode is **inferred**, not a new public flag |

## A. Layout move

`content/drafts/<book>/` holds only authored chapter `.md`. Assembly output
moves to `content/rendered/<book>/`. Authored non-prose stays in
`content/specs/<book>/`.

- **A1** `book-assembler/SKILL.md:258` -- drop `--output-dir content/drafts/<book>`.
  Draft render's default already mirrors to `content/rendered/<book>/`.
- **A2** Skill + `docs/WRITE-A-BOOK.md:605-612` -- `book.tex`/`book.md` into
  `content/rendered/<book>/`. `\input` paths stay relative and unchanged.
- **A3** `docs/WRITE-A-BOOK.md:645-648` -- the build `cd`s into rendered.
- **A4** `SKILL.md:297` -- `draft gate` path.
- **A5** `render_output/_cli.py` -- `--output-dir` help text. The flag stays:
  public surface.
- **A6** `render_output/_assets.py:77` -- re-word `_copy_beside`'s `SameFileError`
  rationale. **Keep the guard**: a caller can still aim `--output-dir` at the
  input's own directory.

## B. citekey_union -- the substantive fix

`compute()` derives one directory (`assembled.parent`, citekey_union.py:99) and
spends it on two jobs that the move puts in different trees:

| Job | Needs | Why |
| --- | --- | --- |
| `_citekey_union_includes.split` | `assembled.parent` (rendered) | where the fragments are |
| `acceptance_units` / `_recorded_citekeys` / `unit.state` | drafts | `spec.spec_dir` requires `relative_to(DRAFTS_DIR)` (`spec/__init__.py:93`) |

Left unfixed this does not merely crash -- pointed at a drafts path it would
resolve zero fragments and report **every citekey in the book as dropped**,
which is the exact false report the module's docstring exists to prevent.

- **B1 (blocker, resolved)** The mapping helper needs a **new module**.
  Measured with `scripts/code_standards.py`:
  `citekey_union.py` **239/250**, `review/__init__.py` **247/250**.
  C2 counts docstrings. Neither file has room; put it in e.g.
  `chitragupta/review/_book_paths.py`.
- **B2** `citekey_union.py:99` -- includes vs records split, records via
  `mirrored_dir(assembled, RENDERED_DIR, DRAFTS_DIR)`, falling back to
  `assembled.parent` when not under rendered/.
- **B3** `refuse_a_unit()` (`:138`) -- same mapping. Strictly better: a rendered
  `ch-01.tex` currently tracebacks; after, it gives #496's refusal.
- **B4** `run()` (`:271`) -- catch `spec.SpecError`. It is
  `class SpecError(Exception)`, a sibling of `UnitError`, not a subclass.
- **B5** `review/__init__.py:135-145` -- `report_dir` learns the rendered input,
  so `--write` lands in `content/review/<book>/` instead of colliding flat. Its
  docstring currently argues *for* the flat fallback; it moves in the same edit.
  Watch the 3-line headroom.
- **B6** Tests: rendered `book.tex` computes; a rendered fragment refuses
  instead of tracebacking; `--write` mirrors.

## C. Preamble, numbering, ToC

- **C1** Optional `content/specs/<book>/preamble.tex`, copied to rendered/ and
  `\input` **last** so it overrides the generated defaults. Absent => no
  `\input`, silently. The **skill** does the copy (it already writes `book.tex`
  there, and the absent case is a composition-time judgement).
- **C2** Skeleton `SKILL.md:66` -- `\setcounter{secnumdepth}{2}`. This is
  `book.cls:268`'s own default, so the line documents intent rather than changing
  behaviour. Drop the `% if the units number themselves` comment.
- **C3** Skeleton -- `\setcounter{tocdepth}{1}`. **The real departure**:
  `book.cls:588` defaults to 2 and nothing in the repo sets it today. Levels are
  part -1, chapter 0, section 1, subsection 2, so parts/chapters/sections are
  listed and subsections are not.
- **C4** `SKILL.md:386-395` -- table-caption prose: the default branch inverts to
  per-chapter "1.1, 2.1". Both pdflatex measurements stay true.
- **C5** `render_output/_tables.py:33` -- same claim in a docstring.
- **C6** `docs/WRITE-A-BOOK.md:675`, `SKILL.md:447` -- stop calling secnumdepth
  a hand-edit; point at `preamble.tex` as the override. This doc defect predates
  the change.
- **C7** Disambiguate "preamble" wherever both appear: **generated** (inline in
  `book.tex`) vs **authored** (`preamble.tex`).
- **C8** Test: no `_citekey_union_includes.py` change needed --
  `\input{preamble}` resolves via `_SUFFIXES`, lands in `others`, and its
  citekeys correctly report under `appeared`.

Numbering is consistent because the spec's section titles carry no numbers. A
book whose units number their own headings puts `-2` in `preamble.tex`.

## D. Book-wide bibliography

**The crux.** Citeproc assigns numbers in the same pass that builds the list, so
resolution must move, not just the list. Measured, two chapters sharing a source:

```text
deferred (one bibtex pass over the book)      today (citeproc per unit)
  Ch1: overview [1], sync [2]                   Ch1: overview [1], sync [2]
  Ch2: overview [1], factory [3], anomaly [4]   Ch2: overview [1], factory [2], anomaly [3]
```

Deferred is distinct across the whole book, shared not duplicated, and
continuous. Per-unit collides: `[2]` is Chen in Ch1 and Eriksen in Ch2, so
merely relocating the list would silently cite the wrong source.

Standalone renders are unchanged -- they keep citeproc and the vendored CSL, and
keep their own reference list.

- **D1** `_pandoc.py:101-171` -- the deferred path swaps
  `--citeproc --bibliography --csl` for `--natbib --bibliography`.
  **Open: define the inference.** `--fragment` alone cannot mean deferred --
  `thesis-chapter-writer` emits a fragment a *thesis* `\input`s and its `.pdf`
  preview relies on citeproc (`thesis-chapter-writer/SKILL.md:630-634`). Candidate
  discriminator is an output directory under `content/rendered/<book>/` with a
  spec; verify it is available at that point in `render()`.
- **D2** `_citeproc.py:130` -- persist the **aliased** `.bib` into
  `content/rendered/<book>/`. Alias is mandatory: unaliased, `--natbib` emits
  `\citep[art\_2019]{tygesen_state}` for `tygesen_state---art_2019` -- a
  truncated key *and* a bogus optional argument. With `_alias_for`'s existing
  output the key survives whole.
- **D3** `_citeproc.py:142` -- a drop-References branch beside
  `_swap_manual_refs_for_citeproc`, reusing `references.section_start`/`section_end`.
  **Preserve the M-8 tail** (`:168-172`). Temp copy only, never the draft -- the
  authored `.md` is what `unit.state` digests, so editing it would flip every
  unit in the book to `stale:`.
- **D4** Skeleton -- `\usepackage[numbers,sort&compress]{natbib}`,
  `\bibliographystyle{IEEEtran}`, `\bibliography{<stem>}`, and
  `\addcontentsline{toc}{chapter}{Bibliography}` (book makes it `\chapter*`,
  invisible to the ToC).
- **D5** Skeleton + layout + `SKILL.md:170-179` +
  `docs/WRITE-A-BOOK.md:622-628` -- `citeproc-defs.def` is dead; no
  `CSLReferences` in deferred mode.
- **D6** `docs/WRITE-A-BOOK.md:645-653` -- two passes become pdflatex, bibtex,
  pdflatex, pdflatex.
- **D7** `docs/WRITE-A-BOOK.md:656-670` -- the ``Citation `x' on page`` log check
  goes from vestigial to load-bearing.
- **D8** `SKILL.md:86-96` -- "no bibliography at the end, and no `natbib`,
  `bibtex` or `biber`" inverts.
- **D9** `scripts/install_full_pipeline.sh:222-225` -- "natbib is deliberately not
  preferred" inverts; `[numbers]` + `IEEEtran.bst` is IEEE numeric. Note the
  script already installs bibtex and IEEEtran.bst *for exactly this* (`:213-215`).
- **D10** `_pandoc.py:117-130` -- the comment promising a fragment "carries its
  own IEEE reference list rather than deferring to a bibliography at the end
  of the book" is the sentence this falsifies.
- **D11** `render_output/__init__.py:35`, `_citeproc.py:81` -- docstrings state
  the swap as unconditional.
- **D12** Test: `\bibliography{refs}` is invisible to `_LATEX_INCLUDE_RE`
  (`\input`/`\include` only), so the `.bib`'s corpus-wide keys do not flood the
  `appeared` direction.
- **D13** Document: never point `draft gate` at a fragment -- `-x2d-` aliases are
  not ledger keys and would FAIL the one gate in this project.
- **D14** **Normalisation: no code.** Brace-protected acronyms make `ieee.csl` and
  `IEEEtran.bst` byte-identical (verified). Unbraced, IEEEtran lowercases them:
  `"A Survey of IoT and AI ..."` renders as `"a survey of iot and ai ..."` while
  CSL preserves `IoT`/`AI`. So this is source hygiene, not an implementation
  divergence. Two doc items and one fixture rule:
  - `docs/WRITE-A-BOOK.md` + corpus-sync docs: acronyms in `bibliography.bib`
    titles must be brace-protected (`{IoT}`, `{FMI}`). Standard BibTeX practice,
    newly load-bearing because bibtex is now in the render path.
  - Drift-guard test: render a fixed sample via both and assert the lists match.
    The fixture **must** use braced acronyms, or it pins mangled output as expected.
  - Do **not** build acronym detection or a warning check. Brace-protection
    makes both unnecessary.

**Exposure to flag:** the real `bibliography.bib` was never required to brace
acronyms, because citeproc handles unbraced ones correctly. Every unbraced
acronym becomes visible in the first assembled book's bibliography. Whether to
sweep the corpus is a separate call.

## E. Cross-cutting

- **Genre skills: no change.** Their References step stays correct for a
  standalone draft; the behaviour forks at render time.
  `thesis-chapter-writer/SKILL.md:629-634` already decided this exact case for a
  thesis, for the same reason.
- `tests/test_skill_book_assembly.py` pins skill content -- expect it red across
  A, C and D.
- Check whether the inferred mode touches PACKAGING.md's test-enforced command
  table (a subcommand would; an inferred mode should not).
- Per PR: version bump, the four-command lint set plus markdownlint, 100% coverage.
- A worktree needs `cp config.toml.example config.toml` before its first test run.

## Sequencing

Two PRs, **sequential off main**. Stacking gets zero CI -- `ci.yml` filters on
`base=main`.

1. **A + B + C** -- layout, the union fix, preamble/numbering/ToC.
2. **D** -- the bibliography. Depends on A: it adds the `.bib` to, and removes
   `citeproc-defs.def` from, the rendered layout.
