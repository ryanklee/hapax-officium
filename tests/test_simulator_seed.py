# ai-agents/tests/test_simulator_seed.py
"""Tests for seed date rebasing."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from agents.simulator_pipeline.seed import find_latest_date, rebase_seed_dates

if TYPE_CHECKING:
    from pathlib import Path


class TestFindLatestDate:
    def test_finds_latest_date_in_frontmatter(self, tmp_path: Path):
        """Scans frontmatter for date fields and returns the latest."""
        (tmp_path / "people").mkdir()
        (tmp_path / "people" / "alice.md").write_text(
            "---\ntype: person\nlast-1on1: 2026-03-08\n---\n"
        )
        (tmp_path / "coaching").mkdir()
        (tmp_path / "coaching" / "note.md").write_text(
            "---\ntype: coaching\ncheck-in-by: 2026-03-10\n---\n"
        )
        result = find_latest_date(tmp_path)
        assert result == date(2026, 3, 10)

    def test_returns_none_for_no_dates(self, tmp_path: Path):
        """Returns None if no date fields found."""
        (tmp_path / "people").mkdir()
        (tmp_path / "people" / "alice.md").write_text("---\ntype: person\nname: Alice\n---\n")
        result = find_latest_date(tmp_path)
        assert result is None

    def test_ignores_body_dates(self, tmp_path: Path):
        """Dates in body content (not frontmatter) are ignored."""
        (tmp_path / "meetings").mkdir()
        (tmp_path / "meetings" / "meeting.md").write_text(
            "---\ntype: meeting\n---\nMet on 2099-12-31 to discuss things.\n"
        )
        result = find_latest_date(tmp_path)
        assert result is None


class TestRebaseSeedDates:
    def test_shifts_dates_backward(self, tmp_path: Path):
        """Rebases seed dates relative to simulation start_date."""
        (tmp_path / "people").mkdir()
        (tmp_path / "people" / "alice.md").write_text(
            "---\ntype: person\nlast-1on1: 2026-03-08\n---\nBody text.\n"
        )
        (tmp_path / "coaching").mkdir()
        (tmp_path / "coaching" / "note.md").write_text(
            "---\ntype: coaching\ncheck-in-by: 2026-03-10\ncreated: 2026-03-01\n---\nCoaching.\n"
        )

        # Latest seed date is 2026-03-10, sim starts 2026-01-01
        # Offset = sim_start - latest - 1 = 2026-01-01 - 2026-03-10 - 1 = -69 days
        rebase_seed_dates(tmp_path, sim_start=date(2026, 1, 1))

        alice = (tmp_path / "people" / "alice.md").read_text()
        assert "2026-03-08" not in alice
        # Body preserved
        assert "Body text." in alice

        note = (tmp_path / "coaching" / "note.md").read_text()
        assert "2026-03-10" not in note
        assert "2026-03-01" not in note
        assert "Coaching." in note

    def test_noop_when_no_dates(self, tmp_path: Path):
        """No-op if seed has no date fields."""
        (tmp_path / "people").mkdir()
        (tmp_path / "people" / "alice.md").write_text("---\ntype: person\nname: Alice\n---\n")
        rebase_seed_dates(tmp_path, sim_start=date(2026, 1, 1))
        content = (tmp_path / "people" / "alice.md").read_text()
        assert "name: Alice" in content

    def test_preserves_non_date_content(self, tmp_path: Path):
        """Non-date frontmatter and body content are preserved."""
        (tmp_path / "people").mkdir()
        (tmp_path / "people" / "alice.md").write_text(
            "---\ntype: person\nname: Alice\nteam: platform\nlast-1on1: 2026-03-08\n---\nAlice body.\n"
        )
        rebase_seed_dates(tmp_path, sim_start=date(2026, 1, 1))
        content = (tmp_path / "people" / "alice.md").read_text()
        assert "name: Alice" in content
        assert "team: platform" in content
        assert "Alice body." in content
