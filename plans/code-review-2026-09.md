# 🔍 Whole-tree code review, 2026-09: findings and improvements

Status: **point-in-time record.** Written 2026-09-01, against
`main` at 51a012eb (version 6.53.2). Findings are transcribed here
once; the issues opened from them (the map at the end of this file)
are the live copies, and this file is allowed to go stale the way
every file in `plans/` is -- see [plans/README.md](README.md).

**Written for** whoever works one of these findings, and for the next
whole-tree review to diff against.

**Assumed:** the review conventions in
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md) and the
"what is not debt" table in
[docs/TECHNICAL-DEBT.md](../docs/TECHNICAL-DEBT.md) -- every deliberate
convention listed there was filtered out before a finding was recorded,
so nothing below is a registered ratchet offender, a rationale comment,
a documented broad `except`, or any other recorded decision re-reported
as a defect.

**Not covered here:** `content/` and `papers/` (the user's drafts and
bibliography, not this repository's code), `.claude/skills/` prose, and
`docker/` (still unbuilt in any environment this project has run in --
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) already records it as a
draft to validate, and re-finding that is not a finding).

## 🔬 Method

Eight parallel reviewers, one per architectural cluster, each reading
every file in its cluster in full and verifying each candidate finding
against the code -- several by executing the suspect path -- before
reporting it: corpus/ledger, retrieval/references, overlap/verbatim,
style/review-aids, draft/dossier/citation-gate, enrich/pdf_text,
render_output/infra, and scripts/CI/tests/bench. The full suite was
run first in the review worktree as a baseline: 16 failed / 4249
passed / 5 skipped, all 16 the known environmental worktree failures.
The two critical findings below were then re-verified independently
against the source before this file was written.

Severity means what it changes, not how big the fix is: **critical** =
defeats the project's core guarantee or silently loses corpus data;
**major** = wrong or silently incomplete output on realistic input;
**minor** = robustness, performance, drift or dead-code cost with a
bounded blast radius.

## 📊 Summary

| Severity | Count | Where they cluster |
| --- | --- | --- |
| Critical | 2 | The citation gate's code-blanking on `.tex`; the sync state machine's `discovered` state |
| Major | 24 | Gate regex gaps; tier-3 verbatim seams; silent-partial reports; the enrich pool re-deriving what `sync_pool` already solved |
| Minor | ~55 | Unguarded JSON/TOML reads; IEEE formatter edge cases; probes that lie; config getters that silently default |

The single strongest pattern: **reports that silently say less, or
other, than they measured.** It recurs in every layer -- the gate
reading "0 citations, OK" through a blanking bug, sync exiting 0 on a
suspicious bib, tier 3 declaring "checked against all three tiers"
after scanning one section, `render` discarding pandoc's warnings,
vale errors parsing as "no findings". Each is individually small; the
class is the project's own named worst failure, and it is the axis to
prioritise on.

## 🚨 Critical

| # | Where | Defect | Improvement |
| --- | --- | --- | --- |
| C-1 | `chitragupta/citation_gate.py:94` | `_INLINE_CODE_RE` is applied to LaTeX input, where a backtick is an open-quote character: the span between two ` `` ` open-quotes on one line matches as "inline code" and is blanked, and any `\citep{...}` inside it vanishes. Verified: a sentence that LaTeX-quotes two phrases (double-backtick openers) with `\citep{fabricated2024}` between them extracts zero citekeys -- the gate prints OK and a fabricated citekey ships. The same blanking also silently drops those citations from `sections.md` derivation and `unit accept`'s recorded citekeys | Skip Markdown inline-code blanking for `.tex` input (thread the suffix into `_blank_code`/`check_document`), and pin a regression test with a LaTeX-quoted sentence citing a key |
| C-2 | `chitragupta/ledger_upsert.py:275-282` | A row at status `discovered` with an unchanged PDF is never scheduled for parsing again -- `_next_status` retries only `parsed`-with-missing-outputs and transient `parse_failed`. Every path that separates upsert from parse (backend unavailable, Ctrl+C or crash between upsert and result recording) strands the document: the next healthy run reports it "unchanged" and exits 0, and the paper is permanently invisible to retrieval. The function's own docstring names this exact failure class -- it was fixed for `parse_failed` and missed for `discovered` | Add `old_status == "discovered"` (with a PDF present) to the re-parse branch, with a two-run regression test: strand a row at `discovered`, re-sync, assert it parses |

## 🔥 Major

### The citation gate (three more false-negative paths, one false positive)

