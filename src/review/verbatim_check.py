#!/usr/bin/env python3
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

Three modes:
    python3 -m src.review verbatim overlap <draft.md> <citekey> [--n 8]
        report the longest verbatim word-n-gram runs shared between the
        draft's sentences citing <citekey> and that source's parsed text.

    python3 -m src.review verbatim scan <draft.md> [--min-run 8] [--gap 1]
                                       [--limit N] [--write] [--formats md,tex,pdf]
        slide the WHOLE draft across the WHOLE corpus index (src/overlap_index.py),
        not just the sources a paragraph happens to cite -- catches verbatim
        reuse from an uncited source, and reuse in connective prose that
        cites nothing at all. Prints by default; --write also files the
        report under content/review/, beside the same draft's provenance
        and coverage reports.

    python3 -m src.review verbatim locate <citekey> "<phrase>" [more phrases...]
        report which PDF page each phrase (or its distinctive words)
        appears on, for fact-checking page numbers.

Exits 0 on every successful invocation, findings or not -- a review aid,
not a gate. A draft this layer will not read (missing, or outside
content/) exits 1; a malformed invocation exits 2, the usual CLI-usage
error, not a verdict.
"""

import argparse
import re
import shlex
import subprocess
import sys
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


def _tokenize_draft(text):
    """Every word of `text` (masked, citation markers stripped) as a flat
    list across the whole draft, plus which citekeys each paragraph
    cites.

    Flat rather than paragraph-scoped: an n-gram window can cross a
    paragraph break in the word stream this produces, unlike `overlap`'s
    per-paragraph scan. That is a deliberate trade -- catching reuse in
    the (much more common) single-paragraph case matters more than the
    rare false-candidate an adjacent-paragraph seam could produce, and a
    real match still has to line up with actual corpus text to survive.
    """
    masked = _mask_for_scan(text)
    paragraphs = re.split(r"\n\s*\n", masked)
    words = []
    paragraph_citekeys = []
    for p_idx, para in enumerate(paragraphs):
        paragraph_citekeys.append({key for _, key in citation_gate.extract_citekeys(para)})
        clean = re.sub(r"\[@[^\]]+\]", "", para)
        quote_spans = _quote_char_spans(clean)
        for m in WORD.finditer(clean.lower()):
            words.append(_DraftWord(m.group(0), p_idx, _char_in_spans(m.start(), quote_spans)))
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


def scan_findings(draft, min_run=None, gap=1, limit=None):
    """Slide `draft`'s whole normalized text across the corpus-wide index,
    grouping matches by `(citekey, page, diagonal)` and merging each
    group into maximal same-diagonal runs (see `_merge_runs`). Returns
    `(findings, min_run)`, longest run first; this function never raises
    for "nothing found" and returns an empty list in that case -- this is
    a review aid, not a gate, and it is not wired into anything that
    treats a nonzero exit as a failure. It does raise `ValueError` for a request
    it cannot honor at all, e.g. `min_run` below the corpus index's own
    n-gram size (see below) -- that is not "no findings", it is "this
    input can't be scanned as asked", and the `scan` CLI (below) turns it
    into the same stderr-plus-exit-2 usage error as its other malformed
    invocations, e.g. `--gap` with no value.

    Known limitation, not fixed here: `src/overlap_index.py`'s
    `token_position` resets to 0 at every page break in the *source*, so
    a run can never merge across one -- a genuine verbatim lift that
    straddles a page break in the parsed source is reported as two
    (or more) separate, shorter findings instead of one. Most of the time
    both halves still individually clear `--min-run` and the reuse is
    still visible, just split; but a short remainder stranded alone on
    the far side of the break (fewer words than `--min-run` on that page)
    is invisible, same as if it were never there. Fixing this needs a
    global (not per-page) token position in the fingerprint cache, which
    changes the `.fpr` cache format and is out of scope for this PR.
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
    n = index.n
    draft_hashes = overlap_index.gram_hashes(word_strs, n)

    # (citekey, page, diagonal) -> draft positions whose n-gram matched a
    # posting on that diagonal (src_pos - draft_pos constant) -- two
    # matches on the same diagonal are still "in step" even with
    # non-matching words between them, which is exactly what makes a
    # gap-tolerant merge (below) a same-diagonal 1-D problem rather than a
    # general alignment one.
    groups = {}
    for j, gh in enumerate(draft_hashes):
        for citekey, page, src_pos in overlap_index.postings_for_gram(index, gh):
            groups.setdefault((citekey, page, src_pos - j), []).append(j)

    findings = []
    for (citekey, page, _diagonal), positions in groups.items():
        for run in _merge_runs(positions, gap, n):
            start, end = run[0], run[-1] + n
            span_words = end - start
            if span_words < min_run:
                continue
            matched_words = len({idx for p in run for idx in range(p, p + n)})
            run_words = words[start:end]
            # Paragraphs *plural*: _tokenize_draft's word stream is flat
            # (module note above), so a run can cross a paragraph break --
            # checking only the start word's paragraph would call a run
            # "uncited" when it actually runs on into a paragraph that
            # does cite this source, or vice versa.
            run_paragraphs = {w.paragraph for w in run_words}
            cites_source = any(citekey in paragraph_citekeys[p] for p in run_paragraphs)
            findings.append({
                "citekey": citekey,
                "page": page,
                "span_words": span_words,
                "matched_words": matched_words,
                "start": start,
                "fragment": " ".join(word_strs[start:end]),
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
    return findings, min_run


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


def format_scan(findings, min_run):
    """The plain-text form, for stdout."""
    if not findings:
        return f"no verbatim run of >= {min_run} words found anywhere in the draft"
    lines = []
    for f in findings:
        flags = _flags(f)
        flag_text = f" [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"  [{f['span_words']} words{_matched_note(f)}, pdf p.{f['page']}] "
            f"{f['citekey']} (tier={f['tier']}){flag_text}"
        )
        lines.append(f"      {f['fragment']}")
        lines.append(f"      in: {f['context']}...")
    return "\n".join(lines)


def render_scan_markdown(draft, findings, min_run, gap, limit):
    """The same findings as a Markdown report, for `--write`.

    Kept beside `format_scan` rather than replacing it: stdout is read in
    a terminal mid-review and wants no syntax, while a file kept for
    months is read next to the same draft's provenance and coverage
    reports and should look like them.
    """
    # `--write` is part of the invocation: this function is only reached
    # under that flag, and a recorded command without it reproduces the
    # findings on stdout but not the file -- which is what a reader
    # holding the file wants to regenerate. `--formats` is left out; it
    # selects renders *of* this report and changes nothing in it.
    command = ["python3", "-m", "src.review", "verbatim", "scan", str(draft),
               "--min-run", str(min_run), "--gap", str(gap)]
    if limit is not None:
        command += ["--limit", str(limit)]
    command += ["--write"]

    lines = review.header(Path(draft), "verbatim", shlex.join(command))
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

    lines += [f"{len(findings)} run(s), longest first.", ""]
    for f in findings:
        flags = _flags(f)
        flag_text = f" -- **{', '.join(flags)}**" if flags else ""
        lines += [
            f"### {f['span_words']} words{_matched_note(f)} -- `{f['citekey']}` "
            f"p.{f['page']}{flag_text}",
            "",
            f"> {f['fragment']}",
            "",
            f"In context: {f['context']}...",
            "",
        ]
    return "\n".join(lines)


def cmd_scan(draft, min_run=None, gap=1, limit=None, write=False, formats=("md", "tex", "pdf")):
    """`scan`'s stdout entry point: run the scan and print it.

    Printing stays the default -- the usual use is a question asked and
    answered in one sitting. `write` additionally puts the Markdown
    report in `content/review/`, mirroring the draft's path, beside the
    same draft's provenance and coverage reports.
    """
    findings, min_run = scan_findings(draft, min_run, gap, limit)
    print(format_scan(findings, min_run))
    if write:
        body = render_scan_markdown(draft, findings, min_run, gap, limit)
        review.print_written(review.write(Path(draft), "verbatim", body, list(formats)))


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
    """The `verbatim` aid's three modes.

    `parser` is passed by src/review/__main__.py, which has already
    created this aid's subparser and needs the modes hung off *that*
    rather than off a fresh top-level parser -- so the flags are declared
    once, here, and the entry point never restates them.
    """
    if parser is None:
        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
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
    p_scan.add_argument("--write", action="store_true",
                        help="Also write the report to content/review/, mirroring the "
                             "draft's path. Off by default: printing is the usual use.")
    p_scan.add_argument("--formats", default="md,tex,pdf",
                        help="Additional formats to render beside the Markdown report (default: md,tex,pdf). The .md is always written -- it is the report; tex/pdf are renders of it, and need pandoc/pdflatex on PATH.")

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
        cmd_scan(
            str(draft), args.min_run, args.gap, args.limit,
            write=args.write,
            formats=[f.strip() for f in args.formats.split(",") if f.strip()],
        )
    except ValueError as exc:
        # "this input can't be scanned as asked" (e.g. --min-run below the
        # corpus index's own n-gram size) is a usage error, not a finding.
        print(exc, file=sys.stderr)
        return 2
    return 0
