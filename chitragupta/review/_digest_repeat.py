"""Is any passage copied into a verbatim digest twice? (#1172)

Every run of a digest can match its source and the digest still read
badly: #1172's dogfood draft carried one source's heat-balance
equations and their symbol definitions in three sections, each copy
verified, and only a reader noticed. A run repeated is the source's
words twice, so nothing about matching can see it; this module compares
the copied spans with each other instead.

**A sentence is the unit.** Each copied span is split into sentences;
a sentence whose flattened text (`_quotation_match.flatten`, the same
letters-and-digits stream every match reads) already appeared in an
earlier span of the same citekey is a `repeated-text` finding on the
later one, naming the line of the first. Comparing whole spans would
miss the usual case, where the second copy starts or ends a sentence
earlier than the first.

`MIN_CHARS` keeps a short stock sentence -- "Thus." or a bare heading
fragment -- from matching across a source that happens to use it twice.
It is not tuned: it is about eight words, the length below which a
repeated sentence says nothing about whether a passage was copied twice.
On the dogfood draft before its repeats were removed, every repeated
sentence was far above it.

The finding counts in no fraction, like `dangling-reference`: the text
is still the source's words. It is a fault of the digest's shape.

Stdlib only, interpreter tier 1.
"""

from chitragupta import sentences
from chitragupta.review._digest_model import Finding, Span
from chitragupta.review._quotation_match import flatten

MIN_CHARS = 40


def _sentences(span: Span) -> list[str]:
    return [span.text[a:b] for a, b in sentences.spans(span.text)]


def repeats(spans: list[Span]) -> list[Finding]:
    """One `repeated-text` finding per sentence copied again from the
    same source, in document order."""
    first: dict[tuple[str, str], tuple[int, int]] = {}
    found = []
    for index, span in enumerate(spans):
        for sentence in _sentences(span):
            flat = flatten(sentence)
            if len(flat) < MIN_CHARS:
                continue
            for citekey in span.citekeys:
                seen = first.setdefault((citekey, flat), (index, span.line))
                if seen[0] != index:
                    detail = {"first_line": seen[1]}
                    found.append(
                        Finding("repeated-text", span.line, sentence, span.citekeys, detail)
                    )
                    break
    return found
