"""Domain models and data representation for the CSP Scheduling Engine.

Defines dataclasses for Courses, Faculty, Classrooms, Student Groups,
Time Slots, Assignments, and Problem Definitions, as well as domain generation utilities.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set, Any


# Standard weekday schedule
DEFAULT_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# Standard 1-hour time slots from 09:00 to 17:00
DEFAULT_TIME_SLOTS = [
    "09:00",
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
]


@dataclass(frozen=True)
class TimeSlot:
    """Represents a specific day and start time."""
    day: str
    time: str

    def __str__(self) -> str:
        return f"{self.day} {self.time}"

    @classmethod
    def from_str_or_tuple(cls, val: Any) -> "TimeSlot":
        """Convert a tuple ('Monday', '09:00') or string 'Monday 09:00' to TimeSlot."""
        if isinstance(val, TimeSlot):
            return val
        if isinstance(val, (tuple, list)) and len(val) == 2:
            return cls(day=str(val[0]), time=str(val[1]))
        if isinstance(val, str):
            parts = val.split()
            if len(parts) == 2:
                return cls(day=parts[0], time=parts[1])
        raise ValueError(f"Cannot parse TimeSlot from {val}")


@dataclass
class Course:
    """Represents an academic course/subject to be scheduled."""
    id: str
    name: str
    faculty_id: str
    student_group_id: str
    enrollment: int
    duration: int = 1  # Duration in hours / slots
    is_lab: bool = False
    preferred_days: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Course":
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            faculty_id=data["faculty_id"],
            student_group_id=data["student_group_id"],
            enrollment=int(data.get("enrollment", 0)),
            duration=int(data.get("duration", 1)),
            is_lab=bool(data.get("is_lab", False)),
            preferred_days=list(data.get("preferred_days", [])),
        )


@dataclass
class Faculty:
    """Represents an instructor teaching one or more courses."""
    id: str
    name: str
    available_slots: List[TimeSlot] = field(default_factory=list)
    preferred_slots: List[TimeSlot] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Faculty":
        avail = [
            TimeSlot.from_str_or_tuple(s) for s in data.get("available_slots", [])
        ]
        pref = [
            TimeSlot.from_str_or_tuple(s) for s in data.get("preferred_slots", [])
        ]
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            available_slots=avail,
            preferred_slots=pref,
        )


@dataclass
class Room:
    """Represents a physical classroom or specialized laboratory."""
    id: str
    name: str
    capacity: int
    room_type: str = "classroom"  # "classroom" or "lab"
    available_slots: List[TimeSlot] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Room":
        avail = [
            TimeSlot.from_str_or_tuple(s) for s in data.get("available_slots", [])
        ]
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            capacity=int(data.get("capacity", 0)),
            room_type=data.get("room_type", "classroom").lower(),
            available_slots=avail,
        )


@dataclass
class StudentGroup:
    """Represents a cohort/batch/section of students taking common courses."""
    id: str
    name: str
    existing_schedule: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudentGroup":
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            existing_schedule=list(data.get("existing_schedule", [])),
        )


@dataclass(frozen=True)
class ScheduleValue:
    """Represents a concrete domain value (room, day, start_time) for a course assignment."""
    room_id: str
    day: str
    start_time: str

    def __str__(self) -> str:
        return f"{self.day} {self.start_time} in Room {self.room_id}"


@dataclass
class Assignment:
    """Represents a scheduled course with its assigned room, day, and time."""
    course_id: str
    course_name: str
    faculty_id: str
    student_group_id: str
    room_id: str
    day: str
    start_time: str
    duration: int
    is_lab: bool = False
    enrollment: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "course_name": self.course_name,
            "faculty_id": self.faculty_id,
            "student_group_id": self.student_group_id,
            "room_id": self.room_id,
            "day": self.day,
            "start_time": self.start_time,
            "duration": self.duration,
            "is_lab": self.is_lab,
            "enrollment": self.enrollment,
        }


@dataclass
class SchedulingProblem:
    """Encapsulates all input data, parameters, and candidate slots for a scheduling problem."""
    courses: List[Course] = field(default_factory=list)
    faculty: List[Faculty] = field(default_factory=list)
    rooms: List[Room] = field(default_factory=list)
    student_groups: List[StudentGroup] = field(default_factory=list)
    days: List[str] = field(default_factory=lambda: list(DEFAULT_DAYS))
    time_slots: List[str] = field(default_factory=lambda: list(DEFAULT_TIME_SLOTS))

    # Lookup helpers
    _course_map: Dict[str, Course] = field(init=False, default_factory=dict)
    _faculty_map: Dict[str, Faculty] = field(init=False, default_factory=dict)
    _room_map: Dict[str, Room] = field(init=False, default_factory=dict)
    _student_group_map: Dict[str, StudentGroup] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self.rebuild_indices()

    def rebuild_indices(self):
        """Build dictionary lookups for fast retrieval."""
        self._course_map = {c.id: c for c in self.courses}
        self._faculty_map = {f.id: f for f in self.faculty}
        self._room_map = {r.id: r for r in self.rooms}
        self._student_group_map = {sg.id: sg for sg in self.student_groups}

    def get_course(self, course_id: str) -> Optional[Course]:
        return self._course_map.get(course_id)

    def get_faculty(self, faculty_id: str) -> Optional[Faculty]:
        return self._faculty_map.get(faculty_id)

    def get_room(self, room_id: str) -> Optional[Room]:
        return self._room_map.get(room_id)

    def get_student_group(self, group_id: str) -> Optional[StudentGroup]:
        return self._student_group_map.get(group_id)

    def get_consecutive_slots(self, day: str, start_time: str, duration: int) -> Optional[List[str]]:
        """Return the list of consecutive time slot strings if they fit in the day, or None."""
        if start_time not in self.time_slots:
            return None
        start_idx = self.time_slots.index(start_time)
        if start_idx + duration > len(self.time_slots):
            return None
        return self.time_slots[start_idx : start_idx + duration]

    @classmethod
    def from_dict_data(
        cls,
        courses_data: Optional[List[Dict[str, Any]]] = None,
        faculty_data: Optional[List[Dict[str, Any]]] = None,
        rooms_data: Optional[List[Dict[str, Any]]] = None,
        student_groups_data: Optional[List[Dict[str, Any]]] = None,
        days: Optional[List[str]] = None,
        time_slots: Optional[List[str]] = None,
        courses: Optional[List[Dict[str, Any]]] = None,
        faculty: Optional[List[Dict[str, Any]]] = None,
        rooms: Optional[List[Dict[str, Any]]] = None,
        student_groups: Optional[List[Dict[str, Any]]] = None,
    ) -> "SchedulingProblem":
        """Factory method to construct SchedulingProblem from list of dicts."""
        c_list = courses_data if courses_data is not None else (courses or [])
        f_list = faculty_data if faculty_data is not None else (faculty or [])
        r_list = rooms_data if rooms_data is not None else (rooms or [])
        sg_list = student_groups_data if student_groups_data is not None else (student_groups or [])

        return cls(
            courses=[Course.from_dict(c) for c in c_list],
            faculty=[Faculty.from_dict(f) for f in f_list],
            rooms=[Room.from_dict(r) for r in r_list],
            student_groups=[StudentGroup.from_dict(sg) for sg in sg_list],
            days=days or list(DEFAULT_DAYS),
            time_slots=time_slots or list(DEFAULT_TIME_SLOTS),
        )


def generate_course_domain(
    course: Course,
    problem: SchedulingProblem,
) -> List[ScheduleValue]:
    """
    Generate initial possible domain values for a course.
    
    A domain value is a ScheduleValue(room_id, day, start_time).
    Filters out obvious static incompatibilities (e.g. room capacity < course enrollment,
    lab requirement mismatch, or duration exceeding day limits).
    """
    domain: List[ScheduleValue] = []
    
    faculty = problem.get_faculty(course.faculty_id)
    faculty_available_slots = (
        set(faculty.available_slots) if (faculty and faculty.available_slots) else None
    )

    for room in problem.rooms:
        # H3: Room capacity check
        if room.capacity < course.enrollment:
            continue

        # H4: Room type check
        # A lab course MUST use a lab room. A normal course can use a classroom or a lab if needed.
        if course.is_lab and room.room_type != "lab":
            continue

        room_available_slots = (
            set(room.available_slots) if room.available_slots else None
        )

        for day in problem.days:
            # If course specifies preferred days and we want initial filter (optional),
            # but we allow all problem days so search doesn't artificially fail.
            for start_time in problem.time_slots:
                # H7 & H8: Course duration must fit inside the timetable
                slots = problem.get_consecutive_slots(day, start_time, course.duration)
                if slots is None:
                    continue

                # Check if all slots in duration are within faculty availability if specified
                if faculty_available_slots is not None:
                    all_avail = all(
                        TimeSlot(day, s) in faculty_available_slots for s in slots
                    )
                    if not all_avail:
                        continue

                # Check if all slots in duration are within room availability if specified
                if room_available_slots is not None:
                    all_room_avail = all(
                        TimeSlot(day, s) in room_available_slots for s in slots
                    )
                    if not all_room_avail:
                        continue

                domain.append(ScheduleValue(room_id=room.id, day=day, start_time=start_time))

    return domain