| # | Where | Defect | Improvement |
| --- | --- | --- | --- |
| M-1 | `chitragupta/citation_gate.py:63-65` | Biblatex multicite commands (`\cites{a}{b}`, `\parencites`, ...) capture only the first brace group; the second key passes the gate unseen | Consume trailing brace groups and extract keys from each |
| M-2 | `chitragupta/citation_gate.py:80` | `_PANDOC_CITE_RE` requires a letter first character; Pandoc accepts digit/underscore-start keys, so `[@3dprinting_2020]` is invisible rather than unresolved | Widen the capture to `[A-Za-z0-9_][A-Za-z0-9_-]*` |
| M-3 | `chitragupta/citation_gate.py:93` | `_FENCED_CODE_RE` pairs every ` ``` ` token in document order regardless of line position: one stray triple-backtick in prose shifts the pairing, blanking following prose (citations pass unseen) and exposing code interiors | Anchor fences to line starts (`^[ \t]{0,3}` + `re.MULTILINE`), and add `~~~` fences while there (the false-positive half: a tilde-fenced `@dataclass` currently FAILs the gate and pushes the hook to mangle valid teaching code) |

### Silent-partial reports and swallowed diagnostics

| # | Where | Defect | Improvement |
| --- | --- | --- | --- |
| M-4 | `chitragupta/sync.py:247` | A sync against an empty/corrupt bib -- the state the code itself labels SUSPICIOUS -- still exits 0; the unattended caller's only API is the exit code. A later `--remove-stale` surfaces it as an uncaught `RuntimeError` traceback instead of a refusal | Exit nonzero on suspicious; catch the `prune_missing` error and print a refusal |
| M-5 | `chitragupta/ledger.py:171-184` + `chitragupta/ledger_upsert.py:213-237` | Neither the hash-change UPDATE nor `mark_parse_failed` clears `parsed_path`, and `retrieval.py:_full_text` reads it regardless of status -- a changed-then-unparseable PDF keeps serving the *previous* version's text as current | NULL `parsed_path` on parse-fail/hash-change, or require `status == 'parsed'` in `_full_text` as `overlap_index_ledger` already does |
| M-6 | `chitragupta/sync_pool.py:130-141` | The stall watchdog cannot stop the default `pdftotext` backend: `terminate_workers` is a thread-pool no-op and the stall path never cancels queued futures -- jobs recorded as failures keep running and writing parsed text the ledger says failed | `shutdown(wait=False, cancel_futures=True)` in the stall branch; kill in-flight subprocesses or document the watchdog as docling-only |
| M-7 | `chitragupta/render_output/__init__.py:303` | `subprocess.run(capture_output=True)` discards pandoc's stderr on exit 0 -- citeproc's "citation not found" and missing-image warnings are thrown away on the success path | Forward `result.stderr` to the caller's stderr, prefixed |
| M-8 | `chitragupta/render_output/_citeproc.py:163-168` | The citeproc temp copy is truncated at the References heading: an appendix or acknowledgments after `## References` silently vanishes from tex/pdf/docx output while the md path keeps it | Re-append the remainder after the entries block, or warn. Same section-extent family as m-33 and M-15 |
| M-9 | `chitragupta/style_check.py:162-180` | `run_vale` never inspects returncode/stderr: vale's own errors parse as zero findings, and `cwd=PROJECT_ROOT` plus a caller-relative path makes vale silently check nothing while Python-side checks succeed | Resolve the draft path before the argv; raise `MissingBinary` on nonzero exit with empty stdout |
| M-10 | `chitragupta/review/_citekey_union_includes.py:117-120` | An include whose stem is a unit id is marked "included" before existence is checked -- a renamed/deleted chapter file still reports "Lost in assembly: none", the exact silent loss the aid exists to catch | Resolve unit-stem includes too; report resolution failures in `unread` |
| M-11 | `chitragupta/review/citation_provenance.py:118-121` | `_sentence_around` matches citekeys by bare substring, so `smith2020` matches the sentence citing `smith2020a` -- provenance and the NLI support aid score the wrong claim, and the agenda files a mis-keyed item | Match the delimited citation form (`@key` + boundary), or membership-test via `extract_citekeys_from_line`. Same family as m-52 |
| M-12 | `chitragupta/review/quotation.py:94` | `build_report` calls `dossier_dir` bare; a draft under `content/` but outside `content/drafts/` -- which the layer's contract supports -- gets a `DossierError` traceback instead of the empty report every sibling aid degrades to | Catch `DossierError` and return an empty report, matching `_read_drift` |
| M-13 | `chitragupta/evidence_appendix.py:230` | `--output-dir`'s help promises confinement to `content/` but `emit()`/`write()` never check -- the verbatim-quote sidecar (the one artifact `.gitignore` exists to contain) writes anywhere on the filesystem | Refuse via `config.resolves_inside(out_dir, CONTENT_DIR)`, mirroring `render_output._target_dir` |

