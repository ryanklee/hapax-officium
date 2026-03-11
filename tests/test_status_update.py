"""Tests for agents/status_update.py — status report data gathering and model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import yaml

from agents.status_update import (
    StatusReport,
    _body_excerpt,
    _file_date,
    _format_context_for_prompt,
    _gather_week_context,
    _parse_frontmatter,
    _save_report,
)
from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    """Write a markdown file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


# ── StatusReport model ───────────────────────────────────────────────────


class TestStatusReportModel:
    def test_all_fields(self):
        report = StatusReport(
            headline="Good week overall",
            themes=["alignment improving", "hiring pipeline healthy"],
            risks=["headcount freeze possible"],
            wins=["shipped v2.0"],
            asks=["need budget approval"],
        )
        assert report.headline == "Good week overall"
        assert len(report.themes) == 2
        assert len(report.risks) == 1
        assert len(report.wins) == 1
        assert len(report.asks) == 1

    def test_defaults_empty_lists(self):
        report = StatusReport(headline="Quiet week")
        assert report.themes == []
        assert report.risks == []
        assert report.wins == []
        assert report.asks == []

    def test_serialization(self):
        report = StatusReport(
            headline="test",
            themes=["a"],
            risks=["b"],
            wins=["c"],
            asks=["d"],
        )
        data = report.model_dump()
        assert data["headline"] == "test"
        assert data["themes"] == ["a"]


# ── _parse_frontmatter ──────────────────────────────────────────────────


class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path: Path):
        _write_md(tmp_path / "test.md", {"type": "meeting", "date": "2026-03-05"}, "Body text")
        fm, body = _parse_frontmatter(tmp_path / "test.md")
        assert fm["type"] == "meeting"
        assert fm["date"] == "2026-03-05"
        assert "Body text" in body

    def test_no_frontmatter(self, tmp_path: Path):
        path = tmp_path / "plain.md"
        path.write_text("Just some text", encoding="utf-8")
        fm, body = _parse_frontmatter(path)
        assert fm == {}
        assert "Just some text" in body

    def test_missing_file(self, tmp_path: Path):
        fm, body = _parse_frontmatter(tmp_path / "nonexistent.md")
        assert fm == {}
        assert body == ""


# ── _file_date ──────────────────────────────────────────────────────────


class TestFileDate:
    def test_date_from_frontmatter(self, tmp_path: Path):
        path = tmp_path / "test.md"
        dt = _file_date({"date": "2026-03-05"}, path)
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 5

    def test_date_from_filename(self, tmp_path: Path):
        path = tmp_path / "2026-03-07-standup.md"
        dt = _file_date({}, path)
        assert dt is not None
        assert dt.day == 7

    def test_no_date_returns_none(self, tmp_path: Path):
        path = tmp_path / "random-notes.md"
        dt = _file_date({}, path)
        assert dt is None

    def test_datetime_in_frontmatter(self, tmp_path: Path):
        path = tmp_path / "test.md"
        now = datetime(2026, 3, 5, 10, 0, 0, tzinfo=UTC)
        dt = _file_date({"date": now}, path)
        assert dt == now

    def test_created_at_iso(self, tmp_path: Path):
        path = tmp_path / "test.md"
        dt = _file_date({"created_at": "2026-03-05T10:00:00Z"}, path)
        assert dt is not None
        assert dt.day == 5


# ── _body_excerpt ───────────────────────────────────────────────────────


class TestBodyExcerpt:
    def test_short_body_unchanged(self):
        assert _body_excerpt("short text") == "short text"

    def test_long_body_truncated(self):
        text = "a" * 600
        result = _body_excerpt(text, max_chars=500)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")

    def test_strips_whitespace(self):
        assert _body_excerpt("  hello  ") == "hello"


# ── _gather_week_context ────────────────────────────────────────────────


