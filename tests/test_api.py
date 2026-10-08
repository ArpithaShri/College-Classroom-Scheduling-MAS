"""Tests for Flask REST API layer.

Covers:
- API Health endpoint
- Department CRUD endpoints
- Faculty CRUD endpoints
- Classroom CRUD endpoints
- Student Group CRUD endpoints
- Course CRUD endpoints
- Timetable retrieval and deletion
- CSP-driven Schedule Generation endpoint (successful & infeasible scenarios)
- Rescheduling and conflict resolution endpoint
- Request validation, foreign key checks, and error responses
- CORS headers
"""

import json
import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from database.db import db
from database.seed_data import seed_database
from app.models import Department, Faculty, Room, StudentGroup, Course, Timetable, Assignment


@pytest.fixture
def app() -> Flask:
    """Create a test Flask application with an in-memory SQLite database."""
    test_app = create_app("testing")
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Flask test client."""
    return app.test_client()


# ============================================================================
# 1. API HEALTH & CORS
# ============================================================================

def test_api_health_endpoint(client: FlaskClient):
    """Verify /api/health returns 200 and healthy message."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "College Classroom Scheduling API is running" in data["message"]
    # Check CORS header
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ============================================================================
# 2. DEPARTMENT CRUD
# ============================================================================

def test_department_crud_lifecycle(client: FlaskClient):
    """Test full CRUD lifecycle for Departments."""
    # 1. List initially empty
    resp = client.get("/api/departments")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 0

    # 2. Create department
    payload = {"id": "DEPT-CS", "name": "Computer Science", "code": "CSE"}
    resp = client.post("/api/departments", json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert data["department"]["id"] == "DEPT-CS"
    assert data["department"]["code"] == "CSE"

    # 3. Duplicate ID conflict (409)
    resp = client.post("/api/departments", json=payload)
    assert resp.status_code == 409
    assert resp.get_json()["success"] is False

    # 4. Duplicate code conflict (409)
    resp = client.post("/api/departments", json={"id": "DEPT-CS2", "name": "CS 2", "code": "CSE"})
    assert resp.status_code == 409

    # 5. Missing required fields (400)
    resp = client.post("/api/departments", json={"id": "DEPT-X"})
    assert resp.status_code == 400

    # 6. Get single department
    resp = client.get("/api/departments/DEPT-CS")
    assert resp.status_code == 200
    assert resp.get_json()["department"]["name"] == "Computer Science"

    # 7. Get non-existent department (404)
    resp = client.get("/api/departments/DEPT-NONEXISTENT")
    assert resp.status_code == 404

    # 8. Update department (PUT)
    resp = client.put("/api/departments/DEPT-CS", json={"name": "CS & Engineering", "code": "CS-ENG"})
    assert resp.status_code == 200
    assert resp.get_json()["department"]["name"] == "CS & Engineering"
    assert resp.get_json()["department"]["code"] == "CS-ENG"

    # 9. Delete department
    resp = client.delete("/api/departments/DEPT-CS")
    assert resp.status_code == 200

    # 10. Confirm deletion
    resp = client.get("/api/departments/DEPT-CS")
    assert resp.status_code == 404


# ============================================================================
# 3. FACULTY CRUD
# ============================================================================

def test_faculty_crud_lifecycle(client: FlaskClient):
    """Test full CRUD lifecycle for Faculty members."""
    # Create parent department
    client.post("/api/departments", json={"id": "DEPT-CS", "name": "Computer Science", "code": "CSE"})

    # 1. Create faculty
    fac_payload = {
        "id": "F001",
        "name": "Dr. Alan Turing",
        "email": "turing@college.edu",
        "department_id": "DEPT-CS",
        "max_daily_hours": 6,
        "max_consecutive_hours": 3,
        "preferred_slots": [["Monday", "10:00"], ["Tuesday", "10:00"]],
    }
    resp = client.post("/api/faculty", json=fac_payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["faculty"]["id"] == "F001"
    assert len(data["faculty"]["preferred_slots"]) == 2

    # 2. Duplicate faculty ID (409)
    resp = client.post("/api/faculty", json=fac_payload)
    assert resp.status_code == 409

    # 3. Invalid department reference (400)
    invalid_fac = dict(fac_payload)
    invalid_fac["id"] = "F002"
    invalid_fac["department_id"] = "INVALID-DEPT"
    resp = client.post("/api/faculty", json=invalid_fac)
    assert resp.status_code == 400

    # 4. Get faculty
    resp = client.get("/api/faculty/F001")
    assert resp.status_code == 200
    assert resp.get_json()["faculty"]["name"] == "Dr. Alan Turing"

    # 5. Update faculty (PUT)
    resp = client.put("/api/faculty/F001", json={"name": "Prof. Alan M. Turing", "max_daily_hours": 5})
    assert resp.status_code == 200
    assert resp.get_json()["faculty"]["name"] == "Prof. Alan M. Turing"
    assert resp.get_json()["faculty"]["max_daily_hours"] == 5

    # 6. Delete faculty
    resp = client.delete("/api/faculty/F001")
    assert resp.status_code == 200

    resp = client.get("/api/faculty/F001")
    assert resp.status_code == 404


# ============================================================================
# 4. CLASSROOM CRUD
# ============================================================================

def test_classroom_crud_lifecycle(client: FlaskClient):
    """Test full CRUD lifecycle for Classrooms / Labs."""
    # 1. Create classroom
    room_payload = {
        "id": "R101",
        "name": "Lecture Hall 101",
        "building": "Main Block",
        "capacity": 60,
        "room_type": "classroom",
        "has_projector": True,
    }
    resp = client.post("/api/classrooms", json=room_payload)
    assert resp.status_code == 201
    assert resp.get_json()["classroom"]["capacity"] == 60

    # 2. Invalid capacity (400)
    bad_room = dict(room_payload)
    bad_room["id"] = "R102"
    bad_room["capacity"] = -5
    resp = client.post("/api/classrooms", json=bad_room)
    assert resp.status_code == 400

    # 3. Invalid room_type (400)
    bad_type_room = dict(room_payload)
    bad_type_room["id"] = "R103"
    bad_type_room["room_type"] = "auditorium_invalid"
    resp = client.post("/api/classrooms", json=bad_type_room)
    assert resp.status_code == 400

    # 4. Duplicate room ID (409)
    resp = client.post("/api/classrooms", json=room_payload)
    assert resp.status_code == 409

    # 5. Update classroom (PUT)
    resp = client.put("/api/classrooms/R101", json={"capacity": 75, "building": "North Wing"})
    assert resp.status_code == 200
    assert resp.get_json()["classroom"]["capacity"] == 75
    assert resp.get_json()["classroom"]["building"] == "North Wing"

    # 6. Delete classroom
    resp = client.delete("/api/classrooms/R101")
    assert resp.status_code == 200
    assert client.get("/api/classrooms/R101").status_code == 404


# ============================================================================
# 5. STUDENT GROUP CRUD
# ============================================================================

def test_student_group_crud_lifecycle(client: FlaskClient):
    """Test full CRUD lifecycle for Student Groups."""
    client.post("/api/departments", json={"id": "DEPT-CS", "name": "Computer Science", "code": "CSE"})

    # 1. Create student group
    sg_payload = {
        "id": "CSE-A",
        "name": "CS Section A",
        "department_id": "DEPT-CS",
        "size": 55,
        "year_of_study": 3,
    }
    resp = client.post("/api/student-groups", json=sg_payload)
    assert resp.status_code == 201
    assert resp.get_json()["student_group"]["size"] == 55

    # 2. Duplicate ID conflict (409)
    resp = client.post("/api/student-groups", json=sg_payload)
    assert resp.status_code == 409

    # 3. Invalid size (400)
    bad_sg = dict(sg_payload)
    bad_sg["id"] = "CSE-B"
    bad_sg["size"] = 0
    resp = client.post("/api/student-groups", json=bad_sg)
    assert resp.status_code == 400

    # 4. Update student group (PUT)
    resp = client.put("/api/student-groups/CSE-A", json={"size": 60, "name": "CS Section A (Updated)"})
    assert resp.status_code == 200
    assert resp.get_json()["student_group"]["size"] == 60

    # 5. Delete student group
    resp = client.delete("/api/student-groups/CSE-A")
    assert resp.status_code == 200
    assert client.get("/api/student-groups/CSE-A").status_code == 404


# ============================================================================
# 6. COURSE CRUD
# ============================================================================

def test_course_crud_lifecycle(client: FlaskClient):
    """Test full CRUD lifecycle for Courses."""
    # Setup dependencies
    client.post("/api/departments", json={"id": "DEPT-CS", "name": "Computer Science", "code": "CSE"})
    client.post("/api/faculty", json={"id": "F001", "name": "Dr. Alan Turing", "department_id": "DEPT-CS"})
    client.post("/api/student-groups", json={"id": "CSE-A", "name": "CS Section A", "size": 50, "department_id": "DEPT-CS"})
    client.post("/api/classrooms", json={"id": "R101", "name": "Room 101", "capacity": 60, "room_type": "classroom"})

    # 1. Create course
    course_payload = {
        "id": "CS301",
        "name": "Machine Learning",
        "department_id": "DEPT-CS",
        "faculty_id": "F001",
        "student_group_id": "CSE-A",
        "enrollment": 50,
        "duration": 1,
        "is_lab": False,
        "preferred_days": ["Monday", "Wednesday"],
        "preferred_time": "10:00",
        "preferred_room_id": "R101",
    }
    resp = client.post("/api/courses", json=course_payload)
    assert resp.status_code == 201
    assert resp.get_json()["course"]["name"] == "Machine Learning"

    # 2. Duplicate ID conflict (409)
    resp = client.post("/api/courses", json=course_payload)
    assert resp.status_code == 409

    # 3. Non-existent faculty (400)
    bad_fac = dict(course_payload)
    bad_fac["id"] = "CS302"
    bad_fac["faculty_id"] = "NONEXISTENT_FAC"
    assert client.post("/api/courses", json=bad_fac).status_code == 400

    # 4. Non-existent student group (400)
    bad_group = dict(course_payload)
    bad_group["id"] = "CS303"
    bad_group["student_group_id"] = "NONEXISTENT_GROUP"
    assert client.post("/api/courses", json=bad_group).status_code == 400

    # 5. Update course (PUT)
    resp = client.put("/api/courses/CS301", json={"enrollment": 55, "name": "Applied Machine Learning"})
    assert resp.status_code == 200
    assert resp.get_json()["course"]["enrollment"] == 55
    assert resp.get_json()["course"]["name"] == "Applied Machine Learning"

    # 6. Delete course
    resp = client.delete("/api/courses/CS301")
    assert resp.status_code == 200
    assert client.get("/api/courses/CS301").status_code == 404


# ============================================================================
# 7. CSP SCHEDULE GENERATION ENDPOINT
# ============================================================================

def test_schedule_generation_happy_path(client: FlaskClient, app: Flask):
    """Test generating a timetable from seeded database records."""
    with app.app_context():
        seed_database()

    # Request schedule generation
    gen_payload = {
        "name": "Fall 2026 CS Timetable",
        "academic_term": "Fall 2026",
    }
    resp = client.post("/api/schedule/generate", json=gen_payload)
    assert resp.status_code == 201
    data = resp.get_json()

    assert data["success"] is True
    assert data["timetable_id"] is not None
    assert data["status"] == "SCHEDULED"
    assert "fitness_score" in data
    assert len(data["assignments"]) == 4

    # Verify assignments fields
    first_asgn = data["assignments"][0]
    assert "course_id" in first_asgn
    assert "room_id" in first_asgn
    assert "day" in first_asgn
    assert "start_time" in first_asgn
    assert "faculty_id" in first_asgn
    assert "student_group_id" in first_asgn

    # Verify retrieval of generated timetable
    tt_id = data["timetable_id"]
    get_resp = client.get(f"/api/timetable/{tt_id}")
    assert get_resp.status_code == 200
    tt_data = get_resp.get_json()
    assert tt_data["timetable"]["id"] == tt_id
    assert len(tt_data["assignments"]) == 4


def test_schedule_generation_empty_database(client: FlaskClient):
    """Test schedule generation fails cleanly if no courses exist."""
    resp = client.post("/api/schedule/generate", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "No courses found" in data["error"]


def test_schedule_generation_infeasible_problem(client: FlaskClient):
    """Test schedule generation returns 409 when problem is over-constrained."""
    # Setup problem with 0 rooms capable of holding a large course
    client.post("/api/departments", json={"id": "DEPT-CS", "name": "CS", "code": "CSE"})
    client.post("/api/faculty", json={"id": "F001", "name": "Dr. Turing", "department_id": "DEPT-CS"})
    client.post("/api/student_groups" if False else "/api/student-groups", json={"id": "CSE-A", "name": "CS A", "size": 100, "department_id": "DEPT-CS"})
    # Only tiny room capacity 20, but course enrollment is 100
    client.post("/api/classrooms", json={"id": "R_TINY", "name": "Tiny Room", "capacity": 20, "room_type": "classroom"})
    client.post("/api/courses", json={"id": "CS100", "name": "Massive Class", "faculty_id": "F001", "student_group_id": "CSE-A", "enrollment": 100, "duration": 1})

    resp = client.post("/api/schedule/generate", json={})
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["success"] is False
    assert "conflicts" in data
    assert len(data["conflicts"]) > 0


# ============================================================================
# 8. TIMETABLES RETRIEVAL & DELETION
# ============================================================================

def test_timetables_list_and_delete(client: FlaskClient, app: Flask):
    """Test retrieving list of timetables and deleting a timetable."""
    with app.app_context():
        seed_database()

    # Generate timetable
    gen_resp = client.post("/api/schedule/generate", json={"name": "Test Timetable"})
    tt_id = gen_resp.get_json()["timetable_id"]

    # List timetables
    resp = client.get("/api/timetables")
    assert resp.status_code == 200
    assert resp.get_json()["count"] >= 1

    # Delete timetable
    del_resp = client.delete(f"/api/timetables/{tt_id}")
    assert del_resp.status_code == 200
    assert del_resp.get_json()["success"] is True

    # Confirm 404 after deletion
    assert client.get(f"/api/timetables/{tt_id}").status_code == 404


# ============================================================================
# 9. RESCHEDULING & CONFLICT RESOLUTION
# ============================================================================

def test_rescheduling_endpoint(client: FlaskClient, app: Flask):
    """Test requesting alternative slot for a course during a conflict."""
    with app.app_context():
        seed_database()

    # Generate timetable first
    gen_resp = client.post("/api/schedule/generate", json={})
    assert gen_resp.status_code == 201

    # Request reschedule for CS301 excluding room R101 at Monday 10:00
    reschedule_payload = {
        "course_id": "CS301",
        "reason": "CLASSROOM_CAPACITY",
        "current_room_id": "R101",
        "current_day": "Monday",
        "current_time": "10:00",
    }
    resp = client.post("/api/schedule/reschedule", json=reschedule_payload)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["success"] is True
    assert data["course_id"] == "CS301"
    assert "alternative" in data
    alt = data["alternative"]
    assert alt["course_id"] == "CS301"
    assert alt["room_id"] != ""
    assert alt["day"] != ""
    assert alt["start_time"] != ""
    # Should not be the excluded candidate
    assert not (alt["room_id"] == "R101" and alt["day"] == "Monday" and alt["start_time"] == "10:00")


def test_rescheduling_nonexistent_course(client: FlaskClient):
    """Test reschedule returns 404 for non-existent course."""
    resp = client.post("/api/schedule/reschedule", json={"course_id": "NONEXISTENT_COURSE"})
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
