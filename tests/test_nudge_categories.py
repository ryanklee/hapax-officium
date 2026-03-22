"""Tests for nudge category slot allocation and redistribution."""

from __future__ import annotations

from logos.data.nudges import CATEGORY_SLOTS, Nudge, _allocate_by_category


class TestCategoryAllocation:
    def test_each_category_gets_slots(self):
        nudges = [
            Nudge(
                category="people",
                priority_score=70,
                priority_label="high",
                title="P1",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="people",
                priority_score=65,
                priority_label="high",
                title="P2",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="people",
                priority_score=60,
                priority_label="medium",
                title="P3",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="people",
                priority_score=55,
                priority_label="medium",
                title="P4",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="goals",
                priority_score=70,
                priority_label="high",
                title="G1",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="goals",
                priority_score=65,
                priority_label="high",
                title="G2",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="goals",
                priority_score=60,
                priority_label="medium",
                title="G3",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="operational",
                priority_score=70,
                priority_label="high",
                title="O1",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="operational",
                priority_score=65,
                priority_label="high",
                title="O2",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="operational",
                priority_score=60,
                priority_label="medium",
                title="O3",
                detail="",
                suggested_action="",
            ),
        ]

        result = _allocate_by_category(nudges)

        cats = [n.category for n in result]
        assert cats.count("people") == CATEGORY_SLOTS["people"]  # 3
        assert cats.count("goals") == CATEGORY_SLOTS["goals"]  # 2
        assert cats.count("operational") == CATEGORY_SLOTS["operational"]  # 2
        assert len(result) == 7

    def test_unused_slots_redistribute(self):
        nudges = [
            Nudge(
                category="people",
                priority_score=70,
                priority_label="high",
                title="P1",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="people",
                priority_score=65,
                priority_label="high",
                title="P2",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="people",
                priority_score=60,
                priority_label="medium",
                title="P3",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="people",
                priority_score=55,
                priority_label="medium",
                title="P4",
                detail="",
                suggested_action="",
            ),
            # goals has only 1 item (budget=2), so 1 slot redistributes
            Nudge(
                category="goals",
                priority_score=70,
                priority_label="high",
                title="G1",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="operational",
                priority_score=65,
                priority_label="high",
                title="O1",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="operational",
                priority_score=60,
                priority_label="medium",
                title="O2",
                detail="",
                suggested_action="",
            ),
        ]

        result = _allocate_by_category(nudges)

        # 3 people (budget) + 1 goals + 2 operational + 1 overflow (P4 at 55)
        assert len(result) == 7
        cats = [n.category for n in result]
        assert cats.count("people") == 4  # got the extra slot
        assert cats.count("goals") == 1
        assert cats.count("operational") == 2

    def test_empty_nudges(self):
        result = _allocate_by_category([])
        assert result == []

    def test_single_category_only(self):
        nudges = [
            Nudge(
                category="people",
                priority_score=70,
                priority_label="high",
                title=f"P{i}",
                detail="",
                suggested_action="",
            )
            for i in range(10)
        ]

        result = _allocate_by_category(nudges)

        # All 7 slots go to people (only category with items)
        assert len(result) == 7
        assert all(n.category == "people" for n in result)

    def test_result_sorted_by_priority(self):
        nudges = [
            Nudge(
                category="people",
                priority_score=40,
                priority_label="low",
                title="P-low",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="goals",
                priority_score=70,
                priority_label="high",
                title="G-high",
                detail="",
                suggested_action="",
            ),
            Nudge(
                category="operational",
                priority_score=55,
                priority_label="medium",
                title="O-med",
                detail="",
                suggested_action="",
            ),
        ]

        result = _allocate_by_category(nudges)

        scores = [n.priority_score for n in result]
        assert scores == sorted(scores, reverse=True)