### Tier-3 verbatim detection and the remediation loop

| # | Where | Defect | Improvement |
| --- | --- | --- | --- |
| M-14 | `chitragupta/review/verbatim_check/_embed.py:91` + `_scan.py:124-134` | The per-section alignment cap runs *before* the dedupe against tier-1/2 findings, so a section that quotes verbatim and also paraphrases loses the real paraphrase: the cap keeps the verbatim passage's alignment, the dedupe then drops it, and the paraphrase was already discarded | Filter alignments against exact+skip-gram spans before `overlap_embed.report()` applies its cap |
| M-15 | `chitragupta/overlap_segments.py:154-157` + `_embed.py:58-76` | A draft heading not found in `sections.md` is silently skipped, and `not_run` fires only at zero matches -- a draft with 9 of 10 headings renamed scans one section while the report claims all three tiers checked everything | Diff recorded sections against matched titles and surface the unmatched count |
| M-16 | `chitragupta/overlap_chroma.py:86, 173-174` | Chroma freshness is never checked against the corpus: a cited source with no chunks ranks last and is cut by the shortlist cap with no signal -- tier 3 never aligns against the one source added since enrich last ran | Detect citekeys absent from the collection; shortlist them ahead of the cap or report "N cited sources not embedded" |
| M-17 | `chitragupta/review/verbatim_check/_recheck.py:53-56` + `_baseline.py` | `objective()` counts embedding-tier findings and the baseline never records `tiers_not_run` or the embedding model -- the "deterministic half of the remediation loop" inflates or deflates with tier availability, stalling the agenda-reviser's strictly-falling counter for reasons no edit caused | Exclude `tier == "embedding"` from `objective()`; record corpus key and `tiers_not_run` in the payload and warn/refuse on mismatch |

### The enrich pool re-deriving solved machinery

| # | Where | Defect | Improvement |
| --- | --- | --- | --- |
| M-18 | `chitragupta/enrich/_docling_pool.py:174` + `docling_parse.py:312` | The pool drains with `executor.map()` (input-order, no per-future error handling) and the cache save is not in a `finally` -- one OOM-killed worker discards every fingerprint from the run, including completed documents. `sync_pool.py:157-166` documents this exact hazard as the reason it does the opposite | `submit()` + `as_completed()`, per-future `BrokenProcessPool` handling, cache save in `finally` |
| M-19 | `chitragupta/enrich/_docling_pool.py:180` | The drain loop uses `except KeyboardInterrupt` instead of `pdf_text.interrupt_guard` -- the measured 60s+ interrupt path the guard exists to close, and a second Ctrl+C loses the cache entirely | Wrap the drain in `interrupt_guard`; save the cache incrementally |
| M-20 | `chitragupta/enrich/docling_parse.py:305-311` | The serial path emits no per-document progress line, and the pool prints in input order -- with biggest-first ordering, nothing prints until the largest PDF finishes. This is the killed-at-399-of-501 convention (#50) verbatim | `say()` the `[i/n] citekey` line before the slow call; `as_completed` for the pool |
| M-21 | `chitragupta/pdf_text/_gpu.py:222` | `gpu_count()` returns 0 whenever `config.PARSER != "docling"`, but enrich always runs docling regardless -- on a multi-GPU pdftotext-configured host every enrich worker pins to `cuda:0`, the documented 12-workers-one-card pathology, with the full-card skip disabled | Parameterise docling-ness into `gpu_count`/`worker_ceiling` instead of gating on `config.PARSER` |
| M-22 | `chitragupta/enrich/_docling_pool.py:117` | `parse_one` fingerprints the PDF *after* parsing: a PDF replaced mid-parse records the new `(size, mtime_ns)` against text from the old bytes, served stale forever. The serial path stats before parsing and fails safe | Return the fingerprint `parse_doc` already stored in its cache dict |
| M-23 | `chitragupta/enrich/embed_index.py:197-246` | `build_index` never deletes: a citekey removed from the bib keeps its chunks in Chroma forever, so `search()` returns hits no draft may cite -- contradicting the docstring's stated invariant | Delete chunks whose citekey left the corpus at the end of `build_index`, and report the count |
| M-24 | `chitragupta/enrich/doc_vectors.py:22-30` | The embed cache is read with unguarded `json.loads` and written non-atomically -- a kill mid-save leaves torn JSON and every later topic run crashes until the file is hand-deleted, the exact failure the docling cache next door defends against | Copy the `_docling_cache` pattern: tolerate unreadable as empty, write tmp + `os.replace` |

### Everything else major

| # | Where | Defect | Improvement |
| --- | --- | --- | --- |
| M-25 | `chitragupta/porter_stemmer.py:208-232` | Steps 2-4 fall through to shorter suffixes when a matched suffix's condition fails; published Porter stops at the longest match (as this module's own `_step1b` does). Verified: "argument" → "argum", "agreement" → "agreem" -- and the test suite pins no `-ement` word, so the module's a-test-would-catch-it claim is false exactly here | Return at first suffix match; bump `overlap_skipgram._TOKENIZER_VERSION` per its coupling note; pin "argument"/"agreement" |
| M-26 | `chitragupta/render_output/_figure_captions.py:100-104` | Captions are interpolated raw into a `raw_tex` figure block -- neither markdown-processed nor LaTeX-escaped. `&` fails the compile, `%` silently truncates the rest of the caption including the label, and a caption citing `[@key]` reaches the PDF literally. The table path (`_tables._caption_for`) already does this right | Keep captions in pandoc-visible syntax and inject only the raw float wrapper, mirroring the table path |
| M-27 | `chitragupta/spec/__init__.py:154` | Chapter sign-off digests are computed over prose lines only, so an edit inside a fenced block of a signed chapter's brief does not move the digest -- `unit accept` proceeds against outline text no human signed | Digest the raw text slice between headings; use prose-lines only to locate them |
| M-28 | `chitragupta/dossier/_sections.py:55` + `_drift.py:257-259` | `_KEY` requires a separator character, so separator-free citekeys (`Knuth1984`) are invisible to every dossier parse -- a cited paper leaving the corpus is never reported in `drift().missing` | For the ledger-differencing paths, also accept backticked/`@` tokens that exactly equal a known ledger citekey |
| M-29 | `scripts/merge_pr.py:97-113` | `_bullets_in` does not track code fences: dash-bullet lines inside a fenced block in the PR description are scraped into the squash commit body verbatim, and checkbox lines under any non-template heading are scraped as content | Track fence state; drop bullets matching a checkbox shape |

