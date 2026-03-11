"""Tests for agents/ingest.py — document ingestion pipeline.

Covers transcript detection, frontmatter type detection, classification,
and document processing/routing. All tests use tmp_path with patched DATA_DIR.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.ingest import (
    DocumentType,
    _detect_frontmatter_type,
    _detect_transcript,
    classify_document,
    process_document,
)
from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────────────


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    """Write a markdown file with YAML frontmatter."""
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


# ── _detect_transcript ───────────────────────────────────────────────────


class TestDetectTranscript:
    def test_vtt_file(self, tmp_path: Path):
        p = tmp_path / "meeting.vtt"
        p.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello", encoding="utf-8")
        assert _detect_transcript(p) is True

    def test_srt_file(self, tmp_path: Path):
        p = tmp_path / "meeting.srt"
        p.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello", encoding="utf-8")
        assert _detect_transcript(p) is True

    def test_md_with_speaker_turns(self, tmp_path: Path):
        p = tmp_path / "transcript.md"
        p.write_text(
            "Alice: Hello everyone\n"
            "Bob: Hi Alice\n"
            "Charlie: Good morning\n"
            "Alice: Let's get started\n",
            encoding="utf-8",
        )
        assert _detect_transcript(p) is True

    def test_md_without_speaker_turns(self, tmp_path: Path):
        p = tmp_path / "notes.md"
        p.write_text(
            "# Meeting Notes\n\nSome regular markdown content.\n",
            encoding="utf-8",
        )
        assert _detect_transcript(p) is False

    def test_md_with_too_few_turns(self, tmp_path: Path):
        p = tmp_path / "chat.md"
        p.write_text("Alice: Hello\nBob: Hi\n", encoding="utf-8")
        assert _detect_transcript(p) is False

    def test_non_md_non_vtt(self, tmp_path: Path):
        p = tmp_path / "data.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        assert _detect_transcript(p) is False


# ── _detect_frontmatter_type ─────────────────────────────────────────────


class TestDetectFrontmatterType:
    def test_typed_frontmatter(self, tmp_path: Path):
        p = _write_md(tmp_path / "person.md", "type: person\nname: Alice\n")
        assert _detect_frontmatter_type(p) == "person"

    def test_no_type_field(self, tmp_path: Path):
        p = _write_md(tmp_path / "note.md", "name: Alice\nteam: platform\n")
        assert _detect_frontmatter_type(p) is None

    def test_no_frontmatter(self, tmp_path: Path):
        p = tmp_path / "plain.md"
        p.write_text("Just plain text.", encoding="utf-8")
        assert _detect_frontmatter_type(p) is None

    def test_non_md_file(self, tmp_path: Path):
        p = tmp_path / "data.json"
        p.write_text('{"type": "person"}', encoding="utf-8")
        assert _detect_frontmatter_type(p) is None


# ── classify_document ────────────────────────────────────────────────────


class TestClassifyDocument:
    def test_vtt_is_transcript(self, tmp_path: Path):
        p = tmp_path / "call.vtt"
        p.write_text("WEBVTT\n\n00:00 --> 00:01\nHi", encoding="utf-8")
        assert classify_document(p) == DocumentType.TRANSCRIPT

    def test_srt_is_transcript(self, tmp_path: Path):
        p = tmp_path / "call.srt"
        p.write_text("1\n00:00:00 --> 00:00:01\nHi", encoding="utf-8")
        assert classify_document(p) == DocumentType.TRANSCRIPT

    def test_md_transcript_beats_frontmatter(self, tmp_path: Path):
        """Transcript detection takes priority over frontmatter type."""
        p = tmp_path / "mixed.md"
        p.write_text(
            "---\ntype: reference\n---\nAlice: Hello\nBob: Hi\nCharlie: Hey\n",
            encoding="utf-8",
        )
        assert classify_document(p) == DocumentType.TRANSCRIPT

    def test_frontmatter_person(self, tmp_path: Path):
        p = _write_md(tmp_path / "alice.md", "type: person\nname: Alice\n")
        assert classify_document(p) == DocumentType.PERSON

    def test_frontmatter_meeting(self, tmp_path: Path):
        p = _write_md(tmp_path / "standup.md", "type: meeting\ndate: 2026-03-09\n")
        assert classify_document(p) == DocumentType.MEETING

    def test_frontmatter_coaching(self, tmp_path: Path):
        p = _write_md(tmp_path / "coaching.md", "type: coaching\nperson: Bob\n")
        assert classify_document(p) == DocumentType.COACHING

    def test_frontmatter_feedback(self, tmp_path: Path):
        p = _write_md(tmp_path / "fb.md", "type: feedback\nperson: Charlie\n")
        assert classify_document(p) == DocumentType.FEEDBACK

    def test_frontmatter_decision(self, tmp_path: Path):
        p = _write_md(tmp_path / "dec.md", "type: decision\ntitle: Reorg\n")
        assert classify_document(p) == DocumentType.DECISION

    def test_frontmatter_reference(self, tmp_path: Path):
        p = _write_md(tmp_path / "ref.md", "type: reference\ntitle: Policy\n")
        assert classify_document(p) == DocumentType.REFERENCE

    def test_unknown_type_falls_through(self, tmp_path: Path):
        p = _write_md(tmp_path / "weird.md", "type: alien\n")
        assert classify_document(p) == DocumentType.UNSTRUCTURED

    def test_plain_md_is_unstructured(self, tmp_path: Path):
        p = tmp_path / "notes.md"
        p.write_text("Some plain notes.", encoding="utf-8")
        assert classify_document(p) == DocumentType.UNSTRUCTURED

    def test_non_md_is_unstructured(self, tmp_path: Path):
        p = tmp_path / "data.csv"
        p.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        assert classify_document(p) == DocumentType.UNSTRUCTURED


# ── process_document ─────────────────────────────────────────────────────


class TestProcessDocument:
    async def test_process_person(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            (tmp_path / "people").mkdir()

            src = _write_md(
                tmp_path / "alice.md", "type: person\nname: Alice\n", "Notes about Alice"
            )
            result = await process_document(src)

            assert result.success is True
            assert result.doc_type == DocumentType.PERSON
            assert result.destination == tmp_path / "people" / "alice.md"
            assert (tmp_path / "people" / "alice.md").exists()
        finally:
            config.reset_data_dir()

    async def test_process_feedback(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            (tmp_path / "feedback").mkdir()

            src = _write_md(tmp_path / "fb.md", "type: feedback\nperson: Bob\n", "Feedback content")
            result = await process_document(src)

            assert result.success is True
            assert result.doc_type == DocumentType.FEEDBACK
            assert result.destination == tmp_path / "feedback" / "fb.md"
            assert (tmp_path / "feedback" / "fb.md").exists()
        finally:
            config.reset_data_dir()

    async def test_process_transcript_vtt(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            (tmp_path / "meetings").mkdir()

            src = tmp_path / "standup.vtt"
            src.write_text(
                "WEBVTT\n\n00:00.000 --> 00:01.000\nHello everyone\n",
                encoding="utf-8",
            )
            result = await process_document(src)

            assert result.success is True
            assert result.doc_type == DocumentType.TRANSCRIPT
            dest = tmp_path / "meetings" / "standup.md"
            assert result.destination == dest
            assert dest.exists()
            content = dest.read_text(encoding="utf-8")
            assert "type: meeting" in content
            assert "source: transcript" in content
            assert "WEBVTT" in content
        finally:
            config.reset_data_dir()

    async def test_process_with_type_override(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            (tmp_path / "references").mkdir()

            src = tmp_path / "doc.md"
            src.write_text("Some unstructured doc.", encoding="utf-8")
            result = await process_document(src, doc_type=DocumentType.REFERENCE)

            assert result.success is True
            assert result.doc_type == DocumentType.REFERENCE
            assert (tmp_path / "references" / "doc.md").exists()
        finally:
            config.reset_data_dir()

    async def test_process_missing_file(self, tmp_path: Path):
        result = await process_document(tmp_path / "nonexistent.md")
        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_process_unstructured_no_routing(self, tmp_path: Path):
        config.set_data_dir(tmp_path)
        try:
            src = tmp_path / "random.md"
            src.write_text("Just some notes.", encoding="utf-8")
            result = await process_document(src)

            assert result.success is True
            assert result.doc_type == DocumentType.UNSTRUCTURED
            assert result.destination is None
        finally:
            config.reset_data_dir()
