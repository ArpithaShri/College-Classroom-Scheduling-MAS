# College Classroom Scheduling System Using Multi-Agent Systems (MAS)

A final-year engineering project that automates timetable generation and classroom scheduling using a Multi-Agent System (MAS) powered by SPADE and Constraint Satisfaction Problem (CSP) solvers.

---

## 📌 Project Overview

College classroom scheduling is an NP-hard combinatorial optimization problem characterized by competing faculty preferences, room capacity restrictions, departmental curricula, and student cohort constraints. This system decentralizes schedule negotiation among five autonomous SPADE agents and solves hard/soft constraints using backtracking CSP with Minimum Remaining Values (MRV) and forward checking.

---

## 🏛️ System Architecture

### Multi-Agent System (SPADE Framework)
1. **Department Agent**: Manages curriculum requirements, course offerings, and weekly credit hours.
2. **Faculty Agent**: Negotiates faculty time availability, course proficiencies, and workload bounds.
3. **Classroom Agent**: Tracks room capacity, lab equipment, projector availability, and physical room constraints.
4. **Student Group Agent**: Prevents cohort overlaps, manages section sizes, and enforces daily study load limits.
5. **Timetable Coordinator Agent**: Aggregates constraints, runs CSP/MRV scheduling engine, and resolves inter-agent conflicts.

### Backend & Storage
- **Flask**: REST API server and management portal.
- **Flask-SQLAlchemy / SQLite**: Relational storage for entities, preferences, assignments, and audit logs.
- **CSP Solver**: Constraint Satisfaction Problem engine using MRV heuristic and forward checking.

---

## 🚀 Setup & Installation (Phase 1)

### Prerequisites
- Python 3.10+ (Verified on Python 3.14)
- Git

### Quickstart
1. **Clone Repository**:
   ```bash
   git clone https://github.com/ArpithaShri/College-Classroom-Scheduling-MAS.git
   cd College-Classroom-Scheduling-MAS
   ```

2. **Create and Activate Virtual Environment**:
   ```powershell
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Verification Tests**:
   ```bash
   pytest
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
├── app/                   # Flask web application
│   ├── __init__.py        # App factory
│   ├── models.py          # Database models (placeholder)
│   ├── routes/            # Blueprint routes
│   │   └── __init__.py
│   ├── static/            # Static assets (CSS, JS)
│   │   ├── css/
│   │   └── js/
│   └── templates/         # HTML templates
├── agents/                # SPADE Multi-Agent System
│   └── __init__.py
├── scheduler/             # CSP Scheduling Solver
│   └── __init__.py
├── database/              # DB initialization & migrations
│   └── __init__.py
├── tests/                 # Unit & integration test suite
│   ├── __init__.py
│   └── test_setup.py      # Foundation verification tests
└── docs/                  # Project specifications & reports
```

---

## 📄 License
Academic Final Year Project - All Rights Reserved.