## 📉 Minor

Grouped by theme; each row is one or more sites sharing a fix shape.

### Unguarded reads of hand-editable or interruptible files

| # | Where | Defect and improvement |
| --- | --- | --- |
| m-30 | `chitragupta/review/agenda/_sources.py:99` | One truncated aid sidecar JSON crashes the whole agenda with a traceback, against the module's own "degrade to absent" contract. Catch and return `AidSource(available=False)` with a reason |
| m-31 | `chitragupta/retrieval_cache.py:93-97` | A cache entry that is a dict with a matching fingerprint but missing `term_freqs`/`length` is reused and crashes every later `search()`. Validate the inner shape in the guard |
| m-32 | `chitragupta/acronyms.py:18-22,118`; `chitragupta/seed_topics.py:146-149` | User-editable TOML and stage-written JSON propagate raw `TOMLDecodeError`/`JSONDecodeError`/`AttributeError` tracebacks. Catch and refuse cleanly with the path named, as `seed_topics`' own other paths do |

### Section extent: "everything after the References heading"

| # | Where | Defect and improvement |
| --- | --- | --- |
| m-33 | `chitragupta/references.py:211-216, 252-255` | `numbered_markdown`/`apply` treat heading-to-EOF as the old section: real content after References is deleted on the next run, and the heading is rebuilt at level 2 regardless of the original. Splice to the next same-or-higher heading, or refuse |
| m-34 | `chitragupta/review/verbatim_check/_masking.py:56-60` | The scan mask blanks References-to-EOF, so an appendix after References is unscannable and reads clean. Bound the mask at the next same-or-higher heading |

One fix shape, three consumers (with M-8): the References section's
extent deserves one shared helper rather than three private guesses.

### Probes and reports that lie in the reassuring direction

