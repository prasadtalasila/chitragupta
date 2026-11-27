"""Gap-tolerant run merging, shared by the exact and skip-gram tiers."""


def _merge_runs(positions: list[int], gap: int, n: int) -> list[list[int]]:
    """Sorted draft word-positions on one diagonal -> maximal runs,
    merging two anchors separated by at most `gap` non-matching *words*.

    Subtracts `n`, not 1: one edited word poisons n-1 consecutive anchors,
    so `next - prev - n` is 1 for a single-word edit, as #111 asks for
    g=1; `-1` would silently need gap>=7 for the same edit.
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
    """Tier 2's `_merge_runs`: `(start, end, page)` spans on one diagonal,
    merged across up to `gap` uncovered positions.

    Separate because a skip-gram window has no fixed width to subtract;
    spans carry their own extents. Returns `(start, end, members)`, the
    members kept so `matched_words` counts only real match positions.
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
