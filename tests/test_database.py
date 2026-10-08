"""Comprehensive unit and integration tests for SQLite database layer and SQLAlchemy models."""

import pytest
from app import create_app
from database.db import db, init_db
from database.seed_data import seed_database
from app.models import (
    Department,
    Faculty,
    Room,
    StudentGroup,
    Course,
    Timetable,
    Assignment,
    AgentAuditLog,
)
from scheduler.domain import TimeSlot


@pytest.fixture
def app():
    """Create a Flask test application with in-memory SQLite database."""
    app = create_app(config_name="testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def session(app):
    """Provide clean database session for test scope."""
    with app.app_context():
        yield db.session


def test_database_table_creation(app):
    """Verify all 8 core tables exist in the database schema."""
    with app.app_context():
        table_names = db.metadata.tables.keys()
        expected = [
            "departments",
            "faculty",
            "rooms",
            "student_groups",
            "courses",
            "timetables",
            "assignments",
            "agent_audit_logs",
        ]
        for tbl in expected:
            assert tbl in table_names


def test_department_model_crud(session):
    """Test Department model creation, query, and serialization."""
    dept = Department(id="DEPT-CS", name="Computer Science & Engineering", code="CSE")
    session.add(dept)
    session.commit()

    queried = session.get(Department, "DEPT-CS")
    assert queried is not None
    assert queried.code == "CSE"

    d_dict = queried.to_dict()
    assert d_dict["id"] == "DEPT-CS"
    assert d_dict["name"] == "Computer Science & Engineering"
    assert d_dict["code"] == "CSE"


def test_faculty_model_and_domain_conversion(session):
    """Test Faculty model JSON slot properties and domain dataclass conversion."""
    dept = Department(id="DEPT-CS", name="Computer Science", code="CSE")
    session.add(dept)
    session.flush()

    fac = Faculty(
        id="F001",
        name="Dr. Alan Turing",
        email="turing@college.edu",
        department_id="DEPT-CS",
        max_daily_hours=6,
        max_consecutive_hours=3,
    )
    fac.available_slots = [["Monday", "10:00"], ["Tuesday", "10:00"]]
    fac.preferred_slots = [TimeSlot("Monday", "10:00")]

    session.add(fac)
    session.commit()

    queried = session.get(Faculty, "F001")
    assert len(queried.available_slots) == 2
    assert queried.preferred_slots == [["Monday", "10:00"]]

    domain_fac = queried.to_domain()
    assert domain_fac.id == "F001"
    assert TimeSlot("Monday", "10:00") in domain_fac.available_slots
    assert TimeSlot("Monday", "10:00") in domain_fac.preferred_slots


def test_room_model_and_domain_conversion(session):
    """Test Room model capacity, room type, and domain conversion."""
    room = Room(
        id="LAB-01",
        name="AI & Networks Lab",
        building="Complex A",
        capacity=50,
        room_type="lab",
        has_projector=True,
    )
    session.add(room)
    session.commit()

    queried = session.get(Room, "LAB-01")
    assert queried.capacity == 50
    assert queried.room_type == "lab"

    domain_room = queried.to_domain()
    assert domain_room.id == "LAB-01"
    assert domain_room.capacity == 50
    assert domain_room.room_type == "lab"


def test_student_group_model_and_domain_conversion(session):
    """Test StudentGroup model attributes and domain conversion."""
    dept = Department(id="DEPT-CS", name="Computer Science", code="CSE")
    session.add(dept)
    session.flush()

    group = StudentGroup(
        id="CSE-A",
        name="Computer Science Section A",
        department_id="DEPT-CS",
        size=55,
        year_of_study=3,
    )
    group.commitments = [["Wednesday", "16:00"]]
    session.add(group)
    session.commit()

    queried = session.get(StudentGroup, "CSE-A")
    assert queried.size == 55
    assert queried.commitments == [["Wednesday", "16:00"]]

    domain_sg = queried.to_domain()
    assert domain_sg.id == "CSE-A"
    assert domain_sg.name == "Computer Science Section A"


def test_course_model_and_domain_conversion(session):
    """Test Course model relationships and domain conversion."""
    dept = Department(id="DEPT-CS", name="Computer Science", code="CSE")
    fac = Faculty(id="F001", name="Dr. Turing", department_id="DEPT-CS")
    group = StudentGroup(id="CSE-A", name="CSE Section A", department_id="DEPT-CS", size=55)
    session.add_all([dept, fac, group])
    session.flush()

    course = Course(
        id="CS301",
        name="Machine Learning",
        department_id="DEPT-CS",
        faculty_id="F001",
        student_group_id="CSE-A",
        enrollment=55,
        duration=1,
        is_lab=False,
        preferred_time="10:00",
        preferred_room_id="R102",
    )
    course.preferred_days = ["Monday", "Tuesday"]
    session.add(course)
    session.commit()

    queried = session.get(Course, "CS301")
    assert queried.enrollment == 55
    assert queried.preferred_days == ["Monday", "Tuesday"]

    domain_c = queried.to_domain()
    assert domain_c.id == "CS301"
    assert domain_c.faculty_id == "F001"
    assert domain_c.student_group_id == "CSE-A"
    assert domain_c.duration == 1


def test_timetable_and_assignment_lifecycle(session):
    """Test creating Timetable sessions and linked Assignment records."""
    dept = Department(id="DEPT-CS", name="Computer Science", code="CSE")
    fac = Faculty(id="F001", name="Dr. Turing", department_id="DEPT-CS")
    group = StudentGroup(id="CSE-A", name="CSE Section A", department_id="DEPT-CS", size=55)
    room = Room(id="R102", name="Hall 102", capacity=65, room_type="classroom")
    course = Course(
        id="CS301",
        name="Machine Learning",
        department_id="DEPT-CS",
        faculty_id="F001",
        student_group_id="CSE-A",
        enrollment=55,
    )
    session.add_all([dept, fac, group, room, course])
    session.flush()

    tt = Timetable(name="Fall 2026 CS Timetable", academic_term="Fall 2026", status="SCHEDULED")
    session.add(tt)
    session.flush()

    asgn = Assignment(
        timetable_id=tt.id,
        course_id="CS301",
        course_name="Machine Learning",
        faculty_id="F001",
        student_group_id="CSE-A",
        room_id="R102",
        day="Monday",
        start_time="10:00",
        duration=1,
        enrollment=55,
        status="SCHEDULED",
    )
    session.add(asgn)
    session.commit()

    queried_tt = session.get(Timetable, tt.id)
    assert len(queried_tt.assignments) == 1
    assert queried_tt.assignments[0].room_id == "R102"

    domain_asgn = queried_tt.assignments[0].to_domain()
    assert domain_asgn.day == "Monday"
    assert domain_asgn.start_time == "10:00"


def test_agent_audit_log_model(session):
    """Test recording and querying agent communication audit logs."""
    log_entry = AgentAuditLog(
        timestamp="10:30:00",
        sender="department_cs@localhost",
        receiver="coordinator@localhost",
        message_type="REQUEST",
        course_id="CS301",
        status="SENT",
        reason=None,
    )
    log_entry.payload = {"course_id": "CS301", "faculty_id": "F001", "enrollment": 55}

    session.add(log_entry)
    session.commit()

    queried = session.query(AgentAuditLog).filter_by(message_type="REQUEST").first()
    assert queried is not None
    assert queried.payload["enrollment"] == 55
    assert queried.sender == "department_cs@localhost"


def test_seed_database_utility(session):
    """Test seeding database with standard entities and verifying populated counts."""
    seed_database(session=session)

    dept_count = session.query(Department).count()
    fac_count = session.query(Faculty).count()
    room_count = session.query(Room).count()
    group_count = session.query(StudentGroup).count()
    course_count = session.query(Course).count()

    assert dept_count == 2
    assert fac_count == 4
    assert room_count == 5
    assert group_count == 3
    assert course_count == 4