| # | Where | Defect and improvement |
| --- | --- | --- |
| m-35 | `chitragupta/doctor.py:64-67` | The enrich-extra probe imports only `sentence_transformers` and reports the whole tier ok. Probe each of docling/bertopic/chromadb/sentence_transformers and name the missing ones |
| m-36 | `chitragupta/pdf_text/_converter.py:149-151` | A missing `status` attribute on a docling result is treated as success -- an upstream rename would silently write PARTIAL documents, inverting the check's purpose. Fail closed |
| m-37 | `chitragupta/init.py:189-195` | A `COPY_VERBATIM` source missing from the wheel copies nothing and exits 0 -- a scaffold without `.claude/` (so without the gate hook) reports success. Check each source exists before copying |
| m-38 | `chitragupta/hook_launchers.py:121-125` | Every hook program is probed with `-c "import chitragupta"` without checking it is a Python interpreter; a bash-launched hook would report a false fault every session (latent). Gate the probe on an interpreter-shaped basename |
| m-39 | `chitragupta/enrich/__main__.py:252` | `_run_stages` returns 0 even when every stage errored. Return nonzero when any stage status is `error` |
| m-40 | `chitragupta/enrich/docling_parse.py:100-102` | A missing docling module errors once per document ("partial") instead of one honest `skipped` naming the install step. Probe once in the stage |
| m-41 | `chitragupta/tldr.py:118-122` | `stale` compares `None != None` when the fingerprint cannot be computed at all and reports fresh, against the docstring's explicit contrary promise. Treat uncomputable as stale |
| m-42 | `chitragupta/passages.py:317-325,348` | A held single-page rung-3 result is discarded expecting rung 4; an absent PDF then yields `[]` with a false reason, and an empty rung-4 yields no reason at all. Fall back to the held result; give the empty case a reason |
| m-43 | `chitragupta/enrich/topic_converge.py:163` | With `topic_distribution` off, converge silently emits zero emergent topics and lists every paper uncovered. Synthesise single-membership rows or report the absence |

### Config and cache hygiene

| # | Where | Defect and improvement |
| --- | --- | --- |
| m-44 | `chitragupta/config.py:151-172,267-278` | `_get`/`_get_float`/`_get_bool` silently fall back to the default on a wrong-typed TOML value (`collapse_citations = "false"` means True), unlike the validated getters in the same file. Raise on present-but-wrong-typed |
| m-45 | `chitragupta/config.py` (seven sites) | Integer settings read as `int(_get_float(...))` truncate silently (`min_tokens = 0.5` → 0). Add `_get_int` rejecting non-integral values |
| m-46 | `chitragupta/enrich/_docling_cache.py:55-59` | Invalidation ignores `DOCLING_IMAGE_SCALE` though the worker's converter key includes it -- a scale change serves old bitmaps forever. Add scale to the payload check |
| m-47 | `chitragupta/enrich/topic_model.py:278-288` + `topic_converge.py` | `topics.json` records neither embedding model nor method, so converge pairs stale assignments with vectors from a different space silently. Record and check |
| m-48 | `chitragupta/enrich/embed_index.py:171-174` | The unchanged-doc skip compares only text hash; a corrected bib title never refreshes chunk metadata. Include the title in the check |

### Small correctness edges

