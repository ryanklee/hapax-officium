"""Tests for agents/management_prep.py — management preparation agent.

Tests data collection logic. LLM synthesis is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.management_prep import (
    ManagementOverview,
    PrepDocument,
    TeamSnapshot,
    _collect_person_context,
    _collect_team_context,
    _find_person,
    _read_recent_meetings,
    format_overview_md,
    format_prep_md,
    format_snapshot_md,
    generate_1on1_prep,
    generate_overview,
    generate_team_snapshot,
)
from cockpit.data.management import (
    CoachingState,
    FeedbackState,
    ManagementSnapshot,
    PersonState,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


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


def _make_person(**kwargs) -> PersonState:
    defaults = {"name": "Alice", "team": "platform", "role": "engineer", "cadence": "weekly"}
    defaults.update(kwargs)
    return PersonState(**defaults)


# ── _find_person ─────────────────────────────────────────────────────────────


class TestFindPerson:
    def test_finds_by_exact_name(self):
        snap = _make_snapshot(people=[_make_person(name="Alice")])
        assert _find_person(snap, "Alice") is not None

    def test_finds_case_insensitive(self):
        snap = _make_snapshot(people=[_make_person(name="Alice")])
        assert _find_person(snap, "alice") is not None

    def test_not_found(self):
        snap = _make_snapshot(people=[_make_person(name="Alice")])
        assert _find_person(snap, "Bob") is None


# ── _read_recent_meetings (stubbed) ──────────────────────────────────────────


class TestReadRecentMeetings:
    def test_returns_empty_list(self):
        """Stub always returns empty — vault excised."""
        assert _read_recent_meetings("Alice") == []

    def test_returns_empty_with_limit(self):
        assert _read_recent_meetings("Alice", limit=3) == []


# ── _collect_person_context ──────────────────────────────────────────────────


class TestCollectPersonContext:
    def test_basic_context(self):
        person = _make_person(
            name="Alice",
            cognitive_load=3,
            growth_vector="leadership",
        )
        snap = _make_snapshot(people=[person])
        ctx = _collect_person_context(person, snap)
        assert "Alice" in ctx
        assert "leadership" in ctx
        assert "3" in ctx

    def test_includes_coaching(self):
        person = _make_person(name="Alice")
        coaching = CoachingState(
            title="delegation experiment",
            person="Alice",
            status="active",
            overdue=True,
        )
        snap = _make_snapshot(people=[person], coaching=[coaching])
        ctx = _collect_person_context(person, snap)
        assert "delegation experiment" in ctx
        assert "OVERDUE" in ctx

    def test_includes_feedback(self):
        person = _make_person(name="Alice")
        feedback = FeedbackState(
            title="q1 growth",
            person="Alice",
            category="growth",
            direction="given",
        )
        snap = _make_snapshot(people=[person], feedback=[feedback])
        ctx = _collect_person_context(person, snap)
        assert "q1 growth" in ctx


# ── _collect_team_context ────────────────────────────────────────────────────


class TestCollectTeamContext:
    def test_basic_team(self):
        snap = _make_snapshot(
            people=[
                _make_person(name="Alice", cognitive_load=3),
                _make_person(name="Bob", cognitive_load=5),
            ],
            active_people_count=2,
            high_load_count=1,
        )
        ctx = _collect_team_context(snap)
        assert "Alice" in ctx
        assert "Bob" in ctx
        assert "High load (4+): 1" in ctx


# ── generate_1on1_prep (mocked LLM) ─────────────────────────────────────────


class TestGenerate1on1Prep:
    @pytest.mark.asyncio
    async def test_person_not_found(self):
        with patch("agents.management_prep.collect_management_state") as mock:
            mock.return_value = _make_snapshot()
            prep = await generate_1on1_prep("NonexistentPerson")
        assert "No active person record found" in prep.summary

    @pytest.mark.asyncio
    async def test_person_found_calls_agent(self):
        snap = _make_snapshot(people=[_make_person(name="Alice")])
        mock_result = MagicMock()
        mock_result.output = PrepDocument(
            summary="Alice context",
            rolling_themes=["growth"],
        )
        with (
            patch("agents.management_prep.collect_management_state", return_value=snap),
            patch("agents.management_prep.prep_agent") as mock_agent,
        ):
            mock_agent.run = AsyncMock(return_value=mock_result)
            prep = await generate_1on1_prep("Alice")
        assert prep.summary == "Alice context"
        mock_agent.run.assert_awaited_once()


# ── generate_team_snapshot (mocked LLM) ──────────────────────────────────────


class TestGenerateTeamSnapshot:
    @pytest.mark.asyncio
    async def test_empty_team(self):
        with patch("agents.management_prep.collect_management_state") as mock:
            mock.return_value = _make_snapshot()
            snap = await generate_team_snapshot()
        assert "No active people" in snap.headline

    @pytest.mark.asyncio
    async def test_with_people_calls_agent(self):
        snap = _make_snapshot(people=[_make_person(name="Alice")])
        mock_result = MagicMock()
        mock_result.output = TeamSnapshot(
            headline="Team healthy",
            people_summaries=["Alice: all good"],
        )
        with (
            patch("agents.management_prep.collect_management_state", return_value=snap),
            patch("agents.management_prep.snapshot_agent") as mock_agent,
        ):
            mock_agent.run = AsyncMock(return_value=mock_result)
            result = await generate_team_snapshot()
        assert result.headline == "Team healthy"


# ── Formatters ───────────────────────────────────────────────────────────────


class TestFormatters:
    def test_format_prep_md(self):
        prep = PrepDocument(
            summary="Context for Alice",
            rolling_themes=["growth", "delegation"],
            open_items=["Review PR #42"],
            coaching_status="Active experiment on delegation",
            suggested_topics=["Discuss project timeline"],
            energy_signals="Low energy last week",
        )
        md = format_prep_md("Alice", prep)
        assert "# 1:1 Prep" in md
        assert "Alice" in md
        assert "delegation" in md
        assert "PR #42" in md
        assert "Low energy" in md

    def test_format_snapshot_md(self):
        snap = TeamSnapshot(
            headline="Team nominal",
            people_summaries=["Alice: healthy", "Bob: high load"],
            load_assessment="Load skewing high",
            themes=["Scaling concerns"],
        )
        md = format_snapshot_md(snap)
        assert "Team nominal" in md
        assert "Alice: healthy" in md
        assert "Scaling concerns" in md

    def test_format_overview_md(self):
        overview = ManagementOverview(
            headline="All 1:1s current",
            body="Team is healthy with no overdue items.",
            key_actions=["Review coaching experiment"],
        )
        md = format_overview_md(overview)
        assert "All 1:1s current" in md
        assert "Review coaching" in md
        assert "Updated" in md


# ── F-6.5: generate_overview tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_overview_success():
    """generate_overview returns LLM output on success."""
    mock_result = MagicMock()
    mock_result.output = ManagementOverview(
        headline="Team healthy",
        body="No issues.",
        key_actions=["Review OKRs"],
    )

    with (
        patch("agents.management_prep.overview_agent") as mock_agent,
        patch("agents.management_prep.collect_management_state"),
    ):
        mock_agent.run = AsyncMock(return_value=mock_result)
        result = await generate_overview()

    assert result.headline == "Team healthy"
    assert "Review OKRs" in result.key_actions


@pytest.mark.asyncio
async def test_generate_overview_handles_error():
    """generate_overview returns error overview on LLM failure."""
    with (
        patch("agents.management_prep.overview_agent") as mock_agent,
        patch("agents.management_prep.collect_management_state"),
    ):
        mock_agent.run = AsyncMock(side_effect=RuntimeError("model down"))
        result = await generate_overview()

    assert "failed" in result.headline.lower()
    assert "model down" in result.body
