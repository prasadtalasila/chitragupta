"""Plagiarism / page-locator helper for reviewing a draft.

One of the three aids in the **review layer**, with
src/review/citation_provenance.py and src/review/citation_coverage.py --
run by hand on a finished draft, never automatically, never a gate, and
never holding the write lock. src/review/__init__.py owns where a written
report goes (`content/review/<topic>/<stem>.verbatim.md`, mirroring the
draft's path) and what its header looks like.

Reached through the layer's single entry point, src/review/__main__.py,
never as `python -m src.review.verbatim_check`: this module has no
__main__ block of its own, so that invocation would import it and exit 0
without doing anything. See docs/ARCHITECTURE.md on why every layer's
command surface stays one level deep.

Four modes:
    python -m src.review verbatim overlap <draft.md> <citekey> [--n 8]
        report the longest verbatim word-n-gram runs shared between the
        draft's sentences citing <citekey> and that source's parsed text.

    python -m src.review verbatim scan <draft.md> [--min-run 8] [--gap 1]
                                       [--limit N] [--json]
                                       [--write] [--formats md,tex,pdf]
        slide the WHOLE draft across the WHOLE corpus index (src/overlap_index.py),
        not just the sources a paragraph happens to cite -- catches verbatim
        reuse from an uncited source, and reuse in connective prose that
        cites nothing at all. Prints by default; --write also files the
        report under content/review/, beside the same draft's provenance
        and coverage reports. --json prints the same findings as data
        instead of as text, and --write files that too, as the report's
        `.json` sibling -- see `scan_payload`.

    python -m src.review verbatim recheck <draft.md> --baseline <scan.json>
                                          [--json]
        re-scan the draft at the baseline's own floor and report which of
        its findings are gone, which remain, and which the edits
        introduced. The deterministic half of #129's remediation loop:
        "did this rewrite fix the finding without breaking anything else"
        is an acceptance test, and one a model should not be deciding by
        reading two reports side by side. Still not a gate -- it exits 0
        whatever it finds, and `python -m src.draft gate` remains the only
        thing in this pipeline that blocks.

    python -m src.review verbatim locate <citekey> "<phrase>" [more phrases...]
        report which PDF page each phrase (or its distinctive words)
        appears on, for fact-checking page numbers.

Exits 0 on every successful invocation, findings or not -- a review aid,
not a gate. A draft this layer will not read (missing, or outside
content/) exits 1; a malformed invocation exits 2, the usual CLI-usage
error, not a verdict.
"""

import argparse
import bisect
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from src import citation_gate, config, overlap_index, references, review

BIB = config.BIB_FILE_PATH
PARSED_DIR = config.PARSED_DIR


