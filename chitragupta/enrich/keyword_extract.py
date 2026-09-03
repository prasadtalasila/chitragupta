"""Stage: extract each paper's own declared keywords into a seed list.

Most papers declare their own keywords near the abstract -- IEEE's
`Index Terms—X, Y, Z`, Elsevier's `Keywords: X · Y · Z`, Springer
sometimes with no punctuation between phrases at all. This stage finds
that line in each parsed document, splits it on whatever separator the
paper's own formatting uses, and aggregates the phrases across the
corpus into `config.KEYWORDS_PATH` (`content/keywords.toml` by default),
written in the exact `topics = [...]` shape
`chitragupta/seed_topics.py:load()` reads.

**`content/keywords.toml` is a generated artifact, regenerated fresh on
every run** -- machine output like `content/topics.json`, never a
hand-curated file like `content/seed_topics.toml`. Hand-edits are
silently overwritten by the next run; a phrase worth keeping permanently
is promoted into `seed_topics.toml`, the author's own list, instead.

Why the papers' declarations and not TF-IDF over the full text: both
were built and compared side by side on this project's own 497-document
corpus (bench/RESULTS.md, 2026-09-03c). The declared-keywords list read
as genuinely meaningful topic vocabulary and reached 97.6% seed-topic
coverage on its own; the TF-IDF list was mostly generic single words and
body-text noise. The catch that shapes this module's contract: a
detectable declaration existed in only 262 of those 497 papers (52.7%),
so **a document with no declaration is skipped, not substituted or
estimated** -- it contributes nothing, and the stage's report counts how
many documents had one rather than papering over the gap.

The extraction constants below were measured on that same corpus rather
than chosen: the 200-line window keeps a References-section false
positive out, the 300-character truncation survives Docling flattening a
whole PDF column (declaration + affiliations + abstract) into one line,
and the lowercase-to-uppercase fallback split is lossy on multi-word
phrases but the alternative was silently dropping the 27% of detected
declarations whose PDF extraction left no punctuation between phrases.

Pure text processing over the same parsed text every other stage reads
(`doc_vectors.corpus_texts()`): no model, no GPU, no LLM -- the corpus
layer's no-LLM rule holds here as everywhere.
"""

import json
import re

from chitragupta import config
from chitragupta.enrich import doc_vectors
from chitragupta.enrich.corpus import CorpusDoc

# How many lines from the top of a document the declaration may sit in.
# A References entry titled "Keywords in ..." sits far below this.
SCAN_LINES = 200
# How much of the line after the marker is split at all -- Docling
# occasionally flattens a whole PDF column into one line, and everything
# past the real declaration is affiliations and abstract.
LINE_CAP = 300
# The longest string still plausibly one keyword phrase; anything past
# this is flattened prose that survived LINE_CAP.
PHRASE_CAP = 60

# Best separator first: a middle dot or pipe is only ever a deliberate
# separator, a semicolon nearly so, while a comma can sit inside one
# phrase ("modeling, simulation and control") -- so the comma decides
# only when nothing stronger is on the line.
SEPARATORS = ("·", "|", ";", ",")

# The marker must open the line (leading whitespace and Markdown
# decoration allowed): "The keywords: ..." mid-prose is not a
# declaration, and matching it was measured to be the main false
# positive.
_MARKER = re.compile(r"^[\s#*_>-]*(?:keywords|index terms)\b(.*)$", re.IGNORECASE)

# What separates the marker from its payload: ":", an em dash, bold
# markers around the colon. The middle dot is deliberately absent --
# it is a phrase separator, and eating a leading one would be harmless
# but eating it here would blur the two roles.
_MARKER_TRAILING = " \t:;.*_—–-"

# The no-separator fallback: split where a word ending in a lowercase
# letter meets one starting with an uppercase letter. Lossy by design --
# "Digital Twin" splits apart as often as "Digital Twin Internet of
# Things" splits right -- but measured (bench/RESULTS.md, 2026-09-03c)
# against the alternative of dropping 27% of detected declarations.
_CASE_BOUNDARY = re.compile(r"(?<=[a-z])\s+(?=[A-Z])")


def _clean(fragment: str) -> str:
    """One candidate phrase: lowercased, whitespace collapsed, stray
    separator punctuation stripped from the edges. Never splits -- the
    phrase survives whole, the same guarantee seed_topics._clean()
    makes for the hand-written list."""
    return " ".join(fragment.strip(" \t.,;·|").lower().split())