| # | Where | Defect and improvement |
| --- | --- | --- |
| m-49 | `chitragupta/references_ieee.py:58-68,136,160-166,71-74` | Four formatter edges: `and others` renders literally instead of "et al."; single-hyphen page ranges get `p.` and the wrong dash; `rstrip(".")` mangles titles ending in abbreviations; the venue-order comment says the opposite of what the order does. Fix each; they are one test module apart |
| m-50 | `chitragupta/references_renumber.py:89-94` | `[@doe2020, p. 33]` fails the group regex and renders nested `[[1], p. 33]`. Extend the group regex with an optional preserved locator |
| m-51 | `chitragupta/bib_reader.py:76-83` | `split(" and ")` misses line-wrapped author separators (bibtexparser preserves newlines): two authors collapse into one mangled name silently. Split on `\s+and\s+` |
| m-52 | `chitragupta/review/verbatim_check/_corpus.py:122` | `sentences_citing` matches citekeys by substring: `overlap` mode scans paragraphs citing a suffixed sibling key. Match delimited forms (family of M-11) |
| m-53 | `chitragupta/review/verbatim_check/_overlap.py:59` | `cmd_overlap` deletes citation markers instead of blanking, welding adjacent tokens -- the defect `_tokenize_draft`'s docstring records fixing for `scan`, still live here. Substitute a space |
| m-54 | `chitragupta/review/verbatim_check/_masking.py:23` | An unpaired straight quote opens a "quoted" span to the next quotation's opener, demoting real findings between them to the quoted bucket. Bound spans at paragraph breaks |
| m-55 | `chitragupta/overlap_segments.py:164` | `line_starts[section.start]` raises `IndexError` when a citekeyed heading is the last line with no trailing newline. Guard as `end` already is |
| m-56 | `chitragupta/render_output/_math.py:264-301` | The inline-span pass and its warnings run over fence bodies, rewriting `` `tau` `` to `$\tau$` inside code blocks. Mask fences first, as the neighbouring comment claims |
| m-57 | `chitragupta/render_output/_equation_captions.py:128-154` | Duplicate equation ids number last-wins (both render "Equation 2") where the table path numbers by position. Number positionally |
| m-58 | `chitragupta/render_output/_assets.py:16,48-55` | Image paths with spaces or `%20` are never copied beside the tex output, which then fails to compile standalone. Match bracketed targets; unquote before resolving |
| m-59 | `chitragupta/render_output/_figure_captions.py:42-45` | Any non-blank line under a `figure:` marker is taken as the caption -- a missing blank line silently moves a prose sentence into the caption. Warn when the "caption" has a non-blank continuation |
| m-60 | `chitragupta/render_output/_cli.py:185-194` | A bare `except KeyError` around the whole pipeline reports genuine bugs as `[error] somekey`. Raise and catch a dedicated missing-citekey exception |
| m-61 | `chitragupta/review/citation_coverage.py:74-78` | Per-line extraction inherits both gaps the gate's docstring documents (fenced `@key` reads cited; wrapped `\citep` missed); whole-text `extract_citekeys` is strictly simpler and correct. Use it |
| m-62 | `chitragupta/review/_claims.py:206-214` | Every sentence in a block carries the block's first line, misdirecting findings by up to the block length. Map each sentence to its own line from existing offsets |
| m-63 | `chitragupta/spec/_signoff.py:24` vs `spec/__init__.py:72` | The sign-off writer accepts chapter ids with `:` but its own reader cannot re-parse them -- `ch:intro` signs off yet stays unsigned forever. Make writer and reader agree |
| m-64 | `chitragupta/dossier/_outline.py:27` | `_HEADING` accepts `#` though the contract is `##`-or-deeper: a title line becomes a phantom failing section. `#{2,6}` |
| m-65 | `chitragupta/dossier/_citekeys.py:200-213` | Duplicate evidence blocks for one key silently keep only the last. Keep the first and report |
| m-66 | `chitragupta/dossier/_draft_fingerprint.py:148` | `_math_desync` filters on another module's message wording; a rewording silently empties the check. Expose a structured kind |
| m-67 | `chitragupta/entailment.py:74` | Label lookup is case-sensitive with no default: a configured checkpoint with `ENTAILMENT`/`LABEL_n` labels raises bare `StopIteration`. Match case-insensitively and raise a named error |
| m-68 | `chitragupta/dedup.py:53-56` | Missing titles default to "Untitled" and punctuation-only titles normalise to empty, flagging unrelated entries as duplicates every run. Skip empty-normalised buckets |
| m-69 | `chitragupta/unit/_cli.py:66-97` | `unit accept --source` records claimed grounding citekeys into the permanent record unchecked against the ledger; and the gate-then-re-read at :88-94 hashes text the gate never saw. Validate sources; read once |
| m-70 | `chitragupta/review/figure_layout/_probe.py:34-39` | pdflatex wraps log lines at ~79 chars, so long node names silently fail the CGBOX parse and report "declared but not measured". Set `max_print_line` in the subprocess env |
| m-91 | `chitragupta/review/verbatim_check/_corpus.py:97-103` | `pages()` runs pdftotext with `check=True` and no handler: a poppler-less host or corrupt PDF gives `verbatim locate` a traceback instead of the parsed-text fallback the no-PDF branch already has. Catch and fall through |
| m-71 | `chitragupta/ledger_upsert.py:46-48` | An uncaught `OSError` on a PDF moved mid-sync aborts the whole run with a traceback -- the sibling pool helper already catches this race. Catch and treat as no-PDF this run |
| m-72 | `chitragupta/ledger_cli.py:90` | The read-only inspector connects with `timeout=0` and dies if a read lands in one of sync's per-document commit windows -- against its stated purpose. Use a small timeout |
| m-73 | `chitragupta/style_check.py:225-233` | An agenda run on an unrecorded-dialect draft pays three vale subprocess runs for a proposal the agenda never surfaces. Add a `propose=False` knob for the agenda path |

### Performance with measured or structural impact

