"""Unit tests for DepartmentAgent."""

import pytest
from agents.department_agent import DepartmentAgent
from agents.communication import REQUEST, ACCEPT, FINAL_ACCEPT, REJECT


def test_department_agent_initialization():
    """Verify local state and attributes of DepartmentAgent."""
    agent = DepartmentAgent(
        jid="dept_cs@localhost",
        department_id="DEPT-CS",
        department_name="Computer Science & Engineering",
        coordinator_jid="coordinator@localhost",
    )
    assert agent.department_id == "DEPT-CS"
    assert agent.coordinator_jid == "coordinator@localhost"
    assert agent.course_requirements == {}
    assert agent.pending_requests == {}


def test_department_agent_add_course_requirement():
    """Verify adding course requirements and building structured REQUEST messages."""
    agent = DepartmentAgent(
        jid="dept_cs@localhost",
        department_id="DEPT-CS",
    )

    agent.add_course_requirement(
        course_id="CS301",
        course_name="Machine Learning",
        faculty_id="F001",
        student_group_id="CSE-A",
        enrollment=55,
        duration=1,
        preferred_day="Monday",
        preferred_time="10:00",
        preferred_room="R102",
    )

    assert "CS301" in agent.course_requirements
    req = agent.build_scheduling_request("CS301")
    assert req["type"] == REQUEST
    assert req["course_id"] == "CS301"
    assert req["faculty_id"] == "F001"
    assert req["enrollment"] == 55
    assert req["day"] == "Monday"


def test_department_agent_process_coordinator_response():
    """Verify state transitions upon receiving ACCEPT and REJECT responses."""
    agent = DepartmentAgent(jid="dept_cs@localhost")
    agent.add_course_requirement(
        course_id="CS301",
        course_name="Machine Learning",
        faculty_id="F001",
        student_group_id="CSE-A",
        enrollment=55,
    )
    agent.pending_requests["CS301"] = agent.build_scheduling_request("CS301")

    # Simulate FINAL_ACCEPT
    accepted_payload = {
        "course_id": "CS301",
        "day": "Monday",
        "start_time": "10:00",
        "room_id": "R102",
        "status": "SCHEDULED",
    }
    agent.process_coordinator_response("coordinator@localhost", FINAL_ACCEPT, accepted_payload)

    assert "CS301" not in agent.pending_requests
    assert "CS301" in agent.scheduled_courses
    assert agent.scheduled_courses["CS301"]["room_id"] == "R102"

    # Simulate REJECT on another course
    agent.pending_requests["CS999"] = {"course_id": "CS999"}
    reject_payload = {"course_id": "CS999", "reason": "No feasible slot"}
    agent.process_coordinator_response("coordinator@localhost", REJECT, reject_payload)

    assert "CS999" not in agent.pending_requests
    assert "CS999" in agent.failed_requests
