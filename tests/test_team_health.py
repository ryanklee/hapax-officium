"""Tests for logos/data/team_health.py — team health aggregation and Larson classification.

Tests classification logic with synthetic data. collect_team_health tests
use mocked collect_management_state since vault is excised.
"""

from __future__ import annotations

from unittest.mock import patch

from logos.data.management import ManagementSnapshot, PersonState
from logos.data.team_health import (
    TeamState,
    _compute_majority_team_type,
    classify_larson_state,
    collect_team_health,
)

# ── classify_larson_state ──────────────────────────────────────────────────


class TestClassifyLarsonState:
    def test_falling_behind_high_load(self):
        team = TeamState(
            name="platform",
            size=3,
            avg_cognitive_load=4.5,
            stale_1on1_count=0,
            coaching_active_count=0,
        )
        state, evidence = classify_larson_state(team)
        assert state == "falling-behind"
        assert any("4.5" in e for e in evidence)

    def test_falling_behind_stale_1on1s(self):
        team = TeamState(
            name="sre",
            size=4,
            avg_cognitive_load=2.0,
            stale_1on1_count=3,  # 75% stale
            coaching_active_count=0,
        )
        state, evidence = classify_larson_state(team)
        assert state == "falling-behind"
        assert any("stale" in e for e in evidence)

    def test_treading_water(self):
        team = TeamState(
            name="devops",
            size=3,
            avg_cognitive_load=3.5,
            stale_1on1_count=0,
            coaching_active_count=0,
        )
        state, evidence = classify_larson_state(team)
        assert state == "treading-water"
        assert any("no active coaching" in e for e in evidence)

    def test_repaying_debt(self):
        team = TeamState(
            name="platform",
            size=4,
            avg_cognitive_load=3.0,
            stale_1on1_count=1,
            coaching_active_count=2,
        )
        state, evidence = classify_larson_state(team)
        assert state == "repaying-debt"
        assert any("coaching" in e for e in evidence)

    def test_innovating(self):
        team = TeamState(
            name="platform",
            size=3,
            avg_cognitive_load=2.0,
            stale_1on1_count=0,
            coaching_active_count=1,
        )
        state, evidence = classify_larson_state(team)
        assert state == "innovating"
        assert any("< 3" in e for e in evidence)
        assert any("coaching" in e for e in evidence)
        assert any("no stale" in e for e in evidence)

    def test_insufficient_data_empty_team(self):
        team = TeamState(name="empty", size=0)
        state, evidence = classify_larson_state(team)
        assert state == ""
        assert evidence == []

    def test_insufficient_data_no_load(self):
        team = TeamState(
            name="new",
            size=2,
            avg_cognitive_load=None,
            stale_1on1_count=0,
            coaching_active_count=0,
        )
        state, evidence = classify_larson_state(team)
        assert state == ""

    def test_boundary_load_exactly_4(self):
        team = TeamState(
            name="edge",
            size=2,
            avg_cognitive_load=4.0,
            stale_1on1_count=0,
            coaching_active_count=0,
        )
        state, _ = classify_larson_state(team)
        assert state == "falling-behind"

    def test_boundary_stale_exactly_50_pct(self):
        team = TeamState(
            name="edge",
            size=4,
            avg_cognitive_load=2.0,
            stale_1on1_count=2,  # exactly 50%
            coaching_active_count=0,
        )
        state, _ = classify_larson_state(team)
        # 50% is not > 50%, so not falling-behind
        assert state != "falling-behind"


# ── collect_team_health ────────────────────────────────────────────────────


class TestCollectTeamHealth:
    def test_empty_snapshot_returns_empty(self):
        """With empty management snapshot, team health is empty."""
        snap = collect_team_health(snapshot=ManagementSnapshot())
        assert snap.total_people == 0
        assert snap.teams == []

    def test_groups_by_team(self):
        """With mocked management state, teams are grouped correctly."""
        mock_snap = ManagementSnapshot(
            people=[
                PersonState(name="Alice", team="platform", cognitive_load=3),
                PersonState(name="Bob", team="sre", cognitive_load=2),
                PersonState(name="Charlie", team="platform", cognitive_load=4),
            ],
            active_people_count=3,
        )
        with patch("logos.data.team_health.collect_management_state", return_value=mock_snap):
            snap = collect_team_health()

        assert snap.total_people == 3
        assert len(snap.teams) == 2
        team_names = {t.name for t in snap.teams}
        assert team_names == {"platform", "sre"}

        platform = next(t for t in snap.teams if t.name == "platform")
        assert platform.size == 2
        assert platform.avg_cognitive_load == 3.5

    def test_team_state_aggregation(self):
        mock_snap = ManagementSnapshot(
            people=[
                PersonState(
                    name="Alice",
                    team="platform",
                    cognitive_load=5,
                    stale_1on1=True,
                    days_since_1on1=15,
                    coaching_active=True,
                ),
                PersonState(name="Bob", team="platform", cognitive_load=3),
            ],
            active_people_count=2,
        )
        with patch("logos.data.team_health.collect_management_state", return_value=mock_snap):
            snap = collect_team_health()

        platform = snap.teams[0]
        assert platform.avg_cognitive_load == 4.0
        assert platform.high_load_count == 1
        assert platform.stale_1on1_count == 1
        assert platform.coaching_active_count == 1

    def test_unassigned_team(self):
        mock_snap = ManagementSnapshot(
            people=[PersonState(name="Lone", cognitive_load=2)],
            active_people_count=1,
        )
        with patch("logos.data.team_health.collect_management_state", return_value=mock_snap):
            snap = collect_team_health()

        assert len(snap.teams) == 1
        assert snap.teams[0].name == "unassigned"

    def test_falling_behind_counted(self):
        mock_snap = ManagementSnapshot(
            people=[
                PersonState(name="A", team="overloaded", cognitive_load=5),
                PersonState(name="B", team="overloaded", cognitive_load=4),
            ],
            active_people_count=2,
        )
        with patch("logos.data.team_health.collect_management_state", return_value=mock_snap):
            snap = collect_team_health()

        assert snap.teams_falling_behind == 1


# ── _compute_majority_team_type ────────────────────────────────────────────


class TestComputeMajorityTeamType:
    def test_majority(self):
        members = [
            PersonState(name="A", team_type="stream-aligned"),
            PersonState(name="B", team_type="stream-aligned"),
            PersonState(name="C", team_type="platform"),
        ]
        assert _compute_majority_team_type(members) == "stream-aligned"

    def test_no_types(self):
        members = [PersonState(name="A"), PersonState(name="B")]
        assert _compute_majority_team_type(members) == ""

    def test_empty_list(self):
        assert _compute_majority_team_type([]) == ""