| # | Where | Defect and improvement |
| --- | --- | --- |
| m-74 | `chitragupta/retrieval_cache.py:44-53` | Every `search()` re-parses the whole index (14 MB live) and rewrites it on any change, multiplied by parallel subagents. Memoize per process on `(size, mtime_ns)` |
| m-75 | `chitragupta/ledger_upsert.py:238` | One fsync'd commit per reference, every reference rewritten every run (`last_synced`): a no-op sync is ~646 write transactions. Batch-commit at the caller |
| m-76 | `chitragupta/overlap_segments.py:272` | `word_chars` rebuilt per sentence: O(words × sentences) before any embedding. Hoist |
| m-77 | `chitragupta/style_tables.py:86-94` | Per-table re-`splitlines` of the whole document, O(document) per table on the 178k-word book. Hoist one split |
| m-78 | `chitragupta/enrich/_docling_pool.py:162` | The quadratic whole-dataclass membership scan the sibling comment explicitly forbids, four lines away. Use a citekey set |
| m-79 | `chitragupta/overlap_embed.py:151` | Tier 3 opens a *writer* ledger connection (mkdir, migrations, commits) in a read-only layer and never closes it -- it can contend with a live sync's lock. Connect `mode=ro` and close, as `_ledger_connect_ro` does |
| m-80 | `chitragupta/enrich/topic_labels.py:123` | `author_names` leaks a connection per labelled run when it owns one. Use the context manager |
| m-81 | `chitragupta/ledger.py:269-273` | `all_items` clobbers the connection-wide row factory and resets it to `None`, not the prior value, with no `finally`. Use a cursor-level factory |

### Retrieval design, tooling and drift

| # | Where | Defect and improvement |
| --- | --- | --- |
| m-82 | `chitragupta/retrieval.py:90-91` | 1-2 character tokens are dropped on both index and query sides: "AI", "ML", "5G" can never rank, and an all-acronym query returns `[]` silently. Lower the bound with a schema bump, or warn on lost query terms |
| m-83 | `.pylintrc:6-10,90` | The header still says "NOT ENFORCED YET. No CI job runs this" and cites a since-renamed section; `py-version=3.10` vs the project's `^3.12`. Rewrite the header; bump py-version |
| m-84 | `.github/workflows/docs.yml:16-19` | `tags-ignore` under a `branches:`-filtered push trigger re-enables tag builds for non-`v*` tags -- the opposite of the semantics ci.yml's own header documents. Delete the block |
| m-85 | `scripts/install_full_pipeline.sh:466-468` | `ensure_gpu_torch` reinstalls torch unpinned from the CUDA index while its documented mirror pins deliberately. Pin to the installed version |
| m-86 | `scripts/install_full_pipeline.sh:223-224,249-253` | Two load-bearing comments are now false (vale is no longer the only external download; `install_vale` is reached from `os-deps`, so a checksum mismatch fails the test leg too). Correct both |
| m-87 | `.github/workflows/ci.yml:97-103,180-185` | The venv cache lineage plus `poetry install` without `--sync` keeps lock-removed packages importable in CI forever while clean installs break. Drop `restore-keys` or add `--sync` (minding the cpu-torch swap) |
| m-88 | `tests/test_enrich_embed_index.py:24-119` and sibling | chromadb/sentence-transformers are faked even on the CI leg where the real stack is installed; drift is caught only by a manual smoke step. Add one self-skipping integration module driving the real libraries |
| m-89 | dead code | `dossier/_retrieval.py:164` (`retrieval_cost`, still re-exported), `unit/__init__.py:302` (`sections`), `overlap_index_query.py:16` (`pages_for_gram`): no production callers (verified). Delist in a housekeeping PR, per the surgical-changes rule |
| m-90 | `chitragupta/review/citation_provenance.py:216-229` | `write_report` is called only by tests; `run()` re-implements it inline. Converge on one call path |

## 🧵 Cross-cutting themes

1. **Silent partiality is the recurring failure**, not wrong
   computation. The arithmetic (BM25, gap analysis, rolling hashes,
   offset tracking) survived adversarial review everywhere; what fails
   is the report *around* it claiming more coverage than the run had.
2. **Second implementations regress solved problems.** The enrich pool
   re-derived four hazards `sync_pool` already closed (M-18 to M-22);
   figure captions re-derived what table captions solved (M-26);
   `cmd_overlap` kept the token-welding bug `scan` fixed (m-53). When
   a hazard is closed in one place, the close belongs in a shared
   helper or a named convention, not a comment the next copy skips.
3. **The prose-pinning machinery covers `docs/` but not dotfile
   headers, shell comments, or cross-module message coupling** --
   which is exactly where m-83, m-86 and m-66 live.
4. **Validation is split with no stated principle**: config getters,
   JSON cache readers and subprocess boundaries each exist in both a
   loudly-validated and a silently-defaulting variant. Converging each
   pair on the validated one is cheap and closes a dozen minors.

