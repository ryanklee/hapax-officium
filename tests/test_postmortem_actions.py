"""Tests for logos/data/postmortem_actions.py."""

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


class TestCollectPostmortemActions:
    def test_open_action(self, tmp_path: Path):
        from logos.data.postmortem_actions import collect_postmortem_action_state

        _write_md(
            tmp_path / "postmortem-actions" / "add-alerting.md",
            {
                "type": "postmortem-action",
                "incident-ref": "2026-02-15-api-gateway-outage",
                "title": "Add alerting",
                "owner": "Marcus",
                "status": "open",
                "priority": "high",
                "due-date": "2026-03-01",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_postmortem_action_state()
        finally:
            config.reset_data_dir()

        assert snap.open_count == 1
        assert snap.actions[0].title == "Add alerting"

    def test_overdue_action(self, tmp_path: Path):
        from logos.data.postmortem_actions import collect_postmortem_action_state

        _write_md(
            tmp_path / "postmortem-actions" / "overdue.md",
            {
                "type": "postmortem-action",
                "title": "Overdue task",
                "status": "open",
                "due-date": "2026-01-01",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_postmortem_action_state()
        finally:
            config.reset_data_dir()

        assert snap.overdue_count == 1
        assert snap.actions[0].overdue is True
        assert snap.actions[0].days_overdue > 0

    def test_completed_not_open(self, tmp_path: Path):
        from logos.data.postmortem_actions import collect_postmortem_action_state

        _write_md(
            tmp_path / "postmortem-actions" / "done.md",
            {
                "type": "postmortem-action",
                "title": "Done",
                "status": "completed",
                "completed-date": "2026-02-20",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_postmortem_action_state()
        finally:
            config.reset_data_dir()

        assert snap.open_count == 0

    def test_missing_dir(self, tmp_path: Path):
        from logos.data.postmortem_actions import collect_postmortem_action_state

        config.set_data_dir(tmp_path)
        try:
            snap = collect_postmortem_action_state()
        finally:
            config.reset_data_dir()

        assert snap.actions == []
