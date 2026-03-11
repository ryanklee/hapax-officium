"""Tests for cockpit API data cache."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cockpit.api.cache import DataCache


class TestDataCache:
    def test_initial_state_empty(self):
        c = DataCache()
        assert c.management is None
        assert c.nudges == []
        assert c.goals is None
        assert c.agents == []
        assert c.team_health is None

    def test_cache_age_negative_before_refresh(self):
        c = DataCache()
        assert c.cache_age() == -1

    async def test_refresh_populates_management(self):
        c = DataCache()
        mock_management = MagicMock()
        mock_management.return_value = type("M", (), {"people_count": 5, "stale_1on1s": 1})()
        with (
            patch("cockpit.data.management.collect_management_state", mock_management),
            patch("cockpit.data.goals.collect_goals", MagicMock(return_value=None)),
            patch("cockpit.data.team_health.collect_team_health", MagicMock(return_value=None)),
            patch("cockpit.data.agents.get_agent_registry", MagicMock(return_value=[])),
            patch("cockpit.data.nudges.collect_nudges", MagicMock(return_value=[])),
        ):
            await c.refresh()
        assert c.management is not None
        assert c.management.people_count == 5

    async def test_refresh_populates_nudges(self):
        c = DataCache()
        mock_nudge = type("N", (), {"priority": 10, "source": "management", "message": "test"})()
        with (
            patch("cockpit.data.management.collect_management_state", MagicMock(return_value=None)),
            patch("cockpit.data.goals.collect_goals", MagicMock(return_value=None)),
            patch("cockpit.data.team_health.collect_team_health", MagicMock(return_value=None)),
            patch("cockpit.data.agents.get_agent_registry", MagicMock(return_value=[])),
            patch("cockpit.data.nudges.collect_nudges", MagicMock(return_value=[mock_nudge])),
        ):
            await c.refresh()
        assert len(c.nudges) == 1

    async def test_cache_age_positive_after_refresh(self):
        c = DataCache()
        with (
            patch("cockpit.data.management.collect_management_state", MagicMock(return_value=None)),
            patch("cockpit.data.goals.collect_goals", MagicMock(return_value=None)),
            patch("cockpit.data.team_health.collect_team_health", MagicMock(return_value=None)),
            patch("cockpit.data.agents.get_agent_registry", MagicMock(return_value=[])),
            patch("cockpit.data.nudges.collect_nudges", MagicMock(return_value=[])),
        ):
            await c.refresh()
        assert c.cache_age() >= 0

    async def test_refresh_tolerates_collector_errors(self):
        """If a collector raises, others still run and cache doesn't break."""
        c = DataCache()
        with (
            patch(
                "cockpit.data.management.collect_management_state", side_effect=Exception("boom")
            ),
            patch("cockpit.data.goals.collect_goals", MagicMock(return_value=None)),
            patch("cockpit.data.team_health.collect_team_health", MagicMock(return_value=None)),
            patch("cockpit.data.agents.get_agent_registry", MagicMock(return_value=[])),
            patch("cockpit.data.nudges.collect_nudges", MagicMock(return_value=[])),
        ):
            await c.refresh()
        # Management stays None due to error, but cache_age is updated
        assert c.management is None
        assert c.cache_age() >= 0
