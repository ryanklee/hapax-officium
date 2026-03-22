"""Tests for logos/data/incidents.py — incident state collection."""

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


class TestCollectIncidents:
    def test_open_incident(self, tmp_path: Path):
        from logos.data.incidents import collect_incident_state

        _write_md(
            tmp_path / "incidents" / "2026-03-05-outage.md",
            {
                "type": "incident",
                "title": "API outage",
                "severity": "sev1",
                "status": "mitigated",
                "detected": "2026-03-05T14:00:00",
                "owner": "Marcus Johnson",
                "teams-affected": ["Platform"],
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_incident_state()
        finally:
            config.reset_data_dir()

        assert snap.open_count == 1
        assert snap.incidents[0].open is True
        assert snap.incidents[0].severity == "sev1"

    def test_closed_incident_not_open(self, tmp_path: Path):
        from logos.data.incidents import collect_incident_state

        _write_md(
            tmp_path / "incidents" / "2026-02-15-resolved.md",
            {
                "type": "incident",
                "title": "Resolved",
                "severity": "sev2",
                "status": "closed",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_incident_state()
        finally:
            config.reset_data_dir()

        assert snap.open_count == 0
        assert snap.incidents[0].open is False

    def test_missing_postmortem_counted(self, tmp_path: Path):
        from logos.data.incidents import collect_incident_state

        _write_md(
            tmp_path / "incidents" / "2026-03-01-no-pm.md",
            {
                "type": "incident",
                "title": "No postmortem",
                "severity": "sev2",
                "status": "mitigated",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_incident_state()
        finally:
            config.reset_data_dir()

        assert snap.missing_postmortem_count == 1
        assert snap.incidents[0].has_postmortem is False

    def test_postmortem_complete_has_postmortem(self, tmp_path: Path):
        from logos.data.incidents import collect_incident_state

        _write_md(
            tmp_path / "incidents" / "2026-02-15-done.md",
            {
                "type": "incident",
                "title": "Done",
                "severity": "sev1",
                "status": "postmortem-complete",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_incident_state()
        finally:
            config.reset_data_dir()

        assert snap.incidents[0].has_postmortem is True

    def test_teams_affected_parsed(self, tmp_path: Path):
        from logos.data.incidents import collect_incident_state

        _write_md(
            tmp_path / "incidents" / "2026-03-05-multi.md",
            {
                "type": "incident",
                "title": "Multi-team",
                "severity": "sev1",
                "status": "mitigated",
                "teams-affected": ["Platform", "Product", "Data"],
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_incident_state()
        finally:
            config.reset_data_dir()

        assert snap.incidents[0].teams_affected == ["Platform", "Product", "Data"]

    def test_missing_dir(self, tmp_path: Path):
        from logos.data.incidents import collect_incident_state

        config.set_data_dir(tmp_path)
        try:
            snap = collect_incident_state()
        finally:
            config.reset_data_dir()

        assert snap.incidents == []
