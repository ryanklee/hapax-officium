"""End-to-end integration tests for the data flow pipeline.

Validates: data files -> collector -> nudges -> team_health -> writer round-trip.
All tests use tmp_path and config.set_data_dir() to redirect DATA_DIR.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from agents.ingest import DocumentType, process_document
from cockpit.data.management import (
    collect_management_state,
)
from cockpit.data.nudges import collect_nudges
from cockpit.data.team_health import collect_team_health
from shared.config import config
from shared.management_bridge import generate_facts
from shared.vault_writer import (
    create_coaching_starter,
    create_decision_starter,
    create_fb_record_starter,
    write_1on1_prep_to_vault,
)

if TYPE_CHECKING:
    from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────────────


def _setup_data(tmp_path: Path) -> Path:
    """Write a minimal but complete set of test data to tmp_path.

    Creates:
    - 2 people (Alice: active, weekly, stale 1:1, cognitive-load high;
                Bob: active, biweekly)
    - 1 coaching record (Alice, overdue check-in-by)
    - 1 feedback record (Bob, overdue follow-up-by, not followed up)
    - Empty dirs for meetings, decisions, references, inbox, processed
    """
    people_dir = tmp_path / "people"
    people_dir.mkdir()

    coaching_dir = tmp_path / "coaching"
    coaching_dir.mkdir()

    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir()

    for d in ("meetings", "decisions", "references", "inbox", "processed"):
        (tmp_path / d).mkdir()

    # Alice: stale 1:1 (last-1on1 more than 10 days ago for weekly cadence)
    (people_dir / "alice.md").write_text(
        "---\n"
        "type: person\n"
        "name: Alice\n"
        "team: platform\n"
        "role: engineer\n"
        "cadence: weekly\n"
        "status: active\n"
        "cognitive-load: high\n"
        "last-1on1: 2026-02-01\n"
        "---\n"
        "Alice person note body.\n",
        encoding="utf-8",
    )

    # Bob: active, biweekly, no stale 1:1 (recent enough)
    recent_date = (date.today() - timedelta(days=5)).isoformat()
    (people_dir / "bob.md").write_text(
        "---\n"
        "type: person\n"
        "name: Bob\n"
        "team: platform\n"
        "role: senior engineer\n"
        "cadence: biweekly\n"
        "status: active\n"
        f"last-1on1: {recent_date}\n"
        "---\n"
        "Bob person note body.\n",
        encoding="utf-8",
    )

    # Coaching record for Alice — overdue check-in
    (coaching_dir / "alice-delegation.md").write_text(
        "---\n"
        "type: coaching\n"
        "title: Delegation growth\n"
        "person: Alice\n"
        "status: active\n"
        "check-in-by: 2026-02-15\n"
        "---\n"
        "Coaching body.\n",
        encoding="utf-8",
    )

    # Feedback record for Bob — overdue follow-up
    (feedback_dir / "bob-code-review.md").write_text(
        "---\n"
        "type: feedback\n"
        "title: Code review quality\n"
        "person: Bob\n"
        "direction: given\n"
        "category: growth\n"
        "follow-up-by: 2026-02-20\n"
        "followed-up: false\n"
        "---\n"
        "Feedback body.\n",
        encoding="utf-8",
    )

    return tmp_path


# ── Integration tests ───────────────────────────────────────────────────


class TestEndToEndDataFlow:
    """End-to-end tests: data files -> collector -> nudges -> team_health -> writer."""

    def test_collector_reads_data(self, tmp_path: Path):
        """collect_management_state() sees 2 active people and detects all issues."""
        data_dir = _setup_data(tmp_path)

        config.set_data_dir(data_dir)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()

        # 2 active people
        assert snap.active_people_count == 2
        assert len(snap.people) == 2
        names = {p.name for p in snap.people}
        assert names == {"Alice", "Bob"}

        # Stale 1:1 for Alice (weekly cadence, last 1:1 was 2026-02-01)
        assert snap.stale_1on1_count == 1
        alice = next(p for p in snap.people if p.name == "Alice")
        assert alice.stale_1on1 is True
        assert alice.cognitive_load == 4

        bob = next(p for p in snap.people if p.name == "Bob")
        assert bob.stale_1on1 is False

        # Overdue coaching
        assert snap.overdue_coaching_count == 1
        assert len(snap.coaching) == 1
        assert snap.coaching[0].person == "Alice"
        assert snap.coaching[0].overdue is True

        # Overdue feedback
        assert snap.overdue_feedback_count == 1
        assert len(snap.feedback) == 1
        assert snap.feedback[0].person == "Bob"
        assert snap.feedback[0].overdue is True
        assert snap.feedback[0].followed_up is False

        # High load count (cognitive_load == "high")
        assert snap.high_load_count == 1

    def test_bridge_generates_facts(self, tmp_path: Path):
        """generate_facts() returns facts for people + coaching + feedback."""
        data_dir = _setup_data(tmp_path)

        config.set_data_dir(data_dir)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        assert len(facts) > 0

        # Should have facts from people (team/role + cadence), coaching, feedback
        texts = [f["value"] for f in facts]

        # People facts
        assert any("Alice" in t and "platform" in t for t in texts)
        assert any("Bob" in t and "platform" in t for t in texts)

        # Cadence facts
        assert any("weekly" in t and "Alice" in t for t in texts)
        assert any("biweekly" in t and "Bob" in t for t in texts)

        # Coaching fact
        assert any("coaching" in t.lower() and "Alice" in t for t in texts)

        # Feedback fact
        assert any("feedback" in t.lower() and "Bob" in t for t in texts)

        # All facts have required ProfileFact fields
        for fact in facts:
            assert "value" in fact
            assert "dimension" in fact
            assert "source" in fact
            assert "key" in fact
            assert "confidence" in fact
            assert "evidence" in fact

    def test_nudges_from_data(self, tmp_path: Path):
        """collect_nudges() returns nudges for stale 1:1, overdue coaching, overdue feedback."""
        data_dir = _setup_data(tmp_path)

        config.set_data_dir(data_dir)
        try:
            nudges = collect_nudges(max_nudges=10)
        finally:
            config.reset_data_dir()

        assert len(nudges) >= 3

        titles = [n.title for n in nudges]

        # Stale 1:1 nudge for Alice
        assert any("Stale 1:1" in t and "Alice" in t for t in titles)

        # Overdue coaching nudge
        assert any("Coaching" in t and "overdue" in t.lower() for t in titles)

        # Overdue feedback nudge
        assert any("Feedback" in t and "overdue" in t.lower() for t in titles)

        # All nudges have required fields
        for n in nudges:
            assert n.category
            assert n.priority_score >= 0
            assert n.priority_label in ("critical", "high", "medium", "low")

    def test_team_health_from_data(self, tmp_path: Path):
        """collect_team_health() groups people by team from data files."""
        data_dir = _setup_data(tmp_path)

        # cognitive_load is now converted to numeric by the collector
        config.set_data_dir(data_dir)
        try:
            health = collect_team_health()
        finally:
            config.reset_data_dir()

        assert health.total_people == 2
        assert len(health.teams) >= 1

        # Both Alice and Bob are on "platform" team
        platform = next(t for t in health.teams if t.name == "platform")
        assert platform.size == 2
        assert platform.avg_cognitive_load is not None

    def test_writer_creates_files(self, tmp_path: Path):
        """Writer functions create files, and re-running collector picks them up."""
        data_dir = _setup_data(tmp_path)

        config.set_data_dir(data_dir)
        try:
            # Create files via writer
            coaching_path = create_coaching_starter("Charlie", "Improve testing habits")
            assert coaching_path is not None
            assert coaching_path.exists()
            assert coaching_path.parent == data_dir / "coaching"

            fb_path = create_fb_record_starter("Charlie", "Good PR review this week")
            assert fb_path is not None
            assert fb_path.exists()
            assert fb_path.parent == data_dir / "feedback"

            decision_path = create_decision_starter(
                "Adopt new CI pipeline", "weekly-sync-2026-03-01"
            )
            assert decision_path is not None
            assert decision_path.exists()
            assert decision_path.parent == data_dir / "decisions"

            prep_path = write_1on1_prep_to_vault("Alice", "# Prep for Alice\n\n- Topics")
            assert prep_path is not None
            assert prep_path.exists()
            assert prep_path.parent == data_dir / "1on1-prep"

            # Re-run collector — should pick up new coaching and feedback files
            snap = collect_management_state()

            # Original + new coaching
            assert len(snap.coaching) == 2
            coaching_people = {c.person for c in snap.coaching}
            assert "Charlie" in coaching_people
            assert "Alice" in coaching_people

            # Original + new feedback
            assert len(snap.feedback) == 2
            feedback_people = {f.person for f in snap.feedback}
            assert "Charlie" in feedback_people
            assert "Bob" in feedback_people

        finally:
            config.reset_data_dir()

    async def test_ingest_routes_document(self, tmp_path: Path):
        """process_document() routes a person note to data/people/."""
        data_dir = _setup_data(tmp_path)

        # Create a person note in a temporary location (outside data_dir)
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        person_file = source_dir / "dana.md"
        person_file.write_text(
            "---\n"
            "type: person\n"
            "name: Dana\n"
            "team: sre\n"
            "role: engineer\n"
            "cadence: weekly\n"
            "status: active\n"
            "---\n"
            "Dana person note.\n",
            encoding="utf-8",
        )

        config.set_data_dir(data_dir)
        try:
            result = await process_document(person_file)
        finally:
            config.reset_data_dir()

        assert result.success is True
        assert result.doc_type == DocumentType.PERSON
        assert result.destination is not None
        assert result.destination.parent == data_dir / "people"
        assert result.destination.name == "dana.md"
        assert result.destination.exists()

        # Verify collector now sees 3 people (Alice, Bob, Dana)
        config.set_data_dir(data_dir)
        try:
            snap = collect_management_state()
        finally:
            config.reset_data_dir()

        assert snap.active_people_count == 3
        names = {p.name for p in snap.people}
        assert "Dana" in names
