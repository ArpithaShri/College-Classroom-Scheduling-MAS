"""REST API Endpoints for College Classroom Scheduling System.

Defines HTTP handlers for CRUD operations on Departments, Faculty, Classrooms,
Student Groups, Courses, and Timetables, as well as CSP-driven Schedule Generation
and Rescheduling negotiation endpoints.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from flask import jsonify, request

from . import api_bp
from database.db import db
from app.models import Department, Faculty, Room, StudentGroup, Course, Timetable, Assignment
from scheduler.domain import (
    SchedulingProblem,
    Course as DomainCourse,
    Faculty as DomainFaculty,
    Room as DomainRoom,
    StudentGroup as DomainStudentGroup,
    ScheduleValue,
    Assignment as DomainAssignment,
    generate_course_domain,
)
from scheduler.constraints import HardConstraintValidator, SoftConstraintEvaluator, UtilityWeights
from scheduler.csp_solver import CSPScheduler


# ============================================================================
# API HEALTH
# ============================================================================

@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint confirming API status."""
    return jsonify({
        "success": True,
        "message": "College Classroom Scheduling API is running",
    }), 200


# ============================================================================
# DEPARTMENTS CRUD
# ============================================================================

@api_bp.route("/departments", methods=["GET"])
def get_departments():
    """Retrieve all academic departments."""
    departments = Department.query.order_by(Department.id).all()
    return jsonify({
        "success": True,
        "count": len(departments),
        "departments": [d.to_dict() for d in departments],
    }), 200


@api_bp.route("/departments/<string:dept_id>", methods=["GET"])
def get_department(dept_id: str):
    """Retrieve a single academic department by ID."""
    dept = db.session.get(Department, dept_id)
    if not dept:
        return jsonify({
            "success": False,
            "error": f"Department with ID '{dept_id}' not found",
        }), 404
    return jsonify({
        "success": True,
        "department": dept.to_dict(),
    }), 200


