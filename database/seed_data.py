"""Seed data generator for College Classroom Scheduling System.

Populates initial academic departments, instructors, physical classrooms/labs,
student cohorts, and courses into the SQLite database.
"""

from typing import List, Dict, Any
from database.db import db
from app.models import Department, Faculty, Room, StudentGroup, Course, Timetable


def get_default_departments_data() -> List[Dict[str, Any]]:
    return [
        {
            "id": "DEPT-CS",
            "name": "Computer Science & Engineering",
            "code": "CSE",
        },
        {
            "id": "DEPT-EC",
            "name": "Electronics & Communication Engineering",
            "code": "ECE",
        },
    ]


def get_default_faculty_data() -> List[Dict[str, Any]]:
    return [
        {
            "id": "F001",
            "name": "Dr. Alan Turing",
            "email": "turing@college.edu",
            "department_id": "DEPT-CS",
            "max_daily_hours": 6,
            "max_consecutive_hours": 3,
            "preferred_slots": [["Monday", "10:00"], ["Tuesday", "10:00"], ["Wednesday", "10:00"]],
        },
        {
            "id": "F002",
            "name": "Dr. Ada Lovelace",
            "email": "lovelace@college.edu",
            "department_id": "DEPT-CS",
            "max_daily_hours": 6,
            "max_consecutive_hours": 3,
            "preferred_slots": [["Wednesday", "11:00"], ["Thursday", "11:00"]],
        },
        {
            "id": "F003",
            "name": "Dr. Claude Shannon",
            "email": "shannon@college.edu",
            "department_id": "DEPT-CS",
            "max_daily_hours": 5,
            "max_consecutive_hours": 2,
            "preferred_slots": [["Monday", "09:00"], ["Friday", "09:00"]],
        },
        {
            "id": "F004",
            "name": "Dr. Grace Hopper",
            "email": "hopper@college.edu",
            "department_id": "DEPT-CS",
            "max_daily_hours": 6,
            "max_consecutive_hours": 3,
            "preferred_slots": [["Tuesday", "14:00"], ["Thursday", "14:00"]],
        },
    ]


def get_default_rooms_data() -> List[Dict[str, Any]]:
    return [
        {
            "id": "R101",
            "name": "Classroom 101",
            "building": "Main Academic Block",
            "capacity": 40,
            "room_type": "classroom",
            "has_projector": True,
        },
        {
            "id": "R102",
            "name": "Lecture Hall 102",
            "building": "Main Academic Block",
            "capacity": 65,
            "room_type": "classroom",
            "has_projector": True,
        },
        {
            "id": "R103",
            "name": "Auditorium 103",
            "building": "Tech Tower",
            "capacity": 120,
            "room_type": "classroom",
            "has_projector": True,
        },
        {
            "id": "LAB-01",
            "name": "AI & Networks Lab",
            "building": "CS Lab Complex",
            "capacity": 50,
            "room_type": "lab",
            "has_projector": True,
        },
        {
            "id": "LAB-02",
            "name": "Systems Programming Lab",
            "building": "CS Lab Complex",
            "capacity": 35,
            "room_type": "lab",
            "has_projector": True,
        },
    ]


def get_default_student_groups_data() -> List[Dict[str, Any]]:
    return [
        {
            "id": "CSE-A",
            "name": "Computer Science Section A",
            "department_id": "DEPT-CS",
            "size": 55,
            "year_of_study": 3,
        },
        {
            "id": "CSE-B",
            "name": "Computer Science Section B",
            "department_id": "DEPT-CS",
            "size": 40,
            "year_of_study": 3,
        },
        {
            "id": "CSE-AIML",
            "name": "AI & ML Specialization Cohort",
            "department_id": "DEPT-CS",
            "size": 45,
            "year_of_study": 4,
        },
    ]


