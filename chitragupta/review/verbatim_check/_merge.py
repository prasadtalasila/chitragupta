"""Gap-tolerant run merging, shared by the exact and skip-gram tiers.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""


def _merge_runs(positions: list[int], gap: int, n: int) -> list[list[int]]:
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


def _merge_spans(
    spans: list[tuple[int, int, int]], gap: int
) -> list[tuple[int, int, list[tuple[int, int, int]]]]:
    """The tier-2 analogue of `_merge_runs`: `spans` is `(start, end,
    page)` triples on one diagonal, merged into maximal runs tolerating
    up to `gap` non-covered original positions between one span's end
    and the next's start.

    A separate function, not `_merge_runs` reused, because a skip-gram
    window's width in original draft positions is not fixed the way
    tier 1's `n`-word anchors are -- it varies with how many stopwords
    and opposite-family words it happens to skip -- so there is no
    single `n` to subtract the way `_merge_runs`' gap arithmetic needs.
    Comparing `start - previous_end` directly needs no such constant:
    the two spans already carry their own extents.

    Returns `(start, end, members)` triples, `members` the `(start,
    end, page)` triples that merged into this run -- kept rather than
    collapsed, so `_skipgram_tier_findings` can recover exactly which
    original positions were the subject of an actual skip-gram match,
    not merely inside the merged span (its `matched_words`).
    """
    ordered = sorted(spans)
    runs = [[ordered[0]]]
    run_end = ordered[0][1]
    for item in ordered[1:]:
        start, end, _page = item
        if start - run_end <= gap:
            runs[-1].append(item)
            run_end = max(run_end, end)
        else:
            runs.append([item])
            run_end = end
    return [(min(m[0] for m in run), max(m[1] for m in run), run) for run in runs]