@api_bp.route("/departments", methods=["POST"])
def create_department():
    """Create a new academic department."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    dept_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()
    code = str(data.get("code", "")).strip().upper()

    if not dept_id or not name or not code:
        return jsonify({
            "success": False,
            "error": "Missing required fields: 'id', 'name', and 'code' are mandatory",
        }), 400

    if db.session.get(Department, dept_id):
        return jsonify({
            "success": False,
            "error": f"Department with ID '{dept_id}' already exists",
        }), 409

    if Department.query.filter_by(code=code).first():
        return jsonify({
            "success": False,
            "error": f"Department with code '{code}' already exists",
        }), 409

    try:
        dept = Department(id=dept_id, name=name, code=code)
        db.session.add(dept)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Department created successfully",
            "department": dept.to_dict(),
        }), 201
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while creating department"}), 500


@api_bp.route("/departments/<string:dept_id>", methods=["PUT"])
def update_department(dept_id: str):
    """Update an existing academic department."""
    dept = db.session.get(Department, dept_id)
    if not dept:
        return jsonify({
            "success": False,
            "error": f"Department with ID '{dept_id}' not found",
        }), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    if "name" in data and data["name"]:
        dept.name = str(data["name"]).strip()

    if "code" in data and data["code"]:
        new_code = str(data["code"]).strip().upper()
        existing = Department.query.filter(Department.code == new_code, Department.id != dept_id).first()
        if existing:
            return jsonify({
                "success": False,
                "error": f"Department with code '{new_code}' already exists",
            }), 409
        dept.code = new_code

    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Department updated successfully",
            "department": dept.to_dict(),
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while updating department"}), 500


@api_bp.route("/departments/<string:dept_id>", methods=["DELETE"])
def delete_department(dept_id: str):
    """Delete an academic department and its cascade relationships."""
    dept = db.session.get(Department, dept_id)
    if not dept:
        return jsonify({
            "success": False,
            "error": f"Department with ID '{dept_id}' not found",
        }), 404

    try:
        db.session.delete(dept)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Department '{dept_id}' deleted successfully",
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while deleting department"}), 500


# ============================================================================
# FACULTY CRUD
# ============================================================================

@api_bp.route("/faculty", methods=["GET"])
def get_faculty():
    """Retrieve all faculty members."""
    faculty_list = Faculty.query.order_by(Faculty.id).all()
    return jsonify({
        "success": True,
        "count": len(faculty_list),
        "faculty": [f.to_dict() for f in faculty_list],
    }), 200


@api_bp.route("/faculty/<string:fac_id>", methods=["GET"])
def get_faculty_member(fac_id: str):
    """Retrieve a single faculty member by ID."""
    fac = db.session.get(Faculty, fac_id)
    if not fac:
        return jsonify({
            "success": False,
            "error": f"Faculty member with ID '{fac_id}' not found",
        }), 404
    return jsonify({
        "success": True,
        "faculty": fac.to_dict(),
    }), 200


@api_bp.route("/faculty", methods=["POST"])
def create_faculty_member():
    """Create a new faculty member."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    fac_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()

    if not fac_id or not name:
        return jsonify({
            "success": False,
            "error": "Missing required fields: 'id' and 'name' are mandatory",
        }), 400

    if db.session.get(Faculty, fac_id):
        return jsonify({
            "success": False,
            "error": f"Faculty with ID '{fac_id}' already exists",
        }), 409

    dept_id = data.get("department_id")
    if dept_id and not db.session.get(Department, dept_id):
        return jsonify({
            "success": False,
            "error": f"Referenced department '{dept_id}' does not exist",
        }), 400

    try:
        max_daily = int(data.get("max_daily_hours", 6))
        max_consecutive = int(data.get("max_consecutive_hours", 3))
        if max_daily <= 0 or max_consecutive <= 0:
            return jsonify({
                "success": False,
                "error": "Faculty teaching hours limits must be positive integers",
            }), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid integer format for teaching hours"}), 400

    try:
        fac = Faculty(
            id=fac_id,
            name=name,
            email=data.get("email"),
            department_id=dept_id,
            max_daily_hours=max_daily,
            max_consecutive_hours=max_consecutive,
        )
        if "available_slots" in data:
            fac.available_slots = data["available_slots"]
        if "preferred_slots" in data:
            fac.preferred_slots = data["preferred_slots"]

        db.session.add(fac)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Faculty member created successfully",
            "faculty": fac.to_dict(),
        }), 201
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while creating faculty member"}), 500


@api_bp.route("/faculty/<string:fac_id>", methods=["PUT"])
def update_faculty_member(fac_id: str):
    """Update an existing faculty member."""
    fac = db.session.get(Faculty, fac_id)
    if not fac:
        return jsonify({
            "success": False,
            "error": f"Faculty member with ID '{fac_id}' not found",
        }), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    if "name" in data and data["name"]:
        fac.name = str(data["name"]).strip()

    if "email" in data:
        fac.email = data["email"]

    if "department_id" in data:
        dept_id = data["department_id"]
        if dept_id and not db.session.get(Department, dept_id):
            return jsonify({
                "success": False,
                "error": f"Referenced department '{dept_id}' does not exist",
            }), 400
        fac.department_id = dept_id

    if "max_daily_hours" in data:
        try:
            val = int(data["max_daily_hours"])
            if val <= 0:
                return jsonify({"success": False, "error": "max_daily_hours must be positive"}), 400
            fac.max_daily_hours = val
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid integer format for max_daily_hours"}), 400

    if "max_consecutive_hours" in data:
        try:
            val = int(data["max_consecutive_hours"])
            if val <= 0:
                return jsonify({"success": False, "error": "max_consecutive_hours must be positive"}), 400
            fac.max_consecutive_hours = val
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid integer format for max_consecutive_hours"}), 400

    if "available_slots" in data:
        fac.available_slots = data["available_slots"]

    if "preferred_slots" in data:
        fac.preferred_slots = data["preferred_slots"]

    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Faculty member updated successfully",
            "faculty": fac.to_dict(),
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while updating faculty member"}), 500


