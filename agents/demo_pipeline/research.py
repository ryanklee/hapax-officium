"""Subject matter research — gathers audience-filtered context for demo planning."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Callable

    from agents.demo_models import AudienceDossier

log = logging.getLogger(__name__)

# Path to canonical workflow definitions
WORKFLOW_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "workflow-registry.yaml"
)

# Audience -> which sources to gather
AUDIENCE_SOURCES: dict[str, list[str]] = {
    "family": [
        "major_components",
        "component_registry",
        "health_summary",
        "profile_facts_rich",
        "briefing_stats",
        "operator_philosophy",
        "domain_literature",
        "workflow_patterns",
    ],
    "team-member": [
        "major_components",
        "component_registry",
        "health_summary",
        "system_docs_summary",
        "profile_facts_rich",
        "briefing_stats",
        "domain_literature",
        "workflow_patterns",
    ],
    "leadership": [
        "major_components",
        "component_registry_rich",
        "health_summary",
        "langfuse_metrics",
        "system_docs",
        "profile_facts_rich",
        "operator_philosophy",
        "briefing_stats",
        "web_research",
        "architecture_rag",
        "design_plans",
        "domain_literature",
        "audit_findings",
        "workflow_patterns",
    ],
    "technical-peer": [
        "major_components",
        "component_registry_rich",
        "health_summary",
        "langfuse_metrics",
        "qdrant_stats",
        "system_docs",
        "profile_facts_rich",
        "operator_philosophy",
        "briefing_stats",
        "web_research",
        "architecture_rag",
        "design_plans",
        "domain_literature",
        "audit_findings",
        "workflow_patterns",
    ],
}

# Path to canonical system docs (local project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SYSTEM_CLAUDE_MD = _PROJECT_ROOT / "CLAUDE.md"


def _gather_component_registry() -> str:
    """Read component-registry.yaml and format component names + descriptions."""
    try:
        from shared.config import PROFILES_DIR

        registry_path = PROFILES_DIR / "component-registry.yaml"
        if not registry_path.is_file():
            log.debug("component-registry.yaml not found at %s", registry_path)
            return ""
        data = yaml.safe_load(registry_path.read_text())
        components = data.get("components", {})
        if not components:
            return ""
        lines = []
        for name, info in components.items():
            role = info.get("role", "")
            current = info.get("current", "")
            lines.append(f"- **{name}**: {role} (current: {current})")
        return "\n".join(lines)
    except Exception:
        log.exception("Failed to gather component registry")
        return ""


async def _gather_health_summary() -> str:
    """Run health checks and format score + any failures."""
    try:
        from agents.system_check import run_checks

        results = await run_checks()
        lines = []
        for r in results:
            status = "PASS" if r.ok else "FAIL"
            lines.append(f"  {r.name}: {status} — {r.message}")
        return "\n".join(lines)
    except Exception as exc:
        return f"(health check unavailable: {exc})"


def _gather_langfuse_metrics() -> str:
    """Query Langfuse for model usage and cost metrics.

    Delegates to shared.ops_live.query_langfuse_cost().
    """
    try:
        from shared.ops_live import query_langfuse_cost

        result = query_langfuse_cost(days=7)
        if "not available" in result.lower() or "no llm generations" in result.lower():
            return ""
        return result
    except Exception:
        log.exception("Failed to gather Langfuse metrics")
        return ""


def _gather_qdrant_stats() -> str:
    """List Qdrant collections with point counts.

    Delegates to shared.ops_live.query_qdrant_stats().
    """
    try:
        from shared.ops_live import query_qdrant_stats

        result = query_qdrant_stats()
        if "not available" in result.lower() or "no qdrant" in result.lower():
            return ""
        return result
    except Exception:
        log.exception("Failed to gather Qdrant stats")
        return ""


def _gather_system_docs(summary: bool = False) -> str:
    """Read CLAUDE.md as system documentation."""
    try:
        doc_path = _SYSTEM_CLAUDE_MD
        if not doc_path.is_file():
            log.debug("CLAUDE.md not found at %s", doc_path)
            return ""
        content = doc_path.read_text()
        if summary:
            return content[:2000]
        return content
    except Exception:
        log.exception("Failed to gather system docs")
        return ""


def _gather_profile_facts(scope: str) -> str:
    """Search profile-facts Qdrant collection for facts relevant to scope.

    Delegates to shared.knowledge_search.search_profile().
    """
    try:
        from shared.knowledge_search import search_profile

        result = search_profile(f"profile facts about {scope}", limit=10)
        if "no profile facts" in result.lower():
            return ""
        return result
    except Exception:
        log.exception("Failed to gather profile facts")
        return ""


def _gather_web_research(scope: str, audience: str) -> str:
    """Search the web for industry context relevant to the demo scope."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        log.debug("No TAVILY_API_KEY set, skipping web research")
        return ""
    try:
        import httpx

        query = f"{scope} autonomous agent system architecture trends"
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": 5,
                "search_depth": "basic",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return ""
        lines = []
        for r in results:
            title = r.get("title", "")
            content = r.get("content", "")[:200]
            lines.append(f"- **{title}**: {content}")
        return "\n".join(lines)
    except Exception:
        log.exception("Failed to gather web research")
        return ""


