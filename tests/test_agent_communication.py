"""Unit tests for SPADE communication protocols and message logging."""

import json
from agents.communication import (
    REQUEST,
    PROPOSE,
    ACCEPT,
    REJECT,
    COUNTER_PROPOSE,
    CONFLICT,
    RESCHEDULE,
    ALLOCATE,
    CHECK_TIMETABLE,
    CONFIRM,
    FINAL_ACCEPT,
    SchedulingMessagePayload,
    create_spade_message,
    parse_spade_message,
    create_template_for,
    AgentMessageLogger,
    agent_logger,
)


def test_performative_constants():
    """Verify that all standard FIPA/SPADE performatives are defined and unique."""
    performatives = [
        REQUEST,
        PROPOSE,
        ACCEPT,
        REJECT,
        COUNTER_PROPOSE,
        CONFLICT,
        RESCHEDULE,
        ALLOCATE,
        CHECK_TIMETABLE,
        CONFIRM,
        FINAL_ACCEPT,
    ]
    assert len(performatives) == len(set(performatives))
    for p in performatives:
        assert isinstance(p, str)
        assert p.isupper()


def test_scheduling_message_payload_serialization():
    """Test payload creation, serialization to dict/json, and deserialization."""
    payload = SchedulingMessagePayload(
        type=PROPOSE,
        course_id="CS301",
        course_name="Machine Learning",
        faculty_id="F001",
        student_group_id="CSE-A",
        room_id="R101",
        day="Monday",
        start_time="10:00",
        duration=1,
        enrollment=55,
        room_type="classroom",
        status="PROPOSED",
    )

    data_dict = payload.to_dict()
    assert data_dict["course_id"] == "CS301"
    assert data_dict["faculty_id"] == "F001"
    assert data_dict["enrollment"] == 55

    json_str = payload.to_json()
    assert "Machine Learning" in json_str

    deserialized = SchedulingMessagePayload.from_json(json_str)
    assert deserialized.course_id == "CS301"
    assert deserialized.room_id == "R101"
    assert deserialized.day == "Monday"


def test_create_and_parse_spade_message():
    """Test constructing and parsing SPADE messages with ontology and metadata."""
    payload = {
        "type": REQUEST,
        "course_id": "CS101",
        "faculty_id": "F002",
        "student_group_id": "CSE-B",
        "enrollment": 40,
    }
    msg = create_spade_message(
        to="coordinator@localhost",
        sender="dept_cs@localhost",
        performative=REQUEST,
        payload=payload,
    )

    assert str(msg.to) == "coordinator@localhost"
    assert str(msg.sender) == "dept_cs@localhost"
    assert msg.get_metadata("performative") == REQUEST
    assert msg.get_metadata("ontology") == "classroom-scheduling"

    perf, parsed_data = parse_spade_message(msg)
    assert perf == REQUEST
    assert parsed_data["course_id"] == "CS101"
    assert parsed_data["faculty_id"] == "F002"


def test_spade_template_matching():
    """Test template filtering on performative metadata."""
    tmpl = create_template_for(PROPOSE)
    msg_propose = create_spade_message(
        to="faculty@localhost",
        sender="coord@localhost",
        performative=PROPOSE,
        payload={"course_id": "CS201"},
    )
    msg_reject = create_spade_message(
        to="faculty@localhost",
        sender="coord@localhost",
        performative=REJECT,
        payload={"course_id": "CS201"},
    )

    assert tmpl.match(msg_propose)
    assert not tmpl.match(msg_reject)


def test_agent_message_logger():
    """Test recording and formatting inter-agent audit logs."""
    logger_instance = AgentMessageLogger()
    logger_instance.clear()
    assert len(logger_instance.get_logs()) == 0

    entry = logger_instance.log_message(
        sender="dept_cs@localhost",
        receiver="coordinator@localhost",
        message_type=REQUEST,
        course="CS301",
        payload={"course_id": "CS301", "day": "Monday", "start_time": "10:00"},
        status="SENT",
    )

    assert entry["course"] == "CS301"
    assert entry["message_type"] == "REQUEST"
    assert len(logger_instance.get_logs()) == 1

    formatted = logger_instance.format_entry(entry)
    assert "dept_cs → coordinator" in formatted
    assert "REQUEST" in formatted
    assert "Course: CS301" in formatted
