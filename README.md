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

## 📂 Project Structure

```
College-Classroom-Scheduling-MAS/
├── README.md              # Project documentation
├── .gitignore             # Git ignore patterns
├── requirements.txt       # Project dependencies
├── config.py              # Configuration settings
├── run.py                 # Application entry point
├── agents/                # SPADE Multi-Agent System (Phase 3)
│   ├── __init__.py        # Package exports
│   ├── base_agent.py      # BaseAgent with identity & logging
│   ├── communication.py   # Message protocol, performatives & logger
│   ├── department_agent.py # DepartmentAgent
│   ├── faculty_agent.py   # FacultyAgent
│   ├── classroom_agent.py # ClassroomAgent
│   ├── student_group_agent.py # StudentGroupAgent
│   ├── timetable_coordinator.py # TimetableCoordinatorAgent
│   └── demo_agents.py     # Interactive MAS demonstration scenarios
├── scheduler/             # CSP Scheduling Solver (Phase 2)
│   ├── __init__.py        # Solver exports
│   ├── domain.py          # Domain dataclasses (Course, Faculty, Room, etc.)
│   ├── constraints.py     # Hard (H1-H8) and Soft (S1-S4) constraints
│   ├── csp_solver.py      # CSPScheduler with MRV & backtracking
│   └── demo.py            # CSP solver benchmark demo
├── app/                   # Flask web application
├── database/              # DB initialization & migrations
├── tests/                 # 50+ Unit & integration tests
│   ├── test_setup.py
│   ├── test_csp_solver.py
│   ├── test_base_agent.py
│   ├── test_agent_communication.py
│   ├── test_faculty_agent.py
│   ├── test_classroom_agent.py
│   ├── test_student_group_agent.py
│   ├── test_department_agent.py
│   └── test_coordinator_agent.py
└── docs/                  # Project specifications & reports
```

---

## 📄 License
Academic Final Year Project - All Rights Reserved.

