"""Tests for agents/review_prep.py — review evidence data gathering and model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import yaml

from agents.review_prep import (
    ReviewEvidence,
    _gather_person_evidence,
    _save_review,
)
from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    """Write a markdown file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


# ── ReviewEvidence model ─────────────────────────────────────────────────


class TestReviewEvidenceModel:
    def test_all_fields(self):
        review = ReviewEvidence(
            person="Alice",
            period_months=6,
            contributions=["Led API redesign (2026-01-15)"],
            growth_trajectory=["Took on cross-team coordination in Q1"],
            development_areas=["Documentation coverage declined in Feb"],
            evidence_citations=["meetings/2026-01-15-1on1.md: discussed API work"],
        )
        assert review.person == "Alice"
        assert review.period_months == 6
        assert len(review.contributions) == 1
        assert len(review.growth_trajectory) == 1
        assert len(review.development_areas) == 1
        assert len(review.evidence_citations) == 1

    def test_defaults_empty_lists(self):
        review = ReviewEvidence(person="Bob", period_months=3)
        assert review.contributions == []
        assert review.growth_trajectory == []
        assert review.development_areas == []
        assert review.evidence_citations == []

    def test_serialization(self):
        review = ReviewEvidence(
            person="Alice",
            period_months=6,
            contributions=["a"],
            growth_trajectory=["b"],
            development_areas=["c"],
            evidence_citations=["d"],
        )
        data = review.model_dump()
        assert data["person"] == "Alice"
        assert data["period_months"] == 6
        assert data["contributions"] == ["a"]


# ── _gather_person_evidence — meetings via attendees ─────────────────────


class TestGatherMeetingsByAttendees:
    def test_matches_attendees_list(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{today}-1on1.md",
            {
                "type": "meeting",
                "title": "1:1 with Alice",
                "date": today,
                "attendees": ["Alice", "Operator"],
            },
            "Discussed project status",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["meetings"]) == 1
        assert ev["meetings"][0]["filename"] == f"{today}-1on1.md"

    def test_attendee_case_insensitive(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{today}-1on1.md",
            {
                "type": "meeting",
                "title": "1:1",
                "date": today,
                "attendees": ["ALICE", "Operator"],
            },
            "Content",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["meetings"]) == 1


# ── _gather_person_evidence — meetings via body text ─────────────────────


class TestGatherMeetingsByBodyText:
    def test_matches_body_mention(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{today}-standup.md",
            {
                "type": "meeting",
                "title": "Standup",
                "date": today,
            },
            "Alice presented the new design",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["meetings"]) == 1

    def test_no_match_excludes(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{today}-standup.md",
            {
                "type": "meeting",
                "title": "Standup",
                "date": today,
            },
            "Bob presented the new design",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["meetings"]) == 0


# ── _gather_person_evidence — coaching ───────────────────────────────────


class TestGatherCoaching:
    def test_matches_person_field(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "coaching" / f"{today}-experiment.md",
            {
                "type": "coaching",
                "title": "Delegation experiment",
                "person": "Alice",
                "date": today,
            },
            "Trying to delegate more reviews",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["coaching"]) == 1
        assert ev["coaching"][0]["frontmatter"]["title"] == "Delegation experiment"

    def test_excludes_other_person(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "coaching" / f"{today}-experiment.md",
            {
                "type": "coaching",
                "title": "Delegation experiment",
                "person": "Bob",
                "date": today,
            },
            "Content",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["coaching"]) == 0


# ── _gather_person_evidence — feedback ───────────────────────────────────


class TestGatherFeedback:
    def test_matches_person_field(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "feedback" / f"{today}-code-review.md",
            {
                "type": "feedback",
                "title": "Code review quality",
                "person": "Alice",
                "direction": "given",
                "date": today,
            },
            "Feedback on code review thoroughness",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["feedback"]) == 1

    def test_person_case_insensitive(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "feedback" / f"{today}-review.md",
            {
                "type": "feedback",
                "person": "alice",
                "date": today,
            },
            "Content",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["feedback"]) == 1


# ── Date filtering ───────────────────────────────────────────────────────


