"""Concrete reactive rules mapping filesystem changes to action cascades.

Twelve rules that wire DATA_DIR filesystem events to existing agent and collector
functions. Action handlers use lazy imports to avoid circular dependencies and
heavy import costs at module load time.

Self-trigger prevention: handlers that write to DATA_DIR accept an optional
ignore_fn callable. When provided, they call ignore_fn(path) before each write
so the watcher suppresses the resulting filesystem event.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from logos.engine.models import Action, ChangeEvent
from logos.engine.rules import Rule, RuleRegistry

# Type alias for the watcher's ignore function
IgnoreFn = Callable[[Path], None] | None


# ---------------------------------------------------------------------------
# Action handlers (lazy imports inside each function)
# ---------------------------------------------------------------------------


async def _refresh_cache() -> str:
    from logos.api.cache import cache

    await cache.refresh()
    return "cache refreshed"


async def _ingest_document(path: Path, ignore_fn: IgnoreFn = None) -> str:
    """Classify and route an inbox file, then move original to processed/.

    Transcript destinations (meetings/) are NOT suppressed via ignore_fn
    so that meeting_cascade can fire and extract meeting data. Other
    destinations are suppressed to avoid redundant cache refreshes.
    """
    import shutil

    from agents.ingest import DocumentType, classify_document, process_document

    doc_type = classify_document(path)
    result = await process_document(path, doc_type)

    # Suppress non-transcript destinations (transcripts need meeting_cascade)
    if (
        ignore_fn
        and result.destination
        and result.doc_type not in (DocumentType.TRANSCRIPT, DocumentType.MEETING)
    ):
        ignore_fn(result.destination)

    # Move original to processed/ (mirroring watch daemon behavior)
    if result.success and result.destination:
        from shared.config import config

        processed = config.data_dir / "processed"
        processed.mkdir(exist_ok=True)
        try:
            dest = processed / path.name
            if dest.exists():
                dest = processed / f"{path.stem}_{int(path.stat().st_mtime)}{path.suffix}"
            shutil.move(str(path), str(dest))
        except OSError:
            pass  # best-effort cleanup

    doc_label = result.doc_type.value if result.doc_type else "unknown"
    return f"ingested as {doc_label}"


async def _extract_meeting(path: Path, ignore_fn: IgnoreFn = None) -> str:
    from agents.meeting_lifecycle import process_meeting, route_extractions

    extraction = await process_meeting(path)
    created = route_extractions(extraction, path)
    if ignore_fn:
        for p in created:
            ignore_fn(p)
    return f"extracted {len(created)} items"


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------


def _rule_inbox_ingest(ignore_fn: IgnoreFn = None) -> Rule:
    """Trigger on file CREATED in inbox/."""
    return Rule(
        name="inbox_ingest",
        description="Ingest new files dropped into inbox/",
        trigger_filter=lambda e: e.subdirectory == "inbox" and e.event_type == "created",
        produce=lambda e: [
            Action(
                name="ingest_document",
                handler=_ingest_document,
                args={"path": e.path, "ignore_fn": ignore_fn},
                phase=0,
                priority=0,
            ),
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=1,
                priority=10,
                depends_on=["ingest_document"],
            ),
        ],
    )


def _rule_meeting_cascade(ignore_fn: IgnoreFn = None) -> Rule:
    """Trigger on file CREATED or MODIFIED in meetings/.

    Skips generated prep files (prep-*.md) to avoid re-extraction loops.
    Phase 0: refresh cache. Phase 1: extract meeting data (LLM).
    """

    def _filter(e: ChangeEvent) -> bool:
        if e.subdirectory != "meetings":
            return False
        if e.event_type not in ("created", "modified"):
            return False
        # Skip generated prep files to prevent extraction loops
        return not e.path.name.startswith("prep-")

    def _produce(e: ChangeEvent) -> list[Action]:
        return [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
            Action(
                name="extract_meeting",
                handler=_extract_meeting,
                args={"path": e.path, "ignore_fn": ignore_fn},
                phase=1,
                priority=0,
                depends_on=["refresh_cache"],
            ),
        ]

    return Rule(
        name="meeting_cascade",
        description="Refresh cache and extract meeting data on meeting note changes",
        trigger_filter=_filter,
        produce=_produce,
    )


def _rule_person_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in people/.

    Only refresh_cache needed — cache.refresh() already recomputes
    nudges and team_health internally.
    """
    return Rule(
        name="person_changed",
        description="Refresh cache on person changes (includes nudges + team health)",
        trigger_filter=lambda e: (
            e.subdirectory == "people" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
        ],
    )


