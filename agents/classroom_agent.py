"""Classroom Agent implementation for SPADE Multi-Agent System.

Represents an individual physical classroom or laboratory.
Maintains local state for room capacity, room type, availability, and active bookings.
Validates room allocation requests, rejects capacity/type violations, and suggests alternatives.
"""

from typing import Optional, List, Dict, Tuple, Set, Any, Union
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from .base_agent import BaseAgent
from .communication import (
    ALLOCATE,
    PROPOSE,
    ACCEPT,
    REJECT,
    COUNTER_PROPOSE,
    CONFLICT,
    CONFIRM,
    REASON_CAPACITY_INSUFFICIENT,
    REASON_ROOM_TYPE_MISMATCH,
    REASON_ROOM_OCCUPIED,
    SchedulingMessagePayload,
    parse_spade_message,
)
from scheduler.domain import TimeSlot, DEFAULT_DAYS, DEFAULT_TIME_SLOTS


class ClassroomReceiverBehaviour(CyclicBehaviour):
    """Cyclic behaviour for receiving and processing room allocation requests and confirmations."""

    async def run(self):
        msg = await self.receive(timeout=1.0)
        if msg:
            agent: "ClassroomAgent" = self.agent
            performative, payload = agent.record_received_message(msg)
            reply = agent.process_incoming_message(msg.sender, performative, payload)
            if reply:
                await self.send(reply)


class ClassroomAgent(BaseAgent):
    """Autonomous agent representing a physical room or laboratory."""

    def __init__(
        self,
        jid: str,
        password: Optional[str] = None,
        room_id: str = "R101",
        room_name: str = "Classroom 101",
        capacity: int = 40,
        room_type: str = "classroom",
        available_slots: Optional[List[Any]] = None,
        **kwargs,
    ):
        super().__init__(jid=jid, password=password, role="ClassroomAgent", **kwargs)

        self.room_id = room_id
        self.room_name = room_name
        self.capacity = capacity
        self.room_type = room_type.lower()

        # Available slots
        self.available_slots: Set[Tuple[str, str]] = set()
        if available_slots is not None:
            for s in available_slots:
                ts = TimeSlot.from_str_or_tuple(s)
                self.available_slots.add((ts.day, ts.time))
        else:
            for d in DEFAULT_DAYS:
                for t in DEFAULT_TIME_SLOTS:
                    self.available_slots.add((d, t))

        # Local knowledge of active room bookings: (day, time) -> course_id
        self.current_bookings: Dict[Tuple[str, str], str] = {}

    async def setup(self):
        """Register CyclicBehaviour on startup."""
        await super().setup()
        receiver = ClassroomReceiverBehaviour()
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

    def validate_room(
        self,
        day: str,
        start_time: str,
        duration: int = 1,
        enrollment: int = 0,
        requested_room_type: str = "classroom",
        course_id: str = "",
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
        """Validate if room satisfies capacity, room type, and slot availability."""
        # Check Capacity
        if self.capacity < enrollment:
            reason = (
                f"R{self.room_id.replace('R', '')} capacity {self.capacity} < enrollment {enrollment}"
                if "R" in self.room_id
                else f"Capacity {self.capacity} < enrollment {enrollment}"
            )
            return False, reason, []

        # Check Room Type
        req_type = requested_room_type.lower()
        if req_type != self.room_type:
            return (
                False,
                f"Room type mismatch: required {req_type}, room is {self.room_type}",
                [],
            )

        slots = self.get_consecutive_slots(day, start_time, duration)
        if not slots:
            return False, f"Invalid time/duration bounds: {day} {start_time}", []

        # Check Available Slots
        for slot in slots:
            if (day, slot) not in self.available_slots:
                return False, f"Room {self.room_id} unavailable at {day} {slot}", []

        # Check Double Booking / Occupied
        for slot in slots:
            if (day, slot) in self.current_bookings:
                existing = self.current_bookings[(day, slot)]
                return (
                    False,
                    f"Room {self.room_id} already occupied by {existing} at {day} {slot}",
                    self.find_free_slots(duration),
                )

        return True, None, []

    def is_slot_free(self, day: str, start_time: str, duration: int = 1) -> bool:
        """Check directly whether a room slot is free."""
        slots = self.get_consecutive_slots(day, start_time, duration)
        if not slots:
            return False
        for slot in slots:
            if (day, slot) not in self.available_slots:
                return False
            if (day, slot) in self.current_bookings:
                return False
        return True

    def find_free_slots(self, duration: int = 1) -> List[Dict[str, Any]]:
        """Find slots when this room is unoccupied."""
        free_slots = []
        for day in DEFAULT_DAYS:
            for start_time in DEFAULT_TIME_SLOTS:
                if self.is_slot_free(day, start_time, duration):
                    free_slots.append({"day": day, "start_time": start_time})
                    if len(free_slots) >= 5:
                        return free_slots
        return free_slots

    def handle_allocate_or_propose(
        self, payload: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle ALLOCATE or PROPOSE performative from Coordinator."""
        course_id = payload.get("course_id", "")
        day = payload.get("day", "")
        start_time = payload.get("start_time", "")
        duration = int(payload.get("duration", 1))
        enrollment = int(payload.get("enrollment", 0))
        room_type = payload.get("room_type", "classroom")

        is_valid, reason, alternatives = self.validate_room(
            day=day,
            start_time=start_time,
            duration=duration,
            enrollment=enrollment,
            requested_room_type=room_type,
            course_id=course_id,
        )

        resp_payload = dict(payload)
        resp_payload["timestamp"] = ""

        if is_valid:
            resp_payload["status"] = "ACCEPTED"
            resp_payload["reason"] = f"R{self.room_id.replace('R', '')} capacity sufficient"
            return ACCEPT, resp_payload
        else:
            resp_payload["status"] = "REJECTED"
            resp_payload["reason"] = reason or REASON_CAPACITY_INSUFFICIENT
            resp_payload["counter_proposals"] = alternatives
            if "occupied" in (reason or "").lower() or "conflict" in (reason or "").lower():
                return CONFLICT, resp_payload
            return REJECT, resp_payload

    def handle_confirm(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Commit room booking locally upon receiving confirmation."""
        course_id = payload.get("course_id", "")
        day = payload.get("day", "")
        start_time = payload.get("start_time", "")
        duration = int(payload.get("duration", 1))

        slots = self.get_consecutive_slots(day, start_time, duration)
        if slots:
            for slot in slots:
                self.current_bookings[(day, slot)] = course_id

        self.logger.info(
            f"Classroom {self.room_id} booked for {course_id} at {day} {start_time}"
        )
        resp_payload = dict(payload)
        resp_payload["status"] = "CONFIRMED"
        return ACCEPT, resp_payload

    def process_incoming_message(
        self, sender: Any, performative: str, payload: Dict[str, Any]
    ) -> Optional[Message]:
        """Process received message and build response."""
        p_upper = performative.upper()

        if p_upper in (ALLOCATE, PROPOSE):
            resp_type, resp_payload = self.handle_allocate_or_propose(payload)
            return self.make_message(to=str(sender), performative=resp_type, payload=resp_payload)
        elif p_upper == CONFIRM:
            resp_type, resp_payload = self.handle_confirm(payload)
            return self.make_message(to=str(sender), performative=resp_type, payload=resp_payload)

        return None
