"""Student Group Agent implementation for SPADE Multi-Agent System.

Represents a cohort or section of students (e.g., CSE-A).
Maintains local state for student commitments and scheduled timetable.
Validates proposed class timings to avoid timetable clashes for students.
"""

from typing import Optional, List, Dict, Tuple, Set, Any, Union
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from .base_agent import BaseAgent
from .communication import (
    CHECK_TIMETABLE,
    PROPOSE,
    ACCEPT,
    REJECT,
    CONFLICT,
    COUNTER_PROPOSE,
    CONFIRM,
    REASON_TIMETABLE_OVERLAP,
    SchedulingMessagePayload,
    parse_spade_message,
)
from scheduler.domain import DEFAULT_DAYS, DEFAULT_TIME_SLOTS


class StudentGroupReceiverBehaviour(CyclicBehaviour):
    """Cyclic behaviour for processing timetable verification requests."""

    async def run(self):
        msg = await self.receive(timeout=1.0)
        if msg:
            agent: "StudentGroupAgent" = self.agent
            performative, payload = agent.record_received_message(msg)
            reply = agent.process_incoming_message(msg.sender, performative, payload)
            if reply:
                await self.send(reply)


class StudentGroupAgent(BaseAgent):
    """Autonomous agent representing a student cohort or batch."""

    def __init__(
        self,
        jid: str,
        password: Optional[str] = None,
        group_id: str = "CSE-A",
        group_name: str = "Computer Science Section A",
        size: int = 60,
        existing_timetable: Optional[Dict[Tuple[str, str], str]] = None,
        commitments: Optional[Set[Tuple[str, str]]] = None,
        **kwargs,
    ):
        super().__init__(jid=jid, password=password, role="StudentGroupAgent", **kwargs)

        self.group_id = group_id
        self.group_name = group_name
        self.size = size

        # Local knowledge of group's timetable: (day, time) -> course_name / course_id
        self.existing_timetable: Dict[Tuple[str, str], str] = (
            dict(existing_timetable) if existing_timetable else {}
        )
        self.commitments: Set[Tuple[str, str]] = (
            set(commitments) if commitments else set()
        )

    async def setup(self):
        """Register CyclicBehaviour on startup."""
        await super().setup()
        receiver = StudentGroupReceiverBehaviour()
        self.add_behaviour(receiver)

    def get_consecutive_slots(
        self, day: str, start_time: str, duration: int
    ) -> Optional[List[str]]:
        """Compute list of consecutive time slots."""
        if start_time not in DEFAULT_TIME_SLOTS:
            return None
        idx = DEFAULT_TIME_SLOTS.index(start_time)
        if idx + duration > len(DEFAULT_TIME_SLOTS):
            return None
        return DEFAULT_TIME_SLOTS[idx : idx + duration]

    def validate_timetable(
        self,
        day: str,
        start_time: str,
        duration: int = 1,
        course_id: str = "",
        course_name: str = "",
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
        """Validate if student group is free and has no timetable clash."""
        slots = self.get_consecutive_slots(day, start_time, duration)
        if not slots:
            return (
                False,
                f"Invalid time bounds: {day} {start_time} for {duration}h",
                self.find_free_slots(duration),
            )

        # Check existing class schedule
        for slot in slots:
            if (day, slot) in self.existing_timetable:
                existing_course = self.existing_timetable[(day, slot)]
                return (
                    False,
                    f"{existing_course} already scheduled at {day} {slot}",
                    self.find_free_slots(duration),
                )

        # Check other commitments
        for slot in slots:
            if (day, slot) in self.commitments:
                return (
                    False,
                    f"Group {self.group_id} has prior commitment at {day} {slot}",
                    self.find_free_slots(duration),
                )

        return True, None, []

    def is_slot_free(self, day: str, start_time: str, duration: int = 1) -> bool:
        """Check directly whether a slot is free of timetable conflicts."""
        slots = self.get_consecutive_slots(day, start_time, duration)
        if not slots:
            return False
        for slot in slots:
            if (day, slot) in self.existing_timetable or (day, slot) in self.commitments:
                return False
        return True

    def find_free_slots(self, duration: int = 1) -> List[Dict[str, Any]]:
        """Find conflict-free slots for this student cohort."""
        free_slots = []
        for day in DEFAULT_DAYS:
            for start_time in DEFAULT_TIME_SLOTS:
                if self.is_slot_free(day, start_time, duration):
                    free_slots.append({"day": day, "start_time": start_time})
                    if len(free_slots) >= 5:
                        return free_slots
        return free_slots

    def handle_check_timetable_or_propose(
        self, payload: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle CHECK_TIMETABLE or PROPOSE performative from Coordinator."""
        course_id = payload.get("course_id", "")
        course_name = payload.get("course_name", course_id)
        day = payload.get("day", "")
        start_time = payload.get("start_time", "")
        duration = int(payload.get("duration", 1))

        is_valid, reason, alternatives = self.validate_timetable(
            day=day,
            start_time=start_time,
            duration=duration,
            course_id=course_id,
            course_name=course_name,
        )

        resp_payload = dict(payload)
        resp_payload["timestamp"] = ""

        if is_valid:
            resp_payload["status"] = "ACCEPTED"
            resp_payload["reason"] = "No timetable conflict"
            return ACCEPT, resp_payload
        else:
            resp_payload["status"] = "CONFLICT"
            resp_payload["reason"] = reason or REASON_TIMETABLE_OVERLAP
            resp_payload["counter_proposals"] = alternatives
            return CONFLICT, resp_payload

    def handle_confirm(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Commit slot to group's timetable locally upon confirmation."""
        course_id = payload.get("course_id", "")
        course_name = payload.get("course_name", course_id)
        day = payload.get("day", "")
        start_time = payload.get("start_time", "")
        duration = int(payload.get("duration", 1))

        slots = self.get_consecutive_slots(day, start_time, duration)
        if slots:
            for slot in slots:
                self.existing_timetable[(day, slot)] = course_name or course_id

        self.logger.info(
            f"StudentGroup {self.group_id} added {course_name or course_id} at {day} {start_time}"
        )
        resp_payload = dict(payload)
        resp_payload["status"] = "CONFIRMED"
        return ACCEPT, resp_payload

    def process_incoming_message(
        self, sender: Any, performative: str, payload: Dict[str, Any]
    ) -> Optional[Message]:
        """Process received message and build response."""
        p_upper = performative.upper()

        if p_upper in (CHECK_TIMETABLE, PROPOSE):
            resp_type, resp_payload = self.handle_check_timetable_or_propose(payload)
            return self.make_message(to=str(sender), performative=resp_type, payload=resp_payload)
        elif p_upper == CONFIRM:
            resp_type, resp_payload = self.handle_confirm(payload)
            return self.make_message(to=str(sender), performative=resp_type, payload=resp_payload)

        return None
