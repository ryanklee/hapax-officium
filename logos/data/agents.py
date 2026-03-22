"""Static agent registry for logos with structured flag metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentFlag:
    """Structured metadata for a single CLI flag."""

    flag: str
    description: str
    flag_type: str = "bool"  # "bool" | "value" | "positional"
    default: str | None = None
    choices: list[str] | None = None
    metavar: str | None = None


@dataclass
class AgentInfo:
    name: str
    uses_llm: bool
    description: str
    command: str
    module: str = ""
    flags: list[AgentFlag] = field(default_factory=list)


AGENT_REGISTRY: list[AgentInfo] = [
    AgentInfo(
        "management-prep",
        True,
        "1:1 prep, team snapshots, overview",
        "uv run python -m agents.management_prep",
        module="agents.management_prep",
        flags=[
            AgentFlag(
                "--person", "Generate 1:1 prep for a person", flag_type="value", metavar="NAME"
            ),
            AgentFlag("--team-snapshot", "Generate team state snapshot"),
            AgentFlag("--overview", "Generate management overview"),
            AgentFlag("--json", "Machine-readable JSON output"),
            AgentFlag("--save", "Save to vault"),
        ],
    ),
    AgentInfo(
        "meeting-lifecycle",
        True,
        "Meeting prep, transcript processing, weekly review",
        "uv run python -m agents.meeting_lifecycle",
        module="agents.meeting_lifecycle",
        flags=[
            AgentFlag("--prepare", "Auto-generate 1:1 prep for meetings coming due"),
            AgentFlag(
                "--process",
                "Extract structured data from a meeting note",
                flag_type="value",
                metavar="FILE",
            ),
            AgentFlag(
                "--transcript",
                "Ingest a transcript file into a meeting note",
                flag_type="value",
                metavar="FILE",
            ),
            AgentFlag("--weekly-review", "Pre-populate weekly review from vault data"),
        ],
    ),
    AgentInfo(
        "management-briefing",
        True,
        "Morning management briefing",
        "uv run python -m agents.management_briefing",
        module="agents.management_briefing",
        flags=[
            AgentFlag("--save", "Save to profiles/management-briefing.md"),
            AgentFlag("--json", "Machine-readable JSON output"),
            AgentFlag("--notify", "Send notification"),
        ],
    ),
    AgentInfo(
        "management-profiler",
        True,
        "Management self-awareness profiler",
        "uv run python -m agents.management_profiler",
        module="agents.management_profiler",
        flags=[
            AgentFlag("--show", "Display current management profile"),
            AgentFlag("--auto", "Unattended mode: detect changes, update if needed"),
            AgentFlag("--curate", "Run quality curation on existing profile"),
            AgentFlag("--digest", "Generate profile digest (per-dimension summaries)"),
        ],
    ),
    AgentInfo(
        "management-activity",
        False,
        "Management activity tracker (vault-based metrics)",
        "uv run python -m agents.management_activity",
        module="agents.management_activity",
        flags=[
            AgentFlag("--json", "Machine-readable JSON output"),
            AgentFlag(
                "--days", "Rolling window in days", flag_type="value", default="30", metavar="N"
            ),
        ],
    ),
    AgentInfo(
        "demo",
        True,
        "Generate audience-tailored system demos",
        "uv run python -m agents.demo",
        module="agents.demo",
        flags=[
            AgentFlag(
                "request", "Natural language request", flag_type="positional", metavar="REQUEST"
            ),
            AgentFlag(
                "--audience",
                "Override audience archetype",
                flag_type="value",
                metavar="ARCHETYPE",
                choices=["family", "technical-peer", "leadership", "team-member"],
            ),
            AgentFlag(
                "--format",
                "Output format",
                flag_type="value",
                default="slides",
                choices=["slides", "video", "markdown-only"],
            ),
            AgentFlag("--json", "Print script JSON instead of generating demo"),
        ],
    ),
    AgentInfo(
        "system-check",
        False,
        "Management system health checks",
        "uv run python -m agents.system_check",
        module="agents.system_check",
        flags=[
            AgentFlag("--json", "Output machine-readable JSON"),
        ],
    ),
    AgentInfo(
        "ingest",
        False,
        "Document ingestion pipeline",
        "uv run python -m agents.ingest",
        module="agents.ingest",
        flags=[
            AgentFlag("file", "File to ingest", flag_type="positional", metavar="FILE"),
            AgentFlag("--type", "Document type override", flag_type="value", metavar="TYPE"),
            AgentFlag("--watch", "Watch directory for new files"),
        ],
    ),
    AgentInfo(
        "status-update",
        True,
        "Upward-facing status reports",
        "uv run python -m agents.status_update",
        module="agents.status_update",
        flags=[
            AgentFlag("--daily", "Generate daily status update"),
            AgentFlag("--save", "Save to vault"),
        ],
    ),
    AgentInfo(
        "review-prep",
        True,
        "Performance review evidence aggregation",
        "uv run python -m agents.review_prep",
        module="agents.review_prep",
        flags=[
            AgentFlag(
                "--person", "Team member to prepare review for", flag_type="value", metavar="NAME"
            ),
            AgentFlag(
                "--months", "Lookback period in months", flag_type="value", default="6", metavar="N"
            ),
            AgentFlag("--save", "Save to vault"),
        ],
    ),
]


def get_agent_registry() -> list[AgentInfo]:
    return AGENT_REGISTRY
