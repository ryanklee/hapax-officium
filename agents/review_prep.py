"""review_prep.py — Performance review evidence aggregation agent.

Consumes 3-12 months of meeting notes, coaching, feedback, and profile facts
for a specific person. Produces evidence aggregation: contributions summary,
growth trajectory, development areas, evidence citations.

CRITICAL SAFETY: Evidence aggregation only. Never generates evaluative language,
ratings, or recommendations per management_safety axiom.

Zero LLM calls for data collection; one LLM call for synthesis.

Usage:
    uv run python -m agents.review_prep --person "Alice" --months 6
    uv run python -m agents.review_prep --person "Alice" --months 12 --save
    uv run python -m agents.review_prep --person "Alice" --json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from shared.config import config, get_model

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)

# ── Frontmatter parsing (same pattern as management_bridge.py) ───────────

_FM_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)", re.DOTALL)


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file.

    Returns (frontmatter_dict, body_text). On any error returns ({}, "").
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        log.warning("review_prep: cannot read %s: %s", path, exc)
        return {}, ""

    match = _FM_RE.match(text)
    if not match:
        return {}, text

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        log.warning("review_prep: bad YAML in %s: %s", path, exc)
        return {}, match.group(2)

    if not isinstance(fm, dict):
        return {}, match.group(2)

    return fm, match.group(2)


# ── Date extraction ──────────────────────────────────────────────────────


def _file_date(fm: dict, path: Path) -> datetime | None:
    """Extract date from frontmatter or filename. Returns UTC datetime or None."""
    date_val = fm.get("date")
    if date_val:
        if isinstance(date_val, datetime):
            if date_val.tzinfo is None:
                return date_val.replace(tzinfo=UTC)
            return date_val
        try:
            return datetime.strptime(str(date_val), "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            pass

    for key in ("created", "created_at", "timestamp"):
        val = fm.get(key)
        if val:
            try:
                dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except (ValueError, TypeError):
                pass

    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if date_match:
        try:
            return datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            pass

    return None


# ── Schemas ──────────────────────────────────────────────────────────────


class ReviewEvidence(BaseModel):
    """Evidence aggregation for performance review preparation."""

    person: str = Field(description="Name of the person being reviewed")
    period_months: int = Field(description="Review period in months")
    contributions: list[str] = Field(
        default_factory=list,
        description="Factual contributions with dates/context",
    )
    growth_trajectory: list[str] = Field(
        default_factory=list,
        description="Observable growth patterns with evidence",
    )
    development_areas: list[str] = Field(
        default_factory=list,
        description="Areas with room for growth, evidence-based",
    )
    evidence_citations: list[str] = Field(
        default_factory=list,
        description="Source citations (file, date, excerpt)",
    )


# ── Data gathering ───────────────────────────────────────────────────────


def _body_excerpt(body: str, max_chars: int = 500) -> str:
    """Return the first max_chars characters of body text, stripped."""
    text = body.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _gather_person_evidence(person: str, months: int = 6) -> dict[str, list[dict]]:
    """Scan DATA_DIR for evidence related to a specific person.

    Checks:
    - Meetings: attendees frontmatter list and body text for person name (case-insensitive)
    - Coaching: person frontmatter field
    - Feedback: person frontmatter field

    Filters by date cutoff (months * 30 days).

    Returns dict with 'meetings', 'coaching', 'feedback' lists of dicts
    containing 'filename', 'frontmatter', 'excerpt'.
    """
    cutoff = datetime.now(UTC) - timedelta(days=months * 30)
    person_lower = person.lower()

    evidence: dict[str, list[dict]] = {
        "meetings": [],
        "coaching": [],
        "feedback": [],
    }

    # Meetings: check attendees list and body text
    meetings_dir = config.data_dir / "meetings"
    if meetings_dir.is_dir():
        for path in sorted(meetings_dir.glob("*.md")):
            fm, body = _parse_frontmatter(path)
            file_dt = _file_date(fm, path)

            if file_dt is not None and file_dt < cutoff:
                continue

            # Check attendees frontmatter
            attendees = fm.get("attendees", [])
            if isinstance(attendees, list):
                attendee_match = any(person_lower in str(a).lower() for a in attendees)
            else:
                attendee_match = False

            # Check body text
            body_match = person_lower in body.lower()

            if attendee_match or body_match:
                evidence["meetings"].append(
                    {
                        "filename": path.name,
                        "frontmatter": fm,
                        "excerpt": _body_excerpt(body),
                    }
                )

    # Coaching: match person frontmatter field
    coaching_dir = config.data_dir / "coaching"
    if coaching_dir.is_dir():
        for path in sorted(coaching_dir.glob("*.md")):
            fm, body = _parse_frontmatter(path)
            file_dt = _file_date(fm, path)

            if file_dt is not None and file_dt < cutoff:
                continue

            fm_person = str(fm.get("person", "")).lower()
            if fm_person == person_lower:
                evidence["coaching"].append(
                    {
                        "filename": path.name,
                        "frontmatter": fm,
                        "excerpt": _body_excerpt(body),
                    }
                )

    # Feedback: match person frontmatter field
    feedback_dir = config.data_dir / "feedback"
    if feedback_dir.is_dir():
        for path in sorted(feedback_dir.glob("*.md")):
            fm, body = _parse_frontmatter(path)
            file_dt = _file_date(fm, path)

            if file_dt is not None and file_dt < cutoff:
                continue

            fm_person = str(fm.get("person", "")).lower()
            if fm_person == person_lower:
                evidence["feedback"].append(
                    {
                        "filename": path.name,
                        "frontmatter": fm,
                        "excerpt": _body_excerpt(body),
                    }
                )

    return evidence


# ── LLM synthesis ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are aggregating evidence for a performance review preparation document.
You consume meeting notes, coaching records, and feedback records for a specific
person and produce a structured evidence summary.

CRITICAL SAFETY CONSTRAINTS:
- STRICTLY factual -- observable contributions, measurable growth, cited evidence
- NEVER generate evaluative language, ratings, scores, or rankings
- NEVER generate feedback language or coaching recommendations
- NEVER suggest what the manager should say or write
- Every claim must cite a specific source (file, date)

OUTPUT GUIDELINES:
- Contributions: factual statements about what the person did, with dates
- Growth trajectory: observable changes in capability or scope over the period
- Development areas: areas where evidence suggests room for growth, cited factually
- Evidence citations: exact source references (filename, date, relevant excerpt)
- If data is sparse, say so honestly -- do not fabricate or extrapolate
- Be precise and concise. No adjectives of quality or judgment.
"""

