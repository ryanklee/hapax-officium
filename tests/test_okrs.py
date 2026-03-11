"""Tests for cockpit/data/okrs.py — OKR state collection."""

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


class TestCollectOKRs:
    def test_active_okr_with_key_results(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(
            tmp_path / "okrs" / "2026-q1-platform.md",
            {
                "type": "okr",
                "scope": "team",
                "team": "Platform",
                "quarter": "2026-Q1",
                "status": "active",
                "objective": "Improve reliability",
                "key-results": [
                    {
                        "id": "kr1",
                        "description": "Reduce P99",
                        "target": 200,
                        "current": 310,
                        "unit": "ms",
                        "direction": "decrease",
                        "confidence": 0.6,
                        "last-updated": "2026-02-28",
                    },
                    {
                        "id": "kr2",
                        "description": "Uptime",
                        "target": 99.95,
                        "current": 99.91,
                        "unit": "percent",
                        "direction": "increase",
                        "confidence": 0.8,
                        "last-updated": "2026-03-05",
                    },
                ],
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_okr_state()
        finally:
            config.reset_data_dir()

        assert snap.active_count == 1
        assert len(snap.okrs) == 1
        okr = snap.okrs[0]
        assert okr.objective == "Improve reliability"
        assert okr.team == "Platform"
        assert len(okr.key_results) == 2
        assert okr.key_results[0].confidence == 0.6

    def test_scored_okr_excluded_from_active(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(
            tmp_path / "okrs" / "2025-q4-done.md",
            {
                "type": "okr",
                "status": "scored",
                "objective": "Old OKR",
                "quarter": "2025-Q4",
                "score": 0.7,
                "scored-at": "2026-01-05",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_okr_state()
        finally:
            config.reset_data_dir()

        assert snap.active_count == 0
        assert len(snap.okrs) == 1

    def test_at_risk_kr_counted(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(
            tmp_path / "okrs" / "2026-q1-risk.md",
            {
                "type": "okr",
                "status": "active",
                "objective": "Risky",
                "quarter": "2026-Q1",
                "key-results": [
                    {
                        "id": "kr1",
                        "description": "Bad",
                        "target": 100,
                        "current": 10,
                        "confidence": 0.3,
                        "last-updated": "2026-03-01",
                    },
                    {
                        "id": "kr2",
                        "description": "Ok",
                        "target": 100,
                        "current": 80,
                        "confidence": 0.9,
                        "last-updated": "2026-03-01",
                    },
                ],
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_okr_state()
        finally:
            config.reset_data_dir()

        assert snap.at_risk_count == 1
        assert snap.okrs[0].at_risk_count == 1

    def test_stale_kr_detected(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(
            tmp_path / "okrs" / "2026-q1-stale.md",
            {
                "type": "okr",
                "status": "active",
                "objective": "Stale",
                "quarter": "2026-Q1",
                "key-results": [
                    {
                        "id": "kr1",
                        "description": "Old",
                        "target": 100,
                        "current": 50,
                        "confidence": 0.7,
                        "last-updated": "2026-01-01",
                    },
                ],
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_okr_state()
        finally:
            config.reset_data_dir()

        assert snap.stale_kr_count == 1
        assert snap.okrs[0].key_results[0].stale is True

    def test_missing_dir_returns_empty(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        config.set_data_dir(tmp_path)
        try:
            snap = collect_okr_state()
        finally:
            config.reset_data_dir()

        assert snap.okrs == []
        assert snap.active_count == 0

    def test_no_key_results_field(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(
            tmp_path / "okrs" / "2026-q1-bare.md",
            {
                "type": "okr",
                "status": "active",
                "objective": "Bare OKR",
                "quarter": "2026-Q1",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_okr_state()
        finally:
            config.reset_data_dir()

        assert len(snap.okrs) == 1
        assert snap.okrs[0].key_results == []

    def test_wrong_type_skipped(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(
            tmp_path / "okrs" / "not-okr.md",
            {
                "type": "person",
                "name": "Alice",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_okr_state()
        finally:
            config.reset_data_dir()

        assert snap.okrs == []