def _gather_component_registry_rich() -> str:
    """Read component-registry.yaml with full details: role, current, constraints, eval_notes."""
    try:
        from shared.config import PROFILES_DIR

        registry_path = PROFILES_DIR / "component-registry.yaml"
        if not registry_path.is_file():
            log.debug("component-registry.yaml not found at %s", registry_path)
            return ""
        data = yaml.safe_load(registry_path.read_text())
        components = data.get("components", {})
        if not components:
            return ""
        lines = []
        for name, info in components.items():
            role = info.get("role", "")
            current = info.get("current", "")
            lines.append(f"### {name}")
            lines.append(f"- **Role**: {role}")
            lines.append(f"- **Current**: {current}")
            constraints = info.get("constraints", "")
            if constraints:
                lines.append(f"- **Constraints**: {constraints}")
            eval_notes = info.get("eval_notes", "")
            if eval_notes:
                lines.append(f"- **Eval notes**: {eval_notes}")
        return "\n".join(lines)
    except Exception:
        log.exception("Failed to gather rich component registry")
        return ""


def _gather_briefing_stats() -> str:
    """Read briefing.md and return operational stats section."""
    try:
        from shared.config import PROFILES_DIR

        briefing_path = PROFILES_DIR / "briefing.md"
        if not briefing_path.is_file():
            log.debug("briefing.md not found at %s", briefing_path)
            return ""
        content = briefing_path.read_text()
        if not content.strip():
            return ""
        return content.strip()
    except Exception:
        log.exception("Failed to gather briefing stats")
        return ""


def _gather_profile_facts_rich(scope: str, audience: str = "") -> str:
    """Search profile-facts with audience-aware queries, dedup by (dimension, key), up to 30 facts."""
    try:
        from shared.config import embed, get_qdrant

        client = get_qdrant()
        # Audience-aware queries — family audiences need personal context,
        # technical audiences need workflow/design facts
        if audience == "family":
            queries = [
                "management practice patterns what this system helps with",
                "team leadership goals decision support workflow automation",
                "communication style identity neurocognitive profile energy",
                f"what the {scope} does daily life practical impact",
            ]
        else:
            queries = [
                f"profile facts about {scope}",
                "system design philosophy axioms goals motivation",
                "operator background expertise experience",
            ]
        seen: set[tuple[str, str]] = set()
        facts: list[str] = []
        for q in queries:
            vector = embed(q)
            results = client.query_points(
                collection_name="profile-facts",
                query=vector,
                limit=15,
            )
            for hit in results.points:
                payload = hit.payload or {}
                dim = payload.get("dimension", "")
                key = payload.get("key", "")
                dedup_key = (dim, key)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                fact = payload.get("fact", payload.get("text", ""))
                if fact:
                    dim_label = f"[{dim}] " if dim else ""
                    facts.append(f"- {dim_label}{fact}")
                if len(facts) >= 30:
                    break
            if len(facts) >= 30:
                break
        return "\n".join(facts)
    except Exception:
        log.exception("Failed to gather rich profile facts")
        return ""


