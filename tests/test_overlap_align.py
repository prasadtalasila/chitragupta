from chitragupta import overlap_align


class TestAlign:
    def test_a_single_strong_pair_aligns_to_itself(self):
        [found] = overlap_align.align([[0.4, -0.5], [-0.5, -0.5]])
        assert (found.draft_start, found.draft_end) == (0, 1)
        assert (found.source_start, found.source_end) == (0, 1)
        assert found.score == 0.4

    def test_consecutive_pairs_chain_into_one_alignment(self):
        scores = [[0.3, -0.5, -0.5], [-0.5, 0.3, -0.5], [-0.5, -0.5, 0.3]]
        [found] = overlap_align.align(scores)
        assert (found.draft_start, found.draft_end) == (0, 3)
        assert found.score == pytest_approx(0.9)

    def test_the_alignment_is_local_and_stops_at_the_negative_cells(self):
        scores = [
            [-0.5, -0.5, -0.5, -0.5],
            [-0.5, 0.4, -0.5, -0.5],
            [-0.5, -0.5, 0.4, -0.5],
            [-0.5, -0.5, -0.5, -0.5],
        ]
        [found] = overlap_align.align(scores)
        assert (found.draft_start, found.draft_end) == (1, 3)

    def test_a_gap_is_crossed_when_it_is_cheaper_than_stopping(self):
        scores = [[0.5, -0.9, -0.9], [-0.9, -0.9, -0.9], [-0.9, -0.9, 0.5]]
        [found] = overlap_align.align(scores, gap_penalty=0.1)
        assert (found.draft_start, found.draft_end) == (0, 3)

    def test_a_gap_is_not_crossed_when_the_penalty_makes_it_too_dear(self):
        scores = [[0.5, -0.9, -0.9], [-0.9, -0.9, -0.9], [-0.9, -0.9, 0.5]]
        found = overlap_align.align(scores, gap_penalty=5.0)
        assert all(a.draft_end - a.draft_start == 1 for a in found)

    def test_matched_records_only_the_diagonal_steps(self):
        scores = [[0.5, -0.9, -0.9], [-0.9, -0.9, -0.9], [-0.9, -0.9, 0.5]]
        [found] = overlap_align.align(scores, gap_penalty=0.1)
        assert found.matched == (0, 2)

    def test_a_second_alignment_elsewhere_is_reported_too(self):
        scores = [
            [0.5, -0.9, -0.9, -0.9],
            [-0.9, -0.9, -0.9, -0.9],
            [-0.9, -0.9, -0.9, -0.9],
            [-0.9, -0.9, -0.9, 0.6],
        ]
        found = overlap_align.align(scores)
        assert len(found) == 2
        assert [a.score for a in found] == [0.6, 0.5]

    def test_two_alignments_never_share_a_draft_sentence(self):
        scores = [[0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, 0.5]]
        found = overlap_align.align(scores)
        spans = [(a.draft_start, a.draft_end) for a in found]
        for i, (start, end) in enumerate(spans):
            for other_start, other_end in spans[i + 1 :]:
                assert end <= other_start or other_end <= start

    def test_it_never_reports_more_than_the_limit(self):
        scores = [[-9.0] * 12 for _ in range(12)]
        for block in (0, 4, 8):
            scores[block][block] = 0.5
        assert len(overlap_align.align(scores, limit=2)) == 2
        assert len(overlap_align.align(scores)) == 3

    def test_a_peak_whose_traceback_reenters_a_claimed_row_is_dropped(self):
        scores = [[0.9, 0.9], [0.9, 0.9]]
        found = overlap_align.align(scores, gap_penalty=0.0, limit=3)
        spans = [(a.draft_start, a.draft_end) for a in found]
        assert len(spans) == len(set(spans))
        for i, (start, end) in enumerate(spans):
            for other_start, other_end in spans[i + 1 :]:
                assert end <= other_start or other_end <= start

    def test_nothing_positive_gives_no_alignment(self):
        assert overlap_align.align([[-0.1, -0.2], [-0.3, -0.4]]) == []

    def test_an_empty_matrix_is_an_ordinary_outcome_not_an_error(self):
        assert overlap_align.align([]) == []
        assert overlap_align.align([[]]) == []

    def test_an_alignment_reaching_the_first_sentence_traces_back_to_zero(self):
        [found] = overlap_align.align([[0.5]])
        assert (found.draft_start, found.source_start) == (0, 0)

    def test_a_caller_supplied_floor_stops_the_tracing(self):
        scores = [[-9.0] * 12 for _ in range(12)]
        scores[0][0] = 0.9
        scores[4][4] = 0.2
        found = overlap_align.align(scores, minimum_score=0.5)
        assert [a.score for a in found] == [0.9]

    def test_the_structural_floor_is_zero_not_a_policy_knob(self):
        assert overlap_align.MIN_ALIGNMENT_SCORE == 0.0


def pytest_approx(value):
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) < 1e-9

        def __repr__(self):
            return f"~{value}"

    return _Approx()
