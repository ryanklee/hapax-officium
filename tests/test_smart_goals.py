"""Tests for logos/data/smart_goals.py — SMART goal collection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


class TestCollectSmartGoals:
    def test_active_goal(self, tmp_path: Path):
        from logos.data.smart_goals import collect_smart_goal_state

        _write_md(
            tmp_path / "goals" / "sarah-principal.md",
            {
                "type": "goal",
                "framework": "smart",
                "person": "Sarah Chen",
                "status": "active",
                "category": "career-development",
                "created": "2026-01-15",
                "target-date": "2026-06-30",
                "last-reviewed": "2026-03-01",
                "review-cadence": "quarterly",
                "specific": "Lead cross-team review",
                "measurable": "Approved by 3+ leads",
                "achievable": "Has led single-team reviews",
                "relevant": "Aligns with promo criteria",
                "time-bound": "Q2 2026",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_smart_goal_state()
        finally:
            config.reset_data_dir()

        assert snap.active_count == 1
        assert snap.goals[0].person == "Sarah Chen"
        assert snap.goals[0].specific == "Lead cross-team review"

    def test_overdue_goal(self, tmp_path: Path):
        from logos.data.smart_goals import collect_smart_goal_state

        _write_md(
            tmp_path / "goals" / "jordan-overdue.md",
            {
                "type": "goal",
                "framework": "smart",
                "person": "Jordan Kim",
                "status": "active",
                "target-date": "2026-01-15",
                "specific": "Past due goal",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_smart_goal_state()
        finally:
            config.reset_data_dir()

        assert snap.overdue_count == 1
        assert snap.goals[0].overdue is True

    def test_review_overdue(self, tmp_path: Path):
        from logos.data.smart_goals import collect_smart_goal_state

        _write_md(
            tmp_path / "goals" / "marcus-stale.md",
            {
                "type": "goal",
                "framework": "smart",
                "person": "Marcus",
                "status": "active",
                "last-reviewed": "2025-10-01",
                "review-cadence": "quarterly",
                "specific": "Stale review",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_smart_goal_state()
        finally:
            config.reset_data_dir()

        assert snap.review_overdue_count == 1
        assert snap.goals[0].review_overdue is True

    def test_completed_excluded_from_active(self, tmp_path: Path):
        from logos.data.smart_goals import collect_smart_goal_state

        _write_md(
            tmp_path / "goals" / "done.md",
            {
                "type": "goal",
                "framework": "smart",
                "person": "Alice",
                "status": "completed",
                "specific": "Done goal",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_smart_goal_state()
        finally:
            config.reset_data_dir()

        assert snap.active_count == 0
        assert len(snap.goals) == 1

    def test_missing_dir(self, tmp_path: Path):
        from logos.data.smart_goals import collect_smart_goal_state

        config.set_data_dir(tmp_path)
        try:
            snap = collect_smart_goal_state()
        finally:
            config.reset_data_dir()

        assert snap.goals == []

    def test_wrong_type_skipped(self, tmp_path: Path):
        from logos.data.smart_goals import collect_smart_goal_state

        _write_md(
            tmp_path / "goals" / "not-goal.md",
            {
                "type": "person",
                "name": "Alice",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_smart_goal_state()
        finally:
            config.reset_data_dir()

        assert snap.goals == []