def _rule_coaching_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in coaching/."""
    return Rule(
        name="coaching_changed",
        description="Refresh cache on coaching changes (includes nudges)",
        trigger_filter=lambda e: (
            e.subdirectory == "coaching" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
        ],
    )


def _rule_feedback_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in feedback/."""
    return Rule(
        name="feedback_changed",
        description="Refresh cache on feedback changes (includes nudges)",
        trigger_filter=lambda e: (
            e.subdirectory == "feedback" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
        ],
    )


def _rule_decision_logged() -> Rule:
    """Trigger on file CREATED in decisions/."""
    return Rule(
        name="decision_logged",
        description="Refresh cache when a decision is logged",
        trigger_filter=lambda e: e.subdirectory == "decisions" and e.event_type == "created",
        produce=lambda e: [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
        ],
    )


def _rule_okr_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in okrs/."""
    return Rule(
        name="okr_changed",
        description="Refresh cache on OKR changes",
        trigger_filter=lambda e: (
            e.subdirectory == "okrs" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)
        ],
    )


def _rule_smart_goal_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in goals/."""
    return Rule(
        name="smart_goal_changed",
        description="Refresh cache on SMART goal changes",
        trigger_filter=lambda e: (
            e.subdirectory == "goals" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)
        ],
    )


def _rule_incident_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in incidents/."""
    return Rule(
        name="incident_changed",
        description="Refresh cache on incident changes",
        trigger_filter=lambda e: (
            e.subdirectory == "incidents" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)
        ],
    )


def _rule_postmortem_action_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in postmortem-actions/."""
    return Rule(
        name="postmortem_action_changed",
        description="Refresh cache on postmortem action changes",
        trigger_filter=lambda e: (
            e.subdirectory == "postmortem-actions" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)
        ],
    )


def _rule_review_cycle_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in review-cycles/."""
    return Rule(
        name="review_cycle_changed",
        description="Refresh cache on review cycle changes",
        trigger_filter=lambda e: (
            e.subdirectory == "review-cycles" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)
        ],
    )


def _rule_status_report_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in status-reports/."""
    return Rule(
        name="status_report_changed",
        description="Refresh cache on status report changes",
        trigger_filter=lambda e: (
            e.subdirectory == "status-reports" and e.event_type in ("created", "modified")
        ),
        produce=lambda e: [
            Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)
        ],
    )


# ---------------------------------------------------------------------------
# Registry builder
# ---------------------------------------------------------------------------


def build_default_rules(
    ignore_fn: IgnoreFn = None,
) -> RuleRegistry:
    """Create a RuleRegistry with all 12 default reactive rules.

    Args:
        ignore_fn: Optional callable (typically DataDirWatcher.ignore) for
            self-trigger prevention. Passed through to write-producing handlers.
    """
    registry = RuleRegistry()
    registry.register(_rule_inbox_ingest(ignore_fn))
    registry.register(_rule_meeting_cascade(ignore_fn))
    registry.register(_rule_person_changed())
    registry.register(_rule_coaching_changed())
    registry.register(_rule_feedback_changed())
    registry.register(_rule_decision_logged())
    registry.register(_rule_okr_changed())
    registry.register(_rule_smart_goal_changed())
    registry.register(_rule_incident_changed())
    registry.register(_rule_postmortem_action_changed())
    registry.register(_rule_review_cycle_changed())
    registry.register(_rule_status_report_changed())
    return registry
