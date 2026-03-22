"""Tests for logos.engine.reactive_rules — 12 concrete reactive rules."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from logos.engine.models import ChangeEvent
from logos.engine.reactive_rules import build_default_rules


def _make_event(
    subdirectory: str = "people",
    event_type: str = "modified",
    path: str | None = None,
) -> ChangeEvent:
    if path is None:
        path = f"data/{subdirectory}/test.md"
    return ChangeEvent(
        path=Path(path),
        subdirectory=subdirectory,
        event_type=event_type,
        doc_type=None,
        timestamp=datetime(2026, 3, 9, 12, 0),
    )


def _get_rule(name: str):
    registry = build_default_rules()
    for rule in registry.rules:
        if rule.name == name:
            return rule
    raise ValueError(f"Rule {name!r} not found")


# --- build_default_rules ---


def test_build_default_rules_count():
    registry = build_default_rules()
    assert len(registry.rules) == 12


def test_build_default_rules_names():
    registry = build_default_rules()
    names = {r.name for r in registry.rules}
    assert names == {
        "inbox_ingest",
        "meeting_cascade",
        "person_changed",
        "coaching_changed",
        "feedback_changed",
        "decision_logged",
        "okr_changed",
        "smart_goal_changed",
        "incident_changed",
        "postmortem_action_changed",
        "review_cycle_changed",
        "status_report_changed",
    }


# --- inbox_ingest ---


def test_inbox_ingest_matches_created_in_inbox():
    rule = _get_rule("inbox_ingest")
    event = _make_event(subdirectory="inbox", event_type="created")
    assert rule.trigger_filter(event) is True


def test_inbox_ingest_rejects_modified_in_inbox():
    rule = _get_rule("inbox_ingest")
    event = _make_event(subdirectory="inbox", event_type="modified")
    assert rule.trigger_filter(event) is False


def test_inbox_ingest_rejects_wrong_subdirectory():
    rule = _get_rule("inbox_ingest")
    event = _make_event(subdirectory="people", event_type="created")
    assert rule.trigger_filter(event) is False


def test_inbox_ingest_produces_correct_actions():
    rule = _get_rule("inbox_ingest")
    event = _make_event(subdirectory="inbox", event_type="created", path="data/inbox/doc.pdf")
    actions = rule.produce(event)
    assert len(actions) == 2
    names = [a.name for a in actions]
    assert "ingest_document" in names
    assert "refresh_cache" in names
    ingest = next(a for a in actions if a.name == "ingest_document")
    assert ingest.phase == 0
    assert ingest.priority == 0
    assert ingest.args["path"] == event.path
    assert "ignore_fn" in ingest.args  # self-trigger prevention wired
    refresh = next(a for a in actions if a.name == "refresh_cache")
    assert refresh.phase == 1
    assert refresh.priority == 10
    assert "ingest_document" in refresh.depends_on


# --- meeting_cascade ---


def test_meeting_cascade_matches_created_in_meetings():
    rule = _get_rule("meeting_cascade")
    event = _make_event(subdirectory="meetings", event_type="created")
    assert rule.trigger_filter(event) is True


def test_meeting_cascade_matches_modified_in_meetings():
    rule = _get_rule("meeting_cascade")
    event = _make_event(subdirectory="meetings", event_type="modified")
    assert rule.trigger_filter(event) is True


def test_meeting_cascade_rejects_wrong_subdirectory():
    rule = _get_rule("meeting_cascade")
    event = _make_event(subdirectory="people", event_type="created")
    assert rule.trigger_filter(event) is False


def test_meeting_cascade_produces_correct_actions():
    rule = _get_rule("meeting_cascade")
    event = _make_event(subdirectory="meetings", event_type="created")
    actions = rule.produce(event)
    assert len(actions) == 2
    names = [a.name for a in actions]
    assert "refresh_cache" in names
    assert "extract_meeting" in names
    refresh = next(a for a in actions if a.name == "refresh_cache")
    assert refresh.phase == 0
    extract = next(a for a in actions if a.name == "extract_meeting")
    assert extract.phase == 1
    assert "refresh_cache" in extract.depends_on
    assert extract.args["path"] == event.path


def test_meeting_cascade_skips_prep_files():
    rule = _get_rule("meeting_cascade")
    event = _make_event(
        subdirectory="meetings",
        event_type="created",
        path="data/meetings/prep-alice-2026-03-09.md",
    )
    assert rule.trigger_filter(event) is False


# --- person_changed ---


def test_person_changed_matches_created_in_people():
    rule = _get_rule("person_changed")
    event = _make_event(subdirectory="people", event_type="created")
    assert rule.trigger_filter(event) is True


def test_person_changed_matches_modified_in_people():
    rule = _get_rule("person_changed")
    event = _make_event(subdirectory="people", event_type="modified")
    assert rule.trigger_filter(event) is True


def test_person_changed_rejects_wrong_subdirectory():
    rule = _get_rule("person_changed")
    event = _make_event(subdirectory="meetings", event_type="modified")
    assert rule.trigger_filter(event) is False


def test_person_changed_produces_correct_actions():
    rule = _get_rule("person_changed")
    event = _make_event(subdirectory="people", event_type="modified")
    actions = rule.produce(event)
    assert len(actions) == 1
    assert actions[0].name == "refresh_cache"
    assert actions[0].phase == 0
    assert actions[0].priority == 0


# --- coaching_changed ---


def test_coaching_changed_matches_created_in_coaching():
    rule = _get_rule("coaching_changed")
    event = _make_event(subdirectory="coaching", event_type="created")
    assert rule.trigger_filter(event) is True


def test_coaching_changed_matches_modified_in_coaching():
    rule = _get_rule("coaching_changed")
    event = _make_event(subdirectory="coaching", event_type="modified")
    assert rule.trigger_filter(event) is True


def test_coaching_changed_rejects_wrong_subdirectory():
    rule = _get_rule("coaching_changed")
    event = _make_event(subdirectory="people", event_type="modified")
    assert rule.trigger_filter(event) is False


def test_coaching_changed_produces_correct_actions():
    rule = _get_rule("coaching_changed")
    event = _make_event(subdirectory="coaching", event_type="modified")
    actions = rule.produce(event)
    assert len(actions) == 1
    assert actions[0].name == "refresh_cache"
    assert actions[0].phase == 0
    assert actions[0].priority == 0


# --- feedback_changed ---


def test_feedback_changed_matches_created_in_feedback():
    rule = _get_rule("feedback_changed")
    event = _make_event(subdirectory="feedback", event_type="created")
    assert rule.trigger_filter(event) is True


def test_feedback_changed_matches_modified_in_feedback():
    rule = _get_rule("feedback_changed")
    event = _make_event(subdirectory="feedback", event_type="modified")
    assert rule.trigger_filter(event) is True


def test_feedback_changed_rejects_wrong_subdirectory():
    rule = _get_rule("feedback_changed")
    event = _make_event(subdirectory="meetings", event_type="modified")
    assert rule.trigger_filter(event) is False


def test_feedback_changed_produces_correct_actions():
    rule = _get_rule("feedback_changed")
    event = _make_event(subdirectory="feedback", event_type="modified")
    actions = rule.produce(event)
    assert len(actions) == 1
    assert actions[0].name == "refresh_cache"
    assert actions[0].phase == 0


# --- decision_logged ---


def test_decision_logged_matches_created_in_decisions():
    rule = _get_rule("decision_logged")
    event = _make_event(subdirectory="decisions", event_type="created")
    assert rule.trigger_filter(event) is True


def test_decision_logged_rejects_modified_in_decisions():
    rule = _get_rule("decision_logged")
    event = _make_event(subdirectory="decisions", event_type="modified")
    assert rule.trigger_filter(event) is False


def test_decision_logged_rejects_wrong_subdirectory():
    rule = _get_rule("decision_logged")
    event = _make_event(subdirectory="people", event_type="created")
    assert rule.trigger_filter(event) is False


def test_decision_logged_produces_correct_actions():
    rule = _get_rule("decision_logged")
    event = _make_event(subdirectory="decisions", event_type="created")
    actions = rule.produce(event)
    assert len(actions) == 1
    assert actions[0].name == "refresh_cache"
    assert actions[0].phase == 0
    assert actions[0].priority == 0
