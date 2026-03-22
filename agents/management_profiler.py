"""management_profiler.py — Management self-awareness profiler.

Builds a structured profile of the OPERATOR's management behavior by mining
management data (1:1 patterns, feedback records, decision logs,
coaching experiments, meeting notes). Answers "how do I tend to manage?"

Usage:
    uv run python -m agents.management_profiler              # Full extraction
    uv run python -m agents.management_profiler --show       # Display current profile
    uv run python -m agents.management_profiler --auto       # Unattended: detect changes, update if needed
    uv run python -m agents.management_profiler --curate     # Run quality curation on existing profile
    uv run python -m agents.management_profiler --digest     # Generate profile digest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from shared.config import get_model

# Import Langfuse OTel config (side-effect: configures exporter)
try:
    from shared import langfuse_config  # noqa: F401
except ImportError:
    pass  # Langfuse optional

log = logging.getLogger("management_profiler")


# ── Schemas ──────────────────────────────────────────────────────────────────

PROFILE_DIMENSIONS = [
    "management_practice",  # cadence habits, delegation patterns, meeting conduct
    "team_leadership",  # leadership style, growth orientation, risk tolerance
    "decision_patterns",  # speed, risk tolerance, information requirements
    "communication_style",  # directness, feedback delivery patterns, written vs verbal
    "attention_distribution",  # which team members get more/less focus
    "self_awareness",  # stated vs actual management patterns
]

# Sources representing operator intent (explicit statements).
# These take precedence over observation sources during merge.
AUTHORITY_SOURCES = frozenset({"interview", "operator", "correction"})

# Safety constraint injected into all LLM prompts
_SAFETY_CONSTRAINT = (
    "Profile the OPERATOR's management behavior only. Never profile or evaluate "
    "team members. This answers 'how do I tend to manage?' -- never 'how is "
    "Person X performing?'"
)


class ProfileFact(BaseModel):
    """A single extracted fact about the operator's management behavior."""

    dimension: str = Field(description="Profile dimension: " + ", ".join(PROFILE_DIMENSIONS))
    key: str = Field(description="Snake_case identifier for this fact")
    value: str = Field(description="The factual information")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence 0.0-1.0")
    source: str = Field(description='Source identifier, e.g. "management-bridge"')
    evidence: str = Field(description="Supporting quote or paraphrase from source")


class ChunkExtraction(BaseModel):
    """Structured output from the extraction agent."""

    facts: list[ProfileFact] = Field(default_factory=list)


class ProfileDimension(BaseModel):
    """A group of facts under one dimension with a narrative summary."""

    name: str
    summary: str = ""
    facts: list[ProfileFact] = Field(default_factory=list)


class ManagementProfile(BaseModel):
    """The operator's management self-awareness profile."""

    summary: str = ""
    dimensions: list[ProfileDimension] = Field(default_factory=list)
    sources_processed: list[str] = Field(default_factory=list)
    version: int = 1
    updated_at: str = ""


class SynthesisOutput(BaseModel):
    """Structured output from the synthesis agent."""

    summary: str = Field(description="2-3 sentence summary of operator's management style")
    dimension_summaries: dict[str, str] = Field(
        description="Dimension name -> narrative summary paragraph"
    )


# ── Agents ───────────────────────────────────────────────────────────────────

extraction_agent = Agent(
    get_model("balanced"),
    output_type=ChunkExtraction,
    system_prompt=(
        "You are a management self-awareness profiler. Given text from management "
        "notes (1:1 records, feedback logs, decision records, coaching experiments, "
        "meeting notes), extract facts about the OPERATOR's management patterns.\n\n"
        f"SAFETY: {_SAFETY_CONSTRAINT}\n\n"
        "Dimensions to extract into: " + ", ".join(PROFILE_DIMENSIONS) + "\n\n"
        "Guidelines:\n"
        "- Extract concrete, specific management behavior patterns\n"
        "- Focus on HOW the operator manages, not on team member performance\n"
        "- Set confidence based on how explicit the evidence is (0.9+ for stated patterns, "
        "0.5-0.7 for inferred patterns, below 0.5 for weak signals)\n"
        "- Use snake_case keys (e.g., 'feedback_delivery_speed', '1on1_rescheduling_rate')\n"
        "- Include supporting evidence from the source material\n"
        "- If the chunk has no extractable management pattern information, return empty facts"
    ),
)

synthesis_agent = Agent(
    get_model("balanced"),
    output_type=SynthesisOutput,
    system_prompt=(
        "You are a management profile synthesis agent. Given extracted facts about an "
        "operator's management behavior, produce a coherent self-awareness profile.\n\n"
        f"SAFETY: {_SAFETY_CONSTRAINT}\n\n"
        "For the summary: Write 2-3 sentences capturing how this person tends to manage -- "
        "their cadence habits, communication style, decision patterns, and growth orientation.\n\n"
        "For dimension summaries: Write a concise paragraph for each dimension that has facts. "
        "Synthesize the facts into a narrative about the operator's management tendencies. "
        "Highlight patterns and potential blind spots."
    ),
)

