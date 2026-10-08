# College Classroom Scheduling System Using Multi-Agent Systems (MAS)

A final-year engineering project that automates timetable generation and classroom scheduling using a Multi-Agent System (MAS) powered by SPADE and Constraint Satisfaction Problem (CSP) solvers.

---

## 📌 Project Overview

College classroom scheduling is an NP-hard combinatorial optimization problem characterized by competing faculty preferences, room capacity restrictions, departmental curricula, and student cohort constraints. This system decentralizes schedule negotiation among five autonomous SPADE agents and solves hard/soft constraints using backtracking CSP with Minimum Remaining Values (MRV) and forward checking.

---

## 🏛️ System Architecture

### Multi-Agent System (SPADE Framework)
1. **Department Agent** (`DepartmentAgent`): Maintains course requirements, submits scheduling requests (`REQUEST`), tracks scheduled vs. pending/failed courses.
2. **Faculty Agent** (`FacultyAgent`): Local knowledge of instructor availability, preferences, and teaching workload; detects double-booking and validates/rejects proposals.
3. **Classroom Agent** (`ClassroomAgent`): Local knowledge of room capacity, room type (classroom/lab), and occupancy; prevents room double-booking and rejects insufficient capacity.
4. **Student Group Agent** (`StudentGroupAgent`): Local knowledge of student cohort timetable; detects student timetable clashes and returns conflicts (`CONFLICT`).
5. **Timetable Coordinator Agent** (`TimetableCoordinatorAgent`): Orchestrates decentralized negotiation across agents, consults CSP solver (`scheduler.CSPScheduler`) for alternative domain values, triggers dynamic rescheduling (`RESCHEDULE`), and confirms final schedules.

### Backend & Storage
- **SPADE (v4.1+)**: Genuine Multi-Agent framework using FIPA-compliant ACL messaging over XMPP.
- **CSP Engine**: Constraint Satisfaction Problem engine using MRV heuristic, forward checking, and multi-criteria utility scoring.
- **Flask**: REST API server and management portal (Phases 4-5).
- **Flask-SQLAlchemy / SQLite**: Relational storage for entities, preferences, assignments, and audit logs.

---

## ⚡ Multi-Agent Demonstration & Testing (Phase 3)

### Running the MAS Demos
Execute the interactive demonstration showing Happy-Path negotiation, Classroom Capacity conflict resolution, and Student Timetable clash rescheduling:
```powershell
python agents/demo_agents.py
```

### Running Test Suite
```powershell
pytest -v
```

---

## 🌐 XMPP / SPADE Runtime Configuration

- **Local Development / Offline Mode**: Uses SPADE's agent abstractions and in-memory event dispatching alongside optional in-process `pyjabber` local server for complete zero-dependency offline development.
- **External XMPP Server**: If using an external Prosody / Ejabberd server, configure `XMPP_SERVER` and `XMPP_PASSWORD` in `config.py` or `.env`.

---

---

## 🚀 Flask REST API (Phase 4 Step 2)

### Starting the Flask Server
```powershell
python run.py
```
The server starts by default at `http://127.0.0.1:5000` with the SQLite database automatically initialized and seeded.

### Base URL
`http://127.0.0.1:5000/api`

### Available Endpoints

| Resource | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **Health** | `GET` | `/api/health` | API status and liveness check |
| **Departments** | `GET`, `POST` | `/api/departments` | List all / Create department |
| | `GET`, `PUT`, `DELETE` | `/api/departments/<id>` | Read, update, delete department |
| **Faculty** | `GET`, `POST` | `/api/faculty` | List all / Create faculty member |
| | `GET`, `PUT`, `DELETE` | `/api/faculty/<id>` | Read, update, delete faculty member |
| **Classrooms** | `GET`, `POST` | `/api/classrooms` | List all / Create classroom or lab |
| | `GET`, `PUT`, `DELETE` | `/api/classrooms/<id>` | Read, update, delete classroom |
| **Student Groups** | `GET`, `POST` | `/api/student-groups` | List all / Create student cohort |
| | `GET`, `PUT`, `DELETE` | `/api/student-groups/<id>` | Read, update, delete student group |
| **Courses** | `GET`, `POST` | `/api/courses` | List all / Create course requirement |
| | `GET`, `PUT`, `DELETE` | `/api/courses/<id>` | Read, update, delete course |
| **Timetables** | `GET` | `/api/timetables` | List all generated timetables |
| | `GET`, `DELETE` | `/api/timetables/<id>` | Retrieve full timetable / Delete timetable |
| **Scheduling** | `POST` | `/api/schedule/generate` | Generate optimal schedule with CSP engine |
| **Rescheduling** | `POST` | `/api/schedule/reschedule` | Propose alternative slot on conflict |

### Example: Generate a Timetable
**Request:**
```http
POST /api/schedule/generate
Content-Type: application/json

{
    "name": "Fall 2026 CS Timetable",
    "academic_term": "Fall 2026"
}
```

**Response (201 Created):**
```json
{
    "success": true,
    "timetable_id": 1,
    "status": "SCHEDULED",
    "fitness_score": 8.3738,
    "statistics": {
        "variables": 4,
        "assignments_tried": 4,
        "backtracks": 0,
        "search_time_sec": 0.0099,
        "total_utility": 8.3738
    },
    "assignments": [
        {
            "course_id": "CS301",
            "course_name": "Machine Learning",
            "faculty_id": "F001",
            "student_group_id": "CSE-A",
            "room_id": "R102",
            "day": "Tuesday",
            "start_time": "10:00",
            "duration": 1,
            "is_lab": false,
            "enrollment": 55,
            "status": "SCHEDULED"
        }
    ]
}
```

### Example: Reschedule on Conflict
**Request:**
```http
POST /api/schedule/reschedule
Content-Type: application/json

{
    "course_id": "CS301",
    "reason": "CLASSROOM_CAPACITY",
    "current_room_id": "R101",
    "current_day": "Monday",
    "current_time": "10:00"
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "course_id": "CS301",
    "course_name": "Machine Learning",
    "reason": "CLASSROOM_CAPACITY",
    "message": "Alternative assignment found successfully",
    "alternative": {
        "course_id": "CS301",
        "course_name": "Machine Learning",
        "room_id": "R102",
        "day": "Tuesday",
        "start_time": "10:00",
        "duration": 1,
        "utility_score": 2.1769
    }
}
```

---

## 📂 Project Structure

```
College-Classroom-Scheduling-MAS/
├── README.md              # Project documentation
├── .gitignore             # Git ignore patterns
├── requirements.txt       # Project dependencies
├── config.py              # Configuration settings
├── run.py                 # Application entry point
├── api/                   # Flask REST API layer (Phase 4 Step 2)
│   ├── __init__.py        # Blueprint definition & CORS error handlers
│   └── routes.py          # CRUD & scheduling endpoints
├── app/                   # Flask application core & SQLAlchemy models
│   ├── __init__.py        # App factory
│   └── models.py          # Relational ORM models
├── database/              # SQLite database management & seed data
├── agents/                # SPADE Multi-Agent System (Phase 3)
├── scheduler/             # CSP Scheduling Solver (Phase 2)
├── tests/                 # 70+ Unit, integration & API test suites
└── docs/                  # Project specifications & reports
```

---

## 📄 License
Academic Final Year Project - All Rights Reserved.