@api_bp.route("/faculty/<string:fac_id>", methods=["DELETE"])
def delete_faculty_member(fac_id: str):
    """Delete a faculty member."""
    fac = db.session.get(Faculty, fac_id)
    if not fac:
        return jsonify({
            "success": False,
            "error": f"Faculty member with ID '{fac_id}' not found",
        }), 404

    try:
        db.session.delete(fac)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Faculty member '{fac_id}' deleted successfully",
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while deleting faculty member"}), 500


# ============================================================================
# CLASSROOMS CRUD
# ============================================================================

@api_bp.route("/classrooms", methods=["GET"])
def get_classrooms():
    """Retrieve all physical classrooms and laboratories."""
    rooms = Room.query.order_by(Room.id).all()
    return jsonify({
        "success": True,
        "count": len(rooms),
        "classrooms": [r.to_dict() for r in rooms],
    }), 200


@api_bp.route("/classrooms/<string:room_id>", methods=["GET"])
def get_classroom(room_id: str):
    """Retrieve a single classroom by ID."""
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({
            "success": False,
            "error": f"Classroom with ID '{room_id}' not found",
        }), 404
    return jsonify({
        "success": True,
        "classroom": room.to_dict(),
    }), 200


@api_bp.route("/classrooms", methods=["POST"])
def create_classroom():
    """Create a new classroom or laboratory entity."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    room_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()

    if not room_id or not name or "capacity" not in data:
        return jsonify({
            "success": False,
            "error": "Missing required fields: 'id', 'name', and 'capacity' are mandatory",
        }), 400

    if db.session.get(Room, room_id):
        return jsonify({
            "success": False,
            "error": f"Classroom with ID '{room_id}' already exists",
        }), 409

    try:
        capacity = int(data["capacity"])
        if capacity <= 0:
            return jsonify({"success": False, "error": "Classroom capacity must be a positive integer"}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Classroom capacity must be a valid integer"}), 400

    room_type = str(data.get("room_type", "classroom")).lower().strip()
    if room_type not in ["classroom", "lab"]:
        return jsonify({"success": False, "error": "room_type must be either 'classroom' or 'lab'"}), 400

    try:
        room = Room(
            id=room_id,
            name=name,
            building=data.get("building"),
            capacity=capacity,
            room_type=room_type,
            has_projector=bool(data.get("has_projector", True)),
        )
        if "available_slots" in data:
            room.available_slots = data["available_slots"]

        db.session.add(room)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Classroom created successfully",
            "classroom": room.to_dict(),
        }), 201
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while creating classroom"}), 500


@api_bp.route("/classrooms/<string:room_id>", methods=["PUT"])
def update_classroom(room_id: str):
    """Update an existing classroom or laboratory entity."""
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({
            "success": False,
            "error": f"Classroom with ID '{room_id}' not found",
        }), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    if "name" in data and data["name"]:
        room.name = str(data["name"]).strip()

    if "building" in data:
        room.building = data["building"]

    if "capacity" in data:
        try:
            cap = int(data["capacity"])
            if cap <= 0:
                return jsonify({"success": False, "error": "Classroom capacity must be a positive integer"}), 400
            room.capacity = cap
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Classroom capacity must be a valid integer"}), 400

    if "room_type" in data:
        rt = str(data["room_type"]).lower().strip()
        if rt not in ["classroom", "lab"]:
            return jsonify({"success": False, "error": "room_type must be either 'classroom' or 'lab'"}), 400
        room.room_type = rt

    if "has_projector" in data:
        room.has_projector = bool(data["has_projector"])

    if "available_slots" in data:
        room.available_slots = data["available_slots"]

    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Classroom updated successfully",
            "classroom": room.to_dict(),
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while updating classroom"}), 500


@api_bp.route("/classrooms/<string:room_id>", methods=["DELETE"])
def delete_classroom(room_id: str):
    """Delete a classroom entity."""
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({
            "success": False,
            "error": f"Classroom with ID '{room_id}' not found",
        }), 404

    try:
        db.session.delete(room)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Classroom '{room_id}' deleted successfully",
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while deleting classroom"}), 500


# ============================================================================
# STUDENT GROUPS CRUD
# ============================================================================

@api_bp.route("/student-groups", methods=["GET"])
def get_student_groups():
    """Retrieve all student groups."""
    groups = StudentGroup.query.order_by(StudentGroup.id).all()
    return jsonify({
        "success": True,
        "count": len(groups),
        "student_groups": [g.to_dict() for g in groups],
    }), 200


@api_bp.route("/student-groups/<string:group_id>", methods=["GET"])
def get_student_group(group_id: str):
    """Retrieve a single student group by ID."""
    sg = db.session.get(StudentGroup, group_id)
    if not sg:
        return jsonify({
            "success": False,
            "error": f"Student group with ID '{group_id}' not found",
        }), 404
    return jsonify({
        "success": True,
        "student_group": sg.to_dict(),
    }), 200


@api_bp.route("/student-groups", methods=["POST"])
def create_student_group():
    """Create a new student group / cohort."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    group_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()

    if not group_id or not name or "size" not in data:
        return jsonify({
            "success": False,
            "error": "Missing required fields: 'id', 'name', and 'size' are mandatory",
        }), 400

    if db.session.get(StudentGroup, group_id):
        return jsonify({
            "success": False,
            "error": f"Student group with ID '{group_id}' already exists",
        }), 409

    try:
        size = int(data["size"])
        if size <= 0:
            return jsonify({"success": False, "error": "Student group size must be a positive integer"}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Student group size must be a valid integer"}), 400

    dept_id = data.get("department_id")
    if dept_id and not db.session.get(Department, dept_id):
        return jsonify({
            "success": False,
            "error": f"Referenced department '{dept_id}' does not exist",
        }), 400

    try:
        year = int(data.get("year_of_study", 1))
    except (ValueError, TypeError):
        year = 1

    try:
        sg = StudentGroup(
            id=group_id,
            name=name,
            department_id=dept_id,
            size=size,
            year_of_study=year,
        )
        if "commitments" in data:
            sg.commitments = data["commitments"]

        db.session.add(sg)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Student group created successfully",
            "student_group": sg.to_dict(),
        }), 201
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while creating student group"}), 500


