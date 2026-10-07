"""Constraint Satisfaction Problem (CSP) Scheduler Package.

Exports core solver classes and data structures for timetable scheduling.
"""

from .domain import (
    TimeSlot,
    Course,
    Faculty,
    Room,
    StudentGroup,
    ScheduleValue,
    Assignment,
    SchedulingProblem,
    generate_course_domain,
    DEFAULT_DAYS,
    DEFAULT_TIME_SLOTS,
)

from .constraints import (
    HardConstraintValidator,
    SoftConstraintEvaluator,
    UtilityWeights,
)

from .csp_solver import (
    CSPScheduler,
    SolverResult,
)

__all__ = [
    "TimeSlot",
    "Course",
    "Faculty",
    "Room",
    "StudentGroup",
    "ScheduleValue",
    "Assignment",
    "SchedulingProblem",
    "generate_course_domain",
    "DEFAULT_DAYS",
    "DEFAULT_TIME_SLOTS",
    "HardConstraintValidator",
    "SoftConstraintEvaluator",
    "UtilityWeights",
    "CSPScheduler",
    "SolverResult",
]
