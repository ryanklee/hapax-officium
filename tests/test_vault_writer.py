"""Tests for shared/vault_writer.py — markdown file writing to DATA_DIR."""

from __future__ import annotations

import yaml

from shared.config import config


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text."""
    assert text.startswith("---\n"), f"Expected frontmatter, got: {text[:40]}"
    end = text.index("---\n", 4)
    return yaml.safe_load(text[4:end])


class TestWriteToVault:
    def test_creates_file_without_frontmatter(self, tmp_path):
        from shared.vault_writer import write_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_to_vault("notes", "test.md", "Hello world")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert result.exists()
        assert result.read_text() == "Hello world"
        assert result == tmp_path / "notes" / "test.md"

    def test_creates_file_with_frontmatter(self, tmp_path):
        from shared.vault_writer import write_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_to_vault("notes", "test.md", "Body", {"type": "note", "tag": "x"})
        finally:
            config.reset_data_dir()

        assert result is not None
        text = result.read_text()
        fm = _parse_frontmatter(text)
        assert fm["type"] == "note"
        assert fm["tag"] == "x"
        assert text.endswith("Body")

    def test_creates_parent_dirs(self, tmp_path):
        from shared.vault_writer import write_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_to_vault("deep/nested/dir", "file.md", "content")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert result.exists()
        assert result.parent == tmp_path / "deep" / "nested" / "dir"


class TestBriefingWriter:
    def test_writes_briefing(self, tmp_path):
        from shared.vault_writer import write_briefing_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_briefing_to_vault("# Morning Briefing\nAll clear.")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert result.exists()
        assert "briefing-" in result.name
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "briefing"
        assert "date" in fm


class TestDigestWriter:
    def test_writes_digest(self, tmp_path):
        from shared.vault_writer import write_digest_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_digest_to_vault("# Digest\nItems here.")
        finally:
            config.reset_data_dir()

        assert result is not None
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "digest"


class TestPrepWriter:
    def test_writes_1on1_prep(self, tmp_path):
        from shared.vault_writer import write_1on1_prep_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_1on1_prep_to_vault("Alice Smith", "# Prep\nTopics here.")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert result.exists()
        assert "prep-alice-smith-" in result.name
        assert result.parent.name == "1on1-prep"
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "prep"
        assert fm["person"] == "Alice Smith"


class TestCoachingStarter:
    def test_creates_coaching_file(self, tmp_path):
        from shared.vault_writer import create_coaching_starter

        config.set_data_dir(tmp_path)
        try:
            result = create_coaching_starter("Bob Jones", "Noticed improved communication.")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert result.parent.name == "coaching"
        assert "bob-jones-" in result.name
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "coaching"
        assert fm["person"] == "Bob Jones"
        assert "Noticed improved communication." in result.read_text()


class TestFeedbackStarter:
    def test_creates_feedback_file(self, tmp_path):
        from shared.vault_writer import create_fb_record_starter

        config.set_data_dir(tmp_path)
        try:
            result = create_fb_record_starter("Carol Danvers", "Great demo delivery.")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert result.parent.name == "feedback"
        assert "carol-danvers-" in result.name
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "feedback"
        assert fm["person"] == "Carol Danvers"


class TestDecisionStarter:
    def test_creates_decision_file(self, tmp_path):
        from shared.vault_writer import create_decision_starter

        config.set_data_dir(tmp_path)
        try:
            result = create_decision_starter(
                "Adopt new CI pipeline for backend services", "standup-2026-03-09"
            )
        finally:
            config.reset_data_dir()

        assert result is not None
        assert result.parent.name == "decisions"
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "decision"
        assert fm["meeting_ref"] == "standup-2026-03-09"

    def test_decision_slug_truncated(self, tmp_path):
        from shared.vault_writer import create_decision_starter

        long_text = "A" * 100 + " rest of decision"
        config.set_data_dir(tmp_path)
        try:
            result = create_decision_starter(long_text, "")
        finally:
            config.reset_data_dir()

        assert result is not None
        # Slug should be first 40 chars
        assert len(result.stem.split("-2026")[0]) <= 40

    def test_decision_without_meeting_ref(self, tmp_path):
        from shared.vault_writer import create_decision_starter

        config.set_data_dir(tmp_path)
        try:
            result = create_decision_starter("Some decision", "")
        finally:
            config.reset_data_dir()

        assert result is not None
        fm = _parse_frontmatter(result.read_text())
        assert "meeting_ref" not in fm


class TestNudgesWriter:
    def test_writes_nudges_checklist(self, tmp_path):
        from shared.vault_writer import write_nudges_to_vault

        nudges = [{"label": "Follow up with Alice"}, {"label": "Review PR #42"}]
        config.set_data_dir(tmp_path)
        try:
            result = write_nudges_to_vault(nudges)
        finally:
            config.reset_data_dir()

        assert result is not None
        text = result.read_text()
        assert "- [ ] Follow up with Alice" in text
        assert "- [ ] Review PR #42" in text
        fm = _parse_frontmatter(text)
        assert fm["type"] == "nudges"


class TestGoalsWriter:
    def test_writes_goals(self, tmp_path):
        from shared.vault_writer import write_goals_to_vault

        goals = [{"label": "Ship v2"}, {"label": "Hire senior dev"}]
        config.set_data_dir(tmp_path)
        try:
            result = write_goals_to_vault(goals)
        finally:
            config.reset_data_dir()

        assert result is not None
        text = result.read_text()
        assert "- Ship v2" in text
        assert "- Hire senior dev" in text
        fm = _parse_frontmatter(text)
        assert fm["type"] == "goals"


class TestTeamSnapshotWriter:
    def test_writes_snapshot(self, tmp_path):
        from shared.vault_writer import write_team_snapshot_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_team_snapshot_to_vault("# Team\nAll good.")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert "team-snapshot-" in result.name
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "team-snapshot"


class TestOverviewWriter:
    def test_writes_overview(self, tmp_path):
        from shared.vault_writer import write_management_overview_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_management_overview_to_vault("# Overview\nSummary.")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert "overview-" in result.name
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "overview"


class TestBridgePromptWriter:
    def test_writes_prompt(self, tmp_path):
        from shared.vault_writer import write_bridge_prompt_to_vault

        config.set_data_dir(tmp_path)
        try:
            result = write_bridge_prompt_to_vault("prep-system", "You are a prep agent.")
        finally:
            config.reset_data_dir()

        assert result is not None
        assert result.name == "prompt-prep-system.md"
        fm = _parse_frontmatter(result.read_text())
        assert fm["type"] == "prompt"
        assert fm["name"] == "prep-system"


class TestErrorHandling:
    def test_returns_none_on_failure(self, tmp_path):
        from shared.vault_writer import write_to_vault

        # Use a path that can't be written (file as parent)
        fake_dir = tmp_path / "blocker"
        fake_dir.write_text("I am a file")
        config.set_data_dir(fake_dir)
        try:
            result = write_to_vault("sub", "test.md", "content")
        finally:
            config.reset_data_dir()

        assert result is None