# Register axiom compliance tools on agents that make architectural decisions
from shared.axiom_tools import get_axiom_tools

for _tool_fn in get_axiom_tools():
    extraction_agent.tool(_tool_fn)
    synthesis_agent.tool(_tool_fn)


# ── Curation schemas & agent ─────────────────────────────────────────────────


class CurationOp(BaseModel):
    """A single curation operation on profile facts."""

    action: Literal["merge", "delete", "update", "flag"] = Field(
        description="merge: combine redundant facts; delete: remove stale/irrelevant; "
        "update: fix key/value/confidence; flag: mark contradiction for human review"
    )
    keys: list[str] = Field(description="Fact key(s) affected by this operation")
    reason: str = Field(description="Why this operation is needed")
    new_key: str | None = Field(default=None, description="For merge/update: the resulting key")
    new_value: str | None = Field(default=None, description="For merge/update: the resulting value")
    new_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="For merge/update: the resulting confidence"
    )
    gap_type: str | None = Field(
        default=None,
        description="For flag action: 'stated_vs_actual' (operator says X but does Y), "
        "'consistency' (pattern varies across team members), "
        "'blind_spot' (pattern not recognized by operator)",
    )


class DimensionCuration(BaseModel):
    """Curation results for a single profile dimension."""

    dimension: str
    operations: list[CurationOp] = Field(default_factory=list)
    health_score: float = Field(
        ge=0.0, le=1.0, description="0.0 = needs major cleanup, 1.0 = pristine"
    )


curator_agent = Agent(
    get_model("balanced"),
    output_type=DimensionCuration,
    system_prompt=(
        "You are a management profile quality curator. Given facts for one dimension "
        "of a management self-awareness profile, assess quality and return curation ops.\n\n"
        f"SAFETY: {_SAFETY_CONSTRAINT}\n\n"
        "Operations:\n"
        "- **merge**: Two or more facts say the same thing differently.\n"
        "- **delete**: Fact is stale, too vague, or about a team member rather than "
        "the operator's management pattern.\n"
        "- **update**: Key needs normalization or confidence is miscalibrated.\n"
        "- **flag**: Facts reveal a stated-vs-actual gap in management behavior. "
        "Set gap_type to 'stated_vs_actual', 'consistency', or 'blind_spot'.\n\n"
        "Guidelines:\n"
        "- Delete any facts that evaluate team members rather than operator behavior\n"
        "- Be aggressive about merging redundancy\n"
        "- Stated-vs-actual gaps are the most valuable signal for self-awareness\n"
        "- health_score: 1.0 if no operations needed, lower based on severity"
    ),
)


# ── Fact merging ─────────────────────────────────────────────────────────────


def _source_prefix(source: str) -> str:
    """Extract the source type prefix (e.g., 'interview' from 'interview:2024-...')."""
    return source.split("/")[0].split(":")[0]


def merge_facts(existing: list[ProfileFact], new: list[ProfileFact]) -> list[ProfileFact]:
    """Merge new facts into existing with authority-aware precedence.

    When a new fact conflicts with an existing fact on the same (dimension, key):
    - Authority source (interview/operator/correction) always wins over observation
    - Observation source never overrides an authority source
    - Same source type: higher confidence wins
    """
    fact_map: dict[tuple[str, str], ProfileFact] = {}

    for fact in existing:
        key = (fact.dimension, fact.key)
        fact_map[key] = fact

    for fact in new:
        key = (fact.dimension, fact.key)
        if key not in fact_map:
            fact_map[key] = fact
            continue

        existing_fact = fact_map[key]
        new_is_authority = _source_prefix(fact.source) in AUTHORITY_SOURCES
        existing_is_authority = _source_prefix(existing_fact.source) in AUTHORITY_SOURCES

        if new_is_authority and not existing_is_authority:
            fact_map[key] = fact
        elif existing_is_authority and not new_is_authority:
            pass
        elif fact.confidence > existing_fact.confidence:
            fact_map[key] = fact

    return list(fact_map.values())


def group_facts_by_dimension(facts: list[ProfileFact]) -> dict[str, list[ProfileFact]]:
    """Group facts by their dimension."""
    groups: dict[str, list[ProfileFact]] = {}
    for fact in facts:
        groups.setdefault(fact.dimension, []).append(fact)
    return groups


# ── Data sources ─────────────────────────────────────────────────────────────

import contextlib

