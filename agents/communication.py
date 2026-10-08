"""Communication Protocol and Message Serialization for SPADE Agents.

Defines standardized performatives, structured JSON payload schemas,
and a central message logging facility for multi-agent interaction.
"""

import json
import uuid
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union

from spade.message import Message
from spade.template import Template

logger = logging.getLogger("agents.communication")

# Standard SPADE Message Performatives / Types
REQUEST = "REQUEST"
PROPOSE = "PROPOSE"
ACCEPT = "ACCEPT"
REJECT = "REJECT"
COUNTER_PROPOSE = "COUNTER_PROPOSE"
CONFLICT = "CONFLICT"
RESCHEDULE = "RESCHEDULE"
ALLOCATE = "ALLOCATE"
CHECK_TIMETABLE = "CHECK_TIMETABLE"
CONFIRM = "CONFIRM"
FINAL_ACCEPT = "FINAL_ACCEPT"

ALL_PERFORMATIVES = [
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

# Standard Reason Codes
REASON_FACULTY_UNAVAILABLE = "FACULTY_UNAVAILABLE"
REASON_FACULTY_DOUBLE_BOOKED = "FACULTY_DOUBLE_BOOKED"
REASON_CAPACITY_INSUFFICIENT = "CAPACITY_INSUFFICIENT"
REASON_ROOM_TYPE_MISMATCH = "ROOM_TYPE_MISMATCH"
REASON_ROOM_OCCUPIED = "ROOM_OCCUPIED"
REASON_TIMETABLE_OVERLAP = "TIMETABLE_OVERLAP"
REASON_NO_FEASIBLE_SLOT = "NO_FEASIBLE_SLOT"


@dataclass
class SchedulingMessagePayload:
    """Structured payload for all inter-agent messages."""

    type: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    course_id: str = ""
    course_name: str = ""
    faculty_id: str = ""
    student_group_id: str = ""
    room_id: Optional[str] = None
    day: Optional[str] = None
    start_time: Optional[str] = None
    duration: int = 1
    enrollment: int = 0
    room_type: str = "classroom"
    is_lab: bool = False
    status: Optional[str] = None
    reason: Optional[str] = None
    counter_proposals: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert payload to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize payload to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchedulingMessagePayload":
        """Instantiate payload from dictionary."""
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> "SchedulingMessagePayload":
        """Deserialize payload from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


def create_spade_message(
    to: str,
    sender: Optional[str] = None,
    performative: str = PROPOSE,
    payload: Optional[Union[Dict[str, Any], SchedulingMessagePayload]] = None,
    thread: Optional[str] = None,
) -> Message:
    """Construct a standardized SPADE Message with structured JSON body and metadata."""
    msg = Message(to=str(to))
    if sender:
        msg.sender = str(sender)

    msg.set_metadata("performative", str(performative).upper())
    msg.set_metadata("ontology", "classroom-scheduling")
    msg.set_metadata("language", "json")

    if thread:
        msg.thread = str(thread)

    if payload is None:
        payload_dict = {
            "type": performative,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
    elif isinstance(payload, SchedulingMessagePayload):
        payload_dict = payload.to_dict()
    elif isinstance(payload, dict):
        payload_dict = dict(payload)
        if "type" not in payload_dict:
            payload_dict["type"] = performative
        if "timestamp" not in payload_dict:
            payload_dict["timestamp"] = datetime.now().strftime("%H:%M:%S")
    else:
        raise ValueError(f"Unsupported payload type: {type(payload)}")

    msg.body = json.dumps(payload_dict)
    return msg


def parse_spade_message(msg: Message) -> Tuple[str, Dict[str, Any]]:
    """Extract the performative and parsed JSON dictionary from a SPADE message."""
    performative = msg.get_metadata("performative") or "UNKNOWN"
    body = msg.body or "{}"
    try:
        data = json.loads(body)
    except Exception as e:
        logger.warning(f"Failed to decode message body as JSON: {e}. Raw body: {body}")
        data = {"raw": body}

    if "type" in data and performative == "UNKNOWN":
        performative = data["type"]

    return performative.upper(), data


def create_template_for(performative: Optional[str] = None) -> Template:
    """Create a SPADE Template for matching messages with a specific performative."""
    template = Template()
    template.set_metadata("ontology", "classroom-scheduling")
    if performative:
        template.set_metadata("performative", performative.upper())
    return template


class AgentMessageLogger:
    """In-memory and stream message logger for MAS interaction auditing."""

    def __init__(self):
        self._logs: List[Dict[str, Any]] = []

    def log_message(
        self,
        sender: str,
        receiver: str,
        message_type: str,
        course: str = "",
        payload: Optional[Dict[str, Any]] = None,
        status: str = "",
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an inter-agent message interaction."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "sender": str(sender),
            "receiver": str(receiver),
            "message_type": str(message_type).upper(),
            "course": course or (payload.get("course_id", "") if payload else ""),
            "payload": payload or {},
            "status": status,
            "reason": reason or (payload.get("reason") if payload else None),
        }
        self._logs.append(entry)
        return entry

    def get_logs(self) -> List[Dict[str, Any]]:
        """Return a copy of all recorded log entries."""
        return list(self._logs)

    def clear(self):
        """Clear all stored logs."""
        self._logs.clear()

    @staticmethod
    def format_entry(entry: Dict[str, Any]) -> str:
        """Format a single log entry into human-readable multi-line string."""
        ts = entry.get("timestamp", "")
        sender = entry.get("sender", "").split("@")[0]
        receiver = entry.get("receiver", "").split("@")[0]
        mtype = entry.get("message_type", "")
        course = entry.get("course", "")
        reason = entry.get("reason", "")
        payload = entry.get("payload", {})

        lines = [
            f"[{ts}]",
            f"{sender} → {receiver}",
            f"{mtype}",
        ]
        if course:
            lines.append(f"Course: {course}")
        if "day" in payload and "start_time" in payload and payload["day"]:
            lines.append(f"Slot: {payload['day']} {payload['start_time']}")
        if "room_id" in payload and payload["room_id"]:
            lines.append(f"Room: {payload['room_id']}")
        if reason:
            lines.append(f"Reason: {reason}")

        return "\n".join(lines)


# Global singleton logger instance for multi-agent execution
agent_logger = AgentMessageLogger()