class TestDateFiltering:
    def test_excludes_old_evidence(self, tmp_path: Path):
        old_date = (datetime.now(UTC) - timedelta(days=200)).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{old_date}-old.md",
            {
                "type": "meeting",
                "title": "Old meeting",
                "date": old_date,
                "attendees": ["Alice"],
            },
            "Old content",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["meetings"]) == 0

    def test_includes_recent_evidence(self, tmp_path: Path):
        recent = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "coaching" / f"{recent}-exp.md",
            {
                "type": "coaching",
                "title": "Recent coaching",
                "person": "Alice",
                "date": recent,
            },
            "Recent",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["coaching"]) == 1

    def test_includes_undated_files(self, tmp_path: Path):
        """Files without parseable dates should be included (not excluded)."""
        _write_md(
            tmp_path / "feedback" / "undated-feedback.md",
            {
                "type": "feedback",
                "person": "Alice",
            },
            "Undated feedback content",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert len(ev["feedback"]) == 1

    def test_longer_period_includes_more(self, tmp_path: Path):
        """12-month lookback should include files that 3-month excludes."""
        five_months_ago = (datetime.now(UTC) - timedelta(days=150)).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{five_months_ago}-meeting.md",
            {
                "type": "meeting",
                "title": "5 months ago",
                "date": five_months_ago,
                "attendees": ["Alice"],
            },
            "Content from 5 months ago",
        )

        config.set_data_dir(tmp_path)
        try:
            ev_3 = _gather_person_evidence("Alice", months=3)
            ev_12 = _gather_person_evidence("Alice", months=12)
        finally:
            config.reset_data_dir()

        assert len(ev_3["meetings"]) == 0
        assert len(ev_12["meetings"]) == 1


# ── Unknown person ───────────────────────────────────────────────────────


class TestUnknownPerson:
    def test_returns_empty_evidence(self, tmp_path: Path):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _write_md(
            tmp_path / "meetings" / f"{today}-standup.md",
            {
                "type": "meeting",
                "title": "Standup",
                "date": today,
                "attendees": ["Bob", "Carol"],
            },
            "Bob and Carol discussed roadmap",
        )

        _write_md(
            tmp_path / "coaching" / f"{today}-coaching.md",
            {
                "type": "coaching",
                "person": "Bob",
                "date": today,
            },
            "Bob coaching",
        )

        _write_md(
            tmp_path / "feedback" / f"{today}-feedback.md",
            {
                "type": "feedback",
                "person": "Carol",
                "date": today,
            },
            "Carol feedback",
        )

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Nonexistent Person", months=6)
        finally:
            config.reset_data_dir()

        assert ev["meetings"] == []
        assert ev["coaching"] == []
        assert ev["feedback"] == []

    def test_empty_dirs(self, tmp_path: Path):
        (tmp_path / "meetings").mkdir()
        (tmp_path / "coaching").mkdir()
        (tmp_path / "feedback").mkdir()

        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert ev == {"meetings": [], "coaching": [], "feedback": []}

    def test_missing_dirs(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            ev = _gather_person_evidence("Alice", months=6)
        finally:
            config.reset_data_dir()

        assert ev == {"meetings": [], "coaching": [], "feedback": []}


# ── _save_review ─────────────────────────────────────────────────────────


class TestSaveReview:
    def test_saves_to_references(self, tmp_path: Path):
        review = ReviewEvidence(
            person="Alice",
            period_months=6,
            contributions=["Led API redesign"],
            growth_trajectory=["Expanded scope"],
            development_areas=["Documentation"],
            evidence_citations=["meetings/2026-01-15.md"],
        )

        config.set_data_dir(tmp_path)
        try:
            path = _save_review(review)
        finally:
            config.reset_data_dir()

        assert path.exists()
        assert "review-evidence-alice-" in path.name
        content = path.read_text()
        assert "person: Alice" in content
        assert "Led API redesign" in content
        assert "Expanded scope" in content
        assert "Documentation" in content
        assert "meetings/2026-01-15.md" in content

    def test_filename_slug(self, tmp_path: Path):
        review = ReviewEvidence(
            person="Alice Smith",
            period_months=12,
        )

        config.set_data_dir(tmp_path)
        try:
            path = _save_review(review)
        finally:
            config.reset_data_dir()

        assert "review-evidence-alice-smith-" in path.name