## 🎫 Issue map

Every finding above is tracked by exactly one of these issues; a
finding id appears in its issue's body, and each issue is scoped to
what one coherent PR could close.

| Issue | Findings |
| --- | --- |
| [#487](https://github.com/prasadtalasila/chitragupta/issues/487) | C-1, M-1, M-2, M-3, m-61 |
| [#488](https://github.com/prasadtalasila/chitragupta/issues/488) | C-2 |
| [#489](https://github.com/prasadtalasila/chitragupta/issues/489) | M-4 |
| [#490](https://github.com/prasadtalasila/chitragupta/issues/490) | M-5 |
| [#491](https://github.com/prasadtalasila/chitragupta/issues/491) | M-6 |
| [#492](https://github.com/prasadtalasila/chitragupta/issues/492) | M-8, m-33, m-34 |
| [#493](https://github.com/prasadtalasila/chitragupta/issues/493) | M-7, m-56, m-57, m-58, m-59, m-60 |
| [#494](https://github.com/prasadtalasila/chitragupta/issues/494) | M-26 |
| [#495](https://github.com/prasadtalasila/chitragupta/issues/495) | M-9, m-73 |
| [#496](https://github.com/prasadtalasila/chitragupta/issues/496) | M-12, m-30, M-10, m-62, m-70 |
| [#497](https://github.com/prasadtalasila/chitragupta/issues/497) | M-11, m-52 |
| [#498](https://github.com/prasadtalasila/chitragupta/issues/498) | M-13 |
| [#499](https://github.com/prasadtalasila/chitragupta/issues/499) | M-14, M-15, M-16 |
| [#500](https://github.com/prasadtalasila/chitragupta/issues/500) | M-17 |
| [#501](https://github.com/prasadtalasila/chitragupta/issues/501) | M-18, M-19, M-20, M-22, m-78 |
| [#502](https://github.com/prasadtalasila/chitragupta/issues/502) | M-21 |
| [#503](https://github.com/prasadtalasila/chitragupta/issues/503) | M-23, m-48 |
| [#504](https://github.com/prasadtalasila/chitragupta/issues/504) | M-24, m-31, m-32, m-46, m-47 |
| [#505](https://github.com/prasadtalasila/chitragupta/issues/505) | M-25 |
| [#506](https://github.com/prasadtalasila/chitragupta/issues/506) | M-27, M-28, m-63, m-64, m-65, m-66, m-69 |
| [#507](https://github.com/prasadtalasila/chitragupta/issues/507) | M-29 |
| [#508](https://github.com/prasadtalasila/chitragupta/issues/508) | m-49, m-50, m-51, m-68 |
| [#509](https://github.com/prasadtalasila/chitragupta/issues/509) | m-35 to m-43 |
| [#510](https://github.com/prasadtalasila/chitragupta/issues/510) | m-44, m-45 |
| [#511](https://github.com/prasadtalasila/chitragupta/issues/511) | m-74, m-75, m-76, m-77, m-80, m-81 |
| [#512](https://github.com/prasadtalasila/chitragupta/issues/512) | m-83 to m-87 |
| [#513](https://github.com/prasadtalasila/chitragupta/issues/513) | m-82 |
| [#514](https://github.com/prasadtalasila/chitragupta/issues/514) | m-88 |
| [#515](https://github.com/prasadtalasila/chitragupta/issues/515) | m-89, m-90 |
| [#516](https://github.com/prasadtalasila/chitragupta/issues/516) | m-53, m-54, m-55, m-79, m-91 |
| [#550](https://github.com/prasadtalasila/chitragupta/issues/550) | m-71, m-72 |
| [#551](https://github.com/prasadtalasila/chitragupta/issues/551) | m-67 |

## ✅ What was reviewed and found sound

Recorded so the next review does not re-litigate it: the exact and
skip-gram overlap tiers (no false-negative found in either); the
retrieval cache's invalidation and atomic-write discipline; the
sentence splitter; the renumbering offset arithmetic; BM25; the
runlock; the ledger migration scheme; `check_version_bump`'s
main-not-tags comparison and PyPI three-state logic; `release.py`'s
packaging; `release.yml`'s tag verification and PyPI gating;
SHA-pinned actions and clean secrets handling; the bench self-check
convention (23 of 25 scripts, both exceptions reasoned in
`bench/README.md`); and the deliberate decisions in
[docs/TECHNICAL-DEBT.md](../docs/TECHNICAL-DEBT.md)'s "what is not
debt" table, all of which were confirmed as stated rather than
re-flagged.
