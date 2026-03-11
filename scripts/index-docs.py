#!/usr/bin/env python3
"""index-docs.py — Index project documentation into Qdrant for demo research.

Reads markdown and YAML files from the hapax-officium project root, chunks them
by heading boundaries, embeds via nomic-embed-text, and upserts into the
Qdrant "documents" collection with deterministic UUIDs for idempotency.

Usage:
    uv run python scripts/index-docs.py [--verbose] [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import uuid
from pathlib import Path

# Ensure ai-agents/ is on sys.path so shared imports work
_SCRIPT_DIR = Path(__file__).resolve().parent
_AI_AGENTS_DIR = _SCRIPT_DIR.parent
if str(_AI_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AI_AGENTS_DIR))

from shared.config import PROJECT_ROOT, embed_batch, get_qdrant  # noqa: E402

log = logging.getLogger("index-docs")

COLLECTION = "documents"
SOURCE_PREFIX = "/documents/rag-sources/hapax-officium"
BATCH_SIZE = 100
MIN_CHUNK_CHARS = 200
MAX_CHUNK_CHARS = 1500
UUID_NAMESPACE = uuid.NAMESPACE_URL


# ── File discovery ──────────────────────────────────────────────────────────


def _discover_files() -> list[Path]:
    """Return all markdown and YAML files to index."""
    files: list[Path] = []

    # Explicit root-level files
    for name in ("CLAUDE.md", "README.md", "agent-architecture.md", "operations-manual.md"):
        p = PROJECT_ROOT / name
        if p.is_file():
            files.append(p)

    # ai-agents/CLAUDE.md
    p = PROJECT_ROOT / "ai-agents" / "CLAUDE.md"
    if p.is_file():
        files.append(p)

    # axioms/registry.yaml
    p = PROJECT_ROOT / "axioms" / "registry.yaml"
    if p.is_file():
        files.append(p)

    # axioms/implications/*.yaml
    impl_dir = PROJECT_ROOT / "axioms" / "implications"
    if impl_dir.is_dir():
        files.extend(sorted(impl_dir.glob("*.yaml")))

    # docs/**/*.md (recursive)
    docs_dir = PROJECT_ROOT / "docs"
    if docs_dir.is_dir():
        files.extend(sorted(docs_dir.rglob("*.md")))

    return files


# ── Chunking ────────────────────────────────────────────────────────────────


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Split text into (heading_hierarchy, body) tuples at ## and ### boundaries.

    Returns a list of (section_heading, section_text) pairs.
    Heading hierarchy tracks parent ## when splitting at ### level.
    """
    # Match lines starting with ## or ### (but not #### or deeper)
    heading_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

    matches = list(heading_pattern.finditer(text))
    if not matches:
        # No headings — return the whole text as one chunk
        return [("(document)", text.strip())]

    sections: list[tuple[str, str]] = []

    # Text before the first heading
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("(preamble)", preamble))

    current_h2 = ""
    for i, match in enumerate(matches):
        level = match.group(1)
        title = match.group(2).strip()

        # Track heading hierarchy
        if level == "##":
            current_h2 = f"## {title}"
            heading = current_h2
        else:  # ###
            if current_h2:
                heading = f"{current_h2} > ### {title}"
            else:
                heading = f"### {title}"

        # Extract body text until next heading
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if body:
            sections.append((heading, body))

    return sections


def _split_long_section(heading: str, text: str) -> list[tuple[str, str]]:
    """Split a section exceeding MAX_CHUNK_CHARS at paragraph boundaries."""
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[tuple[str, str]] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_len = len(para)

        if current_len + para_len + 2 > MAX_CHUNK_CHARS and current_parts:
            chunks.append((heading, "\n\n".join(current_parts)))
            current_parts = []
            current_len = 0

        current_parts.append(para)
        current_len += para_len + 2  # account for \n\n join

    if current_parts:
        chunks.append((heading, "\n\n".join(current_parts)))

    return chunks


