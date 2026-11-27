"""Is any passage copied into a verbatim digest twice? (#1172)

Every run can match its source and the digest still repeat one passage in
three sections, which matching cannot see; this compares copied spans with
each other. The unit is a sentence: one whose flattened text
(`_quotation_match.flatten`) already appeared in an earlier span of the
same citekey is `repeated-text` on the later one. Whole spans would miss
copies that start or end a sentence apart.

`MIN_CHARS` (about eight words, not tuned) keeps a stock sentence like
"Thus." from matching. The finding counts in no fraction: the text is
still the source's.
"""

from chitragupta import sentences
from chitragupta.review._digest_model import Finding, Span
from chitragupta.review._quotation_match import flatten

MIN_CHARS = 40


def _sentences(span: Span) -> list[str]:
    return [span.text[a:b] for a, b in sentences.spans(span.text)]


def repeats(spans: list[Span]) -> list[Finding]:
    """One `repeated-text` finding per sentence copied again from the same
    source, in document order."""
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
