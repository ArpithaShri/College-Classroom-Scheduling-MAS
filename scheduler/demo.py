"""Demonstration and trace execution for the CSP Scheduling Engine.

Runs representative scheduling scenarios showing:
- Scenario 1: Multi-course timetable generation with MRV, room sizing, and lab constraints.
- Scenario 2: Constrained scheduling requiring search exploration, constraint rejection, and backtracking.
"""

import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scheduler import (
    SchedulingProblem,
    Course,
    Faculty,
    Room,
    StudentGroup,
    TimeSlot,
    CSPScheduler,
    UtilityWeights,
)


def run_scenario_1():
    print("=" * 78)
    print("  SCENARIO 1: MULTI-COURSE TIMETABLE GENERATION (LECTURES & 2-HOUR LABS)")
    print("=" * 78)

    rooms_data = [
        {"id": "R101", "name": "AB1-101 (Lecture Hall)", "capacity": 60, "room_type": "classroom"},
        {"id": "R102", "name": "AB1-102 (Small Class)", "capacity": 35, "room_type": "classroom"},
        {"id": "LAB01", "name": "Computing Lab 1", "capacity": 40, "room_type": "lab"},
    ]

    faculty_data = [
        {
            "id": "F001",
            "name": "Dr. Kumar",
            "available_slots": [
                ("Monday", "09:00"), ("Monday", "10:00"), ("Monday", "11:00"),
                ("Tuesday", "09:00"), ("Tuesday", "10:00"),
            ],
            "preferred_slots": [("Monday", "09:00"), ("Tuesday", "09:00")],
        },
        {
            "id": "F002",
            "name": "Prof. Sharma",
            "available_slots": [
                ("Monday", "09:00"), ("Monday", "10:00"), ("Monday", "11:00"),
                ("Tuesday", "10:00"), ("Tuesday", "11:00"),
            ],
            "preferred_slots": [("Monday", "10:00")],
        },
        {
            "id": "F003",
            "name": "Dr. Anita",
            "available_slots": [
                ("Monday", "09:00"), ("Monday", "10:00"), ("Monday", "11:00"),
                ("Tuesday", "09:00"), ("Tuesday", "10:00"),
            ],
            "preferred_slots": [("Monday", "11:00")],
        },
    ]

    student_groups_data = [
        {"id": "CSE-A", "name": "CSE Section A", "existing_schedule": []},
        {"id": "CSE-B", "name": "CSE Section B", "existing_schedule": []},
    ]

    courses_data = [
        {
            "id": "CS301",
            "name": "Machine Learning",
            "faculty_id": "F001",
            "student_group_id": "CSE-A",
            "enrollment": 55,
            "duration": 1,
            "is_lab": False,
        },
        {
            "id": "CS302",
            "name": "Computer Networks",
            "faculty_id": "F002",
            "student_group_id": "CSE-A",
            "enrollment": 55,
            "duration": 1,
            "is_lab": False,
        },
        {
            "id": "CS303",
            "name": "AI Systems Lab",
            "faculty_id": "F001",
            "student_group_id": "CSE-B",
            "enrollment": 35,
            "duration": 2,  # 2-hour lab
            "is_lab": True,
        },
        {
            "id": "CS304",
            "name": "Database Management",
            "faculty_id": "F003",
            "student_group_id": "CSE-B",
            "enrollment": 30,
            "duration": 1,
            "is_lab": False,
        },
    ]

    days = ["Monday", "Tuesday"]
    time_slots = ["09:00", "10:00", "11:00"]

    problem = SchedulingProblem.from_dict_data(
        courses_data=courses_data,
        faculty_data=faculty_data,
        rooms_data=rooms_data,
        student_groups_data=student_groups_data,
        days=days,
        time_slots=time_slots,
    )

    scheduler = CSPScheduler(problem=problem, enable_logging=False)
    result = scheduler.solve()

    print("\n--- EXECUTION TRACE ---")
    for entry in scheduler.trace_log:
        print(f"  {entry}")

    print("\n--- RESULTS & METRICS ---")
    print(f"  Status:               {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  Total Variables:      {result.statistics['variables']}")
    print(f"  Assignments Tried:    {result.statistics['assignments_tried']}")
    print(f"  Backtrack Steps:      {result.statistics['backtracks']}")
    print(f"  Search Time:          {result.statistics['search_time_sec'] * 1000:.3f} ms")
    print(f"  Total Utility Score:  {result.statistics.get('total_utility', 0.0)}")

    if result.success:
        print("\n--- FINAL SCHEDULE ---")
        header = f"  {'DAY':<10} | {'TIME':<12} | {'ROOM':<8} | {'COURSE':<22} | {'FACULTY':<12} | {'GROUP':<8} | {'TYPE'}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for a in result.schedule:
            c_type = "LAB" if a["is_lab"] else "LECTURE"
            slot_str = f"{a['start_time']} ({a['duration']}h)"
            print(
                f"  {a['day']:<10} | {slot_str:<12} | {a['room_id']:<8} | {a['course_name']:<22} | {a['faculty_id']:<12} | {a['student_group_id']:<8} | {c_type}"
            )
        print("  " + "-" * (len(header) - 2))