from shared.config import PROFILES_DIR

if TYPE_CHECKING:
    from pathlib import Path


def load_management_facts() -> list[ProfileFact]:
    """Load management facts from the management bridge.

    Uses shared.management_bridge to extract deterministic facts from
    management data (1:1 patterns, coaching, feedback, meetings).
    """
    facts: list[ProfileFact] = []

    # Load from management bridge structured facts file
    facts_file = PROFILES_DIR / "management-structured-facts.json"
    if facts_file.exists():
        try:
            data = json.loads(facts_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    with contextlib.suppress(Exception):
                        facts.append(ProfileFact.model_validate(item))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to load management facts from %s: %s", facts_file.name, e)

    return facts


def generate_and_load_management_facts() -> list[ProfileFact]:
    """Run management bridge to generate facts, then load them.

    Calls shared.management_bridge.generate_facts(), saves the output,
    then loads as ProfileFact objects.
    """
    try:
        from shared.management_bridge import generate_facts, save_facts

        raw_facts = generate_facts()
        if raw_facts:
            save_facts(raw_facts)
            log.info("Generated %d management facts", len(raw_facts))
    except Exception as e:
        log.warning("Management bridge generation failed: %s", e)

    return load_management_facts()


def _gather_vault_text_chunks(vault_path: Path | None = None) -> list[dict]:
    """Gather text content from management notes for LLM extraction.

    Returns empty list — vault data source excised.
    Data source will be reimplemented with VS Code + Qdrant integration.
    """
    return []


# ── Pipeline ─────────────────────────────────────────────────────────────────

DEFAULT_EXTRACTION_CONCURRENCY = 8


async def extract_from_chunks(
    chunks: list[dict],
    *,
    concurrency: int = DEFAULT_EXTRACTION_CONCURRENCY,
    existing_fact_keys: set[tuple[str, str]] | None = None,
) -> list[ProfileFact]:
    """Run the extraction agent on each text chunk with bounded concurrency.

    Args:
        chunks: Dicts with 'text', 'source_id', 'source_type'.
        concurrency: Max parallel LLM calls.
        existing_fact_keys: Known (dimension, key) pairs for dedup.
    """
    all_facts: list[ProfileFact] = []
    total = len(chunks)
    completed = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)

    seen_keys: set[tuple[str, str]] = set(existing_fact_keys or ())

    async def _extract_one(chunk: dict) -> list[ProfileFact]:
        nonlocal completed

        async with sem:
            prompt = (
                f"Source: {chunk['source_id']} (type: {chunk['source_type']})\n\n"
                f"--- TEXT ---\n{chunk['text']}\n--- END ---"
            )
            try:
                result = await extraction_agent.run(prompt)
                facts = result.output.facts or []
                for fact in facts:
                    fact.source = chunk["source_id"]
            except Exception as e:
                print(f"    -> ERROR [{chunk['source_id']}]: {e}", file=sys.stderr, flush=True)
                facts = []

            async with lock:
                completed += 1
                new_key_count = 0
                for fact in facts:
                    fkey = (fact.dimension, fact.key)
                    if fkey not in seen_keys:
                        seen_keys.add(fkey)
                        new_key_count += 1

                if facts:
                    print(
                        f"  [{completed}/{total}] {chunk['source_id']} -> "
                        f"{len(facts)} facts ({new_key_count} new keys)",
                        flush=True,
                    )
                else:
                    print(f"  [{completed}/{total}] {chunk['source_id']} -> no facts", flush=True)

            return facts

    tasks = [asyncio.create_task(_extract_one(chunk)) for chunk in chunks]
    results = await asyncio.gather(*tasks)

    for facts in results:
        all_facts.extend(facts)

    return all_facts


async def synthesize_profile(facts: list[ProfileFact]) -> SynthesisOutput:
    """Run the synthesis agent on all collected facts."""
    grouped = group_facts_by_dimension(facts)

    parts: list[str] = []
    for dim, dim_facts in sorted(grouped.items()):
        parts.append(f"## {dim}")
        for f in dim_facts:
            parts.append(
                f"- **{f.key}**: {f.value} (confidence: {f.confidence}, source: {f.source})"
            )
        parts.append("")

    facts_text = "\n".join(parts)
    prompt = (
        f"Synthesize these management behavior facts into a self-awareness profile:\n\n{facts_text}"
    )

    result = await synthesis_agent.run(prompt)
    return result.output