@api_bp.route("/student-groups/<string:group_id>", methods=["PUT"])
def update_student_group(group_id: str):
    """Update an existing student group."""
    sg = db.session.get(StudentGroup, group_id)
    if not sg:
        return jsonify({
            "success": False,
            "error": f"Student group with ID '{group_id}' not found",
        }), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    if "name" in data and data["name"]:
        sg.name = str(data["name"]).strip()

    if "department_id" in data:
        dept_id = data["department_id"]
        if dept_id and not db.session.get(Department, dept_id):
            return jsonify({
                "success": False,
                "error": f"Referenced department '{dept_id}' does not exist",
            }), 400
        sg.department_id = dept_id

    if "size" in data:
        try:
            size = int(data["size"])
            if size <= 0:
                return jsonify({"success": False, "error": "Student group size must be a positive integer"}), 400
            sg.size = size
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Student group size must be a valid integer"}), 400

    if "year_of_study" in data:
        try:
            sg.year_of_study = int(data["year_of_study"])
        except (ValueError, TypeError):
            pass

    if "commitments" in data:
        sg.commitments = data["commitments"]

    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Student group updated successfully",
            "student_group": sg.to_dict(),
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while updating student group"}), 500


@api_bp.route("/student-groups/<string:group_id>", methods=["DELETE"])
def delete_student_group(group_id: str):
    """Delete a student group entity."""
    sg = db.session.get(StudentGroup, group_id)
    if not sg:
        return jsonify({
            "success": False,
            "error": f"Student group with ID '{group_id}' not found",
        }), 404

    try:
        db.session.delete(sg)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Student group '{group_id}' deleted successfully",
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while deleting student group"}), 500