def run_scenario_2():
    print("\n" + "=" * 78)
    print("  SCENARIO 2: CONSTRAINED COMPETITION & BACKTRACKING TRACE")
    print("=" * 78)

    # 2 courses, 1 room, 2 slots: F1 prefers slot 09:00, but F2 ONLY has slot 09:00.
    # When solver tries F1 in 09:00, F2 has no slots left -> triggers forward check / backtrack!
    courses_data = [
        {"id": "CS401", "name": "Cloud Computing", "faculty_id": "F_ALICE", "student_group_id": "CSE-A", "enrollment": 40},
        {"id": "CS402", "name": "Cyber Security", "faculty_id": "F_BOB", "student_group_id": "CSE-B", "enrollment": 40},
    ]

    faculty_data = [
        {
            "id": "F_ALICE",
            "name": "Dr. Alice",
            "available_slots": [("Monday", "09:00"), ("Monday", "10:00")],
            "preferred_slots": [("Monday", "09:00")],
        },
        {
            "id": "F_BOB",
            "name": "Dr. Bob",
            "available_slots": [("Monday", "09:00")],  # Only available at 09:00
            "preferred_slots": [("Monday", "09:00")],
        },
    ]

    rooms_data = [
        {"id": "R201", "name": "Seminar Room", "capacity": 50, "room_type": "classroom"},
    ]

    student_groups_data = [
        {"id": "CSE-A", "name": "CSE Section A"},
        {"id": "CSE-B", "name": "CSE Section B"},
    ]

    problem = SchedulingProblem.from_dict_data(
        courses_data=courses_data,
        faculty_data=faculty_data,
        rooms_data=rooms_data,
        student_groups_data=student_groups_data,
        days=["Monday"],
        time_slots=["09:00", "10:00"],
    )

    scheduler = CSPScheduler(problem=problem, enable_logging=False)
    result = scheduler.solve()

    print("\n--- EXECUTION TRACE ---")
    for entry in scheduler.trace_log:
        print(f"  {entry}")

    print("\n--- RESULTS & METRICS ---")
    print(f"  Status:               {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  Total Variables:      {result.statistics['variables']}")
    print(f"  Assignments Tried:    {result.statistics['assignments_tried']}")
    print(f"  Backtrack Steps:      {result.statistics['backtracks']}")
    print(f"  Search Time:          {result.statistics['search_time_sec'] * 1000:.3f} ms")

    if result.success:
        print("\n--- FINAL SCHEDULE ---")
        header = f"  {'DAY':<10} | {'TIME':<12} | {'ROOM':<8} | {'COURSE':<20} | {'FACULTY':<10} | {'GROUP':<8}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for a in result.schedule:
            slot_str = f"{a['start_time']} ({a['duration']}h)"
            print(
                f"  {a['day']:<10} | {slot_str:<12} | {a['room_id']:<8} | {a['course_name']:<20} | {a['faculty_id']:<10} | {a['student_group_id']:<8}"
            )
        print("  " + "-" * (len(header) - 2))


def run_scenario_3():
    print("\n" + "=" * 78)
    print("  SCENARIO 3: DEAD-END AVOIDANCE & GENUINE BACKTRACKING TRACE")
    print("=" * 78)

    # C1 and C2 both have 2 slots in initial domain (Monday 09:00, Monday 10:00).
    # Both want Room R301.
    # C1 is evaluated first (e.g. higher enrollment) and tries 09:00.
    # C2 also requires Room R301. C3 requires Room R301 at 10:00 strictly.
    # When C1 takes 09:00, C2 is forced to 10:00, but C3 has only 10:00 -> wipeout -> backtrack!

    courses_data = [
        {"id": "CS501", "name": "Deep Learning", "faculty_id": "F_D1", "student_group_id": "G1", "enrollment": 45},
        {"id": "CS502", "name": "Big Data", "faculty_id": "F_D2", "student_group_id": "G2", "enrollment": 40},
        {"id": "CS503", "name": "Embedded Systems", "faculty_id": "F_D3", "student_group_id": "G3", "enrollment": 35},
    ]

    faculty_data = [
        {"id": "F_D1", "name": "Dr. D1", "available_slots": [("Monday", "09:00"), ("Monday", "10:00")]},
        {"id": "F_D2", "name": "Dr. D2", "available_slots": [("Monday", "09:00"), ("Monday", "10:00")]},
        {"id": "F_D3", "name": "Dr. D3", "available_slots": [("Monday", "10:00")]},  # Strictly 10:00 only
    ]

    rooms_data = [
        {"id": "R301", "name": "Special Lab", "capacity": 50, "room_type": "classroom"},
    ]

    student_groups_data = [
        {"id": "G1", "name": "Group 1"},
        {"id": "G2", "name": "Group 2"},
        {"id": "G3", "name": "Group 3"},
    ]

    problem = SchedulingProblem.from_dict_data(
        courses_data=courses_data,
        faculty_data=faculty_data,
        rooms_data=rooms_data,
        student_groups_data=student_groups_data,
        days=["Monday"],
        time_slots=["09:00", "10:00"],  # Only 2 slots for 3 courses -> will show search exhaustion/backtracking
    )

    scheduler = CSPScheduler(problem=problem, enable_logging=False)
    result = scheduler.solve()

    print("\n--- EXECUTION TRACE ---")
    for entry in scheduler.trace_log:
        print(f"  {entry}")

    print("\n--- RESULTS & METRICS ---")
    print(f"  Status:               {'SUCCESS' if result.success else 'FAILED (Expected: 3 courses into 2 slots)'}")
    print(f"  Total Variables:      {result.statistics['variables']}")
    print(f"  Assignments Tried:    {result.statistics['assignments_tried']}")
    print(f"  Backtrack Steps:      {result.statistics['backtracks']}")
    print(f"  Search Time:          {result.statistics['search_time_sec'] * 1000:.3f} ms")


if __name__ == "__main__":
    run_scenario_1()
    run_scenario_2()
    run_scenario_3()