def build_profile(
    facts: list[ProfileFact],
    synthesis: SynthesisOutput,
    sources_processed: list[str],
    existing_profile: ManagementProfile | None = None,
) -> ManagementProfile:
    """Assemble the final ManagementProfile from facts and synthesis output."""
    grouped = group_facts_by_dimension(facts)

    dimensions: list[ProfileDimension] = []
    for dim_name in PROFILE_DIMENSIONS:
        dim_facts = grouped.get(dim_name, [])
        summary = synthesis.dimension_summaries.get(dim_name, "")
        if dim_facts or summary:
            dimensions.append(
                ProfileDimension(
                    name=dim_name,
                    summary=summary,
                    facts=dim_facts,
                )
            )

    # Include any extra dimensions not in the default list
    for dim_name in sorted(grouped.keys()):
        if dim_name not in PROFILE_DIMENSIONS:
            dimensions.append(
                ProfileDimension(
                    name=dim_name,
                    summary=synthesis.dimension_summaries.get(dim_name, ""),
                    facts=grouped[dim_name],
                )
            )

    version = (existing_profile.version + 1) if existing_profile else 1

    return ManagementProfile(
        summary=synthesis.summary,
        dimensions=dimensions,
        sources_processed=sources_processed,
        version=version,
        updated_at=datetime.now(UTC).isoformat(),
    )


# ── I/O ──────────────────────────────────────────────────────────────────────


def load_existing_profile() -> ManagementProfile | None:
    """Load existing management profile from disk if it exists."""
    path = PROFILES_DIR / "management-profile.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return ManagementProfile.model_validate(data)
    except json.JSONDecodeError as e:
        log.warning("Profile %s is corrupt (invalid JSON): %s", path, e)
        return None
    except Exception as e:
        log.warning("Failed to load profile %s: %s", path, e)
        return None


