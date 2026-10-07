"""Hard and Soft Constraints Implementation for the CSP Scheduling Engine.

Hard constraints (H1 to H8) MUST never be violated.
Soft constraints (S1 to S4) are scored using a configurable utility function
to guide domain value ordering and overall timetable optimization.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Set, Any
from .domain import (
    Course,
    Faculty,
    Room,
    StudentGroup,
    ScheduleValue,
    Assignment,
    SchedulingProblem,
    TimeSlot,
)


@dataclass
class UtilityWeights:
    """Configurable weights for the multi-criteria utility function."""
    w_faculty_preference: float = 1.0
    w_room_utilization: float = 0.8
    w_student_convenience: float = 0.5
    w_schedule_gaps: float = 0.6
    w_negotiation_cost: float = 0.0  # Zero placeholder for Phase 2; active in Phase 3


class HardConstraintValidator:
    """Validates hard constraints H1 to H8 for candidate assignments."""

    @staticmethod
    def get_assigned_slots(
        day: str, start_time: str, duration: int, problem: SchedulingProblem
    ) -> List[str]:
        """Get the list of individual hour slots for a given day, start time, and duration."""
        slots = problem.get_consecutive_slots(day, start_time, duration)
        return slots if slots is not None else []

    @classmethod
    def slots_overlap(
        cls,
        day1: str,
        start1: str,
        dur1: int,
        day2: str,
        start2: str,
        dur2: int,
        problem: SchedulingProblem,
    ) -> bool:
        """Check if two time blocks on the timetable overlap."""
        if day1 != day2:
            return False
        slots1 = set(cls.get_assigned_slots(day1, start1, dur1, problem))
        slots2 = set(cls.get_assigned_slots(day2, start2, dur2, problem))
        return bool(slots1.intersection(slots2))

    @classmethod
    def check_h1_faculty_double_booking(
        cls,
        course: Course,
        val: ScheduleValue,
        current_assignments: List[Assignment],
        problem: SchedulingProblem,
    ) -> Tuple[bool, Optional[str]]:
        """H1: A faculty member cannot teach two courses at the same time."""
        for a in current_assignments:
            if a.faculty_id == course.faculty_id:
                if cls.slots_overlap(
                    val.day, val.start_time, course.duration,
                    a.day, a.start_time, a.duration, problem
                ):
                    return False, f"H1: Faculty conflict - {course.faculty_id} already teaching {a.course_id} at {val.day} {val.start_time}"
        return True, None

    @classmethod
    def check_h2_classroom_double_booking(
        cls,
        course: Course,
        val: ScheduleValue,
        current_assignments: List[Assignment],
        problem: SchedulingProblem,
    ) -> Tuple[bool, Optional[str]]:
        """H2: A classroom cannot host two courses at the same time."""
        for a in current_assignments:
            if a.room_id == val.room_id:
                if cls.slots_overlap(
                    val.day, val.start_time, course.duration,
                    a.day, a.start_time, a.duration, problem
                ):
                    return False, f"H2: Classroom conflict - Room {val.room_id} already occupied by {a.course_id} at {val.day} {val.start_time}"
        return True, None

    @classmethod
    def check_h3_classroom_capacity(
        cls,
        course: Course,
        room: Room,
    ) -> Tuple[bool, Optional[str]]:
        """H3: Room capacity must be greater than or equal to course enrollment."""
        if room.capacity < course.enrollment:
            return False, f"H3: Capacity conflict - Room {room.id} capacity ({room.capacity}) < enrollment ({course.enrollment})"
        return True, None

    @classmethod
    def check_h4_room_type(
        cls,
        course: Course,
        room: Room,
    ) -> Tuple[bool, Optional[str]]:
        """H4: A laboratory course must use a laboratory room."""
        if course.is_lab and room.room_type != "lab":
            return False, f"H4: Room type conflict - Lab course {course.id} cannot use non-lab room {room.id}"
        return True, None

    @classmethod
    def check_h5_faculty_availability(
        cls,
        course: Course,
        val: ScheduleValue,
        problem: SchedulingProblem,
    ) -> Tuple[bool, Optional[str]]:
        """H5: A course cannot be scheduled when its faculty member is unavailable."""
        faculty = problem.get_faculty(course.faculty_id)
        if faculty and faculty.available_slots:
            slots = problem.get_consecutive_slots(val.day, val.start_time, course.duration)
            if slots is None:
                return False, f"H5: Faculty unavailable - slot {val.day} {val.start_time} is not a valid timetable slot"
            for slot in slots:
                if TimeSlot(val.day, slot) not in faculty.available_slots:
                    return False, f"H5: Faculty unavailable - {faculty.name} is not available at {val.day} {slot}"
        return True, None

    @classmethod
    def check_h6_student_group_conflict(
        cls,
        course: Course,
        val: ScheduleValue,
        current_assignments: List[Assignment],
        problem: SchedulingProblem,
    ) -> Tuple[bool, Optional[str]]:
        """H6: A student group cannot have two courses at the same time."""
        # Check against assignments in the current solving schedule
        for a in current_assignments:
            if a.student_group_id == course.student_group_id:
                if cls.slots_overlap(
                    val.day, val.start_time, course.duration,
                    a.day, a.start_time, a.duration, problem
                ):
                    return False, f"H6: Student group conflict - Group {course.student_group_id} already has {a.course_id} at {val.day} {val.start_time}"

        # Check against student group's pre-existing schedule if present
        sg = problem.get_student_group(course.student_group_id)
        if sg and sg.existing_schedule:
            candidate_slots = set(cls.get_assigned_slots(val.day, val.start_time, course.duration, problem))
            for item in sg.existing_schedule:
                if item.get("day") == val.day:
                    exist_start = item.get("time", item.get("start_time"))
                    exist_dur = int(item.get("duration", 1))
                    exist_slots = set(cls.get_assigned_slots(val.day, exist_start, exist_dur, problem))
                    if candidate_slots.intersection(exist_slots):
                        return False, f"H6: Pre-existing schedule conflict for student group {sg.id} at {val.day} {val.start_time}"

        return True, None

    @classmethod
    def check_h7_and_h8_valid_time_slot_and_duration(
        cls,
        course: Course,
        val: ScheduleValue,
        problem: SchedulingProblem,
    ) -> Tuple[bool, Optional[str]]:
        """H7 & H8: Course fits inside timetable slot bounds and maintains consecutive duration."""
        slots = problem.get_consecutive_slots(val.day, val.start_time, course.duration)
        if slots is None or len(slots) < course.duration:
            return False, f"H7/H8: Slot range overflow - {course.id} duration {course.duration} exceeds schedule boundaries at {val.start_time}"
        return True, None

    @classmethod
    def is_consistent(
        cls,
        course: Course,
        val: ScheduleValue,
        current_assignments: List[Assignment],
        problem: SchedulingProblem,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate all hard constraints H1 to H8 simultaneously.
        Returns (True, None) if consistent, or (False, reason) if any constraint fails.
        """
        room = problem.get_room(val.room_id)
        if not room:
            return False, f"Room {val.room_id} not found"

        # H7 & H8: Valid Time Slot and Duration Bounds
        ok, reason = cls.check_h7_and_h8_valid_time_slot_and_duration(course, val, problem)
        if not ok:
            return False, reason

        # H3: Room Capacity
        ok, reason = cls.check_h3_classroom_capacity(course, room)
        if not ok:
            return False, reason

        # H4: Room Type
        ok, reason = cls.check_h4_room_type(course, room)
        if not ok:
            return False, reason

        # H5: Faculty Availability
        ok, reason = cls.check_h5_faculty_availability(course, val, problem)
        if not ok:
            return False, reason

        # H1: Faculty Double Booking
        ok, reason = cls.check_h1_faculty_double_booking(course, val, current_assignments, problem)
        if not ok:
            return False, reason

        # H2: Classroom Double Booking
        ok, reason = cls.check_h2_classroom_double_booking(course, val, current_assignments, problem)
        if not ok:
            return False, reason

        # H6: Student Group Conflict
        ok, reason = cls.check_h6_student_group_conflict(course, val, current_assignments, problem)
        if not ok:
            return False, reason

        return True, None


