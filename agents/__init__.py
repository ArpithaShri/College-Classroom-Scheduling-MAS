"""Multi-Agent System (SPADE) Package.

Exports the five core domain agents, the base agent class, and communication utilities.
"""

from .communication import (
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
    agent_logger,
)

from .base_agent import BaseAgent
from .department_agent import DepartmentAgent
from .faculty_agent import FacultyAgent
from .classroom_agent import ClassroomAgent
from .student_group_agent import StudentGroupAgent
from .timetable_coordinator import TimetableCoordinatorAgent

__all__ = [
    "BaseAgent",
    "DepartmentAgent",
    "FacultyAgent",
    "ClassroomAgent",
    "StudentGroupAgent",
    "TimetableCoordinatorAgent",
    "REQUEST",
    "PROPOSE",
    "ACCEPT",
    "REJECT",
    "COUNTER_PROPOSE",
    "CONFLICT",
    "RESCHEDULE",
    "ALLOCATE",
    "CHECK_TIMETABLE",
    "CONFIRM",
    "FINAL_ACCEPT",
    "SchedulingMessagePayload",
    "create_spade_message",
    "parse_spade_message",
    "create_template_for",
    "agent_logger",
]