def get_default_courses_data() -> List[Dict[str, Any]]:
    return [
        {
            "id": "CS301",
            "name": "Machine Learning",
            "department_id": "DEPT-CS",
            "faculty_id": "F001",
            "student_group_id": "CSE-A",
            "enrollment": 55,
            "duration": 1,
            "is_lab": False,
            "preferred_days": ["Monday", "Tuesday", "Wednesday"],
            "preferred_time": "10:00",
            "preferred_room_id": "R102",
        },
        {
            "id": "CS302",
            "name": "Operating Systems",
            "department_id": "DEPT-CS",
            "faculty_id": "F002",
            "student_group_id": "CSE-A",
            "enrollment": 55,
            "duration": 1,
            "is_lab": False,
            "preferred_days": ["Wednesday", "Thursday"],
            "preferred_time": "11:00",
            "preferred_room_id": "R102",
        },
        {
            "id": "CS303",
            "name": "Computer Networks",
            "department_id": "DEPT-CS",
            "faculty_id": "F003",
            "student_group_id": "CSE-B",
            "enrollment": 40,
            "duration": 1,
            "is_lab": False,
            "preferred_days": ["Monday", "Friday"],
            "preferred_time": "09:00",
            "preferred_room_id": "R101",
        },
        {
            "id": "CS304",
            "name": "AI Systems Laboratory",
            "department_id": "DEPT-CS",
            "faculty_id": "F001",
            "student_group_id": "CSE-AIML",
            "enrollment": 45,
            "duration": 2,
            "is_lab": True,
            "preferred_days": ["Thursday", "Friday"],
            "preferred_time": "14:00",
            "preferred_room_id": "LAB-01",
        },
    ]


def seed_database(session=None):
    """Seed default entities into the database."""
    sess = session or db.session

    # 1. Departments
    for d_data in get_default_departments_data():
        if not sess.get(Department, d_data["id"]):
            dept = Department(**d_data)
            sess.add(dept)
    sess.flush()

    # 2. Faculty
    for f_data in get_default_faculty_data():
        if not sess.get(Faculty, f_data["id"]):
            fac = Faculty(
                id=f_data["id"],
                name=f_data["name"],
                email=f_data.get("email"),
                department_id=f_data.get("department_id"),
                max_daily_hours=f_data.get("max_daily_hours", 6),
                max_consecutive_hours=f_data.get("max_consecutive_hours", 3),
            )
            fac.preferred_slots = f_data.get("preferred_slots", [])
            sess.add(fac)
    sess.flush()

    # 3. Rooms
    for r_data in get_default_rooms_data():
        if not sess.get(Room, r_data["id"]):
            room = Room(
                id=r_data["id"],
                name=r_data["name"],
                building=r_data.get("building"),
                capacity=r_data["capacity"],
                room_type=r_data["room_type"],
                has_projector=r_data.get("has_projector", True),
            )
            sess.add(room)
    sess.flush()

    # 4. Student Groups
    for sg_data in get_default_student_groups_data():
        if not sess.get(StudentGroup, sg_data["id"]):
            sg = StudentGroup(
                id=sg_data["id"],
                name=sg_data["name"],
                department_id=sg_data.get("department_id"),
                size=sg_data["size"],
                year_of_study=sg_data.get("year_of_study", 1),
            )
            sess.add(sg)
    sess.flush()

    # 5. Courses
    for c_data in get_default_courses_data():
        if not sess.get(Course, c_data["id"]):
            course = Course(
                id=c_data["id"],
                name=c_data["name"],
                department_id=c_data.get("department_id"),
                faculty_id=c_data["faculty_id"],
                student_group_id=c_data["student_group_id"],
                enrollment=c_data["enrollment"],
                duration=c_data.get("duration", 1),
                is_lab=c_data.get("is_lab", False),
                preferred_time=c_data.get("preferred_time"),
                preferred_room_id=c_data.get("preferred_room_id"),
            )
            course.preferred_days = c_data.get("preferred_days", [])
            sess.add(course)
    sess.flush()

    sess.commit()
