"""Tests for cockpit/data/review_cycles.py."""

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


class TestCollectReviewCycles:
    def test_active_cycle(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        _write_md(
            tmp_path / "review-cycles" / "2026-h1-sarah.md",
            {
                "type": "review-cycle",
                "cycle": "2026-H1",
                "person": "Sarah Chen",
                "status": "self-assessment-due",
                "self-assessment-due": "2026-04-15",
                "self-assessment-received": False,
                "peer-feedback-requested": 3,
                "peer-feedback-received": 1,
                "review-due": "2026-05-01",
                "calibration-date": "2026-05-10",
                "delivered": False,
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_review_cycle_state()
        finally:
            config.reset_data_dir()

        assert snap.active_count == 1
        assert snap.cycles[0].person == "Sarah Chen"
        assert snap.cycles[0].peer_feedback_gap == 2

    def test_overdue_cycle(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        _write_md(
            tmp_path / "review-cycles" / "2025-h2-late.md",
            {
                "type": "review-cycle",
                "cycle": "2025-H2",
                "person": "Bob",
                "status": "writing",
                "review-due": "2026-01-01",
                "delivered": False,
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_review_cycle_state()
        finally:
            config.reset_data_dir()

        assert snap.overdue_count == 1
        assert snap.cycles[0].overdue is True

    def test_delivered_excluded_from_active(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        _write_md(
            tmp_path / "review-cycles" / "2025-h2-done.md",
            {
                "type": "review-cycle",
                "cycle": "2025-H2",
                "person": "Alice",
                "status": "delivered",
                "delivered": True,
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_review_cycle_state()
        finally:
            config.reset_data_dir()

        assert snap.active_count == 0

    def test_peer_feedback_gap_total(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        _write_md(
            tmp_path / "review-cycles" / "2026-h1-a.md",
            {
                "type": "review-cycle",
                "person": "A",
                "status": "writing",
                "peer-feedback-requested": 3,
                "peer-feedback-received": 1,
            },
        )
        _write_md(
            tmp_path / "review-cycles" / "2026-h1-b.md",
            {
                "type": "review-cycle",
                "person": "B",
                "status": "writing",
                "peer-feedback-requested": 4,
                "peer-feedback-received": 2,
            },
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_review_cycle_state()
        finally:
            config.reset_data_dir()

        assert snap.peer_feedback_gap_total == 4  # (3-1) + (4-2)

    def test_missing_dir(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        config.set_data_dir(tmp_path)
        try:
            snap = collect_review_cycle_state()
        finally:
            config.reset_data_dir()

        assert snap.cycles == []
