
"""Unit tests for TimetableCoordinatorAgent."""

import pytest
import asyncio

from agents.timetable_coordinator import TimetableCoordinatorAgent
from agents.department_agent import DepartmentAgent
from agents.faculty_agent import FacultyAgent
from agents.classroom_agent import ClassroomAgent
from agents.student_group_agent import StudentGroupAgent
from agents.communication import ACCEPT, REJECT, CONFIRM
from scheduler.domain import SchedulingProblem, Room, TimeSlot


def test_coordinator_initialization_and_registry():
    """Verify coordinator initialization and agent registry."""
    coordinator = TimetableCoordinatorAgent(jid="coordinator@localhost")

    coordinator.register_faculty_agent("F001", "faculty_f001@localhost")
    coordinator.register_classroom_agent("R101", "classroom_r101@localhost")
    coordinator.register_student_group_agent(
        "CSE-A", "studentgroup_csea@localhost"
    )
    coordinator.register_department_agent("DEPT-CS", "dept_cs@localhost")

    assert coordinator.faculty_agents["F001"] == "faculty_f001@localhost"
    assert coordinator.classroom_agents["R101"] == "classroom_r101@localhost"
    assert (
        coordinator.student_group_agents["CSE-A"]
        == "studentgroup_csea@localhost"
    )
    assert coordinator.department_agents["DEPT-CS"] == "dept_cs@localhost"


def test_coordinator_happy_path_negotiation():
    """Verify multi-agent consensus when all constraints are satisfied."""
    problem = SchedulingProblem(
        rooms=[
            Room(
                id="R102",
                name="Hall 102",
                capacity=65,
                room_type="classroom",
            )
        ]
    )

    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@localhost",
        scheduling_problem=problem,
    )

    fac_agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
    )
    room_agent = ClassroomAgent(
        jid="classroom_r102@localhost",
        room_id="R102",
        capacity=65,
    )
    sg_agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
    )

    request = {
        "course_id": "CS301",
        "course_name": "Machine Learning",
        "faculty_id": "F001",
        "student_group_id": "CSE-A",
        "enrollment": 55,
        "duration": 1,
        "day": "Monday",
        "start_time": "10:00",
        "room_id": "R102",
    }

    async def run_test():
        success, schedule, msg = (
            await coordinator.coordinate_course_negotiation(
                request_payload=request,
                faculty_agent=fac_agent,
                classroom_agents_map={"R102": room_agent},
                student_group_agent=sg_agent,
            )
        )

        assert success is True
        assert schedule["status"] == "SCHEDULED"
        assert schedule["room_id"] == "R102"
        assert schedule["day"] == "Monday"
        assert schedule["start_time"] == "10:00"

    asyncio.run(run_test())


def test_coordinator_capacity_conflict_and_rescheduling():
    """Verify rescheduling when the initial room lacks sufficient capacity."""
    rooms = [
        Room(
            id="R101",
            name="Room 101",
            capacity=40,
            room_type="classroom",
        ),
        Room(
            id="R102",
            name="Room 102",
            capacity=65,
            room_type="classroom",
        ),
    ]

    problem = SchedulingProblem(rooms=rooms)

    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@localhost",
        scheduling_problem=problem,
    )

    fac_agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
    )
    room_r101 = ClassroomAgent(
        jid="classroom_r101@localhost",
        room_id="R101",
        capacity=40,
    )
    room_r102 = ClassroomAgent(
        jid="classroom_r102@localhost",
        room_id="R102",
        capacity=65,
    )
    sg_agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
    )

    request = {
        "course_id": "CS301",
        "course_name": "Machine Learning",
        "faculty_id": "F001",
        "student_group_id": "CSE-A",
        "enrollment": 60,
        "duration": 1,
        "day": "Monday",
        "start_time": "10:00",
        "room_id": "R101",
    }

    async def run_test():
        success, schedule, _ = (
            await coordinator.coordinate_course_negotiation(
                request_payload=request,
                faculty_agent=fac_agent,
                classroom_agents_map={
                    "R101": room_r101,
                    "R102": room_r102,
                },
                student_group_agent=sg_agent,
            )
        )

        assert success is True
        assert schedule["room_id"] == "R102"
        assert schedule["enrollment"] == 60

    asyncio.run(run_test())


def test_coordinator_student_conflict_and_rescheduling():
    """Verify rescheduling when the student group is already busy."""
    problem = SchedulingProblem(
        rooms=[
            Room(
                id="R102",
                name="Room 102",
                capacity=65,
                room_type="classroom",
            )
        ]
    )

    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@localhost",
        scheduling_problem=problem,
    )

    fac_agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
    )
    room_r102 = ClassroomAgent(
        jid="classroom_r102@localhost",
        room_id="R102",
        capacity=65,
    )

    existing = {("Monday", "10:00"): "Computer Networks"}

    sg_agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
        existing_timetable=existing,
    )

    request = {
        "course_id": "CS301",
        "course_name": "Machine Learning",
        "faculty_id": "F001",
        "student_group_id": "CSE-A",
        "enrollment": 55,
        "duration": 1,
        "day": "Monday",
        "start_time": "10:00",
        "room_id": "R102",
    }

    async def run_test():
        success, schedule, _ = (
            await coordinator.coordinate_course_negotiation(
                request_payload=request,
                faculty_agent=fac_agent,
                classroom_agents_map={"R102": room_r102},
                student_group_agent=sg_agent,
            )
        )

        assert success is True
        assert (
            schedule["day"],
            schedule["start_time"],
        ) != ("Monday", "10:00")
        assert schedule["status"] == "SCHEDULED"

    asyncio.run(run_test())



def test_coordinator_does_not_finalize_when_confirmation_is_rejected(
    monkeypatch,
):
    """An assignment must not be finalized if an agent rejects confirmation."""
    from agents.communication import ACCEPT, REJECT, CONFIRM

    problem = SchedulingProblem(
        rooms=[
            Room(
                id="R101",
                name="Room 101",
                capacity=60,
                room_type="classroom",
            )
        ]
    )

    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@localhost",
        password="test",
        scheduling_problem=problem,
    )

    async def fake_send_and_await_reply(
        to_jid,
        performative,
        payload,
        timeout=2.0,
        direct_target_agent=None,
    ):
        # Simulate the classroom becoming unavailable during final confirmation.
        if performative == CONFIRM and "classroom" in to_jid.lower():
            return REJECT, {"reason": "Room became unavailable"}

        # All other negotiation messages are accepted.
        return ACCEPT, {}

    monkeypatch.setattr(
        coordinator,
        "send_and_await_reply",
        fake_send_and_await_reply,
    )

    async def run_test():
        result = await coordinator.coordinate_course_negotiation(
            request_payload={
                "course_id": "CS301",
                "course_name": "Test Course",
                "faculty_id": "F001",
                "student_group_id": "CSE-A",
                "enrollment": 30,
                "duration": 1,
                "day": "Monday",
                "start_time": "10:00",
                "room_id": "R101",
            }
        )

        assert result is not None, (
            "Negotiation returned None instead of a result tuple."
        )

        success, assignment, reason = result

        assert success is False
        assert assignment is None
        assert "confirmation failed" in reason.lower()
        assert coordinator.confirmed_assignments == []

    asyncio.run(run_test())