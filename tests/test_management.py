"""Tests for logos/data/management.py — management state collection.

Covers frontmatter parsing, people/coaching/feedback collection,
staleness computation, and snapshot aggregates.
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from typing import TYPE_CHECKING

from logos.data.management import (
    CoachingState,
    FeedbackState,
    ManagementSnapshot,
    PersonState,
    _collect_coaching,
    _collect_feedback,
    _collect_people,
    _parse_frontmatter,
    collect_management_state,
)
from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────────────


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    """Write a markdown file with YAML frontmatter."""
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def _days_ago(n: int) -> str:
    """Return ISO date string for n days ago."""
    return (date.today() - timedelta(days=n)).isoformat()


def _days_from_now(n: int) -> str:
    """Return ISO date string for n days in the future."""
    return (date.today() + timedelta(days=n)).isoformat()


# ── _parse_frontmatter ───────────────────────────────────────────────────


class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path: Path):
        p = tmp_path / "test.md"
        _write_md(p, "name: Alice\nteam: platform\n", "Some body text")
        fm, body = _parse_frontmatter(p)
        assert fm["name"] == "Alice"
        assert fm["team"] == "platform"
        assert "Some body text" in body

    def test_no_frontmatter(self, tmp_path: Path):
        p = tmp_path / "test.md"
        p.write_text("Just plain text, no frontmatter.", encoding="utf-8")
        fm, body = _parse_frontmatter(p)
        assert fm == {}
        assert "Just plain text" in body

    def test_missing_file(self, tmp_path: Path):
        p = tmp_path / "nonexistent.md"
        fm, body = _parse_frontmatter(p)
        assert fm == {}
        assert body == ""

    def test_bad_yaml(self, tmp_path: Path):
        p = tmp_path / "test.md"
        p.write_text("---\n: : : invalid yaml [[\n---\nbody", encoding="utf-8")
        fm, body = _parse_frontmatter(p)
        assert fm == {}
        assert "body" in body

    def test_empty_frontmatter(self, tmp_path: Path):
        p = tmp_path / "test.md"
        p.write_text("---\n\n---\nbody text", encoding="utf-8")
        fm, body = _parse_frontmatter(p)
        assert fm == {}
        assert "body text" in body

    def test_frontmatter_scalar_not_dict(self, tmp_path: Path):
        p = tmp_path / "test.md"
        p.write_text("---\njust a string\n---\nbody", encoding="utf-8")
        fm, body = _parse_frontmatter(p)
        assert fm == {}

    def test_binary_file(self, tmp_path: Path):
        p = tmp_path / "binary.md"
        p.write_bytes(b"\x80\x81\x82\x83")
        fm, body = _parse_frontmatter(p)
        assert fm == {}
        assert body == ""


# ── _collect_people ──────────────────────────────────────────────────────


class TestCollectPeople:
    def test_reads_person_file(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "alice.md",
            f"type: person\nname: Alice\nteam: platform\nrole: engineer\n"
            f"cadence: weekly\nlast-1on1: {_days_ago(3)}\ncognitive-load: moderate\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert len(result) == 1
        assert result[0].name == "Alice"
        assert result[0].team == "platform"
        assert result[0].cadence == "weekly"
        assert result[0].days_since_1on1 == 3
        assert result[0].stale_1on1 is False
        assert result[0].cognitive_load == 2

    def test_skips_inactive(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "bob.md",
            "type: person\nname: Bob\nstatus: inactive\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert len(result) == 0

    def test_skips_non_person_type(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(people_dir / "notes.md", "type: note\nname: Notes\n")
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert len(result) == 0

    def test_empty_dir(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result == []

    def test_no_dir(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result == []

    def test_name_fallback_from_filename(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(people_dir / "jane-doe.md", "type: person\n")
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].name == "Jane Doe"

    def test_stale_weekly(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "alice.md",
            f"type: person\nname: Alice\ncadence: weekly\nlast-1on1: {_days_ago(11)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].stale_1on1 is True
        assert result[0].days_since_1on1 == 11

    def test_not_stale_weekly(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "alice.md",
            f"type: person\nname: Alice\ncadence: weekly\nlast-1on1: {_days_ago(9)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].stale_1on1 is False

    def test_stale_biweekly(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "bob.md",
            f"type: person\nname: Bob\ncadence: biweekly\nlast-1on1: {_days_ago(18)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].stale_1on1 is True

    def test_stale_monthly(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "carol.md",
            f"type: person\nname: Carol\ncadence: monthly\nlast-1on1: {_days_ago(36)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].stale_1on1 is True

    def test_stale_default_cadence(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "dave.md",
            f"type: person\nname: Dave\nlast-1on1: {_days_ago(15)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].stale_1on1 is True
        assert result[0].cadence == ""

    def test_no_last_1on1(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(people_dir / "eve.md", "type: person\nname: Eve\n")
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].stale_1on1 is False
        assert result[0].days_since_1on1 is None

    def test_domains_list(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "alice.md",
            "type: person\nname: Alice\ndomains:\n  - engineering\n  - infra\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].domains == ["engineering", "infra"]

    def test_domains_string(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "alice.md",
            "type: person\nname: Alice\ndomains: engineering\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].domains == ["engineering"]

    def test_domains_default(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(people_dir / "alice.md", "type: person\nname: Alice\n")
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        assert result[0].domains == ["management"]

    def test_all_fields_mapped(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "full.md",
            "type: person\n"
            "name: Full Person\n"
            "team: platform\n"
            "role: senior engineer\n"
            "cadence: weekly\n"
            "status: active\n"
            "cognitive-load: high\n"
            "growth-vector: technical-leadership\n"
            "feedback-style: direct\n"
            f"last-1on1: {_days_ago(2)}\n"
            "coaching-active: true\n"
            "career-goal-3y: staff engineer\n"
            "current-gaps: system design\n"
            "current-focus: scaling project\n"
            f"last-career-convo: {_days_ago(30)}\n"
            "team-type: product\n"
            "interaction-mode: async\n"
            "skill-level: senior\n"
            "will-signal: high\n"
            "domains:\n  - engineering\n"
            "relationship: direct-report\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_people()
        finally:
            config.reset_data_dir()
        p = result[0]
        assert p.name == "Full Person"
        assert p.growth_vector == "technical-leadership"
        assert p.feedback_style == "direct"
        assert p.coaching_active is True
        assert p.career_goal_3y == "staff engineer"
        assert p.current_gaps == "system design"
        assert p.current_focus == "scaling project"
        assert p.team_type == "product"
        assert p.interaction_mode == "async"
        assert p.skill_level == "senior"
        assert p.will_signal == "high"
        assert p.relationship == "direct-report"
        assert p.cognitive_load == 4


# ── _collect_coaching ────────────────────────────────────────────────────


class TestCollectCoaching:
    def test_reads_coaching_file(self, tmp_path: Path):
        coaching_dir = tmp_path / "coaching"
        coaching_dir.mkdir()
        _write_md(
            coaching_dir / "delegation.md",
            f"type: coaching\ntitle: Delegation Experiment\nperson: Alice\n"
            f"status: active\ncheck-in-by: {_days_ago(5)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_coaching()
        finally:
            config.reset_data_dir()
        assert len(result) == 1
        assert result[0].title == "Delegation Experiment"
        assert result[0].person == "Alice"
        assert result[0].overdue is True
        assert result[0].days_overdue == 5

    def test_not_overdue(self, tmp_path: Path):
        coaching_dir = tmp_path / "coaching"
        coaching_dir.mkdir()
        _write_md(
            coaching_dir / "future.md",
            f"type: coaching\ntitle: Future Check\ncheck-in-by: {_days_from_now(5)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_coaching()
        finally:
            config.reset_data_dir()
        assert result[0].overdue is False
        assert result[0].days_overdue == 0

    def test_no_check_in_date(self, tmp_path: Path):
        coaching_dir = tmp_path / "coaching"
        coaching_dir.mkdir()
        _write_md(
            coaching_dir / "nodates.md",
            "type: coaching\ntitle: No Dates\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_coaching()
        finally:
            config.reset_data_dir()
        assert result[0].overdue is False
        assert result[0].days_overdue == 0

    def test_title_fallback(self, tmp_path: Path):
        coaching_dir = tmp_path / "coaching"
        coaching_dir.mkdir()
        _write_md(coaching_dir / "my-experiment.md", "type: coaching\n")
        config.set_data_dir(tmp_path)
        try:
            result = _collect_coaching()
        finally:
            config.reset_data_dir()
        assert result[0].title == "My Experiment"

    def test_empty_dir(self, tmp_path: Path):
        coaching_dir = tmp_path / "coaching"
        coaching_dir.mkdir()
        config.set_data_dir(tmp_path)
        try:
            result = _collect_coaching()
        finally:
            config.reset_data_dir()
        assert result == []

    def test_no_dir(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            result = _collect_coaching()
        finally:
            config.reset_data_dir()
        assert result == []

    def test_skips_non_coaching(self, tmp_path: Path):
        coaching_dir = tmp_path / "coaching"
        coaching_dir.mkdir()
        _write_md(coaching_dir / "notes.md", "type: note\ntitle: Notes\n")
        config.set_data_dir(tmp_path)
        try:
            result = _collect_coaching()
        finally:
            config.reset_data_dir()
        assert len(result) == 0


# ── _collect_feedback ────────────────────────────────────────────────────


class TestCollectFeedback:
    def test_reads_feedback_file(self, tmp_path: Path):
        feedback_dir = tmp_path / "feedback"
        feedback_dir.mkdir()
        _write_md(
            feedback_dir / "q1-growth.md",
            f"type: feedback\ntitle: Q1 Growth\nperson: Alice\n"
            f"direction: given\ncategory: growth\n"
            f"follow-up-by: {_days_ago(10)}\nfollowed-up: false\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_feedback()
        finally:
            config.reset_data_dir()
        assert len(result) == 1
        assert result[0].title == "Q1 Growth"
        assert result[0].person == "Alice"
        assert result[0].overdue is True
        assert result[0].days_overdue == 10

    def test_not_overdue_when_followed_up(self, tmp_path: Path):
        feedback_dir = tmp_path / "feedback"
        feedback_dir.mkdir()
        _write_md(
            feedback_dir / "done.md",
            f"type: feedback\ntitle: Done\nfollow-up-by: {_days_ago(10)}\nfollowed-up: true\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_feedback()
        finally:
            config.reset_data_dir()
        assert result[0].overdue is False
        assert result[0].days_overdue == 0

    def test_not_overdue_future_date(self, tmp_path: Path):
        feedback_dir = tmp_path / "feedback"
        feedback_dir.mkdir()
        _write_md(
            feedback_dir / "future.md",
            f"type: feedback\ntitle: Future\nfollow-up-by: {_days_from_now(5)}\nfollowed-up: false\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_feedback()
        finally:
            config.reset_data_dir()
        assert result[0].overdue is False

    def test_no_follow_up_date(self, tmp_path: Path):
        feedback_dir = tmp_path / "feedback"
        feedback_dir.mkdir()
        _write_md(
            feedback_dir / "nodates.md",
            "type: feedback\ntitle: No Dates\nfollowed-up: false\n",
        )
        config.set_data_dir(tmp_path)
        try:
            result = _collect_feedback()
        finally:
            config.reset_data_dir()
        assert result[0].overdue is False

    def test_title_fallback(self, tmp_path: Path):
        feedback_dir = tmp_path / "feedback"
        feedback_dir.mkdir()
        _write_md(feedback_dir / "my-feedback.md", "type: feedback\n")
        config.set_data_dir(tmp_path)
        try:
            result = _collect_feedback()
        finally:
            config.reset_data_dir()
        assert result[0].title == "My Feedback"

    def test_empty_dir(self, tmp_path: Path):
        feedback_dir = tmp_path / "feedback"
        feedback_dir.mkdir()
        config.set_data_dir(tmp_path)
        try:
            result = _collect_feedback()
        finally:
            config.reset_data_dir()
        assert result == []

    def test_no_dir(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            result = _collect_feedback()
        finally:
            config.reset_data_dir()
        assert result == []


# ── collect_management_state (snapshot aggregates) ───────────────────────


class TestCollectManagementState:
    def test_empty_data_dir(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()
        assert isinstance(snap, ManagementSnapshot)
        assert snap.active_people_count == 0
        assert snap.stale_1on1_count == 0
        assert snap.overdue_coaching_count == 0
        assert snap.overdue_feedback_count == 0
        assert snap.high_load_count == 0

    def test_stale_count(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "alice.md",
            f"type: person\nname: Alice\ncadence: weekly\nlast-1on1: {_days_ago(11)}\n",
        )
        _write_md(
            people_dir / "bob.md",
            f"type: person\nname: Bob\ncadence: weekly\nlast-1on1: {_days_ago(3)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()
        assert snap.stale_1on1_count == 1
        assert snap.active_people_count == 2

    def test_overdue_coaching_count(self, tmp_path: Path):
        coaching_dir = tmp_path / "coaching"
        coaching_dir.mkdir()
        _write_md(
            coaching_dir / "overdue.md",
            f"type: coaching\ntitle: Overdue\ncheck-in-by: {_days_ago(5)}\n",
        )
        _write_md(
            coaching_dir / "ok.md",
            f"type: coaching\ntitle: OK\ncheck-in-by: {_days_from_now(5)}\n",
        )
        config.set_data_dir(tmp_path)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()
        assert snap.overdue_coaching_count == 1

    def test_overdue_feedback_count(self, tmp_path: Path):
        feedback_dir = tmp_path / "feedback"
        feedback_dir.mkdir()
        _write_md(
            feedback_dir / "overdue.md",
            f"type: feedback\ntitle: Overdue\nfollow-up-by: {_days_ago(5)}\nfollowed-up: false\n",
        )
        _write_md(
            feedback_dir / "done.md",
            f"type: feedback\ntitle: Done\nfollow-up-by: {_days_ago(5)}\nfollowed-up: true\n",
        )
        config.set_data_dir(tmp_path)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()
        assert snap.overdue_feedback_count == 1

    def test_high_load_count(self, tmp_path: Path):
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "high.md",
            "type: person\nname: High Load\ncognitive-load: high\n",
        )
        _write_md(
            people_dir / "low.md",
            "type: person\nname: Low Load\ncognitive-load: moderate\n",
        )
        _write_md(
            people_dir / "very-high.md",
            "type: person\nname: Very High\ncognitive-load: critical\n",
        )
        config.set_data_dir(tmp_path)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()
        assert snap.high_load_count == 2
        assert snap.active_people_count == 3

    def test_cognitive_load_string_values(self, tmp_path: Path):
        """cognitive-load frontmatter strings are converted to numeric values."""
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        _write_md(
            people_dir / "alice.md",
            "type: person\nname: Alice\ncognitive-load: high\n",
        )
        _write_md(
            people_dir / "bob.md",
            "type: person\nname: Bob\ncognitive-load: critical\n",
        )
        _write_md(
            people_dir / "carol.md",
            "type: person\nname: Carol\ncognitive-load: low\n",
        )
        _write_md(
            people_dir / "dave.md",
            "type: person\nname: Dave\n",
        )
        config.set_data_dir(tmp_path)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()
        assert snap.high_load_count == 2  # Alice (high=4) + Bob (critical=5)
        assert snap.active_people_count == 4
        # Verify individual values
        by_name = {p.name: p for p in snap.people}
        assert by_name["Alice"].cognitive_load == 4
        assert by_name["Bob"].cognitive_load == 5
        assert by_name["Carol"].cognitive_load == 1
        assert by_name["Dave"].cognitive_load is None

    def test_full_snapshot(self, tmp_path: Path):
        """Integration: all three subdirectories populated."""
        (tmp_path / "people").mkdir()
        (tmp_path / "coaching").mkdir()
        (tmp_path / "feedback").mkdir()

        _write_md(
            tmp_path / "people" / "alice.md",
            f"type: person\nname: Alice\ncadence: weekly\n"
            f"last-1on1: {_days_ago(11)}\ncognitive-load: high\n",
        )
        _write_md(
            tmp_path / "coaching" / "delegation.md",
            f"type: coaching\ntitle: Delegation\ncheck-in-by: {_days_ago(3)}\n",
        )
        _write_md(
            tmp_path / "feedback" / "q1.md",
            f"type: feedback\ntitle: Q1\nfollow-up-by: {_days_ago(7)}\nfollowed-up: false\n",
        )

        config.set_data_dir(tmp_path)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()

        assert snap.active_people_count == 1
        assert snap.stale_1on1_count == 1
        assert snap.overdue_coaching_count == 1
        assert snap.overdue_feedback_count == 1
        assert snap.high_load_count == 1
        assert len(snap.people) == 1
        assert len(snap.coaching) == 1
        assert len(snap.feedback) == 1


# ── Dataclass defaults ───────────────────────────────────────────────────


class TestPersonState:
    def test_new_fields_default_empty(self):
        p = PersonState(name="Test")
        assert p.career_goal_3y == ""
        assert p.current_gaps == ""
        assert p.current_focus == ""
        assert p.last_career_convo == ""
        assert p.team_type == ""
        assert p.interaction_mode == ""
        assert p.skill_level == ""
        assert p.will_signal == ""

    def test_has_domains_field(self):
        fields = {f.name for f in dataclasses.fields(PersonState)}
        assert "domains" in fields

    def test_has_relationship_field(self):
        fields = {f.name for f in dataclasses.fields(PersonState)}
        assert "relationship" in fields

    def test_domains_default_management(self):
        p = PersonState(name="Test")
        assert p.domains == ["management"]

    def test_relationship_default_empty(self):
        p = PersonState(name="Test")
        assert p.relationship == ""

    def test_basic_construction(self):
        p = PersonState(
            name="Alice",
            team="platform",
            role="engineer",
            cadence="weekly",
            cognitive_load=4,
            coaching_active=True,
        )
        assert p.name == "Alice"
        assert p.team == "platform"
        assert p.cognitive_load == 4
        assert p.coaching_active is True


class TestCoachingState:
    def test_basic_construction(self):
        c = CoachingState(
            title="delegation experiment",
            person="Alice",
            status="active",
            overdue=True,
            days_overdue=5,
        )
        assert c.title == "delegation experiment"
        assert c.overdue is True
        assert c.days_overdue == 5


class TestFeedbackState:
    def test_basic_construction(self):
        f = FeedbackState(
            title="q1 growth",
            person="Alice",
            direction="given",
            category="growth",
            overdue=True,
            days_overdue=10,
        )
        assert f.title == "q1 growth"
        assert f.overdue is True


class TestManagementSnapshot:
    def test_empty_snapshot(self):
        snap = ManagementSnapshot()
        assert snap.active_people_count == 0
        assert snap.people == []

    def test_snapshot_with_data(self):
        snap = ManagementSnapshot(
            people=[PersonState(name="Alice")],
            active_people_count=1,
            stale_1on1_count=1,
        )
        assert snap.active_people_count == 1
        assert len(snap.people) == 1