def save_profile(profile: ManagementProfile) -> None:
    """Save profile to JSON and Markdown."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = PROFILES_DIR / "management-profile.json"
    json_path.write_text(profile.model_dump_json(indent=2))
    print(f"Saved: {json_path}")

    # Markdown
    md_path = PROFILES_DIR / "management-profile.md"
    md_path.write_text(_profile_to_markdown(profile))
    print(f"Saved: {md_path}")


def _profile_to_markdown(profile: ManagementProfile) -> str:
    """Render a ManagementProfile as readable Markdown."""
    lines: list[str] = [
        "# Management Self-Awareness Profile",
        "",
        f"*Version {profile.version} -- {profile.updated_at}*",
        "",
    ]

    lines.append("## Summary")
    lines.append("")
    lines.append(profile.summary or "*No summary generated yet.*")
    lines.append("")

    for dim in profile.dimensions:
        lines.append(f"## {dim.name.replace('_', ' ').title()}")
        lines.append("")
        if dim.summary:
            lines.append(dim.summary)
            lines.append("")
        if dim.facts:
            lines.append("| Key | Value | Confidence | Source |")
            lines.append("|-----|-------|-----------|--------|")
            for f in sorted(dim.facts, key=lambda x: -x.confidence):
                lines.append(f"| {f.key} | {f.value} | {f.confidence:.1f} | {f.source} |")
            lines.append("")

    # Data gaps
    covered = {d.name for d in profile.dimensions}
    missing = [d for d in PROFILE_DIMENSIONS if d not in covered]
    if missing:
        lines.append("## Data Gaps")
        lines.append("")
        lines.append("The following dimensions have no data yet:")
        lines.append("")
        for m in missing:
            lines.append(f"- {m.replace('_', ' ').title()}")
        lines.append("")

    # Sources
    lines.append("## Sources Processed")
    lines.append("")
    for s in profile.sources_processed:
        lines.append(f"- {s}")
    lines.append("")

    return "\n".join(lines)


# ── Interview integration ────────────────────────────────────────────────────


def flush_interview_facts(
    facts: list,
    insights: list,
    source: str = "interview:logos",
) -> str:
    """Merge interview-sourced facts into the management profile.

    Converts RecordedFact objects from the interview system into ProfileFact
    objects and merges them with the existing profile. Does NOT run LLM
    synthesis -- just merges facts and saves.

    Args:
        facts: list of RecordedFact.
        insights: list of RecordedInsight.
        source: Source tag for provenance tracking.

    Returns:
        Summary of what was updated.
    """
    if not facts and not insights:
        return "No facts or insights to flush."

    source_tag = source
    now_iso = datetime.now(UTC).isoformat()

    # Convert RecordedFact -> ProfileFact (only management dimensions)
    new_profile_facts: list[ProfileFact] = []
    for rf in facts:
        if rf.dimension not in PROFILE_DIMENSIONS:
            continue  # Skip non-management dimensions
        new_profile_facts.append(
            ProfileFact(
                dimension=rf.dimension,
                key=rf.key,
                value=rf.value,
                confidence=rf.confidence,
                source=source_tag,
                evidence=rf.evidence,
            )
        )

    # Convert insights to facts in management dimensions
    insight_dimension_map = {
        "management_gap": "management_practice",
        "leadership_pattern": "team_leadership",
        "decision_bias": "decision_patterns",
        "communication_gap": "communication_style",
        "attention_bias": "attention_distribution",
        "blind_spot": "self_awareness",
    }
    for ins in insights:
        dim = insight_dimension_map.get(ins.category, "self_awareness")
        desc_hash = hex(hash(ins.description) & 0xFFFF)[2:]
        new_profile_facts.append(
            ProfileFact(
                dimension=dim,
                key=f"insight_{ins.category}_{desc_hash}",
                value=f"{ins.description}. Recommendation: {ins.recommendation}"
                if ins.recommendation
                else ins.description,
                confidence=0.85,
                source=source_tag,
                evidence=f"Interview insight ({ins.category})",
            )
        )

    # Load existing profile and merge
    existing = load_existing_profile()
    if existing:
        existing_facts = [f for dim in existing.dimensions for f in dim.facts]
        merged = merge_facts(existing_facts, new_profile_facts)
    else:
        merged = new_profile_facts

    # Rebuild dimensions (without re-synthesizing)
    grouped = group_facts_by_dimension(merged)
    existing_summaries: dict[str, str] = {}
    if existing:
        existing_summaries = {d.name: d.summary for d in existing.dimensions}

    dimensions: list[ProfileDimension] = []
    for dim_name in PROFILE_DIMENSIONS:
        dim_facts = grouped.get(dim_name, [])
        if dim_facts:
            dimensions.append(
                ProfileDimension(
                    name=dim_name,
                    summary=existing_summaries.get(dim_name, ""),
                    facts=dim_facts,
                )
            )

    version = (existing.version + 1) if existing else 1
    updated_profile = ManagementProfile(
        summary=existing.summary if existing else "",
        dimensions=dimensions,
        sources_processed=(existing.sources_processed if existing else []) + [source_tag],
        version=version,
        updated_at=now_iso,
    )

    save_profile(updated_profile)

    new_fact_count = len(facts)
    insight_count = len(insights)
    return (
        f"Flushed {new_fact_count} facts and {insight_count} insights to management profile "
        f"(v{version}, {len(merged)} total facts).\n"
        f"Run `management_profiler --auto` to update dimension summaries."
    )


# ── Operator corrections ──────────────────────────────────────────────────────


def apply_corrections(corrections: list[dict]) -> str:
    """Apply operator corrections to the management profile.

    Each correction dict has:
        dimension: str
        key: str
        value: str | None  (None = delete the fact)

    Returns summary of changes.
    """
    existing = load_existing_profile()
    if not existing:
        return "No profile found. Run extraction first."

    existing_facts = [f for dim in existing.dimensions for f in dim.facts]
    now_iso = datetime.now(UTC).isoformat()
    applied = 0
    deleted = 0

    for corr in corrections:
        dim = corr.get("dimension", "")
        key = corr.get("key", "")
        value = corr.get("value")

        if value is None:
            before = len(existing_facts)
            existing_facts = [
                f for f in existing_facts if not (f.dimension == dim and f.key == key)
            ]
            if len(existing_facts) < before:
                deleted += 1
        else:
            correction_fact = ProfileFact(
                dimension=dim,
                key=key,
                value=value,
                confidence=1.0,
                source="operator:correction",
                evidence=f"Operator correction at {now_iso}",
            )
            existing_facts = merge_facts(existing_facts, [correction_fact])
            applied += 1

    # Rebuild dimensions
    grouped = group_facts_by_dimension(existing_facts)
    existing_summaries = {d.name: d.summary for d in existing.dimensions}

    dimensions: list[ProfileDimension] = []
    for dim_name in PROFILE_DIMENSIONS:
        dim_facts = grouped.get(dim_name, [])
        if dim_facts:
            dimensions.append(
                ProfileDimension(
                    name=dim_name,
                    summary=existing_summaries.get(dim_name, ""),
                    facts=dim_facts,
                )
            )

    updated_profile = ManagementProfile(
        summary=existing.summary,
        dimensions=dimensions,
        sources_processed=existing.sources_processed,
        version=existing.version + 1,
        updated_at=now_iso,
    )
    save_profile(updated_profile)

    parts = []
    if applied:
        parts.append(f"{applied} corrected")
    if deleted:
        parts.append(f"{deleted} deleted")
    total = sum(len(d.facts) for d in dimensions)
    return f"Applied corrections ({', '.join(parts)}). Profile v{updated_profile.version}, {total} total facts."


# ── Profile curation ─────────────────────────────────────────────────────────


def apply_curation(
    facts: list[ProfileFact],
    curation: DimensionCuration,
) -> tuple[list[ProfileFact], list[CurationOp]]:
    """Apply curation operations to a list of facts for one dimension.

    Returns (curated_facts, flagged_ops) -- flagged ops need human review.
    """
    fact_map = {f.key: f for f in facts}
    flagged: list[CurationOp] = []

    for op in curation.operations:
        if op.action == "delete":
            for key in op.keys:
                fact_map.pop(key, None)

        elif op.action == "merge":
            source_facts = [fact_map.pop(k) for k in op.keys if k in fact_map]
            if source_facts and op.new_key and op.new_value is not None:
                best_confidence = op.new_confidence or max(f.confidence for f in source_facts)
                all_sources = ", ".join(sorted({f.source for f in source_facts}))
                fact_map[op.new_key] = ProfileFact(
                    dimension=curation.dimension,
                    key=op.new_key,
                    value=op.new_value,
                    confidence=best_confidence,
                    source=all_sources,
                    evidence=f"Merged from: {', '.join(op.keys)}. {op.reason}",
                )

        elif op.action == "update":
            for key in op.keys:
                if key not in fact_map:
                    continue
                fact = fact_map[key]
                target_key = op.new_key or key
                if target_key != key:
                    fact_map.pop(key)
                fact_map[target_key] = ProfileFact(
                    dimension=curation.dimension,
                    key=target_key,
                    value=op.new_value or fact.value,
                    confidence=op.new_confidence
                    if op.new_confidence is not None
                    else fact.confidence,
                    source=fact.source,
                    evidence=fact.evidence,
                )

        elif op.action == "flag":
            flagged.append(op)

    return list(fact_map.values()), flagged


async def curate_profile(profile: ManagementProfile) -> tuple[ManagementProfile, list[CurationOp]]:
    """Run the curator agent on each dimension of the profile.

    Returns (curated_profile, all_flagged_ops).
    """
    all_flagged: list[CurationOp] = []
    curated_dimensions: list[ProfileDimension] = []
    total_ops = 0

    for dim in profile.dimensions:
        if not dim.facts:
            curated_dimensions.append(dim)
            continue

        fact_lines = []
        for f in dim.facts:
            fact_lines.append(
                f"- **{f.key}**: {f.value} (confidence={f.confidence:.2f}, source={f.source})"
            )

        prompt = f"Dimension: {dim.name}\nFact count: {len(dim.facts)}\n\n" + "\n".join(fact_lines)

        print(f"  Curating {dim.name} ({len(dim.facts)} facts)...", flush=True)
        try:
            result = await curator_agent.run(prompt)
            curation = result.output

            curated_facts, flagged = apply_curation(dim.facts, curation)
            all_flagged.extend(flagged)
            total_ops += len(curation.operations)

            op_summary = []
            for action in ("merge", "delete", "update", "flag"):
                count = sum(1 for o in curation.operations if o.action == action)
                if count:
                    op_summary.append(f"{count} {action}")

            if op_summary:
                print(
                    f"    -> {', '.join(op_summary)} | health: {curation.health_score:.2f}",
                    flush=True,
                )
            else:
                print(f"    -> clean | health: {curation.health_score:.2f}", flush=True)

            curated_dimensions.append(
                ProfileDimension(
                    name=dim.name,
                    summary=dim.summary,
                    facts=curated_facts,
                )
            )

        except Exception as e:
            log.error(f"Curation failed for {dim.name}: {e}")
            curated_dimensions.append(dim)

    before_count = sum(len(d.facts) for d in profile.dimensions)
    after_count = sum(len(d.facts) for d in curated_dimensions)

    curated_profile = profile.model_copy(
        update={
            "dimensions": curated_dimensions,
            "version": profile.version + 1,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    print(f"\nCuration complete: {total_ops} operations applied")
    print(f"  Facts: {before_count} -> {after_count} ({before_count - after_count} removed/merged)")
    if all_flagged:
        print(f"  Flagged for review: {len(all_flagged)}")

    return curated_profile, all_flagged


async def run_curate() -> None:
    """Run curation on existing profile."""
    profile = load_existing_profile()
    if not profile:
        print("No profile found. Run extraction first.")
        return

    fact_count = sum(len(d.facts) for d in profile.dimensions)
    print(
        f"Curating profile v{profile.version} ({fact_count} facts, "
        f"{len(profile.dimensions)} dimensions)...\n"
    )

    curated, flagged = await curate_profile(profile)
    save_profile(curated)

    # Re-synthesize after curation since facts changed
    all_facts = [f for dim in curated.dimensions for f in dim.facts]
    print("\nRe-synthesizing after curation...")
    synthesis = await synthesize_profile(all_facts)

    # Update summaries
    final_dims = []
    for dim in curated.dimensions:
        new_summary = synthesis.dimension_summaries.get(dim.name, dim.summary)
        final_dims.append(ProfileDimension(name=dim.name, summary=new_summary, facts=dim.facts))

    final = curated.model_copy(
        update={
            "summary": synthesis.summary,
            "dimensions": final_dims,
        }
    )
    save_profile(final)

    # Append flagged items to the markdown
    if flagged:
        md_path = PROFILES_DIR / "management-profile.md"
        flag_lines = ["\n## Flagged for Review\n"]
        for op in flagged:
            prefix = f"[{op.gap_type}] " if op.gap_type else ""
            flag_lines.append(f"- {prefix}**{', '.join(op.keys)}**: {op.reason}")
        with open(md_path, "a") as f:
            f.write("\n".join(flag_lines) + "\n")
        print(f"\nFlagged items appended to {md_path}")


# ── Profile digest generation ─────────────────────────────────────────────────


async def generate_digest(profile: ManagementProfile) -> dict:
    """Generate a pre-computed profile digest with per-dimension summaries.

    One LLM call per dimension using the fast model. Returns the digest dict
    and saves it to profiles/management-digest.json.
    """
    from shared.config import get_model as _get_model

    grouped = group_facts_by_dimension([f for dim in profile.dimensions for f in dim.facts])

    dimensions: dict[str, dict] = {}
    for dim_name in PROFILE_DIMENSIONS:
        facts = grouped.get(dim_name, [])
        count = len(facts)
        if count == 0:
            dimensions[dim_name] = {
                "summary": "No data collected yet.",
                "fact_count": 0,
                "avg_confidence": 0.0,
            }
            continue

        avg_conf = sum(f.confidence for f in facts) / count
        top_facts = sorted(facts, key=lambda f: -f.confidence)[:20]
        fact_lines = [f"- {f.key}: {f.value} (conf: {f.confidence})" for f in top_facts]

        try:
            summary_agent = Agent(
                _get_model("fast"),
                system_prompt=(
                    "Summarize these management behavior facts into a concise narrative paragraph "
                    "(200-400 tokens). Focus on key management patterns and tendencies. "
                    f"Write about the operator's management style. {_SAFETY_CONSTRAINT}"
                ),
            )
            result = await summary_agent.run(
                f"Dimension: {dim_name}\n"
                f"Facts ({count} total, showing top {len(top_facts)}):\n" + "\n".join(fact_lines)
            )
            summary = result.output
        except Exception as e:
            log.warning("Failed to summarize dimension %s: %s", dim_name, e)
            summary = f"{count} facts collected, avg confidence {avg_conf:.2f}."

        dimensions[dim_name] = {
            "summary": summary,
            "fact_count": count,
            "avg_confidence": round(avg_conf, 2),
        }

    total_facts = sum(d["fact_count"] for d in dimensions.values())

    digest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "profile_version": profile.version,
        "total_facts": total_facts,
        "overall_summary": profile.summary or "",
        "dimensions": dimensions,
    }

    # Save to disk
    digest_path = PROFILES_DIR / "management-digest.json"
    digest_path.write_text(json.dumps(digest, indent=2))
    log.info("Saved management profile digest: %s (%d facts)", digest_path, total_facts)

    return digest


# ── CLI ──────────────────────────────────────────────────────────────────────


async def run_extraction() -> None:
    """Main extraction pipeline -- management data sources."""
    existing = load_existing_profile()

    # Step 1: Generate deterministic facts from management bridge
    print("Generating management facts...")
    bridge_facts = generate_and_load_management_facts()
    print(f"  {len(bridge_facts)} deterministic facts from management bridge")

    # Step 2: Gather text for LLM extraction
    chunks = _gather_vault_text_chunks()
    print(f"  {len(chunks)} text chunks from management data")

    if not bridge_facts and not chunks:
        print("No management data found.")
        return

    # Step 3: Extract from text chunks via LLM
    existing_facts: list[ProfileFact] = []
    if existing:
        for dim in existing.dimensions:
            existing_facts.extend(dim.facts)
    existing_keys = {(f.dimension, f.key) for f in existing_facts}

    llm_facts: list[ProfileFact] = []
    if chunks:
        print(f"\nExtracting management patterns from {len(chunks)} chunks...")
        llm_facts = await extract_from_chunks(chunks, existing_fact_keys=existing_keys)
        print(f"Extracted {len(llm_facts)} facts via LLM")

    # Step 4: Merge all facts
    all_new = bridge_facts + llm_facts
    all_facts = merge_facts(existing_facts, all_new)
    print(f"Merged to {len(all_facts)} facts ({len(existing_facts)} existing + {len(all_new)} new)")

    # Step 5: Synthesize
    print("\nSynthesizing management profile...")
    synthesis = await synthesize_profile(all_facts)

    # Track sources
    new_source_ids = {c["source_id"] for c in chunks}
    if bridge_facts:
        new_source_ids.add("management-bridge")
    all_processed = sorted(set(existing.sources_processed if existing else []) | new_source_ids)

    # Build and save
    profile = build_profile(all_facts, synthesis, all_processed, existing)
    save_profile(profile)
    print(f"\nManagement profile v{profile.version}")
    print(f"  {len(all_facts)} facts across {len(profile.dimensions)} dimensions")


async def run_auto() -> None:
    """Unattended auto-update: generate facts, extract if needed.

    Designed for systemd timer / cron invocation.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    # Generate fresh management facts
    bridge_facts = generate_and_load_management_facts()
    log.info("Generated %d management bridge facts", len(bridge_facts))

    # Gather text chunks
    chunks = _gather_vault_text_chunks()

    if not bridge_facts and not chunks:
        log.info("No management data found -- nothing to do")
        return

    # Load existing profile
    existing = load_existing_profile()
    existing_facts: list[ProfileFact] = []
    if existing:
        for dim in existing.dimensions:
            existing_facts.extend(dim.facts)
    existing_keys = {(f.dimension, f.key) for f in existing_facts}

    # Extract from text chunks
    llm_facts: list[ProfileFact] = []
    if chunks:
        log.info("Processing %d text chunks", len(chunks))
        llm_facts = await extract_from_chunks(chunks, existing_fact_keys=existing_keys)
        log.info("Extracted %d facts from text chunks", len(llm_facts))

    # Merge
    all_new = bridge_facts + llm_facts
    all_facts = merge_facts(existing_facts, all_new)
    log.info("Merged to %d facts", len(all_facts))

    # Synthesize
    synthesis = await synthesize_profile(all_facts)

    new_source_ids = {c["source_id"] for c in chunks}
    if bridge_facts:
        new_source_ids.add("management-bridge")
    all_processed = sorted(set(existing.sources_processed if existing else []) | new_source_ids)

    profile = build_profile(all_facts, synthesis, all_processed, existing)
    save_profile(profile)
    log.info(
        "Management profile v%d: %d facts across %d dimensions",
        profile.version,
        len(all_facts),
        len(profile.dimensions),
    )

    # Curate after extraction
    log.info("Running post-extraction curation")
    curated, flagged = await curate_profile(profile)
    save_profile(curated)

    # Re-synthesize after curation
    curated_facts = [f for dim in curated.dimensions for f in dim.facts]
    synthesis = await synthesize_profile(curated_facts)
    final_dims = []
    for dim in curated.dimensions:
        new_summary = synthesis.dimension_summaries.get(dim.name, dim.summary)
        final_dims.append(ProfileDimension(name=dim.name, summary=new_summary, facts=dim.facts))
    final = curated.model_copy(update={"summary": synthesis.summary, "dimensions": final_dims})
    save_profile(final)

    if flagged:
        log.warning("Flagged %d items for human review", len(flagged))

    # Generate digest
    try:
        digest = await generate_digest(final)
        log.info("Generated management digest: %d facts", digest["total_facts"])
    except Exception as e:
        log.warning("Digest generation failed: %s", e)

    log.info("Auto-update complete")