_agent = Agent(
    get_model("balanced"),
    system_prompt=SYSTEM_PROMPT,
    output_type=ReviewEvidence,
)


def _format_evidence_for_prompt(person: str, months: int, evidence: dict[str, list[dict]]) -> str:
    """Format gathered evidence into a structured prompt for the LLM."""
    lines: list[str] = [
        f"Aggregate review evidence for {person} over the last {months} months.",
        "",
    ]

    for category, items in evidence.items():
        if not items:
            lines.append(f"## {category.title()}\nNo {category} data found.\n")
            continue

        lines.append(f"## {category.title()} ({len(items)} files)")
        for item in items:
            fm = item["frontmatter"]
            title = fm.get("title", item["filename"])
            date = fm.get("date", "unknown date")
            lines.append(f"### {title} ({date})")
            if item["excerpt"]:
                lines.append(item["excerpt"])
            lines.append("")

    total = sum(len(v) for v in evidence.values())
    if total == 0:
        lines.append(
            f"No evidence files found for {person}. Generate a minimal report "
            "noting the evidence gap."
        )

    return "\n".join(lines)


async def generate_review_evidence(
    person: str, months: int = 6, save: bool = False
) -> ReviewEvidence:
    """Gather evidence and generate review evidence summary via LLM.

    Args:
        person: Name of the person to gather evidence for.
        months: Number of months to look back (default 6).
        save: If True, save the report to DATA_DIR/references/.

    Returns:
        ReviewEvidence with contributions, growth, development areas, citations.
    """
    evidence = _gather_person_evidence(person, months)
    prompt = _format_evidence_for_prompt(person, months, evidence)

    try:
        result = await _agent.run(prompt)
        review = result.output
    except Exception as e:
        log.error("LLM review evidence synthesis failed for %s: %s", person, e)
        review = ReviewEvidence(
            person=person,
            period_months=months,
            contributions=[],
            growth_trajectory=[],
            development_areas=[],
            evidence_citations=[f"Error: {e}"],
        )

    if save:
        _save_review(review)

    return review


def _save_review(review: ReviewEvidence) -> Path:
    """Save review evidence as markdown to DATA_DIR/references/."""
    refs_dir = config.data_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    person_slug = review.person.lower().replace(" ", "-")
    filename = f"review-evidence-{person_slug}-{today}.md"
    path = refs_dir / filename

    lines = [
        "---",
        "type: review-evidence",
        f"person: {review.person}",
        f"period_months: {review.period_months}",
        f"date: {today}",
        "---",
        "",
        f"# Review Evidence -- {review.person} ({review.period_months}mo)",
        "",
    ]

    if review.contributions:
        lines.append("## Contributions")
        for c in review.contributions:
            lines.append(f"- {c}")
        lines.append("")

    if review.growth_trajectory:
        lines.append("## Growth Trajectory")
        for g in review.growth_trajectory:
            lines.append(f"- {g}")
        lines.append("")

    if review.development_areas:
        lines.append("## Development Areas")
        for d in review.development_areas:
            lines.append(f"- {d}")
        lines.append("")

    if review.evidence_citations:
        lines.append("## Evidence Citations")
        for e in review.evidence_citations:
            lines.append(f"- {e}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Saved review evidence to %s", path)
    return path


# ── Formatters ───────────────────────────────────────────────────────────


def format_human(review: ReviewEvidence) -> str:
    """Format review evidence for terminal display."""
    lines = [
        f"Review Evidence: {review.person} ({review.period_months}mo)",
        "",
    ]

    if review.contributions:
        lines.append("Contributions:")
        for c in review.contributions:
            lines.append(f"  - {c}")
        lines.append("")

    if review.growth_trajectory:
        lines.append("Growth Trajectory:")
        for g in review.growth_trajectory:
            lines.append(f"  - {g}")
        lines.append("")

    if review.development_areas:
        lines.append("Development Areas:")
        for d in review.development_areas:
            lines.append(f"  - {d}")
        lines.append("")

    if review.evidence_citations:
        lines.append("Evidence Citations:")
        for e in review.evidence_citations:
            lines.append(f"  - {e}")
        lines.append("")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Performance review evidence aggregation",
        prog="python -m agents.review_prep",
    )
    parser.add_argument(
        "--person",
        type=str,
        required=True,
        help="Name of the person to gather evidence for",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="Number of months to look back (default: 6)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save evidence report to DATA_DIR/references/",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable JSON output",
    )
    args = parser.parse_args()

    print(
        f"Gathering review evidence for {args.person} ({args.months}mo)...",
        file=sys.stderr,
    )
    review = await generate_review_evidence(person=args.person, months=args.months, save=args.save)

    if args.json:
        print(review.model_dump_json(indent=2))
    else:
        print(format_human(review))


if __name__ == "__main__":
    asyncio.run(main())
