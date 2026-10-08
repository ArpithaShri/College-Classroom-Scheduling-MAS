"""SQLAlchemy database models for College Classroom Scheduling System.

Defines tables for Departments, Faculty, Classrooms/Labs, Student Groups, Courses,
Timetables, Schedule Assignments, and MAS Communication Audit Logs.
"""

from datetime import datetime, timezone
import json
from typing import Dict, Any, List, Optional

def utc_now():
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

from database.db import db
from scheduler.domain import (
    Course as DomainCourse,
    Faculty as DomainFaculty,
    Room as DomainRoom,
    StudentGroup as DomainStudentGroup,
    Assignment as DomainAssignment,
    TimeSlot,
)


class Department(db.Model):
    """Academic Department entity."""

    __tablename__ = "departments"

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    faculty_members = db.relationship("Faculty", back_populates="department", cascade="all, delete-orphan")
    courses = db.relationship("Course", back_populates="department", cascade="all, delete-orphan")
    student_groups = db.relationship("StudentGroup", back_populates="department", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Department {self.id}: {self.name}>"


class Faculty(db.Model):
    """Instructor / Faculty entity."""

    __tablename__ = "faculty"

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=True)
    department_id = db.Column(db.String(50), db.ForeignKey("departments.id"), nullable=True)
    max_daily_hours = db.Column(db.Integer, default=6)
    max_consecutive_hours = db.Column(db.Integer, default=3)
    available_slots_json = db.Column(db.Text, default="[]")  # JSON list of [day, time]
    preferred_slots_json = db.Column(db.Text, default="[]")  # JSON list of [day, time]
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    department = db.relationship("Department", back_populates="faculty_members")
    courses = db.relationship("Course", back_populates="faculty")
    assignments = db.relationship("Assignment", back_populates="faculty")

    @property
    def available_slots(self) -> List[List[str]]:
        try:
            return json.loads(self.available_slots_json or "[]")
        except Exception:
            return []

    @available_slots.setter
    def available_slots(self, slots: List[Any]):
        formatted = []
        for s in slots:
            if isinstance(s, (list, tuple)):
                formatted.append([str(s[0]), str(s[1])])
            elif hasattr(s, "day") and hasattr(s, "time"):
                formatted.append([str(s.day), str(s.time)])
        self.available_slots_json = json.dumps(formatted)

    @property
    def preferred_slots(self) -> List[List[str]]:
        try:
            return json.loads(self.preferred_slots_json or "[]")
        except Exception:
            return []

    @preferred_slots.setter
    def preferred_slots(self, slots: List[Any]):
        formatted = []
        for s in slots:
            if isinstance(s, (list, tuple)):
                formatted.append([str(s[0]), str(s[1])])
            elif hasattr(s, "day") and hasattr(s, "time"):
                formatted.append([str(s.day), str(s.time)])
        self.preferred_slots_json = json.dumps(formatted)

    def to_domain(self) -> DomainFaculty:
        return DomainFaculty(
            id=self.id,
            name=self.name,
            available_slots=[TimeSlot(s[0], s[1]) for s in self.available_slots],
            preferred_slots=[TimeSlot(s[0], s[1]) for s in self.preferred_slots],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "department_id": self.department_id,
            "max_daily_hours": self.max_daily_hours,
            "max_consecutive_hours": self.max_consecutive_hours,
            "available_slots": self.available_slots,
            "preferred_slots": self.preferred_slots,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Faculty {self.id}: {self.name}>"


class Room(db.Model):
    """Classroom or Laboratory entity."""

    __tablename__ = "rooms"

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    building = db.Column(db.String(100), nullable=True)
    capacity = db.Column(db.Integer, nullable=False, default=40)
    room_type = db.Column(db.String(30), nullable=False, default="classroom")  # "classroom" or "lab"
    has_projector = db.Column(db.Boolean, default=True)
    available_slots_json = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    assignments = db.relationship("Assignment", back_populates="room")

    @property
    def available_slots(self) -> List[List[str]]:
        try:
            return json.loads(self.available_slots_json or "[]")
        except Exception:
            return []

    @available_slots.setter
    def available_slots(self, slots: List[Any]):
        formatted = []
        for s in slots:
            if isinstance(s, (list, tuple)):
                formatted.append([str(s[0]), str(s[1])])
            elif hasattr(s, "day") and hasattr(s, "time"):
                formatted.append([str(s.day), str(s.time)])
        self.available_slots_json = json.dumps(formatted)

    def to_domain(self) -> DomainRoom:
        return DomainRoom(
            id=self.id,
            name=self.name,
            capacity=self.capacity,
            room_type=self.room_type.lower(),
            available_slots=[TimeSlot(s[0], s[1]) for s in self.available_slots],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "building": self.building,
            "capacity": self.capacity,
            "room_type": self.room_type,
            "has_projector": self.has_projector,
            "available_slots": self.available_slots,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Room {self.id}: {self.name} (Cap: {self.capacity}, Type: {self.room_type})>"


class StudentGroup(db.Model):
    """Student Cohort / Section entity."""

    __tablename__ = "student_groups"

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    department_id = db.Column(db.String(50), db.ForeignKey("departments.id"), nullable=True)
    size = db.Column(db.Integer, nullable=False, default=60)
    year_of_study = db.Column(db.Integer, default=1)
    commitments_json = db.Column(db.Text, default="[]")  # JSON list of [day, time]
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    department = db.relationship("Department", back_populates="student_groups")
    courses = db.relationship("Course", back_populates="student_group")
    assignments = db.relationship("Assignment", back_populates="student_group")

    @property
    def commitments(self) -> List[List[str]]:
        try:
            return json.loads(self.commitments_json or "[]")
        except Exception:
            return []

    @commitments.setter
    def commitments(self, slots: List[Any]):
        formatted = []
        for s in slots:
            if isinstance(s, (list, tuple)):
                formatted.append([str(s[0]), str(s[1])])
            elif hasattr(s, "day") and hasattr(s, "time"):
                formatted.append([str(s.day), str(s.time)])
        self.commitments_json = json.dumps(formatted)

    def to_domain(self) -> DomainStudentGroup:
        return DomainStudentGroup(
            id=self.id,
            name=self.name,
            existing_schedule=[],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "department_id": self.department_id,
            "size": self.size,
            "year_of_study": self.year_of_study,
            "commitments": self.commitments,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<StudentGroup {self.id}: {self.name} (Size: {self.size})>"


class Course(db.Model):
    """Academic Course / Subject entity."""

    __tablename__ = "courses"

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    department_id = db.Column(db.String(50), db.ForeignKey("departments.id"), nullable=True)
    faculty_id = db.Column(db.String(50), db.ForeignKey("faculty.id"), nullable=False)
    student_group_id = db.Column(db.String(50), db.ForeignKey("student_groups.id"), nullable=False)
    enrollment = db.Column(db.Integer, nullable=False, default=50)
    duration = db.Column(db.Integer, nullable=False, default=1)  # Duration in hours
    is_lab = db.Column(db.Boolean, default=False)
    preferred_days_json = db.Column(db.Text, default="[]")  # JSON list of days
    preferred_time = db.Column(db.String(20), nullable=True)
    preferred_room_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    department = db.relationship("Department", back_populates="courses")
    faculty = db.relationship("Faculty", back_populates="courses")
    student_group = db.relationship("StudentGroup", back_populates="courses")
    assignments = db.relationship("Assignment", back_populates="course")

    @property
    def preferred_days(self) -> List[str]:
        try:
            return json.loads(self.preferred_days_json or "[]")
        except Exception:
            return []

    @preferred_days.setter
    def preferred_days(self, days: List[str]):
        self.preferred_days_json = json.dumps(list(days))

    def to_domain(self) -> DomainCourse:
        return DomainCourse(
            id=self.id,
            name=self.name,
            faculty_id=self.faculty_id,
            student_group_id=self.student_group_id,
            enrollment=self.enrollment,
            duration=self.duration,
            is_lab=self.is_lab,
            preferred_days=self.preferred_days,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "department_id": self.department_id,
            "faculty_id": self.faculty_id,
            "student_group_id": self.student_group_id,
            "enrollment": self.enrollment,
            "duration": self.duration,
            "is_lab": self.is_lab,
            "preferred_days": self.preferred_days,
            "preferred_time": self.preferred_time,
            "preferred_room_id": self.preferred_room_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Course {self.id}: {self.name} (Faculty: {self.faculty_id}, Group: {self.student_group_id})>"


class Timetable(db.Model):
    """Timetable Session representing a complete schedule solution."""

    __tablename__ = "timetables"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False, default="Master Timetable")
    academic_term = db.Column(db.String(50), nullable=False, default="Fall 2026")
    status = db.Column(db.String(30), default="SCHEDULED")  # DRAFT, SCHEDULED, CONFLICT
    fitness_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    assignments = db.relationship("Assignment", back_populates="timetable", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "academic_term": self.academic_term,
            "status": self.status,
            "fitness_score": self.fitness_score,
            "assignments_count": len(self.assignments),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Timetable {self.id}: {self.name} ({self.status})>"


class Assignment(db.Model):
    """Individual scheduled slot assignment."""

    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timetable_id = db.Column(db.Integer, db.ForeignKey("timetables.id"), nullable=True)
    course_id = db.Column(db.String(50), db.ForeignKey("courses.id"), nullable=False)
    course_name = db.Column(db.String(150), nullable=False)
    faculty_id = db.Column(db.String(50), db.ForeignKey("faculty.id"), nullable=False)
    student_group_id = db.Column(db.String(50), db.ForeignKey("student_groups.id"), nullable=False)
    room_id = db.Column(db.String(50), db.ForeignKey("rooms.id"), nullable=False)
    day = db.Column(db.String(20), nullable=False)  # Monday - Friday
    start_time = db.Column(db.String(20), nullable=False)  # e.g. "10:00"
    duration = db.Column(db.Integer, nullable=False, default=1)
    is_lab = db.Column(db.Boolean, default=False)
    enrollment = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default="SCHEDULED")
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    timetable = db.relationship("Timetable", back_populates="assignments")
    course = db.relationship("Course", back_populates="assignments")
    faculty = db.relationship("Faculty", back_populates="assignments")
    student_group = db.relationship("StudentGroup", back_populates="assignments")
    room = db.relationship("Room", back_populates="assignments")

    def to_domain(self) -> DomainAssignment:
        return DomainAssignment(
            course_id=self.course_id,
            course_name=self.course_name,
            faculty_id=self.faculty_id,
            student_group_id=self.student_group_id,
            room_id=self.room_id,
            day=self.day,
            start_time=self.start_time,
            duration=self.duration,
            is_lab=self.is_lab,
            enrollment=self.enrollment,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timetable_id": self.timetable_id,
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
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Assignment {self.course_id} in {self.room_id} on {self.day} {self.start_time}>"


class AgentAuditLog(db.Model):
    """Audit log for inter-agent messages and negotiation steps."""

    __tablename__ = "agent_audit_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.String(50), nullable=False)
    sender = db.Column(db.String(150), nullable=False)
    receiver = db.Column(db.String(150), nullable=False)
    message_type = db.Column(db.String(50), nullable=False)
    course_id = db.Column(db.String(50), nullable=True)
    payload_json = db.Column(db.Text, default="{}")
    status = db.Column(db.String(50), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    @property
    def payload(self) -> Dict[str, Any]:
        try:
            return json.loads(self.payload_json or "{}")
        except Exception:
            return {}

    @payload.setter
    def payload(self, data: Dict[str, Any]):
        self.payload_json = json.dumps(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "course_id": self.course_id,
            "payload": self.payload,
            "status": self.status,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<AgentAuditLog [{self.timestamp}] {self.sender} -> {self.receiver} ({self.message_type})>"
