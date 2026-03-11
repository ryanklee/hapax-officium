"""agents/ingest.py — Document classifier, router, and watch folder daemon.

Deterministic document ingestion pipeline. Files dropped into DATA_DIR/inbox/
or submitted via CLI are classified by extension and YAML frontmatter, then
routed to the appropriate DATA_DIR subdirectory.

No LLM calls — classification uses deterministic rules (extension, frontmatter
type field, speaker-turn patterns). LLM classification of unstructured content
is a future enhancement.

Usage:
    uv run python -m agents.ingest <file>              # Classify and process
    uv run python -m agents.ingest --type transcript <file>  # Skip classification
    uv run python -m agents.ingest --watch             # Start watch daemon
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import yaml

from shared.config import config
from shared.notify import send_notification

_log = logging.getLogger(__name__)

# ── Frontmatter regex (same pattern as management.py) ────────────────────

_FM_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)", re.DOTALL)

# Speaker-turn pattern: "Name:" or "Speaker N:" at line start
_SPEAKER_RE = re.compile(r"^[A-Z][A-Za-z\s]+:\s", re.MULTILINE)


# ── Document types ───────────────────────────────────────────────────────


class DocumentType(StrEnum):
    TRANSCRIPT = "transcript"
    MEETING = "meeting"
    PERSON = "person"
    COACHING = "coaching"
    FEEDBACK = "feedback"
    DECISION = "decision"
    REFERENCE = "reference"
    UNSTRUCTURED = "unstructured"


# Map document types to DATA_DIR subdirectories
_TYPE_TO_DIR: dict[DocumentType, str] = {
    DocumentType.TRANSCRIPT: "meetings",
    DocumentType.MEETING: "meetings",
    DocumentType.PERSON: "people",
    DocumentType.COACHING: "coaching",
    DocumentType.FEEDBACK: "feedback",
    DocumentType.DECISION: "decisions",
    DocumentType.REFERENCE: "references",
}


@dataclass
class ProcessResult:
    """Result of processing a single document."""

    success: bool
    doc_type: DocumentType
    destination: Path | None = None
    outputs: list[str] | None = None
    error: str | None = None


# ── Detection functions ──────────────────────────────────────────────────


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file.

    Returns (frontmatter_dict, body_text). On any error returns ({}, "").
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("ingest: cannot read %s: %s", path, exc)
        return {}, ""

    match = _FM_RE.match(text)
    if not match:
        return {}, text

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        _log.warning("ingest: bad YAML in %s: %s", path, exc)
        return {}, match.group(2)

    if not isinstance(fm, dict):
        return {}, match.group(2)

    return fm, match.group(2)


def _detect_transcript(path: Path) -> bool:
    """Return True if file looks like a transcript.

    Matches: .vtt/.srt extension, or .md with 3+ speaker-turn patterns.
    """
    suffix = path.suffix.lower()
    if suffix in (".vtt", ".srt"):
        return True

    if suffix == ".md":
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return False
        turns = _SPEAKER_RE.findall(text)
        return len(turns) >= 3

    return False


def _detect_frontmatter_type(path: Path) -> str | None:
    """Return the 'type' field from YAML frontmatter, or None."""
    if path.suffix.lower() != ".md":
        return None
    fm, _ = _parse_frontmatter(path)
    return fm.get("type") if fm else None


def classify_document(path: Path) -> DocumentType:
    """Classify a document by extension, content, and frontmatter.

    Priority: transcript detection first, then frontmatter type, then
    fallback to UNSTRUCTURED.
    """
    # 1. Check transcript patterns (extension + speaker turns)
    if _detect_transcript(path):
        return DocumentType.TRANSCRIPT

    # 2. Check frontmatter type field
    fm_type = _detect_frontmatter_type(path)
    if fm_type:
        try:
            return DocumentType(fm_type)
        except ValueError:
            _log.info("ingest: unknown frontmatter type '%s' in %s", fm_type, path)

    return DocumentType.UNSTRUCTURED


# ── Transcript conversion ────────────────────────────────────────────────


def _convert_transcript_to_md(path: Path) -> str:
    """Convert a .vtt/.srt transcript to markdown with meeting frontmatter.

    Returns the markdown content as a string.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Cannot read transcript {path}: {exc}") from exc

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    stem = path.stem

    frontmatter = (
        f"---\ntype: meeting\ndate: {today}\nsource: transcript\noriginal: {path.name}\n---\n"
    )

    return f"{frontmatter}\n# Transcript: {stem}\n\n{text}"


# ── Processing ───────────────────────────────────────────────────────────


