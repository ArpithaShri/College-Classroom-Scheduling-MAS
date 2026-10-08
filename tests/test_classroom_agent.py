"""Unit tests for ClassroomAgent."""

import pytest
from agents.classroom_agent import ClassroomAgent
from agents.communication import ALLOCATE, PROPOSE, ACCEPT, REJECT, CONFLICT, CONFIRM


def test_classroom_agent_initialization():
    """Verify local state and attributes of ClassroomAgent."""
    agent = ClassroomAgent(
        jid="classroom_r101@localhost",
        room_id="R101",
        room_name="Classroom 101",
        capacity=45,
        room_type="classroom",
    )
    assert agent.room_id == "R101"
    assert agent.capacity == 45
    assert agent.room_type == "classroom"
    assert agent.current_bookings == {}


def test_classroom_agent_capacity_validation():
    """Verify acceptance when capacity is sufficient, and rejection when exceeded."""
    agent = ClassroomAgent(
        jid="classroom_r101@localhost",
        room_id="R101",
        capacity=40,
    )

    # Valid: enrollment 35 <= capacity 40
    valid, reason, _ = agent.validate_room("Monday", "10:00", duration=1, enrollment=35)
    assert valid is True
    assert reason is None

    # Invalid: enrollment 50 > capacity 40
    valid, reason, _ = agent.validate_room("Monday", "10:00", duration=1, enrollment=50)
    assert valid is False
    assert "capacity" in reason.lower()


def test_classroom_agent_room_type_validation():
    """Verify rejection when a lab is required but room is theory classroom."""
    agent = ClassroomAgent(
        jid="classroom_r101@localhost",
        room_id="R101",
        capacity=60,
        room_type="classroom",
    )

    valid, reason, _ = agent.validate_room(
        "Monday", "10:00", duration=1, enrollment=30, requested_room_type="lab"
    )
    assert valid is False
    assert "room type mismatch" in reason.lower()


def test_classroom_agent_double_booking():
    """Verify conflict detection when room is already occupied."""
    agent = ClassroomAgent(
        jid="classroom_r101@localhost",
        room_id="R101",
        capacity=60,
    )
    # Book Monday 10:00 for CS101
    agent.current_bookings[("Monday", "10:00")] = "CS101"

    valid, reason, _ = agent.validate_room(
        "Monday", "10:00", duration=1, enrollment=30, course_id="CS301"
    )
    assert valid is False
    assert "already occupied" in reason.lower()


def test_classroom_agent_allocate_and_confirm():
    """Verify handle_allocate_or_propose and confirm cycle."""
    agent = ClassroomAgent(
        jid="classroom_r102@localhost",
        room_id="R102",
        capacity=65,
    )

    req = {
        "course_id": "CS301",
        "day": "Monday",
        "start_time": "10:00",
        "duration": 1,
        "enrollment": 55,
        "room_type": "classroom",
    }

    resp_type, resp_payload = agent.handle_allocate_or_propose(req)
    assert resp_type == ACCEPT
    assert resp_payload["status"] == "ACCEPTED"

    agent.handle_confirm(req)
    assert agent.current_bookings[("Monday", "10:00")] == "CS301"
