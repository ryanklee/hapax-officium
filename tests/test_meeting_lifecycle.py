"""Tests for agents/meeting_lifecycle.py — meeting lifecycle automation.

Uses mocked management state. No real vault or LLM access.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from cockpit.data.management import ManagementSnapshot, PersonState

if TYPE_CHECKING:
    from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────────────────


def _days_ago(n: int) -> str:
    return (datetime.now(UTC) - timedelta(days=n)).strftime("%Y-%m-%d")


def _write_note(path: Path, frontmatter: dict, body: str = "") -> Path:
    parts = ["---", yaml.dump(frontmatter, default_flow_style=False).strip(), "---"]
    if body:
        parts.append("")
        parts.append(body)
    path.write_text("\n".join(parts))
    return path


def _make_snapshot(**kwargs) -> ManagementSnapshot:
    defaults = {
        "people": [],
        "coaching": [],
        "feedback": [],
        "stale_1on1_count": 0,
        "overdue_coaching_count": 0,
        "overdue_feedback_count": 0,
        "high_load_count": 0,
        "active_people_count": 0,
    }
    defaults.update(kwargs)
    return ManagementSnapshot(**defaults)


# ── discover_due_meetings tests ────────────────────────────────────────────


class TestDiscoverDueMeetings:
    def test_weekly_stale_returns_due(self):
        snap = _make_snapshot(
            people=[
                PersonState(
                    name="Alice",
                    cadence="weekly",
                    last_1on1=_days_ago(7),
                    days_since_1on1=7,
                    stale_1on1=True,
                ),
            ]
        )
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import discover_due_meetings

            due = discover_due_meetings()
        assert len(due) == 1
        assert due[0].person_name == "Alice"
        assert due[0].prep_threshold == 5

    def test_weekly_fresh_not_due(self):
        snap = _make_snapshot(
            people=[
                PersonState(
                    name="Bob",
                    cadence="weekly",
                    last_1on1=_days_ago(3),
                    days_since_1on1=3,
                    stale_1on1=False,
                ),
            ]
        )
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import discover_due_meetings

            due = discover_due_meetings()
        assert len(due) == 0

    def test_no_cadence_not_due(self):
        snap = _make_snapshot(
            people=[
                PersonState(name="Charlie", last_1on1=_days_ago(30), days_since_1on1=30),
            ]
        )
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import discover_due_meetings

            due = discover_due_meetings()
        assert len(due) == 0

    def test_empty_snapshot(self):
        snap = _make_snapshot()
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import discover_due_meetings

            due = discover_due_meetings()
        assert len(due) == 0

    def test_biweekly_threshold(self):
        snap = _make_snapshot(
            people=[
                PersonState(
                    name="Dana", cadence="biweekly", last_1on1=_days_ago(14), days_since_1on1=14
                ),
            ]
        )
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import discover_due_meetings

            due = discover_due_meetings()
        assert len(due) == 1
        assert due[0].prep_threshold == 12

    def test_person_filter(self):
        snap = _make_snapshot(
            people=[
                PersonState(
                    name="Alice", cadence="weekly", last_1on1=_days_ago(7), days_since_1on1=7
                ),
                PersonState(
                    name="Bob", cadence="weekly", last_1on1=_days_ago(7), days_since_1on1=7
                ),
            ]
        )
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import discover_due_meetings

            due = discover_due_meetings(person_filter="Alice")
        assert len(due) == 1
        assert due[0].person_name == "Alice"


# ── prepare_all tests ──────────────────────────────────────────────────────


class TestPrepareAll:
    @pytest.mark.asyncio
    async def test_dry_run_no_writes(self):
        snap = _make_snapshot(
            people=[
                PersonState(
                    name="Alice", cadence="weekly", last_1on1=_days_ago(7), days_since_1on1=7
                ),
            ]
        )
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import prepare_all

            summary = await prepare_all(dry_run=True)
        assert summary.meetings_due == 1
        assert summary.preps_generated == 0


# ── process_meeting tests ─────────────────────────────────────────────────


class TestProcessMeeting:
    @pytest.mark.asyncio
    async def test_process_meeting_returns_extraction(self, tmp_path: Path):
        from agents.meeting_lifecycle import MeetingExtraction

        note = tmp_path / "meeting.md"
        _write_note(
            note, {"type": "meeting"}, "# Meeting\n- Action: fix bug\n- Decision: use Python"
        )

        mock_extraction = MeetingExtraction(
            action_items=[],
            decisions=["Use Python"],
            summary="Discussed technical approach",
        )

        with patch("agents.meeting_lifecycle.extract_agent") as mock_agent:
            mock_result = MagicMock()
            mock_result.output = mock_extraction
            mock_agent.run = AsyncMock(return_value=mock_result)

            from agents.meeting_lifecycle import process_meeting

            result = await process_meeting(note)

        assert result.summary == "Discussed technical approach"
        assert len(result.decisions) == 1

    @pytest.mark.asyncio
    async def test_process_meeting_empty_on_error(self, tmp_path: Path):
        note = tmp_path / "nonexistent.md"
        from agents.meeting_lifecycle import process_meeting

        result = await process_meeting(note)
        assert result.summary == ""
        assert result.action_items == []


# ── route_extractions tests ──────────────────────────────────────────────


class TestRouteExtractions:
    def test_empty_extraction_no_starters(self, tmp_path: Path):
        from agents.meeting_lifecycle import MeetingExtraction, route_extractions

        extraction = MeetingExtraction()
        note = tmp_path / "2026-03-03-alice-1on1.md"
        _write_note(note, {"type": "meeting"})

        created = route_extractions(extraction, note)
        assert created == []

    def test_routes_decisions(self, tmp_path: Path):
        from agents.meeting_lifecycle import MeetingExtraction, route_extractions

        extraction = MeetingExtraction(
            decisions=["Migrate to PostgreSQL"],
        )
        note = tmp_path / "2026-03-03-alice-1on1.md"
        _write_note(note, {"type": "meeting", "attendees": ["Alice"]})

        created = route_extractions(extraction, note)
        # vault_writer rehydrated — creates return paths
        assert len(created) == 1
        assert created[0].exists()

    def test_routes_coaching_observation(self, tmp_path: Path):
        from agents.meeting_lifecycle import MeetingExtraction, route_extractions

        extraction = MeetingExtraction(
            coaching_observations=["Alice showed strong debugging skills under pressure"],
        )
        note = tmp_path / "2026-03-03-alice-1on1.md"
        _write_note(note, {"type": "meeting", "attendees": ["Alice"]})

        created = route_extractions(extraction, note)
        assert len(created) == 1
        assert created[0].exists()


# ── _person_from_meeting_path tests ───────────────────────────────────────


class TestPersonFromMeetingPath:
    def test_from_filename(self, tmp_path: Path):
        from agents.meeting_lifecycle import _person_from_meeting_path

        note = tmp_path / "2026-03-03-alice-1on1.md"
        note.write_text("---\ntype: meeting\n---\n")
        assert _person_from_meeting_path(note) == "Alice"

    def test_from_attendees(self, tmp_path: Path):
        from agents.meeting_lifecycle import _person_from_meeting_path

        note = tmp_path / "meeting.md"
        _write_note(note, {"type": "meeting", "attendees": ["Alice Smith"]})
        assert _person_from_meeting_path(note) == "Alice Smith"

    def test_no_info_returns_empty(self, tmp_path: Path):
        from agents.meeting_lifecycle import _person_from_meeting_path

        note = tmp_path / "meeting.md"
        _write_note(note, {"type": "meeting"})
        assert _person_from_meeting_path(note) == ""


# ── weekly review tests ──────────────────────────────────────────────────


class TestWeeklyReview:
    def test_weekly_review_with_people(self):
        snap = _make_snapshot(
            people=[
                PersonState(
                    name="Alice",
                    cadence="weekly",
                    last_1on1=_days_ago(15),
                    stale_1on1=True,
                    days_since_1on1=15,
                    cognitive_load=4,
                    coaching_active=True,
                ),
                PersonState(name="Bob", cadence="weekly", last_1on1=_days_ago(3), cognitive_load=2),
            ]
        )
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import generate_weekly_review

            data = generate_weekly_review()

        assert len(data.cognitive_load_table) == 2
        assert any(r["person"] == "Alice" for r in data.cognitive_load_table)
        assert len(data.risks) >= 1  # At least stale 1:1 or high load

    def test_weekly_review_empty(self):
        snap = _make_snapshot()
        with patch("agents.meeting_lifecycle.collect_management_state", return_value=snap):
            from agents.meeting_lifecycle import generate_weekly_review

            data = generate_weekly_review()
        assert data.cognitive_load_table == []
        assert data.meetings_this_week == 0

    def test_format_weekly_review_md(self):
        from agents.meeting_lifecycle import WeeklyReviewData, format_weekly_review_md

        data = WeeklyReviewData(
            cognitive_load_table=[
                {"person": "Alice", "load": 4, "signals": "stale 1:1", "action": "schedule 1:1"},
            ],
            risks=["High load: Alice (4/5)"],
            meetings_this_week=3,
        )
        md = format_weekly_review_md(data)
        assert "Weekly Review" in md
        assert "Alice" in md
        assert "4/5" in md
        assert "## Wins" in md  # Blank section for operator
        assert "## Next Week Focus" in md


# ── write_weekly_review_to_vault tests ────────────────────────────────────


class TestWriteWeeklyReviewToVault:
    def test_writes_review_file(self):
        """vault_writer rehydrated — write returns path."""
        from agents.meeting_lifecycle import (
            WeeklyReviewData,
            write_weekly_review_to_vault,
        )

        data = WeeklyReviewData(
            cognitive_load_table=[{"person": "A", "load": 3, "signals": "", "action": ""}],
        )
        path = write_weekly_review_to_vault(data)
        assert path is not None
        assert path.exists()