# ============================================================================
# COURSES CRUD
# ============================================================================

@api_bp.route("/courses", methods=["GET"])
def get_courses():
    """Retrieve all academic courses."""
    courses = Course.query.order_by(Course.id).all()
    return jsonify({
        "success": True,
        "count": len(courses),
        "courses": [c.to_dict() for c in courses],
    }), 200


@api_bp.route("/courses/<string:course_id>", methods=["GET"])
def get_course(course_id: str):
    """Retrieve a single academic course by ID."""
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({
            "success": False,
            "error": f"Course with ID '{course_id}' not found",
        }), 404
    return jsonify({
        "success": True,
        "course": course.to_dict(),
    }), 200


@api_bp.route("/courses", methods=["POST"])
def create_course():
    """Create a new academic course requirement."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    required_fields = ["id", "name", "faculty_id", "student_group_id", "enrollment"]
    missing = [f for f in required_fields if f not in data or data[f] is None or data[f] == ""]
    if missing:
        return jsonify({
            "success": False,
            "error": f"Missing required fields: {', '.join(missing)}",
        }), 400

    course_id = str(data["id"]).strip()
    name = str(data["name"]).strip()
    faculty_id = str(data["faculty_id"]).strip()
    group_id = str(data["student_group_id"]).strip()

    if db.session.get(Course, course_id):
        return jsonify({
            "success": False,
            "error": f"Course with ID '{course_id}' already exists",
        }), 409

    if not db.session.get(Faculty, faculty_id):
        return jsonify({
            "success": False,
            "error": f"Referenced faculty '{faculty_id}' does not exist",
        }), 400

    if not db.session.get(StudentGroup, group_id):
        return jsonify({
            "success": False,
            "error": f"Referenced student group '{group_id}' does not exist",
        }), 400

    dept_id = data.get("department_id")
    if dept_id and not db.session.get(Department, dept_id):
        return jsonify({
            "success": False,
            "error": f"Referenced department '{dept_id}' does not exist",
        }), 400

    pref_room = data.get("preferred_room_id")
    if pref_room and not db.session.get(Room, pref_room):
        return jsonify({
            "success": False,
            "error": f"Referenced preferred room '{pref_room}' does not exist",
        }), 400

    try:
        enrollment = int(data["enrollment"])
        duration = int(data.get("duration", 1))
        if enrollment <= 0 or duration <= 0:
            return jsonify({
                "success": False,
                "error": "Enrollment and duration must be positive integers",
            }), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Enrollment and duration must be valid integers"}), 400

    try:
        course = Course(
            id=course_id,
            name=name,
            department_id=dept_id,
            faculty_id=faculty_id,
            student_group_id=group_id,
            enrollment=enrollment,
            duration=duration,
            is_lab=bool(data.get("is_lab", False)),
            preferred_time=data.get("preferred_time"),
            preferred_room_id=pref_room,
        )
        if "preferred_days" in data:
            course.preferred_days = data["preferred_days"]

        db.session.add(course)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Course created successfully",
            "course": course.to_dict(),
        }), 201
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while creating course"}), 500


@api_bp.route("/courses/<string:course_id>", methods=["PUT"])
def update_course(course_id: str):
    """Update an existing academic course."""
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({
            "success": False,
            "error": f"Course with ID '{course_id}' not found",
        }), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    if "name" in data and data["name"]:
        course.name = str(data["name"]).strip()

    if "faculty_id" in data:
        fac_id = str(data["faculty_id"]).strip()
        if not db.session.get(Faculty, fac_id):
            return jsonify({
                "success": False,
                "error": f"Referenced faculty '{fac_id}' does not exist",
            }), 400
        course.faculty_id = fac_id

    if "student_group_id" in data:
        group_id = str(data["student_group_id"]).strip()
        if not db.session.get(StudentGroup, group_id):
            return jsonify({
                "success": False,
                "error": f"Referenced student group '{group_id}' does not exist",
            }), 400
        course.student_group_id = group_id

    if "department_id" in data:
        dept_id = data["department_id"]
        if dept_id and not db.session.get(Department, dept_id):
            return jsonify({
                "success": False,
                "error": f"Referenced department '{dept_id}' does not exist",
            }), 400
        course.department_id = dept_id

    if "preferred_room_id" in data:
        pref_room = data["preferred_room_id"]
        if pref_room and not db.session.get(Room, pref_room):
            return jsonify({
                "success": False,
                "error": f"Referenced preferred room '{pref_room}' does not exist",
            }), 400
        course.preferred_room_id = pref_room

    if "enrollment" in data:
        try:
            enr = int(data["enrollment"])
            if enr <= 0:
                return jsonify({"success": False, "error": "Enrollment must be a positive integer"}), 400
            course.enrollment = enr
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Enrollment must be a valid integer"}), 400

    if "duration" in data:
        try:
            dur = int(data["duration"])
            if dur <= 0:
                return jsonify({"success": False, "error": "Duration must be a positive integer"}), 400
            course.duration = dur
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Duration must be a valid integer"}), 400

    if "is_lab" in data:
        course.is_lab = bool(data["is_lab"])

    if "preferred_days" in data:
        course.preferred_days = data["preferred_days"]

    if "preferred_time" in data:
        course.preferred_time = data["preferred_time"]

    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Course updated successfully",
            "course": course.to_dict(),
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while updating course"}), 500


@api_bp.route("/courses/<string:course_id>", methods=["DELETE"])
def delete_course(course_id: str):
    """Delete an academic course entity."""
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({
            "success": False,
            "error": f"Course with ID '{course_id}' not found",
        }), 404

    try:
        db.session.delete(course)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Course '{course_id}' deleted successfully",
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while deleting course"}), 500


# ============================================================================
# TIMETABLES CRUD & RETRIEVAL
# ============================================================================

@api_bp.route("/timetables", methods=["GET"])
def get_timetables():
    """Retrieve all generated timetables summary."""
    timetables = Timetable.query.order_by(Timetable.id.desc()).all()
    return jsonify({
        "success": True,
        "count": len(timetables),
        "timetables": [t.to_dict() for t in timetables],
    }), 200


@api_bp.route("/timetables/<int:timetable_id>", methods=["GET"])
@api_bp.route("/timetable/<int:timetable_id>", methods=["GET"])
def get_timetable(timetable_id: int):
    """Retrieve complete timetable metadata and scheduled slot assignments."""
    tt = db.session.get(Timetable, timetable_id)
    if not tt:
        return jsonify({
            "success": False,
            "error": f"Timetable with ID {timetable_id} not found",
        }), 404

    return jsonify({
        "success": True,
        "timetable": tt.to_dict(),
        "assignments": [a.to_dict() for a in tt.assignments],
    }), 200


@api_bp.route("/timetables/<int:timetable_id>", methods=["DELETE"])
@api_bp.route("/timetable/<int:timetable_id>", methods=["DELETE"])
def delete_timetable(timetable_id: int):
    """Delete a timetable and its cascading assignments."""
    tt = db.session.get(Timetable, timetable_id)
    if not tt:
        return jsonify({
            "success": False,
            "error": f"Timetable with ID {timetable_id} not found",
        }), 404

    try:
        db.session.delete(tt)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Timetable {timetable_id} deleted successfully",
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error while deleting timetable"}), 500


# ============================================================================
# CSP SCHEDULING ENGINE INTEGRATION
# ============================================================================

@api_bp.route("/schedule/generate", methods=["POST"])
def generate_schedule():
    """
    Generate an optimal conflict-free college timetable using the CSP engine.

    Workflow:
    1. Loads all Courses, Faculty, Classrooms, and Student Groups from database.
    2. Converts models to scheduler domain objects.
    3. Solves the scheduling problem via CSPScheduler (MRV + backtracking + soft scoring).
    4. Persists the Timetable session and Assignment records in an atomic transaction.
    5. Returns the complete generated timetable as JSON.
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name", "Master Generated Timetable")
    academic_term = data.get("academic_term", "Fall 2026")

    # 1. Fetch domain records from SQLite database
    courses_db = Course.query.all()
    faculty_db = Faculty.query.all()
    rooms_db = Room.query.all()
    student_groups_db = StudentGroup.query.all()

    if not courses_db:
        return jsonify({
            "success": False,
            "error": "No courses found in database to schedule. Please populate courses first.",
        }), 400

    if not rooms_db:
        return jsonify({
            "success": False,
            "error": "No classrooms found in database. Please populate classrooms first.",
        }), 400

    # 2. Convert models to domain representations
    domain_courses = [c.to_domain() for c in courses_db]
    domain_faculty = [f.to_domain() for f in faculty_db]
    domain_rooms = [r.to_domain() for r in rooms_db]
    domain_student_groups = [sg.to_domain() for sg in student_groups_db]

    # 3. Formulate Scheduling Problem
    problem = SchedulingProblem(
        courses=domain_courses,
        faculty=domain_faculty,
        rooms=domain_rooms,
        student_groups=domain_student_groups,
    )

    # 4. Invoke existing CSP Solver
    scheduler = CSPScheduler(problem=problem, enable_logging=False)
    result = scheduler.solve()

    if not result.success:
        return jsonify({
            "success": False,
            "error": "Scheduling failed: Problem is infeasible or over-constrained",
            "conflicts": result.conflicts,
            "statistics": result.statistics,
        }), 409

    # 5. Persist the generated schedule atomically
    try:
        timetable = Timetable(
            name=name,
            academic_term=academic_term,
            status="SCHEDULED",
            fitness_score=result.statistics.get("total_utility", 0.0),
        )
        db.session.add(timetable)
        db.session.flush()

        # Create Assignment records linked to Timetable
        for item in result.schedule:
            assignment = Assignment(
                timetable_id=timetable.id,
                course_id=item["course_id"],
                course_name=item["course_name"],
                faculty_id=item["faculty_id"],
                student_group_id=item["student_group_id"],
                room_id=item["room_id"],
                day=item["day"],
                start_time=item["start_time"],
                duration=item["duration"],
                is_lab=item.get("is_lab", False),
                enrollment=item.get("enrollment", 0),
                status="SCHEDULED",
            )
            db.session.add(assignment)

        db.session.commit()

        return jsonify({
            "success": True,
            "timetable_id": timetable.id,
            "status": timetable.status,
            "fitness_score": timetable.fitness_score,
            "statistics": result.statistics,
            "assignments": [a.to_dict() for a in timetable.assignments],
        }), 201

    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": "Database error while persisting timetable assignments",
        }), 500