async def process_document(
    path: Path,
    doc_type: DocumentType | None = None,
) -> ProcessResult:
    """Classify and route a document to the appropriate DATA_DIR subdirectory.

    Args:
        path: Path to the document file.
        doc_type: Override classification. If None, classify automatically.

    Returns:
        ProcessResult with success status, type, and destination.
    """
    if not path.exists():
        return ProcessResult(
            success=False,
            doc_type=doc_type or DocumentType.UNSTRUCTURED,
            error=f"File not found: {path}",
        )

    if doc_type is None:
        doc_type = classify_document(path)

    _log.info("ingest: processing %s as %s", path.name, doc_type.value)

    # Unstructured documents have no routing target
    if doc_type == DocumentType.UNSTRUCTURED:
        return ProcessResult(
            success=True,
            doc_type=doc_type,
            outputs=["No routing target for unstructured documents"],
        )

    # Determine destination directory
    subdir = _TYPE_TO_DIR.get(doc_type)
    if not subdir:
        return ProcessResult(
            success=False,
            doc_type=doc_type,
            error=f"No directory mapping for type {doc_type.value}",
        )

    dest_dir = config.data_dir / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[str] = []

    try:
        if doc_type == DocumentType.TRANSCRIPT:
            # Convert transcript to .md with meeting frontmatter
            md_content = _convert_transcript_to_md(path)
            dest_path = dest_dir / f"{path.stem}.md"
            dest_path.write_text(md_content, encoding="utf-8")
            outputs.append(f"Converted transcript to {dest_path}")
        else:
            # Copy typed document to appropriate subdirectory
            dest_path = dest_dir / path.name
            shutil.copy2(path, dest_path)
            outputs.append(f"Filed to {dest_path}")

    except OSError as exc:
        return ProcessResult(
            success=False,
            doc_type=doc_type,
            error=f"Failed to file document: {exc}",
        )

    return ProcessResult(
        success=True,
        doc_type=doc_type,
        destination=dest_path,
        outputs=outputs,
    )


# ── Watch daemon ─────────────────────────────────────────────────────────


async def _watch_inbox(poll_interval: float = 30.0) -> None:
    """Poll DATA_DIR/inbox/ for new files and process them.

    Processed files are moved to DATA_DIR/processed/ with a timestamp prefix.
    Runs indefinitely until cancelled.
    """
    inbox_dir = config.data_dir / "inbox"
    processed_dir = config.data_dir / "processed"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    _log.info("ingest: watching %s (poll every %.0fs)", inbox_dir, poll_interval)

    while True:
        try:
            files = sorted(inbox_dir.iterdir())
        except OSError as exc:
            _log.error("ingest: cannot read inbox: %s", exc)
            await asyncio.sleep(poll_interval)
            continue

        for file_path in files:
            if not file_path.is_file():
                continue

            _log.info("ingest: found %s in inbox", file_path.name)

            try:
                result = await process_document(file_path)

                # Move original to processed/ with timestamp prefix
                ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
                processed_name = f"{ts}_{file_path.name}"
                processed_dest = processed_dir / processed_name
                shutil.move(str(file_path), str(processed_dest))

                if result.success:
                    send_notification(
                        "Document Ingested",
                        f"{file_path.name} → {result.doc_type.value}"
                        + (f" → {result.destination}" if result.destination else ""),
                        priority="default",
                    )
                    _log.info(
                        "ingest: %s processed as %s",
                        file_path.name,
                        result.doc_type.value,
                    )
                else:
                    send_notification(
                        "Ingest Error",
                        f"{file_path.name}: {result.error}",
                        priority="high",
                        tags=["warning"],
                    )
                    _log.error("ingest: %s failed: %s", file_path.name, result.error)

            except Exception as exc:
                _log.error(
                    "ingest: unexpected error processing %s: %s",
                    file_path.name,
                    exc,
                )
                send_notification(
                    "Ingest Error",
                    f"Unexpected error processing {file_path.name}: {exc}",
                    priority="high",
                    tags=["warning"],
                )

        await asyncio.sleep(poll_interval)


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        prog="agents.ingest",
        description="Document classifier, router, and watch folder daemon.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        help="File to classify and process",
    )
    parser.add_argument(
        "--type",
        dest="doc_type",
        choices=[t.value for t in DocumentType],
        help="Override document type classification",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Start inbox watch daemon",
    )

    args = parser.parse_args()

    if args.watch:
        print(f"Watching {config.data_dir / 'inbox'} for new documents...")
        try:
            asyncio.run(_watch_inbox())
        except KeyboardInterrupt:
            print("\nStopped.")
            sys.exit(0)
    elif args.file:
        override = DocumentType(args.doc_type) if args.doc_type else None
        result = asyncio.run(process_document(args.file, doc_type=override))
        if result.success:
            print(f"Type: {result.doc_type.value}")
            if result.destination:
                print(f"Destination: {result.destination}")
            if result.outputs:
                for out in result.outputs:
                    print(f"  {out}")
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