class TestGatherWeekContext:
    def test_returns_correct_structure(self, tmp_path: Path):
        # Create meeting file with recent date
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{today}-standup.md",
            {
                "type": "meeting",
                "title": "Daily Standup",
                "date": today,
            },
            "Discussed blockers",
        )

        config.set_data_dir(tmp_path)
        try:
            ctx = _gather_week_context(days=7)
        finally:
            config.reset_data_dir()

        assert "meetings" in ctx
        assert "coaching" in ctx
        assert "feedback" in ctx
        assert len(ctx["meetings"]) == 1
        assert ctx["meetings"][0]["filename"] == f"{today}-standup.md"
        assert ctx["meetings"][0]["frontmatter"]["title"] == "Daily Standup"
        assert "Discussed blockers" in ctx["meetings"][0]["excerpt"]

    def test_date_filtering_excludes_old(self, tmp_path: Path):
        # Old file (30 days ago)
        old_date = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{old_date}-old.md",
            {
                "type": "meeting",
                "title": "Old Meeting",
                "date": old_date,
            },
            "Old content",
        )

        # Recent file
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{today}-new.md",
            {
                "type": "meeting",
                "title": "New Meeting",
                "date": today,
            },
            "New content",
        )

        config.set_data_dir(tmp_path)
        try:
            ctx = _gather_week_context(days=7)
        finally:
            config.reset_data_dir()

        assert len(ctx["meetings"]) == 1
        assert ctx["meetings"][0]["frontmatter"]["title"] == "New Meeting"

    def test_includes_file_without_date(self, tmp_path: Path):
        # File with no parseable date should be included (not excluded)
        _write_md(
            tmp_path / "meetings" / "undated-notes.md",
            {
                "type": "meeting",
                "title": "Undated Notes",
            },
            "Some content",
        )

        config.set_data_dir(tmp_path)
        try:
            ctx = _gather_week_context(days=7)
        finally:
            config.reset_data_dir()

        assert len(ctx["meetings"]) == 1

    def test_multiple_categories(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        _write_md(
            tmp_path / "meetings" / f"{today}-standup.md",
            {
                "type": "meeting",
                "title": "Standup",
                "date": today,
            },
        )
        _write_md(
            tmp_path / "coaching" / f"{today}-experiment.md",
            {
                "type": "coaching",
                "title": "Experiment A",
                "date": today,
            },
        )
        _write_md(
            tmp_path / "feedback" / f"{today}-peer.md",
            {
                "type": "feedback",
                "title": "Peer Review",
                "date": today,
            },
        )

        config.set_data_dir(tmp_path)
        try:
            ctx = _gather_week_context(days=7)
        finally:
            config.reset_data_dir()

        assert len(ctx["meetings"]) == 1
        assert len(ctx["coaching"]) == 1
        assert len(ctx["feedback"]) == 1

    def test_empty_dirs(self, tmp_path: Path):
        (tmp_path / "meetings").mkdir()
        (tmp_path / "coaching").mkdir()
        (tmp_path / "feedback").mkdir()

        config.set_data_dir(tmp_path)
        try:
            ctx = _gather_week_context(days=7)
        finally:
            config.reset_data_dir()

        assert ctx["meetings"] == []
        assert ctx["coaching"] == []
        assert ctx["feedback"] == []

    def test_missing_dirs(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            ctx = _gather_week_context(days=7)
        finally:
            config.reset_data_dir()

        assert ctx["meetings"] == []
        assert ctx["coaching"] == []
        assert ctx["feedback"] == []

    def test_daily_lookback(self, tmp_path: Path):
        # 3 days ago — should be excluded for daily
        old_date = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{old_date}-old.md",
            {
                "type": "meeting",
                "title": "3 Days Ago",
                "date": old_date,
            },
        )

        # Today — should be included
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{today}-today.md",
            {
                "type": "meeting",
                "title": "Today",
                "date": today,
            },
        )

        config.set_data_dir(tmp_path)
        try:
            ctx = _gather_week_context(days=1)
        finally:
            config.reset_data_dir()

        assert len(ctx["meetings"]) == 1
        assert ctx["meetings"][0]["frontmatter"]["title"] == "Today"


# ── _format_context_for_prompt ──────────────────────────────────────────


class TestFormatContextForPrompt:
    def test_includes_period(self):
        ctx = {"meetings": [], "coaching": [], "feedback": []}
        prompt = _format_context_for_prompt(ctx, days=7)
        assert "7 days" in prompt

    def test_daily_period(self):
        ctx = {"meetings": [], "coaching": [], "feedback": []}
        prompt = _format_context_for_prompt(ctx, days=1)
        assert "last day" in prompt

    def test_includes_file_data(self):
        ctx = {
            "meetings": [
                {
                    "filename": "2026-03-05-standup.md",
                    "frontmatter": {"title": "Daily Standup", "date": "2026-03-05"},
                    "excerpt": "Discussed blockers",
                }
            ],
            "coaching": [],
            "feedback": [],
        }
        prompt = _format_context_for_prompt(ctx, days=7)
        assert "Daily Standup" in prompt
        assert "Discussed blockers" in prompt

    def test_empty_context_notes_gap(self):
        ctx = {"meetings": [], "coaching": [], "feedback": []}
        prompt = _format_context_for_prompt(ctx, days=7)
        assert "No data files found" in prompt


# ── _save_report ────────────────────────────────────────────────────────


class TestSaveReport:
    def test_saves_weekly(self, tmp_path: Path):
        report = StatusReport(
            headline="Good week",
            themes=["alignment"],
            risks=["headcount"],
            wins=["shipped"],
            asks=["budget"],
        )

        config.set_data_dir(tmp_path)
        try:
            path = _save_report(report, days=7)
        finally:
            config.reset_data_dir()

        assert path.exists()
        assert "status-weekly-" in path.name
        content = path.read_text()
        assert "Good week" in content
        assert "alignment" in content
        assert "headcount" in content
        assert "shipped" in content
        assert "budget" in content
        assert "period: weekly" in content

    def test_saves_daily(self, tmp_path: Path):
        report = StatusReport(headline="Quick day")

        config.set_data_dir(tmp_path)
        try:
            path = _save_report(report, days=1)
        finally:
            config.reset_data_dir()

        assert "status-daily-" in path.name
        content = path.read_text()
        assert "period: daily" in content
