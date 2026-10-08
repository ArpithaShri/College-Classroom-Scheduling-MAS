"""Department Agent implementation for SPADE Multi-Agent System.

Represents an academic department (e.g., Department of Computer Science).
Maintains curriculum and course requirements, initiates scheduling requests (REQUEST),
processes responses from the Timetable Coordinator, and tracks completion status.
"""

from typing import Optional, List, Dict, Tuple, Set, Any, Union
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message

from .base_agent import BaseAgent
from .communication import (
    REQUEST,
    PROPOSE,
    ACCEPT,
    REJECT,
    FINAL_ACCEPT,
    COUNTER_PROPOSE,
    CONFLICT,
    SchedulingMessagePayload,
    parse_spade_message,
)
from scheduler.domain import Course


class DepartmentReceiverBehaviour(CyclicBehaviour):
    """Cyclic behaviour for receiving responses and status updates from Coordinator."""

    async def run(self):
        msg = await self.receive(timeout=1.0)
        if msg:
            agent: "DepartmentAgent" = self.agent
            performative, payload = agent.record_received_message(msg)
            agent.process_coordinator_response(msg.sender, performative, payload)


class SendCourseRequestBehaviour(OneShotBehaviour):
    """OneShot behaviour to transmit a course scheduling REQUEST to the coordinator."""

    def __init__(self, request_payload: Dict[str, Any]):
        super().__init__()
        self.request_payload = request_payload

    async def run(self):
        agent: "DepartmentAgent" = self.agent
        await agent.send_message(
            to=agent.coordinator_jid,
            performative=REQUEST,
            payload=self.request_payload,
        )


class DepartmentAgent(BaseAgent):
    """Autonomous agent representing an academic department managing course requirements."""

    def __init__(
        self,
        jid: str,
        password: Optional[str] = None,
        department_id: str = "DEPT-CS",
        department_name: str = "Computer Science & Engineering",
        coordinator_jid: str = "coordinator@localhost",
        **kwargs,
    ):
        super().__init__(jid=jid, password=password, role="DepartmentAgent", **kwargs)

        self.department_id = department_id
        self.department_name = department_name
        self.coordinator_jid = str(coordinator_jid)

        # Local knowledge
        self.course_requirements: Dict[str, Dict[str, Any]] = {}
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.scheduled_courses: Dict[str, Dict[str, Any]] = {}
        self.failed_requests: Dict[str, Dict[str, Any]] = {}

    async def setup(self):
        """Register CyclicBehaviour on startup."""
        await super().setup()
        receiver = DepartmentReceiverBehaviour()
        self.add_behaviour(receiver)

    def add_course_requirement(
        self,
        course_id: str,
        course_name: str,
        faculty_id: str,
        student_group_id: str,
        enrollment: int,
        duration: int = 1,
        room_type: str = "classroom",
        is_lab: bool = False,
        preferred_day: Optional[str] = None,
        preferred_time: Optional[str] = None,
        preferred_room: Optional[str] = None,
    ):
        """Register a course requirement in the department curriculum."""
        self.course_requirements[course_id] = {
            "course_id": course_id,
            "course_name": course_name,
            "faculty_id": faculty_id,
            "student_group_id": student_group_id,
            "enrollment": enrollment,
            "duration": duration,
            "room_type": room_type.lower(),
            "is_lab": is_lab,
            "day": preferred_day,
            "start_time": preferred_time,
            "room_id": preferred_room,
        }

    def build_scheduling_request(
        self, course_id: str
    ) -> Optional[Dict[str, Any]]:
        """Construct structured request payload for a registered course requirement."""
        req = self.course_requirements.get(course_id)
        if not req:
            return None

        payload = {
            "type": REQUEST,
            "course_id": req["course_id"],
            "course_name": req["course_name"],
            "faculty_id": req["faculty_id"],
            "student_group_id": req["student_group_id"],
            "enrollment": req["enrollment"],
            "duration": req["duration"],
            "room_type": req["room_type"],
            "is_lab": req["is_lab"],
            "day": req.get("day"),
            "start_time": req.get("start_time"),
            "room_id": req.get("room_id"),
            "status": "REQUESTED",
        }
        return payload

    async def request_schedule_course(
        self, course_id: str
    ) -> Optional[Message]:
        """Send a scheduling request for a registered course to the coordinator."""
        payload = self.build_scheduling_request(course_id)
        if not payload:
            self.logger.error(f"Cannot request schedule: Course {course_id} not registered.")
            return None

        self.pending_requests[course_id] = payload
        msg = await self.send_message(
            to=self.coordinator_jid,
            performative=REQUEST,
            payload=payload,
        )
        return msg

    def process_coordinator_response(
        self, sender: Any, performative: str, payload: Dict[str, Any]
    ):
        """Handle incoming responses (ACCEPT, FINAL_ACCEPT, REJECT) from the Coordinator."""
        course_id = payload.get("course_id", "")
        p_upper = performative.upper()

        if p_upper in (ACCEPT, FINAL_ACCEPT):
            self.scheduled_courses[course_id] = payload
            self.pending_requests.pop(course_id, None)
            self.logger.info(
                f"Department {self.department_id}: Course {course_id} successfully scheduled at {payload.get('day')} {payload.get('start_time')} in {payload.get('room_id')}."
            )
        elif p_upper == REJECT:
            self.failed_requests[course_id] = payload
            self.pending_requests.pop(course_id, None)
            self.logger.warning(
                f"Department {self.department_id}: Course {course_id} scheduling failed. Reason: {payload.get('reason')}"
            )
