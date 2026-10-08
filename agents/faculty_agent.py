"""Faculty Agent implementation for SPADE Multi-Agent System.

Manages individual faculty availability, preferences, and teaching workload.
Validates proposed slots, detects double booking, accepts/rejects slots,
and generates counter-proposals.
"""

from typing import Optional, List, Dict, Tuple, Set, Any, Union
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from .base_agent import BaseAgent
from .communication import (
    PROPOSE,
    ACCEPT,
    REJECT,
    COUNTER_PROPOSE,
    CONFLICT,
    CONFIRM,
    REASON_FACULTY_UNAVAILABLE,
    REASON_FACULTY_DOUBLE_BOOKED,
    SchedulingMessagePayload,
    parse_spade_message,
    create_template_for,
)
from scheduler.domain import TimeSlot, DEFAULT_DAYS, DEFAULT_TIME_SLOTS


class FacultyReceiverBehaviour(CyclicBehaviour):
    """Cyclic behaviour for receiving and processing proposals, allocations, and confirmations."""

    async def run(self):
        msg = await self.receive(timeout=1.0)
        if msg:
            agent: "FacultyAgent" = self.agent
            performative, payload = agent.record_received_message(msg)
            reply = agent.process_incoming_message(msg.sender, performative, payload)
            if reply:
                await self.send(reply)


class FacultyAgent(BaseAgent):
    """Autonomous agent representing an instructor in the scheduling system."""

    def __init__(
        self,
        jid: str,
        password: Optional[str] = None,
        faculty_id: str = "F001",
        faculty_name: str = "Faculty Member",
        available_slots: Optional[List[Any]] = None,
        preferred_slots: Optional[List[Any]] = None,
        max_daily_hours: int = 6,
        max_consecutive_hours: int = 3,
        **kwargs,
    ):
        super().__init__(jid=jid, password=password, role="FacultyAgent", **kwargs)

        self.faculty_id = faculty_id
        self.faculty_name = faculty_name
        self.max_daily_hours = max_daily_hours
        self.max_consecutive_hours = max_consecutive_hours

        # Convert available slots to normalized set of (day, time)
        self.available_slots: Set[Tuple[str, str]] = set()
        if available_slots is not None:
            for s in available_slots:
                ts = TimeSlot.from_str_or_tuple(s)
                self.available_slots.add((ts.day, ts.time))
        else:
            # Default to all standard slots if unspecified
            for d in DEFAULT_DAYS:
                for t in DEFAULT_TIME_SLOTS:
                    self.available_slots.add((d, t))

        # Preferred slots
        self.preferred_slots: List[Tuple[str, str]] = []
        if preferred_slots:
            for s in preferred_slots:
                ts = TimeSlot.from_str_or_tuple(s)
                self.preferred_slots.append((ts.day, ts.time))

        # Local knowledge of booked assignments: (day, time) -> course_id
        self.existing_assignments: Dict[Tuple[str, str], str] = {}

    async def setup(self):
        """Register CyclicBehaviour on startup."""
        await super().setup()
        receiver = FacultyReceiverBehaviour()
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

    def validate_slot(
        self, day: str, start_time: str, duration: int = 1, course_id: str = ""
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
        """Validate if faculty is available and free for the proposed slot.

        Returns (is_valid, reason, alternative_slots).
        """
        slots = self.get_consecutive_slots(day, start_time, duration)
        if not slots:
            return (
                False,
                f"Invalid slot time/duration: {day} {start_time} for {duration}h",
                self.find_alternative_slots(duration),
            )

        # Check availability
        for slot in slots:
            if (day, slot) not in self.available_slots:
                return (
                    False,
                    f"Faculty {self.faculty_id} unavailable at {day} {slot}",
                    self.find_alternative_slots(duration),
                )

        # Check double booking
        for slot in slots:
            if (day, slot) in self.existing_assignments:
                existing = self.existing_assignments[(day, slot)]
                return (
                    False,
                    f"Faculty {self.faculty_id} double booked (teaching {existing} at {day} {slot})",
                    self.find_alternative_slots(duration),
                )

        # Check max daily hours
        daily_count = sum(
            1 for (d, _) in self.existing_assignments.keys() if d == day
        )
        if daily_count + duration > self.max_daily_hours:
            return (
                False,
                f"Faculty daily limit ({self.max_daily_hours}h) exceeded on {day}",
                self.find_alternative_slots(duration),
            )

        return True, None, []

    def is_slot_free(self, day: str, start_time: str, duration: int = 1) -> bool:
        """Check directly whether a slot is free of faculty conflicts."""
        slots = self.get_consecutive_slots(day, start_time, duration)
        if not slots:
            return False
        for slot in slots:
            if (day, slot) not in self.available_slots:
                return False
            if (day, slot) in self.existing_assignments:
                return False
        daily_count = sum(1 for (d, _) in self.existing_assignments.keys() if d == day)
        if daily_count + duration > self.max_daily_hours:
            return False
        return True

    def find_alternative_slots(self, duration: int = 1) -> List[Dict[str, Any]]:
        """Find free available slots for this faculty."""
        alternatives = []
        for day in DEFAULT_DAYS:
            for start_time in DEFAULT_TIME_SLOTS:
                if self.is_slot_free(day, start_time, duration):
                    alternatives.append({"day": day, "start_time": start_time})
                    if len(alternatives) >= 5:
                        return alternatives
        return alternatives

    def handle_propose(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle a PROPOSE performative from Coordinator."""
        course_id = payload.get("course_id", "")
        day = payload.get("day", "")
        start_time = payload.get("start_time", "")
        duration = int(payload.get("duration", 1))

        is_valid, reason, alternatives = self.validate_slot(
            day, start_time, duration, course_id
        )

        resp_payload = dict(payload)
        resp_payload["timestamp"] = ""

        if is_valid:
            resp_payload["status"] = "ACCEPTED"
            resp_payload["reason"] = f"Faculty {self.faculty_id} available"
            return ACCEPT, resp_payload
        else:
            resp_payload["status"] = "REJECTED"
            resp_payload["reason"] = reason or REASON_FACULTY_UNAVAILABLE
            resp_payload["counter_proposals"] = alternatives
            if alternatives:
                return COUNTER_PROPOSE, resp_payload
            return REJECT, resp_payload

    def handle_confirm(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle final CONFIRM message and commit the schedule locally."""
        course_id = payload.get("course_id", "")
        day = payload.get("day", "")
        start_time = payload.get("start_time", "")
        duration = int(payload.get("duration", 1))

        slots = self.get_consecutive_slots(day, start_time, duration)
        if slots:
            for slot in slots:
                self.existing_assignments[(day, slot)] = course_id

        self.logger.info(
            f"Faculty {self.faculty_id} confirmed assignment for {course_id} at {day} {start_time}"
        )
        resp_payload = dict(payload)
        resp_payload["status"] = "CONFIRMED"
        return ACCEPT, resp_payload

    def process_incoming_message(
        self, sender: Any, performative: str, payload: Dict[str, Any]
    ) -> Optional[Message]:
        """Process received message and build SPADE response."""
        p_upper = performative.upper()

        if p_upper == PROPOSE:
            resp_type, resp_payload = self.handle_propose(payload)
            return self.make_message(to=str(sender), performative=resp_type, payload=resp_payload)
        elif p_upper == CONFIRM:
            resp_type, resp_payload = self.handle_confirm(payload)
            return self.make_message(to=str(sender), performative=resp_type, payload=resp_payload)

        return None
