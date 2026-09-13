"""What `chitragupta/context_budget.py` promises the genre skills.

Three properties carry the whole module and are asserted separately
rather than as one "it works" case, because they fail for different
reasons: the split is deterministic and pure (so a skill's budget can be
reviewed in a diff), the budgets never sum past the window (so a skill
cannot promise the model more than it has), and the reserve is taken off
the top before anything else is sized (so the answer is always payable).

The degenerate cases have their own class. They are the part the issue
asked to be *defined* rather than merely to not crash, so each one
asserts the defined answer, not just the absence of an exception.
"""

import pytest

from chitragupta import context_budget


class TestAllocate:
    def test_the_default_section_set_is_every_working_section_plus_the_reserve(self):
        budgets = context_budget.allocate(200_000)
        assert set(budgets) == {"dossier", "passages", "draft", "reserve"}

    def test_the_budgets_never_sum_past_the_window(self):
        for window in (0, 1, 7, 999, 6_826, 6_827, 100_000, 200_000, 1_000_000):
            assert sum(context_budget.allocate(window).values()) <= window

    def test_the_same_input_gives_the_same_answer(self):
        assert context_budget.allocate(200_000) == context_budget.allocate(200_000)

    def test_the_shares_are_proportional_to_the_weights(self):
        budgets = context_budget.allocate(200_000)
        assert budgets == {
            "dossier": 30_000,
            "passages": 90_000,
            "draft": 50_000,
            "reserve": 30_000,
        }

    def test_a_named_subset_leaves_the_rest_unallocated_rather_than_resharing_it(self):
        """The comparability property: `passages` at a given window is the
        same number whichever skill asked, so two skills' budgets can be
        compared without also reading which other sections each selected."""
        whole = context_budget.allocate(200_000)
        subset = context_budget.allocate(200_000, ("passages",))
        assert subset == {"passages": whole["passages"], "reserve": whole["reserve"]}

    def test_the_section_order_of_the_request_does_not_change_the_answer(self):
        assert context_budget.allocate(200_000, ("draft", "dossier")) == context_budget.allocate(
            200_000, ("dossier", "draft")
        )

    def test_a_section_it_does_not_know_is_rejected_by_name(self):
        with pytest.raises(ValueError, match="history"):
            context_budget.allocate(200_000, ("history",))

    def test_asking_for_the_reserve_as_a_section_is_rejected(self):
        """It is unconditional, so naming it reads as a request that could
        be declined -- which is exactly what the module refuses to allow."""
        with pytest.raises(ValueError, match="reserve"):
            context_budget.allocate(200_000, ("reserve",))


class TestTheReserveIsNeverRaided:
    def test_the_reserve_is_its_share_of_a_window_that_can_pay_for_one(self):
        assert context_budget.allocate(200_000)["reserve"] == 30_000

    def test_a_window_too_small_for_the_floor_spends_all_of_it_on_the_reserve(self):
        assert context_budget.allocate(500) == {
            "dossier": 0,
            "passages": 0,
            "draft": 0,
            "reserve": 500,
        }

    def test_the_working_sections_share_only_what_the_reserve_left(self):
        budgets = context_budget.allocate(4_000)
        assert budgets["reserve"] == context_budget.RESERVE_FLOOR
        assert sum(budgets.values()) <= 4_000


class TestDegenerateInput:
    def test_an_empty_section_set_still_returns_the_reserve(self):
        """Defined, not an error: a caller that has nothing to fill still
        needs the number it must leave the model to answer with."""
        assert context_budget.allocate(200_000, ()) == {"reserve": 30_000}

    def test_a_window_of_zero_allocates_zero_everywhere(self):
        assert context_budget.allocate(0) == {
            "dossier": 0,
            "passages": 0,
            "draft": 0,
            "reserve": 0,
        }

    def test_a_negative_window_is_rejected(self):
        with pytest.raises(ValueError, match="window_size"):
            context_budget.allocate(-1)

    def test_a_non_integer_window_is_rejected(self):
        with pytest.raises(TypeError, match="window_size"):
            context_budget.allocate(200_000.0)

    def test_a_boolean_window_is_rejected(self):
        """`bool` is an `int` in Python, and `allocate(True)` is far more
        likely a caller that passed the wrong argument than one asking for
        a one-token window."""
        with pytest.raises(TypeError, match="window_size"):
            context_budget.allocate(True)


class TestTheWeightTable:
    def test_the_weights_and_the_reserve_are_a_whole_window(self):
        assert sum(context_budget.WORKING_WEIGHTS.values()) + context_budget.RESERVE_WEIGHT == 100

    def test_the_table_is_not_mutable_through_the_module_attribute(self):
        with pytest.raises(TypeError):
            context_budget.WORKING_WEIGHTS["passages"] = 99