def _gather_operator_philosophy() -> str:
    """Load operator.json and format axioms, goals, and key design patterns."""
    try:
        from shared.operator import get_operator

        data = get_operator()
        if not data:
            return ""
        lines = []
        axioms = data.get("axioms", {})
        if axioms:
            lines.append("### Axioms")
            for name, value in axioms.items():
                lines.append(f"- **{name}**: {value}")
        goals = data.get("goals", {})
        primary = goals.get("primary", [])
        secondary = goals.get("secondary", [])
        if primary or secondary:
            lines.append("\n### Goals")
            for g in primary:
                if isinstance(g, dict):
                    lines.append(f"- **{g.get('name', '')}**: {g.get('description', '')}")
                else:
                    lines.append(f"- {g}")
            for g in secondary:
                if isinstance(g, dict):
                    lines.append(f"- {g.get('name', '')}: {g.get('description', '')}")
                else:
                    lines.append(f"- {g}")
        patterns = data.get("patterns", {})
        if patterns:
            lines.append("\n### Key Patterns")
            for category, items in patterns.items():
                cat_label = category.replace("_", " ").title()
                lines.append(f"**{cat_label}**:")
                for item in items[:3]:  # Top 3 per category
                    lines.append(f"- {item}")
        return "\n".join(lines) if lines else ""
    except Exception:
        log.exception("Failed to gather operator philosophy")
        return ""


def _gather_architecture_rag(scope: str, limit: int = 10) -> str:
    """Semantic search over architecture docs in Qdrant 'documents' collection.

    Filters by source path containing 'hapax-officium' to isolate architecture docs
    from personal data in the same collection.
    """
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchText

        from shared.config import embed, get_qdrant

        client = get_qdrant()
        queries = [
            f"{scope} system architecture design",
            f"{scope} design rationale trade-offs decisions",
            f"{scope} agent orchestration tiered architecture",
        ]
        hapax_filter = Filter(
            must=[FieldCondition(key="source", match=MatchText(text="hapax-officium"))]
        )
        seen_ids: set[str] = set()
        chunks: list[str] = []
        for q in queries:
            vector = embed(q)
            results = client.query_points(
                collection_name="documents",
                query=vector,
                query_filter=hapax_filter,
                limit=5,
            )
            for hit in results.points:
                pid = str(hit.id)
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                payload = hit.payload or {}
                source = payload.get("source", "")
                filename = Path(source).name if source else "unknown"
                text = payload.get("text", "")
                if text:
                    chunks.append(f"**[{filename}]** {text}")
                if len(chunks) >= limit:
                    break
            if len(chunks) >= limit:
                break
        return "\n\n".join(chunks) if chunks else ""
    except Exception:
        log.exception("Failed to gather architecture RAG")
        return ""


def _gather_design_plans(scope: str, max_chars: int = 8000) -> str:
    """Read relevant design plans from docs/plans/.

    Scores filenames by keyword overlap with scope, sorts by relevance
    then recency (date-prefixed filenames).
    """
    try:
        plans_dir = _PROJECT_ROOT / "docs" / "plans"
        if not plans_dir.is_dir():
            log.debug("Plans directory not found at %s", plans_dir)
            return ""
        plan_files = sorted(plans_dir.glob("*.md"))
        if not plan_files:
            return ""

        # Score each file by keyword overlap with scope
        scope_words = set(re.findall(r"\w+", scope.lower()))
        scored: list[tuple[int, str, Path]] = []
        for pf in plan_files:
            name_words = set(re.findall(r"\w+", pf.stem.lower()))
            overlap = len(scope_words & name_words)
            # Date prefix for recency (higher = more recent)
            date_str = pf.stem[:10] if len(pf.stem) >= 10 else ""
            scored.append((overlap, date_str, pf))

        # Sort by overlap desc, then date desc
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

        # Read top 5 matching plans
        lines: list[str] = []
        total_chars = 0
        for _overlap, _date, pf in scored[:5]:
            try:
                content = pf.read_text()
                remaining = max_chars - total_chars
                if remaining <= 0:
                    break
                if len(content) > remaining:
                    content = content[:remaining] + "\n...(truncated)"
                lines.append(f"### {pf.name}\n\n{content}")
                total_chars += len(content)
            except OSError:
                continue
        return "\n\n".join(lines)
    except Exception:
        log.exception("Failed to gather design plans")
        return ""


def _gather_audit_findings() -> str:
    """Read the holistic audit synthesis."""
    try:
        audit_path = _PROJECT_ROOT / "docs" / "audit" / "v2" / "10-holistic.md"
        if not audit_path.is_file():
            log.debug("Holistic audit not found at %s", audit_path)
            return ""
        content = audit_path.read_text()
        # Return first 4000 chars (executive summary + key findings)
        return content[:4000] if len(content) > 4000 else content
    except Exception:
        log.exception("Failed to gather audit findings")
        return ""