class SoftConstraintEvaluator:
    """Calculates soft constraint scores and assignment utility."""

    @staticmethod
    def score_faculty_preference(
        course: Course,
        val: ScheduleValue,
        problem: SchedulingProblem,
    ) -> float:
        """S1: Faculty preferred slots (Returns 1.0 if in preferred slots, 0.0 otherwise)."""
        faculty = problem.get_faculty(course.faculty_id)
        if not faculty or not faculty.preferred_slots:
            return 0.5  # Neutral if faculty has no specific preferences
        slots = problem.get_consecutive_slots(val.day, val.start_time, course.duration)
        if not slots:
            return 0.0
        preferred_count = sum(
            1 for s in slots if TimeSlot(val.day, s) in faculty.preferred_slots
        )
        return preferred_count / len(slots)

    @staticmethod
    def score_room_utilization(
        course: Course,
        val: ScheduleValue,
        problem: SchedulingProblem,
    ) -> float:
        """
        S3: Room utilization efficiency.
        Ideal ratio is enrollment / capacity close to 1.0 (without exceeding 1.0).
        Penalizes severe under-utilization (e.g., 10 students in a 100-seat lecture hall).
        """
        room = problem.get_room(val.room_id)
        if not room or room.capacity <= 0:
            return 0.0
        if course.enrollment > room.capacity:
            return 0.0
        ratio = course.enrollment / room.capacity
        # Return utilization ratio directly (0.0 to 1.0)
        return max(0.0, min(1.0, ratio))

    @staticmethod
    def score_student_gaps(
        course: Course,
        val: ScheduleValue,
        current_assignments: List[Assignment],
        problem: SchedulingProblem,
    ) -> float:
        """
        S2: Penalize gaps between classes for the same student group on the same day.
        Returns a penalty score from 0.0 (no gaps / adjacent or only class) to 1.0 (large isolated gaps).
        """
        same_group_same_day = [
            a for a in current_assignments
            if a.student_group_id == course.student_group_id and a.day == val.day
        ]
        if not same_group_same_day:
            return 0.0  # First class of the day, no gap created yet

        candidate_start_idx = (
            problem.time_slots.index(val.start_time)
            if val.start_time in problem.time_slots else 0
        )
        candidate_end_idx = candidate_start_idx + course.duration

        min_gap = 999
        for a in same_group_same_day:
            if a.start_time in problem.time_slots:
                a_start_idx = problem.time_slots.index(a.start_time)
                a_end_idx = a_start_idx + a.duration
                if candidate_start_idx >= a_end_idx:
                    gap = candidate_start_idx - a_end_idx
                elif a_start_idx >= candidate_end_idx:
                    gap = a_start_idx - candidate_end_idx
                else:
                    gap = 0
                if gap < min_gap:
                    min_gap = gap

        # Convert gap hours into a penalty score (0 gap -> 0 penalty, 3+ gap -> 1.0 penalty)
        return min(1.0, min_gap / 4.0)

    @classmethod
    def evaluate_assignment_utility(
        cls,
        course: Course,
        val: ScheduleValue,
        current_assignments: List[Assignment],
        problem: SchedulingProblem,
        weights: Optional[UtilityWeights] = None,
    ) -> float:
        """
        Calculates multi-criteria utility score for a candidate assignment:
        Utility = w1(Faculty Pref) + w2(Room Util) + w3(Student Convenience) - w4(Gaps) - w5(Negotiation Cost)
        """
        w = weights or UtilityWeights()
        fac_pref = cls.score_faculty_preference(course, val, problem)
        room_util = cls.score_room_utilization(course, val, problem)
        gap_penalty = cls.score_student_gaps(course, val, current_assignments, problem)
        student_conv = 1.0 - gap_penalty

        utility = (
            (w.w_faculty_preference * fac_pref)
            + (w.w_room_utilization * room_util)
            + (w.w_student_convenience * student_conv)
            - (w.w_schedule_gaps * gap_penalty)
            - (w.w_negotiation_cost * 0.0)
        )
        return round(utility, 4)