def _chunk_file(path: Path, rel_path: str) -> list[dict]:
    """Chunk a single file into indexable records."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return []

    # For YAML files, treat the whole file as one chunk
    if path.suffix in (".yaml", ".yml"):
        section = f"(document) {path.name}"
        point_id = uuid.uuid5(UUID_NAMESPACE, f"{rel_path}::{section}")
        return [
            {
                "id": str(point_id),
                "text": text.strip()[:MAX_CHUNK_CHARS],
                "source": f"{SOURCE_PREFIX}/{rel_path}",
                "filename": path.name,
                "section": section,
            }
        ]

    sections = _split_by_headings(text)
    records: list[dict] = []

    for heading, body in sections:
        if len(body) > MAX_CHUNK_CHARS:
            sub_chunks = _split_long_section(heading, body)
            for idx, (sub_heading, sub_body) in enumerate(sub_chunks):
                if len(sub_body) < MIN_CHUNK_CHARS:
                    continue
                section_key = (
                    f"{sub_heading} (part {idx + 1})" if len(sub_chunks) > 1 else sub_heading
                )
                point_id = uuid.uuid5(UUID_NAMESPACE, f"{rel_path}::{section_key}")
                records.append(
                    {
                        "id": str(point_id),
                        "text": sub_body,
                        "source": f"{SOURCE_PREFIX}/{rel_path}",
                        "filename": path.name,
                        "section": section_key,
                    }
                )
        else:
            if len(body) < MIN_CHUNK_CHARS:
                continue
            point_id = uuid.uuid5(UUID_NAMESPACE, f"{rel_path}::{heading}")
            records.append(
                {
                    "id": str(point_id),
                    "text": body,
                    "source": f"{SOURCE_PREFIX}/{rel_path}",
                    "filename": path.name,
                    "section": heading,
                }
            )

    return records


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Index project docs into Qdrant")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--dry-run", action="store_true", help="Chunk and report but do not embed or upsert"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s: %(message)s",
    )

    files = _discover_files()
    log.info("Discovered %d files to index", len(files))

    # Chunk all files
    all_records: list[dict] = []
    for path in files:
        rel_path = str(path.relative_to(PROJECT_ROOT))
        records = _chunk_file(path, rel_path)
        if args.verbose:
            log.debug("  %s -> %d chunks", rel_path, len(records))
        all_records.extend(records)

    log.info("Total chunks: %d", len(all_records))

    if not all_records:
        log.warning("No chunks produced — nothing to index")
        return

    if args.dry_run:
        log.info("Dry run — skipping embedding and upsert")
        for rec in all_records:
            print(f"  [{rec['filename']}] {rec['section']} ({len(rec['text'])} chars)")
        return

    # Embed in batches
    log.info("Embedding %d chunks via nomic-embed-text ...", len(all_records))
    texts = [rec["text"] for rec in all_records]
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        vectors = embed_batch(batch, prefix="search_document")
        all_vectors.extend(vectors)
        if args.verbose:
            log.debug("  Embedded batch %d-%d", i, i + len(batch))

    # Upsert into Qdrant
    from qdrant_client.models import PointStruct

    client = get_qdrant()
    points = []
    for rec, vec in zip(all_records, all_vectors, strict=False):
        points.append(
            PointStruct(
                id=rec["id"],
                vector=vec,
                payload={
                    "source": rec["source"],
                    "text": rec["text"],
                    "filename": rec["filename"],
                    "section": rec["section"],
                },
            )
        )

    log.info("Upserting %d points into Qdrant '%s' ...", len(points), COLLECTION)
    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i : i + BATCH_SIZE]
        client.upsert(collection_name=COLLECTION, points=batch)
        if args.verbose:
            log.debug("  Upserted batch %d-%d", i, i + len(batch))

    log.info("Done. Indexed %d chunks from %d files.", len(points), len(files))


if __name__ == "__main__":
    main()