def _gather_major_components() -> str:
    """Extract major system components from CLAUDE.md that MUST appear in demos.

    Reads the canonical system docs and identifies components with dedicated
    sections, ensuring the demo prompt always reflects the current architecture.
    """
    try:
        doc_path = _SYSTEM_CLAUDE_MD
        if not doc_path.is_file():
            return ""
        content = doc_path.read_text()

        # Extract key sections that represent major components
        components: list[str] = []

        # Vaults section
        if "## Vaults" in content or "vault" in content.lower():
            components.append(
                "- **Obsidian Vault**: Knowledge layer for management data. "
                "Agents write briefings/prep docs via vault_writer.py. "
                "Contains: person notes, meetings, projects, decisions, daily/weekly notes, 1:1 prep."
            )

        # Multi-Channel Access
        if "## Multi-Channel Access" in content:
            components.append(
                "- **Web Dashboard** (cockpit-web): Management command center with "
                "action items, agents grid, team health sidebar, briefing panel, and goals tracking."
            )

        # Tier 2 Agents
        if "## Tier 2 Agents" in content:
            # Count implemented agents
            import re

            agent_table = content[content.find("### Implemented") : content.find("### Planned")]
            agent_count = len(re.findall(r"^\| `\w+`", agent_table, re.MULTILINE))
            components.append(
                f"- **Tier 2 Agents**: {agent_count} implemented Pydantic AI agents "
                "(management_prep, meeting_lifecycle, management_briefing, management_profiler, "
                "management_activity, demo, demo_eval, system_check)."
            )

        # Tier 3 Services
        if "## Tier 3 Services" in content:
            components.append(
                "- **Scheduled Services**: systemd timers for system checks (15min), "
                "daily briefing (07:00), meeting prep (06:30), profile updates (12h)."
            )

        # Self-demo capability
        if "demo" in content.lower() and "demo_eval" in content:
            components.append(
                "- **Self-Demo System** (demo + demo_eval agents): The system can generate "
                "audience-tailored demos OF ITSELF — Playwright screenshots, D2 diagrams, "
                "voice-cloned narration, screencasts, HTML player, MP4 video. "
                "LLM-as-judge evaluation with self-healing loop. "
                "Audience personas + dossiers calibrate tone, vocabulary, forbidden terms. "
                "This is a unique capability — the system explains and presents itself."
            )

        if not components:
            return ""
        return (
            "These are the MAJOR system components that should be featured in any full-system demo:\n\n"
            + "\n".join(components)
        )
    except Exception:
        log.exception("Failed to gather major components")
        return ""


def _gather_domain_literature(scope: str, max_chars: int = 6000) -> str:
    """Load pre-curated domain literature from the corpus directory.

    Matches files by keyword overlap with scope. Always includes foundational
    files (cognitive load, agent architecture). Returns up to ~6K chars across 4 files.
    """
    try:
        corpus_dir = Path(__file__).parent / "domain_corpus"
        if not corpus_dir.is_dir():
            log.debug("Domain corpus not found at %s", corpus_dir)
            return ""
        md_files = list(corpus_dir.glob("*.md"))
        if not md_files:
            return ""

        # Foundational files always included
        foundational_stems = {"cognitive-load-theory", "autonomous-agent-architectures"}

        # Score by keyword overlap
        scope_words = set(re.findall(r"\w+", scope.lower()))
        scored: list[tuple[int, bool, Path]] = []
        for mf in md_files:
            is_foundational = mf.stem in foundational_stems
            # Parse YAML frontmatter for keywords
            try:
                text = mf.read_text()
                fm_keywords: list[str] = []
                if text.startswith("---"):
                    end = text.find("---", 3)
                    if end > 0:
                        fm = yaml.safe_load(text[3:end])
                        if isinstance(fm, dict):
                            fm_keywords = fm.get("keywords", [])
                            fm_keywords += fm.get("relevance", [])
            except Exception:
                fm_keywords = []

            name_words = set(re.findall(r"\w+", mf.stem.lower()))
            kw_words = set(w.lower() for kw in fm_keywords for w in re.findall(r"\w+", kw))
            overlap = len(scope_words & (name_words | kw_words))
            scored.append((overlap, is_foundational, mf))

        # Sort: foundational first, then by overlap desc
        scored.sort(key=lambda x: (x[1], x[0]), reverse=True)

        lines: list[str] = []
        total_chars = 0
        for _overlap, _is_foundational, mf in scored[:4]:
            try:
                content = mf.read_text()
                # Strip frontmatter for output
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end > 0:
                        content = content[end + 3 :].strip()
                remaining = max_chars - total_chars
                if remaining <= 0:
                    break
                if len(content) > remaining:
                    content = content[:remaining] + "\n...(truncated)"
                lines.append(f"### {mf.stem.replace('-', ' ').title()}\n\n{content}")
                total_chars += len(content)
            except OSError:
                continue
        return "\n\n".join(lines)
    except Exception:
        log.exception("Failed to gather domain literature")
        return ""