# ============================================================================
# RESCHEDULING & CONFLICT NEGOTIATION
# ============================================================================

@api_bp.route("/schedule/reschedule", methods=["POST"])
def reschedule_conflict():
    """
    Request an alternative valid assignment for a course when a scheduling conflict occurs.

    Accepts:
    - course_id (str, required)
    - reason (str, optional: e.g. CLASSROOM_CAPACITY, FACULTY_UNAVAILABLE)
    - current_room_id, current_day, current_time (optional: conflicted slot to exclude)
    - timetable_id (optional: reference timetable to check against existing assignments)
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400

    course_id = str(data.get("course_id", "")).strip()
    if not course_id:
        return jsonify({"success": False, "error": "Missing required field: 'course_id'"}), 400

    course_model = db.session.get(Course, course_id)
    if not course_model:
        return jsonify({
            "success": False,
            "error": f"Course '{course_id}' not found",
        }), 404

    reason = data.get("reason", "UNSPECIFIED_CONFLICT")

    # Current candidate slot to exclude if provided
    cur_room = data.get("current_room_id") or data.get("room_id")
    cur_day = data.get("current_day") or data.get("day")
    cur_time = data.get("current_time") or data.get("start_time")

    excluded_candidates: Set[Tuple[str, str, str]] = set()
    if cur_room and cur_day and cur_time:
        excluded_candidates.add((str(cur_room), str(cur_day), str(cur_time)))

    # Fetch domain context
    courses_db = Course.query.all()
    faculty_db = Faculty.query.all()
    rooms_db = Room.query.all()
    student_groups_db = StudentGroup.query.all()

    domain_courses = [c.to_domain() for c in courses_db]
    domain_faculty = [f.to_domain() for f in faculty_db]
    domain_rooms = [r.to_domain() for r in rooms_db]
    domain_student_groups = [sg.to_domain() for sg in student_groups_db]

    problem = SchedulingProblem(
        courses=domain_courses,
        faculty=domain_faculty,
        rooms=domain_rooms,
        student_groups=domain_student_groups,
    )

    domain_course = course_model.to_domain()
    raw_domain = generate_course_domain(domain_course, problem)

    # Filter out excluded candidate slot
    valid_candidates = [
        val for val in raw_domain if (val.room_id, val.day, val.start_time) not in excluded_candidates
    ]

    # Check against current existing assignments from timetable if provided or latest
    timetable_id = data.get("timetable_id")
    current_assignments: List[DomainAssignment] = []

    if timetable_id:
        tt = db.session.get(Timetable, timetable_id)
        if tt:
            current_assignments = [
                a.to_domain() for a in tt.assignments if a.course_id != course_id
            ]
    else:
        latest_tt = Timetable.query.order_by(Timetable.id.desc()).first()
        if latest_tt:
            current_assignments = [
                a.to_domain() for a in latest_tt.assignments if a.course_id != course_id
            ]

    # Filter candidates by hard constraints against other scheduled courses
    consistent_candidates: List[ScheduleValue] = []
    for val in valid_candidates:
        consistent, _ = HardConstraintValidator.is_consistent(
            domain_course, val, current_assignments, problem
        )
        if consistent:
            consistent_candidates.append(val)

    if not consistent_candidates:
        return jsonify({
            "success": False,
            "course_id": course_id,
            "error": f"No alternative feasible slot found for course '{course_id}' under current constraints",
        }), 409

    # Score consistent candidates using soft-constraint utility
    weights = UtilityWeights()
    scored_candidates = []
    for val in consistent_candidates:
        score = SoftConstraintEvaluator.evaluate_assignment_utility(
            domain_course, val, current_assignments, problem, weights
        )
        scored_candidates.append((score, val))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_val = scored_candidates[0]

    return jsonify({
        "success": True,
        "course_id": course_id,
        "course_name": course_model.name,
        "reason": reason,
        "message": "Alternative assignment found successfully",
        "alternative": {
            "course_id": course_id,
            "course_name": course_model.name,
            "faculty_id": course_model.faculty_id,
            "student_group_id": course_model.student_group_id,
            "room_id": best_val.room_id,
            "day": best_val.day,
            "start_time": best_val.start_time,
            "duration": course_model.duration,
            "is_lab": course_model.is_lab,
            "enrollment": course_model.enrollment,
            "utility_score": round(best_score, 4),
        },
    }), 200
