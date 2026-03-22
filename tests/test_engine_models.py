"""Tests for logos/engine/models.py — reactive engine core data models.

Covers construction, default values, actions_by_phase grouping/sorting,
and edge cases for all four dataclasses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

from logos.engine.models import Action, ActionPlan, ChangeEvent, DeliveryItem

# ── ChangeEvent ──────────────────────────────────────────────────────────


class TestChangeEvent:
    def test_construction(self):
        ts = datetime(2026, 3, 9, 12, 0, 0)
        ev = ChangeEvent(
            path=Path("/data/people/alice.md"),
            subdirectory="people",
            event_type="modified",
            doc_type="person",
            timestamp=ts,
        )
        assert ev.path == Path("/data/people/alice.md")
        assert ev.subdirectory == "people"
        assert ev.event_type == "modified"
        assert ev.doc_type == "person"
        assert ev.timestamp == ts

    def test_none_doc_type(self):
        ev = ChangeEvent(
            path=Path("/data/unknown/file.txt"),
            subdirectory="unknown",
            event_type="created",
            doc_type=None,
            timestamp=datetime.now(),
        )
        assert ev.doc_type is None

    def test_event_types(self):
        for et in ("created", "modified", "deleted"):
            ev = ChangeEvent(
                path=Path("/data/f.md"),
                subdirectory="people",
                event_type=et,
                doc_type=None,
                timestamp=datetime.now(),
            )
            assert ev.event_type == et


# ── Action ───────────────────────────────────────────────────────────────


class TestAction:
    def test_construction_with_defaults(self):
        handler = AsyncMock()
        action = Action(name="refresh_snapshot", handler=handler)
        assert action.name == "refresh_snapshot"
        assert action.handler is handler
        assert action.args == {}
        assert action.priority == 0
        assert action.phase == 0
        assert action.depends_on == []

    def test_construction_with_all_fields(self):
        handler = AsyncMock()
        action = Action(
            name="generate_prep",
            handler=handler,
            args={"person": "alice"},
            priority=10,
            phase=2,
            depends_on=["refresh_snapshot"],
        )
        assert action.args == {"person": "alice"}
        assert action.priority == 10
        assert action.phase == 2
        assert action.depends_on == ["refresh_snapshot"]

    def test_default_lists_are_independent(self):
        """Each instance gets its own default list, not a shared mutable."""
        a1 = Action(name="a", handler=AsyncMock())
        a2 = Action(name="b", handler=AsyncMock())
        a1.depends_on.append("x")
        assert a2.depends_on == []


# ── ActionPlan ───────────────────────────────────────────────────────────


class TestActionPlan:
    def _make_event(self) -> ChangeEvent:
        return ChangeEvent(
            path=Path("/data/people/alice.md"),
            subdirectory="people",
            event_type="modified",
            doc_type="person",
            timestamp=datetime(2026, 3, 9, 12, 0, 0),
        )

    def test_construction_with_defaults(self):
        ev = self._make_event()
        plan = ActionPlan(trigger=ev, created_at=datetime.now())
        assert plan.trigger is ev
        assert plan.actions == []
        assert plan.results == {}
        assert plan.errors == {}
        assert plan.skipped == set()

    def test_actions_by_phase_grouping(self):
        ev = self._make_event()
        h = AsyncMock()
        actions = [
            Action(name="a", handler=h, phase=1, priority=5),
            Action(name="b", handler=h, phase=0, priority=0),
            Action(name="c", handler=h, phase=1, priority=2),
            Action(name="d", handler=h, phase=2, priority=0),
        ]
        plan = ActionPlan(trigger=ev, actions=actions, created_at=datetime.now())
        by_phase = plan.actions_by_phase()

        # Phases should be sorted by phase number
        assert list(by_phase.keys()) == [0, 1, 2]

        # Phase 0
        assert [a.name for a in by_phase[0]] == ["b"]

        # Phase 1 — sorted by priority (ascending: 2 before 5)
        assert [a.name for a in by_phase[1]] == ["c", "a"]

        # Phase 2
        assert [a.name for a in by_phase[2]] == ["d"]

    def test_actions_by_phase_empty(self):
        ev = self._make_event()
        plan = ActionPlan(trigger=ev, created_at=datetime.now())
        assert plan.actions_by_phase() == {}

    def test_actions_by_phase_single_phase(self):
        ev = self._make_event()
        h = AsyncMock()
        actions = [
            Action(name="x", handler=h, phase=0, priority=10),
            Action(name="y", handler=h, phase=0, priority=1),
        ]
        plan = ActionPlan(trigger=ev, actions=actions, created_at=datetime.now())
        by_phase = plan.actions_by_phase()
        assert list(by_phase.keys()) == [0]
        assert [a.name for a in by_phase[0]] == ["y", "x"]

    def test_default_collections_are_independent(self):
        ev = self._make_event()
        p1 = ActionPlan(trigger=ev, created_at=datetime.now())
        p2 = ActionPlan(trigger=ev, created_at=datetime.now())
        p1.actions.append(Action(name="z", handler=AsyncMock()))
        p1.results["foo"] = "bar"
        p1.errors["baz"] = "err"
        p1.skipped.add("skip")
        assert p2.actions == []
        assert p2.results == {}
        assert p2.errors == {}
        assert p2.skipped == set()


# ── ActionPlan trigger optional ──────────────────────────────────────────


class TestActionPlanTriggerOptional:
    def test_action_plan_without_trigger(self):
        plan = ActionPlan(created_at=datetime.now(UTC))
        assert plan.trigger is None
        assert plan.actions == []

    def test_action_plan_with_trigger(self):
        event = ChangeEvent(
            path=Path("/tmp/test.md"),
            subdirectory="people",
            event_type="modified",
            doc_type="person",
            timestamp=datetime.now(UTC),
        )
        plan = ActionPlan(created_at=datetime.now(UTC), trigger=event)
        assert plan.trigger is event


# ── DeliveryItem ─────────────────────────────────────────────────────────


class TestDeliveryItem:
    def test_construction_with_defaults(self):
        ts = datetime(2026, 3, 9, 14, 0, 0)
        item = DeliveryItem(
            title="Prep updated",
            detail="1:1 prep for Alice regenerated",
            priority="medium",
            category="generated",
            source_action="generate_prep",
            timestamp=ts,
        )
        assert item.title == "Prep updated"
        assert item.detail == "1:1 prep for Alice regenerated"
        assert item.priority == "medium"
        assert item.category == "generated"
        assert item.source_action == "generate_prep"
        assert item.timestamp == ts
        assert item.artifacts == []

    def test_construction_with_artifacts(self):
        item = DeliveryItem(
            title="Report ready",
            detail="Status report generated",
            priority="high",
            category="generated",
            source_action="status_report",
            timestamp=datetime.now(),
            artifacts=[Path("/data/reports/q1.md"), Path("/data/reports/q1.pdf")],
        )
        assert len(item.artifacts) == 2
        assert item.artifacts[0] == Path("/data/reports/q1.md")

    def test_default_artifacts_are_independent(self):
        d1 = DeliveryItem(
            title="a",
            detail="b",
            priority="low",
            category="detected",
            source_action="x",
            timestamp=datetime.now(),
        )
        d2 = DeliveryItem(
            title="c",
            detail="d",
            priority="low",
            category="detected",
            source_action="y",
            timestamp=datetime.now(),
        )
        d1.artifacts.append(Path("/tmp/f"))
        assert d2.artifacts == []