def run_show() -> None:
    """Display current management profile."""
    profile = load_existing_profile()
    if not profile:
        print("No management profile found. Run extraction first:")
        print("  uv run python -m agents.management_profiler")
        return

    md_path = PROFILES_DIR / "management-profile.md"
    if md_path.exists():
        print(md_path.read_text())
    else:
        print(_profile_to_markdown(profile))


async def run_digest() -> None:
    """Generate profile digest only."""
    profile = load_existing_profile()
    if not profile:
        print("No management profile found. Run extraction first.")
        return
    digest = await generate_digest(profile)
    print(
        f"Generated digest: {digest['total_facts']} facts across {len(digest['dimensions'])} dimensions"
    )
    print(f"Saved to: {PROFILES_DIR / 'management-digest.json'}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Management self-awareness profiler",
        prog="python -m agents.management_profiler",
    )
    parser.add_argument("--show", action="store_true", help="Display current management profile")
    parser.add_argument(
        "--auto", action="store_true", help="Unattended mode: detect changes, update if needed"
    )
    parser.add_argument(
        "--curate", action="store_true", help="Run quality curation on existing profile"
    )
    parser.add_argument(
        "--digest", action="store_true", help="Generate profile digest (per-dimension summaries)"
    )

    args = parser.parse_args()

    if args.digest:
        await run_digest()
    elif args.curate:
        await run_curate()
    elif args.auto:
        await run_auto()
    elif args.show:
        run_show()
    else:
        await run_extraction()


if __name__ == "__main__":
    asyncio.run(main())
