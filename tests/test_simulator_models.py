# ai-agents/tests/test_simulator_models.py
"""Tests for simulator pipeline models."""

from __future__ import annotations

from agents.simulator_pipeline.models import (
    ContentPolicy,
    SimulatedEvent,
    TickResult,
)


class TestSimulatedEvent:
    def test_basic_event(self):
        """SimulatedEvent with all required fields."""
        event = SimulatedEvent(
            date="2026-03-05",
            workflow_type="one_on_one",
            subdirectory="meetings",
            filename="2026-03-05-alice-1on1.md",
            participant="Alice",
            topics=["project status", "blockers"],
            metadata={"type": "meeting", "meeting-type": "one-on-one", "person": "Alice"},
        )
        assert event.workflow_type == "one_on_one"
        assert event.participant == "Alice"
        assert event.body_template is None

    def test_event_with_body_template(self):
        """Events for meetings/decisions/status-reports can have body content."""
        event = SimulatedEvent(
            date="2026-03-05",
            workflow_type="decision",
            subdirectory="decisions",
            filename="2026-03-05-adopt-ci.md",
            topics=["CI pipeline", "migration plan"],
            metadata={"type": "decision", "title": "Adopt new CI"},
            body_template="## Context\n\n{topics}\n\n## Decision\n\n{decision_text}",
        )
        assert event.body_template is not None

    def test_coaching_feedback_no_body(self):
        """Coaching/feedback events must NOT have evaluative body content."""
        event = SimulatedEvent(
            date="2026-03-05",
            workflow_type="coaching_note",
            subdirectory="coaching",
            filename="2026-03-05-alice-delegation.md",
            participant="Alice",
            topics=["delegation", "project ownership"],
            metadata={"type": "coaching", "person": "Alice", "status": "active"},
        )
        assert event.body_template is None


class TestContentPolicy:
    def test_restricted_types(self):
        """ContentPolicy identifies coaching/feedback as restricted."""
        assert ContentPolicy.is_restricted("coaching_note") is True
        assert ContentPolicy.is_restricted("feedback") is True
        assert ContentPolicy.is_restricted("one_on_one") is False
        assert ContentPolicy.is_restricted("decision") is False
        assert ContentPolicy.is_restricted("incident") is False

    def test_allows_body_for_unrestricted(self):
        """Unrestricted types allow body_template."""
        assert ContentPolicy.allows_body("decision") is True
        assert ContentPolicy.allows_body("status_report") is True
        assert ContentPolicy.allows_body("one_on_one") is True

    def test_blocks_body_for_restricted(self):
        """Restricted types block body_template."""
        assert ContentPolicy.allows_body("coaching_note") is False
        assert ContentPolicy.allows_body("feedback") is False


class TestTickResult:
    def test_tick_result(self):
        """TickResult holds events for a single tick."""
        result = TickResult(
            date="2026-03-05",
            events=[
                SimulatedEvent(
                    date="2026-03-05",
                    workflow_type="one_on_one",
                    subdirectory="meetings",
                    filename="2026-03-05-alice.md",
                    topics=["standup"],
                    metadata={"type": "meeting"},
                ),
            ],
            checkpoint_ran=False,
        )
        assert len(result.events) == 1
        assert result.checkpoint_ran is False

    def test_has_significant_events(self):
        """TickResult detects incident/review-cycle events."""
        result = TickResult(
            date="2026-03-05",
            events=[
                SimulatedEvent(
                    date="2026-03-05",
                    workflow_type="incident",
                    subdirectory="incidents",
                    filename="2026-03-05-outage.md",
                    topics=["service outage"],
                    metadata={"type": "incident", "severity": "high"},
                ),
            ],
            checkpoint_ran=False,
        )
        assert result.has_significant_events is True

    def test_no_significant_events(self):
        """TickResult with only meetings is not significant."""
        result = TickResult(
            date="2026-03-05",
            events=[
                SimulatedEvent(
                    date="2026-03-05",
                    workflow_type="one_on_one",
                    subdirectory="meetings",
                    filename="2026-03-05-alice.md",
                    topics=["standup"],
                    metadata={"type": "meeting"},
                ),
            ],
            checkpoint_ran=False,
        )
        assert result.has_significant_events is False