def _gather_workflow_patterns(scope: str) -> str:
    """Load canonical workflow definitions from workflow-registry.yaml.

    For broad scopes (full, entire, system, everything, all), returns ALL workflows.
    For narrow scopes, filters by matching scope keywords against workflow name, label,
    and component names.

    Returns formatted text with each workflow's label, trigger, and numbered steps.
    Returns empty string if file not found or on errors.
    """
    try:
        if not WORKFLOW_REGISTRY_PATH.is_file():
            log.debug("workflow-registry.yaml not found at %s", WORKFLOW_REGISTRY_PATH)
            return ""
        data = yaml.safe_load(WORKFLOW_REGISTRY_PATH.read_text())
        workflows = data.get("workflows", {})
        if not workflows:
            return ""

        # Determine if scope is broad
        broad_keywords = {"full", "entire", "system", "everything", "all"}
        scope_words = set(re.findall(r"\w+", scope.lower()))
        is_broad = bool(scope_words & broad_keywords)

        selected: list[tuple[str, dict]] = []
        if is_broad:
            selected = list(workflows.items())
        else:
            for wf_id, wf in workflows.items():
                # Match against workflow id, label, and component names
                match_text = " ".join(
                    [
                        wf_id.replace("-", " "),
                        wf.get("label", "").lower(),
                        " ".join(c.replace("_", " ") for c in wf.get("components", [])),
                    ]
                )
                match_words = set(re.findall(r"\w+", match_text))
                if scope_words & match_words:
                    selected.append((wf_id, wf))

        if not selected:
            return ""

        lines: list[str] = []
        for wf_id, wf in selected:
            label = wf.get("label", wf_id)
            trigger = wf.get("trigger", "unknown")
            steps = wf.get("steps", [])
            lines.append(f"### {label}")
            lines.append(f"**Trigger**: {trigger}")
            for i, step in enumerate(steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")  # blank line between workflows

        return "\n".join(lines).strip()
    except Exception:
        log.exception("Failed to gather workflow patterns")
        return ""


def _gather_profile_digest_summary(scope: str) -> str:
    """Load operator-digest.json via ProfileStore and return overall + scope-relevant summaries."""
    try:
        from shared.profile_store import ProfileStore

        store = ProfileStore()
        digest = store.get_digest()
        if not digest:
            return ""
        lines = []
        overall = digest.get("overall_summary", "")
        if overall:
            lines.append(overall)
        dimensions = digest.get("dimensions", {})
        scope_lower = scope.lower()
        for dim_name, dim_data in dimensions.items():
            summary = dim_data.get("summary", "")
            if summary and scope_lower in dim_name.lower():
                lines.append(f"\n**{dim_name}**: {summary}")
        return "\n".join(lines) if lines else ""
    except Exception:
        log.exception("Failed to gather profile digest summary")
        return ""


def _format_audience_dossier(dossier: AudienceDossier) -> str:
    """Format dossier as a ## Audience Profile section."""

    lines = [f"**Name**: {dossier.name}"]
    if dossier.context:
        lines.append(f"**Context**: {dossier.context}")
    cal = dossier.calibration or {}
    emphasize = cal.get("emphasize", [])
    skip = cal.get("skip", [])
    if emphasize:
        lines.append(f"**Emphasize**: {', '.join(emphasize)}")
    if skip:
        lines.append(f"**Skip**: {', '.join(skip)}")
    return "\n".join(lines)


# Map source names to their gather functions.
# Functions that need arguments are wrapped in the main function below.
_SYNC_SOURCES: dict[str, Callable[..., str]] = {
    "component_registry": _gather_component_registry,
    "langfuse_metrics": _gather_langfuse_metrics,
    "qdrant_stats": _gather_qdrant_stats,
}

# Section headers for each source
_SECTION_HEADERS: dict[str, str] = {
    "major_components": "## Major System Components (MUST feature in full-system demos)",
    "component_registry": "## System Components",
    "component_registry_rich": "## System Components (Detailed)",
    "health_summary": "## Current Health",
    "langfuse_metrics": "## LLM Usage Metrics",
    "qdrant_stats": "## Vector Database",
    "system_docs": "## System Documentation",
    "system_docs_summary": "## System Documentation (Summary)",
    "profile_facts": "## Operator Profile",
    "profile_facts_rich": "## Operator Profile (Detailed)",
    "web_research": "## Industry Context",
    "briefing_stats": "## Operational Briefing",
    "operator_philosophy": "## Design Philosophy",
    "profile_digest": "## Profile Digest",
    "architecture_rag": "## Architecture Documentation (RAG)",
    "design_plans": "## Design Plans",
    "audit_findings": "## System Audit Findings",
    "domain_literature": "## Domain Literature",
    "workflow_patterns": "## System Workflows (Canonical Definitions)",
}


async def gather_research(
    scope: str,
    audience: str,
    on_progress: Callable[[str], None] | None = None,
    enrichment_actions: list[str] | None = None,
    audience_dossier: AudienceDossier | None = None,
) -> str:
    """Gather audience-filtered research context for demo planning.

    Args:
        scope: What the demo is about (e.g. "agent architecture", "health monitoring").
        audience: Audience archetype key from AUDIENCE_SOURCES.
        on_progress: Optional callback for progress updates.
        enrichment_actions: Extra source keys appended to the audience's default list.
            Used by sufficiency gate for autonomous remediation.
        audience_dossier: If provided, formatted and appended as ## Audience Profile section.

    Returns:
        Formatted research document with section headers.
    """
    sources = list(AUDIENCE_SOURCES.get(audience, AUDIENCE_SOURCES["family"]))
    if enrichment_actions:
        for action in enrichment_actions:
            if action not in sources:
                sources.append(action)

    sections: list[str] = []
    succeeded: list[str] = []
    failed: list[str] = []

    for source_name in sources:
        if on_progress:
            on_progress(f"Gathering {source_name}...")

        content = ""
        try:
            if source_name == "major_components":
                content = _gather_major_components()
            elif source_name == "component_registry":
                content = _gather_component_registry()
            elif source_name == "component_registry_rich":
                content = _gather_component_registry_rich()
            elif source_name == "health_summary":
                content = await _gather_health_summary()
            elif source_name == "langfuse_metrics":
                content = _gather_langfuse_metrics()
            elif source_name == "qdrant_stats":
                content = _gather_qdrant_stats()
            elif source_name == "system_docs":
                content = _gather_system_docs(summary=False)
            elif source_name == "system_docs_summary":
                content = _gather_system_docs(summary=True)
            elif source_name == "profile_facts":
                content = _gather_profile_facts(scope)
            elif source_name == "profile_facts_rich":
                content = _gather_profile_facts_rich(scope, audience)
            elif source_name == "web_research":
                content = _gather_web_research(scope, audience)
            elif source_name == "briefing_stats":
                content = _gather_briefing_stats()
            elif source_name == "operator_philosophy":
                content = _gather_operator_philosophy()
            elif source_name == "profile_digest":
                content = _gather_profile_digest_summary(scope)
            elif source_name == "architecture_rag":
                content = _gather_architecture_rag(scope)
            elif source_name == "design_plans":
                content = _gather_design_plans(scope)
            elif source_name == "audit_findings":
                content = _gather_audit_findings()
            elif source_name == "domain_literature":
                content = _gather_domain_literature(scope)
            elif source_name == "workflow_patterns":
                content = _gather_workflow_patterns(scope)
            else:
                log.warning("Unknown source: %s", source_name)
                continue
        except Exception:
            log.exception("Source %s failed unexpectedly", source_name)
            content = ""

        if content:
            header = _SECTION_HEADERS.get(source_name, f"## {source_name}")
            sections.append(f"{header}\n\n{content}")
            succeeded.append(source_name)
        else:
            failed.append(source_name)

    # Append audience dossier if provided
    if audience_dossier:
        dossier_content = _format_audience_dossier(audience_dossier)
        if dossier_content:
            sections.append(f"## Audience Profile\n\n{dossier_content}")

    # Aggregate research quality signal
    total = len(succeeded) + len(failed)
    if failed:
        log.warning(
            "Research gathered %d/%d sources. Failed: %s",
            len(succeeded),
            total,
            ", ".join(failed),
        )
        if on_progress:
            on_progress(
                f"Research: {len(succeeded)}/{total} sources gathered. Missing: {', '.join(failed)}"
            )
    else:
        if on_progress:
            on_progress(f"Research complete ({len(succeeded)}/{total} sources).")

    return "\n\n".join(sections)
