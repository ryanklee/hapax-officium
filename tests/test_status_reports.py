"""Tests for cockpit/data/status_reports.py."""

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


class TestCollectStatusReports:
    def test_current_report(self, tmp_path: Path):
        from datetime import date

        from cockpit.data.status_reports import collect_status_report_state

        today = date.today().isoformat()
        _write_md(
            tmp_path / "status-reports" / f"{today}-weekly.md",
            {
                "type": "status-report",
                "date": today,
                "cadence": "weekly",
                "direction": "upward",
                "generated": True,
                "edited": True,
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_status_report_state()
        finally:
            config.reset_data_dir()

        assert len(snap.reports) == 1
        assert snap.latest_date == today
        assert snap.stale is False

    def test_stale_weekly(self, tmp_path: Path):
        from cockpit.data.status_reports import collect_status_report_state

        _write_md(
            tmp_path / "status-reports" / "2026-01-01-weekly.md",
            {
                "type": "status-report",
                "date": "2026-01-01",
                "cadence": "weekly",
                "direction": "upward",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_status_report_state()
        finally:
            config.reset_data_dir()

        assert snap.stale is True
        assert snap.reports[0].stale is True

    def test_missing_dir(self, tmp_path: Path):
        from cockpit.data.status_reports import collect_status_report_state

        config.set_data_dir(tmp_path)
        try:
            snap = collect_status_report_state()
        finally:
            config.reset_data_dir()

        assert snap.reports == []
        assert snap.stale is False

    def test_latest_date_is_most_recent(self, tmp_path: Path):
        from cockpit.data.status_reports import collect_status_report_state

        _write_md(
            tmp_path / "status-reports" / "2026-02-01-weekly.md",
            {
                "type": "status-report",
                "date": "2026-02-01",
                "cadence": "weekly",
            },
        )
        _write_md(
            tmp_path / "status-reports" / "2026-03-01-weekly.md",
            {
                "type": "status-report",
                "date": "2026-03-01",
                "cadence": "weekly",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_status_report_state()
        finally:
            config.reset_data_dir()

        assert snap.latest_date == "2026-03-01"
