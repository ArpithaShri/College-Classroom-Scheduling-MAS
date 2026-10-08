"""Unit tests for StudentGroupAgent."""

import pytest
from agents.student_group_agent import StudentGroupAgent
from agents.communication import CHECK_TIMETABLE, PROPOSE, ACCEPT, CONFLICT, CONFIRM


def test_student_group_agent_initialization():
    """Verify local state and attributes of StudentGroupAgent."""
    agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
        group_name="Section A",
        size=60,
    )
    assert agent.group_id == "CSE-A"
    assert agent.size == 60
    assert agent.existing_timetable == {}


def test_student_group_agent_validate_free_slot():
    """Verify acceptance when group has no conflicting classes."""
    agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
    )
    valid, reason, _ = agent.validate_timetable("Monday", "10:00", duration=1)
    assert valid is True
    assert reason is None


def test_student_group_agent_timetable_clash():
    """Verify CONFLICT when another course is already scheduled for the group."""
    schedule = {("Monday", "10:00"): "Computer Networks"}
    agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
        existing_timetable=schedule,
    )

    valid, reason, alts = agent.validate_timetable(
        "Monday", "10:00", duration=1, course_id="CS301", course_name="Machine Learning"
    )
    assert valid is False
    assert "Computer Networks already scheduled" in reason
    assert len(alts) > 0


def test_student_group_agent_handle_check_timetable_and_confirm():
    """Verify handle_check_timetable_or_propose and confirm cycle."""
    agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
    )

    proposal = {
        "course_id": "CS301",
        "course_name": "Machine Learning",
        "day": "Monday",
        "start_time": "10:00",
        "duration": 1,
    }

    # Check
    resp_type, resp_payload = agent.handle_check_timetable_or_propose(proposal)
    assert resp_type == ACCEPT
    assert resp_payload["status"] == "ACCEPTED"

    # Confirm
    agent.handle_confirm(proposal)
    assert agent.existing_timetable[("Monday", "10:00")] == "Machine Learning"
