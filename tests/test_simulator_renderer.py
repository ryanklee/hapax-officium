# ai-agents/tests/test_simulator_renderer.py
"""Tests for simulator event renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.simulator_pipeline.models import SimulatedEvent
from agents.simulator_pipeline.renderer import render_event, render_events

if TYPE_CHECKING:
    from pathlib import Path


class TestRenderEvent:
    def test_renders_meeting_with_body(self, tmp_path: Path):
        """Meeting event produces markdown with frontmatter + body."""
        event = SimulatedEvent(
            date="2026-03-05",
            workflow_type="one_on_one",
            subdirectory="meetings",
            filename="2026-03-05-alice-1on1.md",
            participant="Alice",
            topics=["project status", "blockers", "career growth"],
            metadata={
                "type": "meeting",
                "meeting-type": "one-on-one",
                "person": "Alice",
                "date": "2026-03-05",
            },
            body_template="## Topics\n\n- {topics_list}\n\n## Action Items\n\n- Follow up on blockers",
        )
        path = render_event(event, tmp_path)

        assert path.exists()
        assert path == tmp_path / "meetings" / "2026-03-05-alice-1on1.md"

        content = path.read_text()
        assert "---" in content
        assert "type: meeting" in content
        assert "meeting-type: one-on-one" in content

    def test_renders_coaching_structural(self, tmp_path: Path):
        """Coaching event has structural body only — no evaluative language."""
        event = SimulatedEvent(
            date="2026-03-05",
            workflow_type="coaching_note",
            subdirectory="coaching",
            filename="2026-03-05-alice-delegation.md",
            participant="Alice",
            topics=["delegation", "project ownership"],
            metadata={
                "type": "coaching",
                "person": "Alice",
                "status": "active",
                "check-in-by": "2026-03-19",
            },
        )
        path = render_event(event, tmp_path)

        assert path.exists()
        content = path.read_text()
        assert "type: coaching" in content
        assert "person: Alice" in content
        assert "delegation" in content.lower()

    def test_renders_feedback_structural(self, tmp_path: Path):
        """Feedback event body is structural only."""
        event = SimulatedEvent(
            date="2026-03-05",
            workflow_type="feedback",
            subdirectory="feedback",
            filename="2026-03-05-bob-review.md",
            participant="Bob",
            topics=["code review", "pair programming"],
            metadata={
                "type": "feedback",
                "person": "Bob",
                "direction": "given",
                "category": "growth",
            },
        )
        path = render_event(event, tmp_path)

        assert path.exists()
        content = path.read_text()
        assert "type: feedback" in content

    def test_creates_subdirectory(self, tmp_path: Path):
        """Renderer creates subdirectory if it doesn't exist."""
        event = SimulatedEvent(
            date="2026-03-05",
            workflow_type="decision",
            subdirectory="decisions",
            filename="2026-03-05-ci.md",
            topics=["CI pipeline"],
            metadata={"type": "decision", "title": "Adopt CI"},
        )
        path = render_event(event, tmp_path)
        assert (tmp_path / "decisions").is_dir()
        assert path.exists()


class TestRenderEvents:
    def test_renders_multiple_events(self, tmp_path: Path):
        """render_events() writes all events and returns paths."""
        events = [
            SimulatedEvent(
                date="2026-03-05",
                workflow_type="one_on_one",
                subdirectory="meetings",
                filename="2026-03-05-alice.md",
                topics=["standup"],
                metadata={"type": "meeting"},
            ),
            SimulatedEvent(
                date="2026-03-05",
                workflow_type="decision",
                subdirectory="decisions",
                filename="2026-03-05-ci.md",
                topics=["CI"],
                metadata={"type": "decision"},
            ),
        ]
        paths = render_events(events, tmp_path)
        assert len(paths) == 2
        assert all(p.exists() for p in paths)
