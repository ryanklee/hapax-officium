"""Tests for shared/management_bridge.py — fact generation from DATA_DIR."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import yaml

from shared.config import config
from shared.management_bridge import (
    _make_fact,
    generate_facts,
    save_facts,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    """Write a markdown file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


# ── _make_fact ───────────────────────────────────────────────────────────


class TestMakeFact:
    def test_structure(self):
        fact = _make_fact("some text", "team_leadership", "people/alice.md")
        assert fact["value"] == "some text"
        assert fact["dimension"] == "team_leadership"
        assert "management-bridge:" in fact["source"]
        assert fact["key"]  # non-empty
        assert fact["confidence"] == 0.90
        assert fact["evidence"] == "some text"

    def test_validates_as_profile_fact(self):
        from agents.management_profiler import ProfileFact

        fact = _make_fact("test value", "management_practice", "people/alice.md")
        pf = ProfileFact.model_validate(fact)
        assert pf.value == "test value"


# ── generate_facts ───────────────────────────────────────────────────────


class TestGenerateFacts:
    def test_people_facts(self, tmp_path: Path):
        _write_md(
            tmp_path / "people" / "alice.md",
            {
                "type": "person",
                "name": "Alice Smith",
                "team": "Platform",
                "role": "Senior Engineer",
                "cadence": "weekly",
                "status": "active",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        texts = [f["value"] for f in facts]
        assert any("Alice Smith is on Platform team" in t for t in texts)
        assert any("weekly 1:1 cadence with Alice Smith" in t for t in texts)
        assert any(f["dimension"] == "team_leadership" for f in facts)
        assert any(f["dimension"] == "management_practice" for f in facts)

    def test_people_skips_inactive(self, tmp_path: Path):
        _write_md(
            tmp_path / "people" / "bob.md",
            {
                "type": "person",
                "name": "Bob",
                "team": "Core",
                "role": "Engineer",
                "status": "inactive",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        assert len(facts) == 0

    def test_coaching_facts(self, tmp_path: Path):
        _write_md(
            tmp_path / "coaching" / "alice-delegation.md",
            {
                "type": "coaching",
                "person": "Alice",
                "title": "Delegation skills",
                "status": "active",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        assert len(facts) == 1
        assert "Coaching hypothesis for Alice: Delegation skills" in facts[0]["value"]
        assert facts[0]["dimension"] == "management_practice"

    def test_feedback_facts(self, tmp_path: Path):
        _write_md(
            tmp_path / "feedback" / "alice-q1.md",
            {
                "type": "feedback",
                "person": "Alice",
                "direction": "given",
                "category": "technical-growth",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        assert len(facts) == 1
        assert "Feedback record (given) for Alice: technical-growth" in facts[0]["value"]

    def test_meeting_facts(self, tmp_path: Path):
        _write_md(
            tmp_path / "meetings" / "2026-03-01-standup.md",
            {
                "type": "meeting",
                "title": "Team Standup",
                "date": "2026-03-01",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        assert len(facts) == 1
        assert "Meeting: Team Standup (2026-03-01)" in facts[0]["value"]
        assert facts[0]["dimension"] == "attention_distribution"

    def test_meeting_facts_limited_to_20(self, tmp_path: Path):
        meetings_dir = tmp_path / "meetings"
        for i in range(25):
            _write_md(
                meetings_dir / f"2026-01-{i + 1:02d}-meeting.md",
                {
                    "type": "meeting",
                    "title": f"Meeting {i + 1}",
                    "date": f"2026-01-{i + 1:02d}",
                },
            )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        assert len(facts) == 20

    def test_empty_dirs_returns_empty(self, tmp_path: Path):
        (tmp_path / "people").mkdir()
        (tmp_path / "coaching").mkdir()
        (tmp_path / "feedback").mkdir()
        (tmp_path / "meetings").mkdir()

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        assert facts == []

    def test_missing_dirs_returns_empty(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        assert facts == []

    def test_combined_facts(self, tmp_path: Path):
        _write_md(
            tmp_path / "people" / "alice.md",
            {
                "type": "person",
                "name": "Alice",
                "team": "Platform",
                "role": "Engineer",
            },
        )
        _write_md(
            tmp_path / "coaching" / "alice-growth.md",
            {
                "type": "coaching",
                "person": "Alice",
                "title": "Growth plan",
                "status": "active",
            },
        )
        _write_md(
            tmp_path / "feedback" / "alice-review.md",
            {
                "type": "feedback",
                "person": "Alice",
                "direction": "given",
                "category": "performance",
            },
        )
        _write_md(
            tmp_path / "meetings" / "2026-03-01-sync.md",
            {
                "type": "meeting",
                "title": "Sync",
                "date": "2026-03-01",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        # 1 person (team_leadership) + 1 meeting + 1 coaching + 1 feedback = 4
        # (no cadence on alice so no management_practice from people)
        assert len(facts) == 4
        dims = {f["dimension"] for f in facts}
        assert "team_leadership" in dims
        assert "management_practice" in dims
        assert "attention_distribution" in dims


# ── save_facts ───────────────────────────────────────────────────────────


class TestSaveFacts:
    def test_writes_json(self, tmp_path: Path):
        output = tmp_path / "management-structured-facts.json"
        facts = [_make_fact("test", "dim", "src")]

        with (
            patch("shared.management_bridge.PROFILES_DIR", tmp_path),
            patch("shared.management_bridge.FACTS_OUTPUT", output),
        ):
            result = save_facts(facts)

        assert result == output
        assert output.exists()
        loaded = json.loads(output.read_text(encoding="utf-8"))
        assert len(loaded) == 1
        assert loaded[0]["value"] == "test"

    def test_saves_empty_list(self, tmp_path: Path):
        output = tmp_path / "management-structured-facts.json"

        with (
            patch("shared.management_bridge.PROFILES_DIR", tmp_path),
            patch("shared.management_bridge.FACTS_OUTPUT", output),
        ):
            path = save_facts([])

        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == []


# ── OKR facts ────────────────────────────────────────────────────────────


class TestOKRFacts:
    def test_okr_generates_fact(self, tmp_path: Path):
        _write_md(
            tmp_path / "okrs" / "2026-q1-platform.md",
            {
                "type": "okr",
                "status": "active",
                "objective": "Improve reliability",
                "scope": "team",
                "team": "Platform",
                "quarter": "2026-Q1",
                "key-results": [
                    {
                        "id": "kr1",
                        "description": "P99",
                        "target": 200,
                        "current": 310,
                        "confidence": 0.6,
                        "last-updated": "2026-03-01",
                    },
                ],
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        okr_facts = [f for f in facts if "OKR" in f["value"]]
        assert len(okr_facts) >= 1
        assert any("Improve reliability" in f["value"] for f in okr_facts)
        assert any(f["dimension"] == "strategic_alignment" for f in okr_facts)


# ── Incident facts ───────────────────────────────────────────────────────


class TestIncidentFacts:
    def test_incident_generates_fact(self, tmp_path: Path):
        _write_md(
            tmp_path / "incidents" / "2026-02-15-outage.md",
            {
                "type": "incident",
                "title": "API outage",
                "severity": "sev1",
                "status": "postmortem-complete",
                "duration-minutes": 75,
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        incident_facts = [
            f for f in facts if "incident" in f["value"].lower() or "outage" in f["value"].lower()
        ]
        assert len(incident_facts) >= 1
        assert any(f["dimension"] == "attention_distribution" for f in incident_facts)


# ── Review cycle facts ───────────────────────────────────────────────────


class TestReviewCycleFacts:
    def test_review_cycle_generates_fact(self, tmp_path: Path):
        _write_md(
            tmp_path / "review-cycles" / "2026-h1-sarah.md",
            {
                "type": "review-cycle",
                "cycle": "2026-H1",
                "person": "Sarah Chen",
                "status": "self-assessment-due",
                "review-due": "2026-05-01",
            },
        )

        config.set_data_dir(tmp_path)
        try:
            facts = generate_facts()
        finally:
            config.reset_data_dir()

        rc_facts = [
            f for f in facts if "Review cycle" in f["value"] or "review" in f["value"].lower()
        ]
        assert len(rc_facts) >= 1
        assert any(f["dimension"] == "management_practice" for f in rc_facts)