def bib_entry(citekey):
    if not BIB.exists():
        # papers/bibliography.bib is gitignored, per-host data (see
        # AGENTS.md) -- absent on a fresh clone/CI checkout until someone
        # exports their own. Treat that the same as "citekey not in the
        # bib file" rather than crashing on a raw FileNotFoundError.
        return ""
    text = BIB.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"@\w+\{" + re.escape(citekey) + r",", text)
    if not m:
        return ""
    # Brace-match to the entry's real end rather than stopping at the
    # first "\n}": that sequence occurs *inside* multi-line field values
    # too (an `annote` holding a URL list is the common case here), which
    # truncated the entry mid-way and hid every field after it --
    # including `file`, so 40 papers looked like they had no PDF at all.
    depth = 0
    for i in range(text.index("{", m.start()), len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[m.start():i + 1]
    return text[m.start():]  # unbalanced braces: hand back what we have


def pdf_path(citekey):
    """The `file` field's attachment format is `Desc:path:mimetype`,
    `;`-separated per attachment -- the same shape src.bib_reader
    parses, and it must be split the same way here.

    Splitting on ':' and taking the first segment that merely *ends in*
    `.pdf` picks the human-readable description, not the path: this
    project's export writes both, as
    `Smith - 2024 - Title.pdf:pdfs/21/Smith - 2024 - Title.pdf:application/pdf`.
    Those two coincide only when the attachment sits directly beside the
    .bib, so the mistake was invisible in a flat fixture directory and
    silently lost 196 of 501 real PDFs -- `locate`/`overlap` then fell
    back to parsed text and reported page 1 for everything.
    """
    entry = bib_entry(citekey)
    m = re.search(r"file = \{(.*?)\},", entry, re.S)
    if not m:
        return None
    # Anchor a relative attachment path to the bib file's own directory,
    # matching src.bib_reader._resolve_pdf_path -- not REPO, which is
    # wrong the moment BIB_FILE points somewhere outside the checked-out
    # repo (a relative path in the file field is only ever relative to
    # wherever the .bib itself lives).
    bib_dir = BIB.resolve().parent
    for attachment in m.group(1).split(";"):
        parts = attachment.split(":")
        if len(parts) < 3:
            continue
        if "pdf" not in parts[-1].lower():
            continue
        p = Path(":".join(parts[1:-1]).strip())
        if not p.is_absolute():
            p = bib_dir / p
        if p.is_file():
            return p
    return None


def pages(citekey):
    """Return list of page texts, 1-indexed by position+1 (PDF page order)."""
    p = pdf_path(citekey)
    if p is None:
        parsed = PARSED_DIR / f"{citekey}.txt"
        if not parsed.exists():
            return []
        # pdftotext leaves stray NUL/control bytes in some files, which
        # makes grep treat them as binary and report nothing. Strip them
        # so a false "no match" can't be mistaken for a real absence.
        raw = parsed.read_text(encoding="utf-8", errors="replace")
        return re.sub(r"[\x00-\x08\x0e-\x1f]", " ", raw).split("\f")
    out = subprocess.run(
        ["pdftotext", "-layout", str(p), "-"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.split("\f")


WORD = re.compile(r"[a-z0-9]+")


def norm(text):
    return WORD.findall(text.lower())


def sentences_citing(draft, citekey):
    """Whole paragraphs mentioning the citekey, not just the citing sentence.

    Paraphrased-but-uncited sentences sitting next to a citation are
    exactly where borrowed wording hides, so compare the whole
    paragraph against the source.
    """
    text = Path(draft).read_text(encoding="utf-8")
    paras = re.split(r"\n\s*\n", text)
    return [re.sub(r"\s+", " ", p) for p in paras if citekey in p]


def cmd_overlap(draft, citekey, n=8):
    """Verbatim word-n-gram overlap between `draft`'s paragraphs citing
    `citekey` and that source's corpus-layer parsed text (src/ledger.py's
    `parsed_path`) -- fingerprinted and cached by src/overlap_index.py, so
    a re-run over an unchanged source costs no re-fingerprinting.

    This reads the ledger's already-parsed text rather than re-invoking
    `pdftotext` on the PDF the way `pages()`/this function used to: for a
    citekey the ledger has actually parsed, that is the same text every
    other reader of this corpus sees (and the only text a `docling`-backed
    corpus has at all -- `pdftotext -layout` output never entered the
    ledger there). A citekey the ledger has not parsed reports "no source
    text", same as before.
    """
    item = overlap_index.ledger_item(citekey)
    if item is None:
        print(f"no source text for {citekey}")
        return
    pdf_hash, parsed_path = item
    grams = overlap_index.grams_for_citekey(citekey, pdf_hash, parsed_path, n)
    hits = []
    for s in sentences_citing(draft, citekey):
        w = norm(re.sub(r"\[@[^\]]+\]", "", s))
        draft_hashes = overlap_index.gram_hashes(w, n)
        run, runs = [], []
        for j, gh in enumerate(draft_hashes):
            if gh in grams:
                run.append((j, grams[gh]))
            else:
                if run:
                    runs.append(run)
                run = []
        if run:
            runs.append(run)
        for r in runs:
            start = r[0][0]
            length = r[-1][0] + n - start
            hits.append((length, r[0][1], " ".join(w[start:start + length]), s[:80]))
    hits.sort(reverse=True)
    if not hits:
        print(f"{citekey}: no verbatim run of >= {n} words found")
    for length, pg, frag, ctx in hits[:25]:
        print(f"  [{length} words, pdf p.{pg}] {frag}\n      in: {ctx}...")


# ---------------------------------------------------------------------
# scan: whole-draft x whole-corpus. See module docstring and issue #111
# for what this catches that `overlap` structurally cannot: verbatim
# reuse from a source the citing paragraph doesn't cite, and reuse in
# connective prose (introductions, transitions, summaries) that cites
# nothing at all -- `overlap` never looks at either, no matter how often
# it's run, because it only ever compares one citekey's cited paragraphs.
# ---------------------------------------------------------------------

# Straight or curly double-quoted spans, and Markdown blockquote lines --
# deliberately not cleverer than that (no nesting, no single quotes,
# which double as apostrophes and would flag most of the draft). Detecting
# *that* a run sits inside quote delimiters is a cheap, deterministic bit
# attached to a finding; whether that should downgrade severity (a
# legitimate page-anchored quotation vs. unmarked reuse) is Phase 2's
# policy call, not this one's.
_QUOTE_SPAN_RE = re.compile(r'["“]([^"”]{2,})["”]')


def _quote_char_spans(text):
    spans = [(m.start(), m.end()) for m in _QUOTE_SPAN_RE.finditer(text)]
    pos = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(">"):
            spans.append((pos, pos + len(line)))
        pos += len(line)
    return spans


def _char_in_spans(pos, spans):
    return any(start <= pos < end for start, end in spans)


def _mask_for_scan(text):
    """Code-fence/inline-code and References-section blanking, sharing
    the corpus's own masking discipline rather than reinventing it:
    `citation_gate._blank_code` is what keeps a Python `@dataclass` or a
    `\\citep{...}`-shaped code example from reading as a real citation,
    and the same false-positive shape applies here -- code prose is not
    draft prose. The References section is generated from bib metadata
    (titles, venues), so scanning it would flag every source's own title
    page as "verbatim overlap with itself".

    `references.section_start` is handed the *original* lines (its own
    contract -- it blanks internally just to find the heading) and
    returns an index into them; `_blank_code` never changes line count,
    so that index still lines up with the blanked text's lines.
    """
    original_lines = text.splitlines(keepends=True)
    idx = references.section_start(original_lines)
    lines = citation_gate._blank_code(text).splitlines(keepends=True)
    if idx is not None:
        lines = lines[:idx] + [re.sub(r"[^\n]", " ", line) for line in lines[idx:]]
    return "".join(lines)


@dataclass
class _DraftWord:
    text: str
    paragraph: int
    quoted: bool
    # Where this word sits in the *original* text handed to
    # `_tokenize_draft` -- not in the masked, marker-blanked, lowercased
    # stream `text` came out of. `original[char:char_end]` is the word as
    # written, casing and all, which is what a remediation loop needs to
    # hand `Edit` (#129). See `_lower_offsets` for why the two can differ
    # by more than case.
    char: int
    char_end: int


_PARA_SPLIT_RE = re.compile(r"\n\s*\n")
_CITE_MARKER_RE = re.compile(r"\[@[^\]]+\]")


def _paragraphs(text):
    """`(offset, paragraph)` for each paragraph of `text`, splitting where
    `re.split(r"\\n\\s*\\n", text)` splits and keeping the offset that
    split throws away.

    The offset is the half of the answer a caller that means to *edit*
    needs: without it a word's position is known only within its own
    paragraph, and every paragraph after the first is off by however much
    preceded it.
    """
    out = []
    pos = 0
    for m in _PARA_SPLIT_RE.finditer(text):
        out.append((pos, text[pos:m.start()]))
        pos = m.end()
    out.append((pos, text[pos:]))
    return out


def _lower_offsets(text):
    """`text.lower()`, plus -- when lowercasing moved anything -- the
    index in `text` of every character of that result.

    `str.lower()` is not length-preserving: `"İ"` lowercases to two code
    points, so every offset after one is shifted. Everything else in this
    masking chain preserves offsets deliberately
    (`citation_gate._blank_code` says as much in its own comment), and
    this is the one step that cannot, so it reports the shift instead of
    hiding it.

    The lowercasing itself has to stay. `src/overlap_index.py`
    fingerprints the corpus with `WORD.findall(text.lower())`; matching
    the draft case-insensitively instead would read `"İstanbul"` as one
    word where the corpus reads two, and the two sides would stop
    agreeing on what a word is -- which is the whole basis of a match.

    `None` rather than a range-mapping list for the overwhelmingly common
    case where lowercasing changed no lengths: it says "offsets are their
    own indices" once, instead of every caller carrying a list it would
    only ever index by identity.
    """
    lowered = text.lower()
    if len(lowered) == len(text):
        return lowered, None
    parts = []
    offsets = []
    for i, ch in enumerate(text):
        low = ch.lower()
        parts.append(low)
        offsets.extend([i] * len(low))
    # Rebuilt character by character rather than reusing `lowered`, so the
    # string actually searched is the one these offsets describe.
    return "".join(parts), offsets


def _original_index(offsets, i):
    return i if offsets is None else offsets[i]


def _blank_span(m):
    return re.sub(r"[^\n]", " ", m.group(0))


def _tokenize_draft(text):
    """Every word of `text` (masked, citation markers blanked) as a flat
    list across the whole draft, plus which citekeys each paragraph
    cites. Each word carries where it sits in `text` itself.

    Flat rather than paragraph-scoped: an n-gram window can cross a
    paragraph break in the word stream this produces, unlike `overlap`'s
    per-paragraph scan. That is a deliberate trade -- catching reuse in
    the (much more common) single-paragraph case matters more than the
    rare false-candidate an adjacent-paragraph seam could produce, and a
    real match still has to line up with actual corpus text to survive.

    **Blanked, not stripped.** The citation marker used to be deleted,
    which shifted every character after it and was one of the two reasons
    a finding could not be located in the file it came from (the other
    being the paragraph split; see `_paragraphs`). Blanking it with
    spaces is `_blank_code`'s existing discipline, applied to the one
    place in this module that still deleted. It also stops
    `twins[@key]matter` from welding into a single token, which deleting
    did.
    """
    masked = _mask_for_scan(text)
    words = []
    paragraph_citekeys = []
    for p_idx, (para_start, para) in enumerate(_paragraphs(masked)):
        paragraph_citekeys.append({key for _, key in citation_gate.extract_citekeys(para)})
        clean = _CITE_MARKER_RE.sub(_blank_span, para)
        quote_spans = _quote_char_spans(clean)
        lowered, offsets = _lower_offsets(clean)
        for m in WORD.finditer(lowered):
            start = _original_index(offsets, m.start())
            end = _original_index(offsets, m.end() - 1) + 1
            words.append(_DraftWord(
                m.group(0), p_idx, _char_in_spans(start, quote_spans),
                para_start + start, para_start + end,
            ))
    return words, paragraph_citekeys


def _merge_runs(positions, gap, n):
    """Sorted draft word-positions on one diagonal -> maximal runs,
    merging two anchors separated by at most `gap` non-matching *words*.

    Not `next_start - prev_start - 1 <= gap`: a single edited word inside
    an n-gram poisons every window that overlaps it, which is n-1
    consecutive anchor starts (7 for the default n=8), not 1 -- the last
    clean anchor before a one-word edit and the first clean one after it
    are n+1 anchor-starts apart, not 2. `gap` counts actual skipped
    words, so the comparison has to subtract `n`, not `1`, to recover
    that: `next_start - prev_start - n` is 1 for a genuine single-word
    edit, matching the "g=1 recovers a single edited word" the design
    (issue #111, scoping comment) asks for. Using `-1` here would demand
    gap>=7 to catch the exact same one-word edit -- silently far more
    permissive than whatever `--gap` value the caller actually chose.
    """
    positions = sorted(set(positions))
    runs = [[positions[0]]]
    for p in positions[1:]:
        if p - runs[-1][-1] - n <= gap:
            runs[-1].append(p)
        else:
            runs.append([p])
    return runs


# ---------------------------------------------------------------------
# allowlist: per-host boilerplate (acronyms, fixed phrasing, defined
# terms, whole paragraphs) this draft's owner has decided `scan` should
# never flag. config.VERBATIM_ALLOWLIST_PATH is gitignored, per-host
# data -- see docs/PLAGIARISM.md and config.py's own comment on it.
# ---------------------------------------------------------------------

_ALLOWLIST_KEYS = ("acronyms", "phrases", "definitions", "paragraphs")


def _load_allowlist_phrases():
    """Every phrase across the allowlist file's four categories,
    normalized into word tuples via `norm()` -- the same tokenization
    `scan` itself uses on the draft, so a phrase matches regardless of
    how it's capitalized or spaced in the file.

    No file -> no suppressions: the normal state for a fresh clone, since
    nothing ever commits this file (see config.VERBATIM_ALLOWLIST_PATH).
    A *present* file that isn't valid TOML, that this process cannot read
    (permissions, or the path is a directory), whose category isn't a
    list of strings, or that carries a key outside the four documented
    ones (a typo like `pharses`), raises ValueError rather than
    degrading to "no suppressions" -- a policy file that silently
    stopped suppressing is exactly the failure that surfaces months
    later as "why did this stop working," not as "no findings today."
    An unknown key is exactly that failure mode: without the check, a
    misspelled category loads as an empty list, no phrases suppress, and
    nothing says why. `run()` only catches `ValueError` as a usage error
    (`OSError` would otherwise escape as an unhandled traceback instead
    of the same clean exit 2), so both open() and parsing are wrapped.
    """
    path = config.VERBATIM_ALLOWLIST_PATH
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: malformed TOML -- {exc}") from None
    except OSError as exc:
        raise ValueError(f"{path}: cannot read allowlist -- {exc}") from None

    unknown = sorted(set(data) - set(_ALLOWLIST_KEYS))
    if unknown:
        raise ValueError(
            f"{path}: unknown key(s) {unknown} -- expected only "
            f"{list(_ALLOWLIST_KEYS)}"
        )

    phrases = []
    for key in _ALLOWLIST_KEYS:
        values = data.get(key, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(f"{path}: {key!r} must be a list of strings")
        phrases.extend(values)

    normalized = (tuple(norm(p)) for p in phrases)
    return [words for words in normalized if words]


def _mask_allowlisted(span_word_strs, allowlist_tuples):
    """Boolean mask, one entry per word in `span_word_strs`, True where
    that position is covered by a contiguous occurrence of any
    allowlisted phrase.

    A phrase can occur more than once in one span, and two allowlisted
    phrases can overlap (a whole paragraph allowlisted alongside a
    phrase that also appears inside it) -- ORing into one mask handles
    both without double-counting a word twice.
    """
    n = len(span_word_strs)
    masked = [False] * n
    for phrase in allowlist_tuples:
        length = len(phrase)
        if length == 0 or length > n:
            continue
        for i in range(n - length + 1):
            if tuple(span_word_strs[i:i + length]) == phrase:
                for j in range(i, i + length):
                    masked[j] = True
    return masked


def _newline_offsets(text):
    """Every newline's index in `text`, ascending -- one sweep, reused by
    every finding.

    `text.count("\\n", 0, char_start)` per finding is O(len(text)) each
    time, so a long draft with many findings pays for the whole file once
    per finding. `citation_gate.extract_citekeys` already computes its
    line numbers in a single forward pass rather than per match, for
    exactly this reason; this is that discipline applied here.
    """
    return [m.start() for m in re.finditer("\n", text)]


def _line_at(newlines, pos):
    """The 1-based line `pos` falls on, given `_newline_offsets`.

    `bisect_left`, so a newline character counts as ending the line it
    sits on rather than starting the next one -- the same convention
    `str.count("\\n", 0, pos)` had.
    """
    return bisect.bisect_left(newlines, pos) + 1


def finding_id(citekey, page, fragment):
    """A finding's name, stable across runs and across edits elsewhere in
    the draft. `page` is the run's start page (`scan_findings` passes
    `min(run_pages)`, not `end_page`) -- a run that merges differently on
    a later scan can land on a different start page and so get a
    different id, which is correct: the finding really did change.

    Deliberately position-free. `start` moves whenever anything above a
    finding is edited, so an identity built on it would rename every
    remaining finding the moment the first one was repaired, and nothing
    could then decide whether a given finding had survived a revision --
    which is the whole job (R2, docs/AUTO-IMPROVEMENT.md).

    Two identical runs from the same source page therefore share an id.
    `recheck` is written to understate progress in that case rather than
    overstate it: with two copies in the baseline and one repaired, the
    id is still present and the finding still reports as persisting.
    """
    digest = hashlib.sha256(f"{citekey}\x00{page}\x00{fragment}".encode())
    return digest.hexdigest()[:12]


def scan_findings(draft, min_run=None, gap=1, limit=None):
    """Slide `draft`'s whole normalized text across the corpus-wide index,
    grouping matches by `(citekey, diagonal)` and merging each group into
    maximal same-diagonal runs (see `_merge_runs`). Returns `(findings,
    min_run, suppressed)`, `findings` longest run first; `suppressed` is
    how many runs the allowlist (see `_load_allowlist_phrases`) dropped.
    This function never raises for "nothing found" and returns an empty
    list in that case -- this is a review aid, not a gate, and it is not
    wired into anything that treats a nonzero exit as a failure. It does
    raise `ValueError` for a request it cannot honor at all -- `min_run`
    below the corpus index's own n-gram size (see below), or a malformed
    allowlist file -- that is not "no findings", it is "this input can't
    be scanned as asked", and the `scan` CLI (below) turns it into the
    same stderr-plus-exit-2 usage error as its other malformed
    invocations, e.g. `--gap` with no value.

    A finding is dropped, not just flagged, when the allowlist accounts
    for enough of it that what's left would not itself have cleared
    `min_run` -- e.g. a run that is entirely one allowlisted standard's
    name. A run that merely *contains* a short allowlisted phrase inside
    a much longer otherwise-unexplained lift is kept: suppressing the
    whole thing would hide the real overlap the allowlist was never
    meant to excuse.

    A run can span a page break in the source: `src/overlap_index.py`'s
    `token_position` is a global offset into the document (#131), not
    reset per page, so `diagonal` (`src_pos - draft_pos`) stays constant
    across the boundary and the two halves merge into one run the same
    way a same-diagonal gap does. Each finding reports `page` and
    `end_page` -- equal for an ordinary single-page run, `end_page >
    page` for one that straddles a break -- rather than picking one side
    and losing the other.
    """
    if min_run is None:
        min_run = overlap_index.DEFAULT_N

    index = overlap_index.build_corpus_index()
    if min_run < index.n:
        raise ValueError(
            f"--min-run must be >= {index.n} (the corpus index's own n-gram "
            "size, src.overlap_index.DEFAULT_N) -- a shorter run cannot be "
            "detected without rebuilding the whole corpus index at a "
            "different n. Change the index's n, not this flag, if that is "
            "really what's needed."
        )

    text = Path(draft).read_text(encoding="utf-8")
    words, paragraph_citekeys = _tokenize_draft(text)
    word_strs = [w.text for w in words]
    newlines = _newline_offsets(text)
    n = index.n
    draft_hashes = overlap_index.gram_hashes(word_strs, n)

    # (citekey, diagonal) -> {draft position: source page} for every
    # n-gram match on that diagonal (src_pos - draft_pos constant) -- two
    # matches on the same diagonal are still "in step" even with
    # non-matching words between them, which is exactly what makes a
    # gap-tolerant merge (below) a same-diagonal 1-D problem rather than a
    # general alignment one. `page` is not part of the group key: a run
    # that truly spans a source page break has postings attributed to two
    # different pages but the same diagonal (global token positions,
    # #131), and grouping on page too would split it right back apart.
    # One write per (group, j): a fixed j and diagonal pin src_pos
    # (`src_pos = diagonal + j`), and a document fingerprint has exactly
    # one posting per position, so no second write ever competes for the
    # same key.
    groups = {}
    for j, gh in enumerate(draft_hashes):
        for citekey, page, src_pos in overlap_index.postings_for_gram(index, gh):
            groups.setdefault((citekey, src_pos - j), {})[j] = page

    allowlist = _load_allowlist_phrases()

    findings = []
    suppressed = 0
    for (citekey, _diagonal), pos_pages in groups.items():
        for run in _merge_runs(list(pos_pages), gap, n):
            start, end = run[0], run[-1] + n
            span_words = end - start
            if span_words < min_run:
                continue
            if allowlist:
                mask = _mask_allowlisted(word_strs[start:end], allowlist)
                if span_words - sum(mask) < min_run:
                    suppressed += 1
                    continue
            matched_words = len({idx for p in run for idx in range(p, p + n)})
            run_words = words[start:end]
            char_start, char_end = run_words[0].char, run_words[-1].char_end
            fragment = " ".join(word_strs[start:end])
            # Paragraphs *plural*: _tokenize_draft's word stream is flat
            # (module note above), so a run can cross a paragraph break --
            # checking only the start word's paragraph would call a run
            # "uncited" when it actually runs on into a paragraph that
            # does cite this source, or vice versa.
            run_paragraphs = {w.paragraph for w in run_words}
            cites_source = any(citekey in paragraph_citekeys[p] for p in run_paragraphs)
            run_pages = [pos_pages[p] for p in run]
            # Hoisted out of the dict rather than inlined as #131 wrote
            # it: `finding_id` needs the same start page the payload
            # reports, and computing `min(run_pages)` twice is how those
            # two quietly stop agreeing.
            page = min(run_pages)
            findings.append({
                "id": finding_id(citekey, page, fragment),
                "citekey": citekey,
                "page": page,
                "end_page": max(run_pages),
                "span_words": span_words,
                "matched_words": matched_words,
                "start": start,
                # 1-based, counted in the original text: the only one of
                # these four a person reads directly.
                "line": _line_at(newlines, char_start),
                "char_start": char_start,
                "char_end": char_end,
                "draft_text": text[char_start:char_end],
                "fragment": fragment,
                "context": " ".join(word_strs[max(0, start - 6):min(len(word_strs), end + 6)]),
                "cites_source": cites_source,
                # `all`, not `any`: "sits inside quote delimiters" means
                # the whole run is inside the quote, not merely that one
                # word of it happens to be near/inside an unrelated
                # quoted phrase.
                "quoted": all(w.quoted for w in run_words),
                "tier": "exact",
            })

    # Longest run first, no silent truncation -- every finding above the
    # floor prints unless --limit narrows it, matching the issue's explicit
    # break from `overlap`'s hardcoded top-25.
    findings.sort(key=lambda f: (-f["span_words"], f["citekey"], f["start"]))
    if limit is not None:
        findings = findings[:limit]
    return findings, min_run, suppressed


def _flags(finding):
    flags = []
    if not finding["cites_source"]:
        flags.append("UNCITED SOURCE")
    if finding["quoted"]:
        flags.append("quoted")
    return flags


def _matched_note(finding):
    if finding["matched_words"] == finding["span_words"]:
        return ""
    return f", {finding['matched_words']} matched"


def _page_range(finding):
    """`p.N` for an ordinary single-page run, `p.N-M` for one whose
    postings start on more than one page (#131).

    Not a guarantee that `p.N` never means multi-page content: `page`/
    `end_page` are the pages an n-gram in the run actually *starts* on, so
    a remainder shorter than the index's own n-gram size -- recovered
    into the run's word content because nothing that short can start a
    gram of its own -- can leave `end_page` unmoved even though the run's
    text reaches that page. See `scan_findings`'s docstring."""
    page, end_page = finding["page"], finding["end_page"]
    return f"p.{page}" if page == end_page else f"p.{page}-{end_page}"


# A run at or above this many words is "long" for bucketing purposes
# (see `_bucket`) -- a fixed policy constant, not a flag: the threshold
# is project-wide reading guidance, not a per-invocation choice.
LONG_RUN_WORDS = 15

# Most-damning-first: an uncited long run first, then an uncited short
# one, and only then a quoted-and-cited run, which is the likeliest to be
# a deliberate, legitimate quotation.
BUCKET_ORDER = ("long", "short", "quoted")


def _bucket(finding):
    """Which severity bucket the written report groups `finding` under.

    `quoted` only demotes a run to the low-priority `quoted` bucket when
    it *also* cites its source -- a quoted-but-uncited run is still the
    finding `overlap` structurally cannot make and `_flags` calls "the
    one most worth reading first" (see below); burying it under `quoted`
    just because it happens to sit inside quote marks would contradict
    that. It buckets by length like any other uncited run instead.
    """
    if finding["quoted"] and finding["cites_source"]:
        return "quoted"
    return "long" if finding["span_words"] >= LONG_RUN_WORDS else "short"


def _bucket_title(bucket):
    if bucket == "long":
        return f"Long verbatim runs (>= {LONG_RUN_WORDS} words)"
    if bucket == "short":
        return "Short verbatim runs"
    return "Quoted runs"


def format_scan(findings, min_run, suppressed=0):
    """The plain-text form, for stdout."""
    if not findings:
        base = f"no verbatim run of >= {min_run} words found anywhere in the draft"
    else:
        lines = []
        for f in findings:
            flags = _flags(f)
            flag_text = f" [{', '.join(flags)}]" if flags else ""
            lines.append(
                f"  [{f['span_words']} words{_matched_note(f)}, pdf {_page_range(f)}] "
                f"{f['citekey']} (tier={f['tier']}){flag_text}"
            )
            lines.append(f"      {f['fragment']}")
            lines.append(f"      in: {f['context']}...")
        base = "\n".join(lines)
    if suppressed:
        base += (
            f"\n\n{suppressed} finding(s) suppressed by the allowlist "
            f"({config.VERBATIM_ALLOWLIST_PATH.name})."
        )
    return base


# The finding fields the JSON payload publishes, in the order they are
# written. Spelled out rather than serialising `scan_findings`' dicts
# directly: those are this module's working representation and a key
# added there for some later internal purpose would otherwise silently
# become part of a published contract that #128's severity buckets and
# #129's remediation loop consume.
_PAYLOAD_FIELDS = (
    "id", "citekey", "page", "end_page", "tier", "span_words",
    "matched_words", "start", "line", "char_start", "char_end",
    "draft_text", "fragment", "context", "cites_source", "quoted",
)


def published(finding):
    """One of `scan_findings`' working dicts as the payload publishes it:
    `_PAYLOAD_FIELDS` in order, plus the derived `severity`.

    One function rather than the same comprehension in `scan_payload` and
    `recheck_findings`, so "what a published finding looks like" has a
    single definition -- `recheck` compares its own freshly-scanned
    findings against a baseline written by `scan`, and the two disagreeing
    about the shape is the one way that comparison could go quietly
    wrong.
    """
    return {
        **{field: finding[field] for field in _PAYLOAD_FIELDS},
        "severity": _bucket(finding),
    }


def scan_command(draft, min_run, gap, limit, write, as_json):
    """The invocation recorded in both the Markdown report's header and
    the JSON payload's envelope, so a reader holding either file can
    regenerate it.

    Every flag that changes *what is reported* is recorded, including the
    two that decide where it went: a report capped by `--limit` reads
    very differently from an uncapped one, and a recorded command without
    `--write` reproduces the findings on stdout but not the file. Only
    `--formats` is left out -- it selects renders *of* the Markdown
    report and changes nothing in it or in the payload. The allowlist is
    left out too, on both the command and the payload: it's per-host
    config, not a flag, so it can't join a re-runnable invocation -- its
    path and effect are recorded separately (see `render_scan_markdown`'s
    header bullet and `scan_payload`'s `suppressed` field).
    """
    command = ["python", "-m", "src.review", "verbatim", "scan", str(draft),
               "--min-run", str(min_run), "--gap", str(gap)]
    if limit is not None:
        command += ["--limit", str(limit)]
    if write:
        command += ["--write"]
    if as_json:
        command += ["--json"]
    return shlex.join(command)


def scan_payload(draft, findings, min_run, gap, limit, suppressed, command):
    """The same findings as data: `review.envelope`'s provenance, the
    three flags that set the reporting floor, how many findings the
    allowlist suppressed, and one object per finding.

    An additional serialisation of the list `scan_findings` already
    returned, never a second computation -- so the printed form and this
    one cannot disagree about what was found. `severity` is likewise
    derived, not stored: `_bucket` is a pure function of fields already in
    `_PAYLOAD_FIELDS`, so a consumer that wants the written report's
    long/short/quoted grouping gets it here instead of reimplementing the
    threshold.

    `start` is a **word** offset into the draft's normalised word stream
    (`_tokenize_draft`: masked, citation markers blanked, lowercased,
    punctuation dropped), not a character offset and not a line number.
    Neither it nor `fragment`/`context` -- which are that same stream,
    space-joined -- can be located or matched in the draft file as
    written. Those three locate a run for a *reader*.

    `line`, `char_start`, `char_end` and `draft_text` locate it for an
    *editor* (#129): they index the draft as written, so
    `draft[char_start:char_end] == draft_text` exactly -- which is what
    makes `draft_text` usable as an `Edit` `old_string`.

    The span runs from the first matched word's first character to the
    last matched word's last character, so it holds every original
    character *between* them: casing, interior punctuation, line breaks,
    and any citation marker sitting mid-run. It stops at the last word,
    which is the boundary worth being exact about -- a trailing period or
    closing quote sits just past `char_end` and is **not** included, so a
    rewrite substituted for `draft_text` leaves that punctuation where
    the sentence already had it. Leading punctuation is outside the span
    for the same reason.

    Nothing here decides *whether* to edit; the review layer still only
    ever reports.

    `id` names the finding across runs -- see `finding_id`, and `recheck`,
    which is the reason it exists.

    `cites_source` and `quoted` are the two bits the printed form shows
    as `UNCITED SOURCE` and `quoted`. Booleans rather than those labels:
    the point of this payload is that a caller stops matching display
    text, and a flag list would only move the parsing one layer down.
    """
    payload = review.envelope(Path(draft), "verbatim", command)
    payload.update({
        "min_run": min_run,
        "gap": gap,
        "limit": limit,
        "suppressed": suppressed,
        "findings": [published(f) for f in findings],
    })
    return payload


def render_scan_markdown(draft, findings, min_run, limit, command, suppressed=0):
    """The same findings as a Markdown report, for `--write`.

    Kept beside `format_scan` rather than replacing it: stdout is read in
    a terminal mid-review and wants no syntax, while a file kept for
    months is read next to the same draft's provenance and coverage
    reports and should look like them.

    `command` is built once, by `scan_command`, and handed to both this
    function and `scan_payload` -- so the Markdown header and the JSON
    envelope cannot disagree about what produced them.
    """
    allowlist_path = config.VERBATIM_ALLOWLIST_PATH
    if not allowlist_path.exists():
        allowlist_line = f"- Allowlist: none configured (`{allowlist_path}` not found)"
    else:
        allowlist_line = (
            f"- Allowlist: `{allowlist_path}` ({suppressed} finding(s) suppressed)"
        )

    lines = review.header(Path(draft), "verbatim", command)
    lines = lines[:-1] + [allowlist_line, ""]
    lines += [
        "## How to read this",
        "",
        "Every run of at least `--min-run` words this draft shares with **any**",
        "parsed source in the corpus, cited or not. Sharing wording is not by",
        "itself misconduct -- a defined term, a standard's name and a correctly",
        "quoted sentence all show up here -- so each finding is a place to look,",
        "not a charge.",
        "",
        "Two flags narrow the reading:",
        "",
        "- **UNCITED SOURCE** -- the paragraph the run sits in does not cite the",
        "  source it matched. That is the finding `overlap` structurally cannot",
        "  make, and the one most worth reading first.",
        "- **quoted** -- the whole run sits inside quote delimiters, so it is",
        "  most likely a deliberate quotation.",
        "",
        "Findings below are grouped most-damning-first: long runs, then short",
        "ones, then quoted runs -- but a quoted run only drops into the last",
        "group when it also cites the source it matched. A quoted run from an",
        "uncited source is still grouped by length, not buried under `quoted`.",
        "",
        "The allowlist bullet above names a per-host, gitignored file",
        "(`content/verbatim_allowlist.toml`, see docs/PLAGIARISM.md) of",
        "boilerplate this host's owner has decided never to flag -- a run is",
        "only dropped when what's left after discounting the allowlisted text",
        "would no longer clear `--min-run` on its own, so a real lift that",
        "merely contains a defined term still shows up below.",
        "",
        "**A clean run is not a clean bill of health.** This is the exact",
        "detection tier; the paraphrase tiers beside it are unbuilt, so this",
        "comes up short by being silently incomplete rather than by being wrong.",
        "See docs/PLAGIARISM.md.",
        "",
        "## Findings",
        "",
    ]

    if not findings:
        lines += [
            f"No verbatim run of {min_run} words or more was found anywhere in "
            "the draft.",
            "",
        ]
        return "\n".join(lines)

    lines += [f"{len(findings)} run(s), grouped most-damning-first.", ""]
    if limit is not None:
        lines += [
            f"This report was capped at `--limit {limit}` finding(s), taken from",
            "the longest-first list *before* grouping into the buckets below --",
            "a bucket may look emptier here than an uncapped scan would show, or",
            "be absent entirely, because its findings were cut before grouping.",
            "",
        ]

    buckets = {key: [] for key in BUCKET_ORDER}
    for f in findings:
        buckets[_bucket(f)].append(f)

    for key in BUCKET_ORDER:
        bucket_findings = buckets[key]
        if not bucket_findings:
            continue
        lines += [f"### {_bucket_title(key)}", ""]
        for f in bucket_findings:
            flags = _flags(f)
            flag_text = f" -- **{', '.join(flags)}**" if flags else ""
            lines += [
                f"#### {f['span_words']} words{_matched_note(f)} -- `{f['citekey']}` "
                f"{_page_range(f)}{flag_text}",
                "",
                f"> {f['fragment']}",
                "",
                f"In context: {f['context']}...",
                "",
            ]
    return "\n".join(lines)


def cmd_scan(draft, min_run=None, gap=1, limit=None, write=False,
             formats=("md", "tex", "pdf"), as_json=False):
    """`scan`'s stdout entry point: run the scan and print it.

    Printing text stays the default -- the usual use is a question asked
    and answered in one sitting, by a person. `as_json` prints the
    payload instead, for a caller that would otherwise have to parse that
    text back into data.

    `write` additionally puts the Markdown report in `content/review/`,
    mirroring the draft's path, beside the same draft's provenance and
    coverage reports -- and the payload beside it as the report's `.json`
    sibling, whether or not `as_json` was asked for. Unconditionally,
    because the file is written for whatever reads it later
    (docs/AUTO-IMPROVEMENT.md's `agenda`), not for whoever ran this
    command: a payload that appeared only when someone happened to also
    pass `--json` would be missing exactly when a later consumer needed
    it.

    Under `as_json` the written-files summary goes to stderr, so stdout
    is only ever the payload and `scan --json --write > findings.json` is
    a valid JSON file -- the discipline `dossier brief` already follows.
    """
    findings, min_run, suppressed = scan_findings(draft, min_run, gap, limit)

    # The default path prints text and stops. Returning here rather than
    # falling through keeps the payload's cost off it entirely -- a
    # projection per finding, and the `pyproject.toml` read
    # `review.version()` does for the envelope -- none of which the
    # printed form uses.
    if not (as_json or write):
        print(format_scan(findings, min_run, suppressed))
        return

    command = scan_command(draft, min_run, gap, limit, write, as_json)
    payload = scan_payload(draft, findings, min_run, gap, limit, suppressed, command)

    # Same `indent=2`, same key order, no trailing difference: what this
    # prints is byte-for-byte what `write_json` files, so a caller may
    # redirect stdout or read the sibling and get the same bytes.
    print(json.dumps(payload, indent=2) if as_json else format_scan(findings, min_run, suppressed))

    if write:
        body = render_scan_markdown(draft, findings, min_run, limit, command, suppressed)
        written = review.write(Path(draft), "verbatim", body, list(formats))
        written["json"] = review.write_json(Path(draft), "verbatim", payload)
        review.print_written(written, stream=sys.stderr if as_json else sys.stdout)


# ---------------------------------------------------------------------
# recheck: this scan against a recorded one. The half of #129's
# remediation loop that has to be deterministic -- "is this finding gone,
# and did repairing it break anything else" is the acceptance test a
# constrained rewrite is held to, and a model deciding that by reading
# two reports is exactly the judgement that should not be a judgement.
# ---------------------------------------------------------------------


# What `recheck` reads off a *baseline's* findings. It prints them in
# `resolved` -- the findings that are gone, so it never rescanned them and
# has only the file to go on. Named rather than stood in for by `id`,
# because the two failures differ: a payload can carry an `id` and still
# be missing something the output line needs. `end_page` is the live case
# -- a payload written between `id` landing and #131's page range claims
# the same release series, passes the version check below, and then
# crashes `_page_range`. Checked against `_PAYLOAD_FIELDS` in the tests,
# so a field required here but never written cannot slip in.
_BASELINE_FIELDS = (
    "id", "citekey", "page", "end_page", "span_words", "severity", "line",
)


def load_baseline(path):
    """A `scan` payload read back off disk, refused if it cannot serve as
    a comparison basis.

    Refuses rather than degrades in five cases, all of which would
    otherwise produce a confident and wrong answer:

    - not this aid's payload. The review layer's aids share `envelope()`,
      so a coverage report is also JSON with a `findings` key, and
      comparing against one would report every verbatim finding as new.
    - a payload written under `--limit`. Truncation happens after
      sorting, so a finding absent from a capped baseline may simply have
      been cut -- "new" then means "new or merely unreported", which is
      not something a caller can act on.
    - a payload missing any of `_BASELINE_FIELDS`, which is what an older
      `scan` wrote. One of those sits at the canonical report path for
      every draft an earlier version scanned, which is exactly where a
      caller is told to look, so this is the likeliest bad baseline of
      the five and the one that most deserves a remedy rather than a
      `KeyError`. An empty findings list is not this case: a draft
      repaired to clean is a legitimate baseline, and has no finding to
      be missing anything.
    - a payload from a different release series (`_series`, below). What
      counts as one finding can change between series -- #131 made a run
      that used to report as two merge into one, which changes that
      finding's `id` (`finding_id`'s `page` argument) even though nothing
      in the draft or the source moved -- so a cross-series comparison
      could report a repair that never happened.
    - unreadable or not JSON at all.

    The last two overlap but neither covers the other: a payload can be
    the right shape and mean something different (same series check), or
    claim this series and still be missing a field (the shape check --
    which is what a build taken between `id` landing and #131's
    `end_page` produces).
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read the baseline {path}: {exc}") from None
    except json.JSONDecodeError:
        raise ValueError(
            f"{path} is not a verbatim scan payload -- it is not valid JSON. "
            "Write one with `verbatim scan <draft> --write`."
        ) from None

    if (not isinstance(payload, dict) or payload.get("aid") != "verbatim"
            or "findings" not in payload):
        raise ValueError(
            f"{path} is not a verbatim scan payload. Write one with "
            "`verbatim scan <draft> --write`, which files it as the "
            "report's .json sibling."
        )
    if payload.get("limit") is not None:
        raise ValueError(
            f"{path} was written with --limit {payload['limit']}, so it lists "
            "only the longest findings and cannot say what was absent. "
            "Re-scan without --limit to take a baseline."
        )
    findings = payload["findings"]
    missing = []
    for key in ("min_run", "gap"):
        if key not in payload:
            missing.append(key)
        elif not isinstance(payload[key], int) or isinstance(payload[key], bool):
            # `recheck_findings` hands these straight to `scan_findings`
            # uncoerced; a hand-edited `"min_run": "8"` would otherwise
            # reach `_merge_runs`' `int <= str` comparison and raise
            # TypeError, not the clean ValueError/exit-2 refusal every
            # other malformed baseline gets. `bool` is a subclass of
            # `int`, but `min_run`/`gap` are word counts -- True/False
            # would silently become 1/0 instead of naming the problem.
            missing.append(f"{key} (not an int)")
    if (not isinstance(findings, list)
            or any(not isinstance(f, dict) for f in findings)):
        missing.append("findings (not a list of findings)")
    else:
        missing += sorted({
            field for f in findings for field in _BASELINE_FIELDS if field not in f
        })
    if missing:
        raise ValueError(
            f"{path} is missing {', '.join(missing)}, so it predates this "
            "command: it is a verbatim scan payload, but an older one than "
            "`recheck` can read. Re-scan the draft with `verbatim scan "
            "<draft> --write` to replace it, then compare against that."
        )
    recorded, running = payload.get("version"), review.version()
    if _series(recorded) and _series(recorded) != _series(running):
        raise ValueError(
            f"{path} was written by chitragupta {recorded}, and this is "
            f"{running}. What counts as one finding changes between release "
            "series -- a scan that learns to merge two runs into one gives "
            "wording nobody touched a different `id` -- so a comparison "
            "across one would report repairs that never happened. Re-scan "
            "the draft with `verbatim scan <draft> --write` to take a "
            "baseline this version wrote."
        )
    return payload


def _series(version):
    """A version's `major.minor`, or `None` where there is nothing to
    compare.

    The release series is the right granularity because
    DEVELOPER-AGENTS.md defines it that way: a patch release is
    "nothing that changes what the pipeline does", so a finding-shape
    change cannot land in one, while a minor release is exactly where new
    functionality -- `severity` in 5.4.0, the allowlist in 5.5.0, `id`
    here -- has repeatedly arrived. Checking the full string instead
    would force a needless re-scan after every patch; checking nothing
    would let a real contract change through silently.

    `None` for a missing version, a non-string one (a hand-edited or
    corrupted baseline JSON can put anything under that key, and a
    malformed `version` is not this function's refusal to make -- the
    shape check above already covers a baseline that isn't trustworthy),
    and for `review.version()`'s `"unknown"` fallback, which means
    pyproject could not be read: turning one unreadable file into a
    second, unrelated refusal helps nobody.
    """
    if not isinstance(version, str) or version == "unknown":
        return None
    return ".".join(version.split(".")[:2])


def recheck_findings(draft, baseline):
    """`(resolved, persisting, new, objective_before, objective_after)`
    for `draft` against `baseline`, rescanned at the baseline's own floor.

    The floor comes from the baseline rather than from a flag because two
    scans are only comparable at the same one, and the baseline's already
    happened -- a caller who could pass `--min-run` here could quietly
    compare a strict run against a lax one and read the difference as
    progress.

    Findings are matched by `finding_id`, which is position-free, so an
    edit above a finding does not report it as resolved-and-new. Where a
    baseline holds two findings sharing an id (see `finding_id`), a
    single repair leaves the id present and both still count as
    persisting -- understating progress, which is the direction an
    acceptance test should err in.
    """
    findings, _, _ = scan_findings(
        draft, baseline["min_run"], baseline["gap"], None
    )
    payload_now = [published(f) for f in findings]
    before = baseline["findings"]

    now_ids = {f["id"] for f in payload_now}
    before_ids = {f["id"] for f in before}
    resolved = [f for f in before if f["id"] not in now_ids]
    persisting = [f for f in payload_now if f["id"] in before_ids]
    new = [f for f in payload_now if f["id"] not in before_ids]

    # "Objective" is the two defect buckets. A run that is both quoted and
    # cited is a correctly attributed quotation, so counting it here would
    # make converting a lift into a quotation -- one of the two repairs
    # this loop is for -- look like no improvement at all.
    def objective(items):
        return sum(1 for f in items if f["severity"] != "quoted")

    return resolved, persisting, new, objective(before), objective(payload_now)


def recheck_command(draft, baseline):
    """The invocation recorded in the payload's envelope, so a reader
    holding the payload can regenerate it.

    Always includes `--json`, and takes no flag saying whether to: only
    the JSON form carries an envelope, so the recorded command is the one
    that reproduces *this file*. `scan_command` takes the flag because it
    is shared with the Markdown report, which the text form of a
    comparison has no counterpart to.
    """
    return shlex.join(["python", "-m", "src.review", "verbatim", "recheck",
                       str(draft), "--baseline", str(baseline), "--json"])


def recheck_payload(draft, baseline_path, baseline, groups, counts, command):
    """The comparison as data -- the form the remediation loop reads.

    Carries the baseline's path, version and floor as well as the three
    groups: a verdict whose basis is not recorded beside it is one nobody
    can check later, which is the same reason `scan_payload` carries
    `min_run`. See `_version_note` for what the version is doing here.
    """
    resolved, persisting, new = groups
    before, after = counts
    payload = review.envelope(Path(draft), "verbatim", command)
    payload.update({
        "baseline": str(baseline_path),
        "baseline_version": baseline.get("version"),
        "min_run": baseline["min_run"],
        "gap": baseline["gap"],
        "objective_before": before,
        "objective_after": after,
        "objective_delta": after - before,
        "resolved": resolved,
        "persisting": persisting,
        "new": new,
    })
    return payload


def format_recheck(baseline_path, baseline, groups, counts):
    """The plain-text form, for stdout."""
    resolved, persisting, new = groups
    before, after = counts
    lines = [
        f"baseline: {baseline_path}",
        f"floor:    --min-run {baseline['min_run']} --gap {baseline['gap']} (from the baseline)",
        "",
    ]
    for label, items in (("resolved", resolved), ("persisting", persisting), ("new", new)):
        lines.append(f"  {label} ({len(items)}):")
        if not items:
            lines.append("      -")
        for f in items:
            lines.append(
                f"      {f['id']}  [{f['span_words']} words, {f['severity']}] "
                f"{f['citekey']} {_page_range(f)} line {f['line']}"
            )
        lines.append("")
    lines.append(
        f"objective findings (long + short): {before} -> {after} ({after - before:+d})"
    )
    return "\n".join(lines)


def cmd_recheck(draft, baseline, as_json=False):
    """`recheck`'s stdout entry point.

    Prints and stops -- no `--write`. A scan report is kept beside the
    draft because it is read again months later; this is a comparison
    against one particular baseline, consumed by whoever asked for it and
    stale the next time the draft is touched. Filing it would leave a
    directory of near-identical reports whose only difference is which
    edit had happened yet.
    """
    loaded = load_baseline(baseline)
    resolved, persisting, new, before, after = recheck_findings(draft, loaded)
    groups, counts = (resolved, persisting, new), (before, after)

    if not as_json:
        print(format_recheck(baseline, loaded, groups, counts))
        return

    command = recheck_command(draft, baseline)
    print(json.dumps(
        recheck_payload(draft, baseline, loaded, groups, counts, command), indent=2
    ))


def cmd_locate(citekey, *phrases):
    src_pages = pages(citekey)
    print(f"{citekey}: {len(src_pages)} pdf pages")
    for phrase in phrases:
        keys = [w for w in norm(phrase) if len(w) > 3]
        best = []
        for i, pg in enumerate(src_pages, 1):
            w = set(norm(pg))
            score = sum(1 for k in keys if k in w)
            best.append((score / max(len(keys), 1), i))
        best.sort(reverse=True)
        top = ", ".join(f"p.{i} ({s:.0%})" for s, i in best[:4])
        print(f"  {phrase!r}\n      -> {top}")


def _bounded_int(minimum, name):
    """An argparse `type` that rejects an out-of-range value as a usage
    error rather than letting it through to be silently absorbed.

    A value that parses fine can still be nonsensical: `--limit 0`
    silently hides every finding behind the same "no verbatim run found"
    message a genuinely clean draft prints, and a negative `--gap` breaks
    even a pure-verbatim run's merge (Python's `list[:0]`/negative-gap
    arithmetic degrade silently rather than raising) -- both look like
    "nothing to report" instead of the usage error they actually are.
    """
    def parse(raw):
        try:
            value = int(raw)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{raw!r} is not a valid value") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"{name} must be >= {minimum}")
        return value
    return parse


def build_parser(parser=None):
    """The `verbatim` aid's four modes.

    `parser` is passed by src/review/__main__.py, which has already
    created this aid's subparser and needs the modes hung off *that*
    rather than off a fresh top-level parser -- so the flags are declared
    once, here, and the entry point never restates them.
    """
    if parser is None:
        # A one-line description rather than this module's docstring, for
        # the reason src/corpus.py's DESCRIPTION gives (#152).
        parser = argparse.ArgumentParser(
            description="Report how much wording a draft shares with the sources it cites.",
        )
    sub = parser.add_subparsers(dest="mode")

    p_overlap = sub.add_parser("overlap", help="per-citekey verbatim runs")
    p_overlap.add_argument("draft", help="Markdown draft to check")
    p_overlap.add_argument("citekey", help="The cited source to compare against")
    p_overlap.add_argument("--n", type=_bounded_int(1, "--n"), default=8,
                           help="Minimum run length in words (default: 8)")

    p_scan = sub.add_parser("scan", help="whole-draft x whole-corpus scan")
    p_scan.add_argument("draft", help="Markdown draft to scan")
    p_scan.add_argument("--min-run", type=_bounded_int(1, "--min-run"), default=None,
                        help="Reporting length floor in words (default: the corpus "
                             "index's own n-gram size)")
    p_scan.add_argument("--gap", type=_bounded_int(0, "--gap"), default=1,
                        help="Non-matching words tolerated inside a run (default: 1)")
    p_scan.add_argument("--limit", type=_bounded_int(1, "--limit"), default=None,
                        help="Cap how many findings print (default: all of them)")
    p_scan.add_argument("--json", action="store_true",
                        help="Print the findings as JSON instead of as text, for a "
                             "caller that would otherwise parse the printed form. "
                             "--write files it beside the report either way.")
    p_scan.add_argument("--write", action="store_true",
                        help="Also write the report to content/review/, mirroring the "
                             "draft's path. Off by default: printing is the usual use.")
    p_scan.add_argument("--formats", default="md,tex,pdf",
                        help="Additional formats to render beside the Markdown report (default: md,tex,pdf). The .md is always written -- it is the report; tex/pdf are renders of it, and need pandoc/pdflatex on PATH.")

    p_recheck = sub.add_parser("recheck", help="this scan against a recorded one")
    p_recheck.add_argument("draft", help="Markdown draft to re-scan")
    p_recheck.add_argument("--baseline", required=True,
                           help="A scan payload to compare against, as written by "
                                "`scan --write`. Its --min-run and --gap are reused, "
                                "so the two scans are comparable.")
    p_recheck.add_argument("--json", action="store_true",
                           help="Print the comparison as JSON instead of as text.")

    p_locate = sub.add_parser("locate", help="which page a phrase is on")
    p_locate.add_argument("citekey", help="The source to search")
    p_locate.add_argument("phrases", nargs="+", help="Phrases to locate")

    # So run() can print this aid's own help when no mode was given,
    # whether it was reached directly or through the entry point's
    # `verbatim` subparser -- which is a different parser object.
    parser.set_defaults(_parser=parser)
    return parser


def main(argv=None):
    """Exit codes: `0` on every successful invocation, findings or not --
    a review aid, not a gate. `1` for a draft this layer will not read
    (missing, or outside `content/`). `2` for a malformed invocation,
    the usual CLI-usage error, which argparse already uses.

    No mode at all prints the usage and exits 0: that is the same "tell
    me how to use this" request as `--help`, not an error.
    """
    parser = build_parser()
    return run(parser.parse_args(sys.argv[1:] if argv is None else argv))


def run(args):
    """Dispatch already-parsed arguments.

    Split from main() so src/review/__main__.py can hand over the args it
    parsed with this module's own build_parser(), rather than re-slicing
    argv and parsing it twice.
    """
    if args.mode is None:
        args._parser.print_help()
        return 0

    if args.mode == "locate":
        cmd_locate(args.citekey, *args.phrases)
        return 0

    try:
        draft = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.mode == "overlap":
        cmd_overlap(str(draft), args.citekey, args.n)
        return 0

    try:
        if args.mode == "recheck":
            cmd_recheck(str(draft), args.baseline, as_json=args.json)
        else:
            cmd_scan(
                str(draft), args.min_run, args.gap, args.limit,
                write=args.write,
                formats=[f.strip() for f in args.formats.split(",") if f.strip()],
                as_json=args.json,
            )
    except ValueError as exc:
        # "this input can't be scanned as asked" (e.g. --min-run below the
        # corpus index's own n-gram size, or a baseline that cannot serve
        # as one) is a usage error, not a finding.
        print(exc, file=sys.stderr)
        return 2
    return 0