def declared_phrases(text: str) -> tuple[str, ...]:
    """The phrases this one document's own declaration line carries.

    `()` for a document with no detectable declaration -- the ordinary
    state of half this project's own corpus, not an error. The first
    matching line wins; a marker line with no payload is still that
    document's declaration (of nothing), not a reason to scan on.
    """
    for line in text.splitlines()[:SCAN_LINES]:
        match = _MARKER.match(line)
        if match is None:
            continue
        payload = match.group(1).lstrip(_MARKER_TRAILING)[:LINE_CAP]
        separator = next((sep for sep in SEPARATORS if sep in payload), None)
        if separator is not None:
            fragments = payload.split(separator)
        else:
            fragments = _CASE_BOUNDARY.split(payload)
        phrases = []
        for fragment in fragments:
            phrase = _clean(fragment)
            if phrase and len(phrase) <= PHRASE_CAP:
                phrases.append(phrase)
        return tuple(phrases)
    return ()


def aggregate(per_doc: dict, min_df: "int | None" = None, top_n: "int | None" = None) -> list[str]:
    """The corpus-wide list: phrases ranked by how many distinct
    documents declare them, floored at `min_df`, capped at `top_n`
    (ties alphabetical), then returned sorted alphabetically.

    Distinct documents, not occurrences -- the per-document `set()` is
    what keeps one paper repeating a phrase from ever inflating it.
    Rank decides membership; the alphabetical sort at the end is
    presentation, because the artifact is read by a person scanning
    for a phrase, not by anything that cares which of two survivors
    was declared more often.
    """
    floor = config.KEYWORD_MIN_DF if min_df is None else min_df
    limit = config.KEYWORD_TOP_N if top_n is None else top_n

    counts: dict[str, int] = {}
    for phrases in per_doc.values():
        for phrase in set(phrases):
            counts[phrase] = counts.get(phrase, 0) + 1

    ranked = sorted(
        (phrase for phrase, count in counts.items() if count >= floor),
        key=lambda phrase: (-counts[phrase], phrase),
    )
    return sorted(ranked[:limit])


def write_keywords(phrases: list[str]) -> None:
    """`config.KEYWORDS_PATH`, replaced whole.

    `json.dumps` per phrase, because a JSON string is a valid TOML basic
    string with the same escapes -- a phrase carrying a quote or a
    non-ASCII character survives the round trip through
    `seed_topics.load()` without this module growing a TOML writer.
    """
    lines = [
        "# Generated by `chitragupta enrich --stages extract-keywords` from each",
        '# paper\'s own declared "Keywords:"/"Index Terms" line. Regenerated fresh',
        "# on every run -- do not hand-edit. To keep a phrase permanently, promote",
        "# it into content/seed_topics.toml, the hand-written list.",
        "",
    ]
    if phrases:
        lines.append("topics = [")
        lines.extend(f"    {json.dumps(phrase)}," for phrase in phrases)
        lines.append("]")
    else:
        lines.append("topics = []")
    config.KEYWORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.KEYWORDS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_stage(docs: list[CorpusDoc]) -> dict:
    """The whole stage, shaped as an enrichment-stage result.

    The status vocabulary lives here rather than in
    chitragupta/enrich/stages.py for the same ceiling reason
    topic_seeding.run_stage() states: the wrapper there stays one line.

    `skipped` only when no document has any parsed text at all --
    nothing to scan. A corpus that parsed fine but declared nothing is
    `ok` with an *empty* `topics = []` written and counted as such:
    that is a true answer about the corpus, and leaving a previous
    run's file in place would be a stale one.
    """
    doc_texts = doc_vectors.corpus_texts(docs)
    if not doc_texts:
        return {
            "status": "skipped",
            "detail": {"reason": "no parsed documents to scan for declared keywords"},
        }

    declared = {
        citekey: phrases
        for citekey, phrases in (
            (citekey, declared_phrases(text)) for citekey, text in doc_texts.items()
        )
        if phrases
    }
    phrases = aggregate(declared)
    write_keywords(phrases)
    return {
        "status": "ok",
        "detail": {
            "documents": len(doc_texts),
            "with_declaration": len(declared),
            "phrases": len(phrases),
            "path": str(config.KEYWORDS_PATH),
        },
    }
