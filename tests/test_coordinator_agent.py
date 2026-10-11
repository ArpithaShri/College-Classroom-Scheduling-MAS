
"""Unit tests for TimetableCoordinatorAgent."""

import pytest
import asyncio
from collections import deque

from agents.timetable_coordinator import (
    AgentCommunicationError,
    CoordinatorRequestHandler,
    TimetableCoordinatorAgent,
)
from agents.department_agent import DepartmentAgent
from agents.faculty_agent import FacultyAgent
from agents.classroom_agent import ClassroomAgent
from agents.student_group_agent import StudentGroupAgent
from agents.communication import (
    ACCEPT,
    REJECT,
    CONFIRM,
    create_spade_message,
    parse_spade_message,
)
from scheduler.domain import (
    Course,
    Faculty,
    Room,
    SchedulingProblem,
    StudentGroup,
    TimeSlot,
)


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
        assert "no candidate passed" in reason.lower()
        assert coordinator.confirmed_assignments == []

    asyncio.run(run_test())


def test_confirmation_rejection_cancels_partial_booking_and_tries_alternative():
    problem = SchedulingProblem(
        courses=[
            Course(
                id="CS301",
                name="Machine Learning",
                faculty_id="F001",
                student_group_id="CSE-A",
                enrollment=30,
                duration=1,
            )
        ],
        faculty=[Faculty(id="F001", name="Faculty One")],
        rooms=[Room(id="R101", name="Room 101", capacity=60)],
        student_groups=[StudentGroup(id="CSE-A", name="Section A")],
    )
    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@localhost",
        scheduling_problem=problem,
    )
    faculty_agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
    )
    room_agent = ClassroomAgent(
        jid="classroom_r101@localhost",
        room_id="R101",
        capacity=60,
    )
    student_agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
    )

    original_confirm = room_agent.handle_confirm
    rejected_first_confirmation = False

    def reject_first_room_confirmation(payload):
        nonlocal rejected_first_confirmation
        if not rejected_first_confirmation:
            rejected_first_confirmation = True
            return REJECT, {
                **payload,
                "reason": "Room became unavailable during confirmation",
            }
        return original_confirm(payload)

    room_agent.handle_confirm = reject_first_room_confirmation

    async def run_test():
        success, assignment, reason = (
            await coordinator.coordinate_course_negotiation(
                request_payload={
                    "course_id": "CS301",
                    "course_name": "Machine Learning",
                    "faculty_id": "F001",
                    "student_group_id": "CSE-A",
                    "enrollment": 30,
                    "duration": 1,
                    "day": "Monday",
                    "start_time": "10:00",
                    "room_id": "R101",
                },
                faculty_agent=faculty_agent,
                classroom_agents_map={"R101": room_agent},
                student_group_agent=student_agent,
            )
        )

        assert success is True, reason
        assert assignment is not None
        assert (assignment["day"], assignment["start_time"]) != (
            "Monday",
            "10:00",
        )
        assert assignment["status"] == "SCHEDULED"
        assert coordinator.confirmed_assignments == [assignment]
        assert faculty_agent.existing_assignments == {
            (assignment["day"], assignment["start_time"]): "CS301"
        }
        assert room_agent.current_bookings == {
            (assignment["day"], assignment["start_time"]): "CS301"
        }
        assert student_agent.existing_timetable == {
            (assignment["day"], assignment["start_time"]): "Machine Learning"
        }

    asyncio.run(run_test())


class _CoordinatorBehaviorStub:
    def __init__(self, agent, send_error=None):
        self.agent = agent
        self.send_error = send_error
        self.sent = []
        self.incoming = deque()

    async def send(self, message):
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(message)

    async def receive(self, timeout=None):
        return self.incoming.popleft()


def test_live_message_send_failure_is_reported_and_pending_reply_removed():
    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@example.test",
    )
    behavior = _CoordinatorBehaviorStub(
        coordinator, send_error=OSError("transport unavailable")
    )

    async def run_test():
        with pytest.raises(AgentCommunicationError, match="Could not transmit"):
            await CoordinatorRequestHandler.send_and_wait(
                behavior,
                to_jid="faculty@example.test",
                performative="PROPOSE",
                payload={"course_id": "CS301"},
                timeout=0.1,
            )

        assert coordinator._pending_replies == {}
        assert any(
            entry["status"] == "SENT:FAILED"
            for entry in coordinator.message_history
        )

    asyncio.run(run_test())


def test_live_reply_timeout_is_reported_and_pending_reply_removed():
    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@example.test",
    )
    behavior = _CoordinatorBehaviorStub(coordinator)

    async def run_test():
        with pytest.raises(AgentCommunicationError, match="Timed out waiting"):
            await CoordinatorRequestHandler.send_and_wait(
                behavior,
                to_jid="faculty@example.test",
                performative="PROPOSE",
                payload={"course_id": "CS301"},
                timeout=0.001,
            )

        assert coordinator._pending_replies == {}
        assert any(
            entry["status"] == "LIVE:TIMEOUT"
            for entry in coordinator.message_history
        )

    asyncio.run(run_test())


def test_live_reply_rejects_mismatched_sender_and_correlation_id():
    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@example.test",
    )
    behavior = _CoordinatorBehaviorStub(coordinator)

    async def run_test():
        exchange = asyncio.create_task(
            CoordinatorRequestHandler.send_and_wait(
                behavior,
                to_jid="faculty@example.test",
                performative="PROPOSE",
                payload={"course_id": "CS301"},
                timeout=0.5,
            )
        )
        await asyncio.sleep(0)
        request = behavior.sent[0]
        _, request_payload = parse_spade_message(request)
        correlation_id = request_payload["correlation_id"]

        behavior.incoming.append(
            create_spade_message(
                to=str(coordinator.jid),
                sender="attacker@example.test",
                performative=ACCEPT,
                payload={"correlation_id": correlation_id},
                thread=correlation_id,
            )
        )
        await CoordinatorRequestHandler.run(behavior)

        behavior.incoming.append(
            create_spade_message(
                to=str(coordinator.jid),
                sender="faculty@example.test",
                performative=ACCEPT,
                payload={"correlation_id": correlation_id},
                thread="wrong-correlation",
            )
        )
        await CoordinatorRequestHandler.run(behavior)

        behavior.incoming.append(
            create_spade_message(
                to="another-agent@example.test",
                sender="faculty@example.test",
                performative=ACCEPT,
                payload={"correlation_id": correlation_id},
                thread=correlation_id,
            )
        )
        await CoordinatorRequestHandler.run(behavior)

        assert not exchange.done()
        assert sum(
            entry["status"] == "LIVE:UNMATCHED"
            for entry in coordinator.message_history
        ) == 3

        behavior.incoming.append(
            create_spade_message(
                to=str(coordinator.jid),
                sender="faculty@example.test",
                performative=ACCEPT,
                payload={
                    "correlation_id": correlation_id,
                    "decision": "accepted",
                },
                thread=correlation_id,
            )
        )
        await CoordinatorRequestHandler.run(behavior)

        response_type, response_payload = await exchange
        assert response_type == ACCEPT
        assert response_payload["decision"] == "accepted"

    asyncio.run(run_test())