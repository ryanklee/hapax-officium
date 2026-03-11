# ai-agents/tests/test_simulator_event_gen.py
"""Tests for LLM-driven event generation (mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from agents.simulator_pipeline.event_gen import generate_tick_events
from agents.simulator_pipeline.models import SimulatedEvent


class TestGenerateTickEvents:
    async def test_returns_events_from_llm(self):
        """LLM generates a list of SimulatedEvent objects."""
        mock_events = [
            SimulatedEvent(
                date="2026-03-05",
                workflow_type="one_on_one",
                subdirectory="meetings",
                filename="2026-03-05-alice-1on1.md",
                participant="Alice",
                topics=["project status"],
                metadata={"type": "meeting", "meeting-type": "one-on-one"},
            ),
        ]

        mock_result = MagicMock()
        mock_result.output = mock_events

        with patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            events = await generate_tick_events(prompt="Simulate events for 2026-03-05...")

        assert len(events) == 1
        assert events[0].workflow_type == "one_on_one"

    async def test_empty_day_returns_empty_list(self):
        """LLM can return empty list (quiet day)."""
        mock_result = MagicMock()
        mock_result.output = []

        with patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            events = await generate_tick_events(prompt="Simulate...")

        assert events == []

    async def test_strips_restricted_body_templates(self):
        """Body templates on restricted types are stripped for safety."""
        mock_events = [
            SimulatedEvent(
                date="2026-03-05",
                workflow_type="coaching_note",
                subdirectory="coaching",
                filename="2026-03-05-alice.md",
                participant="Alice",
                topics=["delegation"],
                metadata={"type": "coaching"},
                body_template="This should be stripped",
            ),
        ]

        mock_result = MagicMock()
        mock_result.output = mock_events

        with patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            events = await generate_tick_events(prompt="Simulate...")

        assert events[0].body_template is None

    async def test_preserves_unrestricted_body_templates(self):
        """Body templates on unrestricted types are preserved."""
        mock_events = [
            SimulatedEvent(
                date="2026-03-05",
                workflow_type="decision",
                subdirectory="decisions",
                filename="2026-03-05-ci.md",
                topics=["CI"],
                metadata={"type": "decision"},
                body_template="## Decision\n\nAdopt new CI.",
            ),
        ]

        mock_result = MagicMock()
        mock_result.output = mock_events

        with patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            events = await generate_tick_events(prompt="Simulate...")

        assert events[0].body_template == "## Decision\n\nAdopt new CI."

    async def test_validates_events_when_workflows_provided(self):
        """Events are validated against valid_workflows when provided."""
        mock_events = [
            SimulatedEvent(
                date="2026-03-05",
                workflow_type="one_on_one",
                subdirectory="meetings",
                filename="2026-03-05-alice-1on1.md",
                participant="Alice",
                topics=["project status"],
                metadata={"type": "meeting", "meeting-type": "one-on-one"},
            ),
            SimulatedEvent(
                date="2026-03-05",
                workflow_type="bogus_type",
                subdirectory="bogus",
                filename="2026-03-05-bogus.md",
                topics=["nothing"],
                metadata={"type": "bogus"},
            ),
        ]

        mock_result = MagicMock()
        mock_result.output = mock_events

        valid_workflows = {
            "one_on_one": {"subdirectory": "meetings/"},
        }

        with patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            events = await generate_tick_events(
                prompt="Simulate...",
                valid_workflows=valid_workflows,
            )

        assert len(events) == 1
        assert events[0].workflow_type == "one_on_one"

    async def test_skips_validation_when_no_workflows(self):
        """Events are not validated when valid_workflows is None."""
        mock_events = [
            SimulatedEvent(
                date="2026-03-05",
                workflow_type="totally_unknown",
                subdirectory="whatever",
                filename="2026-03-05-thing.md",
                topics=["stuff"],
                metadata={"type": "thing"},
            ),
        ]

        mock_result = MagicMock()
        mock_result.output = mock_events

        with patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            events = await generate_tick_events(prompt="Simulate...")

        assert len(events) == 1  # no validation, passes through
