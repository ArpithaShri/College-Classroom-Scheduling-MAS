"""Unit tests for FacultyAgent."""

import pytest
from agents.faculty_agent import FacultyAgent
from agents.communication import PROPOSE, ACCEPT, REJECT, COUNTER_PROPOSE, CONFIRM
from scheduler.domain import TimeSlot


def test_faculty_agent_initialization():
    """Verify local knowledge initialization for FacultyAgent."""
    avail = [TimeSlot("Monday", "10:00"), TimeSlot("Monday", "11:00")]
    pref = [TimeSlot("Monday", "10:00")]
    agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
        faculty_name="Dr. Turing",
        available_slots=avail,
        preferred_slots=pref,
    )

    assert agent.faculty_id == "F001"
    assert agent.faculty_name == "Dr. Turing"
    assert ("Monday", "10:00") in agent.available_slots
    assert ("Tuesday", "10:00") not in agent.available_slots
    assert len(agent.preferred_slots) == 1
    assert agent.existing_assignments == {}


def test_faculty_agent_validate_available_slot():
    """Verify validation passes for an available free slot."""
    avail = [TimeSlot("Monday", "10:00"), TimeSlot("Monday", "11:00")]
    agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
        available_slots=avail,
    )

    is_valid, reason, alts = agent.validate_slot("Monday", "10:00", duration=1, course_id="CS301")
    assert is_valid is True
    assert reason is None


def test_faculty_agent_reject_unavailable_slot():
    """Verify rejection when proposed slot is outside faculty availability."""
    avail = [TimeSlot("Monday", "10:00")]
    agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
        available_slots=avail,
    )

    is_valid, reason, alts = agent.validate_slot("Tuesday", "10:00", duration=1, course_id="CS301")
    assert is_valid is False
    assert "unavailable" in reason.lower()
    assert len(alts) > 0  # Suggests Monday 10:00 as alternative


def test_faculty_agent_double_booking_detection():
    """Verify conflict detection when faculty is already booked for another course."""
    avail = [TimeSlot("Monday", "10:00"), TimeSlot("Tuesday", "10:00")]
    agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
        available_slots=avail,
    )

    # Book Monday 10:00 for CS101
    agent.existing_assignments[("Monday", "10:00")] = "CS101"

    # Attempt to schedule CS301 at the same time
    is_valid, reason, alts = agent.validate_slot("Monday", "10:00", duration=1, course_id="CS301")
    assert is_valid is False
    assert "double booked" in reason.lower()


def test_faculty_agent_handle_propose_and_confirm():
    """Verify handle_propose returns ACCEPT and handle_confirm commits locally."""
    avail = [TimeSlot("Monday", "10:00")]
    agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
        available_slots=avail,
    )

    proposal = {
        "course_id": "CS301",
        "day": "Monday",
        "start_time": "10:00",
        "duration": 1,
    }

    # Propose
    resp_type, resp_payload = agent.handle_propose(proposal)
    assert resp_type == ACCEPT
    assert resp_payload["status"] == "ACCEPTED"

    # Confirm
    conf_type, conf_payload = agent.handle_confirm(proposal)
    assert conf_type == ACCEPT
    assert agent.existing_assignments[("Monday", "10:00")] == "CS301"
